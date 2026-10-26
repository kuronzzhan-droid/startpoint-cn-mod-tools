"""Equipment level, soul availability and player-facing text contracts."""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_describe
import wf_wiki_equipment as equipment
from wf_wiki_equipment_helpers import PublicText, effects, endpoint_row, learned_rows


def ability(slot="0", learned="1", power="10000", maximum="20000"):
    row = [""] * 123
    row[:3] = [slot, learned, "0"]
    row[44:50] = ["32", "0", "", "", power, maximum]
    return row


class Source:
    def __init__(self):
        self.data = {}
        self._tables = {}
        self.live_hashes = {}
        self.missing = set()
        self.verify_unchanged = Mock()

    def table(self, key):
        return self.data.get(key, {})

    def raw(self, key):
        return None


class EquipmentTests(unittest.TestCase):
    def test_equipment_elements_follow_server_registry_without_guessing_unknowns(self):
        self.assertEqual([equipment.equipment_element(value) for value in range(6)], list("火水雷风光暗"))
        self.assertEqual(equipment.equipment_element(-1), "通用/未分类")
        for value in (None, "0", True, 6):
            self.assertEqual(equipment.equipment_element(value), "未标注")

    def test_slot_upgrades_replace_old_version_without_losing_other_slots(self):
        rows = [ability("0", "1"), ability("0", "3"), ability("0", "5"), ability("1", "1")]
        self.assertEqual([row[:2] for row in learned_rows(rows, 4)], [["0", "3"], ["1", "1"]])
        self.assertEqual(len(learned_rows(rows, 5)), 2)

    def test_endpoint_values_remain_source_immutable_and_have_no_ranges(self):
        row = ability()
        self.assertEqual(endpoint_row(row, "ability_soul", True)[48:50], ["20000"] * 2)
        self.assertEqual(endpoint_row(row, "ability_soul", False)[48:50], ["10000"] * 2)
        self.assertEqual(row[48:50], ["10000", "20000"])
        text = PublicText(Source())
        self.assertEqual(effects([row], "ability_soul", 5, text), ["自身 攻击力 20%"])
        self.assertEqual(effects([row], "ability_soul", 1, text, False), ["自身 攻击力 10%"])

    def test_native_group_names_and_terms_do_not_expose_codes(self):
        source = Source()
        source.data = {"character": {"10": [["internal_wolf", "1", "5", "0", "Beast", "tag_wolf"]]},
                       "text": {"10": [["狼骑士"]]}, "condition": {"80001": [["hidden", "月耀"]]}}
        text = PublicText(source)
        result = text.clean("tag_wolf·MySelf：固有80001；Direct伤害；[hidden_code]")
        self.assertEqual(result, "狼骑士·自身：月耀；直接攻击伤害；特殊效果")
        self.assertEqual(text.clean("自身 战斗不能Base计数- 400%"), "自身 复活所需碰撞次数-4次")
        self.assertEqual(text.clean("自身 2号位技能槽 50%"), "自身 技能槽上限 50%")
        self.assertEqual(text.clean("Elapsed时间≥3600 → 自身 屏障 10%"), "经过时间≥3600 → 自身 屏障 10%")
        self.assertEqual(text.clean("经过时间时间≥3600"), "经过时间≥3600")

    def test_boundary_materials_are_charged_once(self):
        rows = [{"stage": 1, "enhancementMaxLevel": 69, "costs": [{"id": 1, "amount": 12}]},
                {"stage": 2, "enhancementMaxLevel": 70, "costs": [{"id": 1, "amount": 30}],
                 "userCost": {"type": 2, "amount": 10}}]
        costs = equipment.enhancement_costs(rows, {"1": "深渊代币"})
        self.assertEqual(costs["total"], [{"name": "深渊代币", "amount": 858}, {"name": "羁绊证", "amount": 10}])

    def test_soul_registry_is_distinct_from_generation_flag(self):
        source = Source()
        soul_row = ability()
        erow = ["internal", "测试剑", "0", "", "", "", "item/test", "描述", "5", "false", "10", "5"]
        source.data = {equipment.EQUIPMENT: {"10": [erow], "11": [erow]}, equipment.SOUL: {"10": [soul_row]}}
        upgrade = ["0", "1", "10", "24", "48"] + ability(power="10000", maximum="10000")[2:]
        source.data[equipment.ENHANCEMENT] = {"10": [["10", "", "测试剑强化"]]}
        source.data[equipment.ENHANCEMENT_ABILITY] = {"10": [upgrade]}
        source._tables[(equipment.STATUS, False, "wiki-nested")] = {
            "10": {"1": "100,20", "5": "150,30"}, "11": {"1": "100,20", "5": "150,30"}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "assets").mkdir()
            for name, value in {"equipment_ids": [10, 11], "soul_item_ids": [10], "equipment_element": {"10": 0, "11": -1}, "equipment_enhancement_shop": {}}.items():
                (root / "assets" / (name + ".json")).write_text(json.dumps(value), encoding="utf8")
            rules = root / "client-patch/equipment-rules/rules.py"
            rules.parent.mkdir(parents=True)
            rules.write_text("class Config:\n    cursed_threshold: int = 2\n    decay_off: int = 4\n", encoding="utf8")
            with patch.object(equipment.EquipmentImages, "image", return_value="media/icon.webp"):
                result = equipment.build_equipment_catalog(root, Mock(), source)
        first, second = result["equipment"]
        self.assertEqual(first["element"], "火")
        self.assertEqual(second["element"], "通用/未分类")
        self.assertTrue(first["canSoul"])
        self.assertFalse(first["soul"]["canGenerate"])
        self.assertFalse(second["canSoul"])
        self.assertEqual(second["soul"]["effects"], [])
        self.assertEqual(first["stats"]["awakened"], {"hp": 150, "atk": 30})
        self.assertEqual(first["enhancement"]["finalEffects"], ["自身 攻击力 30%"])
        self.assertEqual(first["enhancement"]["initialFinalEffects"], ["自身 攻击力 20%"])
        source.verify_unchanged.assert_called_once()

    def assert_party_policy_counts_souls_and_excludes_paradox_from_curses(self, raw):
        policy = equipment.party_rules(raw)
        self.assertEqual(policy["curseExclusion"]["threshold"], 2)
        self.assertFalse(policy["curseExclusion"]["paradoxIncluded"])
        self.assertTrue(policy["paradoxDecay"]["includesSouls"])
        self.assertTrue(policy["paradoxDecay"]["excludeSelf"])
        self.assertEqual(policy["paradoxDecay"]["offAtOtherCount"], 4)

    def test_party_policy_parser_counts_souls_and_excludes_paradox_from_curses(self):
        fixture = Path(__file__).parent / "fixtures/wiki/equipment_rules.py.txt"
        self.assert_party_policy_counts_souls_and_excludes_paradox_from_curses(fixture.read_bytes())

    def test_current_client_party_policy_matches_guide(self):
        source = client_patch_path('equipment-rules/rules.py')
        if not source.is_file():
            self.skipTest("可选集成校验需要匹配版本的完整客户端补丁源码")
        self.assert_party_policy_counts_souls_and_excludes_paradox_from_curses(source.read_bytes())


if __name__ == "__main__":
    unittest.main()
