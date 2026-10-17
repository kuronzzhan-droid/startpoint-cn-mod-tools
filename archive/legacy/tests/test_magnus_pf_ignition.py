"""狮子 A3：每三次任意等级 PF，将三层计入现有点火状态。"""
import unittest
from test_midautumn_kit_magnus import _LIVE, _ReadOnlyCtx, KM, KL


@unittest.skipUnless(_LIVE, 'requires official table fixtures')
class MagnusPfIgnitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = _ReadOnlyCtx()
        cls.rows = [KL.build_row(cls.ctx, 'ability', donor, cells, source=source,
                    element=0, expect_describe=text)[0]
                    for donor, source, cells, text in KM.PLAN[3]]

    def test_new_gain_is_all_level_pf_three_under_fire_and_main_gate(self):
        row, = [r for r in self.rows if r[27] == '2' and r[47] == '461']
        self.assertEqual((row[1], row[2]), ('false', 'action_skill'))
        self.assertEqual((row[6], row[9], row[10], row[11]), ('2', '600000', '600000', 'Red'))
        self.assertEqual((row[28], row[30], row[31], row[34], row[35]),
                         ('0', '300000', '300000', '(None)', '0'))
        self.assertEqual((row[48], row[68], row[74]), ('0', KM.UID, '3'))

    def test_existing_identity_and_number_preserved_instead_of_second_icon(self):
        old = self.rows[0]
        new = self.rows[-1]
        for column in (47, 48, 51, 52, 59, 60, 68):
            self.assertEqual(new[column], old[column], column)
        self.assertEqual(new[59:61], ['100000', '100000'])
        self.assertEqual(old[74], '1')
        self.assertEqual(new[74], '3')
        KM._order_problems(self.rows)
        KL.check_ability_key(self.rows, f'{KM.CID}3', KM.CODE, 3)

    def test_panel_retains_old_rules_and_explains_new_trigger(self):
        lines = KM.CAS_TEXTS[KM.SLOT_OVERRIDE[3]].splitlines()
        self.assertEqual(len(lines), 6)
        self.assertIn('技能时，自身引擎点火＋1层', lines[0])
        self.assertEqual(lines[-1], KM.MAIN_ICON+'火属性共鸣时，每发动3次强化弹射，自身引擎点火＋3层')


if __name__ == '__main__':
    unittest.main()
