"""Strict read-only inspection of one explicitly configured legacy target."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Final, Protocol
import zipfile

from ._legacy_zip import central_preflight, copy_member, validate_infos
from ._platform_state import ManagedProcess
from .canonical import canonical_json_bytes
from .errors import ReleaseError
from .target import ManagedTarget, TargetCompatibility


_LAYERS: Final = ("common", "medium", "android")
_REPARSE_POINT: Final = 0x0400
_JS_MAX_SAFE_INTEGER: Final = (1 << 53) - 1
_VERSION: Final = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
_ARCHIVE_NAME: Final = re.compile(
    rf"pinball-({_VERSION})-({_VERSION})-([1-9][0-9]*)-"
    r"([A-Za-z0-9][A-Za-z0-9._+-]*)\.zip"
)
_MAX_ARCHIVE_BYTES: Final = 16 * 1024 * 1024 * 1024


def _invalid(message: str, **details: object) -> ReleaseError:
    return ReleaseError("WFREL_LEGACY_TARGET_INVALID", message, details)


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        getattr(item, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _identity(item: os.stat_result) -> tuple[int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(_VERSION, value)
    if match is None:
        raise _invalid("legacy CDN version is not canonical")
    parsed = tuple(int(part) for part in match.groups())
    if any(part > _JS_MAX_SAFE_INTEGER for part in parsed):
        raise _invalid("legacy CDN version is outside the supported range")
    return parsed  # type: ignore[return-value]


def _directory(path: Path, label: str) -> None:
    try:
        item = path.lstat()
    except OSError:
        raise _invalid("legacy CDN layer is unavailable", layer=label) from None
    if _is_reparse(item) or not stat.S_ISDIR(item.st_mode):
        raise _invalid("legacy CDN layer is unavailable", layer=label)


def _parse_name(name: str) -> tuple[str, str, int, str]:
    if not name.isascii():
        raise _invalid("legacy CDN archive filename is not canonical", archiveName=name)
    match = _ARCHIVE_NAME.fullmatch(name)
    if match is None:
        raise _invalid("legacy CDN archive filename is not canonical", archiveName=name)
    start = match.group(1)
    end = match.group(5)
    sequence = int(match.group(9))
    tag = match.group(10)
    _version(start)
    _version(end)
    return start, end, sequence, tag


def _inspect_zip(path: Path, *, layer: str) -> tuple[int, str, tuple[int, int]]:
    try:
        before = path.lstat()
    except OSError:
        raise _invalid("legacy CDN archive is unavailable", layer=layer) from None
    if (
        _is_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_size <= 0
        or before.st_size > _MAX_ARCHIVE_BYTES
    ):
        raise _invalid("legacy CDN archive is unavailable", layer=layer)
    expected = _identity(before)
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode) or _identity(opened) != expected:
            raise OSError("archive identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            digest = hashlib.sha256()
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            stream.seek(0)
            central_preflight(stream)
            with zipfile.ZipFile(stream) as bundle:
                members = validate_infos(bundle.infolist(), allow_directories=False)
                for _name, info in members:
                    copy_member(bundle, info)
            opened_after = _identity(os.fstat(stream.fileno()))
        after = path.lstat()
    except ReleaseError as error:
        if error.code == "WFREL_LEGACY_TARGET_INVALID":
            raise
        raise _invalid("legacy CDN archive is invalid", layer=layer) from error
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
        raise _invalid("legacy CDN archive is invalid", layer=layer) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if _is_reparse(after) or opened_after != expected or _identity(after) != expected:
        raise _invalid("legacy CDN archive changed while it was read", layer=layer)
    return expected[2], digest.hexdigest(), expected[:2]


@dataclass(frozen=True)
class LegacyArchiveFacts:
    relative_path: str
    from_version: str
    target_version: str
    sequence: int
    tag: str
    size: int
    sha256: str
    _object_identity: tuple[int, int] = field(repr=False, compare=False)


@dataclass(frozen=True)
class LegacyLayerFacts:
    layer: str
    archives: tuple[LegacyArchiveFacts, ...]
    sha256: str


class LegacyProcessStatus(str, Enum):
    OWNED_RUNNING = "owned-running"
    NOT_OWNED = "not-owned"


@dataclass(frozen=True)
class LegacyTargetFacts:
    chain_tail: str
    layers: tuple[LegacyLayerFacts, ...]
    compatibility: TargetCompatibility
    process_status: LegacyProcessStatus
    preview_only_reasons: tuple[str, ...]


class _ProcessReader(Protocol):
    def current_process(self) -> ManagedProcess | None: ...


def _layer_digest(layer: str, archives: Sequence[LegacyArchiveFacts]) -> str:
    value = {
        "layer": layer,
        "archives": [
            {
                "relativePath": item.relative_path,
                "bytes": item.size,
                "sha256": item.sha256,
            }
            for item in archives
        ],
    }
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _inspect_layer(
    cn_root: Path,
    layer: str,
    seen_objects: set[tuple[int, int]],
) -> LegacyLayerFacts:
    directory = cn_root / f"archive-{layer}-diff"
    _directory(directory, layer)
    try:
        before_entries = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    except OSError:
        raise _invalid("legacy CDN layer is unavailable", layer=layer) from None
    folded: set[str] = set()
    archives: list[LegacyArchiveFacts] = []
    for path in before_entries:
        if path.name.casefold() in folded:
            raise _invalid("legacy CDN archive names are ambiguous", layer=layer)
        folded.add(path.name.casefold())
        start, end, sequence, tag = _parse_name(path.name)
        size, digest, object_identity = _inspect_zip(path, layer=layer)
        if object_identity in seen_objects:
            raise _invalid("legacy CDN archive object is duplicated", layer=layer)
        seen_objects.add(object_identity)
        archives.append(LegacyArchiveFacts(
            relative_path=f"archive-{layer}-diff/{path.name}",
            from_version=start,
            target_version=end,
            sequence=sequence,
            tag=tag,
            size=size,
            sha256=digest,
            _object_identity=object_identity,
        ))
    try:
        after_names = tuple(sorted(item.name for item in directory.iterdir()))
    except OSError:
        raise _invalid("legacy CDN layer changed while it was read", layer=layer) from None
    if tuple(item.name for item in before_entries) != after_names:
        raise _invalid("legacy CDN layer changed while it was read", layer=layer)
    ordered = tuple(sorted(
        archives,
        key=lambda item: (
            _version(item.from_version), _version(item.target_version), item.sequence, item.tag,
        ),
    ))
    return LegacyLayerFacts(layer, ordered, _layer_digest(layer, ordered))


def _descriptor(layer: LegacyLayerFacts) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (item.from_version, item.target_version, item.sequence)
        for item in layer.archives
    )


def _chain_tail(
    layers: tuple[LegacyLayerFacts, ...],
    baseline: str,
) -> str:
    descriptors = tuple(_descriptor(layer) for layer in layers)
    if any(value != descriptors[0] for value in descriptors[1:]):
        raise _invalid("legacy CDN layers do not describe the same archive set")
    if not descriptors[0]:
        return baseline
    by_edge: dict[tuple[str, str], list[int]] = {}
    for start, end, sequence in descriptors[0]:
        if _version(start) >= _version(end):
            raise _invalid("legacy CDN versions must increase")
        by_edge.setdefault((start, end), []).append(sequence)
    for parts in by_edge.values():
        sequences = sorted(parts)
        if sequences != list(range(1, len(parts) + 1)):
            raise _invalid("legacy CDN edge parts are not contiguous")
    outgoing: dict[str, str] = {}
    incoming: dict[str, str] = {}
    for start, end in by_edge:
        if start in outgoing or end in incoming:
            raise _invalid("legacy CDN graph forks or merges")
        outgoing[start] = end
        incoming[end] = start
    heads = set(outgoing) - set(incoming)
    tails = set(incoming) - set(outgoing)
    if len(heads) != 1 or len(tails) != 1:
        raise _invalid("legacy CDN graph has no unique chain")
    head = next(iter(heads))
    if head != baseline:
        raise _invalid("legacy CDN chain does not start at the resource baseline")
    visited: set[tuple[str, str]] = set()
    current = head
    while current in outgoing:
        edge = current, outgoing[current]
        if edge in visited:
            raise _invalid("legacy CDN graph contains a cycle")
        visited.add(edge)
        current = edge[1]
    if len(visited) != len(by_edge) or current not in tails:
        raise _invalid("legacy CDN graph is disconnected")
    return current


def inspect_legacy_target(
    target: ManagedTarget,
    platform: _ProcessReader,
) -> LegacyTargetFacts:
    """Inspect exact local legacy facts without writing target state."""
    if not isinstance(target, ManagedTarget) or not callable(
        getattr(platform, "current_process", None)
    ):
        raise _invalid("legacy target inspection input is invalid")
    cn_root = target.cdn_root / "cn"
    _directory(cn_root, "cn")
    seen_objects: set[tuple[int, int]] = set()
    layers = tuple(_inspect_layer(cn_root, layer, seen_objects) for layer in _LAYERS)
    tail = _chain_tail(layers, target.compatibility.resource_baseline)
    process = platform.current_process()
    if process is not None and not isinstance(process, ManagedProcess):
        raise _invalid("managed process status is invalid")
    status = (
        LegacyProcessStatus.OWNED_RUNNING
        if process is not None
        else LegacyProcessStatus.NOT_OWNED
    )
    reasons = () if process is not None else ("WFREL_LEGACY_PROCESS_NOT_OWNED",)
    return LegacyTargetFacts(
        chain_tail=tail,
        layers=layers,
        compatibility=target.compatibility,
        process_status=status,
        preview_only_reasons=reasons,
    )


__all__ = [
    "LegacyArchiveFacts",
    "LegacyLayerFacts",
    "LegacyProcessStatus",
    "LegacyTargetFacts",
    "inspect_legacy_target",
]
