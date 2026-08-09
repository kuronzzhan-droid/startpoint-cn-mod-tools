"""Strict, read-only inspection of explicit Patch Overlay outer ZIPs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import io
import os
from pathlib import Path
import re
import stat
from typing import Final
import zipfile

from .canonical import load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError


_REPARSE_POINT: Final = 0x0400
_JS_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_MAX_METADATA_BYTES: Final = 1024 * 1024
_MAX_MEMBER_BYTES: Final = 8 * 1024 * 1024 * 1024
_MAX_TOTAL_BYTES: Final = 16 * 1024 * 1024 * 1024
_RATIO_THRESHOLD: Final = 1024 * 1024
_MAX_COMPRESSION_RATIO: Final = 100
_VERSION_RE: Final = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
)
_DIFF_NAME_RE: Final = re.compile(
    r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-"
    r"([1-9][0-9]*)-([a-fA-F0-9]+)\.zip"
)
_SHA256_RE: Final = re.compile(r"[a-f0-9]{64}")
_ARCHIVE_KEYS: Final = frozenset(
    {"relativePath", "layer", "order", "bytes", "sha256"}
)
_METADATA_MEMBERS: Final = frozenset(
    {"README.md", "requires.json", "patch-manifest.json"}
)
_LAYERS: Final = ("common", "medium", "android")


@dataclass(frozen=True)
class SourceFile:
    """One validated outer Overlay file pinned to its inspection facts."""

    path: Path
    relative_path: str
    size: int
    manifest_sha256: str
    from_version: str
    target_version: str
    _identity: tuple[int, int, int, int] = field(repr=False, compare=False)


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _snapshot(file_stat: os.stat_result) -> tuple[int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_size,
        file_stat.st_mtime_ns,
    )


def _is_reparse(file_stat: os.stat_result) -> bool:
    return stat.S_ISLNK(file_stat.st_mode) or bool(
        getattr(file_stat, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _regular_snapshot(path: Path, *, label: str) -> tuple[int, int, int, int]:
    try:
        file_stat = os.lstat(path)
    except OSError as error:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "explicit Overlay archive is unavailable",
            archiveName=label,
        ) from error
    if _is_reparse(file_stat) or not stat.S_ISREG(file_stat.st_mode):
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "explicit Overlay archive must be a non-reparse regular file",
            archiveName=label,
        )
    if file_stat.st_size <= 0 or file_stat.st_size > _MAX_MEMBER_BYTES:
        raise _error(
            "WFREL_OVERLAY_LIMIT",
            "explicit Overlay archive has an unsafe size",
            archiveName=label,
        )
    return _snapshot(file_stat)


def _version(value: object, *, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    parsed = tuple(int(part) for part in match.groups())
    if any(part > _JS_MAX_SAFE_INTEGER for part in parsed):
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    return parsed


def _safe_archive_path(value: object, *, layer: str) -> tuple[str, re.Match[str]]:
    if not isinstance(value, str):
        raise _error("WFREL_OVERLAY_INVALID", "archive path is invalid", label="relativePath")
    try:
        normalize_relative_path(value)
    except ReleaseError as error:
        raise _error("WFREL_OVERLAY_INVALID", "archive path is invalid", label="relativePath") from error
    if (
        not value.isascii()
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in value)
        or any(character in value for character in ":?#%")
        or value.split("/")[:-1] != [f"archive-{layer}-diff"]
    ):
        raise _error("WFREL_OVERLAY_INVALID", "archive path is invalid", label="relativePath")
    match = _DIFF_NAME_RE.fullmatch(value.rsplit("/", 1)[-1])
    if match is None:
        raise _error("WFREL_OVERLAY_INVALID", "archive filename is invalid", label="relativePath")
    return value, match


def _validate_zip_limits(infos: Sequence[zipfile.ZipInfo], *, archive_name: str) -> None:
    total = 0
    for info in infos:
        if info.is_dir() or info.filename.endswith("/"):
            raise _error(
                "WFREL_OVERLAY_INVALID",
                "Patch Overlay ZIP cannot contain directory entries",
                archiveName=archive_name,
            )
        if info.file_size < 0 or info.file_size > _MAX_MEMBER_BYTES:
            raise _error(
                "WFREL_OVERLAY_LIMIT",
                "Patch Overlay ZIP member exceeds the size limit",
                archiveName=archive_name,
            )
        total += info.file_size
        if total > _MAX_TOTAL_BYTES:
            raise _error(
                "WFREL_OVERLAY_LIMIT",
                "Patch Overlay ZIP exceeds the total size limit",
                archiveName=archive_name,
            )
        if info.file_size > _RATIO_THRESHOLD and (
            info.compress_size <= 0
            or info.file_size > info.compress_size * _MAX_COMPRESSION_RATIO
        ):
            raise _error(
                "WFREL_OVERLAY_LIMIT",
                "Patch Overlay ZIP member exceeds the compression-ratio limit",
                archiveName=archive_name,
            )


def _read_json_member(
    bundle: zipfile.ZipFile,
    infos: Mapping[str, zipfile.ZipInfo],
    name: str,
    *,
    archive_name: str,
) -> object:
    info = infos[name]
    if info.file_size > _MAX_METADATA_BYTES:
        raise _error(
            "WFREL_OVERLAY_LIMIT",
            "Overlay metadata exceeds the size limit",
            archiveName=archive_name,
        )
    try:
        raw = bundle.read(info)
        return load_json_strict_bytes(raw, label=name)
    except ReleaseError as error:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "Overlay metadata JSON is invalid",
            archiveName=archive_name,
            member=name,
        ) from error


def _validate_inner_zip(raw: bytes, *, archive_name: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            infos = inner.infolist()
            _validate_zip_limits(infos, archive_name=archive_name)
            normalized_names: set[str] = set()
            for info in infos:
                try:
                    original = normalize_relative_path(info.orig_filename)
                    normalized = normalize_relative_path(info.filename)
                except ReleaseError as error:
                    raise _error(
                        "WFREL_OVERLAY_INVALID",
                        "inner ZIP member path is invalid",
                        archiveName=archive_name,
                    ) from error
                if original != normalized or normalized in normalized_names:
                    raise _error(
                        "WFREL_OVERLAY_INVALID",
                        "inner ZIP member path is duplicated",
                        archiveName=archive_name,
                    )
                normalized_names.add(normalized)
            if inner.testzip() is not None:
                raise zipfile.BadZipFile("inner ZIP member contract failed")
    except ReleaseError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "manifest-declared payload is not a valid ZIP",
            archiveName=archive_name,
        ) from error


def _validate_overlay_manifest(
    bundle: zipfile.ZipFile,
    infos: Mapping[str, zipfile.ZipInfo],
    manifest: object,
    *,
    archive_name: str,
) -> tuple[str, str]:
    if not isinstance(manifest, Mapping):
        raise _error("WFREL_OVERLAY_INVALID", "patch manifest must be an object")
    required = {"schema", "targetVersion", "compatibleClient", "archives"}
    if (
        not required.issubset(manifest)
        or type(manifest.get("schema")) is not int
        or manifest.get("schema") != 1
    ):
        raise _error("WFREL_OVERLAY_INVALID", "patch manifest schema is invalid")
    if manifest.get("compatibleClient") != "CN 1.8.1":
        raise _error("WFREL_OVERLAY_INVALID", "patch manifest client is incompatible")
    target = manifest.get("targetVersion")
    _version(target, label="targetVersion")
    if "baseVersion" in manifest:
        _version(manifest["baseVersion"], label="baseVersion")
    entries = manifest.get("archives")
    if not isinstance(entries, list) or not entries:
        raise _error("WFREL_OVERLAY_INVALID", "patch manifest archives must be nonempty")

    declared: set[str] = set()
    layers: dict[str, list[int]] = {layer: [] for layer in _LAYERS}
    edge_from: str | None = None
    for index, value in enumerate(entries):
        if not isinstance(value, Mapping) or set(value) != _ARCHIVE_KEYS:
            raise _error(
                "WFREL_OVERLAY_INVALID",
                "patch archive entry keys are invalid",
                archiveIndex=index,
            )
        layer = value.get("layer")
        if not isinstance(layer, str) or layer not in layers:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive layer is invalid")
        relative_path, match = _safe_archive_path(value.get("relativePath"), layer=layer)
        order = value.get("order")
        size = value.get("bytes")
        digest = value.get("sha256")
        if type(order) is not int or not 0 < order <= _JS_MAX_SAFE_INTEGER:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive order is invalid")
        if type(size) is not int or not 0 < size <= _JS_MAX_SAFE_INTEGER:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive size is invalid")
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive SHA-256 is invalid")
        from_version, to_version = match.group(1), match.group(2)
        _version(from_version, label="archive.fromVersion")
        _version(to_version, label="archive.toVersion")
        if to_version != target or int(match.group(3)) != order:
            raise _error("WFREL_OVERLAY_INVALID", "archive filename disagrees with manifest")
        if edge_from is None:
            edge_from = from_version
        elif edge_from != from_version:
            raise _error("WFREL_OVERLAY_GRAPH", "one Overlay must describe one version edge")
        if relative_path in declared:
            raise _error("WFREL_OVERLAY_INVALID", "archive path is duplicated")
        declared.add(relative_path)
        layers[layer].append(order)
        info = infos.get(relative_path)
        if info is None or info.file_size != size:
            raise _error("WFREL_OVERLAY_INVALID", "archive size does not match manifest")
        try:
            raw = bundle.read(info)
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise _error("WFREL_OVERLAY_INVALID", "archive payload is corrupt") from error
        if hashlib.sha256(raw).hexdigest() != digest:
            raise _error("WFREL_OVERLAY_INVALID", "archive digest does not match manifest")
        _validate_inner_zip(raw, archive_name=archive_name)

    for layer, orders in layers.items():
        if not orders or sorted(orders) != list(range(1, len(orders) + 1)):
            raise _error(
                "WFREL_OVERLAY_INVALID",
                "each Overlay layer must use contiguous orders starting at one",
                layer=layer,
            )
    expected = _METADATA_MEMBERS | declared
    if set(infos) != expected:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "outer Overlay ZIP does not match its explicit member allowlist",
            archiveName=archive_name,
        )
    assert isinstance(target, str) and edge_from is not None
    return edge_from, target


def _inspect_overlay(path: Path) -> SourceFile:
    absolute = Path(os.path.abspath(os.fspath(path)))
    archive_name = absolute.name or "overlay.zip"
    try:
        relative_path = normalize_relative_path(archive_name)
    except ReleaseError as error:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "outer Overlay filename is not canonical",
            archiveName=archive_name,
        ) from error
    identity = _regular_snapshot(absolute, label=archive_name)
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(absolute, flags)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode) or _snapshot(opened) != identity:
            raise OSError("archive identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            with zipfile.ZipFile(stream) as bundle:
                infos_list = bundle.infolist()
                names: list[str] = []
                seen_names: set[str] = set()
                for info in infos_list:
                    try:
                        original = normalize_relative_path(info.orig_filename)
                        normalized = normalize_relative_path(info.filename)
                    except ReleaseError as error:
                        raise _error(
                            "WFREL_OVERLAY_INVALID",
                            "outer Overlay ZIP member path is invalid",
                            archiveName=archive_name,
                        ) from error
                    if original != normalized or normalized in seen_names:
                        raise _error(
                            "WFREL_OVERLAY_INVALID",
                            "outer Overlay ZIP members are duplicated or noncanonical",
                            archiveName=archive_name,
                        )
                    names.append(normalized)
                    seen_names.add(normalized)
                if not names or names[-1] != "patch-manifest.json":
                    raise _error(
                        "WFREL_OVERLAY_INVALID",
                        "outer Overlay ZIP members are incomplete",
                        archiveName=archive_name,
                    )
                _validate_zip_limits(infos_list, archive_name=archive_name)
                infos = dict(zip(names, infos_list, strict=True))
                if not _METADATA_MEMBERS.issubset(infos):
                    raise _error(
                        "WFREL_OVERLAY_INVALID",
                        "outer Overlay ZIP metadata is incomplete",
                        archiveName=archive_name,
                    )
                if any(
                    infos[name].file_size > _MAX_METADATA_BYTES
                    for name in _METADATA_MEMBERS
                ):
                    raise _error(
                        "WFREL_OVERLAY_LIMIT",
                        "Overlay metadata exceeds the size limit",
                        archiveName=archive_name,
                    )
                bundle.read(infos["README.md"])
                requires = _read_json_member(
                    bundle, infos, "requires.json", archive_name=archive_name
                )
                if not isinstance(requires, Mapping):
                    raise _error("WFREL_OVERLAY_INVALID", "requires.json must be an object")
                manifest_raw = bundle.read(infos["patch-manifest.json"])
                try:
                    manifest = load_json_strict_bytes(
                        manifest_raw, label="patch-manifest.json"
                    )
                except ReleaseError as error:
                    raise _error(
                        "WFREL_OVERLAY_INVALID",
                        "patch-manifest.json is invalid",
                        archiveName=archive_name,
                    ) from error
                edge_from, target = _validate_overlay_manifest(
                    bundle, infos, manifest, archive_name=archive_name
                )
            after_open = _snapshot(os.fstat(stream.fileno()))
        after_path = os.lstat(absolute)
        if after_open != identity or _snapshot(after_path) != identity or _is_reparse(after_path):
            raise OSError("archive identity changed while reading")
    except ReleaseError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "outer Overlay ZIP is unreadable or changed during inspection",
            archiveName=archive_name,
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return SourceFile(
        path=absolute,
        relative_path=relative_path,
        size=identity[2],
        manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        from_version=edge_from,
        target_version=target,
        _identity=identity,
    )


def _ordered_chain(files: Sequence[SourceFile]) -> tuple[tuple[SourceFile, ...], str]:
    by_edge: dict[tuple[str, str], SourceFile] = {}
    outgoing: dict[str, SourceFile] = {}
    incoming: dict[str, SourceFile] = {}
    for source in files:
        edge = (source.from_version, source.target_version)
        if edge in by_edge:
            raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay edge is duplicated")
        if source.from_version in outgoing or source.target_version in incoming:
            raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph forks or merges")
        if _version(source.from_version, label="fromVersion") >= _version(
            source.target_version, label="targetVersion"
        ):
            raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay versions must increase")
        by_edge[edge] = source
        outgoing[source.from_version] = source
        incoming[source.target_version] = source
    heads = set(outgoing) - set(incoming)
    tails = set(incoming) - set(outgoing)
    if len(heads) != 1 or len(tails) != 1:
        raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph has no unique chain tail")
    ordered: list[SourceFile] = []
    current = next(iter(heads))
    visited: set[tuple[str, str]] = set()
    while current in outgoing:
        source = outgoing[current]
        edge = (source.from_version, source.target_version)
        if edge in visited:
            raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph contains a cycle")
        visited.add(edge)
        ordered.append(source)
        current = source.target_version
    if len(visited) != len(files) or current not in tails:
        raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph is disconnected")
    return tuple(ordered), current


def inspect_patch_overlay_chain(
    overlay_archives: Sequence[Path],
) -> tuple[tuple[SourceFile, ...], str]:
    """Inspect explicit outer ZIPs and return their unique chain order and tail."""
    if isinstance(overlay_archives, (str, bytes)) or not isinstance(
        overlay_archives, Sequence
    ) or not overlay_archives:
        raise _error(
            "WFREL_OVERLAY_INVALID",
            "at least one explicit Patch Overlay archive is required",
        )
    files: list[SourceFile] = []
    seen_objects: set[tuple[int, int]] = set()
    seen_names: set[str] = set()
    for raw_path in overlay_archives:
        if not isinstance(raw_path, (str, os.PathLike)):
            raise _error("WFREL_OVERLAY_INVALID", "Overlay archive path is invalid")
        path = Path(raw_path)
        identity = _regular_snapshot(path, label=path.name or "overlay.zip")
        object_key = identity[:2]
        if object_key in seen_objects:
            raise _error("WFREL_OVERLAY_INVALID", "Overlay archive is duplicated")
        source = _inspect_overlay(path)
        if source.relative_path in seen_names:
            raise _error("WFREL_OVERLAY_INVALID", "Overlay archive filename is duplicated")
        seen_objects.add(object_key)
        seen_names.add(source.relative_path)
        files.append(source)
    return _ordered_chain(files)
