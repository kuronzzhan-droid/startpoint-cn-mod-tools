# -*- coding: utf-8 -*-
"""Scoped 1.4.312 edge construction and repository transaction tests."""
from __future__ import annotations

import hashlib
import io
import json
import random
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_inventory_support import InventoryCase, LOGICAL, ordered, sha256

import wf_character_pack as character_pack
import wf_mod_tool as core
import wf_scoped_release as scoped


FILE_LOGICAL = "character/fixture/icon.png"


class ScopedReleaseTest(InventoryCase):
    @staticmethod
    def spec(from_version: str, patch_id: str) -> scoped.EdgeSpec:
        return scoped.EdgeSpec(
            from_version=from_version,
            to_version="1.4.312",
            tag="localsync0806",
            patch_id=patch_id,
            name=f"fixture {from_version}",
            description="fixture scoped edge",
            created_at="2026-08-06",
        )

    def table_and_file_contract(self, terminal_table: bytes, terminal_file: bytes):
        claim = self.flat_claim("owned")
        return self.parse(self.payload([
            self.member("owner-table", terminal_table, claim),
            self.file_member(
                "owner-file", terminal_file, logical_path=FILE_LOGICAL
            ),
        ]))

    @staticmethod
    def entry_payload(plan: scoped.EdgePlan, logical_path: str) -> bytes:
        return next(
            entry.payload for entry in plan.entries
            if entry.logical_path == logical_path
        )

    def test_two_baselines_merge_only_claimed_rows_and_skip_equal_file(self):
        terminal_table = ordered([
            ("sentinel", b"operator-wip"), ("owned", b"terminal")
        ])
        terminal_file = b"terminal opaque"
        contract = self.table_and_file_contract(terminal_table, terminal_file)
        terminal = {
            ("common", LOGICAL): terminal_table,
            ("common", FILE_LOGICAL): terminal_file,
        }
        baseline_277 = {
            ("common", LOGICAL): ordered([
                ("sentinel", b"base-277"), ("owned", b"old-277")
            ]),
            ("common", FILE_LOGICAL): None,
        }
        baseline_311 = {
            ("common", LOGICAL): ordered([
                ("sentinel", b"base-311"), ("owned", b"old-311")
            ]),
            ("common", FILE_LOGICAL): terminal_file,
        }
        reader = lambda member: terminal[member.key]

        edge_277 = scoped.build_edge_plan(
            contract, baseline_277, reader,
            self.spec("1.4.277", "fixture-main"),
        )
        edge_311 = scoped.build_edge_plan(
            contract, baseline_311, reader,
            self.spec("1.4.311", "fixture-compatibility"),
        )

        self.assertEqual(
            {LOGICAL, FILE_LOGICAL},
            {entry.logical_path for entry in edge_277.entries},
        )
        self.assertEqual([LOGICAL], [entry.logical_path for entry in edge_311.entries])
        for plan, sentinel in ((edge_277, b"base-277"), (edge_311, b"base-311")):
            keys, rows = core._strict_orderedmap_rows(
                self.entry_payload(plan, LOGICAL),
                label="scoped-output", compressed_rows=True,
            )
            self.assertEqual(["sentinel", "owned"], keys)
            self.assertEqual([sentinel, b"terminal"], rows)

    def test_baseline_key_set_is_exact_and_tables_cannot_be_absent(self):
        terminal_table = ordered([("owned", b"terminal")])
        contract = self.parse(self.payload([
            self.member("owner", terminal_table, self.flat_claim("owned"))
        ]))
        reader = lambda _member: terminal_table
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "table baseline.*absent"):
            scoped.build_edge_plan(
                contract, {("common", LOGICAL): None}, reader,
                self.spec("1.4.277", "fixture-main"),
            )
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "baseline key set"):
            scoped.build_edge_plan(
                contract,
                {
                    ("common", LOGICAL): terminal_table,
                    ("common", "extra/path.png"): b"extra",
                },
                reader,
                self.spec("1.4.277", "fixture-main"),
            )

    def test_server_claims_are_not_read_or_written_into_client_edge(self):
        client = b"client file"
        server = b'{"169999":[["GINOVI"]]}'
        server_claim = character_pack.TableClaim(
            "server", "cdndata/character_text.json", "json_object", ("169999",)
        )
        contract = self.parse(self.payload([
            self.file_member("client", client, logical_path=FILE_LOGICAL),
            self.member(
                "server", server, server_claim,
                root="server", logical_path="cdndata/character_text.json",
            ),
        ]))

        def reader(member):
            if member.root == "server":
                raise AssertionError("server root must not be read by the ZIP builder")
            return client

        plan = scoped.build_edge_plan(
            contract, {("common", FILE_LOGICAL): None}, reader,
            self.spec("1.4.277", "fixture-main"),
        )
        self.assertEqual([FILE_LOGICAL], [entry.logical_path for entry in plan.entries])
        self.assertTrue(all(entry.root != "server" for entry in plan.entries))

    def opaque_contract(self, members: list[tuple[str, str, bytes]]):
        payload = []
        for index, (root, logical, raw) in enumerate(members):
            payload.append({
                "owner": f"owner-{index}",
                "kind": "file",
                "root": root,
                "logical_path": logical,
                "size": len(raw),
                "sha256": sha256(raw),
            })
        return self.parse(self.payload(payload))

    def test_zip_parts_are_deterministic_hard_capped_and_globally_sequenced(self):
        randomizer = random.Random(312)
        members = [
            (root, f"fixture/{root}/{index}.bin", randomizer.randbytes(420))
            for root in ("common", "medium", "android")
            for index in range(3)
        ]
        contract = self.opaque_contract(list(reversed(members)))
        terminal = {(root, logical): raw for root, logical, raw in members}
        baseline = {key: None for key in terminal}
        plan = scoped.build_edge_plan(
            contract, baseline, lambda member: terminal[member.key],
            self.spec("1.4.277", "fixture-main"), max_zip_bytes=1_250,
        )
        rebuilt = scoped.build_edge_plan(
            contract, dict(reversed(list(baseline.items()))),
            lambda member: terminal[member.key],
            self.spec("1.4.277", "fixture-main"), max_zip_bytes=1_250,
        )

        self.assertEqual(
            [(part.name, part.blob) for part in plan.parts],
            [(part.name, part.blob) for part in rebuilt.parts],
        )
        self.assertEqual(
            list(range(1, len(plan.parts) + 1)),
            [part.sequence for part in plan.parts],
        )
        self.assertEqual(
            sorted((part.root for part in plan.parts), key=scoped.CLIENT_ROOTS.index),
            [part.root for part in plan.parts],
        )
        for part in plan.parts:
            self.assertLessEqual(len(part.blob), 1_250)
            with zipfile.ZipFile(io.BytesIO(part.blob)) as archive:
                infos = archive.infolist()
                self.assertEqual(sorted(info.filename for info in infos), archive.namelist())
                self.assertTrue(all(info.date_time == scoped.ZIP_TIMESTAMP for info in infos))
                self.assertTrue(all(info.create_system == 3 for info in infos))
                self.assertIsNone(archive.testzip())

        with self.assertRaisesRegex(scoped.ScopedReleaseError, "5 MiB"):
            scoped.build_edge_plan(
                contract, baseline, lambda member: terminal[member.key],
                self.spec("1.4.277", "fixture-main"),
                max_zip_bytes=scoped.CI_ZIP_CAP + 1,
            )
        one_raw = randomizer.randbytes(2_000)
        one = self.opaque_contract([("common", "fixture/large.bin", one_raw)])
        with self.assertRaisesRegex(scoped.ScopedReleaseError, "single member"):
            scoped.build_edge_plan(
                one, {("common", "fixture/large.bin"): None},
                lambda _member: one_raw,
                self.spec("1.4.277", "fixture-main"), max_zip_bytes=600,
            )

    def two_small_plans(self) -> tuple[scoped.EdgePlan, scoped.EdgePlan]:
        raw = b"opaque payload"
        contract = self.opaque_contract([("common", FILE_LOGICAL, raw)])
        reader = lambda _member: raw
        return (
            scoped.build_edge_plan(
                contract, {("common", FILE_LOGICAL): None}, reader,
                self.spec("1.4.277", "local-live-main"),
            ),
            scoped.build_edge_plan(
                contract, {("common", FILE_LOGICAL): b"old"}, reader,
                self.spec("1.4.311", "local-live-compatibility"),
            ),
        )

    def test_manifest_entries_keep_cdn_version_and_declare_both_edges(self):
        plans = self.two_small_plans()
        original = b'{"cdn_version":"1.4.54","patches":[]}\n'
        rendered = scoped.render_manifest(original, plans)
        value = json.loads(rendered)
        self.assertEqual("1.4.54", value["cdn_version"])
        self.assertEqual(
            [("1.4.277", "1.4.312"), ("1.4.311", "1.4.312")],
            [(item["depends_on"], item["version"]) for item in value["patches"]],
        )
        self.assertEqual(
            [[part.name for part in plan.parts] for plan in plans],
            [item["chain"] for item in value["patches"]],
        )
        self.assertEqual(
            [
                [
                    {
                        "name": part.name,
                        "size": len(part.blob),
                        "sha256": hashlib.sha256(part.blob).hexdigest(),
                    }
                    for part in plan.parts
                ]
                for plan in plans
            ],
            [item["archive_integrity"] for item in value["patches"]],
        )

    def test_stage_is_exact_and_repository_publish_is_manifest_last(self):
        plans = self.two_small_plans()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            staged = scoped.stage_archives(plans, root / "staging")
            self.assertEqual(
                {part.name for plan in plans for part in plan.parts},
                {path.name for path in staged},
            )
            self.assertTrue(all(path.read_bytes() for path in staged))

            active = root / "repo" / "assets" / "asset-patch" / "active"
            active.mkdir(parents=True)
            manifest = active.parent / "manifest.json"
            original = b'{"cdn_version":"1.4.54","patches":[]}\n'
            manifest.write_bytes(original)
            original_mode = stat.S_IMODE(manifest.stat().st_mode)
            events: list[str] = []
            scoped.publish_archives_and_manifest(
                plans, active, manifest,
                expected_manifest_sha256=hashlib.sha256(original).hexdigest(),
                checkpoint=events.append,
                client_profile="official",
            )
            self.assertEqual("after_manifest", events[-1])
            self.assertEqual(
                ["after_archive"] * sum(len(plan.parts) for plan in plans),
                [event for event in events if event == "after_archive"],
            )
            self.assertEqual("before_manifest", events[-2])
            self.assertEqual(
                {part.name for plan in plans for part in plan.parts},
                {path.name for path in active.glob("*.zip")},
            )
            self.assertEqual("1.4.54", json.loads(manifest.read_bytes())["cdn_version"])
            self.assertEqual(original_mode, stat.S_IMODE(manifest.stat().st_mode))

    def test_publish_failure_before_manifest_rolls_back_only_new_archives(self):
        plans = self.two_small_plans()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active = root / "assets" / "asset-patch" / "active"
            active.mkdir(parents=True)
            existing = active / "pinball-1.4.1-1.4.2-1-existing.zip"
            existing.write_bytes(b"existing")
            manifest = active.parent / "manifest.json"
            original = b'{"cdn_version":"1.4.54","patches":[]}\n'
            manifest.write_bytes(original)

            def fail(phase: str) -> None:
                if phase == "before_manifest":
                    raise RuntimeError("injected manifest failure")

            with self.assertRaisesRegex(RuntimeError, "injected"):
                scoped.publish_archives_and_manifest(
                    plans, active, manifest,
                    expected_manifest_sha256=hashlib.sha256(original).hexdigest(),
                    checkpoint=fail,
                    client_profile="official",
                )
            self.assertEqual(original, manifest.read_bytes())
            self.assertEqual({existing.name}, {path.name for path in active.iterdir()})
            self.assertEqual(b"existing", existing.read_bytes())


if __name__ == "__main__":
    import unittest
    unittest.main()
