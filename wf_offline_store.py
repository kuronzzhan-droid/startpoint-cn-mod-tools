#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Freeze and verify the immutable three-root CN 1.4.196 asset store."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import stat
import sys
import zipfile
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

import wf_assets
from wf_asset_inventory import DEFAULT_CHUNK_SIZE
from wf_character_pack import ARCHIVE_PREFIXES


MOD_DIR = Path(__file__).resolve().parent
REPO_ROOT = MOD_DIR.parent
RootName = Literal["common", "medium", "android"]
RootedKey = tuple[RootName, str]
ROOT_NAMES: tuple[RootName, ...] = ("common", "medium", "android")
HASHED_RELATIVE_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{38}$")
HASH_DIRECTORY_RE = re.compile(r"^[0-9a-f]{2}$")
KNOWN_BACKUP_RE = re.compile(
    r"(?:^|/)(?:\.bak|.*\.bak(?:-.*)?|.*\.tmp|.*\.part|partial_downloaded\.json)$"
)
REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
# CPython issue #126253: some Windows stat paths surface invalid bit 0x10000000;
# it is not a documented persistent FILE_ATTRIBUTE_* value.
WINDOWS_STAT_INVALID_DIRECTORY_ATTRIBUTE = 0x10000000
EXPECTED_COUNTS: Mapping[RootName, int] = MappingProxyType(
    {"common": 113_822, "medium": 23_458, "android": 1_009}
)
LEGACY_PREFIX = "WorldFlipper/dummy/download/"
LEGACY_MARKERS = {
    "WorldFlipper/dummy/download/.empty",
    "WorldFlipper/dummy/info.json",
}


class StoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoreRoots:
    common: Path
    medium: Path
    android: Path


@dataclass(frozen=True, slots=True)
class StoreMember:
    root: RootName
    relative: str
    source: Path
    size: int
    sha256: str
    stat_signature: tuple[int, ...]

    @property
    def key(self) -> RootedKey:
        return self.root, self.relative


@dataclass(frozen=True, slots=True)
class StoreScanReport:
    roots: StoreRoots
    members: tuple[StoreMember, ...]
    excluded: tuple[str, ...]
    counts: Mapping[RootName, int]
    total_bytes: int
    tree_sha256: str


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    current_count: int
    legacy_count: int
    added: tuple[RootedKey, ...]
    missing: tuple[RootedKey, ...]


@dataclass(frozen=True, slots=True)
class ZipPathReport:
    archive: Path
    members: tuple[RootedKey, ...]


@dataclass(frozen=True, slots=True)
class TailEdgeReport:
    archive: Path
    members: tuple[RootedKey, ...]
    member_count: int


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str
    source: str


@dataclass(frozen=True, slots=True)
class SnapshotReport:
    worldflipper_root: Path
    copied_members: tuple[Path, ...]
    copied_entries: tuple[ManifestEntry, ...]
    generated_entries: tuple[ManifestEntry, ...]


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse(metadata: object) -> bool:
    if stat.S_ISLNK(int(getattr(metadata, "st_mode"))):
        return True
    return bool(int(getattr(metadata, "st_file_attributes", 0)) & REPARSE_ATTRIBUTE)


def _file_id_stat_identity(volume_serial: int, file_id: int) -> tuple[int, int]:
    """Truncate FILE_ID_INFO identity to the width this Python's os.stat reports.

    Before 3.12, Windows os.stat fills st_dev/st_ino from GetFileInformationByHandle
    (32-bit volume serial, 64-bit file index) — the low halves of FILE_ID_INFO.
    """
    if os.name == "nt" and sys.version_info < (3, 12):
        return (volume_serial & 0xFFFF_FFFF, file_id & 0xFFFF_FFFF_FFFF_FFFF)
    return (volume_serial, file_id)


def _stat_signature(metadata: object) -> tuple[int, ...]:
    return (
        int(getattr(metadata, "st_dev", 0)),
        int(getattr(metadata, "st_ino", 0)),
        int(getattr(metadata, "st_mode")),
        int(getattr(metadata, "st_size")),
        int(getattr(metadata, "st_mtime_ns")),
        int(getattr(metadata, "st_ctime_ns")),
        int(getattr(metadata, "st_file_attributes", 0)),
    )


def _opened_file_identity(metadata: object) -> tuple[int, ...]:
    """Fields stable across Path.lstat and os.fstat for the same open file."""
    return (
        int(getattr(metadata, "st_dev", 0)),
        int(getattr(metadata, "st_ino", 0)),
        int(getattr(metadata, "st_mode")),
        int(getattr(metadata, "st_size")),
        int(getattr(metadata, "st_mtime_ns")),
    )


def _checked_lstat(path: Path, *, kind: str) -> object:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise StoreError(f"cannot inspect {kind}: {path}: {error}") from error
    if _is_reparse(metadata):
        raise StoreError(f"reparse point is forbidden for {kind}: {path}")
    return metadata


def _require_same_lstat(path: Path, expected: tuple[int, ...], *, kind: str) -> object:
    metadata = _checked_lstat(path, kind=kind)
    if _stat_signature(metadata) != expected:
        raise StoreError(f"{kind} changed during scan: {path}")
    return metadata


def _windows_final_path_from_handle(handle: int) -> Path:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = kernel32.GetFinalPathNameByHandleW
    function.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
    function.restype = ctypes.c_uint32
    size = 512
    while True:
        buffer = ctypes.create_unicode_buffer(size)
        written = function(ctypes.c_void_p(handle), buffer, size, 0)
        if written == 0:
            raise StoreError(
                f"cannot resolve opened handle final path: WinError {ctypes.get_last_error()}"
            )
        if written < size:
            value = buffer.value
            break
        size = written + 1
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return _absolute(Path(value))


def _windows_final_path(descriptor: int) -> Path | None:
    if os.name != "nt":
        return None
    import msvcrt

    handle = msvcrt.get_osfhandle(descriptor)
    return _windows_final_path_from_handle(handle)


@contextlib.contextmanager
def _windows_directory_guard(
    path: Path, expected_signature: tuple[int, ...], *, kind: str
):
    import ctypes

    class FileIdInfo(ctypes.Structure):
        _fields_ = [
            ("volume_serial", ctypes.c_uint64),
            ("file_id", ctypes.c_ubyte * 16),
        ]

    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    class ByHandleFileInfo(ctypes.Structure):
        _fields_ = [
            ("file_attributes", ctypes.c_uint32),
            ("creation_time", FileTime),
            ("last_access_time", FileTime),
            ("last_write_time", FileTime),
            ("volume_serial", ctypes.c_uint32),
            ("file_size_high", ctypes.c_uint32),
            ("file_size_low", ctypes.c_uint32),
            ("number_of_links", ctypes.c_uint32),
            ("file_index_high", ctypes.c_uint32),
            ("file_index_low", ctypes.c_uint32),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        os.fspath(path),
        0x0001 | 0x0080,  # FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES
        0x0001 | 0x0002,  # FILE_SHARE_READ | FILE_SHARE_WRITE; deliberately no DELETE
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise StoreError(
            f"cannot open guarded Windows {kind}: {path}: WinError {ctypes.get_last_error()}"
        )
    try:
        basic_info = ByHandleFileInfo()
        get_basic_info = kernel32.GetFileInformationByHandle
        get_basic_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(ByHandleFileInfo)]
        get_basic_info.restype = ctypes.c_int
        if not get_basic_info(ctypes.c_void_p(handle), ctypes.byref(basic_info)):
            raise StoreError(
                f"cannot inspect guarded Windows {kind} attributes: {path}: "
                f"WinError {ctypes.get_last_error()}"
            )
        if not basic_info.file_attributes & 0x10:  # FILE_ATTRIBUTE_DIRECTORY
            raise StoreError(f"opened Windows {kind} is not a directory: {path}")
        if basic_info.file_attributes & REPARSE_ATTRIBUTE:
            raise StoreError(f"reparse point is forbidden for opened Windows {kind}: {path}")

        info = FileIdInfo()
        get_info = kernel32.GetFileInformationByHandleEx
        get_info.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        get_info.restype = ctypes.c_int
        if not get_info(
            ctypes.c_void_p(handle), 18, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise StoreError(
                f"cannot inspect guarded Windows {kind}: {path}: "
                f"WinError {ctypes.get_last_error()}"
            )
        opened_identity = _file_id_stat_identity(
            int(info.volume_serial),
            int.from_bytes(bytes(info.file_id), "little"),
        )
        expected_identity = (expected_signature[0], expected_signature[1])
        if opened_identity != expected_identity:
            raise StoreError(
                f"{kind} changed while opening directory handle: {path}: "
                f"expected={expected_identity} actual={opened_identity}"
            )
        final_path = _windows_final_path_from_handle(handle)
        if os.path.normcase(os.fspath(final_path)) != os.path.normcase(
            os.fspath(_absolute(path))
        ):
            raise StoreError(
                f"opened {kind} directory final path mismatch: "
                f"expected={path} actual={final_path}"
            )
        _require_same_lstat(path, expected_signature, kind=kind)
        yield handle
        _require_same_lstat(path, expected_signature, kind=kind)
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


@contextlib.contextmanager
def _stable_reader(
    path: Path,
    expected_signature: tuple[int, ...],
    *,
    kind: str,
):
    before = _require_same_lstat(path, expected_signature, kind=kind)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if os.name != "nt":
        flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise StoreError(f"cannot open {kind}: {path}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if _is_reparse(opened):
            raise StoreError(f"reparse point is forbidden for opened {kind}: {path}")
        expected_identity = _opened_file_identity(before)
        opened_identity = _opened_file_identity(opened)
        if opened_identity != expected_identity:
            raise StoreError(
                f"{kind} changed while opening: {path}: "
                f"expected={expected_identity} actual={opened_identity}"
            )
        final_path = _windows_final_path(descriptor)
        if final_path is not None and os.path.normcase(os.fspath(final_path)) != os.path.normcase(
            os.fspath(_absolute(path))
        ):
            raise StoreError(
                f"opened {kind} final path escaped expected path: expected={path} actual={final_path}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            yield stream
    finally:
        os.close(descriptor)
    _require_same_lstat(path, expected_signature, kind=kind)


def _stream_sha256(stream: object) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(DEFAULT_CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    return size, digest.hexdigest()


def _hash_stable_file(
    path: Path, expected_signature: tuple[int, ...], *, kind: str
) -> tuple[int, str]:
    with _stable_reader(path, expected_signature, kind=kind) as stream:
        return _stream_sha256(stream)


def _scandir_names(path: Path, expected_signature: tuple[int, ...], *, kind: str) -> list[str]:
    _require_same_lstat(path, expected_signature, kind=kind)
    try:
        if os.name == "nt":
            with _windows_directory_guard(path, expected_signature, kind=kind):
                with os.scandir(path) as entries:
                    names = sorted(entry.name for entry in entries)
        else:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                opened = os.fstat(descriptor)
                before = _require_same_lstat(path, expected_signature, kind=kind)
                if _is_reparse(opened) or _opened_file_identity(opened) != _opened_file_identity(
                    before
                ):
                    raise StoreError(f"{kind} changed while opening directory fd: {path}")
                with os.scandir(descriptor) as entries:
                    names = sorted(entry.name for entry in entries)
                after = os.fstat(descriptor)
                if _opened_file_identity(after) != _opened_file_identity(opened):
                    raise StoreError(f"opened {kind} directory changed during scan: {path}")
            finally:
                os.close(descriptor)
    except OSError as error:
        raise StoreError(f"cannot enumerate {kind} {path}: {error}") from error
    _require_same_lstat(path, expected_signature, kind=kind)
    return names


def resolve_store_roots(
    profile: str,
    *,
    profiles_path: Path = MOD_DIR / "profiles.json",
) -> StoreRoots:
    profiles_path = _absolute(Path(profiles_path))
    try:
        payload = json.loads(profiles_path.read_text(encoding="utf-8"))
        selected = payload["profiles"][profile]
        configured = selected["store"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise StoreError(f"cannot resolve profile {profile!r} from {profiles_path}: {error}") from error
    if not isinstance(configured, str) or not configured:
        raise StoreError(f"profile {profile!r} has no valid store path")
    base = profiles_path.parent.parent if profiles_path.parent.name == "mod-tools" else profiles_path.parent
    target_store = _absolute(base / configured)
    located = wf_assets.roots(target_store)
    return StoreRoots(
        common=_absolute(located["upload"]),
        medium=_absolute(located["medium"]),
        android=_absolute(located["android"]),
    )


def _tree_sha256(members: Collection[StoreMember]) -> str:
    digest = hashlib.sha256()
    for member in members:
        digest.update(member.root.encode("ascii"))
        digest.update(b"\0")
        digest.update(member.relative.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(member.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(member.sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def enumerate_hashed_members(roots: StoreRoots) -> StoreScanReport:
    members: list[StoreMember] = []
    excluded: list[str] = []
    seen_roots: set[str] = set()
    for root_name in ROOT_NAMES:
        root = _absolute(getattr(roots, root_name))
        root_key = os.path.normcase(os.fspath(root))
        if root_key in seen_roots:
            raise StoreError(f"store roots must be distinct: {root}")
        seen_roots.add(root_key)
        root_metadata = _checked_lstat(root, kind=f"{root_name} root")
        if not stat.S_ISDIR(int(getattr(root_metadata, "st_mode"))):
            raise StoreError(f"store root is not a directory: {root}")
        root_signature = _stat_signature(root_metadata)
        first_level = _scandir_names(root, root_signature, kind=f"{root_name} root")
        for prefix_name in first_level:
            _require_same_lstat(root, root_signature, kind=f"{root_name} root")
            prefix_path = root / prefix_name
            prefix_metadata = _checked_lstat(prefix_path, kind="store member")
            relative = prefix_name
            if KNOWN_BACKUP_RE.fullmatch(relative) and stat.S_ISREG(
                int(getattr(prefix_metadata, "st_mode"))
            ):
                excluded.append(f"{root_name}:{relative}")
                continue
            if not HASH_DIRECTORY_RE.fullmatch(prefix_name) or not stat.S_ISDIR(
                int(getattr(prefix_metadata, "st_mode"))
            ):
                raise StoreError(f"unknown non-hashed member: {root_name}:{relative}")
            prefix_signature = _stat_signature(prefix_metadata)
            second_level = _scandir_names(prefix_path, prefix_signature, kind="hash directory")
            for file_name in second_level:
                _require_same_lstat(root, root_signature, kind=f"{root_name} root")
                _require_same_lstat(prefix_path, prefix_signature, kind="hash directory")
                source = prefix_path / file_name
                relative = f"{prefix_name}/{file_name}"
                before = _checked_lstat(source, kind="store member")
                if KNOWN_BACKUP_RE.fullmatch(relative) and stat.S_ISREG(
                    int(getattr(before, "st_mode"))
                ):
                    excluded.append(f"{root_name}:{relative}")
                    continue
                if not HASHED_RELATIVE_RE.fullmatch(relative) or not stat.S_ISREG(
                    int(getattr(before, "st_mode"))
                ):
                    raise StoreError(f"unknown non-hashed member: {root_name}:{relative}")
                before_signature = _stat_signature(before)
                size, digest = _hash_stable_file(
                    source, before_signature, kind="store member"
                )
                if size != int(getattr(before, "st_size")):
                    raise StoreError(f"file changed while hashing: {source}")
                _require_same_lstat(root, root_signature, kind=f"{root_name} root")
                _require_same_lstat(prefix_path, prefix_signature, kind="hash directory")
                members.append(
                    StoreMember(
                        root=root_name,
                        relative=relative,
                        source=source,
                        size=int(getattr(before, "st_size")),
                        sha256=digest,
                        stat_signature=before_signature,
                    )
                )
    members.sort(key=lambda item: (ROOT_NAMES.index(item.root), item.relative))
    counts = MappingProxyType(
        {name: sum(member.root == name for member in members) for name in ROOT_NAMES}
    )
    frozen = tuple(members)
    return StoreScanReport(
        roots=StoreRoots(*(_absolute(getattr(roots, name)) for name in ROOT_NAMES)),
        members=frozen,
        excluded=tuple(sorted(excluded)),
        counts=counts,
        total_bytes=sum(member.size for member in frozen),
        tree_sha256=_tree_sha256(frozen),
    )


def _parse_archive_member(name: str, *, legacy: bool) -> RootedKey:
    if "\\" in name or name.startswith("/") or any(part in ("", ".", "..") for part in name.split("/")):
        raise StoreError(f"unsafe ZIP member path: {name}")
    normalized = name
    if legacy:
        if not normalized.startswith(LEGACY_PREFIX):
            raise StoreError(f"unknown legacy ZIP member: {name}")
        normalized = normalized[len(LEGACY_PREFIX):]
    for root_name in ROOT_NAMES:
        prefix = ARCHIVE_PREFIXES[root_name]
        if normalized.startswith(prefix):
            relative = normalized[len(prefix):]
            if HASHED_RELATIVE_RE.fullmatch(relative):
                return root_name, relative
            break
    label = "legacy ZIP" if legacy else "tail edge"
    raise StoreError(f"unknown {label} member: {name}")


def _allowed_legacy_directory(name: str) -> bool:
    normalized = name.rstrip("/")
    fixed = {
        "WorldFlipper",
        "WorldFlipper/dummy",
        "WorldFlipper/dummy/download",
        "WorldFlipper/dummy/download/production",
    }
    if normalized in fixed:
        return True
    for prefix in ARCHIVE_PREFIXES.values():
        root = (LEGACY_PREFIX + prefix).rstrip("/")
        if normalized == root:
            return True
        if normalized.startswith(root + "/") and HASH_DIRECTORY_RE.fullmatch(normalized[len(root) + 1 :]):
            return True
    return False


def inspect_legacy_zip_paths(archive: Path) -> ZipPathReport:
    archive = _absolute(Path(archive))
    members: set[RootedKey] = set()
    member_names: set[str] = set()
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = info.filename
                if name in member_names:
                    raise StoreError(f"duplicate legacy ZIP member name: {name}")
                member_names.add(name)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                unix_kind = stat.S_IFMT(unix_mode)
                if info.create_system == 3 and unix_kind not in (
                    0,
                    stat.S_IFREG,
                    stat.S_IFDIR,
                ):
                    raise StoreError(
                        f"special legacy ZIP member is forbidden: {name}: mode={oct(unix_mode)}"
                    )
                if info.is_dir():
                    if not _allowed_legacy_directory(name):
                        raise StoreError(f"unknown legacy ZIP member: {name}")
                    continue
                if name in LEGACY_MARKERS:
                    continue
                key = _parse_archive_member(name, legacy=True)
                if key in members:
                    raise StoreError(f"duplicate legacy ZIP member: {name}")
                members.add(key)
    except (OSError, zipfile.BadZipFile) as error:
        raise StoreError(f"cannot inspect legacy ZIP {archive}: {error}") from error
    return ZipPathReport(archive=archive, members=tuple(sorted(members)))


def compare_path_sets(
    current: Collection[RootedKey], legacy: Collection[RootedKey]
) -> SnapshotDiff:
    current_set = set(current)
    legacy_set = set(legacy)
    diff = SnapshotDiff(
        len(current),
        len(legacy),
        tuple(sorted(current_set - legacy_set)),
        tuple(sorted(legacy_set - current_set)),
    )
    actual = (diff.current_count, diff.legacy_count, len(diff.added), len(diff.missing))
    if actual != (138_289, 137_820, 469, 0):
        raise StoreError(f"snapshot count mismatch: {diff}")
    if len(current_set) != len(current) or len(legacy_set) != len(legacy):
        raise StoreError("snapshot path sets contain duplicate members")
    return diff


def verify_tail_edge(
    archive: Path,
    *,
    current: Collection[StoreMember] | Mapping[RootedKey, StoreMember] | None = None,
    expected_from: str = "1.4.195",
    expected_to: str = "1.4.196",
) -> TailEdgeReport:
    archive = _absolute(Path(archive))
    version_match = re.fullmatch(
        r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9]\d*)-(.+)\.zip",
        archive.name,
    )
    if version_match is None or version_match.group(1, 2) != (expected_from, expected_to):
        raise StoreError(
            f"tail edge version mismatch: expected {expected_from}->{expected_to}, "
            f"found {archive.name}"
        )
    if current is None:
        raise StoreError("tail edge verification requires current StoreMember metadata")
    if isinstance(current, Mapping):
        current_map = dict(current)
    else:
        current_map = {member.key: member for member in current}
    members: list[RootedKey] = []
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    raise StoreError(f"tail edge contains directory member: {info.filename}")
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                unix_kind = stat.S_IFMT(unix_mode)
                if info.create_system == 3 and unix_kind not in (0, stat.S_IFREG):
                    raise StoreError(
                        f"special tail ZIP member is forbidden: {info.filename}: "
                        f"mode={oct(unix_mode)}"
                    )
                key = _parse_archive_member(info.filename, legacy=False)
                if key[0] != "common":
                    raise StoreError(f"tail edge must contain common members only: {info.filename}")
                if key in members:
                    raise StoreError(f"tail edge contains duplicate member: {info.filename}")
                members.append(key)
                expected = current_map.get(key)
                if expected is None:
                    raise StoreError("tail edge contains members absent from the frozen current store")
                if info.file_size != expected.size:
                    raise StoreError(
                        f"tail edge declared size mismatch for {key}: "
                        f"expected={expected.size} declared={info.file_size}"
                    )
                digest = hashlib.sha256()
                size = 0
                with zf.open(info, "r") as stream:
                    while size <= expected.size:
                        limit = min(DEFAULT_CHUNK_SIZE, expected.size + 1 - size)
                        chunk = stream.read(limit)
                        if not chunk:
                            break
                        digest.update(chunk)
                        size += len(chunk)
                        if size > expected.size:
                            raise StoreError(f"tail edge expands beyond expected size for {key}")
                found_digest = digest.hexdigest()
                if (size, found_digest) != (expected.size, expected.sha256):
                    raise StoreError(
                        f"tail edge content mismatch for {key}: "
                        f"expected size/sha={(expected.size, expected.sha256)}, "
                        f"found size/sha={(size, found_digest)}"
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise StoreError(f"cannot inspect tail edge {archive}: {error}") from error
    if len(members) != 12 or len(set(members)) != 12:
        raise StoreError(f"tail edge must contain exactly 12 unique members, found {len(members)}")
    frozen = tuple(sorted(members))
    return TailEdgeReport(archive=archive, members=frozen, member_count=len(frozen))


def required_free_bytes(total_store_bytes: int, source_apk_bytes: int) -> int:
    if total_store_bytes < 0 or source_apk_bytes < 0:
        raise ValueError("byte counts must be non-negative")
    return total_store_bytes * 2 + source_apk_bytes * 3 + 2 * 1024**3


def marker_entries(
    total_store_bytes: int, *, snapshot_version: str = "1.4.196"
) -> tuple[ManifestEntry, ManifestEntry]:
    if snapshot_version != "1.4.196":
        raise StoreError(f"unsupported offline snapshot version: {snapshot_version}")
    info = (
        json.dumps(
            {
                "version": snapshot_version,
                "assetRecoveryInfo": [],
                "totalSize": total_store_bytes,
                "assetSizeKind": "fulfill",
                "baseUrl": "https://xiaozhiche/",
                "latestModifiedTimeOfArchive": "",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    return (
        ManifestEntry(
            "WorldFlipper/dummy/info.json",
            len(info),
            hashlib.sha256(info).hexdigest(),
            "generated-marker",
        ),
        ManifestEntry(
            "WorldFlipper/dummy/download/.empty",
            1,
            hashlib.sha256(b"0").hexdigest(),
            "generated-marker",
        ),
    )


def _directory_identity(metadata: object) -> tuple[int, ...]:
    return (
        int(getattr(metadata, "st_dev", 0)),
        int(getattr(metadata, "st_ino", 0)),
        int(getattr(metadata, "st_mode")),
        int(getattr(metadata, "st_file_attributes", 0))
        & ~WINDOWS_STAT_INVALID_DIRECTORY_ATTRIBUTE,
    )


def _owned_directory_signature(metadata: object) -> tuple[int, ...]:
    signature = list(_stat_signature(metadata))
    signature[-1] &= ~WINDOWS_STAT_INVALID_DIRECTORY_ATTRIBUTE
    return tuple(signature)


def _verify_owned_chain(
    staging_root: Path,
    parent: Path,
    owned: dict[Path, tuple[int, ...]],
) -> None:
    try:
        relative = parent.relative_to(staging_root)
    except ValueError as error:
        raise StoreError(f"destination parent escapes staging root: {parent}") from error
    current = staging_root
    _require_same_owned_directory(
        current, owned[current], kind="owned staging directory"
    )
    for part in relative.parts:
        current = current / part
        expected = owned.get(current)
        if expected is None:
            raise StoreError(f"unowned staging directory in destination chain: {current}")
        _require_same_owned_directory(
            current, expected, kind="owned staging directory"
        )


def _refresh_owned_parent(
    parent: Path,
    owned: dict[Path, tuple[int, ...]],
) -> None:
    previous = owned[parent]
    current = _checked_lstat(parent, kind="owned staging directory")
    if not stat.S_ISDIR(int(getattr(current, "st_mode"))) or _directory_identity(
        current
    ) != _directory_identity(SimpleStat(previous)):
        raise StoreError(f"owned staging directory identity changed: {parent}")
    owned[parent] = _stat_signature(current)


class SimpleStat:
    """Adapter for comparing a recorded stat signature without magic slices."""

    def __init__(self, signature: tuple[int, ...]) -> None:
        (
            self.st_dev,
            self.st_ino,
            self.st_mode,
            self.st_size,
            self.st_mtime_ns,
            self.st_ctime_ns,
            self.st_file_attributes,
        ) = signature


def _require_same_owned_directory(
    path: Path, expected: tuple[int, ...], *, kind: str
) -> object:
    metadata = _checked_lstat(path, kind=kind)
    if not stat.S_ISDIR(int(getattr(metadata, "st_mode"))) or (
        _owned_directory_signature(metadata)
        != _owned_directory_signature(SimpleStat(expected))
    ):
        raise StoreError(f"{kind} changed during scan: {path}")
    return metadata


def _open_exclusive_at(
    parent_descriptor: int,
    name: str,
    *,
    nofollow_flag: int,
) -> int:
    """Create one basename relative to a verified POSIX directory descriptor."""
    if name in ("", ".", "..") or Path(name).name != name:
        raise StoreError(f"unsafe relative staging filename: {name}")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | nofollow_flag
        | getattr(os, "O_BINARY", 0)
    )
    return os.open(name, flags, 0o600, dir_fd=parent_descriptor)


@contextlib.contextmanager
def _posix_directory_guard(
    path: Path, expected_signature: tuple[int, ...], *, kind: str
):
    before = _require_same_owned_directory(path, expected_signature, kind=kind)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise StoreError(f"cannot open guarded POSIX {kind}: {path}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or _directory_identity(opened) != _directory_identity(before):
            raise StoreError(f"{kind} changed while opening POSIX directory fd: {path}")
        yield descriptor
        after = os.fstat(descriptor)
        if _directory_identity(after) != _directory_identity(opened):
            raise StoreError(f"opened POSIX {kind} identity changed: {path}")
    finally:
        os.close(descriptor)


def _ensure_owned_directory(
    staging_root: Path,
    relative: Path,
    owned: dict[Path, tuple[int, ...]],
) -> Path:
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise StoreError(f"unsafe staging directory path: {relative}")
    current = staging_root
    for part in relative.parts:
        _verify_owned_chain(staging_root, current, owned)
        child = current / part
        if child in owned:
            _require_same_owned_directory(
                child, owned[child], kind="owned staging directory"
            )
            current = child
            continue
        try:
            os.mkdir(child)
        except OSError as error:
            raise StoreError(f"cannot create staging directory {child}: {error}") from error
        _refresh_owned_parent(current, owned)
        child_metadata = _checked_lstat(child, kind="new staging directory")
        if not stat.S_ISDIR(int(getattr(child_metadata, "st_mode"))):
            raise StoreError(f"new staging path is not a directory: {child}")
        owned[child] = _stat_signature(child_metadata)
        _verify_owned_chain(staging_root, child, owned)
        current = child
    return current


@contextlib.contextmanager
def _exclusive_staging_writer(
    staging_root: Path,
    destination: Path,
    owned: dict[Path, tuple[int, ...]],
):
    """Exclusive staging writer.

    POSIX creates relative to a held, verified parent dirfd. Windows holds the
    owned-chain checks and validates the opened handle final path before the
    first payload byte; without a native handle-relative create, an adversarial
    concurrent swap can leave a newly created zero-byte external file or empty
    directory, but can never overwrite an existing node or receive payload bytes.
    """
    parent = destination.parent
    _verify_owned_chain(staging_root, parent, owned)
    guard = (
        _posix_directory_guard(parent, owned[parent], kind="owned staging directory")
        if os.name != "nt"
        else contextlib.nullcontext(None)
    )
    with guard as parent_descriptor:
        try:
            if os.name != "nt":
                descriptor = _open_exclusive_at(
                    parent_descriptor,
                    destination.name,
                    nofollow_flag=os.O_NOFOLLOW,
                )
            else:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                descriptor = os.open(destination, flags, 0o600)
        except OSError as error:
            raise StoreError(
                f"cannot exclusively create staging file {destination}: {error}"
            ) from error
        try:
            _refresh_owned_parent(parent, owned)
            opened = os.fstat(descriptor)
            if _is_reparse(opened) or not stat.S_ISREG(int(getattr(opened, "st_mode"))):
                raise StoreError(
                    f"new staging file is not a regular non-reparse file: {destination}"
                )
            final_path = _windows_final_path(descriptor)
            if final_path is not None and os.path.normcase(os.fspath(final_path)) != os.path.normcase(
                os.fspath(_absolute(destination))
            ):
                raise StoreError(
                    f"opened staging file final path escaped staging root: "
                    f"expected={destination} actual={final_path}"
                )
            _verify_owned_chain(staging_root, parent, owned)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                yield stream
            final_opened = os.fstat(descriptor)
            final_path_metadata = _checked_lstat(destination, kind="staging destination")
            if _opened_file_identity(final_opened) != _opened_file_identity(final_path_metadata):
                raise StoreError(f"staging destination changed while writing: {destination}")
            _verify_owned_chain(staging_root, parent, owned)
        finally:
            os.close(descriptor)


def _write_generated(
    staging_root: Path,
    owned: dict[Path, tuple[int, ...]],
    relative: Path,
    data: bytes,
) -> None:
    parent = _ensure_owned_directory(staging_root, relative.parent, owned)
    path = parent / relative.name
    with _exclusive_staging_writer(staging_root, path, owned) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def materialize_snapshot(
    scan: StoreScanReport,
    worldflipper_root: Path,
    *,
    snapshot_version: str,
) -> SnapshotReport:
    if snapshot_version != "1.4.196":
        raise StoreError(f"unsupported offline snapshot version: {snapshot_version}")
    worldflipper_root = _absolute(Path(worldflipper_root))
    parent = worldflipper_root.parent
    parent_metadata = _checked_lstat(parent, kind="staging parent")
    if not stat.S_ISDIR(int(getattr(parent_metadata, "st_mode"))):
        raise StoreError(f"staging parent is not a directory: {parent}")
    try:
        worldflipper_root.lstat()
    except FileNotFoundError:
        pass
    except OSError as error:
        raise StoreError(f"cannot inspect staging destination {worldflipper_root}: {error}") from error
    else:
        raise StoreError(f"staging destination must not already exist: {worldflipper_root}")

    fresh_scan = enumerate_hashed_members(scan.roots)
    if fresh_scan.tree_sha256 != scan.tree_sha256 or fresh_scan.members != scan.members:
        raise StoreError("source drift detected since scan")

    parent_before = _stat_signature(parent_metadata)
    try:
        os.mkdir(worldflipper_root)
    except OSError as error:
        raise StoreError(f"cannot create staging root {worldflipper_root}: {error}") from error
    parent_after = _checked_lstat(parent, kind="staging parent")
    if _directory_identity(parent_after) != _directory_identity(SimpleStat(parent_before)):
        raise StoreError(f"staging parent identity changed while creating root: {parent}")
    root_metadata = _checked_lstat(worldflipper_root, kind="new staging root")
    if not stat.S_ISDIR(int(getattr(root_metadata, "st_mode"))):
        raise StoreError(f"new staging root is not a directory: {worldflipper_root}")
    owned_directories = {worldflipper_root: _stat_signature(root_metadata)}
    copied_paths: list[Path] = []
    copied_entries: list[ManifestEntry] = []
    for member in scan.members:
        destination_relative = ARCHIVE_PREFIXES[member.root] + member.relative
        relative = Path("dummy") / "download" / Path(destination_relative)
        destination_parent = _ensure_owned_directory(
            worldflipper_root, relative.parent, owned_directories
        )
        destination = destination_parent / relative.name
        digest = hashlib.sha256()
        copied_size = 0
        with _stable_reader(
            member.source, member.stat_signature, kind="snapshot source"
        ) as source:
            with _exclusive_staging_writer(
                worldflipper_root, destination, owned_directories
            ) as target:
                while True:
                    chunk = source.read(DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    copied_size += len(chunk)
                target.flush()
                os.fsync(target.fileno())
        copied_hash = digest.hexdigest()
        if copied_size != member.size or copied_hash != member.sha256:
            raise StoreError(f"copied content mismatch: {member.source}")
        destination_metadata = _checked_lstat(destination, kind="snapshot destination")
        if int(getattr(destination_metadata, "st_size")) != member.size:
            raise StoreError(f"copied destination size mismatch: {destination}")
        destination_signature = _stat_signature(destination_metadata)
        _, destination_hash = _hash_stable_file(
            destination, destination_signature, kind="snapshot destination"
        )
        if destination_hash != member.sha256:
            raise StoreError(f"copied destination SHA-256 mismatch: {destination}")
        copied_paths.append(destination)
        copied_entries.append(
            ManifestEntry(
                f"WorldFlipper/dummy/download/{destination_relative}",
                member.size,
                member.sha256,
                f"store:{member.root}",
            )
        )

    final_scan = enumerate_hashed_members(scan.roots)
    if final_scan.tree_sha256 != scan.tree_sha256 or final_scan.members != scan.members:
        raise StoreError("source drift detected after snapshot copy")

    generated = marker_entries(scan.total_bytes, snapshot_version=snapshot_version)
    info_payload = (
        json.dumps(
            {
                "version": snapshot_version,
                "assetRecoveryInfo": [],
                "totalSize": scan.total_bytes,
                "assetSizeKind": "fulfill",
                "baseUrl": "https://xiaozhiche/",
                "latestModifiedTimeOfArchive": "",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    _write_generated(
        worldflipper_root, owned_directories, Path("dummy/info.json"), info_payload
    )
    _write_generated(
        worldflipper_root,
        owned_directories,
        Path("dummy/download/.empty"),
        b"0",
    )
    return SnapshotReport(
        worldflipper_root=worldflipper_root,
        copied_members=tuple(copied_paths),
        copied_entries=tuple(copied_entries),
        generated_entries=generated,
    )


def _repo_path(value: str) -> Path:
    path = Path(value)
    return _absolute(path if path.is_absolute() else REPO_ROOT / path)


def preflight(args: argparse.Namespace) -> dict[str, object]:
    if args.snapshot_version != "1.4.196":
        raise StoreError(f"unsupported offline snapshot version: {args.snapshot_version}")
    if not args.no_copy:
        raise StoreError("preflight is metadata-only; --no-copy is required")
    roots = resolve_store_roots(args.profile)
    scan = enumerate_hashed_members(roots)
    if dict(scan.counts) != dict(EXPECTED_COUNTS):
        raise StoreError(f"store root count mismatch: {dict(scan.counts)}")
    legacy = inspect_legacy_zip_paths(_repo_path(args.legacy_zip))
    diff = compare_path_sets(tuple(member.key for member in scan.members), legacy.members)
    tail = verify_tail_edge(
        _repo_path(args.tail_zip),
        current=scan.members,
        expected_from="1.4.195",
        expected_to="1.4.196",
    )
    return {
        "ok": True,
        "mode": "metadata-only",
        "no_copy": True,
        "snapshot_version": args.snapshot_version,
        "counts": dict(scan.counts),
        "total_count": len(scan.members),
        "total_bytes": scan.total_bytes,
        "tree_sha256": scan.tree_sha256,
        "excluded": list(scan.excluded),
        "legacy_count": diff.legacy_count,
        "added_count": len(diff.added),
        "missing_count": len(diff.missing),
        "tail_verified": tail.member_count,
        "staging_created": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("preflight", help="hash and compare metadata without copying")
    command.add_argument("--profile", required=True)
    command.add_argument("--snapshot-version", required=True, choices=("1.4.196",))
    command.add_argument("--legacy-zip", required=True)
    command.add_argument("--tail-zip", required=True)
    command.add_argument("--no-copy", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(args)
        else:
            parser.error(f"unknown command: {args.command}")
    except StoreError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
