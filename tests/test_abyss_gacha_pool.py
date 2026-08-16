#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact odds-math tests for the nine-character abyss pickup pool."""

from __future__ import annotations

import unittest
from fractions import Fraction

try:
    import wf_abyss_gacha_contract as contract
    import wf_abyss_gacha_pool as pool_contract
except ImportError:
    contract = None
    pool_contract = None


STANDARD_FIVE_IDS = (111001, 111002)
LIMITED_DONOR_FIVE_ID = 111003


def _entry(character_id: int, rank: int, odds: int, *, limited: bool = False):
    return {
        "id": character_id,
        "rank": rank,
        "odds": odds,
        "isRateUp": True,
        "isLimited": limited,
        "isExchangeable": True,
        "rarity": 500.0,
        "trialReadingForced": True,
    }


def _donor_runtime() -> dict[str, object]:
    return {
        "rankRates": {"normal": [50, 250, 700], "multiGuarantee": [50, 950]},
        "pool": {
            "1": [
                _entry(STANDARD_FIVE_IDS[0], 5, 9),
                _entry(STANDARD_FIVE_IDS[1], 5, 7),
                _entry(LIMITED_DONOR_FIVE_ID, 5, 5, limited=True),
                *(
                    _entry(character_id, 5, 3)
                    for character_id in (141129, 161141, 123001, 131182)
                ),
            ],
            "2": [_entry(211001, 4, 31), _entry(221001, 4, 29)],
            "3": [_entry(311001, 3, 17), _entry(321001, 3, 13)],
        },
    }


class AbyssPickupPoolOddsTests(unittest.TestCase):
    def _require_module(self):
        if contract is None or pool_contract is None:
            self.fail("abyss gacha pool modules are missing")

    def _pool(self):
        self._require_module()
        return contract.build_runtime_pool(_donor_runtime())

    def test_contract_pins_nine_pickups_with_one_locked_out_of_exchange(self):
        self._require_module()
        self.assertEqual(9, len(contract.CHARACTER_IDS))
        self.assertEqual(9, pool_contract.PICKUP_CHARACTER_COUNT)
        self.assertEqual(9, len(set(contract.CHARACTER_IDS)))
        self.assertEqual(
            sorted(contract.CHARACTER_IDS), list(contract.CHARACTER_IDS)
        )
        self.assertIn(139997, contract.CHARACTER_IDS)
        self.assertEqual((139997,), contract.NON_EXCHANGEABLE_CHARACTER_IDS)
        self.assertTrue(
            set(contract.NON_EXCHANGEABLE_CHARACTER_IDS)
            <= set(contract.CHARACTER_IDS)
        )

    def test_nine_pickups_share_exactly_one_percent_of_all_draws(self):
        pool = self._pool()
        five = pool["1"]
        pickups = [entry for entry in five if entry["isLimited"]]
        standard = [entry for entry in five if not entry["isLimited"]]
        self.assertEqual(9, len(pickups))
        self.assertEqual(6, len(standard))

        pickup_odds = {entry["odds"] for entry in pickups}
        standard_odds = {entry["odds"] for entry in standard}
        self.assertEqual({len(standard)}, pickup_odds)
        self.assertEqual({4 * len(pickups)}, standard_odds)
        total_weight = sum(entry["odds"] for entry in five)
        self.assertEqual(5 * len(pickups) * len(standard), total_weight)

        total, each = pool_contract.pickup_rates(pool)
        self.assertEqual(Fraction(1, 100), total)
        self.assertEqual(Fraction(1, 900), each)
        self.assertEqual(0.01, float(total))
        self.assertEqual(Fraction(1, 100), each * len(pickups))
        self.assertEqual(Fraction(1, 100), pool_contract.PICKUP_TOTAL_RATE)

        # The standard five-star tail keeps the remaining 4%.
        five_rate = Fraction(50, 1000)
        tail = five_rate * Fraction(
            sum(entry["odds"] for entry in standard), total_weight
        )
        self.assertEqual(Fraction(1, 25), tail)
        self.assertEqual(Fraction(1, 20), tail + total)

    def test_pool_rarity_mirrors_the_official_per_mille_weighting(self):
        pool = self._pool()
        five = pool["1"]
        total_weight = sum(entry["odds"] for entry in five)
        for entry in five:
            self.assertAlmostEqual(
                1000.0 * entry["odds"] / total_weight, entry["rarity"], places=9
            )
        self.assertAlmostEqual(
            1000.0, sum(entry["rarity"] for entry in five), places=6
        )

    def test_only_the_locked_pickup_is_excluded_from_the_exchange(self):
        pool = self._pool()
        exchangeable = {
            entry["id"]: entry["isExchangeable"] for entry in pool["1"]
        }
        self.assertFalse(exchangeable[139997])
        for character_id in contract.CHARACTER_IDS:
            if character_id != 139997:
                self.assertTrue(exchangeable[character_id], character_id)
        for character_id in contract.STANDARD_EXCHANGE_CHARACTER_IDS:
            self.assertTrue(exchangeable[character_id], character_id)
        self.assertFalse(exchangeable[STANDARD_FIVE_IDS[0]])
        self.assertTrue(all(entry["isRateUp"] for entry in pool["1"][:9]))
        self.assertEqual(
            8,
            sum(
                1 for entry in pool["1"]
                if entry["isLimited"] and entry["isExchangeable"]
            ),
        )

    def test_character_five_rows_carry_the_locked_exchange_flag(self):
        pool = self._pool()
        rows = contract.build_character_odds_rows(5, pool)
        by_id = {
            row.split(",", 1)[0]: row.split(",") for row in rows.values()
        }
        self.assertEqual(
            ["139997", "5", "6", "true", "true", "false", "false"],
            by_id["139997"],
        )
        self.assertEqual(
            ["139998", "5", "6", "true", "true", "true", "false"],
            by_id["139998"],
        )
        self.assertEqual(
            ["111001", "5", "36", "false", "false", "false", "false"],
            by_id["111001"],
        )

    def test_rejects_pickup_count_drift_and_unknown_exchange_locks(self):
        self._require_module()
        donor = _donor_runtime()
        with self.assertRaisesRegex(ValueError, "nine unique positive integers"):
            pool_contract.build_pickup_pool(
                donor, contract.CHARACTER_IDS[:8],
                contract.STANDARD_EXCHANGE_CHARACTER_IDS,
                contract.NON_EXCHANGEABLE_CHARACTER_IDS,
            )
        for locked in ((139997, 139997), (999999,), (141129,)):
            with self.subTest(locked=locked):
                with self.assertRaisesRegex(
                    ValueError, "non-exchangeable pickup"
                ):
                    pool_contract.build_pickup_pool(
                        donor, contract.CHARACTER_IDS,
                        contract.STANDARD_EXCHANGE_CHARACTER_IDS, locked,
                    )

    def test_pickup_rates_reject_pools_that_are_not_the_locked_contract(self):
        pool = self._pool()
        broken = {
            "1": [dict(entry) for entry in pool["1"]],
            "2": pool["2"],
            "3": pool["3"],
        }
        broken["1"][0]["odds"] = 1
        with self.assertRaisesRegex(ValueError, "pickup rate"):
            pool_contract.pickup_rates(broken)


if __name__ == "__main__":
    unittest.main()
