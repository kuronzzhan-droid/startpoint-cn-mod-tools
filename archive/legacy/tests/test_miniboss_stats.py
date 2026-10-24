"""官方面板断点、整数缩放与角色定位不改变六能力预算。"""
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core
from wf_miniboss_roster import ROSTER
from wf_miniboss_stats import TARGETS, CURVE_DONOR, status_row, metadata


class MinibossStatsTests(unittest.TestCase):
    @staticmethod
    def official():
        # Actual official 111001 values, independently read from official CDN.
        row = core.encode_status_row([("1", 53, 11), ("10", 532, 112),
                                      ("80", 3192, 672), ("100", 3511, 739)])
        return core.build_orderedmap_raw_rows(core.OrderedMap("status", [CURVE_DONOR], [row], Path(".")))

    def test_all_fifteen_targets_and_native_breakpoints(self):
        self.assertEqual(set(TARGETS), {char.cid for char in ROSTER})
        for cid, target in TARGETS.items():
            entries = core.decode_status_row(status_row(cid, self.official()))
            self.assertEqual([level for level, _, _ in entries], ["1", "10", "80", "100"])
            self.assertEqual(entries[-1][1:], target)
            self.assertTrue(all(a[1] < b[1] and a[2] < b[2] for a, b in zip(entries, entries[1:])))
            self.assertEqual(metadata(cid)["damage_bonus_budget_offset"], 0)

    def test_tank_and_healer_trade_base_attack_for_survival(self):
        self.assertGreater(TARGETS["159999"][0], TARGETS["169993"][0])
        self.assertLess(TARGETS["129996"][1], TARGETS["149994"][1])

    def test_official_curve_ratios_with_only_integer_rounding(self):
        entries = core.decode_status_row(status_row("169993", self.official()))
        self.assertEqual(entries[0], ("1", 54, 15))
        self.assertEqual(entries[1], ("10", 545, 149))
        self.assertEqual(entries[2], ("80", 3273, 891))


if __name__ == "__main__":
    unittest.main()
