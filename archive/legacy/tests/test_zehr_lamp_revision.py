import json
from copy import deepcopy
from pathlib import Path
import unittest

import wf_zehr_lamp_revision as R


class LampTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent/'fixtures/zehr_lamp_before.json').read_bytes())
        self.a, self.b = self.data['a1'], self.data['a3']

    def test_resonance_combo_replaces_flip_and_rewards_stay_in_sync(self):
        a, b = R.revise_rows(self.a, self.b)
        grants = [r for r in a if r[47] == '461']
        gains = [r for r in b if r[5] == '0' and r[47] in ('32', '55')]
        self.assertEqual(len(grants+gains), 4)
        for r in grants+gains:
            self.assertEqual(r[6:12], ['2','','','600000','600000','White'])
            self.assertEqual(r[27], '12')
            self.assertEqual(r[30:32], ['5500000']*2)
            self.assertEqual(r[35], '300')
        self.assertEqual(len(a), len(self.a)-1)
        self.assertEqual(a[0], self.a[1])  # opening gauge untouched
        self.assertEqual(a[1], self.a[2])  # skill enhancement untouched
        self.assertEqual(a[-1], self.a[-1])  # wick multiplier untouched

    def test_growth_is_current_combo_not_permanent_stacks(self):
        a, b = R.revise_rows(self.a, self.b)
        r = b[-1]
        self.assertEqual(r[5], '1')
        self.assertEqual(r[6:13], self.b[5][6:13])
        self.assertEqual(r[97:103], ['2','','','100000','100000','(None)'])
        self.assertEqual(r[109], '23')
        self.assertEqual(r[113:115], ['5000']*2)
        # Match native floor(combo/1) multiplier; dropping combo removes growth.
        for combo, expected in [(0,0), (35,1.75), (55,2.75), (9999,499.95)]:
            self.assertAlmostEqual((combo//(int(r[100])/100000))*int(r[113])/100000, expected)
        self.assertEqual(b[4][113:115], ['15000']*2)
        self.assertEqual(b[5][30:32], ['3500000']*2)
        self.assertEqual(b[5][51:53], ['1500000']*2)
        self.assertEqual(b[1:3], self.b[1:3])  # dash untouched

    def test_duration_and_text(self):
        self.assertEqual(R.revise_unique(self.data['unique'])[0][3], '900')
        one, three = (R.revise_text(s, self.data['text'+str(s)]) for s in (1,3))
        self.assertNotIn('自身攻击力＋150%', one)
        self.assertIn('共鸣时，每达成55连击', one)
        self.assertIn('15秒', one)
        self.assertIn('额外乘区＋15%', three)
        self.assertIn('每达成35连击，连击＋15', three)
        self.assertIn('强化弹射伤害随连击数提高', three)
        self.assertNotIn('每1连击', three)
        self.assertNotIn('上限', three)

    def test_idempotent_and_input_not_mutated(self):
        original = deepcopy(self.data)
        a, b = R.revise_rows(self.a, self.b)
        self.assertEqual(R.revise_rows(a,b), (a,b))
        self.assertEqual(self.data, original)
        for s in (1,3):
            text = R.revise_text(s,self.data['text'+str(s)])
            self.assertEqual(R.revise_text(s,text),text)

    def test_migrates_published_two_percent_without_changing_other_fields(self):
        a, b = R.revise_rows(self.a, self.b)
        b[-1][113:115] = ['2000']*2
        before = deepcopy(b)
        new_a, new_b = R.revise_rows(a, b)
        self.assertEqual(new_a, a)
        self.assertEqual(new_b[:-1], before[:-1])
        self.assertEqual(new_b[-1][:113], before[-1][:113])
        self.assertEqual(new_b[-1][115:], before[-1][115:])
        self.assertEqual(new_b[-1][113:115], ['5000']*2)
        old = R.ICON+'持有「灯火正旺」期间，每1连击，强化弹射伤害＋2%'
        new = R.revise_text(3, old)
        self.assertEqual(new, R.ICON+'持有「灯火正旺」期间，强化弹射伤害随连击数提高')


if __name__ == '__main__':
    unittest.main()
