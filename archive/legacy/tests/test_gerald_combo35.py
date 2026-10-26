import unittest
import wf_mod_tool as core
from wf_gerald_combo35 import revise


def baseline():
    fields={0:'unicorn_lancer_rose_4',1:'true',2:'attack_common',3:'0',5:'0',6:'202',
            13:'2',16:'600000',17:'600000',18:'Blue',20:'0',27:'12',30:'5000000',
            31:'5000000',34:'8',35:'0',39:'(None)',46:'0',47:'32',48:'0',51:'25000',52:'25000'}
    attack=[fields.get(i,'') for i in range(126)]
    charge=attack.copy()
    charge[34]='(None)';charge[47]='211';charge[51:53]=['10000','10000']
    return [attack,charge]


class GeraldCombo35Test(unittest.TestCase):
    def test_threshold_cap_and_charge(self):
        before=baseline();after=core.read_csv_lines(revise(core.write_csv_lines(before)))
        self.assertEqual(after[0][30:32],['3500000','3500000'])
        self.assertEqual(after[1][30:32],['3500000','3500000'])
        self.assertEqual(after[0][34],'10')
        self.assertEqual(after[0][51:53],['25000','25000'])
        self.assertEqual(after[1][34],'(None)')
        self.assertEqual(after[1][51:53],['5000','5000'])
        allowed=({30,31,34},{30,31,51,52})
        for n,(old,new) in enumerate(zip(before,after)):
            self.assertTrue(all(a==b for i,(a,b) in enumerate(zip(old,new)) if i not in allowed[n]))

    def test_idempotent(self):
        once=revise(core.write_csv_lines(baseline()))
        self.assertEqual(revise(once),once)

    def test_condition_drift_is_rejected(self):
        for col in (6,13,16,18,27,47):
            rows=baseline();rows[0][col]='0'
            with self.assertRaises(ValueError):revise(core.write_csv_lines(rows))

    def test_partial_change_is_rejected(self):
        rows=baseline();rows[0][30]='3500000'
        with self.assertRaises(ValueError):revise(core.write_csv_lines(rows))


if __name__=='__main__':unittest.main()
