"""Read-only compatibility planning and strict requirements capture."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

import wf_character_workspace

from .baseline_assets import verify_asset_replacement_baseline
from .canonical import canonical_json_bytes, load_json_strict_bytes
from .compatibility import ActiveState, VerifiedRelease, evaluate_requirements
from .errors import ReleaseError
from .probe import TargetFacts
from .receipts import load_active_state, load_previous_state
from .release_archive import capture_parent, verify_parent
from .schema import parse_requirements
from .target import ManagedTarget
from .verifier import verify_release_contract


@dataclass(frozen=True)
class RequirementsCaptureReceipt:
    requirements_capture_version: int
    requirements_sha256: str
    server_capability_count: int

    def to_wire(self) -> dict[str, object]:
        return {
            "requirementsCaptureVersion": self.requirements_capture_version,
            "requirementsSha256": self.requirements_sha256,
            "serverCapabilityCount": self.server_capability_count,
            "writesLive": False,
        }


@dataclass(frozen=True)
class InstallPlan:
    active_release_ids: tuple[str, ...]
    codes: tuple[str, ...]
    compatible: bool
    current_cdn_target_version: str
    expected_cdn_target_version: str
    no_op: bool
    release_id: str
    rollback_available: bool
    rollback_release_ids: tuple[str, ...]
    writes_live: bool = False

    def to_wire(self) -> dict[str, object]:
        return {
            "activeReleaseIds": list(self.active_release_ids),
            "codes": list(self.codes),
            "compatible": self.compatible,
            "currentCdnTargetVersion": self.current_cdn_target_version,
            "expectedCdnTargetVersion": self.expected_cdn_target_version,
            "noOp": self.no_op,
            "releaseId": self.release_id,
            "rollbackAvailable": self.rollback_available,
            "rollbackReleaseIds": list(self.rollback_release_ids),
            "writesLive": self.writes_live,
        }


def _fail(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


def _workspace_capabilities(workspace: Path) -> tuple[tuple[str, ...], str]:
    report = wf_character_workspace.inspect_workspace(workspace)
    if report.get("release_ready") is not True:
        raise _fail(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character workspace must be sealed and release ready",
        )
    current = wf_character_workspace.load_workspace(workspace)
    try:
        value = json.loads(
            (current.package_dir / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise _fail(
            "WFREL_CHARACTER_SOURCE_INVALID", "character workspace manifest is unavailable"
        ) from error
    capabilities = value.get("required_capabilities") if isinstance(value, Mapping) else None
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(item, str) or not item for item in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise _fail(
            "WFREL_CHARACTER_SOURCE_INVALID",
            "character workspace required capabilities are invalid",
        )
    digest = report.get("input_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise _fail("WFREL_CHARACTER_SOURCE_INVALID", "workspace digest is invalid")
    return tuple(sorted(capabilities, key=lambda item: item.encode("utf-8"))), digest


def _publish_json(output: Path, raw: bytes) -> None:
    if not output.is_absolute() or output.exists():
        raise _fail("WFREL_BUILD_OUTPUT_INVALID", "output must be a new absolute path")
    parent = capture_parent(output.parent)
    staging_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=".wf-requirements-", suffix=".tmp",
            dir=output.parent, delete=False,
        ) as staging:
            staging_path = Path(staging.name)
            if staging.write(raw) != len(raw):
                raise OSError("requirements write was incomplete")
            staging.flush()
            os.fsync(staging.fileno())
        if staging_path.read_bytes() != raw:
            raise OSError("requirements readback disagrees")
        verify_parent(parent)
        try:
            os.link(staging_path, output)
        except OSError as error:
            raise _fail(
                "WFREL_BUILD_OUTPUT_CHANGED",
                "requirements output could not be committed without clobbering",
            ) from error
    except ReleaseError:
        raise
    except OSError as error:
        raise _fail("WFREL_BUILD_IO", "requirements output could not be written") from error
    finally:
        if staging_path is not None:
            try:
                staging_path.unlink()
            except FileNotFoundError:
                pass


def capture_target_requirements(
    target: ManagedTarget,
    workspace: Path,
    output: Path,
) -> RequirementsCaptureReceipt:
    """Bind one sealed workspace to current read-only target compatibility facts."""
    if not isinstance(target, ManagedTarget):
        raise _fail("WFREL_REQUIRE_TARGET", "managed target is invalid")
    destination = Path(output)
    if not destination.is_absolute() or destination.exists():
        raise _fail("WFREL_BUILD_OUTPUT_INVALID", "output must be a new absolute path")
    capabilities, workspace_digest = _workspace_capabilities(Path(workspace))
    facts = target.target_probe().run()
    if not set(capabilities).issubset(facts.capabilities):
        raise _fail(
            "WFREL_REQUIRE_SERVER_CAPABILITY",
            "target does not provide every workspace capability",
        )
    wire = {
        "clientPatchProfile": target.compatibility.client_patch_profile,
        "clientVersions": [target.compatibility.client_version],
        "contentDigests": [facts.content_digest],
        "patchOverlaySchema": facts.patch_overlay_schema,
        "resourceBaselines": [target.compatibility.resource_baseline],
        "runtimeApi": facts.runtime_api,
        "schemaVersion": 1,
        "serverCapabilities": list(capabilities),
    }
    requirements = parse_requirements(wire)
    current = wf_character_workspace.inspect_workspace(Path(workspace))
    if current.get("input_digest") != workspace_digest:
        raise _fail(
            "WFREL_CHARACTER_SOURCE_CHANGED",
            "character workspace changed while capturing requirements",
        )
    raw = canonical_json_bytes(requirements.to_wire())
    # Independent strict readback prevents a serializer/parser split.
    if parse_requirements(
        load_json_strict_bytes(raw, label="requirements.json")
    ) != requirements:
        raise _fail("WFREL_SCHEMA_INVALID", "requirements readback disagrees")
    _publish_json(destination, raw)
    return RequirementsCaptureReceipt(
        1, hashlib.sha256(raw).hexdigest(), len(capabilities)
    )


def _active_state(target: ManagedTarget) -> ActiveState:
    active = target.state_root / "active.json"
    if active.exists() or active.is_symlink():
        return load_active_state(target.state_root)
    previous = target.state_root / "previous.json"
    if previous.exists() or previous.is_symlink():
        raise _fail(
            "WFREL_STATE_CONFLICT",
            "active state is missing beside retained previous state",
        )
    compatibility = target.compatibility
    return ActiveState(
        compatibility.client_version,
        compatibility.resource_baseline,
        compatibility.client_patch_profile,
        (),
        (),
    )


def plan_verified_install(
    verified: VerifiedRelease,
    target: ManagedTarget,
    facts: TargetFacts,
) -> InstallPlan:
    """Compare already verified modern facts without rereading the Release."""
    if not isinstance(target, ManagedTarget):
        raise _fail("WFREL_REQUIRE_TARGET", "managed target is invalid")
    active = _active_state(target)
    report = evaluate_requirements(verified, facts, active)
    no_op = report.codes == ("WFREL_OWNERSHIP_NOOP",)
    baseline_codes: tuple[str, ...] = ()
    if not no_op and verified.manifest.source_evidence.accepted_asset_replacements:
        try:
            verify_asset_replacement_baseline(verified, target, facts)
        except ReleaseError as error:
            baseline_codes = (error.code,)
    expected_version = verified.manifest.expected_state.cdn_target_version
    active_version = target.cdn_root / "patches" / expected_version
    version_occupied = not no_op and (
        active_version.exists() or active_version.is_symlink()
    )
    codes = report.codes + baseline_codes + (
        ("WFREL_STATE_VERSION_CONFLICT",) if version_occupied else ()
    )
    previous_path = target.state_root / "previous.json"
    rollback_ids: tuple[str, ...] = ()
    if previous_path.exists() or previous_path.is_symlink():
        previous = load_previous_state(target.state_root)
        rollback_ids = tuple(item.release_id for item in previous.releases)
    return InstallPlan(
        tuple(item.release_id for item in active.releases),
        codes,
        report.compatible and not baseline_codes and not version_occupied,
        facts.cdn_target_version,
        expected_version,
        no_op,
        verified.manifest.release_id,
        bool(rollback_ids),
        rollback_ids,
    )


def plan_install(release: Path, target: ManagedTarget) -> InstallPlan:
    """Verify and compare one release without materializing or switching anything."""
    if not isinstance(target, ManagedTarget):
        raise _fail("WFREL_REQUIRE_TARGET", "managed target is invalid")
    _report, verified = verify_release_contract(Path(release))
    return plan_verified_install(verified, target, target.target_probe().run())


__all__ = [
    "InstallPlan", "RequirementsCaptureReceipt", "capture_target_requirements", "plan_install",
    "plan_verified_install",
]
