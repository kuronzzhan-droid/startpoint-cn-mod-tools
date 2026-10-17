"""Offline contracts for imported GBF drafts; these are not gameplay tests."""
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_gbf_duo_dsl as D
import wf_gbf_duo_rows as R
from wf_gbf_duo_kit import BLOCKERS, check_draft
from wf_gbf_soriz import transfer
import wf_seasonal7_common as C


class DraftTests(unittest.TestCase):
    def test_opening_keeps_hurt_before_barrier_and_guts(self):
        tree = D.ghandagoza_opening()
        find = C.commands(tree, 'FindAllSubjects')[0]
        nodes = find[-1][1]
        self.assertEqual(nodes[0][1], ['CreateRatioAttack', 0, 1, D.v(1)])
        self.assertEqual(nodes[1][1][0:3], ['Wait', 1, '*'])
        self.assertEqual(C.commands(nodes[1], 'CreateBarrier')[0][2], D.v(1))
        self.assertIn(['ACGuts', D.v(1)], list(C.walk(nodes[1])))
        self.assertEqual(check_draft([], {}, {'opening': tree}), [])

    def test_empty_branch_and_arity_fail_before_export(self):
        invalid = D.tree(D.cmd('CreateBarrier', 0, D.v(.5)))
        self.assertTrue(any('arity' in x for x in check_draft([], {}, {'bad': invalid})))

    def test_missing_subject_fails_before_export(self):
        invalid = D.tree(D.cmd('CreateBarrier', 777, D.v(.5), ['GenericBarrierHitEffect']))
        self.assertTrue(check_draft([], {}, {'bad': invalid}))

    def test_heat_transfer_never_clears_the_destination_first(self):
        # 完成态契约（D15）：同帧结算顺序是「赋予(8) → 删除(9)」，先删目标 = 本帧叠的层数被自己清零，
        # 余热永远 0 层。唯一允许的删除是最后那条清源。
        tree = D.tree(transfer(12998604, 12998605, clear_source=True))
        self.assertEqual(len(C.commands(tree, 'ConditionalsConditionAccumulationNumber')), 10)
        deletes = C.commands(tree, 'DeleteCondition')
        self.assertEqual([d[2] for d in deletes], [['DCUnique', 12998604]])
        self.assertEqual(check_draft([], {}, {'transfer': tree}), [])

    def test_hp_percent_threshold_units(self):
        # 队伍失血档位的完成态契约搬到 test_gbf_kit_soriz.py：官方零先例的 SumOfPartyHpLow 100 行
        # 已改成 1 行 during 110 + 来源 9 SumOfParty（D9），这里只留「每失血 1%」的单位契约。
        own = R.row(129987, 1, 'AttackPoint', 2, during=True,
                    trigger='HpDecrease', threshold=.01, start=100000)
        self.assertEqual(own[100:103], ['1000', '1000', '(None)'])
        self.assertEqual(own[105:107], ['100000', '100000'])
        self.assertEqual(check_draft([], {1:[own]}, {}), [])

    def test_soriz_is_no_longer_a_blocked_draft(self):
        # 索利兹的机制已装进包（见 tests/test_gbf_kit_soriz.py 的完成态契约）。
        self.assertNotIn('soriz', BLOCKERS)

    def test_ghandagoza_is_no_longer_a_blocked_draft(self):
        # 冈达葛萨的机制已装进包（见 tests/test_gbf_kit_ghandagoza.py 的完成态契约）。
        self.assertNotIn('ghandagoza', BLOCKERS)


if __name__ == '__main__':
    unittest.main()
