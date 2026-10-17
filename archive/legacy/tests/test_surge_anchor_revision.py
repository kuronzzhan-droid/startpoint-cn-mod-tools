"""阶段边界、Fever结束事件和非队长锚点的回归用例。"""
import json
from copy import deepcopy
from pathlib import Path
import unittest

import wf_regis_surge_stages as R
import wf_yuki_leader_anchor as Y
from wf_seasonal7_kit_philia import cmds, spec_paths
import wf_seasonal7_kit_regis as K


class SurgeAnchorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).parent/'fixtures/surge_anchor_before.json').read_bytes())

    def test_three_disjoint_stages_boundary_and_damage(self):
        for source in self.data['regis']:
            tree = R.revise_skill(source)
            choice = tree[11][1][1]
            for stacks, total, suffix in [(0,50,'/rec_android'), (2,80,'/rec_android'),
                (3,120,'_laser'), (4,135,'_laser'), (5,175,'_beam'), (99,1585,'_beam')]:
                branch = choice
                while branch[0] == 'Command':
                    c = branch[1]
                    branch = c[3] if stacks >= c[2] else c[4]
                attacks = list(cmds(branch, 'CreateNormalAttack'))
                self.assertEqual(len(attacks), 1)
                value = attacks[0][6][0]
                self.assertEqual(10*(value['max']+value['vlv'][0]['max']*stacks), total)
                self.assertEqual(value['min'], value['max'])
                self.assertTrue(any(p.endswith(suffix) for p in spec_paths(branch)))
                bind = list(cmds(branch,'BindConditionAccumulationVariable'))[0]
                self.assertEqual(bind[1:4], [-17,value['vlv'][0]['vid'],['DCUnique',R.UID]])

    def test_preserves_support_buffs_and_art(self):
        for source in self.data['regis']:
            tree = R.revise_skill(source)
            self.assertEqual(set(spec_paths(tree)), set(spec_paths(source)))
            for name in ('StopBall','CreateCondition','AddFeverPoint'):
                self.assertEqual(list(cmds(tree,name)),list(cmds(source,name)))
            self.assertEqual(tree[11][1][-1],source[11][1][-1])
            self.assertEqual(K.skill_desc_coverage_problems([tree],R.DESCRIPTION),[])

    def test_fever_end_grants_one_stack_leader_only_without_new_gate(self):
        leader, third = R.revise_rows(self.data['139994'],self.data['1399943'],self.data['1399941'])
        expected = deepcopy(self.data['139994'])
        expected[4][49:51] = ['25000', '25000']
        self.assertEqual(leader[:-1], expected)
        row = leader[-1]
        self.assertEqual((row[25],row[45],row[49],row[57],row[66]),
                         ('184','461','100000','100000',str(R.UID)))
        self.assertEqual(row[4], '0')
        self.assertEqual(row[33], '0')

    def test_skill_multiplier_keeps_original_ability_buff_and_is_self_only(self):
        _, third = R.revise_rows(self.data['139994'],self.data['1399943'],self.data['1399941'])
        expected = deepcopy(self.data['1399943'])
        expected[2][51:53] = ['25000', '25000']
        self.assertEqual(third[:-1], expected)
        row = third[-1]
        self.assertEqual((row[1],row[6],row[11],row[13],row[97]),('false','2','Yellow','12','4'))
        self.assertEqual(row[109:115],['411','0','','','25000','25000'])

    def test_yuki_changes_only_center_effect_subject(self):
        for source in self.data['yuki']:
            tree = Y.revise_skill(source)
            self.assertFalse(any(c[3] == -17 for c in cmds(tree,'ShowEffect')))
            center = next(c for c in cmds(tree,'ShowEffect') if c[2][1].endswith('/psychic_yuki_barrier'))
            self.assertEqual(center[3],-18)
            center[3] = -17
            self.assertEqual(tree,source)

    def test_transforms_are_idempotent_and_do_not_mutate_sources(self):
        before = deepcopy(self.data)
        for name, module in [('regis',R),('yuki',Y)]:
            for source in self.data[name]:
                tree=module.revise_skill(source)
                self.assertEqual(module.revise_skill(tree),tree)
        leader,third=R.revise_rows(self.data['139994'],self.data['1399943'],self.data['1399941'])
        self.assertEqual(R.revise_rows(leader,third,self.data['1399941']),(leader,third))
        self.assertEqual(before,self.data)

    def test_fever_gauge_text_and_opening_gauge_are_separate(self):
        before = deepcopy(self.data['1399941'])
        leader, third = R.revise_rows(self.data['139994'], self.data['1399943'], before)
        self.assertEqual(before, self.data['1399941'])
        self.assertEqual(before[0][51:53], ['50000', '50000'])
        self.assertEqual(leader[5][49:51], ['25000', '25000'])
        for slot in (0, 3):
            updated = R.revise_text(slot, '进入FEVER模式时，自身技能槽＋50%')
            self.assertIn('自身技能槽＋25%', updated)
            self.assertNotIn('自身技能槽＋50%', updated)


if __name__ == '__main__':
    unittest.main()
