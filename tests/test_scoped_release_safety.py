# -*- coding: utf-8 -*-
"""Adversarial coverage for scoped payload and repository release boundaries."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import InventoryCase, LOGICAL, ordered

import wf_character_pack as character_pack
import wf_mod_tool as core
import wf_scoped_release as scoped


FILE_LOGICAL = "character/fixture/safety.bin"
EMPTY_MANIFEST = b'{"cdn_version":"1.4.54","patches":[]}\n'


class ScopedReleaseSafetyTest(InventoryCase):
    @staticmethod
    def spec(
        from_version: str = "1.4.277", patch_id: str = "safety-main"
    ) -> scoped.EdgeSpec:
        return scoped.EdgeSpec(
            from_version=from_version,
            to_version="1.4.312",
            tag="safety0806",
            patch_id=patch_id,
            name="safety fixture",
            description="adversarial scoped release fixture",
            created_at="2026-08-06",
        )

    def small_plan(
        self, from_version: str = "1.4.277", patch_id: str = "safety-main"
    ) -> scoped.EdgePlan:
        raw = b"terminal opaque"
        contract = self.parse(self.payload([
            self.file_member("file-owner", raw, logical_path=FILE_LOGICAL)
        ]))
        return scoped.build_edge_plan(
            contract,
            {("common", FILE_LOGICAL): None},
            lambda _member: raw,
            self.spec(from_version, patch_id),
        )

    @staticmethod
    def output_table(plan: scoped.EdgePlan) -> tuple[list[str], list[bytes]]:
        entry = next(item for item in plan.entries if item.logical_path == LOGICAL)
        return core._strict_orderedmap_rows(
            entry.payload, label="multi-owner-output", compressed_rows=True
        )

    def test_disjoint_table_owners_accumulate_once_and_equal_output_is_omitted(self):
        terminal = ordered([
            ("sentinel", b"terminal-wip"),
            ("owner-a", b"terminal-a"),
            ("owner-b", b"terminal-b"),
        ])
        claim_a = character_pack.TableClaim(
            "common", LOGICAL, "flat", ("owner-a",)
        )
        claim_b = character_pack.TableClaim(
            "common", LOGICAL, "flat", ("owner-b",)
        )
        contract = self.parse(self.payload([
            self.member("a", terminal, claim_a),
            self.member("b", terminal, claim_b),
        ]))
        baseline = ordered([
            ("sentinel", b"baseline-only"),
            ("owner-a", b"old-a"),
            ("owner-b", b"old-b"),
        ])
        plan = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): baseline},
            lambda _member: terminal,
            self.spec(),
        )
        self.assertEqual([LOGICAL], [entry.logical_path for entry in plan.entries])
        keys, rows = self.output_table(plan)
        self.assertEqual(["sentinel", "owner-a", "owner-b"], keys)
        self.assertEqual([b"baseline-only", b"terminal-a", b"terminal-b"], rows)

        already_equal = ordered([
            ("sentinel", b"baseline-only"),
            ("owner-a", b"terminal-a"),
            ("owner-b", b"terminal-b"),
        ])
        omitted = scoped.build_edge_plan(
            contract,
            {("common", LOGICAL): already_equal},
            lambda _member: terminal,
            self.spec(),
        )
        self.assertEqual((), omitted.entries)
        self.assertEqual((), omitted.parts)

    def test_divergent_overlap_contract_fails_closed(self):
        terminal_a = ordered([("owned", b"value-a")])
        terminal_b = ordered([("owned", b"value-b")])
        claim = self.flat_claim("owned")
        contract = self.parse(self.payload([
            self.member("a", terminal_a, claim),
            self.member("b", terminal_b, claim),
        ]))
        by_owner = {"a": terminal_a, "b": terminal_b}
        with self.assertRaises(scoped.ScopedReleaseError):
            scoped.build_edge_plan(
                contract,
                {("common", LOGICAL): ordered([("owned", b"old")])},
                lambda member: by_owner[member.owner],
                self.spec(),
            )

    def test_manifest_rejects_missing_or_extra_archive_payloads(self):
        plan = self.small_plan()
        digest = core.sha1_path("fixture/missing.bin")
        missing_entry = scoped.ScopedEntry(
            "common",
            "fixture/missing.bin",
            f"production/upload/{digest[:2]}/{digest[2:]}",
            b"missing",
        )
        missing = scoped.EdgePlan(plan.spec, plan.entries + (missing_entry,), plan.parts)
        extra = scoped.EdgePlan(plan.spec, (), plan.parts)
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "missing"):
            scoped.render_manifest(EMPTY_MANIFEST, (missing,))
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "extra"):
            scoped.render_manifest(EMPTY_MANIFEST, (extra,))

    def test_manifest_rejects_duplicate_patch_ids_and_edges(self):
        primary = self.small_plan()
        compatibility = self.small_plan("1.4.311", "safety-compatibility")
        same_id = scoped.EdgePlan(
            replace(compatibility.spec, patch_id=primary.spec.patch_id),
            compatibility.entries,
            compatibility.parts,
        )
        same_edge = scoped.EdgePlan(
            replace(primary.spec, patch_id="safety-other"),
            primary.entries,
            primary.parts,
        )
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "patch id"):
            scoped.render_manifest(EMPTY_MANIFEST, (primary, same_id))
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "scoped edge"):
            scoped.render_manifest(EMPTY_MANIFEST, (primary, same_edge))

        duplicate_existing = {
            "cdn_version": "1.4.54",
            "patches": [
                {"id": "old", "depends_on": "1.4.1", "version": "1.4.2"},
                {"id": "old", "depends_on": "1.4.2", "version": "1.4.3"},
            ],
        }
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "patch id"):
            scoped.render_manifest(json.dumps(duplicate_existing).encode(), (primary,))
        duplicate_existing["patches"][1]["id"] = "other"
        duplicate_existing["patches"][1]["depends_on"] = "1.4.1"
        duplicate_existing["patches"][1]["version"] = "1.4.2"
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "manifest edge"):
            scoped.render_manifest(json.dumps(duplicate_existing).encode(), (primary,))

    def test_manifest_rejects_scoped_edge_inside_existing_aggregate_chain(self):
        seed = self.small_plan()
        spec = replace(
            seed.spec,
            from_version="1.4.91",
            to_version="1.4.92",
            patch_id="aggregate-inner-duplicate",
        )
        inner = scoped.EdgePlan(
            spec,
            seed.entries,
            tuple(
                replace(
                    part,
                    name=(
                        f"pinball-{spec.from_version}-{spec.to_version}-"
                        f"{part.sequence}-{spec.tag}.zip"
                    ),
                )
                for part in seed.parts
            ),
        )
        aggregate = {
            "cdn_version": "1.4.54",
            "patches": [{
                "id": "historical-aggregate",
                "type": "patch",
                "enabled": True,
                "depends_on": "1.4.90",
                "version": "1.4.93",
                "chain": [
                    "pinball-1.4.90-1.4.91-1-old.zip",
                    "pinball-1.4.91-1.4.92-1-old.zip",
                    "pinball-1.4.92-1.4.93-1-old.zip",
                ],
            }],
        }
        with self.assertRaisesRegex(
            scoped.ScopedReleaseError,
            r"duplicate (?:manifest|scoped) edge.*1\.4\.91->1\.4\.92",
        ):
            scoped.render_manifest(json.dumps(aggregate).encode(), (inner,))

        aggregate["patches"].append({
            "id": "overlapping-aggregate",
            "type": "patch",
            "enabled": True,
            "depends_on": "1.4.80",
            "version": "1.4.92",
            "chain": [
                "pinball-1.4.80-1.4.91-1-other.zip",
                "pinball-1.4.91-1.4.92-1-other.zip",
            ],
        })
        with self.assertRaisesRegex(
            scoped.ScopedReleaseError,
            r"duplicate manifest edge.*1\.4\.91->1\.4\.92",
        ):
            scoped.render_manifest(json.dumps(aggregate).encode(), (seed,))

    def test_existing_lock_is_preserved_without_archive_or_manifest_writes(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            patch_root = Path(td) / "asset-patch"
            active = patch_root / "active"
            active.mkdir(parents=True)
            manifest = patch_root / "manifest.json"
            manifest.write_bytes(EMPTY_MANIFEST)
            lock = patch_root / ".wf-scoped-release.lock"
            lock.write_bytes(b"another publisher")

            with self.assertRaises(scoped.ScopedReleaseError):
                scoped.publish_archives_and_manifest(
                    (plan,),
                    active,
                    manifest,
                    expected_manifest_sha256=hashlib.sha256(EMPTY_MANIFEST).hexdigest(),
                    client_profile="official",
                )
            self.assertEqual(b"another publisher", lock.read_bytes())
            self.assertEqual([], list(active.iterdir()))
            self.assertEqual(EMPTY_MANIFEST, manifest.read_bytes())

    def test_private_name_collision_is_never_deleted_as_owned_output(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            patch_root = Path(td) / "asset-patch"
            active = patch_root / "active"
            active.mkdir(parents=True)
            manifest = patch_root / "manifest.json"
            manifest.write_bytes(EMPTY_MANIFEST)
            token = "1" * 32
            foreign = active / f".wf-scoped-{token}-1.pending"
            foreign.write_bytes(b"foreign")

            with mock.patch.object(
                scoped.transaction.uuid, "uuid4", return_value=type(
                    "FixedUuid", (), {"hex": token}
                )()
            ):
                with self.assertRaises(scoped.ScopedReleaseError):
                    scoped.publish_archives_and_manifest(
                        (plan,),
                        active,
                        manifest,
                        expected_manifest_sha256=hashlib.sha256(
                            EMPTY_MANIFEST
                        ).hexdigest(),
                        client_profile="official",
                    )
            self.assertEqual(b"foreign", foreign.read_bytes())
            self.assertEqual(EMPTY_MANIFEST, manifest.read_bytes())
            self.assertFalse((patch_root / ".wf-scoped-release.lock").exists())

    def test_exclusive_write_failure_leaves_no_partial_staging_file(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            staging = Path(td) / "staging"
            with mock.patch.object(
                scoped.transaction.os, "fsync", side_effect=OSError("injected fsync")
            ):
                with self.assertRaisesRegex(scoped.ScopedReleaseError, "injected fsync"):
                    scoped.stage_archives((plan,), staging)
            self.assertFalse(staging.exists())

    def test_archive_tamper_after_visibility_link_aborts_before_manifest(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            patch_root = Path(td) / "asset-patch"
            active = patch_root / "active"
            active.mkdir(parents=True)
            manifest = patch_root / "manifest.json"
            manifest.write_bytes(EMPTY_MANIFEST)

            def tamper(phase: str) -> None:
                if phase == "after_archive":
                    target = next(active.glob("*.zip"))
                    target.write_bytes(b"tampered" * 800_000)

            with self.assertRaisesRegex(
                scoped.ScopedReleaseError, "hard cap|readback|drift|changed"
            ):
                scoped.publish_archives_and_manifest(
                    (plan,),
                    active,
                    manifest,
                    expected_manifest_sha256=hashlib.sha256(EMPTY_MANIFEST).hexdigest(),
                    checkpoint=tamper,
                    client_profile="official",
                )
            self.assertEqual(EMPTY_MANIFEST, manifest.read_bytes())
            self.assertEqual([], list(active.iterdir()))
            self.assertFalse((patch_root / ".wf-scoped-release.lock").exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows handle cleanup contract")
    def test_incomplete_rollback_retains_lock_and_orphan_for_manual_recovery(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            patch_root = Path(td) / "asset-patch"
            active = patch_root / "active"
            active.mkdir(parents=True)
            manifest = patch_root / "manifest.json"
            manifest.write_bytes(EMPTY_MANIFEST)
            api = scoped.transaction._windows_owned_api()
            real_dispose = api.dispose

            def refuse_archive_dispose(handle: int) -> None:
                target = api.final_path(handle)
                if target.parent == active and target.suffix == ".zip":
                    raise PermissionError("injected exact handle cleanup failure")
                real_dispose(handle)

            def fail(phase: str) -> None:
                if phase == "before_manifest":
                    raise RuntimeError("injected precommit failure")

            with mock.patch.object(
                api, "dispose", side_effect=refuse_archive_dispose
            ):
                with self.assertRaisesRegex(
                    scoped.ScopedReleaseError, "rollback|lock|handle"
                ):
                    scoped.publish_archives_and_manifest(
                        (plan,),
                        active,
                        manifest,
                        expected_manifest_sha256=hashlib.sha256(
                            EMPTY_MANIFEST
                        ).hexdigest(),
                        checkpoint=fail,
                        client_profile="official",
                    )
            lock = patch_root / ".wf-scoped-release.lock"
            self.assertTrue(lock.is_file())
            self.assertEqual(EMPTY_MANIFEST, manifest.read_bytes())
            self.assertEqual(1, len(list(active.glob("*.zip"))))
            for target in active.glob("*.zip"):
                target.unlink()
            lock.unlink()

    def test_publish_rejects_reparse_in_any_existing_ancestor_before_writes(self):
        plan = self.small_plan()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            patch_root = root / "nested" / "asset-patch"
            active = patch_root / "active"
            active.mkdir(parents=True)
            manifest = patch_root / "manifest.json"
            manifest.write_bytes(EMPTY_MANIFEST)
            unsafe_ancestor = root / "nested"
            real_is_reparse = scoped.transaction._is_reparse

            with mock.patch.object(
                scoped.transaction,
                "_is_reparse",
                side_effect=lambda path: (
                    Path(path) == unsafe_ancestor or real_is_reparse(Path(path))
                ),
            ):
                with self.assertRaisesRegex(
                    scoped.ScopedReleaseError, "ancestor|reparse"
                ):
                    scoped.publish_archives_and_manifest(
                        (plan,),
                        active,
                        manifest,
                        expected_manifest_sha256=hashlib.sha256(
                            EMPTY_MANIFEST
                        ).hexdigest(),
                        client_profile="official",
                    )
            self.assertEqual(EMPTY_MANIFEST, manifest.read_bytes())
            self.assertEqual([], list(active.iterdir()))
            self.assertFalse((patch_root / ".wf-scoped-release.lock").exists())

    def test_archive_inputs_reject_noncanonical_versions_tags_and_roots(self):
        with self.assertRaises(scoped.ScopedReleaseError):
            replace(self.spec(), tag="é")
        with self.assertRaisesRegex(scoped.archive.ArchiveError, "roots"):
            scoped.archive.build_parts(
                (),
                roots=("common", "common"),
                from_version="1.4.277",
                to_version="1.4.312",
                tag="safety0806",
                max_zip_bytes=scoped.CI_ZIP_CAP,
            )
        with self.assertRaisesRegex(scoped.archive.ArchiveError, "version"):
            scoped.archive.build_parts(
                (),
                roots=scoped.CLIENT_ROOTS,
                from_version="1.4.312",
                to_version="1.4.277",
                tag="safety0806",
                max_zip_bytes=scoped.CI_ZIP_CAP,
            )
        plan = self.small_plan()
        invalid = scoped.EdgePlan(
            plan.spec,
            plan.entries,
            (replace(plan.parts[0], root="unknown"),),
        )
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(scoped.ScopedReleaseError, "root"):
                scoped.stage_archives((invalid,), Path(td) / "staging")


if __name__ == "__main__":
    unittest.main()
