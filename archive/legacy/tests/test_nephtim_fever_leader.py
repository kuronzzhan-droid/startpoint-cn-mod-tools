"""奈芙提姆队长的PF门、直击计数与暗共鸣常驻贯穿延时。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_client_legality as legality
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as kit


class NephtimFeverLeaderTest(unittest.TestCase):
    def setUp(self):
        self.source, _ = official_sources()
        self.rows = kit.leader_rows(self.source)

    def test_all_rows_are_native_dark_only_and_leave_sources_untouched(self):
        before = deepcopy(self.source)
        kit.leader_rows(self.source)
        self.assertEqual(before, self.source)
        for row in self.rows:
            self.assertEqual(124, len(row))
            self.assertEqual([], legality.client_legality_problems("leader_ability", row))
            self.assertEqual([], legality.declared_block_field_problems("leader_ability", row))
            self.assertEqual([], legality.ability_element_column_problems("leader_ability", row, 6))
            self.assertEqual(["2", "", "", "600000", "600000", "Black", ""], row[4:11])

    def test_native_special_pf_references_the_combined_three_level_program(self):
        pf = self.rows[0]
        self.assertEqual("722", pf[45])
        self.assertEqual([kit.PF_ID, "1,2,3", kit.PF_STRING_ID], pf[80:83])
        custom = kit.leader_rows(self.source, power_flip_id="custom_pf", power_flip_string_id="custom_text")
        self.assertEqual(["custom_pf", "1,2,3", "custom_text"], custom[0][80:83])

    def test_skill_enhancement_flag_follows_pf_then_dark_base_direct_and_attack(self):
        # 作者 2026-09-27（方案B）：I536 从能力1搬进队长，紧跟 I722；与官方队长 121189#3 同形。
        flag, direct, attack = self.rows[1:4]
        self.assertEqual(["ruin_girl_campus", "0", ""] + abilities.enhance_row(self.source)[5:], flag)
        self.assertEqual(("0", "0", "0", "536", abilities.CHANGE_SKILL_STRING_ID),
                         (flag[3], flag[11], flag[25], flag[45], flag[68]))
        self.assertEqual([0, 1, 3, 4, 7, 8, 9, 11, 18, 25, 37, 44, 45, 68],
                         [i for i, value in enumerate(flag) if value != ""])
        self.assertEqual(536, kit.metadata()["skill_enhancement_flag"]["content"])
        self.assertEqual(("33", "400000", "5", "Black", "0"),
                         (direct[45], direct[49], direct[46], direct[47], direct[11]))
        self.assertEqual(("32", "200000", "5", "Black", "0"),
                         (attack[45], attack[49], attack[46], attack[47], attack[11]))
        # Fever 中技能槽上限+10%（during 124，前置12）已移入能力2。
        self.assertFalse(any(r[3] == "1" or r[107] == "124" for r in self.rows))
        # 作者 2026-09-27 第二批：前置12（Fever）只出现在从能力3 搬来的两条 T235 贯穿成长行（第9、10行）。
        self.assertEqual([8, 9], [i for i, r in enumerate(self.rows) if "12" in (r[4], r[11], r[18])])
        self.assertEqual({"235"}, {self.rows[i][25] for i in (8, 9)})

    def test_dark_resonance_piercing_extension_is_carried_by_ability2(self):
        # 第一批 8 行 + 2026-09-27 第二批追加的两条贯穿成长（I32/I33）= 10 行。
        self.assertEqual(10, len(self.rows))
        self.assertEqual(["722", "536", "33", "32", "50", "56", "211", "629", "32", "33"],
                         [r[45] for r in self.rows])
        extension = kit.metadata()["piercing_extension"]
        self.assertFalse(extension["requires_fever"])
        self.assertEqual("dark_resonance", extension["strategy"])
        self.assertEqual((0, "ability2"), (extension["leader_rows"], extension["location"]))

    def test_piercing_is_one_merged_ability2_row_without_transition_increments(self):
        self.assertEqual([], [row for row in self.rows if row[45] == "190"])
        self.assertFalse({"8", "184", "139", "18"} & {row[25] for row in self.rows})
        a2 = [row for row in abilities.ability_rows(self.source)["1699892"] if row[47] == "190"]
        self.assertEqual(1, len(a2))
        # 原队长 20000 + 能力2 20000 按行相加 = 合并后的单行 40000。
        self.assertEqual(("0", "190", "40000", "true"), (a2[0][27], a2[0][47], a2[0][51], a2[0][1]))
        self.assertEqual(40, kit.metadata()["piercing_extension"]["ability2_percent"])

    def test_only_the_approved_piercing_strategy_is_accepted(self):
        self.assertEqual(self.rows, kit.leader_rows(self.source, piercing_extension="dark_resonance"))
        for policy in ("fever", "own_fever_sources", "", None):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "approved dark_resonance"):
                kit.leader_rows(self.source, piercing_extension=policy)


if __name__ == "__main__":
    unittest.main()
