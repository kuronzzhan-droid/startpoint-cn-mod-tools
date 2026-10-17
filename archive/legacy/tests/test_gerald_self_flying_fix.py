"""Regress the published Ball condition target without changing skill behavior."""

from wf.paths import root_path
from copy import deepcopy
from pathlib import Path
import shutil
import re
import sys
import tempfile
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_gerald_self_flying_fix as fix
import wf_gerald_r2_data as generator

SOURCE = Path(('${WF_ROOT}/pkgarchive/unicorn_lancer_rose-1.4.768'.replace("${WF_ROOT}", str(root_path()))))


class GeraldSelfFlyingTests(unittest.TestCase):
    def setUp(self):
        if not SOURCE.is_dir():
            self.skipTest("published Gerald 1.4.768 fixture unavailable")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.package = Path(temporary.name) / "codex_out/package"
        self.package.mkdir(parents=True)
        shutil.copyfile(SOURCE / "manifest.json", self.package / "manifest.json")
        for logical in fix.LOGICALS:
            path = self.package / "roots/common" / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / "roots/common" / logical, path)

    def snapshot(self):
        return {p: p.read_bytes() for p in self.package.rglob("*") if p.is_file()}

    def tree(self, level):
        path = self.package / "roots/common" / fix.LOGICALS[level - 1]
        return wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]

    def test_only_the_bad_ball_subject_changes_and_entire_rest_is_exact(self):
        for level in (1, 2):
            before = self.tree(level)
            after = fix.fix_tree(before, level)
            conditions = list(wf_dsl.iter_dsl_commands(after, "CreateCondition"))
            flying, = [n for n in conditions if n[2][0][0] == "ACFlying"]
            self.assertEqual(flying[1:3], [-17, [["ACFlying", [{"min": 1200, "max": 1200}]]]])
            flying[1] = -18
            self.assertEqual(before, after, "every other field must remain exact")

    def test_generator_repairs_previous_output_and_remains_idempotent(self):
        for level in (1, 2):
            before = self.tree(level)
            expected = fix.fix_tree(before, level)
            self.assertEqual(generator.revise_tree(before, str(level)), expected)
            self.assertEqual(generator.revise_tree(expected, str(level)), expected)

    def test_native_condition_owner_contract_and_squad_forwarding(self):
        # Source-backed contract probe, not a claim to execute Flash in Python.
        # Guard the exact native methods so the probe cannot silently diverge.
        root = Path(('${WF_ROOT}/outputs/re-workspace/decompile/scripts/pinball/scene/battle/battle'.replace("${WF_ROOT}", str(root_path()))))
        if not root.exists():
            self.skipTest("native source fixture unavailable")
        ball = (root / "squad/ball/BallImpl.as").read_text(encoding="utf-8")
        member = (root / "squad/member/MemberImpl.as").read_text(encoding="utf-8")
        resolver = (root / "action/ActionEvaluationResolver.as").read_text(encoding="utf-8")
        slot = (root / "condition/ConditionSlot.as").read_text(encoding="utf-8")
        self.assertIn("_new(-17),getMyself()", resolver)
        self.assertIn("_new(-18),getPlayersBall()", resolver)
        def body(source, name):
            match = re.search(r"function " + name + r"\([^)]*\)\s*:\s*\w+\s*\{([^}]+)\}", source)
            self.assertIsNotNone(match)
            return match.group(1).strip()
        self.assertEqual(body(member, "getMyselfAsActionSubject"), "return this;")
        def probe(source):
            self.assertEqual(body(source, "isConditionOwnable"), "return !isBreakableBlock();")
            statement = body(source, "isBreakableBlock")
            if "throw false;" in statement:
                raise RuntimeError("native Ball.isBreakableBlock throws false")
            self.assertEqual(statement, "return false;")
            return True
        with self.assertRaisesRegex(RuntimeError, "Ball.isBreakableBlock"):
            probe(ball)
        self.assertTrue(probe(member))
        apply = slot[slot.index("public function applyConditionChange("):]
        forwarding = "_loc10_.applyConditionChange(param1,param2,param3,param4,param5,param6,param7,param8);"
        self.assertLess(apply.index(forwarding), apply.index("ConditionChangeContentTools.fit(owner,param1.content)"))
        self.assertIn("if(!squad.conditionSlot.isFlying())", member)

    def test_dry_run_idempotence_and_manifest_preservation(self):
        before = self.snapshot()
        self.assertTrue(all(f["changed"] for f in fix.revise(self.package)["files"]))
        self.assertEqual(before, self.snapshot())
        fix.revise(self.package, dry_run=False)
        self.assertEqual(before[self.package / "manifest.json"],
                         (self.package / "manifest.json").read_bytes())
        applied = self.snapshot()
        self.assertFalse(any(f["changed"] for f in fix.revise(self.package, dry_run=False)["files"]))
        self.assertEqual(applied, self.snapshot())

    def test_unknown_skill_damage_fails_before_writing_first_file(self):
        path = self.package / "roots/common" / fix.LOGICALS[1]
        tree = self.tree(2)
        attack = next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        attack[6][0]["max"] += 1
        encoder = zlib.compressobj(level=9, wbits=-15)
        path.write_bytes(encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush())
        before = self.snapshot()
        with self.assertRaises(ValueError):
            fix.revise(self.package, dry_run=False)
        self.assertEqual(before, self.snapshot())

    def test_live_archive_and_other_character_are_rejected(self):
        with self.assertRaises(ValueError):
            fix.revise(SOURCE)
        tree = deepcopy(self.tree(1))
        flying = next(n for n in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                      if n[2][0][0] == "ACFlying")
        flying[1] = 13
        with self.assertRaises(ValueError):
            fix.fix_tree(tree, 1)


if __name__ == "__main__":
    unittest.main()
