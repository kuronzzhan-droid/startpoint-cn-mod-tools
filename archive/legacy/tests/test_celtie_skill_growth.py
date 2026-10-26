"""原生分支作用域与SLvValue层数倍率回归；覆盖未共鸣和退出Fever。"""
from copy import deepcopy
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_celtie_skill_growth as growth
import wf_celtie_fever_skill as skill


def active_scope(expression, *, fever, wind_members, layers, scope=None):
    """独立转录原生子Environment继承、当前层绑定和互斥执行。"""
    scope = {} if scope is None else dict(scope)
    if expression[0] == 'Block':
        for child in expression[1]:
            result = active_scope(child, fever=fever, wind_members=wind_members,
                                  layers=layers, scope=scope)
            if result is not None:
                return result
            if child[0] == 'Command' and child[1][0] == 'BindConditionAccumulationVariable':
                command = child[1]
                scope[command[2]] = min(layers / command[4], command[5])
        return None
    command = expression[1]
    if command[0] == 'ConditionalsFeverMode':
        child = command[1 if fever else 2]
    elif command[0] == 'ConditionalsUnifyElement':
        assert command[1:3] == [4, 6]
        child = command[3 if wind_members >= 6 else 4]
    elif command[0] == 'FindNearSubjects':
        return command, scope
    else:
        return None
    return active_scope(child, fever=fever, wind_members=wind_members,
                        layers=layers, scope=scope)


def evaluated_multiplier(attack, variables):
    return sum(term['max'] + sum(
        v['min'] + (v['max'] - v['min']) * variables[v['vid']]
        for v in term.get('vlv', [])) for term in attack[6])


class CeltieSkillGrowthTests(unittest.TestCase):
    def setUp(self):
        # Only the two mutually exclusive landing bodies contain damage.
        def branch():
            return skill.block(*(skill.cmd('CreateNormalAttack', 0, 4, 0, 0, 0,
                skill.value(weight * 75 / 70)) for weight in (25, 45)))
        self.near = ['FindNearSubjects', branch(), branch()]
        self.before = deepcopy(self.near)

    def test_all_three_branches_inherit_binding_and_preserve_damage_body(self):
        tree = growth.with_starwind_growth(self.near)
        self.assertEqual(self.before, self.near)
        self.assertEqual(3, len(skill.nodes(tree, 'FindNearSubjects')))
        bindings = skill.nodes(tree, 'BindConditionAccumulationVariable')
        # 2026-09-27 第二批（口径 A5）：共鸣∧Fever 支上限 2147483647→10（官方 blackflower_wiz_smr22 同为 10）。
        self.assertEqual([10, 0, 0], [b[5] for b in bindings])
        for binding in bindings:
            self.assertEqual([-17, 14998905, ['DCUnique', 14998902], 1], binding[1:5])
        for near in skill.nodes(tree, 'FindNearSubjects'):
            restored = deepcopy(near)
            for attack in skill.nodes(restored, 'CreateNormalAttack'):
                attack[6][0].pop('vlv')
            self.assertEqual(self.before, restored)

    def test_seventy_five_plus_ten_per_layer_up_to_ten_layers_only_inside_resonant_fever(self):
        # 2026-09-27 第二批（口径 A5）：层数贡献封顶 10 层 ⇒ 最多 75+100 倍。
        tree = growth.with_starwind_growth(self.near)
        for fever, winds in ((True, 6), (True, 5), (False, 6), (False, 5)):
            for layers in (0, 1, 7, 10, 11, 100, 2147483647):
                with self.subTest(fever=fever, winds=winds, layers=layers):
                    near, variables = active_scope(tree, fever=fever,
                        wind_members=winds, layers=layers)
                    expected = 75 + (10 * min(layers, 10) if fever and winds == 6 else 0)
                    for branch in near[1:]:
                        actual = sum(evaluated_multiplier(a, variables)
                                     for a in skill.nodes(branch, 'CreateNormalAttack'))
                        self.assertAlmostEqual(actual / expected, 1, places=12)

    def test_wrong_damage_shape_is_rejected_instead_of_scaling_unrelated_hits(self):
        wrong = deepcopy(self.near)
        skill.nodes(wrong, 'CreateNormalAttack')[0][6] = skill.value(999)
        with self.assertRaisesRegex(ValueError, 'base'):
            growth.with_starwind_growth(wrong)
        with self.assertRaisesRegex(ValueError, 'four'):
            growth.with_starwind_growth(['FindNearSubjects', skill.block()])


if __name__ == '__main__':
    unittest.main()
