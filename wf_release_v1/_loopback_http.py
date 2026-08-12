"""Pinned loopback JSON transport shared by discovery and readiness polling."""

from __future__ import annotations

from http.client import HTTPConnection, HTTPException
import ipaddress
import socket
import threading
import time
from typing import Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .canonical import load_json_strict_bytes
from .errors import ReleaseError


_MAX_HTTP_BYTES: Final = 256 * 1024


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


def read_loopback_json(
    url: str,
    timeout_seconds: float,
    *,
    expected_path: str,
    label: str,
    retry_statuses: frozenset[int] = frozenset(),
) -> object:
    """Read one bounded JSON response from a DNS-pinned loopback endpoint."""
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


def wait_health_ready(url: str, timeout_seconds: float) -> None:
    """Wait within one total budget for health contract v1 readiness."""
    total = _timeout(timeout_seconds)
    _validated_url(url, "/healthz", "healthUrl")
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
        return
