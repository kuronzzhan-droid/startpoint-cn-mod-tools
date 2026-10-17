"""Native knight/supporter combination preserves both official behaviors."""
from __future__ import annotations

from wf.paths import root_path

import copy
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core

SOURCE = Path(('${WF_ROOT}/startpoint-cn/work/codex_out/newchars-r2-20260906/gerald-native-pf'.replace("${WF_ROOT}", str(root_path()))))
PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r2-20260906/unicorn_lancer_rose/package'.replace("${WF_ROOT}", str(root_path()))))


class GeraldNativePFTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("wf_gerald_native_pf_dsl")
        if not SOURCE.is_dir():
            self.skipTest("V9 native knight/supporter source fixture is unavailable")

    def sources(self, level):
        return tuple((SOURCE / f"{kind}_lv{level}.action.dsl.amf3.deflate").read_bytes()
                     for kind in ("knight", "supporter"))

    def test_all_levels_keep_exact_knight_base_and_one_end(self):
        for level, end_frame in ((1, 69), (2, 89), (3, 109)):
            raw, donor = self.sources(level)
            tree = self.mod.compose(raw, donor, level)
            original = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            self.assertEqual(tree[:11], original[:11])
            self.assertEqual(tree[11][1][:3], original[11][1])
            self.assertEqual(len(list(wf_dsl.iter_dsl_commands(tree, "NotifyPowerflipEnd"))), 1)
            self.assertEqual([entry[1][1] for entry in tree[11][1]
                              if entry[0] == "Event" and entry[1][0] == "Wait"], [end_frame])
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)

    def test_supporter_conditions_and_level_three_attack_survive(self):
        for level, attack_time, strength, movement_time in (
                (1, 150, .3, 60), (2, 180, .4, 90), (3, 240, .5, 150)):
            tree = self.mod.compose(*self.sources(level), level)
            conditions = list(wf_dsl.iter_dsl_commands(tree, "CreateCondition"))
            self.assertEqual(len(conditions), 3)
            self.assertEqual(conditions[0][2][0], ["ACAttackPoint",
                             [{"min": attack_time, "max": attack_time}],
                             [{"min": strength, "max": strength}], [{"min": 1, "max": 1}]])
            self.assertEqual(conditions[1][2][0], ["ACPiercing",
                             [{"min": movement_time, "max": movement_time}]])
            self.assertEqual(conditions[2][2][0], ["ACFlying",
                             [{"min": movement_time, "max": movement_time}]])
            self.assertEqual({n[2] for n in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects")}, {33})
            attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertEqual(len(attacks), 2 if level == 3 else 1)
            if level == 3:
                self.assertEqual(attacks[1][1], 203)
                self.assertEqual(attacks[1][6], [{"min": 4, "max": 4}])
                self.assertIn("powerflip_attack_support_three", str(attacks[1][15]))

    def test_donor_bound_ids_and_consumers_use_same_namespace(self):
        tree = self.mod.compose(*self.sources(3), 3)
        find = list(wf_dsl.iter_dsl_commands(tree, "FindAllSubjects"))
        self.assertEqual([n[1] for n in find], [200, 204])
        effects = list(wf_dsl.iter_dsl_commands(tree, "ShowEffect"))
        self.assertEqual(effects[1][3], 200)
        self.assertTrue(effects[1][1].endswith("_support"))
        self.assertEqual({n[1] for n in wf_dsl.iter_dsl_commands(tree, "CreateCondition")}, {204})
        hit = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))[1]
        self.assertEqual((hit[2], hit[19], hit[21], hit[22]), (-1, 201, 202, 203))

    def test_source_byte_drift_rejected(self):
        raw, donor = self.sources(1)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.mod.compose(raw, donor + b"changed", 1)

    def test_package_preserves_existing_rows_and_claims(self):
        mod = importlib.import_module("wf_gerald_native_pf_r2")
        if not PACKAGE.is_dir():
            self.skipTest("Gerald R2 package fixture is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "codex_out/package"
            target.mkdir(parents=True)
            (target / "manifest.json").write_bytes((PACKAGE / "manifest.json").read_bytes())
            for logical in (mod.LEADER, mod.STRINGS):
                output = target / "roots/common" / logical
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes((PACKAGE / "roots/common" / logical).read_bytes())
            leader = target / "roots/common" / mod.LEADER
            old = core.read_orderedmap_file(leader, mod.LEADER).text_rows()
            initial = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
            mod.revise(target, SOURCE, dry_run=True)
            self.assertEqual(initial, {p: p.read_bytes() for p in target.rglob("*") if p.is_file()})
            mod.revise(target, SOURCE, dry_run=False)
            actual = core.read_orderedmap_file(leader, mod.LEADER).text_rows()
            self.assertEqual({k: v for k, v in old.items() if k != "129992"},
                             {k: v for k, v in actual.items() if k != "129992"})
            new_rows = core.read_csv_lines(actual["129992"])
            self.assertEqual(new_rows[:8], core.read_csv_lines(old["129992"])[:8])
            self.assertEqual(len(new_rows), 9)
            self.assertEqual((new_rows[8][45], new_rows[8][80], new_rows[8][81]),
                             ("722", mod.PF_KEY, "1,2,3"))
            pf = core.read_orderedmap_file(target / "roots/common" / mod.PF_TABLE, mod.PF_TABLE)
            self.assertEqual(pf.keys, [mod.PF_KEY])
            manifest = json.loads((target / "manifest.json").read_text("utf-8"))
            self.assertFalse(manifest["qa"]["release_ready"])
            self.assertIn(mod.PF_TABLE, [x["logical_path"] for x in manifest["tables"]])
            before_again = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
            mod.revise(target, SOURCE, dry_run=False)
            self.assertEqual(before_again, {p: p.read_bytes() for p in target.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
