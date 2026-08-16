#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed gacha contract repair for thunder hotfix 1.1.6."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import wf_abyss_gacha_contract as contract
import wf_abyss_gacha_pool as pool_contract
import wf_mod_tool as core
from wf_abyss_gacha_compile import (
    _build_flat,
    _canonical_json,
    _decode_flat,
    _decode_inner,
    _decode_raw,
    _new_nested,
    _strict_json_object,
)


GACHA_REPAIR_PATHS = (
    contract.GACHA_MASTER_LOGICAL,
    contract.RARITY_ODDS_LOGICAL,
    contract.CHARACTER_3_ODDS_LOGICAL,
    contract.CHARACTER_4_ODDS_LOGICAL,
    contract.CHARACTER_5_ODDS_LOGICAL,
    contract.RICH_TEXT_BODY_LOGICAL,
    "cdndata/gacha.json",
    "gacha.json",
)
# The sealed 1.1.0 source package froze a pure eight-character pickup pool.
# It is an input fingerprint, so it must never track the live pickup contract.
SEALED_SOURCE_CHARACTER_IDS = (
    129999, 139998, 139999, 149998,
    149999, 169998, 169999, 179999,
)
_OLD_RICH_TEXT_SHA256 = (
    "e47383674b190e6fa52e8ad5b529c57a485c764e893f8b92198c6ae5f6e8214a"
)
_OLD_RANK_RATES = {"normal": [1000, 0, 0], "multiGuarantee": [1000, 0]}
_OLD_RARITY_ROWS = {"0": "5,100", "1": "4,0", "2": "3,0"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _old_pool() -> dict[str, list[dict[str, object]]]:
    return {
        "1": [{
            "id": character_id,
            "rank": 5,
            "odds": 100,
            "isRateUp": True,
            "isLimited": True,
            "isExchangeable": False,
            "rarity": 125.0,
            "trialReadingForced": False,
        } for character_id in SEALED_SOURCE_CHARACTER_IDS],
        "2": [],
        "3": [],
    }


def _old_master_row(expected_start_date: str) -> list[str]:
    return [
        contract.CODE_NAME, contract.TITLE, "100", contract.LIST_BANNER_LOGICAL,
        "2", "", "", "", "", "1", "5", contract.RARITY_ODDS_ID,
        contract.RICH_TEXT_ID, "0", contract.CHARACTER_3_ODDS_ID,
        contract.CHARACTER_4_ODDS_ID, contract.CHARACTER_5_ODDS_ID,
        "normal", "normal_guarantee", "false", "false", "false",
        "", "", "", "", "", str(contract.SINGLE_TICKET_ID),
        str(contract.TEN_TICKET_ID), expected_start_date, contract.END_DATE,
        "(None)", "false", "116", "117", "169", "170", "(None)",
        "false", "(None)", "(None)", "(None)", "(None)", "false",
        "false", "(None)", "false",
    ]


def _old_runtime(expected_start_date: str) -> dict[str, object]:
    return {
        "type": 0,
        "paymentType": 0,
        "pageKind": 2,
        "singleCost": 150,
        "multiCost": 1500,
        "discountCost": 50,
        "onceTicketItemId": contract.SINGLE_TICKET_ID,
        "tenTicketItemId": contract.TEN_TICKET_ID,
        "wildcardTicketAvailable": False,
        "rarityOddsId": contract.RARITY_ODDS_ID,
        "guaranteeRarity": 5,
        "rankRates": _OLD_RANK_RATES,
        "movieName": "normal",
        "guaranteeMovieName": "normal_guarantee",
        "toUseOddsUpAsTrialReading": False,
        "canBeStartDashExchange": False,
        "startDate": expected_start_date,
        "endDate": contract.END_DATE,
        "name": contract.TITLE,
        "pool": _old_pool(),
    }


def _old_character_five_rows() -> dict[str, str]:
    return {
        str(index): f"{character_id},5,100,true,true,false,false"
        for index, character_id in enumerate(SEALED_SOURCE_CHARACTER_IDS)
    }


def _expected_old_nested() -> dict[str, bytes]:
    return {
        contract.RARITY_ODDS_LOGICAL: _new_nested(
            contract.RARITY_ODDS_LOGICAL,
            contract.RARITY_ODDS_ID,
            _OLD_RARITY_ROWS,
        ),
        contract.CHARACTER_3_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_3_ODDS_LOGICAL,
            contract.CHARACTER_3_ODDS_ID,
            {},
        ),
        contract.CHARACTER_4_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_4_ODDS_LOGICAL,
            contract.CHARACTER_4_ODDS_ID,
            {},
        ),
        contract.CHARACTER_5_ODDS_LOGICAL: _new_nested(
            contract.CHARACTER_5_ODDS_LOGICAL,
            contract.CHARACTER_5_ODDS_ID,
            _old_character_five_rows(),
        ),
    }


def _validate_old_contract(
    files: Mapping[str, bytes], *, expected_start_date: str
) -> tuple[dict[str, bytes], dict[str, object], dict[str, object]]:
    if (
        not isinstance(expected_start_date, str)
        or not expected_start_date
        or not isinstance(files, Mapping)
        or not set(GACHA_REPAIR_PATHS).issubset(files)
        or any(not isinstance(key, str) or not isinstance(raw, bytes)
               for key, raw in files.items())
    ):
        raise ValueError("gacha hotfix input payload set is invalid")
    try:
        master_rows = _decode_flat(
            files[contract.GACHA_MASTER_LOGICAL], contract.GACHA_MASTER_LOGICAL
        )
        master = core.read_csv_lines(
            master_rows[contract.GACHA_KEY].decode("utf-8")
        )
        runtime = _strict_json_object(files["gacha.json"], "gacha.json")
        cdndata = _strict_json_object(
            files["cdndata/gacha.json"], "cdndata/gacha.json"
        )
    except (KeyError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError("source gacha contract drift") from exc
    old_row = _old_master_row(expected_start_date)
    if (
        master != [old_row]
        or runtime.get(contract.GACHA_KEY) != _old_runtime(expected_start_date)
        or cdndata.get(contract.GACHA_KEY) != [old_row]
        or _sha(files[contract.RICH_TEXT_BODY_LOGICAL])
        != _OLD_RICH_TEXT_SHA256
    ):
        raise ValueError("source gacha contract drift")
    for logical, expected in _expected_old_nested().items():
        if files[logical] != expected:
            raise ValueError(f"source gacha contract drift: {logical}")
    donor = runtime.get(contract.STANDARD_POOL_DONOR_ID)
    contract.build_runtime_pool(donor)
    return master_rows, runtime, cdndata


def _assert_nested_rows(raw: bytes, logical: str, outer: str, rows: Mapping[str, str]) -> None:
    decoded_outer = _decode_raw(raw, logical)
    if set(decoded_outer) != {outer}:
        raise AssertionError(f"gacha odds outer readback drift: {logical}")
    decoded = _decode_inner(decoded_outer[outer], logical)
    if decoded != {key: value.encode("utf-8") for key, value in rows.items()}:
        raise AssertionError(f"gacha odds rows readback drift: {logical}")


def repair_gacha_contract(
    files: Mapping[str, bytes],
    *,
    expected_start_date: str,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Replace the authenticated pure-eight source with a normal pickup pool."""

    master_rows, runtime, cdndata = _validate_old_contract(
        files, expected_start_date=expected_start_date
    )
    desired_pool = contract.build_runtime_pool(
        runtime[contract.STANDARD_POOL_DONOR_ID]
    )
    desired_master = contract.build_gacha_master_row()
    desired_runtime = contract.build_server_runtime(desired_pool)

    repaired = dict(files)
    master_rows[contract.GACHA_KEY] = core.write_csv_lines(
        [desired_master]
    ).encode("utf-8")
    repaired[contract.GACHA_MASTER_LOGICAL] = _build_flat(
        contract.GACHA_MASTER_LOGICAL, master_rows
    )
    runtime[contract.GACHA_KEY] = desired_runtime
    cdndata[contract.GACHA_KEY] = [desired_master]
    repaired["gacha.json"] = _canonical_json(runtime)
    repaired["cdndata/gacha.json"] = _canonical_json(cdndata)

    desired_odds = {
        contract.RARITY_ODDS_LOGICAL: (
            contract.RARITY_ODDS_ID, contract.build_rarity_odds_rows()
        ),
        contract.CHARACTER_3_ODDS_LOGICAL: (
            contract.CHARACTER_3_ODDS_ID,
            contract.build_character_odds_rows(3, desired_pool),
        ),
        contract.CHARACTER_4_ODDS_LOGICAL: (
            contract.CHARACTER_4_ODDS_ID,
            contract.build_character_odds_rows(4, desired_pool),
        ),
        contract.CHARACTER_5_ODDS_LOGICAL: (
            contract.CHARACTER_5_ODDS_ID,
            contract.build_character_odds_rows(5, desired_pool),
        ),
    }
    for logical, (outer, rows) in desired_odds.items():
        repaired[logical] = _new_nested(logical, outer, rows)
        _assert_nested_rows(repaired[logical], logical, outer, rows)
    repaired[contract.RICH_TEXT_BODY_LOGICAL] = contract.build_rich_text_body()

    changed = [
        logical for logical in GACHA_REPAIR_PATHS
        if repaired[logical] != files[logical]
    ]
    if tuple(changed) != GACHA_REPAIR_PATHS:
        raise AssertionError(f"gacha repair changed payload drift: {changed}")
    if (
        _decode_flat(repaired[contract.GACHA_MASTER_LOGICAL],
                     contract.GACHA_MASTER_LOGICAL)[contract.GACHA_KEY]
        != core.write_csv_lines([desired_master]).encode("utf-8")
        or _strict_json_object(repaired["gacha.json"], "gacha.json").get(
            contract.GACHA_KEY
        ) != desired_runtime
        or _strict_json_object(
            repaired["cdndata/gacha.json"], "cdndata/gacha.json"
        ).get(contract.GACHA_KEY) != [desired_master]
        or repaired[contract.RICH_TEXT_BODY_LOGICAL]
        != contract.build_rich_text_body()
    ):
        raise AssertionError("gacha repaired payload readback drift")
    pickup_total, pickup_each = pool_contract.pickup_rates(desired_pool)
    return repaired, {
        "schema_version": 1,
        "status": "repaired_ticket_only_pool_exchange_contract",
        "writes_live": False,
        "source_start_date": expected_start_date,
        "start_date": contract.START_DATE,
        "rank_rates": list(desired_runtime["rankRates"]["normal"]),
        "guarantee_rarity": desired_runtime["guaranteeRarity"],
        "exchange_required_points": {"limited": 250, "standard": 250},
        "limited_pickup_count": len(contract.CHARACTER_IDS),
        "exchangeable_limited_count": len(contract.EXCHANGEABLE_CHARACTER_IDS),
        "non_exchangeable_limited_count": len(
            contract.NON_EXCHANGEABLE_CHARACTER_IDS
        ),
        "non_exchangeable_limited_ids": list(
            contract.NON_EXCHANGEABLE_CHARACTER_IDS
        ),
        "limited_rate_total_ratio": [
            pickup_total.numerator, pickup_total.denominator
        ],
        "limited_rate_each_ratio": [
            pickup_each.numerator, pickup_each.denominator
        ],
        "exchangeable_standard_count": len(
            contract.STANDARD_EXCHANGE_CHARACTER_IDS
        ),
        "page_kind": desired_runtime["pageKind"],
        "ticket_exec_types": {"single": 3, "ten": 4},
        "changed_payload_count": len(changed),
        "changed_paths": list(changed),
        "output_sha256": {
            logical: _sha(repaired[logical]) for logical in changed
        },
    }


__all__ = [
    "GACHA_REPAIR_PATHS", "SEALED_SOURCE_CHARACTER_IDS", "repair_gacha_contract",
]
