"""One read-only plan entry that preserves modern and legacy semantics."""

from __future__ import annotations

from pathlib import Path

from .errors import ReleaseError
from .legacy_compatibility import LegacyInstallPlan, plan_legacy_install
from .planning import InstallPlan, _active_state, plan_verified_install
from .target import ManagedTarget
from .target_capability import inspect_target_capability
from .verifier import verify_release_contract


def plan_target_install(
    release: Path,
    target: ManagedTarget,
    platform: object,
) -> InstallPlan | LegacyInstallPlan:
    """Verify once and plan against one frozen capability inspection."""
    _report, verified = verify_release_contract(release)
    capability = inspect_target_capability(target, platform)
    if capability.level == "modern" and capability._modern_facts is not None:
        return plan_verified_install(verified, target, capability._modern_facts)
    if capability._legacy_facts is not None:
        return plan_legacy_install(verified, capability._legacy_facts, _active_state(target))
    code = capability.blockers[0] if capability.blockers else "WFREL_REQUIRE_TARGET"
    raise ReleaseError(code, "target facts are insufficient for installation planning")


__all__ = ["plan_target_install"]
