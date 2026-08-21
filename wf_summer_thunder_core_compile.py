#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compiler for the summer thunder dragon's core character masters.

The compiler accepts only explicit, audited donor row bytes and returns
decoded-table replacement payloads.  It never reads or writes a store,
workspace, package, CDN, server, or device.  Image, mana, speech, action-skill,
and ability assembly deliberately remain outside this module.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

import wf_mod_tool as core


CHARACTER_ID = 139998
CODE_NAME = "cnmod_thunder_dragon_ascendant"
PACKAGE_ID = "cnmod_thunder_dragon_ascendant"
BASE_CHARACTER_ID = 231001

CHARACTER_WIDTH = 37
CHARACTER_TEXT_WIDTH = 12

_DONOR_SHA256 = {
    "thunder_dragon_character": (
        "64e267bbb2a04c642f0a5bd846c42e64a5b6dd70dc05e9a08106c7f05167c0ff"
    ),
    "dragon_skin_character": (
        "a7a20c3e79bbd6e7ab787c39d0df8dde5991cca9ef0cb90144634536e470f376"
    ),
    "summer_thunder_character": (
        "d24e176cdec6a0664db72c26c6b19c464e973e46e120ae734b3cc64ca2abb204"
    ),
    "dragon_skin_status": (
        "80d9113503e36e8a7d267a4a364cc1b78eaaf1e69a49d4cd7c30ec79688f4c6a"
    ),
    "scaffold_awake_status": (
        "444dae2059d918233728f4775784d898054b48e0b7582a8b9ad9539dc52ada26"
    ),
}

_SCAFFOLD_SHA256 = {
    "character": {
        "139998": "7c5118fa5c7e9a0ac878c8e3effb162f26fcda54c81c36b926a9363077503e12",
    },
    "character_status": {
        "139998": "d29e2236058952c752c3fde4116d11d1def6ccf9bb25ebd745915b161d724e5f",
    },
    "character_text": {
        "139998": "ebf107b65d0db24b3b2b80e43ef4c2919aa40d8ab1a3e9a5b37f3d53d78d0177",
    },
    "character_awake_status": {
        "139998": _DONOR_SHA256["scaffold_awake_status"],
    },
}

_DONOR_CHARACTER_FIELDS = {
    "thunder_dragon_character": {
        0: "thunder_dragon",
        2: "4",
        3: "2",
        4: "Dragon",
        6: "4",
        7: "Female",
        17: "231001",
        25: "0",
        26: "Attacker",
        27: "231001",
        31: "true",
    },
    "dragon_skin_character": {
        0: "wind_dragon_wt22",
        2: "5",
        3: "3",
        4: "Dragon",
        6: "4",
        7: "Male",
        17: "141099",
        25: "1",
        26: "Attacker",
        27: "141008",
        31: "false",
    },
    "summer_thunder_character": {
        0: "combat_soldier_smr22",
        2: "5",
        3: "2",
        4: "Human,Machine",
        6: "2",
        7: "Female",
        17: "131104",
        25: "0",
        26: "Attacker",
        27: "151006",
        31: "false",
        34: "1",
        35: "true",
    },
}

_STATUS_ENTRIES = [
    ("10", 445, 129),
    ("1", 45, 13),
    ("80", 2670, 774),
    ("100", 2937, 852),
]

_SKILL_DESCRIPTION = (
    "向前方释放由中心扩散的黄蓝雷波，对扇形范围内的敌人造成雷属性伤害"
    "（合计55倍／55段），并赋予自身「雷电增幅」效果（10秒）。"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _as_bytes(label: str, value: object) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{label} donor row must be bytes")
    return bytes(value)


def _decode_single_csv(label: str, payload: bytes, width: int) -> list[str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} donor row is not UTF-8 CSV") from exc
    rows = core.read_csv_lines(text)
    if len(rows) != 1 or len(rows[0]) != width:
        raise ValueError(f"{label} donor row must contain one {width}-column CSV row")
    if core.write_csv_lines(rows).encode("utf-8") != payload:
        raise ValueError(f"{label} donor CSV does not roundtrip canonically")
    return rows[0]


def _validate_character_donor(label: str, payload: bytes) -> list[str]:
    row = _decode_single_csv(label, payload, CHARACTER_WIDTH)
    for index, expected in _DONOR_CHARACTER_FIELDS[label].items():
        if row[index] != expected:
            raise ValueError(
                f"{label} audited field drift at c{index}: "
                f"expected {expected!r}, got {row[index]!r}"
            )
    return row


def _validate_donors(donor_rows: Mapping[str, object]) -> dict[str, bytes]:
    if set(donor_rows) != set(_DONOR_SHA256):
        raise ValueError(f"donor rows must contain exactly {sorted(_DONOR_SHA256)}")

    donors = {label: _as_bytes(label, donor_rows[label]) for label in _DONOR_SHA256}
    for label, expected in _DONOR_SHA256.items():
        actual = _sha256(donors[label])
        if actual != expected:
            raise ValueError(
                f"{label} donor identity drift: expected {expected}, got {actual}"
            )

    for label in _DONOR_CHARACTER_FIELDS:
        _validate_character_donor(label, donors[label])

    try:
        status = core.decode_status_row(donors["dragon_skin_status"])
    except Exception as exc:
        raise ValueError("dragon_skin_status donor nested row is invalid") from exc
    if status != _STATUS_ENTRIES:
        raise ValueError(
            f"dragon_skin_status audited values drift: expected {_STATUS_ENTRIES}, got {status}"
        )
    if core.encode_status_row(status) != donors["dragon_skin_status"]:
        raise ValueError("dragon_skin_status donor nested row does not roundtrip")

    awake = _decode_single_csv(
        "scaffold_awake_status", donors["scaffold_awake_status"], 2
    )
    if awake != ["26", "0"]:
        raise ValueError(
            f"scaffold_awake_status audited values drift: expected ['26', '0'], got {awake}"
        )
    return donors


def _encode_csv_row(label: str, row: list[str], width: int) -> str:
    if len(row) != width:
        raise AssertionError(f"{label} width drift: expected {width}, got {len(row)}")
    text = core.write_csv_lines([row])
    if core.read_csv_lines(text) != [row]:
        raise AssertionError(f"{label} CSV roundtrip failed")
    return text


def _build_character_row() -> list[str]:
    return [
        CODE_NAME,
        "1",
        "5",
        "2",
        "Dragon",
        "",
        "4",
        "Female",
        CODE_NAME,
        "(None)",
        "", "", "", "", "", "", "",
        str(CHARACTER_ID),
        "碧海雷鸣的共振",
        *(f"{CHARACTER_ID}{slot}" for slot in range(1, 7)),
        "0",
        "Attacker",
        str(BASE_CHARACTER_ID),
        "(None)",
        "1",
        "false",
        "false",
        "0", "0", "1", "true",
        "6,6,6,6,6,6",
    ]


def _build_character_text_row() -> list[str]:
    return [
        "拉姆斯",
        "LAMUSI",
        "沉睡于险峻高山的雷龙，在星见镇伙伴们的邀请下第一次踏上海滨。"
        "她似乎很中意海风与潮声；而当双翼掠过碧海，悠闲的假日也会随雷鸣化作耀眼的浪潮。",
        "鸣彻碧海的雷龙",
        "碧海雷潮",
        _SKILL_DESCRIPTION,
        "碧海雷潮＋",
        _SKILL_DESCRIPTION,
        "(None)",
        "(None)",
        "碧海雷鸣的共振",
        "",
    ]


def compile_summer_thunder_core(donor_rows: Mapping[str, object]) -> dict[str, object]:
    """Compile isolated owned replacements for the four core character tables."""
    _validate_donors(donor_rows)

    character_row = _build_character_row()
    character_text_row = _build_character_text_row()
    if character_row[18] != character_text_row[10]:
        raise AssertionError("leader title drift between character and character_text")
    if character_text_row[4] != "碧海雷潮" or character_text_row[6] != "碧海雷潮＋":
        raise AssertionError("action-skill display name drift")

    character = _encode_csv_row("character", character_row, CHARACTER_WIDTH)
    character_text = _encode_csv_row(
        "character_text", character_text_row, CHARACTER_TEXT_WIDTH
    )
    character_status = core.encode_status_row(_STATUS_ENTRIES)
    if core.decode_status_row(character_status) != _STATUS_ENTRIES:
        raise AssertionError("character_status nested orderedmap roundtrip failed")

    key = str(CHARACTER_ID)
    tables = {
        "character": {key: character},
        "character_status": {key: character_status},
        "character_text": {key: character_text},
        "character_awake_status": {},
    }
    owned_replacements = {
        "character_awake_status": {
            "mode": "owned_replace",
            "owned_keys": [key],
            "set_keys": [],
            "delete_keys": [key],
            "expected_existing_sha256": dict(
                _SCAFFOLD_SHA256["character_awake_status"]
            ),
        },
    }
    report = {
        "schema_version": 1,
        "status": "compiled_isolated_core_master",
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_id": PACKAGE_ID,
        "base_character_id": BASE_CHARACTER_ID,
        "donor_sha256": dict(_DONOR_SHA256),
        "expected_scaffold_sha256": {
            table: dict(rows) for table, rows in _SCAFFOLD_SHA256.items()
        },
        "output_sha256": {
            "character": {key: _sha256(character.encode("utf-8"))},
            "character_status": {key: _sha256(character_status)},
            "character_text": {key: _sha256(character_text.encode("utf-8"))},
        },
        "writes_live": False,
        "package_manifest_eligible": False,
        "next_gate": (
            "assemble into the isolated character workspace, apply owned replacements, "
            "read back all rows, then complete three-layer sync and sealing"
        ),
    }
    return {
        "tables": tables,
        "owned_replacements": owned_replacements,
        "report": report,
    }
