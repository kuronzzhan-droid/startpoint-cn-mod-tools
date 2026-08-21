#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Top-level pure compilation tests for the combined replacement package."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import unittest

import wf_abyss_gacha_package_compile as module
import wf_abyss_gacha_package_contract as contract
import wf_abyss_ticket_compile as tickets
import wf_abyss_gacha_contract as gacha_contract
import wf_mod_tool as core
import wf_rogue_shop as shop
from tests.summer_thunder_package_fixtures import complete_image
from tests.test_abyss_gacha_compile import (
    _decode_flat,
    _flat,
    _sources as gacha_sources,
)
from tests.test_abyss_gacha_package_components import flat_bytes
from tests.test_abyss_ticket_compile import (
    _base_item_assets,
    _item_fixture,
    _ticket_type_fixture,
)
from tests.test_abyss_ticket_drop import quest_fixture, rogue_fixture
from tests.test_rogue_shop import client_fixture, server_fixture


def source_package() -> contract.SealedSourcePackage:
    image = complete_image(accepted_skill=True)
    manifest = copy.deepcopy(image.manifest)
    manifest["qa"].update({
        "release_ready": True,
        "workspace_input_sha256": "a" * 64,
    })
    common, server = gacha_sources()
    roots = {root: dict(files) for root, files in image.roots.items()}
    roots["common"][gacha_contract.CHARACTER_MASTER_LOGICAL] = common[
        gacha_contract.CHARACTER_MASTER_LOGICAL
    ]
    roots["server"]["character.json"] = server["character.json"]
    for root, logical in (
        ("common", gacha_contract.CHARACTER_MASTER_LOGICAL),
        ("server", "character.json"),
    ):
        raw = roots[root][logical]
        entry = next(
            item for item in manifest["roots"][root]
            if item["logical_path"] == logical
        )
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
        entry["size"] = len(raw)
    return contract.SealedSourcePackage(
        roots=roots,
        manifest=manifest,
        workspace_input_sha256="a" * 64,
        source_locks_sha256="b" * 64,
        package_acceptance={
            "package_manifest_eligible": True,
            "writes_live": False,
        },
        skill_follow_gate={
            "package_manifest_eligible": True,
            "writes_live": False,
        },
    )


def source_package_with_character_rows() -> contract.SealedSourcePackage:
    return source_package()


def compile_sources() -> module.AdditionSources:
    common, server = gacha_sources()
    sheet, atlas = _base_item_assets()
    client = shop.build_client_shop(client_fixture(), shop.WEAPONS)
    server_shop, id_map = server_fixture()
    server_shop, id_map = shop.build_server_shop(
        server_shop, id_map, shop.WEAPONS
    )
    for key in shop.TICKET_SHOP_IDS:
        client.pop(key)
        server_shop[shop.EVENT_TYPE][shop.EVENT_ID].pop(key)
        id_map.pop(key)
    return module.AdditionSources(
        gacha_common=common,
        gacha_server=server,
        existing_common_paths=tuple(common),
        item_raw=flat_bytes(_item_fixture(), tickets.ITEM_T),
        ticket_type_raw=flat_bytes(
            _ticket_type_fixture(), tickets.GACHA_TICKET_TYPE_T
        ),
        item_ids_raw=b"[7,999001,999003]",
        item_sheet_raw=sheet,
        item_atlas_raw=atlas,
        shop_client_raw=flat_bytes(client, shop.SHOP_T),
        shop_server_raw=json.dumps(
            server_shop, ensure_ascii=False, separators=(",", ":")
        ).encode(),
        shop_id_map_raw=json.dumps(
            id_map, ensure_ascii=False, separators=(",", ":")
        ).encode(),
        rogue_event_raw=json.dumps(
            rogue_fixture(), separators=(",", ":")
        ).encode(),
        rush_event_quest_raw=json.dumps(
            quest_fixture(), separators=(",", ":")
        ).encode(),
    )


class CombinedCompileTests(unittest.TestCase):
    def test_compiles_eligible_exact_derived_payload_and_claim_addition(self):
        sources = compile_sources()
        additions = module.compile_additions(source_package(), sources)

        self.assertEqual(22, sum(len(files) for files in additions.roots.values()))
        self.assertEqual(
            {"common": 14, "medium": 1, "android": 0, "server": 7},
            {root: len(files) for root, files in additions.roots.items()},
        )
        self.assertEqual(contract.expected_new_claims(), list(additions.table_claims))
        self.assertEqual(
            {"gacha", "tickets", "shop", "drop", "banners"},
            set(additions.component_reports),
        )
        self.assertTrue(additions.acceptance["all_references_closed"])
        self.assertTrue(additions.acceptance["drop_source_sync_closed"])
        self.assertTrue(additions.acceptance["drop_contract_closed"])
        self.assertTrue(additions.acceptance["package_manifest_eligible"])
        self.assertEqual([], additions.acceptance["unresolved_art_payloads"])
        self.assertFalse(additions.acceptance["writes_live"])
        self.assertEqual(
            contract.DROP_RUNTIME_SOURCE_SYNC,
            additions.component_reports["drop"]["runtime_source_sync"],
        )

    def test_package_image_closes_after_exact_reviewed_runtime_source_sync(self):
        image = module.compile_package_image(
            source_package(), compile_sources(), generator_git_head="c" * 40
        )

        audit = contract.audit_package_image(image)
        self.assertTrue(audit["apply_ready"])
        self.assertTrue(audit["drop_source_sync_closed"])
        self.assertEqual(
            contract.DROP_RUNTIME_SOURCE_SYNC,
            audit["drop_runtime_source_sync"],
        )
        self.assertEqual(
            contract.DROP_RUNTIME_SOURCE_SYNC,
            image.source_report["source_locks"]["component_reports"]["drop"][
                "runtime_source_sync"
            ],
        )

    def test_is_deterministic_does_not_mutate_inputs_and_hash_binds_every_source(self):
        source = source_package()
        sources = compile_sources()
        common_before = dict(sources.gacha_common)
        server_before = dict(sources.gacha_server)

        source = source_package()
        first = module.compile_additions(source, sources)
        second = module.compile_additions(source, sources)

        self.assertEqual(first, second)
        self.assertEqual(common_before, sources.gacha_common)
        self.assertEqual(server_before, sources.gacha_server)
        self.assertGreaterEqual(len(first.input_sha256), 18)
        self.assertTrue(all(
            len(value) == 64 and value == value.lower()
            for value in first.input_sha256.values()
        ))
        self.assertEqual(
            hashlib.sha256(sources.rush_event_quest_raw).hexdigest(),
            first.input_sha256["drop:rush_event_quest.json"],
        )

    def test_rejects_any_component_output_or_claim_drift(self):
        sources = compile_sources()
        original = module.compile_ticket_component

        def drifted(**kwargs):
            result = original(**kwargs)
            roots = {root: dict(files) for root, files in result.roots.items()}
            roots["common"]["unexpected/path"] = b"drift"
            return type(result)(
                roots, result.table_claims, result.input_sha256, result.report
            )

        module.compile_ticket_component = drifted
        try:
            with self.assertRaisesRegex(contract.PackageAssemblyError, "payload set"):
                module.compile_additions(source_package(), sources)
        finally:
            module.compile_ticket_component = original

    def test_merges_old_package_character_claims_into_validation_sources_only(self):
        source = source_package_with_character_rows()
        sources = compile_sources()
        common = dict(sources.gacha_common)
        rows = _decode_flat(
            common[gacha_contract.CHARACTER_MASTER_LOGICAL],
            gacha_contract.CHARACTER_MASTER_LOGICAL,
        )
        rows.pop("139998")
        common[gacha_contract.CHARACTER_MASTER_LOGICAL] = _flat(
            gacha_contract.CHARACTER_MASTER_LOGICAL,
            {key: value.decode() for key, value in rows.items()},
        )
        server = dict(sources.gacha_server)
        characters = json.loads(server["character.json"])
        characters.pop("139998")
        server["character.json"] = json.dumps(
            characters, separators=(",", ":")
        ).encode()
        missing = dataclasses.replace(
            sources, gacha_common=common, gacha_server=server
        )

        additions = module.compile_additions(source, missing)

        report = additions.component_reports["gacha"]
        self.assertTrue(report["source_package_character_overlay"])
        self.assertNotIn(
            gacha_contract.CHARACTER_MASTER_LOGICAL,
            additions.roots["common"],
        )
        self.assertNotIn("character.json", additions.roots["server"])


if __name__ == "__main__":
    unittest.main()
