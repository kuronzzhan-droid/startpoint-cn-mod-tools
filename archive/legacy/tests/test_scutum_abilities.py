"""盾牌座原生字段、门槛、数值及装配引用回归。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as legality
import wf_scutum_abilities as kit
import wf_scutum_abilities_rows as rows


def official_source():
    # Original Stella151147 A3 During and AdditionalUnisonAttack rows.
    during = "stella_ballot23_3,false,attack_white,0,,1,2,,,600000,600000,White,,0,,,,,,,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,4,,,,,,,,,,,false,0,5,White,,75000,150000,,,,,,,,,,,"
    instant = "stella_ballot23_3,false,attack_white,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,717,0,,,50000,100000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,"
    return {"1511473": [during.split(","), instant.split(",")]}


class ScutumAbilitiesTest(unittest.TestCase):
    def setUp(self):
        self.source = official_source()
        self.abilities = kit.ability_rows(self.source)
        self.leader = kit.leader_rows(self.source)

    def test_native_parsers_and_official_source_preserved(self):
        before = deepcopy(self.source)
        kit.ability_rows(self.source)
        self.assertEqual(before, self.source)
        for kind, collection, width in (
                ("ability", sum(self.abilities.values(), []), 126),
                ("leader_ability", self.leader, 124)):
            for row in collection:
                self.assertEqual(width, len(row))
                self.assertEqual([], legality.client_legality_problems(kind, row))
                self.assertEqual([], legality.declared_block_field_problems(kind, row))
                self.assertEqual([], legality.ability_element_column_problems(kind, row, 3))

    def test_a1_and_a3_are_main_only(self):
        for key, group in self.abilities.items():
            self.assertEqual({"false" if key in ("1499881", "1499883") else "true"}, {r[1] for r in group})

    def test_leader_floating_piercing_and_damage_counter_are_independent(self):
        floating, combo, dash, attack, direct, separate = self.leader
        self.assertEqual(("31", "1", "5", "Green", "400000"),
                         (floating[95], floating[107], floating[108], floating[109], floating[111]))
        self.assertEqual(("0", "200", "900000"), (combo[25], combo[45], combo[49]))
        self.assertEqual(["2", "", "", "600000", "600000", "Green", ""], dash[4:11])
        self.assertEqual(("21", "7", "(None)", "1000000", "300", "629"),
                         (dash[25], dash[26], dash[27], dash[28], dash[33], dash[45]))
        for row, content, strength in ((attack, "0", "150000"), (direct, "1", "150000"),
                                       (separate, "410", "20000")):
            self.assertEqual(("0", "30", content, strength),
                             (row[4], row[95], row[107], row[111]))

    def test_floating_growth_has_four_native_applications_and_retains_a4(self):
        growth = self.abilities["1499881"][:2] + self.abilities["1499884"][1:]
        self.assertEqual(["33", "32", "32"], [r[47] for r in growth])
        for row in growth:
            self.assertEqual(("236", "100000", "30000000", "4", "50000", "5", "Green"),
                             (row[27], row[30], row[32], row[34], row[51], row[48], row[49]))
            self.assertEqual(200, int(row[34]) * int(row[51]) / 1000)

    def test_a1_initial_gauge_and_floating_charge_speed(self):
        speed, party, self_charge = self.abilities["1499881"][2:]
        self.assertEqual(("31", "3", "15000"), (speed[97], speed[109], speed[113]))
        self.assertEqual(("2", "Green", "0", "211", "5", "50000"),
                         (party[6], party[11], party[27], party[47], party[48], party[51]))
        self.assertEqual(("2", "0", "211", "0", "100000"),
                         (self_charge[6], self_charge[27], self_charge[47], self_charge[48], self_charge[51]))
        for row in self.abilities["1499881"]:
            self.assertEqual(["2", "", "", "600000", "600000", "Green", ""], row[6:13])
        self.assertEqual("0", self.abilities["1499884"][1][6])

    def test_barrier_covers_party_and_multiballs_and_a2_growth_uses_self_hits(self):
        barrier = self.abilities["1499882"][:2]
        self.assertEqual(["5", "8"], [r[48] for r in barrier])
        for row in barrier:
            self.assertEqual(("3", "Green", "65", "227", "10000"),
                             (row[6], row[11], row[27], row[47], row[51]))
        slayers = self.abilities["1499882"][2:4]
        for row, content in zip(slayers, ("139", "506")):
            self.assertEqual(("20", "0", "3000000", "7", content, "55000"),
                             (row[27], row[28], row[30], row[34], row[47], row[51]))
            self.assertEqual(385, int(row[34]) * int(row[51]) / 1000)
        charge = self.abilities["1499882"][-1]
        self.assertEqual(("51", "211", "5", "Green", "2500", "2500"),
                         (charge[27], charge[47], charge[48], charge[49], charge[51], charge[52]))

    def test_collect_is_friendly_and_shield_and_collect_gate_self_independent_term(self):
        grants = self.abilities["1499883"][:2]
        self.assertEqual(["5", "8"], [r[48] for r in grants])
        for row in grants:
            self.assertEqual(("2", "Green"), (row[6], row[11]))
            self.assertEqual(("65", "300", "461", "14998801"),
                             (row[27], row[35], row[47], row[68]))
        shield = self.abilities["1499883"][2]
        self.assertEqual(["187", "0", "", "", "", "", "14998801"], shield[6:13])
        self.assertEqual(("72", "0", "410", "0", "20000"),
                         (shield[97], shield[98], shield[109], shield[110], shield[113]))
        unique = kit.unique_rows()["14998801"][0]
        self.assertEqual(["300", "1"], unique[3:5])
        self.assertEqual(["false", "true", "0", "0", "true"], unique[9:14])

    def test_a3_wind_debuff_uses_trigger_enemy_and_stella_unison_base_attack(self):
        debuff, unison = self.abilities["1499883"][-2:]
        self.assertEqual(("38", "20", "0", "442", "-2000", "150000000", "20"),
                         (debuff[6], debuff[27], debuff[28], debuff[47], debuff[51], debuff[57], debuff[61]))
        self.assertEqual(("0", "0", "717", "0", "100000"),
                         (unison[6], unison[27], unison[47], unison[48], unison[51]))
        # I717 adds source.unisonAtk to the normal 25% contribution.
        main_atk, sub_atk = 101, 204
        self.assertEqual(356, main_atk + int(.25 * sub_atk) + int(int(unison[51]) / 100000 * sub_atk))

    def test_collect_followup_is_one_expiring_owner_window_for_both_hit_sources(self):
        followups = [r for r in self.abilities["1499883"] if r[47] == "629"]
        self.assertEqual(1, len(followups))
        for row in followups:
            self.assertEqual(["187", "0", "", "", "", "", "14998801"], row[6:13])
            self.assertEqual(("false", "185", "0", "100000", "(None)", "300", "14998802"),
                             (row[1], row[27], row[28], row[30], row[34], row[35], row[37]))
            self.assertEqual((rows.COLLECT_CHASE_STRING,
                              rows.HELPER_PREFIX + rows.COLLECT_CHASE_STRING),
                             (row[70], row[71]))
        markers = [r for r in self.abilities["1499883"]
                   if r[47] == "461" and r[68] == "14998802"]
        self.assertEqual(["0", "9"], [r[28] for r in markers])
        for row in markers:
            self.assertEqual(("187", "14998801", "20", "0", "0"),
                             (row[6], row[12], row[27], row[35], row[48]))
        clear = next(r for r in self.abilities["1499883"] if r[47] == "528")
        self.assertEqual(("0", "185", "0", "14998802", "0", "14998802"),
                         (clear[6], clear[27], clear[28], clear[37], clear[48], clear[68]))
        self.assertEqual(["1", "1"], kit.unique_rows()["14998802"][0][3:5])
        self.assertEqual("true", kit.unique_rows()["14998802"][0][9])
        self.assertEqual("false", kit.unique_rows()["14998801"][0][9])
        self.assertTrue(all(r[39] == "(None)" for r in followups))
        meta = kit.metadata()["collect_followup"]
        self.assertEqual(5, meta["attack_multiplier"])
        self.assertTrue(meta["includes_new_multiballs_during_window"])
        self.assertFalse(meta["individual_trigger_holder_required"])

    def test_a4_a5_timers_and_a6_upgrade_keep_independent_conditions(self):
        swift = self.abilities["1499884"][0]
        self.assertEqual(("3", "Green", "51", "31", "18000000"),
                         (swift[6], swift[11], swift[27], swift[47], swift[57]))
        periodic, chase = self.abilities["1499885"]
        self.assertEqual(("3", "77", "30000000", "26", "18000000"),
                         (periodic[6], periodic[27], periodic[30], periodic[47], periodic[57]))
        self.assertEqual(("38", "23", "7", "Green", "629"),
                         (chase[6], chase[27], chase[28], chase[29], chase[47]))
        flag = self.abilities["1499886"][0]
        self.assertEqual(("2", "0", "536", rows.CHANGE_STRING),
                         (flag[6], flag[27], flag[47], flag[70]))
        self.assertEqual("Green", flag[11])

    def test_native_shared_handler_cooldown_model_handles_same_frame_balls_and_windows(self):
        # Mirrors AbilityTriggerHandler: precondition -> synchronous cooltime
        # assignment -> apply; ConditionSlot may suppress duplicate same-frame
        # grants, but correctness must also hold if different gids notify twice.
        def simulate(events, main=True):
            next_ready, result = 0, []
            for frame, puller, collect in events:
                if main and collect and puller in (0, 9) and frame >= next_ready:
                    next_ready = frame + 300
                    result.append(frame)
            return result
        events = [(0, 7, True), (0, 0, True), (0, 9, True), (1, 9, True),
                  (299, 0, True), (300, 9, False), (301, 9, True),
                  (301, 9, True), (600, 0, True), (601, 0, True)]
        self.assertEqual([0, 301, 601], simulate(events))
        self.assertEqual([], simulate(events, main=False))

    def test_panel_merges_chase_and_retains_native_main_icon(self):
        flat = kit.flat_string_rows()
        a3 = flat["desc_override_scutum_valentine_3"][0][0]
        self.assertEqual(1, a3.count("共用CT：5秒"))
        self.assertTrue(all("<icon id='main'>" in line for line in a3.splitlines()))
        self.assertNotIn("14998802", a3)
        for slot in (1, 6):
            self.assertIn("风属性共鸣", flat[f"desc_override_scutum_valentine_{slot}"][0][0])

    def test_real_install_output_has_all_flat_dependencies_and_no_publish_side_effect(self):
        class Capture:
            def __init__(self, source):
                self.source, self.outputs = source, {}
            def rows(self, logical):
                assert logical == kit.ABILITY_TABLE
                return self.source
            def table(self, logical, replacements):
                self.outputs[logical] = deepcopy(replacements)
        capture = Capture(self.source)
        result = kit.install(capture)
        self.assertEqual({kit.ABILITY_TABLE, kit.LEADER_TABLE, kit.UNIQUE_TABLE, kit.STRING_TABLE},
                         set(capture.outputs))
        flat = capture.outputs[kit.STRING_TABLE]
        all_rows = [(r, 47) for group in capture.outputs[kit.ABILITY_TABLE].values() for r in group]
        all_rows += [(r, 45) for r in capture.outputs[kit.LEADER_TABLE][kit.CID]]
        for row, content in all_rows:
            if row[content] in ("536", "629"):
                self.assertTrue(flat[row[content + 23]][0][0].strip())
        self.assertFalse(result["requires_collect_hit_resolution"])


if __name__ == "__main__":
    unittest.main()
