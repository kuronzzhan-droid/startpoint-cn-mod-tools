"""Private classic STORE ZIP sealing and no-clobber publication."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import struct
import secrets
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


@dataclass(frozen=True)
class ParentState:
    components: tuple[tuple[Path, tuple[int, int]], ...]


@dataclass(frozen=True)
class ArchiveReadback:
    release_id: str
    archive_sha256: str
    file_count: int


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


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


def write_archive(stream: BinaryIO, members: tuple[tuple[str, Path], ...]) -> None:
    if not members or len(members) >= _UINT16_MAX:
        raise _error("WFREL_BUILD_LIMIT", "classic ZIP member limit exceeded", label="archive")
    try:
        with zipfile.ZipFile(stream, "w", allowZip64=False) as bundle:
            bundle.comment = b""
            for name, path in members:
                size = path.stat().st_size
                if size > _UINT32_MAX:
                    raise zipfile.LargeZipFile("classic member limit")
                info = zipfile.ZipInfo(name, FIXED_TIME)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = FIXED_MODE << 16
                info.extra = b""
                with path.open("rb") as reader, bundle.open(
                    info, "w", force_zip64=False
                ) as writer:
                    _copy_stream(reader, writer)
    except (OSError, zipfile.LargeZipFile) as error:
        raise _error(
            "WFREL_BUILD_LIMIT",
            "classic STORE ZIP could not be created",
            label="archive",
        ) from error


def force_utf8_flags(stream: BinaryIO) -> None:
    """Set the UTF-8 bit for ASCII names in both classic ZIP headers."""
    stream.flush()
    with zipfile.ZipFile(stream, "r") as bundle:
        infos = bundle.infolist()
        central = bundle.start_dir
    for info in infos:
        stream.seek(info.header_offset)
        if stream.read(4) != b"PK\x03\x04":
            raise _error("WFREL_ARCHIVE_INVALID", "local ZIP header is invalid", label="archive")
        stream.seek(info.header_offset + 6)
        flags = struct.unpack("<H", stream.read(2))[0] | 0x800
        stream.seek(info.header_offset + 6)
        stream.write(struct.pack("<H", flags))
    cursor = central
    for _ in infos:
        stream.seek(cursor)
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise _error("WFREL_ARCHIVE_INVALID", "central ZIP header is invalid", label="archive")
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", header, 28)
        flags = struct.unpack_from("<H", header, 8)[0] | 0x800
        stream.seek(cursor + 8)
        stream.write(struct.pack("<H", flags))
        cursor += 46 + name_length + extra_length + comment_length
    stream.flush()
    os.fsync(stream.fileno())


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def readback_archive(path: Path) -> ArchiveReadback:
    try:
        with zipfile.ZipFile(path, "r", allowZip64=False) as bundle:
            infos = bundle.infolist()
            names = [info.filename for info in infos]
            if (
                not infos
                or names != sorted(names, key=lambda item: item.encode("utf-8"))
                or len(names) != len(set(names))
                or bundle.comment
            ):
                raise ValueError("member set is not canonical")
            for info in infos:
                if (
                    info.date_time != FIXED_TIME
                    or info.compress_type != zipfile.ZIP_STORED
                    or info.create_system != 3
                    or info.external_attr >> 16 != FIXED_MODE
                    or info.extra
                    or not info.flag_bits & 0x800
                    or info.is_dir()
                    or info.file_size != info.compress_size
                ):
                    raise ValueError("member metadata is not canonical")
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
                requires_raw != canonical_json_bytes(requirements.to_wire())
                or ownership_raw != canonical_json_bytes(ownership.to_wire())
                or hashlib.sha256(requires_raw).hexdigest()
                != release.metadata_sha256.requires
                or hashlib.sha256(ownership_raw).hexdigest()
                != release.metadata_sha256.ownership
            ):
                raise ValueError("metadata bytes are not bound")
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
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, zipfile.LargeZipFile, ReleaseError) as error:
        if isinstance(error, ReleaseError) and error.code == "WFREL_ARCHIVE_INVALID":
            raise
        raise _error(
            "WFREL_ARCHIVE_INVALID",
            "independent archive readback failed",
            label="archive",
        ) from error
    return ArchiveReadback(release.release_id, _sha256_path(path), len(release.files))


def reopen_for_readback(staging: Path, parent: Path) -> ArchiveReadback:
    path = parent / f".wfrel-readback-{secrets.token_hex(16)}.zip"
    try:
        os.link(staging, path)
        return readback_archive(path)
    except OSError as error:
        raise _error(
            "WFREL_ARCHIVE_INVALID",
            "temporary archive could not be reopened",
            label="archive",
        ) from error
    finally:
        try:
            if path.exists() and os.path.samefile(staging, path):
                path.unlink()
        except OSError:
            pass


def publish_new(staging: Path, output: Path, parent: ParentState) -> None:
    verify_parent(parent)
    try:
        os.link(staging, output)
    except OSError as error:
        raise _error(
            "WFREL_BUILD_OUTPUT_EXISTS",
            "output could not be published without replacement",
            label="output",
        ) from error
    try:
        verify_parent(parent)
        if not os.path.samefile(staging, output):
            raise OSError("published identity changed")
    except (OSError, ReleaseError) as error:
        try:
            if output.exists() and os.path.samefile(staging, output):
                output.unlink()
        except OSError:
            pass
        raise _error(
            "WFREL_BUILD_OUTPUT_CHANGED",
            "published output identity could not be confirmed",
            label="output",
        ) from error
