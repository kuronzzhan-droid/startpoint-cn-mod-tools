# -*- coding: utf-8 -*-
"""wf_gacha_odds_sync：角色池 7 列 / 装备池 6 列两条分支（W3，武器扭蛋 990003 的前置）。

全部在临时 store 里跑：CDN gacha 表 + 嵌套概率表 + 临时 gacha.json，不读 live。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_gacha_odds_sync as odds  # noqa: E402
import wf_mod_tool as core  # noqa: E402

GACHA_LOGICAL = "master/gacha/gacha.orderedmap"


def gacha_row(prize_kind: str, prefix: str) -> list[str]:
    row = [""] * 47
    row[0], row[11], row[13] = prefix, f"{prefix}_rarity", prize_kind
    if prize_kind == "1":
        row[22], row[23], row[24] = f"{prefix}_3", f"{prefix}_4", f"{prefix}_5"
    else:
        row[14], row[15], row[16] = f"{prefix}_character_3", f"{prefix}_character_4", f"{prefix}_character_5"
    return row


def entry(i: int, rank: int, weight: int, **flags) -> dict:
    return {"id": i, "rank": rank, "odds": weight, "isRateUp": flags.get("up", False),
            "isLimited": flags.get("lim", False), "isExchangeable": flags.get("ex", False),
            "rarity": 0.0, **({"trialReadingForced": True} if flags.get("trial") else {})}


class Fixture:
    def __init__(self, root: Path):
        self.store = root / "store"
        self.gacha_json = root / "gacha.json"
        rows = {"990003": gacha_row("1", "wg"), "990004": gacha_row("0", "cg")}
        ordered = core.OrderedMap(GACHA_LOGICAL, list(rows),
                                  [core.write_csv_lines([r]).encode("utf-8") for r in rows.values()],
                                  Path("<memory>"))
        self.write(GACHA_LOGICAL, core.build_orderedmap(ordered))
        for sid in ("wg_rarity", "wg_3", "wg_4", "wg_5", "cg_rarity", "cg_character_3",
                    "cg_character_4", "cg_character_5"):
            self.write(odds._odds_path(sid), odds.build_nested(sid, ["0"], ["0,0"]))
        weapon = {"rankRates": {"normal": [150, 250, 600], "multiGuarantee": [150, 850]},
                  "pool": {"1": [entry(5900101, 5, 152, up=True, lim=True),
                                 entry(5910101, 5, 456, lim=True, ex=True),
                                 entry(5920001, 5, 0, lim=True)],
                           "2": [entry(4010003, 4, 1)], "3": [entry(3010006, 3, 1)]}}
        character = {"rankRates": {"normal": [50, 250, 700], "multiGuarantee": [50, 950]},
                     "pool": {"1": [entry(111001, 5, 3, up=True, trial=True)],
                              "2": [entry(211001, 4, 2)], "3": [entry(311001, 3, 1, ex=True)]}}
        self.gacha_json.write_text(json.dumps({"990003": weapon, "990004": character}), encoding="utf-8")

    def write(self, logical: str, raw: bytes) -> None:
        path = core.table_path(self.store, logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def lines(self, sid: str) -> list[str]:
        logical = odds._odds_path(sid)
        return odds.read_nested(core.table_path(self.store, logical), logical)[2]


class LayoutTests(unittest.TestCase):
    def test_prize_kind_selects_columns_and_width(self):
        self.assertIs(odds.EQUIPMENT_LAYOUT, odds.odds_layout(gacha_row("1", "x")))
        self.assertIs(odds.CHARACTER_LAYOUT, odds.odds_layout(gacha_row("0", "x")))
        self.assertEqual({3: 22, 4: 23, 5: 24}, odds.EQUIPMENT_LAYOUT.columns)
        self.assertEqual({3: 14, 4: 15, 5: 16}, odds.CHARACTER_LAYOUT.columns)
        self.assertEqual((6, 7), (odds.EQUIPMENT_LAYOUT.width, odds.CHARACTER_LAYOUT.width))

    def test_unknown_prize_kind_is_refused(self):
        with self.assertRaises(odds.OddsSyncError):
            odds.odds_layout(gacha_row("2", "x"))

    def test_odds_line_follows_the_layout(self):
        e = entry(5910101, 5, 456, lim=True, ex=True, trial=True)
        self.assertEqual("5910101,5,456,false,true,true",
                         odds.odds_line(e, 5, odds.EQUIPMENT_BOOL_FIELDS))
        self.assertEqual("5910101,5,456,false,true,true,true", odds.odds_line(e, 5))
        self.assertEqual(["5,150", "4,250", "3,600"], odds.rarity_lines([150, 250, 600]))


class SyncPoolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fx = Fixture(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def sync(self, pool: str, apply: bool) -> dict:
        return odds.sync_pool(pool, self.fx.store, apply=apply, stamp="t",
                              gacha_json=self.fx.gacha_json)

    def test_equipment_pool_dry_run_reads_c22_to_c24_and_writes_nothing(self):
        before = {sid: self.fx.lines(sid) for sid in ("wg_3", "wg_4", "wg_5")}
        report = self.sync("990003", apply=False)
        self.assertEqual("equipment", report["layout"])
        kinds = [t["kind"] for t in report["tables"]]
        self.assertEqual(["rarity", "equipment_5", "equipment_4", "equipment_3"], kinds)
        self.assertTrue(all(t["changed"] for t in report["tables"]))
        t5 = report["tables"][1]
        self.assertEqual(608, t5["weight_total"])
        self.assertEqual({"11.250%": 1, "3.750%": 1, "0.000%": 1}, t5["display_buckets"])
        self.assertEqual(before, {sid: self.fx.lines(sid) for sid in before})

    def test_equipment_pool_apply_writes_six_column_rows_in_server_order(self):
        self.sync("990003", apply=True)
        self.assertEqual(["5,150", "4,250", "3,600"], self.fx.lines("wg_rarity"))
        self.assertEqual(["5900101,5,152,true,true,false", "5910101,5,456,false,true,true",
                          "5920001,5,0,false,true,false"], self.fx.lines("wg_5"))
        self.assertEqual(["4010003,4,1,false,false,false"], self.fx.lines("wg_4"))
        self.assertEqual(["3010006,3,1,false,false,false"], self.fx.lines("wg_3"))
        # 角色池的表一张没动
        self.assertEqual(["0,0"], self.fx.lines("cg_character_5"))
        # 再跑一遍：已同步，全部 changed=False（幂等）
        self.assertFalse(any(t["changed"] for t in self.sync("990003", apply=False)["tables"]))

    def test_character_pool_keeps_seven_columns(self):
        report = self.sync("990004", apply=True)
        self.assertEqual("character", report["layout"])
        self.assertEqual(["111001,5,3,true,false,false,true"], self.fx.lines("cg_character_5"))
        self.assertEqual(["311001,3,1,false,false,true,false"], self.fx.lines("cg_character_3"))
        self.assertEqual(["5,50", "4,250", "3,700"], self.fx.lines("cg_rarity"))
        self.assertEqual(["0,0"], self.fx.lines("wg_5"))

    def test_empty_pointer_column_is_refused(self):
        row = gacha_row("1", "wg")
        row[24] = ""
        ordered = core.OrderedMap(GACHA_LOGICAL, ["990003"], [core.write_csv_lines([row]).encode()],
                                  Path("<memory>"))
        self.fx.write(GACHA_LOGICAL, core.build_orderedmap(ordered))
        with self.assertRaises(odds.OddsSyncError):
            self.sync("990003", apply=False)


if __name__ == "__main__":
    unittest.main()
