#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed, serial-bound device acceptance for the offline Android bundle.

The public probe is deliberately read-only.  The only mutating ADB operations in
this module live in :func:`prepare_device`, behind an exact confirmation token,
an exact-one-device gate, candidate hash binding, and clean shared-storage
checks.  In particular, this module never removes or renames the broad shared
``WorldFlipper`` directory and never extracts the data archive automatically.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, BinaryIO, Protocol

from wf_offline_bundle import APK_NAME, CandidateIdentity, canonical_json_bytes


EXPECTED_PACKAGE = "com.leiting.wf"
_IS_WINDOWS = os.name == "nt"
PREPARE_CONFIRM_PREFIX = "RESET_AND_REINSTALL_COM_LEITING_WF_ON_"
RECEIPT_SCHEMA_VERSION = 1

REQUIRED_MANUAL_CHECKS = (
    "home_party_character_list_open",
    "original_character_1_and_129999_139999_149999_owned",
    "all_three_characters_enter_battle_and_use_skill",
    "seris_dual_form_skill_powerflip_results_stable",
    "gerald_scale_list_party_battle_correct",
    "rush_700099_round_reward_token_confirmed",
    "all_15_weapons_visible_one_obtained_and_equipped",
    "weapon_effect_whitelist_and_non_whitelist_confirmed",
    "save_button_force_stop_restart_restores_progress",
    "airplane_mode_held_no_companion_service",
)

REQUIRED_OFFLINE_PROBE_GATES = (
    "airplane_mode",
    "wifi_disabled",
    "mobile_disabled",
    "no_default_route",
    "no_active_network",
    "companion_ports_unused",
)

# Known local services used by the server, admin UI, and mod GUI.  A connection
# to any of them makes the airplane-mode acceptance dependent on a companion.
COMPANION_PORTS = frozenset({8000, 8001, 5173, 8765, 8766})

_SERIAL_DIGEST_SALT = b"world-flipper-offline-device-acceptance:v1\x00"
_SERIAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_INSTANCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_BUILD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_PROC_ENDPOINT_RE = re.compile(r"^[0-9A-Fa-f]+:([0-9A-Fa-f]{1,4})$")
_FATAL_LOG_RE = re.compile(
    r"fatal\s+exception|fatal\s+signal|\bam_crash\b|"
    r"\bam_anr\b|\banr\s+in\s+com\.leiting\.wf\b|"
    r"process\s+com\.leiting\.wf\s+has\s+died|\bcrash(?:ed)?\b",
    re.IGNORECASE,
)
_MAX_RECEIPT_BYTES = 1024 * 1024

_SAVE_HAXE_PATH = "/sdcard/WorldFlipper/save_haxe"
_DUMMY_DATA_PATH = "/sdcard/WorldFlipper/dummy"


class DeviceError(RuntimeError):
    """Raised when a device or receipt cannot be proven safe and exact."""


class AdbRunner(Protocol):
    """Injected ADB boundary; ``serial=None`` is used only for ``devices -l``."""

    def adb(self, serial: str | None, *args: str) -> Any:
        """Run an ADB command and return text or a CompletedProcess-like value."""


@dataclass(frozen=True, slots=True)
class DeviceTarget:
    adb: Path
    serial: str
    package: str = EXPECTED_PACKAGE
    mumu_manager: Path | None = None
    instance: str | None = None


@dataclass(frozen=True, slots=True)
class DeviceProbeReport:
    serial_digest: str
    package_name: str
    airplane_mode: bool
    wifi_disabled: bool
    mobile_disabled: bool
    no_default_route: bool
    no_active_network: bool
    companion_ports_unused: bool
    save_haxe_present_before: bool
    dummy_data_present_before: bool
    fatal_log_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceAcceptanceReceipt:
    schema_version: int
    build_id: str
    apk_sha256: str
    data_zip_sha256: str
    evidence_sha256: str
    serial_digest: str
    probe: DeviceProbeReport
    checks: Mapping[str, bool]
    accepted_at_utc: str


@dataclass(frozen=True, slots=True)
class _WindowsHandleInfo:
    attributes: int
    identity: tuple[int, int]
    size: int
    link_count: int


@dataclass(slots=True)
class _LockedReadFile:
    path: Path
    handle: BinaryIO
    info: _WindowsHandleInfo
    parent_chain: tuple[_OwnedDirectory, ...]


@dataclass(slots=True)
class _OwnedDirectory:
    path: Path
    raw_handle: int | None
    identity: tuple[int, int]


@dataclass(slots=True)
class _StagedReceipt:
    path: Path
    handle: BinaryIO
    info: _WindowsHandleInfo
    sha256: str


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _lexical_absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _windows_file_api():
    if not _IS_WINDOWS:
        raise DeviceError("stable device acceptance requires Windows file handles")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_void_p,
    )
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return ctypes, wintypes, kernel32


def _windows_handle_info(raw_handle: int, *, label: str) -> _WindowsHandleInfo:
    import ctypes
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        )

    _ctypes, _wintypes, kernel32 = _windows_file_api()
    info = ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(raw_handle, ctypes.byref(info)):
        raise DeviceError(f"cannot inspect stable {label} handle") from ctypes.WinError(
            ctypes.get_last_error()
        )
    identity = (
        int(info.dwVolumeSerialNumber),
        (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
    )
    if identity[0] == 0 or identity[1] == 0:
        raise DeviceError(f"stable {label} handle has no nonzero identity")
    return _WindowsHandleInfo(
        attributes=int(info.dwFileAttributes),
        identity=identity,
        size=(int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
        link_count=int(info.nNumberOfLinks),
    )


def _stream_raw_handle(stream: BinaryIO) -> int:
    import msvcrt

    return int(msvcrt.get_osfhandle(stream.fileno()))


def _require_regular_windows_info(info: _WindowsHandleInfo, *, label: str) -> None:
    if info.attributes & 0x10:
        raise DeviceError(f"{label} must be a regular file")
    if info.attributes & 0x400:
        raise DeviceError(f"{label} must not be a reparse point")
    if info.link_count != 1:
        raise DeviceError(f"{label} must not have hard-link aliases")


def _open_locked_read_file(path: Path, *, label: str) -> _LockedReadFile:
    """Open one Windows file object read-only while denying writes and deletes."""

    if not _IS_WINDOWS:
        raise DeviceError("stable device acceptance requires Windows file handles")
    import ctypes
    import msvcrt

    target = _lexical_absolute(path)
    parent_chain = _open_directory_chain(target.parent, label=f"{label} parent")
    kernel32: Any | None = None
    raw_handle: int | None = None
    descriptor: int | None = None
    stream: BinaryIO | None = None
    try:
        _ctypes, _wintypes, kernel32 = _windows_file_api()
        candidate = kernel32.CreateFileW(
            str(target),
            0x80000000,  # GENERIC_READ
            0x00000001,  # FILE_SHARE_READ only
            None,
            3,  # OPEN_EXISTING
            0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
            None,
        )
        if candidate == ctypes.c_void_p(-1).value:
            raise DeviceError(f"cannot open stable {label} handle") from ctypes.WinError(
                ctypes.get_last_error()
            )
        raw_handle = int(candidate)
        info = _windows_handle_info(raw_handle, label=label)
        _require_regular_windows_info(info, label=label)
        descriptor = msvcrt.open_osfhandle(raw_handle, os.O_RDONLY | os.O_BINARY)
        raw_handle = None
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        return _LockedReadFile(target, stream, info, parent_chain)
    except BaseException as original_error:
        cleanup_error: BaseException | None = None
        try:
            if stream is not None:
                stream.close()
            elif descriptor is not None:
                os.close(descriptor)
            elif raw_handle is not None and kernel32 is not None:
                kernel32.CloseHandle(raw_handle)
        except BaseException as exc:
            cleanup_error = exc
        try:
            _close_directory_chain(parent_chain)
        except BaseException as close_error:
            cleanup_error = cleanup_error or close_error
        if cleanup_error is not None:
            original_error.add_note(
                f"failed to close stable {label} handles: {type(cleanup_error).__name__}"
            )
        if isinstance(original_error, DeviceError):
            raise
        raise DeviceError(f"cannot open stable {label} handle") from original_error


def _current_locked_info(locked: _LockedReadFile, *, label: str) -> _WindowsHandleInfo:
    if locked.handle.closed:
        raise DeviceError(f"stable {label} handle is closed")
    info = _windows_handle_info(_stream_raw_handle(locked.handle), label=label)
    _require_regular_windows_info(info, label=label)
    if info.identity != locked.info.identity:
        raise DeviceError(f"stable {label} handle identity changed")
    return info


def _windows_file_info_at_path(path: Path, *, label: str) -> _WindowsHandleInfo:
    """Inspect one lexical name without dereferencing reparse points."""

    if not _IS_WINDOWS:
        raise DeviceError("stable device acceptance requires Windows file handles")
    import ctypes

    target = _lexical_absolute(path)
    _ctypes, _wintypes, kernel32 = _windows_file_api()
    raw_handle = kernel32.CreateFileW(
        str(target),
        0x00000080,  # FILE_READ_ATTRIBUTES
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00200000,
        None,
    )
    if raw_handle == ctypes.c_void_p(-1).value:
        raise DeviceError(f"cannot bind {label} pathname") from ctypes.WinError(
            ctypes.get_last_error()
        )
    try:
        info = _windows_handle_info(int(raw_handle), label=label)
        _require_regular_windows_info(info, label=label)
        return info
    finally:
        kernel32.CloseHandle(raw_handle)


def _require_locked_path_binding(locked: _LockedReadFile, *, label: str) -> None:
    _require_directory_chain_binding(locked.parent_chain, label=f"{label} parent")
    current = _current_locked_info(locked, label=label)
    if current.size != locked.info.size or current.link_count != locked.info.link_count:
        raise DeviceError(f"stable {label} handle metadata changed")
    rebound = _windows_file_info_at_path(locked.path, label=f"{label} pathname")
    if rebound.identity != locked.info.identity:
        raise DeviceError(f"{label} pathname identity changed")


def _close_locked_read_file(locked: _LockedReadFile, *, label: str) -> None:
    close_error: BaseException | None = None
    if not locked.handle.closed:
        try:
            locked.handle.close()
        except OSError as exc:
            close_error = exc
    try:
        _close_directory_chain(locked.parent_chain)
    except BaseException as exc:
        close_error = close_error or exc
    if close_error is not None:
        raise DeviceError(f"failed to close stable {label} handles") from close_error


def _hash_locked_file(locked: _LockedReadFile, *, label: str) -> str:
    before = _current_locked_info(locked, label=label)
    try:
        position = locked.handle.tell()
        locked.handle.seek(0)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = locked.handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
        locked.handle.seek(position)
    except OSError as exc:
        raise DeviceError(f"cannot hash stable {label} handle") from exc
    after = _current_locked_info(locked, label=label)
    if before != after or size != locked.info.size:
        raise DeviceError(f"stable {label} handle changed while hashing")
    return digest.hexdigest()


def _read_locked_file_bytes(
    locked: _LockedReadFile,
    *,
    label: str,
    max_bytes: int,
) -> bytes:
    """Read one bounded payload from the already locked Windows file object."""

    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise DeviceError(f"{label} read limit is invalid")
    before = _current_locked_info(locked, label=label)
    if before.size > max_bytes:
        raise DeviceError(f"{label} is too large")
    try:
        position = locked.handle.tell()
        locked.handle.seek(0)
        payload = locked.handle.read(max_bytes + 1)
        locked.handle.seek(position)
    except OSError as exc:
        raise DeviceError(f"cannot read stable {label} handle") from exc
    after = _current_locked_info(locked, label=label)
    if before != after or after.size != locked.info.size:
        raise DeviceError(f"stable {label} handle changed while reading")
    if not isinstance(payload, bytes) or len(payload) != after.size:
        raise DeviceError(f"stable {label} handle size changed while reading")
    return payload


def _validate_target(target: DeviceTarget) -> None:
    if not isinstance(target, DeviceTarget):
        raise DeviceError("device target has an invalid type")
    if not isinstance(target.serial, str) or _SERIAL_RE.fullmatch(target.serial) is None:
        raise DeviceError("ADB serial is invalid or noncanonical")
    if not isinstance(target.package, str) or str.__eq__(target.package, EXPECTED_PACKAGE) is not True:
        raise DeviceError(f"device package must be {EXPECTED_PACKAGE}")
    if (target.mumu_manager is None) != (target.instance is None):
        raise DeviceError("MuMu manager and instance must be supplied together")
    if target.instance is not None and (
        not isinstance(target.instance, str) or _INSTANCE_RE.fullmatch(target.instance) is None
    ):
        raise DeviceError("MuMu instance is invalid")
    try:
        Path(target.adb)
        if target.mumu_manager is not None:
            Path(target.mumu_manager)
    except Exception as exc:
        raise DeviceError("device executable path is invalid") from exc


def _validate_identity(identity: CandidateIdentity) -> None:
    if not isinstance(identity, CandidateIdentity):
        raise DeviceError("candidate identity has an invalid type")
    if not isinstance(identity.build_id, str) or _BUILD_ID_RE.fullmatch(identity.build_id) is None:
        raise DeviceError("candidate build ID is invalid")
    for label, value in (
        ("APK", identity.apk_sha256),
        ("data ZIP", identity.data_zip_sha256),
        ("guide", identity.guide_sha256),
        ("release evidence", identity.evidence_sha256),
    ):
        if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
            raise DeviceError(f"candidate {label} hash is invalid")


def _confirmation_matches(confirm: object, expected: str) -> bool:
    if not isinstance(confirm, str):
        return False
    try:
        supplied = str.encode(confirm, "utf-8", "strict")
        required = str.encode(expected, "utf-8", "strict")
    except Exception:
        return False
    return hmac.compare_digest(supplied, required)


def _result_parts(value: Any, *, label: str) -> tuple[int, str]:
    if isinstance(value, str):
        return 0, value
    if isinstance(value, bytes):
        try:
            return 0, value.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise DeviceError(f"ADB {label} returned invalid UTF-8") from exc
    if hasattr(value, "returncode") and hasattr(value, "stdout"):
        returncode = getattr(value, "returncode")
        stdout = getattr(value, "stdout")
        if isinstance(returncode, bool) or not isinstance(returncode, int):
            raise DeviceError(f"ADB {label} returned an invalid status")
        if isinstance(stdout, bytes):
            try:
                stdout = stdout.decode("utf-8", "strict")
            except UnicodeDecodeError as exc:
                raise DeviceError(f"ADB {label} returned invalid UTF-8") from exc
        if not isinstance(stdout, str):
            raise DeviceError(f"ADB {label} returned invalid output")
        return returncode, stdout
    raise DeviceError(f"ADB {label} returned an unsupported result")


def _adb(
    runner: AdbRunner,
    serial: str | None,
    *args: str,
    label: str,
    allow_failure: bool = False,
) -> tuple[int, str]:
    try:
        value = runner.adb(serial, *args)
    except DeviceError:
        raise
    except Exception as exc:
        raise DeviceError(f"ADB {label} failed ({type(exc).__name__})") from exc
    returncode, stdout = _result_parts(value, label=label)
    if returncode != 0 and not allow_failure:
        raise DeviceError(f"ADB {label} failed with exit code {returncode}")
    return returncode, stdout


def _require_command_success(output: str, *, label: str) -> None:
    lines = tuple(line.strip() for line in output.splitlines() if line.strip())
    if not lines or lines[-1] != "Success":
        raise DeviceError(f"ADB {label} did not report Success")


def _parse_devices(text: str) -> tuple[tuple[str, str], ...]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or lines[0].strip() != "List of devices attached":
        raise DeviceError("ADB devices output is malformed")
    devices: list[tuple[str, str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split()
        if len(fields) < 2:
            raise DeviceError("ADB devices output contains a malformed device row")
        devices.append((fields[0], fields[1]))
    return tuple(devices)


def _require_exact_device(target: DeviceTarget, runner: AdbRunner) -> None:
    _validate_target(target)
    _, output = _adb(runner, None, "devices", "-l", label="device enumeration")
    devices = _parse_devices(output)
    if len(devices) != 1:
        raise DeviceError("exactly one ADB device must be listed")
    serial, state = devices[0]
    if serial != target.serial:
        raise DeviceError("listed ADB serial does not match the explicit target serial")
    if state != "device":
        raise DeviceError(f"target ADB serial is {state}, not online")


def _package_is_installed(target: DeviceTarget, runner: AdbRunner) -> bool:
    _, output = _adb(
        runner,
        target.serial,
        "shell",
        "pm",
        "list",
        "packages",
        target.package,
        label="package query",
    )
    lines = tuple(line.strip() for line in output.splitlines() if line.strip())
    if not lines:
        return False
    expected = f"package:{target.package}"
    if lines != (expected,):
        raise DeviceError("installed package query returned a package mismatch")
    _, activity_output = _adb(
        runner,
        target.serial,
        "shell",
        "cmd",
        "package",
        "resolve-activity",
        "--brief",
        target.package,
        label="package activity query",
    )
    activity_lines = tuple(line.strip() for line in activity_output.splitlines() if line.strip())
    if len(activity_lines) != 1 or not activity_lines[0].startswith(f"{target.package}/"):
        raise DeviceError("installed package activity does not match com.leiting.wf")
    return True


def _parse_binary_state(value: str, *, label: str) -> bool:
    normalized = value.strip()
    if normalized == "1":
        return True
    if normalized == "0":
        return False
    raise DeviceError(f"ADB {label} state is unrecognized")


def _parse_enabled_disabled(value: str, *, label: str) -> bool:
    normalized = " ".join(value.casefold().split())
    if normalized == "disabled" or normalized.endswith(" is disabled"):
        return True
    if normalized == "enabled" or normalized.endswith(" is enabled"):
        return False
    raise DeviceError(f"ADB {label} state is unrecognized")


def _no_active_network(value: str) -> bool:
    normalized = " ".join(value.casefold().split())
    if normalized in {"", "null", "none", "no active network"}:
        return True
    match = re.search(r"active default network\s*:\s*([^\s,}]+)", normalized)
    if match is not None:
        return match.group(1) in {"null", "none"}
    # Unknown connectivity output cannot prove absence, so it fails the gate.
    return False


def _companion_ports_unused(value: str) -> bool:
    for line in value.splitlines():
        fields = line.split()
        for endpoint in fields[1:3]:
            match = _PROC_ENDPOINT_RE.fullmatch(endpoint)
            if match is not None and int(match.group(1), 16) in COMPANION_PORTS:
                return False
        for decimal in re.findall(r"(?<![0-9]):([0-9]{1,5})(?![0-9])", line):
            port = int(decimal)
            if port <= 65535 and port in COMPANION_PORTS:
                return False
    return True


def _path_exists(target: DeviceTarget, runner: AdbRunner, path: str, *, label: str) -> bool:
    _, output = _adb(
        runner,
        target.serial,
        "shell",
        "if",
        "[",
        "-e",
        path,
        "];",
        "then",
        "printf",
        "1;",
        "else",
        "printf",
        "0;",
        "fi",
        label=label,
    )
    return _parse_binary_state(output, label=label)


def _fatal_log_lines(value: str) -> tuple[str, ...]:
    findings: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if line and _FATAL_LOG_RE.search(line):
            findings.append(line[:500])
    return tuple(findings)


def _serial_digest(serial: str) -> str:
    return hashlib.sha256(_SERIAL_DIGEST_SALT + serial.encode("utf-8", "strict")).hexdigest()


def probe_device(target: DeviceTarget, *, runner: AdbRunner) -> DeviceProbeReport:
    """Read device state without clearing, installing, deleting, or renaming data."""

    _validate_target(target)
    _require_exact_device(target, runner)
    _package_is_installed(target, runner)
    _, airplane = _adb(
        runner,
        target.serial,
        "shell",
        "settings",
        "get",
        "global",
        "airplane_mode_on",
        label="airplane mode query",
    )
    _, wifi = _adb(
        runner,
        target.serial,
        "shell",
        "settings",
        "get",
        "global",
        "wifi_on",
        label="Wi-Fi query",
    )
    _, mobile = _adb(
        runner,
        target.serial,
        "shell",
        "settings",
        "get",
        "global",
        "mobile_data",
        label="mobile-data query",
    )
    _, ipv4_route = _adb(
        runner,
        target.serial,
        "shell",
        "ip",
        "-4",
        "route",
        "show",
        "default",
        label="IPv4 default-route query",
    )
    _, ipv6_route = _adb(
        runner,
        target.serial,
        "shell",
        "ip",
        "-6",
        "route",
        "show",
        "default",
        label="IPv6 default-route query",
    )
    _, connectivity = _adb(
        runner,
        target.serial,
        "shell",
        "dumpsys",
        "connectivity",
        label="active-network query",
    )
    _, tcp = _adb(
        runner,
        target.serial,
        "shell",
        "cat",
        "/proc/net/tcp",
        "/proc/net/tcp6",
        label="TCP dependency query",
    )
    save_haxe = _path_exists(target, runner, _SAVE_HAXE_PATH, label="save_haxe presence query")
    dummy_data = _path_exists(target, runner, _DUMMY_DATA_PATH, label="dummy-data presence query")
    _, logcat = _adb(
        runner,
        target.serial,
        "logcat",
        "-d",
        "-v",
        "brief",
        label="logcat snapshot",
    )
    return DeviceProbeReport(
        serial_digest=_serial_digest(target.serial),
        package_name=target.package,
        airplane_mode=_parse_binary_state(airplane, label="airplane mode"),
        wifi_disabled=not _parse_binary_state(wifi, label="Wi-Fi"),
        mobile_disabled=not _parse_binary_state(mobile, label="mobile data"),
        no_default_route=not bool(ipv4_route.strip() or ipv6_route.strip()),
        no_active_network=_no_active_network(connectivity),
        companion_ports_unused=_companion_ports_unused(tcp),
        save_haxe_present_before=save_haxe,
        dummy_data_present_before=dummy_data,
        fatal_log_lines=_fatal_log_lines(logcat),
    )


def prepare_device(
    target: DeviceTarget,
    candidate_dir: Path,
    identity: CandidateIdentity,
    *,
    confirm: str,
    runner: AdbRunner,
) -> DeviceProbeReport:
    """Clear/reinstall only the exact target after every non-mutating gate passes."""

    _validate_target(target)
    _validate_identity(identity)
    expected = PREPARE_CONFIRM_PREFIX + target.serial
    if not _confirmation_matches(confirm, expected):
        raise DeviceError("device preparation confirmation does not match the exact serial-bound token")
    if not _IS_WINDOWS:
        raise DeviceError("device preparation requires a stable Windows candidate APK handle")
    try:
        apk = _lexical_absolute(Path(candidate_dir) / APK_NAME)
    except Exception as exc:
        raise DeviceError("candidate directory is invalid") from exc
    locked = _open_locked_read_file(apk, label="candidate APK")
    try:
        _require_locked_path_binding(locked, label="candidate APK")
        if not hmac.compare_digest(
            _hash_locked_file(locked, label="candidate APK"), identity.apk_sha256
        ):
            raise DeviceError("candidate APK hash drift before install")
        _require_exact_device(target, runner)
        before = probe_device(target, runner=runner)
        try:
            _validate_probe(before)
        except DeviceError as exc:
            if before.save_haxe_present_before or before.dummy_data_present_before:
                raise DeviceError(
                    "clean QA requires a dedicated empty instance or a manual backup of existing "
                    "WorldFlipper shared data"
                ) from exc
            raise
        installed = _package_is_installed(target, runner)
        # Recheck both immutable inputs immediately before the first write.
        _require_exact_device(target, runner)
        _require_locked_path_binding(locked, label="candidate APK")
        if not hmac.compare_digest(
            _hash_locked_file(locked, label="candidate APK"), identity.apk_sha256
        ):
            raise DeviceError("candidate APK hash drift before install")
        if installed:
            _, clear_output = _adb(
                runner,
                target.serial,
                "shell",
                "pm",
                "clear",
                target.package,
                label="package clear",
            )
            _require_command_success(clear_output, label="package clear")
            _, uninstall_output = _adb(
                runner,
                target.serial,
                "uninstall",
                target.package,
                label="package uninstall",
            )
            _require_command_success(uninstall_output, label="package uninstall")
        _, install_output = _adb(
            runner,
            target.serial,
            "install",
            str(apk),
            label="candidate install",
        )
        _require_command_success(install_output, label="candidate install")
        _require_exact_device(target, runner)
        if not _package_is_installed(target, runner):
            raise DeviceError("candidate package is not installed after install")
        after = probe_device(target, runner=runner)
        _validate_probe(after)
        _require_locked_path_binding(locked, label="candidate APK")
        if not hmac.compare_digest(
            _hash_locked_file(locked, label="candidate APK"), identity.apk_sha256
        ):
            raise DeviceError("candidate APK hash drift during install")
        return after
    finally:
        _close_locked_read_file(locked, label="candidate APK")


def _validate_probe(probe: DeviceProbeReport) -> None:
    if not isinstance(probe, DeviceProbeReport):
        raise DeviceError("device probe has an invalid type")
    if not isinstance(probe.serial_digest, str) or _HASH_RE.fullmatch(probe.serial_digest) is None:
        raise DeviceError("device probe serial digest is invalid")
    if probe.package_name != EXPECTED_PACKAGE:
        raise DeviceError("device probe package mismatch")
    for field_name in REQUIRED_OFFLINE_PROBE_GATES:
        if getattr(probe, field_name) is not True:
            raise DeviceError(f"device probe does not prove offline gate: {field_name}")
    if probe.save_haxe_present_before is not False or probe.dummy_data_present_before is not False:
        raise DeviceError("device probe does not prove a clean shared-data baseline")
    if not isinstance(probe.fatal_log_lines, tuple) or any(
        not isinstance(line, str) for line in probe.fatal_log_lines
    ):
        raise DeviceError("device probe fatal log lines are invalid")
    if probe.fatal_log_lines:
        raise DeviceError("device probe contains fatal or crash log lines")


def _validated_checks(checks: Mapping[str, bool], *, require_order: bool) -> dict[str, bool]:
    if not isinstance(checks, Mapping):
        raise DeviceError("manual acceptance checks must be a mapping")
    items = tuple(checks.items())
    keys = tuple(key for key, _ in items)
    if require_order and keys != REQUIRED_MANUAL_CHECKS:
        if set(keys) == set(REQUIRED_MANUAL_CHECKS):
            raise DeviceError("manual acceptance checks must be supplied in the exact order")
        raise DeviceError("all manual acceptance checks must be present and true")
    if set(keys) != set(REQUIRED_MANUAL_CHECKS) or len(keys) != len(REQUIRED_MANUAL_CHECKS):
        raise DeviceError("all manual acceptance checks must be present and true")
    output: dict[str, bool] = {}
    for key, value in items:
        if not isinstance(key, str) or value is not True:
            raise DeviceError("all manual acceptance checks must be present and true")
        output[key] = True
    return output


def _probe_document(probe: DeviceProbeReport) -> dict[str, Any]:
    return {
        "serial_digest": probe.serial_digest,
        "package_name": probe.package_name,
        "airplane_mode": probe.airplane_mode,
        "wifi_disabled": probe.wifi_disabled,
        "mobile_disabled": probe.mobile_disabled,
        "no_default_route": probe.no_default_route,
        "no_active_network": probe.no_active_network,
        "companion_ports_unused": probe.companion_ports_unused,
        "save_haxe_present_before": probe.save_haxe_present_before,
        "dummy_data_present_before": probe.dummy_data_present_before,
        "fatal_log_lines": list(probe.fatal_log_lines),
    }


def _receipt_document(receipt: DeviceAcceptanceReceipt) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "build_id": receipt.build_id,
        "apk_sha256": receipt.apk_sha256,
        "data_zip_sha256": receipt.data_zip_sha256,
        "evidence_sha256": receipt.evidence_sha256,
        "serial_digest": receipt.serial_digest,
        "probe": _probe_document(receipt.probe),
        "checks": dict(receipt.checks),
        "accepted_at_utc": receipt.accepted_at_utc,
    }


def _open_owned_directory(
    path: Path,
    *,
    label: str,
    allow_create: bool = False,
) -> _OwnedDirectory:
    """Bind one real directory and deny rename/delete for the handle lifetime."""

    if not _IS_WINDOWS:
        raise DeviceError("receipt publication requires stable Windows directory handles")
    import ctypes

    target = _lexical_absolute(path)
    _ctypes, _wintypes, kernel32 = _windows_file_api()
    desired_access = 0x0020 | 0x0080  # FILE_TRAVERSE | FILE_READ_ATTRIBUTES
    if allow_create:
        desired_access |= 0x0001 | 0x0002  # FILE_LIST_DIRECTORY | FILE_ADD_FILE
    raw_handle = kernel32.CreateFileW(
        str(target),
        desired_access,
        0x00000001 | 0x00000002,  # share read/write; deny delete/rebind
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if raw_handle == ctypes.c_void_p(-1).value:
        raise DeviceError(f"cannot bind stable {label} handle") from ctypes.WinError(
            ctypes.get_last_error()
        )
    try:
        info = _windows_handle_info(int(raw_handle), label=label)
        if not info.attributes & 0x10:
            raise DeviceError(f"{label} is not a directory")
        if info.attributes & 0x400:
            raise DeviceError(f"{label} must not be a reparse point")
        return _OwnedDirectory(target, int(raw_handle), info.identity)
    except BaseException:
        kernel32.CloseHandle(raw_handle)
        raise


def _windows_drive_type(root: str) -> int:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    return int(kernel32.GetDriveTypeW(root))


def _directory_chain_paths(path: Path, *, label: str) -> tuple[Path, ...]:
    try:
        target = _lexical_absolute(path)
    except Exception as exc:
        raise DeviceError(f"{label} path is invalid") from exc
    rendered = str(target)
    if _WINDOWS_ABSOLUTE_RE.match(rendered) is None or target.drive.startswith("\\\\"):
        raise DeviceError(f"{label} must be on one local Windows drive")
    root = Path(target.anchor)
    if _windows_drive_type(str(root)) != 3:  # DRIVE_FIXED
        raise DeviceError(f"{label} must be on one fixed local Windows drive")
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise DeviceError(f"{label} path is not drive-rooted") from exc
    output = [root]
    current = root
    for component in relative.parts:
        if component in {"", ".", ".."} or Path(component).name != component:
            raise DeviceError(f"{label} path contains an invalid component")
        current /= component
        output.append(current)
    return tuple(output)


def _open_directory_chain(
    path: Path,
    *,
    label: str,
    allow_create_at_leaf: bool = False,
) -> tuple[_OwnedDirectory, ...]:
    opened: list[_OwnedDirectory] = []
    try:
        components = _directory_chain_paths(path, label=label)
        for index, component in enumerate(components):
            opened.append(
                _open_owned_directory(
                    component,
                    label=f"{label} component",
                    allow_create=allow_create_at_leaf and index == len(components) - 1,
                )
            )
        return tuple(opened)
    except BaseException as original_error:
        try:
            _close_directory_chain(tuple(opened))
        except BaseException as close_error:
            original_error.add_note(
                f"failed to close partial {label} chain: {type(close_error).__name__}"
            )
        if isinstance(original_error, DeviceError):
            raise
        raise DeviceError(f"cannot bind stable {label} chain") from original_error


def _require_directory_chain_binding(
    chain: tuple[_OwnedDirectory, ...],
    *,
    label: str,
) -> None:
    if not chain:
        raise DeviceError(f"stable {label} chain is empty")
    for owned in chain:
        _require_owned_directory_binding(owned, label=f"{label} component")


def _close_directory_chain(chain: tuple[_OwnedDirectory, ...]) -> None:
    first_error: BaseException | None = None
    for owned in reversed(chain):
        try:
            _close_owned_directory(owned)
        except BaseException as exc:
            first_error = first_error or exc
    if first_error is not None:
        raise DeviceError("failed to close stable directory chain") from first_error


def _directory_identity_at_path(path: Path, *, label: str) -> tuple[int, int]:
    if not _IS_WINDOWS:
        raise DeviceError("receipt publication requires stable Windows directory handles")
    import ctypes

    target = _lexical_absolute(path)
    _ctypes, _wintypes, kernel32 = _windows_file_api()
    raw_handle = kernel32.CreateFileW(
        str(target),
        0x0001 | 0x0080,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if raw_handle == ctypes.c_void_p(-1).value:
        raise DeviceError(f"cannot rebind {label} pathname") from ctypes.WinError(
            ctypes.get_last_error()
        )
    try:
        info = _windows_handle_info(int(raw_handle), label=label)
        if not info.attributes & 0x10 or info.attributes & 0x400:
            raise DeviceError(f"{label} pathname is not a real directory")
        return info.identity
    finally:
        kernel32.CloseHandle(raw_handle)


def _require_owned_directory_binding(owned: _OwnedDirectory, *, label: str) -> None:
    if owned.raw_handle is None:
        raise DeviceError(f"stable {label} handle is closed")
    current = _windows_handle_info(owned.raw_handle, label=label)
    if not current.attributes & 0x10 or current.attributes & 0x400:
        raise DeviceError(f"stable {label} handle changed type")
    if current.identity != owned.identity:
        raise DeviceError(f"stable {label} handle identity changed")
    if _directory_identity_at_path(owned.path, label=label) != owned.identity:
        raise DeviceError(f"{label} pathname identity changed")


def _close_owned_directory(owned: _OwnedDirectory) -> None:
    if owned.raw_handle is None:
        return
    _ctypes, _wintypes, kernel32 = _windows_file_api()
    raw_handle = owned.raw_handle
    if not kernel32.CloseHandle(raw_handle):
        raise DeviceError("failed to close stable receipt parent handle")
    owned.raw_handle = None


def _mark_raw_file_handle_for_delete(raw_handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = (("DeleteFile", wintypes.BOOLEAN),)

    _ctypes, _wintypes, kernel32 = _windows_file_api()
    disposition = FileDispositionInfo(True)
    if not kernel32.SetFileInformationByHandle(
        raw_handle,
        4,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _validated_windows_leaf(name: str, *, label: str) -> str:
    if not isinstance(name, str) or name in {"", ".", ".."}:
        raise DeviceError(f"{label} must be one filename")
    if Path(name).name != name or any(character in '<>:"/\\|?*' for character in name):
        raise DeviceError(f"{label} must be one safe filename")
    if name[-1] in {" ", "."} or any(ord(character) < 32 for character in name):
        raise DeviceError(f"{label} must be one canonical filename")
    try:
        encoded = str.encode(name, "utf-16-le", "strict")
    except UnicodeEncodeError as exc:
        raise DeviceError(f"{label} is not valid UTF-16") from exc
    if len(encoded) > 510:
        raise DeviceError(f"{label} is too long")
    stem = name.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"COM{index}" for index in range(1, 10))
    reserved.update(f"LPT{index}" for index in range(1, 10))
    if stem in reserved:
        raise DeviceError(f"{label} is a reserved Windows filename")
    return name


def _nt_create_file_relative(parent_handle: int, name: str) -> int:
    """Create one new non-reparse file relative to an already stable directory."""

    leaf = _validated_windows_leaf(name, label="receipt staging filename")
    if (
        not _IS_WINDOWS
        or not isinstance(parent_handle, int)
        or isinstance(parent_handle, bool)
        or parent_handle <= 0
    ):
        raise DeviceError("stable receipt parent handle is invalid")
    import ctypes
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = (
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        )

    class ObjectAttributes(ctypes.Structure):
        _fields_ = (
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(UnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", ctypes.c_void_p),
            ("SecurityQualityOfService", ctypes.c_void_p),
        )

    class IoStatusValue(ctypes.Union):
        _fields_ = (("Status", wintypes.LONG), ("Pointer", ctypes.c_void_p))

    class IoStatusBlock(ctypes.Structure):
        _anonymous_ = ("Value",)
        _fields_ = (("Value", IoStatusValue), ("Information", ctypes.c_size_t))

    if ctypes.sizeof(wintypes.WCHAR) != 2:
        raise DeviceError("Windows UTF-16 ABI is unsupported")
    encoded = leaf.encode("utf-16-le", "strict")
    name_buffer = ctypes.create_unicode_buffer(leaf)
    unicode_name = UnicodeString(
        len(encoded),
        len(encoded) + ctypes.sizeof(ctypes.c_wchar),
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        wintypes.HANDLE(parent_handle),
        ctypes.pointer(unicode_name),
        0x00000040 | 0x00001000,  # OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE
        None,
        None,
    )
    io_status = IoStatusBlock()
    raw_handle = wintypes.HANDLE()
    ntdll = ctypes.WinDLL("ntdll", use_last_error=False)
    ntdll.NtCreateFile.argtypes = (
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.ULONG,
        ctypes.POINTER(ObjectAttributes),
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        wintypes.ULONG,
    )
    ntdll.NtCreateFile.restype = wintypes.LONG
    ntdll.RtlNtStatusToDosError.argtypes = (wintypes.LONG,)
    ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG
    desired_access = 0x0001 | 0x0002 | 0x0080 | 0x0100 | 0x00010000 | 0x00100000
    status = int(
        ntdll.NtCreateFile(
            ctypes.byref(raw_handle),
            desired_access,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            0x00000100,  # FILE_ATTRIBUTE_TEMPORARY
            0x00000001,  # FILE_SHARE_READ only
            2,  # FILE_CREATE
            0x00000020 | 0x00000040 | 0x00200000,
            None,
            0,
        )
    )
    if status < 0:
        leaked = int(raw_handle.value or 0)
        if leaked > 0:
            _ctypes, _wintypes, kernel32 = _windows_file_api()
            kernel32.CloseHandle(leaked)
        mapped = int(ntdll.RtlNtStatusToDosError(status))
        error = ctypes.WinError(mapped)
        error.add_note(f"NtCreateFile status=0x{status & 0xFFFFFFFF:08x}")
        raise error
    created = int(raw_handle.value or 0)
    if created <= 0:
        raise DeviceError("NtCreateFile returned no receipt staging handle")
    if int(io_status.Information) != 2:  # FILE_CREATED
        cleanup_error: BaseException | None = None
        try:
            _mark_raw_file_handle_for_delete(created)
        except BaseException as exc:
            cleanup_error = exc
        _ctypes, _wintypes, kernel32 = _windows_file_api()
        kernel32.CloseHandle(created)
        error = DeviceError("receipt staging file was not created exclusively")
        if cleanup_error is not None:
            error.add_note("failed to clean unexpected NtCreateFile handle")
        raise error
    return created


def _rename_file_handle_relative_no_replace(
    file_handle: int,
    parent_handle: int,
    name: str,
) -> None:
    """Rename one owned file into the held parent without absolute path lookup."""

    leaf = _validated_windows_leaf(name, label="receipt destination filename")
    if (
        not _IS_WINDOWS
        or not isinstance(file_handle, int)
        or isinstance(file_handle, bool)
        or file_handle <= 0
        or not isinstance(parent_handle, int)
        or isinstance(parent_handle, bool)
        or parent_handle <= 0
    ):
        raise DeviceError("receipt publication handle is invalid")
    import ctypes
    from ctypes import wintypes

    class RenameControl(ctypes.Union):
        _fields_ = (("ReplaceIfExists", wintypes.BOOLEAN), ("Flags", wintypes.DWORD))

    class FileRenameInfo(ctypes.Structure):
        _anonymous_ = ("Control",)
        _fields_ = (
            ("Control", RenameControl),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),
            ("FileName", wintypes.WCHAR * 1),
        )

    class IoStatusValue(ctypes.Union):
        _fields_ = (("Status", wintypes.LONG), ("Pointer", ctypes.c_void_p))

    class IoStatusBlock(ctypes.Structure):
        _anonymous_ = ("Value",)
        _fields_ = (("Value", IoStatusValue), ("Information", ctypes.c_size_t))

    encoded_name = leaf.encode("utf-16-le", "strict")
    buffer_size = max(ctypes.sizeof(FileRenameInfo), FileRenameInfo.FileName.offset + len(encoded_name))
    buffer = ctypes.create_string_buffer(buffer_size)
    rename = FileRenameInfo.from_buffer(buffer)
    rename.ReplaceIfExists = False
    rename.RootDirectory = wintypes.HANDLE(parent_handle)
    rename.FileNameLength = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(buffer) + FileRenameInfo.FileName.offset,
        encoded_name,
        len(encoded_name),
    )
    io_status = IoStatusBlock()
    ntdll = ctypes.WinDLL("ntdll", use_last_error=False)
    ntdll.NtSetInformationFile.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(IoStatusBlock),
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.c_int,
    )
    ntdll.NtSetInformationFile.restype = wintypes.LONG
    ntdll.RtlNtStatusToDosError.argtypes = (wintypes.LONG,)
    ntdll.RtlNtStatusToDosError.restype = wintypes.ULONG
    status = int(
        ntdll.NtSetInformationFile(
            wintypes.HANDLE(file_handle),
            ctypes.byref(io_status),
            buffer,
            buffer_size,
            10,  # FileRenameInformation
        )
    )
    if status < 0:
        mapped = int(ntdll.RtlNtStatusToDosError(status))
        error = ctypes.WinError(mapped)
        error.add_note(f"NtSetInformationFile status=0x{status & 0xFFFFFFFF:08x}")
        raise error


def _create_receipt_staging(parent: _OwnedDirectory, payload: bytes, name: str) -> _StagedReceipt:
    if parent.raw_handle is None:
        raise DeviceError("stable receipt parent handle is closed")
    import msvcrt

    _require_owned_directory_binding(parent, label="receipt parent")
    raw_handle: int | None = None
    descriptor: int | None = None
    stream: BinaryIO | None = None
    staged: _StagedReceipt | None = None
    try:
        for _attempt in range(128):
            staging_name = f".{name}.tmp-{uuid.uuid4().hex}"
            path = parent.path / staging_name
            try:
                raw_handle = _nt_create_file_relative(parent.raw_handle, staging_name)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {80, 183}:
                    raise
        if raw_handle is None:
            raise DeviceError("cannot allocate exclusive receipt staging file")
        info = _windows_handle_info(raw_handle, label="receipt staging")
        _require_regular_windows_info(info, label="receipt staging")
        descriptor = msvcrt.open_osfhandle(raw_handle, os.O_RDWR | os.O_BINARY)
        raw_handle = None
        stream = os.fdopen(descriptor, "w+b")
        descriptor = None
        staged = _StagedReceipt(path, stream, info, "")
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
        finished = _windows_handle_info(_stream_raw_handle(stream), label="receipt staging")
        _require_regular_windows_info(finished, label="receipt staging")
        if finished.identity != info.identity or finished.size != len(payload):
            raise DeviceError("receipt staging identity or size changed")
        staged.info = finished
        staged.sha256 = hashlib.sha256(payload).hexdigest()
        _require_staged_receipt_binding(staged, expected_payload=payload)
        return staged
    except BaseException as original_error:
        cleanup_error: BaseException | None = None
        if staged is not None:
            try:
                _cleanup_staged_receipt(staged)
            except BaseException as exc:
                cleanup_error = exc
        elif stream is not None:
            try:
                _mark_raw_file_handle_for_delete(_stream_raw_handle(stream))
            except BaseException as exc:
                cleanup_error = exc
            try:
                stream.close()
            except OSError as exc:
                cleanup_error = cleanup_error or exc
        elif descriptor is not None:
            try:
                _mark_raw_file_handle_for_delete(int(msvcrt.get_osfhandle(descriptor)))
            except BaseException as exc:
                cleanup_error = exc
            try:
                os.close(descriptor)
            except OSError as exc:
                cleanup_error = cleanup_error or exc
        elif raw_handle is not None:
            try:
                _mark_raw_file_handle_for_delete(raw_handle)
            except BaseException as exc:
                cleanup_error = exc
            _ctypes, _wintypes, kernel32 = _windows_file_api()
            kernel32.CloseHandle(raw_handle)
        if cleanup_error is not None:
            original_error.add_note(
                "failed to clean exact receipt staging handle: "
                f"{type(cleanup_error).__name__}"
            )
        if isinstance(original_error, DeviceError):
            raise
        raise DeviceError("cannot create stable receipt staging file") from original_error


def _read_staged_receipt_bytes(staged: _StagedReceipt) -> bytes:
    if staged.handle.closed:
        raise DeviceError("stable receipt staging handle is closed")
    try:
        position = staged.handle.tell()
        staged.handle.seek(0)
        payload = staged.handle.read(_MAX_RECEIPT_BYTES + 1)
        staged.handle.seek(position)
    except OSError as exc:
        raise DeviceError("cannot read stable receipt staging handle") from exc
    if len(payload) > _MAX_RECEIPT_BYTES:
        raise DeviceError("device acceptance receipt is too large")
    return payload


def _require_staged_receipt_binding(
    staged: _StagedReceipt,
    *,
    expected_payload: bytes,
) -> None:
    if staged.handle.closed:
        raise DeviceError("stable receipt staging handle is closed")
    current = _windows_handle_info(
        _stream_raw_handle(staged.handle), label="receipt staging"
    )
    _require_regular_windows_info(current, label="receipt staging")
    if current.identity != staged.info.identity or current.size != len(expected_payload):
        raise DeviceError("receipt staging handle identity or size changed")
    rebound = _windows_file_info_at_path(staged.path, label="receipt staging")
    if rebound.identity != staged.info.identity:
        raise DeviceError("receipt staging pathname identity changed")
    actual = _read_staged_receipt_bytes(staged)
    if not hmac.compare_digest(hashlib.sha256(actual).hexdigest(), staged.sha256):
        raise DeviceError("receipt staging bytes changed")
    if actual != expected_payload:
        raise DeviceError("receipt staging canonical payload changed")


def _rename_receipt_handle_no_replace(
    staged: _StagedReceipt,
    parent: _OwnedDirectory,
    destination_name: str,
) -> None:
    if parent.raw_handle is None or staged.handle.closed:
        raise DeviceError("receipt publication handle is closed")
    destination_name = _validated_windows_leaf(
        destination_name, label="receipt publication destination"
    )
    _require_owned_directory_binding(parent, label="receipt parent")
    destination = parent.path / destination_name
    _rename_file_handle_relative_no_replace(
        _stream_raw_handle(staged.handle),
        parent.raw_handle,
        destination_name,
    )
    staged.path = destination


def _require_published_receipt_binding(
    staged: _StagedReceipt,
    destination: Path,
    expected_payload: bytes,
) -> None:
    if _lexical_absolute(destination) != staged.path:
        raise DeviceError("published receipt destination binding changed")
    _require_staged_receipt_binding(staged, expected_payload=expected_payload)
    actual = _read_staged_receipt_bytes(staged)
    try:
        document = json.loads(actual.decode("utf-8", "strict"), object_pairs_hook=_unique_object)
    except (_DuplicateJsonKey, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeviceError("published receipt is not unique-key UTF-8 JSON") from exc
    if not isinstance(document, dict) or canonical_json_bytes(document) != actual:
        raise DeviceError("published receipt is not canonical JSON")


def _cleanup_staged_receipt(staged: _StagedReceipt) -> None:
    if staged.handle.closed:
        return
    disposition_error: BaseException | None = None
    try:
        _mark_raw_file_handle_for_delete(_stream_raw_handle(staged.handle))
    except BaseException as exc:
        disposition_error = exc
    try:
        staged.handle.close()
    except OSError as exc:
        raise DeviceError("failed to close exact receipt staging handle") from exc
    if disposition_error is not None:
        raise DeviceError("failed to delete exact receipt staging handle") from disposition_error


def _close_published_receipt(staged: _StagedReceipt) -> None:
    if staged.handle.closed:
        return
    try:
        staged.handle.close()
    except OSError as exc:
        raise DeviceError("failed to close published receipt handle") from exc


def _write_atomic_no_replace(output: Path, payload: bytes) -> None:
    if not _IS_WINDOWS:
        raise DeviceError("receipt publication requires stable Windows handles")
    try:
        destination = _lexical_absolute(output)
    except (TypeError, ValueError, OSError) as exc:
        raise DeviceError("receipt output path is invalid") from exc
    destination_name = _validated_windows_leaf(
        destination.name, label="receipt output filename"
    )
    parent_chain = _open_directory_chain(
        destination.parent,
        label="receipt parent",
        allow_create_at_leaf=True,
    )
    parent = parent_chain[-1]
    staged: _StagedReceipt | None = None
    completed = False
    active_error: BaseException | None = None
    try:
        _require_directory_chain_binding(parent_chain, label="receipt parent")
        if _lexists(destination):
            raise DeviceError("device acceptance receipt already exists")
        staged = _create_receipt_staging(parent, payload, destination_name)
        _require_staged_receipt_binding(staged, expected_payload=payload)
        try:
            _rename_receipt_handle_no_replace(staged, parent, destination_name)
        except OSError as exc:
            try:
                observed = _windows_file_info_at_path(destination, label="receipt destination")
            except DeviceError:
                observed = None
            if observed is not None and observed.identity != staged.info.identity:
                raise DeviceError("device acceptance receipt already exists") from exc
            raise DeviceError("device acceptance receipt could not be published atomically") from exc
        _require_directory_chain_binding(parent_chain, label="receipt parent")
        _require_published_receipt_binding(staged, destination, payload)
        completed = True
    except BaseException as original_error:
        active_error = original_error
        if staged is not None and not staged.handle.closed:
            try:
                _cleanup_staged_receipt(staged)
            except BaseException as cleanup_error:
                original_error.add_note(
                    "failed to roll back exact receipt handle: "
                    f"{type(cleanup_error).__name__}"
                )
        raise
    finally:
        close_error: BaseException | None = None
        if completed and staged is not None:
            try:
                _close_published_receipt(staged)
            except BaseException as exc:
                close_error = exc
        try:
            _close_directory_chain(parent_chain)
        except BaseException as exc:
            close_error = close_error or exc
        if close_error is not None:
            if active_error is not None:
                active_error.add_note(
                    "failed to close stable receipt publication parent handles: "
                    f"{type(close_error).__name__}"
                )
            elif completed:
                raise DeviceError(
                    "failed to close stable receipt publication handles"
                ) from close_error


def record_manual_acceptance(
    identity: CandidateIdentity,
    probe: DeviceProbeReport,
    checks: Mapping[str, bool],
    output: Path,
) -> DeviceAcceptanceReceipt:
    """Write one canonical, immutable receipt bound to a frozen candidate."""

    _validate_identity(identity)
    _validate_probe(probe)
    checked = _validated_checks(checks, require_order=True)
    try:
        output_path = Path(output)
    except Exception as exc:
        raise DeviceError("device acceptance receipt output path is invalid") from exc
    accepted_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    receipt = DeviceAcceptanceReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        build_id=identity.build_id,
        apk_sha256=identity.apk_sha256,
        data_zip_sha256=identity.data_zip_sha256,
        evidence_sha256=identity.evidence_sha256,
        serial_digest=probe.serial_digest,
        probe=probe,
        checks=MappingProxyType(checked),
        accepted_at_utc=accepted_at,
    )
    try:
        payload = canonical_json_bytes(_receipt_document(receipt))
    except Exception as exc:
        raise DeviceError("device acceptance receipt could not be encoded") from exc
    _write_atomic_no_replace(output_path, payload)
    return receipt


class _DuplicateJsonKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise _DuplicateJsonKey(key)
        output[key] = value
    return output


def _read_regular_bytes(path: Path, *, label: str) -> bytes:
    if not _IS_WINDOWS:
        raise DeviceError("stable receipt validation requires Windows file handles")
    try:
        target = _lexical_absolute(path)
        locked = _open_locked_read_file(target, label=label)
    except DeviceError:
        raise
    except Exception as exc:
        raise DeviceError(f"cannot open stable {label} handle") from exc
    active_error: BaseException | None = None
    try:
        _require_locked_path_binding(locked, label=label)
        raw = _read_locked_file_bytes(locked, label=label, max_bytes=_MAX_RECEIPT_BYTES)
        _require_locked_path_binding(locked, label=label)
        return raw
    except BaseException as exc:
        active_error = exc
        if isinstance(exc, DeviceError):
            raise
        raise DeviceError(f"cannot validate stable {label} handle") from exc
    finally:
        try:
            _close_locked_read_file(locked, label=label)
        except DeviceError as exc:
            if active_error is not None:
                active_error.add_note(f"failed to close stable {label} handle")
            else:
                raise


def _looks_absolute(value: str) -> bool:
    lowered = value.casefold()
    return (
        value.startswith("/")
        or value.startswith("\\")
        or _WINDOWS_ABSOLUTE_RE.match(value) is not None
        or lowered.startswith("file://")
    )


def _reject_absolute_strings(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and _looks_absolute(key):
                raise DeviceError("absolute path is forbidden in a device receipt")
            _reject_absolute_strings(item)
    elif isinstance(value, list):
        for item in value:
            _reject_absolute_strings(item)
    elif isinstance(value, str) and _looks_absolute(value):
        raise DeviceError("absolute path is forbidden in a device receipt")


def _require_exact_fields(value: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise DeviceError(f"{label} schema has unknown or missing fields")


def _require_bool(value: Any, *, label: str) -> bool:
    if value is not True and value is not False:
        raise DeviceError(f"{label} must be a boolean")
    return value


def _parse_utc(value: Any) -> str:
    if not isinstance(value, str) or not (value.endswith("Z") or value.endswith("+00:00")):
        raise DeviceError("device receipt accepted_at_utc must be UTC")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DeviceError("device receipt accepted_at_utc must be ISO-8601 UTC") from exc
    if parsed.utcoffset() != timedelta(0):
        raise DeviceError("device receipt accepted_at_utc must be UTC")
    return value


def validate_acceptance_receipt(
    path: Path,
    identity: CandidateIdentity,
) -> DeviceAcceptanceReceipt:
    """Reparse a canonical receipt and bind every candidate/offline fact."""

    _validate_identity(identity)
    try:
        receipt_path = Path(path)
    except Exception as exc:
        raise DeviceError("device acceptance receipt path is invalid") from exc
    raw = _read_regular_bytes(receipt_path, label="device acceptance receipt")
    try:
        text = raw.decode("utf-8", "strict")
        document = json.loads(text, object_pairs_hook=_unique_object)
    except (_DuplicateJsonKey, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeviceError("device acceptance receipt is not unique-key UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise DeviceError("device acceptance receipt must be an object")
    _reject_absolute_strings(document)
    try:
        canonical = canonical_json_bytes(document)
    except Exception as exc:
        raise DeviceError("device acceptance receipt is not canonical JSON") from exc
    if raw != canonical:
        raise DeviceError("device acceptance receipt bytes are not canonical")
    _require_exact_fields(
        document,
        {
            "schema_version",
            "build_id",
            "apk_sha256",
            "data_zip_sha256",
            "evidence_sha256",
            "serial_digest",
            "probe",
            "checks",
            "accepted_at_utc",
        },
        label="device acceptance receipt",
    )
    if document.get("schema_version") != RECEIPT_SCHEMA_VERSION or isinstance(
        document.get("schema_version"), bool
    ):
        raise DeviceError("device acceptance receipt schema mismatch")
    for key, expected in (
        ("build_id", identity.build_id),
        ("apk_sha256", identity.apk_sha256),
        ("data_zip_sha256", identity.data_zip_sha256),
        ("evidence_sha256", identity.evidence_sha256),
    ):
        value = document.get(key)
        if not isinstance(value, str) or not hmac.compare_digest(value, expected):
            raise DeviceError(f"device receipt {key} mismatch")
    serial_digest = document.get("serial_digest")
    if not isinstance(serial_digest, str) or _HASH_RE.fullmatch(serial_digest) is None:
        raise DeviceError("device receipt serial digest is invalid")
    probe_value = document.get("probe")
    if not isinstance(probe_value, dict):
        raise DeviceError("device receipt probe must be an object")
    _require_exact_fields(
        probe_value,
        {
            "serial_digest",
            "package_name",
            "airplane_mode",
            "wifi_disabled",
            "mobile_disabled",
            "no_default_route",
            "no_active_network",
            "companion_ports_unused",
            "save_haxe_present_before",
            "dummy_data_present_before",
            "fatal_log_lines",
        },
        label="device receipt probe",
    )
    if probe_value.get("serial_digest") != serial_digest:
        raise DeviceError("device receipt serial digest mismatch")
    package_name = probe_value.get("package_name")
    if package_name != EXPECTED_PACKAGE:
        raise DeviceError("device receipt package mismatch")
    probe_bools: dict[str, bool] = {}
    for field_name in (
        *REQUIRED_OFFLINE_PROBE_GATES,
        "save_haxe_present_before",
        "dummy_data_present_before",
    ):
        probe_bools[field_name] = _require_bool(
            probe_value.get(field_name), label=f"device receipt probe.{field_name}"
        )
    fatal_lines = probe_value.get("fatal_log_lines")
    if not isinstance(fatal_lines, list) or any(not isinstance(line, str) for line in fatal_lines):
        raise DeviceError("device receipt fatal_log_lines must be a string array")
    probe = DeviceProbeReport(
        serial_digest=serial_digest,
        package_name=package_name,
        airplane_mode=probe_bools["airplane_mode"],
        wifi_disabled=probe_bools["wifi_disabled"],
        mobile_disabled=probe_bools["mobile_disabled"],
        no_default_route=probe_bools["no_default_route"],
        no_active_network=probe_bools["no_active_network"],
        companion_ports_unused=probe_bools["companion_ports_unused"],
        save_haxe_present_before=probe_bools["save_haxe_present_before"],
        dummy_data_present_before=probe_bools["dummy_data_present_before"],
        fatal_log_lines=tuple(fatal_lines),
    )
    _validate_probe(probe)
    checks_value = document.get("checks")
    if not isinstance(checks_value, dict):
        raise DeviceError("device receipt checks must be an object")
    checked = _validated_checks(checks_value, require_order=False)
    accepted_at = _parse_utc(document.get("accepted_at_utc"))
    return DeviceAcceptanceReceipt(
        schema_version=RECEIPT_SCHEMA_VERSION,
        build_id=identity.build_id,
        apk_sha256=identity.apk_sha256,
        data_zip_sha256=identity.data_zip_sha256,
        evidence_sha256=identity.evidence_sha256,
        serial_digest=serial_digest,
        probe=probe,
        checks=MappingProxyType(checked),
        accepted_at_utc=accepted_at,
    )


__all__ = [
    "AdbRunner",
    "COMPANION_PORTS",
    "DeviceAcceptanceReceipt",
    "DeviceError",
    "DeviceProbeReport",
    "DeviceTarget",
    "EXPECTED_PACKAGE",
    "PREPARE_CONFIRM_PREFIX",
    "REQUIRED_MANUAL_CHECKS",
    "REQUIRED_OFFLINE_PROBE_GATES",
    "prepare_device",
    "probe_device",
    "record_manual_acceptance",
    "validate_acceptance_receipt",
]
