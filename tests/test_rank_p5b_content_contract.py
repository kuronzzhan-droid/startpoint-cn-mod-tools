#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rank P5b share-package content contract.

These assertions intentionally live outside the generic share-variant fixtures:
the production package must fail if the older three-character contract is ever
used for the 2026-08-29 Gray delivery.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


MOD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as policy_mod  # noqa: E402
import wf_share_variant as share_mod  # noqa: E402


BOSS_IDS = ("169994", "169980", "179981", "169995")
BOSS_ABILITIES = tuple(
    f"{character_id}{index}"
    for character_id in BOSS_IDS
    for index in range(1, 7)
)
BOSS_ACTIONS = (
    "white_tiger_ghost_playable",
    "abyss_beast_playable",
    "cnmod_epuration_empress",
    "maou2_playable",
)
BOSS_POWER_FLIPS = tuple(f"{name}_pf" for name in BOSS_ACTIONS)
DEGREE_IDS = tuple(str(value) for value in range(9_900_002, 9_900_007))


class RankP5bContentContractTest(unittest.TestCase):
    def test_expected_rows_cover_all_four_bosses_and_their_combat_contract(self):
        expected = policy_mod.EXPECTED_CONTENT_ROWS
        for logical in (
            "master/character/character.orderedmap",
            "master/character/character_status.orderedmap",
            "master/character/character_text.orderedmap",
            "master/ability/leader_ability.orderedmap",
            "master/mana_board/mana_node.orderedmap",
        ):
            self.assertTrue(set(BOSS_IDS).issubset(expected[logical]), logical)
        self.assertTrue(set(BOSS_ABILITIES).issubset(
            expected["master/ability/ability.orderedmap"]))
        self.assertTrue(set(BOSS_ACTIONS).issubset(
            expected["master/skill/action_skill.orderedmap"]))
        self.assertTrue(set(BOSS_POWER_FLIPS).issubset(
            expected["master/skill/power_flip_action.orderedmap"]))

    def test_expected_rows_cover_gacha_degrees_and_veteran_shop_entry(self):
        expected = policy_mod.EXPECTED_CONTENT_ROWS
        self.assertEqual(("990002",), expected["master/gacha/gacha.orderedmap"])
        self.assertEqual(("990002",),
                         expected["master/gacha/gacha_feature_content.orderedmap"])
        self.assertEqual(DEGREE_IDS, expected["master/degree/degree.orderedmap"])
        self.assertIn("9700118", expected["master/shop/event_item_shop.orderedmap"])
        self.assertIn("999015", expected["master/item/item.orderedmap"])
        self.assertIn("999016", expected["master/item/item.orderedmap"])

    def test_every_rank_p5b_expected_row_is_classified_as_custom_content(self):
        policy = policy_mod.Policy()
        for logical, keys in policy_mod.EXPECTED_CONTENT_ROWS.items():
            for key in keys:
                self.assertTrue(
                    policy.is_content_key(logical, key),
                    f"{logical}:{key} was not classified as custom content",
                )

    def test_share_variant_description_names_the_current_four_bosses(self):
        for variant, description in share_mod.VARIANT_DESC.items():
            for character_id in BOSS_IDS:
                self.assertIn(character_id, description, f"{variant}:{character_id}")
            self.assertNotIn("三自制角色", description)


if __name__ == "__main__":
    unittest.main()
