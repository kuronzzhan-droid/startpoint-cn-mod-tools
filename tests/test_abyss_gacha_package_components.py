#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure ticket/shop/drop package component compilation tests."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

import wf_abyss_gacha_package_components as module
import wf_abyss_ticket_compile as tickets
import wf_mod_tool as core
import wf_rogue_shop as shop
from tests.test_abyss_ticket_compile import (
    _base_item_assets,
    _item_fixture,
    _ticket_type_fixture,
)
from tests.test_abyss_ticket_drop import quest_fixture, rogue_fixture
from tests.test_rogue_shop import client_fixture, server_fixture


def flat_bytes(rows: dict[str, object], logical: str) -> bytes:
    return core.build_orderedmap(core.OrderedMap(
        logical,
        list(rows),
        [value.encode("utf-8") if isinstance(value, str) else value for value in rows.values()],
        Path("<fixture>"),
    ))


class PackageComponentTests(unittest.TestCase):
    def test_ticket_component_emits_four_payloads_two_claims_and_preserves_donors(self):
        sheet, atlas = _base_item_assets()
        item_before = _item_fixture()
        result = module.compile_ticket_component(
            item_raw=flat_bytes(item_before, tickets.ITEM_T),
            ticket_type_raw=flat_bytes(
                _ticket_type_fixture(), tickets.GACHA_TICKET_TYPE_T
            ),
            item_ids_raw=b"[7,999001,999003]",
            sheet_raw=sheet,
            atlas_raw=atlas,
        )

        self.assertEqual(4, result.report["payload_count"])
        self.assertEqual(2, result.report["table_claim_count"])
        item_after = core.read_orderedmap_file_from_bytes(
            result.roots["common"][tickets.ITEM_T]
        )
        for key in item_before:
            before = item_before[key]
            expected = before.decode() if isinstance(before, bytes) else before
            self.assertEqual(expected, item_after[key])
        self.assertEqual([7, 999001, 999003, 999013, 999014], json.loads(
            result.roots["server"]["item_ids.json"]
        ))
        self.assertTrue(result.report["ticket_contract_closed"])
        self.assertFalse(result.report["writes_live"])
        self.assertEqual({
            tickets.ITEM_SHEET_LOGICAL: {
                "before_sha256": hashlib.sha256(sheet).hexdigest(),
                "before_size": len(sheet),
            },
            tickets.ITEM_ATLAS_LOGICAL: {
                "before_sha256": hashlib.sha256(atlas).hexdigest(),
                "before_size": len(atlas),
            },
        }, result.report["shared_asset_replacements"])
        preservation = result.report["shared_asset_preservation"]
        sheet_prefix = preservation["sheet_prefix"]
        self.assertEqual(
            sheet_prefix["before_rgba_sha256"],
            sheet_prefix["after_prefix_rgba_sha256"],
        )
        self.assertEqual(
            [sheet_prefix["before_dimensions"][0],
             sheet_prefix["before_dimensions"][1] + 22],
            sheet_prefix["after_dimensions"],
        )
        atlas_prefix = preservation["atlas_prefix"]
        self.assertEqual(
            atlas_prefix["before_entries_sha256"],
            atlas_prefix["after_prefix_entries_sha256"],
        )
        self.assertEqual(
            atlas_prefix["before_entry_count"] + 2,
            atlas_prefix["after_entry_count"],
        )

    def test_ticket_component_rejects_preoccupied_or_malformed_owned_ids(self):
        sheet, atlas = _base_item_assets()
        item = _item_fixture()
        item["999013"] = item["999003"]
        with self.assertRaisesRegex(ValueError, "already occupy"):
            module.compile_ticket_component(
                item_raw=flat_bytes(item, tickets.ITEM_T),
                ticket_type_raw=flat_bytes(
                    _ticket_type_fixture(), tickets.GACHA_TICKET_TYPE_T
                ),
                item_ids_raw=b"[7,999001,999003]",
                sheet_raw=sheet,
                atlas_raw=atlas,
            )
        with self.assertRaisesRegex(Exception, "duplicates"):
            module.compile_ticket_component(
                item_raw=flat_bytes(_item_fixture(), tickets.ITEM_T),
                ticket_type_raw=flat_bytes(
                    _ticket_type_fixture(), tickets.GACHA_TICKET_TYPE_T
                ),
                item_ids_raw=b"[7,7,999001,999003]",
                sheet_raw=sheet,
                atlas_raw=atlas,
            )

    def _shop_sources(self) -> tuple[bytes, bytes, bytes]:
        client = shop.build_client_shop(client_fixture(), shop.WEAPONS)
        server, id_map = server_fixture()
        server, id_map = shop.build_server_shop(server, id_map, shop.WEAPONS)
        for key in shop.TICKET_SHOP_IDS:
            client.pop(key)
            server[shop.EVENT_TYPE][shop.EVENT_ID].pop(key)
            id_map.pop(key)
        return (
            flat_bytes(client, shop.SHOP_T),
            json.dumps(server, ensure_ascii=False, separators=(",", ":")).encode(),
            json.dumps(id_map, ensure_ascii=False, separators=(",", ":")).encode(),
        )

    def test_shop_component_adds_only_two_ticket_products_across_three_mirrors(self):
        client_raw, server_raw, id_map_raw = self._shop_sources()
        client_before = core.read_orderedmap_file_from_bytes(client_raw)
        server_before = json.loads(server_raw)
        map_before = json.loads(id_map_raw)

        result = module.compile_shop_component(
            client_raw=client_raw,
            server_shop_raw=server_raw,
            id_map_raw=id_map_raw,
        )

        self.assertEqual(3, result.report["payload_count"])
        self.assertEqual(3, result.report["table_claim_count"])
        client_after = core.read_orderedmap_file_from_bytes(
            result.roots["common"][shop.SHOP_T]
        )
        server_after = json.loads(
            result.roots["server"][shop.SHOP_JSON]
        )
        map_after = json.loads(result.roots["server"][shop.SHOP_ID_MAP_JSON])
        self.assertEqual(
            client_before,
            {key: value for key, value in client_after.items()
             if key not in shop.TICKET_SHOP_IDS},
        )
        self.assertEqual(
            server_before[shop.EVENT_TYPE][shop.EVENT_ID],
            {key: value for key, value in server_after[shop.EVENT_TYPE][shop.EVENT_ID].items()
             if key not in shop.TICKET_SHOP_IDS},
        )
        self.assertEqual(
            map_before,
            {key: value for key, value in map_after.items()
             if key not in shop.TICKET_SHOP_IDS},
        )
        self.assertTrue(result.report["shop_contract_closed"])

    def test_shop_component_rejects_ticket_id_occupied_in_any_mirror(self):
        client_raw, server_raw, id_map_raw = self._shop_sources()
        id_map = json.loads(id_map_raw)
        id_map["9700116"] = {"eventType": 1, "eventId": 2}
        with self.assertRaisesRegex(ValueError, "already occupy"):
            module.compile_shop_component(
                client_raw=client_raw,
                server_shop_raw=server_raw,
                id_map_raw=json.dumps(id_map, separators=(",", ":")).encode(),
            )

    def test_drop_component_outputs_only_rogue_event_and_uses_quest_as_validation(self):
        rogue = rogue_fixture()
        quests = quest_fixture()
        result = module.compile_drop_component(
            rogue_event_raw=json.dumps(rogue, separators=(",", ":")).encode(),
            rush_event_quest_raw=json.dumps(quests, separators=(",", ":")).encode(),
        )

        self.assertEqual({"rogue_event.json"}, set(result.roots["server"]))
        self.assertEqual(
            {"master/quest/event/cnmod_rogue_event.orderedmap"},
            set(result.roots["common"]),
        )
        self.assertNotIn("rush_event_quest.json", result.roots["server"])
        self.assertEqual(2, result.report["payload_count"])
        self.assertEqual(2, result.report["table_claim_count"])
        after = json.loads(result.roots["server"]["rogue_event.json"])
        self.assertEqual(rogue["events"]["700007"], after["events"]["700007"])
        self.assertEqual(999014, after["events"]["700099"]["folder_clear_chance"][0]["id"])
        self.assertEqual(0.05, after["events"]["700099"]["folder_clear_chance"][0]["chance"])
        client = core.read_orderedmap_file_from_bytes(
            result.roots["common"][
                "master/quest/event/cnmod_rogue_event.orderedmap"
            ]
        )
        self.assertEqual({
            "700099": "1,0,999014,1,0.05\n1,0,11003,1,0.5"
        }, client)
        self.assertTrue(result.report["client_server_drop_mirror_exact"])
        self.assertTrue(result.report["drop_contract_closed"])
        self.assertEqual(
            hashlib.sha256(json.dumps(quests, separators=(",", ":")).encode()).hexdigest(),
            result.report["validation_only_sha256"]["rush_event_quest.json"],
        )


if __name__ == "__main__":
    unittest.main()
