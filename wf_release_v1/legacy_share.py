"""Read-only inspection of legacy ``wfshare`` bundles.

This adapter deliberately stops before conversion.  A legacy share is not a
``wf-release-v1`` archive: its requirements have different semantics and it
may carry host-side scripts.  Inspection proves the declared CDN edge and
reports the work that must be migrated without executing any bundled code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Final, Mapping, Sequence
from zipfile import BadZipFile, ZipFile, ZipInfo

from .canonical import load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError


_MAX_METADATA_BYTES: Final = 1024 * 1024
_MAX_MEMBER_BYTES: Final = 8 * 1024 * 1024 * 1024
_MAX_TOTAL_BYTES: Final = 16 * 1024 * 1024 * 1024
_MAX_MEMBERS: Final = 65534
_REPARSE_POINT: Final = 0x0400
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_VERSION: Final = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_ARCHIVE: Final = re.compile(
    r"^archive-(common|medium|android)-diff/"
    r"pinball-([0-9]+\.[0-9]+\.[0-9]+)-"
    r"([0-9]+\.[0-9]+\.[0-9]+)-([1-9][0-9]*)-"
    r"([A-Za-z0-9][A-Za-z0-9._-]*)\.zip$"
)
_SCRIPT_SUFFIXES: Final = frozenset(
    {".bat", ".cmd", ".com", ".dll", ".exe", ".js", ".ps1", ".py", ".sh"}
)


def _error(message: str, **details: object) -> ReleaseError:
    return ReleaseError("WFREL_SHARE_INVALID", message, details)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise _error(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise _error(f"{label} fields are invalid")


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(f"{label} must be a non-empty string")
    return value


def _integer(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _error(f"{label} must be a non-negative integer")
    return value


def _version(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _VERSION.fullmatch(result) is None:
        raise _error(f"{label} is invalid")
    return result


def _safe_path(value: str) -> str:
    try:
        result = normalize_relative_path(value)
    except ReleaseError as error:
        raise _error("legacy share contains an unsafe member") from error
    if ":" in result or any(part.endswith((" ", ".")) for part in result.split("/")):
        raise _error("legacy share contains an unsafe member")
    return result


def _regular(info: ZipInfo) -> None:
    if info.flag_bits & 0x1:
        raise _error("legacy share contains an encrypted member")
    mode = (info.external_attr >> 16) & 0xFFFF
    if info.create_system == 3 and mode and not stat.S_ISREG(mode):
        raise _error("legacy share contains a non-regular member")


def _members(bundle: ZipFile) -> tuple[str, dict[str, ZipInfo]]:
    infos = bundle.infolist()
    if not infos or len(infos) > _MAX_MEMBERS:
        raise _error("legacy share member count is invalid")
    seen: set[str] = set()
    folded: set[str] = set()
    files: dict[str, ZipInfo] = {}
    roots: set[str] = set()
    total = 0
    for info in infos:
        name = _safe_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
        root, _, relative = name.partition("/")
        roots.add(root)
        key = name.casefold()
        if name in seen or key in folded:
            raise _error("legacy share contains duplicate members")
        seen.add(name)
        folded.add(key)
        if info.is_dir():
            continue
        if not relative:
            raise _error("legacy share files must be under one root directory")
        _regular(info)
        if info.file_size < 0 or info.file_size > _MAX_MEMBER_BYTES:
            raise _error("legacy share member is too large")
        total += info.file_size
        if total > _MAX_TOTAL_BYTES:
            raise _error("legacy share is too large")
        files[relative] = info
    if len(roots) != 1 or not files:
        raise _error("legacy share must contain exactly one root directory")
    return next(iter(roots)), files


def _read_small(bundle: ZipFile, info: ZipInfo, *, label: str) -> bytes:
    if info.file_size > _MAX_METADATA_BYTES:
        raise _error(f"{label} is too large")
    raw = bundle.read(info)
    if len(raw) != info.file_size:
        raise _error(f"{label} length changed")
    return raw


def _nested_archive(
    bundle: ZipFile, info: ZipInfo, *, relative_path: str
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b") as temporary:
        with bundle.open(info, "r") as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_MEMBER_BYTES:
                    raise _error("legacy content archive is too large")
                digest.update(chunk)
                temporary.write(chunk)
        if size != info.file_size:
            raise _error("legacy content archive length changed")
        temporary.seek(0)
        try:
            with ZipFile(temporary, "r") as inner:
                entries = inner.infolist()
                if not entries or len(entries) > _MAX_MEMBERS:
                    raise _error("legacy content archive entry count is invalid")
                inner_seen: set[str] = set()
                inner_total = 0
                for item in entries:
                    name = _safe_path(item.filename.rstrip("/") if item.is_dir() else item.filename)
                    if name in inner_seen:
                        raise _error("legacy content archive contains duplicate entries")
                    inner_seen.add(name)
                    if item.is_dir():
                        continue
                    _regular(item)
                    inner_total += item.file_size
                    if item.file_size > _MAX_MEMBER_BYTES or inner_total > _MAX_TOTAL_BYTES:
                        raise _error("legacy content archive is too large")
        except BadZipFile as error:
            raise _error("legacy content archive is not a valid ZIP", member=relative_path) from error
    return digest.hexdigest(), len(entries)


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
    variant: str
    from_version: str
    target_version: str
    archives: tuple[LegacyContentArchive, ...]
    content_entry_count: int
    server_data_files: int
    server_data_scripts: int
    server_table_count: int
    enhancement: bool

    def to_wire(self) -> dict[str, object]:
        blockers = [
            "release-requirements-mapping-required",
            "sealed-character-workspace-required",
        ]
        if self.server_data_files:
            blockers.append("server-data-migration-required")
        if self.server_data_scripts:
            blockers.append("server-data-script-review-required")
        warnings = ["full-variant-includes-enhancements"] if self.enhancement else []
        return {
            "archiveSha256": self.archive_sha256,
            "blockers": blockers,
            "contentArchiveCount": len(self.archives),
            "contentArchives": [item.to_wire() for item in self.archives],
            "contentEntryCount": self.content_entry_count,
            "fromVersion": self.from_version,
            "migrationStatus": "blocked" if blockers else "ready",
            "serverDataFiles": self.server_data_files,
            "serverDataScripts": self.server_data_scripts,
            "serverTableCount": self.server_table_count,
            "sourceFormat": "wfshare-v2",
            "targetVersion": self.target_version,
            "variant": self.variant,
            "warnings": warnings,
        }


def _parse_requirements(value: object) -> tuple[Mapping[str, object], bool]:
    document = _mapping(value, label="requires.json")
    _exact(
        document,
        {"schemaVersion", "pack", "enhancement", "enhancementDetail", "requires"},
        label="requires.json",
    )
    if document["schemaVersion"] != 2 or not isinstance(document["enhancement"], bool):
        raise _error("requires.json version or enhancement flag is invalid")
    _mapping(document["enhancementDetail"], label="enhancementDetail")
    _mapping(document["requires"], label="requires")
    pack = _mapping(document["pack"], label="pack")
    _exact(pack, {"variant", "since", "tail", "sourceEdges", "anchor", "archives"}, label="pack")
    if pack["variant"] not in {"full", "content-only"}:
        raise _error("legacy share variant is invalid")
    _version(pack["since"], label="pack.since")
    _version(pack["tail"], label="pack.tail")
    _integer(pack["sourceEdges"], label="pack.sourceEdges")
    return pack, document["enhancement"]


def _inspect(bundle: ZipFile, archive_sha256: str) -> LegacySharePlan:
    _root, files = _members(bundle)
    try:
        requires_info = files["requires.json"]
        report_info = files["report.json"]
    except KeyError as error:
        raise _error("legacy share metadata is incomplete") from error
    pack, enhancement = _parse_requirements(
        load_json_strict_bytes(_read_small(bundle, requires_info, label="requires.json"), label="requires.json")
    )
    anchor = _mapping(pack["anchor"], label="pack.anchor")
    _exact(anchor, {"from", "to"}, label="pack.anchor")
    from_version = _version(anchor["from"], label="pack.anchor.from")
    target_version = _version(anchor["to"], label="pack.anchor.to")
    archive_paths = pack["archives"]
    if not isinstance(archive_paths, list) or not archive_paths:
        raise _error("pack.archives must be a non-empty array")
    declared = [_safe_path(_string(item, label="pack archive")) for item in archive_paths]
    if len(set(declared)) != len(declared):
        raise _error("pack.archives contains duplicates")

    report = _mapping(
        load_json_strict_bytes(_read_small(bundle, report_info, label="report.json"), label="report.json"),
        label="report.json",
    )
    _exact(report, {"variant", "tag", "pack", "entries", "summary", "outputs"}, label="report.json")
    if report["variant"] != pack["variant"]:
        raise _error("report variant does not match requirements")
    total_entries = _integer(report["entries"], label="report.entries")
    summary = _mapping(report["summary"], label="report.summary")
    _exact(summary, {"entries", "kept", "dropped", "rebuilt"}, label="report.summary")
    for field in ("kept", "dropped", "rebuilt"):
        _integer(summary[field], label=f"report.summary.{field}")
    if _integer(summary["entries"], label="report.summary.entries") != total_entries:
        raise _error("report summary does not match entry total")
    outputs = report["outputs"]
    if not isinstance(outputs, list):
        raise _error("report.outputs must be an array")
    output_paths = []
    parsed_outputs: list[Mapping[str, object]] = []
    for value in outputs:
        output = _mapping(value, label="report output")
        _exact(output, {"root", "path", "entries", "size", "sha256"}, label="report output")
        output_paths.append(_safe_path(_string(output["path"], label="report output path")))
        parsed_outputs.append(output)
    if output_paths != declared:
        raise _error("archive declarations do not match")

    archives: list[LegacyContentArchive] = []
    for path, output in zip(declared, parsed_outputs, strict=True):
        match = _ARCHIVE.fullmatch(path)
        if match is None or match.group(2) != from_version or match.group(3) != target_version:
            raise _error("legacy content archive edge is invalid")
        expected_root = match.group(1)
        if output["root"] != expected_root:
            raise _error("legacy content archive root is invalid")
        info = files.get(path)
        if info is None:
            raise _error("declared content archive is missing")
        digest, entries = _nested_archive(bundle, info, relative_path=path)
        expected_digest = _string(output["sha256"], label="archive sha256")
        if _SHA256.fullmatch(expected_digest) is None or digest != expected_digest:
            raise _error("archive digest does not match bytes")
        expected_size = _integer(output["size"], label="archive size")
        expected_entries = _integer(output["entries"], label="archive entries")
        if info.file_size != expected_size or entries != expected_entries:
            raise _error("archive report does not match bytes")
        archives.append(LegacyContentArchive(path, expected_root, entries, expected_size, digest))
    if sum(item.entries for item in archives) != total_entries:
        raise _error("report entry total does not match archives")

    server_files = [
        (path, info)
        for path, info in files.items()
        if path.startswith("server-data/") or path.startswith("server-assets/")
    ]
    scripts = sum(Path(path).suffix.casefold() in _SCRIPT_SUFFIXES for path, _info in server_files)
    table_count = 0
    for path, info in server_files:
        if Path(path).suffix.casefold() != ".json":
            continue
        value = load_json_strict_bytes(_read_small(bundle, info, label="server data JSON"), label="server data JSON")
        table_count += len(_mapping(value, label="server data JSON"))

    allowed = {"requires.json", "report.json", *declared}
    for path in files:
        if path in allowed or path.startswith(("server-data/", "server-assets/")):
            continue
        if "/" not in path and Path(path).suffix.casefold() in {".md", ".txt"}:
            _read_small(bundle, files[path], label="share documentation")
            continue
        raise _error("legacy share contains an unrecognized member")
    return LegacySharePlan(
        archive_sha256,
        _string(pack["variant"], label="pack.variant"),
        from_version,
        target_version,
        tuple(archives),
        total_entries,
        len(server_files),
        scripts,
        table_count,
        enhancement,
    )


def _identity(value: os.stat_result) -> tuple[int, int, int, int, bool, bool]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        stat.S_ISREG(value.st_mode),
        bool(getattr(value, "st_file_attributes", 0) & _REPARSE_POINT),
    )


def inspect_legacy_share(path: Path) -> LegacySharePlan:
    """Inspect one legacy share without extracting it or executing bundled code."""
    source = Path(path)
    descriptor = -1
    try:
        before = _identity(source.lstat())
        if not before[4] or before[5] or before[2] <= 0 or before[2] > _MAX_TOTAL_BYTES:
            raise _error("legacy share must be a bounded regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        opened = _identity(os.fstat(descriptor))
        if opened != before:
            raise _error("legacy share identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            digest = hashlib.sha256()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            stream.seek(0)
            try:
                with ZipFile(stream, "r") as bundle:
                    plan = _inspect(bundle, digest.hexdigest())
            except BadZipFile as error:
                raise _error("legacy share is not a valid ZIP") from error
            if _identity(os.fstat(stream.fileno())) != opened:
                raise _error("legacy share changed while being inspected")
        if _identity(source.lstat()) != opened:
            raise _error("legacy share changed while being inspected")
        return plan
    except ReleaseError:
        raise
    except OSError as error:
        raise ReleaseError("WFREL_SHARE_IO", "legacy share could not be inspected") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = ["LegacyContentArchive", "LegacySharePlan", "inspect_legacy_share"]
