"""Pure compatibility planning for verified content on legacy targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from .compatibility import ActiveState, VerifiedRelease, evaluate_ownership
from .errors import ReleaseError
from .legacy_target import LegacyProcessStatus, LegacyTargetFacts
from .verifier_overlay import VerifiedOverlayChain


_TARGET_PROTOCOL: Final = "legacy"
_CONTENT_CAPABILITY: Final = ("content.sync@1",)


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_LEGACY_PLAN_INVALID", message)


@dataclass(frozen=True)
class LegacyInstallPlan:
    release_id: str
    preview_only: bool
    installable: bool
    no_op: bool
    codes: tuple[str, ...]
    from_version: str
    target_version: str
    overlay: VerifiedOverlayChain = field(repr=False)
    target_protocol: str = _TARGET_PROTOCOL
    writes_live: bool = False

    def to_wire(self) -> dict[str, object]:
        return {
            "codes": list(self.codes),
            "fromVersion": self.from_version,
            "installable": self.installable,
            "noOp": self.no_op,
            "previewOnly": self.preview_only,
            "releaseId": self.release_id,
            "targetProtocol": self.target_protocol,
            "targetVersion": self.target_version,
            "writesLive": self.writes_live,
        }


def _component_codes(release: VerifiedRelease) -> list[str]:
    kinds = tuple(item.kind for item in release.manifest.components)
    paths = tuple(item.path for item in release.manifest.files)
    if "server" in kinds or any(path.startswith("server/") for path in paths):
        return ["WFREL_LEGACY_SERVER_DATA_BLOCKED"]
    expected = release.manifest.expected_state
    if (
        kinds != ("content",)
        or any(not path.startswith("content/") for path in paths)
        or expected.content_digest is not None
        or expected.mode_digest is not None
    ):
        return ["WFREL_LEGACY_COMPONENT_UNSUPPORTED"]
    return []


def _requirement_codes(
    release: VerifiedRelease,
    target: LegacyTargetFacts,
) -> list[str]:
    required = release.requirements
    actual = target.compatibility
    codes: list[str] = []
    if required.server_capabilities != _CONTENT_CAPABILITY:
        codes.append("WFREL_LEGACY_CAPABILITY_UNSUPPORTED")
    if actual.client_version not in required.client_versions:
        codes.append("WFREL_REQUIRE_CLIENT_VERSION")
    if actual.resource_baseline not in required.resource_baselines:
        codes.append("WFREL_REQUIRE_RESOURCE_BASELINE")
    if required.client_patch_profile and not actual.client_patch_profile:
        codes.append("WFREL_REQUIRE_CLIENT_PATCH_PROFILE")
    if required.patch_overlay_schema != 1:
        codes.append("WFREL_REQUIRE_PATCH_OVERLAY_SCHEMA")
    return codes


def _cdn_conflict(target: LegacyTargetFacts, overlay: VerifiedOverlayChain) -> bool:
    local_archives = tuple(
        archive
        for layer in target.layers
        for archive in layer.archives
    )
    local_paths = {item.relative_path.casefold() for item in local_archives}
    local_edges = {(item.from_version, item.target_version) for item in local_archives}
    local_versions = {
        version
        for item in local_archives
        for version in (item.from_version, item.target_version)
    }
    candidates = tuple(
        archive
        for edge in overlay.edges
        for archive in edge.archives
    )
    candidate_paths = tuple(item.relative_path.casefold() for item in candidates)
    candidate_edges = {(edge.from_version, edge.target_version) for edge in overlay.edges}
    return (
        target.chain_tail != overlay.from_version
        or overlay.target_version in local_versions
        or bool(local_edges & candidate_edges)
        or len(set(candidate_paths)) != len(candidate_paths)
        or bool(local_paths & set(candidate_paths))
    )


def plan_legacy_install(
    release: VerifiedRelease,
    target: LegacyTargetFacts,
    active: ActiveState,
) -> LegacyInstallPlan:
    """Return one detached, path-free plan without reading or writing target state."""
    if (
        not isinstance(release, VerifiedRelease)
        or not isinstance(target, LegacyTargetFacts)
        or not isinstance(active, ActiveState)
        or not isinstance(release.overlay, VerifiedOverlayChain)
    ):
        raise _invalid("legacy compatibility input is invalid")
    overlay = release.overlay
    release_id = release.manifest.release_id
    active_ids = {item.release_id for item in active.releases}
    if release_id in active_ids:
        return LegacyInstallPlan(
            release_id,
            False,
            True,
            True,
            ("WFREL_OWNERSHIP_NOOP",),
            overlay.from_version,
            overlay.target_version,
            overlay=overlay,
        )
    if release_id in set(active.known_release_ids):
        return LegacyInstallPlan(
            release_id,
            False,
            False,
            False,
            ("WFREL_LEGACY_RELEASE_HISTORICAL",),
            overlay.from_version,
            overlay.target_version,
            overlay=overlay,
        )

    codes = _component_codes(release)
    codes.extend(_requirement_codes(release, target))
    if (
        release.manifest.expected_state.cdn_target_version
        != overlay.target_version
        or _cdn_conflict(target, overlay)
    ):
        codes.append("WFREL_LEGACY_CDN_CONFLICT")
    codes.extend(evaluate_ownership(release, active).codes)

    preview_only = target.process_status is LegacyProcessStatus.NOT_OWNED
    if preview_only:
        codes.extend(target.preview_only_reasons)
    elif (
        target.process_status is not LegacyProcessStatus.OWNED_RUNNING
        or target.preview_only_reasons
    ):
        raise _invalid("legacy process facts are invalid")
    frozen_codes = tuple(dict.fromkeys(codes))
    return LegacyInstallPlan(
        release_id,
        preview_only,
        not frozen_codes,
        False,
        frozen_codes,
        overlay.from_version,
        overlay.target_version,
        overlay=overlay,
    )


__all__ = ["LegacyInstallPlan", "plan_legacy_install"]
