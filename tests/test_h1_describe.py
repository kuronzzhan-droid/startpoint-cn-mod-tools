# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tool_source import tool_source  # noqa: E402


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_describe  # noqa: E402


class DescribeSemanticsTest(unittest.TestCase):
    def make_ability_row(self) -> list[str]:
        row = [""] * int(wf_describe.layout("ability")["ncols"])
        row[0] = "semantic_test"
        row[1] = "false"
        row[2] = "action_skill"
        row[5] = "0"  # Instant
        return row

    def set_skill_gauge_content(self, row: list[str], strength: int = 5000) -> None:
        base = wf_describe.layout("ability")["blocks"]["instant_content"]
        row[base] = "211"  # SkillGauge
        row[base + 1] = "0"  # Myself
        row[base + 4] = str(strength)
        row[base + 5] = str(strength)

    def set_unique_content(self, row: list[str], *, kind: int, levels: int) -> None:
        base = wf_describe.layout("ability")["blocks"]["instant_content"]
        row[base] = str(kind)
        row[base + 1] = "0"  # Myself
        row[base + 4] = row[base + 5] = str(levels * 100000)
        row[base + 23] = "semantic_unique"
        if kind == 461:  # ConditionUnique applies the change once.
            row[base + 12] = row[base + 13] = "100000"

    def test_self_direct_attack_source_and_main_position_are_visible(self) -> None:
        row = self.make_ability_row()
        blocks = wf_describe.layout("ability")["blocks"]
        trigger = blocks["instant_trigger"]
        row[trigger] = "20"  # MemberDirectAttack
        row[trigger + 1] = "0"  # Myself
        row[trigger + 3] = row[trigger + 4] = "100000"
        row[trigger + 8] = "120"  # two seconds, raw frames
        self.set_skill_gauge_content(row)

        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("[主位]", rendered)
        self.assertIn("自身·直接攻击", rendered)
        self.assertIn("CT2秒", rendered)
        self.assertIn("技能槽 5%", rendered)

    def test_other_wind_skill_source_is_visible(self) -> None:
        row = self.make_ability_row()
        blocks = wf_describe.layout("ability")["blocks"]
        trigger = blocks["instant_trigger"]
        row[trigger] = "23"  # SkillInvoke
        row[trigger + 1] = "4"  # OneOfExceptMyself
        row[trigger + 2] = "Green"
        row[trigger + 3] = row[trigger + 4] = "100000"
        self.set_skill_gauge_content(row, 10000)

        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("除自身任一(风)·技能发动", rendered)
        self.assertIn("技能槽 10%", rendered)

    def test_instant_delay_is_seconds_not_frames(self) -> None:
        row = self.make_ability_row()
        blocks = wf_describe.layout("ability")["blocks"]
        trigger = blocks["instant_trigger"]
        row[trigger] = "23"
        row[trigger + 1] = "0"
        row[trigger + 3] = row[trigger + 4] = "100000"
        row[blocks["instant_delay"]] = "2"
        self.set_skill_gauge_content(row, 20000)

        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("(延迟2秒)", rendered)
        self.assertNotIn("0.0333333", rendered)

    def test_unisonable_row_is_not_marked_main_only(self) -> None:
        row = self.make_ability_row()
        row[1] = "true"
        self.set_skill_gauge_content(row)
        self.assertNotIn("[主位]", wf_describe.describe_line(row, "ability"))

    def test_puller_enum_nine_differs_between_instant_and_during(self) -> None:
        self.assertEqual("多球任一", wf_describe.INSTANT_PULLER_CN[9])
        self.assertEqual("全队总和", wf_describe.DURING_PULLER_CN[9])
        self.assertEqual("多球任一", wf_describe.DURING_PULLER_CN[10])

    def test_six_element_character_slayer_is_explicit_damage_term(self) -> None:
        row = self.make_ability_row()
        blocks = wf_describe.layout("ability")["blocks"]
        row[5] = "1"  # During
        content = blocks["during_content"]
        row[content] = "20"  # CharacterSlayer
        row[content + 1] = "0"  # Myself
        row[content + 4] = row[content + 5] = "15000"
        row[content + 8] = "Red,Blue,Green,Yellow,White,Black"

        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("对六属性敌人造成的伤害+15%（独立伤害乘区1）", rendered)
        self.assertNotIn("角色特攻", rendered)
        self.assertNotIn("[限Red", rendered)

    def test_unique_condition_strength_is_level_not_percent(self) -> None:
        row = self.make_ability_row()
        self.set_unique_content(row, kind=461, levels=2)
        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("固有状态等级+ 2", rendered)
        self.assertNotIn("200%", rendered)
        self.assertNotIn("×1次", rendered)

    def test_consume_unique_condition_strength_is_level_not_percent(self) -> None:
        row = self.make_ability_row()
        self.set_unique_content(row, kind=525, levels=3)
        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("消耗固有状态等级 3", rendered)
        self.assertNotIn("300%", rendered)

    def test_coffin_count_is_integer_not_percent(self) -> None:
        row = self.make_ability_row()
        base = wf_describe.layout("ability")["blocks"]["instant_content"]
        row[base] = "203"  # CoffinBaseCountDown
        row[base + 1] = "5"  # Party
        row[base + 4] = row[base + 5] = "3500000"
        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("棺柩计数- 35", rendered)
        self.assertNotIn("3500%", rendered)

    def test_guts_strength_is_integer_not_percent(self) -> None:
        row = self.make_ability_row()
        base = wf_describe.layout("ability")["blocks"]["instant_content"]
        row[base] = "468"  # ConditionGuts
        row[base + 1] = "0"  # Myself
        row[base + 4] = row[base + 5] = "100000"
        row[base + 12] = row[base + 13] = "100000"
        rendered = wf_describe.describe_line(row, "ability")
        self.assertIn("毅力次数+ 1", rendered)
        self.assertNotIn("100%", rendered)
        self.assertNotIn("×1次", rendered)


if __name__ == "__main__":
    unittest.main()


def test_composer_exposes_distinct_puller_enums_and_third_skill_tier(monkeypatch):
    import importlib.util
    import wf_mod_tool as core

    monkeypatch.setattr(core, "resolve_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(core, "resolve_active_store", lambda *args, **kwargs: MOD_TOOLS)
    monkeypatch.setattr(core, "default_source_store", lambda: None)
    monkeypatch.setattr(core, "resolve_server_dir", lambda: MOD_TOOLS)
    spec = importlib.util.spec_from_file_location("_h1_gui_metadata", tool_source(MOD_TOOLS, "wf_gui.py"))
    wf_gui = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, wf_gui)
    spec.loader.exec_module(wf_gui)

    monkeypatch.setattr(wf_gui, "list_unique_conditions", lambda: {"conditions": []})
    metadata = wf_gui.composer_meta()
    assert metadata["small"]["instant_puller"]["9"] == "多球任一"
    assert metadata["small"]["during_puller"]["9"] == "全队总和"
    fields = wf_gui._SKILL_TEXT_SYNC["3"]
    assert [wf_gui.CHAR_FIELD_MAP[field] for field in fields] == [("text", 8), ("text", 9)]
