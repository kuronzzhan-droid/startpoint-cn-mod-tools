"""Pinned local JSON transport shared by discovery and readiness polling."""

from __future__ import annotations

from http.client import HTTPConnection, HTTPException
import ipaddress
import errno
import re
import socket
import threading
import time
from collections.abc import Mapping
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .canonical import load_json_strict_bytes
from .errors import ReleaseError


_MAX_HTTP_BYTES: Final = 256 * 1024
_OPERATION_ID: Final = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{32}")
_RFC1918: Final = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


def _schema(label: str, message: str) -> ReleaseError:
    return ReleaseError("WFREL_SCHEMA_INVALID", message, {"label": label})


def _unavailable(
    label: str,
    message: str,
    *,
    retryable: bool,
    status: int | None = None,
) -> ReleaseError:
    details: dict[str, object] = {"label": label, "retryable": retryable}
    if status is not None:
        details["status"] = status
    return ReleaseError("WFREL_REQUIRE_TARGET", message, details)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        del request, file_pointer, code, message, headers, new_url
        return None


class _PinnedHTTPConnection(HTTPConnection):
    def __init__(self, host: str, *, pinned_host: str, **kwargs) -> None:
        super().__init__(host, **kwargs)
        self._pinned_host = pinned_host
        self._connected_socket: socket.socket | None = None

    def connect(self) -> None:
        original_host = self.host
        try:
            self.host = self._pinned_host
            super().connect()
            self._connected_socket = self.sock
        finally:
            self.host = original_host

    def abort(self) -> None:
        if self._connected_socket is not None:
            try:
                self._connected_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.close()


class _PinnedHTTPHandler(HTTPHandler):
    def __init__(self, pinned_host: str) -> None:
        super().__init__()
        self._pinned_host = pinned_host
        self._connection: _PinnedHTTPConnection | None = None

    def http_open(self, request):
        def connection(host: str, **kwargs) -> HTTPConnection:
            self._connection = _PinnedHTTPConnection(
                host, pinned_host=self._pinned_host, **kwargs
            )
            return self._connection

        return self.do_open(connection, request)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.abort()


def _validated_url(url: str, expected_path: str, label: str):
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise _schema(label, "local URL port is invalid") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != expected_path
    ):
        raise _schema(label, "local URL does not match its required endpoint")
    return parsed, port or 80


def _timeout(value: object) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not 0 < value <= 30
    ):
        raise _schema("timeoutSeconds", "probe timeout is invalid")
    return float(value)


def _approved_numeric_host(host: object) -> bool:
    if not isinstance(host, str):
        return False
    try:
        address = ipaddress.ip_address(host)
    except (TypeError, ValueError):
        return False
    effective = (
        address.ipv4_mapped
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None
        else address
    )
    private_v4 = isinstance(effective, ipaddress.IPv4Address) and any(
        effective in network for network in _RFC1918
    )
    return host == address.compressed and (effective.is_loopback or private_v4)


def require_tcp_endpoint_unbound(host: str, port: int, *, label: str) -> None:
    """Prove one exact local bind is available without accepting a foreign listener."""
    if (
        not isinstance(host, str)
        or not host.isascii()
        or type(port) is not int
        or not 0 < port <= 65535
        or not isinstance(label, str)
        or not label
    ):
        raise _schema(label if isinstance(label, str) and label else "endpoint", "local bind is invalid")
    wildcard = host in {"0.0.0.0", "::"}
    if not wildcard and not _approved_numeric_host(host):
        raise _schema(label, "local bind host is invalid")
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    endpoint = (host, port, 0, 0) if family == socket.AF_INET6 else (host, port)
    listener = socket.socket(family, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(endpoint)
    except OSError as error:
        occupied = error.errno in {
            errno.EADDRINUSE,
            getattr(errno, "WSAEADDRINUSE", 10048),
        } or getattr(error, "winerror", None) == 10048
        if occupied:
            raise ReleaseError(
                "WFREL_PROCESS_RUNNING",
                "managed endpoint is already occupied",
                {"label": label},
            ) from None
        raise ReleaseError(
            "WFREL_PLATFORM_INVALID",
            "managed endpoint is not an available local bind",
            {"label": label},
        ) from None
    finally:
        listener.close()


def require_local_address(host: str, *, label: str) -> None:
    """Prove a declared public address belongs to a local network interface."""
    if not isinstance(label, str) or not label or not _approved_numeric_host(host):
        raise _schema(label if isinstance(label, str) and label else "address", "local address is invalid")
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    endpoint = (host, 0, 0, 0) if family == socket.AF_INET6 else (host, 0)
    probe = socket.socket(family, socket.SOCK_STREAM)
    try:
        probe.bind(endpoint)
    except OSError:
        raise ReleaseError(
            "WFREL_PLATFORM_INVALID",
            "declared public address is not assigned to this host",
            {"label": label},
        ) from None
    finally:
        probe.close()


def require_endpoint_unbound(origin: str) -> None:
    """Prove the target HTTP origin is an unoccupied local endpoint."""
    parsed, port = _validated_url(origin, "", "serverUrl")
    host = "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname
    if host is None:  # pragma: no cover - guarded by URL validation
        raise _schema("serverUrl", "local URL host is invalid")
    require_tcp_endpoint_unbound(host, port, label="http")


def _validated_managed_bindings(value: Mapping[str, object]) -> dict[str, object]:
    if set(value) != {"http", "session", "cdnBaseUrl"}:
        raise _schema("health", "managed health bindings are invalid")
    http = value.get("http")
    session = value.get("session")
    cdn_base_url = value.get("cdnBaseUrl")
    if (
        not isinstance(http, dict)
        or set(http) != {"host", "port", "publicHost"}
        or http.get("host") != "0.0.0.0"
        or type(http.get("port")) is not int
        or not 0 < http["port"] <= 65535
        or not isinstance(http.get("publicHost"), str)
        or ":" in http["publicHost"]
        or not _approved_numeric_host(http["publicHost"])
        or not isinstance(session, dict)
        or set(session) != {"host", "port", "publicHost"}
        or session.get("host") != "0.0.0.0"
        or type(session.get("port")) is not int
        or not 0 < session["port"] <= 65535
        or session.get("publicHost") != http["publicHost"]
        or http["port"] == session["port"]
        or cdn_base_url != f"http://{http['publicHost']}:{http['port']}/patch/cn"
    ):
        raise _schema("health", "managed health bindings are invalid")
    return {
        "http": dict(http),
        "session": dict(session),
        "cdnBaseUrl": cdn_base_url,
    }


def read_loopback_json(
    url: str,
    timeout_seconds: float,
    *,
    expected_path: str,
    label: str,
    retry_statuses: frozenset[int] = frozenset(),
) -> object:
    """Read one bounded JSON response from a DNS-pinned local endpoint."""
    parsed, port = _validated_url(url, expected_path, f"{label}Url")
    deadline = time.monotonic() + _timeout(timeout_seconds)
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        addresses: list[tuple] = []
        resolution_error: list[OSError] = []

        def resolve() -> None:
            try:
                addresses.extend(
                    socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
                )
            except OSError as error:
                resolution_error.append(error)

        resolver = threading.Thread(target=resolve, daemon=True)
        resolver.start()
        resolver.join(max(0.0, deadline - time.monotonic()))
        if resolver.is_alive():
            raise TimeoutError("local hostname resolution timed out")
        if resolution_error:
            raise resolution_error[0]
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
            effective = (
                ip.ipv4_mapped
                if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped
                else ip
            )
            if not effective.is_loopback:
                raise _schema(f"{label}Url", "local hostname does not resolve only to loopback")
        if not addresses:
            raise OSError("local hostname has no addresses")
        pinned_host = addresses[0][4][0].split("%", 1)[0]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("local request timeout elapsed during resolution")
        handler = _PinnedHTTPHandler(pinned_host)
        timer = threading.Timer(remaining, handler.close)
        timer.daemon = True
        timer.start()
        try:
            with build_opener(ProxyHandler({}), handler, _NoRedirect()).open(
                request, timeout=remaining
            ) as response:
                if response.status != 200:
                    raise _unavailable(
                        label,
                        "target endpoint request failed",
                        retryable=False,
                        status=response.status,
                    )
                if response.headers.get_content_type() != "application/json":
                    raise _schema(label, "target endpoint content type is invalid")
                chunks: list[bytes] = []
                size = 0
                while size <= _MAX_HTTP_BYTES:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("local request timeout elapsed while reading")
                    chunk = response.read1(min(64 * 1024, _MAX_HTTP_BYTES + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                raw = b"".join(chunks)
                declared = response.headers.get("Content-Length")
                if declared is not None and (
                    not declared.isdecimal() or int(declared) != len(raw)
                ):
                    raise _schema(label, "target endpoint body is truncated")
        finally:
            timer.cancel()
            handler.close()
    except ReleaseError:
        raise
    except HTTPError as error:
        retryable = error.code in retry_statuses
        status = error.code
        error.close()
        raise _unavailable(
            label,
            "target endpoint is unavailable",
            retryable=retryable,
            status=status,
        ) from error
    except (HTTPException, URLError, OSError, TimeoutError, socket.gaierror) as error:
        raise _unavailable(
            label, "target endpoint is unavailable", retryable=True
        ) from error
    if len(raw) > _MAX_HTTP_BYTES:
        raise _schema(label, "target endpoint exceeds the size limit")
    try:
        return load_json_strict_bytes(raw, label=label)
    except ReleaseError as error:
        raise ReleaseError(error.code, error.message, error.details) from None


def wait_health_ready(
    url: str,
    timeout_seconds: float,
    *,
    expected_operation_id: str | None = None,
    expected_pid: int | None = None,
    expected_bindings: Mapping[str, object] | None = None,
) -> None:
    """Wait within one total budget for health contract v1 readiness."""
    total = _timeout(timeout_seconds)
    _validated_url(url, "/healthz", "healthUrl")
    expected_launch: dict[str, object] | None = None
    if expected_operation_id is not None or expected_pid is not None or expected_bindings is not None:
        if (
            expected_operation_id is None
            or type(expected_pid) is not int
            or expected_pid <= 0
            or not isinstance(expected_bindings, Mapping)
        ):
            raise _schema("health", "managed health expectation is invalid")
        if _OPERATION_ID.fullmatch(expected_operation_id) is None:
            raise _schema("health", "managed operation identity is invalid")
        bindings = _validated_managed_bindings(expected_bindings)
        expected_launch = {
            "operationId": expected_operation_id,
            "pid": expected_pid,
            **bindings,
        }
    deadline = time.monotonic() + total
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _unavailable("health", "target health did not become ready", retryable=False)
        try:
            value = read_loopback_json(
                url,
                remaining,
                expected_path="/healthz",
                label="health",
                retry_statuses=frozenset({503}),
            )
        except ReleaseError as error:
            if error.code != "WFREL_REQUIRE_TARGET" or error.details.get("retryable") is not True:
                raise
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
            continue
        if not isinstance(value, dict):
            raise _schema("health", "health response must be an object")
        version = value.get("contractVersion")
        status = value.get("status")
        if type(version) is not int or version != 1 or not isinstance(status, str):
            raise _schema("health", "health response contract is invalid")
        if status != "ready":
            raise _schema("health", "successful health response is not ready")
        if expected_launch is not None and value.get("managedLaunch") != expected_launch:
            raise ReleaseError(
                "WFREL_PROCESS_IDENTITY",
                "health endpoint does not belong to the managed launch",
            )
        if expected_launch is not None:
            services = value.get("services")
            if (
                not isinstance(services, dict)
                or services.get("http") is not True
                or services.get("tcp") is not True
            ):
                raise ReleaseError(
                    "WFREL_REQUIRE_TARGET",
                    "managed HTTP and TCP services are not both ready",
                    {"label": "health.services", "retryable": False},
                )
        return
