# -*- coding: utf-8 -*-
"""武器扭蛋 990003 构建器门禁（设计 §3.1 校验、§12.2）。

live（store / assets / 官方 1.4.0 全量档）只读；暂存只写临时目录。live 已上线本池后再跑，
暂存差异为空也照样成立（构建的是目标态），拼接/重打包另有合成数据用例保证有牙。
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zlib
from fractions import Fraction
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_assets as assets  # noqa: E402
import wf_gacha_odds_sync as odds  # noqa: E402
import wf_share_update_codec as codec  # noqa: E402
import wf_weapon_gacha as W  # noqa: E402

LIVE: W.Live
OUT: dict
PAYLOADS: dict
EMPTY_ART: tempfile.TemporaryDirectory


_LIVE_READY = False


def _prepare_live():
    global _LIVE_READY
    if _LIVE_READY:
        return
    from external_sources import require_live_store
    require_live_store()
    global LIVE, OUT, PAYLOADS, EMPTY_ART
    LIVE = W.Live()
    OUT = W.build(LIVE)
    EMPTY_ART = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(EMPTY_ART.cleanup)
    PAYLOADS = W.stage_payloads(LIVE, OUT, art_dir=Path(EMPTY_ART.name))
    _LIVE_READY = True


class _LiveCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _prepare_live()


OWNED_KEYS = {
    W.GACHA_LOGICAL: {W.GACHA_KEY},
    W.FEATURE_LOGICAL: {W.GACHA_KEY},
    W.RICH_TEXT_MASTER_LOGICAL: {W.RICH_TEXT_ID},
    W.ITEM_LOGICAL: {"999019", "999020"},
    W.SHOP_LOGICAL: {"990099032", "990099033", "990099034", *W.DELETED_SHOP_KEYS},
}
SHOP_KEYS = ("990099032", "990099033", "990099034")


class PoolTests(_LiveCase):
    def test_no_problems(self):
        self.assertEqual([], OUT["problems"])
        self.assertEqual([], PAYLOADS["problems"])

    def test_composition_and_display_order(self):
        tiers = OUT["tiers"]
        self.assertEqual((335, 80, 37), (len(tiers[5]), len(tiers[4]), len(tiers[3])))
        ids5 = [r.id for r in tiers[5]]
        self.assertEqual(W.DEATHBRINGER, ids5[0])
        self.assertEqual(list(W.CURSED), ids5[1:30])
        self.assertEqual(W.PARADOX, ids5[30])
        self.assertEqual(list(W.ABYSS), ids5[31:46])
        official5 = ids5[46:]
        self.assertEqual(289, len(official5))
        self.assertEqual(sorted(official5), official5)
        for rank in (4, 3):
            ids = [r.id for r in tiers[rank]]
            self.assertEqual(sorted(ids), ids)
        every = [r.id for rows in tiers.values() for r in rows]
        self.assertEqual(len(every), len(set(every)))
        self.assertNotIn(5095000, every)
        self.assertFalse(set(range(100013, 100024)) & set(every))

    def test_rank_matches_live_equipment_and_all_are_weapons(self):
        equipment = LIVE.flat(W.EQUIPMENT_LOGICAL)
        for rank, rows in OUT["tiers"].items():
            for row in rows:
                cells = equipment[str(row.id)]
                self.assertEqual((str(rank), "0"), (cells[11], cells[2]), row.id)

    def test_integer_weights(self):
        five = OUT["tiers"][5]
        self.assertEqual(22800, sum(r.weight for r in five))
        by_id = {r.id: r for r in five}
        self.assertEqual({456}, {by_id[i].weight for i in W.CURSED})
        self.assertEqual(152, by_id[W.DEATHBRINGER].weight)
        self.assertEqual(0, by_id[W.PARADOX].weight)
        self.assertEqual({31}, {r.weight for r in five[31:]})
        self.assertEqual({1}, {r.weight for r in OUT["tiers"][4] + OUT["tiers"][3]})

    def test_exact_probabilities(self):
        rates = W.exact_rates(OUT["tiers"])
        self.assertEqual(100, sum(rates.values()))
        self.assertEqual([15, 25, 60], [sum(rates[r.id] for r in OUT["tiers"][k]) for k in (5, 4, 3)])
        self.assertEqual({Fraction(3, 10)}, {rates[i] for i in W.CURSED})
        self.assertEqual(Fraction(1, 10), rates[W.DEATHBRINGER])
        self.assertEqual(0, rates[W.PARADOX])

    def test_flags(self):
        five = {r.id: r for r in OUT["tiers"][5]}
        self.assertTrue(five[W.DEATHBRINGER].rate_up)
        self.assertEqual([W.DEATHBRINGER], [r.id for rows in OUT["tiers"].values() for r in rows if r.rate_up])
        exchangeable = [r.id for rank in (5, 4, 3) for r in OUT["tiers"][rank] if r.exchangeable]
        self.assertEqual(list(W.CURSED), exchangeable)
        self.assertFalse(five[W.PARADOX].exchangeable)
        self.assertTrue(all(five[i].limited for i in (W.DEATHBRINGER, W.PARADOX, *W.CURSED, *W.ABYSS)))

    def test_client_display_strings(self):
        tiers = OUT["tiers"]
        shown = W.client_display(tiers)
        self.assertEqual("0.300", shown[W.CURSED[0]])
        self.assertEqual("0.100", shown[W.DEATHBRINGER])
        self.assertEqual("0.000", shown[W.PARADOX])
        self.assertEqual("0.020", shown[W.ABYSS[0]])
        self.assertEqual("0.020", shown[tiers[5][-1].id])
        self.assertEqual({"0.312"}, {shown[r.id] for r in tiers[4]})
        self.assertEqual({"1.621"}, {shown[r.id] for r in tiers[3]})
        tenth = W.client_display(tiers, guarantee=True)
        self.assertEqual(("0.300", "1.062", "0.000"),
                         (tenth[W.CURSED[0]], tenth[tiers[4][0].id], tenth[tiers[3][0].id]))
        self.assertEqual(["15.00", "85.00"], [odds.fmt_rarity(W.guarantee_weight(r) / 10) for r in (5, 4)])
        self.assertEqual(["15.00", "25.00", "60.00"], [odds.fmt_rarity(W.rarity_weight(r) / 10) for r in (5, 4, 3)])


class ClientRowTests(_LiveCase):
    def test_column_counts(self):
        rows = OUT["rows"]
        self.assertEqual(47, len(rows[W.GACHA_LOGICAL][W.GACHA_KEY]))
        self.assertEqual({23}, {len(r) for r in rows[W.ITEM_LOGICAL].values()})
        self.assertEqual({50}, {len(r) for r in OUT["shop_target"]["rows"].values()})
        self.assertEqual(9, len(OUT["feature"][W.GACHA_KEY]["1"]))

    def test_gacha_row_contract(self):
        row = OUT["rows"][W.GACHA_LOGICAL][W.GACHA_KEY]
        self.assertEqual(["cnmod_weapon_gacha", "武器扭蛋", "3", "dynamic/gacha_list_banner/cnmod_weapon_gacha", "2"],
                         row[:5])
        self.assertEqual(["1", "4", "cnmod_weapon_gacha_rarity", "rich_text/cnmod_weapon_gacha_note", "1"], row[9:14])
        self.assertEqual([""] * 8, row[14:22])
        self.assertEqual(["cnmod_weapon_gacha_3", "cnmod_weapon_gacha_4", "cnmod_weapon_gacha_5", "1", "false",
                          "999019", "999020", "2000-01-01 00:00:00", "2199-12-31 23:59:59"], row[22:31])
        self.assertEqual(("73", "74", "true"), (row[33], row[34], row[44]))
        server = OUT["server_gacha"]
        self.assertEqual((1, 2, 999019, 999020, False, 4), (server["type"], server["pageKind"],
                         server["onceTicketItemId"], server["tenTicketItemId"],
                         server["wildcardTicketAvailable"], server["guaranteeRarity"]))
        self.assertEqual({"normal": [150, 250, 600], "multiGuarantee": [150, 850]}, server["rankRates"])

    def test_client_odds_equal_server_row_by_row(self):
        pool = OUT["server_gacha"]["pool"]
        self.assertEqual(["5,150", "4,250", "3,600"], OUT["odds"][W.RARITY_ODDS_ID])
        for group, rank in (("1", 5), ("2", 4), ("3", 3)):
            lines = OUT["odds"][W.EQUIPMENT_ODDS_IDS[rank]]
            self.assertEqual(len(pool[group]), len(lines))
            for entry, line in zip(pool[group], lines):
                cells = line.split(",")
                self.assertEqual(6, len(cells))
                self.assertEqual([entry["id"], rank, entry["odds"]], [int(c) for c in cells[:3]])
                self.assertEqual([entry["isRateUp"], entry["isLimited"], entry["isExchangeable"]],
                                 [c == "true" for c in cells[3:]])
                self.assertEqual({"id", "rank", "odds", "isRateUp", "isLimited", "isExchangeable", "rarity"},
                                 set(entry))

    def test_nested_files_round_trip_byte_exact(self):
        for sid in (W.RARITY_ODDS_ID, *W.EQUIPMENT_ODDS_IDS.values()):
            logical = W.odds_logical(sid)
            raw = OUT["files"][logical]
            outer, inner, lines = W.read_nested_bytes(raw, logical)
            self.assertEqual((sid, [str(i) for i in range(len(lines))], OUT["odds"][sid]), (outer, inner, lines))
            self.assertEqual(raw, odds.build_nested(outer, inner, lines))
            with tempfile.TemporaryDirectory() as tmp:     # 同一文件走发布工具自己的读法
                path = Path(tmp) / "t.orderedmap"
                path.write_bytes(raw)
                self.assertEqual((sid, inner, lines), odds.read_nested(path, logical))
                odds.assert_roundtrip(path, logical)

    def test_feature_and_rich_text_keys(self):
        self.assertEqual({"1": ["1", "dynamic/gacha_banner/cnmod_weapon_gacha", "", "", "", "", "(None)", "", ""]},
                         OUT["feature"][W.GACHA_KEY])
        self.assertEqual({W.RICH_TEXT_ID: None}, OUT["rows"][W.RICH_TEXT_MASTER_LOGICAL])
        html = W.inflate_raw(OUT["files"][W.RICH_TEXT_BODY_LOGICAL])
        self.assertEqual(OUT["html"], html)
        for needle in ("武器扭蛋券", "五重决战", "★5武器总出现概率为15%", "0.3%", "死亡使者·终式概率UP",
                       "悖论武器登记于本扭蛋但出现概率为0%", "第10次必定获得★4以上", "250点", "诅咒武器", "突破",
                       "兑换点数不会丢失"):
            self.assertIn(needle, html)
        # 作者 0928「除了武器名字，其他地方都不要英文的，写悖论」：说明正文不写 PARADOX
        self.assertNotIn("PARADOX", html)
        self.assertEqual("悖论武器", W.PARADOX_CLASS)

    def test_ticket_rows_and_icons(self):
        atlas = LIVE.atlas_names()
        rows = OUT["rows"][W.ITEM_LOGICAL]
        for ticket, gacha_type in zip(W.TICKETS, ("3", "4")):
            row = rows[str(ticket.item_id)]
            self.assertIn(row[3], atlas)
            self.assertTrue(row[3].startswith("item/spends/tickets/ticket_equipment_00"))
            self.assertEqual(("8", gacha_type, "4"), (row[6], row[13], row[14]))
            self.assertNotIn(",", row[5])
            self.assertEqual(("2000-01-01 00:00:00", "2199-12-31 23:59:59"), (row[19], row[20]))

    def test_shop_rows_prices_and_deletions(self):
        """武器觉醒与新掉落设计 §5.4：032=王币×1、033=王币×10；034=王币×500+五王心核×5+深渊觉醒核×10→禁忌星铁，
        每人限购 60（作者 0928 晚）；c9 6/5/4。"""
        self.assertEqual(tuple(str(k) for k in range(990099003, 990099032)), W.DELETED_SHOP_KEYS)
        self.assertEqual(29, len(W.DELETED_SHOP_KEYS))
        self.assertEqual({W.SHOP_LOGICAL: W.DELETED_SHOP_KEYS}, OUT["flat_delete"])
        self.assertEqual((10000310, 10000311), (W.KING_COIN_ID, W.STAR_STEEL_ID))
        rows = OUT["shop_target"]["rows"]
        self.assertEqual(set(SHOP_KEYS), set(rows))
        once, ten, steel = (rows[k] for k in SHOP_KEYS)
        self.assertEqual(["10000310", "1", "(None)", "", "(None)", "", "(None)", ""], once[17:25])
        self.assertEqual(["10000310", "10", "(None)", "", "(None)", "", "(None)", ""], ten[17:25])
        self.assertEqual(["10000310", "500", "10000147", "5", "2370100", "10", "(None)", ""], steel[17:25])
        self.assertEqual((10000147, 2370100), (W.FIVE_KING_CORE_ID, W.ABYSS_CORE_ID))
        for row, reward, order, limit in ((once, "999019", "6", None), (ten, "999020", "5", None),
                                          (steel, "10000311", "4", "60")):
            self.assertEqual(("99", order, "5", "0", reward, "1"), (row[0], row[9], row[13], row[32], row[33], row[34]))
            # c28 单次上限 = min(99, 限购)、c29 max_frequency = 限购（先例 990099001：5/5）
            self.assertEqual(("2000-01-01 00:00:00", "2099-12-31 23:59:59", "1", limit or "99"), tuple(row[25:29]))
            self.assertEqual((limit or "(None)", "(None)", "(None)"), tuple(row[29:32]))
            self.assertLessEqual(len(row[10]), 60)
            self.assertNotIn(",", row[10])
            self.assertNotIn("PARADOX", row[10])
            self.assertIn("深界王币", row[10])
        self.assertIn("五王心核", steel[10])
        self.assertIn("深渊觉醒核", steel[10])
        self.assertIn("悖论武器", steel[10])
        self.assertEqual(("禁忌星铁", "item/materials/mod/cursed/forbidden_star_steel"), (steel[6], steel[12]))
        self.assertEqual(("item/spends/tickets/ticket_equipment_001", "item/spends/tickets/ticket_equipment_002"),
                         (once[12], ten[12]))
        # 界面按 c9 倒序：032 > 033 > 034 > 990099002(2) > 990099001(1)
        live_shop = LIVE.flat(W.SHOP_LOGICAL)
        self.assertEqual(("2", "1"), (live_shop["990099002"][9], live_shop["990099001"][9]))
        server = OUT["shop_target"]["server"]
        self.assertEqual({"costs": [{"id": 10000310, "amount": 10}],
                          "rewards": [{"type": 0, "id": 999020, "count": 1}],
                          "availableFrom": "2000-01-01 00:00:00", "availableUntil": "2099-12-31 23:59:59",
                          "stock": 9999}, server["990099033"])
        self.assertEqual([{"id": 10000310, "amount": 1}], server["990099032"]["costs"])
        self.assertEqual({"costs": [{"id": 10000310, "amount": 500}, {"id": 10000147, "amount": 5},
                                    {"id": 2370100, "amount": 10}],
                          "rewards": [{"type": 0, "id": 10000311, "count": 1}],
                          "availableFrom": "2000-01-01 00:00:00", "availableUntil": "2099-12-31 23:59:59",
                          "stock": 60}, server["990099034"])
        self.assertEqual((None, None, 60), tuple(p.limit for p in W.shop_products()))
        self.assertEqual({k: 99 for k in SHOP_KEYS}, OUT["shop_target"]["map"])
        shop = OUT["server"][W.SERVER_SHOP]
        self.assertEqual(("99",), shop.path)
        self.assertEqual(W.DELETED_SHOP_KEYS, shop.delete)
        self.assertEqual(W.DELETED_SHOP_KEYS, OUT["server"][W.SERVER_SHOP_MAP].delete)

    def test_old_prices_are_never_written_back(self):
        """暂缓时不碰 032–034；上架时只写新价。无论哪种，暂存里 032–034 都不出现结晶/图纸成本（旧价），且都收王币。"""
        shop = OUT["server"][W.SERVER_SHOP]
        if OUT["report"]["shop_deferred"]:
            self.assertEqual({}, OUT["rows"][W.SHOP_LOGICAL])
            self.assertEqual({}, shop.upsert)
            self.assertEqual({}, OUT["server"][W.SERVER_SHOP_MAP].upsert)
            self.assertTrue(OUT["warnings"])
            self.assertTrue(all(w.startswith("五重商店 032–034 暂缓") for w in OUT["warnings"]))
        else:
            self.assertEqual(OUT["shop_target"]["rows"], OUT["rows"][W.SHOP_LOGICAL])
            self.assertEqual(OUT["shop_target"]["server"], shop.upsert)
        if W.SERVER_SHOP in PAYLOADS["server"]:
            staged = json.loads(PAYLOADS["server"][W.SERVER_SHOP][0].decode("utf-8"))["99"]
            for key in SHOP_KEYS:
                if key in staged:
                    ids = {c["id"] for c in staged[key]["costs"]}
                    self.assertIn(10000310, ids, key)
                    self.assertFalse(ids & {10000144, 10000145}, key)
        if W.SHOP_LOGICAL in PAYLOADS["tables"]:
            staged = codec.unpack(PAYLOADS["tables"][W.SHOP_LOGICAL][0])
            for key in SHOP_KEYS:
                if key in staged:
                    cells = W.core.read_csv_lines(zlib.decompress(staged[key]).decode("utf-8"))[0]
                    self.assertEqual("10000310", cells[17], key)
                    self.assertFalse({"10000144", "10000145"} & set(cells[17:25:2]), key)


class ReadyLive(W.Live):
    """live 叠加「边 E1/E2 已上线」：多出王币/禁忌星铁两行与禁忌星铁 c3 图（只在内存里）。"""

    def flat(self, logical):
        out = super().flat(logical)
        if logical == W.ITEM_LOGICAL:
            out = dict(out)
            out.setdefault("10000310", ["mod_five_boss_king_coin", "10000310"] + [""] * 21)
            out.setdefault("10000311", ["mod_forbidden_star_steel", "10000311"] + [""] * 21)
        return out

    def raw(self, logical, root="upload"):
        if logical == W.STAR_STEEL_THUMB + ".png":
            return b"synthetic"
        return super().raw(logical, root)


class ShopReadinessTests(unittest.TestCase):
    def test_prerequisites(self):
        waiting = W.shop_prerequisites({}, lambda _: False, drop_live=True)
        self.assertEqual(7, len(waiting))          # 王币、五王心核、深渊觉醒核、禁忌星铁、两张券各 1 条 + 商品图 1 条
        for item_id in ("10000310", "10000311", "10000147", "2370100"):
            self.assertTrue(any(item_id in w for w in waiting), item_id)
        self.assertTrue(any("forbidden_star_steel.png" in w for w in waiting))
        self.assertEqual(8, len(W.shop_prerequisites({}, lambda _: False, drop_live=False)))
        items = {"10000310": [], "10000311": [], "10000147": [], "2370100": [], "999019": [], "999020": []}
        has_thumb = lambda logical: logical == W.STAR_STEEL_THUMB + ".png"  # noqa: E731
        self.assertEqual([], W.shop_prerequisites(items, has_thumb, drop_live=True))
        # 设计 §7 第 7 步：道具行与图都上线了，五重掉落没发王币也不上架（否则券不收结晶、王币无来源）
        waiting = W.shop_prerequisites(items, has_thumb, drop_live=False)
        self.assertEqual(1, len(waiting))
        self.assertIn("五重掉落", waiting[0])

    def test_drop_not_live_defers_even_when_items_are_live(self):
        _prepare_live()
        out = W.build(ReadyLive(), drop_live=False)
        self.assertEqual([], out["problems"])
        self.assertEqual({}, out["rows"][W.SHOP_LOGICAL])
        self.assertEqual({}, out["server"][W.SERVER_SHOP].upsert)
        self.assertEqual({}, out["server"][W.SERVER_SHOP_MAP].upsert)
        self.assertTrue(any("五重掉落" in w for w in out["warnings"]))
        self.assertEqual(out["report"]["shop_deferred"], [w[len("五重商店 032–034 暂缓："):] for w in out["warnings"]])

    def test_drop_detection_default_matches_function(self):
        _prepare_live()
        out = W.build(ReadyLive())
        self.assertEqual(not W.five_boss_drop_live(), any("五重掉落" in w for w in out["report"]["shop_deferred"]))

    def test_shop_order_and_description_gates(self):
        _prepare_live()
        template = LIVE.flat(W.SHOP_LOGICAL)[W.SHOP_TEMPLATE_KEY]
        _, _, problems = W.shop_targets(template)
        self.assertEqual([], problems)
        self.assertTrue(W.shop_targets(template[:49])[2])
        from dataclasses import replace
        from unittest import mock
        bad = (replace(W.STAR_STEEL_PRODUCT, shop_description="可代替本体突破诅咒武器与PARADOX。"),      # 英文名只许在武器名里
               replace(W.STAR_STEEL_PRODUCT, costs=W.STAR_STEEL_PRODUCT.costs + ((10000145, 1), (10000144, 1))),
               replace(W.STAR_STEEL_PRODUCT, limit=0))
        for product in bad:
            with self.subTest(product=product), mock.patch.object(W, "STAR_STEEL_PRODUCT", product):
                self.assertTrue(W.shop_targets(template)[2])

    def test_ready_live_stages_new_prices_only_on_owned_keys(self):
        _prepare_live()
        live = ReadyLive()
        out = W.build(live, drop_live=True)
        self.assertEqual([], out["problems"])
        self.assertEqual([], out["report"]["shop_deferred"])
        self.assertEqual(set(SHOP_KEYS), set(out["rows"][W.SHOP_LOGICAL]))
        self.assertEqual(set(SHOP_KEYS), set(out["server"][W.SERVER_SHOP].upsert))
        self.assertEqual({k: 99 for k in SHOP_KEYS}, out["server"][W.SERVER_SHOP_MAP].upsert)
        payloads = W.stage_payloads(live, out, art_dir=Path(EMPTY_ART.name))
        self.assertEqual([], payloads["problems"])
        # live 已上线过某一版价格时只暂存差异（幂等）：改动键 ⊆ 本池三键，改后三键逐格等于目标行
        old = codec.unpack(LIVE.raw(W.SHOP_LOGICAL))
        if W.SHOP_LOGICAL in payloads["tables"]:
            staged, changed, deleted = payloads["tables"][W.SHOP_LOGICAL]
            self.assertEqual([], deleted)
            self.assertLessEqual(set(changed), set(SHOP_KEYS))
            rows = codec.unpack(staged)
            self.assertEqual(list(old), [k for k in rows if k in old])
            for key in old:
                if key not in changed:
                    self.assertEqual(old[key], rows[key])
        else:
            rows = old
        for key in SHOP_KEYS:
            cells = W.core.read_csv_lines(zlib.decompress(rows[key]).decode("utf-8"))[0]
            self.assertEqual(out["shop_target"]["rows"][key], cells, key)
        if W.SERVER_SHOP in payloads["server"]:
            text, added, deleted, updated = payloads["server"][W.SERVER_SHOP]
            self.assertLessEqual(set(added) | set(updated), set(SHOP_KEYS))
            self.assertEqual([], [d for d in deleted if d not in W.DELETED_SHOP_KEYS])
            server = json.loads(text.decode("utf-8"))["99"]
        else:
            server = LIVE.server_json(W.SERVER_SHOP)["99"]
        self.assertEqual({k: out["shop_target"]["server"][k] for k in SHOP_KEYS}, {k: server[k] for k in SHOP_KEYS})
        self.assertEqual([{"id": 10000310, "amount": 500}, {"id": 10000147, "amount": 5}, {"id": 2370100, "amount": 10}],
                         server["990099034"]["costs"])
        self.assertEqual(60, server["990099034"]["stock"])
        self.assertEqual({"990099001", "990099002"} | set(SHOP_KEYS), set(server))
        if W.SERVER_SHOP_MAP in payloads["server"]:
            shop_map = json.loads(payloads["server"][W.SERVER_SHOP_MAP][0])
        else:
            shop_map = LIVE.server_json(W.SERVER_SHOP_MAP)
        self.assertEqual({k: 99 for k in SHOP_KEYS}, {k: shop_map[k] for k in SHOP_KEYS})


class StagedLiveTests(_LiveCase):
    """对真实 live 字节做的暂存（内存）：只动本池键，其余逐字节。"""

    def test_tables_touch_only_owned_keys(self):
        for logical, (staged, changed, deleted) in PAYLOADS["tables"].items():
            self.assertLessEqual(set(changed) | set(deleted), OWNED_KEYS[logical], logical)
            old, new = codec.unpack(LIVE.raw(logical)), codec.unpack(staged)
            for key, blob in old.items():
                if key not in changed and key not in deleted:
                    self.assertEqual(blob, new[key], (logical, key))
            self.assertFalse(set(deleted) & set(new))
            self.assertEqual(set(old) - set(deleted) | set(changed), set(new))
        if W.SHOP_LOGICAL in PAYLOADS["tables"]:
            _, _, deleted = PAYLOADS["tables"][W.SHOP_LOGICAL]
            live_keys = set(codec.unpack(LIVE.raw(W.SHOP_LOGICAL)))
            self.assertEqual(sorted(set(W.DELETED_SHOP_KEYS) & live_keys), sorted(deleted))

    def test_new_flat_rows_are_compressed_like_live_rows(self):
        for logical, (staged, changed, _) in PAYLOADS["tables"].items():
            if logical == W.FEATURE_LOGICAL:
                continue
            rows = codec.unpack(staged)
            for key in changed:
                if logical == W.RICH_TEXT_MASTER_LOGICAL:
                    self.assertEqual(b"", rows[key])
                else:
                    self.assertEqual(b"\x78\x9c", rows[key][:2], (logical, key))
                    self.assertEqual(W.core.write_csv_lines([OUT["rows"][logical][key]]),
                                     zlib.decompress(rows[key]).decode("utf-8"))

    def test_server_splices_leave_every_other_key_identical(self):
        for name, (payload, added, deleted, updated) in PAYLOADS["server"].items():
            old_text = LIVE.server_text(name)
            new_text = payload.decode("utf-8")
            old, new = json.loads(old_text), json.loads(new_text)
            edit = OUT["server"][name]
            if isinstance(old, list):
                self.assertEqual(old + [int(a) for a in added], new)
                continue
            intended = {edit.path[0]} if edit.path else set(edit.upsert) | set(edit.delete)
            for key in set(old) | set(new):
                if key not in intended:
                    self.assertEqual(old.get(key), new.get(key), (name, key))
            if edit.path:
                inner_old, inner_new = old[edit.path[0]], new[edit.path[0]]
                for key in set(inner_old) | set(inner_new):
                    if key not in set(edit.upsert) | set(edit.delete):
                        self.assertEqual(inner_old.get(key), inner_new.get(key), (name, key))
                self.assertFalse(set(edit.delete) & set(inner_new))
            # 行尾风格原样
            self.assertEqual("\r\n" in old_text, "\r\n" in new_text, name)
            self.assertEqual(old_text.endswith("\n"), new_text.endswith("\n"), name)

    def test_server_targets_match_contract(self):
        server = OUT["server"]
        self.assertEqual({W.GACHA_KEY}, set(server[W.SERVER_GACHA].upsert))
        self.assertEqual("compact", server[W.SERVER_GACHA].style)
        self.assertEqual({"999019": {"category": 4, "sale_price": 100, "sellable": False},
                          "999020": {"category": 4, "sale_price": 100, "sellable": False}},
                         server[W.SERVER_ITEM_SALE].upsert)
        self.assertEqual({"999019": "武器扭蛋券", "999020": "武器扭蛋十连券"}, server[W.SERVER_ITEM_LOOKUP].upsert)
        self.assertEqual((999019, 999020), server[W.SERVER_ITEM_IDS].append)
        self.assertEqual({W.GACHA_KEY: [OUT["rows"][W.GACHA_LOGICAL][W.GACHA_KEY]]}, server[W.SERVER_CDN_GACHA].upsert)
        self.assertEqual({W.GACHA_KEY: {"1": [OUT["feature"][W.GACHA_KEY]["1"]]}}, server[W.SERVER_CDN_FEATURE].upsert)


class SpliceTests(unittest.TestCase):
    CRLF = ('{\r\n  "1": {\r\n    "a": 1\r\n  },\r\n  "99": {\r\n    "k1": {\r\n      "x": [\r\n        1\r\n      ]\r\n'
            '    },\r\n    "k2": {\r\n      "x": [\r\n        2\r\n      ]\r\n    },\r\n    "k3": {\r\n      "x": [\r\n'
            '        3\r\n      ]\r\n    }\r\n  }\r\n}\r\n')

    def test_nested_crlf_delete_and_append(self):
        edit = W.ServerEdit(path=("99",), upsert={"k9": {"x": [9]}}, delete=("k2", "k3"), style="indent",
                            siblings=("k1",))
        text, added, deleted, updated = W.splice_json(self.CRLF, edit)
        self.assertEqual((["k9"], ["k2", "k3"], []), (added, deleted, updated))
        self.assertEqual({"1": {"a": 1}, "99": {"k1": {"x": [1]}, "k9": {"x": [9]}}}, json.loads(text))
        self.assertTrue(text.startswith(self.CRLF[:self.CRLF.index('"k2"')].rstrip(" ")))
        self.assertIn('"k9": {\r\n      "x": [\r\n        9\r\n      ]\r\n    }\r\n  }\r\n}\r\n', text)
        self.assertNotIn("\n", text.replace("\r\n", ""))
        # 再跑一遍 = 无改动
        self.assertEqual((text, [], [], []), W.splice_json(text, edit))

    def test_compact_value_on_default_top_level(self):
        text = '{"1": {"a": 1, "b": [1, 2]}, "990002": {"a":2,"b":[3]}}'
        edit = W.ServerEdit(upsert={"990003": {"a": 3, "b": [0.0]}}, style="compact", siblings=("990002",))
        new, added, _, _ = W.splice_json(text, edit)
        self.assertEqual(text[:-1] + ', "990003": {"a":3,"b":[0.0]}}', new)
        self.assertEqual(["990003"], added)

    def test_list_append_skips_present(self):
        new, added, _, _ = W.splice_json("[1, 2, 999019]", W.ServerEdit(append=(999019, 999020)))
        self.assertEqual(("[1, 2, 999019, 999020]", ["999020"]), (new, added))

    def test_update_existing_key_in_place(self):
        text = '{\n  "a": 1,\n  "b": 2,\n  "c": 3\n}'
        new, added, deleted, updated = W.splice_json(text, W.ServerEdit(upsert={"b": 5}, style="indent", siblings=("a",)))
        self.assertEqual(('{\n  "a": 1,\n  "b": 5,\n  "c": 3\n}', [], [], ["b"]), (new, added, deleted, updated))

    def test_style_mismatch_is_refused(self):
        with self.assertRaises(W.SpliceError):
            W.splice_json('{"a": {"x": 1}, "b": {"x": 2}}',
                          W.ServerEdit(upsert={"c": {"x": 3}}, style="compact", siblings=("a",)))

    def test_non_uniform_separators_are_refused(self):
        with self.assertRaises(W.SpliceError):
            W.splice_json('{"a": 1, "b": 2,"c": 3}', W.ServerEdit(upsert={"d": 4}, siblings=("a",)))

    def test_missing_sibling_is_refused(self):
        with self.assertRaises(W.SpliceError):
            W.splice_json('{"a": 1, "b": 2}', W.ServerEdit(upsert={"d": 4}, siblings=("zz",)))


class RepackTests(unittest.TestCase):
    def table(self) -> bytes:
        rows = {"1": zlib.compress(b"a,b", 9), "2": b"", "3": zlib.compress(b"c,d", 9), "4": zlib.compress(b"e", 9)}
        return codec.pack(rows)

    def test_upsert_delete_keep_other_bytes(self):
        raw = self.table()
        staged, changed, deleted = W.repack(raw, {"3": "c,d", "9": "new,row", "8": None}, ("2", "4", "missing"))
        self.assertEqual((["9", "8"], ["2", "4"]), (changed, deleted))
        old, new = codec.unpack(raw), codec.unpack(staged)
        self.assertEqual(["1", "3", "9", "8"], list(new))
        self.assertEqual((old["1"], old["3"]), (new["1"], new["3"]))      # 同内容不重压，字节原样
        self.assertEqual(b"new,row", zlib.decompress(new["9"]))
        self.assertEqual(b"", new["8"])
        self.assertEqual((raw, [], []), W.repack(raw, {"1": "a,b", "2": None}, ("absent",)))   # 无改动原样返回

    def test_nested_feature_rows(self):
        inner = codec.pack({"1": zlib.compress(b"1,x,,")})
        raw = codec.pack({"5": inner, "6": inner})
        staged, changed, _ = W.repack(raw, {"7": {"1": "1,y,,"}, "6": {"1": "1,x,,"}}, nested=True)
        self.assertEqual(["7"], changed)
        new = codec.unpack(staged)
        self.assertEqual((inner, inner), (new["5"], new["6"]))
        self.assertEqual({"1": "1,y,,"}, W._feature_cells(new["7"]))


class ArtAndStageTests(_LiveCase):
    def write_png(self, path: Path, size, alpha=255):
        from PIL import Image
        Image.new("RGBA", size, (40, 10, 30, alpha)).save(path)

    def test_art_roots_and_publish_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            self.write_png(art / "list_banner.png", (510, 180), alpha=0)
            self.write_png(art / "cover.png", (1440, 1789))
            payloads = W.stage_payloads(LIVE, OUT, art_dir=art, server=False)
        files = payloads["files"]
        banner = files.get("dynamic/gacha_list_banner/cnmod_weapon_gacha.png")
        cover = files.get("medium:dynamic/gacha_banner/cnmod_weapon_gacha.png")
        self.assertIsNotNone(banner)
        self.assertIsNotNone(cover)
        self.assertEqual(("upload", "medium"), (banner["root"], cover["root"]))
        self.assertEqual("dynamic/gacha_banner/cnmod_weapon_gacha.png", cover["logical"])
        self.assertEqual(assets.PNG_FAKE, cover["payload"][:8])
        from PIL import Image
        with Image.open(io.BytesIO(assets.png_decode(banner["payload"]))) as image:
            self.assertEqual(((510, 180), "RGBA"), (image.size, image.mode))
        self.assertEqual(["dynamic/gacha_list_banner/cnmod_weapon_gacha.png",
                          "medium:dynamic/gacha_banner/cnmod_weapon_gacha.png"], payloads["publish_tables"][-2:])
        self.assertEqual([], payloads["missing_art"])

    def test_art_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            self.write_png(art / "list_banner.png", (500, 180))
            self.write_png(art / "cover.png", (1440, 1789), alpha=200)
            problems = W.stage_payloads(LIVE, OUT, art_dir=art, server=False)["problems"]
        self.assertTrue(any("list_banner.png" in p and "尺寸" in p for p in problems))
        self.assertTrue(any("cover.png" in p and "不透明" in p for p in problems))

    def test_missing_art_is_reported_not_fatal(self):
        self.assertEqual(2, len(PAYLOADS["missing_art"]))
        self.assertFalse(any(k.endswith(".png") for k in PAYLOADS["files"]))

    def test_stage_writes_the_apply_fix_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "w"
            result = W.stage(work, LIVE, art_dir=Path(EMPTY_ART.name), out=OUT)
            self.assertFalse(result["refused"])
            plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
            self.assertEqual({"tables", "files", "server", "deleted"}, set(plan))
            for logical, info in plan["tables"].items():
                staged = (work / "stage" / "common" / logical).read_bytes()
                self.assertEqual(W.sha256(staged), info["staged_sha256"])
                self.assertEqual(W.sha256(LIVE.raw(logical)), info["live_sha256"])
                self.assertEqual(sorted(info["changed"]), info["changed"])
            for logical, keys in plan["deleted"].items():
                self.assertLessEqual(set(keys), set(plan["tables"][logical]["changed"]))
            for key, info in plan["files"].items():
                self.assertFalse(key.startswith(W.MEDIUM_PREFIX))
                self.assertTrue((work / "stage" / "common" / key).is_file())
                self.assertIn("live_sha256", info)
            for name, info in plan["server"].items():
                staged = (work / "stage" / "server" / name).read_bytes()
                self.assertEqual(W.sha256(staged), info["staged_sha256"])
                self.assertEqual(W.sha256(LIVE.server_bytes(name)), info["live_sha256"])

    def test_stage_refuses_live_directories_and_problems(self):
        with self.assertRaises(SystemExit):
            W.stage(LIVE.assets_dir / "weapon-gacha-stage", LIVE, out=OUT)
        self.assertFalse((LIVE.assets_dir / "weapon-gacha-stage").exists())
        bad = dict(OUT, problems=["synthetic"])
        with tempfile.TemporaryDirectory() as tmp:
            result = W.stage(Path(tmp) / "w", LIVE, art_dir=Path(EMPTY_ART.name), out=bad)
            self.assertTrue(result["refused"])
            self.assertFalse((Path(tmp) / "w").exists())


if __name__ == "__main__":
    unittest.main()
