# -*- coding: utf-8 -*-
"""Frozen local-live release contract integration tests."""
from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parent.parent
CONTRACTS = MOD_TOOLS / "release-contracts"
sys.path.insert(0, str(MOD_TOOLS))


class LocalLiveReleaseContractTest(unittest.TestCase):
    def setUp(self):
        self.contract = importlib.import_module("wf_local_release_contract")
        self.provenance = importlib.import_module("wf_local_release_provenance")
        self.server = importlib.import_module("wf_local_server_contract")
        self.bundle = self.contract.load_bundle(CONTRACTS)

    def test_bundle_exposes_the_exact_233_path_client_scope(self):
        self.assertEqual(233, self.bundle.client_unique_path_count)
        self.assertEqual(257, len(self.bundle.terminal.members))
        self.assertEqual(("1.4.277", "1.4.311"), self.bundle.baseline_versions)

        owner_counts = {}
        for member in self.bundle.terminal.members:
            owner_counts[member.owner] = owner_counts.get(member.owner, 0) + 1
        self.assertEqual(
            {
                "abyss_700099_core": 1,
                "abyss_tower": 23,
                "abyss_weapons": 20,
                "ginovi": 111,
                "lafu_lunar_ny": 90,
                "light_dark_dragons": 12,
            },
            owner_counts,
        )

    def test_loading_the_committed_bundle_is_canonical_and_read_only(self):
        before = {
            path.name: path.read_bytes()
            for path in sorted(CONTRACTS.glob("local-live-*.json"))
        }
        reloaded = self.contract.load_bundle(CONTRACTS)
        self.assertEqual(self.bundle, reloaded)
        self.assertEqual(
            before,
            {
                path.name: path.read_bytes()
                for path in sorted(CONTRACTS.glob("local-live-*.json"))
            },
        )

    def test_provenance_covers_each_path_once_with_independent_baselines(self):
        provenance = self.bundle.provenance
        self.assertEqual(
            "34481b057b90f05df4eb13e8e4fd458a0054f9e7b1c2ec582a8fb6c09cb7df77",
            provenance.inventory_sha256,
        )
        counts = {
            version: sum(
                member.versions[version] is not None
                for member in provenance.members
            )
            for version in provenance.baselines
        }
        self.assertEqual({"1.4.277": 55, "1.4.311": 219}, counts)

        terminal_owners = {}
        for member in self.bundle.terminal.members:
            terminal_owners.setdefault(member.key, set()).add(member.owner)
        self.assertEqual(
            terminal_owners,
            {member.key: set(member.owners) for member in provenance.members},
        )

    def test_present_table_provenance_anchors_unclaimed_rows_in_inventory_digest(self):
        provenance = self.bundle.provenance
        table_evidence = [
            evidence
            for member in provenance.members
            for evidence in member.versions.values()
            if evidence is not None and evidence.table_claims
        ]
        self.assertTrue(table_evidence)
        self.assertTrue(all(
            isinstance(evidence.unclaimed_sha256, str)
            and len(evidence.unclaimed_sha256) == 64
            for evidence in table_evidence
        ))

        first = table_evidence[0]
        changed = replace(first, unclaimed_sha256="0" * 64)
        changed_members = tuple(
            replace(
                member,
                versions={
                    version: (
                        changed
                        if evidence is first
                        else evidence
                    )
                    for version, evidence in member.versions.items()
                },
            )
            for member in provenance.members
        )
        self.assertNotEqual(
            self.provenance.provenance_sha256(provenance.members),
            self.provenance.provenance_sha256(changed_members),
        )

    def test_claim_boundaries_keep_shared_and_negative_ownership_exact(self):
        by_key = {}
        for member in self.bundle.terminal.members:
            by_key.setdefault(member.key, []).append(member)
        rush = by_key[("common", "master/quest/event/rush_event.orderedmap")]
        self.assertEqual(["abyss_700099_core"], [item.owner for item in rush])

        unique = by_key[("common", "master/character/unique_condition.orderedmap")]
        ginovi = next(item for item in unique if item.owner == "ginovi")
        lafu = next(item for item in unique if item.owner == "lafu_lunar_ny")
        self.assertIn("169998", ginovi.claim.outer_keys)
        self.assertEqual(("170000",), lafu.claim.outer_keys)

        forbidden = {
            "master/battle/zako/general_zako.orderedmap",
            "master/battle/zako/zako_level.orderedmap",
            "master/battle/boss/general_enemy_watch.orderedmap",
            "master/battle/boss/orochi.orderedmap",
        }
        self.assertTrue(forbidden.isdisjoint(path for _root, path in by_key))

    def test_server_contract_uses_exact_nested_selectors_and_frozen_migrations(self):
        migration = self.bundle.migrations
        self.assertEqual(1, len(migration.client_tables))
        self.assertEqual(18, len(migration.server_members))
        client = migration.client_tables[0]
        self.assertEqual(
            "master/shop/event_item_shop.orderedmap", client.logical_path
        )
        self.assertNotEqual(client.preimage_sha256, client.terminal_sha256)

        changed = [
            member for member in migration.server_members
            if member.preimage_sha256 != member.terminal_sha256
        ]
        self.assertEqual(4, len(changed))
        ginovi = next(
            member for member in changed
            if member.logical_path == "cdndata/character_text.json"
            and member.selector.keys == ("169999",)
        )
        self.assertEqual("LAFU", ginovi.preimage["169999"][0][1])
        self.assertEqual("GINOVI", ginovi.terminal["169999"][0][1])

        rogue = next(
            member for member in migration.server_members
            if member.logical_path == "rogue_event.json"
        )
        self.assertEqual(("events",), rogue.selector.path)
        self.assertEqual(("700099",), rogue.selector.keys)
        shop = next(
            member for member in migration.server_members
            if member.logical_path == "event_item_shop.json"
        )
        self.assertEqual(("11", "700099"), shop.selector.path)
        self.assertEqual(15, len(shop.selector.keys))

    def test_shop_live_migration_changes_only_name_not_installed_description(self):
        import wf_mod_tool as core

        migration = self.bundle.migrations.client_tables[0]
        baseline_shop = next(
            member for member in self.bundle.baselines["1.4.311"].members
            if member.owner == "abyss_weapons"
            and member.logical_path == migration.logical_path
        )
        self.assertNotEqual(
            baseline_shop.projection_sha256, migration.preimage_sha256
        )
        self.assertNotEqual(
            baseline_shop.source_sha256, migration.preimage.source_sha256
        )
        for before, after in zip(migration.preimage.rows, migration.terminal.rows):
            self.assertEqual(before[:2], after[:2])
            before_csv = core.read_csv_lines(before[2].decode("utf-8"))[0]
            after_csv = core.read_csv_lines(after[2].decode("utf-8"))[0]
            self.assertEqual(
                [7],
                [
                    index for index, (old, new) in enumerate(
                        zip(before_csv, after_csv)
                    )
                    if old != new
                ],
            )
            self.assertEqual(before_csv[11], after_csv[11])
            self.assertIn("练习关", before_csv[11])

    def test_malformed_provenance_and_server_parent_expansion_fail_closed(self):
        provenance_raw = json.loads(
            (CONTRACTS / "local-live-baseline-provenance.json").read_text(
                encoding="utf-8"
            )
        )
        provenance_raw["members"][0]["logical_path"] = "../escape"
        with self.assertRaisesRegex(self.contract.InventoryError, "logical_path"):
            self.contract.parse_provenance(provenance_raw)

        migration_raw = json.loads(
            (CONTRACTS / "local-live-migrations-1.4.312.json").read_text(
                encoding="utf-8"
            )
        )
        rogue = next(
            member for member in migration_raw["server_members"]
            if member["logical_path"] == "rogue_event.json"
        )
        rogue["selector"] = {
            "kind": "object_keys", "path": [], "keys": ["events"]
        }
        with self.assertRaisesRegex(self.server.MigrationError, "selector|digest"):
            self.server.parse_contract(migration_raw)

    def test_contract_json_and_scalar_types_are_strict(self):
        migration_raw = json.loads(
            (CONTRACTS / "local-live-migrations-1.4.312.json").read_text(
                encoding="utf-8"
            )
        )
        migration_raw["contract_id"] = 312
        with self.assertRaisesRegex(self.server.MigrationError, "contract_id"):
            self.server.parse_contract(migration_raw)

        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            duplicate = temp_root / "duplicate.json"
            duplicate.write_text(
                '{"schema":"wf-local-migration-contract/v1",'
                '"schema":"wf-local-migration-contract/v1"}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(self.server.MigrationError, "duplicate JSON"):
                self.server.load_contract(duplicate)
            non_json = temp_root / "nan.json"
            non_json.write_text('{"schema":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(self.contract.InventoryError, "non-JSON"):
                self.contract.load_provenance(non_json)

    def test_client_candidate_exact_rejects_unowned_full_table_drift(self):
        import wf_character_pack as character_pack
        import wf_mod_tool as core
        import wf_release_inventory as inventory

        logical = "master/shop/event_item_shop.orderedmap"
        claim = character_pack.TableClaim("common", logical, "flat", ("owned",))

        def ordered(sentinel: bytes) -> bytes:
            return core.build_orderedmap(core.OrderedMap(
                "fixture", ["sentinel", "owned"], [sentinel, b"row"],
                Path("<fixture>"),
            ))

        raw = ordered(b"before")
        state = self.server.ClientState(
            len(raw), hashlib.sha256(raw).hexdigest(),
            inventory.projection_sha256(raw, claim),
            (("owned", None, b"row"),),
        )
        member = self.server.ClientTableMigration(
            "owner", "common", logical, claim, state, state
        )
        self.assertEqual("terminal", self.server.classify_client_table(member, raw))
        with self.assertRaisesRegex(self.server.MigrationError, "source|drift"):
            self.server.classify_client_table(member, ordered(b"after!"))

    def test_cross_contract_closure_rejects_id_and_migration_source_drift(self):
        validate = getattr(self.contract, "validate_bundle", None)
        self.assertIsNotNone(validate, "bundle validator must be public for builders")

        bad_provenance = replace(self.bundle.provenance, contract_id="alias-contract")
        with self.assertRaisesRegex(self.contract.InventoryError, "provenance.*id"):
            validate(replace(self.bundle, provenance=bad_provenance))

        client = self.bundle.migrations.client_tables[0]
        bad_state = replace(client.terminal, source_sha256="0" * 64)
        bad_client = replace(client, terminal=bad_state)
        bad_migrations = replace(
            self.bundle.migrations, client_tables=(bad_client,)
        )
        with self.assertRaisesRegex(self.contract.InventoryError, "migration.*terminal"):
            validate(replace(self.bundle, migrations=bad_migrations))

        rogue = next(
            member for member in self.bundle.migrations.server_members
            if member.logical_path == "rogue_event.json"
        )
        expanded = replace(
            rogue,
            selector=replace(rogue.selector, path=(), keys=("events",)),
        )
        expanded_members = tuple(
            expanded if member is rogue else member
            for member in self.bundle.migrations.server_members
        )
        with self.assertRaisesRegex(self.contract.InventoryError, "server selector"):
            validate(replace(
                self.bundle,
                migrations=replace(
                    self.bundle.migrations, server_members=expanded_members
                ),
            ))

    def test_release_artifact_gate_rejects_wrong_from_version_and_invalid_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            cdn = Path(temp)
            for root in ("common", "medium", "android"):
                (cdn / f"archive-{root}-diff").mkdir(parents=True)
            fake = (
                cdn / "archive-common-diff"
                / "pinball-1.4.1-1.4.312-1-not-a-zip.zip"
            )
            fake.write_bytes(b"not a zip")
            with self.assertRaisesRegex(
                self.contract.InventoryError, "canonical|ZIP|1.4.311"
            ):
                self.contract.require_release_artifacts(cdn, "1.4.312")

    @unittest.skipUnless(
        os.environ.get("WF_REAL_LOCAL_REPO"), "requires explicit local truth root"
    )
    def test_real_baselines_attest_read_only_over_the_published_local_edge(self):
        import wf_mod_tool as core
        import wf_release_inventory as inventory

        repo = Path(os.environ["WF_REAL_LOCAL_REPO"])
        before = self.contract.snapshot_metadata(
            (repo / ".cdn" / "cn", repo / "assets" / "asset-patch" / "active")
        )
        reports = self.contract.attest_bundle_baselines(
            self.bundle, repo / ".cdn" / "cn", repo
        )
        self.assertEqual((55, 243), tuple(report.member_count for report in reports))

        shop = self.bundle.migrations.client_tables[0]
        historical_shop = inventory.resolve_allowlisted_members(
            repo / ".cdn" / "cn", repo,
            [(shop.root, shop.logical_path)], target_tail="1.4.311",
        )[(shop.root, shop.logical_path)].raw
        historical_rows = inventory.project_claim(
            historical_shop, shop.claim
        ).rows
        for historical, terminal in zip(historical_rows, shop.terminal.rows):
            before_csv = core.read_csv_lines(historical[2].decode("utf-8"))[0]
            after_csv = core.read_csv_lines(terminal[2].decode("utf-8"))[0]
            self.assertEqual(
                [7, 11],
                [
                    index for index, (old, new) in enumerate(
                        zip(before_csv, after_csv)
                    )
                    if old != new
                ],
            )
        # The local compatibility edge has been published into this CDN, so the
        # 1.4.311 baseline above is now resolved past a chain tail that already
        # carries 1.4.312 -- and attestation still may not touch either tree.
        artifacts = self.contract.require_release_artifacts(
            repo / ".cdn" / "cn", "1.4.312"
        )
        self.assertEqual(
            ["pinball-1.4.311-1.4.312-1-localsync0806.zip"],
            [path.name for path in artifacts],
        )
        published = artifacts[0].read_bytes()
        # Compare against this repository's own manifest, not the truth root's:
        # the published archive and the committed one must be the same bytes.
        manifest = json.loads(
            (MOD_TOOLS.parent / "assets" / "asset-patch" / "manifest.json")
            .read_text(encoding="utf-8")
        )
        expected = next(
            record
            for patch in manifest["patches"]
            if patch["id"] == "local-live-compatibility"
            for record in patch["archive_integrity"]
        )
        self.assertEqual(expected["size"], len(published))
        self.assertEqual(
            expected["sha256"], hashlib.sha256(published).hexdigest()
        )
        for package, owner in (
            ("ginovi", "ginovi"),
            ("lafu_lunar_ny", "lafu_lunar_ny"),
        ):
            member = next(
                item for item in self.bundle.terminal.members
                if item.owner == owner
                and item.logical_path == "master/ability/ability.orderedmap"
            )
            historical = (
                repo / "work" / "character_packs" / package / "package"
                / "roots" / "common" / "master" / "ability"
                / "ability.orderedmap"
            ).read_bytes()
            one_member = type(self.bundle.terminal)(
                f"historical-{package}", (member,)
            )
            with self.assertRaisesRegex(
                self.contract.InventoryError, "source (size|sha256) drift"
            ):
                inventory.attest_source_contract(
                    one_member, lambda _member: historical
                )
        self.assertEqual(
            before,
            self.contract.snapshot_metadata(
                (repo / ".cdn" / "cn", repo / "assets" / "asset-patch" / "active")
            ),
        )


if __name__ == "__main__":
    unittest.main()
