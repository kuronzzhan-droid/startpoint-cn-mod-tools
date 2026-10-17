"""简版说明的真实条件、覆盖键以及多行平表编码契约。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_bianca_dragon_abilities as bianca
import wf_bianca_dragon_bridge as bianca_bridge
import wf_celtie_fever_abilities as celtie
import wf_celtie_fever_leader as celtie_leader
import wf_campus_panel_text as text
import wf_mod_tool as core
import test_bianca_dragon_abilities as bianca_fixture
import test_celtie_fever_abilities as celtie_fixture
import test_celtie_fever_leader as leader_fixture


def generated_kit(cid):
    if cid == "119989":
        source, leaders = bianca_fixture.official_sources()
        return bianca.ability_rows(source), bianca.leader_rows(source, leaders)
    fixture = leader_fixture.CeltieFeverLeaderTest()
    fixture.setUp()
    return celtie.ability_rows(celtie_fixture.official_sources()), fixture.rows


class CampusPanelTextTest(unittest.TestCase):
    def test_all_sections_exist_and_active_has_only_authorized_numeric_effects(self):
        for cid in text.CODES:
            sections = text.panel_descriptions(cid)
            self.assertEqual(set(sections), {"active", "leader", "a1", "a2", "a3", "a4", "a5", "a6"})
            self.assertEqual(sections["active"], text.active_description(cid))
            if cid == "149989":
                self.assertIn("基础合计75倍", sections["active"])
                self.assertIn("风属性共鸣且Fever模式中", sections["active"])
                self.assertIn("随「星风心得」成长", sections["active"])
                self.assertNotIn("能力3", sections["active"])
                self.assertIn("每层额外增加10倍", sections["active"])
            else:
                self.assertNotRegex(sections["active"], r"[0-9%％]")
            for value in sections.values():
                self.assertTrue(value.strip())
                self.assertNotRegex(value, r"I251|I629|DSL|APK|Unique|上限2147483647|交叉处不会重复")
        bianca_active = text.active_description("119989")
        for term in ("幼龙不在场", "幼龙在场", "成功召唤", "向下吐息", "幼龙回应", "幼龙吐息", "持续驻场", "退场"):
            self.assertIn(term, bianca_active)
        self.assertIn("伤害量以能力伤害加成判定", text.active_description("149989"))

    def test_real_first_row_ids_resolve_seven_distinct_overrides_without_mutating_kit(self):
        keys = set()
        for cid in text.CODES:
            abilities, leaders = generated_kit(cid)
            before = deepcopy((abilities, leaders))
            rows = text.override_string_rows(cid, abilities, leaders)
            self.assertEqual(before, (abilities, leaders))
            self.assertEqual(len(rows), 7)
            self.assertFalse(keys & rows.keys())
            keys.update(rows)
            self.assertEqual(rows["desc_override_" + leaders[0][0]][0][0], text.panel_descriptions(cid)["leader"])
            for slot in range(1, 7):
                first = abilities[cid + str(slot)][0]
                self.assertEqual(rows["desc_override_" + first[0]][0][0], text.panel_descriptions(cid)[f"a{slot}"])
                # 不能把自定义说明写到原生觉醒种类/等级字段。
                self.assertEqual(first[3:5], ["0", ""])
            self.assertEqual(leaders[0][1:3], ["0", ""])
        self.assertEqual(len(keys), 14)

    def test_missing_or_colliding_string_ids_are_rejected(self):
        abilities, leaders = generated_kit("119989")
        del abilities["1199894"]
        with self.assertRaisesRegex(ValueError, "a4"):
            text.override_string_rows("119989", abilities, leaders)
        abilities, leaders = generated_kit("149989")
        abilities["1499892"][0][0] = abilities["1499891"][0][0]
        with self.assertRaisesRegex(ValueError, "a2"):
            text.override_string_rows("149989", abilities, leaders)

    def test_flat_csv_roundtrip_preserves_real_newlines_and_single_cell_shape(self):
        for cid in text.CODES:
            rows = text.override_string_rows(cid, *generated_kit(cid))
            rows.update(text.native_flat_string_rows(cid))
            for key, group in rows.items():
                self.assertEqual(len(group), 1, key)
                self.assertEqual(len(group[0]), 1, key)
                self.assertTrue(group[0][0].strip(), key)
                self.assertNotIn("\\n", group[0][0], key)
                self.assertEqual(core.read_csv_lines(core.write_csv_lines(group)), group)

    def test_native_strings_only_replace_real_existing_content_keys(self):
        originals = {
            "119989": {**bianca.fever_tick_string_rows(), **bianca_bridge.flat_string_rows()},
            "149989": {**celtie.flat_string_rows(), **celtie_leader.flat_string_rows()},
        }
        for cid, rows in originals.items():
            rewritten = text.native_flat_string_rows(cid)
            self.assertTrue(set(rewritten) <= set(rows))
            self.assertTrue(all(text.CODES[cid] in key for key in rewritten))

    def test_bianca_conditional_and_unconditional_effects_remain_distinct(self):
        panels = text.panel_descriptions("119989")
        leader = panels["leader"].splitlines()
        self.assertIn("火属性共鸣", leader[0])
        self.assertIn("火属性共鸣", leader[1])
        self.assertNotIn("共鸣", leader[-1])  # 原真实I251追击没有共鸣门。
        self.assertIn("50倍火属性能力伤害", leader[-1])
        for term in ("+200%", "+400%", "Fever槽+500", "技能槽+25%"):
            self.assertIn(term, panels["leader"])
        for term in ("<icon id='main'>", "火属性共鸣时", "Fever模式中", "上限+20%", "每经过2秒", "队长技能槽+5%", "+50%", "清空"):
            self.assertIn(term, panels["a3"])
        abilities, _ = generated_kit("119989")
        attack, buff = abilities["1199892"]
        self.assertEqual((attack[35], buff[35]), ("60", "0"))
        self.assertIn("冷却1秒", panels["a2"].splitlines()[0])
        self.assertNotIn("冷却", panels["a2"].splitlines()[1])
        self.assertIn("火属性共鸣时，Fever模式中，每经过2秒", panels["a3"].splitlines()[1])
        # 2026-09-27 第三轮面板合并（wf_balance_20260927c_panels）：能力伤害与额外乘区两行同条件并为一行。
        self.assertIn("每层「焰域研修」使火属性角色能力伤害+50%、能力伤害额外乘区+1%", panels["a3"])
        separate = [row for row in abilities["1199893"] if row[109] == "412"]
        self.assertEqual(len(separate), 1)
        self.assertEqual(separate[0][113:115], ["1000", "1000"])
        self.assertEqual(panels["a4"].splitlines()[1], "Fever模式中，火属性角色技能充能速度+10%。")
        self.assertNotIn("共鸣", panels["a6"])
        self.assertEqual(panels["a6"].count("最大+100%"), 2)

    def test_celtie_stock_gain_consumption_and_limits_remain_explicit(self):
        panels = text.panel_descriptions("149989")
        leaders = generated_kit("149989")[1]
        self.assertEqual([row[4] for row in leaders[:2]], ["0", "0"])
        self.assertEqual(panels["leader"].splitlines()[0], "风属性角色攻击力+200%、能力伤害+400%。")
        self.assertNotIn("共鸣", panels["leader"].splitlines()[0])
        self.assertTrue(panels["leader"].splitlines()[1].startswith("风属性共鸣时，强化弹射"))
        for term in ("风属性共鸣时", "+200%", "+400%", "10倍", "2层", "消耗1层", "连击+7"):
            self.assertIn(term, panels["leader"])
        for term in ("分为3次", "+200%", "每消耗1层", "+5%"):
            self.assertIn(term, panels["a2"])
        # 2026-09-27 第二批覆盖：能力3 心得改为有上限（+8%/+5%，最多10层），无上限逐层成长搬进队长（+2.5%/+2.5%）。
        for term in ("<icon id='main'>", "风属性共鸣时", "35次", "非Fever", "25倍", "7的倍数", "+700%", "+0.7%", "+15%", "星风心得", "能力伤害+8%、攻击力+5%（最多10层）"):
            self.assertIn(term, panels["a3"])
        # 2026-09-27 第三轮（c）：队长每层 +20%/+20%（口径 D1），末行追加队长撤技能倍率封顶（口径 U8）；
        # 「星风心得」只由带风共鸣的 629 授予，其效果行不写「风属性共鸣时，」（面板共鸣省略）；
        # 末行是能力1 I704 开关行（前置 仅队长 + 风共鸣），共鸣是真实条件，保留。
        self.assertEqual(panels["leader"].splitlines()[-2],
                         "Fever模式中，每层「星风心得」使风属性角色能力伤害+20%、攻击力+20%。")
        # 2026-09-27 技能强化文案规范：强化条目点名技能、定性不写数字与秒数；技能描述只写本体（不写「不受此限」）。
        self.assertEqual(panels["leader"].splitlines()[-1],
                         "风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。")
        self.assertIn("2层「星风快门」与2层「星风心得」", panels["leader"])
        self.assertTrue(panels["active"].endswith("每层额外增加10倍（最多10层）。"))
        self.assertNotIn("不受此限", "".join(panels.values()))
        self.assertNotIn("星风快门累积", "".join(panels.values()))
        self.assertIn("命中的敌人风属性抗性降低", panels["a1"])
        self.assertIn("为『风中快门·十字双空牙』追加", panels["a1"])
        self.assertNotIn("全场敌人", panels["a1"])
        for slot, effect in (("a4", "贯穿"), ("a5", "浮游"), ("a6", "最大速度固定效果")):
            for term in ("风属性共鸣时", "Fever模式中", "每经过5秒", "1秒", effect):
                self.assertIn(term, panels[slot])
        for value in panels.values():
            self.assertNotRegex(value, "同条件|本场|无次数上限|消耗快门不减少|获取不衰减|与队长技分别|两者齐备")
        row = generated_kit("149989")[0]["1499896"][0]
        self.assertEqual((row[47], row[51], row[52]), ("688", "200000", "200000"))

    def test_main_slot_badge_matches_the_actual_unison_restriction(self):
        for cid in text.CODES:
            abilities, _ = generated_kit(cid)
            panels = text.panel_descriptions(cid)
            for slot in range(1, 7):
                restricted = any(row[1] == "false" for row in abilities[cid + str(slot)])
                self.assertEqual(restricted, "<icon id='main'>" in panels[f"a{slot}"])
            self.assertNotIn("<icon id='main'>", panels["leader"])

    def test_override_capability_is_explicit_and_return_values_are_isolated(self):
        self.assertEqual(text.metadata()["required_client_capabilities"], ["panel-description-override-v2"])
        self.assertFalse(text.metadata()["combat_rows_modified"])
        copy = text.panel_descriptions("119989")
        copy["leader"] = "changed"
        self.assertNotEqual(copy, text.panel_descriptions("119989"))
        for function in (text.panel_descriptions, text.active_description, text.native_flat_string_rows):
            with self.assertRaises(ValueError):
                function("999999")


if __name__ == "__main__":
    unittest.main()
