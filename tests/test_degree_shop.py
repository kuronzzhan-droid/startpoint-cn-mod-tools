# -*- coding: utf-8 -*-
"""资深玩家称号商店生成器契约测试（仅使用临时 store/assets）。"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
import wf_degree_shop as shop  # noqa: E402
import wf_rogue_rewards as rogue_rewards  # noqa: E402
import wf_rogue_shop as rogue_shop  # noqa: E402


def template_row() -> list[str]:
    return [f"donor-{index}" for index in range(shop.CLIENT_COLUMNS)]


class DegreeShopContractTest(unittest.TestCase):
    def test_builds_exact_client_server_and_id_map_rows(self):
        client = {
            "310200": core.write_csv_lines([template_row()]),
            "9700117": "unrelated-client-row",
        }
        server = {
            "11": {"700099": {"9700117": {"unrelated": True}}},
            "2": {"100006": {"310200": {"donor": True}}},
        }
        id_map = {
            "9700117": {"eventType": 11, "eventId": 700099},
            "310200": {"eventType": 2, "eventId": 100006},
        }
        originals = copy.deepcopy((client, server, id_map))

        built_client, built_server, built_map = shop.build_contract(
            client, server, id_map
        )

        self.assertEqual(originals, (client, server, id_map))
        row = core.read_csv_lines(built_client[shop.SHOP_ITEM_ID])[0]
        self.assertEqual(shop.CLIENT_COLUMNS, len(row))
        expected = {
            0: "6", 1: "700099", 2: "11",
            3: "(None)", 4: "(None)", 5: "(None)", 6: "(None)",
            7: "资深玩家", 8: "9700118", 9: "1", 10: "18",
            11: "资深玩家专属称号。使用500万星导石兑换，每个存档限1次。",
            12: "(None)", 13: "item/etc/degree", 14: "5",
            15: "0", 16: "5000000",
            26: "2000-01-01 00:00:00", 27: "2099-12-31 23:59:59",
            28: "0", 29: "1", 30: "1", 31: "(None)",
            32: "6", 33: "(None)", 34: "1", 50: "false",
        }
        expected.update({index: "(None)" for index in range(17, 26)})
        expected.update({index: "(None)" for index in range(35, 50)})
        for column, value in expected.items():
            self.assertEqual(value, row[column], f"c{column}")
        self.assertFalse(row[13].endswith(".png"))
        self.assertFalse(row[13].isdigit())
        self.assertNotEqual("5", row[32], "客户端 c32 不能与服务端 reward type 对齐")

        product = built_server["11"]["700099"][shop.SHOP_ITEM_ID]
        self.assertEqual([], product["costs"])
        self.assertEqual(
            [{"type": 5, "id": 9900006, "count": 1}], product["rewards"]
        )
        self.assertEqual({"type": 0, "amount": 5_000_000}, product["userCost"])
        self.assertEqual(1, product["stock"])
        self.assertEqual(
            {"eventType": 11, "eventId": 700099},
            built_map[shop.SHOP_ITEM_ID],
        )
        self.assertEqual("unrelated-client-row", built_client["9700117"])
        self.assertEqual({"unrelated": True}, built_server["11"]["700099"]["9700117"])

    def test_validation_fails_closed_on_path_or_enum_conflation(self):
        client, server, id_map = shop.build_contract(
            {"310200": core.write_csv_lines([template_row()])},
            {"11": {"700099": {}}},
            {},
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            for logical in (
                shop.THUMBNAIL_LOGICAL + ".png",
                shop.DEGREE_IMAGE_LOGICAL + ".png",
            ):
                target = core.table_path(store, logical)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fixture")
            self.assertEqual([], shop.validate_contract(client, server, id_map, store))

            bad_client = copy.deepcopy(client)
            row = core.read_csv_lines(bad_client[shop.SHOP_ITEM_ID])[0]
            row[13] = "9900006"
            row[32] = "5"
            bad_client[shop.SHOP_ITEM_ID] = core.write_csv_lines([row])
            problems = shop.validate_contract(bad_client, server, id_map, store)
            self.assertTrue(any("c13" in problem and "数字" in problem for problem in problems))
            self.assertTrue(any("c32" in problem and "6" in problem for problem in problems))

            bad_server = copy.deepcopy(server)
            bad_server["11"]["700099"][shop.SHOP_ITEM_ID]["rewards"][0]["type"] = 6
            problems = shop.validate_contract(client, bad_server, id_map, store)
            self.assertTrue(any("reward" in problem and "type=5" in problem for problem in problems))

    def test_thumbnail_uses_the_locked_base_texture_key_without_adding_pending(self):
        client, server, id_map = shop.build_contract(
            {"310200": core.write_csv_lines([template_row()])},
            {"11": {"700099": {}}},
            {},
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            degree_image = core.table_path(
                store, shop.DEGREE_IMAGE_LOGICAL + ".png"
            )
            degree_image.parent.mkdir(parents=True, exist_ok=True)
            degree_image.write_bytes(b"fixture")

            self.assertEqual([], shop.validate_contract(client, server, id_map, store))
            self.assertFalse(core.table_path(
                store, shop.THUMBNAIL_LOGICAL + ".png"
            ).exists())

    def test_write_requires_task1_pending_and_appends_only_client_table_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = root / "store"
            assets = root / "assets"
            pending = root / "sync_pending.json"
            assets.mkdir()
            client = {"310200": core.write_csv_lines([template_row()])}
            table_path = core.table_path(store, shop.SHOP_LOGICAL)
            table_path.parent.mkdir(parents=True, exist_ok=True)
            quest.save_table(shop.SHOP_LOGICAL, client, path=table_path, backup=False)
            (assets / "event_item_shop.json").write_text(
                json.dumps({"11": {"700099": {}}}), encoding="utf-8"
            )
            (assets / "event_item_shop_id_map.json").write_text("{}", encoding="utf-8")
            pending.write_text(json.dumps(shop.TASK1_PENDING), encoding="utf-8")
            for logical in (
                shop.THUMBNAIL_LOGICAL + ".png",
                shop.DEGREE_IMAGE_LOGICAL + ".png",
            ):
                target = core.table_path(store, logical)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fixture")

            result = shop.write_contract(store=store, assets_dir=assets, pending_path=pending)

            self.assertEqual(shop.SHOP_ITEM_ID, result["shop_item_id"])
            self.assertEqual(
                [*shop.TASK1_PENDING, table_path.relative_to(store).as_posix()],
                json.loads(pending.read_text(encoding="utf-8")),
            )
            self.assertEqual([], shop.verify_paths(store, assets))
            self.assertEqual([], list(root.rglob("*.bak*")))
            for name in ("event_item_shop.json", "event_item_shop_id_map.json"):
                target = assets / name
                parsed = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(
                    json.dumps(parsed, ensure_ascii=False).encode("utf-8"),
                    target.read_bytes(),
                )

            pending.write_text(json.dumps([*shop.TASK1_PENDING, "foreign/hash"]), encoding="utf-8")
            with self.assertRaisesRegex(shop.DegreeShopError, "pending"):
                shop.write_contract(store=store, assets_dir=assets, pending_path=pending)

    def test_cli_dry_run_is_read_only_and_verify_checks_written_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = root / "store"
            assets = root / "assets"
            pending = root / "sync_pending.json"
            assets.mkdir()
            table_path = core.table_path(store, shop.SHOP_LOGICAL)
            table_path.parent.mkdir(parents=True, exist_ok=True)
            quest.save_table(
                shop.SHOP_LOGICAL,
                {"310200": core.write_csv_lines([template_row()])},
                path=table_path,
                backup=False,
            )
            (assets / "event_item_shop.json").write_text(
                json.dumps({"11": {"700099": {}}}), encoding="utf-8"
            )
            (assets / "event_item_shop_id_map.json").write_text("{}", encoding="utf-8")
            pending.write_text(json.dumps(shop.TASK1_PENDING), encoding="utf-8")
            for logical in (
                shop.THUMBNAIL_LOGICAL + ".png",
                shop.DEGREE_IMAGE_LOGICAL + ".png",
            ):
                target = core.table_path(store, logical)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fixture")

            args = [
                "--store", str(store),
                "--assets-dir", str(assets),
                "--pending", str(pending),
            ]
            before = (table_path.read_bytes(), (assets / "event_item_shop.json").read_bytes())
            self.assertEqual(0, shop.main(args))
            self.assertEqual(before, (table_path.read_bytes(), (assets / "event_item_shop.json").read_bytes()))
            self.assertEqual(1, shop.main([*args, "--verify"]))

            shop.write_contract(store=store, assets_dir=assets, pending_path=pending)
            self.assertEqual(0, shop.main([*args, "--verify"]))

    def test_rogue_shop_rerun_preserves_ticket_and_degree_rows(self):
        client = {
            "310200": core.write_csv_lines([template_row()]),
            "9700116": "ticket-116",
            "9700117": "ticket-117",
        }
        server = {"11": {"700099": {
            "9700116": {"ticket": 116},
            "9700117": {"ticket": 117},
        }}}
        id_map = {
            "9700116": {"eventType": 11, "eventId": 700099},
            "9700117": {"eventType": 11, "eventId": 700099},
        }
        client, server, id_map = shop.build_contract(client, server, id_map)

        rerun_client = rogue_shop.build_client_shop(client, rogue_rewards.WEAPONS)
        rerun_server, rerun_map = rogue_shop.build_server_shop(
            server, id_map, rogue_rewards.WEAPONS
        )

        self.assertEqual("ticket-116", rerun_client["9700116"])
        self.assertEqual("ticket-117", rerun_client["9700117"])
        self.assertEqual(client[shop.SHOP_ITEM_ID], rerun_client[shop.SHOP_ITEM_ID])
        self.assertEqual({"ticket": 116}, rerun_server["11"]["700099"]["9700116"])
        self.assertEqual({"ticket": 117}, rerun_server["11"]["700099"]["9700117"])
        self.assertEqual(server["11"]["700099"][shop.SHOP_ITEM_ID], rerun_server["11"]["700099"][shop.SHOP_ITEM_ID])
        self.assertEqual(id_map[shop.SHOP_ITEM_ID], rerun_map[shop.SHOP_ITEM_ID])
        self.assertEqual([], rogue_shop.validate_shop(rerun_client, rerun_server, rerun_map))


if __name__ == "__main__":
    unittest.main()
