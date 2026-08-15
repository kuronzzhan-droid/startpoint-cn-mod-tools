"""Strict read-only resolution of the active modern Content Snapshot graph."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
import stat
from pathlib import Path
from typing import Final

from wf_character_pack import logical_path_problem
from wf_offline_store import (
    StoreError,
    _checked_lstat,
    _require_same_lstat,
    _stable_reader,
    _stat_signature,
)

from .canonical import canonical_json_bytes, load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError
from .target import ManagedTarget


_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_VERSION: Final = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)
_LAYERS: Final = {"common": 0, "quality": 1, "platform": 2}
_JSON_LIMIT: Final = 16 * 1024 * 1024


@dataclass(frozen=True)
class JsonSnapshot:
    path: Path
    raw: bytes
    signature: tuple[int, ...]
    guards: tuple[tuple[Path, tuple[int, ...], str], ...]


@dataclass(frozen=True)
class ArchiveDescriptor:
    relative_path: str
    compressed_bytes: int
    sha256: str
    layer: str
    order: int
    source_kind: str
    source_target_version: str | None


@dataclass(frozen=True)
class SnapshotAuthority:
    asset_version: str
    release_digest: str
    archives: tuple[ArchiveDescriptor, ...]
    evidence: tuple[JsonSnapshot, ...]


def _unavailable(message: str, *, label: str) -> ReleaseError:
    return ReleaseError(
        "WFREL_ASSET_BASELINE_UNAVAILABLE",
        message,
        {"label": label},
    )


def _exact(value: object, keys: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise _unavailable("Content Snapshot fields are invalid", label=label)
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _unavailable("Content Snapshot string is invalid", label=label)
    return value


def _integer(value: object, label: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise _unavailable("Content Snapshot integer is invalid", label=label)
    return value


def _version(value: object, label: str) -> str:
    result = _string(value, label)
    if _VERSION.fullmatch(result) is None:
        raise _unavailable("Content Snapshot version is invalid", label=label)
    return result


def _digest(value: object, label: str) -> str:
    result = _string(value, label)
    if _DIGEST.fullmatch(result) is None:
        raise _unavailable("Content Snapshot digest is invalid", label=label)
    return result


def _sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if _SHA256.fullmatch(result) is None:
        raise _unavailable("Content archive digest is invalid", label=label)
    return result


def _safe_relative(value: object, label: str, *, ascii_only: bool = False) -> str:
    result = _string(value, label)
    try:
        result = normalize_relative_path(result)
    except ReleaseError as error:
        raise _unavailable("Content Snapshot path is unsafe", label=label) from error
    if logical_path_problem(result) is not None or (
        ascii_only and (
            any(not 0x21 <= ord(character) <= 0x7E for character in result)
            or any(character in result for character in ":?#%")
        )
    ):
        raise _unavailable("Content Snapshot path is not portable", label=label)
    return result


def _guard_file(
    root: Path,
    relative_path: str,
    *,
    label: str,
) -> tuple[Path, tuple[tuple[Path, tuple[int, ...], str], ...]]:
    candidate = root.joinpath(*relative_path.split("/"))
    guards: list[tuple[Path, tuple[int, ...], str]] = []
    current = root
    try:
        for index, segment in enumerate(("", *relative_path.split("/"))):
            if index:
                current /= segment
            kind = label if index == len(relative_path.split("/")) else f"{label} parent"
            metadata = _checked_lstat(current, kind=kind)
            leaf = index == len(relative_path.split("/"))
            if leaf and not stat.S_ISREG(metadata.st_mode):
                raise StoreError(f"{label} is not a regular file")
            if not leaf and not stat.S_ISDIR(metadata.st_mode):
                raise StoreError(f"{label} parent is not a directory")
            guards.append((current, _stat_signature(metadata), kind))
        physical_root = root.resolve(strict=True)
        physical_candidate = candidate.resolve(strict=True)
        physical_candidate.relative_to(physical_root)
    except (OSError, RuntimeError, StoreError, ValueError) as error:
        raise _unavailable("Content Snapshot file is unavailable", label=label) from error
    return candidate, tuple(guards)


def _read_json(root: Path, relative_path: str, *, label: str) -> tuple[object, JsonSnapshot]:
    path, guards = _guard_file(root, relative_path, label=label)
    signature = guards[-1][1]
    try:
        if signature[3] > _JSON_LIMIT:
            raise StoreError(f"{label} exceeds the size limit")
        with _stable_reader(path, signature, kind=label) as stream:
            raw = stream.read(_JSON_LIMIT + 1)
    except (OSError, StoreError) as error:
        raise _unavailable("Content Snapshot file cannot be read", label=label) from error
    if len(raw) > _JSON_LIMIT or len(raw) != signature[3]:
        raise _unavailable("Content Snapshot file changed while read", label=label)
    try:
        value = load_json_strict_bytes(raw, label=label)
        if canonical_json_bytes(value) != raw:
            raise _unavailable("Content Snapshot JSON is not canonical", label=label)
    except ReleaseError as error:
        if error.code == "WFREL_ASSET_BASELINE_UNAVAILABLE":
            raise
        raise _unavailable("Content Snapshot JSON is invalid", label=label) from error
    return value, JsonSnapshot(path, raw, signature, guards)


def assert_unchanged(snapshot: JsonSnapshot) -> None:
    try:
        for path, signature, kind in snapshot.guards:
            _require_same_lstat(path, signature, kind=kind)
    except StoreError as error:
        raise _unavailable(
            "Content Snapshot authority changed during verification",
            label=snapshot.path.name,
        ) from error


def _object(
    store_root: Path,
    reference: object,
    *,
    label: str,
) -> tuple[object, JsonSnapshot]:
    item = _exact(reference, frozenset({"object"}), label)
    identity = _digest(item["object"], f"{label}.object")
    value, snapshot = _read_json(
        store_root,
        f"objects/{identity.removeprefix('sha256:')}.json",
        label=label,
    )
    if "sha256:" + hashlib.sha256(snapshot.raw).hexdigest() != identity:
        raise _unavailable("Content object identity does not match", label=label)
    return value, snapshot


def _release_manifest(
    value: object,
    *,
    asset_version: str,
    path_digest: str,
) -> tuple[str, Mapping[str, object], object, object]:
    item = _exact(value, frozenset({
        "schemaVersion", "assetVersion", "runtimeSchemaVersion",
        "generatorVersion", "releaseDigest", "tables", "catalog", "summary",
    }), "release manifest")
    if item["schemaVersion"] != 1 or item["runtimeSchemaVersion"] != 1:
        raise _unavailable("Content release schema is unsupported", label="release manifest")
    if _version(item["assetVersion"], "release.assetVersion") != asset_version:
        raise _unavailable("Content release version disagrees with pointer", label="release manifest")
    _integer(item["generatorVersion"], "release.generatorVersion", positive=True)
    release_digest = _digest(item["releaseDigest"], "release.releaseDigest")
    if release_digest.removeprefix("sha256:") != path_digest:
        raise _unavailable("Content release path identity disagrees", label="release manifest")
    tables = item["tables"]
    if not isinstance(tables, Mapping) or not tables:
        raise _unavailable("Content release tables are invalid", label="release.tables")
    for name, raw in tables.items():
        _safe_relative(name, "release.tables name")
        table = _exact(raw, frozenset({
            "object", "scope", "converterId", "converterVersion", "sources",
        }), f"release.tables.{name}")
        _digest(table["object"], f"release.tables.{name}.object")
        if table["scope"] not in {"cdn", "bundled", "server"}:
            raise _unavailable("Content table scope is invalid", label=f"release.tables.{name}")
        _string(table["converterId"], f"release.tables.{name}.converterId")
        _integer(table["converterVersion"], f"release.tables.{name}.converterVersion", positive=True)
        if not isinstance(table["sources"], list):
            raise _unavailable("Content table sources are invalid", label=f"release.tables.{name}")
    body = dict(item)
    del body["releaseDigest"]
    computed = "sha256:" + hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    if computed != release_digest:
        raise _unavailable("Content release identity does not match", label="release manifest")
    return release_digest, item, item["catalog"], item["summary"]


def _catalog(value: object, asset_version: str) -> tuple[
    Mapping[str, object], tuple[Mapping[str, object], ...], dict[str, Mapping[str, object]]
]:
    catalog = _exact(value, frozenset({
        "edges", "entityListsRelativePath", "fullBaseVersion",
        "installedBytes", "schemaVersion", "targetVersion",
    }), "catalog")
    if catalog["schemaVersion"] != 1:
        raise _unavailable("Catalog schema is unsupported", label="catalog.schemaVersion")
    base = _version(catalog["fullBaseVersion"], "catalog.fullBaseVersion")
    if _version(catalog["targetVersion"], "catalog.targetVersion") != asset_version:
        raise _unavailable("Catalog target disagrees with active version", label="catalog.targetVersion")
    _integer(catalog["installedBytes"], "catalog.installedBytes")
    _safe_relative(catalog["entityListsRelativePath"], "catalog.entityListsRelativePath")
    raw_edges = catalog["edges"]
    if not isinstance(raw_edges, list) or not raw_edges:
        raise _unavailable("Catalog edges are invalid", label="catalog.edges")
    edges: list[Mapping[str, object]] = []
    by_path: dict[str, Mapping[str, object]] = {}
    for edge_index, raw_edge in enumerate(raw_edges):
        edge = _exact(raw_edge, frozenset({
            "archives", "assetSizeKind", "fromVersion", "platform", "toVersion",
        }), f"catalog.edges[{edge_index}]")
        if edge["platform"] != "android" or edge["assetSizeKind"] not in {"shortened", "fulfill"}:
            raise _unavailable("Catalog edge scope is invalid", label=f"catalog.edges[{edge_index}]")
        if edge["fromVersion"] is not None:
            _version(edge["fromVersion"], f"catalog.edges[{edge_index}].fromVersion")
        _version(edge["toVersion"], f"catalog.edges[{edge_index}].toVersion")
        archives = edge["archives"]
        if not isinstance(archives, list) or not archives:
            raise _unavailable("Catalog edge archives are invalid", label=f"catalog.edges[{edge_index}].archives")
        parsed_archives: list[Mapping[str, object]] = []
        for archive_index, raw_archive in enumerate(archives):
            label = f"catalog.edges[{edge_index}].archives[{archive_index}]"
            archive = _exact(raw_archive, frozenset({
                "compressedBytes", "layer", "order", "relativePath", "sha256",
            }), label)
            path = _safe_relative(archive["relativePath"], f"{label}.relativePath", ascii_only=True)
            _integer(archive["compressedBytes"], f"{label}.compressedBytes", positive=True)
            _sha256(archive["sha256"], f"{label}.sha256")
            if archive["layer"] not in _LAYERS:
                raise _unavailable("Catalog archive layer is invalid", label=f"{label}.layer")
            _integer(archive["order"], f"{label}.order", positive=True)
            if path in by_path and by_path[path] != archive:
                raise _unavailable("Catalog archive path has conflicting identities", label=label)
            by_path[path] = archive
            parsed_archives.append(archive)
        expected = sorted(parsed_archives, key=lambda archive: (
            _LAYERS[str(archive["layer"])], int(archive["order"]), str(archive["relativePath"]),
        ))
        if parsed_archives != expected:
            raise _unavailable("Catalog archives are not canonically ordered", label=f"catalog.edges[{edge_index}].archives")
        for layer in _LAYERS:
            orders = [int(item["order"]) for item in parsed_archives if item["layer"] == layer]
            if orders and orders != list(range(1, len(orders) + 1)):
                raise _unavailable("Catalog archive orders are not contiguous", label=f"catalog.edges[{edge_index}].archives")
        edges.append(edge)
    scoped = tuple(edge for edge in edges if edge["assetSizeKind"] == "fulfill")
    full = [edge for edge in scoped if edge["fromVersion"] is None]
    if len(full) != 1 or full[0]["toVersion"] != base:
        raise _unavailable("Catalog must have one exact fulfill full edge", label="catalog.edges")
    return catalog, scoped, by_path


def _selected_edges(
    catalog: Mapping[str, object],
    scoped: tuple[Mapping[str, object], ...],
) -> tuple[Mapping[str, object], ...]:
    full = next(edge for edge in scoped if edge["fromVersion"] is None)
    target = str(catalog["targetVersion"])
    diffs = tuple(edge for edge in scoped if edge["fromVersion"] is not None)
    start = str(full["toVersion"])
    adjacency: dict[str, list[tuple[Mapping[str, object], str]]] = {}
    for edge in diffs:
        adjacency.setdefault(str(edge["fromVersion"]), []).append(
            (edge, str(edge["toVersion"]))
        )

    reachable = {start}
    pending = [start]
    while pending:
        version = pending.pop()
        if version == target:
            continue
        for _edge, next_version in adjacency.get(version, ()):
            if next_version not in reachable:
                reachable.add(next_version)
                pending.append(next_version)

    indegree = {version: 0 for version in reachable}
    for version in reachable:
        if version == target:
            continue
        for _edge, next_version in adjacency.get(version, ()):
            indegree[next_version] += 1
    ready = deque(
        version for version, count in indegree.items() if count == 0
    )
    ordered: list[str] = []
    while ready:
        version = ready.popleft()
        ordered.append(version)
        if version == target:
            continue
        for _edge, next_version in adjacency.get(version, ()):
            indegree[next_version] -= 1
            if indegree[next_version] == 0:
                ready.append(next_version)
    if len(ordered) != len(reachable):
        raise _unavailable("Catalog does not have one unique fulfill path", label="catalog.edges")

    path_counts: dict[str, int] = {}
    for version in reversed(ordered):
        if version == target:
            path_counts[version] = 1
            continue
        count = sum(
            path_counts.get(next_version, 0)
            for _edge, next_version in adjacency.get(version, ())
        )
        path_counts[version] = min(count, 2)
    if path_counts.get(start) != 1:
        raise _unavailable("Catalog does not have one unique fulfill path", label="catalog.edges")

    selected: list[Mapping[str, object]] = []
    version = start
    while version != target:
        choices = tuple(
            (edge, next_version)
            for edge, next_version in adjacency.get(version, ())
            if path_counts.get(next_version, 0)
        )
        if len(choices) != 1:
            raise _unavailable(
                "Catalog does not have one unique fulfill path",
                label="catalog.edges",
            )
        edge, version = choices[0]
        selected.append(edge)
    return (full, *selected)


def _archive_sources(
    summary: object,
    *,
    asset_version: str,
    catalog: Mapping[str, object],
    by_path: Mapping[str, Mapping[str, object]],
    release_generator_version: int,
    release_table_count: int,
) -> dict[str, tuple[str, str | None]]:
    item = _exact(summary, frozenset({
        "archiveSources", "assetVersion", "counts", "entityListsRelativePath",
        "generatorVersion", "patchSourceDigest", "schemaVersion",
    }), "summary")
    if item["schemaVersion"] != 1 or _version(item["assetVersion"], "summary.assetVersion") != asset_version:
        raise _unavailable("Summary identity is invalid", label="summary")
    generator_version = _integer(
        item["generatorVersion"], "summary.generatorVersion", positive=True
    )
    if generator_version != release_generator_version:
        raise _unavailable(
            "Summary generator disagrees with release manifest",
            label="summary.generatorVersion",
        )
    _digest(item["patchSourceDigest"], "summary.patchSourceDigest")
    if item["entityListsRelativePath"] != catalog["entityListsRelativePath"]:
        raise _unavailable("Summary entity-list path disagrees", label="summary.entityListsRelativePath")
    counts = _exact(item["counts"], frozenset({"archives", "ignoredPaths", "tables"}), "summary.counts")
    for key in counts:
        _integer(counts[key], f"summary.counts.{key}")
    if counts["archives"] != len(by_path):
        raise _unavailable(
            "Summary archive count disagrees with catalog",
            label="summary.counts.archives",
        )
    if counts["tables"] != release_table_count:
        raise _unavailable(
            "Summary table count disagrees with release manifest",
            label="summary.counts.tables",
        )
    sources = _exact(item["archiveSources"], frozenset({"archives", "schemaVersion"}), "summary.archiveSources")
    if sources["schemaVersion"] != 1 or not isinstance(sources["archives"], list):
        raise _unavailable("Archive-source manifest is invalid", label="summary.archiveSources")
    expected_paths = list(by_path)
    actual_paths: list[str] = []
    result: dict[str, tuple[str, str | None]] = {}
    for index, raw in enumerate(sources["archives"]):
        entry = _exact(raw, frozenset({"relativePath", "source"}), f"summary.archiveSources.archives[{index}]")
        path = _safe_relative(entry["relativePath"], f"summary.archiveSources.archives[{index}].relativePath", ascii_only=True)
        source = entry["source"]
        if not isinstance(source, Mapping) or source.get("kind") not in {"baseline", "patch"}:
            raise _unavailable("Archive source is invalid", label=f"summary.archiveSources.archives[{index}].source")
        if source["kind"] == "baseline":
            _exact(source, frozenset({"kind"}), f"summary.archiveSources.archives[{index}].source")
            parsed = ("baseline", None)
        else:
            patch = _exact(source, frozenset({"kind", "targetVersion"}), f"summary.archiveSources.archives[{index}].source")
            parsed = ("patch", _version(patch["targetVersion"], f"summary.archiveSources.archives[{index}].source.targetVersion"))
        if path in result:
            raise _unavailable("Archive source is duplicated", label="summary.archiveSources")
        actual_paths.append(path)
        result[path] = parsed
    if actual_paths != expected_paths:
        raise _unavailable("Archive sources do not exactly cover catalog archives", label="summary.archiveSources")
    return result


def load_snapshot_authority(
    target: ManagedTarget,
    *,
    expected_version: str,
    expected_release_digest: str | None,
) -> SnapshotAuthority:
    state_root = target.data_root / "state" / "content"
    store_root = target.data_root / "content" / "store"
    current_value, current_snapshot = _read_json(state_root, "current.json", label="current pointer")
    current = _exact(current_value, frozenset({"assetVersion", "release", "schemaVersion"}), "current pointer")
    if current["schemaVersion"] != 1:
        raise _unavailable("Current pointer schema is unsupported", label="current pointer")
    asset_version = _version(current["assetVersion"], "current.assetVersion")
    if asset_version != expected_version:
        raise _unavailable("Current pointer version disagrees with release overlay", label="current.assetVersion")
    release_relative = _safe_relative(current["release"], "current.release")
    match = re.fullmatch(
        rf"releases/{re.escape(asset_version)}-([0-9a-f]{{64}})/manifest\.json",
        release_relative,
    )
    if match is None:
        raise _unavailable("Current release path is not canonical", label="current.release")
    release_value, release_snapshot = _read_json(store_root, release_relative, label="release manifest")
    release_digest, _release, catalog_ref, summary_ref = _release_manifest(
        release_value,
        asset_version=asset_version,
        path_digest=match.group(1),
    )
    if expected_release_digest is not None and expected_release_digest != release_digest:
        raise _unavailable("Live release digest disagrees with Content Snapshot", label="release.releaseDigest")
    catalog_value, catalog_snapshot = _object(store_root, catalog_ref, label="catalog object")
    summary_value, summary_snapshot = _object(store_root, summary_ref, label="summary object")
    catalog, scoped, by_path = _catalog(catalog_value, asset_version)
    release_tables = _release["tables"]
    if not isinstance(release_tables, Mapping):
        raise _unavailable(
            "Content release tables are invalid",
            label="release.tables",
        )
    sources = _archive_sources(
        summary_value,
        asset_version=asset_version,
        catalog=catalog,
        by_path=by_path,
        release_generator_version=_integer(
            _release["generatorVersion"],
            "release.generatorVersion",
            positive=True,
        ),
        release_table_count=len(release_tables),
    )
    selected = _selected_edges(catalog, scoped)
    archives: list[ArchiveDescriptor] = []
    for edge in selected:
        for raw in edge["archives"]:  # type: ignore[union-attr]
            path = str(raw["relativePath"])
            source_kind, source_version = sources[path]
            archives.append(ArchiveDescriptor(
                relative_path=path,
                compressed_bytes=int(raw["compressedBytes"]),
                sha256=str(raw["sha256"]),
                layer=str(raw["layer"]),
                order=int(raw["order"]),
                source_kind=source_kind,
                source_target_version=source_version,
            ))
    evidence = (current_snapshot, release_snapshot, catalog_snapshot, summary_snapshot)
    for snapshot in evidence:
        assert_unchanged(snapshot)
    return SnapshotAuthority(asset_version, release_digest, tuple(archives), evidence)


__all__ = [
    "ArchiveDescriptor",
    "JsonSnapshot",
    "SnapshotAuthority",
    "assert_unchanged",
    "load_snapshot_authority",
]
