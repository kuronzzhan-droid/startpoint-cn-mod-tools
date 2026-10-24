import unittest
from copy import deepcopy
from wf_zehr_slow_spin import slow_parts,slow_timeline,slow_attack


class SlowSpinTest(unittest.TestCase):
    def test_parts_hold_original_poses_at_thirty_three_percent_speed(self):
        source={'i':[],'g':[{'t':3,'s':[]}],'m':[],'t':[], 'c':[], 'a':[],'o':[],'s':1}
        old=deepcopy(source);new=slow_parts(source)
        self.assertEqual(source,old)
        self.assertEqual(new['g'][1],source['g'][0])
        strip=new['g'][0]['s'][0]
        self.assertEqual(strip['i'],1)
        self.assertEqual([k['r'] for k in strip['l'] for _ in range(k['t'])],[0,0,0,1,1,1,2,2,2])
        self.assertEqual(new['g'][0]['t'],9)
        source['g'][0]['t']=99
        self.assertEqual(slow_parts(source)['g'][0]['t'],300)

    def test_timeline_sequences_and_audio_stay_aligned(self):
        source={'sequences':[dict(begin=1,end=14,name='start',kind='pass'),
                            dict(begin=15,end=28,name='loop',kind='loop')],
                'sounds':[dict(begin=2,end=-1,path='s')],'points':[]}
        new=slow_timeline(source)
        self.assertEqual([(s['begin'],s['end']) for s in new['sequences']],[(1,42),(43,84)])
        self.assertEqual(new['sounds'][0]['begin'],4)
        self.assertEqual(new['sounds'][0]['end'],-1)

    def test_heavier_hits_raise_damage_but_keep_break_fever_and_lifetime(self):
        for hits,duration in ((9,210),(12,270),(15,330)):
            atk=['CreateNormalAttack']+[None]*16
            for col,num in ((6,6.3),(13,1.5),(14,3)):
                atk[col]=[dict(min=num,max=num)]
            area=['CreateHitArea']+[None]*23
            area[2]=-18;area[13]=['SpecifyHitAreaLifetimeDirectly',duration]
            area[9]=['Circle',[dict(min=160,max=160)]]
            effect=['ShowEffect']+[None]*12
            effect[12]=['Some',[dict(min=3.2,max=3.2)]]
            area[20]=['Block',[['Command',deepcopy(effect)],['Command',deepcopy(effect)]]]
            area[14]=['CalculatedUsingMaxNumOfHits',hits]
            area[23]=['Block',[['Command',atk]]]
            result,report=slow_attack(area)
            self.assertEqual(result[13],area[13]);self.assertLess(result[14][1],hits)
            for col in (6,13,14):
                self.assertAlmostEqual(result[23][1][0][1][col][0]['max']*result[14][1],atk[col][0]['max']*hits*(2.025 if col==6 else 1))
            self.assertEqual(report['total_damage_ratio'],2.025)
            ratio={9:1,12:1.2,15:1.1}[hits]
            self.assertAlmostEqual(result[9][1][0]['max'],160*ratio)
            self.assertAlmostEqual(result[20][1][0][1][12][1][0]['max'],3.2*ratio)
            self.assertEqual(area[9][1][0]['max'],160)

    def test_unknown_source_shapes_rejected(self):
        with self.assertRaises(ValueError):slow_parts({'m':[1]})
        with self.assertRaises(ValueError):slow_timeline({'points':[1]})
        with self.assertRaises(ValueError):slow_attack([])


if __name__=='__main__':unittest.main()
