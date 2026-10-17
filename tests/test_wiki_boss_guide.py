"""Five-boss guide rejects drift and explains current numeric mechanics."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_five_boss_v2 as builder
from wf_wiki_boss_guide import verify_affixes, verify_trials
from wf_wiki_boss_text import affix_texts, enemy_conditions, reward_text


class BossGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[1]
        cls.spec = json.loads((cls.repo / "five_boss_v2_spec.json").read_text(encoding="utf8"))

    def test_current_affix_values_are_visible_without_programs(self):
        text = affix_texts(self.spec["affix_params"])
        self.assertIn("250 次直接攻击", text["heal_seal"]["description"])
        self.assertIn("上限 30", text["combo_cap"]["description"])
        self.assertIn("15 秒", text["purge_r1"]["description"])
        self.assertIn("30% 技能槽", text["sig_king_seal"]["description"])
        self.assertNotIn("mod_fb", json.dumps(list(text.values())))

    def test_enemy_resistances_are_not_player_damage_buffs(self):
        result = enemy_conditions([(0, .5), (3, -.3), (4, None)])
        self.assertEqual(result, ["敌方能力伤害耐性 +50%", "敌方技能伤害耐性 -30%", "敌方弱体耐性"])

    def test_live_program_drift_prevents_publication(self):
        trees = builder.affix_library(self.spec["affix_params"])
        source = Mock()
        source.tree.side_effect = lambda path: trees[path.split("$")[1].split(".")[0]]
        verify_affixes(source, self.spec["affix_params"])
        source.tree.return_value = []
        source.tree.side_effect = None
        with self.assertRaisesRegex(ValueError, "机制已变化"):
            verify_affixes(source, self.spec["affix_params"])

    def test_trials_count_hits_and_drift_is_rejected(self):
        boss = {"routine": {"out": "test", "trials": {"charge": {"kind": "skill", "count": 12, "frames": 600}}}}
        row = [""] * 48
        for index, value in {22: "1", 23: "12", 24: "true", 29: "12", 47: "600"}.items():
            row[index] = value
        table = {"test": {"80": {"charge": builder.write_rows([row])}}}
        with patch("wf_wiki_boss_guide.nested", return_value=table):
            result = verify_trials(Mock(), boss)
            self.assertIn("10 秒内达成 12 次技能命中", result[0])
            row[23] = "11"
            table["test"]["80"]["charge"] = builder.write_rows([row])
            with self.assertRaisesRegex(ValueError, "试炼门槛变化"):
                verify_trials(Mock(), boss)

    def assert_reward_rates_and_manual_exceptions(self, raw):
        names = {str(key): str(key) for key in [10000144, 10000145, 10000146, 10000147, 10000310]}
        result = reward_text(raw, names)
        self.assertIn("60%", result[0]["description"])
        self.assertIn("不受手动倍率", result[0]["description"])
        self.assertIn("10–15", result[3]["description"])
        self.assertIn("5%", result[-1]["description"])
        self.assertIn("可能重复", result[-1]["description"])
        with self.assertRaisesRegex(ValueError, "公式已变化"):
            reward_text(raw.replace("amount: 10 * input.rewardMultiplier", "amount: 20 * input.rewardMultiplier"), names)

    def test_reward_parser_rates_and_manual_exceptions(self):
        fixture = Path(__file__).parent / "fixtures/wiki/five_boss_rewards.ts.txt"
        self.assert_reward_rates_and_manual_exceptions(fixture.read_text(encoding="utf8"))

    def test_current_server_reward_rates_match_guide(self):
        source = self.repo / "src/multi/five-boss/rewards.ts"
        if not source.is_file():
            self.skipTest("可选集成校验需要匹配版本的完整游戏服务端源码")
        self.assert_reward_rates_and_manual_exceptions(source.read_text(encoding="utf8"))


if __name__ == "__main__":
    unittest.main()
