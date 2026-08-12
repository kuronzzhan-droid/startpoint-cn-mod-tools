"""Pure release requirements, expected-state, and ownership gates."""

from __future__ import annotations

from dataclasses import dataclass

from .probe import TargetFacts
from .schema import OwnershipManifest, ReleaseManifest, ReleaseRequirements
from .verifier_overlay import VerifiedOverlayChain


@dataclass(frozen=True)
class VerifiedRelease:
    """Detached values obtained from an independently verified release."""

    manifest: ReleaseManifest
    requirements: ReleaseRequirements
    ownership: OwnershipManifest
    overlay: VerifiedOverlayChain | None = None


@dataclass(frozen=True)
class ActiveRelease:
    """One immutable active release and its exact ownership projection."""

    release_id: str
    ownership: OwnershipManifest


@dataclass(frozen=True)
class ActiveState:
    """Pure local facts needed before an install may start."""

    client_version: str
    resource_baseline: str
    client_patch_profile: bool
    releases: tuple[ActiveRelease, ...]
    known_release_ids: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityReport:
    compatible: bool
    codes: tuple[str, ...]


def _report(codes: list[str] | tuple[str, ...]) -> CompatibilityReport:
    frozen = tuple(codes)
    return CompatibilityReport(not frozen, frozen)


def _exclusive_claims(ownership: OwnershipManifest) -> frozenset[tuple[str, str]]:
    """Return install-exclusive keys; paths remain sealed-source evidence."""
    return frozenset(
        (("entity", value) for value in ownership.entities),
    ) | frozenset(
        (("record", value) for value in ownership.records),
    )


def _requirement_codes(
    release: VerifiedRelease,
    target: TargetFacts,
    active: ActiveState,
) -> list[str]:
    required = release.requirements
    codes: list[str] = []
    if target.runtime_api != required.runtime_api:
        codes.append("WFREL_REQUIRE_RUNTIME_API")
    if not set(required.server_capabilities).issubset(target.capabilities):
        codes.append("WFREL_REQUIRE_SERVER_CAPABILITY")
    if active.client_version not in required.client_versions:
        codes.append("WFREL_REQUIRE_CLIENT_VERSION")
    if active.resource_baseline not in required.resource_baselines:
        codes.append("WFREL_REQUIRE_RESOURCE_BASELINE")
    if target.content_digest not in required.content_digests:
        codes.append("WFREL_REQUIRE_CONTENT_DIGEST")
    if target.patch_overlay_schema != required.patch_overlay_schema:
        codes.append("WFREL_REQUIRE_PATCH_OVERLAY_SCHEMA")
    if required.client_patch_profile and not active.client_patch_profile:
        codes.append("WFREL_REQUIRE_CLIENT_PATCH_PROFILE")
    return codes


def _ownership_codes(
    release: VerifiedRelease,
    active: ActiveState,
) -> list[str]:
    active_by_id = {item.release_id: item for item in active.releases}
    known_ids = set(active.known_release_ids) | set(active_by_id)
    replacements = set(release.manifest.replaces)
    new_claims = _exclusive_claims(release.ownership)
    codes: list[str] = []

    if any(release_id not in known_ids for release_id in replacements):
        codes.append("WFREL_OWNERSHIP_REPLACES_UNKNOWN")
    if any(
        release_id in known_ids and release_id not in active_by_id
        for release_id in replacements
    ):
        codes.append("WFREL_OWNERSHIP_REPLACES_INACTIVE")

    colliding_owners = {
        item.release_id
        for item in active.releases
        if _exclusive_claims(item.ownership) & new_claims
    }
    if colliding_owners - replacements:
        codes.append("WFREL_OWNERSHIP_CONFLICT")
    if any(
        not _exclusive_claims(active_by_id[release_id].ownership).issubset(new_claims)
        for release_id in replacements & set(active_by_id)
    ):
        codes.append("WFREL_OWNERSHIP_REPLACES_PARTIAL")
    return codes


def evaluate_ownership(
    release: VerifiedRelease,
    active: ActiveState,
) -> CompatibilityReport:
    """Evaluate only the shared exact ownership replacement contract."""
    if not isinstance(release, VerifiedRelease) or not isinstance(active, ActiveState):
        raise TypeError("ownership compatibility input is invalid")
    if any(item.release_id == release.manifest.release_id for item in active.releases):
        return CompatibilityReport(True, ("WFREL_OWNERSHIP_NOOP",))
    return _report(_ownership_codes(release, active))


def evaluate_requirements(
    release: VerifiedRelease,
    target: TargetFacts,
    active: ActiveState,
) -> CompatibilityReport:
    """Evaluate pre-install requirements and exact ownership replacement."""
    if any(
        item.release_id == release.manifest.release_id
        for item in active.releases
    ):
        return CompatibilityReport(True, ("WFREL_OWNERSHIP_NOOP",))
    codes = _requirement_codes(release, target, active)
    codes.extend(_ownership_codes(release, active))
    return _report(codes)


def evaluate_expected_state(
    release: VerifiedRelease,
    target: TargetFacts,
) -> CompatibilityReport:
    """Evaluate post-start target facts against the release expected state."""
    expected = release.manifest.expected_state
    codes: list[str] = []
    if target.cdn_target_version != expected.cdn_target_version:
        codes.append("WFREL_REQUIRE_EXPECTED_CDN_STATE")
    if (
        expected.content_digest is not None
        and target.content_digest != expected.content_digest
    ):
        codes.append("WFREL_REQUIRE_EXPECTED_CONTENT_STATE")
    if expected.mode_digest is not None and target.mode_digest != expected.mode_digest:
        codes.append("WFREL_REQUIRE_EXPECTED_MODE_STATE")
    return _report(codes)
