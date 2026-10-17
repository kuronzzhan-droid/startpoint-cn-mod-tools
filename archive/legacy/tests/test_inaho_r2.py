"""Scoped R2 ability migration and preservation checks."""
from __future__ import annotations

from wf.paths import root_path

import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core

BASELINE = {'1399952': 'fox_oracle_autumn_2,true,attack_yellow,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,15,,,100000,100000,,,(None),45,,,,(None),,,,,,,0,354,0,,,1000000,2000000,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,',
 '1399955': 'fox_oracle_autumn_5,true,attack_yellow,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,693,5,Yellow,,10000,20000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n'
            'fox_oracle_autumn_5,true,attack_yellow,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,118,5,Yellow,,20000,40000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n'
            'fox_oracle_autumn_5,true,attack_yellow,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,(None),,,,,,,0,696,,,,20000,40000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,',
 '1399956': 'fox_oracle_autumn_6,true,fever,0,,0,0,,,,,,,0,,,,,,,0,,,,,,,23,7,Yellow,100000,100000,,,(None),0,,,,(None),,,,,,,0,213,,,,17500000,35000000,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n'
            'fox_oracle_autumn_6,true,fever,0,,1,0,,,,,,,0,,,,,,,0,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,(None),,,,,,,,,,,,4,,,,,,,,,,,false,413,,,,15000,30000,,,,,,,,,,,'}

class InahoR2Tests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("wf_inaho_r2")
        self.rows = {key: core.read_csv_lines(value) for key, value in BASELINE.items()}

    def test_ball_flip_is_not_dash_and_original_i354_is_untouched(self):
        old = copy.deepcopy(self.rows)
        result = self.mod.revise_rows(self.rows)
        self.assertEqual(self.rows, old)
        self.assertEqual(result["1399952"][0], old["1399952"][0])
        added = result["1399952"][1]
        self.assertEqual((added[6], added[27], added[47]), ("12", "6", "226"))
        self.assertEqual((added[30], added[31], added[34], added[35]),
                         ("100000", "100000", "(None)", "0"))
        self.assertEqual((added[51], added[52], added[1]), ("250000", "500000", "true"))

    def test_all_five_six_rows_require_six_thunder_and_fever_gate_remains(self):
        result = self.mod.revise_rows(self.rows)
        for key in ("1399955", "1399956"):
            for row in result[key]:
                self.assertEqual((row[6], row[9], row[10], row[11]),
                                 ("2", "600000", "600000", "Yellow"))
        self.assertEqual(result["1399956"][1][97], "4")
        self.assertEqual(result["1399956"][1][109], "413")
        self.assertEqual(result["1399956"][0][27:36], self.rows["1399956"][0][27:36])

    def test_independent_ability_damage_replaces_only_independent_pf(self):
        result = self.mod.revise_rows(self.rows)["1399955"]
        self.assertEqual([r[47] for r in result], ["693", "118", "695"])
        self.assertEqual(result[2][48:53], ["5", "Yellow", "", "10000", "20000"])
        for i in (0, 1):
            self.assertEqual(result[i][13:], self.rows["1399955"][i][13:])

    def test_foreign_keys_extra_rows_and_existing_conditions_are_preserved(self):
        foreign = [list(self.rows["1399952"][0])]
        self.rows["foreign"] = foreign
        extra = list(self.rows["1399955"][0])
        extra[47], extra[6] = "35", "12"
        self.rows["1399955"].append(extra)
        result = self.mod.revise_rows(self.rows)
        self.assertEqual(result["foreign"], foreign)
        revised = result["1399955"][-1]
        self.assertEqual(revised[:13], extra[:13])
        self.assertEqual(revised[20:], extra[20:])
        self.assertEqual(revised[13:20], ["2", "", "", "600000", "600000", "Yellow", ""])

    def test_changed_known_input_or_duplicate_aborts(self):
        self.rows["1399955"][0][52] = "25000"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.mod.revise_rows(self.rows)
        self.rows = {key: core.read_csv_lines(value) for key, value in BASELINE.items()}
        self.rows["1399952"].append(list(self.rows["1399952"][0]))
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.mod.revise_rows(self.rows)

    def test_condition_slots_full_fail_without_mutation(self):
        extra = list(self.rows["1399955"][0])
        extra[47] = "35"
        extra[6] = extra[13] = extra[20] = "12"
        self.rows["1399955"].append(extra)
        before = copy.deepcopy(self.rows)
        with self.assertRaisesRegex(ValueError, "precondition"):
            self.mod.revise_rows(self.rows)
        self.assertEqual(self.rows, before)

    def test_idempotent(self):
        once = self.mod.revise_rows(self.rows)
        self.assertEqual(self.mod.revise_rows(once), once)

    def test_package_dry_run_guard_hashes_and_only_three_keys(self):
        source = Path(('${WF_ROOT}/pkgarchive/fox_oracle_autumn-1.4.765'.replace("${WF_ROOT}", str(root_path()))))
        if not source.is_dir():
            self.skipTest("immutable installed package fixture is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "codex_out/package"
            table = package / "roots/common" / self.mod.ABILITY
            table.parent.mkdir(parents=True)
            table.write_bytes((source / "roots/common" / self.mod.ABILITY).read_bytes())
            manifest = package / "manifest.json"
            manifest.write_bytes((source / "manifest.json").read_bytes())
            before = {p: p.read_bytes() for p in (table, manifest)}
            self.mod.revise(package, dry_run=True)
            self.assertEqual(before, {p: p.read_bytes() for p in (table, manifest)})
            with self.assertRaises(ValueError):
                self.mod.revise(source, dry_run=True)
            original = core.read_orderedmap_file(table, self.mod.ABILITY).text_rows()
            self.mod.revise(package, dry_run=False)
            actual = core.read_orderedmap_file(table, self.mod.ABILITY).text_rows()
            self.assertEqual({k for k in original if original[k] != actual[k]}, set(BASELINE))
            data = json.loads(manifest.read_text("utf-8"))
            claim = next(x for x in data["roots"]["common"] if x["logical_path"] == self.mod.ABILITY)
            import hashlib
            self.assertEqual(claim["sha256"], hashlib.sha256(table.read_bytes()).hexdigest())
            self.assertFalse(data["qa"]["release_ready"])
            second = {p: p.read_bytes() for p in (table, manifest)}
            self.mod.revise(package, dry_run=False)
            self.assertEqual(second, {p: p.read_bytes() for p in (table, manifest)})


if __name__ == "__main__":
    unittest.main()
