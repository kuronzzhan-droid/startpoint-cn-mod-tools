"""Atomic, inert import workspaces for verified legacy ``wfshare`` bundles."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import BinaryIO, Final, Iterator
from zipfile import BadZipFile, LargeZipFile, ZipFile

import wf_character_workspace

from ._legacy_mapping import LegacyPath, parse_path_map, path_map_bytes
from ._legacy_zip import central_preflight, copy_member, error, outer_files, validate_infos
from .canonical import (
    FileIdentity,
    canonical_json_bytes,
    load_json_strict_bytes,
    stream_copy_and_hash_stable_file,
)
from .errors import ReleaseError
from .legacy_share import LegacySharePlan, _inspect
from .receipts import _sync_directory


_REPARSE_POINT: Final = 0x0400
_PREFIXES: Final = {
    "common": "production/upload/",
    "medium": "production/medium_upload/",
    "android": "production/android_upload/",
}


@contextmanager
def _owned_staging(parent: Path) -> Iterator[Path]:
    raw = Path(tempfile.mkdtemp(prefix=".legacy-import-", dir=parent))
    temporary = wf_character_workspace._absolute(raw)  # type: ignore[attr-defined]
    try:
        yield temporary / "workspace"
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


@dataclass(frozen=True)
class ImportedPayload:
    root: str
    hashed_path: str
    logical_path: str | None
    workspace_path: str
    identity: FileIdentity

    def to_wire(self) -> dict[str, object]:
        return {
            "hashedPath": self.hashed_path,
            "logicalPath": self.logical_path,
            "path": self.workspace_path,
            "root": self.root,
            "sha256": self.identity.sha256,
            "size": self.identity.size,
        }


@dataclass(frozen=True)
class ImportedQuarantineFile:
    source_path: str
    workspace_path: str
    identity: FileIdentity
    script: bool

    def to_wire(self) -> dict[str, object]:
        return {
            "path": self.workspace_path,
            "script": self.script,
            "sha256": self.identity.sha256,
            "size": self.identity.size,
            "sourcePath": self.source_path,
        }


@dataclass(frozen=True)
class LegacyImportReceipt:
    archive_sha256: str
    archive_size: int
    plan: LegacySharePlan
    mapping_status: str
    client_payload_editable: bool
    payloads: tuple[ImportedPayload, ...]
    quarantine: tuple[ImportedQuarantineFile, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "archiveSha256": self.archive_sha256,
            "archiveSize": self.archive_size,
            "blockers": self.plan.to_wire()["blockers"],
            "clientPayloadEditable": self.client_payload_editable,
            "fromVersion": self.plan.from_version,
            "legacyImportVersion": 1,
            "mappingStatus": self.mapping_status,
            "migrationStatus": "blocked",
            "payloadFileCount": len(self.payloads),
            "quarantineFileCount": len(self.quarantine),
            "sourceDialect": self.plan.source_dialect,
            "sourceFormat": "wfshare-v2",
            "targetVersion": self.plan.target_version,
            "variant": self.plan.variant,
            "warnings": self.plan.to_wire()["warnings"],
        }


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int, bool]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_mode,
        _is_reparse(value),
    )


def _hash_stream(stream: BinaryIO) -> FileIdentity:
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        digest.update(chunk)
    stream.seek(0)
    return FileIdentity(size, digest.hexdigest())


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        item = path.lstat()
    except OSError as exc:
        raise ReleaseError("WFREL_SHARE_IO", "legacy import output parent is unavailable") from exc
    if not stat.S_ISDIR(item.st_mode) or _is_reparse(item):
        raise ReleaseError("WFREL_SHARE_IO", "legacy import output parent is unsafe")
    return item.st_dev, item.st_ino


def _same_directory(path: Path, expected: tuple[int, int]) -> None:
    if _directory_identity(path) != expected:
        raise ReleaseError("WFREL_SHARE_IO", "legacy import output parent changed")


def _sync_file(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ReleaseError("WFREL_SHARE_IO", "legacy import file could not be synchronized") from exc


def _write_bytes(path: Path, raw: bytes) -> FileIdentity:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb", buffering=0) as stream:
            written = stream.write(raw)
            if written != len(raw):
                raise OSError("short write")
            os.fsync(stream.fileno())
    except OSError as exc:
        raise ReleaseError("WFREL_SHARE_IO", "legacy import file could not be written") from exc
    return FileIdentity(len(raw), hashlib.sha256(raw).hexdigest())


def _copy_zip_member(bundle: ZipFile, info, destination: Path) -> FileIdentity:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".legacy-member-", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w+b", buffering=0) as writer:
            size, digest = copy_member(bundle, info, writer)
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
        return FileIdentity(size, digest)
    except ReleaseError:
        raise
    except OSError as exc:
        raise ReleaseError("WFREL_SHARE_IO", "legacy import member could not be written") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _load_mapping(mapping: Path | None, staging: Path) -> tuple[LegacyPath, ...]:
    if mapping is None:
        return ()
    copied = staging / ".mapping-input.json"
    try:
        stream_copy_and_hash_stable_file(Path(mapping), copied)
        raw = copied.read_bytes()
    except ReleaseError as exc:
        if exc.code.startswith("WFREL_JSON_") or exc.code == "WFREL_SHARE_INVALID":
            raise
        raise ReleaseError("WFREL_SHARE_IO", "legacy path map is unavailable") from exc
    finally:
        copied.unlink(missing_ok=True)
    paths = parse_path_map(raw)
    _write_bytes(staging / "legacy-path-map.json", path_map_bytes(paths))
    return paths


def _member_root(name: str) -> tuple[str, str]:
    for root, prefix in _PREFIXES.items():
        if name.startswith(prefix):
            return root, name[len(prefix):]
    raise error("legacy content archive member is outside its declared layer")


def _script(path: str) -> bool:
    suffix = PurePosixPath(path).suffix.casefold()
    return path.startswith("server-data/") and suffix != ".json" or suffix in {
        ".bat", ".cmd", ".com", ".dll", ".exe", ".hta", ".jar", ".js",
        ".mjs", ".msi", ".ps1", ".psm1", ".py", ".pyw", ".scr", ".sh",
        ".vbe", ".vbs", ".wsf", ".wsh",
    }


def _extract_workspace(
    source: BinaryIO,
    staging: Path,
    plan: LegacySharePlan,
    mappings: tuple[LegacyPath, ...],
) -> tuple[tuple[ImportedPayload, ...], tuple[ImportedQuarantineFile, ...]]:
    by_member = {item.member: item for item in mappings}
    seen_mappings: set[str] = set()
    payloads: dict[str, ImportedPayload] = {}
    quarantine: list[ImportedQuarantineFile] = []
    source.seek(0)
    central_preflight(source)
    try:
        with ZipFile(source, "r", allowZip64=True) as outer:
                _root, files = outer_files(outer)
                for name in ("requires.json", "report.json"):
                    info = files.get(name)
                    if info is not None:
                        _copy_zip_member(outer, info, staging / "metadata" / name)
                for archive in plan.archives:
                    info = files[archive.path]
                    archive_path = staging / "archives" / Path(archive.path)
                    identity = _copy_zip_member(outer, info, archive_path)
                    if identity != FileIdentity(archive.size, archive.sha256):
                        raise error("legacy content archive changed during import")
                    with archive_path.open("rb") as inner_stream:
                        central_preflight(inner_stream)
                        with ZipFile(inner_stream, "r", allowZip64=True) as inner:
                            for member_name, member in validate_infos(
                                inner.infolist(), allow_directories=False
                            ):
                                root, hashed = _member_root(member_name)
                                mapping = by_member.get(member_name)
                                if mapping is not None:
                                    seen_mappings.add(member_name)
                                    relative = f"roots/{root}/{mapping.logical_path}"
                                    logical = mapping.logical_path
                                else:
                                    relative = f"opaque/{root}/{hashed}"
                                    logical = None
                                identity = _copy_zip_member(inner, member, staging / Path(relative))
                                payloads[member_name] = ImportedPayload(
                                    root, hashed, logical, relative, identity
                                )
                for name, info in files.items():
                    if not name.startswith(("server-data/", "server-assets/", "dev-catalog/")):
                        continue
                    relative = f"quarantine/{name}"
                    identity = _copy_zip_member(outer, info, staging / Path(relative))
                    quarantine.append(
                        ImportedQuarantineFile(name, relative, identity, _script(name))
                    )
    except ReleaseError:
        raise
    except (OSError, RuntimeError, NotImplementedError, BadZipFile, LargeZipFile) as exc:
        raise error("legacy share changed while being imported") from exc
    missing = sorted(set(by_member) - seen_mappings, key=lambda item: item.encode("utf-8"))
    if missing:
        raise error("legacy path map member does not exist")
    return (
        tuple(payloads[name] for name in sorted(payloads, key=lambda item: item.encode("utf-8"))),
        tuple(sorted(quarantine, key=lambda item: item.source_path.encode("utf-8"))),
    )


def _inventory(
    receipt: LegacyImportReceipt,
    payloads: tuple[ImportedPayload, ...],
    quarantine: tuple[ImportedQuarantineFile, ...],
) -> dict[str, object]:
    plan = receipt.plan.to_wire()
    return {
        **receipt.to_wire(),
        "contentArchives": [
            {**item.to_wire(), "workspacePath": f"archives/{item.path}"}
            for item in receipt.plan.archives
        ],
        "inspection": plan,
        "payloadFiles": [item.to_wire() for item in payloads],
        "quarantineFiles": [item.to_wire() for item in quarantine],
        "sourceArchive": {
            "path": "source.wfshare.zip",
            "sha256": receipt.archive_sha256,
            "size": receipt.archive_size,
        },
    }


def import_legacy_share(
    share: Path,
    output: Path,
    *,
    mapping: Path | None = None,
) -> LegacyImportReceipt:
    """Create one new isolated workspace; never execute or install legacy bytes."""
    source = Path(share)
    destination = Path(output)
    if not destination.is_absolute():
        raise ReleaseError("WFREL_SHARE_INVALID", "legacy import output must be absolute")
    parent = destination.parent
    parent_identity = _directory_identity(parent)
    if destination.exists():
        raise ReleaseError("WFREL_SHARE_IO", "legacy import output already exists")
    with _owned_staging(parent) as staging:
        staging.mkdir()
        copied = staging / "source.wfshare.zip"
        try:
            copied_identity = stream_copy_and_hash_stable_file(source, copied)
        except ReleaseError as exc:
            raise ReleaseError("WFREL_SHARE_IO", "legacy share could not be copied") from exc
        _sync_file(copied)
        try:
            before_path = _file_identity(copied.lstat())
            if before_path[5] or not stat.S_ISREG(before_path[4]):
                raise OSError("private source is not a regular file")
            with copied.open("rb", buffering=0) as snapshot:
                opened = _file_identity(os.fstat(snapshot.fileno()))
                if opened != before_path:
                    raise OSError("private source identity changed before open")
                central_preflight(snapshot)
                with ZipFile(snapshot, "r", allowZip64=True) as outer:
                    plan = _inspect(outer, copied_identity.sha256)
                if plan.archive_sha256 != copied_identity.sha256:
                    raise error("legacy share digest changed during import")
                mappings = _load_mapping(mapping, staging)
                payloads, quarantine = _extract_workspace(
                    snapshot, staging, plan, mappings
                )
                if (
                    _hash_stream(snapshot) != copied_identity
                    or _file_identity(os.fstat(snapshot.fileno())) != opened
                    or _file_identity(copied.lstat()) != opened
                ):
                    raise error("legacy share changed while being imported")
        except ReleaseError:
            raise
        except OSError as exc:
            raise ReleaseError(
                "WFREL_SHARE_IO", "legacy share changed while being imported"
            ) from exc
        mapped = sum(item.logical_path is not None for item in payloads)
        status = "opaque" if mapped == 0 else "complete" if mapped == len(payloads) else "partial"
        receipt = LegacyImportReceipt(
            plan.archive_sha256,
            copied_identity.size,
            plan,
            status,
            status == "complete",
            payloads,
            quarantine,
        )
        inventory_path = staging / "legacy-import.json"
        _write_bytes(inventory_path, canonical_json_bytes(_inventory(receipt, payloads, quarantine)))
        parsed = load_json_strict_bytes(inventory_path.read_bytes(), label="legacy import inventory")
        if canonical_json_bytes(parsed) != inventory_path.read_bytes():
            raise error("legacy import inventory is not canonical")
        for directory in sorted(
            (item for item in staging.rglob("*") if item.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        ):
            _sync_directory(directory)
        _sync_directory(staging)
        _same_directory(parent, parent_identity)
        if destination.exists():
            raise ReleaseError("WFREL_SHARE_IO", "legacy import output appeared during commit")
        try:
            os.rename(staging, wf_character_workspace._absolute(destination))  # type: ignore[attr-defined]
        except OSError as exc:
            raise ReleaseError("WFREL_SHARE_IO", "legacy import workspace could not be committed") from exc
        _sync_directory(parent)
        return receipt


__all__ = ["LegacyImportReceipt", "import_legacy_share"]
