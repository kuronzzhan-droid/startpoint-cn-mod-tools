#!/usr/bin/env python3
"""One operator-facing workflow for the frozen offline Android release.

The orchestration layer is intentionally dependency-injected.  Unit tests use
small deterministic services, while :class:`RealReleaseServices` is the only
production adapter allowed to connect Tasks 3--13.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import hmac
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
import zipfile
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "out" / "wf-offline-android"
DEFAULT_SNAPSHOT_VERSION = "1.4.196"
DEFAULT_SOURCE_APK = Path.home() / "Downloads" / "base.apk.1"
DEFAULT_LEGACY_ZIP = REPO_ROOT / "弹国服" / "单机版数据包.zip"
DEFAULT_TAIL_ZIP = (
    REPO_ROOT
    / ".cdn"
    / "cn"
    / "archive-common-diff"
    / "pinball-1.4.195-1.4.196-1-mod07200253.zip"
)
DEFAULT_RELEASE_HOME = Path.home() / ".wf-offline-release"
PROTECTED_OUTPUT_ROOTS = tuple(
    REPO_ROOT / name for name in ("弹国服", ".cdn", "assets", "work")
)
FINAL_DIR_NAME = "WF离线整合版"
PASSWORD_ENV = "WF_OFFLINE_KEYSTORE_PASSWORD"
SIGNER_CONFIRMATION = "CREATE_WF_OFFLINE_RELEASE_SIGNER"
PREPARE_CONFIRM_PREFIX = "RESET_AND_REINSTALL_COM_LEITING_WF_ON_"
EXPECTED_STORE_COUNTS = {"common": 113_822, "medium": 23_458, "android": 1_009}
EXPECTED_LEGACY_COUNT = 137_820
EXPECTED_CURRENT_COUNT = 138_289
EXPECTED_ADDED_COUNT = 469
EXPECTED_TAIL_COUNT = 12
MAX_CONTENT_GUARDS = 4096

COMMANDS = (
    "preflight",
    "build-candidate",
    "device-probe",
    "prepare-device",
    "device-accept",
    "finalize",
    "verify",
    "init-signer",
)
STAGES = (
    "preflight",
    "scan-store",
    "legacy-tail-gates",
    "copy-snapshot",
    "player-overlay",
    "content-data-gates",
    "build-apk",
    "content-client-gate",
    "build-zip",
    "verify-zip",
    "render-guide",
    "freeze-candidate",
    "secret-scan",
)
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

_BUILD_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ABSOLUTE_RE = re.compile(r"(?i)(?:[A-Z]:[\\/]|(?:file://)|(?:^|\s)/(?:[^\s]+))")


class ReleaseError(RuntimeError):
    """A public, already-redacted release failure."""


@dataclass(frozen=True, slots=True)
class OfflineReleaseConfig:
    source_apk: Path
    snapshot_version: str
    output_root: Path
    profile_id: str
    legacy_zip: Path
    tail_zip: Path
    toolchain: Any
    signing: Any


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    status: Literal["awaiting_device_acceptance", "finalized", "verified"]
    build_id: str
    candidate_dir: Path | None
    final_dir: Path | None
    identity: Any
    stage_reports: tuple[Mapping[str, Any], ...] = ()


@dataclass(slots=True)
class _OwnedStaging:
    path: Path
    marker_token: str
    handle: int | None = None
    identity: tuple[int, int] | None = None
    parent_handle: int | None = None
    parent_identity: tuple[int, int] | None = None
    ancestor_chain: tuple[tuple[Path, int, tuple[int, int]], ...] = ()


@dataclass(slots=True)
class _ReservedFile:
    path: Path
    guard_path: Path
    guard_handle: int
    parent_chain: tuple[tuple[Path, int, tuple[int, int]], ...]
    destructive_started: bool = False
    completed: bool = False


@dataclass(frozen=True, slots=True)
class _WindowsFileInfo:
    identity: tuple[int, int]
    size: int
    link_count: int
    attributes: int


@dataclass(slots=True)
class _LockedRegular:
    path: Path
    descriptor: int
    info: _WindowsFileInfo
    parent_chain: tuple[tuple[Path, int, tuple[int, int]], ...]


@dataclass(slots=True)
class _HeldSidecarGuard:
    path: Path
    handle: int
    parent_chain: tuple[tuple[Path, int, tuple[int, int]], ...]


@dataclass(slots=True)
class _DirectoryLease:
    path: Path
    chain: tuple[tuple[Path, int, tuple[int, int]], ...] = ()


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return value.name
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ReleaseError(f"unsupported public value type: {type(value).__name__}")


def _public_identity(value: Any) -> dict[str, str]:
    names = (
        "build_id",
        "apk_sha256",
        "data_zip_sha256",
        "guide_sha256",
        "evidence_sha256",
    )
    if isinstance(value, Mapping):
        if set(value) != set(names):
            raise ReleaseError("candidate identity schema is invalid")
        source = value
    else:
        source = {name: getattr(value, name, None) for name in names}
    result = {name: str(source.get(name, "")) for name in names}
    if not _BUILD_ID_RE.fullmatch(result.get("build_id", "")):
        raise ReleaseError("candidate build_id is invalid")
    for name in names[1:]:
        if re.fullmatch(r"[0-9a-f]{64}", result[name]) is None:
            raise ReleaseError(f"candidate {name} is invalid")
    return result


def _configured_secrets() -> tuple[str, ...]:
    value = os.environ.get(PASSWORD_ENV)
    return (value,) if value else ()


def _validate_release_secret_scan(bundle_module: Any, target: Path) -> dict[str, Any]:
    findings = bundle_module.scan_release_for_secrets(
        target,
        secret_values=_configured_secrets(),
    )
    try:
        return dict(bundle_module.validate_release_secret_findings(findings))
    except bundle_module.BundleError as exc:
        raise ReleaseError(_redact(exc)) from exc


def _sanitized_child_environment() -> dict[str, str]:
    forbidden = PASSWORD_ENV.casefold()
    return {
        key: value
        for key, value in os.environ.items()
        if key.casefold() != forbidden
    }


def _redact(value: BaseException | object) -> str:
    text = str(value)
    try:
        import wf_offline_toolchain as toolchain_module

        text = toolchain_module.redact_process_error(value, secrets=_configured_secrets())
    except Exception:
        for secret in _configured_secrets():
            text = text.replace(secret, "<redacted>")
        text = _ABSOLUTE_RE.sub("<path>", text)
    for secret in _configured_secrets():
        text = text.replace(secret, "<redacted>")
        text = text.replace(secret.casefold(), "<redacted>")
    return text[:1000] or type(value).__name__


def _safe_exception(stage: str, error: BaseException) -> ReleaseError:
    return ReleaseError(f"{stage}: {_redact(error)}")


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _resolved_with_missing_tail(path: Path) -> Path:
    target = Path(os.path.abspath(path))
    missing: list[str] = []
    current = target
    while not _lexists(current):
        parent = current.parent
        if parent == current:
            raise ReleaseError("offline output has no resolvable existing ancestor")
        if not current.name or current.name in {".", ".."}:
            raise ReleaseError("offline output contains an invalid component")
        missing.append(current.name)
        current = parent
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise ReleaseError("offline output ancestor cannot be resolved safely") from exc
    for component in reversed(missing):
        resolved /= component
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    left_text = os.path.normcase(os.path.abspath(left))
    right_text = os.path.normcase(os.path.abspath(right))
    try:
        common = os.path.commonpath((left_text, right_text))
    except ValueError:
        return False
    return common in {left_text, right_text}


def _path_is_within(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(os.path.abspath(path))
    root_text = os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath((path_text, root_text)) == root_text
    except ValueError:
        return False


def _require_output_scope(target: Path) -> None:
    lexical = Path(os.path.abspath(target))
    resolved = _resolved_with_missing_tail(lexical)
    for protected in PROTECTED_OUTPUT_ROOTS:
        protected_lexical = Path(os.path.abspath(protected))
        protected_resolved = _resolved_with_missing_tail(protected_lexical)
        if _paths_overlap(lexical, protected_lexical) or _paths_overlap(
            resolved, protected_resolved
        ):
            raise ReleaseError(
                "offline output overlaps a protected live or user-WIP root"
            )
    repo_lexical = Path(os.path.abspath(REPO_ROOT))
    repo_resolved = _resolved_with_missing_tail(repo_lexical)
    canonical_lexical = Path(os.path.abspath(DEFAULT_OUTPUT_ROOT))
    canonical_resolved = _resolved_with_missing_tail(canonical_lexical)
    touches_repo = _path_is_within(lexical, repo_lexical) or _path_is_within(
        resolved, repo_resolved
    )
    if touches_repo and not (
        _path_is_within(lexical, canonical_lexical)
        and _path_is_within(resolved, canonical_resolved)
    ):
        raise ReleaseError(
            "repository-local offline output must stay inside out/wf-offline-android"
        )


def _require_safe_release_config(config: OfflineReleaseConfig) -> Path:
    if config.snapshot_version != DEFAULT_SNAPSHOT_VERSION:
        raise ReleaseError("unsupported offline snapshot version")
    version_root = Path(config.output_root) / DEFAULT_SNAPSHOT_VERSION
    _require_output_scope(version_root)
    return version_root


def _require_receipt_output_scope(
    config: OfflineReleaseConfig,
    candidate_id: str,
    receipt_out: Path,
) -> None:
    _require_safe_release_config(config)
    receipt = Path(os.path.abspath(receipt_out))
    _require_output_scope(receipt)
    receipt_resolved = _resolved_with_missing_tail(receipt)
    for protected in (
        _candidate_path(config, candidate_id),
        _final_path(config),
    ):
        protected_lexical = Path(os.path.abspath(protected))
        protected_resolved = _resolved_with_missing_tail(protected_lexical)
        if _paths_overlap(receipt, protected_lexical) or _paths_overlap(
            receipt_resolved, protected_resolved
        ):
            raise ReleaseError(
                "device acceptance receipt must stay outside candidate and final bundles"
            )


def _is_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & 0x400
    )


def _windows_directory_identity(raw: int) -> tuple[int, int]:
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

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileInformationByHandle.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    info = ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(raw, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not int(info.dwFileAttributes) & 0x10 or int(info.dwFileAttributes) & 0x400:
        raise ReleaseError("owned staging is not a plain directory")
    identity = (
        int(info.dwVolumeSerialNumber),
        (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
    )
    if identity[0] <= 0 or identity[1] <= 0:
        raise ReleaseError("release directory has no stable local identity")
    return identity


def _windows_directory_handle(
    path: Path,
    *,
    request_delete: bool = True,
    deny_delete: bool = True,
    list_directory: bool = True,
) -> tuple[int, tuple[int, int]]:
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
    # Ancestor handles only need traversal plus attributes.  Requesting
    # FILE_LIST_DIRECTORY all the way up the chain fails on otherwise
    # traversable profile directories with deliberately restrictive ACLs.
    desired_access = 0x0020 | 0x0080
    if list_directory:
        desired_access |= 0x0001
    if request_delete:
        desired_access |= 0x00010000
    share_mode = 0x00000001 | 0x00000002
    if not deny_delete:
        share_mode |= 0x00000004
    raw = kernel32.CreateFileW(
        str(path),
        desired_access,
        share_mode,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if raw == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        identity = _windows_directory_identity(int(raw))
    except BaseException:
        kernel32.CloseHandle(raw)
        raise
    return int(raw), identity


def _create_windows_owned_directory(
    parent_handle: int,
    leaf: str,
) -> tuple[int, tuple[int, int]]:
    """Atomically create and bind a directory relative to a held parent."""

    from ctypes import wintypes

    if not leaf or leaf in {".", ".."} or any(character in leaf for character in "\\/\0"):
        raise ReleaseError("owned staging leaf is invalid")

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

    encoded = leaf.encode("utf-16-le", "strict")
    name_buffer = ctypes.create_unicode_buffer(leaf)
    unicode_name = UnicodeString(
        len(encoded),
        len(encoded) + ctypes.sizeof(wintypes.WCHAR),
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
    output = wintypes.HANDLE()
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
    desired_access = (
        0x0001  # FILE_LIST_DIRECTORY
        | 0x0002  # FILE_ADD_FILE
        | 0x0004  # FILE_ADD_SUBDIRECTORY
        | 0x0020  # FILE_TRAVERSE
        | 0x0040  # FILE_DELETE_CHILD
        | 0x0080  # FILE_READ_ATTRIBUTES
        | 0x0100  # FILE_WRITE_ATTRIBUTES
        | 0x00010000  # DELETE
        | 0x00100000  # SYNCHRONIZE
    )
    status = int(
        ntdll.NtCreateFile(
            ctypes.byref(output),
            desired_access,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            0x10,  # FILE_ATTRIBUTE_DIRECTORY
            0x1 | 0x2,  # FILE_SHARE_READ | FILE_SHARE_WRITE (no delete)
            2,  # FILE_CREATE
            0x1 | 0x20 | 0x4000 | 0x00200000,
            None,
            0,
        )
    )
    if status < 0:
        leaked = int(output.value or 0)
        if leaked:
            _close_windows_handle(leaked)
        mapped = int(ntdll.RtlNtStatusToDosError(status))
        error = ctypes.WinError(mapped)
        error.add_note(f"NtCreateFile status=0x{status & 0xFFFFFFFF:08x}")
        raise error
    raw = int(output.value or 0)
    if raw <= 0 or int(io_status.Information) != 2:  # FILE_CREATED
        _close_windows_handle(raw)
        raise ReleaseError("owned staging was not created exclusively")
    try:
        return raw, _windows_directory_identity(raw)
    except BaseException:
        _close_windows_handle(raw)
        raise


def _windows_regular_handle_info(raw: int) -> _WindowsFileInfo:
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

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetFileInformationByHandle.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    info = ByHandleFileInformation()
    if not kernel32.GetFileInformationByHandle(raw, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    attributes = int(info.dwFileAttributes)
    if attributes & 0x10 or attributes & 0x400:
        raise ReleaseError("device preparation sidecar member is not a plain file")
    links = int(info.nNumberOfLinks)
    if links != 1:
        raise ReleaseError("device preparation sidecar member has hard-link aliases")
    identity = (
        int(info.dwVolumeSerialNumber),
        (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
    )
    if identity[0] <= 0 or identity[1] <= 0:
        raise ReleaseError("release file has no stable local identity")
    return _WindowsFileInfo(
        identity=identity,
        size=(int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
        link_count=links,
        attributes=attributes,
    )


def _windows_extended_path(path: Path) -> str:
    rendered = os.path.abspath(path)
    if rendered.startswith("\\\\?\\"):
        return rendered
    if rendered.startswith("\\\\"):
        return "\\\\?\\UNC\\" + rendered[2:]
    return "\\\\?\\" + rendered


def _windows_regular_path_info(path: Path) -> _WindowsFileInfo:
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
    raw = kernel32.CreateFileW(
        _windows_extended_path(path),
        0x0080,
        0x1 | 0x2 | 0x4,
        None,
        3,
        0x00200000,
        None,
    )
    if raw == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _windows_regular_handle_info(int(raw))
    finally:
        kernel32.CloseHandle(raw)


def _windows_regular_delete_handle(path: Path) -> tuple[int, _WindowsFileInfo]:
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
    raw = kernel32.CreateFileW(
        str(path),
        0x00010000 | 0x0080,
        0x1 | 0x2,
        None,
        3,
        0x00200000,
        None,
    )
    if raw == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return int(raw), _windows_regular_handle_info(int(raw))
    except BaseException:
        kernel32.CloseHandle(raw)
        raise


def _open_locked_regular(
    path: Path,
    *,
    bound_root: _OwnedStaging | None = None,
) -> _LockedRegular:
    if os.name != "nt":
        raise ReleaseError("stable sidecar reads require Windows handles")
    import msvcrt
    from ctypes import wintypes

    target = Path(os.path.abspath(path))
    chain = _open_windows_directory_chain(target.parent, bound_root=bound_root)
    raw = 0
    descriptor = -1
    try:
        for index, (member, _handle, identity) in enumerate(chain):
            _require_windows_bound_path(
                member,
                identity,
                label=f"device preparation read parent {index}",
            )
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
        candidate = kernel32.CreateFileW(
            str(target),
            0x80000000,
            0x1,
            None,
            3,
            0x00200000,
            None,
        )
        if candidate == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        raw = int(candidate)
        info = _windows_regular_handle_info(raw)
        rebound = _windows_regular_path_info(target)
        if rebound.identity != info.identity:
            raise ReleaseError("device preparation sidecar pathname identity changed")
        descriptor = msvcrt.open_osfhandle(
            raw,
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
        raw = 0
        return _LockedRegular(target, descriptor, info, chain)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        elif raw > 0:
            _close_windows_handle(raw)
        _close_windows_directory_chain(chain)
        raise


def _read_locked_regular(
    locked: _LockedRegular,
    *,
    max_bytes: int = 1024 * 1024,
) -> bytes:
    if locked.descriptor < 0:
        raise ReleaseError("device preparation sidecar handle is closed")
    import msvcrt

    for index, (member, _handle, identity) in enumerate(locked.parent_chain):
        _require_windows_bound_path(
            member,
            identity,
            label=f"device preparation read parent {index}",
        )
    raw_handle = int(msvcrt.get_osfhandle(locked.descriptor))
    before = _windows_regular_handle_info(raw_handle)
    if before != locked.info or before.size > max_bytes:
        raise ReleaseError("device preparation sidecar metadata changed")
    os.lseek(locked.descriptor, 0, os.SEEK_SET)
    payload = os.read(locked.descriptor, max_bytes + 1)
    after = _windows_regular_handle_info(raw_handle)
    rebound = _windows_regular_path_info(locked.path)
    if (
        before != after
        or rebound != locked.info
        or len(payload) != locked.info.size
    ):
        raise ReleaseError("device preparation sidecar changed while reading")
    return payload


def _close_locked_regular(locked: _LockedRegular) -> None:
    active_error: BaseException | None = None
    if locked.descriptor >= 0:
        try:
            os.close(locked.descriptor)
        except BaseException as exc:
            active_error = exc
        locked.descriptor = -1
    try:
        _close_windows_directory_chain(locked.parent_chain)
    except BaseException as exc:
        active_error = active_error or exc
    locked.parent_chain = ()
    if active_error is not None:
        raise ReleaseError("cannot close stable sidecar handles") from active_error


@contextlib.contextmanager
def _locked_regular_guard(
    path: Path,
    *,
    bound_root: _OwnedStaging | None = None,
):
    locked = _open_locked_regular(Path(path), bound_root=bound_root)
    try:
        yield locked
    finally:
        _close_locked_regular(locked)


def _open_locked_release_files(
    directory: Path,
    expected_names: Sequence[str],
) -> dict[str, _LockedRegular]:
    """Bind the complete release leaf set and deny writes/deletes until closed."""

    if os.name != "nt":
        raise ReleaseError("release verification requires stable Windows file handles")
    names = tuple(expected_names)
    if (
        not names
        or len(names) != len(set(names))
        or any(
            not isinstance(name, str)
            or not name
            or name in {".", ".."}
            or Path(name).name != name
            or any(character in name for character in "\\/\0")
            for name in names
        )
    ):
        raise ReleaseError("release verification file set is invalid")
    target = Path(directory)
    opened: dict[str, _LockedRegular] = {}
    try:
        observed = tuple(sorted(entry.name for entry in os.scandir(target)))
        if observed != tuple(sorted(names)):
            raise ReleaseError("release directory member set changed before verification")
        for name in names:
            opened[name] = _open_locked_regular(target / name)
        rebound = tuple(sorted(entry.name for entry in os.scandir(target)))
        if rebound != tuple(sorted(names)):
            raise ReleaseError("release directory member set changed while binding files")
        for name, locked in opened.items():
            if _windows_regular_path_info(target / name) != locked.info:
                raise ReleaseError("release file identity changed while binding files")
        return opened
    except BaseException:
        _close_locked_release_files(opened)
        raise


def _close_locked_release_files(locked_files: Mapping[str, _LockedRegular]) -> None:
    first_error: BaseException | None = None
    for locked in reversed(tuple(locked_files.values())):
        try:
            _close_locked_regular(locked)
        except BaseException as exc:
            first_error = first_error or exc
    if first_error is not None:
        raise ReleaseError("cannot close stable release file handles") from first_error


def _require_locked_release_files(
    directory: Path,
    locked_files: Mapping[str, _LockedRegular],
    expected_names: Sequence[str],
) -> None:
    names = tuple(expected_names)
    if tuple(locked_files) != names:
        raise ReleaseError("release verification lock set is incomplete")
    observed = tuple(sorted(entry.name for entry in os.scandir(directory)))
    if observed != tuple(sorted(names)):
        raise ReleaseError("release directory member set changed during verification")
    for name, locked in locked_files.items():
        current = _windows_regular_path_info(Path(directory) / name)
        if current != locked.info:
            raise ReleaseError("release file changed during verification")


def _run_release_cleanup(
    steps: Sequence[tuple[str, Callable[[], None]]],
) -> None:
    """Run every cleanup step; never strand later locks behind an early error."""

    active_error = sys.exception()
    failures: list[tuple[str, BaseException]] = []
    for label, operation in steps:
        try:
            operation()
        except BaseException as exc:
            failures.append((label, exc))
    if not failures:
        return
    if active_error is not None:
        for label, failure in failures:
            active_error.add_note(
                f"release cleanup failed at {label}: {type(failure).__name__}"
            )
        return
    error = ReleaseError(
        "release verification cleanup failed: "
        + ", ".join(label for label, _failure in failures)
    )
    for label, failure in failures[1:]:
        error.add_note(f"additional cleanup failure at {label}: {type(failure).__name__}")
    raise error from failures[0][1]


def _nt_create_windows_regular(
    parent_handle: int,
    leaf: str,
    *,
    request_delete: bool = True,
) -> int:
    """CREATE_NEW one regular file relative to a held directory handle."""

    from ctypes import wintypes

    if not leaf or leaf in {".", ".."} or any(character in leaf for character in "\\/\0"):
        raise ReleaseError("device preparation sidecar leaf is invalid")

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

    encoded = leaf.encode("utf-16-le", "strict")
    name_buffer = ctypes.create_unicode_buffer(leaf)
    unicode_name = UnicodeString(
        len(encoded),
        len(encoded) + ctypes.sizeof(wintypes.WCHAR),
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        wintypes.HANDLE(parent_handle),
        ctypes.pointer(unicode_name),
        0x00000040 | 0x00001000,
        None,
        None,
    )
    io_status = IoStatusBlock()
    output = wintypes.HANDLE()
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
    desired_access = 0x0001 | 0x0002 | 0x0080 | 0x0100 | 0x00100000
    if request_delete:
        desired_access |= 0x00010000
    status = int(
        ntdll.NtCreateFile(
            ctypes.byref(output),
            desired_access,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            0x100,  # FILE_ATTRIBUTE_TEMPORARY
            0x1,  # FILE_SHARE_READ only; deny writes/deletes/rebinds
            2,  # FILE_CREATE
            0x20 | 0x40 | 0x00200000,
            None,
            0,
        )
    )
    if status < 0:
        leaked = int(output.value or 0)
        if leaked:
            _close_windows_handle(leaked)
        mapped = int(ntdll.RtlNtStatusToDosError(status))
        error = ctypes.WinError(mapped)
        error.add_note(f"NtCreateFile status=0x{status & 0xFFFFFFFF:08x}")
        raise error
    raw = int(output.value or 0)
    if raw <= 0 or int(io_status.Information) != 2:
        _close_windows_handle(raw)
        raise ReleaseError("device preparation sidecar member was not created exclusively")
    try:
        _windows_regular_handle_info(raw)
    except BaseException:
        _close_windows_handle(raw)
        raise
    return raw


def _rename_windows_file_relative_no_replace(
    file_handle: int,
    parent_handle: int,
    leaf: str,
) -> None:
    from ctypes import wintypes

    if not leaf or leaf in {".", ".."} or any(character in leaf for character in "\\/\0"):
        raise ReleaseError("device preparation destination leaf is invalid")

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

    encoded = leaf.encode("utf-16-le", "strict")
    size = max(
        ctypes.sizeof(FileRenameInfo),
        FileRenameInfo.FileName.offset + len(encoded),
    )
    buffer = ctypes.create_string_buffer(size)
    rename = FileRenameInfo.from_buffer(buffer)
    rename.ReplaceIfExists = False
    rename.RootDirectory = wintypes.HANDLE(parent_handle)
    rename.FileNameLength = len(encoded)
    ctypes.memmove(
        ctypes.addressof(buffer) + FileRenameInfo.FileName.offset,
        encoded,
        len(encoded),
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
            size,
            10,
        )
    )
    if status < 0:
        mapped = int(ntdll.RtlNtStatusToDosError(status))
        error = ctypes.WinError(mapped)
        error.add_note(f"NtSetInformationFile status=0x{status & 0xFFFFFFFF:08x}")
        raise error


def _close_windows_handle(raw: int | None) -> None:
    if raw is None or os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle(raw)


def _duplicate_windows_handle(raw: int) -> int:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.DuplicateHandle.argtypes = (
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.DuplicateHandle.restype = wintypes.BOOL
    process = kernel32.GetCurrentProcess()
    duplicate = wintypes.HANDLE()
    if not kernel32.DuplicateHandle(
        process,
        wintypes.HANDLE(raw),
        process,
        ctypes.byref(duplicate),
        0,
        False,
        0x00000002,  # DUPLICATE_SAME_ACCESS
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    value = int(duplicate.value or 0)
    if value <= 0:
        raise ReleaseError("cannot duplicate a stable release file handle")
    return value


def _mark_directory_delete(raw: int) -> None:
    from ctypes import wintypes

    class FileDispositionInfo(ctypes.Structure):
        _fields_ = (("DeleteFile", wintypes.BOOLEAN),)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    )
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    disposition = FileDispositionInfo(True)
    if not kernel32.SetFileInformationByHandle(
        raw, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _create_owned_staging(version_root: Path) -> _OwnedStaging:
    handle: int | None = None
    identity: tuple[int, int] | None = None
    parent_handle: int | None = None
    parent_identity: tuple[int, int] | None = None
    ancestor_chain: tuple[tuple[Path, int, tuple[int, int]], ...] = ()
    if os.name == "nt":
        try:
            ancestor_chain = _open_or_create_windows_directory_chain(version_root)
            _parent_path, parent_handle, parent_identity = ancestor_chain[-1]
        except BaseException as exc:
            raise ReleaseError("cannot bind owned staging parent") from exc
    else:
        _ensure_posix_plain_directory(version_root)
        parent_metadata = version_root.lstat()
        parent_identity = (int(parent_metadata.st_dev), int(parent_metadata.st_ino))
    token = uuid.uuid4().hex
    path = version_root / f".staging-{token}"
    try:
        if os.name == "nt":
            assert parent_handle is not None
            handle, identity = _create_windows_owned_directory(
                parent_handle, path.name
            )
        else:
            path.mkdir(mode=0o700)
            metadata = path.lstat()
            identity = (int(metadata.st_dev), int(metadata.st_ino))
    except FileExistsError as exc:
        _close_windows_directory_chain(ancestor_chain)
        raise ReleaseError("owned staging already exists") from exc
    except BaseException:
        _close_windows_directory_chain(ancestor_chain)
        raise
    marker = path / ".offline-release-owner.json"
    try:
        _write_exclusive(
            marker,
            _canonical_bytes({"schema_version": 1, "token": token}),
        )
        if os.name == "nt":
            _require_windows_bound_path(
                path,
                identity,
                label="owned staging root after marker write",
            )
    except BaseException as exc:
        cleanup_error: BaseException | None = None
        try:
            if os.name == "nt":
                _require_windows_bound_path(
                    path,
                    identity,
                    label="failed owned staging root",
                )
                assert handle is not None
                assert identity is not None
                _remove_tree_contents(
                    path,
                    bound_handle=handle,
                    bound_identity=identity,
                )
                _mark_directory_delete(handle)
            elif identity is not None:
                metadata = path.lstat()
                if (int(metadata.st_dev), int(metadata.st_ino)) != identity:
                    raise ReleaseError("failed owned staging identity changed")
                _remove_tree_contents(path)
                path.rmdir()
        except BaseException as cleanup_exc:
            cleanup_error = cleanup_exc
        _close_windows_handle(handle)
        _close_windows_directory_chain(ancestor_chain)
        if cleanup_error is not None:
            exc.add_note("failed to clean an unmarked handle-bound staging directory")
        raise
    return _OwnedStaging(
        path,
        token,
        handle,
        identity,
        parent_handle,
        parent_identity,
        ancestor_chain,
    )


def _windows_drive_type(root: str) -> int:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    return int(kernel32.GetDriveTypeW(root))


def _windows_chain_paths(path: Path) -> tuple[Path, ...]:
    target = Path(os.path.abspath(path))
    anchor = Path(target.anchor)
    if (
        not target.anchor
        or re.fullmatch(r"[A-Za-z]:", target.drive) is None
        or target.anchor.startswith("\\\\")
    ):
        raise ReleaseError("release output must use one local Windows drive")
    if _windows_drive_type(str(anchor)) != 3:  # DRIVE_FIXED
        raise ReleaseError("release output must use one fixed local Windows drive")
    paths = [anchor]
    current = anchor
    for part in target.parts[1:]:
        current = current / part
        paths.append(current)
    return tuple(paths)


def _windows_directory_chain_plan(
    path: Path,
    *,
    bound_root: _OwnedStaging | None,
) -> tuple[
    list[tuple[Path, int, tuple[int, int]]],
    tuple[Path, ...],
]:
    """Duplicate an owned-root prefix and return descendants still to open."""

    members = _windows_chain_paths(path)
    if bound_root is None:
        return [], members
    if (
        bound_root.handle is None
        or bound_root.handle <= 0
        or bound_root.identity is None
        or not bound_root.ancestor_chain
    ):
        raise ReleaseError("owned staging has no complete Windows handle chain")
    owned_path = Path(os.path.abspath(bound_root.path))
    source_prefix = (
        *(
            (Path(os.path.abspath(member)), raw_handle, identity)
            for member, raw_handle, identity in bound_root.ancestor_chain
        ),
        (owned_path, bound_root.handle, bound_root.identity),
    )
    source_paths = tuple(member for member, _raw_handle, _identity in source_prefix)
    if len(members) < len(source_paths) or members[: len(source_paths)] != source_paths:
        raise ReleaseError("release directory is outside the bound owned staging root")

    duplicated: list[tuple[Path, int, tuple[int, int]]] = []
    try:
        for index, (member, raw_handle, identity) in enumerate(source_prefix):
            _require_windows_bound_path(
                member,
                identity,
                label=f"bound release ancestor {index}",
            )
            if _windows_directory_identity(raw_handle) != identity:
                raise ReleaseError("bound release ancestor handle identity changed")
            duplicate = _duplicate_windows_handle(raw_handle)
            try:
                if _windows_directory_identity(duplicate) != identity:
                    raise ReleaseError("duplicated release ancestor identity changed")
            except BaseException:
                _close_windows_handle(duplicate)
                raise
            duplicated.append((member, duplicate, identity))
    except BaseException:
        _close_windows_directory_chain(tuple(duplicated))
        raise
    return duplicated, members[len(source_paths) :]


def _open_or_create_windows_directory_chain(
    path: Path,
    *,
    bound_root: _OwnedStaging | None = None,
) -> tuple[tuple[Path, int, tuple[int, int]], ...]:
    """Create missing plain directories while holding every existing ancestor."""

    opened, remaining = _windows_directory_chain_plan(path, bound_root=bound_root)
    try:
        for index, member in enumerate(remaining, start=len(opened)):
            try:
                handle, identity = _windows_directory_handle(
                    member,
                    request_delete=False,
                    deny_delete=True,
                    list_directory=False,
                )
            except FileNotFoundError:
                # Every ancestor is already held without FILE_SHARE_DELETE, so
                # this single-component create cannot be redirected.  A racing
                # pre-created object makes mkdir fail closed; it is never
                # accepted via exist_ok or followed as a reparse point.
                member.mkdir(mode=0o700)
                handle, identity = _windows_directory_handle(
                    member,
                    request_delete=False,
                    deny_delete=True,
                    list_directory=False,
                )
            opened.append((member, handle, identity))
            _require_windows_bound_path(
                member,
                identity,
                label=f"release output ancestor {index}",
            )
    except BaseException:
        _close_windows_directory_chain(tuple(opened))
        raise
    return tuple(opened)


def _open_windows_directory_chain(
    path: Path,
    *,
    bound_root: _OwnedStaging | None = None,
) -> tuple[tuple[Path, int, tuple[int, int]], ...]:
    opened, remaining = _windows_directory_chain_plan(path, bound_root=bound_root)
    try:
        for member in remaining:
            handle, identity = _windows_directory_handle(
                member,
                request_delete=False,
                deny_delete=True,
                list_directory=False,
            )
            opened.append((member, handle, identity))
    except BaseException:
        _close_windows_directory_chain(tuple(opened))
        raise
    return tuple(opened)


def _ensure_posix_plain_directory(path: Path) -> None:
    target = Path(os.path.abspath(path))
    missing: list[Path] = []
    current = target
    while not _lexists(current):
        if current.parent == current:
            raise ReleaseError("release output has no existing ancestor")
        missing.append(current)
        current = current.parent
    for member in (current, *reversed(missing)):
        if not _lexists(member):
            member.mkdir(mode=0o700)
        metadata = member.lstat()
        if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise ReleaseError("release output contains a reparse or non-directory component")


def _acquire_directory_lease(
    path: Path,
    *,
    create: bool = True,
    bound_root: _OwnedStaging | None = None,
) -> _DirectoryLease:
    target = Path(os.path.abspath(path))
    try:
        if os.name == "nt":
            return _DirectoryLease(
                target,
                (
                    _open_or_create_windows_directory_chain(
                        target,
                        bound_root=bound_root,
                    )
                    if create
                    else _open_windows_directory_chain(
                        target,
                        bound_root=bound_root,
                    )
                ),
            )
        if create:
            _ensure_posix_plain_directory(target)
        else:
            metadata = target.lstat()
            if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise ReleaseError("release directory is not a plain directory")
        return _DirectoryLease(target)
    except ReleaseError:
        raise
    except BaseException as exc:
        raise ReleaseError("cannot bind release output directory") from exc


def _release_directory_lease(lease: _DirectoryLease) -> None:
    _close_windows_directory_chain(lease.chain)
    lease.chain = ()


def _close_windows_directory_chain(
    chain: tuple[tuple[Path, int, tuple[int, int]], ...]
) -> None:
    for _path, handle, _identity in reversed(chain):
        _close_windows_handle(handle)


def _require_windows_bound_path(path: Path, expected: tuple[int, int] | None, *, label: str) -> None:
    if expected is None:
        raise ReleaseError(f"{label} has no stable identity")
    opened: int | None = None
    try:
        opened, actual = _windows_directory_handle(
            path,
            request_delete=False,
            deny_delete=False,
            list_directory=False,
        )
        if actual != expected:
            raise ReleaseError(f"{label} identity changed")
    except ReleaseError:
        raise
    except OSError as exc:
        raise ReleaseError(f"{label} identity changed") from exc
    finally:
        _close_windows_handle(opened)


def _remove_tree_contents(
    path: Path,
    *,
    bound_handle: int | None = None,
    bound_identity: tuple[int, int] | None = None,
) -> None:
    if os.name == "nt":
        if bound_handle is None or bound_identity is None:
            raise ReleaseError("owned staging child has no stable Windows binding")
        if _windows_directory_identity(bound_handle) != bound_identity:
            raise ReleaseError("owned staging cleanup handle identity changed")
        _require_windows_bound_path(
            path,
            bound_identity,
            label="owned staging cleanup directory",
        )
    with os.scandir(path) as iterator:
        entries = list(iterator)
    for entry in entries:
        if entry.name in {"", ".", ".."} or Path(entry.name).name != entry.name:
            raise ReleaseError("owned staging contains an invalid child name")
        child = Path(entry.path)
        metadata = child.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ReleaseError("owned staging contains a reparse point")
        if stat.S_ISDIR(metadata.st_mode):
            if os.name == "nt":
                child_handle: int | None = None
                try:
                    child_handle, child_identity = _windows_directory_handle(child)
                    if int(metadata.st_ino) != child_identity[1]:
                        raise ReleaseError("owned staging child identity changed after lstat")
                    _require_windows_bound_path(
                        child,
                        child_identity,
                        label="owned staging child directory",
                    )
                    _remove_tree_contents(
                        child,
                        bound_handle=child_handle,
                        bound_identity=child_identity,
                    )
                    _require_windows_bound_path(
                        child,
                        child_identity,
                        label="owned staging child directory after cleanup",
                    )
                    _mark_directory_delete(child_handle)
                finally:
                    _close_windows_handle(child_handle)
            else:
                _remove_tree_contents(child)
                child.rmdir()
        elif stat.S_ISREG(metadata.st_mode):
            if os.name == "nt":
                file_handle: int | None = None
                try:
                    file_handle, file_info = _windows_regular_delete_handle(child)
                    if (
                        int(metadata.st_ino) != file_info.identity[1]
                        or int(metadata.st_size) != file_info.size
                    ):
                        raise ReleaseError("owned staging file identity changed after lstat")
                    rebound = _windows_regular_path_info(child)
                    if rebound != file_info:
                        raise ReleaseError("owned staging file pathname identity changed")
                    _mark_directory_delete(file_handle)
                finally:
                    _close_windows_handle(file_handle)
            else:
                child.unlink()
        else:
            raise ReleaseError("owned staging contains a non-regular member")
    if os.name == "nt":
        assert bound_handle is not None
        assert bound_identity is not None
        if _windows_directory_identity(bound_handle) != bound_identity:
            raise ReleaseError("owned staging cleanup handle changed after traversal")
        _require_windows_bound_path(
            path,
            bound_identity,
            label="owned staging cleanup directory after traversal",
        )
        with os.scandir(path) as iterator:
            if next(iterator, None) is not None:
                raise ReleaseError("owned staging changed during cleanup")


def _cleanup_owned_staging(owned: _OwnedStaging) -> None:
    active_error: BaseException | None = None
    try:
        if os.name == "nt":
            if owned.handle is None or owned.parent_handle is None:
                raise ReleaseError("owned staging handles are closed")
            if not owned.ancestor_chain:
                raise ReleaseError("owned staging ancestor chain is closed")
            for index, (member, _handle, identity) in enumerate(owned.ancestor_chain):
                _require_windows_bound_path(
                    member,
                    identity,
                    label=f"owned staging ancestor {index}",
                )
            _require_windows_bound_path(
                owned.path,
                owned.identity,
                label="owned staging root",
            )
        marker = owned.path / ".offline-release-owner.json"
        document = json.loads(marker.read_text(encoding="utf-8"))
        if document != {"schema_version": 1, "token": owned.marker_token}:
            raise ReleaseError("owned staging marker mismatch")
        metadata = owned.path.lstat()
        current = (int(metadata.st_dev), int(metadata.st_ino))
        if os.name != "nt" and current != owned.identity:
            raise ReleaseError("owned staging identity changed")
        if os.name == "nt":
            assert owned.handle is not None
            assert owned.identity is not None
            _remove_tree_contents(
                owned.path,
                bound_handle=owned.handle,
                bound_identity=owned.identity,
            )
            _mark_directory_delete(owned.handle)
        else:
            _remove_tree_contents(owned.path)
            owned.path.rmdir()
    except BaseException as exc:
        active_error = exc
    finally:
        _close_windows_handle(owned.handle)
        owned.handle = None
        _close_windows_directory_chain(owned.ancestor_chain)
        owned.ancestor_chain = ()
        owned.parent_handle = None
    if active_error is not None:
        raise ReleaseError("cannot clean handle-bound owned staging") from active_error


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sidecar_guard_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.reserve")


def _acquire_sidecar_guard(path: Path) -> _HeldSidecarGuard:
    if os.name != "nt":
        raise ReleaseError("device preparation sidecars require stable Windows handles")
    target = Path(os.path.abspath(path))
    guard = _sidecar_guard_path(target)
    chain: tuple[tuple[Path, int, tuple[int, int]], ...] = ()
    raw = 0
    try:
        chain = _open_windows_directory_chain(target.parent)
        for index, (member, _handle, identity) in enumerate(chain):
            _require_windows_bound_path(
                member,
                identity,
                label=f"device preparation guard parent {index}",
            )
        try:
            raw = _nt_create_windows_regular(chain[-1][1], guard.name)
        except OSError as exc:
            if getattr(exc, "winerror", None) in {80, 183}:
                raise ReleaseError(
                    "device preparation sidecar reservation crash-poison exists"
                ) from exc
            raise
        info = _windows_regular_handle_info(raw)
        rebound = _windows_regular_path_info(guard)
        if rebound.identity != info.identity:
            raise ReleaseError("device preparation sidecar guard identity changed")
        return _HeldSidecarGuard(guard, raw, chain)
    except BaseException:
        if raw > 0:
            try:
                _mark_directory_delete(raw)
            finally:
                _close_windows_handle(raw)
        _close_windows_directory_chain(chain)
        raise


def _release_sidecar_guard(guard: _HeldSidecarGuard) -> None:
    active_error: BaseException | None = None
    if guard.handle > 0:
        try:
            _mark_directory_delete(guard.handle)
        except BaseException as exc:
            active_error = exc
        finally:
            _close_windows_handle(guard.handle)
            guard.handle = 0
    try:
        _close_windows_directory_chain(guard.parent_chain)
    except BaseException as exc:
        active_error = active_error or exc
    guard.parent_chain = ()
    if active_error is not None:
        raise ReleaseError("cannot release device preparation sidecar guard") from active_error


def _reserve_file(path: Path) -> _ReservedFile:
    if os.name != "nt":
        raise ReleaseError("device preparation sidecars require stable Windows handles")
    target = Path(os.path.abspath(path))
    guard = _sidecar_guard_path(target)
    chain: tuple[tuple[Path, int, tuple[int, int]], ...] = ()
    guard_handle = 0
    try:
        chain = _open_windows_directory_chain(target.parent)
        for index, (member, _handle, identity) in enumerate(chain):
            _require_windows_bound_path(
                member,
                identity,
                label=f"device preparation parent {index}",
            )
        if _lexists(target):
            raise ReleaseError("device preparation sidecar already exists")
        try:
            guard_handle = _nt_create_windows_regular(chain[-1][1], guard.name)
        except OSError as exc:
            if getattr(exc, "winerror", None) in {80, 183}:
                raise ReleaseError(
                    "device preparation sidecar reservation already exists"
                ) from exc
            raise
        if _lexists(target):
            raise ReleaseError("device preparation sidecar already exists")
        guard_info = _windows_regular_handle_info(guard_handle)
        rebound = _windows_regular_path_info(guard)
        if rebound.identity != guard_info.identity:
            raise ReleaseError("device preparation sidecar reservation identity changed")
        return _ReservedFile(target, guard, guard_handle, chain)
    except BaseException:
        if guard_handle > 0:
            try:
                _mark_directory_delete(guard_handle)
            finally:
                _close_windows_handle(guard_handle)
        _close_windows_directory_chain(chain)
        raise


def _finish_reserved_file(reserved: _ReservedFile, payload: bytes) -> None:
    if reserved.completed or reserved.guard_handle <= 0 or not reserved.parent_chain:
        raise ReleaseError("device preparation sidecar reservation is closed")
    if not reserved.destructive_started:
        raise ReleaseError("device preparation sidecar cannot publish before preparation")
    import msvcrt

    raw_handle = 0
    descriptor = -1
    temporary_path: Path | None = None
    published = False
    try:
        for index, (member, _handle, identity) in enumerate(reserved.parent_chain):
            _require_windows_bound_path(
                member,
                identity,
                label=f"device preparation parent {index}",
            )
        parent_handle = reserved.parent_chain[-1][1]
        for _attempt in range(128):
            temporary_path = reserved.path.with_name(
                f".{reserved.path.name}.tmp-{uuid.uuid4().hex}"
            )
            try:
                raw_handle = _nt_create_windows_regular(
                    parent_handle, temporary_path.name
                )
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {80, 183}:
                    raise
        if raw_handle <= 0 or temporary_path is None:
            raise ReleaseError("cannot allocate device preparation sidecar staging file")
        initial = _windows_regular_handle_info(raw_handle)
        descriptor = msvcrt.open_osfhandle(
            raw_handle,
            os.O_RDWR | getattr(os, "O_BINARY", 0),
        )
        raw_handle = 0
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        active_handle = int(msvcrt.get_osfhandle(descriptor))
        finished = _windows_regular_handle_info(active_handle)
        if finished.identity != initial.identity or finished.size != len(payload):
            raise ReleaseError("device preparation sidecar staging identity changed")
        rebound = _windows_regular_path_info(temporary_path)
        if rebound.identity != initial.identity:
            raise ReleaseError("device preparation sidecar staging path changed")
        os.lseek(descriptor, 0, os.SEEK_SET)
        actual = os.read(descriptor, len(payload) + 1)
        if actual != payload:
            raise ReleaseError("device preparation sidecar staging bytes changed")
        _rename_windows_file_relative_no_replace(
            active_handle,
            parent_handle,
            reserved.path.name,
        )
        temporary_path = reserved.path
        published = True
        for index, (member, _handle, identity) in enumerate(reserved.parent_chain):
            _require_windows_bound_path(
                member,
                identity,
                label=f"device preparation parent {index}",
            )
        final_info = _windows_regular_path_info(reserved.path)
        if final_info.identity != initial.identity or final_info.size != len(payload):
            raise ReleaseError("published device preparation sidecar identity changed")
        current = _windows_regular_handle_info(active_handle)
        if current != final_info:
            raise ReleaseError("published device preparation sidecar handle changed")
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.read(descriptor, len(payload) + 1) != payload:
            raise ReleaseError("published device preparation sidecar bytes changed")
    except BaseException:
        cleanup_handle = raw_handle
        if descriptor >= 0:
            cleanup_handle = int(msvcrt.get_osfhandle(descriptor))
        if cleanup_handle > 0:
            try:
                _mark_directory_delete(cleanup_handle)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                    descriptor = -1
                else:
                    _close_windows_handle(cleanup_handle)
                    raw_handle = 0
        raise
    if not published:
        raise ReleaseError("device preparation sidecar was not published")
    os.close(descriptor)
    descriptor = -1
    try:
        _mark_directory_delete(reserved.guard_handle)
    finally:
        _close_windows_handle(reserved.guard_handle)
        reserved.guard_handle = 0
    _close_windows_directory_chain(reserved.parent_chain)
    reserved.parent_chain = ()
    reserved.completed = True


def _abort_reserved_file(reserved: _ReservedFile) -> None:
    if reserved.completed:
        return
    active_error: BaseException | None = None
    if reserved.guard_handle > 0:
        try:
            if not reserved.destructive_started:
                _mark_directory_delete(reserved.guard_handle)
        except BaseException as exc:
            active_error = exc
        finally:
            _close_windows_handle(reserved.guard_handle)
            reserved.guard_handle = 0
    try:
        _close_windows_directory_chain(reserved.parent_chain)
    except BaseException as exc:
        active_error = active_error or exc
    reserved.parent_chain = ()
    if active_error is not None:
        raise ReleaseError("cannot close device preparation reservation") from active_error


def _write_failure_receipt(
    config: OfflineReleaseConfig,
    *,
    command: str,
    error: BaseException,
    stage: str | None = None,
) -> None:
    reserved: _ReservedFile | None = None
    lease: _DirectoryLease | None = None
    try:
        version_root = _require_safe_release_config(config)
        failures = version_root / "failures"
        lease = _acquire_directory_lease(failures)
        document = {
            "command": command,
            "error": _redact(error),
            "stage": stage,
            "status": "error",
        }
        reserved = _reserve_file(
            failures / f"failure-{uuid.uuid4().hex}.json"
        )
        reserved.destructive_started = True
        _finish_reserved_file(reserved, _canonical_bytes(document))
    except BaseException:
        if reserved is not None:
            try:
                _abort_reserved_file(reserved)
            except BaseException:
                pass
        return
    finally:
        if lease is not None:
            try:
                _release_directory_lease(lease)
            except BaseException:
                pass


def _normalise_stage_report(name: str, value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and set(value) == {"name", "status", "evidence"}:
        report = dict(value)
    else:
        report = {"name": name, "status": "ok", "evidence": _json_value(value)}
    if report["name"] != name or report["status"] != "ok" or not isinstance(
        report["evidence"], Mapping
    ):
        raise ReleaseError(f"{name} returned an invalid stage report")
    # Prove the report is JSON-safe before it can be returned or persisted.
    json.loads(_canonical_bytes(report))
    return report


def _validate_preflight(report: Mapping[str, Any]) -> str:
    evidence = report.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ReleaseError("preflight evidence is invalid")
    build_id = evidence.get("build_id")
    if not isinstance(build_id, str) or _BUILD_ID_RE.fullmatch(build_id) is None:
        raise ReleaseError("preflight build_id is invalid")
    if evidence.get("signer_ready") is not True:
        raise ReleaseError("offline signer is not ready")
    if evidence.get("fingerprint_verified") is not True:
        raise ReleaseError("offline signer fingerprint is not verified")
    certificate = evidence.get("certificate_sha256")
    if not isinstance(certificate, str) or re.fullmatch(r"[0-9a-f]{64}", certificate) is None:
        raise ReleaseError("offline signer certificate fingerprint is invalid")
    free = evidence.get("disk_free_bytes")
    required = evidence.get("disk_required_bytes")
    if not isinstance(free, int) or not isinstance(required, int) or free < required:
        raise ReleaseError("insufficient disk space for offline release")
    actual = evidence.get("source_apk_sha256")
    expected = evidence.get("expected_source_apk_sha256")
    if not isinstance(actual, str) or actual != expected:
        raise ReleaseError("source APK hash does not match the accepted baseline")
    if evidence.get("store_counts") != EXPECTED_STORE_COUNTS:
        raise ReleaseError("preflight store root count mismatch")
    exact_counts = {
        "legacy_count": EXPECTED_LEGACY_COUNT,
        "current_count": EXPECTED_CURRENT_COUNT,
        "added_count": EXPECTED_ADDED_COUNT,
        "missing_count": 0,
        "tail_member_count": EXPECTED_TAIL_COUNT,
    }
    for name, expected_value in exact_counts.items():
        if evidence.get(name) != expected_value:
            raise ReleaseError(f"preflight {name} mismatch")
    return build_id


def _require_verified_signer_report(
    report: Mapping[str, Any],
    signing: Any,
) -> None:
    expected = str(getattr(signing, "expected_certificate_sha256", "")).casefold()
    actual = report.get("certificate_sha256")
    if (
        report.get("signer_ready") is not True
        or report.get("fingerprint_verified") is not True
        or not isinstance(actual, str)
        or len(expected) != 64
        or not hmac.compare_digest(actual.casefold(), expected)
    ):
        raise ReleaseError("offline signer verification report is invalid")


def _source_checkpoint(value: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    expected_fields = {
        "source_apk_sha256",
        "store_tree_sha256",
        "source_apk_size",
        "store_total_bytes",
        "store_counts",
    }
    if set(value) != expected_fields:
        raise ReleaseError(f"{label} source fingerprint schema mismatch")
    result = dict(value)
    for name in ("source_apk_sha256", "store_tree_sha256"):
        if not isinstance(result.get(name), str) or re.fullmatch(
            r"[0-9a-f]{64}", str(result[name])
        ) is None:
            raise ReleaseError(f"{label} {name} is invalid")
    for name in ("source_apk_size", "store_total_bytes"):
        if type(result.get(name)) is not int or int(result[name]) < 0:
            raise ReleaseError(f"{label} {name} is invalid")
    if result.get("store_counts") != EXPECTED_STORE_COUNTS:
        raise ReleaseError(f"{label} store counts mismatch")
    result["store_counts"] = dict(EXPECTED_STORE_COUNTS)
    return result


def _scan_source_checkpoint(
    before: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = report.get("evidence")
    if not isinstance(evidence, Mapping):
        raise ReleaseError("scan-store evidence is invalid")
    checkpoint = {
        "source_apk_sha256": before.get("source_apk_sha256"),
        "store_tree_sha256": evidence.get("tree_sha256"),
        "source_apk_size": before.get("source_apk_size"),
        "store_total_bytes": evidence.get("total_bytes"),
        "store_counts": evidence.get("counts"),
    }
    return _source_checkpoint(checkpoint, label="scan-store")


def _require_same_sources(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    left = _source_checkpoint(before, label="before")
    right = _source_checkpoint(after, label="after")
    if not hmac.compare_digest(left["source_apk_sha256"], right["source_apk_sha256"]):
        raise ReleaseError("source APK drift during offline build")
    if not hmac.compare_digest(left["store_tree_sha256"], right["store_tree_sha256"]):
        raise ReleaseError("source store drift during offline build")
    if left["source_apk_size"] != right["source_apk_size"]:
        raise ReleaseError("source APK size drift during offline build")
    if (
        left["store_total_bytes"] != right["store_total_bytes"]
        or left["store_counts"] != right["store_counts"]
    ):
        raise ReleaseError("source store inventory drift during offline build")


def _candidate_path(config: OfflineReleaseConfig, build_id: str) -> Path:
    if not isinstance(build_id, str) or _BUILD_ID_RE.fullmatch(build_id) is None:
        raise ReleaseError("candidate build_id is invalid")
    return Path(config.output_root) / config.snapshot_version / f".candidate-{build_id}"


def _final_path(config: OfflineReleaseConfig) -> Path:
    return Path(config.output_root) / config.snapshot_version / FINAL_DIR_NAME


def _build_candidate_bound(
    config: OfflineReleaseConfig,
    *,
    services: Any | None = None,
) -> ReleaseResult:
    service = services or RealReleaseServices(config)
    owned: _OwnedStaging | None = None
    stage_name = "source-fingerprint"
    reports: list[Mapping[str, Any]] = []
    try:
        source_before = service.fingerprint_sources(config)
        stage_name = "preflight"
        preflight = _normalise_stage_report(
            "preflight", service.preflight(config, source_fingerprint=source_before)
        )
        reports.append(preflight)
        build_id = _validate_preflight(preflight)
        candidate = _candidate_path(config, build_id)
        final = _final_path(config)
        if _lexists(candidate):
            raise ReleaseError("candidate already exists")
        if _lexists(final):
            raise ReleaseError("final already exists")
        owned = _create_owned_staging(Path(config.output_root) / config.snapshot_version)

        operations = (
            ("scan-store", service.scan_store),
            ("legacy-tail-gates", service.legacy_tail_gates),
            ("copy-snapshot", service.copy_snapshot),
            ("player-overlay", service.player_overlay),
            ("content-data-gates", service.content_data_gates),
            ("build-apk", service.build_apk),
            ("content-client-gate", service.content_client_gate),
            ("build-zip", service.build_zip),
            ("verify-zip", service.verify_zip),
        )
        for stage_name, operation in operations:
            stage_report = _normalise_stage_report(
                stage_name,
                operation(
                    config,
                    staging_dir=owned.path,
                    build_id=build_id,
                    stage_reports=tuple(reports),
                ),
            )
            reports.append(stage_report)
            if stage_name == "scan-store":
                scan_checkpoint = _scan_source_checkpoint(source_before, stage_report)
                _require_same_sources(source_before, scan_checkpoint)

        # This second call is deliberately after every source-reading build
        # stage and before candidate publication.
        stage_name = "source-fingerprint"
        source_after = service.fingerprint_sources(config)
        _require_same_sources(source_before, source_after)
        source_fingerprint = {
            "before": _source_checkpoint(source_before, label="before"),
            "scan": scan_checkpoint,
            "after": _source_checkpoint(source_after, label="after"),
            "unchanged": True,
        }

        for stage_name, operation in (
            ("render-guide", service.render_guide),
            ("freeze-candidate", service.freeze_candidate),
            ("secret-scan", service.secret_scan),
        ):
            reports.append(
                _normalise_stage_report(
                    stage_name,
                    operation(
                        config,
                        staging_dir=owned.path,
                        build_id=build_id,
                        stage_reports=tuple(reports),
                        source_fingerprint=source_fingerprint,
                    ),
                )
            )
        identity_value = reports[-2]["evidence"].get("identity")
        identity = _public_identity(identity_value)
        if identity["build_id"] != build_id:
            raise ReleaseError("frozen candidate build_id mismatch")
        _cleanup_owned_staging(owned)
        owned = None
        return ReleaseResult(
            "awaiting_device_acceptance",
            build_id,
            candidate,
            None,
            identity,
            tuple(reports),
        )
    except KeyboardInterrupt as error:
        if owned is not None:
            try:
                _cleanup_owned_staging(owned)
            except BaseException as cleanup_error:
                error.add_note(f"owned staging cleanup failed: {type(cleanup_error).__name__}")
        _write_failure_receipt(config, command="build-candidate", error=error, stage=stage_name)
        raise
    except BaseException as error:
        if owned is not None:
            try:
                _cleanup_owned_staging(owned)
            except BaseException as cleanup_error:
                error.add_note(f"owned staging cleanup failed: {type(cleanup_error).__name__}")
        public = error if isinstance(error, ReleaseError) else _safe_exception(stage_name, error)
        _write_failure_receipt(config, command="build-candidate", error=public, stage=stage_name)
        raise public from (None if public is error else error)


def build_candidate(
    config: OfflineReleaseConfig,
    *,
    services: Any | None = None,
) -> ReleaseResult:
    version_root = _require_safe_release_config(config)
    lease = _acquire_directory_lease(version_root)
    try:
        return _build_candidate_bound(config, services=services)
    finally:
        _release_directory_lease(lease)


def preflight_release(config: OfflineReleaseConfig, *, services: Any | None = None) -> Mapping[str, Any]:
    version_root = _require_safe_release_config(config)
    lease = _acquire_directory_lease(version_root)
    try:
        service = services or RealReleaseServices(config)
        source = service.fingerprint_sources(config)
        report = _normalise_stage_report(
            "preflight", service.preflight(config, source_fingerprint=source)
        )
        _validate_preflight(report)
        return report
    finally:
        _release_directory_lease(lease)


def finalize_release(
    config: OfflineReleaseConfig,
    *,
    candidate_id: str,
    receipt: Path,
    services: Any | None = None,
) -> ReleaseResult:
    version_root = _require_safe_release_config(config)
    lease = _acquire_directory_lease(version_root)
    try:
        service = services or RealReleaseServices(config)
        identity = service.load_candidate_identity(candidate_id, independent=True)
        service.validate_acceptance_receipt(Path(receipt), identity)
        final = _final_path(config)
        service.finalize_candidate(
            _candidate_path(config, candidate_id), Path(receipt), final
        )
        verified = service.verify_final_bundle(final)
        return ReleaseResult("finalized", candidate_id, None, final, _public_identity(verified))
    finally:
        _release_directory_lease(lease)


def verify_release(
    config: OfflineReleaseConfig,
    *,
    bundle: Path | None = None,
    candidate_id: str | None = None,
    services: Any | None = None,
) -> ReleaseResult:
    version_root = _require_safe_release_config(config)
    lease = _acquire_directory_lease(version_root)
    try:
        service = services or RealReleaseServices(config)
        if (bundle is None) == (candidate_id is None):
            raise ReleaseError("verify requires exactly one candidate or bundle")
        if candidate_id is not None:
            identity = service.load_candidate_identity(candidate_id, independent=True)
            evidence = getattr(service, "_verification_evidence", None)
            reports = (
                {
                    "name": "candidate-verify",
                    "status": "ok",
                    "evidence": _json_value(evidence),
                },
            ) if isinstance(evidence, Mapping) else ()
            return ReleaseResult(
                "verified",
                candidate_id,
                _candidate_path(config, candidate_id),
                None,
                _public_identity(identity),
                reports,
            )
        assert bundle is not None
        identity = service.verify_final_bundle(Path(bundle), independent=True)
        public = _public_identity(identity)
        evidence = getattr(service, "_verification_evidence", None)
        reports = (
            {
                "name": "final-verify",
                "status": "ok",
                "evidence": _json_value(evidence),
            },
        ) if isinstance(evidence, Mapping) else ()
        return ReleaseResult(
            "verified", public["build_id"], None, Path(bundle), public, reports
        )
    finally:
        _release_directory_lease(lease)


class SubprocessAdbRunner:
    """Concrete argv-only Task13 runner; it never chooses a default device."""

    def __init__(self, adb: Path, *, timeout_seconds: int = 60, runner: Callable[..., Any] | None = None) -> None:
        import subprocess

        self.adb_path = Path(adb)
        self.timeout_seconds = timeout_seconds
        self._runner = runner or subprocess.run

    def adb(self, serial: str | None, *args: str) -> Any:
        if any(
            not isinstance(argument, str)
            or not argument
            or any(ord(character) < 0x20 for character in argument)
            for argument in args
        ):
            raise ReleaseError("ADB argv contains an invalid argument")
        if serial is None:
            if tuple(args) != ("devices", "-l"):
                raise ReleaseError("serial-less ADB is allowed only for devices -l")
            command = [str(self.adb_path), "devices", "-l"]
        else:
            if (
                not isinstance(serial, str)
                or not serial
                or serial.startswith("-")
                or any(ord(character) < 0x21 for character in serial)
            ):
                raise ReleaseError("ADB serial is invalid")
            command = [str(self.adb_path), "-s", serial, *args]
        return self._runner(
            command,
            shell=False,
            check=False,
            capture_output=True,
            text=False,
            timeout=self.timeout_seconds,
            env=_sanitized_child_environment(),
        )


class RealReleaseServices:
    """Production adapter.  Exact Task3--13 wiring is implemented below."""

    def __init__(self, config: OfflineReleaseConfig) -> None:
        _require_safe_release_config(config)
        self.config = config
        self._toolchain_value = config.toolchain
        self._signing_value = config.signing
        self._roots: Any | None = None
        self._scan: Any | None = None
        self._fingerprint_roots: Any | None = None
        self._fingerprint_scan: Any | None = None
        self._legacy: Any | None = None
        self._diff: Any | None = None
        self._tail: Any | None = None
        self._snapshot: Any | None = None
        self._staged_roots: Any | None = None
        self._entries: tuple[Any, ...] = ()
        self._player_report: Any | None = None
        self._content_data_report: Any | None = None
        self._content_client_report: Any | None = None
        self._apk_report: Any | None = None
        self._apk_path: Path | None = None
        self._apk_report_path: Path | None = None
        self._zip_build_report: Any | None = None
        self._zip_verify_report: Any | None = None
        self._zip_path: Path | None = None
        self._guide: bytes | None = None
        self._identity: Any | None = None
        self._candidate_dir: Path | None = None
        self._verification_evidence: dict[str, Any] | None = None

    @staticmethod
    def _modules() -> tuple[Any, Any, Any, Any, Any, Any, Any]:
        import wf_offline_bundle as bundle_module
        import wf_offline_content as content_module
        import wf_offline_device as device_module
        import wf_offline_player as player_module
        import wf_offline_store as store_module
        import wf_offline_toolchain as toolchain_module
        import wf_offline_zip as zip_module

        return (
            store_module,
            player_module,
            content_module,
            zip_module,
            bundle_module,
            device_module,
            toolchain_module,
        )

    @staticmethod
    def _apk_builder() -> Any:
        name = "wf_offline_release_task11_builder"
        existing = sys.modules.get(name)
        if existing is not None:
            return existing
        path = REPO_ROOT / "client-patch" / "offline-android" / "build_offline_apk.py"
        specification = importlib.util.spec_from_file_location(name, path)
        if specification is None or specification.loader is None:
            raise ReleaseError("tracked offline APK builder cannot be loaded")
        loaded = importlib.util.module_from_spec(specification)
        sys.modules[name] = loaded
        try:
            specification.loader.exec_module(loaded)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        return loaded

    @staticmethod
    def _stage(name: str, **evidence: Any) -> dict[str, Any]:
        return {"name": name, "status": "ok", "evidence": evidence}

    @staticmethod
    def _stable_file_hash(path: Path) -> tuple[int, str]:
        target = Path(path)
        before = target.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise ReleaseError("release source is not a plain regular file")
        digest = hashlib.sha256()
        size = 0
        with target.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ReleaseError("release source identity drift before hashing")
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                digest.update(block)
            after = os.fstat(stream.fileno())
        if (
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            or size != before.st_size
        ):
            raise ReleaseError("release source drift while hashing")
        return size, digest.hexdigest()

    @staticmethod
    def _verification_runner(command: Sequence[Any], **kwargs: Any) -> Any:
        inherited = kwargs.pop("env", os.environ)
        forbidden = PASSWORD_ENV.casefold()
        kwargs["env"] = {
            str(key): str(value)
            for key, value in dict(inherited).items()
            if str(key).casefold() != forbidden
        }
        kwargs.setdefault("shell", False)
        return subprocess.run(command, **kwargs)

    def _verification_signing(self, claimed_certificate: str) -> Any:
        *_head, toolchain_module = self._modules()
        configured = self._signing_value
        if configured is not None:
            trusted = str(
                getattr(configured, "expected_certificate_sha256", "")
            ).casefold()
            keystore = Path(
                getattr(
                    configured,
                    "keystore",
                    DEFAULT_RELEASE_HOME / "wf-offline-release.jks",
                )
            )
        else:
            public_path = DEFAULT_RELEASE_HOME / "signer-public.json"
            try:
                _alias, trusted = toolchain_module._load_public_signer(public_path)
            except BaseException as exc:
                raise ReleaseError("trusted public signer identity is unavailable") from exc
            keystore = DEFAULT_RELEASE_HOME / "wf-offline-release.jks"
        if (
            re.fullmatch(r"[0-9a-f]{64}", trusted) is None
            or not isinstance(claimed_certificate, str)
            or not hmac.compare_digest(trusted, claimed_certificate.casefold())
        ):
            raise ReleaseError("release signer does not match the trusted public identity")
        # Verification never opens the keystore and never needs its password;
        # SigningConfig is used only to carry the pinned public fingerprint and
        # the redaction environment name through the Task11 verifier.
        return toolchain_module.SigningConfig(
            keystore=keystore,
            expected_certificate_sha256=trusted,
        )

    @staticmethod
    def _copy_locked_artifact(
        source: Path,
        destination: Path,
        expected_sha256: str,
    ) -> _LockedRegular | None:
        locked: _LockedRegular | None = None
        digest = hashlib.sha256()
        try:
            if os.name == "nt":
                locked = _open_locked_regular(source)
                reader = os.fdopen(os.dup(locked.descriptor), "rb")
            else:
                reader = Path(source).open("rb")
            with reader, Path(destination).open("xb") as writer:
                for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                    digest.update(chunk)
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
            if not hmac.compare_digest(digest.hexdigest(), expected_sha256):
                raise ReleaseError("release artifact hash changed before independent verification")
            if locked is not None:
                rebound = _windows_regular_path_info(Path(source))
                if rebound != locked.info:
                    raise ReleaseError("release artifact identity changed before verification")
            return locked
        except BaseException:
            if locked is not None:
                _close_locked_regular(locked)
            try:
                Path(destination).unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _verified_client_stage_reports(
        builder: Any,
        lock: Mapping[str, Any],
        verifier_stages: Sequence[Mapping[str, Any]],
        before_swf_sha256: str,
        after_swf_sha256: str,
    ) -> list[dict[str, Any]]:
        if len(verifier_stages) != 4:
            raise ReleaseError("independent APK verifier did not return four patch gates")
        stages = [dict(stage) for stage in verifier_stages]
        abyss_lock = lock.get("abyss_stage")
        if not isinstance(abyss_lock, Mapping):
            raise ReleaseError("offline APK lock has no abyss stage")
        target_class = abyss_lock.get("target_class")
        if target_class != "pinball.common.data.character.BattleCharacterLogic":
            raise ReleaseError("offline APK lock abyss target class is invalid")
        if stages[0].get("target_class") != target_class:
            raise ReleaseError("independent APK verifier abyss target class is invalid")
        stages[0].update(
            {
                "stage": "abyss-mode-equipment",
                "target_class": target_class,
                "before_method_sha256": abyss_lock.get("before_method_sha256"),
                "match_count": 1,
            }
        )
        derived_outputs = [
            str(lock.get("post_abyss_swf_sha256", "")),
            hashlib.sha256(
                b"independent-seris\0" + builder.canonical_json_bytes(stages[1])
            ).hexdigest(),
            hashlib.sha256(
                b"independent-render\0" + builder.canonical_json_bytes(stages[2])
            ).hexdigest(),
            after_swf_sha256,
        ]
        if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in derived_outputs):
            raise ReleaseError("independent APK verifier stage hash is invalid")
        previous = before_swf_sha256
        for stage, output in zip(stages, derived_outputs, strict=True):
            if hmac.compare_digest(previous, output):
                raise ReleaseError("independent APK verifier returned a no-op stage")
            stage["input_sha256"] = previous
            stage["output_sha256"] = output
            previous = output
        return stages

    def _independently_verify_apk(
        self,
        apk_snapshot: Path,
        owned: _OwnedStaging,
        evidence: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        builder = self._apk_builder()
        toolchain = self._toolchain()
        apk_evidence = evidence["apk"]
        signing = self._verification_signing(str(apk_evidence["certificate_sha256"]))
        lock_path = REPO_ROOT / "client-patch" / "offline-android" / "base-lock.json"
        lock = builder.load_base_lock(lock_path)
        baseline = builder.inspect_apk(
            Path(self.config.source_apk),
            toolchain,
            runner=self._verification_runner,
        )
        builder.assert_locked_baseline(baseline, lock)
        transaction = owned.path / "apk-independent"
        transaction.mkdir(exist_ok=False)
        base_snapshot = transaction / "base.apk"
        source_identity = builder._copy_source_snapshot(
            Path(self.config.source_apk), base_snapshot, str(baseline.apk_sha256)
        )

        def bound_file_guard(path: Path):
            return _locked_regular_guard(path, bound_root=owned)

        with contextlib.ExitStack() as guards:
            guards.enter_context(bound_file_guard(base_snapshot))
            source_swf = builder._extract_exactly_one_swf(
                base_snapshot, transaction / "source.swf"
            )
            candidate_swf = builder._extract_exactly_one_swf(
                Path(apk_snapshot), transaction / "candidate.swf"
            )
            guards.enter_context(bound_file_guard(source_swf))
            guards.enter_context(bound_file_guard(candidate_swf))
            before_swf = builder._sha256_file(source_swf)
            after_swf = builder._sha256_file(candidate_swf)
            verifier_config = SimpleNamespace(toolchain=toolchain, signing=signing)
            signature, verifier_stages, output_sha256 = builder.verify_signed_apk(
                Path(apk_snapshot),
                verifier_config,
                baseline,
                lock,
                transaction,
                candidate_swf,
                runner=self._verification_runner,
                file_guard=bound_file_guard,
            )
        builder._assert_source_unchanged(
            Path(self.config.source_apk), source_identity, str(baseline.apk_sha256)
        )
        stages = self._verified_client_stage_reports(
            builder,
            lock,
            verifier_stages,
            before_swf,
            after_swf,
        )
        client_report = {
            "output_sha256": output_sha256,
            "certificate_sha256": str(signature["certificate_sha256"]),
            "patch_order": list(builder.PATCH_ORDER),
            "stage_reports": stages,
            "full_resource_version": builder.EXPECTED_FULL_RESOURCE_VERSION,
            "aligned": True,
            "signature_schemes": dict(signature["signature_schemes"]),
            "verified": True,
        }
        expected_apk = {
            "output_sha256": apk_evidence["output_sha256"],
            "certificate_sha256": apk_evidence["certificate_sha256"],
            "full_resource_version": apk_evidence["full_resource_version"],
            "aligned": apk_evidence["aligned"],
            "signature_schemes": dict(apk_evidence["signature_schemes"]),
            "verified": apk_evidence["verified"],
        }
        observed_apk = {
            key: client_report[key]
            for key in expected_apk
        }
        if observed_apk != expected_apk:
            raise ReleaseError("independent APK evidence does not match the artifact")
        patches = evidence["patches"]
        if (
            list(patches["order"]) != list(builder.PATCH_ORDER)
            or not hmac.compare_digest(str(patches["before_swf_sha256"]), before_swf)
            or not hmac.compare_digest(str(patches["after_swf_sha256"]), after_swf)
        ):
            raise ReleaseError("independent SWF patch evidence does not match the artifact")
        return client_report, {
            "aligned": True,
            "certificate_sha256": client_report["certificate_sha256"],
            "offline_baseline_verified": True,
            "output_sha256": output_sha256,
            "patch_gate_count": 4,
            "signature_schemes": dict(client_report["signature_schemes"]),
            "swf_after_sha256": after_swf,
            "swf_before_sha256": before_swf,
        }

    @staticmethod
    def _require_data_manifest_matches_source(
        store_module: Any,
        bundle_module: Any,
        scan: Any,
        evidence: Mapping[str, Any],
    ) -> tuple[Any, ...]:
        documents = evidence["data"]["entries"]
        candidate = {str(item["path"]): dict(item) for item in documents}
        source: dict[str, dict[str, Any]] = {}
        for member in scan.members:
            path = bundle_module.ROOT_PREFIXES[str(member.root)] + str(member.relative)
            source[path] = {
                "path": path,
                "size": int(member.size),
                "sha256": str(member.sha256),
                "source": str(member.root),
            }
        player = evidence["player"]
        overlay_paths = [
            path
            for path, item in source.items()
            if item["source"] == "common"
            and hmac.compare_digest(str(item["sha256"]), str(player["before_sha256"]))
        ]
        if len(overlay_paths) != 1:
            raise ReleaseError("independent player overlay source binding is ambiguous")
        overlay_path = overlay_paths[0]
        expected_paths = set(source)
        marker_entries = store_module.marker_entries(
            int(scan.total_bytes), snapshot_version=DEFAULT_SNAPSHOT_VERSION
        )
        marker_documents = {
            str(entry.path): {
                "path": str(entry.path),
                "size": int(entry.size),
                "sha256": str(entry.sha256),
                "source": "generated-marker",
            }
            for entry in marker_entries
        }
        expected_paths.update(marker_documents)
        if set(candidate) != expected_paths:
            raise ReleaseError("independent data manifest path set differs from the source store")
        for path, expected in source.items():
            observed = candidate[path]
            if path == overlay_path:
                if (
                    observed.get("source") != "common"
                    or not hmac.compare_digest(
                        str(observed.get("sha256", "")),
                        str(player["after_sha256"]),
                    )
                ):
                    raise ReleaseError("independent player overlay output binding mismatch")
                continue
            if observed != expected:
                raise ReleaseError("independent data manifest differs from the source store")
        for path, expected in marker_documents.items():
            if candidate[path] != expected:
                raise ReleaseError("independent generated marker evidence mismatch")
        return tuple(
            store_module.ManifestEntry(
                str(item["path"]),
                int(item["size"]),
                str(item["sha256"]),
                str(item["source"]),
            )
            for item in documents
        )

    @staticmethod
    def _content_lock_plan(
        evidence: Mapping[str, Any],
        content_module: Any,
        bundle_module: Any,
    ) -> tuple[frozenset[tuple[str, str]], frozenset[str]]:
        """Derive a bounded lock closure, then let the validator audit every access."""

        content = evidence.get("content")
        characters = content.get("characters") if isinstance(content, Mapping) else None
        if not isinstance(characters, list):
            raise ReleaseError("independent content evidence has no character closure")
        guarded: set[tuple[str, str]] = {
            ("common", str(content_module.PLAYER_CHARACTER_LOGICAL)),
            ("common", str(content_module.PLAYER_ITEM_LOGICAL)),
        }
        roots = frozenset(bundle_module.ROOT_PREFIXES)
        for character in characters:
            bound = character.get("bound_files") if isinstance(character, Mapping) else None
            if not isinstance(bound, list):
                raise ReleaseError("independent character evidence has no bound-file closure")
            for item in bound:
                if not isinstance(item, Mapping):
                    raise ReleaseError("independent character bound-file evidence is invalid")
                path = item.get("path")
                source = item.get("source")
                if not isinstance(path, str) or not path.startswith("roots/"):
                    continue
                parts = path.split("/", 2)
                if len(parts) != 3 or parts[1] not in roots or not parts[2]:
                    raise ReleaseError("independent character root binding is invalid")
                expected_source = f"snapshot:{parts[1]}"
                if source != expected_source:
                    raise ReleaseError("independent character root/source binding is invalid")
                guarded.add((parts[1], parts[2]))
        rogue_module = importlib.import_module("wf_rogue_validate")
        rogue_logicals = rogue_module.offline_release_logicals()
        if not isinstance(rogue_logicals, tuple) or not rogue_logicals:
            raise ReleaseError("independent rogue logical closure is invalid")
        guarded.update(("common", str(logical)) for logical in rogue_logicals)
        if len(guarded) > MAX_CONTENT_GUARDS:
            raise ReleaseError("independent content lock closure exceeds the safety limit")
        members: set[str] = set()
        for root_name, logical in guarded:
            if root_name not in roots:
                raise ReleaseError("independent content lock root is invalid")
            try:
                logical = content_module._require_logical(logical)
                relative = str(content_module.hashed_rel(logical)).replace("\\", "/")
            except BaseException as exc:
                raise ReleaseError("independent content lock logical is invalid") from exc
            members.add(bundle_module.ROOT_PREFIXES[root_name] + relative)
        if not members or len(members) > MAX_CONTENT_GUARDS:
            raise ReleaseError("independent content member lock closure is invalid")
        return frozenset(guarded), frozenset(members)

    @staticmethod
    def _data_root_inventory(
        entries: Sequence[Any],
        bundle_module: Any,
    ) -> dict[str, frozenset[str]]:
        inventory: dict[str, set[str]] = {
            str(root_name): set() for root_name in bundle_module.ROOT_PREFIXES
        }
        markers = {
            "WorldFlipper/dummy/info.json",
            "WorldFlipper/dummy/download/.empty",
        }
        for entry in entries:
            name = str(entry.path)
            if name in markers:
                continue
            matches = [
                (str(root_name), str(prefix))
                for root_name, prefix in bundle_module.ROOT_PREFIXES.items()
                if name.startswith(str(prefix))
            ]
            if len(matches) != 1:
                raise ReleaseError("independent data manifest root inventory is invalid")
            root_name, prefix = matches[0]
            relative = name[len(prefix) :]
            if not relative or relative in inventory[root_name]:
                raise ReleaseError("independent data manifest root inventory is ambiguous")
            inventory[root_name].add(relative)
        return {
            root_name: frozenset(relative_paths)
            for root_name, relative_paths in inventory.items()
        }

    @staticmethod
    def _extract_verified_data_zip(
        zip_path: Path,
        locked_zip: _LockedRegular | None,
        extraction_root: Path,
        entries: Sequence[Any],
        bundle_module: Any,
        *,
        guard_paths: Collection[str],
        bound_root: _OwnedStaging | None = None,
    ) -> tuple[Any, tuple[_DirectoryLease, ...], tuple[int, ...]]:
        roots = {
            "common": extraction_root / "WorldFlipper" / "dummy" / "download" / "production" / "upload",
            "medium": extraction_root / "WorldFlipper" / "dummy" / "download" / "production" / "medium_upload",
            "android": extraction_root / "WorldFlipper" / "dummy" / "download" / "production" / "android_upload",
        }
        leases: dict[str, _DirectoryLease] = {}
        file_handles: list[int] = []
        raw_stream: Any | None = None
        required_guards = frozenset(str(path) for path in guard_paths)
        if len(required_guards) > MAX_CONTENT_GUARDS:
            raise ReleaseError("independent extraction guard set exceeds the safety limit")
        if not required_guards.issubset({str(entry.path) for entry in entries}):
            raise ReleaseError("independent content lock closure is absent from the data manifest")
        guarded_seen: set[str] = set()

        def bind_parent(path: Path) -> _DirectoryLease:
            key = os.path.normcase(os.path.abspath(path))
            if key not in leases:
                leases[key] = _acquire_directory_lease(
                    path,
                    bound_root=bound_root,
                )
            return leases[key]

        try:
            for root in roots.values():
                bind_parent(root)
            if locked_zip is not None:
                duplicated_zip_descriptor = os.dup(locked_zip.descriptor)
                try:
                    raw_stream = os.fdopen(duplicated_zip_descriptor, "rb")
                except BaseException:
                    _run_release_cleanup(
                        (("data-zip-descriptor", lambda: os.close(duplicated_zip_descriptor)),)
                    )
                    raise
                archive_input: Any = raw_stream
            else:
                archive_input = zip_path
            try:
                with zipfile.ZipFile(archive_input, "r") as archive:
                    for entry in entries:
                        name = str(entry.path)
                        if name not in required_guards:
                            continue
                        root_name: str | None = None
                        relative: str | None = None
                        for candidate_root, prefix in bundle_module.ROOT_PREFIXES.items():
                            if name.startswith(prefix):
                                root_name = candidate_root
                                relative = name[len(prefix) :]
                                break
                        if root_name is not None and relative is not None:
                            destination = roots[root_name] / Path(relative)
                        elif name == "WorldFlipper/dummy/info.json":
                            destination = extraction_root / "WorldFlipper" / "dummy" / "info.json"
                        elif name == "WorldFlipper/dummy/download/.empty":
                            destination = extraction_root / "WorldFlipper" / "dummy" / "download" / ".empty"
                        else:
                            raise ReleaseError("independent ZIP contains an unrecognized member")
                        parent_lease = bind_parent(destination.parent)
                        digest = hashlib.sha256()
                        size = 0
                        raw_guard = 0
                        if os.name == "nt" and name in required_guards:
                            if not parent_lease.chain:
                                raise ReleaseError("independent extraction parent is not handle-bound")
                            raw_guard = _nt_create_windows_regular(
                                parent_lease.chain[-1][1],
                                destination.name,
                                request_delete=False,
                            )
                            file_handles.append(raw_guard)
                            guarded_seen.add(name)
                            writer_handle = _duplicate_windows_handle(raw_guard)
                            import msvcrt

                            try:
                                descriptor = msvcrt.open_osfhandle(
                                    writer_handle,
                                    os.O_WRONLY | getattr(os, "O_BINARY", 0),
                                )
                            except BaseException:
                                _close_windows_handle(writer_handle)
                                raise
                        else:
                            descriptor = os.open(
                                destination,
                                os.O_WRONLY
                                | os.O_CREAT
                                | os.O_EXCL
                                | getattr(os, "O_BINARY", 0),
                                0o600,
                            )
                        try:
                            with archive.open(name, "r") as source:
                                while True:
                                    chunk = source.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    digest.update(chunk)
                                    size += len(chunk)
                                    view = memoryview(chunk)
                                    while view:
                                        written = os.write(descriptor, view)
                                        if written <= 0:
                                            raise OSError("short extraction write")
                                        view = view[written:]
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                        if raw_guard:
                            if _windows_regular_handle_info(raw_guard).size != size:
                                raise ReleaseError("independent ZIP extraction size drift")
                        if (
                            size != int(entry.size)
                            or not hmac.compare_digest(digest.hexdigest(), str(entry.sha256))
                        ):
                            raise ReleaseError("independent ZIP extraction hash mismatch")
            finally:
                if raw_stream is not None:
                    _run_release_cleanup((("data-zip-stream", raw_stream.close),))
            store_module, *_unused = RealReleaseServices._modules()
            if guarded_seen != set(required_guards):
                raise ReleaseError("independent content lock closure was not fully extracted")
            return (
                store_module.StoreRoots(
                    common=roots["common"],
                    medium=roots["medium"],
                    android=roots["android"],
                ),
                tuple(leases.values()),
                tuple(file_handles),
            )
        except BaseException:
            cleanup_steps: list[tuple[str, Callable[[], None]]] = []
            cleanup_steps.extend(
                (
                    f"content-file-{index}",
                    lambda raw_handle=raw_handle: _close_windows_handle(raw_handle),
                )
                for index, raw_handle in enumerate(reversed(file_handles), start=1)
            )
            cleanup_steps.extend(
                (
                    f"content-directory-{index}",
                    lambda lease=lease: _release_directory_lease(lease),
                )
                for index, lease in enumerate(
                    reversed(tuple(leases.values())),
                    start=1,
                )
            )
            _run_release_cleanup(cleanup_steps)
            raise

    def _independently_verify_release_artifacts(
        self,
        artifact_dir: Path,
        identity: Any,
        evidence: Mapping[str, Any],
        *,
        expected_files: Sequence[str],
        final_bundle: bool,
    ) -> dict[str, Any]:
        (
            store_module,
            _player_module,
            content_module,
            zip_module,
            bundle_module,
            _device_module,
            _toolchain_module,
        ) = self._modules()
        target = Path(artifact_dir)
        target_lease = _acquire_directory_lease(target, create=False)
        locked_files: dict[str, _LockedRegular] = {}
        owned: _OwnedStaging | None = None
        apk_lock: _LockedRegular | None = None
        apk_snapshot_lock: _LockedRegular | None = None
        zip_lock: _LockedRegular | None = None
        extraction_leases: tuple[_DirectoryLease, ...] = ()
        extraction_file_handles: tuple[int, ...] = ()
        try:
            locked_files = _open_locked_release_files(target, expected_files)
            owned = _create_owned_staging(
                Path(self.config.output_root) / self.config.snapshot_version
            )
            apk_snapshot = owned.path / "independent.apk"
            apk_lock = self._copy_locked_artifact(
                target / bundle_module.APK_NAME,
                apk_snapshot,
                identity.apk_sha256,
            )
            apk_snapshot_lock = _open_locked_regular(
                apk_snapshot,
                bound_root=owned,
            )
            if os.name == "nt":
                zip_lock = _open_locked_regular(target / bundle_module.DATA_ZIP_NAME)
                if not hmac.compare_digest(
                    self._stable_file_hash(target / bundle_module.DATA_ZIP_NAME)[1],
                    identity.data_zip_sha256,
                ):
                    raise ReleaseError("data ZIP changed before independent verification")
            client_report, apk_result = self._independently_verify_apk(
                apk_snapshot,
                owned,
                evidence,
            )
            source_size, source_hash = self._stable_file_hash(Path(self.config.source_apk))
            roots = store_module.resolve_store_roots(self.config.profile_id)
            current_scan = store_module.enumerate_hashed_members(roots)
            current_checkpoint = _source_checkpoint(
                {
                    "source_apk_sha256": source_hash,
                    "store_tree_sha256": current_scan.tree_sha256,
                    "source_apk_size": source_size,
                    "store_total_bytes": current_scan.total_bytes,
                    "store_counts": dict(current_scan.counts),
                },
                label="independent source",
            )
            fingerprints = evidence["source_fingerprint"]
            for name in ("before", "scan", "after"):
                _require_same_sources(current_checkpoint, fingerprints[name])
            if fingerprints.get("unchanged") is not True:
                raise ReleaseError("independent source fingerprint is not unchanged")
            legacy = store_module.inspect_legacy_zip_paths(Path(self.config.legacy_zip))
            diff = store_module.compare_path_sets(
                tuple(member.key for member in current_scan.members), legacy.members
            )
            current = {member.key: member for member in current_scan.members}
            tail = store_module.verify_tail_edge(
                Path(self.config.tail_zip),
                current=current,
                expected_from="1.4.195",
                expected_to=self.config.snapshot_version,
            )
            if (
                diff.legacy_count != EXPECTED_LEGACY_COUNT
                or diff.current_count != EXPECTED_CURRENT_COUNT
                or len(diff.added) != EXPECTED_ADDED_COUNT
                or diff.missing
                or tail.member_count != EXPECTED_TAIL_COUNT
            ):
                raise ReleaseError("independent legacy/tail source gates failed")
            entries = self._require_data_manifest_matches_source(
                store_module,
                bundle_module,
                current_scan,
                evidence,
            )
            guarded_logicals, guarded_members = self._content_lock_plan(
                evidence,
                content_module,
                bundle_module,
            )
            root_inventory = self._data_root_inventory(entries, bundle_module)
            zip_report = zip_module.verify_data_zip(
                target / bundle_module.DATA_ZIP_NAME,
                entries,
                expected_members=len(entries),
                production=True,
            )
            if (
                not hmac.compare_digest(
                    str(zip_report.archive_sha256),
                    str(evidence["data"]["archive_sha256"]),
                )
                or zip_report.member_count != evidence["data"]["member_count"]
                or zip_report.total_uncompressed_bytes
                != evidence["data"]["total_uncompressed_bytes"]
                or zip_report.zip64 is not evidence["data"]["zip64"]
            ):
                raise ReleaseError("independent data ZIP report mismatch")
            (
                staged_roots,
                extraction_leases,
                extraction_file_handles,
            ) = self._extract_verified_data_zip(
                target / bundle_module.DATA_ZIP_NAME,
                zip_lock,
                owned.path / "extracted",
                entries,
                bundle_module,
                guard_paths=guarded_members,
                bound_root=owned,
            )
            client_report_path = owned.path / "independent-client-report.json"
            _write_exclusive(
                client_report_path,
                self._apk_builder().canonical_json_bytes(client_report),
            )
            with _locked_regular_guard(client_report_path, bound_root=owned):
                def require_guarded_logical(root_name: str, logical: str) -> None:
                    if (root_name, logical) not in guarded_logicals:
                        raise ReleaseError(
                            "independent content validator accessed an unlocked logical"
                        )

                content_report = content_module.validate_offline_content(
                    staged_roots,
                    workspace_sources=None,
                    phase4_asset_logicals=content_module.SERIS_PHASE4_ASSET_LOGICALS,
                    assets_dir=REPO_ROOT / "assets",
                    client_report=client_report_path,
                    snapshot_access_guard=require_guarded_logical,
                    snapshot_root_inventory=root_inventory,
                )
            if (
                content_report.ready is not True
                or content_report.client_gate_ready is not True
                or self._content_document(content_report) != evidence["content"]
            ):
                raise ReleaseError("independent content gates do not match release evidence")
            result = {
                "apk": apk_result,
                "content": {
                    "character_count": len(content_report.characters),
                    "client_gate_ready": True,
                    "ready": True,
                    "rogue_ready": content_report.rogue.ready,
                },
                "data": {
                    "archive_sha256": zip_report.archive_sha256,
                    "member_count": zip_report.member_count,
                    "total_uncompressed_bytes": zip_report.total_uncompressed_bytes,
                    "zip64": zip_report.zip64,
                },
                "legacy_tail": {
                    "added_count": len(diff.added),
                    "current_count": diff.current_count,
                    "legacy_count": diff.legacy_count,
                    "missing_count": len(diff.missing),
                    "tail_member_count": tail.member_count,
                },
                "source_fingerprint": {
                    "after": current_checkpoint,
                    "before": current_checkpoint,
                    "scan": current_checkpoint,
                    "unchanged": True,
                },
            }
            _require_locked_release_files(target, locked_files, expected_files)
            if final_bundle:
                rebound_identity = bundle_module.verify_final_bundle(target)
            else:
                rebound_identity, rebound_evidence = bundle_module.verify_candidate(target)
                if rebound_evidence != evidence:
                    raise ReleaseError("candidate evidence changed during independent verification")
            if _public_identity(rebound_identity) != _public_identity(identity):
                raise ReleaseError("release identity changed during independent verification")
            result.update(_validate_release_secret_scan(bundle_module, target))
            _require_locked_release_files(target, locked_files, expected_files)
            return result
        finally:
            cleanup_steps: list[tuple[str, Callable[[], None]]] = []
            cleanup_steps.extend(
                (
                    f"content-file-{index}",
                    lambda raw_handle=raw_handle: _close_windows_handle(raw_handle),
                )
                for index, raw_handle in enumerate(
                    reversed(extraction_file_handles),
                    start=1,
                )
            )
            cleanup_steps.extend(
                (
                    f"content-directory-{index}",
                    lambda lease=lease: _release_directory_lease(lease),
                )
                for index, lease in enumerate(reversed(extraction_leases), start=1)
            )
            if zip_lock is not None:
                cleanup_steps.append(
                    ("data-zip-lock", lambda: _close_locked_regular(zip_lock))
                )
            if apk_snapshot_lock is not None:
                cleanup_steps.append(
                    (
                        "apk-snapshot-lock",
                        lambda: _close_locked_regular(apk_snapshot_lock),
                    )
                )
            if apk_lock is not None:
                cleanup_steps.append(
                    ("source-apk-lock", lambda: _close_locked_regular(apk_lock))
                )
            if owned is not None:
                cleanup_steps.append(
                    ("owned-verification-staging", lambda: _cleanup_owned_staging(owned))
                )
            cleanup_steps.append(
                ("release-file-set", lambda: _close_locked_release_files(locked_files))
            )
            cleanup_steps.append(
                ("release-directory", lambda: _release_directory_lease(target_lease))
            )
            _run_release_cleanup(cleanup_steps)

    def _toolchain(self) -> Any:
        if self._toolchain_value is None:
            *_unused, toolchain_module = self._modules()
            self._toolchain_value = toolchain_module.discover_toolchain()
        return self._toolchain_value

    def _signing(self) -> Any:
        if self._signing_value is None:
            *_unused, toolchain_module = self._modules()
            self._signing_value = toolchain_module.load_signing_config(
                DEFAULT_RELEASE_HOME, env=os.environ
            )
        return self._signing_value

    def fingerprint_sources(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        store_module, *_rest = self._modules()
        source_size, source_hash = self._stable_file_hash(Path(self.config.source_apk))
        roots = store_module.resolve_store_roots(self.config.profile_id)
        scan = store_module.enumerate_hashed_members(roots)
        if self._fingerprint_scan is None:
            self._fingerprint_roots = roots
            self._fingerprint_scan = scan
        return {
            "source_apk_sha256": source_hash,
            "store_tree_sha256": scan.tree_sha256,
            "source_apk_size": source_size,
            "store_total_bytes": scan.total_bytes,
            "store_counts": dict(scan.counts),
        }

    def preflight(
        self,
        _config: OfflineReleaseConfig,
        *,
        source_fingerprint: Mapping[str, Any],
        **_kwargs: Any,
    ) -> Mapping[str, Any]:
        store_module, _player, _content, _zip, _bundle, _device, toolchain_module = self._modules()
        version_root = _require_safe_release_config(self.config)
        try:
            version_metadata = version_root.lstat()
        except OSError as exc:
            raise ReleaseError("release output lease is missing") from exc
        if _is_reparse(version_metadata) or not stat.S_ISDIR(version_metadata.st_mode):
            raise ReleaseError("release output lease is not a plain directory")
        if _lexists(_final_path(self.config)):
            raise ReleaseError("final already exists")
        builder = self._apk_builder()
        lock = builder.load_base_lock(
            REPO_ROOT / "client-patch" / "offline-android" / "base-lock.json"
        )
        expected_hash = str(lock.source_apk_sha256)
        toolchain = self._toolchain()
        signing = self._signing()
        signer_report = toolchain_module.verify_signing_config(
            signing,
            java=toolchain.java,
            env=os.environ,
        )
        _require_verified_signer_report(signer_report, signing)
        scan = self._fingerprint_scan
        if scan is None or self._fingerprint_roots is None:
            raise ReleaseError("preflight source scan is unavailable")
        if (
            dict(scan.counts) != EXPECTED_STORE_COUNTS
            or scan.tree_sha256 != source_fingerprint.get("store_tree_sha256")
            or scan.total_bytes != source_fingerprint.get("store_total_bytes")
        ):
            raise ReleaseError("preflight source scan does not match its fingerprint")
        legacy = store_module.inspect_legacy_zip_paths(Path(self.config.legacy_zip))
        current_keys = tuple(member.key for member in scan.members)
        diff = store_module.compare_path_sets(current_keys, legacy.members)
        current = {member.key: member for member in scan.members}
        tail = store_module.verify_tail_edge(
            Path(self.config.tail_zip),
            current=current,
            expected_from="1.4.195",
            expected_to=self.config.snapshot_version,
        )
        if (
            diff.legacy_count != EXPECTED_LEGACY_COUNT
            or diff.current_count != EXPECTED_CURRENT_COUNT
            or len(diff.added) != EXPECTED_ADDED_COUNT
            or diff.missing
            or tail.member_count != EXPECTED_TAIL_COUNT
        ):
            raise ReleaseError("preflight legacy/tail snapshot gates failed")
        required = store_module.required_free_bytes(
            int(source_fingerprint["store_total_bytes"]),
            int(source_fingerprint["source_apk_size"]),
        )
        free = int(shutil.disk_usage(version_root).free)
        build_id = uuid.uuid4().hex
        if _lexists(_candidate_path(self.config, build_id)):
            raise ReleaseError("candidate already exists")
        return self._stage(
            "preflight",
            build_id=build_id,
            signer_ready=True,
            fingerprint_verified=True,
            certificate_sha256=str(signer_report["certificate_sha256"]).casefold(),
            disk_free_bytes=free,
            disk_required_bytes=required,
            source_apk_sha256=source_fingerprint["source_apk_sha256"],
            expected_source_apk_sha256=expected_hash,
            store_counts=source_fingerprint["store_counts"],
            legacy_count=diff.legacy_count,
            current_count=diff.current_count,
            added_count=len(diff.added),
            missing_count=len(diff.missing),
            tail_member_count=tail.member_count,
        )

    def scan_store(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        store_module, *_rest = self._modules()
        self._roots = store_module.resolve_store_roots(self.config.profile_id)
        self._scan = store_module.enumerate_hashed_members(self._roots)
        expected = EXPECTED_STORE_COUNTS
        if dict(self._scan.counts) != expected or len(self._scan.members) != sum(expected.values()):
            raise ReleaseError("store root count mismatch")
        return self._stage(
            "scan-store",
            counts=dict(self._scan.counts),
            total_count=len(self._scan.members),
            total_bytes=self._scan.total_bytes,
            tree_sha256=self._scan.tree_sha256,
        )

    def legacy_tail_gates(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        store_module, *_rest = self._modules()
        if self._scan is None:
            raise ReleaseError("scan-store must run before legacy-tail-gates")
        self._legacy = store_module.inspect_legacy_zip_paths(Path(self.config.legacy_zip))
        current_keys = tuple(member.key for member in self._scan.members)
        self._diff = store_module.compare_path_sets(current_keys, self._legacy.members)
        current = {member.key: member for member in self._scan.members}
        self._tail = store_module.verify_tail_edge(
            Path(self.config.tail_zip),
            current=current,
            expected_from="1.4.195",
            expected_to=self.config.snapshot_version,
        )
        if (
            self._diff.legacy_count != EXPECTED_LEGACY_COUNT
            or self._diff.current_count != EXPECTED_CURRENT_COUNT
            or len(self._diff.added) != EXPECTED_ADDED_COUNT
            or self._diff.missing
            or self._tail.member_count != EXPECTED_TAIL_COUNT
        ):
            raise ReleaseError("legacy/tail snapshot gates failed")
        return self._stage(
            "legacy-tail-gates",
            legacy_count=self._diff.legacy_count,
            current_count=self._diff.current_count,
            added_count=len(self._diff.added),
            missing_count=len(self._diff.missing),
            tail_member_count=self._tail.member_count,
        )

    def copy_snapshot(self, _config: OfflineReleaseConfig, *, staging_dir: Path, **_kwargs: Any) -> Mapping[str, Any]:
        store_module, *_rest = self._modules()
        if self._scan is None:
            raise ReleaseError("scan-store must run before copy-snapshot")
        worldflipper = Path(staging_dir) / "WorldFlipper"
        self._snapshot = store_module.materialize_snapshot(
            self._scan, worldflipper, snapshot_version=self.config.snapshot_version
        )
        production = worldflipper / "dummy" / "download" / "production"
        self._staged_roots = store_module.StoreRoots(
            production / "upload",
            production / "medium_upload",
            production / "android_upload",
        )
        self._entries = tuple(
            (*self._snapshot.copied_entries, *self._snapshot.generated_entries)
        )
        return self._stage(
            "copy-snapshot",
            copied_count=len(self._snapshot.copied_entries),
            generated_count=len(self._snapshot.generated_entries),
        )

    def player_overlay(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        store_module, player_module, *_rest = self._modules()
        if self._staged_roots is None:
            raise ReleaseError("copy-snapshot must run before player-overlay")
        self._player_report = player_module.apply_initial_player_overlay(
            self._staged_roots.common
        )
        expected_path = (
            "WorldFlipper/dummy/download/production/upload/"
            + self._player_report.relative_path.replace("\\", "/")
        )
        matches = [
            index
            for index, entry in enumerate(self._entries)
            if entry.path == expected_path and entry.source == "store:common"
        ]
        if len(matches) != 1:
            raise ReleaseError("player overlay did not bind exactly one common manifest entry")
        player_file = self._staged_roots.common / self._player_report.relative_path
        size, digest = self._stable_file_hash(player_file)
        if digest != self._player_report.after_sha256:
            raise ReleaseError("player overlay report hash mismatch")
        index = matches[0]
        previous = self._entries[index]
        rebound = store_module.ManifestEntry(
            previous.path, size, digest, previous.source
        )
        updated = list(self._entries)
        updated[index] = rebound
        self._entries = tuple(updated)
        return self._stage(
            "player-overlay",
            player_id="1000",
            before_sha256=self._player_report.before_sha256,
            after_sha256=self._player_report.after_sha256,
            added_character_ids=list(self._player_report.added_character_ids),
            character_level=self._player_report.character_level,
        )

    def _validate_content(self, client_report: Path | None) -> Any:
        _store, _player, content_module, *_rest = self._modules()
        if self._staged_roots is None:
            raise ReleaseError("copy-snapshot must run before content gates")
        return content_module.validate_offline_content(
            self._staged_roots,
            workspace_sources=None,
            phase4_asset_logicals=content_module.SERIS_PHASE4_ASSET_LOGICALS,
            assets_dir=REPO_ROOT / "assets",
            client_report=client_report,
        )

    def content_data_gates(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        self._content_data_report = self._validate_content(None)
        if self._content_data_report.ready is not True or self._content_data_report.client_gate_ready is not None:
            raise ReleaseError("offline content data gates failed")
        return self._stage(
            "content-data-gates",
            ready=True,
            character_count=len(self._content_data_report.characters),
            rogue_ready=self._content_data_report.rogue.ready,
        )

    def build_apk(self, _config: OfflineReleaseConfig, *, staging_dir: Path, **_kwargs: Any) -> Mapping[str, Any]:
        builder = self._apk_builder()
        artifacts = Path(staging_dir) / "artifacts"
        artifacts.mkdir(exist_ok=False)
        self._apk_path = artifacts / "offline.apk"
        self._apk_report_path = artifacts / "offline-apk-report.json"
        work_dir = Path(staging_dir) / "apk-work"
        if not str(work_dir).isascii():
            raise ReleaseError("APK work directory must be ASCII-only")
        build_config = builder.OfflineApkBuildConfig(
            source_apk=Path(self.config.source_apk),
            baseline_lock=REPO_ROOT / "client-patch" / "offline-android" / "base-lock.json",
            output_apk=self._apk_path,
            report_path=self._apk_report_path,
            work_dir=work_dir,
            toolchain=self._toolchain(),
            signing=self._signing(),
        )
        self._apk_report = builder.build_offline_apk(build_config)
        return self._stage(
            "build-apk",
            output_sha256=self._apk_report.output_sha256,
            certificate_sha256=self._apk_report.certificate_sha256,
            patch_order=list(self._apk_report.patch_order),
            verified=self._apk_report.verified,
        )

    def content_client_gate(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        if self._apk_report_path is None:
            raise ReleaseError("build-apk must run before content-client-gate")
        self._content_client_report = self._validate_content(self._apk_report_path)
        if (
            self._content_client_report.ready is not True
            or self._content_client_report.client_gate_ready is not True
        ):
            raise ReleaseError("offline content client gate failed")
        return self._stage(
            "content-client-gate",
            ready=True,
            client_gate_ready=True,
        )

    def build_zip(self, _config: OfflineReleaseConfig, *, staging_dir: Path, **_kwargs: Any) -> Mapping[str, Any]:
        _store, _player, _content, zip_module, *_rest = self._modules()
        if self._snapshot is None or not self._entries:
            raise ReleaseError("copy-snapshot must run before build-zip")
        self._zip_path = Path(staging_dir) / "artifacts" / "data.zip"
        self._zip_build_report = zip_module.write_data_zip(
            self._snapshot.worldflipper_root,
            self._zip_path,
            self._entries,
            production=True,
        )
        return self._stage(
            "build-zip",
            archive_sha256=self._zip_build_report.archive_sha256,
            member_count=self._zip_build_report.member_count,
            zip64=self._zip_build_report.zip64,
        )

    def verify_zip(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        _store, _player, _content, zip_module, *_rest = self._modules()
        if self._zip_path is None:
            raise ReleaseError("build-zip must run before verify-zip")
        self._zip_verify_report = zip_module.verify_data_zip(
            self._zip_path,
            self._entries,
            expected_members=len(self._entries),
            production=True,
        )
        if self._zip_verify_report.archive_sha256 != self._zip_build_report.archive_sha256:
            raise ReleaseError("data ZIP hash changed during verification")
        return self._stage(
            "verify-zip",
            archive_sha256=self._zip_verify_report.archive_sha256,
            member_count=self._zip_verify_report.member_count,
            total_uncompressed_bytes=self._zip_verify_report.total_uncompressed_bytes,
            zip64=self._zip_verify_report.zip64,
        )

    def render_guide(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        *_head, bundle_module, _device, _toolchain = self._modules()
        self._guide = bundle_module.render_import_guide(
            snapshot_version=self.config.snapshot_version
        )
        return self._stage(
            "render-guide",
            guide_sha256=hashlib.sha256(self._guide).hexdigest(),
            size=len(self._guide),
        )

    @staticmethod
    def _manifest_entry_document(entry: Any) -> dict[str, Any]:
        source = str(entry.source)
        if source.startswith("store:"):
            source = source.removeprefix("store:")
        return {
            "path": str(entry.path),
            "size": int(entry.size),
            "sha256": str(entry.sha256),
            "source": source,
        }

    @staticmethod
    def _player_document(report: Any) -> dict[str, Any]:
        return {
            "player_id": "1000",
            "before_sha256": report.before_sha256,
            "after_sha256": report.after_sha256,
            "before_character_ids": list(report.before_character_ids),
            "after_character_ids": list(report.after_character_ids),
            "added_character_ids": list(report.added_character_ids),
            "character_level": report.character_level,
        }

    @staticmethod
    def _content_document(report: Any) -> dict[str, Any]:
        return {
            "ready": report.ready,
            "client_gate_ready": report.client_gate_ready,
            "rogue": {
                "event_id": report.rogue.event_id,
                "round_count": report.rogue.round_count,
                "token_id": report.rogue.token_id,
                "weapon_ids": list(report.rogue.weapon_ids),
                "missing_logicals": list(report.rogue.missing_logicals),
                "ready": report.rogue.ready,
            },
            "characters": [
                {
                    "identity": dict(character.identity),
                    "evidence_mode": character.evidence_mode,
                    "required_present": character.required_present,
                    "required_total": character.required_total,
                    "three_layer_consistent": character.three_layer_consistent,
                    "bound_files": [
                        RealReleaseServices._manifest_entry_document(entry)
                        for entry in character.bound_files
                    ],
                    "missing": list(character.missing),
                    "seal_sha256": character.seal_sha256,
                    "rejected_workspace_reason": character.rejected_workspace_reason,
                }
                for character in report.characters
            ],
        }

    def _release_evidence(self, source_fingerprint: Mapping[str, Any]) -> dict[str, Any]:
        *_head, bundle_module, _device, _toolchain = self._modules()
        if any(
            value is None
            for value in (
                self._apk_report,
                self._zip_verify_report,
                self._player_report,
                self._content_client_report,
            )
        ):
            raise ReleaseError("release evidence is incomplete")
        entries = sorted(
            (self._manifest_entry_document(entry) for entry in self._entries),
            key=lambda item: item["path"],
        )
        root_bytes = {"common": 0, "medium": 0, "android": 0}
        root_counts = {"common": 0, "medium": 0, "android": 0}
        for entry in entries:
            source = entry["source"]
            if source in root_bytes:
                root_bytes[source] += int(entry["size"])
                root_counts[source] += 1
        first_stage = self._apk_report.stage_reports[0]
        last_stage = self._apk_report.stage_reports[-1]
        first_input = first_stage["input_sha256"]
        last_output = last_stage["output_sha256"]
        commit = self._git_output(("rev-parse", "HEAD"))
        dirty = bool(self._git_output(("status", "--porcelain")))
        if set(source_fingerprint) != {"before", "scan", "after", "unchanged"}:
            raise ReleaseError("release source fingerprint schema is invalid")
        if source_fingerprint.get("unchanged") is not True:
            raise ReleaseError("release source fingerprint is not unchanged")
        before = _source_checkpoint(source_fingerprint["before"], label="before")
        scan = _source_checkpoint(source_fingerprint["scan"], label="scan")
        after = _source_checkpoint(source_fingerprint["after"], label="after")
        _require_same_sources(before, scan)
        _require_same_sources(before, after)
        source_size, source_hash = self._stable_file_hash(Path(self.config.source_apk))
        if (
            not hmac.compare_digest(source_hash, after["source_apk_sha256"])
            or source_size != after["source_apk_size"]
        ):
            raise ReleaseError("source APK drift before candidate freeze")
        return {
            "source_apk": {
                "basename": Path(self.config.source_apk).name,
                "size": source_size,
                "sha256": after["source_apk_sha256"],
            },
            "source_fingerprint": {
                "before": before,
                "scan": scan,
                "after": after,
                "unchanged": True,
            },
            "patches": {
                "before_swf_sha256": first_input,
                "after_swf_sha256": last_output,
                "order": list(self._apk_report.patch_order),
            },
            "signer": {
                "certificate_sha256": self._apk_report.certificate_sha256,
            },
            "versions": {
                "source_resource_version": "1.4.54",
                "output_resource_version": self._apk_report.full_resource_version,
                "snapshot_version": self.config.snapshot_version,
            },
            "data": {
                "archive_sha256": self._zip_verify_report.archive_sha256,
                "member_count": self._zip_verify_report.member_count,
                "total_uncompressed_bytes": self._zip_verify_report.total_uncompressed_bytes,
                "zip64": self._zip_verify_report.zip64,
                "roots": {
                    root: {
                        "count": root_counts[root],
                        "bytes": root_bytes[root],
                        "archive_prefix": bundle_module.ROOT_PREFIXES[root],
                    }
                    for root in ("common", "medium", "android")
                },
                "entries": entries,
            },
            "player": self._player_document(self._player_report),
            "content": self._content_document(self._content_client_report),
            "apk": {
                "output_sha256": self._apk_report.output_sha256,
                "certificate_sha256": self._apk_report.certificate_sha256,
                "full_resource_version": self._apk_report.full_resource_version,
                "aligned": self._apk_report.aligned,
                "signature_schemes": dict(self._apk_report.signature_schemes),
                "verified": self._apk_report.verified,
            },
            "gates": {
                "store_snapshot": True,
                "legacy_tail": True,
                "player_overlay": True,
                "content": True,
                "apk": True,
                "zip": True,
                "source_unchanged": True,
            },
            "git": {"commit": commit, "dirty": dirty},
        }

    @staticmethod
    def _git_output(args: tuple[str, ...]) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            env=_sanitized_child_environment(),
        )
        if completed.returncode != 0:
            raise ReleaseError("cannot collect read-only git release evidence")
        return completed.stdout.strip()

    def freeze_candidate(
        self,
        _config: OfflineReleaseConfig,
        *,
        build_id: str,
        source_fingerprint: Mapping[str, Any],
        **_kwargs: Any,
    ) -> Mapping[str, Any]:
        *_head, bundle_module, _device, _toolchain = self._modules()
        if self._apk_path is None or self._zip_path is None or self._guide is None:
            raise ReleaseError("candidate artifacts are incomplete")
        self._candidate_dir = _candidate_path(self.config, build_id)
        evidence = self._release_evidence(source_fingerprint)
        self._identity = bundle_module.freeze_candidate(
            self._apk_path,
            self._zip_path,
            self._guide,
            self._candidate_dir,
            build_id=build_id,
            release_evidence=evidence,
        )
        return self._stage(
            "freeze-candidate", identity=_public_identity(self._identity)
        )

    def secret_scan(self, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        *_head, bundle_module, _device, _toolchain = self._modules()
        if self._candidate_dir is None:
            raise ReleaseError("freeze-candidate must run before secret-scan")
        report = _validate_release_secret_scan(bundle_module, self._candidate_dir)
        verified, _evidence = bundle_module.verify_candidate(self._candidate_dir)
        if verified != self._identity:
            raise ReleaseError("candidate identity changed after secret scan")
        return self._stage("secret-scan", **report)

    def _load_candidate(self, candidate_id: str) -> tuple[Path, Any, dict[str, Any]]:
        *_head, bundle_module, _device, _toolchain = self._modules()
        candidate = _candidate_path(self.config, candidate_id)
        if candidate.name != f".candidate-{candidate_id}":
            raise ReleaseError("candidate directory identity mismatch")
        identity, evidence = bundle_module.verify_candidate(candidate)
        if identity.build_id != candidate_id:
            raise ReleaseError("candidate build_id does not match its directory")
        self._verification_evidence = _validate_release_secret_scan(
            bundle_module,
            candidate,
        )
        return candidate, identity, evidence

    def load_candidate_identity(
        self,
        candidate_id: str,
        *_args: Any,
        independent: bool = False,
        **_kwargs: Any,
    ) -> Any:
        candidate, identity, evidence = self._load_candidate(candidate_id)
        if independent:
            *_head, bundle_module, _device, _toolchain = self._modules()
            self._verification_evidence = self._independently_verify_release_artifacts(
                candidate,
                identity,
                evidence,
                expected_files=bundle_module.CANDIDATE_FILES,
                final_bundle=False,
            )
        return identity

    def validate_acceptance_receipt(self, receipt: Path, identity: Any, *_args: Any, **_kwargs: Any) -> Any:
        *_head, _bundle, device_module, _toolchain = self._modules()
        return device_module.validate_acceptance_receipt(Path(receipt), identity)

    def finalize_candidate(
        self,
        candidate_dir: Path,
        receipt: Path,
        final_dir: Path,
        *_args: Any,
        **_kwargs: Any,
    ) -> Mapping[str, Any]:
        *_head, bundle_module, device_module, _toolchain = self._modules()
        output = bundle_module.finalize_candidate(
            Path(candidate_dir),
            Path(receipt),
            Path(final_dir),
            receipt_validator=device_module.validate_acceptance_receipt,
        )
        identity = bundle_module.verify_final_bundle(output)
        return {"identity": _public_identity(identity)}

    def verify_final_bundle(
        self,
        final_dir: Path,
        *_args: Any,
        independent: bool = False,
        **_kwargs: Any,
    ) -> Any:
        *_head, bundle_module, _device, _toolchain = self._modules()
        target = Path(final_dir)
        identity = bundle_module.verify_final_bundle(target)
        self._verification_evidence = _validate_release_secret_scan(
            bundle_module,
            target,
        )
        if independent:
            manifest_path = target / bundle_module.MANIFEST_NAME
            try:
                raw = manifest_path.read_bytes()
                manifest = json.loads(raw)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ReleaseError("final manifest cannot be loaded independently") from exc
            if raw != bundle_module.canonical_json_bytes(manifest):
                raise ReleaseError("final manifest is not canonical")
            evidence_fields = (
                "source_apk",
                "source_fingerprint",
                "patches",
                "signer",
                "versions",
                "data",
                "player",
                "content",
                "apk",
                "gates",
                "git",
            )
            evidence = {name: manifest[name] for name in evidence_fields}
            self._verification_evidence = self._independently_verify_release_artifacts(
                target,
                identity,
                evidence,
                expected_files=bundle_module.FINAL_FILES,
                final_bundle=True,
            )
        return identity

    def _target(self, serial: str) -> tuple[Any, Any]:
        *_head, _bundle, device_module, _toolchain = self._modules()
        toolchain = self._toolchain()
        if getattr(toolchain, "adb", None) is None:
            raise ReleaseError("ADB is not available in the verified toolchain")
        target = device_module.DeviceTarget(
            Path(toolchain.adb),
            serial,
            # The operator contract is serial-only ADB.  Task13 requires
            # manager and instance to be supplied as a pair, so an optional
            # discovered manager must not leak into this target.
            mumu_manager=None,
        )
        return target, SubprocessAdbRunner(Path(toolchain.adb))

    def probe_device(self, candidate_id: str, serial: str, *_args: Any, **_kwargs: Any) -> Any:
        *_head, _bundle, device_module, _toolchain = self._modules()
        self._load_candidate(candidate_id)
        target, runner = self._target(serial)
        return device_module.probe_device(target, runner=runner)

    @staticmethod
    def _probe_document(probe: Any) -> dict[str, Any]:
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

    def _prepared_sidecar(self, build_id: str, serial_digest: str) -> Path:
        if _BUILD_ID_RE.fullmatch(build_id) is None:
            raise ReleaseError("device preparation build_id is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", serial_digest) is None:
            raise ReleaseError("device preparation serial digest is invalid")
        return (
            Path(self.config.output_root)
            / self.config.snapshot_version
            / "device-preparation"
            / f"serial-{serial_digest}.json"
        )

    def _prepare_device_bound(
        self,
        candidate_id: str,
        serial: str,
        confirmation: str,
        *_args: Any,
        **_kwargs: Any,
    ) -> Mapping[str, Any]:
        *_head, bundle_module, device_module, _toolchain = self._modules()
        candidate, identity, _evidence = self._load_candidate(candidate_id)
        target, runner = self._target(serial)
        baseline_hint = device_module.probe_device(target, runner=runner)
        self._require_clean_probe(device_module, baseline_hint)
        sidecar = self._prepared_sidecar(candidate_id, baseline_hint.serial_digest)
        sidecar_lease = _acquire_directory_lease(sidecar.parent)
        reserved: _ReservedFile | None = None
        try:
            reserved = _reserve_file(sidecar)
            reserved.destructive_started = True
            probe = device_module.prepare_device(
                target,
                candidate,
                identity,
                confirm=confirmation,
                runner=runner,
            )
            self._require_clean_probe(device_module, probe)
            if probe.serial_digest != baseline_hint.serial_digest:
                raise ReleaseError("device serial digest changed during preparation")
            document = {
                "schema_version": 1,
                "candidate_identity": _public_identity(identity),
                "serial_digest": probe.serial_digest,
                "probe": self._probe_document(probe),
            }
            _finish_reserved_file(
                reserved, bundle_module.canonical_json_bytes(document)
            )
        except BaseException:
            if reserved is not None:
                _abort_reserved_file(reserved)
            raise
        finally:
            _release_directory_lease(sidecar_lease)
        return {
            "prepared": True,
            "build_id": candidate_id,
            "serial_digest": probe.serial_digest,
            "sidecar": sidecar.name,
        }

    def prepare_device(
        self,
        candidate_id: str,
        serial: str,
        confirmation: str,
        *_args: Any,
        **_kwargs: Any,
    ) -> Mapping[str, Any]:
        version_root = _require_safe_release_config(self.config)
        lease = _acquire_directory_lease(version_root)
        try:
            return self._prepare_device_bound(
                candidate_id,
                serial,
                confirmation,
                *_args,
                **_kwargs,
            )
        finally:
            _release_directory_lease(lease)

    @staticmethod
    def _require_clean_probe(device_module: Any, probe: Any) -> None:
        RealReleaseServices._require_qa_probe(
            device_module, probe, probe.serial_digest
        )
        if probe.save_haxe_present_before is not False or probe.dummy_data_present_before is not False:
            raise ReleaseError("device preparation requires a clean shared-data baseline")

    @staticmethod
    def _probe_from_document(device_module: Any, value: Mapping[str, Any]) -> Any:
        expected = {
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
        }
        if set(value) != expected:
            raise ReleaseError("device preparation sidecar probe schema mismatch")
        return device_module.DeviceProbeReport(
            serial_digest=value["serial_digest"],
            package_name=value["package_name"],
            airplane_mode=value["airplane_mode"],
            wifi_disabled=value["wifi_disabled"],
            mobile_disabled=value["mobile_disabled"],
            no_default_route=value["no_default_route"],
            no_active_network=value["no_active_network"],
            companion_ports_unused=value["companion_ports_unused"],
            save_haxe_present_before=value["save_haxe_present_before"],
            dummy_data_present_before=value["dummy_data_present_before"],
            fatal_log_lines=tuple(value["fatal_log_lines"]),
        )

    def _load_prepared_probe(self, identity: Any, serial_digest: str) -> Any:
        *_head, bundle_module, device_module, _toolchain = self._modules()
        sidecar = self._prepared_sidecar(identity.build_id, serial_digest)
        guard = _acquire_sidecar_guard(sidecar)
        locked: _LockedRegular | None = None
        try:
            locked = _open_locked_regular(sidecar)
            raw = _read_locked_regular(locked)
            try:
                document = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ReleaseError("device preparation sidecar is invalid") from exc
            if raw != bundle_module.canonical_json_bytes(document):
                raise ReleaseError("device preparation sidecar is not canonical")
            if set(document) != {
                "schema_version",
                "candidate_identity",
                "serial_digest",
                "probe",
            }:
                raise ReleaseError("device preparation sidecar schema mismatch")
            if document["schema_version"] != 1:
                raise ReleaseError("device preparation sidecar version mismatch")
            if document["candidate_identity"] != _public_identity(identity):
                raise ReleaseError("device preparation candidate identity mismatch")
            if document["serial_digest"] != serial_digest:
                raise ReleaseError("device preparation serial digest mismatch")
            probe = self._probe_from_document(device_module, document["probe"])
            if probe.serial_digest != serial_digest:
                raise ReleaseError("device preparation probe digest mismatch")
            if _read_locked_regular(locked) != raw:
                raise ReleaseError("device preparation sidecar changed during validation")
            return probe
        finally:
            close_error: BaseException | None = None
            if locked is not None:
                try:
                    _close_locked_regular(locked)
                except BaseException as exc:
                    close_error = exc
            try:
                _release_sidecar_guard(guard)
            except BaseException as exc:
                close_error = close_error or exc
            if close_error is not None:
                raise ReleaseError("cannot close prepared sidecar validation handles") from close_error

    @staticmethod
    def _require_qa_probe(device_module: Any, probe: Any, serial_digest: str) -> None:
        if probe.serial_digest != serial_digest or probe.package_name != device_module.EXPECTED_PACKAGE:
            raise ReleaseError("QA device identity mismatch")
        for field_name in device_module.REQUIRED_OFFLINE_PROBE_GATES:
            if getattr(probe, field_name) is not True:
                raise ReleaseError(f"QA device offline gate failed: {field_name}")
        if probe.fatal_log_lines:
            raise ReleaseError("QA device contains fatal or crash log lines")

    def _record_manual_acceptance_bound(
        self,
        candidate_id: str,
        serial: str,
        receipt_out: Path,
        checks: Mapping[str, bool],
        *_args: Any,
        **_kwargs: Any,
    ) -> Any:
        *_head, _bundle, device_module, _toolchain = self._modules()
        _candidate, identity, _evidence = self._load_candidate(candidate_id)
        target, runner = self._target(serial)
        qa_probe = device_module.probe_device(target, runner=runner)
        baseline = self._load_prepared_probe(identity, qa_probe.serial_digest)
        self._require_qa_probe(device_module, qa_probe, baseline.serial_digest)
        combined = device_module.DeviceProbeReport(
            serial_digest=qa_probe.serial_digest,
            package_name=qa_probe.package_name,
            airplane_mode=qa_probe.airplane_mode,
            wifi_disabled=qa_probe.wifi_disabled,
            mobile_disabled=qa_probe.mobile_disabled,
            no_default_route=qa_probe.no_default_route,
            no_active_network=qa_probe.no_active_network,
            companion_ports_unused=qa_probe.companion_ports_unused,
            save_haxe_present_before=baseline.save_haxe_present_before,
            dummy_data_present_before=baseline.dummy_data_present_before,
            fatal_log_lines=qa_probe.fatal_log_lines,
        )
        return device_module.record_manual_acceptance(
            identity, combined, checks, Path(receipt_out)
        )

    def record_manual_acceptance(
        self,
        candidate_id: str,
        serial: str,
        receipt_out: Path,
        checks: Mapping[str, bool],
        *_args: Any,
        **_kwargs: Any,
    ) -> Any:
        version_root = _require_safe_release_config(self.config)
        version_lease = _acquire_directory_lease(version_root)
        receipt_lease: _DirectoryLease | None = None
        try:
            _require_receipt_output_scope(
                self.config,
                candidate_id,
                Path(receipt_out),
            )
            receipt_lease = _acquire_directory_lease(Path(receipt_out).parent)
            return self._record_manual_acceptance_bound(
                candidate_id,
                serial,
                Path(receipt_out),
                checks,
                *_args,
                **_kwargs,
            )
        finally:
            if receipt_lease is not None:
                _release_directory_lease(receipt_lease)
            _release_directory_lease(version_lease)

    def init_signer(self, confirmation: str, *_args: Any, **_kwargs: Any) -> Mapping[str, Any]:
        *_head, _bundle, _device, toolchain_module = self._modules()
        toolchain = self._toolchain()
        config = toolchain_module.init_signer_interactive(
            DEFAULT_RELEASE_HOME,
            confirmation=confirmation,
            java=toolchain.java,
        )
        return {
            "signer_ready": True,
            "certificate_sha256": config.expected_certificate_sha256,
        }


def _result_document(command: str, result: Any) -> dict[str, Any]:
    document: dict[str, Any] = {"command": command, "ok": True}
    if isinstance(result, ReleaseResult):
        document.update(
            {
                "build_id": result.build_id,
                "candidate": result.candidate_dir.name if result.candidate_dir else None,
                "deliverable": (
                    command == "verify"
                    and result.status == "verified"
                    and result.candidate_dir is None
                    and result.final_dir is not None
                ),
                "final": result.final_dir.name if result.final_dir else None,
                "identity": _public_identity(result.identity),
                "status": result.status,
            }
        )
        if command == "verify" and len(result.stage_reports) == 1:
            report = result.stage_reports[0]
            document["verification"] = {
                "name": report["name"],
                **_json_value(report["evidence"]),
            }
    elif isinstance(result, Mapping):
        document.update(_json_value(result))
        document.setdefault("status", "ok")
    else:
        document["result"] = _json_value(result)
        document["status"] = "ok"
    return document


def _error_document(command: str, error: BaseException) -> dict[str, Any]:
    return {
        "command": command,
        "errors": [_redact(error)],
        "ok": False,
        "status": "error",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def build_args(command: str) -> argparse.ArgumentParser:
        item = sub.add_parser(command)
        item.add_argument("--source-apk", type=Path, default=DEFAULT_SOURCE_APK)
        item.add_argument("--snapshot-version", default=DEFAULT_SNAPSHOT_VERSION)
        item.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
        return item

    build_args("preflight")
    build_args("build-candidate")
    probe = sub.add_parser("device-probe")
    probe.add_argument("--candidate", required=True)
    probe.add_argument("--serial", required=True)
    prepare = sub.add_parser("prepare-device")
    prepare.add_argument("--candidate", required=True)
    prepare.add_argument("--serial", required=True)
    prepare.add_argument("--confirm", required=True)
    accept = sub.add_parser("device-accept")
    accept.add_argument("--candidate", required=True)
    accept.add_argument("--serial", required=True)
    accept.add_argument("--receipt-out", type=Path, required=True)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--candidate", required=True)
    finalize.add_argument("--receipt", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify_group = verify.add_mutually_exclusive_group(required=True)
    verify_group.add_argument("--bundle", type=Path)
    verify_group.add_argument("--candidate")
    signer = sub.add_parser("init-signer")
    signer.add_argument("--confirm", required=True)
    for item in (probe, prepare, accept, finalize, verify):
        item.add_argument("--snapshot-version", default=DEFAULT_SNAPSHOT_VERSION)
        item.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser


def _config_from_args(args: argparse.Namespace) -> OfflineReleaseConfig:
    return OfflineReleaseConfig(
        source_apk=Path(getattr(args, "source_apk", DEFAULT_SOURCE_APK)),
        snapshot_version=str(getattr(args, "snapshot_version", DEFAULT_SNAPSHOT_VERSION)),
        output_root=Path(getattr(args, "output_root", DEFAULT_OUTPUT_ROOT)),
        profile_id="cn",
        legacy_zip=DEFAULT_LEGACY_ZIP,
        tail_zip=DEFAULT_TAIL_ZIP,
        toolchain=None,
        signing=None,
    )


def _explicit_checks(input_fn: Callable[[str], str]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name in REQUIRED_MANUAL_CHECKS:
        try:
            answer = input_fn(f"{name} [yes/no]: ")
        except (EOFError, StopIteration) as exc:
            raise ReleaseError("all ten manual checks require explicit yes input") from exc
        if not isinstance(answer, str) or answer.strip().casefold() != "yes":
            raise ReleaseError("all ten manual checks require explicit yes input")
        checks[name] = True
    return checks


def main(
    argv: Sequence[str] | None = None,
    *,
    services: Any | None = None,
    config: OfflineReleaseConfig | None = None,
    input_fn: Callable[[str], str] = input,
) -> int:
    command = str(argv[0]) if argv else "unknown"
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
        command = args.command
        active_config = config or _config_from_args(args)
        service = services or RealReleaseServices(active_config)
        if command == "preflight":
            result = preflight_release(active_config, services=service)
        elif command == "build-candidate":
            result = build_candidate(active_config, services=service)
        elif command == "device-probe":
            result = service.probe_device(args.candidate, args.serial)
        elif command == "prepare-device":
            result = service.prepare_device(
                args.candidate, args.serial, args.confirm
            )
        elif command == "device-accept":
            checks = _explicit_checks(input_fn)
            result = service.record_manual_acceptance(
                args.candidate,
                args.serial,
                args.receipt_out,
                checks,
            )
        elif command == "finalize":
            result = finalize_release(
                active_config,
                candidate_id=args.candidate,
                receipt=args.receipt,
                services=service,
            )
        elif command == "verify":
            result = verify_release(
                active_config,
                bundle=args.bundle,
                candidate_id=args.candidate,
                services=service,
            )
        elif command == "init-signer":
            result = service.init_signer(args.confirm)
        else:
            raise ReleaseError("unknown command")
        print(_canonical_bytes(_result_document(command, result)).decode("utf-8"), end="")
        return 0
    except KeyboardInterrupt:
        document = _error_document(command, ReleaseError("operation cancelled"))
        print(_canonical_bytes(document).decode("utf-8"), end="")
        return 130
    except BaseException as error:
        document = _error_document(command, error)
        print(_canonical_bytes(document).decode("utf-8"), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
