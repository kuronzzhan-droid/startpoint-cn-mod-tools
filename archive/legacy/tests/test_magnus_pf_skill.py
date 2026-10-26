"""Guard a complete source conversion, with no residual PF or duplicate hit."""
import copy
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl
import wf_magnus_pf_skill as S
import wf_midautumn_kit_magnus as K
from tests.test_midautumn_kit_magnus import _ReadOnlyCtx, _stub_families


class SkillConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = _ReadOnlyCtx()

    def test_each_tier_transfers_exact_damage_and_preserves_movement(self):
        for n, total in [(1, 12), (2, 22), (3, 42)]:
            with self.subTest(level=n):
                base, _ = K.build_pf_tree(self.ctx, n, _stub_families())
                saved = copy.deepcopy(base)
                move, skill, meta = S.split_tree(base)
                commands = lambda t, name: list(wf_dsl.iter_dsl_commands(t, name))
                self.assertEqual(base, saved)
                self.assertEqual(commands(move, 'CreateNormalAttack'), [])
                self.assertEqual(commands(move, 'CreateHitArea'), [])
                for name in ('CreateHitArea', 'CreateNormalAttack'):
                    self.assertEqual(commands(skill, name), commands(base, name))
                for name in ('SetPowerFilpSuppress', 'NotifyPowerflipEnd',
                             'ShowEffect', 'HideEffect'):
                    self.assertEqual(commands(skill, name), [])
                    self.assertEqual(commands(move, name), commands(base, name))
                self.assertEqual(skill[10], 0)
                self.assertAlmostEqual(meta['total'], total, places=5)
                self.assertFalse(K._dsl_problems(move))
                self.assertFalse(K._dsl_problems(skill))

    def test_three_exact_launch_levels_use_native_skill_invocation(self):
        rows = K.build_rows(self.ctx)
        invokes = [r for r in rows['leader'] if r[45] == '629']
        self.assertEqual([r[25] for r in invokes], ['63', '64', '65'])
        self.assertEqual([r[69] for r in invokes], list(K.PF_SKILL_PROGRAMS))
        for r in invokes:
            self.assertEqual((r[4], r[7], r[9], r[11], r[28], r[32], r[33]),
                             ('2', '600000', 'Red', '0', '100000', '(None)', '0'))

    def test_chase_and_consumption_share_self_skill_hit_gate(self):
        rows = K.build_rows(self.ctx)['ability']['1199903']
        invoke = next(r for r in rows if r[47] == '629')
        consume = next(r for r in rows if r[47] == '525')
        for r in (invoke, consume):
            self.assertEqual((r[27], r[28], r[30], r[35]),
                             ('136', '0', '100000', '36'))
            self.assertEqual((r[6], r[12]), ('188', K.UID))
        self.assertLess(rows.index(invoke), rows.index(consume))

    def test_rejects_changed_source_type(self):
        base, _ = K.build_pf_tree(self.ctx, 1, _stub_families())
        base[10] = 3
        with self.assertRaises(ValueError):
            S.split_tree(base)


if __name__ == '__main__':
    unittest.main()
