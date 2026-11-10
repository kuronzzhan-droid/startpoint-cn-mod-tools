"""Additive per-floor ban policy; no tower generation or client/resource writes."""
import copy
import itertools
import random
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import rogue_build as rb
import wf_dsl


def card(elements, strength=99.0, name="原有元素诅咒"):
    return {"name": name, "text": "原有描述", "element_resistance": [(e, strength, False) for e in elements]}


def independent_totals(picks):
    totals = dict.fromkeys(range(1, 7), 0.0)
    for pick in picks:
        for atom in pick.get("element_resistance", []):
            totals[atom[0]] += atom[1]
    return totals


class ElementBanPolicyCase(unittest.TestCase):
    def test_all_existing_subsets_keep_original_cards_and_two_to_five_bans(self):
        for size in range(6):
            for subset in itertools.combinations(range(1, 7), size):
                for seed in range(15):
                    original = [card(subset)] if subset else []
                    before = copy.deepcopy(original)
                    result, receipt = rb.guarantee_element_bans(original, random.Random(seed))
                    self.assertEqual(original, before)
                    self.assertEqual(result[:len(original)], before)
                    actual = {e for e, value in independent_totals(result).items() if value >= 99}
                    self.assertEqual(len(actual), max(2, size))
                    self.assertTrue(set(subset) <= actual)
                    self.assertEqual(receipt["final_banned"], sorted(actual))
                    self.assertEqual(receipt["ordinary_slots_consumed"], 0)
                    self.assertFalse(receipt["runtime_verified"])

    def test_half_and_tenth_damage_are_preserved_but_do_not_count_as_bans(self):
        original = [card([1, 2, 3], 1.0), card([4, 5, 6], 9.0, "三相封界")]
        result, receipt = rb.guarantee_element_bans(original, random.Random(9))
        self.assertEqual(receipt["original_banned"], [])
        self.assertEqual(result[:2], original)
        totals = independent_totals(result)
        for e in receipt["added_banned"]:
            self.assertEqual(totals[e], 999.0)
            self.assertEqual(1 / (1 + totals[e]), 0.001)
        self.assertEqual(len(receipt["open_elements"]), 4)

    def test_all_fifteen_pairs_are_reachable_and_repeatable(self):
        observed = set()
        for seed in range(500):
            a = rb.guarantee_element_bans([], rb.element_ban_rng(seed, 1))
            b = rb.guarantee_element_bans([], rb.element_ban_rng(seed, 1))
            self.assertEqual(a, b)
            observed.add(tuple(a[1]["added_banned"]))
        self.assertEqual(observed, set(itertools.combinations(range(1, 7), 2)))

    def test_no_random_draw_after_existing_minimum_and_reapplication_is_idempotent(self):
        for size in range(2, 6):
            rng = mock.Mock()
            original = [card(range(1, size + 1))]
            result, receipt = rb.guarantee_element_bans(original, rng)
            rng.sample.assert_not_called()
            self.assertEqual(result, original)
            self.assertEqual(receipt["added_banned"], [])
        result, _ = rb.guarantee_element_bans([], random.Random(2))
        self.assertEqual(rb.guarantee_element_bans(result, mock.Mock())[0], result)

    def test_same_element_is_counted_once_and_strengths_are_combined(self):
        original = [card([1], 50), card([1], 49, "另一个原有诅咒")]
        result, receipt = rb.guarantee_element_bans(original, random.Random(1))
        self.assertEqual(receipt["original_banned"], [1])
        self.assertEqual(len(receipt["added_banned"]), 1)
        self.assertNotIn(1, receipt["added_banned"])
        self.assertEqual(independent_totals(result)[1], 99)

    def test_six_bans_are_rejected_without_silently_deleting_an_original(self):
        for original in ([card(range(1, 7))], [card([1, 2, 3]), card([4, 5, 6])],
                         [card(range(1, 7), 50), card(range(1, 7), 49)]):
            before = copy.deepcopy(original)
            with self.assertRaisesRegex(ValueError, "六属性"):
                rb.guarantee_element_bans(original, random.Random(1))
            self.assertEqual(original, before)

    def test_last_open_element_can_keep_ordinary_resistance(self):
        original = [card(range(1, 6), 999), card([6], 9, "暗减伤")]
        result, receipt = rb.guarantee_element_bans(original, random.Random(1))
        self.assertEqual(result, original)
        self.assertEqual(receipt["open_elements"], [6])

    def test_damage_immunity_guard_and_other_effects_survive(self):
        original = [{"name": "复合原有诅咒", "text": "原有文案", "hp": 2.5, "atk": 1.3,
                     "cond": [("1", "0.4")], "damage_resistance": [(3, 0.5, False)]}]
        supplemented, _ = rb.guarantee_element_bans(original, random.Random(1))
        before, after = rb.apply_picks({}, original), rb.apply_picks({}, supplemented)
        for key in ("hp", "atk", "conds", "damage_resistance", "time", "casters"):
            self.assertEqual(before[key], after[key])
        with self.assertRaisesRegex(ValueError, "四种伤害类型"):
            rb.guarantee_element_bans([{"damage_resistance": [(k, 1) for k in range(4)]}], random.Random(1))

    def test_policy_does_not_claim_a_missing_boss_carrier_is_supported(self):
        picks, receipt = rb.guarantee_element_bans([], random.Random(1))
        profile = rb.resolve_curse_capabilities("standard_dsl", "standard", {"boss": False, "element": False})
        self.assertFalse(receipt["runtime_verified"])
        with self.assertRaisesRegex(ValueError, "能力矩阵"):
            rb.apply_picks({"capability_profile": profile}, picks)

    def test_full_dsl_signature_and_readback_for_all_fifteen_pairs(self):
        for pair in itertools.combinations(range(1, 7), 2):
            tree = rb.build_immunity_dsl_tree([], [(e, 999, False) for e in pair])
            blob = rb.build_immunity_dsl_blob(tree)
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"], tree)
        bad = copy.deepcopy(tree)
        bad[11][1][0][1][10] = "wrong-target-kind"
        with self.assertRaises(Exception):
            rb.build_immunity_dsl_blob(bad)

    def test_bad_minimum_or_nan_cannot_bypass_the_guards(self):
        for minimum in (-1, 6, 2.5, True, "2"):
            with self.assertRaises(ValueError):
                rb.guarantee_element_bans([], random.Random(1), minimum)
        with self.assertRaises(ValueError):
            rb.guarantee_element_bans([card([1], float("nan"))], random.Random(1))


if __name__ == "__main__":
    unittest.main()
