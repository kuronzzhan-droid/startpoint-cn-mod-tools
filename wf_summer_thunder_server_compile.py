#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure four-file server compiler for the summer thunder dragon.

The input is an explicit isolated server shadow.  Only character ``139998``
is replaced; the already-remapped mana-node payload is validated and retained
byte-for-byte.  This module never reads or writes a live server, store, CDN,
package workspace, database, or device.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from collections.abc import Mapping, Sequence


CHARACTER_ID = 139998
CODE_NAME = "cnmod_thunder_dragon_ascendant"
SERVER_PATHS = (
    "character.json",
    "mana_node.json",
    "cdndata/character.json",
    "cdndata/character_text.json",
)
_TARGET_KEY = str(CHARACTER_ID)
_MANA_PREFIX = str(CHARACTER_ID * 2)


def _strict_object(raw: bytes, label: str) -> dict:
    if not isinstance(raw, bytes):
        raise TypeError(f"server input must be bytes: {label}")

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def reject_constant(token):
        raise ValueError(f"non-finite JSON constant in {label}: {token}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid UTF-8 JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"server JSON root must be an object: {label}")
    return value


def _canonical(value: dict) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _validate_mana(mana: object) -> tuple[int, int]:
    if not isinstance(mana, dict) or set(mana) != {"1", "2"}:
        raise ValueError("mana boards must contain exactly board 1 and board 2")
    board1, board2 = mana["1"], mana["2"]
    if not isinstance(board1, dict) or not isinstance(board2, dict):
        raise ValueError("mana boards must be JSON objects")
    if (len(board1), len(board2)) != (23, 18):
        raise ValueError(
            "mana board node counts must be board1=23 and board2=18"
        )
    all_ids = set(board1) | set(board2)
    if any(not isinstance(node_id, str) or not node_id.startswith(_MANA_PREFIX)
           for node_id in all_ids):
        raise ValueError(f"mana node prefix must be {_MANA_PREFIX}")
    expected1 = {str(279996200 + index) for index in range(1, 24)}
    expected2 = {str(279996400 + index) for index in range(1, 19)}
    if set(board1) != expected1 or set(board2) != expected2:
        raise ValueError("mana node ids do not match the locked 139998 ranges")

    required_fields = {"field1", "field5", "field6", "items", "manaCost"}
    for node_id, payload in (*board1.items(), *board2.items()):
        valid = isinstance(payload, dict) and set(payload) == required_fields
        if valid:
            valid = all(
                isinstance(payload[field], str)
                for field in ("field1", "field5", "field6")
            )
        if valid:
            items = payload["items"]
            valid = isinstance(items, dict) and all(
                isinstance(item_id, str)
                and item_id.isdecimal()
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
                for item_id, count in items.items()
            )
        if valid:
            mana_cost = payload["manaCost"]
            valid = (
                isinstance(mana_cost, int)
                and not isinstance(mana_cost, bool)
                and mana_cost >= 0
            )
        if not valid:
            raise ValueError(f"mana node payload is invalid: {node_id}")
    return len(board1), len(board2)


def _rows(
    value: Sequence[Sequence[str]], label: str, *, width: int
) -> list[list[str]]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not value
    ):
        raise ValueError(f"{label} must contain one {width}-column row")
    result = []
    for row in value:
        if (
            not isinstance(row, Sequence)
            or isinstance(row, (str, bytes, bytearray))
            or not row
            or any(not isinstance(cell, str) for cell in row)
        ):
            raise ValueError(f"{label} must contain one {width}-column row")
        result.append(list(row))
    if len(result) != 1 or len(result[0]) != width:
        raise ValueError(f"{label} must contain one {width}-column row")
    return result


def compile_summer_thunder_server_files(
    server_files: Mapping[str, bytes],
    *,
    character_rows: Sequence[Sequence[str]],
    character_text_rows: Sequence[Sequence[str]],
) -> dict:
    """Return the four package ``server`` root files and a closed report."""
    if not isinstance(server_files, Mapping) or set(server_files) != set(SERVER_PATHS):
        actual = set(server_files) if isinstance(server_files, Mapping) else set()
        raise ValueError(
            f"server files must match the locked four paths; "
            f"missing={sorted(set(SERVER_PATHS) - actual)}, "
            f"extra={sorted(actual - set(SERVER_PATHS))}"
        )
    decoded = {
        path: _strict_object(server_files[path], path) for path in SERVER_PATHS
    }
    original_non_target = {
        path: {
            key: deepcopy(value)
            for key, value in table.items()
            if key != _TARGET_KEY
        }
        for path, table in decoded.items()
    }
    for path, table in decoded.items():
        if _TARGET_KEY not in table:
            raise ValueError(f"isolated server shadow lacks {_TARGET_KEY}: {path}")

    mana = decoded["mana_node.json"][_TARGET_KEY]
    board1_count, board2_count = _validate_mana(mana)

    character = _rows(character_rows, "character_rows", width=37)
    character_text = _rows(
        character_text_rows, "character_text_rows", width=12
    )
    first = character[0]
    if len(first) < 4 or first[0] != CODE_NAME or first[2] != "5" or first[3] != "2":
        raise ValueError("character row must lock code-name, five-star rarity, and thunder")
    if first[8] != CODE_NAME or first[17] != _TARGET_KEY:
        raise ValueError("character row identity must lock action key and character id")
    if first[19:25] != [f"{CHARACTER_ID}{n}" for n in range(1, 7)]:
        raise ValueError("character row ability ids must be 1399981..1399986")
    display_name = character_text[0][0]
    if not display_name:
        raise ValueError("character display name must not be empty")
    if first[18] != character_text[0][10]:
        raise ValueError("leader title mismatch between character and character_text")

    # JSON decoding produced fresh trees, so these assignments cannot mutate
    # any caller-owned mapping or bytes.
    decoded["character.json"][_TARGET_KEY] = {
        "name": display_name,
        "rarity": 5,
        "element": 2,
        "skill_count": 6,
    }
    decoded["cdndata/character.json"][_TARGET_KEY] = character
    decoded["cdndata/character_text.json"][_TARGET_KEY] = character_text

    files = {
        "character.json": _canonical(decoded["character.json"]),
        # Preserve the already-remapped 41-node tree byte-for-byte.  This is
        # intentional: no server compiler is allowed to infer or renumber it.
        "mana_node.json": bytes(server_files["mana_node.json"]),
        "cdndata/character.json": _canonical(
            decoded["cdndata/character.json"]
        ),
        "cdndata/character_text.json": _canonical(
            decoded["cdndata/character_text.json"]
        ),
    }
    # Read back every output before marking it eligible.
    readback = {path: _strict_object(payload, path) for path, payload in files.items()}
    if readback["cdndata/character.json"][_TARGET_KEY] != character:
        raise AssertionError("server character readback mismatch")
    if readback["cdndata/character_text.json"][_TARGET_KEY] != character_text:
        raise AssertionError("server character_text readback mismatch")
    expected_summary = {
        "name": display_name,
        "rarity": 5,
        "element": 2,
        "skill_count": 6,
    }
    if readback["character.json"][_TARGET_KEY] != expected_summary:
        raise AssertionError("server character summary readback mismatch")
    _validate_mana(readback["mana_node.json"][_TARGET_KEY])
    for path, table in readback.items():
        non_target = {
            key: value for key, value in table.items() if key != _TARGET_KEY
        }
        if non_target != original_non_target[path]:
            raise AssertionError(f"non-target server rows changed: {path}")

    return {
        "files": files,
        "report": {
            "schema_version": 1,
            "character_id": CHARACTER_ID,
            "code_name": CODE_NAME,
            "server_file_count": len(files),
            "mana_node_prefix": _MANA_PREFIX,
            "mana_board_1_nodes": board1_count,
            "mana_board_2_nodes": board2_count,
            "mana_total_nodes": board1_count + board2_count,
            "sha256": {
                path: hashlib.sha256(payload).hexdigest()
                for path, payload in sorted(files.items())
            },
            "root": "server",
            "writes_live": False,
            "package_manifest_eligible": True,
        },
    }


__all__ = [
    "CHARACTER_ID",
    "CODE_NAME",
    "SERVER_PATHS",
    "compile_summer_thunder_server_files",
]
