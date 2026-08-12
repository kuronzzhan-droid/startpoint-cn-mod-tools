"""Read-only inspection of supported legacy ``wfshare`` bundles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from tempfile import SpooledTemporaryFile, TemporaryFile
from typing import BinaryIO, Final
from zipfile import BadZipFile, LargeZipFile, ZipFile

from .canonical import load_json_strict_bytes
from .errors import ReleaseError
from ._legacy_schema import ARCHIVE_PATTERN, ArchiveSpec, parse_metadata
from ._legacy_zip import (
    MAX_METADATA_BYTES,
    MAX_SERVER_JSON_BYTES,
    MAX_TOTAL_BYTES,
    central_preflight,
    copy_member,
    error,
    outer_files,
    read_member,
    validate_infos,
)


_REPARSE_POINT: Final = 0x0400
_PAYLOAD_PREFIX: Final = {
    "common": "production/upload",
    "medium": "production/medium_upload",
    "android": "production/android_upload",
}
_SCRIPT_SUFFIXES: Final = frozenset(
    {
        ".bat",
        ".cmd",
        ".com",
        ".dll",
        ".exe",
        ".hta",
        ".jar",
        ".js",
        ".mjs",
        ".msi",
        ".ps1",
        ".psm1",
        ".py",
        ".pyw",
        ".scr",
        ".sh",
        ".vbe",
        ".vbs",
        ".wsf",
        ".wsh",
    }
)


@dataclass(frozen=True)
class LegacyContentArchive:
    path: str
    root: str
    entries: int
    size: int
    sha256: str

    def to_wire(self) -> dict[str, object]:
        return {
            "entries": self.entries,
            "path": self.path,
            "root": self.root,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclass(frozen=True)
class LegacySharePlan:
    archive_sha256: str
    source_dialect: str
    variant: str
    from_version: str
    target_version: str
    archives: tuple[LegacyContentArchive, ...]
    content_entry_count: int
    server_data_files: int
    server_data_scripts: int
    server_table_count: int
    enhancement: bool
    has_dev_catalog: bool

    def to_wire(self) -> dict[str, object]:
        blockers = [
            "release-requirements-mapping-required",
            "sealed-character-workspace-required",
            "server-data-migration-required",
        ]
        if self.has_dev_catalog:
            blockers.append("dev-catalog-migration-required")
        if self.server_data_scripts:
            blockers.append("server-data-script-review-required")
        warnings = []
        if self.enhancement:
            warnings.append("full-variant-includes-enhancements")
        if self.source_dialect == "catalog-export":
            warnings.append("catalog-export-has-no-archive-report")
        return {
            "archiveSha256": self.archive_sha256,
            "blockers": blockers,
            "contentArchiveCount": len(self.archives),
            "contentArchives": [item.to_wire() for item in self.archives],
            "contentEntryCount": self.content_entry_count,
            "fromVersion": self.from_version,
            "migrationStatus": "blocked",
            "serverDataFiles": self.server_data_files,
            "serverDataScripts": self.server_data_scripts,
            "serverTableCount": self.server_table_count,
            "sourceDialect": self.source_dialect,
            "sourceFormat": "wfshare-v2",
            "targetVersion": self.target_version,
            "variant": self.variant,
            "warnings": warnings,
        }


def _nested_archive(
    bundle: ZipFile,
    info,
    *,
    spec: ArchiveSpec,
) -> tuple[str, int, int]:
    with SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b") as staged:
        size, digest = copy_member(bundle, info, staged)
        central_preflight(staged)
        try:
            with ZipFile(staged, "r", allowZip64=True) as inner:
                members = validate_infos(inner.infolist(), allow_directories=False)
                expected = re.compile(
                    re.escape(_PAYLOAD_PREFIX[spec.layer]) + r"/[0-9a-f]{2}/[0-9a-f]{38}"
                )
                for name, member in members:
                    if expected.fullmatch(name) is None:
                        raise error("legacy content archive member is outside its declared layer")
                    copy_member(inner, member)
        except ReleaseError:
            raise
        except (OSError, RuntimeError, NotImplementedError, BadZipFile, LargeZipFile) as exc:
            raise error("legacy content archive is not a valid ZIP", member=spec.path) from exc
    return digest, len(members), size


def _server_script(path: str) -> bool:
    suffix = Path(path).suffix.casefold()
    if path.startswith("server-data/") and suffix != ".json":
        return True
    return suffix in _SCRIPT_SUFFIXES


def _inspect(bundle: ZipFile, archive_sha256: str) -> LegacySharePlan:
    _root, files = outer_files(bundle)
    requires_info = files.get("requires.json")
    if requires_info is None:
        raise error("legacy share metadata is incomplete")
    requires_value = load_json_strict_bytes(
        read_member(bundle, requires_info, limit=MAX_METADATA_BYTES, label="requires.json"),
        label="requires.json",
    )
    report_info = files.get("report.json")
    report_value = None
    if report_info is not None:
        report_value = load_json_strict_bytes(
            read_member(bundle, report_info, limit=MAX_METADATA_BYTES, label="report.json"),
            label="report.json",
        )
    archive_paths = sorted(path for path in files if ARCHIVE_PATTERN.fullmatch(path))
    metadata = parse_metadata(
        requires_value,
        report_value,
        available_archive_paths=archive_paths,
    )

    archives: list[LegacyContentArchive] = []
    for spec in metadata.archives:
        info = files.get(spec.path)
        if info is None:
            raise error("declared content archive is missing")
        digest, entries, size = _nested_archive(bundle, info, spec=spec)
        if spec.sha256 is not None and digest != spec.sha256:
            raise error("archive digest does not match bytes")
        if spec.size is not None and size != spec.size:
            raise error("archive size does not match bytes")
        if spec.entries is not None and entries != spec.entries:
            raise error("archive entry count does not match bytes")
        archives.append(
            LegacyContentArchive(spec.path, spec.layer, entries, size, digest)
        )
    total_entries = sum(item.entries for item in archives)
    if metadata.report_entries is not None and total_entries != metadata.report_entries:
        raise error("report entry total does not match archives")

    server_paths = [
        path
        for path in files
        if path.startswith("server-data/") or path.startswith("server-assets/")
    ]
    table_count = 0
    scripts = 0
    for path in server_paths:
        info = files[path]
        scripts += _server_script(path)
        if Path(path).suffix.casefold() == ".json":
            value = load_json_strict_bytes(
                read_member(
                    bundle,
                    info,
                    limit=MAX_SERVER_JSON_BYTES,
                    label="server data JSON",
                ),
                label="server data JSON",
            )
            if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
                raise error("server data JSON must be an object")
            table_count += len(value)
        else:
            copy_member(bundle, info)

    dev_paths = [path for path in files if path.startswith("dev-catalog/")]
    for path in dev_paths:
        copy_member(bundle, files[path])

    recognized = {
        "requires.json",
        *(item.path for item in metadata.archives),
        *server_paths,
        *dev_paths,
    }
    if report_info is not None:
        recognized.add("report.json")
    for path, info in files.items():
        if path in recognized:
            continue
        if "/" not in path and Path(path).suffix.casefold() in {".md", ".txt"}:
            read_member(bundle, info, limit=MAX_METADATA_BYTES, label="share documentation")
            continue
        raise error("legacy share contains an unrecognized member")

    return LegacySharePlan(
        archive_sha256,
        metadata.dialect,
        metadata.variant,
        metadata.from_version,
        metadata.target_version,
        tuple(archives),
        total_entries,
        len(server_paths),
        scripts,
        table_count,
        metadata.enhancement,
        bool(dev_paths),
    )


def _identity(value: os.stat_result) -> tuple[int, int, int, int, bool, bool]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        stat.S_ISREG(value.st_mode),
        stat.S_ISLNK(value.st_mode)
        or bool(getattr(value, "st_file_attributes", 0) & _REPARSE_POINT),
    )


def _copy_and_hash(source: BinaryIO, destination: BinaryIO | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_TOTAL_BYTES:
            raise error("legacy share is too large")
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
    if destination is not None:
        destination.flush()
        destination.seek(0)
    return size, digest.hexdigest()


def inspect_legacy_share(path: Path) -> LegacySharePlan:
    """Inspect one immutable private snapshot without extracting or executing it."""
    source = Path(path)
    descriptor = -1
    try:
        before = _identity(source.lstat())
        if not before[4] or before[5] or before[2] <= 0 or before[2] > MAX_TOTAL_BYTES:
            raise error("legacy share must be a bounded regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        opened = _identity(os.fstat(descriptor))
        if opened != before:
            raise error("legacy share identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            with TemporaryFile(mode="w+b") as snapshot:
                size, digest = _copy_and_hash(stream, snapshot)
                if size != opened[2]:
                    raise error("legacy share changed while being copied")
                central_preflight(snapshot)
                try:
                    with ZipFile(snapshot, "r", allowZip64=True) as bundle:
                        plan = _inspect(bundle, digest)
                except ReleaseError:
                    raise
                except (OSError, RuntimeError, NotImplementedError, BadZipFile, LargeZipFile) as exc:
                    raise error("legacy share is not a valid ZIP") from exc
            stream.seek(0)
            final_size, final_digest = _copy_and_hash(stream)
            if (
                final_size != size
                or final_digest != digest
                or _identity(os.fstat(stream.fileno())) != opened
            ):
                raise error("legacy share changed while being inspected")
        if _identity(source.lstat()) != opened:
            raise error("legacy share changed while being inspected")
        return plan
    except ReleaseError:
        raise
    except OSError as exc:
        raise ReleaseError("WFREL_SHARE_IO", "legacy share could not be inspected") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = ["LegacyContentArchive", "LegacySharePlan", "inspect_legacy_share"]
