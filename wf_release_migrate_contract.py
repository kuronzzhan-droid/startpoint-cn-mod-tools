#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Task3A 的严格迁移合同适配为 1.4.312 规划器输入。"""
from __future__ import annotations

from pathlib import Path

import wf_local_server_contract as source_contract
import wf_mod_tool as core
from wf_release_migrate_plan import (
    CHARACTER_LOGICAL,
    CHARACTER_TEXT_LOGICAL,
    NEW_WEAPON_NAMES,
    OLD_WEAPON_NAMES,
    SERVER_CHARACTER,
    SERVER_CHARACTER_TEXT,
    SERVER_EQUIPMENT_LOOKUP,
    SHOP_LOGICAL,
    ClientRowSpec,
    ClientSourceSpec,
    FrozenContract,
    MigrationError,
    NameJsonSpec,
    NameRowSpec,
    ServerRowSpec,
    canonical,
    one_csv_row,
    sha256,
)


DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "release-contracts"
    / "local-live-migrations-1.4.312.json"
)
EXPECTED_CONTRACT_ID = "local-live-migrations-1-4-312"
EXPECTED_TERMINAL_ID = "local-live-terminal-1-4-312"
WEAPON_KEYS = tuple(str(8_000_101 + offset) for offset in range(15))
SHOP_KEYS = tuple(str(9_700_101 + offset) for offset in range(15))
TOWER_KEYS = tuple(str(700_099_001 + offset) for offset in range(30)) + ("700099099",)

# 顺序和 selector 都是合同语义的一部分；被本写事务忽略的成员也不得被替换。
EXPECTED_SERVER_SCOPE = (
    ("lafu_lunar_ny", SERVER_CHARACTER, "object_keys", (), ("169998",), ()),
    ("lafu_lunar_ny", SERVER_CHARACTER_TEXT, "object_keys", (), ("169998",), ()),
    ("lafu_lunar_ny", "character.json", "object_keys", (), ("169998",), ()),
    ("lafu_lunar_ny", "mana_node.json", "object_keys", (), ("169998",), ()),
    ("ginovi", SERVER_CHARACTER, "object_keys", (), ("169999",), ()),
    ("ginovi", SERVER_CHARACTER_TEXT, "object_keys", (), ("169999",), ()),
    ("ginovi", "character.json", "object_keys", (), ("169999",), ()),
    ("ginovi", "mana_node.json", "object_keys", (), ("169999",), ()),
    ("abyss_weapons", SERVER_EQUIPMENT_LOOKUP, "object_keys", (), WEAPON_KEYS, ()),
    ("abyss_weapons", "equipment_max_level.json", "object_keys", (), WEAPON_KEYS, ()),
    ("abyss_weapons", "equipment_element.json", "object_keys", (), WEAPON_KEYS, ()),
    (
        "abyss_weapons", "equipment_ids.json", "array_subsequence", (), (),
        tuple(range(8_000_101, 8_000_116)),
    ),
    ("abyss_700099_core", "item_ids.json", "array_subsequence", (), (), (2_370_099,)),
    (
        "abyss_weapons", "event_item_shop.json", "object_keys",
        ("11", "700099"), SHOP_KEYS, (),
    ),
    ("abyss_weapons", "event_item_shop_id_map.json", "object_keys", (), SHOP_KEYS, ()),
    ("abyss_tower", "rush_event_quest.json", "object_keys", (), TOWER_KEYS, ()),
    ("abyss_tower", "rush_event_quest_folder.json", "object_keys", (), ("700099",), ()),
    ("abyss_tower", "rogue_event.json", "object_keys", ("events",), ("700099",), ()),
)


def _rows(state: source_contract.ClientState) -> dict[str, bytes]:
    return {outer: raw for outer, inner, raw in state.rows if inner is None}


def _require_exact_server_scope(contract: source_contract.MigrationContract) -> None:
    actual = tuple(
        (
            member.owner, member.logical_path, member.selector.kind,
            member.selector.path, member.selector.keys, member.selector.values,
        )
        for member in contract.server_members
    )
    if actual != EXPECTED_SERVER_SCOPE:
        raise MigrationError("Task3A server member scope/order differs from frozen 18-member set")


def _server_members(
    contract: source_contract.MigrationContract,
) -> tuple[tuple[ServerRowSpec, ...], tuple[NameJsonSpec, ...]]:
    character: dict[tuple[str, str], ServerRowSpec] = {}
    lookup_member: source_contract.ServerMember | None = None
    for member in contract.server_members:
        if member.logical_path == SERVER_EQUIPMENT_LOOKUP:
            if lookup_member is not None:
                raise MigrationError("duplicate equipment_lookup migration member")
            lookup_member = member
            continue
        if member.logical_path not in {SERVER_CHARACTER, SERVER_CHARACTER_TEXT}:
            continue
        selector = member.selector
        if selector.kind != "object_keys" or selector.path or len(selector.keys) != 1:
            raise MigrationError(f"invalid server selector for {member.logical_path}")
        key = selector.keys[0]
        if key not in {"169998", "169999"}:
            raise MigrationError(f"unexpected character migration key {key}")
        identity = member.logical_path, key
        if identity in character:
            raise MigrationError(f"duplicate server migration {member.logical_path}:{key}")
        before, after = member.preimage, member.terminal
        if (
            not isinstance(before, dict) or set(before) != {key}
            or not isinstance(after, dict) or set(after) != {key}
        ):
            raise MigrationError(
                f"server migration wrapper is not exact: {member.logical_path}:{key}"
            )
        character[identity] = ServerRowSpec(
            member.logical_path, key,
            sha256(canonical(before[key])), sha256(canonical(after[key])),
        )
    expected = {
        (relative, key)
        for relative in (SERVER_CHARACTER, SERVER_CHARACTER_TEXT)
        for key in ("169998", "169999")
    }
    if set(character) != expected:
        raise MigrationError("server character migration members are incomplete")
    if lookup_member is None:
        raise MigrationError("equipment_lookup migration member is missing")
    selector = lookup_member.selector
    lookup_keys = tuple(str(8_000_101 + offset) for offset in range(15))
    if selector.kind != "object_keys" or selector.path or selector.keys != lookup_keys:
        raise MigrationError("equipment_lookup selector is not exact")
    before_values, after_values = lookup_member.preimage, lookup_member.terminal
    if not isinstance(before_values, dict) or not isinstance(after_values, dict):
        raise MigrationError("equipment_lookup projections must be objects")
    lookup: list[NameJsonSpec] = []
    for index, key in enumerate(lookup_keys):
        before, after = before_values[key], after_values[key]
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise MigrationError(f"equipment_lookup {key} must select objects")
        if before.get("name") != OLD_WEAPON_NAMES[index] or after.get("name") != NEW_WEAPON_NAMES[index]:
            raise MigrationError(f"equipment_lookup {key} has unexpected names")
        if {k: v for k, v in before.items() if k != "name"} != {
            k: v for k, v in after.items() if k != "name"
        }:
            raise MigrationError(f"equipment_lookup {key} changes non-name fields")
        lookup.append(NameJsonSpec(
            key, OLD_WEAPON_NAMES[index], NEW_WEAPON_NAMES[index],
            sha256(canonical(before)), sha256(canonical(after)),
        ))
    ordered = tuple(
        character[(relative, key)]
        for relative in (SERVER_CHARACTER, SERVER_CHARACTER_TEXT)
        for key in ("169998", "169999")
    )
    return ordered, tuple(lookup)


def _client_rows(
    contract: source_contract.MigrationContract,
) -> tuple[ClientRowSpec, ...]:
    by_identity = {
        (member.logical_path, member.selector.keys[0]): member
        for member in contract.server_members
        if member.logical_path in {SERVER_CHARACTER, SERVER_CHARACTER_TEXT}
        and member.selector.kind == "object_keys"
        and not member.selector.path
        and len(member.selector.keys) == 1
    }
    result: list[ClientRowSpec] = []
    for relative, logical, columns in (
        (SERVER_CHARACTER, CHARACTER_LOGICAL, 37),
        (SERVER_CHARACTER_TEXT, CHARACTER_TEXT_LOGICAL, 12),
    ):
        for key in ("169998", "169999"):
            member = by_identity[(relative, key)]
            wrapped = member.terminal
            if (
                not isinstance(wrapped, dict) or set(wrapped) != {key}
                or not isinstance(wrapped[key], list) or len(wrapped[key]) != 1
                or not isinstance(wrapped[key][0], list)
                or any(not isinstance(cell, str) for cell in wrapped[key][0])
            ):
                raise MigrationError(f"terminal server row is not client CSV: {relative}:{key}")
            cells = list(wrapped[key][0])
            if len(cells) != columns:
                raise MigrationError(f"terminal server row width mismatch: {relative}:{key}")
            encoded = core.write_csv_lines([cells]).encode("utf-8")
            result.append(ClientRowSpec(logical, key, columns, sha256(encoded)))
    return tuple(result)


def load_frozen_contract(path: Path = DEFAULT_CONTRACT_PATH) -> FrozenContract:
    """严格加载全部 Task3A 合同后，仅适配本迁移器拥有的投影。"""
    try:
        contract = source_contract.load_contract(Path(path))
    except (source_contract.MigrationError, OSError) as exc:
        raise MigrationError(f"cannot load Task3A migration contract: {exc}") from exc
    if (
        contract.contract_id != EXPECTED_CONTRACT_ID
        or contract.terminal_contract_id != EXPECTED_TERMINAL_ID
        or len(contract.client_tables) != 1
        or len(contract.server_members) != 18
    ):
        raise MigrationError("Task3A migration contract IDs/member counts differ")
    _require_exact_server_scope(contract)
    client = contract.client_tables[0]
    shop_keys = SHOP_KEYS
    if (
        client.owner != "abyss_weapons" or client.root != "common"
        or client.logical_path != SHOP_LOGICAL
        or client.claim.codec_id != "flat" or client.claim.outer_keys != shop_keys
    ):
        raise MigrationError("Task3A client migration is not the exact abyss shop claim")
    before_rows, after_rows = _rows(client.preimage), _rows(client.terminal)
    if tuple(before_rows) != shop_keys or tuple(after_rows) != shop_keys:
        raise MigrationError("event_item_shop migration keys are not exact")
    shop: list[NameRowSpec] = []
    for index, key in enumerate(shop_keys):
        before = one_csv_row(before_rows[key], f"contract shop before:{key}", 51)
        after = one_csv_row(after_rows[key], f"contract shop after:{key}", 51)
        if before[:7] + before[8:] != after[:7] + after[8:]:
            raise MigrationError(f"contract shop {key} changes a non-name column")
        if before[7] != OLD_WEAPON_NAMES[index] or after[7] != NEW_WEAPON_NAMES[index]:
            raise MigrationError(f"contract shop {key} has unexpected names")
        shop.append(NameRowSpec(
            key, before[7], after[7], sha256(before_rows[key]), sha256(after_rows[key]),
        ))
    server, lookup = _server_members(contract)
    return FrozenContract(
        ClientSourceSpec(client.preimage.source_size, client.preimage.source_sha256),
        ClientSourceSpec(client.terminal.source_size, client.terminal.source_sha256),
        _client_rows(contract), tuple(shop), server, lookup, len(contract.server_members),
    )
