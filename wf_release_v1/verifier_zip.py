"""Private raw classic-STORE ZIP reader for the independent verifier."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import struct
from typing import BinaryIO, Final, Iterator
import unicodedata
import zlib

from .canonical import normalize_relative_path
from .errors import ReleaseError


ROOT: Final = "wf-release-v1/"
RELEASE_MEMBER: Final = ROOT + "release-manifest.json"
FIXED_MODE: Final = stat.S_IFREG | 0o644
MAX_MEMBER_BYTES: Final = 0xFFFFFFFE
MAX_TOTAL_BYTES: Final = 0xFFFFFFFE
MAX_MEMBERS: Final = 0xFFFE
MAX_CENTRAL_BYTES: Final = 256 * 1024 * 1024
_REPARSE_POINT: Final = 0x0400
_WINDOWS_FORBIDDEN: Final = frozenset('<>:"\\|?*')
_WINDOWS_DEVICES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
    | {f"COM{index}" for index in "¹²³"}
    | {f"LPT{index}" for index in "¹²³"}
)


@dataclass(frozen=True)
class ZipMember:
    name: str
    data_offset: int
    size: int
    crc32: int


def _error(message: str) -> ReleaseError:
    return ReleaseError("WFREL_ARCHIVE_INVALID", message, {"label": "archive"})


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


@contextmanager
def open_release(path: Path) -> Iterator[tuple[BinaryIO, int]]:
    """Yield one identity-bound release descriptor and verify it again on exit."""
    descriptor = -1
    stream: BinaryIO | None = None
    try:
        before_stat = os.lstat(path)
        if (
            _is_reparse(before_stat)
            or not stat.S_ISREG(before_stat.st_mode)
            or before_stat.st_size <= 0
        ):
            raise OSError("unsafe release archive")
        before = _identity(before_stat)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _identity(opened) != before or _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise OSError("archive identity changed before open")
        stream = os.fdopen(descriptor, "rb", closefd=True)
        descriptor = -1
        yield stream, before[2]
        if _identity(os.fstat(stream.fileno())) != before:
            raise OSError("opened archive changed while reading")
        after = os.lstat(path)
        if _identity(after) != before or _is_reparse(after):
            raise OSError("archive path changed while reading")
    except ReleaseError:
        raise
    except OSError as error:
        raise _error("release archive is unavailable or changed while being read") from error
    finally:
        if stream is not None:
            stream.close()
        elif descriptor >= 0:
            os.close(descriptor)


def _read_at(stream: BinaryIO, offset: int, size: int, archive_size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > archive_size:
        raise ValueError("archive structure is truncated")
    stream.seek(offset)
    raw = stream.read(size)
    if len(raw) != size:
        raise ValueError("archive structure is truncated")
    return raw


def _portable_name(raw_name: bytes) -> str:
    name = raw_name.decode("utf-8", errors="strict")
    if unicodedata.normalize("NFC", name) != name or name.endswith("/") or not name.startswith(ROOT):
        raise ValueError("archive member name is not canonical")
    relative = name.removeprefix(ROOT)
    normalize_relative_path(relative)
    parts = PurePosixPath(relative).parts
    if any(
        part.endswith((" ", "."))
        or part.split(".", 1)[0].upper() in _WINDOWS_DEVICES
        or any(character in _WINDOWS_FORBIDDEN for character in part)
        for part in parts
    ):
        raise ValueError("archive member name is not portable")
    first = parts[0]
    if first not in {
        "release-manifest.json", "requires.json", "ownership.json",
        "content", "server", "modes",
    }:
        raise ValueError("archive has an unknown top-level member")
    return name


def parse_classic_store(stream: BinaryIO, archive_size: int) -> tuple[ZipMember, ...]:
    """Parse exact classic ZIP records without zipfile's path normalization."""
    try:
        if archive_size < 22:
            raise ValueError("archive is truncated")
        eocd_at = archive_size - 22
        eocd = struct.unpack(
            "<IHHHHIIH", _read_at(stream, eocd_at, 22, archive_size)
        )
        signature, disk, central_disk, disk_count, count, central_size, central_at, comment = eocd
        if (
            signature != 0x06054B50
            or disk != 0 or central_disk != 0 or disk_count != count
            or count == 0 or count == 0xFFFF or count > MAX_MEMBERS
            or central_size == 0 or central_size > MAX_CENTRAL_BYTES
            or central_size == 0xFFFFFFFF or central_at == 0xFFFFFFFF
            or comment != 0 or central_at + central_size != eocd_at
            or (eocd_at >= 20 and _read_at(stream, eocd_at - 20, 4, archive_size) == b"PK\x06\x07")
        ):
            raise ValueError("classic ZIP end record is invalid")
        cursor = central_at
        expected_local = 0
        total = 0
        members: list[ZipMember] = []
        seen_exact: set[str] = set()
        seen_portable: set[str] = set()
        for _ in range(count):
            central = struct.unpack(
                "<IHHHHHHIIIHHHHHII",
                _read_at(stream, cursor, 46, archive_size),
            )
            (
                central_signature, made_by, extract, flags, method, dos_time, dos_date,
                crc, compressed, uncompressed, name_length, extra_length, comment_length,
                disk_start, internal_attr, external_attr, local_at,
            ) = central
            raw_name = _read_at(stream, cursor + 46, name_length, archive_size)
            local = struct.unpack(
                "<IHHHHHIIIHH",
                _read_at(stream, local_at, 30, archive_size),
            )
            (
                local_signature, local_extract, local_flags, local_method, local_time,
                local_date, local_crc, local_compressed, local_uncompressed,
                local_name_length, local_extra_length,
            ) = local
            local_name = _read_at(stream, local_at + 30, local_name_length, archive_size)
            if (
                central_signature != 0x02014B50 or local_signature != 0x04034B50
                or made_by != 0x314 or extract != 20 or local_extract != extract
                or flags != 0x800 or local_flags != flags
                or method != 0 or local_method != method
                or dos_time != 0 or local_time != dos_time
                or dos_date != 33 or local_date != dos_date
                or crc != local_crc or compressed != uncompressed
                or local_compressed != compressed or local_uncompressed != uncompressed
                or raw_name != local_name or extra_length != 0 or local_extra_length != 0
                or comment_length != 0 or disk_start != 0 or internal_attr != 0
                or external_attr != FIXED_MODE << 16 or local_at == 0xFFFFFFFF
            ):
                raise ValueError("local and central ZIP headers are not canonical")
            if uncompressed > MAX_MEMBER_BYTES:
                raise ValueError("archive member exceeds the size limit")
            total += uncompressed
            if total > MAX_TOTAL_BYTES:
                raise ValueError("archive payload exceeds the total size limit")
            name = _portable_name(raw_name)
            portable = unicodedata.normalize("NFC", name).casefold()
            if name in seen_exact or portable in seen_portable:
                raise ValueError("archive member name is duplicated or conflicts portably")
            seen_exact.add(name)
            seen_portable.add(portable)
            data_at = local_at + 30 + local_name_length
            local_end = data_at + compressed
            if local_at != expected_local or local_end > central_at:
                raise ValueError("local ZIP members are not contiguous")
            members.append(ZipMember(name, data_at, uncompressed, crc))
            expected_local = local_end
            cursor += 46 + name_length
        if cursor != central_at + central_size or expected_local != central_at:
            raise ValueError("ZIP local and central regions are not exact")
        names = [item.name for item in members]
        if names[-1:] != [RELEASE_MEMBER] or names[:-1] != sorted(
            names[:-1], key=lambda item: item.encode("utf-8")
        ):
            raise ValueError("archive member order is not canonical")
        return tuple(members)
    except (ValueError, UnicodeError, struct.error, ReleaseError) as error:
        raise _error("release ZIP structure is invalid") from error


def read_member(stream: BinaryIO, member: ZipMember, *, limit: int) -> bytes:
    if member.size > limit:
        raise ReleaseError(
            "WFREL_ARCHIVE_LIMIT", "release member exceeds the read limit", {"label": "metadata"}
        )
    stream.seek(member.data_offset)
    raw = stream.read(member.size)
    if len(raw) != member.size or zlib.crc32(raw) & 0xFFFFFFFF != member.crc32:
        raise _error("release member payload is corrupt")
    return raw


def copy_hash_member(stream: BinaryIO, member: ZipMember, destination: BinaryIO | None = None) -> str:
    digest = hashlib.sha256()
    checksum = 0
    remaining = member.size
    stream.seek(member.data_offset)
    while remaining:
        chunk = stream.read(min(1024 * 1024, remaining))
        if not chunk:
            raise _error("release member payload is truncated")
        digest.update(chunk)
        checksum = zlib.crc32(chunk, checksum)
        if destination is not None:
            destination.write(chunk)
        remaining -= len(chunk)
    if checksum & 0xFFFFFFFF != member.crc32:
        raise _error("release member CRC is invalid")
    return digest.hexdigest()
