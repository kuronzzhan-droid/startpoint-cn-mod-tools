#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure row compiler for the summer thunder dragon's locked abilities.

This module only builds CSV rows or additive in-memory table mappings.  It
never writes a store, workspace, package, CDN, server, or device.  Every row
starts from the audited CN 126/124-column parser sentinels, then fills only the
locked character semantics.  This keeps unused enum fields client-legal
without leaking donor effects into the new identity.
"""
from __future__ import annotations

from collections.abc import Mapping

import wf_mod_tool as core


CHARACTER_ID = 139998
CODE_NAME = "cnmod_thunder_dragon_ascendant"
UNIQUE_CONDITION_ID = 139998

ABILITY_WIDTH = 126
LEADER_WIDTH = 124
UNIQUE_WIDTH = 15

UNIQUE_STRING_ID = "unique_cnmod_thunder_dragon_ascendant_amp"
UNIQUE_ICON_PATH = (
    "battle/common/unique_condition/"
    "unique_cnmod_thunder_dragon_ascendant_amp"
)


def _row(width: int, values: Mapping[int, str | int | bool]) -> list[str]:
    row = [""] * width
    for index, value in values.items():
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < width:
            raise ValueError(f"row index outside width {width}: {index!r}")
        if isinstance(value, bool):
            row[index] = "true" if value else "false"
        elif isinstance(value, (str, int)) and not isinstance(value, bool):
            row[index] = str(value)
        else:
            raise ValueError(f"unsupported row value at c{index}: {value!r}")
    return row


def _leader(values: Mapping[int, str | int | bool]) -> list[str]:
    common: dict[int, str | int | bool] = {
        0: CODE_NAME,
        1: 0,
        3: 0,
        4: 0,
        11: 0,
        18: 0,
        25: 0,
        37: "(None)",
        44: 0,
    }
    common.update(values)
    return _row(LEADER_WIDTH, common)


def _ability(
    slot: int,
    *,
    unisonable: bool,
    category: str,
    trigger_kind: int,
    values: Mapping[int, str | int | bool],
) -> list[str]:
    if not 1 <= slot <= 6:
        raise ValueError(f"ability slot outside 1..6: {slot}")
    common: dict[int, str | int | bool] = {
        0: f"{CODE_NAME}_{slot}",
        1: unisonable,
        2: category,
        3: 0,
        5: trigger_kind,
        6: 0,
        13: 0,
        20: 0,
    }
    if trigger_kind == 0:
        common.update({27: 0, 39: "(None)", 46: 0})
    elif trigger_kind == 1:
        common.update({85: "(None)", 108: False})
    else:
        raise ValueError(f"unsupported ability trigger kind: {trigger_kind}")
    common.update(values)
    return _row(ABILITY_WIDTH, common)


def _build_leader_rows() -> dict[str, list[list[str]]]:
    attack = _leader({
        45: 32,
        46: 5,
        47: "Yellow",
        49: 250000,
        50: 250000,
    })
    ability_damage = _leader({
        45: 388,
        46: 5,
        47: "Yellow",
        49: 600000,
        50: 600000,
    })
    amplify = _leader({
        4: 2,
        7: 600000,
        8: 600000,
        9: "Yellow",
        25: 23,
        26: 0,
        28: 100000,
        29: 100000,
        32: "(None)",
        33: 0,
        45: 461,
        46: 0,
        49: 100000,
        50: 100000,
        57: 100000,
        58: 100000,
        66: UNIQUE_CONDITION_ID,
        72: 1,
        73: "(None)",
    })
    power_flip_damage = _leader({
        4: 2,
        7: 600000,
        8: 600000,
        9: "Yellow",
        25: 183,
        28: 100000,
        29: 100000,
        32: "(None)",
        33: 0,
        45: 253,
        46: 0,
        49: 500000,
        50: 500000,
        67: "(None)",
    })
    paralysis = _leader({
        4: 188,
        5: 0,
        7: 100000,
        8: 100000,
        10: UNIQUE_CONDITION_ID,
        25: 144,
        26: 0,
        28: 100000,
        29: 100000,
        32: "(None)",
        33: 0,
        45: 455,
        46: 0,
        55: 18000000,
        56: 18000000,
        65: 0,
        70: False,
    })
    return {str(CHARACTER_ID): [
        attack,
        ability_damage,
        amplify,
        power_flip_damage,
        paralysis,
    ]}


def _build_a1_rows() -> list[list[str]]:
    static = [
        _ability(1, unisonable=True, category="attack_common", trigger_kind=0,
                 values={47: 32, 48: 5, 49: "(None)", 51: 200000, 52: 200000}),
        _ability(1, unisonable=True, category="attack_common", trigger_kind=0,
                 values={47: 388, 48: 5, 49: "(None)", 51: 400000, 52: 400000}),
    ]
    during = []
    for kind in (410, 412):
        during.append(_ability(
            1,
            unisonable=True,
            category="attack_common",
            trigger_kind=1,
            values={
                97: 194,
                98: 0,
                100: 100000,
                101: 100000,
                102: 1,
                104: UNIQUE_CONDITION_ID,
                109: kind,
                110: 0,
                113: 30000,
                114: 30000,
            },
        ))
    return static + during


def _build_a2_rows() -> list[list[str]]:
    dash = _ability(
        2,
        unisonable=True,
        category="action_skill",
        trigger_kind=0,
        values={
            6: 2,
            9: 600000,
            10: 600000,
            11: "Yellow",
            27: 4,
            30: 100000,
            31: 100000,
            34: "(None)",
            35: 60,
            47: 354,
            48: 0,
            51: 500000,
            52: 500000,
            69: "(None)",
        },
    )
    maximum_gauge = _ability(
        2,
        unisonable=True,
        category="action_skill",
        trigger_kind=0,
        values={47: 245, 48: 5, 49: "Yellow", 51: 10000, 52: 10000},
    )
    return [dash, maximum_gauge]


def _build_a3_rows() -> list[list[str]]:
    common_precondition = {
        6: 188,
        7: 0,
        9: 100000,
        10: 100000,
        12: UNIQUE_CONDITION_ID,
    }
    self_gauge = _ability(
        3,
        unisonable=False,
        category="action_skill",
        trigger_kind=0,
        values={
            **common_precondition,
            27: 23,
            28: 5,
            29: "Yellow",
            30: 100000,
            31: 100000,
            34: "(None)",
            35: 0,
            47: 211,
            48: 0,
            51: 25000,
            52: 25000,
        },
    )
    allies_gauge = _ability(
        3,
        unisonable=False,
        category="action_skill",
        trigger_kind=0,
        values={
            **common_precondition,
            27: 23,
            28: 0,
            30: 100000,
            31: 100000,
            34: "(None)",
            35: 0,
            47: 211,
            48: 1,
            49: "(None)",
            51: 25000,
            52: 25000,
        },
    )
    all_enemy = _ability(
        3,
        unisonable=False,
        category="action_skill",
        trigger_kind=0,
        values={
            27: 23,
            28: 5,
            29: "Yellow",
            30: 100000,
            31: 100000,
            34: "(None)",
            35: 0,
            47: 253,
            48: 0,
            51: 2500000,
            52: 2500000,
            69: "(None)",
        },
    )
    return [self_gauge, allies_gauge, all_enemy]


def _build_ability_rows() -> dict[str, list[list[str]]]:
    return {
        "1399981": _build_a1_rows(),
        "1399982": _build_a2_rows(),
        "1399983": _build_a3_rows(),
        "1399984": [_ability(
            4,
            unisonable=True,
            category="action_skill",
            trigger_kind=0,
            values={47: 211, 48: 0, 51: 100000, 52: 100000},
        )],
        "1399985": [
            _ability(
                5,
                unisonable=True,
                category="attack_yellow",
                trigger_kind=0,
                values={47: 32, 48: 5, 49: "Yellow", 51: 90000, 52: 90000},
            ),
            _ability(
                5,
                unisonable=True,
                category="attack_yellow",
                trigger_kind=0,
                values={47: 388, 48: 5, 49: "Yellow", 51: 90000, 52: 90000},
            ),
        ],
        "1399986": [_ability(
            6,
            unisonable=True,
            category="action_skill",
            trigger_kind=0,
            values={47: 35, 48: 0, 51: 15000, 52: 15000},
        )],
    }


def _build_unique_condition_rows() -> dict[str, list[str]]:
    row = [
        UNIQUE_STRING_ID,
        "雷电增幅",
        UNIQUE_ICON_PATH,
        "600",
        "1",
        "(None)",
        "(None)",
        "(None)",
        "(None)",
        "false",
        "false",
        "0",
        "0",
        "true",
        "(None)",
    ]
    if len(row) != UNIQUE_WIDTH:
        raise AssertionError(f"unique condition width drift: {len(row)}")
    return {str(UNIQUE_CONDITION_ID): row}


def build_summer_thunder_ability_rows() -> dict[str, dict]:
    """Return the complete locked leader/A1-A6/unique row contract."""
    return {
        "leader_ability": _build_leader_rows(),
        "ability": _build_ability_rows(),
        "unique_condition": _build_unique_condition_rows(),
    }


def patch_summer_thunder_ability_tables(
    table_rows: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    """Add the locked rows to decoded flat-table mappings without overwrites."""
    required = {"ability", "leader_ability", "unique_condition"}
    if set(table_rows) != required:
        raise ValueError(f"table rows must contain exactly {sorted(required)}")
    output = {
        table: {str(key): str(value) for key, value in rows.items()}
        for table, rows in table_rows.items()
    }
    built = build_summer_thunder_ability_rows()
    for table in sorted(required):
        collisions = sorted(set(output[table]) & set(built[table]))
        if collisions:
            raise ValueError(f"{table} identity collision: {collisions}")
        for key, rows in built[table].items():
            encoded_rows = [rows] if table == "unique_condition" else rows
            output[table][key] = core.write_csv_lines(encoded_rows)
    return output
