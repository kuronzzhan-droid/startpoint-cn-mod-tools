"""奈芙面板的实际能力条件、七组覆盖和平表编码合同。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import test_bianca_dragon_abilities as fixture
import wf_mod_tool as core
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_powerflip as powerflip
import wf_nephtim_fever_skill as skill
import wf_nephtim_fever_text as text


class NephtimFeverTextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source, _ = fixture.official_sources()
        cls.abilities = abilities.ability_rows(source)
        cls.leader = leader.leader_rows(source)

    def panels(self, policy="dark_resonance"):
        return text.panel_descriptions(piercing_extension=policy)

    def test_active_and_eight_sections_have_only_player_facing_text(self):
        panels = self.panels()
        self.assertEqual({"active", "leader", "a1", "a2", "a3", "a4", "a5", "a6"}, set(panels))
        self.assertEqual(text.active_description(), panels["active"])
        self.assertNotRegex(panels["active"], r"[0-9%％]")
        for value in panels.values():
            self.assertTrue(value.strip())
            # 文案规则1：没有上限就什么都不写——面板里不许再出现「无上限」。
            self.assertNotRegex(value,
                                r"同条件|无上限|无次数上限|I629|I536|I722|DSL|APK|Unique|原生|实现")
        for phrase in ("参战者及协力球贯穿", "队伍内角色及协力球", "Fever 模式中"):
            self.assertIn(phrase, panels["active"])

    def test_real_group_ids_create_seven_overrides_without_changing_combat_or_awake_rows(self):
        before = deepcopy((self.abilities, self.leader))
        rows = text.panel_rows(self.abilities, self.leader, piercing_extension="dark_resonance")
        self.assertEqual(before, (self.abilities, self.leader))
        self.assertEqual({"desc_override_ruin_girl_campus"} |
                         {f"desc_override_ruin_girl_campus_{i}" for i in range(1, 7)}, set(rows))
        panels = self.panels()
        self.assertEqual([[panels["leader"]]], rows["desc_override_" + self.leader[0][0]])
        self.assertEqual(["0", ""], self.leader[0][1:3])
        for number in range(1, 7):
            first = self.abilities[f"169989{number}"][0]
            self.assertEqual([[panels[f"a{number}"]]], rows["desc_override_" + first[0]])
            self.assertEqual(["0", ""], first[3:5])

    def test_missing_or_colliding_string_ids_are_rejected(self):
        rows = deepcopy(self.abilities)
        del rows["1699894"]
        with self.assertRaisesRegex(ValueError, "a4"):
            text.panel_rows(rows, self.leader, piercing_extension="dark_resonance")
        rows["1699894"] = deepcopy(rows["1699893"])
        with self.assertRaisesRegex(ValueError, "a4"):
            text.panel_rows(rows, self.leader, piercing_extension="dark_resonance")

    def test_native_keys_and_csv_roundtrip_preserve_single_cell_and_main_markup(self):
        native = text.native_flat_string_rows()
        originals = {**abilities.flat_string_rows(), **leader.flat_string_rows(), **powerflip.flat_string_rows()}
        self.assertTrue(set(native) <= set(originals))
        # I536/I629 说明各自只有一个真源；两个模块曾各写一份不同文案，这里钉死不许再分叉。
        for key in (abilities.CHANGE_SKILL_STRING_ID, abilities.SPAWN_STRING_ID):
            self.assertEqual(originals[key], native[key], key)
        self.assertTrue(all("ruin_girl_campus" in key for key in native))
        rows = text.panel_rows(self.abilities, self.leader, piercing_extension="dark_resonance")
        rows.update(native)
        for key, group in rows.items():
            self.assertEqual((1, 1), (len(group), len(group[0])), key)
            self.assertNotIn("\\n", group[0][0])
            self.assertEqual(group, core.read_csv_lines(core.write_csv_lines(group)))

    def test_a1_is_opening_charge_and_summon_state_has_correct_gates_and_durations(self):
        rows = self.abilities["1699891"]
        self.assertEqual(("211", "50000"), (rows[0][47], rows[0][51]))
        panel = self.panels()["a1"]
        self.assertEqual(text.MAIN_ICON + "战斗开始时，自身技能槽+50%。", panel.splitlines()[0])
        self.assertNotIn("技能槽上限+50%", panel)
        # 作者 2026-09-27（方案B）：I536 强化条目随开关移入队长，能力1只留开局、召唤三行。
        self.assertEqual(4, len(panel.splitlines()))
        self.assertNotIn("强化『", panel)
        self.assertNotIn("强化后的技能发动时", panel)
        # 2026-09-27 第三轮技能强化文案：同一条 I536 强化只写一行 =「暗属性共鸣时，」+ 条目原文（不写「强化后的技能」）。
        enhancement = self.panels()["leader"].splitlines()[1:2]
        self.assertEqual(list(text.ENHANCEMENT_LINES), enhancement)
        self.assertEqual("暗属性共鸣时，" + abilities.CHANGE_SKILL_DESCRIPTION + "。", enhancement[0])
        self.assertIn("强化『" + abilities.SKILL_NAME + "』", enhancement[0])
        self.assertIn("额外赋予暗属性角色及协力球攻击力提升效果", enhancement[0])
        self.assertIn("Fever 模式中发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾", enhancement[0])
        self.assertNotIn("强化后", self.panels()["leader"])
        for line in enhancement:
            # 文案规则2：「技能强化」条目只写强化了什么，不写数字与时间。
            self.assertNotRegex(line, r"[0-9０-９]")
            self.assertNotIn("秒", line)
        # 作者 2026-09-27：召唤间隔 1.5 秒 → 2 秒。
        self.assertEqual(2, text.SUMMON_PERIOD_SECONDS)
        self.assertNotIn("1.5秒", panel)
        self.assertIn("每经过2秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复生命值", panel.splitlines()[1])
        # 作者 2026-09-17 减半：溢出攻击力 +50% → +25%，时长与「可叠加」不动。
        self.assertEqual(25, skill.overflow_attack_percent())
        self.assertIn("该次召唤改为自身攻击力+25%，持续20秒，可叠加", panel)
        self.assertIn("攻击力+25%", abilities.SPAWN_DESCRIPTION)
        self.assertIn("Fever 结束或自身倒下时", panel)
        self.assertEqual("星夜茶会", skill.STATE_NAME)
        self.assertEqual(1500, skill.metadata()["each_ball_lifetime_frames"])
        self.assertEqual("true", skill.unique_rows()[str(skill.STATE_UID)][0][13])

    def test_all_a3_lines_have_native_main_badge_and_exact_conditional_numeric_effects(self):
        panels = self.panels()
        for number in range(1, 7):
            restricted = any(row[1] == "false" for row in self.abilities[f"169989{number}"])
            self.assertEqual(restricted, "<icon id='main'>" in panels[f"a{number}"])
        lines = panels["a3"].splitlines()
        self.assertTrue(all(line.startswith(text.MAIN_ICON + "暗属性共鸣时，") for line in lines))
        self.assertIn("Fever 模式中，当前每有1连击", lines[0])
        # 作者 2026-09-17 减半：连击 5% → 2.5%、贯穿成长 20% → 10%。
        self.assertIn("直接攻击造成的伤害+2.5%（独立乘区）、攻击力+2.5%。", lines[0])
        self.assertNotIn("无上限", lines[0])
        self.assertIn("Fever 模式中，处于贯穿效果的时间每累计2秒", lines[1])
        # 作者 2026-09-27 第二批：能力3 贯穿成长改成有上限的弱化版（攻击力 +5%、直击 +10%，各最多 10 次）。
        self.assertIn("攻击力+5%、直接攻击伤害+10%（最多10次）。", lines[1])
        self.assertIn("Fever 槽+15%", lines[2])
        combo = self.abilities["1699893"][0]
        self.assertEqual(("2", "410", "2500"), (combo[97], combo[109], combo[113]))
        attack, direct = self.abilities["1699893"][2:4]
        self.assertEqual(("32", "5000", "10"), (attack[47], attack[51], attack[34]))
        self.assertEqual(("33", "10000", "10"), (direct[47], direct[51], direct[34]))

    def test_non_main_bonuses_keep_their_actual_targets_and_a5_has_no_resonance_gate(self):
        panels = self.panels()
        # 作者 2026-09-27：贯穿合并为能力2 +40%，并承载 Fever 中技能槽上限+10%。
        # 第三轮面板同条件合并：贯穿延时与直击同为暗共鸣常驻 ⇒ 并成第1行。
        self.assertEqual(["暗属性共鸣时，全队贯穿效果时间+40%，暗属性角色直接攻击伤害+250%。",
                          "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。"],
                         panels["a2"].splitlines())
        maximum = self.abilities["1699892"][2]
        self.assertEqual(("1", "124", "5", "10000"), (maximum[5], maximum[109], maximum[110], maximum[113]))
        self.assertEqual("暗属性共鸣时，Fever 模式中，暗属性角色及协力球直接攻击造成的伤害+50%（独立乘区）。", panels["a4"])
        members, balls = self.abilities["1699894"]
        self.assertEqual("5", members[110])
        self.assertEqual([abilities.multiball_fever.STRING_ID, abilities.multiball_fever.ACTION_PATH], balls[70:72])
        self.assertNotIn("共鸣", panels["a5"])
        self.assertEqual(["0", "0"], [row[6] for row in self.abilities["1699895"]])
        self.assertEqual(["非 Fever 模式中，每经过10秒，赋予全队贯穿效果，持续3秒。",
                          "Fever 模式中，每经过5秒，赋予全队贯穿效果，持续3秒。"], panels["a5"].splitlines())
        self.assertEqual("暗属性共鸣时，暗属性角色直接攻击伤害+100%。", panels["a6"])
        self.assertNotIn("Fever", panels["a6"])

    def test_leader_uses_only_the_confirmed_constant_dark_resonance_piercing(self):
        permanent = self.panels()["leader"].splitlines()
        # 作者 2026-09-27：贯穿延时与技能槽上限两句移出队长（改由能力2承载）。
        # 同日第二批：末尾追加从能力3 搬来的贯穿成长（写到效果为止）→ 9 行；第三轮 +1% → +7%、Fever 槽 +2% → +15%；
        # 第三轮面板同条件合并：第4行（攻击/直击）与第6行（Fever 时间）并成一行 → 8 行；
        # 第三轮技能强化文案：同一条 I536 强化的第2、3行并成一行 → 7 行。
        self.assertEqual(7, len(permanent))
        self.assertNotIn("贯穿效果时间", "\n".join(permanent))
        self.assertNotIn("技能槽上限", "\n".join(permanent))
        self.assertIn("暗属性共鸣时，全队贯穿效果时间+40%，暗属性角色直接攻击伤害+250%。", self.panels()["a2"].splitlines())
        self.assertEqual("暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。", permanent[-2])
        self.assertNotIn("Fever", permanent[-2])
        self.assertEqual("暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，"
                         "暗属性角色攻击力+7%、直接攻击伤害+7%。", permanent[-1])
        self.assertEqual(text.LEADER_PIERCING_LINE, permanent[-1])
        self.assertIn("Fever 槽上升量+15%", permanent[3])
        self.assertTrue(all(line.startswith("暗属性共鸣时，") for line in permanent))
        self.assertNotIn("每直接攻击50次", "\n".join(permanent))
        self.assertIn("强化『" + abilities.SKILL_NAME + "』", permanent[1])
        self.assertIn("攻击力+200%、直接攻击伤害+400%", permanent[2])
        self.assertNotIn("Fever 模式中", permanent[2])
        self.assertEqual(self.panels(), text.panel_descriptions())
        self.assertEqual(("dark_resonance",), text.PIERCING_POLICIES)
        for policy in ("self_source", "unbalanced_fever_edges"):
            with self.assertRaises(ValueError):
                self.panels(policy)

    def test_capability_and_return_values_are_isolated(self):
        meta = text.metadata()
        self.assertEqual(["panel-description-override-v2"], meta["required_client_capabilities"])
        self.assertEqual("dark_resonance", meta["leader_piercing_extension"])
        self.assertFalse(meta["combat_rows_modified"])
        copy = self.panels()
        copy["a1"] = "changed"
        self.assertNotEqual(copy, self.panels())


if __name__ == "__main__":
    unittest.main()
