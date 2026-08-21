#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compiler for the summer thunder dragon's locked ActionDSL.

The functions in this module only return trees, nested action-skill rows, or
logical asset paths mapped to bytes.  They never write a store, package, CDN,
server, or device.
"""
from __future__ import annotations

import copy
import math
import zlib
from collections.abc import Iterable

import wf_dsl


CODE_NAME = "cnmod_thunder_dragon_ascendant"
UNIQUE_CONDITION_ID = 139998
EFFECT_PATH = (
    "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/"
    "fan_lightning/fan_lightning_wave"
)
PROGRAM_PATHS = {
    level: (
        "battle/action/skill/action/rare5/"
        f"{CODE_NAME}${CODE_NAME}_{level}"
    )
    for level in ("1", "2")
}

_SKILL_NAMES = {
    "1": "碧海雷潮",
    "2": "碧海雷潮＋",
}
_SKILL_DESCRIPTION = (
    "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
    "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
)


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _fixed(value: int | float) -> list[dict[str, int | float]]:
    return [{"min": value, "max": value}]


def build_summer_thunder_dragon_skill_tree() -> list:
    """Build the locked 55-hit fan-lightning ActionDSL tree."""
    condition = [
        "Command",
        [
            "CreateCondition",
            -17,
            [["ACUnique", UNIQUE_CONDITION_ID, _fixed(1)]],
            _fixed(1),
            ["GenericConditionHitEffect"],
            True,
            False,
            "",
            None,
            False,
            3,
            _fixed(1),
            False,
        ],
    ]
    show_effect = [
        "Command",
        [
            "ShowEffect",
            "fan_lightning_wave",
            ["SpecifyEffectDirectly", EFFECT_PATH],
            -18,
            ["ForesideOfCharacter"],
            ["PlayOnlyFirstSequence"],
            ["AB"],
            0,
            0,
            -math.pi / 2,
            True,
            False,
            ["Some", _fixed(6.5)],
        ],
    ]
    attack = [
        "Command",
        [
            "CreateNormalAttack",
            2,
            255,
            [],
            [],
            0,
            _fixed(1.0),
            _fixed(0.0),
            False,
            False,
            False,
            False,
            False,
            _fixed(0.0),
            _fixed(0.0),
            ["None"],
            True,
        ],
    ]
    hit_area = [
        "Command",
        [
            "CreateHitArea",
            "*",
            -18,
            ["AB"],
            0,
            0,
            0.0,
            True,
            False,
            ["Sector", _fixed(400), _fixed(math.pi / 2)],
            ["Center"],
            ["Center"],
            ["Single"],
            ["SpecifyHitAreaLifetimeDirectly", 110],
            ["CalculatedUsingMaxNumOfHits", 55],
            ["Some", _fixed(55)],
            False,
            True,
            ["None"],
            0,
            ["Block", []],
            1,
            2,
            ["Block", [attack]],
            0,
            0,
            ["None"],
        ],
    ]
    wait = [
        "Event",
        [
            "Wait",
            12,
            "*",
            ["Block", [show_effect, hit_area]],
        ],
    ]
    return [
        "ActionDsl",
        2,
        ["None"],
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        0,
        ["Block", [condition, wait]],
    ]


def compile_summer_thunder_dragon_action_skills() -> dict[str, bytes]:
    """Compile the same locked tree to distinct level-1 and level-2 paths."""
    payload = _raw_deflate(
        wf_dsl.encode_amf3(build_summer_thunder_dragon_skill_tree())
    )
    return {
        f"{program_path}.action.dsl.amf3.deflate": payload
        for program_path in PROGRAM_PATHS.values()
    }


def patch_summer_thunder_dragon_action_skill_rows(
    donor_rows: Iterable[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    """Patch two donor rows while preserving every unknown schema column."""
    rows = {str(key): copy.deepcopy(columns) for key, columns in donor_rows}
    missing = [level for level in PROGRAM_PATHS if level not in rows]
    if missing:
        raise ValueError(f"donor action_skill rows missing levels: {missing}")

    output: list[tuple[str, list[str]]] = []
    for level in ("1", "2"):
        columns = rows[level]
        if len(columns) != 24:
            raise ValueError(
                f"action_skill level {level} must have 24 columns, got {len(columns)}"
            )
        columns[0] = _SKILL_NAMES[level]
        columns[1] = _SKILL_DESCRIPTION
        columns[2] = "dynamic/skill/atk_front"
        columns[3] = "true"
        columns[4] = "600"
        columns[5] = "600"
        columns[7] = PROGRAM_PATHS[level]
        output.append((level, columns))
    return output
