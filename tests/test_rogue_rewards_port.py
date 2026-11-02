# -*- coding: utf-8 -*-
"""深渊代币展示期限与武器等级成长回归测试。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
from wf.tools.rogue import rogue_rewards as rewards  # noqa: E402


def leaf(rows: list[list[str]]) -> str:
    return core.write_csv_lines(rows)


class TestAbyssRewardProgression(unittest.TestCase):
    def test_token_is_visible_for_the_full_permanent_event_window(self):
        row = [f"c{i}" for i in range(23)]
        row[19] = "2025-05-29 12:00:00"
        row[20] = "2025-06-24 11:59:59"
        row[21] = "false"

        built = rewards.build_token_leaf(leaf([row]))
        actual = core.read_csv_lines(built)[0]

        self.assertEqual(rewards.TOKEN_ID, actual[1])
        self.assertEqual(rewards.TOKEN_START, actual[19])
        self.assertEqual(rewards.TOKEN_END, actual[20])
        self.assertEqual("true", actual[21])

    def test_weapon_level_one_is_half_of_level_five(self):
        template = [""] * 123
        template[44] = "32"
        template[45] = "5"
        template[48] = "12500"
        template[49] = "25000"
        spec = rewards.WeaponSpec(
            "8000999",
            "test",
            "5010001",
            0,
            "Red",
            "test",
            (rewards.EffectSpec("300001", "32", 2_000_000),),
        )

        built = rewards.build_soul_leaf(
            {"300001": leaf([template])}, spec, validate=False
        )
        actual = core.read_csv_lines(built)[0]

        self.assertEqual("5", actual[45])
        self.assertEqual(int(actual[49]) // 2, int(actual[48]))
        self.assertNotEqual(actual[48], actual[49])


if __name__ == "__main__":
    unittest.main()
