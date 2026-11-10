import json
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import abyss_quest_details as details
from wf.tools.rogue import rogue_element_channel as channel


class DetailsTests(unittest.TestCase):
    def test_reroll_inherits_details_without_a_cli_flag(self):
        current = details.with_details("「诅咒」内容", "旧敌人", 100000000)
        self.assertTrue(details.should_enable(None, ["普通描述", current]))
        self.assertFalse(details.should_enable(None, ["普通描述"]))
        self.assertTrue(details.should_enable(True, []))

    def test_rerolled_description_uses_new_enemy_and_final_hp(self):
        original = "「新诅咒」血量变化 【属性伤害：水=0.1%;风=0.1%】"
        floor = {"r": 2, "row": ["", "", "", details.with_details(original, "旧敌人", 100000000)],
                 "pick": {"label": "新敌人"},
                 "hp_audit": {"family": "general", "absolute_verified": True, "true_hp": 250000000}}
        result = details.for_generated_floor(floor)
        decoded = unquote(result)
        self.assertNotIn("旧敌人", decoded)
        self.assertIn("新敌人", decoded)
        self.assertIn("2.50 亿", decoded)
        self.assertEqual(1, result.count("【关卡资料："))
        self.assertEqual(channel.decode(original), channel.decode(result))
        floor["hp_audit"]["absolute_verified"] = False
        with self.assertRaises(ValueError):
            details.for_generated_floor(floor)

    def test_metadata_preserves_combat_block_and_updates_without_duplicates(self):
        original = "「深渊法阵」充能领域 【属性伤害：水=0.1%;风=0.1%】"
        first = details.with_details(original, "甲", 100000000)
        second = details.with_details(first, "乙", 200000000)
        self.assertTrue(second.startswith(original))
        self.assertEqual(1, second.count("【关卡资料："))
        self.assertEqual(channel.decode(original), channel.decode(second))
        value = json.loads(unquote(second.split("【关卡资料：")[1][:-1]))
        self.assertEqual("乙", value["enemy"])
        self.assertIn("2.00 亿", value["hp"])

    def test_invalid_hp_rejected_and_no_estimate_for_mob_floor(self):
        for hp in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                details.with_details("", "敌人", hp)
        self.assertIn("小怪关卡", unquote(details.with_details("", "小怪", None)))

    def test_internal_labels_are_not_player_facing(self):
        pick = {"label": "HP重排·血量保底·异质魔晶羊"}
        self.assertEqual("异质魔晶羊", details.display_enemy(pick))
        pick = {"label": "塔·administrator_light_single", "thumbnail_evidence": {
            "boss_visual_identity": ["管理者\x00battle/boss/administrator"]}}
        self.assertEqual("管理者", details.display_enemy(pick))


if __name__ == "__main__":
    unittest.main()
