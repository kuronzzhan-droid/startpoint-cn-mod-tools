#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable, read-only addition-source loader tests."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import wf_abyss_gacha_contract as gacha_contract
import wf_abyss_gacha_package_compile as package_compile
import wf_abyss_gacha_package_sources as module
import wf_abyss_ticket_compile as tickets
import wf_mod_tool as core
import wf_rogue_shop as shop
from tests.test_abyss_gacha_package_compile import compile_sources, source_package


class AdditionSourceLoaderTests(unittest.TestCase):
    def _roots(self, temporary: Path) -> tuple[Path, Path, object]:
        store = temporary / "base347" / "production" / "upload"
        server = temporary / "server" / "assets"
        store.mkdir(parents=True)
        server.mkdir(parents=True)
        sources = compile_sources()
        store_payloads = {
            **sources.gacha_common,
            tickets.ITEM_T: sources.item_raw,
            tickets.GACHA_TICKET_TYPE_T: sources.ticket_type_raw,
            tickets.ITEM_SHEET_LOGICAL: sources.item_sheet_raw,
            tickets.ITEM_ATLAS_LOGICAL: sources.item_atlas_raw,
            shop.SHOP_T: sources.shop_client_raw,
        }
        server_payloads = {
            **sources.gacha_server,
            "item_ids.json": sources.item_ids_raw,
            shop.SHOP_JSON: sources.shop_server_raw,
            shop.SHOP_ID_MAP_JSON: sources.shop_id_map_raw,
            "rogue_event.json": sources.rogue_event_raw,
            "rush_event_quest.json": sources.rush_event_quest_raw,
        }
        for logical, raw in store_payloads.items():
            path = core.table_path(store, logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        for logical, raw in server_payloads.items():
            path = server.joinpath(*logical.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        return store, server, sources

    def test_loads_every_explicit_source_without_writing_or_scanning_unknown_files(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            store, server, expected = self._roots(temporary)
            unknown = store / "unknown-user-wip"
            unknown.write_bytes(b"preserve")
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in temporary.rglob("*") if path.is_file()
            }

            actual = module.load_addition_sources(store, server)

            self.assertEqual(expected.gacha_common, actual.gacha_common)
            self.assertEqual(expected.gacha_server, actual.gacha_server)
            self.assertEqual(expected.item_raw, actual.item_raw)
            self.assertEqual(expected.item_ids_raw, actual.item_ids_raw)
            self.assertEqual(expected.rush_event_quest_raw, actual.rush_event_quest_raw)
            self.assertEqual(set(expected.gacha_common), set(actual.existing_common_paths))
            after = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in temporary.rglob("*") if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(b"preserve", unknown.read_bytes())

    def test_probes_all_new_gacha_paths_and_fails_closed_on_collision_or_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            store, server, _expected = self._roots(Path(temporary_name))
            collision = gacha_contract.CHARACTER_5_ODDS_LOGICAL
            path = core.table_path(store, collision)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"occupied")
            sources = module.load_addition_sources(store, server)
            self.assertIn(collision, sources.existing_common_paths)
            with self.assertRaisesRegex(ValueError, "collision"):
                package_compile.compile_additions(source_package(), sources)

            (server / "rogue_event.json").unlink()
            with self.assertRaisesRegex(
                module.PackageAssemblyError, "rogue_event.json"
            ):
                module.load_addition_sources(store, server)


if __name__ == "__main__":
    unittest.main()
