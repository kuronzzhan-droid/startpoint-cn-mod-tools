"""Native collision PF must retain the official event lifecycle and ranged attacks."""
from __future__ import annotations

from wf.paths import root_path

from copy import deepcopy
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core

ROOT = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
STORE = ROOT / "弹国服/WorldFlipper/dummy/download/production/upload"
APK = Path(('${WF_ROOT}/out/newchars-pf-v9-20260906/wf_newchars_pf_v9.apk'.replace("${WF_ROOT}", str(root_path()))))
PACKAGE = Path(('${WF_ROOT}/pkgarchive/fox_oracle_autumn-1.4.765'.replace("${WF_ROOT}", str(root_path()))))


def commands(tree, name):
    found = []
    def walk(node):
        if isinstance(node, list):
            if node and node[0] == name:
                found.append(node)
            for child in node:
                walk(child)
    walk(tree)
    return found


class NativePfTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("wf_inaho_native_pf_r2")
        self.dsl = importlib.import_module("wf_native_pf_r2_dsl")
        if not (APK.exists() and PACKAGE.exists()):
            self.skipTest("locked official APK/package fixtures unavailable")
        self.sources = self.mod.load_sources(STORE, APK)

    def test_collision_effect_only_appears_after_contact(self):
        for level in (1, 2, 3):
            tree = self.dsl.compose(self.sources["special", level],
                                    self.sources["ranged", level], level)
            top = tree[11][1]
            self.assertFalse(any(e[0] == "Command" and e[1][0] == "CreateHitArea" for e in top))
            for collision in commands(tree, "CollisionOfBallAndEnemy"):
                self.assertEqual(collision[1:4], [90, 1, "*"])
                self.assertEqual(len(commands(collision, "CreateReferencePoint")), 1)
                self.assertEqual(len(commands(collision, "CreateHitArea")), 2)
                self.assertEqual(commands(collision, "RemoveEvent"), [["RemoveEvent", "ヒット判定"]])
                self.assertEqual(len(commands(collision, "NotifyPowerflipEnd")), 1)
            self.assertEqual(len(commands(tree, "ConditionalsCombo")), 1)
            self.assertEqual(commands(tree, "ConditionalsCombo")[0][1], 35)

    def test_visual_sphere_radius_and_hit_count_scale_together(self):
        for level, radius, hits, scale in [(1, 320, 2, 6.4), (2, 400, 3, 8), (3, 560, 3, 11.2)]:
            tree = self.dsl.compose(self.sources["special", level], self.sources["ranged", level], level)
            combo, = commands(tree, "ConditionalsCombo")
            for block, expected_hits in [(combo[2], hits + 2), (combo[3], hits)]:
                areas = commands(block, "CreateHitArea")
                self.assertEqual([area[14][1] for area in areas], [expected_hits, 1])
                self.assertEqual([area[9][1][0]["max"] for area in areas], [radius, radius])
                sphere = [effect for effect in commands(block, "ShowEffect") if "player_" not in effect[2][1]]
                self.assertEqual(len(sphere), 1)
                self.assertAlmostEqual(sphere[0][12][1][0]["max"], scale)
                self.assertIn("effect_powerflip_attack_special", sphere[0][2][1])

    def test_ranged_attacks_preserved_and_donor_end_removed(self):
        for level in (1, 2, 3):
            tree = self.dsl.compose(self.sources["special", level], self.sources["ranged", level], level)
            donor, = [e for e in tree[11][1] if e[0] == "Event" and e[1][0] == "Wait" and e[1][1] == 1]
            self.assertEqual(commands(donor, "NotifyPowerflipEnd"), [])
            self.assertEqual(commands(donor, "SetPowerFilpSuppress"), [])
            before = commands(self.sources["ranged", level], "CreateNormalAttack")
            after = deepcopy(commands(donor, "CreateNormalAttack"))
            for attack in after:
                attack[1] -= 100
            self.assertEqual(before, after)
            self.assertEqual(tree, wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"])

    def test_unknown_source_and_bad_level_fail_closed(self):
        damaged = deepcopy(self.sources["special", 1])
        commands(damaged, "CollisionOfBallAndEnemy")[0][2] = 2
        with self.assertRaises(ValueError):
            self.dsl.compose(damaged, self.sources["ranged", 1], 1)
        with self.assertRaises(ValueError):
            self.dsl.compose(self.sources["special", 1], self.sources["ranged", 1], 0)

    def test_each_conditional_path_retains_the_entire_original_lifecycle(self):
        for level in (1, 2, 3):
            for fever, resonance, combo in [(False, True, True), (True, False, True),
                                            (True, True, False), (True, True, True)]:
                tree = self.dsl.compose(self.sources["special", level], self.sources["ranged", level], level)
                entry = tree[11][1][3]
                conditions = {"ConditionalsFeverMode": fever, "ConditionalsUnifyElement": resonance,
                              "ConditionalsCombo": combo}
                while entry[0] == "Command" and entry[1][0] in conditions:
                    command = entry[1]
                    true_index = {"ConditionalsFeverMode": 1, "ConditionalsUnifyElement": 3,
                                  "ConditionalsCombo": 2}[command[0]]
                    block = command[true_index + (not conditions[command[0]])]
                    entry, = block[1]
                tree[11][1] = tree[11][1][:3] + [entry]
                areas = commands(entry, "CreateHitArea")
                if fever and resonance and combo:
                    areas[0][14][1] -= 2
                for area in areas:
                    for term in area[9][1]:
                        term["min"] = round(term["min"] / 1.6)
                        term["max"] = round(term["max"] / 1.6)
                for effect in commands(entry, "ShowEffect"):
                    for term in effect[12][1]:
                        term["min"] = round(term["min"] / 1.6)
                        term["max"] = round(term["max"] / 1.6)
                self.assertEqual(tree, self.sources["special", level])

    def fixture_package(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        package = Path(temp.name) / "codex_out" / "package"
        shutil.copytree(PACKAGE, package)
        return package

    def test_package_upgrade_keeps_foreign_rows_and_only_removes_old_629(self):
        package = self.fixture_package()
        ability_path = package / "roots/common" / self.mod.ABILITY
        before = core.read_orderedmap_file(ability_path, self.mod.ABILITY).text_rows()
        report = self.mod.revise(package, STORE, APK, dry_run=False)
        after = core.read_orderedmap_file(ability_path, self.mod.ABILITY).text_rows()
        expected = dict(before)
        expected["1399953"] = core.write_csv_lines(core.read_csv_lines(before["1399953"])[1:])
        self.assertEqual(expected, after)
        self.assertTrue(report["requires_client_capability"])
        ld = core.read_orderedmap_file(package / "roots/common" / self.mod.LEADER, self.mod.LEADER)
        rows = core.read_csv_lines(ld.text_rows()["139995"])
        self.assertEqual(rows[-1][45], "722")
        self.assertEqual(rows[-1][80:83], [self.mod.PF_ID, "1,2,3", self.mod.STRING_ID])
        manifest = json.loads((package / "manifest.json").read_bytes())
        claim, = [t for t in manifest["tables"] if t["logical_path"] == self.mod.PF_TABLE]
        self.assertEqual(claim["outer_keys"], [self.mod.PF_ID])
        self.assertFalse(manifest["qa"]["release_ready"])
        self.assertEqual(len(report["effect_assets"]), 28)
        claimed = {entry["logical_path"] for entry in manifest["roots"]["common"]}
        for logical in report["effect_assets"]:
            self.assertTrue((package / "roots/common" / logical).is_file(), logical)
            self.assertIn(logical, claimed)

    def test_dry_run_and_reapply_are_noops(self):
        package = self.fixture_package()
        def snapshot():
            return {str(p.relative_to(package)): p.read_bytes() for p in package.rglob("*") if p.is_file()}
        before = snapshot()
        self.mod.revise(package, STORE, APK, dry_run=True)
        self.assertEqual(before, snapshot())
        self.mod.revise(package, STORE, APK, dry_run=False)
        applied = snapshot()
        self.mod.revise(package, STORE, APK, dry_run=False)
        self.assertEqual(applied, snapshot())
        with self.assertRaises(ValueError):
            self.mod.revise(PACKAGE, STORE, APK, dry_run=True)

    def test_unknown_existing_private_key_does_not_write_anything(self):
        package = self.fixture_package()
        self.mod.revise(package, STORE, APK, dry_run=False)
        treepath = package / "roots/common" / (self.mod.PROGRAMS[0] + self.mod.SUFFIX)
        treepath.write_bytes(b"unrecognized variant")
        before = {p: p.read_bytes() for p in package.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            self.mod.revise(package, STORE, APK, dry_run=False)
        self.assertEqual(before, {p: p.read_bytes() for p in package.rglob("*") if p.is_file()})

    def test_changed_surviving_ability3_row_is_rejected_before_writes(self):
        package = self.fixture_package()
        self.mod.revise(package, STORE, APK, dry_run=False)
        path = package / "roots/common" / self.mod.ABILITY
        table = core.read_orderedmap_file(path, self.mod.ABILITY)
        rows = core.read_csv_lines(table.text_rows()["1399953"])
        rows[0][52] = "-30000"
        table.set_text_rows({"1399953": core.write_csv_lines(rows)})
        path.write_bytes(core.build_orderedmap(table))
        before = {p: p.read_bytes() for p in package.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            self.mod.revise(package, STORE, APK, dry_run=False)
        self.assertEqual(before, {p: p.read_bytes() for p in package.rglob("*") if p.is_file()})

    def test_stock_effects_are_private_with_identical_pixels_and_motion(self):
        import zlib
        package = self.fixture_package()
        report = self.mod.revise(package, STORE, APK, dry_run=False)
        manifest = json.loads((package / "manifest.json").read_bytes())
        claimed = {entry["logical_path"] for entry in manifest["roots"]["common"]}
        private_prefix = "battle/effect/powerflip/fox_oracle_autumn_native/"
        for logical in report["effect_assets"]:
            self.assertTrue(logical.startswith(private_prefix), logical)
            original = logical.replace(private_prefix, "battle/effect/powerflip/", 1)
            self.assertNotIn(original, claimed)
            self.assertFalse((package / "roots/common" / original).exists())
            digest = core.sha1_path(original)
            original_raw = (STORE / digest[:2] / digest[2:]).read_bytes()
            private_raw = (package / "roots/common" / logical).read_bytes()
            if logical.endswith((".png", ".timeline.amf3.deflate")):
                self.assertEqual(private_raw, original_raw)
            else:
                original_tree = wf_dsl.parse_dsl(zlib.decompress(original_raw, -15))["tree"]
                private_tree = wf_dsl.parse_dsl(zlib.decompress(private_raw, -15))["tree"]
                restored = json.loads(json.dumps(private_tree).replace(private_prefix, "battle/effect/powerflip/"))
                self.assertEqual(restored, original_tree)

    def test_only_exact_previously_added_shared_copies_are_removed(self):
        package = self.fixture_package()
        report = self.mod.revise(package, STORE, APK, dry_run=False)
        manifest_path = package / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        for original in report["effect_path_mapping"]:
            digest = core.sha1_path(original)
            raw = (STORE / digest[:2] / digest[2:]).read_bytes()
            target = package / "roots/common" / original
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            manifest["roots"]["common"].append({"logical_path": original,
                "size": len(raw), "sha256": self.mod.sha(raw)})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        last_target, original_raw = target, raw
        last_target.write_bytes(b"unknown artist changes")
        before = {p: p.read_bytes() for p in package.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            self.mod.revise(package, STORE, APK, dry_run=False)
        self.assertEqual(before, {p: p.read_bytes() for p in package.rglob("*") if p.is_file()})
        last_target.write_bytes(original_raw)
        migrated = self.mod.revise(package, STORE, APK, dry_run=False)
        self.assertEqual(len(migrated["removed"]), 28)
        for original in report["effect_path_mapping"]:
            self.assertFalse((package / "roots/common" / original).exists())


if __name__ == "__main__":
    unittest.main()
