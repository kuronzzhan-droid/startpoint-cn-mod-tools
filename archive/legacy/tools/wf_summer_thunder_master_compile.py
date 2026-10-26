#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure client-master assembler for the summer thunder dragon.

The compiler accepts explicit full-table bytes from an isolated authoring
baseline plus the already compiled core rows.  It returns complete candidate
table bytes, exact character-pack claims, and a readback report.  It never
resolves or writes a store, workspace, package, CDN, server, or device.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import wf_mod_tool as core
import wf_quest_lib as quest
from wf_action_skill_compile import (
    patch_summer_thunder_dragon_action_skill_rows,
)
from wf_summer_thunder_ability_compile import (
    build_summer_thunder_ability_rows,
)
from wf_summer_thunder_voice_compile import (
    build_summer_thunder_character_speech_rows,
)


CHARACTER_ID = 139998
CHARACTER_KEY = str(CHARACTER_ID)
CODE_NAME = "cnmod_thunder_dragon_ascendant"
PACKAGE_ID = CODE_NAME

CHARACTER_LOGICAL = "master/character/character.orderedmap"
CHARACTER_TEXT_LOGICAL = "master/character/character_text.orderedmap"
CHARACTER_SPEECH_LOGICAL = "master/character/character_speech.orderedmap"
ABILITY_LOGICAL = "master/ability/ability.orderedmap"
LEADER_LOGICAL = "master/ability/leader_ability.orderedmap"
UNIQUE_LOGICAL = "master/character/unique_condition.orderedmap"
STATUS_LOGICAL = "master/character/character_status.orderedmap"
ACTION_SKILL_LOGICAL = "master/skill/action_skill.orderedmap"
SKILL_PREVIEW_LOGICAL = "master/skill_preview/skill_preview_character.orderedmap"
MANA_OPEN_LOGICAL = "master/mana_board/mana_board2_open_condition.orderedmap"
UPSKILL_LOGICAL = "master/mana_board/upskill.orderedmap"
STANCE_LOGICAL = "master/stance_detail/character_stance_detail.orderedmap"
CHARACTER_IMAGE_LOGICAL = "master/generated/character_image.orderedmap"
FULL_SHOT_LOGICAL = "master/character/full_shot_image_attribute.orderedmap"
MANA_BOARD_LOGICAL = "master/generated/mana_board.orderedmap"
MANA_NODE_LOGICAL = "master/mana_board/mana_node.orderedmap"
GACHA_SOUND_LOGICAL = "master/character/character_gacha_sound.orderedmap"
TRIMMED_IMAGE_LOGICAL = "master/generated/trimmed_image.orderedmap"

TABLE_CODECS = {
    CHARACTER_LOGICAL: "flat",
    CHARACTER_TEXT_LOGICAL: "flat",
    CHARACTER_SPEECH_LOGICAL: "flat",
    ABILITY_LOGICAL: "flat",
    LEADER_LOGICAL: "flat",
    UNIQUE_LOGICAL: "flat",
    STATUS_LOGICAL: "raw_outer",
    ACTION_SKILL_LOGICAL: "action_nested",
    SKILL_PREVIEW_LOGICAL: "flat",
    MANA_OPEN_LOGICAL: "flat",
    UPSKILL_LOGICAL: "flat",
    STANCE_LOGICAL: "flat",
    CHARACTER_IMAGE_LOGICAL: "raw_outer",
    FULL_SHOT_LOGICAL: "raw_outer",
    MANA_BOARD_LOGICAL: "raw_outer",
    MANA_NODE_LOGICAL: "raw_outer",
    GACHA_SOUND_LOGICAL: "raw_outer",
    TRIMMED_IMAGE_LOGICAL: "flat",
}

ABILITY_KEYS = tuple(f"{CHARACTER_ID}{slot}" for slot in range(1, 7))

TRIM_ROWS = {
    f"character/{CODE_NAME}/ui/full_shot_1440_1920_0": "457,276,2000,2000",
    f"character/{CODE_NAME}/ui/full_shot_1440_1920_1": "457,276,2000,2000",
    f"character/{CODE_NAME}/ui/skill_cutin_0": "0,0,1024,512",
    f"character/{CODE_NAME}/ui/skill_cutin_1": "0,0,1024,512",
}

IMAGE_ROWS = {
    CHARACTER_IMAGE_LOGICAL: {
        "0": "457,276,1086,1448",
        "1": "457,276,1086,1448",
    },
    FULL_SHOT_LOGICAL: {
        "0": "1000,1000,1,1022,536",
        "1": "1000,1000,1,842,761",
    },
}

EXPECTED_FLAT_STRUCTURE = {
    SKILL_PREVIEW_LOGICAL: "903,false,false,903,false,false,(None),(None),",
    MANA_OPEN_LOGICAL: "2015-03-01 12:00:00,2199-12-31 23:59:59",
    UPSKILL_LOGICAL: (
        "common_attack_up,(None),(None),(None),(None),(None),"
        "common_attack_up,(None),(None),(None),(None),(None)"
    ),
    STANCE_LOGICAL: ",1,1,2,,1,1,2",
}

EXPECTED_GACHA_SOUND = {
    "11": "sound_effect/monster/se_dragon_flying",
    "71": "sound_effect/monster/se_scream2",
    "77": "sound_effect/thunder/se_thunder_charge_smash",
    "159": "sound_effect/thunder/se_thunder_wide_area_electricity",
}

# These are target-row identities from the isolated authoring scaffold.  Full
# table hashes are intentionally not locked: unrelated official rows may move
# while every non-owned row must still be preserved byte-for-byte.
LOCKED_STRUCTURE_SHA256 = {
    SKILL_PREVIEW_LOGICAL: "672328daf3b4c83d5b5147180f1ec16e2bb901567f51418c75f67dddaf11ba09",
    MANA_OPEN_LOGICAL: "9240a0b3a2e0355ef95967ac1aee813f37cd865d5cc6c605a0f50e118e6f05a6",
    UPSKILL_LOGICAL: "740f4ca064be4c61104a92b8a32dca516ab9f6f3a76c6dfe60e05c62907ef5ea",
    STANCE_LOGICAL: "06c18ff7e45533ae2b5ef0cd9d37d154217db2e7bfe1676659372d6699dfdbf5",
    GACHA_SOUND_LOGICAL: "d90ee279f29ec623703b2b35b98191d72374dab7ee730f991131ad66f42fad6b",
    MANA_BOARD_LOGICAL: "fd849a87502f18836b27c45734d8b0e04407b61a6fc5a057903fde04e1265669",
    MANA_NODE_LOGICAL: "96ecebd42e80f4263f2869e84f9a3e97a7e181b0139dadd7b3ed393129a99861",
    ACTION_SKILL_LOGICAL: "a1bc7ab0e36600010bb39ea240d482703fdad55596fd5a59d8c63c7e5e6c821b",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require_bytes(label: str, value: object) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{label} must be explicit bytes")
    return bytes(value)


def _decode_flat(raw: bytes, logical: str) -> core.OrderedMap:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=logical, compressed_rows=True
    )
    return core.OrderedMap(logical, keys, rows, Path("<memory>"))


def _decode_raw(raw: bytes, logical: str) -> core.OrderedMap:
    keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        raw, label=logical, compressed_rows=False
    )
    return core.OrderedMap(logical, keys, rows, Path("<memory>"))


def _row_map(table: core.OrderedMap) -> dict[str, bytes]:
    return dict(zip(table.keys, table.rows))


def _target_structure_rows(base: Mapping[str, bytes]) -> dict[str, bytes]:
    rows: dict[str, bytes] = {}
    for logical in LOCKED_STRUCTURE_SHA256:
        if logical == ACTION_SKILL_LOGICAL:
            table = core.load_nested_table_bytes(base[logical], logical)
            try:
                rows[logical] = table.raw_rows[CODE_NAME]
            except KeyError as exc:
                raise ValueError(f"locked scaffold missing: {logical}:{CODE_NAME}") from exc
        elif TABLE_CODECS[logical] == "flat":
            table = _decode_flat(base[logical], logical)
            try:
                rows[logical] = _row_map(table)[CHARACTER_KEY]
            except KeyError as exc:
                raise ValueError(f"locked scaffold missing: {logical}:{CHARACTER_KEY}") from exc
        else:
            table = _decode_raw(base[logical], logical)
            try:
                rows[logical] = _row_map(table)[CHARACTER_KEY]
            except KeyError as exc:
                raise ValueError(f"locked scaffold missing: {logical}:{CHARACTER_KEY}") from exc
    return rows


def _validate_locked_structure(base: Mapping[str, bytes]) -> dict[str, bytes]:
    rows = _target_structure_rows(base)
    for logical, expected in LOCKED_STRUCTURE_SHA256.items():
        actual = _sha256(rows[logical])
        if actual != expected:
            raise ValueError(
                f"locked scaffold drift for {logical}: expected {expected}, got {actual}"
            )

    for logical, expected in EXPECTED_FLAT_STRUCTURE.items():
        try:
            actual = rows[logical].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"locked scaffold is not UTF-8: {logical}") from exc
        if actual != expected:
            raise ValueError(f"locked scaffold semantic drift for {logical}")

    gacha = quest.parse_node(rows[GACHA_SOUND_LOGICAL])
    if gacha != EXPECTED_GACHA_SOUND:
        raise ValueError("locked gacha-sound scaffold semantic drift")

    action = core.load_nested_table_bytes(base[ACTION_SKILL_LOGICAL], ACTION_SKILL_LOGICAL)
    target = action.rows[CODE_NAME]
    if target.keys != ["1", "2", "3"]:
        raise ValueError("locked action_skill scaffold must contain levels 1,2,3")
    for key, text in target.text_rows().items():
        decoded = core.read_csv_lines(text)
        if len(decoded) != 1 or len(decoded[0]) != 24:
            raise ValueError(f"locked action_skill scaffold has invalid level {key}")

    _validate_mana_pair(rows[MANA_BOARD_LOGICAL], rows[MANA_NODE_LOGICAL])
    return rows


def _expected_mana_ids(board_key: str) -> tuple[str, ...]:
    if board_key == "1":
        return tuple(str(279996200 + index) for index in range(1, 24))
    if board_key == "2":
        return tuple(str(279996400 + index) for index in range(1, 19))
    raise AssertionError(f"unexpected board key: {board_key}")


def _single_csv(label: str, text: object, width: int) -> list[str]:
    if not isinstance(text, str):
        raise ValueError(f"{label} must be a CSV leaf")
    rows = core.read_csv_lines(text)
    if len(rows) != 1 or len(rows[0]) != width:
        raise ValueError(f"{label} must contain one {width}-column CSV row")
    if core.write_csv_lines(rows) != text:
        raise ValueError(f"{label} CSV does not roundtrip canonically")
    return rows[0]


def _validate_mana_pair(board_raw: bytes, node_raw: bytes) -> None:
    board = quest.parse_node(board_raw)
    nodes = quest.parse_node(node_raw)
    if not isinstance(board, dict) or not isinstance(nodes, dict):
        raise ValueError("mana target rows must be nested maps")
    if list(board) != ["1", "2"] or list(nodes) != ["1", "2"]:
        raise ValueError("mana boards must contain exactly board 1 and board 2")

    for board_key in ("1", "2"):
        board_rows = board[board_key]
        node_rows = nodes[board_key]
        if not isinstance(board_rows, dict) or not isinstance(node_rows, dict):
            raise ValueError(f"mana board {board_key} must be a map")
        expected_ids = _expected_mana_ids(board_key)
        expected_keys = [str(index) for index in range(1, len(expected_ids) + 1)]
        if set(board_rows) != set(expected_keys) or set(node_rows) != set(expected_keys):
            raise ValueError(
                f"mana board {board_key} node count/key drift; "
                f"expected {len(expected_keys)} nodes"
            )

        seen_board_ids: list[str] = []
        seen_node_ids: list[str] = []
        references: list[str] = []
        for inner_key in expected_keys:
            board_columns = _single_csv(
                f"mana_board {board_key}/{inner_key}", board_rows[inner_key], 6
            )
            node_columns = _single_csv(
                f"mana_node {board_key}/{inner_key}", node_rows[inner_key], 7
            )
            expected_id = expected_ids[int(inner_key) - 1]
            if board_columns[0] != expected_id or node_columns[0] != expected_id:
                raise ValueError(
                    f"mana multiplied_id drift at {board_key}/{inner_key}: "
                    f"expected {expected_id}"
                )
            seen_board_ids.append(board_columns[0])
            seen_node_ids.append(node_columns[0])
            if board_columns[5] != "(None)":
                references.extend(part for part in board_columns[5].split(",") if part)

        if tuple(seen_board_ids) != expected_ids or tuple(seen_node_ids) != expected_ids:
            raise ValueError(f"mana board {board_key} multiplied_id order drift")
        invalid = sorted(set(references) - set(expected_ids))
        if invalid:
            raise ValueError(
                f"mana board {board_key} prerequisite references escape target nodes: {invalid}"
            )


def _validate_compiled_core(compiled: Mapping[str, object]) -> dict[str, Any]:
    if not isinstance(compiled, Mapping):
        raise TypeError("compiled_core must be a mapping")
    tables = compiled.get("tables")
    report = compiled.get("report")
    if not isinstance(tables, Mapping) or not isinstance(report, Mapping):
        raise ValueError("compiled_core must contain tables and report mappings")
    required = {
        "character", "character_status", "character_text", "character_awake_status"
    }
    if set(tables) != required:
        raise ValueError(f"compiled_core tables must contain exactly {sorted(required)}")
    awake = tables["character_awake_status"]
    if not isinstance(awake, Mapping) or awake:
        raise ValueError("compiled_core awake_status must be empty and is never packaged")
    if report.get("writes_live") is not False:
        raise ValueError("compiled_core must prove writes_live=false")
    if (
        report.get("character_id") != CHARACTER_ID
        or report.get("code_name") != CODE_NAME
        or report.get("package_id") != PACKAGE_ID
    ):
        raise ValueError("compiled_core identity drift")

    output: dict[str, Any] = {}
    for name in ("character", "character_status", "character_text"):
        rows = tables[name]
        if not isinstance(rows, Mapping) or set(rows) != {CHARACTER_KEY}:
            raise ValueError(f"compiled_core {name} must own only {CHARACTER_KEY}")
        output[name] = rows[CHARACTER_KEY]
    if not isinstance(output["character"], str) or not isinstance(output["character_text"], str):
        raise TypeError("compiled_core character/text rows must be strings")
    output["character_status"] = _require_bytes(
        "compiled_core character_status row", output["character_status"]
    )

    character_rows = core.read_csv_lines(output["character"])
    text_rows = core.read_csv_lines(output["character_text"])
    if len(character_rows) != 1 or len(character_rows[0]) != 37:
        raise ValueError("compiled_core character row must have 37 columns")
    if len(text_rows) != 1 or len(text_rows[0]) != 12:
        raise ValueError("compiled_core character_text row must have 12 columns")
    character = character_rows[0]
    if (
        character[0] != CODE_NAME
        or character[2] != "5"
        or character[3] != "2"
        or character[4] != "Dragon"
        or character[6] != "4"
        or character[7] != "Female"
        or character[8] != CODE_NAME
        or character[17] != CHARACTER_KEY
    ):
        raise ValueError("compiled_core character identity/shape drift")
    core.decode_status_row(output["character_status"])
    return output


def _replace_flat(
    raw: bytes,
    logical: str,
    replacements: Mapping[str, str],
    *,
    require_existing: bool = True,
) -> bytes:
    table = _decode_flat(raw, logical)
    existing = set(table.keys)
    missing = sorted(set(replacements) - existing)
    if require_existing and missing:
        raise ValueError(f"authoring scaffold missing from {logical}: {missing}")
    table.set_text_rows(dict(replacements))
    return core.build_orderedmap(table)


def _replace_raw(raw: bytes, logical: str, key: str, replacement: bytes) -> bytes:
    table = _decode_raw(raw, logical)
    try:
        index = table.keys.index(key)
    except ValueError as exc:
        raise ValueError(f"authoring scaffold missing from {logical}: {key}") from exc
    table.rows[index] = replacement
    return core.build_orderedmap_raw_rows(table)


def _compile_action(raw: bytes) -> bytes:
    table = core.load_nested_table_bytes(raw, ACTION_SKILL_LOGICAL)
    try:
        donor = table.rows[CODE_NAME]
    except KeyError as exc:
        raise ValueError(f"authoring action scaffold missing: {CODE_NAME}") from exc
    donor_rows = [
        (key, core.read_csv_lines(text)[0])
        for key, text in donor.text_rows().items()
    ]
    patched = patch_summer_thunder_dragon_action_skill_rows(donor_rows)
    table.rows[CODE_NAME] = core.OrderedMap(
        f"{ACTION_SKILL_LOGICAL}#{CODE_NAME}",
        [key for key, _ in patched],
        [core.write_csv_lines([columns]).encode("utf-8") for _, columns in patched],
        Path("<memory>"),
    )
    output = core.build_nested_table(table, ACTION_SKILL_LOGICAL)
    readback = core.load_nested_table_bytes(output, ACTION_SKILL_LOGICAL)
    if readback.rows[CODE_NAME].keys != ["1", "2"]:
        raise AssertionError("action_skill readback retained an unexpected level")
    return output


def _claims() -> list[dict[str, object]]:
    outer_keys = {
        CHARACTER_LOGICAL: [CHARACTER_KEY],
        CHARACTER_TEXT_LOGICAL: [CHARACTER_KEY],
        CHARACTER_SPEECH_LOGICAL: [CHARACTER_KEY],
        ABILITY_LOGICAL: list(ABILITY_KEYS),
        LEADER_LOGICAL: [CHARACTER_KEY],
        UNIQUE_LOGICAL: [CHARACTER_KEY],
        STATUS_LOGICAL: [CHARACTER_KEY],
        ACTION_SKILL_LOGICAL: [CODE_NAME],
        SKILL_PREVIEW_LOGICAL: [CHARACTER_KEY],
        MANA_OPEN_LOGICAL: [CHARACTER_KEY],
        UPSKILL_LOGICAL: [CHARACTER_KEY],
        STANCE_LOGICAL: [CHARACTER_KEY],
        CHARACTER_IMAGE_LOGICAL: [CHARACTER_KEY],
        FULL_SHOT_LOGICAL: [CHARACTER_KEY],
        MANA_BOARD_LOGICAL: [CHARACTER_KEY],
        MANA_NODE_LOGICAL: [CHARACTER_KEY],
        GACHA_SOUND_LOGICAL: [CHARACTER_KEY],
        TRIMMED_IMAGE_LOGICAL: list(TRIM_ROWS),
    }
    claims = []
    for logical, codec in TABLE_CODECS.items():
        claims.append({
            "root": "common",
            "logical_path": logical,
            "codec_id": codec,
            "outer_keys": outer_keys[logical],
            "inner_keys": (
                [{"outer_key": CODE_NAME, "keys": ["1", "2"]}]
                if logical == ACTION_SKILL_LOGICAL else []
            ),
            "semantic_claims": [],
        })
    return claims


def _verify_nonowned(
    before: Mapping[str, bytes],
    after: Mapping[str, bytes],
    claims: list[dict[str, object]],
) -> tuple[int, int]:
    claim_by_path = {item["logical_path"]: item for item in claims}
    outer_changes = 0
    inner_changes = 0
    for logical, codec in TABLE_CODECS.items():
        if codec == "action_nested":
            old = core.load_nested_table_bytes(before[logical], logical)
            new = core.load_nested_table_bytes(after[logical], logical)
            for key in set(old.raw_rows) | set(new.raw_rows):
                if key == CODE_NAME:
                    continue
                if old.raw_rows.get(key) != new.raw_rows.get(key):
                    outer_changes += 1
            for outer_key in set(old.rows) | set(new.rows):
                if outer_key == CODE_NAME:
                    continue
                old_inner = old.rows.get(outer_key)
                new_inner = new.rows.get(outer_key)
                old_rows = _row_map(old_inner) if old_inner else {}
                new_rows = _row_map(new_inner) if new_inner else {}
                inner_changes += sum(
                    old_rows.get(key) != new_rows.get(key)
                    for key in set(old_rows) | set(new_rows)
                )
            continue

        decoder = _decode_raw if codec == "raw_outer" else _decode_flat
        old_rows = _row_map(decoder(before[logical], logical))
        new_rows = _row_map(decoder(after[logical], logical))
        owned = set(claim_by_path[logical]["outer_keys"])
        outer_changes += sum(
            old_rows.get(key) != new_rows.get(key)
            for key in (set(old_rows) | set(new_rows)) - owned
        )
    return outer_changes, inner_changes


def _owned_text(files: Mapping[str, bytes]) -> str:
    fragments: list[str] = []
    for logical, codec in TABLE_CODECS.items():
        if codec == "action_nested":
            nested = core.load_nested_table_bytes(files[logical], logical)
            fragments.extend(nested.rows[CODE_NAME].text_rows().values())
        elif codec == "flat":
            rows = _row_map(_decode_flat(files[logical], logical))
            keys = ABILITY_KEYS if logical == ABILITY_LOGICAL else (
                tuple(TRIM_ROWS) if logical == TRIMMED_IMAGE_LOGICAL else (CHARACTER_KEY,)
            )
            fragments.extend(rows[key].decode("utf-8") for key in keys)
        elif logical in (STATUS_LOGICAL, CHARACTER_IMAGE_LOGICAL, FULL_SHOT_LOGICAL,
                         MANA_BOARD_LOGICAL, MANA_NODE_LOGICAL, GACHA_SOUND_LOGICAL):
            raw = _row_map(_decode_raw(files[logical], logical))[CHARACTER_KEY]
            if logical == STATUS_LOGICAL:
                fragments.append(repr(core.decode_status_row(raw)))
            else:
                fragments.append(json.dumps(quest.parse_node(raw), ensure_ascii=False))
    return "\n".join(fragments)


def _verify_outputs(files: Mapping[str, bytes], claims: list[dict[str, object]]) -> None:
    for claim in claims:
        logical = str(claim["logical_path"])
        codec = str(claim["codec_id"])
        if codec == "action_nested":
            table = core.load_nested_table_bytes(files[logical], logical)
            if CODE_NAME not in table.rows or table.rows[CODE_NAME].keys != ["1", "2"]:
                raise AssertionError("action_skill claim/readback drift")
            continue
        decoder = _decode_raw if codec == "raw_outer" else _decode_flat
        row_map = _row_map(decoder(files[logical], logical))
        missing = sorted(set(claim["outer_keys"]) - set(row_map))
        if missing:
            raise AssertionError(f"claim/readback drift for {logical}: {missing}")

    status = _row_map(_decode_raw(files[STATUS_LOGICAL], STATUS_LOGICAL))[CHARACTER_KEY]
    core.decode_status_row(status)
    for logical, expected in IMAGE_ROWS.items():
        raw = _row_map(_decode_raw(files[logical], logical))[CHARACTER_KEY]
        if quest.parse_node(raw) != expected:
            raise AssertionError(f"image table readback drift: {logical}")
    mana_board = _row_map(_decode_raw(files[MANA_BOARD_LOGICAL], MANA_BOARD_LOGICAL))[CHARACTER_KEY]
    mana_node = _row_map(_decode_raw(files[MANA_NODE_LOGICAL], MANA_NODE_LOGICAL))[CHARACTER_KEY]
    _validate_mana_pair(mana_board, mana_node)

    scrubbed = _owned_text(files).replace(CODE_NAME, "")
    forbidden = ("wind_dragon_wt22", "combat_soldier_smr22", "141099", "131104")
    found = [token for token in forbidden if token in scrubbed]
    if "thunder_dragon" in scrubbed:
        found.append("thunder_dragon")
    if found:
        raise AssertionError(f"owned target rows retain donor identity: {sorted(set(found))}")


def compile_summer_thunder_master_tables(
    base_tables: Mapping[str, object],
    compiled_core: Mapping[str, object],
) -> dict[str, object]:
    """Build all 18 candidate client masters without touching external state."""
    if not isinstance(base_tables, Mapping):
        raise TypeError("base_tables must be an explicit in-memory mapping")
    expected = set(TABLE_CODECS)
    actual = set(base_tables)
    if actual != expected:
        raise ValueError(
            "base tables must contain exactly the client-master contract; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    base = {
        logical: _require_bytes(f"base table {logical}", base_tables[logical])
        for logical in TABLE_CODECS
    }
    core_rows = _validate_compiled_core(compiled_core)
    structure_rows = _validate_locked_structure(base)

    abilities = build_summer_thunder_ability_rows()
    files = dict(base)
    files[CHARACTER_LOGICAL] = _replace_flat(
        base[CHARACTER_LOGICAL], CHARACTER_LOGICAL,
        {CHARACTER_KEY: core_rows["character"]},
    )
    files[CHARACTER_TEXT_LOGICAL] = _replace_flat(
        base[CHARACTER_TEXT_LOGICAL], CHARACTER_TEXT_LOGICAL,
        {CHARACTER_KEY: core_rows["character_text"]},
    )
    files[CHARACTER_SPEECH_LOGICAL] = _replace_flat(
        base[CHARACTER_SPEECH_LOGICAL], CHARACTER_SPEECH_LOGICAL,
        {CHARACTER_KEY: core.write_csv_lines(build_summer_thunder_character_speech_rows())},
    )
    files[ABILITY_LOGICAL] = _replace_flat(
        base[ABILITY_LOGICAL], ABILITY_LOGICAL,
        {
            key: core.write_csv_lines(rows)
            for key, rows in abilities["ability"].items()
        },
    )
    files[LEADER_LOGICAL] = _replace_flat(
        base[LEADER_LOGICAL], LEADER_LOGICAL,
        {
            CHARACTER_KEY: core.write_csv_lines(
                abilities["leader_ability"][CHARACTER_KEY]
            )
        },
    )
    files[UNIQUE_LOGICAL] = _replace_flat(
        base[UNIQUE_LOGICAL], UNIQUE_LOGICAL,
        {
            CHARACTER_KEY: core.write_csv_lines(
                [abilities["unique_condition"][CHARACTER_KEY]]
            )
        },
        require_existing=False,
    )
    files[STATUS_LOGICAL] = _replace_raw(
        base[STATUS_LOGICAL], STATUS_LOGICAL, CHARACTER_KEY,
        core_rows["character_status"],
    )
    files[ACTION_SKILL_LOGICAL] = _compile_action(base[ACTION_SKILL_LOGICAL])

    for logical, rows in IMAGE_ROWS.items():
        files[logical] = _replace_raw(
            base[logical], logical, CHARACTER_KEY, quest.build_node(rows)
        )

    trim = _decode_flat(base[TRIMMED_IMAGE_LOGICAL], TRIMMED_IMAGE_LOGICAL)
    collisions = sorted(set(trim.keys) & set(TRIM_ROWS))
    if collisions:
        raise ValueError(f"trimmed_image identity collision: {collisions}")
    trim.set_text_rows(dict(TRIM_ROWS))
    files[TRIMMED_IMAGE_LOGICAL] = core.build_orderedmap(trim)

    # Structural scaffold tables remain byte-identical after their identities
    # and semantics pass the locked checks above.
    for logical in EXPECTED_FLAT_STRUCTURE:
        if _row_map(_decode_flat(files[logical], logical))[CHARACTER_KEY] != structure_rows[logical]:
            raise AssertionError(f"locked structural row changed: {logical}")
    for logical in (MANA_BOARD_LOGICAL, MANA_NODE_LOGICAL, GACHA_SOUND_LOGICAL):
        if _row_map(_decode_raw(files[logical], logical))[CHARACTER_KEY] != structure_rows[logical]:
            raise AssertionError(f"locked structural row changed: {logical}")

    claims = _claims()
    _verify_outputs(files, claims)
    outer_changes, inner_changes = _verify_nonowned(base, files, claims)
    if outer_changes or inner_changes:
        raise AssertionError(
            f"non-owned table bytes changed: outer={outer_changes}, inner={inner_changes}"
        )

    output_sha256 = {logical: _sha256(payload) for logical, payload in files.items()}
    claims_sha256 = _sha256(
        json.dumps(
            claims, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    report = {
        "schema_version": 1,
        "status": "compiled_isolated_master_tables",
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_id": PACKAGE_ID,
        "table_count": len(files),
        "table_claim_count": len(claims),
        "locked_structure_sha256": dict(LOCKED_STRUCTURE_SHA256),
        "output_sha256": output_sha256,
        "table_claims_sha256": claims_sha256,
        "mana_node_counts": {"1": 23, "2": 18},
        "nonowned_outer_changes": outer_changes,
        "nonowned_inner_changes": inner_changes,
        "awake_status_packaged": False,
        "writes_live": False,
        "table_claims_eligible": True,
        "package_manifest_eligible": False,
        "next_gate": (
            "assemble these full-table payloads and exact claims with the accepted "
            "assets/server payloads, then run workspace status/rebase/preflight/seal"
        ),
    }
    return {"files": files, "table_claims": claims, "report": report}


__all__ = [
    "CHARACTER_ID", "CODE_NAME", "PACKAGE_ID", "TABLE_CODECS",
    "LOCKED_STRUCTURE_SHA256", "TRIM_ROWS",
    "compile_summer_thunder_master_tables",
]
