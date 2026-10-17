"""Read-only target capability levels for CLI and preparation UI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _target
from wf_release_v1.errors import ReleaseError
from wf_release_v1.legacy_target import LegacyProcessStatus
from wf_release_v1.target_protocol import TargetProtocol


class TargetCapabilityTests(unittest.TestCase):
    def test_modern_preserves_all_verified_facts_inside_versioned_probe(self) -> None:
        from wf_release_v1.target_capability import inspect_target_capability

        facts = _target()
        target = SimpleNamespace(target_probe=mock.Mock(return_value=object()))
        platform_factory = mock.Mock(side_effect=AssertionError("modern probe opened platform"))
        with (
            mock.patch(
                "wf_release_v1.target_capability.detect_target_protocol",
                return_value=TargetProtocol.CAPABILITIES_V1,
            ),
            mock.patch(
                "wf_release_v1.target_capability.target_facts_to_wire",
                return_value={"bundleId": facts.bundle_id},
            ) as wire,
            mock.patch(
                "wf_release_v1.target_capability._modern_facts",
                return_value=facts,
            ),
        ):
            result = inspect_target_capability(target, platform_factory)
            result_wire = result.to_wire()
        self.assertEqual({
            "blockers": [],
            "bundleId": facts.bundle_id,
            "installable": True,
            "level": "modern",
            "probeVersion": 2,
            "targetProtocol": "capabilities-v1",
            "writesLive": False,
        }, result_wire)
        wire.assert_called_once_with(facts)
        platform_factory.assert_not_called()

    def test_exact_404_plus_owned_local_facts_is_transition(self) -> None:
        from wf_release_v1.target_capability import inspect_target_capability

        legacy = SimpleNamespace(
            chain_tail="1.4.55",
            process_status=LegacyProcessStatus.OWNED_RUNNING,
            preview_only_reasons=(),
        )
        with (
            mock.patch(
                "wf_release_v1.target_capability.detect_target_protocol",
                return_value=TargetProtocol.LEGACY_CANDIDATE,
            ),
            mock.patch(
                "wf_release_v1.target_capability.inspect_legacy_target",
                return_value=legacy,
            ),
        ):
            wire = inspect_target_capability(
                SimpleNamespace(target_probe=lambda: object()), object()
            ).to_wire()
        self.assertEqual("transition", wire["level"])
        self.assertEqual("legacy", wire["targetProtocol"])
        self.assertTrue(wire["installable"])
        self.assertEqual("1.4.55", wire["legacyChainTail"])
        self.assertNotIn("bundleId", wire)

    def test_exact_404_without_owned_process_is_preparation_only_legacy(self) -> None:
        from wf_release_v1.target_capability import inspect_target_capability

        legacy = SimpleNamespace(
            chain_tail="1.4.55",
            process_status=LegacyProcessStatus.NOT_OWNED,
            preview_only_reasons=("WFREL_LEGACY_PROCESS_NOT_OWNED",),
        )
        with (
            mock.patch(
                "wf_release_v1.target_capability.detect_target_protocol",
                return_value=TargetProtocol.LEGACY_CANDIDATE,
            ),
            mock.patch(
                "wf_release_v1.target_capability.inspect_legacy_target",
                return_value=legacy,
            ),
        ):
            wire = inspect_target_capability(
                SimpleNamespace(target_probe=lambda: object()), object()
            ).to_wire()
        self.assertEqual("legacy", wire["level"])
        self.assertFalse(wire["installable"])
        self.assertEqual(["WFREL_LEGACY_PROCESS_NOT_OWNED"], wire["blockers"])
        self.assertFalse(wire["writesLive"])

    def test_local_legacy_fact_failure_is_a_blocked_legacy_result_not_modern_fallback(self) -> None:
        from wf_release_v1.target_capability import inspect_target_capability

        with (
            mock.patch(
                "wf_release_v1.target_capability.detect_target_protocol",
                return_value=TargetProtocol.LEGACY_CANDIDATE,
            ),
            mock.patch(
                "wf_release_v1.target_capability.inspect_legacy_target",
                side_effect=ReleaseError("WFREL_LEGACY_TARGET_INVALID", "bad local facts"),
            ),
        ):
            wire = inspect_target_capability(
                SimpleNamespace(target_probe=lambda: object()), object()
            ).to_wire()
        self.assertEqual("legacy", wire["level"])
        self.assertEqual(["WFREL_LEGACY_TARGET_INVALID"], wire["blockers"])
        self.assertNotIn("legacyChainTail", wire)

    def test_unified_planner_verifies_once_and_never_maps_a_blocked_legacy_target_to_modern(self) -> None:
        from wf_release_v1.target_planning import plan_target_install

        verified = object()
        target = object()
        modern_plan = object()
        modern = SimpleNamespace(
            level="modern", _modern_facts=object(), _legacy_facts=None, blockers=()
        )
        with (
            mock.patch(
                "wf_release_v1.target_planning.verify_release_contract",
                return_value=(object(), verified),
            ) as verify,
            mock.patch(
                "wf_release_v1.target_planning.inspect_target_capability",
                return_value=modern,
            ),
            mock.patch(
                "wf_release_v1.target_planning.plan_verified_install",
                return_value=modern_plan,
            ) as plan_modern,
        ):
            self.assertIs(modern_plan, plan_target_install(Path("release.zip"), target, object()))
        verify.assert_called_once_with(Path("release.zip"))
        plan_modern.assert_called_once_with(verified, target, modern._modern_facts)

        legacy_facts = object()
        active = object()
        legacy_plan = object()
        legacy = SimpleNamespace(
            level="transition",
            _modern_facts=None,
            _legacy_facts=legacy_facts,
            blockers=(),
        )
        with (
            mock.patch(
                "wf_release_v1.target_planning.verify_release_contract",
                return_value=(object(), verified),
            ),
            mock.patch(
                "wf_release_v1.target_planning.inspect_target_capability",
                return_value=legacy,
            ),
            mock.patch(
                "wf_release_v1.target_planning._active_state", return_value=active
            ),
            mock.patch(
                "wf_release_v1.target_planning.plan_legacy_install",
                return_value=legacy_plan,
            ) as plan_legacy,
        ):
            self.assertIs(legacy_plan, plan_target_install(Path("release.zip"), target, object()))
        plan_legacy.assert_called_once_with(verified, legacy_facts, active)

        blocked = SimpleNamespace(
            level="legacy",
            _modern_facts=None,
            _legacy_facts=None,
            blockers=("WFREL_LEGACY_TARGET_INVALID",),
        )
        with (
            mock.patch(
                "wf_release_v1.target_planning.verify_release_contract",
                return_value=(object(), verified),
            ),
            mock.patch(
                "wf_release_v1.target_planning.inspect_target_capability",
                return_value=blocked,
            ),
            mock.patch(
                "wf_release_v1.target_planning.plan_verified_install",
                side_effect=AssertionError("modern fallback"),
            ),
            self.assertRaises(ReleaseError) as raised,
        ):
            plan_target_install(Path("release.zip"), target, object())
        self.assertEqual("WFREL_LEGACY_TARGET_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
