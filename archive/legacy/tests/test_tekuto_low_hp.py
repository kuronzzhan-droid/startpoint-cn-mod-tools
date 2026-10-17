import json
from copy import deepcopy
from pathlib import Path
import unittest
import wf_tekuto_low_hp as T
from wf_seasonal7_kit_philia import cmds


class TekutoLowHpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((Path(__file__).parent/'fixtures/tekuto_low_hp_before.json').read_bytes())

    def test_removes_both_ally_skill_growth_rows_and_keeps_every_other_leader_row(self):
        before=self.data[T.CID]
        leader,_=T.revise_rows(before,self.data[T.CID+'3'])
        self.assertEqual(leader[:-2],[r for i,r in enumerate(before) if i not in (7,8)])
        self.assertEqual(len(leader),len(before))

    def test_growth_uses_three_and_conditions_two_seconds_and_no_limit(self):
        leader,_=T.revise_rows(self.data[T.CID],self.data[T.CID+'3'])
        r=leader[-2]
        self.assertEqual((r[4],r[9],r[11],r[17],r[18]),('2','Yellow','188',T.CANNON,'9'))
        self.assertEqual(r[21:23],['50000']*2)  # HpLow includes threshold, unlike205.
        self.assertEqual(r[25],'77')
        self.assertEqual(r[28:30],['12000000']*2)  # 120 native frames, not2 frames.
        self.assertEqual(r[32],'(None)')
        self.assertEqual((r[45],r[49],r[50]),('34','100000','100000'))

    def test_half_hp_self_cast_adds_two_engine_stacks_not_cannon_gate(self):
        leader,_=T.revise_rows(self.data[T.CID],self.data[T.CID+'3'])
        r=leader[-1]
        self.assertEqual((r[4],r[11],r[18],r[25],r[26]),('2','9','0','23','0'))
        self.assertEqual(r[14:16],['50000']*2)
        self.assertEqual((r[45],r[66]),('461',T.ENGINE))
        # Native number creates separate discrimination keys, not stack count.
        # One shared instance with magnification 2 adds both layers to the
        # same counter used by the skill and DuringConditionAccumulation.
        self.assertEqual(r[57:59],['100000']*2)
        self.assertEqual(r[72],'2')

    def test_cannon_grant_is_self_skill_and_does_not_require_engine(self):
        _,third=T.revise_rows(self.data[T.CID],self.data[T.CID+'3'])
        self.assertEqual(third[:-1],self.data[T.CID+'3'][:-1])
        r=third[-1]
        self.assertEqual((r[1],r[6],r[11],r[13],r[20],r[27],r[28]),
                         ('false','2','Yellow','0','0','23','0'))
        self.assertEqual(r[68],T.CANNON)
        self.assertEqual(T.revise_unique([['x','x','x','720']])[0][3],'900')

    def test_barrier_once_per_cast_only_when_enhancement_slot2_is_active(self):
        for level in ('1','2'):
            source=self.data[level];tree=T.revise_skill(source)
            self.assertEqual(tree[11][1][:-1],source[11][1])
            gate=tree[11][1][-1][1]
            self.assertEqual(gate[:2],['ConditionalsChangeSkillFlag',2])
            self.assertEqual(gate[3],['Block',[]])
            self.assertEqual(list(cmds(tree,'CreateBarrier')),
                [['CreateBarrier',-17,[{'min':0.15,'max':0.15}],['GenericBarrierHitEffect']]])
            self.assertEqual(list(cmds(tree,'CreateNormalAttack')),list(cmds(source,'CreateNormalAttack')))

    def test_sources_not_mutated_and_unexpected_shape_rejected(self):
        original=deepcopy(self.data)
        T.revise_rows(self.data[T.CID],self.data[T.CID+'3'])
        T.revise_skill(self.data['2'])
        self.assertEqual(original,self.data)
        with self.assertRaises(ValueError): T.revise_rows([],self.data[T.CID+'3'])


if __name__=='__main__': unittest.main()
