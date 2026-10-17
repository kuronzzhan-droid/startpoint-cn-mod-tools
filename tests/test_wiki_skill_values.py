"""Regressions for client-level skill semantics that are easy to mislabel."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_skill_format import Formula
from wf_wiki_skill_values import skill_numeric_details


def slv(lo, hi=None):
    return [{"min": lo, "max": lo if hi is None else hi}]


def cmd(name, *p):
    return ["Command", [name, *p]]


class SkillValueTests(unittest.TestCase):
    def test_percent_frame_and_permanent_units(self):
        fmt = Formula()
        self.assertEqual(fmt.value(slv(.4), "%"), "40%")
        self.assertEqual(fmt.value(slv(480), "秒"), "8秒")
        self.assertEqual(fmt.value(slv(99999999), "秒", permanent=True), "持续至战斗结束")
        self.assertNotIn("战斗", fmt.value(99999999, "秒"))

    def test_formula_adds_all_terms_and_keeps_variable_multiplier(self):
        text = Formula().value([{"min": 2, "max": 3, "mul": 360}, {"min": 4, "max": 5}], "倍")
        self.assertEqual(text, "(2→3) × 成长变量1 + 4→5倍")
        self.assertNotIn("360", text)

    def test_vlv_is_interpolation_formula_not_clamped_range(self):
        value = [{"min": 3, "max": 4, "alv_min": 1, "alv_max": 2,
                  "vlv": [{"vid": 90, "min": 0, "max": 1.5}]}]
        self.assertEqual(Formula().value(value), "3→4 + 能力1成长(1→2) + (0 + 1.5 × 成长变量1)")

    def test_unique_state_id_is_not_duration(self):
        tree = cmd("CreateCondition", 1, [["ACUnique", 151159, slv(1)]], slv(1))
        row = skill_numeric_details(tree, {"151159": [["", "龙之祝福"]]})["rows"][0]
        self.assertEqual(row["label"], "龙之祝福")
        self.assertEqual(row["values"][0], {"label": "增加层数", "value": "1"})
        self.assertNotIn("151159", str(row))

    def test_resistance_element_offset_and_regen_absolute_value(self):
        tree = cmd("CreateCondition", 1, [["ACToleranceOfElement", slv(900), 6, slv(-.1, -.125), slv(99)],
                                        ["ACRegeneration", slv(900), slv(400)]], slv(1))
        rows = skill_numeric_details(tree)["rows"]
        values = {f["label"]: f["value"] for f in rows[0]["values"]}
        self.assertEqual(values["属性"], "暗")
        self.assertEqual(values["效果量"], "-10→-12.5%")
        self.assertEqual(values["叠加上限"], "99")
        self.assertIn({"label": "每次基础回复", "value": "400"}, rows[1]["values"])

    def test_damage_uses_p6_and_only_hit_callback_has_hit_area(self):
        attack = cmd("CreateNormalAttack", 9, 1, [], [], 20, slv(3, 3.5))
        p = [0] * 26
        p[8], p[12], p[13], p[14] = ["Circle", 70], ["SpecifyHitAreaLifetimeDirectly", 150], ["SpecifyMinHitIntervalDirectly", 30], ["Some", slv(5)]
        p[19], p[22] = attack, attack
        rows = skill_numeric_details(cmd("CreateHitArea", *p))["rows"]
        self.assertEqual(rows[0]["values"][0]["value"], "3→3.5倍")
        self.assertEqual(len(rows[0]["values"]), 2)
        values = {f["label"]: f["value"] for f in rows[1]["values"]}
        self.assertEqual(values["最短命中间隔"], "0.5秒")
        self.assertEqual(values["命中次数上限"], "5")

    def test_heal_current_and_maximum_are_distinct(self):
        for mode, label in ((1, "目标当前生命"), (2, "目标最大生命")):
            row = skill_numeric_details(cmd("CreateRatioHeal", 1, mode, slv(.1)))["rows"][0]
            self.assertEqual(row["values"][0]["value"], label)
            self.assertEqual(row["values"][1]["value"], "10%")

    def test_skill_gauge_fraction_is_percent(self):
        row = skill_numeric_details(cmd("AddSkillPoint", 1, slv(.25)))["rows"][0]
        self.assertEqual(row["values"][0]["value"], "25%")

    def test_barrier_is_maximum_hp_fraction(self):
        row = skill_numeric_details(cmd("CreateBarrier", 1, slv(.12)))["rows"][0]
        self.assertEqual(row["values"], [{"label": "计算基准", "value": "目标最大生命"},
                                         {"label": "比例", "value": "12%"}])

    def test_fixed_speed_second_strength_is_skill_charging(self):
        tree = cmd("CreateCondition", 1, [["ACFixedSpeed", slv(600), slv(.4), slv(.5), slv(1)]], slv(1))
        values = {f["label"]: f["value"] for f in skill_numeric_details(tree)["rows"][0]["values"]}
        self.assertEqual(values["球速修正"], "40%")
        self.assertEqual(values["技能充能速度修正"], "50%")

    def test_combo_boost_uses_flip_limit_and_unique_uses_master_duration_cap(self):
        tree = cmd("CreateCondition", 1, [["ACComboBoost", slv(3), slv(10)],
                                         ["ACUnique", 22, slv(1)]], slv(1))
        rows = skill_numeric_details(tree, {"22": [["internal", "龙王显现", "path", "1200", "5"]]})["rows"]
        self.assertEqual(rows[0]["values"][0], {"label": "弹射次数限制", "value": "3"})
        unique = {f["label"]: f["value"] for f in rows[1]["values"]}
        self.assertEqual(unique["持续时间"], "20秒")
        self.assertEqual(unique["叠加上限"], "5")

    def test_indexed_branches_are_not_mislabeled_boolean(self):
        attacks = [cmd("CreateNormalAttack", 1, 1, [], [], 0, slv(n)) for n in (1, 2, 3)]
        rows = skill_numeric_details(cmd("ConditionalsNumExecutions3", False, *attacks))["rows"]
        self.assertEqual([r["context"] for r in rows], [["第 1 次发动"], ["第 2 次发动"], ["第 3 次及以后发动"]])
        rows = skill_numeric_details(cmd("ConditionalsNumCoffins", *attacks))["rows"]
        self.assertEqual([r["context"] for r in rows], [["棺材数量为 0"], ["棺材数量为 1"], ["棺材数量为 2"]])

    def test_unique_branch_condition_is_human_readable(self):
        attack = cmd("CreateNormalAttack", 1, 1, [], [], 0, slv(1))
        tree = cmd("ConditionalsConditionAccumulationNumber", ["DCUnique", 22], 3, attack, attack)
        rows = skill_numeric_details(tree, {"22": [["internal", "龙之祝福"]]})["rows"]
        self.assertEqual(rows[0]["context"], ["龙之祝福层数 ≥ 3：成立"])
        self.assertEqual(rows[1]["context"], ["龙之祝福层数 ≥ 3：不成立"])

    def test_slv_hit_interval_and_remaining_action_lifetime_are_exported(self):
        attack = cmd("CreateNormalAttack", 9, 1, [], [], 20, slv(3))
        p = [0] * 26
        p[8], p[12], p[13] = ["Circle", 70], ["RemainingFramesOfCurrentStateGroup"], ["SpecifyMinHitIntervalSLv", slv(60, 30)]
        p[22] = attack
        values = {f["label"]: f["value"] for f in skill_numeric_details(cmd("CreateHitArea", *p))["rows"][0]["values"]}
        self.assertEqual(values["判定持续"], "至当前动作组结束")
        self.assertEqual(values["最短命中间隔"], "1→0.5秒")


if __name__ == "__main__":
    unittest.main()
