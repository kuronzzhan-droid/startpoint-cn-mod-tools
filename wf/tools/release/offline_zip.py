# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import BinaryIO, Mapping, Sequence

from wf_offline_store import ManifestEntry


FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_EXTERNAL_ATTR = 0o100644 << 16
COPY_CHUNK_SIZE = 1024 * 1024

WORLD_FLIPPER_ROOT = "WorldFlipper/"
INFO_PATH = "WorldFlipper/dummy/info.json"
EMPTY_PATH = "WorldFlipper/dummy/download/.empty"
PRODUCTION_PREFIXES = MappingProxyType(
    {
        "common": "WorldFlipper/dummy/download/production/upload/",
        "medium": "WorldFlipper/dummy/download/production/medium_upload/",
        "android": "WorldFlipper/dummy/download/production/android_upload/",
    }
)
PRODUCTION_HASHED_COUNTS = MappingProxyType(
    {"common": 113_822, "medium": 23_458, "android": 1_009}
)
PRODUCTION_MEMBER_COUNT = 138_291
PRODUCTION_MARKER_COUNT = 2
CONTENT_SNAPSHOT_VERSION = "1.4.196"
FIXED_CREATE_VERSION = 45
FIXED_EXTRACT_VERSION = 45
FIXED_FLAG_BITS = 0
FIXED_INTERNAL_ATTR = 0
FIXED_LOCAL_DOS_TIME = 0
FIXED_LOCAL_DOS_DATE = 33

_HASHED_TAIL_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{38}$")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_EMPTY_SHA256 = hashlib.sha256(b"0").hexdigest()
_EOCD = struct.Struct(zipfile.structEndArchive)
_ZIP64_EOCD = struct.Struct(zipfile.structEndArchive64)
_ZIP64_LOCATOR = struct.Struct(zipfile.structEndArchive64Locator)
_LOCAL_FILE_HEADER = struct.Struct(zipfile.structFileHeader)
_CENTRAL_DIRECTORY_HEADER = struct.Struct(zipfile.structCentralDir)
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_BINARY_FLAG = getattr(os, "O_BINARY", 0)
_NOFOLLOW_FLAG = getattr(os, "O_NOFOLLOW", 0)
_NOINHERIT_FLAG = getattr(os, "O_NOINHERIT", 0)


class OfflineZipError(ValueError):
    """Raised when an offline data archive violates the release contract."""


@dataclass(frozen=True, slots=True)
class ZipVerificationReport:
    archive_sha256: str
    member_count: int
    counts: Mapping[str, int]
    total_uncompressed_bytes: int
    zip64: bool


ZipBuildReport = ZipVerificationReport


@dataclass(frozen=True, slots=True)
class _Zip64EndState:
    disk_entries: int
    total_entries: int
    central_size: int
    central_offset: int
    record_offset: int


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    device: int
    inode: int


def _is_reparse(metadata: object) -> bool:
    if stat.S_ISLNK(int(getattr(metadata, "st_mode"))):
        return True
    return bool(int(getattr(metadata, "st_file_attributes", 0)) & _REPARSE_ATTRIBUTE)


def _identity_from_stat(metadata: object) -> _FileIdentity:
    return _FileIdentity(
        device=int(getattr(metadata, "st_dev")),
        inode=int(getattr(metadata, "st_ino")),
    )


def _validate_archive_file_metadata(metadata: object, label: str) -> None:
    if _is_reparse(metadata):
        raise OfflineZipError(f"{label} must not be a symlink or reparse point")
    if not stat.S_ISREG(int(getattr(metadata, "st_mode"))):
        raise OfflineZipError(f"{label} must be a regular file")


def _path_identity(path: Path) -> _FileIdentity:
    metadata = os.lstat(path)
    _validate_archive_file_metadata(metadata, "archive path")
    return _identity_from_stat(metadata)


def _stream_identity(stream: BinaryIO) -> _FileIdentity:
    metadata = os.fstat(stream.fileno())
    _validate_archive_file_metadata(metadata, "archive handle")
    return _identity_from_stat(metadata)


def _bind_path_identity(path: Path, stream: BinaryIO) -> _FileIdentity:
    handle_identity = _stream_identity(stream)
    if _path_identity(path) != handle_identity:
        raise OfflineZipError("archive path identity changed while opening")
    return handle_identity


def _require_path_identity(path: Path, expected: _FileIdentity) -> None:
    if _path_identity(path) != expected:
        raise OfflineZipError("archive path identity changed during operation")


def _cleanup_owned_output(path: Path, expected: _FileIdentity) -> None:
    try:
        if _path_identity(path) == expected:
            os.unlink(path)
    except (OSError, OfflineZipError):
        return


def _open_exclusive_archive(path: Path) -> tuple[BinaryIO, _FileIdentity]:
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | _BINARY_FLAG | _NOFOLLOW_FLAG | _NOINHERIT_FLAG
    descriptor = os.open(path, flags, 0o600)
    identity: _FileIdentity | None = None
    try:
        metadata = os.fstat(descriptor)
        _validate_archive_file_metadata(metadata, "archive handle")
        identity = _identity_from_stat(metadata)
        stream = os.fdopen(descriptor, "w+b")
    except Exception:
        os.close(descriptor)
        if identity is not None:
            _cleanup_owned_output(path, identity)
        raise
    try:
        if _path_identity(path) != identity:
            raise OfflineZipError("archive path identity changed while opening")
        return stream, identity
    except Exception:
        stream.close()
        if identity is not None:
            _cleanup_owned_output(path, identity)
        raise


def _open_existing_archive(path: Path) -> tuple[BinaryIO, _FileIdentity]:
    flags = os.O_RDONLY | _BINARY_FLAG | _NOFOLLOW_FLAG | _NOINHERIT_FLAG
    descriptor = os.open(path, flags)
    try:
        stream = os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise
    try:
        return stream, _bind_path_identity(path, stream)
    except Exception:
        stream.close()
        raise


def _sync_stream(stream: BinaryIO) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = FIXED_EXTERNAL_ATTR
    info.extra = b""
    info.comment = b""
    return info


def _classify_path(path: str) -> str:
    if path in (INFO_PATH, EMPTY_PATH):
        return "markers"
    for kind, prefix in PRODUCTION_PREFIXES.items():
        if path.startswith(prefix) and _HASHED_TAIL_RE.fullmatch(path[len(prefix) :]):
            return kind
    raise OfflineZipError(f"member path is outside the offline data whitelist: {path!r}")


def _validate_path(path: str) -> None:
    if not isinstance(path, str) or not path:
        raise OfflineZipError("member path must be a non-empty string")
    if "\\" in path:
        raise OfflineZipError(f"member path contains a backslash: {path!r}")
    if path.startswith("/") or _DRIVE_RE.match(path):
        raise OfflineZipError(f"member path must be release-relative: {path!r}")
    parts = path.split("/")
    if "" in parts or "." in parts or ".." in parts:
        if path.endswith("/"):
            raise OfflineZipError(f"explicit directory member is forbidden: {path!r}")
        raise OfflineZipError(f"member path contains an empty or traversal segment: {path!r}")
    if not path.startswith(WORLD_FLIPPER_ROOT):
        raise OfflineZipError(f"member path must use the exact WorldFlipper/ root: {path!r}")
    if len(parts) > 1 and parts[1].casefold() == "worldflipper":
        raise OfflineZipError(f"double WorldFlipper root is forbidden: {path!r}")
    _classify_path(path)


def _validate_paths(paths: Sequence[str]) -> None:
    exact: set[str] = set()
    folded: dict[str, str] = {}
    for path in paths:
        if path in exact:
            raise OfflineZipError(f"duplicate member path: {path!r}")
        exact.add(path)
        key = path.casefold()
        previous = folded.get(key)
        if previous is not None:
            raise OfflineZipError(f"casefold member path collision: {previous!r} and {path!r}")
        folded[key] = path
    for path in paths:
        _validate_path(path)


def _validate_entry_names(entries: Sequence[ManifestEntry]) -> None:
    for entry in entries:
        if not isinstance(entry, ManifestEntry):
            raise OfflineZipError("manifest entries must be ManifestEntry records")
        if not isinstance(entry.path, str):
            raise OfflineZipError("manifest path must be a string")
        if type(entry.size) is not int:
            raise OfflineZipError(f"manifest size must be an integer: {entry.path!r}")
        if entry.size < 0:
            raise OfflineZipError(f"manifest size must be non-negative: {entry.path!r}")
        if not isinstance(entry.sha256, str):
            raise OfflineZipError(f"manifest SHA-256 must be a string: {entry.path!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", entry.sha256):
            raise OfflineZipError(f"manifest SHA-256 is not canonical lowercase hex: {entry.path!r}")
        if entry.path == EMPTY_PATH and (entry.size != 1 or entry.sha256 != _EMPTY_SHA256):
            raise OfflineZipError(".empty must be exactly one ASCII byte '0'")
    _validate_paths([entry.path for entry in entries])


def _validate_marker_payload(path: str, payload: bytes) -> None:
    if path == EMPTY_PATH and payload != b"0":
        raise OfflineZipError(".empty must be exactly one ASCII byte '0'")
    if path != INFO_PATH:
        return
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfflineZipError(f"info.json is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(parsed, dict) or parsed.get("version") != CONTENT_SNAPSHOT_VERSION:
        raise OfflineZipError(
            f"info.json version must be {CONTENT_SNAPSHOT_VERSION}"
        )


def _copy_and_verify(source: Path, destination: BinaryIO, entry: ManifestEntry) -> None:
    digest = hashlib.sha256()
    size = 0
    marker_payload = bytearray() if entry.path in (INFO_PATH, EMPTY_PATH) else None
    try:
        with source.open("rb") as input_file:
            while chunk := input_file.read(COPY_CHUNK_SIZE):
                destination.write(chunk)
                digest.update(chunk)
                size += len(chunk)
                if marker_payload is not None:
                    marker_payload.extend(chunk)
    except OSError as exc:
        raise OfflineZipError(f"cannot read staged member {entry.path!r}: {exc}") from exc
    if size != entry.size:
        raise OfflineZipError(
            f"staged member size mismatch for {entry.path!r}: expected {entry.size}, got {size}"
        )
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != entry.sha256:
        raise OfflineZipError(
            f"staged member SHA-256 mismatch for {entry.path!r}: "
            f"expected {entry.sha256}, got {actual_sha256}"
        )
    if marker_payload is not None:
        _validate_marker_payload(entry.path, bytes(marker_payload))


def _stream_size(stream: BinaryIO) -> int:
    return int(os.fstat(stream.fileno()).st_size)


def _find_eocd(stream: BinaryIO) -> tuple[int, tuple[object, ...], bytes]:
    size = _stream_size(stream)
    tail_size = min(size, zipfile.ZIP_MAX_COMMENT + zipfile.sizeEndCentDir)
    stream.seek(size - tail_size)
    tail = stream.read(tail_size)
    relative = tail.rfind(zipfile.stringEndArchive)
    if relative < 0 or len(tail) - relative < _EOCD.size:
        raise OfflineZipError("archive has no valid ZIP end record")
    record = _EOCD.unpack(tail[relative : relative + _EOCD.size])
    comment_length = int(record[-1])
    end = relative + _EOCD.size + comment_length
    if end != len(tail):
        raise OfflineZipError("archive ZIP end record has an invalid comment length")
    return size - tail_size + relative, record, tail[relative:]


def _read_zip64_eocd(stream: BinaryIO) -> _Zip64EndState | None:
    eocd_offset, _, _ = _find_eocd(stream)
    locator_offset = eocd_offset - _ZIP64_LOCATOR.size
    if locator_offset < 0:
        return None
    stream.seek(locator_offset)
    locator_data = stream.read(_ZIP64_LOCATOR.size)
    if len(locator_data) != _ZIP64_LOCATOR.size:
        return None
    locator = _ZIP64_LOCATOR.unpack(locator_data)
    if locator[0] != zipfile.stringEndArchive64Locator:
        return None
    _, locator_disk, record_offset, total_disks = locator
    if locator_disk != 0 or total_disks != 1:
        raise OfflineZipError("Zip64 locator describes a forbidden multi-disk archive")
    if record_offset < 0 or record_offset + _ZIP64_EOCD.size > locator_offset:
        raise OfflineZipError("Zip64 locator points outside the archive end records")
    stream.seek(record_offset)
    record_data = stream.read(_ZIP64_EOCD.size)
    if len(record_data) != _ZIP64_EOCD.size:
        raise OfflineZipError("Zip64 end record is truncated")
    record = _ZIP64_EOCD.unpack(record_data)
    if record[0] != zipfile.stringEndArchive64:
        raise OfflineZipError("Zip64 locator does not point to a Zip64 end record")
    record_size = int(record[1])
    expected_record_size = zipfile.sizeEndCentDir64 - 12
    if record_size < expected_record_size:
        raise OfflineZipError("Zip64 end record is too short")
    if record_size > expected_record_size:
        raise OfflineZipError("Zip64 extensible data sector is forbidden")
    if int(record_offset) + 12 + record_size != locator_offset:
        raise OfflineZipError("Zip64 end record does not end at its locator")
    if record[4] != 0 or record[5] != 0 or record[6] != record[7]:
        raise OfflineZipError("Zip64 end record describes a forbidden multi-disk archive")
    if int(record[2]) != 45 or int(record[3]) != 45:
        raise OfflineZipError("Zip64 end record has non-deterministic version metadata")
    return _Zip64EndState(
        disk_entries=int(record[6]),
        total_entries=int(record[7]),
        central_size=int(record[8]),
        central_offset=int(record[9]),
        record_offset=int(record_offset),
    )


def _has_zip64_eocd(stream: BinaryIO) -> bool:
    return _read_zip64_eocd(stream) is not None


def _validate_zip64_layout(stream: BinaryIO, member_count: int) -> _Zip64EndState:
    _, classic, _ = _find_eocd(stream)
    zip64 = _read_zip64_eocd(stream)
    if zip64 is None:
        raise OfflineZipError("archive is missing the required Zip64 end record")
    if zip64.disk_entries != member_count or zip64.total_entries != member_count:
        raise OfflineZipError(
            f"Zip64 member count mismatch: expected {member_count}, "
            f"got disk={zip64.disk_entries}, total={zip64.total_entries}"
        )
    classic_disk_entries = int(classic[3])
    classic_total_entries = int(classic[4])
    classic_central_size = int(classic[5])
    classic_central_offset = int(classic[6])
    expected_classic_count = min(member_count, 0xFFFF)
    expected_classic_size = min(zip64.central_size, 0xFFFFFFFF)
    expected_classic_offset = min(zip64.central_offset, 0xFFFFFFFF)
    if classic_disk_entries != expected_classic_count:
        raise OfflineZipError("classic and Zip64 member counts disagree")
    if classic_total_entries != expected_classic_count:
        raise OfflineZipError("classic and Zip64 member counts disagree")
    if classic_central_size != expected_classic_size:
        raise OfflineZipError("classic and Zip64 central directory sizes disagree")
    if classic_central_offset != expected_classic_offset:
        raise OfflineZipError("classic and Zip64 central directory offsets disagree")
    if zip64.central_offset + zip64.central_size != zip64.record_offset:
        raise OfflineZipError("Zip64 central directory boundary does not meet the Zip64 end record")
    return zip64


def _force_zip64_eocd(stream: BinaryIO) -> None:
    if _has_zip64_eocd(stream):
        return
    eocd_offset, record, end_record = _find_eocd(stream)
    _, disk_number, central_disk, disk_entries, total_entries, central_size, central_offset, _ = record
    if disk_number != 0 or central_disk != 0 or disk_entries != total_entries:
        raise OfflineZipError("multi-disk ZIP archives are forbidden")
    zip64_end = _ZIP64_EOCD.pack(
        zipfile.stringEndArchive64,
        zipfile.sizeEndCentDir64 - 12,
        45,
        45,
        0,
        0,
        int(total_entries),
        int(total_entries),
        int(central_size),
        int(central_offset),
    )
    locator = _ZIP64_LOCATOR.pack(zipfile.stringEndArchive64Locator, 0, eocd_offset, 1)
    stream.seek(eocd_offset)
    stream.write(zip64_end)
    stream.write(locator)
    stream.write(end_record)
    stream.truncate()
    _sync_stream(stream)


def _file_sha256(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(COPY_CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest()


def _manifest_mapping(
    expected_entries: Mapping[str, ManifestEntry] | Sequence[ManifestEntry],
) -> dict[str, ManifestEntry]:
    if isinstance(expected_entries, Mapping):
        entries = list(expected_entries.values())
        for key, entry in expected_entries.items():
            if key != entry.path:
                raise OfflineZipError(
                    f"manifest mapping key does not match entry path: {key!r} != {entry.path!r}"
                )
    else:
        entries = list(expected_entries)
    _validate_entry_names(entries)
    return {entry.path: entry for entry in entries}


def _validate_fixed_metadata(info: zipfile.ZipInfo) -> None:
    if info.is_dir():
        raise OfflineZipError(f"explicit directory member is forbidden: {info.filename!r}")
    if info.date_time != FIXED_ZIP_TIME:
        raise OfflineZipError(f"member has a non-deterministic timestamp: {info.filename!r}")
    if info.compress_type != zipfile.ZIP_STORED:
        raise OfflineZipError(f"member is not ZIP_STORED: {info.filename!r}")
    if info.create_system != 3 or info.external_attr != FIXED_EXTERNAL_ATTR:
        raise OfflineZipError(f"member has non-deterministic platform metadata: {info.filename!r}")
    if info.comment:
        raise OfflineZipError(f"member comment is forbidden: {info.filename!r}")
    if (
        info.create_version != FIXED_CREATE_VERSION
        or info.extract_version != FIXED_EXTRACT_VERSION
        or info.flag_bits != FIXED_FLAG_BITS
        or info.internal_attr != FIXED_INTERNAL_ATTR
        or info.volume != 0
        or info.reserved != 0
    ):
        raise OfflineZipError(f"central directory metadata drift: {info.filename!r}")


def _read_exact_at(stream: BinaryIO, offset: int, size: int, label: str) -> bytes:
    if offset < 0:
        raise OfflineZipError(f"{label} has a negative offset")
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise OfflineZipError(f"{label} is truncated")
    return data


def _validate_central_record(
    stream: BinaryIO,
    offset: int,
    central_end: int,
    info: zipfile.ZipInfo,
) -> int:
    header_data = _read_exact_at(
        stream,
        offset,
        _CENTRAL_DIRECTORY_HEADER.size,
        "central directory header",
    )
    header = _CENTRAL_DIRECTORY_HEADER.unpack(header_data)
    if header[zipfile._CD_SIGNATURE] != zipfile.stringCentralDir:
        raise OfflineZipError(
            f"central directory signature mismatch: {info.filename!r}"
        )
    filename_length = int(header[zipfile._CD_FILENAME_LENGTH])
    extra_length = int(header[zipfile._CD_EXTRA_FIELD_LENGTH])
    comment_length = int(header[zipfile._CD_COMMENT_LENGTH])
    variable_size = filename_length + extra_length + comment_length
    record_end = offset + _CENTRAL_DIRECTORY_HEADER.size + variable_size
    if record_end > central_end:
        raise OfflineZipError(
            f"central directory record crosses its declared boundary: {info.filename!r}"
        )
    variable = _read_exact_at(
        stream,
        offset + _CENTRAL_DIRECTORY_HEADER.size,
        variable_size,
        "central directory fields",
    )
    filename = variable[:filename_length]
    extra_start = filename_length
    extra_end = extra_start + extra_length
    extra = variable[extra_start:extra_end]
    comment = variable[extra_end:]
    try:
        expected_filename = info.filename.encode("ascii")
    except UnicodeEncodeError as exc:
        raise OfflineZipError(
            f"central directory filename is not ASCII: {info.filename!r}"
        ) from exc
    if filename != expected_filename or comment != info.comment or extra != info.extra:
        raise OfflineZipError(
            f"central directory variable fields drifted: {info.filename!r}"
        )

    size_zip64 = (
        int(info.file_size) > zipfile.ZIP64_LIMIT
        or int(info.compress_size) > zipfile.ZIP64_LIMIT
    )
    offset_zip64 = int(info.header_offset) > zipfile.ZIP64_LIMIT
    expected_raw_file_size = 0xFFFFFFFF if size_zip64 else int(info.file_size)
    expected_raw_compress_size = 0xFFFFFFFF if size_zip64 else int(info.compress_size)
    expected_raw_offset = 0xFFFFFFFF if offset_zip64 else int(info.header_offset)
    if (
        int(header[zipfile._CD_UNCOMPRESSED_SIZE]) != expected_raw_file_size
        or int(header[zipfile._CD_COMPRESSED_SIZE]) != expected_raw_compress_size
    ):
        raise OfflineZipError(
            f"central directory ZIP64 size encoding is non-canonical: {info.filename!r}"
        )
    if int(header[zipfile._CD_LOCAL_HEADER_OFFSET]) != expected_raw_offset:
        raise OfflineZipError(
            f"central directory ZIP64 offset encoding is non-canonical: {info.filename!r}"
        )

    zip64_values: list[int] = []
    if size_zip64:
        zip64_values.extend((int(info.file_size), int(info.compress_size)))
    if offset_zip64:
        zip64_values.append(int(info.header_offset))
    expected_extra = b""
    if zip64_values:
        expected_extra = struct.pack(
            f"<HH{'Q' * len(zip64_values)}",
            1,
            8 * len(zip64_values),
            *zip64_values,
        )
    if extra != expected_extra:
        raise OfflineZipError(
            "central directory ZIP64 offset/size extra field is non-canonical: "
            f"{info.filename!r}"
        )
    return record_end


def _validate_local_header(stream: BinaryIO, info: zipfile.ZipInfo) -> int:
    header_data = _read_exact_at(
        stream, int(info.header_offset), _LOCAL_FILE_HEADER.size, "local file header"
    )
    header = _LOCAL_FILE_HEADER.unpack(header_data)
    if header[zipfile._FH_SIGNATURE] != zipfile.stringFileHeader:
        raise OfflineZipError(f"local file header signature mismatch: {info.filename!r}")
    filename_length = int(header[zipfile._FH_FILENAME_LENGTH])
    extra_length = int(header[zipfile._FH_EXTRA_FIELD_LENGTH])
    variable = _read_exact_at(
        stream,
        int(info.header_offset) + _LOCAL_FILE_HEADER.size,
        filename_length + extra_length,
        "local file header fields",
    )
    filename = variable[:filename_length]
    extra = variable[filename_length:]
    expected_filename = info.filename.encode("ascii")
    expected_extra = struct.pack(
        "<HHQQ", 1, 16, int(info.file_size), int(info.compress_size)
    )
    metadata_matches = (
        header[zipfile._FH_EXTRACT_VERSION] == FIXED_EXTRACT_VERSION
        and header[zipfile._FH_EXTRACT_SYSTEM] == 0
        and header[zipfile._FH_GENERAL_PURPOSE_FLAG_BITS] == FIXED_FLAG_BITS
        and header[zipfile._FH_COMPRESSION_METHOD] == zipfile.ZIP_STORED
        and header[zipfile._FH_LAST_MOD_TIME] == FIXED_LOCAL_DOS_TIME
        and header[zipfile._FH_LAST_MOD_DATE] == FIXED_LOCAL_DOS_DATE
        and header[zipfile._FH_CRC] == info.CRC
        and header[zipfile._FH_COMPRESSED_SIZE] == 0xFFFFFFFF
        and header[zipfile._FH_UNCOMPRESSED_SIZE] == 0xFFFFFFFF
        and filename == expected_filename
        and extra == expected_extra
    )
    if not metadata_matches:
        raise OfflineZipError(f"local header metadata drift: {info.filename!r}")
    return (
        int(info.header_offset)
        + _LOCAL_FILE_HEADER.size
        + len(expected_filename)
        + len(expected_extra)
        + int(info.compress_size)
    )


def _validate_production_counts(counts: Mapping[str, int], member_count: int) -> None:
    if member_count != PRODUCTION_MEMBER_COUNT:
        raise OfflineZipError(
            f"production archive must contain exactly {PRODUCTION_MEMBER_COUNT} members, got {member_count}"
        )
    for kind, expected in PRODUCTION_HASHED_COUNTS.items():
        actual = counts.get(kind, 0)
        if actual != expected:
            raise OfflineZipError(
                f"production {kind} member count mismatch: expected {expected}, got {actual}"
            )
    markers = counts.get("markers", 0)
    if markers != PRODUCTION_MARKER_COUNT:
        raise OfflineZipError(
            f"production marker count mismatch: expected {PRODUCTION_MARKER_COUNT}, got {markers}"
        )


def _entry_counts(entries: Sequence[ManifestEntry]) -> dict[str, int]:
    counts = {"common": 0, "medium": 0, "android": 0, "markers": 0}
    for entry in entries:
        counts[_classify_path(entry.path)] += 1
    return counts


def _validate_build_contract(entries: Sequence[ManifestEntry], production: bool) -> None:
    if type(production) is not bool:
        raise OfflineZipError("production must be a boolean")
    if production:
        _validate_production_counts(_entry_counts(entries), len(entries))


def write_data_zip(
    staged_worldflipper: Path,
    output: Path,
    entries: Sequence[ManifestEntry],
    *,
    production: bool = True,
) -> ZipBuildReport:
    staged_worldflipper = Path(staged_worldflipper)
    output = Path(output)
    input_entries = tuple(entries)
    _validate_entry_names(input_entries)
    ordered_entries = tuple(sorted(input_entries, key=lambda item: item.path))
    _validate_build_contract(ordered_entries, production)
    if staged_worldflipper.name != "WorldFlipper":
        raise OfflineZipError("staged root basename must be exactly WorldFlipper")
    try:
        staged_metadata = os.lstat(staged_worldflipper)
    except OSError as exc:
        raise OfflineZipError(f"cannot inspect staged WorldFlipper root: {exc}") from exc
    if _is_reparse(staged_metadata) or not stat.S_ISDIR(staged_metadata.st_mode):
        raise OfflineZipError("staged WorldFlipper root must be a real directory")
    stream: BinaryIO | None = None
    created_identity: _FileIdentity | None = None
    complete = False
    try:
        stream, created_identity = _open_exclusive_archive(output)
        with stream:
            with zipfile.ZipFile(stream, "w", allowZip64=True) as archive:
                archive.comment = b""
                for entry in ordered_entries:
                    with archive.open(_zip_info(entry.path), "w", force_zip64=True) as destination:
                        _copy_and_verify(
                            staged_worldflipper.parent / entry.path, destination, entry
                        )
            _sync_stream(stream)
            _force_zip64_eocd(stream)
            report = _verify_data_zip_stream(
                stream,
                os.fspath(output),
                {entry.path: entry for entry in ordered_entries},
                expected_members=len(ordered_entries),
                production=production,
            )
            _require_path_identity(output, created_identity)
            complete = True
            return report
    except FileExistsError:
        raise
    except OfflineZipError:
        raise
    except (OSError, EOFError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise OfflineZipError(f"cannot build data ZIP {os.fspath(output)!r}: {exc}") from exc
    finally:
        if not complete and created_identity is not None:
            _cleanup_owned_output(output, created_identity)


def _verify_data_zip_stream(
    stream: BinaryIO,
    archive_label: str,
    expected_entries: Mapping[str, ManifestEntry] | Sequence[ManifestEntry],
    *,
    expected_members: int | None = None,
    production: bool = True,
) -> ZipVerificationReport:
    expected = _manifest_mapping(expected_entries)
    if expected_members is not None and (
        type(expected_members) is not int or expected_members < 0
    ):
        raise OfflineZipError("expected_members must be a non-negative integer")
    _validate_build_contract(tuple(expected.values()), production)
    if production:
        if expected_members is not None and expected_members != PRODUCTION_MEMBER_COUNT:
            raise OfflineZipError(
                f"production expected_members must be {PRODUCTION_MEMBER_COUNT}, got {expected_members}"
            )
        expected_members = PRODUCTION_MEMBER_COUNT
    elif expected_members is None:
        expected_members = len(expected)

    counts = {"common": 0, "medium": 0, "android": 0, "markers": 0}
    total_uncompressed_bytes = 0
    physical_payload_end = 0
    zip64_state: _Zip64EndState | None = None
    try:
        stream.seek(0)
        try:
            opened_archive = zipfile.ZipFile(stream, "r", allowZip64=True)
        except (OSError, EOFError, zipfile.BadZipFile):
            # pre-3.12 zipfile rejects some malformed end records with its own
            # error; surface the canonical raw-layout rejection when there is one.
            stream.seek(0)
            _validate_zip64_layout(stream, len(expected))
            raise
        with opened_archive as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _validate_paths(names)
            if names != sorted(names):
                raise OfflineZipError("archive member names must be sorted")
            if len(infos) != expected_members:
                raise OfflineZipError(
                    f"archive member count mismatch: expected {expected_members}, got {len(infos)}"
                )
            if set(names) != set(expected):
                missing = sorted(set(expected) - set(names))
                unexpected = sorted(set(names) - set(expected))
                raise OfflineZipError(
                    f"archive/manifest member set mismatch: missing={missing[:3]!r}, "
                    f"unexpected={unexpected[:3]!r}"
                )
            zip64_state = _validate_zip64_layout(stream, len(expected))
            if int(archive.start_dir) != zip64_state.central_offset:
                raise OfflineZipError("ZIP reader and Zip64 central directory offsets disagree")
            central_position = zip64_state.central_offset
            central_end = zip64_state.central_offset + zip64_state.central_size
            for info in infos:
                central_position = _validate_central_record(
                    stream,
                    central_position,
                    central_end,
                    info,
                )
                _validate_fixed_metadata(info)
                if int(info.header_offset) != physical_payload_end:
                    raise OfflineZipError(
                        f"physical local records are not canonical and contiguous: {info.filename!r}"
                    )
                physical_payload_end = _validate_local_header(stream, info)
            if central_position != central_end:
                raise OfflineZipError(
                    "central directory records do not fill their declared boundary"
                )
            if archive.comment:
                raise OfflineZipError("archive comment is forbidden")

            for info in infos:
                entry = expected[info.filename]
                if info.file_size != entry.size:
                    raise OfflineZipError(
                        f"archive member size mismatch for {info.filename!r}: "
                        f"expected {entry.size}, got {info.file_size}"
                    )
                digest = hashlib.sha256()
                size = 0
                marker_payload = (
                    bytearray() if info.filename in (INFO_PATH, EMPTY_PATH) else None
                )
                try:
                    with archive.open(info, "r") as member:
                        while chunk := member.read(COPY_CHUNK_SIZE):
                            digest.update(chunk)
                            size += len(chunk)
                            if marker_payload is not None:
                                marker_payload.extend(chunk)
                except (OSError, EOFError, zipfile.BadZipFile) as exc:
                    raise OfflineZipError(
                        f"archive member SHA-256 verification failed for {info.filename!r}: {exc}"
                    ) from exc
                if size != entry.size:
                    raise OfflineZipError(
                        f"archive member size mismatch for {info.filename!r}: expected {entry.size}, got {size}"
                    )
                actual_sha256 = digest.hexdigest()
                if actual_sha256 != entry.sha256:
                    raise OfflineZipError(
                        f"archive member SHA-256 mismatch for {info.filename!r}: "
                        f"expected {entry.sha256}, got {actual_sha256}"
                    )
                if info.filename == EMPTY_PATH and (size != 1 or actual_sha256 != _EMPTY_SHA256):
                    raise OfflineZipError(".empty must be exactly one ASCII byte '0'")
                if marker_payload is not None:
                    _validate_marker_payload(info.filename, bytes(marker_payload))
                counts[_classify_path(info.filename)] += 1
                total_uncompressed_bytes += size
    except OfflineZipError:
        raise
    except (OSError, EOFError, zipfile.BadZipFile) as exc:
        raise OfflineZipError(f"cannot read data ZIP {archive_label!r}: {exc}") from exc

    if zip64_state is None:
        raise OfflineZipError("archive Zip64 layout was not validated")
    if physical_payload_end != zip64_state.central_offset:
        raise OfflineZipError(
            "physical local records do not end exactly at the central directory"
        )
    zip64 = True
    if production:
        _validate_production_counts(counts, len(expected))
    return ZipVerificationReport(
        archive_sha256=_file_sha256(stream),
        member_count=len(expected),
        counts=MappingProxyType(dict(counts)),
        total_uncompressed_bytes=total_uncompressed_bytes,
        zip64=zip64,
    )


def verify_data_zip(
    archive_path: Path,
    expected_entries: Mapping[str, ManifestEntry] | Sequence[ManifestEntry],
    *,
    expected_members: int | None = None,
    production: bool = True,
) -> ZipVerificationReport:
    archive_path = Path(archive_path)
    try:
        stream, identity = _open_existing_archive(archive_path)
        with stream:
            report = _verify_data_zip_stream(
                stream,
                os.fspath(archive_path),
                expected_entries,
                expected_members=expected_members,
                production=production,
            )
            _require_path_identity(archive_path, identity)
            return report
    except OfflineZipError:
        raise
    except (OSError, EOFError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise OfflineZipError(
            f"cannot read data ZIP {os.fspath(archive_path)!r}: {exc}"
        ) from exc
