"""月兔新数值、队伍回槽范围与连击强化分支的回归。"""
import unittest

import test_midautumn_kit_fluffy as fixtures
import wf_dsl
import wf_midautumn_kit_fluffy as K
from wf_battle_rules import GAINS


@unittest.skipUnless(fixtures._BASELINE, 'requires local native baseline')
class FluffyBalanceTests(unittest.TestCase):
    def test_three_pf_growth_is_resonant_wind_party_and_repeatable(self):
        rows, _ = K.build_leader_rows(fixtures.ctx())
        growth = [r for r in rows if r[25] == '2' and r[28] == '300000']
        self.assertEqual({r[45] for r in growth}, {'35', '245', '694'})
        self.assertEqual(len(growth), 3)
        for row in growth:
            self.assertEqual([row[i] for i in (4, 7, 8, 9)], ['2', '600000', '600000', 'Green'])
            # 09-24 输出各 5%；2026-09-27 平衡第二批覆盖：694（技能伤害额外乘区）5% → 1%，35/245 充能类不动；
            # 第三轮（成长复核）694 回调到 4%
            value = {'35': '5000', '245': '5000', '694': '4000'}[row[45]]
            self.assertEqual([row[i] for i in (29, 32, 33, 46, 47, 49, 50)],
                             ['300000', '(None)', '0', '5', 'Green', value, value])

    def test_cooldowns_keep_pair_order_and_distinct_trigger_thresholds(self):
        leader, _ = K.build_leader_rows(fixtures.ctx())
        pair = [r for r in leader if r[25] == '65']
        self.assertEqual([r[45] for r in pair], ['226', '629'])
        for row in pair:
            self.assertEqual([row[i] for i in (28, 29, 33)], ['500000', '500000', '360'])
        ability, _ = K.build_ability_rows(fixtures.ctx())
        invoke, = [r for r in ability['1499873'] if r[47] == '629']
        self.assertEqual([invoke[i] for i in (27, 30, 31, 35)],
                         ['12', '15000000', '15000000', '720'])

    def test_party_block_preserves_opening_movement_and_all_elements(self):
        ability, _ = K.build_ability_rows(fixtures.ctx())
        rule, = [r for r in ability['1499872'] if r[109] == '423']
        self.assertEqual((rule[1], rule[110], rule[111]), ('true', '5', '(None)'))
        mask = int(rule[118])
        self.assertEqual(mask, GAINS['skill'] | GAINS['ability'])
        self.assertEqual(mask & (GAINS['opening'] | GAINS['movement']), 0)
        self.assertEqual([rule[i] for i in (6, 13, 20, 100, 101)], ['0'] * 5)

    def test_skill_and_both_extra_triggers_keep_combo_scaled_finisher(self):
        for level in ('1', '2'):
            tree, gates = K.build_skill_tree(fixtures.ctx(), level, fixtures.fake_families())
            self.assertAlmostEqual(gates['segment_totals']['rush'] + gates['segment_totals']['pestle'], 25)
            self.assertEqual(gates['segment_totals']['finisher'], 65)
            self.assertEqual(gates['segment_hits'], {'rush': 10, 'pestle': 8, 'finisher': 1})
            for generated in (tree, K.build_invoke_tree(tree)[0]):
                branches = []
                for flag in wf_dsl.iter_dsl_commands(generated, 'ConditionalsChangeSkillFlag'):
                    on = list(wf_dsl.iter_dsl_commands(flag[2], 'CreateNormalAttack'))
                    off = list(wf_dsl.iter_dsl_commands(flag[3], 'CreateNormalAttack'))
                    if on and on[0][6][0]['max'] == 65:
                        branches.append((flag[1], on, off))
                self.assertEqual(len(branches), 1)
                flag, on, off = branches[0]
                self.assertEqual(flag, 1)  # Ability 1 ChangeSkillFlag
                self.assertTrue(on[0][8])  # native combo damage lane remains enabled
                self.assertFalse(off[0][8])
                self.assertEqual(on[0][6], off[0][6])
                combos = list(wf_dsl.iter_dsl_commands(generated, 'AddCombo'))
                self.assertEqual(len(combos), 10)
                for combo in combos:
                    self.assertEqual(combo[1], [{'min': 0.0, 'max': 0.0, 'alv2_min': 55.0, 'alv2_max': 55.0}])


if __name__ == '__main__':
    unittest.main()
