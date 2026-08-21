"""Public independent verifier for wf-release-v1 archives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import tempfile
from typing import BinaryIO, Final

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .compatibility import VerifiedRelease
from .errors import ReleaseError
from .schema import (
    OwnershipManifest,
    ReleaseManifest,
    ReleaseRequirements,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)
from .verifier_overlay import VerifiedOverlayChain, inspect_overlay_chain
from .verifier_modes import verify_mode_component
from .verifier_zip import (
    ROOT,
    ZipMember,
    copy_hash_member,
    open_release,
    parse_classic_store,
    read_member,
)


_RELEASE: Final = ROOT + "release-manifest.json"
_REQUIRES: Final = ROOT + "requires.json"
_OWNERSHIP: Final = ROOT + "ownership.json"
_METADATA: Final = frozenset({_RELEASE, _REQUIRES, _OWNERSHIP})
_MAX_METADATA_BYTES: Final = 1024 * 1024
_CHARACTER_ENTITY: Final = re.compile(r"character:[1-9][0-9]*")


@dataclass(frozen=True)
class VerificationReport:
    release_id: str
    components: tuple[str, ...]
    file_count: int
    payload_bytes: int


def _error(code: str, message: str, **details: object) -> ReleaseError:
    return ReleaseError(code, message, details)


def _metadata(
    stream: BinaryIO,
    by_name: dict[str, ZipMember],
) -> tuple[ReleaseManifest, ReleaseRequirements, OwnershipManifest, dict[str, bytes]]:
    if not _METADATA.issubset(by_name):
        raise _error("WFREL_ARCHIVE_INVALID", "release metadata is incomplete", label="archive")
    raw = {
        name: read_member(stream, by_name[name], limit=_MAX_METADATA_BYTES)
        for name in _METADATA
    }
    release = parse_release_manifest(
        load_json_strict_bytes(raw[_RELEASE], label="release-manifest.json")
    )
    requirements = parse_requirements(
        load_json_strict_bytes(raw[_REQUIRES], label="requires.json")
    )
    ownership = parse_ownership(
        load_json_strict_bytes(raw[_OWNERSHIP], label="ownership.json")
    )
    if (
        raw[_RELEASE] != canonical_json_bytes(release.to_wire())
        or raw[_REQUIRES] != canonical_json_bytes(requirements.to_wire())
        or raw[_OWNERSHIP] != canonical_json_bytes(ownership.to_wire())
    ):
        raise _error("WFREL_ARCHIVE_INVALID", "release metadata is not canonical", label="metadata")
    return release, requirements, ownership, raw


def _exact_set(release: ReleaseManifest, by_name: dict[str, ZipMember]) -> None:
    expected = _METADATA | {f"{ROOT}{item.path}" for item in release.files}
    if set(by_name) != expected:
        raise _error("WFREL_ARCHIVE_INVALID", "archive member set does not match manifest", label="archive")


def _metadata_hashes(release: ReleaseManifest, raw: dict[str, bytes]) -> None:
    if (
        hashlib.sha256(raw[_REQUIRES]).hexdigest() != release.metadata_sha256.requires
        or hashlib.sha256(raw[_OWNERSHIP]).hexdigest() != release.metadata_sha256.ownership
    ):
        raise _error("WFREL_HASH_MISMATCH", "metadata digest does not match manifest", label="metadata")


def _payloads(
    stream: BinaryIO,
    release: ReleaseManifest,
    by_name: dict[str, ZipMember],
    staging: Path,
) -> tuple[int, dict[str, Path]]:
    total = 0
    staged: dict[str, Path] = {}
    for index, item in enumerate(release.files):
        member = by_name[f"{ROOT}{item.path}"]
        path = staging / f"{index}.payload"
        with path.open("xb") as destination:
            digest = copy_hash_member(stream, member, destination)
        if member.size != item.size or digest != item.sha256:
            raise _error("WFREL_HASH_MISMATCH", "payload identity does not match manifest", label="payload")
        staged[item.path] = path
        total += member.size
    return total, staged


def _ownership(release: ReleaseManifest, ownership: OwnershipManifest) -> None:
    replacements = release.source_evidence.accepted_asset_replacements
    expected_asset_claims = {
        f"asset:{item.root}/{item.logical_path}"
        for item in replacements
    }
    actual_asset_claims = {
        item for item in ownership.records if item.startswith("asset:")
    }
    if (
        len(ownership.entities) != 1
        or _CHARACTER_ENTITY.fullmatch(ownership.entities[0]) is None
        or any("*" in value or "?" in value for value in ownership.paths)
        or (
            release.source_evidence.kind == "character-workspace-v2"
            and (
                actual_asset_claims != expected_asset_claims
                or any(item.logical_path not in ownership.paths for item in replacements)
            )
        )
    ):
        raise _error(
            "WFREL_OWNERSHIP_INVALID",
            "character ownership is not an exact sealed-source projection",
            label="ownership",
        )
    # paths are source semantics. The archive cannot prove a byte mapping from
    # those paths into the independently validated outer Overlay ZIP bytes.


def _components(
    release: ReleaseManifest,
    requirements: ReleaseRequirements,
    staged: dict[str, Path],
) -> VerifiedOverlayChain:
    kinds = tuple(component.kind for component in release.components)
    if kinds not in (("content",), ("content", "modes")):
        raise _error(
            "WFREL_COMPONENT_UNSUPPORTED",
            "component receiver schema is unavailable in this vertical slice",
            label="components",
        )
    has_modes = kinds == ("content", "modes")
    if (
        release.expected_state.content_digest is not None
        or (release.expected_state.mode_digest is not None) != has_modes
        or requirements.patch_overlay_schema != 1
    ):
        raise _error("WFREL_COMPONENT_INVALID", "content-only component contract is invalid", label="content")
    content = [item for item in release.files if item.path.startswith("content/")]
    if (
        not content
        or len(content) != len(release.files) - (
            sum(1 for item in release.files if item.path.startswith("modes/"))
            if has_modes else 0
        )
        or any("/" in item.path.removeprefix("content/") for item in content)
    ):
        raise _error("WFREL_COMPONENT_INVALID", "content must contain explicit Overlay ZIPs", label="content")
    paths = [staged[item.path] for item in content]
    overlay = inspect_overlay_chain(tuple(paths))
    if overlay.target_version != release.expected_state.cdn_target_version:
        raise _error("WFREL_COMPONENT_INVALID", "Overlay target disagrees with expected state", label="content")
    if has_modes:
        verify_mode_component(release, requirements, staged)
    return overlay


def verify_release_contract(path: Path) -> tuple[VerificationReport, VerifiedRelease]:
    """Verify one archive and return the exact immutable contract values."""
    with open_release(Path(path)) as (stream, archive_size):
        members = parse_classic_store(stream, archive_size)
        by_name = {item.name: item for item in members}
        release, requirements, ownership, raw = _metadata(stream, by_name)
        _exact_set(release, by_name)
        _metadata_hashes(release, raw)
        with tempfile.TemporaryDirectory(prefix="wfrel-verify-") as temporary:
            payload_bytes, staged = _payloads(
                stream, release, by_name, Path(temporary)
            )
            verify_release_id(release)
            overlay = _components(release, requirements, staged)
            _ownership(release, ownership)
        report = VerificationReport(
            release_id=release.release_id,
            components=tuple(component.kind for component in release.components),
            file_count=len(release.files),
            payload_bytes=payload_bytes,
        )
        return report, VerifiedRelease(release, requirements, ownership, overlay)


def verify_release(path: Path) -> VerificationReport:
    """Verify one archive in the required fixed validation order."""
    return verify_release_contract(path)[0]


__all__ = ["VerificationReport", "verify_release", "verify_release_contract"]
