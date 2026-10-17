import json
from pathlib import Path
import unittest
from copy import deepcopy

from wf_zehr_pf5_cooldown import revise_rows, compact_text


class ZehrPF5Test(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads((Path(__file__).parent/'fixtures/zehr_pf5_before.json').read_bytes())

    def test_only_lv3_counter_and_cooldown_change(self):
        before = deepcopy(self.rows)
        after = revise_rows(self.rows)
        self.assertEqual(before, self.rows)
        changed = [(i,j) for i,(a,b) in enumerate(zip(before,after))
                   for j,(x,y) in enumerate(zip(a,b)) if x != y]
        self.assertEqual(changed, [(1,30),(1,31),(1,35)])
        self.assertEqual(after[1][27:32], ['65','','','500000','500000'])
        self.assertEqual(after[1][35], '300')
        self.assertEqual(after[1][47:53], ['211','5','White','','5000','5000'])
        self.assertEqual(after[1][6:12], ['2','','','600000','600000','White'])
        self.assertEqual(after[0], before[0])

    def test_idempotency_and_unrelated_drift_rejection(self):
        after = revise_rows(self.rows)
        self.assertEqual(revise_rows(after), after)
        for col,value in [(35,'60'),(27,'2'),(49,'Blue'),(51,'10000')]:
            bad = deepcopy(self.rows); bad[1][col] = value
            with self.assertRaises(ValueError): revise_rows(bad)

    def test_text_keeps_duration_and_does_not_add_cooldown(self):
        self.assertEqual(compact_text('灯火正旺12秒（每5秒1次）'), '灯火正旺12秒（CT 5s）')
        plain = '每达成15连击，攻击力＋25%（最多10次）'
        self.assertEqual(compact_text(plain), plain)


if __name__ == '__main__': unittest.main()
