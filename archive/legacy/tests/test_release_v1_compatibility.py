"""Pure requirements, expected-state, and ownership compatibility gates."""

from __future__ import annotations

from dataclasses import replace
import socket
import time
import unittest
from unittest import mock

from tests.release_v1_schema_support import (
    HEX_A,
    HEX_B,
    HEX_C,
    release_without_id,
    requirements_wire,
)
from wf_release_v1.compatibility import (
    ActiveRelease,
    ActiveState,
    VerifiedRelease,
    evaluate_expected_state,
    evaluate_requirements,
)
from wf_release_v1.probe import TargetFacts
from wf_release_v1.schema import (
    compute_release_id,
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
)


OLD_A = "sha256:" + "1" * 64
OLD_B = "sha256:" + "2" * 64
KNOWN_INACTIVE = "sha256:" + "3" * 64


def _ownership(
    *,
    entities: tuple[str, ...] = ("character:310099",),
    records: tuple[str, ...] = ("characters:310099",),
    paths: tuple[str, ...] = ("assets/character/310099",),
):
    return parse_ownership(
        {
            "schemaVersion": 1,
            "entities": list(entities),
            "records": list(records),
            "paths": list(paths),
        }
    )


def _verified(
    *,
    replaces: tuple[str, ...] = (),
    ownership=None,
    requirement_changes: dict[str, object] | None = None,
    expected_changes: dict[str, object] | None = None,
) -> VerifiedRelease:
    manifest = release_without_id()
    manifest["replaces"] = list(replaces)
    if expected_changes:
        manifest["expectedState"].update(expected_changes)  # type: ignore[union-attr]
    manifest["releaseId"] = compute_release_id(manifest)
    requirements = requirements_wire()
    if requirement_changes:
        requirements.update(requirement_changes)
    return VerifiedRelease(
        manifest=parse_release_manifest(manifest),
        requirements=parse_requirements(requirements),
        ownership=ownership or _ownership(),
    )


def _target(**changes: object) -> TargetFacts:
    values: dict[str, object] = {
        "bundle_id": "sha256:" + "4" * 64,
        "server_version": "1.0.0",
        "runtime_id": "sha256:" + "5" * 64,
        "runtime_api": 1,
        "dependency_lock": "sha256:" + "6" * 64,
        "node_version": "20.19.0",
        "node_abi": "127",
        "platform": "win32",
        "arch": "x64",
        "capabilities": ("content.sync@1", "mode.release-contract@1"),
        "content_digest": f"sha256:{HEX_A}",
        "cdn_target_version": "1.4.54",
        "mode_digest": f"sha256:{HEX_C}",
        "patch_overlay_schema": 1,
    }
    values.update(changes)
    return TargetFacts(**values)  # type: ignore[arg-type]


def _active(
    *releases: ActiveRelease,
    client_version: str = "1.4.54",
    resource_baseline: str = "1.4.53",
    client_patch_profile: bool = True,
    known_release_ids: tuple[str, ...] = (),
) -> ActiveState:
    known = tuple(sorted({*known_release_ids, *(item.release_id for item in releases)}))
    return ActiveState(
        client_version=client_version,
        resource_baseline=resource_baseline,
        client_patch_profile=client_patch_profile,
        releases=tuple(releases),
        known_release_ids=known,
    )


class RequirementCompatibilityTests(unittest.TestCase):
    def test_accepts_exact_requirements_without_io_or_clock_access(self) -> None:
        release = _verified()
        with (
            mock.patch("builtins.open", side_effect=AssertionError("disk read")),
            mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("network")),
            mock.patch.object(time, "monotonic", side_effect=AssertionError("clock")),
        ):
            report = evaluate_requirements(release, _target(), _active())
        self.assertEqual((True, ()), (report.compatible, report.codes))

    def test_reports_every_requirement_mismatch_in_stable_order(self) -> None:
        report = evaluate_requirements(
            _verified(),
            _target(
                runtime_api=2,
                capabilities=("content.sync@1",),
                content_digest=f"sha256:{HEX_C}",
                patch_overlay_schema=2,
            ),
            _active(
                client_version="1.4.99",
                resource_baseline="1.4.99",
                client_patch_profile=False,
            ),
        )
        self.assertEqual(
            (
                "WFREL_REQUIRE_RUNTIME_API",
                "WFREL_REQUIRE_SERVER_CAPABILITY",
                "WFREL_REQUIRE_CLIENT_VERSION",
                "WFREL_REQUIRE_RESOURCE_BASELINE",
                "WFREL_REQUIRE_CONTENT_DIGEST",
                "WFREL_REQUIRE_PATCH_OVERLAY_SCHEMA",
                "WFREL_REQUIRE_CLIENT_PATCH_PROFILE",
            ),
            report.codes,
        )
        self.assertFalse(report.compatible)

    def test_each_requirement_is_bound_to_its_own_target_fact(self) -> None:
        cases = (
            ("runtime api", _target(runtime_api=2), _active(), "WFREL_REQUIRE_RUNTIME_API"),
            (
                "server capability",
                _target(capabilities=("content.sync@1",)),
                _active(),
                "WFREL_REQUIRE_SERVER_CAPABILITY",
            ),
            (
                "client version",
                _target(),
                _active(client_version="1.4.99"),
                "WFREL_REQUIRE_CLIENT_VERSION",
            ),
            (
                "resource baseline",
                _target(),
                _active(resource_baseline="1.4.99"),
                "WFREL_REQUIRE_RESOURCE_BASELINE",
            ),
            (
                "content digest",
                _target(content_digest=f"sha256:{HEX_C}"),
                _active(),
                "WFREL_REQUIRE_CONTENT_DIGEST",
            ),
            (
                "patch overlay schema",
                _target(patch_overlay_schema=2),
                _active(),
                "WFREL_REQUIRE_PATCH_OVERLAY_SCHEMA",
            ),
            (
                "client patch profile",
                _target(),
                _active(client_patch_profile=False),
                "WFREL_REQUIRE_CLIENT_PATCH_PROFILE",
            ),
        )
        release = _verified()
        for label, target, active, expected in cases:
            with self.subTest(label=label):
                report = evaluate_requirements(release, target, active)
                self.assertEqual((expected,), report.codes)
                self.assertFalse(report.compatible)

    def test_false_client_patch_requirement_does_not_forbid_a_patched_client(self) -> None:
        release = _verified(requirement_changes={"clientPatchProfile": False})
        report = evaluate_requirements(release, _target(), _active())
        self.assertEqual((True, ()), (report.compatible, report.codes))

    def test_expected_state_is_a_separate_post_install_gate(self) -> None:
        release = _verified(
            expected_changes={
                "contentDigest": f"sha256:{HEX_A}",
                "modeDigest": f"sha256:{HEX_C}",
            }
        )
        compatible = evaluate_expected_state(release, _target())
        self.assertEqual((True, ()), (compatible.compatible, compatible.codes))

        mismatched = evaluate_expected_state(
            release,
            _target(
                cdn_target_version="1.4.55",
                content_digest=f"sha256:{HEX_B}",
                mode_digest=f"sha256:{HEX_B}",
            ),
        )
        self.assertEqual(
            (
                "WFREL_REQUIRE_EXPECTED_CDN_STATE",
                "WFREL_REQUIRE_EXPECTED_CONTENT_STATE",
                "WFREL_REQUIRE_EXPECTED_MODE_STATE",
            ),
            mismatched.codes,
        )

    def test_null_optional_expected_digests_are_not_inferred(self) -> None:
        report = evaluate_expected_state(
            _verified(),
            _target(content_digest=f"sha256:{HEX_B}", mode_digest=f"sha256:{HEX_B}"),
        )
        self.assertEqual((True, ()), (report.compatible, report.codes))


class OwnershipCompatibilityTests(unittest.TestCase):
    def test_same_active_release_is_an_explicit_noop(self) -> None:
        release = _verified()
        active_release = ActiveRelease(release.manifest.release_id, release.ownership)
        report = evaluate_requirements(
            release,
            _target(runtime_api=99),
            _active(active_release),
        )
        self.assertEqual(
            (True, ("WFREL_OWNERSHIP_NOOP",)),
            (report.compatible, report.codes),
        )

    def test_equal_payload_identity_never_allows_implicit_shared_ownership(self) -> None:
        release = _verified()
        report = evaluate_requirements(
            release,
            _target(),
            _active(ActiveRelease(OLD_A, release.ownership)),
        )
        self.assertEqual(("WFREL_OWNERSHIP_CONFLICT",), report.codes)
        self.assertFalse(report.compatible)

    def test_distinct_characters_may_share_source_table_paths(self) -> None:
        old = _ownership(
            entities=("character:129999",),
            records=("action_skill:129999", "character:129999"),
            paths=(
                "character.json",
                "character/seris_dragon_king/ui/square_0.png",
                "master/character/character.orderedmap",
                "master/skill/action_skill.orderedmap",
            ),
        )
        new = _ownership(
            entities=("character:139999",),
            records=("action_skill:139999", "character:139999"),
            paths=(
                "character.json",
                "character/stella_moon_witch/ui/square_0.png",
                "master/character/character.orderedmap",
                "master/skill/action_skill.orderedmap",
            ),
        )
        report = evaluate_requirements(
            _verified(ownership=new),
            _target(),
            _active(ActiveRelease(OLD_A, old)),
        )
        self.assertEqual((True, ()), (report.compatible, report.codes))

    def test_each_exclusive_claim_namespace_blocks_shared_ownership(self) -> None:
        cases = (
            (
                "entity",
                _ownership(
                    entities=("character:310099",),
                    records=("characters:old",),
                    paths=("sources/old",),
                ),
                _ownership(
                    entities=("character:310099",),
                    records=("characters:new",),
                    paths=("sources/new",),
                ),
            ),
            (
                "record",
                _ownership(
                    entities=("character:310098",),
                    records=("characters:310099",),
                    paths=("sources/old",),
                ),
                _ownership(
                    entities=("character:310100",),
                    records=("characters:310099",),
                    paths=("sources/new",),
                ),
            ),
        )
        for label, old, new in cases:
            with self.subTest(label=label):
                report = evaluate_requirements(
                    _verified(ownership=new),
                    _target(),
                    _active(ActiveRelease(OLD_A, old)),
                )
                self.assertEqual(("WFREL_OWNERSHIP_CONFLICT",), report.codes)
                self.assertFalse(report.compatible)

    def test_exact_release_id_replacement_preserves_all_old_claims(self) -> None:
        old = _ownership()
        new = _ownership(
            entities=("character:310099", "character:310100"),
            records=("characters:310099", "characters:310100"),
            paths=("assets/character/310099", "assets/character/310100"),
        )
        release = _verified(replaces=(OLD_A,), ownership=new)
        report = evaluate_requirements(
            release,
            _target(),
            _active(ActiveRelease(OLD_A, old)),
        )
        self.assertEqual((True, ()), (report.compatible, report.codes))

    def test_replacement_rejects_unknown_inactive_and_symbolic_identifiers(self) -> None:
        for replacement, known, expected in (
            (OLD_A, (), "WFREL_OWNERSHIP_REPLACES_UNKNOWN"),
            (KNOWN_INACTIVE, (KNOWN_INACTIVE,), "WFREL_OWNERSHIP_REPLACES_INACTIVE"),
            ("legacy-name", (), "WFREL_OWNERSHIP_REPLACES_UNKNOWN"),
            ("1.2.3", (), "WFREL_OWNERSHIP_REPLACES_UNKNOWN"),
            ("sha256:*", (), "WFREL_OWNERSHIP_REPLACES_UNKNOWN"),
        ):
            release = _verified()
            release = replace(
                release,
                manifest=replace(release.manifest, replaces=(replacement,)),
            )
            with self.subTest(replacement=replacement):
                report = evaluate_requirements(
                    release,
                    _target(),
                    _active(known_release_ids=known),
                )
                self.assertEqual((expected,), report.codes)
                self.assertFalse(report.compatible)

    def test_partial_replacement_cannot_drop_uncovered_ownership(self) -> None:
        old = _ownership(records=("characters:310099", "skills:310099"))
        release = _verified(replaces=(OLD_A,), ownership=_ownership())
        report = evaluate_requirements(
            release,
            _target(),
            _active(ActiveRelease(OLD_A, old)),
        )
        self.assertEqual(("WFREL_OWNERSHIP_REPLACES_PARTIAL",), report.codes)
        self.assertFalse(report.compatible)

    def test_every_colliding_owner_must_be_replaced_exactly(self) -> None:
        first = _ownership()
        second = _ownership(
            entities=("character:310100",),
            records=("characters:310100",),
            paths=("assets/character/310100",),
        )
        combined = _ownership(
            entities=("character:310099", "character:310100"),
            records=("characters:310099", "characters:310100"),
            paths=("assets/character/310099", "assets/character/310100"),
        )
        active = _active(ActiveRelease(OLD_A, first), ActiveRelease(OLD_B, second))

        incomplete = evaluate_requirements(
            _verified(replaces=(OLD_A,), ownership=combined), _target(), active
        )
        self.assertEqual(("WFREL_OWNERSHIP_CONFLICT",), incomplete.codes)
        self.assertFalse(incomplete.compatible)

        exact = evaluate_requirements(
            _verified(replaces=(OLD_A, OLD_B), ownership=combined), _target(), active
        )
        self.assertEqual((True, ()), (exact.compatible, exact.codes))

    def test_replacing_unrelated_active_owner_is_partial_replacement(self) -> None:
        unrelated = _ownership(
            entities=("character:310100",),
            records=("characters:310100",),
            paths=("assets/character/310100",),
        )
        report = evaluate_requirements(
            _verified(replaces=(OLD_A,)),
            _target(),
            _active(ActiveRelease(OLD_A, unrelated)),
        )
        self.assertEqual(("WFREL_OWNERSHIP_REPLACES_PARTIAL",), report.codes)
        self.assertFalse(report.compatible)


if __name__ == "__main__":
    unittest.main()
