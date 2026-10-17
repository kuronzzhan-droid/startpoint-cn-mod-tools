"""碧安卡用户契约回归；四行 fixture 来自官方 1.4.54 CDN。"""
from __future__ import annotations

import copy
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_bianca_dragon_abilities as kit
import wf_client_legality as legality
import wf_dsl


def official_sources():
    # Keep native sentinel spelling and actual 126/124-column shape.
    rows = {
        "1110211": "lady_summoner_xm20_1,true,action_skill,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,211,0,,,25000,50000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",
        "1510013": "ruin_girl_3,false,attack_white,0,,1,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,4,,,,,,,,,,,false,0,5,White,,30000,60000,,,,,,,,,,,",
        "1610633": "blindness_gunner_1halfanv_3,false,attack_black,0,,1,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,134,0,,100000,100000,4,,6,,,,false,0,5,Black,,10000,20000,,,,,,,,,,,",
    }
    ability = {key: [value.split(",")] for key, value in rows.items()}
    leader = {"151001": ["ruin_girl,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,32,5,White,,75000,100000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,".split(",")]}
    return ability, leader


class BiancaDragonAbilitiesTest(unittest.TestCase):
    def setUp(self):
        self.source, self.leader_source = official_sources()
        self.abilities = kit.ability_rows(self.source)
        self.leader = kit.leader_rows(self.source, self.leader_source)

    def test_all_rows_follow_native_parsers_and_sources_stay_untouched(self):
        originals = copy.deepcopy((self.source, self.leader_source))
        kit.ability_rows(self.source)
        kit.leader_rows(self.source, self.leader_source)
        self.assertEqual(originals, (self.source, self.leader_source))
        for table, rows, width in (
            ("ability", sum(self.abilities.values(), []), 126),
            ("leader_ability", self.leader, 124),
        ):
            for row in rows:
                self.assertEqual(width, len(row))
                self.assertEqual([], legality.client_legality_problems(table, row))
                self.assertEqual([], legality.declared_block_field_problems(table, row))
                self.assertEqual([], legality.ability_element_column_problems(table, row, 1))

    def test_abilities_one_and_three_are_main_position_restricted(self):
        # 2026-09-27 平衡第二批（wf_balance_20260927b_bianca）：能力5 去主位限制、开局自充 75% → 50%。
        for slot, rows in self.abilities.items():
            self.assertEqual({"false" if slot.endswith(("1", "3")) else "true"}, {r[1] for r in rows})
        self.assertEqual("50000", self.abilities["1199891"][0][51])

    def test_leader_and_ability_two_require_fire_resonance(self):
        for row in self.leader[:5]:
            self.assertEqual(("2", "600000", "600000", "Red"),
                             (row[4], row[7], row[8], row[9]))
        for row in self.abilities["1199892"]:
            self.assertEqual(("2", "600000", "600000", "Red"),
                             (row[6], row[9], row[10], row[11]))
        self.assertEqual(("200000", "400000", "200000"),
                         (self.leader[0][49], self.leader[1][49], self.leader[2][111]))
        self.assertEqual("0", self.leader[-1][4], "other trigger gates stay unchanged")
        for rows, offsets in ((self.leader, (4, 11, 18)),
                              (sum(self.abilities.values(), []), (6, 13, 20))):
            self.assertNotIn("208", [row[offset] for row in rows for offset in offsets])

    def test_summon_rewards_require_own_unique_marker_and_are_not_opening_charge(self):
        rows = kit.leader_rows(self.source, self.leader_source, summon_unique_id=123456)
        for row in rows[3:5]:
            self.assertEqual(("185", "0", "123456"), (row[25], row[26], row[35]))
        self.assertEqual(("213", "50000000"), (rows[3][45], rows[3][49]))
        self.assertEqual(("211", "5", "Red", "25000"),
                         (rows[4][45], rows[4][46], rows[4][47], rows[4][49]))

    def test_skill_damage_distinguishes_all_enemy_and_nearest_and_true_ability_source(self):
        all_enemy = self.leader[-1]
        self.assertEqual(("23", "7", "Red", "251", "5000000", "(None)", "0"),
                         (all_enemy[25], all_enemy[26], all_enemy[27], all_enemy[45],
                          all_enemy[49], all_enemy[67], all_enemy[33]))
        nearest, buff = self.abilities["1199892"]
        self.assertEqual(("352", "1000000", "60"), (nearest[47], nearest[51], nearest[35]))
        self.assertEqual(("0", "2", "100000", "48000000", "0"),
                         (buff[47], buff[48], buff[51], buff[57], buff[35]))

    def test_fever_stack_reset_deletes_only_private_uid_and_preserves_others(self):
        rows = kit.fever_rows(self.source, fever_stack_unique_id=123457)
        cap, tick, gain, clear, charge, separate = rows
        self.assertEqual(("124", "20000", "4"), (cap[109], cap[113], cap[97]))
        self.assertEqual(("248", "12000000", "629"),
                         (tick[27], tick[30], tick[47]))
        self.assertEqual(kit.FEVER_TICK_STRING_ID, tick[70])
        self.assertEqual(kit.FEVER_TICK_ACTION_PATH, tick[71])
        self.assertEqual(("134", "123457", "154", "50000", "(None)", "12"),
                         (gain[97], gain[104], gain[109], gain[113], gain[102], gain[13]))
        self.assertEqual(("184", "528", "0", "123457", "0"),
                         (clear[27], clear[47], clear[48], clear[68], clear[13]))
        # Native DeleteUniqueCondition targets exactly one ID, not all buffs.
        live = {123457: 8, 42: 3}
        live.pop(int(clear[68]))
        self.assertEqual({42: 3}, live)
        self.assertEqual(("211", "2", "5000", "(None)"),
                         (charge[47], charge[48], charge[51], charge[34]))
        self.assertEqual(separate[104], clear[68])

    def test_fever_each_layer_adds_one_percent_ability_only_separated_damage(self):
        rows = self.abilities["1199893"]
        regular, separate = rows[2], rows[5]
        self.assertEqual([i for i, pair in enumerate(zip(regular, separate)) if pair[0] != pair[1]],
                         [109, 113, 114])
        self.assertEqual((separate[1], separate[6], separate[9:12], separate[13]),
                         ("false", "2", ["600000", "600000", "Red"], "12"))
        self.assertEqual((separate[97:99], separate[100:105]),
                         (["134", "0"], ["100000", "100000", "(None)", "", "11998903"]))
        self.assertEqual(separate[109:115], ["412", "5", "Red", "", "1000", "1000"])
        # Native D134 is a live counter, not a cumulative event trigger. D412 is
        # summed only in the ability damage branch, while D411 would be skill.
        for layers in (0, 1, 3, 10, 120):
            self.assertEqual(layers * int(separate[113]), layers * 1000)
        live = {kit.FEVER_STACK_UNIQUE_ID: 10, 42: 3}
        live.pop(int(rows[3][68]))
        self.assertEqual(live.get(int(separate[104]), 0), 0)
        self.assertEqual(live[42], 3)
        self.assertEqual(kit.metadata()["fever_stack"]["separated_ability_bonus_per_stack"], 0.01)

    def test_charging_speed_duration_and_fever_ratio_keep_distinct_units(self):
        duration, charging = self.abilities["1199894"]
        self.assertEqual(("56", "15000", "2"), (duration[47], duration[51], duration[6]))
        self.assertEqual(("3", "10000", "4", "0"),
                         (charging[109], charging[113], charging[97], charging[6]))
        ratio = self.abilities["1199895"][0]
        # 2026-09-27 平衡第二批（wf_balance_20260927b_bianca）：能力5 去主位限制 c1 false → true、面板不带主位图标。
        self.assertEqual(("true", "2", "600000", "600000", "Red"),
                         (ratio[1], ratio[6], ratio[9], ratio[10], ratio[11]))
        self.assertEqual(("724", "15000", "23", "7", "Red"),
                         (ratio[47], ratio[51], ratio[27], ratio[28], ratio[29]))
        self.assertEqual(["kyubi-fever-ratio-v1"], legality.required_client_capabilities("ability", ratio))
        from wf_campus_panel_text import panel_descriptions
        self.assertEqual("火属性共鸣时，火属性角色发动技能：Fever槽+15%。",
                         panel_descriptions("119989")["a5"])

    def test_ability_six_caps_at_ten_triggers_and_fever_only_gates_attack_gain(self):
        damage, attack = self.abilities["1199896"]
        for row in (damage, attack):
            self.assertEqual(("23", "7", "Red", "10", "5", "Red", "10000"),
                             (row[27], row[28], row[29], row[34], row[48], row[49], row[51]))
            self.assertEqual(100_000, int(row[34]) * int(row[51]))
        self.assertEqual(("388", "0"), (damage[47], damage[13]))
        self.assertEqual(("32", "12"), (attack[47], attack[13]))

    def test_runtime_limits_and_pending_bridge_are_explicit(self):
        metadata = kit.metadata()
        self.assertEqual("all resonance gates use fire pre2 Member(Red,6)",
                         metadata["resonance"])
        self.assertTrue(metadata["fever_stack"]["removed_on_fever_end"])
        self.assertIsNone(metadata["fever_stack"]["balance_cap"])
        self.assertIn("fractional period carries", metadata["fever_stack"]["timer"])
        self.assertIn("bridge", metadata["a1_enhancement_bridge"])

    def test_private_tick_has_native_text_and_only_increments_the_selected_counter(self):
        assets = kit.fever_tick_assets(fever_stack_unique_id=123457)
        self.assertEqual(1, len(assets))
        (tier, path), raw = next(iter(assets.items()))
        self.assertEqual("common", tier)
        self.assertEqual(kit.FEVER_TICK_ACTION_PATH + ".action.dsl.amf3.deflate", path)
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        self.assertEqual("Block", tree[11][0])
        self.assertEqual(1, len(tree[11][1]))
        guard = tree[11][1][0][1]
        self.assertEqual("ConditionalsFeverMode", guard[0])
        self.assertEqual(["Block", []], guard[2])
        command = guard[1][1][0][1]
        self.assertEqual(("CreateCondition", -17), tuple(command[:2]))
        self.assertEqual([["ACUnique", 123457, [{"min": 1, "max": 1}]]], command[2])
        self.assertEqual([], legality.action_dsl_subject_binding_problems(tree))
        self.assertEqual({kit.FEVER_TICK_STRING_ID: [["自身的「焰域研修」等级上升1级"]]},
                         kit.fever_tick_string_rows())


if __name__ == "__main__":
    unittest.main()
