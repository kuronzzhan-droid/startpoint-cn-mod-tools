import copy,sys,unittest
from pathlib import Path
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl,wf_kuro_full_dice as F,wf_midautumn_kit_kuro as K


class FullDiceTests(unittest.TestCase):
    def setUp(self):
        self.original=['Block',K.build_roulette()]
        self.new=F.apply(self.original)

    def test_five_layers_use_original_rewards_six_layers_double_all_six(self):
        old=list(wf_dsl.iter_dsl_commands(self.original,'ConditionalsProbability'))
        new=list(wf_dsl.iter_dsl_commands(self.new,'ConditionalsProbability'))
        self.assertEqual(len(new),6)
        for a,b in zip(old,new):
            for before,after in zip(a[1][1],b[1][1]):
                self.assertEqual(before[1][0],after[1][0])
                gate=after[1][1][1][0][1]
                self.assertEqual(gate[:3],['ConditionalsConditionAccumulationNumber',['DCUnique',13999101],6])
                self.assertEqual(gate[4],before[1][1])
                self.assertNotEqual(gate[3],gate[4])
        self.assertEqual(self.original,['Block',K.build_roulette()])

    def test_reward_values_and_durations(self):
        wheel=next(wf_dsl.iter_dsl_commands(self.new,'ConditionalsProbability'))
        gains=[o[1][1][1][0][1][3][1][0][1] for o in wheel[1][1]]
        attack,fever,pierce,direct,combo,gauge=gains
        for condition in (attack,direct):
            self.assertEqual(condition[2][0][1],[{'min':900,'max':900}])
            self.assertEqual(condition[2][0][2],[{'min':10,'max':10}])
        self.assertEqual(pierce[2][0][1],[{'min':1800,'max':1800}])
        self.assertEqual(fever[1],[{'min':500,'max':500}])
        self.assertEqual(combo[1],[{'min':1000,'max':1000}])
        self.assertEqual(gauge[2],34)
        self.assertEqual(next(wf_dsl.iter_dsl_commands(gauge,'AddSkillPoint'))[2],[{'min':.3,'max':.3}])

    def test_reapplying_cannot_silently_quadruple_rewards(self):
        with self.assertRaises(ValueError):F.apply(self.new)

if __name__=='__main__':unittest.main()
