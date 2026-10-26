"""真实原生供体的Boss优先、回退与朝向跟踪合同。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_celtie_fever_skill as s
from wf_celtie_fever_package import Candidate


class BossLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[2]
        cls.c=Candidate(root,root/'work/character_packs/campus-celtie-20260911')

    def test_default_targets_boss_then_falls_back_in_each_growth_route(self):
        for level in (1,2):
            tree=s.build_skill(level,self.c.official)
            s.validate(tree)
            self.assertEqual(tree,s.parse(s.encode(tree)))
            near=s.nodes(tree,'FindNearSubjects')
            # 2026-09-27 第三轮（c）：共鸣∧Fever 路线按旗号 2 复制一份，3 → 4 条路线。
            self.assertEqual([49,51]*4,[n[3] for n in near])
            self.assertTrue(all(n[5]==90 for n in near))
            self.assertEqual([],s.nodes(tree,'IfThisCharacterIsBoss'))
            for boss in (n for n in near if n[3] == 51):
                self.assertEqual(['DoNothing'],boss[4])
                self.assertEqual(['Command',['RemoveEvent','campus_celtie_boss_fallback']],boss[6][1][0])
            waits=[w for w in s.nodes(tree,'Wait') if w[2]=='campus_celtie_boss_fallback']
            self.assertEqual(4,len(waits))
            self.assertTrue(all(w[1]==1 for w in waits))
            self.assertTrue(all(n[2]==['GH',90] for n in s.nodes(tree,'MoveBall')))
            self.assertTrue(all(n[1]==90 for n in s.nodes(tree,'CollisionOfBallAndSpecificEnemy')))
            self.assertTrue(all(n[1]==90 for n in s.nodes(tree,'GH')))
            for ref in s.nodes(tree,'CreateReferencePoint'):
                self.assertEqual((['GH',90],True),(ref[2],ref[7]))
                self.assertNotEqual(90,ref[10])
                self.assertTrue(all(a[3]==['CD'] and a[8] for a in s.nodes(ref,'CreateHitArea')))
                self.assertTrue(all(e[6]==['CD'] and e[11] for e in s.nodes(ref,'ShowEffect')))
            # Both boss/fallback copies preserve every base and layer multiplier.
            baseline=s.build_skill(level,self.c.official,boss_target=False)
            before=s.nodes(baseline,'CreateNormalAttack')
            after=s.nodes(tree,'CreateNormalAttack')
            self.assertEqual(2*len(before),len(after))
            self.assertEqual({repr(a) for a in before},{repr(a) for a in after})


if __name__=='__main__':unittest.main()
