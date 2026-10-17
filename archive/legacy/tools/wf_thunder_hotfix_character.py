#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure 1.1.6 character-row repair for the summer thunder dragon."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import wf_mod_tool as core
from wf_action_skill_compile import (
    CODE_NAME,
    patch_summer_thunder_dragon_action_skill_rows,
)
from wf_summer_thunder_ability_compile import build_summer_thunder_ability_rows


CHARACTER_KEY = "139998"
ABILITY_LOGICAL = "master/ability/ability.orderedmap"
LEADER_LOGICAL = "master/ability/leader_ability.orderedmap"
UNIQUE_LOGICAL = "master/character/unique_condition.orderedmap"
CHARACTER_TEXT_LOGICAL = "master/character/character_text.orderedmap"
ACTION_SKILL_LOGICAL = "master/skill/action_skill.orderedmap"
SERVER_CHARACTER_TEXT_LOGICAL = "cdndata/character_text.json"

CHARACTER_REPAIR_PATHS = (
    ABILITY_LOGICAL,
    LEADER_LOGICAL,
    UNIQUE_LOGICAL,
    CHARACTER_TEXT_LOGICAL,
    ACTION_SKILL_LOGICAL,
    SERVER_CHARACTER_TEXT_LOGICAL,
)

SKILL_DESCRIPTION = (
    "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
    "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
)


def _require_bytes(label: str, value: object) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{label} must be bytes")
    return bytes(value)


def _replace_flat(
    raw: bytes,
    logical: str,
    replacements: Mapping[str, list[list[str]]],
) -> bytes:
    keys, _pairs, _index_len = core.parse_index(raw)
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate orderedmap key in {logical}")
    text_rows = core.read_orderedmap_file_from_bytes(raw)
    missing = sorted(set(replacements) - set(text_rows))
    if missing:
        raise ValueError(f"character rows missing from {logical}: {missing}")
    replacement_text = {
        key: core.write_csv_lines(rows) for key, rows in replacements.items()
    }
    table = core.OrderedMap(
        logical,
        list(keys),
        [text_rows[key].encode("utf-8") for key in keys],
        Path("<memory>"),
    )
    table.set_text_rows(replacement_text)
    output = core.build_orderedmap(table)
    readback = core.read_orderedmap_file_from_bytes(output)
    if list(readback) != list(keys):
        raise AssertionError(f"orderedmap key order drift: {logical}")
    for key, expected in replacement_text.items():
        if readback.get(key) != expected:
            raise AssertionError(f"character row readback drift: {logical}:{key}")
    for key, before in text_rows.items():
        if key not in replacements and readback.get(key) != before:
            raise AssertionError(f"non-owned row changed: {logical}:{key}")
    return output


def _repair_action_skill(raw: bytes) -> bytes:
    table = core.load_nested_table_bytes(raw, ACTION_SKILL_LOGICAL)
    try:
        source = table.rows[CODE_NAME]
    except KeyError as exc:
        raise ValueError("summer thunder action-skill row is missing") from exc
    donor_rows = [
        (key, core.read_csv_lines(text)[0])
        for key, text in source.text_rows().items()
    ]
    patched = patch_summer_thunder_dragon_action_skill_rows(donor_rows)
    table.rows[CODE_NAME] = core.OrderedMap(
        f"{ACTION_SKILL_LOGICAL}#{CODE_NAME}",
        [key for key, _columns in patched],
        [core.write_csv_lines([columns]).encode("utf-8") for _key, columns in patched],
        Path("<memory>"),
    )
    output = core.build_nested_table(table, ACTION_SKILL_LOGICAL)
    readback = core.load_nested_table_bytes(output, ACTION_SKILL_LOGICAL)
    if readback.rows[CODE_NAME].keys != ["1", "2"]:
        raise AssertionError("summer thunder action-skill level drift")
    for text in readback.rows[CODE_NAME].text_rows().values():
        if core.read_csv_lines(text)[0][1] != SKILL_DESCRIPTION:
            raise AssertionError("summer thunder action-skill description drift")
    return output


def _strict_object(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values):
        output = {}
        for key, value in values:
            if key in output:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            output[key] = value
        return output

    def reject_constant(token: str):
        raise ValueError(f"non-finite JSON constant in {label}: {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid strict JSON in {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {label}")
    return value


def repair_character_contract(
    payloads: Mapping[str, object],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Recompile the six owned character payloads without external writes."""

    if set(payloads) != set(CHARACTER_REPAIR_PATHS):
        raise ValueError("character repair payload set is not exact")
    source = {
        logical: _require_bytes(logical, payloads[logical])
        for logical in CHARACTER_REPAIR_PATHS
    }
    abilities = build_summer_thunder_ability_rows()
    output = dict(source)
    output[ABILITY_LOGICAL] = _replace_flat(
        source[ABILITY_LOGICAL], ABILITY_LOGICAL, abilities["ability"]
    )
    output[LEADER_LOGICAL] = _replace_flat(
        source[LEADER_LOGICAL],
        LEADER_LOGICAL,
        {CHARACTER_KEY: abilities["leader_ability"][CHARACTER_KEY]},
    )
    output[UNIQUE_LOGICAL] = _replace_flat(
        source[UNIQUE_LOGICAL],
        UNIQUE_LOGICAL,
        {CHARACTER_KEY: [abilities["unique_condition"][CHARACTER_KEY]]},
    )

    text_rows = core.read_orderedmap_file_from_bytes(source[CHARACTER_TEXT_LOGICAL])
    if CHARACTER_KEY not in text_rows:
        raise ValueError("summer thunder character_text row is missing")
    old_text = core.read_csv_lines(text_rows[CHARACTER_KEY])
    if len(old_text) != 1 or len(old_text[0]) != 12:
        raise ValueError("summer thunder character_text row shape drift")
    new_text = list(old_text[0])
    new_text[5] = SKILL_DESCRIPTION
    new_text[7] = SKILL_DESCRIPTION
    output[CHARACTER_TEXT_LOGICAL] = _replace_flat(
        source[CHARACTER_TEXT_LOGICAL],
        CHARACTER_TEXT_LOGICAL,
        {CHARACTER_KEY: [new_text]},
    )
    output[ACTION_SKILL_LOGICAL] = _repair_action_skill(
        source[ACTION_SKILL_LOGICAL]
    )

    server = _strict_object(
        source[SERVER_CHARACTER_TEXT_LOGICAL], SERVER_CHARACTER_TEXT_LOGICAL
    )
    if server.get(CHARACTER_KEY) != old_text:
        raise ValueError("client/server character_text source mirror drift")
    server[CHARACTER_KEY] = [new_text]
    output[SERVER_CHARACTER_TEXT_LOGICAL] = json.dumps(
        server, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")

    unchanged = [logical for logical in CHARACTER_REPAIR_PATHS if output[logical] == source[logical]]
    if unchanged:
        raise AssertionError(f"character repair payload did not change: {unchanged}")
    report = {
        "schema_version": 1,
        "status": "recompiled_summer_thunder_character_contract",
        "changed_payload_count": len(CHARACTER_REPAIR_PATHS),
        "unique_condition_duration_frames": 600,
        "leader_paralysis_duration_frames": 180,
        "ability3_other_gauge_percent": 25,
        "ability4_self_gauge_percent": 100,
        "ability5_thunder_attack_percent": 90,
        "ability5_thunder_ability_damage_percent": 90,
        "ability6_self_charge_speed_percent": 15,
        "skill_description_extra_multiplier_mentions": 0,
        "writes_live": False,
    }
    return output, report


__all__ = [
    "CHARACTER_REPAIR_PATHS",
    "SKILL_DESCRIPTION",
    "repair_character_contract",
]
