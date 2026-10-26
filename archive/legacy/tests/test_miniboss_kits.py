"""十五套能力的数值边界、原生目标、有限累计与主位显示。"""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as legality
from wf_miniboss_budget import audit, row_peak
from wf_miniboss_kits import build, PF_CHARACTERS
from wf_miniboss_roster import ROSTER
from wf_miniboss_rows import Kit, make
from wf_miniboss_text import ACTIVE, MAIN, panel_rows

EXPECTED = {"129998": 295, "139996": 285, "129996": 285, "149994": 300,
            "159999": 300, "129995": 295, "149993": 285, "119995": 295,
            "149992": 300, "129994": 285, "119993": 300, "129993": 290,
            "169993": 300, "149991": 295, "119994": 295}


def source_pf(char):
    if char.cid not in PF_CHARACTERS:
        return []
    row = make(722, extra={"powerflip_override.id": char.code,
                          "powerflip_override.levels": "1,2,3",
                          "powerflip_override.description_id": char.code + "_pf"})
    return [[char.code, "0", "", *row[5:]]]


class MinibossKitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kits = {c.cid: build(c.cid, source_leader=source_pf(c)) for c in ROSTER}

    def test_exact_roster_excludes_steam_robot_and_campus_characters(self):
        self.assertEqual(set(EXPECTED), {c.cid for c in ROSTER})
        self.assertNotIn("129970", self.kits)
        self.assertEqual(len({c.code for c in ROSTER}), 15)

    def test_native_rows_and_targets_are_legal(self):
        for c in ROSTER:
            abilities, leaders, _ = self.kits[c.cid]
            self.assertEqual(set(abilities), {c.cid + str(n) for n in range(1, 7)})
            for key, rows in abilities.items():
                self.assertLessEqual(len(rows), 9)
                for row in rows:
                    self.assertEqual(legality.client_legality_problems("ability", row), [])
                    self.assertEqual(row[1], "false" if key.endswith("3") else "true")
                    if row[5] == "0" and row[48] == "5":
                        self.assertEqual(row[49], c.group)
                    if row[5] == "1" and row[110] == "5":
                        self.assertEqual(row[111], c.group)
            for row in leaders[c.cid]:
                self.assertEqual(legality.client_legality_problems("leader_ability", row), [])
                self.assertNotEqual(row[45], "724")

    def test_all_six_ability_peaks_and_single_fifteen_percent_term(self):
        for cid, (_, _, meta) in self.kits.items():
            self.assertEqual(meta["total_peak_percent"], EXPECTED[cid])
            self.assertEqual(len(meta["independent_terms"]), 1)
            self.assertEqual(meta["independent_terms"][0]["peak_percent"], 15)

    def test_unbounded_growth_is_rejected_even_if_panel_claims_cap(self):
        rows = deepcopy(self.kits["119995"][0]["1199953"])
        rows[0][102] = "(None)"
        with self.assertRaisesRegex(ValueError, "finite native cap"):
            audit({2: rows})

    def test_during_layer_and_timed_stack_caps_are_counted(self):
        bear = self.kits["149991"][0]
        clione = self.kits["129996"][0]
        self.assertEqual(float(row_peak(clione["1299962"][1])[0]), 60)
        self.assertEqual(float(row_peak(bear["1499913"][0])[0]), 140)
        self.assertEqual(float(row_peak(bear["1499913"][1])[0]), 140)
        invalid = deepcopy(bear["1499913"])
        invalid[0][102] = "(None)"
        with self.assertRaises(ValueError):
            audit({3: invalid})

    def test_enemy_resistance_reduction_is_included(self):
        _, _, meta = self.kits["119993"]
        self.assertEqual(meta["slot_peak_percent"]["4"], 5)
        self.assertEqual(meta["total_peak_percent"], 300)

    def test_budget_rejects_second_independent_term_and_excess_strength(self):
        term = deepcopy(self.kits["129998"][0]["1299983"][-1])
        with self.assertRaisesRegex(ValueError, "only one independent"):
            audit({3: [term, term]})
        term[51:53] = ["16000", "16000"]
        with self.assertRaisesRegex(ValueError, "only one independent"):
            audit({3: [term]})

    def test_threshold_growth_and_refill_have_distinct_finite_caps(self):
        dog = self.kits["119995"][0]
        growth, refill = dog["1199953"][0], dog["1199955"][0]
        self.assertEqual(growth[97], "134")
        self.assertEqual(growth[102], "5")
        self.assertEqual(float(row_peak(growth)[0]), 200)
        self.assertEqual(refill[27], "12")
        self.assertEqual(refill[30:32], ["3000000", "3000000"])
        self.assertEqual(refill[34], "(None)")

    def test_genin_poison_and_chase_are_main_only_without_bad_resistance(self):
        rows = self.kits["169993"][0]
        chases = rows["1699933"]
        self.assertEqual([row[47] for row in chases], ["629", "629", "525"])
        self.assertEqual(chases[0][9:11], ["300000", "300000"])
        self.assertEqual(chases[0][35], "120")
        self.assertEqual(chases[1][9:11], ["500000", "500000"])
        self.assertEqual(chases[2][51:53], ["500000", "500000"])
        self.assertTrue(all(row[1] == "false" for row in chases))

    def test_native_pf_override_preserved_and_missing_baseline_rejected(self):
        for c in ROSTER:
            if c.cid in PF_CHARACTERS:
                self.assertEqual(self.kits[c.cid][1][c.cid][-1], source_pf(c)[0])
                with self.assertRaises(ValueError):
                    build(c.cid)

    def test_every_panel_has_main_icon_and_no_enum_or_unknown_id(self):
        for c in ROSTER:
            abilities, leaders, _ = self.kits[c.cid]
            texts = panel_rows(c.cid, abilities, leaders[c.cid], "队长测试说明")
            self.assertEqual(len(texts), 7)
            for key, rows in texts.items():
                value = rows[0][0]
                self.assertEqual(MAIN in value, key.endswith("_3"))
                self.assertNotIn("C10010", value)
                self.assertNotIn(str(c.uid), value)
            self.assertTrue(ACTIVE[c.cid])


if __name__ == "__main__":
    unittest.main()
