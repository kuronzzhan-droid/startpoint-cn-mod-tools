"""Offline Kyubi revision must preserve unrelated rows, Fever time and ability 4-6.

The fixture is the author's live package (1.1.1, identical to the store since 1.4.765,
2026-09-06 13:42).  It is already revised: every DSL, orderedmap and text step of the
revision is a byte-for-byte no-op on it, and the special PF carries one extra PF art
node that the revision never produced.  The layout is pinned below so any further
drift of the live tree turns this file red instead of being unpacked past.
"""
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
from unittest.mock import patch
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core

SOURCE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/fox_oracle_autumn/package'.replace("${WF_ROOT}", str(root_path()))))
# tree_hash of the live special PF (author package 1.1.1 == store, 1.4.765..1.4.783).
LIVE_SPECIAL_SHA256 = "fe63ae87585a23dd2606fd768e606d264434ab0c5f899ce748c1c77fb319c97f"
# tree_hash of revise_tree(SPECIAL_BASE): the live tree minus its PF art node
# (work/codex_out/newchars-revision-20260906/pf-agent-package, 2026-09-06 13:28).
REVISION_OUTPUT_SHA256 = "f67189dd9767a486a99b7ea40340a101ed9c430f5fa9d3b32b1f77c4b54a80e9"


class KyubiRevisionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("wf_kyubi_pf_revision")
        self.assertIsNotNone(spec, "the isolated package revision is not implemented")
        self.mod = importlib.import_module("wf_kyubi_pf_revision")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "codex_out" / "kyubi" / "package"
        if not SOURCE.is_dir():
            self.skipTest("original character package fixture is unavailable")
        self.package.mkdir(parents=True)
        shutil.copyfile(SOURCE / "manifest.json", self.package / "manifest.json")
        for root, logical in self.mod.INPUTS:
            target = self.package / "roots" / root / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / "roots" / root / logical, target)

    def test_dry_run_writes_nothing_and_original_path_is_refused(self):
        before = {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}
        report = self.mod.revise(self.package, dry_run=True)
        # Live 1.1.1 is already revised: only the manifest claim and the server
        # mirror's JSON formatting move.  Anything else here is fixture drift.
        self.assertEqual(sorted(report["changed"]),
                         ["manifest.json", "roots/server/cdndata/character_text.json"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()})
        with self.assertRaises(ValueError):
            self.mod.revise(SOURCE, dry_run=True)

    def test_explicit_integration_clone_is_allowed_but_author_package_is_not(self):
        approved = (Path(self.temp.name) / "work/character_packs/codex-revision-20260906"
                    / "fox_oracle_autumn/package")
        approved.mkdir(parents=True)
        (approved / "manifest.json").write_text("{}", encoding="utf-8")
        with patch.object(self.mod, "APPROVED_PACKAGE", approved):
            self.assertEqual(self.mod._package(approved.parent), approved.resolve())
            with self.assertRaises(ValueError):
                self.mod._package(SOURCE)

    def test_no_foreign_rows_fever_or_456_change(self):
        path = self.package / "roots/common/master/ability/ability.orderedmap"
        before = core.read_orderedmap_file(path, "ability").text_rows()
        self.mod.revise(self.package, dry_run=False)
        after = core.read_orderedmap_file(path, "ability").text_rows()
        self.assertEqual(before, after)
        row = core.read_csv_lines(after["1399952"])[0]
        self.assertEqual(row[27], "15")
        self.assertEqual(row[35], "45")
        self.assertEqual(row[47], "354")
        self.assertEqual(row[1], "true", "ability 2 must remain available in unison")

    def test_pf_damage_and_special_available_outside_fever(self):
        self.mod.revise(self.package, dry_run=False)
        for program in (*self.mod.MAIN, self.mod.SPECIAL):
            path = self.package / "roots/common" / (program + self.mod.SUFFIX)
            tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
            self.assertEqual(tree[10], 3)
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
            attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertTrue(attacks)
            self.assertTrue(all(node[-1] is True for node in attacks))
        tree = wf_dsl.parse_dsl(zlib.decompress(
            (self.package / "roots/common" / (self.mod.SPECIAL + self.mod.SUFFIX)).read_bytes(), -15))["tree"]
        # Fever's false branch now has damage, so ordinary PF also has the extra special attack.
        fever = list(wf_dsl.iter_dsl_commands(tree, "ConditionalsFeverMode"))[0]
        self.assertTrue(list(wf_dsl.iter_dsl_commands(fever[2], "CreateNormalAttack")))
        radii = {node[9][1][0]["max"] for node in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")}
        self.assertEqual(radii, {320, 480})

    def test_capability_claim_and_idempotence(self):
        def string_claim(manifest):
            return next(x for x in manifest["tables"]
                        if "custom_ability_string" in x["logical_path"])["outer_keys"]
        before = string_claim(json.loads((self.package / "manifest.json").read_text(encoding="utf-8")))
        self.mod.revise(self.package, dry_run=False)
        manifest = json.loads((self.package / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("kyubi-pf-damage-v1", manifest["required_capabilities"])
        self.assertFalse(manifest["qa"]["release_ready"])
        # The claim carries other features' keys (dual-PF override, panel override);
        # the revision may neither add nor drop any of them.
        self.assertIn(self.mod.SPECIAL_KEY, before)
        self.assertEqual(string_claim(manifest), before)
        first = {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}
        self.mod.revise(self.package, dry_run=False)
        self.assertEqual(first, {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()})

    def test_main_art_nodes_preserved_but_unknown_damage_rejected(self):
        from wf_kyubi_pf_dsl import revise_tree
        path = self.package / "roots/common" / (self.mod.MAIN[0] + self.mod.SUFFIX)
        tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        art = ["Command", ["HideEffect", "test_art_marker"]]
        tree[11][1].append(art)
        snapshot = deepcopy(tree)
        result = revise_tree(tree, self.mod.MAIN[0])
        self.assertIn(art, result[11][1])
        self.assertEqual(result[10], 3)
        self.assertEqual(tree, snapshot, "input tree must not be mutated")
        next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))[6][0]["max"] = 999
        with self.assertRaises(ValueError):
            revise_tree(tree, self.mod.MAIN[0])

    def test_foreign_text_rows_preserved_and_display_matches_pf(self):
        flat_paths = (self.mod.TEXT, self.mod.STRINGS)
        before = {}
        for logical in flat_paths:
            path = self.package / "roots/common" / logical
            before[logical] = core.read_orderedmap_file(path, logical).text_rows()
        self.mod.revise(self.package, dry_run=False)
        for logical in flat_paths:
            path = self.package / "roots/common" / logical
            after = core.read_orderedmap_file(path, logical).text_rows()
            own = "139995" if logical == self.mod.TEXT else self.mod.SPECIAL_KEY
            self.assertEqual({k: v for k, v in before[logical].items() if k != own},
                             {k: v for k, v in after.items() if k != own})
            self.assertIn("强化弹射伤害", after[own])
            self.assertNotIn("范围扩大", after[own])

    def test_live_special_layout_is_pinned_and_revision_is_a_no_op(self):
        from wf_kyubi_pf_dsl import NATIVE_PF_ART, revise_tree, tree_hash
        for program in self.mod.MAIN:
            path = self.package / "roots/common" / (program + self.mod.SUFFIX)
            tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
            self.assertEqual(tree[10], 3, "live main skills are already revised")
        path = self.package / "roots/common" / (self.mod.SPECIAL + self.mod.SUFFIX)
        tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        self.assertEqual(tree[10], 3)
        self.assertEqual([node[1][0] for node in tree[11][1]],
                         ["ShowEffect", "ShowEffect", "ConditionalsFeverMode"])
        self.assertEqual(tree[11][1][0][1][1], "雷华缠球", "hoisted baseline effect first")
        self.assertEqual(tree[11][1][1], NATIVE_PF_ART)
        self.assertEqual(tree_hash(tree), LIVE_SPECIAL_SHA256)
        self.assertEqual(revise_tree(tree, self.mod.SPECIAL), tree)
        # Minus the art node it is exactly the revision's own output, still accepted.
        stripped = deepcopy(tree)
        del stripped[11][1][1]
        self.assertEqual(tree_hash(stripped), REVISION_OUTPUT_SHA256)
        self.assertEqual(revise_tree(stripped, self.mod.SPECIAL), stripped)
        # Every other count, order or node content is refused, never unpacked past.
        drifted_art = deepcopy(NATIVE_PF_ART)
        drifted_art[1][12] = ["None"]
        for label, mutate in (
            ("fourth node", lambda t: t[11][1].insert(1, deepcopy(NATIVE_PF_ART))),
            ("art node before the effect", lambda t: t[11][1].insert(0, t[11][1].pop(1))),
            ("art node after Fever", lambda t: t[11][1].append(t[11][1].pop(1))),
            ("different node in the art slot",
             lambda t: t[11][1].__setitem__(1, ["Command", ["HideEffect", "fox_oracle_autumn_api_pf"]])),
            ("art lifetime drift", lambda t: t[11][1].__setitem__(1, drifted_art)),
            ("foreign node in a two-node body",
             lambda t: (t[11][1].pop(1), t[11][1].__setitem__(0, drifted_art))),
        ):
            mutated = deepcopy(tree)
            mutate(mutated)
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    revise_tree(mutated, self.mod.SPECIAL)

    def test_unknown_special_fails_before_any_package_writes(self):
        path = self.package / "roots/common" / (self.mod.SPECIAL + self.mod.SUFFIX)
        tree = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        next(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))[13][1] = 91
        compressor = zlib.compressobj(wbits=-15)
        path.write_bytes(compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush())
        before = {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}
        with self.assertRaises(ValueError):
            self.mod.revise(self.package, dry_run=False)
        self.assertEqual(before, {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
