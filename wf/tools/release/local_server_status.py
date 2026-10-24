#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed CN listener status probe for stopped-server publication."""
from __future__ import annotations

import errno
import os
import socket
from pathlib import Path


class ServerStatusError(RuntimeError):
    """The configured CN endpoint could not be classified safely."""


def _endpoint(repo_root: Path) -> tuple[str, int]:
    values: dict[str, str] = {}
    try:
        lines = (Path(repo_root) / ".env").read_text(
            encoding="utf-8"
        ).splitlines()
    except FileNotFoundError:
        lines = []
    except OSError as error:
        raise ServerStatusError(str(error)) from error
    for line in lines:
        token = line.strip()
        if not token or token.startswith("#") or "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    host = os.environ.get("CN_LISTEN_HOST")
    if host is None:
        host = values.get("CN_LISTEN_HOST", "127.0.0.1")
    port_token = os.environ.get("CN_LISTEN_PORT")
    if port_token is None:
        port_token = values.get("CN_LISTEN_PORT", "8001")
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    try:
        port = int(port_token)
    except (TypeError, ValueError) as error:
        raise ServerStatusError(f"invalid port {port_token!r}") from error
    if not host or not 1 <= port <= 65535:
        raise ServerStatusError(f"invalid endpoint {host!r}:{port}")
    return host, port


def _windows_listening_ports() -> set[int]:
    import ctypes
    from ctypes import wintypes

    iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
    ERROR_INSUFFICIENT_BUFFER = 122
    TCP_TABLE_OWNER_PID_LISTENER = 3

    class _Row4(ctypes.Structure):
        _fields_ = [
            ("state", wintypes.DWORD),
            ("local_addr", wintypes.DWORD),
            ("local_port", wintypes.DWORD),
            ("remote_addr", wintypes.DWORD),
            ("remote_port", wintypes.DWORD),
            ("pid", wintypes.DWORD),
        ]

    class _Row6(ctypes.Structure):
        _fields_ = [
            ("local_addr", ctypes.c_ubyte * 16),
            ("local_scope", wintypes.DWORD),
            ("local_port", wintypes.DWORD),
            ("remote_addr", ctypes.c_ubyte * 16),
            ("remote_scope", wintypes.DWORD),
            ("remote_port", wintypes.DWORD),
            ("state", wintypes.DWORD),
            ("pid", wintypes.DWORD),
        ]

    ports: set[int] = set()
    for family, row_type in ((socket.AF_INET, _Row4), (socket.AF_INET6, _Row6)):
        size = wintypes.DWORD(0)
        buffer = ctypes.create_string_buffer(0)
        for _attempt in range(8):
            result = iphlpapi.GetExtendedTcpTable(
                buffer, ctypes.byref(size), False, int(family),
                TCP_TABLE_OWNER_PID_LISTENER, 0,
            )
            if result == 0:
                break
            if result != ERROR_INSUFFICIENT_BUFFER:
                raise ServerStatusError(
                    f"GetExtendedTcpTable failed for family {int(family)}: {result}"
                )
            buffer = ctypes.create_string_buffer(size.value)
        else:
            raise ServerStatusError("TCP listener table kept growing")
        if size.value < ctypes.sizeof(wintypes.DWORD):
            raise ServerStatusError("TCP listener table is truncated")
        count = wintypes.DWORD.from_buffer(buffer).value
        offset = ctypes.sizeof(wintypes.DWORD)
        stride = ctypes.sizeof(row_type)
        if offset + count * stride > size.value:
            raise ServerStatusError("TCP listener table row count is inconsistent")
        for index in range(count):
            row = row_type.from_buffer(buffer, offset + index * stride)
            # dwLocalPort is network byte order in the low sixteen bits.
            ports.add(socket.ntohs(row.local_port & 0xFFFF))
    return ports


def _proc_listening_ports() -> set[int]:
    ports: set[int] = set()
    found = False
    for name in ("/proc/net/tcp", "/proc/net/tcp6"):
        path = Path(name)
        try:
            lines = path.read_text(encoding="ascii", errors="strict").splitlines()
        except FileNotFoundError:
            continue
        except (OSError, UnicodeDecodeError) as error:
            raise ServerStatusError(f"cannot read {name}: {error}") from error
        found = True
        for line in lines[1:]:
            fields = line.split()
            if len(fields) < 4:
                continue
            local, state = fields[1], fields[3]
            if state != "0A":  # TCP_LISTEN
                continue
            _address, _sep, port_token = local.rpartition(":")
            try:
                ports.add(int(port_token, 16))
            except ValueError as error:
                raise ServerStatusError(f"malformed {name} row") from error
    if not found:
        raise ServerStatusError("no local TCP listener table is available")
    return ports


def listening_ports() -> set[int]:
    """Every TCP port this host currently has a listening socket on."""
    if os.name == "nt":
        return _windows_listening_ports()
    return _proc_listening_ports()


def server_running(repo_root: Path) -> bool:
    """Classify the configured CN endpoint, or refuse to answer.

    A successful connect means running and an explicit refusal means stopped.
    Anything else -- a timeout, an unreachable network -- says nothing on its
    own, and on a host whose firewall drops rather than refuses, closed ports
    always time out, which made this unable to ever report "stopped".  Fall
    back to the host's own listening-socket table, which answers the real
    question directly and cannot be masked by a packet filter.  If that table
    is unavailable the probe still refuses to answer.
    """
    host, port = _endpoint(Path(repo_root))
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError as error:
        refused = (
            isinstance(error, ConnectionRefusedError)
            or error.errno == errno.ECONNREFUSED
            or getattr(error, "winerror", None) == 10061
        )
        if refused:
            return False
        ambiguous = error
    try:
        ports = listening_ports()
    except ServerStatusError:
        raise
    except Exception as error:
        raise ServerStatusError(
            f"local TCP listener table is unusable: {error}"
        ) from ambiguous
    return port in ports
