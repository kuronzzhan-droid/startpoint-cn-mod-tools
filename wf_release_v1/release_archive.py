"""Private classic STORE ZIP sealing and no-clobber publication."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import stat
import struct
import sys
from typing import BinaryIO, Final
import zipfile

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .errors import ReleaseError
from .schema import (
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)


FIXED_TIME: Final = (1980, 1, 1, 0, 0, 0)
FIXED_MODE: Final = stat.S_IFREG | 0o644
_ROOT: Final = "wf-release-v1"
_REPARSE_POINT: Final = 0x0400
_UINT16_MAX: Final = (1 << 16) - 1
_UINT32_MAX: Final = (1 << 32) - 1
_UTF8_FLAG: Final = 0x800
_DOS_TIME: Final = 0
_DOS_DATE: Final = 33


@dataclass(frozen=True)
class ParentState:
    components: tuple[tuple[Path, tuple[int, int]], ...]


@dataclass(frozen=True)
class ArchiveReadback:
    release_id: str
    archive_sha256: str
    file_count: int
    archive_identity: tuple[int, int, int, int]


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def capture_parent(parent: Path) -> ParentState:
    absolute = Path(os.path.abspath(os.fspath(parent)))
    current = Path(absolute.anchor)
    paths = [current]
    for part in absolute.parts[1:]:
        current /= part
        paths.append(current)
    components: list[tuple[Path, tuple[int, int]]] = []
    try:
        for item in paths:
            metadata = os.lstat(item)
            if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise OSError("unsafe parent component")
            components.append((item, (metadata.st_dev, metadata.st_ino)))
    except OSError as error:
        raise _error(
            "WFREL_BUILD_OUTPUT_INVALID",
            "output parent chain is unavailable or unsafe",
            label="output",
        ) from error
    return ParentState(tuple(components))


def verify_parent(state: ParentState) -> None:
    try:
        for path, expected in state.components:
            metadata = os.lstat(path)
            if (
                (metadata.st_dev, metadata.st_ino) != expected
                or _is_reparse(metadata)
                or not stat.S_ISDIR(metadata.st_mode)
            ):
                raise OSError("parent identity changed")
    except OSError as error:
        raise _error(
            "WFREL_BUILD_OUTPUT_CHANGED",
            "output parent chain changed during build",
            label="output",
        ) from error


def _copy_stream(reader: BinaryIO, writer: BinaryIO) -> None:
    while chunk := reader.read(1024 * 1024):
        writer.write(chunk)


def write_archive(
    stream: BinaryIO,
    members: tuple[tuple[str, BinaryIO, int], ...],
) -> None:
    if not members or len(members) >= _UINT16_MAX:
        raise _error("WFREL_BUILD_LIMIT", "classic ZIP member limit exceeded", label="archive")
    try:
        with zipfile.ZipFile(stream, "w", allowZip64=False) as bundle:
            bundle.comment = b""
            for name, source, expected_size in members:
                if expected_size > _UINT32_MAX:
                    raise zipfile.LargeZipFile("classic member limit")
                source.seek(0, os.SEEK_END)
                if source.tell() != expected_size:
                    raise OSError("staged member size changed")
                source.seek(0)
                info = zipfile.ZipInfo(name, FIXED_TIME)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = FIXED_MODE << 16
                info.extra = b""
                with bundle.open(info, "w", force_zip64=False) as writer:
                    _copy_stream(source, writer)
    except (OSError, zipfile.LargeZipFile) as error:
        raise _error(
            "WFREL_BUILD_LIMIT",
            "classic STORE ZIP could not be created",
            label="archive",
        ) from error


def force_utf8_flags(stream: BinaryIO) -> None:
    """Set the UTF-8 bit in both copies of every classic ZIP header."""
    stream.flush()
    with zipfile.ZipFile(stream, "r") as bundle:
        infos = bundle.infolist()
        central = bundle.start_dir
    for info in infos:
        stream.seek(info.header_offset)
        if stream.read(4) != b"PK\x03\x04":
            raise _error("WFREL_ARCHIVE_INVALID", "local ZIP header is invalid", label="archive")
        stream.seek(info.header_offset + 6)
        flags = struct.unpack("<H", stream.read(2))[0] | _UTF8_FLAG
        stream.seek(info.header_offset + 6)
        stream.write(struct.pack("<H", flags))
    cursor = central
    for _ in infos:
        stream.seek(cursor)
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise _error("WFREL_ARCHIVE_INVALID", "central ZIP header is invalid", label="archive")
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", header, 28)
        flags = struct.unpack_from("<H", header, 8)[0] | _UTF8_FLAG
        stream.seek(cursor + 8)
        stream.write(struct.pack("<H", flags))
        cursor += 46 + name_length + extra_length + comment_length
    stream.flush()
    os.fsync(stream.fileno())


def _read_exact_at(stream: BinaryIO, offset: int, size: int) -> bytes:
    stream.seek(offset)
    raw = stream.read(size)
    if len(raw) != size:
        raise ValueError("archive structure is truncated")
    return raw


def _raw_header_check(stream: BinaryIO, infos: list[zipfile.ZipInfo], size: int) -> None:
    if size < 22:
        raise ValueError("archive is truncated")
    eocd = struct.unpack("<IHHHHIIH", _read_exact_at(stream, size - 22, 22))
    signature, disk, central_disk, disk_count, count, central_size, central_at, comment = eocd
    if (
        signature != 0x06054B50
        or disk != 0
        or central_disk != 0
        or disk_count != count
        or count != len(infos)
        or count == _UINT16_MAX
        or central_size == _UINT32_MAX
        or central_at == _UINT32_MAX
        or comment != 0
        or central_at + central_size != size - 22
    ):
        raise ValueError("classic ZIP end record is invalid")
    cursor = central_at
    expected_local_at = 0
    for info in infos:
        central = struct.unpack(
            "<IHHHHHHIIIHHHHHII", _read_exact_at(stream, cursor, 46)
        )
        (
            central_signature,
            made_by,
            extract,
            flags,
            method,
            dos_time,
            dos_date,
            crc,
            compressed,
            uncompressed,
            name_length,
            extra_length,
            comment_length,
            disk_start,
            internal_attr,
            external_attr,
            local_at,
        ) = central
        raw_name = _read_exact_at(stream, cursor + 46, name_length)
        local = struct.unpack("<IHHHHHIIIHH", _read_exact_at(stream, local_at, 30))
        (
            local_signature,
            local_extract,
            local_flags,
            local_method,
            local_time,
            local_date,
            local_crc,
            local_compressed,
            local_uncompressed,
            local_name_length,
            local_extra_length,
        ) = local
        local_name = _read_exact_at(stream, local_at + 30, local_name_length)
        expected_name = info.filename.encode("utf-8")
        if (
            central_signature != 0x02014B50
            or local_signature != 0x04034B50
            or made_by != (3 << 8) | 20
            or extract != 20
            or local_extract != extract
            or flags != _UTF8_FLAG
            or local_flags != flags
            or method != zipfile.ZIP_STORED
            or local_method != method
            or dos_time != _DOS_TIME
            or local_time != dos_time
            or dos_date != _DOS_DATE
            or local_date != dos_date
            or crc != info.CRC
            or local_crc != crc
            or compressed != info.compress_size
            or uncompressed != info.file_size
            or local_compressed != compressed
            or local_uncompressed != uncompressed
            or raw_name != expected_name
            or local_name != raw_name
            or extra_length != 0
            or local_extra_length != 0
            or comment_length != 0
            or disk_start != 0
            or internal_attr != 0
            or external_attr != FIXED_MODE << 16
            or local_at == _UINT32_MAX
        ):
            raise ValueError("local and central ZIP headers disagree")
        if raw_name.decode("utf-8", errors="strict") != info.filename:
            raise ValueError("ZIP member name is not exact UTF-8")
        local_end = local_at + 30 + local_name_length + local_extra_length + compressed
        if local_at != expected_local_at or local_end > central_at:
            raise ValueError("local ZIP members are not contiguous in central order")
        expected_local_at = local_end
        cursor += 46 + name_length
    if cursor != central_at + central_size or expected_local_at != central_at:
        raise ValueError("ZIP local and central regions are not exact")


def _hash_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    stream.seek(0)
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def readback_archive(stream: BinaryIO) -> ArchiveReadback:
    try:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or _is_reparse(before):
            raise ValueError("archive handle is not regular")
        with zipfile.ZipFile(stream, "r", allowZip64=False) as bundle:
            infos = bundle.infolist()
            names = [info.filename for info in infos]
            if (
                not infos
                or names[:-1] != sorted(names[:-1], key=lambda item: item.encode("utf-8"))
                or names[-1] != f"{_ROOT}/release-manifest.json"
                or len(names) != len(set(names))
                or bundle.comment
            ):
                raise ValueError("member order or set is not canonical")
            _raw_header_check(stream, infos, before.st_size)
            release_raw = bundle.read(f"{_ROOT}/release-manifest.json")
            requires_raw = bundle.read(f"{_ROOT}/requires.json")
            ownership_raw = bundle.read(f"{_ROOT}/ownership.json")
            release = parse_release_manifest(
                load_json_strict_bytes(release_raw, label="release-manifest.json")
            )
            requirements = parse_requirements(
                load_json_strict_bytes(requires_raw, label="requires.json")
            )
            ownership = parse_ownership(
                load_json_strict_bytes(ownership_raw, label="ownership.json")
            )
            verify_release_id(release)
            if (
                release_raw != canonical_json_bytes(release.to_wire())
                or requires_raw != canonical_json_bytes(requirements.to_wire())
                or ownership_raw != canonical_json_bytes(ownership.to_wire())
                or hashlib.sha256(requires_raw).hexdigest()
                != release.metadata_sha256.requires
                or hashlib.sha256(ownership_raw).hexdigest()
                != release.metadata_sha256.ownership
            ):
                raise ValueError("metadata bytes are not canonically bound")
            metadata = {
                f"{_ROOT}/release-manifest.json",
                f"{_ROOT}/requires.json",
                f"{_ROOT}/ownership.json",
            }
            payload = {f"{_ROOT}/{item.path}" for item in release.files}
            if set(names) != metadata | payload:
                raise ValueError("member set does not match the manifest")
            for item in release.files:
                raw = bundle.read(f"{_ROOT}/{item.path}")
                if len(raw) != item.size or hashlib.sha256(raw).hexdigest() != item.sha256:
                    raise ValueError("payload digest mismatch")
        archive_sha256 = _hash_stream(stream)
        after = os.fstat(stream.fileno())
        if _identity(after) != _identity(before):
            raise ValueError("archive identity changed during readback")
    except (
        OSError,
        ValueError,
        KeyError,
        UnicodeError,
        struct.error,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        ReleaseError,
    ) as error:
        if isinstance(error, ReleaseError) and error.code == "WFREL_ARCHIVE_INVALID":
            raise
        raise _error(
            "WFREL_ARCHIVE_INVALID",
            "independent archive readback failed",
            label="archive",
        ) from error
    return ArchiveReadback(
        release.release_id,
        archive_sha256,
        len(release.files),
        _identity(after),
    )


def reopen_for_readback(staging: BinaryIO) -> ArchiveReadback:
    try:
        staging.flush()
        os.fsync(staging.fileno())
        with os.fdopen(os.dup(staging.fileno()), "rb", closefd=True) as reader:
            return readback_archive(reader)
    except OSError as error:
        raise _error(
            "WFREL_ARCHIVE_INVALID",
            "temporary archive could not be reopened",
            label="archive",
        ) from error


def _posix_link_handle(staging: BinaryIO, output: Path, parent: ParentState) -> None:
    if not sys.platform.startswith("linux"):
        raise OSError("descriptor publication is supported only on Linux")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    parent_descriptor = os.open(output.parent, flags)
    try:
        metadata = os.fstat(parent_descriptor)
        if (metadata.st_dev, metadata.st_ino) != parent.components[-1][1]:
            raise OSError("output parent identity changed")
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            linkat = libc.linkat
        except AttributeError as error:
            raise OSError("descriptor publication is unavailable") from error
        linkat.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        )
        linkat.restype = ctypes.c_int
        ctypes.set_errno(0)
        if linkat(
            staging.fileno(),
            b"",
            parent_descriptor,
            os.fsencode(output.name),
            0x1000,
        ) == 0:
            return
        error = ctypes.get_errno()
        if error != errno.EPERM:
            raise OSError(error, "linkat failed")
        ctypes.set_errno(0)
        if linkat(
            -100,
            os.fsencode(f"/proc/self/fd/{staging.fileno()}"),
            parent_descriptor,
            os.fsencode(output.name),
            0x400,
        ) != 0:
            raise OSError(ctypes.get_errno(), "procfd linkat failed")
    finally:
        try:
            os.close(parent_descriptor)
        except OSError:
            # The hard-link syscall is the commit point. A later directory-fd
            # close failure cannot safely turn the committed output into failure.
            pass


def publish_new(
    staging: BinaryIO,
    staging_path: Path | None,
    output: Path,
    parent: ParentState,
    readback: ArchiveReadback,
) -> None:
    try:
        before = os.fstat(staging.fileno())
        if (
            _identity(before) != readback.archive_identity
            or _hash_stream(staging) != readback.archive_sha256
        ):
            raise OSError("readback archive changed before publish")
        if os.name == "nt":
            if (
                staging_path is None
                or _identity(os.lstat(staging_path)) != readback.archive_identity
            ):
                raise OSError("staging path is not the readback archive")
            verify_parent(parent)
            os.link(staging_path, output)
        else:
            _posix_link_handle(staging, output, parent)
    except (OSError, ReleaseError) as error:
        raise _error(
            "WFREL_BUILD_OUTPUT_CHANGED",
            "output could not be published as the readback archive",
            label="output",
        ) from error
