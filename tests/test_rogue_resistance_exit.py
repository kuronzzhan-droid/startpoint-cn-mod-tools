"""第26层三系免疫 + 90%叠层 + 40%关卡抗性的跨来源回归。"""
from __future__ import annotations

import copy
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import rogue_build as rb


def three_walls(open_kind):
    return {"name": "三重壁垒", "text": "三系免疫", "damage_resistance": [
        (kind, 1.0, False) for kind in range(4) if kind != open_kind]}


def stack(kind, layers=90):
    return rb.stacked_resistance_entry(
        "层叠龙鳞", rb.DAMAGE_RESISTANCE_AC[kind], 0.01, layers)


def soft(kind, strength=0.4):
    return {"name": "直击偏转", "text": "关卡抗性",
            "cond": [(str(kind), str(strength))]}


def compiled_totals(out):
    # 独立检查实际编译出的三组值，不调用被测的合计/免疫帮助函数。
    totals = [0.0] * 4
    for kind, value in out["conds"]:
        if kind in {"0", "1", "2", "3"}:
            totals[int(kind)] += float(value)
    for kind, value, _cancelable in out["damage_resistance"]:
        totals[kind] += value
    for constructor, strength, layers in out["stacked_resistance"]:
        if constructor in rb.STACKED_DAMAGE_AC_KIND:
            totals[rb.STACKED_DAMAGE_AC_KIND[constructor]] += strength * layers
    return totals


class ResistanceExitCase(unittest.TestCase):
    def test_floor26_failure_and_all_four_damage_type_variants(self):
        for kind in range(4):
            for value in (0.1, 0.4):
                with self.subTest(kind=kind, soft=value):
                    picks = [three_walls(kind), stack(kind), soft(kind, value)]
                    self.assertEqual(rb.immunity_axes(picks)[0], {"0", "1", "2", "3"})
                    self.assertIn("四种伤害类型", rb.curse_conflict(picks))

    def test_all_three_sources_must_be_added_before_threshold(self):
        for kind in range(4):
            picks = [three_walls(kind), stack(kind, 40), soft(kind, 0.4),
                     {"name": "一次性", "text": "20%", "damage_resistance": [(kind, 0.2)]}]
            self.assertIn("四种伤害类型", rb.curse_conflict(picks))

    def test_quest_plus_one_shot_also_cannot_close_the_last_exit(self):
        for kind in range(4):
            picks = [three_walls(kind), soft(kind),
                     {"name": "一次性", "damage_resistance": [(kind, 0.6)]}]
            self.assertIn("四种伤害类型", rb.curse_conflict(picks))

    def test_below_threshold_and_same_source_merging_remain_valid(self):
        for kind in range(4):
            for picks in ([three_walls(kind), stack(kind)],
                          [three_walls(kind), stack(kind, 50), soft(kind), soft(kind, 0.3)]):
                with self.subTest(kind=kind, picks=picks):
                    self.assertIsNone(rb.curse_conflict(picks))
                    out = rb.apply_picks({}, picks)
                    self.assertAlmostEqual(compiled_totals(out)[kind], 0.9)

    def test_direct_effect_compilation_rejects_before_mutating_output(self):
        out = {"existing": ["preserve"]}
        before = copy.deepcopy(out)
        with self.assertRaisesRegex(ValueError, "四种伤害类型"):
            rb.apply_picks(out, [three_walls(1), stack(1), soft(1)])
        self.assertEqual(out, before)

    def test_forced_bad_combination_is_redrawn_with_full_quota(self):
        pool = [three_walls(1), stack(1), soft(1),
                {"name": "血肉高墙", "text": "敌血增加", "hp": 1.6},
                {"name": "魔力枯竭", "text": "FEVER需求增加", "fever": 800}]
        with mock.patch.object(rb, "_curse_pool", return_value=pool), \
                mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(26, 30, random.Random(26), "hell",
                                  caps={"boss": True}, forced={
                                      "curses": [c["name"] for c in pool[:4]]})
        self.assertNotIn("直击偏转", [c["name"] for c in out["picks"]])
        self.assertGreaterEqual(len(out["picks"]), 4)
        self.assertLess(min(compiled_totals(out)), 1.0)
        self.assertTrue(any("四种伤害类型" in str(call)
                            for call in logger.call_args_list))

    def test_random_output_keeps_an_exit_in_compiled_values(self):
        with mock.patch.object(rb, "log"):
            for seed in range(500):
                # 覆盖一般硬载体及仍允许关卡软抗性的无属性载体。
                for caps in ({"boss": True}, {"boss": True, "element": False}):
                    out = rb.abyss_curses(26, 30, random.Random(seed), "hell", caps=caps)
                    self.assertLess(min(compiled_totals(out)), 1.0 - 1e-12, (seed, out))


if __name__ == "__main__":
    unittest.main()
