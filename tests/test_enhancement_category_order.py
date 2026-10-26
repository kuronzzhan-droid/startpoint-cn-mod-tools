# -*- coding: utf-8 -*-
"""装备强化商店类目横幅顺序（wf_enhancement_category_order）：诅咒(6) → 深渊(5) → 羁绊(7) → 官方 1–4。

作者 0928：强化商店「诅咒武器·觉醒」「深渊武装·觉醒」排在官方类目前面；c1 display_order 6 → -2、5 → -1，
官方 1–4 不动。0929 起「羁绊武器·觉醒」（键 7，c1 = 0，由羁绊生成器新增）排在深渊之后、官方之前；它发布前 live 里没有这一行，
本模块跳过它（OPTIONAL），发布后照常核对。live 只读；另跑诅咒武器生成器（夹具 reader）确认它自己出的类目行 c1 也是 -2（重新暂存不会冲回 6）。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import wf_abyss_weapon_category as abyss  # noqa: E402
import wf_bond_weapon_enhance as bond  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import wf_enhancement_category_order as CO  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/cursed_weapons_templates.json"


def official_rows() -> dict[str, list[str]]:
    """live 形状的 6 行（官方 1–4 取自 live 实测的 string_id；c1 = 键）。"""
    ids = {"1": "anamnesis_weapon", "2": "epuration_weapon", "3": "steam_robot_weapon", "4": "score_attack_event",
           "5": "abyss_weapon", "6": "cursed_weapon"}
    return {k: [sid, k, "(None)", f"类目{k}", f"dynamic/equipment_enhancement/{sid}_banner",
                f"dynamic/equipment_enhancement/{sid}_header", "how", "how2", "2000-01-01 00:00:00", "(None)"]
            for k, sid in ids.items()}


def with_bond(rows: dict[str, list[str]], order: str = bond.CATEGORY_ORDER) -> dict[str, list[str]]:
    """加上羁绊类目行（发布后的 live 形状：c1 已是 0）。"""
    return {**rows, "7": ["bond_weapon", order, "(None)", "羁绊武器·觉醒", "dynamic/equipment_enhancement/bond_weapon_banner",
                          "dynamic/equipment_enhancement/bond_weapon_header", "how", "how2", "2000-01-01 00:00:00", "(None)"]}


class CategoryOrderTests(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(("6", "-2"), (W.ENH_CATEGORY_KEY, W.ENH_CATEGORY_DISPLAY_ORDER))
        self.assertEqual(("5", "-1"), (abyss.NEW_KEY, abyss.DISPLAY_ORDER))
        self.assertEqual(("7", "0"), (bond.CATEGORY_KEY, bond.CATEGORY_ORDER))
        self.assertEqual(("6", "5", "7", "1", "2", "3", "4"), CO.EXPECTED_SEQUENCE)
        self.assertEqual({"7"}, set(CO.OPTIONAL))

    def test_only_c1_of_the_two_own_rows_changes(self):
        live = official_rows()
        upsert, problems = CO.target_rows(live)
        self.assertEqual([], problems)
        self.assertEqual({"5", "6"}, set(upsert))
        for key, row in upsert.items():
            diff = [i for i, (a, b) in enumerate(zip(live[key], row)) if a != b]
            self.assertEqual([CO.ORDER_COL], diff)
            self.assertEqual(len(live[key]), len(row))
        self.assertEqual(("-2", "-1"), (upsert["6"][1], upsert["5"][1]))

    def test_bond_row_optional_until_published(self):
        """live 还没有键 7（羁绊发布前）：不算错、不改序、顺序按现有行核对；有了之后 c1 = 0 即到位。"""
        upsert, problems = CO.target_rows(official_rows())
        self.assertEqual(([], {"5", "6"}), (problems, set(upsert)))
        live = with_bond(official_rows())
        upsert, problems = CO.target_rows(live)
        self.assertEqual(([], {"5", "6"}), (problems, set(upsert)))
        staged = {**live, **upsert}
        self.assertEqual(CO.EXPECTED_SEQUENCE, tuple(sorted(staged, key=lambda k: int(staged[k][1]))))
        again, problems = CO.target_rows(staged)
        self.assertEqual(({}, []), (again, problems))

    def test_bond_row_guards(self):
        live = with_bond(official_rows(), order="1")                        # 与官方类目 1 撞值：排序无兜底
        self.assertTrue(any("重复" in p for p in CO.target_rows(live)[1]))
        live = with_bond(official_rows(), order="9")                        # 有人另改过 c1
        self.assertTrue(CO.target_rows(live)[1])
        live = with_bond(official_rows())
        live["7"][0] = "something_else"                                     # 键 7 不是羁绊类目
        self.assertTrue(CO.target_rows(live)[1])
        live = with_bond(official_rows(), order="7")                        # 原值 = 键：改到 0，其余列不动
        upsert, problems = CO.target_rows(live)
        self.assertEqual([], problems)
        self.assertEqual("0", upsert["7"][1])
        self.assertEqual([1], [i for i, (a, b) in enumerate(zip(live["7"], upsert["7"])) if a != b])

    def test_idempotent(self):
        live = official_rows()
        upsert, _ = CO.target_rows(live)
        again, problems = CO.target_rows({**live, **upsert})
        self.assertEqual(({}, []), (again, problems))

    def test_refuses_drift_duplicates_and_foreign_rows(self):
        live = official_rows()
        live["6"][1] = "7"                                                   # 有人另改过 c1
        self.assertTrue(CO.target_rows(live)[1])
        live = official_rows()
        live["2"][1] = "-2"                                                  # 官方行撞值：排序无兜底
        self.assertTrue(any("重复" in p for p in CO.target_rows(live)[1]))
        live = official_rows()
        live["5"][0] = "something_else"                                      # 键 5 不是深渊类目
        self.assertTrue(CO.target_rows(live)[1])
        live = official_rows()
        del live["6"]
        self.assertTrue(CO.target_rows(live)[1])
        live = official_rows()
        live["3"][1] = "x"
        self.assertTrue(any("不是整数" in p for p in CO.target_rows(live)[1]))

    def test_sequence_gate_bites(self):
        live = official_rows()
        live["1"][1] = "-9"                                                  # 官方行排到最前 ⇒ 不是目标顺序
        self.assertTrue(any("横幅顺序" in p for p in CO.target_rows(live)[1]))

    def test_live_store(self):
        try:
            import wf_weapon_gacha as G
            live = G.Live().flat(CO.CATEGORY_LOGICAL)
        except (SystemExit, FileNotFoundError):
            self.skipTest("本检出没有 live store")
        upsert, problems = CO.target_rows(live)
        self.assertEqual([], problems)
        self.assertLessEqual(set(upsert), {"5", "6", "7"})
        staged = {**live, **upsert}
        expected = tuple(k for k in CO.EXPECTED_SEQUENCE if k in staged)      # 键 7 发布前 live 没有
        self.assertEqual(expected, tuple(sorted(staged, key=lambda k: int(staged[k][1]))))
        for key in ("1", "2", "3", "4"):
            self.assertEqual(key, staged[key][1])                           # 官方 1–4 不动

    def test_cursed_generator_emits_the_same_order(self):
        """诅咒武器生成器自己出的类目行（重新暂存时用）c1 = -2，其余列照旧。"""
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        reader = W.LiveReader(lambda logical: data["flat"].get(logical, {}),
                              lambda logical: data["nested"].get(logical, {}), lambda name: {})
        row = W.build(reader, client_capabilities=W.PATCHED_CLIENT_CAPABILITIES)["flat"][W.ENH_CATEGORY]["6"][0]
        self.assertEqual(["cursed_weapon", "-2", "诅咒武器·觉醒", W.BANNER, W.HEADER, W.START_TIME],
                         [row[0], row[1], row[3], row[4], row[5], row[8]])


if __name__ == "__main__":
    unittest.main()
