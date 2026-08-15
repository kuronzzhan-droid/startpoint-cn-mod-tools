#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Top-level pure compilation tests for the combined replacement package."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest

import wf_abyss_gacha_package_compile as module
import wf_abyss_gacha_package_contract as contract
import wf_abyss_ticket_compile as tickets
import wf_mod_tool as core
import wf_rogue_shop as shop
from tests.summer_thunder_package_fixtures import complete_image
from tests.test_abyss_gacha_compile import _sources as gacha_sources
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
    return contract.SealedSourcePackage(
        roots=image.roots,
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
    def test_compiles_provisional_exact_21_payload_16_claim_addition(self):
        sources = compile_sources()
        additions = module.compile_additions(sources)

        self.assertEqual(21, sum(len(files) for files in additions.roots.values()))
        self.assertEqual(
            {"common": 14, "medium": 0, "android": 0, "server": 7},
            {root: len(files) for root, files in additions.roots.items()},
        )
        self.assertEqual(contract.expected_new_claims(), list(additions.table_claims))
        self.assertEqual(
            {"gacha", "tickets", "shop", "drop", "banners"},
            set(additions.component_reports),
        )
        self.assertFalse(additions.acceptance["all_references_closed"])
        self.assertFalse(additions.acceptance["drop_source_sync_closed"])
        self.assertFalse(additions.acceptance["drop_contract_closed"])
        self.assertFalse(additions.acceptance["package_manifest_eligible"])
        self.assertEqual([], additions.acceptance["unresolved_art_payloads"])
        self.assertFalse(additions.acceptance["writes_live"])

    def test_package_image_is_fail_closed_until_drop_sync_source_is_defined(self):
        with self.assertRaisesRegex(
            contract.PackageAssemblyError, "drop source sync closure is pending"
        ):
            module.compile_package_image(
                source_package(), compile_sources(), generator_git_head="c" * 40
            )

    def test_is_deterministic_does_not_mutate_inputs_and_hash_binds_every_source(self):
        source = source_package()
        sources = compile_sources()
        common_before = dict(sources.gacha_common)
        server_before = dict(sources.gacha_server)

        first = module.compile_additions(sources)
        second = module.compile_additions(sources)

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
                module.compile_additions(sources)
        finally:
            module.compile_ticket_component = original


if __name__ == "__main__":
    unittest.main()
