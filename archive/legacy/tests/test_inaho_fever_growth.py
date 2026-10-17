"""Scoped native growth: original behavior, state safety, and input guards."""
import sys
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core
import wf_inaho_fever_growth_data as data
import wf_inaho_fever_growth as tool
import wf_inaho_growth_detail_data as detail_fix
from wf_client_legality import client_legality_problems
from wf_inaho_fever_drain import make_row

# Three small, immutable own-key rows from the authorized 1.4.776 baseline.
FIXTURE = {
    "1399951": "789cc5d1310a02311005d0de9328fc62269a780b7bab10966c63dcc092a0de5e665603ca5a2c0afe6226f053e4913e5f7d1e4397a20fb5d4f3e01965ac11a194d09dfc2da6942f2080600038923cd7716aa5d6bc6fcdfa9087b8698d61d67ebbb74490f172fbabacfa059c4f8fde01e0c9f758cd40731ee3e4600442d0f92710cb07cd899c5d4862866d9f2b3275fd4c7507ad2a8f0e",
    "1399956": "789ca590bd0a023110847b9fe48429f2733f6f616f15826caadc057217f5f125b759501b51bf660676129809e9ee52f69748ce97adcc8b1bb1e5420874a50c05281800a3aa889c29c674ab3746d4584c72d41c6d0274a7b4d091a3cdcb63a36d357a1a386c59e5d7ff39848f35f517357fe7a5f84effe4838f2ba16f6bd41160df7678008cbf6150",
    "139995": "789cd554410e823010bcfb0c4e9aac49bbb0013fe1dd5343a418924a0d82fa7c534aa322128924e01e3a7bd8c9ceb493a6fa267411ef9514715556c71c180033475d6d44dfb49c997200b0dcea5caeec50d33b1a720e043ba994be022031066449e3d4221d6c20747206d9f04d135243b1389d8d97cd2dad64698d2d9c5668043fc485d77931c7bc0cf06eed01fdad7622834d5682f945a65bb58fcf173edbbc7f101f45b353dff7ad84885f6cd41759145922c5db669154b112a7143c0e08bef7183d9745961f7a1853d845fb0ceb8d7d118763d51d9c989d1d",
}


class GrowthTest(unittest.TestCase):
    def setUp(self):
        self.old = {k: zlib.decompress(bytes.fromhex(v)).decode() for k, v in FIXTURE.items()}
        self.new = data.transform(self.old)
        self.rows = {k: core.read_csv_lines(v) for k, v in self.new.items()}

    def test_exact_baseline_idempotence_and_unknown_rejection(self):
        self.assertEqual({k: data.sha(v) for k, v in self.old.items()}, data.OLD)
        self.assertEqual(data.transform(self.new), self.new)
        for bad in (dict(self.old, **{"1399951": self.old["1399951"] + "\n"}),
                    dict(self.old, **{"1399951": self.new["1399951"]})):
            with self.assertRaisesRegex(ValueError, "unknown or partially"):
                data.transform(bad)

    def test_original_abilities_and_fixed_drain_stay_exact(self):
        old = {k: core.read_csv_lines(v) for k, v in self.old.items()}
        self.assertEqual(self.rows["1399951"][:3], old["1399951"])
        self.assertEqual(self.rows["1399956"][1], old["1399956"][1])
        for index in set(range(10)) - {1}:
            self.assertEqual(self.rows["139995"][index], old["139995"][index])
        self.assertEqual(self.rows["1399951"][-1], make_row())
        self.assertEqual([len(self.rows[k]) for k in data.OLD], [7, 3, 11])

    def test_fallback_is_exclusive_and_preserves_old_conditions(self):
        for key, index, offset in (("1399956", 0, 0), ("139995", 1, -2)):
            old = core.read_csv_lines(self.old[key])[index]
            growth, fallback = self.rows[key][index], self.rows[key][-1]
            start = 13 + offset
            self.assertEqual(growth[start:start + 7], ["187", "0", "", "", "", "", data.UNIQUE_ID])
            self.assertEqual(fallback[start:start + 7], ["199", "0", "", "0", "0", "", data.UNIQUE_ID])
            restored = fallback.copy()
            restored[start:start + 7] = old[start:start + 7]
            self.assertEqual(restored, old)
            self.assertEqual(growth[6 + offset:13 + offset], old[6 + offset:13 + offset])

    def test_native_counter_seed_growth_and_unison_contract(self):
        seed, growth, gain = self.rows["1399951"][3:6]
        for row in (seed, growth, gain):
            self.assertEqual(row[1], "true")
            self.assertEqual(row[46], "0")
        self.assertEqual((seed[27], seed[47], seed[59:61], seed[74]),
                         ("0", "461", ["100000"] * 2, "4200"))
        self.assertEqual((growth[27], growth[47], growth[42], growth[74]),
                         ("184", "461", "400000", "1"))
        self.assertEqual((gain[6], gain[27], gain[47]), ("186", "65", "213"))
        for row in (growth, gain):
            self.assertEqual((row[34], row[35], row[39], row[40]), ("(None)", "0", "3", "0"))
            self.assertEqual(row[45], data.UNIQUE_ID)
        self.assertEqual(data.state_row()[4], str(data.CAP))
        self.assertEqual(data.state_row()[9:14], ["false", "true", "0", "0", "false"])

    def test_all_reachable_levels_keep_original_initial_points(self):
        first = data.simulate(0)[0]["alv_1_to_6"]
        self.assertEqual(first["ability6"]["actual"], [175, 210, 245, 280, 315, 350])
        self.assertEqual(first["pf3"]["actual"], [100, 120, 140, 160, 180, 200])
        self.assertEqual(first["leader"]["actual"][::5], [75, 150])

    def test_growth_recurrence_rounding_cap_and_integer_safety(self):
        phases = data.simulate()
        for previous, current in zip(phases, phases[1:]):
            self.assertEqual(current["stacks"], min(data.CAP, previous["stacks"] * 5 // 4))
        self.assertEqual(phases[1]["alv_1_to_6"]["leader"]["actual"][-1], 180)
        self.assertTrue(phases[-1]["capped"])
        self.assertLess(data.CAP * 5 // 4, 2**31)
        self.assertLess(10 * (data.CAP // 120), 2**31)
        for phase in phases:
            if not phase["capped"]:
                for values in phase["alv_1_to_6"].values():
                    self.assertTrue(all(-0.041 <= e <= 0 for e in values["relative_error"]))

    def test_historical_description_is_rejected_and_hotfix_is_legal(self):
        failures = []
        for key, rows in self.rows.items():
            alias = "leader_ability" if key == "139995" else "ability"
            for index, row in enumerate(rows):
                errors = client_legality_problems(alias, row)
                if errors:
                    failures.append((key, index, errors))
        self.assertEqual([(key, index) for key, index, _ in failures], [("1399951", 4)])
        self.assertEqual(len(failures[0][2]), 1)
        self.assertIn("C10010", failures[0][2][0])
        for key, text in detail_fix.transform(self.new).items():
            alias = "leader_ability" if key == "139995" else "ability"
            for row in core.read_csv_lines(text):
                self.assertEqual(client_legality_problems(alias, row), [])

    def test_wrong_workspace_rejected_without_writes(self):
        with self.assertRaisesRegex(ValueError, "only the assigned"):
            tool._scope(Path(__file__).resolve().parent)


if __name__ == "__main__":
    unittest.main()
