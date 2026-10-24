"""角色详情 C7050 回归：百分比只交给已支持的普通能力解析器。"""
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_text as text


class NephtimDetailC7050Test(unittest.TestCase):
    def setUp(self):
        self.source, _ = official_sources()
        self.abilities = abilities.ability_rows(self.source)
        self.leader = leader.leader_rows(self.source)

    def test_leader_never_requires_the_missing_ratio_constructor(self):
        self.assertFalse(any(r[3] == "0" and r[45] == "724" for r in self.leader))
        self.assertEqual([], leader.metadata()["required_client_capabilities"])

    def test_ratio_is_once_in_main_only_a3_with_dark_gate_and_no_leader_gate(self):
        matches = [(key, row) for key, rows in self.abilities.items()
                   for row in rows if row[5] == "0" and row[47] == "724"]
        self.assertEqual(1, len(matches))
        key, row = matches[0]
        self.assertEqual("1699893", key)
        self.assertEqual("false", row[1])
        self.assertEqual(["2", "", "", "600000", "600000", "Black", ""], row[6:13])
        self.assertEqual(["0", "", "", "", "", "", ""], row[13:20])
        self.assertEqual(["0", "", "", "", "", "", ""], row[20:27])
        self.assertEqual(["20", "7", "Black", "4500000", "4500000"], row[27:32])
        self.assertEqual(["(None)", "0"], row[34:36])
        self.assertEqual(["15000", "15000"], row[51:53])

    def test_panel_moves_the_effect_to_a3_and_keeps_main_badge(self):
        panels = text.panel_descriptions()
        self.assertNotIn("每直接攻击45次", panels["leader"])
        line, = [line for line in panels["a3"].splitlines() if "每直接攻击45次" in line]
        self.assertTrue(line.startswith(text.MAIN_ICON))
        self.assertNotIn("队长", line)
        self.assertIn("暗属性共鸣时", line)
        self.assertIn("Fever 槽+15%", line)
        self.assertNotIn("Fever 模式中", line)


if __name__ == "__main__":
    unittest.main()
