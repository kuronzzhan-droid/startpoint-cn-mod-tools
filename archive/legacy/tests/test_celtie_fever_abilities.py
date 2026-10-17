"""校园希尔媞用户能力契约；fixture 来自官方最新希尔媞的完整 CSV。"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_celtie_fever_abilities as kit
import wf_client_legality as legality


def official_sources():
    row = "wind_spgirl_4anv_1,false,action_skill,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,211,0,,,50000,100000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,"
    during = "blindness_gunner_1halfanv_3,false,attack_black,0,,1,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,134,0,,100000,100000,4,,6,,,,false,0,5,Black,,10000,20000,,,,,,,,,,,"
    return {"1412011": [row.split(",")], "1610633": [during.split(",")]}


class CeltieFeverAbilitiesTest(unittest.TestCase):
    def setUp(self):
        self.source = official_sources()
        self.rows = kit.ability_rows(self.source)

    def test_all_rows_pass_native_shape_fields_and_wind_element_validation(self):
        original = copy.deepcopy(self.source)
        kit.ability_rows(self.source)
        self.assertEqual(original, self.source)
        self.assertEqual({f"149989{i}" for i in range(1, 7)}, set(self.rows))
        for rows in self.rows.values():
            for row in rows:
                self.assertEqual(126, len(row))
                self.assertEqual([], legality.client_legality_problems("ability", row))
                self.assertEqual([], legality.declared_block_field_problems("ability", row))
                self.assertEqual([], legality.ability_element_column_problems("ability", row, 3))

    def test_first_and_third_abilities_are_main_restricted(self):
        # 2026-09-27 第三轮（c，口径 U6）：能力1 末尾加 I704 仅队长开关（前置42），c1 与键一致。
        for sid, rows in self.rows.items():
            self.assertEqual({"false" if sid.endswith(("1", "3")) else "true"},
                             {r[1] for r in rows})
        switch = [r for r in self.rows["1499891"] if r[47] == "704"]
        self.assertEqual([(r[1], r[6]) for r in switch], [("false", "42")])

    def test_opening_charge_and_learned_wind_resonance_flag_are_separate(self):
        charge, flag = self.rows["1499891"][:2]
        self.assertEqual(("0", "0", "211", "0", "50000", "50000"),
                         (charge[6], charge[27], charge[47], charge[48], charge[51], charge[52]))
        self.assertEqual(("2", "600000", "600000", "Green", "0", "536"),
                         (flag[6], flag[9], flag[10], flag[11], flag[27], flag[47]))
        self.assertEqual(kit.CHANGE_SKILL_STRING_ID, flag[70])

    def test_change_skill_flag_has_a_flat_text_entry_required_by_native_client(self):
        flag = self.rows["1499891"][1]
        strings = kit.flat_string_rows()
        self.assertEqual({flag[70], kit.ABILITY_STOCK_STRING_ID,
                          kit.ABILITY_SPEND_STRING_ID, kit.LEADER_UNCAP_STRING_ID}, set(strings))
        self.assertEqual(1, len(strings[flag[70]]))
        text = strings[flag[70]][0][0]
        for term in ("贯穿", "15秒", "风属性角色能力伤害提升100%", "风属性抗性降低25%"):
            self.assertIn(term, text)
        self.assertIn("命中敌人", text)
        self.assertNotIn("全场敌人", text)
        self.assertTrue(kit.metadata()["a1_enhancement"]["requires_skill_dsl_change_skill_flag_branch"])

    def test_a2_uses_native_three_split_hits_and_requires_six_wind_members(self):
        triple, damage = self.rows["1499892"][:2]
        for row in (triple, damage):
            self.assertEqual(("2", "600000", "600000", "Green", "5", "Green"),
                             (row[6], row[9], row[10], row[11], row[48], row[49]))
        self.assertEqual(("202", "0", "0"), (triple[47], triple[51], triple[52]))
        self.assertEqual(("388", "200000", "200000"),
                         (damage[47], damage[51], damage[52]))

    def test_a2_rewards_each_distinct_successful_consumer_with_five_percent(self):
        rows = self.rows["1499892"][2:]
        self.assertEqual(2, len(rows))
        self.assertEqual({"14998903", "14998904"}, {r[37] for r in rows})
        for row in rows:
            self.assertEqual(("true", "2", "Green", "12", "185", "0"),
                             (row[1], row[6], row[11], row[13], row[27], row[28]))
            self.assertEqual(("100000", "100000", "(None)", "0", "724", "5000", "5000"),
                             (row[30], row[31], row[34], row[35], row[47], row[51], row[52]))
            self.assertEqual("(None)", row[39], "Fever listener must not consume another layer")
        self.assertTrue(kit.metadata()["a2_consumed_stock_fever"]["requires_learned_a2"])

    def test_direct_attack_counter_gates_and_all_enemy_damage_are_exact(self):
        damage, gauge = self.rows["1499893"][:2]
        for row in (damage, gauge):
            self.assertEqual(("2", "Green", "600000", "20", "7", "Green", "3500000"),
                             (row[6], row[11], row[9], row[27], row[28], row[29], row[30]))
            self.assertEqual(("(None)", "0"), (row[34], row[35]))
        self.assertEqual(("12", "254", "0", "2500000", "(None)"),
                         (damage[13], damage[47], damage[48], damage[51], damage[69]))
        self.assertEqual(("186", "724", "15000", "", ""),
                         (gauge[13], gauge[47], gauge[51], gauge[48], gauge[69]))
        self.assertEqual(["kyubi-fever-ratio-v1"],
                         legality.required_client_capabilities("ability", gauge))

    def test_combo_attack_caps_independently_while_team_gauge_remains_unlimited(self):
        attack, charge = self.rows["1499893"][2:4]
        for row in (attack, charge):
            self.assertEqual(("2", "Green", "12", "12", "700000", "5", "Green"),
                             (row[6], row[11], row[13], row[27], row[30], row[48], row[49]))
            self.assertEqual("", row[57])  # Permanent native stat gain, no timed buff.
        self.assertEqual(("32", "70000", "10"), (attack[47], attack[51], attack[34]))
        self.assertEqual(700_000, int(attack[51]) * int(attack[34]))
        self.assertEqual(("211", "700", "(None)"), (charge[47], charge[51], charge[34]))
        self.assertEqual('42', charge[35])
        self.assertEqual('0', attack[35])

    def test_a3_stock_grant_and_consume_are_main_only_wind_fever_and_unlimited(self):
        grant, consume = self.rows["1499893"][4:6]
        for row in (grant, consume):
            self.assertEqual(("false", "2", "600000", "600000", "Green", "12"),
                             (row[1], row[6], row[9], row[10], row[11], row[13]))
            self.assertEqual(("100000", "100000", "(None)", "0"),
                             (row[30], row[31], row[34], row[35]))
        self.assertEqual(("23", "7", "Green", "629", kit.ABILITY_STOCK_STRING_ID,
                          kit.ABILITY_STOCK_ACTION_PATH),
                         (grant[27], grant[28], grant[29], grant[47], grant[70], grant[71]))
        self.assertEqual(("26", "", "", "629", "", ""),
                         (consume[27], consume[28], consume[29], consume[47], consume[51], consume[52]))
        self.assertEqual([kit.ABILITY_SPEND_STRING_ID, kit.ABILITY_SPEND_ACTION_PATH],
                         consume[70:72])
        self.assertEqual(("2", "0", "100000", "100000", "14998901"),
                         (consume[39], consume[40], consume[42], consume[43], consume[45]))
        text = kit.flat_string_rows()[grant[70]][0][0]
        self.assertIn("获得1次", text)
        self.assertIn("增加7连击", text)

    def test_a3_stock_and_leader_explicitly_allow_two_separate_consumers(self):
        info = kit.metadata()["a3_stock"]
        self.assertTrue(info["independent_of_leader_consumer"])
        self.assertEqual((1, 1, 7, 3, 2, 14), tuple(info[key] for key in (
            "per_wind_skill", "per_own_flip_cost", "per_own_flip_combo",
            "with_leader_per_wind_skill", "with_leader_max_cost_per_flip",
            "with_leader_max_combo_per_flip")))
        self.assertTrue(info["empty_stock_grants_no_combo"])

    def test_a3_bonus_counts_earned_layers_only_in_wind_fever_capped_at_ten(self):
        # 2026-09-27 第二批（口径 A3）覆盖：c102 (None)→10，能力伤害 25%→8%/层、攻击力 25%→5%/层；
        # 无上限的逐层成长搬进队长（test_celtie_fever_leader）。其余格保持第一批/原生成器输出。
        row = self.rows["1499893"][6]
        attack = self.rows["1499893"][7]
        expected_attack = copy.deepcopy(row)
        expected_attack[109] = "0"  # Native During AttackPointUp; same counter/target/gates.
        expected_attack[113:115] = ["5000", "5000"]
        self.assertEqual(expected_attack, attack)
        self.assertEqual(("false", "1", "2", "Green", "12"),
                         (row[1], row[5], row[6], row[11], row[13]))
        self.assertEqual(("134", "0", "100000", "100000", "10", "14998902"),
                         (row[97], row[98], row[100], row[101], row[102], row[104]))
        self.assertEqual(("154", "5", "Green", "8000", "8000"),
                         (row[109], row[110], row[111], row[113], row[114]))
        self.assertEqual(80_000, int(row[113]) * int(row[102]))       # 能力伤害最多 +80%
        self.assertEqual(50_000, int(attack[113]) * int(attack[102]))  # 攻击力最多 +50%
        self.assertEqual(("", "", "", ""), (row[27], row[47], row[57], row[58]))
        # Consumption addresses spendable stock; no instant ability can clear
        # or consume the separate lifetime-earned counter.
        consume = self.rows["1499893"][5]
        self.assertEqual("14998901", consume[45])
        self.assertNotEqual(consume[45], row[104])
        self.assertFalse(any(r[47] == "528" for rows in self.rows.values() for r in rows))
        info = kit.metadata()["stock_gain_bonus"]
        self.assertEqual((8, 5), (info["per_layer_percent"], info["attack_per_layer_percent"]))
        self.assertEqual(14998902, info["gain_unique_id"])
        for key in ("only_fever", "retain_after_fever", "stock_consume_preserves_bonus",
                    "bonus_uses_cumulative_gained_layers"):
            self.assertTrue(info[key])
        self.assertEqual(10, info["during_trigger_limit"])

    def test_uncapped_gain_row_shape_is_still_available_for_the_leader(self):
        capped = kit._stock_gain_bonus(self.source)
        uncapped = kit._stock_gain_bonus(self.source, 154, 2_500, limit=None)
        self.assertEqual(("(None)", "2500", "2500"), (uncapped[102], uncapped[113], uncapped[114]))
        uncapped[102], uncapped[113:115] = capped[102], capped[113:115]
        self.assertEqual(capped, uncapped, "only limit and strength may differ")

    def test_periodic_party_states_use_300_fever_frames_and_60_frame_duration(self):
        for slot, content in ((4, "26"), (5, "27"), (6, "688")):
            row = self.rows[f"149989{slot}"][0]
            self.assertEqual(("2", "Green", "12", "248", "30000000", content),
                             (row[6], row[11], row[13], row[27], row[30], row[47]))
            self.assertEqual(("6000000", "6000000", "100000", "100000"), tuple(row[57:61]))
            self.assertEqual(("", "", "(None)", "0", "false"),
                             (row[48], row[49], row[34], row[35], row[72]))
        speed = self.rows["1499896"][0]
        self.assertEqual(("200000", "200000", "", "", "(None)"),
                         (speed[51], speed[52], speed[53], speed[54], speed[61]))
        self.assertEqual(2.0, kit.metadata()["periodic_status"]["fixed_speed_strength"])
        self.assertEqual(0, kit.metadata()["periodic_status"]["fixed_speed_skill_charging_strength"])

    def test_metadata_declares_native_counter_carry_and_per_battle_attack(self):
        info = kit.metadata()
        self.assertIn("fractional period carries", info["direct_attack"]["fever_counters"])
        self.assertIn("fractional period carries", info["periodic_status"]["timer"])
        self.assertTrue(info["combo"]["attack_persists_after_fever"])
        self.assertIsNone(info["combo"]["skill_gauge_trigger_limit"])
        self.assertEqual(["kyubi-fever-ratio-v1"], info["required_client_capabilities"])

    def test_wrong_native_shape_is_rejected_without_mutating_source(self):
        bad = {"1412011": [["0"] * 125]}
        original = copy.deepcopy(bad)
        with self.assertRaisesRegex(ValueError, "126"):
            kit.ability_rows(bad)
        self.assertEqual(original, bad)


if __name__ == "__main__":
    unittest.main()
