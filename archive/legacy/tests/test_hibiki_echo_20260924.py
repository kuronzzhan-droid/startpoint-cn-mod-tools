"""澄波响发动计数、追加PF配对及回响合层契约。"""
import unittest

from test_midautumn_kit_hibiki import K, _BASELINE, assembled_rows


@unittest.skipUnless(_BASELINE, "official/live baseline unavailable")
class EchoActivationTests(unittest.TestCase):
    def test_echo_uses_activation_count_and_merges_two_stacks(self):
        leader, _ = assembled_rows()
        echo, = [r for r in leader if r[45] == "461"]
        self.assertEqual([echo[c] for c in (4, 11, 18, 25, 28, 29, 32, 33)],
                         ["0", "0", "0", "2", "300000", "300000", "(None)", "0"])
        # strength=1, number=1, initial_multiply=2: one existing condition, two levels.
        self.assertEqual([echo[c] for c in (46, 49, 50, 57, 58, 66, 72, 73)],
                         ["0", "100000", "100000", "100000", "100000", K.UID, "2", "0"])

    def test_each_additional_pf_has_exactly_one_matching_counter(self):
        leader, _ = assembled_rows()
        invokes = [r for r in leader if r[45] == "629"]
        counters = [r for r in leader if r[45] == "248"]
        self.assertEqual(len(invokes), 2)
        self.assertEqual(len(counters), 2)
        for invoke in invokes:
            counter, = [r for r in counters if r[25] == invoke[25]]
            # Active preconditions and trigger parameters (including cooldown/puller).
            columns = (4, 11, 18, 25, 26, 28, 29, 32, 33)
            if invoke[4] == "2":
                columns += (7, 8, 9, 27)
            self.assertEqual([counter[c] for c in columns], [invoke[c] for c in columns])
            self.assertEqual(counter[49:51], ["100000", "100000"])
        self.assertEqual({r[25]: r[33] for r in counters}, {"23": "0", "4": "90"})
        self.assertTrue(all(r[25] != "2" for r in counters), "no PF-to-PF counter recursion")

    def test_old_party_attack_removed_and_self_hit_growth_preserved(self):
        leader, _ = assembled_rows()
        hits = [r for r in leader if r[25] == "15"]
        self.assertEqual(len(hits), 1)
        # 2026-09-27 第二批平衡：仍不限次（c32=(None)），强度 50% → 5%（3 分钟约 30–75 次 ⇒ ×1/10）；
        # 第三轮（成长复核）按 2/3 回调：5% → 35%。
        self.assertEqual([hits[0][c] for c in (28, 29, 32, 45, 46, 49, 50)],
                         ["400000", "400000", "(None)", "32", "0", "35000", "35000"])
        self.assertNotIn("最多10次", K.PANEL_LEADER)
        self.assertIn("每发动3次强化弹射（含额外触发）", K.PANEL_LEADER)


if __name__ == "__main__":
    unittest.main()
