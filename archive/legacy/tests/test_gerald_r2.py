"""Gerald R2 migration guards data ownership and the battle DSL contract."""
from __future__ import annotations

from wf.paths import root_path

import importlib
import hashlib
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

SOURCE = Path(('${WF_ROOT}/pkgarchive/unicorn_lancer_rose-1.4.764'.replace("${WF_ROOT}", str(root_path()))))


class GeraldR2Tests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("wf_gerald_r2")
        if not SOURCE.is_dir():
            self.skipTest("published Gerald fixture is unavailable")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name) / "codex_out" / "gerald" / "package"
        self.package.mkdir(parents=True)
        shutil.copyfile(SOURCE / "manifest.json", self.package / "manifest.json")
        for root, logical in self.mod.INPUTS:
            path = self.package / "roots" / root / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / "roots" / root / logical, path)

    def snapshot(self):
        return {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}

    def table(self, logical):
        return core.read_orderedmap_file(self.package / "roots/common" / logical,
                                        logical).text_rows()

    def test_dry_run_and_scope_restriction(self):
        before = self.snapshot()
        self.assertTrue(self.mod.revise(self.package, dry_run=True)["changed"])
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError):
            self.mod.revise(SOURCE, dry_run=True)

    def test_foreign_keys_and_ability_456_remain_byte_identical(self):
        before = {logical: self.table(logical) for logical in
                  (self.mod.ABILITY, self.mod.LEADER, self.mod.TEXT, self.mod.STRINGS,
                   self.mod.UNIQUE)}
        self.mod.revise(self.package, dry_run=False)
        allowed = {self.mod.ABILITY: {"1299922"}, self.mod.LEADER: {"129992"},
                   self.mod.TEXT: {"129992"},
                   self.mod.STRINGS: {"change_skill_unicorn_lancer_rose"},
                   self.mod.UNIQUE: set()}
        for logical, old in before.items():
            new = self.table(logical)
            self.assertEqual(set(old), set(new))
            self.assertEqual({k: v for k, v in old.items() if k not in allowed[logical]},
                             {k: v for k, v in new.items() if k not in allowed[logical]})
        four = core.read_csv_lines(self.table(self.mod.ABILITY)["1299924"])
        self.assertEqual(four[1][34], "(None)")

    def test_real_damage_and_self_flying_contract(self):
        self.mod.revise(self.package, dry_run=False)
        leader = core.read_csv_lines(self.table(self.mod.LEADER)["129992"])
        self.assertEqual(leader[0][45], "721")  # official separated Unique skill term
        self.assertEqual(leader[0][66], "129992")
        self.assertEqual((leader[1][28], leader[1][32], leader[1][49]),
                         ("5000000", "10", "100000"))
        ability = core.read_csv_lines(self.table(self.mod.ABILITY)["1299922"])
        self.assertEqual((ability[-1][27], ability[-1][28], ability[-1][29],
                          ability[-1][47], ability[-1][51]),
                         ("23", "5", "Blue", "226", "2500000"))
        for level, logical in enumerate(self.mod.MAIN, 1):
            path = self.package / "roots/common" / logical
            tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
            self.assertEqual(tree[10], 0, "Gerald remains skill damage")
            attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertEqual(sum(node[6][0]["max"] * count for node, count
                                 in zip(attacks, (12, 8, 1))), 60 if level == 1 else 90)
            self.assertTrue(all(node[8] is True for node in attacks))
            flying = [node for node in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                      if node[2][0][0] == "ACFlying"]
            self.assertEqual(len(flying), 1)
            self.assertEqual(flying[0][1:3], [-17, [["ACFlying", [{"min": 1200, "max": 1200}]]]])
            # The self buff lives only inside the existing ability-3 change flag.
            gates = list(wf_dsl.iter_dsl_commands(tree, "ConditionalsChangeSkillFlag"))
            self.assertTrue(any(flying[0] in list(wf_dsl.iter_dsl_commands(g[2], "CreateCondition"))
                                for g in gates))

    def test_both_display_layers_and_idempotence(self):
        self.mod.revise(self.package, dry_run=False)
        client = core.read_csv_lines(self.table(self.mod.TEXT)["129992"])[0]
        server = json.loads((self.package / "roots/server/cdndata/character_text.json").read_bytes())
        self.assertEqual(client, server["129992"][0])
        for text in (client[5], client[7]):
            self.assertNotIn("共鸣", text)
            self.assertIn("连击数", text)
        self.assertIn("90", client[7])
        before = self.snapshot()
        self.assertFalse(self.mod.revise(self.package, dry_run=False)["changed"])
        self.assertEqual(self.snapshot(), before)

    def test_unknown_own_row_aborts_before_writes(self):
        path = self.package / "roots/common" / self.mod.LEADER
        table = core.read_orderedmap_file(path, self.mod.LEADER)
        rows = core.read_csv_lines(table.text_rows()["129992"])
        rows[4][49] = "12345"
        table.set_text_rows({"129992": core.write_csv_lines(rows)})
        path.write_bytes(core.build_orderedmap(table))
        self.refresh_claim(self.mod.LEADER, path.read_bytes())
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.mod.revise(self.package, dry_run=False)
        self.assertEqual(self.snapshot(), before)

    def refresh_claim(self, logical, content):
        path = self.package / "manifest.json"
        manifest = json.loads(path.read_bytes())
        claim = next(r for r in manifest["roots"]["common"] if r["logical_path"] == logical)
        claim.update(sha256=hashlib.sha256(content).hexdigest(), size=len(content))
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_unknown_damage_aborts_even_with_matching_manifest(self):
        logical = self.mod.MAIN[1]
        path = self.package / "roots/common" / logical
        tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))[6][0]["max"] = 99
        compressor = zlib.compressobj(wbits=-15)
        content = compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()
        path.write_bytes(content)
        self.refresh_claim(logical, content)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.mod.revise(self.package, dry_run=False)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
