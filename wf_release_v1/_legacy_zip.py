"""Bounded ZIP primitives for read-only legacy-share inspection."""

from __future__ import annotations

import os
from pathlib import PurePosixPath
import stat
import struct
from typing import BinaryIO, Final, Mapping, Sequence
import unicodedata
import zipfile
import zlib

from .canonical import normalize_relative_path
from .errors import ReleaseError


MAX_METADATA_BYTES: Final = 1024 * 1024
MAX_SERVER_JSON_BYTES: Final = 256 * 1024 * 1024
MAX_MEMBER_BYTES: Final = 8 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 16 * 1024 * 1024 * 1024
MAX_MEMBERS: Final = 65534
MAX_CENTRAL_BYTES: Final = 256 * 1024 * 1024
RATIO_THRESHOLD: Final = 1024 * 1024
MAX_COMPRESSION_RATIO: Final = 100
_WINDOWS_FORBIDDEN: Final = frozenset('<>:"\\|?*')
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
)
_READ_ERRORS: Final = (
    OSError,
    RuntimeError,
    NotImplementedError,
    EOFError,
    zipfile.BadZipFile,
    zipfile.LargeZipFile,
    zlib.error,
)


def error(message: str, **details: object) -> ReleaseError:
    return ReleaseError("WFREL_SHARE_INVALID", message, details)


def central_preflight(stream: BinaryIO) -> None:
    """Bound central-directory allocation before ``ZipFile.infolist`` runs."""
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if size < 22 or size > MAX_TOTAL_BYTES:
            raise ValueError("unsafe ZIP size")
        tail_size = min(size, 65557)
        stream.seek(size - tail_size)
        tail = stream.read(tail_size)
        relative = tail.rfind(b"PK\x05\x06")
        if relative < 0:
            raise ValueError("EOCD is missing")
        eocd_at = size - tail_size + relative
        eocd = struct.unpack("<IHHHHIIH", tail[relative : relative + 22])
        _, disk, central_disk, disk_count, count, central_size, central_at, comment = eocd
        if eocd_at + 22 + comment != size:
            raise ValueError("EOCD is not at EOF")
        central_end = eocd_at
        if 0xFFFF in (disk_count, count) or 0xFFFFFFFF in (central_size, central_at):
            if eocd_at < 20:
                raise ValueError("ZIP64 locator is missing")
            stream.seek(eocd_at - 20)
            locator = struct.unpack("<IIQI", stream.read(20))
            if locator[0] != 0x07064B50 or locator[1] != 0 or locator[3] != 1:
                raise ValueError("ZIP64 locator is invalid")
            zip64_at = locator[2]
            stream.seek(zip64_at)
            fixed = stream.read(56)
            if len(fixed) != 56:
                raise ValueError("ZIP64 EOCD is truncated")
            values = struct.unpack("<IQHHIIQQQQ", fixed)
            (
                signature,
                record_size,
                _made_by,
                _extract,
                zip_disk,
                zip_central_disk,
                zip_disk_count,
                zip_count,
                zip_central_size,
                zip_central_at,
            ) = values
            if (
                signature != 0x06064B50
                or record_size < 44
                or zip_disk != 0
                or zip_central_disk != 0
                or zip_disk_count != zip_count
                or zip64_at + 12 + record_size != eocd_at - 20
            ):
                raise ValueError("ZIP64 EOCD is invalid")
            count, central_size, central_at, central_end = (
                zip_count,
                zip_central_size,
                zip_central_at,
                zip64_at,
            )
        elif disk != 0 or central_disk != 0 or disk_count != count:
            raise ValueError("multi-disk ZIP is invalid")
        if (
            count == 0
            or count > MAX_MEMBERS
            or central_size <= 0
            or central_size > MAX_CENTRAL_BYTES
            or central_at + central_size != central_end
        ):
            raise ValueError("central directory exceeds limits")
        stream.seek(0)
    except (OSError, ValueError, struct.error) as exc:
        raise error("legacy share central directory is unsafe") from exc


def _portable_name(value: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise error("legacy share member path is not normalized")
    try:
        normalized = normalize_relative_path(value)
    except ReleaseError as exc:
        raise error("legacy share contains an unsafe member") from exc
    parts = PurePosixPath(normalized).parts
    if any(
        part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        or any(character in _WINDOWS_FORBIDDEN or ord(character) < 0x20 for character in part)
        for part in parts
    ):
        raise error("legacy share member path is not portable")
    return normalized


def safe_name(info: zipfile.ZipInfo) -> str:
    original = _portable_name(info.orig_filename.rstrip("/") if info.is_dir() else info.orig_filename)
    normalized = _portable_name(info.filename.rstrip("/") if info.is_dir() else info.filename)
    if original != normalized:
        raise error("legacy share raw member name is ambiguous")
    return normalized


def validate_infos(
    infos: Sequence[zipfile.ZipInfo],
    *,
    allow_directories: bool,
) -> tuple[tuple[str, zipfile.ZipInfo], ...]:
    if not infos or len(infos) > MAX_MEMBERS:
        raise error("legacy share member count is invalid")
    result: list[tuple[str, zipfile.ZipInfo]] = []
    kinds: dict[str, bool] = {}
    total = 0
    for info in infos:
        name = safe_name(info)
        folded = unicodedata.normalize("NFC", name).casefold()
        is_directory = info.is_dir()
        if folded in kinds:
            raise error("legacy share contains duplicate portable members")
        if is_directory and not allow_directories:
            raise error("legacy content archive cannot contain directories")
        for parent in PurePosixPath(folded).parents:
            parent_name = parent.as_posix()
            if parent_name == ".":
                break
            if kinds.get(parent_name) is False:
                raise error("legacy share contains a file-directory collision")
        if not is_directory and any(
            existing.startswith(folded + "/") for existing in kinds
        ):
            raise error("legacy share contains a file-directory collision")
        kinds[folded] = is_directory
        if is_directory:
            if info.file_size != 0:
                raise error("legacy share directory entry is invalid")
            continue
        mode = (info.external_attr >> 16) & 0xFFFF
        if info.flag_bits & 0x1 or (info.create_system == 3 and mode and not stat.S_ISREG(mode)):
            raise error("legacy share contains a non-regular member")
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise error("legacy share compression method is unsupported")
        if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
            raise error("legacy share member is too large")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise error("legacy share is too large")
        if info.file_size > RATIO_THRESHOLD and (
            info.compress_size <= 0
            or info.file_size > info.compress_size * MAX_COMPRESSION_RATIO
        ):
            raise error("legacy share compression ratio is unsafe")
        result.append((name, info))
    return tuple(result)


def outer_files(bundle: zipfile.ZipFile) -> tuple[str, dict[str, zipfile.ZipInfo]]:
    infos = bundle.infolist()
    members = validate_infos(infos, allow_directories=True)
    roots = {safe_name(info).partition("/")[0] for info in infos}
    files: dict[str, zipfile.ZipInfo] = {}
    for name, info in members:
        root, separator, relative = name.partition("/")
        if not separator or not relative:
            raise error("legacy share files must be under one root directory")
        files[relative] = info
    if len(roots) != 1 or not files:
        raise error("legacy share must contain exactly one root directory")
    return next(iter(roots)), files


def read_member(bundle: zipfile.ZipFile, info: zipfile.ZipInfo, *, limit: int, label: str) -> bytes:
    if info.file_size > limit:
        raise error(f"{label} is too large")
    try:
        raw = bundle.read(info)
    except _READ_ERRORS as exc:
        raise error(f"{label} is corrupt or unreadable") from exc
    if len(raw) != info.file_size:
        raise error(f"{label} length changed")
    return raw


def copy_member(
    bundle: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: BinaryIO | None = None,
) -> tuple[int, str]:
    import hashlib

    digest = hashlib.sha256()
    size = 0
    try:
        with bundle.open(info, "r") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_MEMBER_BYTES:
                    raise error("legacy share member is too large")
                digest.update(chunk)
                if destination is not None:
                    destination.write(chunk)
    except ReleaseError:
        raise
    except _READ_ERRORS as exc:
        raise error("legacy share member CRC is invalid") from exc
    if size != info.file_size:
        raise error("legacy share member length changed")
    if destination is not None:
        destination.flush()
        destination.seek(0)
    return size, digest.hexdigest()


def validate_payload_members(
    bundle: zipfile.ZipFile,
    infos: Mapping[str, zipfile.ZipInfo],
    *,
    skip: set[str],
) -> None:
    for name, info in infos.items():
        if name not in skip:
            copy_member(bundle, info)


__all__ = [
    "MAX_METADATA_BYTES",
    "MAX_SERVER_JSON_BYTES",
    "central_preflight",
    "copy_member",
    "error",
    "outer_files",
    "read_member",
    "safe_name",
    "validate_infos",
    "validate_payload_members",
]
