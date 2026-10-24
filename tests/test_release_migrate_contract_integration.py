# -*- coding: utf-8 -*-
"""Task3A 严格合同到终态 planner 的真实投影集成回归。"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_local_server_contract as source_contract  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_release_migrate as migrate  # noqa: E402


def _flat(logical: str, rows: tuple[tuple[str, str | None, bytes], ...]) -> bytes:
    return core.build_orderedmap(core.OrderedMap(
        logical,
        [outer for outer, inner, _raw in rows if inner is None],
        [raw for _outer, inner, raw in rows if inner is None],
        Path("<contract-fixture>"),
    ))


class Task3AAdapterPlannerIntegrationTest(unittest.TestCase):
    def test_adapter_binds_server_leaf_hashes_and_full_planner_reaches_terminal(self):
        source = source_contract.load_contract(migrate.DEFAULT_CONTRACT_PATH)
        frozen = migrate.load_frozen_contract()
        members = {
            (member.logical_path, member.selector.keys[0]): member
            for member in source.server_members
            if member.logical_path in {
                migrate.SERVER_CHARACTER, migrate.SERVER_CHARACTER_TEXT,
            }
        }

        client: dict[str, bytes] = {}
        for relative, logical in (
            (migrate.SERVER_CHARACTER, migrate.CHARACTER_LOGICAL),
            (migrate.SERVER_CHARACTER_TEXT, migrate.CHARACTER_TEXT_LOGICAL),
        ):
            rows = []
            for key in ("169998", "169999"):
                terminal = members[(relative, key)].terminal
                self.assertEqual({key}, set(terminal))
                rows.append((key, terminal[key][0]))
            client[logical] = core.build_orderedmap(core.OrderedMap(
                logical,
                [key for key, _cells in rows],
                [
                    core.write_csv_lines([cells]).encode("utf-8")
                    for _key, cells in rows
                ],
                Path("<contract-client-fixture>"),
            ))

        shop = source.client_tables[0]
        shop_before = _flat(migrate.SHOP_LOGICAL, shop.preimage.rows)
        shop_after = _flat(migrate.SHOP_LOGICAL, shop.terminal.rows)
        client[migrate.SHOP_LOGICAL] = shop_before
        # 合同只嵌入 owned rows，无法重建含无关行的 full source；本用例仅替换
        # shop 整表 fingerprint，所有 server specs 仍来自真实严格 adapter。
        frozen = replace(
            frozen,
            shop_preimage=migrate.ClientSourceSpec(
                len(shop_before), hashlib.sha256(shop_before).hexdigest(),
            ),
            shop_terminal=migrate.ClientSourceSpec(
                len(shop_after), hashlib.sha256(shop_after).hexdigest(),
            ),
        )

        server: dict[str, bytes] = {}
        for relative in (migrate.SERVER_CHARACTER, migrate.SERVER_CHARACTER_TEXT):
            payload = {
                key: members[(relative, key)].preimage[key]
                for key in ("169998", "169999")
            }
            server[relative] = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8")
        lookup = next(
            member for member in source.server_members
            if member.logical_path == migrate.SERVER_EQUIPMENT_LOOKUP
        )
        server[migrate.SERVER_EQUIPMENT_LOOKUP] = json.dumps(
            lookup.preimage, ensure_ascii=False, indent=1,
        ).encode("utf-8")

        plan = migrate.plan_terminal_migration(client, server, contract=frozen)

        for relative in (migrate.SERVER_CHARACTER, migrate.SERVER_CHARACTER_TEXT):
            actual = migrate.strict_json_object(plan.server_after[relative], relative)
            for key in ("169998", "169999"):
                self.assertEqual(members[(relative, key)].terminal[key], actual[key])
        self.assertEqual(shop_after, plan.client_after[migrate.SHOP_LOGICAL])


if __name__ == "__main__":
    unittest.main()
