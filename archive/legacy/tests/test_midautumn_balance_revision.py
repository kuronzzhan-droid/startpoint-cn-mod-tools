"""Author's 2026-09-21 changes, verified against assembled native rows."""
import unittest

import wf_midautumn_kit_kyle as K
import wf_midautumn_kit_kuro as U
import wf_midautumn_kit_fluffy as F
import wf_midautumn_kit_hibiki as H
from tests.test_midautumn_kit_kyle import ctx


class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = K.build_rows(ctx())

    def test_pierce_bonus_moves_to_leader_once_without_changing_trigger(self):
        leader = [r for r in self.rows['leader'] if r[25] == '51']
        self.assertEqual(len(leader), 1)
        row = leader[0]
        self.assertEqual(len(row), 124)
        self.assertEqual((row[4], row[7], row[9]), ('2', '600000', 'Yellow'))
        self.assertEqual((row[28], row[32], row[45], row[46], row[47], row[49]),
                         ('100000', '(None)', '32', '5', 'Yellow', '50000'))
        self.assertFalse(any(r[27] == '51' for r in self.rows['ability']['1399902']))
        self.assertEqual([r[113] for r in self.rows['ability']['1399902']], ['50000', '50000'])

    def test_only_crescent_production_counter_changes(self):
        gain = [r for r in self.rows['ability']['1399903']
                if r[27] == '20' and r[68] == K.UID_CRESCENT]
        self.assertEqual(len(gain), 1)
        self.assertEqual(gain[0][30:32], ['10000000', '10000000'])
        # 2026-09-27 平衡批次删去同触发的雷队 Stunify 行，只剩充能 +5%
        self.assertEqual([r[30] for r in self.rows['ability']['1399905'] if r[27] == '20'],
                         ['5000000'])

    def test_dice_threshold_and_cap(self):
        gains = [c for _, c, _ in U.ABILITY['1399913'] if c.get(68) == U.UID_DICE]
        self.assertEqual(len(gains), 1)
        self.assertEqual((gains[0][30], gains[0][31], U.DICE_CAP),
                         ('100000000', '100000000', '6'))

    def test_hibiki_removes_only_swift_grant_and_keeps_base_cooldown(self):
        rows = H.build_rows(ctx())
        self.assertFalse(any(r[45] == '31' for r in rows['leader']))
        dash = [r for r in rows['ability']['1699885'] if r[109] == '422']
        cooldown = [r for r in dash if r[118] == '0']
        self.assertEqual(len(cooldown), 2)
        self.assertEqual([(r[97], r[113]) for r in cooldown], [('1', '-30000'), ('34', '245000')])
        self.assertEqual(sorted(r[118] for r in dash), ['0', '0', '1', '3', '6'])
        self.assertNotIn('强化弹射后获得冲刺', H.PANEL_LEADER)
        self.assertIn('冷却时间−30%', H.PANEL_LEADER)

    def test_swift_keeps_ground_dash_time_for_all_three_leaders(self):
        for kit, base in [(K, -.5), (H, -.3), (F, 0)]:
            guards = [c for _, _, c, _ in kit.PLAN[5] if c.get(97) == '34']
            self.assertEqual(len(guards), 1)
            c = guards[0]
            self.assertEqual((c[6], c[109], c[118]), ('42', '422', '0'))
            self.assertAlmostEqual(90 * (1 + base), 20 * (1 + base + int(c[113]) / 100000))
        self.assertEqual(F.PLAN[5][-1][2][18], 'Green')


if __name__ == '__main__':
    unittest.main()
