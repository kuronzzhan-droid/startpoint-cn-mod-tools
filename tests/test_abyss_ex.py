import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import abyss_ex as ex
import random
from wf.tools.rogue import rogue_build as builder

class ExNativeContract(unittest.TestCase):
    def test_full_optional_pool_keeps_two_immunities_and_never_rolls_time(self):
        caps=builder.resolve_curse_capabilities('boss_level','general',{'boss':True,'element':True,'spawn':True,'panel':False})
        viable={(e,d) for e in range(1,7) for d in range(4)}
        names=set(); fields=0
        for seed in range(20):
            history=[]
            for floor in range(1,31):
                result=ex.roll_curses(builder,floor,random.Random(seed*30+floor),viable,caps,
                    dict(baseline_c86=1,c86_limits=(.001,1000000),baseline_dps=20e9/900,
                         base_duration_s=900,hp_channel='boss_level'),history=history)
                history.append({c['name'] for c in result['picks']})
                names.update(history[-1]);fields+=len(result['casters'])
                self.assertIsNone(result['time'])
                self.assertEqual(len(builder.immunity_axes(result['picks'])[0]),2)
                self.assertIn(len(result['element_resistance']),(3,4))
                self.assertIsNotNone(ex.output_lane(builder,result['picks'],viable,()))
        self.assertTrue({'血肉高墙','魔力枯竭','深渊重甲','嗜血狂潮','深渊壁垒'}<=names,names)
        self.assertGreater(fields,0)
        self.assertNotIn('时之枷锁',names)

    def test_field_pool_does_not_sneak_in_another_damage_lock(self):
        menu=ex.safe_field_menu(builder)
        labels={m[0] for m in menu}
        self.assertTrue(any('重力' in x for x in labels))
        self.assertTrue(any('风' in x for x in labels))
        self.assertTrue(any('水' in x for x in labels))
        self.assertTrue(any('充能' in x for x in labels))
        self.assertFalse(any('攻击-100%' in m[2] or '伤害-300%' in m[2] for m in menu))
    def test_element_enum_is_not_a_bitmask(self):
        dd,ee=ex.condition_bounds([['ACToleranceOfElement',[600],e,[999],[1]] for e in [1,2,3,5,6]])
        self.assertEqual(ee,[0,999,999,999,0,999,999])
        self.assertEqual(dd,[0]*4)
        self.assertEqual(ex.condition_bounds([['ACToleranceOfElement',[600],254,[2],[3]]])[1],[0,6,6,6,6,6,6])
        self.assertEqual(ex.condition_bounds([['ACToleranceOfElement',[600],255,[-.25],[1]]])[1],[0]*7)
    def test_unknown_native_targets_and_conditions_fail_closed(self):
        for tree in ([['ACToleranceOfElement',[1],255,[999],[1]]],
                     [['ACInvincible',[1]]],
                     [['ACSkillDamageResistance',[1],['dynamic'],[1]]]):
            with self.assertRaises(ValueError):ex.condition_bounds(tree)
    def test_native_stacked_immunity_closes_the_lane(self):
        dd,_=ex.condition_bounds([['ACSkillDamageResistance',[100],[.6],[2]],['ACDirectAttackDamageResistance',[100],[-1],[1]]])
        self.assertEqual(dd,[0,0,0,1.2])

if __name__=='__main__':unittest.main()
