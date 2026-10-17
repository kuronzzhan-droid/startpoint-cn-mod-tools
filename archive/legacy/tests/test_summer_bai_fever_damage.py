"""针对原生 Fever 真分支定位和非目标攻击保护的回归检查。"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
from wf_character_revision import encode_tree
from wf_summer_bai_fever_damage import fever_damage


def attack(target, minimum, maximum):
    return ["CreateNormalAttack", target, 255, [], [], 100,
            [{"min": minimum, "max": maximum}], [{"min": 0, "max": 0}],
            False, False, False, False, False, [{"min": 8, "max": 8}],
            [{"min": 3, "max": 3}], ["Coarse"], True]


def area(minimum, maximum):
    return ["CreateHitArea", "*", -1, ["AB"], 0, 0, 0, False, False,
            ["Rectangle", [{"min": 1500, "max": 1500}], [{"min": 2000, "max": 2000}]],
            ["Center"], ["Center"], ["Single"], ["SpecifyHitAreaLifetimeDirectly", 10],
            ["CalculatedUsingMaxNumOfHits", 1], ["Some", [{"min": 1, "max": 1}]],
            False, False, ["None"], 30, ["Block", []], 31, 32,
            ["Block", [["Command", attack(32, minimum, maximum)],
                       ["Command", ["ShakeCamera", 2]]]], 2, 0, ["None"]]


def fixture(level):
    # 同名攻击同时置于普通段、强化段和 Fever 假分支，避免全局倍率替换。
    regular = ["Command", area(3, 3.5)]
    enhanced = ["Command", ["ConditionalsChangeSkillFlag", 1,
                            ["Block", [["Command", area(35, 40)]]], ["Block", []]]]
    fever = ["Command", ["ConditionalsFeverMode",
             ["Block", [["Command", area(50, 50 if level == 1 else 60)]]],
             ["Block", [["Command", area(9, 11)]]]]]
    return ["ActionDsl", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            ["Block", [regular, enhanced, fever]]]


def differences(left, right, path=()):
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [change for i, (a, b) in enumerate(zip(left, right))
                for change in differences(a, b, path + (i,))]
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return [change for key in left for change in differences(left[key], right[key], path + (key,))]
    return [] if left == right else [(path, left, right)]


class SummerFeverDamageTests(unittest.TestCase):
    def test_only_true_branch_magnification_changes_in_both_levels(self):
        for level in (1, 2):
            original = fixture(level)
            before = deepcopy(original)
            revised = fever_damage(original, level)
            expected_prefix = (11, 1, 2, 1, 1, 1, 0, 1, 23, 1, 0, 1, 6, 0)
            self.assertEqual(differences(before, revised), [
                (expected_prefix + ("min",), 50, 75),
                (expected_prefix + ("max",), 50 if level == 1 else 60, 75)])
            self.assertEqual(original, before)

    def test_amf_storage_roundtrip_and_idempotence(self):
        revised = fever_damage(fixture(2), 2)
        decoded = wf_dsl.parse_dsl(zlib.decompress(encode_tree(revised), -15))["tree"]
        self.assertEqual(decoded, revised)
        self.assertEqual(fever_damage(decoded, 2), revised)

    def test_unknown_old_magnification_fails_closed(self):
        tree = fixture(2)
        tree[11][1][2][1][1][1][0][1][23][1][0][1][6][0]["max"] = 61
        with self.assertRaisesRegex(ValueError, "magnification"):
            fever_damage(tree, 2)

    def test_changed_native_reference_or_multi_hit_is_rejected(self):
        for column, replacement in ((24, 0), (15, ["Some", [{"min": 2, "max": 2}]])):
            tree = fixture(2)
            tree[11][1][2][1][1][1][0][1][column] = replacement
            with self.assertRaisesRegex(ValueError, "geometry, hit count or damage reference"):
                fever_damage(tree, 2)

    def test_multiple_fever_branches_are_not_silently_patched(self):
        tree = fixture(1)
        tree[11][1].append(deepcopy(tree[11][1][2]))
        with self.assertRaisesRegex(ValueError, "exactly one native Fever"):
            fever_damage(tree, 1)

    def test_foreign_level_or_missing_fever_rejected(self):
        with self.assertRaises(ValueError):
            fever_damage(fixture(1), 3)
        tree = fixture(1)
        tree[11][1].pop()
        with self.assertRaises(ValueError):
            fever_damage(tree, 1)


if __name__ == "__main__":
    unittest.main()
