"""Native count changes and ordinary split-buff damage stay independent."""
import sys
from pathlib import Path
import unittest
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_nephtim_ball_hit_count as H
import wf_nephtim_fever_leader as leader
from test_bianca_dragon_abilities import official_sources
from wf_nephtim_fever import validate_program
from test_nephtim_fever_skill import nodes
import wf_client_legality as L


class BallHitCountTest(unittest.TestCase):
    def test_single_self_record_dynamic_count_and_expiring_skill_multiplier(self):
        tree = H.action_tree()
        validate_program(tree)
        self.assertFalse(L.action_dsl_lookup_scope_problems(tree))
        self.assertFalse(nodes(tree, 'Event'))
        count = nodes(tree, 'MultiballNumberVariable')[0]
        self.assertIsNone(count[3])  # count every surviving multiball id
        branch = nodes(tree, 'ConditionalsConditionExist')[0]
        self.assertEqual(branch[1:3], [-17, ['DCAdditionalDirectAttack']])
        for ordinary_split in (False, True):
            condition = nodes(branch[3 if ordinary_split else 4], 'CreateCondition')[0]
            self.assertEqual(condition[1], -17)
            self.assertTrue(condition[9])  # invisible, excluded by the visible buff query
            self.assertEqual(condition[7], H.STRING_ID)
            content = condition[2][0]
            for n in (0, 1, 3, 9, 3, 1, 0):
                times = sum(v['min'] * (n if v.get('mul') else 1) for v in content[2])
                total = 1 + content[3][0]['min']
                self.assertEqual(times, n + (2 if ordinary_split else 1))
                self.assertEqual(total, 2 if ordinary_split else 1)
            # 作者 2026-09-27 多人卡顿修复：持续帧 2 → 20（= 2 × 刷新周期 10 帧）。
            self.assertEqual(content[1], [{'min': 20, 'max': 20}])
        self.assertEqual((10, 20), (H.UPDATE_PERIOD_FRAMES, H.TTL_FRAMES))

    def test_leader_row_refreshes_every_ten_frames(self):
        row = H.leader_row(official_sources()[0])
        self.assertEqual(124, len(row))
        # 队长表列位 = 能力表 −2：T77 在 c25，阈值 c28/c29（帧 × 100000）。
        self.assertEqual(('77', '1000000', '1000000', '(None)', '0', '629', H.STRING_ID, H.ACTION_PATH),
                         (row[25], row[28], row[29], row[32], row[33], row[45], row[68], row[69]))
        # 作者 2026-09-27 第二批：队长末尾追加两条贯穿成长（第9、10行），本行固定在第8行。
        self.assertEqual(row, leader.leader_rows(official_sources()[0])[7])
        meta = leader.metadata()['ball_hit_count']
        self.assertEqual((77, 10, 20), (meta['trigger'], meta['update_period_frames'],
                                        meta['condition_duration_frames']))


if __name__ == '__main__':
    unittest.main()
