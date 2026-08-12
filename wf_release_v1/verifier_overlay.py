"""Private independent Patch Overlay validation for release content."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import BinaryIO, Final
import zipfile

from .canonical import load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError


_JS_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_MAX_METADATA_BYTES: Final = 1024 * 1024
_MAX_MEMBER_BYTES: Final = 8 * 1024 * 1024 * 1024
_MAX_TOTAL_BYTES: Final = 16 * 1024 * 1024 * 1024
_RATIO_THRESHOLD: Final = 1024 * 1024
_MAX_COMPRESSION_RATIO: Final = 100
_MAX_MEMBERS: Final = 65534
_MAX_CENTRAL_BYTES: Final = 256 * 1024 * 1024
_VERSION_RE: Final = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_DIFF_NAME_RE: Final = re.compile(
    r"pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-([1-9][0-9]*)-([a-fA-F0-9]+)\.zip"
)
_SHA256_RE: Final = re.compile(r"[a-f0-9]{64}")
_ARCHIVE_KEYS: Final = frozenset({"relativePath", "layer", "order", "bytes", "sha256"})
_METADATA: Final = frozenset({"README.md", "requires.json", "patch-manifest.json"})
_LAYERS: Final = ("common", "medium", "android")


@dataclass(frozen=True)
class VerifiedOverlayArchive:
    relative_path: str
    layer: str
    order: int
    size: int
    sha256: str


@dataclass(frozen=True)
class VerifiedOverlayEdge:
    from_version: str
    target_version: str
    archives: tuple[VerifiedOverlayArchive, ...]


@dataclass(frozen=True)
class VerifiedOverlayChain:
    from_version: str
    target_version: str
    edges: tuple[VerifiedOverlayEdge, ...]


@dataclass(frozen=True)
class _Edge:
    path: Path
    facts: VerifiedOverlayEdge

    @property
    def from_version(self) -> str:
        return self.facts.from_version

    @property
    def target_version(self) -> str:
        return self.facts.target_version


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _version(value: object, *, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    parsed = tuple(int(part) for part in match.groups())
    if any(part > _JS_MAX_SAFE_INTEGER for part in parsed):
        raise _error("WFREL_OVERLAY_INVALID", "Overlay version is invalid", label=label)
    return parsed  # type: ignore[return-value]


def _safe_name(info: zipfile.ZipInfo, seen: set[str], *, archive_name: str) -> str:
    try:
        original = normalize_relative_path(info.orig_filename)
        normalized = normalize_relative_path(info.filename)
    except ReleaseError as error:
        raise _error(
            "WFREL_OVERLAY_INVALID", "Overlay ZIP member path is invalid", archiveName=archive_name
        ) from error
    if original != normalized or normalized in seen:
        raise _error(
            "WFREL_OVERLAY_INVALID", "Overlay ZIP member path is duplicated", archiveName=archive_name
        )
    seen.add(normalized)
    return normalized


def _limits(infos: Sequence[zipfile.ZipInfo], *, archive_name: str) -> None:
    if not infos or len(infos) > _MAX_MEMBERS:
        raise _error("WFREL_OVERLAY_LIMIT", "Overlay ZIP member count is unsafe", archiveName=archive_name)
    total = 0
    for info in infos:
        if info.is_dir() or info.filename.endswith("/"):
            raise _error("WFREL_OVERLAY_INVALID", "Overlay ZIP cannot contain directories", archiveName=archive_name)
        if info.file_size < 0 or info.file_size > _MAX_MEMBER_BYTES:
            raise _error("WFREL_OVERLAY_LIMIT", "Overlay member exceeds the size limit", archiveName=archive_name)
        total += info.file_size
        if total > _MAX_TOTAL_BYTES:
            raise _error("WFREL_OVERLAY_LIMIT", "Overlay exceeds the total size limit", archiveName=archive_name)
        if info.file_size > _RATIO_THRESHOLD and (
            info.compress_size <= 0 or info.file_size > info.compress_size * _MAX_COMPRESSION_RATIO
        ):
            raise _error("WFREL_OVERLAY_LIMIT", "Overlay compression ratio is unsafe", archiveName=archive_name)


def _central_preflight(stream: BinaryIO, *, archive_name: str) -> None:
    """Bound central-directory allocation, including valid single-disk ZIP64."""
    try:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        if size < 22 or size > _MAX_TOTAL_BYTES:
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
                signature, record_size, _made_by, _extract, zip_disk, zip_central_disk,
                zip_disk_count, zip_count, zip_central_size, zip_central_at,
            ) = values
            if (
                signature != 0x06064B50 or record_size < 44 or zip_disk != 0
                or zip_central_disk != 0 or zip_disk_count != zip_count
                or zip64_at + 12 + record_size != eocd_at - 20
            ):
                raise ValueError("ZIP64 EOCD is invalid")
            count, central_size, central_at, central_end = (
                zip_count, zip_central_size, zip_central_at, zip64_at
            )
        elif disk != 0 or central_disk != 0 or disk_count != count:
            raise ValueError("multi-disk ZIP is invalid")
        if (
            count == 0 or count > _MAX_MEMBERS
            or central_size <= 0 or central_size > _MAX_CENTRAL_BYTES
            or central_at + central_size != central_end
        ):
            raise ValueError("central directory exceeds verifier limits")
        stream.seek(0)
    except (OSError, ValueError, struct.error) as error:
        raise _error(
            "WFREL_OVERLAY_LIMIT", "Overlay central directory is unsafe", archiveName=archive_name
        ) from error


def _read_small(bundle: zipfile.ZipFile, info: zipfile.ZipInfo, *, archive_name: str) -> bytes:
    if info.file_size > _MAX_METADATA_BYTES:
        raise _error("WFREL_OVERLAY_LIMIT", "Overlay metadata exceeds the size limit", archiveName=archive_name)
    try:
        return bundle.read(info)
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise _error("WFREL_OVERLAY_INVALID", "Overlay member CRC is invalid", archiveName=archive_name) from error


def _stream_copy_hash(source: BinaryIO, destination: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(1024 * 1024):
        digest.update(chunk)
        destination.write(chunk)
        size += len(chunk)
    destination.flush()
    destination.seek(0)
    return size, digest.hexdigest()


def _verify_inner(stream: BinaryIO, *, archive_name: str) -> None:
    try:
        _central_preflight(stream, archive_name=archive_name)
        with zipfile.ZipFile(stream, "r", allowZip64=True) as inner:
            infos = inner.infolist()
            _limits(infos, archive_name=archive_name)
            seen: set[str] = set()
            for info in infos:
                _safe_name(info, seen, archive_name=archive_name)
                with inner.open(info, "r") as reader:
                    while reader.read(1024 * 1024):
                        pass
    except ReleaseError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _error(
            "WFREL_OVERLAY_INVALID", "manifest payload is not a valid inner ZIP", archiveName=archive_name
        ) from error


def _archive_path(value: object, *, layer: str) -> tuple[str, re.Match[str]]:
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


def _manifest_edge(
    bundle: zipfile.ZipFile,
    infos: Mapping[str, zipfile.ZipInfo],
    manifest: object,
    *,
    archive_name: str,
) -> VerifiedOverlayEdge:
    if not isinstance(manifest, Mapping):
        raise _error("WFREL_OVERLAY_INVALID", "patch manifest must be an object")
    required = {"schema", "targetVersion", "compatibleClient", "archives"}
    if not required.issubset(manifest) or type(manifest.get("schema")) is not int or manifest.get("schema") != 1:
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
    archives: list[VerifiedOverlayArchive] = []
    edge_from: str | None = None
    for index, value in enumerate(entries):
        if not isinstance(value, Mapping) or set(value) != _ARCHIVE_KEYS:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive entry keys are invalid", archiveIndex=index)
        layer = value.get("layer")
        if not isinstance(layer, str) or layer not in layers:
            raise _error("WFREL_OVERLAY_INVALID", "patch archive layer is invalid")
        relative_path, match = _archive_path(value.get("relativePath"), layer=layer)
        order, size, digest = value.get("order"), value.get("bytes"), value.get("sha256")
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
        archives.append(VerifiedOverlayArchive(
            relative_path=relative_path,
            layer=layer,
            order=order,
            size=size,
            sha256=digest,
        ))
        info = infos.get(relative_path)
        if info is None or info.file_size != size:
            raise _error("WFREL_OVERLAY_INVALID", "archive size does not match manifest")
        try:
            with bundle.open(info, "r") as source, tempfile.TemporaryFile(mode="w+b") as staged:
                actual_size, actual_digest = _stream_copy_hash(source, staged)
                if actual_size != size or actual_digest != digest:
                    raise _error("WFREL_OVERLAY_INVALID", "archive digest does not match manifest")
                _verify_inner(staged, archive_name=archive_name)
        except ReleaseError:
            raise
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise _error("WFREL_OVERLAY_INVALID", "archive payload is corrupt") from error
    for layer, orders in layers.items():
        if not orders or sorted(orders) != list(range(1, len(orders) + 1)):
            raise _error("WFREL_OVERLAY_INVALID", "Overlay layer orders are not contiguous", layer=layer)
    if set(infos) != _METADATA | declared:
        raise _error("WFREL_OVERLAY_INVALID", "Overlay member set does not match manifest")
    if edge_from is None or not isinstance(target, str):
        raise _error("WFREL_OVERLAY_INVALID", "Overlay edge is incomplete")
    ordered = tuple(sorted(
        archives,
        key=lambda item: (_LAYERS.index(item.layer), item.order, item.relative_path),
    ))
    return VerifiedOverlayEdge(edge_from, target, ordered)


def _verify_overlay(path: Path) -> _Edge:
    archive_name = path.name or "overlay.zip"
    try:
        with path.open("rb") as raw_stream:
            _central_preflight(raw_stream, archive_name=archive_name)
        with zipfile.ZipFile(path, "r", allowZip64=True) as bundle:
            infos_list = bundle.infolist()
            _limits(infos_list, archive_name=archive_name)
            seen: set[str] = set()
            infos: dict[str, zipfile.ZipInfo] = {}
            for info in infos_list:
                name = _safe_name(info, seen, archive_name=archive_name)
                infos[name] = info
            if not _METADATA.issubset(infos):
                raise _error("WFREL_OVERLAY_INVALID", "Overlay metadata is incomplete", archiveName=archive_name)
            if not infos_list or infos_list[-1].filename != "patch-manifest.json":
                raise _error("WFREL_OVERLAY_INVALID", "patch-manifest.json must be last", archiveName=archive_name)
            _read_small(bundle, infos["README.md"], archive_name=archive_name)
            requires_raw = _read_small(bundle, infos["requires.json"], archive_name=archive_name)
            requires = load_json_strict_bytes(requires_raw, label="requires.json")
            if not isinstance(requires, Mapping):
                raise _error("WFREL_OVERLAY_INVALID", "Overlay requirements must be an object", archiveName=archive_name)
            manifest_raw = _read_small(bundle, infos["patch-manifest.json"], archive_name=archive_name)
            manifest = load_json_strict_bytes(manifest_raw, label="patch-manifest.json")
            facts = _manifest_edge(bundle, infos, manifest, archive_name=archive_name)
    except ReleaseError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _error("WFREL_OVERLAY_INVALID", "outer Overlay ZIP is unreadable", archiveName=archive_name) from error
    return _Edge(path, facts)


def inspect_overlay_chain(paths: Sequence[Path]) -> VerifiedOverlayChain:
    """Verify explicit private Overlay copies and return detached chain facts."""
    if not paths:
        raise _error("WFREL_OVERLAY_INVALID", "at least one Overlay is required")
    edges = [_verify_overlay(Path(path)) for path in paths]
    outgoing: dict[str, _Edge] = {}
    incoming: dict[str, _Edge] = {}
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        key = (edge.from_version, edge.target_version)
        if (
            key in seen_edges or edge.from_version in outgoing or edge.target_version in incoming
            or _version(edge.from_version, label="fromVersion") >= _version(edge.target_version, label="targetVersion")
        ):
            raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph is not a unique increasing chain")
        seen_edges.add(key)
        outgoing[edge.from_version] = edge
        incoming[edge.target_version] = edge
    heads = set(outgoing) - set(incoming)
    tails = set(incoming) - set(outgoing)
    if len(heads) != 1 or len(tails) != 1:
        raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph has no unique head and tail")
    current = next(iter(heads))
    head = current
    visited: set[tuple[str, str]] = set()
    ordered: list[VerifiedOverlayEdge] = []
    while current in outgoing:
        edge = outgoing[current]
        visited.add((edge.from_version, edge.target_version))
        ordered.append(edge.facts)
        current = edge.target_version
    if len(visited) != len(edges) or current not in tails:
        raise _error("WFREL_OVERLAY_GRAPH", "Patch Overlay graph is disconnected")
    return VerifiedOverlayChain(head, current, tuple(ordered))


def verify_overlay_chain(paths: Sequence[Path]) -> str:
    """Independently verify explicit private Overlay copies and return the chain tail."""
    return inspect_overlay_chain(paths).target_version


__all__ = [
    "VerifiedOverlayArchive",
    "VerifiedOverlayChain",
    "VerifiedOverlayEdge",
    "inspect_overlay_chain",
    "verify_overlay_chain",
]
