import unittest

import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_summer_thunder_ability_compile import (
    CHARACTER_ID,
    CODE_NAME,
    UNIQUE_CONDITION_ID,
    build_summer_thunder_ability_rows,
    patch_summer_thunder_ability_tables,
)


ABILITY_IDS = tuple(f"139998{slot}" for slot in range(1, 7))


class SummerThunderAbilityCompileTests(unittest.TestCase):
    def test_builds_exact_locked_row_counts_widths_and_identity(self):
        built = build_summer_thunder_ability_rows()
        self.assertEqual(139998, CHARACTER_ID)
        self.assertEqual("cnmod_thunder_dragon_ascendant", CODE_NAME)
        self.assertEqual(139998, UNIQUE_CONDITION_ID)
        self.assertEqual({"leader_ability", "ability", "unique_condition"}, set(built))

        leaders = built["leader_ability"]
        abilities = built["ability"]
        unique = built["unique_condition"]
        self.assertEqual({"139998"}, set(leaders))
        self.assertEqual(5, len(leaders["139998"]))
        self.assertTrue(all(len(row) == 124 for row in leaders["139998"]))
        self.assertEqual(set(ABILITY_IDS), set(abilities))
        self.assertEqual([4, 2, 3, 1, 2, 1], [len(abilities[key]) for key in ABILITY_IDS])
        self.assertTrue(
            all(len(row) == 126 for rows in abilities.values() for row in rows)
        )
        self.assertEqual({"139998"}, set(unique))
        self.assertEqual(15, len(unique["139998"]))
        self.assertEqual(built, build_summer_thunder_ability_rows())

    def test_every_leader_and_ability_row_is_client_legal(self):
        built = build_summer_thunder_ability_rows()
        for key, rows in built["leader_ability"].items():
            for index, row in enumerate(rows):
                self.assertEqual(
                    [],
                    client_legality_problems("leader_ability", row),
                    f"leader {key} row {index}",
                )
        for key, rows in built["ability"].items():
            for index, row in enumerate(rows):
                self.assertEqual(
                    [],
                    client_legality_problems("ability", row),
                    f"ability {key} row {index}",
                )

        amplify = built["leader_ability"]["139998"][2]
        self.assertEqual("(None)", amplify[73])

    def test_leader_rows_match_locked_effects_without_custom_power_flip(self):
        rows = build_summer_thunder_ability_rows()["leader_ability"]["139998"]
        attack, ability_damage, amplify, power_flip, paralysis = rows
        self.assertEqual(("32", "5", "Yellow", "250000", "250000"),
                         (attack[45], attack[46], attack[47], attack[49], attack[50]))
        self.assertEqual(("388", "5", "Yellow", "600000", "600000"),
                         (ability_damage[45], ability_damage[46], ability_damage[47],
                          ability_damage[49], ability_damage[50]))

        for row in (amplify, power_flip):
            self.assertEqual(("2", "600000", "600000", "Yellow"),
                             (row[4], row[7], row[8], row[9]))
        self.assertEqual(("23", "0", "100000", "100000", "(None)", "0"),
                         (amplify[25], amplify[26], amplify[28], amplify[29],
                          amplify[32], amplify[33]))
        self.assertEqual(("461", "0", "100000", "100000", "100000", "100000",
                          "139998", "1"),
                         (amplify[45], amplify[46], amplify[49], amplify[50],
                          amplify[57], amplify[58], amplify[66], amplify[72]))
        self.assertEqual(("183", "100000", "100000", "(None)", "0"),
                         (power_flip[25], power_flip[28], power_flip[29],
                          power_flip[32], power_flip[33]))
        self.assertEqual(("253", "0", "500000", "500000", "(None)"),
                         (power_flip[45], power_flip[46], power_flip[49],
                          power_flip[50], power_flip[67]))

        self.assertEqual(("188", "0", "100000", "100000", "139998"),
                         (paralysis[4], paralysis[5], paralysis[7],
                          paralysis[8], paralysis[10]))
        self.assertEqual(("144", "0", "100000", "100000", "(None)", "0"),
                         (paralysis[25], paralysis[26], paralysis[28],
                          paralysis[29], paralysis[32], paralysis[33]))
        self.assertEqual(("455", "0", "18000000", "18000000", "0", "false"),
                         (paralysis[45], paralysis[46], paralysis[55],
                          paralysis[56], paralysis[65], paralysis[70]))

        for row in rows:
            self.assertEqual("cnmod_thunder_dragon_ascendant", row[0])
            self.assertEqual("0", row[1])
            self.assertEqual("0", row[3])
            self.assertTrue(all(row[index] == "" for index in (80, 81, 82, 118, 119, 120)))
            self.assertTrue(all(row[index] == "" for index in (68, 69)))

    def test_abilities_preserve_scope_cooldowns_and_unison_amplification(self):
        abilities = build_summer_thunder_ability_rows()["ability"]
        a1 = abilities["1399981"]
        self.assertEqual(["true"] * 4, [row[1] for row in a1])
        self.assertEqual(["attack_common"] * 4, [row[2] for row in a1])
        self.assertEqual(("32", "5", "(None)", "200000", "200000"),
                         (a1[0][47], a1[0][48], a1[0][49], a1[0][51], a1[0][52]))
        self.assertEqual(("388", "5", "(None)", "400000", "400000"),
                         (a1[1][47], a1[1][48], a1[1][49], a1[1][51], a1[1][52]))
        self.assertEqual(["410", "412"], [row[109] for row in a1[2:]])
        for row in a1[2:]:
            self.assertEqual("1", row[5])
            self.assertEqual(("194", "0", "100000", "100000", "1", "139998"),
                             (row[97], row[98], row[100], row[101], row[102], row[104]))
            self.assertEqual(("0", "30000", "30000"),
                             (row[110], row[113], row[114]))

        dash, max_gauge = abilities["1399982"]
        self.assertEqual(("2", "600000", "600000", "Yellow"),
                         (dash[6], dash[9], dash[10], dash[11]))
        self.assertEqual(("4", "100000", "100000", "(None)", "60"),
                         (dash[27], dash[30], dash[31], dash[34], dash[35]))
        self.assertEqual(("354", "0", "500000", "500000", "(None)"),
                         (dash[47], dash[48], dash[51], dash[52], dash[69]))
        self.assertEqual("0", max_gauge[6])
        self.assertTrue(all(max_gauge[index] == "" for index in range(7, 13)))
        self.assertEqual(("245", "5", "Yellow", "10000", "10000"),
                         (max_gauge[47], max_gauge[48], max_gauge[49],
                          max_gauge[51], max_gauge[52]))

        self_gauge, allies_gauge, all_enemy = abilities["1399983"]
        for row in (self_gauge, allies_gauge):
            self.assertEqual(("188", "0", "100000", "100000", "139998"),
                             (row[6], row[7], row[9], row[10], row[12]))
        self.assertEqual(("23", "5", "Yellow", "211", "0", "25000", "25000"),
                         (self_gauge[27], self_gauge[28], self_gauge[29],
                          self_gauge[47], self_gauge[48], self_gauge[51], self_gauge[52]))
        self.assertEqual(("23", "0", "211", "1", "(None)", "25000", "25000"),
                         (allies_gauge[27], allies_gauge[28], allies_gauge[47],
                          allies_gauge[48], allies_gauge[49], allies_gauge[51],
                          allies_gauge[52]))
        self.assertEqual("0", all_enemy[6])
        self.assertTrue(all(all_enemy[index] == "" for index in range(7, 13)))
        self.assertEqual(("23", "5", "Yellow", "253", "0", "2500000",
                          "2500000", "(None)"),
                         (all_enemy[27], all_enemy[28], all_enemy[29], all_enemy[47],
                          all_enemy[48], all_enemy[51], all_enemy[52], all_enemy[69]))

        self.assertEqual(("211", "0", "100000", "100000"),
                          tuple(abilities["1399984"][0][index] for index in (47, 48, 51, 52)))
        attack, ability_damage = abilities["1399985"]
        self.assertEqual(("32", "5", "Yellow", "90000", "90000"),
                         tuple(attack[index] for index in (47, 48, 49, 51, 52)))
        self.assertEqual(("388", "5", "Yellow", "90000", "90000"),
                         tuple(ability_damage[index] for index in (47, 48, 49, 51, 52)))
        self.assertEqual(("35", "0", "15000", "15000"),
                         tuple(abilities["1399986"][0][index] for index in (47, 48, 51, 52)))

        cooldowns = [
            row[35]
            for rows in abilities.values()
            for row in rows
            if row[35] not in ("", "0")
        ]
        self.assertEqual(["60"], cooldowns)
        for rows in abilities.values():
            for row in rows:
                self.assertTrue(all(row[index] == "" for index in (82, 83, 84, 120, 121, 122)))
                self.assertTrue(all(row[index] == "" for index in (70, 71)))

    def test_unique_condition_is_single_stack_600_frame_with_icon_reference(self):
        unique = build_summer_thunder_ability_rows()["unique_condition"]["139998"]
        self.assertEqual(
            [
                "unique_cnmod_thunder_dragon_ascendant_amp",
                "雷电增幅",
                "battle/common/unique_condition/unique_cnmod_thunder_dragon_ascendant_amp",
                "600",
                "1",
                "(None)", "(None)", "(None)", "(None)",
                "false", "false", "0", "0", "true", "(None)",
            ],
            unique,
        )

    def test_flat_table_patch_is_additive_and_refuses_identity_collisions(self):
        original = {
            "ability": {"legacy": "legacy ability"},
            "leader_ability": {"legacy": "legacy leader"},
            "unique_condition": {"7": "legacy unique"},
        }
        patched = patch_summer_thunder_ability_tables(original)
        self.assertEqual(original["ability"]["legacy"], patched["ability"]["legacy"])
        self.assertEqual(original["leader_ability"]["legacy"],
                         patched["leader_ability"]["legacy"])
        self.assertEqual(original["unique_condition"]["7"],
                         patched["unique_condition"]["7"])
        self.assertEqual(set(ABILITY_IDS), set(patched["ability"]) - {"legacy"})
        self.assertEqual({"139998"}, set(patched["leader_ability"]) - {"legacy"})
        self.assertEqual({"139998"}, set(patched["unique_condition"]) - {"7"})
        for key in ABILITY_IDS:
            decoded = core.read_csv_lines(patched["ability"][key])
            self.assertEqual(build_summer_thunder_ability_rows()["ability"][key], decoded)
        self.assertEqual(
            build_summer_thunder_ability_rows()["leader_ability"]["139998"],
            core.read_csv_lines(patched["leader_ability"]["139998"]),
        )
        self.assertEqual(
            [build_summer_thunder_ability_rows()["unique_condition"]["139998"]],
            core.read_csv_lines(patched["unique_condition"]["139998"]),
        )

        collision = {
            "ability": {"1399981": "occupied"},
            "leader_ability": {},
            "unique_condition": {},
        }
        with self.assertRaisesRegex(ValueError, "identity collision"):
            patch_summer_thunder_ability_tables(collision)


if __name__ == "__main__":
    unittest.main()
