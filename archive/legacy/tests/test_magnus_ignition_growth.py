"""Native donor integration: one five-times budget per complete Magnus action."""
from copy import deepcopy
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_midautumn_kit_magnus as K
import wf_magnus_ignition_growth as G
from test_midautumn_kit_magnus import _LIVE, _ReadOnlyCtx, _stub_families


@unittest.skipUnless(_LIVE, 'requires official native donors')
class NativeGrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctx = _ReadOnlyCtx()
        families = _stub_families()
        cls.casts = []
        for level in ('1', '2'):
            tree, meta = K.build_main_tree(ctx, level, families)
            cls.casts.append((tree, meta['ignition_growth']))
        tree, meta = K.build_chase_tree(ctx, families)
        cls.casts.append((tree, meta['ignition_growth']))
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(ctx, level, families)
            shell, skill, meta = K.PF_SKILL.split_tree(tree)
            assert not list(wf_dsl.iter_dsl_commands(shell, 'CreateNormalAttack'))
            cls.casts.append(K.ignition_growth(skill, meta['hits']))

    def test_whole_cast_budget_at_zero_one_five_and_cap(self):
        self.assertEqual([m['hits'] for _, m in self.casts],
                         [[1, 10], [1, 10], [5], [2, 1], [3, 1], [3, 1]])
        for tree, meta in self.casts:
            attacks = list(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))
            bind = tree[11][1][0][1]
            for layers in (0, 1, 5, 10, 35, 99):
                # 第一批输出：每层整招 +5 倍 ＋ 2026-09-27 第二批覆盖：绑定上限 10
                # （变量 = min(层数 / 第4参, 第5参)，ActionEvaluator.as case 101）。
                variable = min(layers / bind[4], bind[5])
                extra = sum(a[6][0]['vlv'][0]['max'] * hits * variable
                            for a, hits in zip(attacks, meta['hits']))
                self.assertAlmostEqual(extra, min(layers, K.IGNITION_DSL_CAP) * 5, places=10)

    def test_snapshot_precedes_events_and_only_binds_once(self):
        for tree, _ in self.casts:
            binds = list(wf_dsl.iter_dsl_commands(tree, 'BindConditionAccumulationVariable'))
            # 第一批输出 上限 99（= G.MAX_LAYERS）＋ 2026-09-27 第二批覆盖：kit 封顶 IGNITION_DSL_CAP=10。
            self.assertEqual(binds, [['BindConditionAccumulationVariable',
                -17, G.VARIABLE, ['DCUnique', G.UID], 1, K.IGNITION_DSL_CAP]])
            self.assertEqual((G.MAX_LAYERS, K.IGNITION_DSL_CAP), (99, 10))
            self.assertEqual(tree[11][1][0], ['Command', binds[0]])
            self.assertEqual(tree[10], 0)

    def test_slash_ability_scaling_and_damage_types_preserved(self):
        for tree, _ in self.casts[:2]:
            slash = next(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))[6][0]
            self.assertEqual((slash['alv_min'], slash['alv_max']), (1.75, 3.5))
        for tree, _ in self.casts:
            self.assertTrue(all(a[24] == 0 for a in
                                wf_dsl.iter_dsl_commands(tree, 'CreateHitArea')))

    def test_hit_budget_drift_rejected_without_modifying_input(self):
        source = self._without_growth(self.casts[-1][0])
        before = deepcopy(source)
        with self.assertRaisesRegex(ValueError, 'hit budget drift'):
            G.with_ignition_growth(source, (2, 1))
        self.assertEqual(source, before)

    def test_only_growth_fields_change_and_duplicate_application_rejected(self):
        for final, meta in self.casts:
            source = self._without_growth(final)
            before = deepcopy(source)
            rebuilt, _ = K.ignition_growth(source, meta['hits'])
            self.assertEqual(source, before)
            self.assertEqual(rebuilt, final)
            # 第一批的原生增长（上限 99）与 kit 输出只差绑定上限一格（第二批覆盖）。
            native, _ = G.with_ignition_growth(source, meta['hits'])
            native[11][1][0][1][5] = K.IGNITION_DSL_CAP
            self.assertEqual(native, final)
            with self.assertRaisesRegex(ValueError, 'existing condition binding'):
                G.with_ignition_growth(rebuilt, meta['hits'])
            with self.assertRaisesRegex(ValueError, 'existing condition binding'):
                K.ignition_growth(rebuilt, meta['hits'])

    @staticmethod
    def _without_growth(tree):
        tree = deepcopy(tree)
        tree[11][1].pop(0)
        for attack in wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'):
            del attack[6][0]['vlv']
        return tree


if __name__ == '__main__':
    unittest.main()
