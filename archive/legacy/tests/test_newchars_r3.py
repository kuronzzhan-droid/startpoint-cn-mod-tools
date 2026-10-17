"""R3 package ownership, native special/ranged separation and repeat safety."""

from wf.paths import root_path
from copy import deepcopy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core
import wf_newchars_r3 as migration
import wf_newchars_r3_data as data

SOURCES = {
    "unicorn_lancer_rose": Path(('${WF_ROOT}/pkgarchive/unicorn_lancer_rose-1.4.766'.replace("${WF_ROOT}", str(root_path())))),
    "fox_oracle_autumn": Path(('${WF_ROOT}/pkgarchive/fox_oracle_autumn-1.4.767'.replace("${WF_ROOT}", str(root_path())))),
}


def commands(tree, name):
    return list(wf_dsl.iter_dsl_commands(tree, name))


class NewCharsR3Tests(unittest.TestCase):
    def setUp(self):
        if not all(path.is_dir() for path in SOURCES.values()):
            self.skipTest("published R2 package fixtures are unavailable")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name) / "codex_out"
        for code, source in SOURCES.items():
            package = self.base / code / "package"
            package.mkdir(parents=True)
            shutil.copyfile(source / "manifest.json", package / "manifest.json")
            logicals = ([migration.ABILITY] if code == "unicorn_lancer_rose" else
                        [migration.LEADER, *migration.PROGRAMS])
            for logical in logicals:
                path = package / "roots/common" / logical
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / "roots/common" / logical, path)

    def path(self, code, logical):
        return self.base / code / "package/roots/common" / logical

    def snapshot(self):
        return {p: p.read_bytes() for p in self.base.rglob("*") if p.is_file()}

    def table(self, code, logical):
        return core.read_orderedmap_file(self.path(code, logical), logical).text_rows()

    def tree(self, level):
        path = self.path("fox_oracle_autumn", migration.PROGRAMS[level - 1])
        return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]

    def test_dry_run_does_not_write_and_archives_are_rejected(self):
        before = self.snapshot()
        result = migration.revise(self.base)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(sum(f["changed"] for f in result["files"]), 5)
        unapproved = self.base.parent / "unapproved"
        (unapproved / "fox_oracle_autumn/package").mkdir(parents=True)
        with self.assertRaises(ValueError):
            migration._package(unapproved, "fox_oracle_autumn", 139995)

    def test_foreign_rows_and_manifests_unchanged_and_replay_is_empty(self):
        before = self.snapshot()
        tables = {(code, logical): self.table(code, logical) for code, logical in
                  (("unicorn_lancer_rose", migration.ABILITY), ("fox_oracle_autumn", migration.LEADER))}
        migration.revise(self.base, dry_run=False)
        for (code, logical), rows in tables.items():
            allowed = "1299926" if code == "unicorn_lancer_rose" else "139995"
            after = self.table(code, logical)
            self.assertEqual(rows.keys(), after.keys())
            self.assertEqual({k: v for k, v in rows.items() if k != allowed},
                             {k: v for k, v in after.items() if k != allowed})
        for path, raw in before.items():
            if path.name == "manifest.json":
                self.assertEqual(path.read_bytes(), raw)
        after = self.snapshot()
        self.assertFalse(any(f["changed"] for f in migration.revise(self.base, dry_run=False)["files"]))
        self.assertEqual(after, self.snapshot())

    def test_unknown_later_input_fails_before_any_earlier_write(self):
        path = self.path("fox_oracle_autumn", migration.PROGRAMS[-1])
        tree = self.tree(3)
        commands(tree, "CreateNormalAttack")[-1][6][0]["max"] += 1
        path.write_bytes(migration._encode(tree))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            migration.revise(self.base, dry_run=False)
        self.assertEqual(before, self.snapshot())

    def test_collision_branches_keep_timing_and_ranged_donor_byte_values(self):
        before = {level: self.tree(level) for level in (1, 2, 3)}
        migration.revise(self.base, dry_run=False)
        for level, source in before.items():
            target = self.tree(level)
            # All top-level content outside the one special conditional is exact.
            self.assertEqual(source[:11], target[:11])
            self.assertEqual(source[11][1][:3], target[11][1][:3])
            self.assertEqual(source[11][1][4:], target[11][1][4:])
            self.assertEqual(source[12:], target[12:])
            for name in ("CollisionOfBallAndEnemy", "CreateReferencePoint", "RemoveEvent",
                         "NotifyPowerflipEnd", "ConditionalsCombo", "ConditionalsUnifyElement"):
                # Event/conditional nodes contain the intentionally edited body;
                # compare their parameters and use leaf commands for lifecycle.
                old = commands(source, name)
                new = commands(target, name)
                if name == "CreateReferencePoint":
                    old, new = [n[:-1] for n in old], [n[:-1] for n in new]
                if name in {"CollisionOfBallAndEnemy", "ConditionalsCombo", "ConditionalsUnifyElement"}:
                    old = [n[:4 if name == "CollisionOfBallAndEnemy" else
                              2 if name == "ConditionalsCombo" else 3] for n in old]
                    new = [n[:4 if name == "CollisionOfBallAndEnemy" else
                              2 if name == "ConditionalsCombo" else 3] for n in new]
                self.assertEqual(old, new)
            old_areas = commands(source[11][1][3], "CreateHitArea")
            new_areas = commands(target[11][1][3], "CreateHitArea")
            for old, new in zip(old_areas, new_areas):
                restored = deepcopy(new)
                restored[9] = old[9]
                restored[23] = old[23]  # Attack callback is compared separately below.
                self.assertEqual(old, restored)

    def test_every_special_branch_has_matching_radius_and_25_percent_less_damage(self):
        for level, radius, scale in ((1, 250, 5), (2, 312.5, 6.25), (3, 437.5, 8.75)):
            source = self.tree(level)
            target = data.inaho_power_flip(source, level)
            special = target[11][1][3]
            areas = commands(special, "CreateHitArea")
            self.assertEqual(len(areas), 8)
            self.assertTrue(all(a[9] == ["Circle", [{"min": radius, "max": radius}]] for a in areas))
            self.assertTrue(all(e[12] == ["Some", [{"min": scale, "max": scale}]]
                                for e in commands(special, "ShowEffect")))
            for old, new in zip(commands(source[11][1][3], "CreateNormalAttack"),
                                commands(special, "CreateNormalAttack")):
                self.assertEqual(new[6][0]["max"], old[6][0]["max"] * 0.75)
                restored = deepcopy(new)
                restored[6] = old[6]
                self.assertEqual(old, restored)
            self.assertEqual(target, data.inaho_power_flip(target, level))

    def test_gerald_replaces_unique_without_changing_leader_or_charge(self):
        text = self.table("unicorn_lancer_rose", migration.ABILITY)["1299926"]
        old = core.read_csv_lines(text)
        new = core.read_csv_lines(data.gerald_ability6(text))
        self.assertEqual(old[1:], new[1:])
        changed = {i for i, (a, b) in enumerate(zip(old[0], new[0])) if a != b}
        self.assertEqual(changed, {35, 47, 51, 52, 68})
        self.assertEqual((new[0][6], new[0][27], new[0][35], new[0][47], new[0][51], new[0][68]),
                         ("42", "20", "0", "226", "500000", ""))

    def test_signed_lv3_row_matches_official_i200_shape(self):
        table = self.table("fox_oracle_autumn", migration.LEADER)
        rows = core.read_csv_lines(data.inaho_leader(table["139995"]))
        self.assertEqual(rows[:-1], core.read_csv_lines(table["139995"]))
        official = next(r for r in core.read_csv_lines(table["221006"]) if r[45] == "200")
        official[0], official[49], official[50] = "fox_oracle_autumn", "-900000", "-900000"
        self.assertEqual(rows[-1], official)


if __name__ == "__main__":
    unittest.main()
