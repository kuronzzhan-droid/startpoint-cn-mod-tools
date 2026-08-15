#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate one official standard pool and derive the abyss pickup pool."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


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
) -> dict[str, object]:
    return {
        "id": source["id"],
        "rank": source["rank"],
        "odds": source["odds"] if odds is None else odds,
        "isRateUp": False,
        "isLimited": False,
        "isExchangeable": False,
        "rarity": source["rarity"] if rarity is None else rarity,
        "trialReadingForced": False,
    }


def build_pickup_pool(
    donor_runtime: object,
    limited_character_ids: Sequence[int],
) -> dict[str, list[dict[str, object]]]:
    """Return 5/4/3 pools with eight 0.5% pickups and a 1% standard ★5 tail."""
    if (
        not isinstance(donor_runtime, dict)
        or donor_runtime.get("rankRates") != STANDARD_RANK_RATES
        or not isinstance(donor_runtime.get("pool"), dict)
        or set(donor_runtime["pool"]) != {"1", "2", "3"}
    ):
        raise _fail("runtime contract drift")
    if (
        isinstance(limited_character_ids, (str, bytes))
        or len(limited_character_ids) != 8
        or len(set(limited_character_ids)) != 8
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
                for value in limited_character_ids)
    ):
        raise ValueError("limited character IDs must be eight unique positive integers")

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
            seen_ids.add(character_id)
            donor[bucket].append(entry)

    standard_five = [entry for entry in donor["1"] if entry["isLimited"] is False]
    if not standard_five:
        raise _fail("contains no standard five-star characters")

    standard_count = len(standard_five)
    # Eight pickups each receive 10% of the ★5 bucket.  The standard tail gets
    # the remaining 20%, divided equally.  With weights N and 2 this remains
    # exact for every positive standard pool size N.
    five = [
        {
            "id": character_id,
            "rank": 5,
            "odds": standard_count,
            "isRateUp": True,
            "isLimited": True,
            "isExchangeable": True,
            "rarity": 100.0,
            "trialReadingForced": False,
        }
        for character_id in limited_character_ids
    ]
    standard_rarity = 200.0 / standard_count
    five.extend(
        _normal_entry(entry, odds=2, rarity=standard_rarity)
        for entry in standard_five
    )
    return {
        "1": five,
        "2": [_normal_entry(entry) for entry in donor["2"]],
        "3": [_normal_entry(entry) for entry in donor["3"]],
    }


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


__all__ = ["STANDARD_RANK_RATES", "build_character_rows", "build_pickup_pool"]
