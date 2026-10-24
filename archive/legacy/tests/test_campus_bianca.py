"""校园碧安卡使用真实官方fixture的候选边界、DSL和资源回归。"""
from __future__ import annotations

import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zlib

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_assets as assets
import wf_campus_bianca as module
import wf_campus_bianca_data as data
import wf_campus_bianca_revision as revision
import wf_dsl
import wf_dsl_sig
import wf_mod_tool as core


class CampusBiancaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (module.ROOT / "mod-tools/profiles.json").is_file():
            raise unittest.SkipTest("official local fixture unavailable")
        cls.builder = module.Builder(apply=False)
        cls.builder.build_tables()
        cls.builder.build_skills()
        cls.builder.build_assets()

    def test_existing_client_table_rows_remain_byte_identical(self):
        for claim in self.builder.claims:
            if claim["root"] != "common":
                continue
            logical = claim["logical_path"]
            original = core.read_orderedmap_file_raw_rows(core.table_path(self.builder.store, logical), logical)
            candidate = core.read_orderedmap_raw_rows_from_bytes(self.builder.outputs["common", logical], logical)
            new = dict(zip(candidate.keys, candidate.rows))
            self.assertEqual(set(candidate.keys) - set(original.keys), set(claim["outer_keys"]))
            for key, raw in zip(original.keys, original.rows):
                self.assertEqual(new[key], raw, (logical, key))

    def test_skill_signatures_damage_and_isolated_slots(self):
        for level in (1, 2):
            logical = f"battle/action/skill/action/rare5/{data.CODE}${data.CODE}_{level}.action.dsl.amf3.deflate"
            tree = wf_dsl.parse_dsl(zlib.decompress(self.builder.outputs["common", logical], -15))["tree"]
            self.assertEqual(tree[10], 2, "global environment uses ordinary ability-damage multiplier")
            commands = list(data.walk_commands(tree))
            for command in commands:
                self.assertIn(command[0], wf_dsl_sig.COMMANDS)
                self.assertEqual(len(command) - 1, len(wf_dsl_sig.COMMANDS[command[0]]), command[0])
            attacks = [c for c in commands if c[0] == "CreateNormalAttack"]
            self.assertEqual(len(attacks), 7)
            self.assertEqual(sum(c[6][0]["max"] for c in attacks[:6]) + attacks[6][6][0]["max"] * 5,
                             23 if level == 1 else 28)
            hit_slots = [c[i] for c in commands if c[0] == "CreateHitArea" for i in (19, 21, 22)]
            self.assertEqual(len(hit_slots), len(set(hit_slots)))
            areas = [c for c in commands if c[0] == "CreateHitArea"]
            self.assertEqual(len(areas), 8, "seven damage areas plus original utility area")
            self.assertTrue(all(c[24] == 2 for c in areas))
            buff = [c for c in commands if c[0] == "CreateCondition" and c[2][0][0] == "ACAbilityDamage"]
            self.assertEqual(len(buff), 1)
            self.assertEqual(buff[0][1], 210)
            self.assertEqual(buff[0][2][0][1], [{"min": 900, "max": 900}])
            self.assertNotIn("ACSkillDamage", str(tree))
            target = next(c for c in commands if c[0] == "FindAllSubjects" and c[1] == 210)
            self.assertEqual(target[2:4], [113, [1]], "only fire allies receive the buff")
            fever = [c for c in commands if c[0] == "ConditionalsFeverMode"]
            self.assertEqual(len(fever), 1)
            self.assertEqual(fever[0][1], ["Block", []], "no active FEVER refill")
            self.assertEqual(fever[0][2][1][0], "AddFeverPoint")
            self.assertFalse(any(c[0] == "CreateSummonsMultiball" for c in commands))
            data.validate_skill(tree)

    def test_invalid_expression_and_subject_are_rejected(self):
        raw = next(raw for (root, path), raw in self.builder.outputs.items() if path.endswith("_1.action.dsl.amf3.deflate"))
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        invalid = deepcopy(tree)
        branch = next(c for c in data.walk_commands(invalid) if c[0] == "ConditionalsFeverMode")
        branch[1] = ["Sequence", []]
        with self.assertRaisesRegex(ValueError, "ActionDslExpression"):
            data.validate_skill(invalid)
        invalid = deepcopy(tree)
        next(c for c in data.walk_commands(invalid) if c[0] == "CreateNormalAttack")[1] = 99999
        with self.assertRaises(ValueError):
            data.validate_skill(invalid)

    def test_native_ability_damage_and_fever_cycle_guards(self):
        source = self.builder.official_rows("master/ability/ability.orderedmap")
        kit = data.ability_rows(source)
        proc = kit[data.CID + "2"][0]
        self.assertEqual(proc[27:30], ["23", "7", "Red"])
        self.assertEqual((proc[35], proc[47]), ("600", "251"))
        for row in kit[data.CID + "3"]:
            self.assertEqual((row[27], row[34], row[35]), ("8", "5", "1200"))
        self.assertEqual(kit[data.CID + "3"][0][52], "50000", "entry recharge is at most 50%")
        refill = kit[data.CID + "4"][0]
        self.assertEqual((refill[6], refill[28], refill[29], refill[34], refill[35], refill[47]),
                         ("186", "0", "", "10", "600", "213"))
        for rows in kit.values():
            for row in rows:
                self.assertNotIn(row[47], ("33", "34"), "old skill support content removed")
                data.validate_row(row, "ability")
        self.assertIn("source flags retained", data.snapshot()["active_source"])
        self.assertIn("createdByAbility=true", data.snapshot()["passive_damage"])

    def test_selective_revision_preserves_other_files_and_rows(self):
        plan = revision.Revision().plan()
        self.assertEqual(len(plan.outputs), 7)
        for (root, logical), raw in plan.outputs.items():
            self.assertNotIn("/ui/", logical)
            self.assertNotIn("/voice/", logical)
            self.assertNotIn("/pixelart/", logical)
            self.assertNotIn("image", logical)
            if logical.endswith(".orderedmap"):
                before = core.read_orderedmap_raw_rows_from_bytes(plan.inputs[root, logical], logical)
                after = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                self.assertEqual(before.keys, after.keys)
                claim = next(c for c in plan.manifest["tables"] if c["logical_path"] == logical)
                for key, a, b in zip(before.keys, before.rows, after.rows):
                    if key not in claim["outer_keys"]:
                        self.assertEqual(a, b, (logical, key))
            elif root == "server":
                before, after = json.loads(plan.inputs[root, logical]), json.loads(raw)
                before.pop(data.CID); after.pop(data.CID)
                self.assertEqual(before, after)
        original = json.loads(plan.original)
        self.assertEqual(original["tables"], plan.manifest["tables"])
        for root, entries in original["roots"].items():
            for entry in entries:
                key = root, entry["logical_path"]
                if key not in plan.outputs:
                    self.assertEqual(entry, plan.index[key])
        self.assertEqual((plan.ws.package_dir / "manifest.json").read_bytes(), plan.original)

    def test_pixel_geometry_alpha_and_palette(self):
        for name in ("sprite_sheet.png", "special_sprite_sheet.png"):
            source = assets.locate(self.builder.store, f"character/{data.PIXEL_CODE}/pixelart/{name}")[1].read_bytes()
            target = self.builder.outputs["common", f"character/{data.CODE}/pixelart/{name}"]
            a = Image.open(io.BytesIO(assets.png_decode(source))).convert("RGBA")
            b = Image.open(io.BytesIO(assets.png_decode(target))).convert("RGBA")
            self.assertEqual(a.size, b.size)
            self.assertEqual(a.getchannel("A").tobytes(), b.getchannel("A").tobytes())
            self.assertNotEqual(a.tobytes(), b.tobytes())

    def test_owned_paths_and_dry_run_does_not_mutate_candidate(self):
        before = hashlib.sha256((self.builder.ws.package_dir / "manifest.json").read_bytes()).hexdigest()
        result = self.builder.finish()
        self.assertFalse(result["writes_live"])
        self.assertFalse(result["apply"])
        self.assertEqual(before, hashlib.sha256((self.builder.ws.package_dir / "manifest.json").read_bytes()).hexdigest())
        for root, logical in self.builder.outputs:
            self.assertFalse(any(x in logical for x in ("/story/", "/words/", "/login/", "episode_banner")))
            if logical.startswith("battle/effect/"):
                self.assertIn("campus_bianca_", logical)


if __name__ == "__main__":
    unittest.main()
