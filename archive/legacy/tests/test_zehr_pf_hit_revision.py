import json
from copy import deepcopy
from pathlib import Path
import unittest

from wf_character_revision import encode_tree
from wf_zantetsu_fever_revision import nodes
from wf_zehr_pf_hit_revision import revise, HIT


class ZehrPfHitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = json.loads((Path(__file__).parent/'fixtures/zehr_pf_hit_before.json').read_bytes())

    def test_only_spin_multiplier_changes_on_all_levels(self):
        for level in (1,2,3):
            source = self.before[str(level)]
            original = deepcopy(source)
            updated = revise(source,level)
            attack = nodes(updated,'CreateNormalAttack')[0]
            self.assertEqual(attack[6],[dict(min=HIT[level],max=HIT[level])])
            self.assertAlmostEqual(attack[6][0]['min']/nodes(source,'CreateNormalAttack')[0][6][0]['min'],1.35)
            self.assertEqual(revise(updated,level),updated)
            encode_tree(updated)
            attack[6] = deepcopy(nodes(source,'CreateNormalAttack')[0][6])
            self.assertEqual(updated,source)  # Timing/range/effects/finisher/break/Fever untouched.
            self.assertEqual(original,source)

    def test_exact_new_values_and_lv3_finisher(self):
        self.assertEqual(HIT,{1:19.74375,2:28.85625,3:38.2725})
        tree = revise(self.before['3'],3)
        self.assertEqual(nodes(tree,'CreateNormalAttack')[1][6],[dict(min=4,max=4)])

    def test_drift_is_rejected_instead_of_rescaling_repeatedly(self):
        for kind in ('hits','multiplier'):
            source = deepcopy(self.before['2'])
            if kind == 'hits':
                nodes(source,'CreateHitArea')[0][14][1]=12
            else:
                nodes(source,'CreateNormalAttack')[0][6][0]['min']=99
            with self.assertRaises(ValueError):
                revise(source,2)


if __name__ == '__main__':
    unittest.main()
