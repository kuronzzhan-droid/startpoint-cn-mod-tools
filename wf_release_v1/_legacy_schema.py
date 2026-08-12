"""Strict metadata contracts for the two supported legacy wfshare dialects."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final, Mapping, Sequence

from .canonical import normalize_relative_path
from .errors import ReleaseError
from ._legacy_zip import error


_JS_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_VERSION: Final = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
ARCHIVE_PATTERN: Final = re.compile(
    r"archive-(common|medium|android)-diff/"
    r"pinball-((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))-"
    r"((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))-"
    r"([1-9][0-9]*)-([^/]+)\.zip"
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_DETAIL_KEYS: Final = {
    "officialBaseline",
    "revertedRows",
    "restoredRows",
    "revertedTables",
    "droppedEntries",
    "note",
    "serverSideEnhancements",
}
_REQUIREMENT_KEYS: Final = {
    "serverRestart",
    "restartReasons",
    "minServerVersion",
    "serverFeatures",
    "clientPatches",
}
_ENHANCEMENT_KEYS: Final = {"file", "row", "field", "ours", "official", "note"}
_CONTENT_SUMMARY_KEYS: Final = {
    "entries",
    "kept",
    "dropped",
    "rebuilt",
    "revertedRows",
    "restoredRows",
    "nestedExtendedRows",
    "droppedLogicals",
    "rebuiltTables",
    "unrecognizedAdditions",
}


@dataclass(frozen=True)
class ArchiveSpec:
    path: str
    layer: str
    from_version: str
    target_version: str
    sequence: int
    tag: str
    entries: int | None = None
    size: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class ShareMetadata:
    dialect: str
    variant: str
    enhancement: bool
    from_version: str
    target_version: str
    archives: tuple[ArchiveSpec, ...]
    report_entries: int | None


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise error(f"{label} must be an object")
    return value


def _exact(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise error(f"{label} fields are invalid")


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or any(ord(character) < 0x20 for character in value):
        raise error(f"{label} must be a non-empty string")
    return value


def _integer(value: object, *, label: str, positive: bool = False) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < (1 if positive else 0)
        or value > _JS_MAX_SAFE_INTEGER
    ):
        raise error(f"{label} must be a canonical integer")
    return value


def version(value: object, *, label: str) -> tuple[int, int, int]:
    raw = _string(value, label=label)
    match = _VERSION.fullmatch(raw)
    if match is None:
        raise error(f"{label} is invalid")
    parsed = tuple(int(part) for part in match.groups())
    if any(part > _JS_MAX_SAFE_INTEGER for part in parsed):
        raise error(f"{label} is invalid")
    return parsed  # type: ignore[return-value]


def _strings(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise error(f"{label} must be an array")
    result = tuple(_string(item, label=f"{label} item") for item in value)
    if len(set(result)) != len(result):
        raise error(f"{label} contains duplicates")
    return result


def _requirements(value: object) -> None:
    document = _mapping(value, label="requires")
    expected = set(_REQUIREMENT_KEYS)
    if "serverDataNote" in document:
        expected.add("serverDataNote")
    _exact(document, expected, label="requires")
    restart = document["serverRestart"]
    if not isinstance(restart, bool):
        raise error("requires.serverRestart must be boolean")
    reasons = _strings(document["restartReasons"], label="requires.restartReasons")
    minimum = document["minServerVersion"]
    if minimum is not None:
        _string(minimum, label="requires.minServerVersion")
    _strings(document["serverFeatures"], label="requires.serverFeatures")
    _strings(document["clientPatches"], label="requires.clientPatches")
    if restart != ("serverDataNote" in document) or bool(reasons) != restart:
        raise error("requires restart fields are inconsistent")
    if restart:
        _string(document["serverDataNote"], label="requires.serverDataNote")


def _variant_detail(value: object, *, variant: str) -> None:
    detail = _mapping(value, label="enhancementDetail")
    _exact(detail, _DETAIL_KEYS, label="enhancementDetail")
    baseline = detail["officialBaseline"]
    if variant == "content-only":
        version(baseline, label="enhancementDetail.officialBaseline")
    elif baseline is not None:
        raise error("full enhancement baseline must be null")
    for field in ("revertedRows", "restoredRows"):
        count = _integer(detail[field], label=f"enhancementDetail.{field}")
        if variant == "full" and count != 0:
            raise error("full enhancement counts must be zero")
    for field in ("revertedTables", "droppedEntries"):
        values = _strings(detail[field], label=f"enhancementDetail.{field}")
        if variant == "full" and values:
            raise error("full enhancement lists must be empty")
    _string(detail["note"], label="enhancementDetail.note")
    enhancements = detail["serverSideEnhancements"]
    if not isinstance(enhancements, list):
        raise error("serverSideEnhancements must be an array")
    if variant == "full" and enhancements:
        raise error("full serverSideEnhancements must be empty")
    for index, value in enumerate(enhancements):
        item = _mapping(value, label=f"serverSideEnhancements[{index}]")
        _exact(item, _ENHANCEMENT_KEYS, label=f"serverSideEnhancements[{index}]")
        for field in _ENHANCEMENT_KEYS:
            _string(item[field], label=f"serverSideEnhancements[{index}].{field}")


def _archive_path(value: object) -> ArchiveSpec:
    raw = _string(value, label="archive path")
    try:
        normalized = normalize_relative_path(raw)
    except ReleaseError as exc:
        raise error("archive path is invalid") from exc
    if normalized != raw:
        raise error("archive path is invalid")
    match = ARCHIVE_PATTERN.fullmatch(raw)
    if match is None:
        raise error("archive path is invalid")
    layer, from_version, target_version, sequence, tag = match.groups()
    version(from_version, label="archive from version")
    version(target_version, label="archive target version")
    return ArchiveSpec(raw, layer, from_version, target_version, int(sequence), tag)


def _validate_parts(archives: Sequence[ArchiveSpec], *, one_edge: bool) -> None:
    if not archives:
        raise error("legacy share has no content archives")
    groups: dict[tuple[str, str, str], list[int]] = {}
    for archive in archives:
        if version(archive.from_version, label="archive from") >= version(
            archive.target_version, label="archive target"
        ):
            raise error("legacy content edge must increase")
        groups.setdefault(
            (archive.from_version, archive.target_version, archive.layer), []
        ).append(archive.sequence)
    for key, sequences in groups.items():
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            raise error("legacy content archive parts are not contiguous", group=key)
    if one_edge and len({(item.from_version, item.target_version) for item in archives}) != 1:
        raise error("variant share must describe exactly one edge")


def _parse_summary(summary_value: object, *, variant: str, report_entries: int) -> None:
    summary = _mapping(summary_value, label="report.summary")
    expected = {"entries", "kept", "dropped", "rebuilt"}
    if variant == "content-only":
        expected = set(_CONTENT_SUMMARY_KEYS)
    _exact(summary, expected, label="report.summary")
    entries = _integer(summary["entries"], label="report.summary.entries")
    kept = _integer(summary["kept"], label="report.summary.kept")
    dropped = _integer(summary["dropped"], label="report.summary.dropped")
    rebuilt = _integer(summary["rebuilt"], label="report.summary.rebuilt")
    if variant == "full":
        if (entries, kept, dropped, rebuilt) != (report_entries, report_entries, 0, 0):
            raise error("full report summary arithmetic is invalid")
        return
    if entries != kept + dropped + rebuilt or report_entries != kept + rebuilt:
        raise error("content-only report summary arithmetic is invalid")
    reverted_rows = _integer(summary["revertedRows"], label="report.summary.revertedRows")
    restored_rows = _integer(summary["restoredRows"], label="report.summary.restoredRows")
    nested_rows = _integer(
        summary["nestedExtendedRows"], label="report.summary.nestedExtendedRows"
    )
    dropped_logicals = _strings(
        summary["droppedLogicals"], label="report.summary.droppedLogicals"
    )
    tables = summary["rebuiltTables"]
    if not isinstance(tables, list):
        raise error("report.summary.rebuiltTables must be an array")
    table_logicals: list[str] = []
    table_totals = {"reverted": 0, "restored": 0, "nestedExtended": 0}
    for index, value in enumerate(tables):
        item = _mapping(value, label=f"rebuiltTables[{index}]")
        _exact(item, {"logical", "reverted", "restored", "nestedExtended", "kept"}, label="rebuilt table")
        table_logicals.append(_string(item["logical"], label="rebuilt table logical"))
        for field in ("reverted", "restored", "nestedExtended", "kept"):
            count = _integer(item[field], label=f"rebuilt table {field}")
            if field in table_totals:
                table_totals[field] += count
    if len(set(table_logicals)) != len(table_logicals):
        raise error("report.summary.rebuiltTables contains duplicate logicals")
    # The producer may count rebuilt non-table assets without a rebuiltTables row,
    # and may count nested additions in unchanged tables.  The remaining totals
    # are exact projections of the detailed table rows.
    if (
        len(tables) > rebuilt
        or len(dropped_logicals) != dropped
        or table_totals["reverted"] != reverted_rows
        or table_totals["restored"] != restored_rows
        or table_totals["nestedExtended"] > nested_rows
    ):
        raise error("content-only report detail totals are inconsistent")
    additions = _mapping(summary["unrecognizedAdditions"], label="unrecognizedAdditions")
    for key, value in additions.items():
        _string(key, label="unrecognizedAdditions key")
        if not _strings(value, label="unrecognizedAdditions rows"):
            raise error("unrecognizedAdditions rows must not be empty")


def _parse_variant(pack: Mapping[str, object], report_value: object) -> ShareMetadata:
    _exact(pack, {"variant", "since", "tail", "sourceEdges", "anchor", "archives"}, label="pack")
    variant = _string(pack["variant"], label="pack.variant")
    if variant not in {"full", "content-only"}:
        raise error("legacy share variant is invalid")
    since = _string(pack["since"], label="pack.since")
    tail = _string(pack["tail"], label="pack.tail")
    if version(since, label="pack.since") > version(tail, label="pack.tail"):
        raise error("pack source chain is decreasing")
    _integer(pack["sourceEdges"], label="pack.sourceEdges", positive=True)
    anchor = _mapping(pack["anchor"], label="pack.anchor")
    _exact(anchor, {"from", "to"}, label="pack.anchor")
    from_version = _string(anchor["from"], label="pack.anchor.from")
    target_version = _string(anchor["to"], label="pack.anchor.to")
    if version(from_version, label="pack.anchor.from") >= version(target_version, label="pack.anchor.to"):
        raise error("pack anchor must increase")
    paths = pack["archives"]
    if not isinstance(paths, list) or not paths:
        raise error("pack.archives must be a non-empty array")
    archives = tuple(_archive_path(item) for item in paths)
    if len({item.path.casefold() for item in archives}) != len(archives):
        raise error("pack.archives contains duplicates")
    _validate_parts(archives, one_edge=True)
    if any((item.from_version, item.target_version) != (from_version, target_version) for item in archives):
        raise error("archive edges do not match pack anchor")

    report = _mapping(report_value, label="report.json")
    _exact(report, {"variant", "tag", "pack", "entries", "summary", "outputs"}, label="report.json")
    tag = _string(report["tag"], label="report.tag")
    if not tag.isalnum() or not tag.islower():
        raise error("variant report tag is invalid")
    if report["variant"] != variant or any(item.tag != tag for item in archives):
        raise error("report variant or tag does not match requirements")
    expected_pack = f"wfshare-{from_version}-to-{target_version}-{variant}"
    if report["pack"] != expected_pack:
        raise error("report pack name is invalid")
    report_entries = _integer(report["entries"], label="report.entries")
    _parse_summary(report["summary"], variant=variant, report_entries=report_entries)
    outputs = report["outputs"]
    if not isinstance(outputs, list) or len(outputs) != len(archives):
        raise error("archive declarations do not match report outputs")
    completed: list[ArchiveSpec] = []
    for declared, value in zip(archives, outputs, strict=True):
        item = _mapping(value, label="report output")
        _exact(item, {"root", "path", "entries", "size", "sha256"}, label="report output")
        digest = _string(item["sha256"], label="archive sha256")
        if item["path"] != declared.path or item["root"] != declared.layer or _SHA256.fullmatch(digest) is None:
            raise error("report output does not match archive declaration")
        completed.append(
            ArchiveSpec(
                declared.path,
                declared.layer,
                declared.from_version,
                declared.target_version,
                declared.sequence,
                declared.tag,
                _integer(item["entries"], label="archive entries", positive=True),
                _integer(item["size"], label="archive size", positive=True),
                digest,
            )
        )
    if sum(item.entries or 0 for item in completed) != report_entries:
        raise error("report entry total does not match archive outputs")
    return ShareMetadata(
        "variant-report", variant, variant == "full", from_version, target_version,
        tuple(completed), report_entries,
    )


def _parse_catalog(pack: Mapping[str, object], available_paths: Sequence[str]) -> ShareMetadata:
    _exact(pack, {"variant", "since", "tail", "edges"}, label="pack")
    if pack["variant"] != "full":
        raise error("catalog export variant must be full")
    since = _string(pack["since"], label="pack.since")
    tail = _string(pack["tail"], label="pack.tail")
    if version(since, label="pack.since") >= version(tail, label="pack.tail"):
        raise error("catalog export edge must increase")
    edge_count = _integer(pack["edges"], label="pack.edges", positive=True)
    archives = tuple(_archive_path(path) for path in available_paths)
    _validate_parts(archives, one_edge=False)
    edges = {(item.from_version, item.target_version) for item in archives}
    outgoing: dict[str, str] = {}
    incoming: dict[str, str] = {}
    for start, target in edges:
        if start in outgoing or target in incoming:
            raise error("catalog export graph is ambiguous")
        outgoing[start] = target
        incoming[target] = start
    heads = set(outgoing) - set(incoming)
    tails = set(incoming) - set(outgoing)
    if len(edges) != edge_count or heads != {since} or tails != {tail}:
        raise error("catalog export graph does not match pack")
    current = since
    visited = 0
    while current in outgoing:
        current = outgoing[current]
        visited += 1
    if current != tail or visited != len(edges):
        raise error("catalog export graph is disconnected")
    return ShareMetadata("catalog-export", "full", True, since, tail, archives, None)


def parse_metadata(
    requires_value: object,
    report_value: object | None,
    *,
    available_archive_paths: Sequence[str],
) -> ShareMetadata:
    document = _mapping(requires_value, label="requires.json")
    _exact(document, {"schemaVersion", "pack", "enhancement", "enhancementDetail", "requires"}, label="requires.json")
    if document["schemaVersion"] != 2 or not isinstance(document["enhancement"], bool):
        raise error("requires.json version or enhancement flag is invalid")
    pack = _mapping(document["pack"], label="pack")
    _requirements(document["requires"])
    if set(pack) == {"variant", "since", "tail", "edges"}:
        if report_value is not None or document["enhancement"] is not True:
            raise error("catalog export metadata is inconsistent")
        detail = _mapping(document["enhancementDetail"], label="enhancementDetail")
        _exact(detail, {"note"}, label="enhancementDetail")
        _string(detail["note"], label="enhancementDetail.note")
        return _parse_catalog(pack, available_archive_paths)
    metadata = _parse_variant(pack, report_value)
    if document["enhancement"] != metadata.enhancement:
        raise error("enhancement flag does not match variant")
    _variant_detail(document["enhancementDetail"], variant=metadata.variant)
    if metadata.variant == "content-only":
        detail = _mapping(document["enhancementDetail"], label="enhancementDetail")
        report = _mapping(report_value, label="report.json")
        summary = _mapping(report["summary"], label="report.summary")
        expected_tables = [
            _mapping(item, label="rebuilt table")["logical"]
            for item in summary["rebuiltTables"]  # type: ignore[union-attr]
        ]
        if (
            detail["revertedRows"] != summary["revertedRows"]
            or detail["restoredRows"] != summary["restoredRows"]
            or detail["revertedTables"] != expected_tables
            or detail["droppedEntries"] != summary["droppedLogicals"]
        ):
            raise error("content-only enhancement detail does not match report summary")
    declared = {item.path.casefold() for item in metadata.archives}
    available = {path.casefold() for path in available_archive_paths}
    if declared != available or len(declared) != len(available_archive_paths):
        raise error("archive declarations do not match package members")
    return metadata


__all__ = ["ARCHIVE_PATTERN", "ArchiveSpec", "ShareMetadata", "parse_metadata", "version"]
