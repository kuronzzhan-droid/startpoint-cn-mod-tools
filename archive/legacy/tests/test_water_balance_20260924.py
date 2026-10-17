from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_water_balance_20260924 as B
import wf_dsl
from wf_client_legality import client_legality_problems
from wf_midautumn_kit_hibiki import dsl_problems

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'water_balance_20260924.json'


class WaterBalanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(FIXTURE.read_bytes())['rows']

    def test_yuki_separate_combo_thresholds_and_targets(self):
        out = B.yuki_rows(self.rows['1299912'])
        self.assertEqual(self.rows['1299912'][0], out[0])
        self.assertEqual(['10000000', '10000000'], out[1][30:32])
        self.assertEqual(['211', '1', 'Blue'], out[1][47:50])
        self.assertEqual(['5000']*2, out[1][51:53])
        self.assertEqual(['7500000']*2, out[2][30:32])
        self.assertEqual(['252', '0', ''], out[2][47:50])
        self.assertEqual(['800000']*2, out[2][51:53])  # 2026-09-27：10 → 8 倍（×0.8）
        for row in out:
            self.assertEqual('Blue', row[11])
            self.assertEqual('600000', row[9])
            self.assertEqual('0', row[35])  # No added cooldown.

    def test_gerald_skill_cast_trigger_resonance_and_no_opening_gauge(self):
        rows = B.gerald_rows('1299921', self.rows['1299921'])
        self.assertEqual(1, len(rows))
        r = rows[0]
        self.assertEqual(('2', '600000', 'Blue', '23', '0', '629'),
                         tuple(r[i] for i in (6, 9, 11, 27, 28, 47)))
        self.assertEqual([B.STRIKE_KEY, B.STRIKE_PROGRAM], r[70:72])

    def test_water_party_ability_damage_and_self_independent_terms(self):
        a2 = B.gerald_rows('1299922', self.rows['1299922'])
        self.assertEqual(self.rows['1299922'], a2[:-1])
        self.assertEqual(['388', '5', 'Blue'], a2[-1][47:50])
        self.assertEqual(['200000']*2, a2[-1][51:53])
        a5 = B.gerald_rows('1299925', self.rows['1299925'])
        # 2026-09-27：行1 全体 252 只改 c51/c52 15 → 12 倍（×0.8），其余逐字保留。
        self.assertEqual([51, 52], [i for i, (x, y) in enumerate(zip(self.rows['1299925'][0], a5[0])) if x != y])
        self.assertEqual(['252', '1500000'], [self.rows['1299925'][0][47], self.rows['1299925'][0][51]])
        self.assertEqual(['1200000']*2, a5[0][51:53])
        self.assertEqual(['694', '695'], [r[47] for r in a5[1:]])
        for r in a5[1:]:
            self.assertEqual('0', r[48])
            self.assertEqual(['20000']*2, r[51:53])

    def test_preimage_drift_is_rejected_and_input_preserved(self):
        for key, old in self.rows.items():
            original = deepcopy(old)
            fn = B.yuki_rows if key == '1299912' else lambda r: B.gerald_rows(key, r)
            fn(old)
            self.assertEqual(original, old)
            old = deepcopy(old); old[0][1] = 'false'
            with self.assertRaises(ValueError): fn(old)

    def test_native_rows_are_legal(self):
        for key, old in self.rows.items():
            rows = B.yuki_rows(old) if key == '1299912' else B.gerald_rows(key, old)
            for row in rows:
                self.assertEqual([], client_legality_problems('ability', row))

    def test_single_nearest_combo_ability_strike(self):
        tree = B.strike_tree()
        self.assertEqual(102, tree[10])
        find = list(wf_dsl.iter_dsl_commands(tree, 'FindNearSubjects'))
        self.assertEqual([-18, 1, 49, ['DoNothing'], 0], find[0][1:6])
        hits = list(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))
        self.assertEqual(1, len(hits))
        self.assertEqual(0, hits[0][1])
        self.assertEqual([{'min': 36, 'max': 36}], hits[0][6])  # 2026-09-27：45 → 36（×0.8）
        self.assertIn('36倍', B.STRIKE_TEXT)
        self.assertTrue(hits[0][8])
        self.assertEqual([], dsl_problems(tree, element=None))
        B.encode_tree(tree)

    def test_skill75_keeps_all_hits_and_combo_bonus(self):
        old = json.loads(FIXTURE.read_bytes())['tree']
        result = B.skill_tree(old)
        oldhits = list(wf_dsl.iter_dsl_commands(old, 'CreateNormalAttack'))
        hits = list(wf_dsl.iter_dsl_commands(result, 'CreateNormalAttack'))
        self.assertAlmostEqual(75, 10*hits[0][6][0]['max']+9*hits[1][6][0]['max']+hits[2][6][0]['max'])
        for a, b in zip(oldhits, hits):
            self.assertTrue(b[8]); b[6] = deepcopy(a[6])
        self.assertEqual(old, result)  # Nothing else is scaled or removed.
