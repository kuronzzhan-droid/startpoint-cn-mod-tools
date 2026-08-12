"""Pure planning gates for installing verified content on legacy targets."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest import mock

from tests.release_v1_schema_support import (
    compute_release_id,
    release_without_id,
    requirements_wire,
)
from tests.release_v1_fixtures import make_patch_overlay, make_sealed_character_workspace
from wf_release_v1.compatibility import ActiveRelease, ActiveState, VerifiedRelease
from wf_release_v1.legacy_compatibility import plan_legacy_install
from wf_release_v1.legacy_target import (
    LegacyLayerFacts,
    LegacyProcessStatus,
    LegacyTargetFacts,
)
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.schema import parse_ownership, parse_release_manifest, parse_requirements
from wf_release_v1.target import TargetCompatibility
from wf_release_v1.verifier_overlay import (
    VerifiedOverlayArchive,
    VerifiedOverlayChain,
    VerifiedOverlayEdge,
    inspect_overlay_chain,
)
from wf_release_v1.verifier import verify_release_contract


OLD_ID = "sha256:" + "1" * 64
HISTORICAL_ID = "sha256:" + "2" * 64


def _ownership(*, entity: str = "character:310099"):
    return parse_ownership({
        "schemaVersion": 1,
        "entities": [entity],
        "records": [f"characters:{entity.split(':', 1)[1]}"],
        "paths": [f"assets/character/{entity.split(':', 1)[1]}"],
    })


def _overlay(
    start: str = "1.4.54",
    target: str = "1.4.55",
) -> VerifiedOverlayChain:
    archives = tuple(
        VerifiedOverlayArchive(
            relative_path=(
                f"archive-{layer}-diff/pinball-{start}-{target}-1-a1.zip"
            ),
            layer=layer,
            order=1,
            size=123,
            sha256="a" * 64,
        )
        for layer in ("common", "medium", "android")
    )
    edge = VerifiedOverlayEdge(start, target, archives)
    return VerifiedOverlayChain(start, target, (edge,))


def _verified(
    *,
    components: tuple[str, ...] = ("content",),
    capabilities: tuple[str, ...] = ("content.sync@1",),
    replaces: tuple[str, ...] = (),
    ownership=None,
    overlay: VerifiedOverlayChain | None = None,
) -> VerifiedRelease:
    verified_overlay = overlay or _overlay()
    manifest = release_without_id()
    manifest["components"] = [
        {"kind": kind, "root": kind} for kind in sorted(components)
    ]
    manifest["files"] = [
        {
            "path": f"{kind}/payload.zip",
            "size": 123,
            "sha256": "d" * 64,
        }
        for kind in sorted(components)
    ]
    manifest["replaces"] = list(replaces)
    manifest["expectedState"]["cdnTargetVersion"] = verified_overlay.target_version  # type: ignore[index]
    manifest["releaseId"] = compute_release_id(manifest)
    requirements = requirements_wire()
    requirements["serverCapabilities"] = list(capabilities)
    return VerifiedRelease(
        parse_release_manifest(manifest),
        parse_requirements(requirements),
        ownership or _ownership(),
        verified_overlay,
    )


def _active(
    *releases: ActiveRelease,
    known: tuple[str, ...] = (),
    client_version: str = "1.4.54",
    resource_baseline: str = "1.4.54",
    client_patch_profile: bool = True,
) -> ActiveState:
    return ActiveState(
        client_version,
        resource_baseline,
        client_patch_profile,
        tuple(releases),
        tuple(sorted({*known, *(item.release_id for item in releases)})),
    )


def _target(
    *,
    tail: str = "1.4.54",
    process: LegacyProcessStatus = LegacyProcessStatus.OWNED_RUNNING,
    client_version: str = "1.4.54",
    resource_baseline: str = "1.4.54",
    client_patch_profile: bool = True,
) -> LegacyTargetFacts:
    layers = tuple(
        LegacyLayerFacts(layer, (), "a" * 64)
        for layer in ("common", "medium", "android")
    )
    reasons = () if process is LegacyProcessStatus.OWNED_RUNNING else (
        "WFREL_LEGACY_PROCESS_NOT_OWNED",
    )
    return LegacyTargetFacts(
        tail,
        layers,
        TargetCompatibility(client_version, resource_baseline, client_patch_profile),
        process,
        reasons,
    )


class LegacyCompatibilityTests(unittest.TestCase):
    def test_returns_one_frozen_installable_path_free_plan_without_io(self) -> None:
        release = _verified()
        with (
            mock.patch("builtins.open", side_effect=AssertionError("disk read")),
            mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("network")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
        ):
            plan = plan_legacy_install(release, _target(), _active())
        self.assertEqual(
            {
                "codes": [],
                "fromVersion": "1.4.54",
                "installable": True,
                "noOp": False,
                "previewOnly": False,
                "releaseId": release.manifest.release_id,
                "targetProtocol": "legacy",
                "targetVersion": "1.4.55",
                "writesLive": False,
            },
            plan.to_wire(),
        )
        with self.assertRaises(FrozenInstanceError):
            plan.codes += ()  # type: ignore[misc]

    def test_overlay_facts_come_from_the_verified_manifest_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = make_patch_overlay(
                root / "first.zip",
                from_version="1.4.54",
                target_version="1.4.55",
            )
            second = make_patch_overlay(
                root / "second.zip",
                from_version="1.4.55",
                target_version="1.4.57",
            )
            facts = inspect_overlay_chain((second, first))
        self.assertEqual(("1.4.54", "1.4.57"), (facts.from_version, facts.target_version))
        self.assertEqual(
            (("1.4.54", "1.4.55"), ("1.4.55", "1.4.57")),
            tuple((item.from_version, item.target_version) for item in facts.edges),
        )
        self.assertEqual(
            ("common", "medium", "android"),
            tuple(item.layer for item in facts.edges[0].archives),
        )
        self.assertTrue(all(item.relative_path.endswith(".zip") for item in facts.edges[0].archives))

    def test_release_verifier_retains_the_same_detached_overlay_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            overlay = make_patch_overlay(
                root / "overlay.zip",
                from_version="1.4.54",
                target_version="1.4.55",
            )
            requirements = requirements_wire()
            requirements["serverCapabilities"] = ["content.sync@1"]
            release_path = root / "release.zip"
            build_character_release(BuildRequest(
                name="legacy-content",
                version="1.0.0",
                workspace=make_sealed_character_workspace(root / "workspace"),
                overlay_archives=(overlay,),
                output=release_path,
                requirements=parse_requirements(requirements),
            ))
            _report, verified = verify_release_contract(release_path)
        self.assertIsNotNone(verified.overlay)
        self.assertEqual(
            ("1.4.54", "1.4.55"),
            (verified.overlay.from_version, verified.overlay.target_version),  # type: ignore[union-attr]
        )

    def test_process_ownership_produces_preview_only_not_installable(self) -> None:
        plan = plan_legacy_install(
            _verified(),
            _target(process=LegacyProcessStatus.NOT_OWNED),
            _active(),
        )
        self.assertEqual(
            (True, False, ("WFREL_LEGACY_PROCESS_NOT_OWNED",)),
            (plan.preview_only, plan.installable, plan.codes),
        )

    def test_active_release_is_noop_but_historical_receipt_is_blocked(self) -> None:
        release = _verified()
        active = ActiveRelease(release.manifest.release_id, release.ownership)
        no_op = plan_legacy_install(
            release,
            _target(process=LegacyProcessStatus.NOT_OWNED, tail="1.4.55"),
            _active(active),
        )
        self.assertEqual(
            (True, True, False, ("WFREL_OWNERSHIP_NOOP",)),
            (no_op.installable, no_op.no_op, no_op.preview_only, no_op.codes),
        )
        historical = plan_legacy_install(
            release,
            _target(),
            _active(known=(release.manifest.release_id,)),
        )
        self.assertEqual(
            (False, ("WFREL_LEGACY_RELEASE_HISTORICAL",)),
            (historical.installable, historical.codes),
        )

    def test_rejects_non_content_or_non_unique_capability_releases(self) -> None:
        mode = plan_legacy_install(
            _verified(components=("content", "modes")), _target(), _active()
        )
        server = plan_legacy_install(
            _verified(components=("content", "server")), _target(), _active()
        )
        ability = plan_legacy_install(
            _verified(capabilities=("content.sync@1", "mode.release-contract@1")),
            _target(),
            _active(),
        )
        self.assertEqual(("WFREL_LEGACY_COMPONENT_UNSUPPORTED",), mode.codes)
        self.assertEqual(("WFREL_LEGACY_SERVER_DATA_BLOCKED",), server.codes)
        self.assertEqual(("WFREL_LEGACY_CAPABILITY_UNSUPPORTED",), ability.codes)

    def test_reports_compatibility_and_cdn_conflicts_in_stable_order(self) -> None:
        plan = plan_legacy_install(
            _verified(),
            _target(
                tail="1.4.53",
                client_version="1.4.99",
                resource_baseline="1.4.99",
                client_patch_profile=False,
            ),
            _active(),
        )
        self.assertEqual(
            (
                "WFREL_REQUIRE_CLIENT_VERSION",
                "WFREL_REQUIRE_RESOURCE_BASELINE",
                "WFREL_REQUIRE_CLIENT_PATCH_PROFILE",
                "WFREL_LEGACY_CDN_CONFLICT",
            ),
            plan.codes,
        )

    def test_reuses_exact_ownership_replacement_rules(self) -> None:
        old = ActiveRelease(OLD_ID, _ownership())
        conflict = plan_legacy_install(_verified(), _target(), _active(old))
        self.assertIn("WFREL_OWNERSHIP_CONFLICT", conflict.codes)

        partial = plan_legacy_install(
            _verified(replaces=(OLD_ID,), ownership=_ownership(entity="character:999999")),
            _target(),
            _active(old),
        )
        self.assertIn("WFREL_OWNERSHIP_REPLACES_PARTIAL", partial.codes)

        unknown = plan_legacy_install(
            _verified(replaces=(HISTORICAL_ID,)), _target(), _active()
        )
        self.assertIn("WFREL_OWNERSHIP_REPLACES_UNKNOWN", unknown.codes)


if __name__ == "__main__":
    unittest.main()
