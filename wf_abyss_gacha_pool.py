#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate one official standard pool and derive the abyss pickup pool."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction


EXPECTED_ENTRY_KEYS = frozenset({
    "id",
    "rank",
    "odds",
    "isRateUp",
    "isLimited",
    "isExchangeable",
    "rarity",
    "trialReadingForced",
})
STANDARD_RANK_RATES = {
    "normal": [50, 250, 700],
    "multiGuarantee": [50, 950],
}
PICKUP_CHARACTER_COUNT = 9
# Every standard five-star carries four times the pickup count, so the pickups
# hold exactly one fifth of the five-star bucket for any standard pool size.
STANDARD_TAIL_WEIGHT_FACTOR = 4
# 5% five-star bucket * 1/5 pickup share = exactly 1% for all pickups together.
PICKUP_TOTAL_RATE = Fraction(1, 100)
PICKUP_EACH_RATE = PICKUP_TOTAL_RATE / PICKUP_CHARACTER_COUNT


def _fail(detail: str) -> ValueError:
    return ValueError(f"standard pool donor {detail}")


def _validated_entry(value: object, *, bucket: str, index: int) -> dict[str, object]:
    label = f"pool {bucket} entry {index}"
    if not isinstance(value, dict) or set(value) != EXPECTED_ENTRY_KEYS:
        raise _fail(f"{label} fields drift")
    expected_rank = {"1": 5, "2": 4, "3": 3}[bucket]
    character_id = value.get("id")
    odds = value.get("odds")
    rarity = value.get("rarity")
    if (
        isinstance(character_id, bool)
        or not isinstance(character_id, int)
        or character_id <= 0
        or value.get("rank") != expected_rank
        or isinstance(odds, bool)
        or not isinstance(odds, int)
        or odds <= 0
        or isinstance(rarity, bool)
        or not isinstance(rarity, (int, float))
        or not math.isfinite(float(rarity))
        or float(rarity) <= 0
    ):
        raise _fail(f"{label} numeric contract drift")
    for field in (
        "isRateUp", "isLimited", "isExchangeable", "trialReadingForced"
    ):
        if not isinstance(value.get(field), bool):
            raise _fail(f"{label} boolean contract drift")
    return dict(value)


def _normal_entry(
    source: Mapping[str, object],
    *,
    odds: int | None = None,
    rarity: float | None = None,
    exchangeable: bool = False,
) -> dict[str, object]:
    return {
        "id": source["id"],
        "rank": source["rank"],
        "odds": source["odds"] if odds is None else odds,
        "isRateUp": False,
        "isLimited": False,
        "isExchangeable": exchangeable,
        "rarity": source["rarity"] if rarity is None else rarity,
        "trialReadingForced": False,
    }


def pickup_rates(
    pool: Mapping[str, Sequence[Mapping[str, object]]]
) -> tuple[Fraction, Fraction]:
    """Return the exact (total, per-character) five-star pickup probabilities."""
    entries = pool.get("1") if isinstance(pool, Mapping) else None
    if not isinstance(entries, Sequence) or not entries:
        raise ValueError("abyss pickup rate input must carry a five-star pool")
    try:
        pickups = [entry for entry in entries if entry.get("isLimited") is True]
        weights = {int(entry["odds"]) for entry in pickups}
        total_weight = sum(int(entry["odds"]) for entry in entries)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"abyss pickup rate input is malformed: {exc}") from exc
    if (
        len(pickups) != PICKUP_CHARACTER_COUNT
        or len(weights) != 1
        or total_weight <= 0
    ):
        raise ValueError(
            "abyss pickup rate contract drift: "
            f"pickups={len(pickups)}, weights={sorted(weights)}"
        )
    five_rate = Fraction(
        STANDARD_RANK_RATES["normal"][0], sum(STANDARD_RANK_RATES["normal"])
    )
    total = five_rate * Fraction(
        sum(int(entry["odds"]) for entry in pickups), total_weight
    )
    each = total / len(pickups)
    if total != PICKUP_TOTAL_RATE or each != PICKUP_EACH_RATE:
        raise ValueError(
            f"abyss pickup rate is not the locked {PICKUP_TOTAL_RATE} total: {total}"
        )
    return total, each


def build_pickup_pool(
    donor_runtime: object,
    limited_character_ids: Sequence[int],
    standard_exchange_character_ids: Sequence[int] = (),
    non_exchangeable_limited_character_ids: Sequence[int] = (),
) -> dict[str, list[dict[str, object]]]:
    """Return 5/4/3 pools with nine pickups sharing 1% and a 4% standard ★5 tail."""
    if (
        not isinstance(donor_runtime, dict)
        or donor_runtime.get("rankRates") != STANDARD_RANK_RATES
        or not isinstance(donor_runtime.get("pool"), dict)
        or set(donor_runtime["pool"]) != {"1", "2", "3"}
    ):
        raise _fail("runtime contract drift")
    if (
        isinstance(limited_character_ids, (str, bytes))
        or len(limited_character_ids) != PICKUP_CHARACTER_COUNT
        or len(set(limited_character_ids)) != PICKUP_CHARACTER_COUNT
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in limited_character_ids)
    ):
        raise ValueError("limited character IDs must be nine unique positive integers")
    if (
        isinstance(non_exchangeable_limited_character_ids, (str, bytes))
        or len(set(non_exchangeable_limited_character_ids))
        != len(non_exchangeable_limited_character_ids)
        or not set(non_exchangeable_limited_character_ids)
        <= set(limited_character_ids)
    ):
        raise ValueError(
            "non-exchangeable pickup IDs must be unique members of the pickup list"
        )
    if (
        isinstance(standard_exchange_character_ids, (str, bytes))
        or len(set(standard_exchange_character_ids))
        != len(standard_exchange_character_ids)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in standard_exchange_character_ids
        )
        or set(standard_exchange_character_ids) & set(limited_character_ids)
    ):
        raise ValueError(
            "standard exchange character IDs must be unique positive non-pickup integers"
        )

    donor: dict[str, list[dict[str, object]]] = {}
    seen_ids: set[int] = set()
    for bucket in ("1", "2", "3"):
        entries = donor_runtime["pool"][bucket]
        if not isinstance(entries, list) or not entries:
            raise _fail(f"pool {bucket} must be a non-empty list")
        donor[bucket] = []
        for index, value in enumerate(entries):
            entry = _validated_entry(value, bucket=bucket, index=index)
            character_id = int(entry["id"])
            if character_id in seen_ids:
                raise _fail(f"duplicate character ID {character_id}")
            if character_id in limited_character_ids:
                raise _fail(f"already contains custom character {character_id}")
            if (
                character_id in standard_exchange_character_ids
                and bucket != "1"
            ):
                raise _fail(
                    f"standard exchange character {character_id} is not five-star"
                )
            seen_ids.add(character_id)
            donor[bucket].append(entry)

    exchange_ids = tuple(standard_exchange_character_ids)
    exchange_id_set = set(exchange_ids)
    donor_exchange = {
        int(entry["id"]): entry
        for entry in donor["1"]
        if int(entry["id"]) in exchange_id_set
    }
    if any(entry["isLimited"] is not False for entry in donor_exchange.values()):
        raise _fail("standard exchange character is limited in donor")
    standard_five = [
        entry for entry in donor["1"]
        if entry["isLimited"] is False and int(entry["id"]) not in exchange_id_set
    ]
    standard_five.extend({
        "id": character_id,
        "rank": 5,
        "odds": 1,
        "isRateUp": False,
        "isLimited": False,
        "isExchangeable": True,
        "rarity": 1.0,
        "trialReadingForced": False,
    } for character_id in exchange_ids)
    if not standard_five:
        raise _fail("contains no standard five-star characters")

    standard_count = len(standard_five)
    pickup_count = len(limited_character_ids)
    locked_ids = set(non_exchangeable_limited_character_ids)
    # The nine pickups share one fifth of the ★5 bucket, which is exactly 1% of
    # all draws; the standard tail keeps the other four fifths (4%).  With
    # weights N per pickup and 4K per standard entry the split stays exact for
    # every positive standard pool size N and pickup count K.
    pickup_odds = standard_count
    standard_odds = STANDARD_TAIL_WEIGHT_FACTOR * pickup_count
    total_weight = pickup_count * pickup_odds + standard_count * standard_odds
    five = [
        {
            "id": character_id,
            "rank": 5,
            "odds": pickup_odds,
            "isRateUp": True,
            "isLimited": True,
            "isExchangeable": character_id not in locked_ids,
            "rarity": 1000.0 * pickup_odds / total_weight,
            "trialReadingForced": False,
        }
        for character_id in limited_character_ids
    ]
    standard_rarity = 1000.0 * standard_odds / total_weight
    five.extend(
        _normal_entry(
            entry,
            odds=standard_odds,
            rarity=standard_rarity,
            exchangeable=int(entry["id"]) in exchange_id_set,
        )
        for entry in standard_five
    )
    pool = {
        "1": five,
        "2": [_normal_entry(entry) for entry in donor["2"]],
        "3": [_normal_entry(entry) for entry in donor["3"]],
    }
    pickup_rates(pool)
    return pool


def build_character_rows(
    pool: Mapping[str, Sequence[Mapping[str, object]]], rarity: int
) -> dict[str, str]:
    bucket = {5: "1", 4: "2", 3: "3"}.get(rarity)
    if bucket is None:
        raise ValueError(f"unsupported abyss gacha rarity: {rarity}")

    def flag(value: object) -> str:
        if not isinstance(value, bool):
            raise TypeError("gacha pool flag must be boolean")
        return "true" if value else "false"

    return {
        str(index): ",".join((
            str(entry["id"]),
            str(entry["rank"]),
            str(entry["odds"]),
            flag(entry["isRateUp"]),
            flag(entry["isLimited"]),
            flag(entry["isExchangeable"]),
            flag(entry["trialReadingForced"]),
        ))
        for index, entry in enumerate(pool[bucket])
    }


__all__ = [
    "STANDARD_RANK_RATES", "PICKUP_CHARACTER_COUNT", "PICKUP_TOTAL_RATE",
    "PICKUP_EACH_RATE", "STANDARD_TAIL_WEIGHT_FACTOR",
    "build_character_rows", "build_pickup_pool", "pickup_rates",
]
