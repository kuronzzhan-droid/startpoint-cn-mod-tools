#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.4.312 本地终态迁移的纯内存规划器。"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import wf_mod_tool as core


CHARACTER_LOGICAL = "master/character/character.orderedmap"
CHARACTER_TEXT_LOGICAL = "master/character/character_text.orderedmap"
SHOP_LOGICAL = "master/shop/event_item_shop.orderedmap"
CLIENT_LOGICALS = (CHARACTER_LOGICAL, CHARACTER_TEXT_LOGICAL, SHOP_LOGICAL)

SERVER_CHARACTER = "cdndata/character.json"
SERVER_CHARACTER_TEXT = "cdndata/character_text.json"
SERVER_EQUIPMENT_LOOKUP = "equipment_lookup.json"
SERVER_FILES = (SERVER_CHARACTER, SERVER_CHARACTER_TEXT, SERVER_EQUIPMENT_LOOKUP)

OLD_WEAPON_NAMES = (
    "灰烬巨剑", "熔核法杖", "深潮长枪", "冻海战锚", "雷鸣双刃",
    "轰电战锤", "裂空战镰", "苍岚长弓", "晨星圣剑", "辉环法器",
    "蚀月大剑", "冥灯魔杖", "深渊征服者", "深渊轮转核", "深渊万象铳",
)
NEW_WEAPON_NAMES = (
    "深渊·灰烬巨剑", "深渊·熔核法杖", "深渊·深潮长枪", "深渊·冻海战锚",
    "深渊·雷鸣双刃", "深渊·轰电战锤", "深渊·裂空战镰", "深渊·苍岚长弓",
    "深渊·晨星圣剑", "深渊·辉环法器", "深渊·蚀月大剑", "深渊·冥灯魔杖",
    "深渊·征服者", "深渊·轮转核", "深渊·万象铳",
)


class MigrationError(RuntimeError):
    """冻结状态、输入格式或事务边界不安全。"""


@dataclass(frozen=True, slots=True)
class ClientSourceSpec:
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ClientRowSpec:
    logical_path: str
    key: str
    column_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class NameRowSpec:
    key: str
    before_name: str
    after_name: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True, slots=True)
class ServerRowSpec:
    logical_path: str
    key: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True, slots=True)
class NameJsonSpec:
    key: str
    before_name: str
    after_name: str
    before_sha256: str
    after_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenContract:
    shop_preimage: ClientSourceSpec
    shop_terminal: ClientSourceSpec
    client_rows: tuple[ClientRowSpec, ...]
    shop_rows: tuple[NameRowSpec, ...]
    server_rows: tuple[ServerRowSpec, ...]
    lookup_rows: tuple[NameJsonSpec, ...]
    source_member_count: int = 18


@dataclass(frozen=True, slots=True)
class JsonLayout:
    style: str
    newline: str


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    client_after: dict[str, bytes]
    server_after: dict[str, bytes]
    changes: tuple[str, ...]


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _duplicate_free_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def strict_json_object(raw: bytes, label: str) -> dict[str, object]:
    """只接受无重复键、无 NaN/Infinity 的 UTF-8 JSON object。"""
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-JSON constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_duplicate_free_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise MigrationError(f"{label}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"{label}: JSON root must be an object")
    return value


def _dump_json(value: object, layout: JsonLayout) -> bytes:
    if layout.style == "compact":
        text = json.dumps(
            value, ensure_ascii=False, sort_keys=False, separators=(",", ":"),
            allow_nan=False,
        )
    elif layout.style == "indent1":
        text = json.dumps(
            value, ensure_ascii=False, sort_keys=False, indent=1, allow_nan=False,
        )
    else:
        raise MigrationError(f"unsupported JSON format style {layout.style!r}")
    return text.replace("\n", layout.newline).encode("utf-8")


def _json_layout(raw: bytes, value: object, logical: str) -> JsonLayout:
    candidates = (
        (JsonLayout("compact", "\n"),)
        if logical in {SERVER_CHARACTER, SERVER_CHARACTER_TEXT}
        else (JsonLayout("indent1", "\n"), JsonLayout("indent1", "\r\n"))
    )
    for layout in candidates:
        if _dump_json(value, layout) == raw:
            return layout
    raise MigrationError(f"{logical}: unsupported JSON format")


def one_csv_row(raw: bytes, label: str, columns: int) -> list[str]:
    try:
        rows = core.read_csv_lines(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MigrationError(f"{label}: invalid UTF-8 CSV row") from exc
    if len(rows) != 1 or len(rows[0]) != columns:
        actual = len(rows[0]) if len(rows) == 1 else f"{len(rows)} rows"
        raise MigrationError(
            f"{label}: expected one {columns}-column CSV row, got {actual}"
        )
    return list(rows[0])


def _flat_rows(raw: bytes, logical: str) -> tuple[list[str], list[bytes]]:
    try:
        return core._strict_orderedmap_rows(  # type: ignore[attr-defined]
            raw, label=logical, compressed_rows=True,
        )
    except Exception as exc:
        raise MigrationError(f"{logical}: {exc}") from exc


def _build_flat(logical: str, keys: list[str], rows: list[bytes]) -> bytes:
    try:
        return core.build_orderedmap(
            core.OrderedMap(logical, list(keys), list(rows), Path("<migration>"))
        )
    except Exception as exc:
        raise MigrationError(f"{logical}: cannot encode orderedmap: {exc}") from exc


def _required(mapping: Mapping[str, bytes], key: str, label: str) -> bytes:
    raw = mapping.get(key)
    if not isinstance(raw, bytes):
        raise MigrationError(f"missing or non-bytes {label}: {key}")
    return raw


def _extract_client_rows(
    tables: Mapping[str, bytes], contract: FrozenContract,
) -> dict[tuple[str, str], list[str]]:
    decoded: dict[str, dict[str, bytes]] = {}
    result: dict[tuple[str, str], list[str]] = {}
    for spec in contract.client_rows:
        if spec.logical_path not in {CHARACTER_LOGICAL, CHARACTER_TEXT_LOGICAL}:
            raise MigrationError(f"unsupported client source {spec.logical_path}")
        if spec.logical_path not in decoded:
            keys, rows = _flat_rows(tables[spec.logical_path], spec.logical_path)
            decoded[spec.logical_path] = dict(zip(keys, rows))
        raw = decoded[spec.logical_path].get(spec.key)
        if raw is None or sha256(raw) != spec.sha256:
            raise MigrationError(
                f"{spec.logical_path}:{spec.key}: exact client row drift"
            )
        result[(spec.logical_path, spec.key)] = one_csv_row(
            raw, f"{spec.logical_path}:{spec.key}", spec.column_count,
        )
    expected = {
        (logical, key)
        for logical in (CHARACTER_LOGICAL, CHARACTER_TEXT_LOGICAL)
        for key in ("169998", "169999")
    }
    if len(contract.client_rows) != 4 or set(result) != expected:
        raise MigrationError("client character source contract is incomplete")
    if result[(CHARACTER_TEXT_LOGICAL, "169999")][1] != "GINOVI":
        raise MigrationError("character_text:169999 must already be GINOVI")
    return result


def _source(raw: bytes) -> ClientSourceSpec:
    return ClientSourceSpec(len(raw), sha256(raw))


def _migrate_shop(raw: bytes, contract: FrozenContract) -> tuple[bytes, bool]:
    specs = contract.shop_rows
    expected_keys = tuple(str(9_700_101 + offset) for offset in range(15))
    if tuple(spec.key for spec in specs) != expected_keys:
        raise MigrationError("shop contract must contain the exact 15 ordered rows")
    source = _source(raw)
    if source == contract.shop_preimage:
        source_state = "before"
    elif source == contract.shop_terminal:
        source_state = "after"
    else:
        raise MigrationError("event_item_shop whole source drift")
    keys, rows = _flat_rows(raw, SHOP_LOGICAL)
    positions = {key: index for index, key in enumerate(keys)}
    states: list[str] = []
    for spec in specs:
        if spec.key not in positions:
            raise MigrationError(f"shop missing row {spec.key}")
        leaf = rows[positions[spec.key]]
        cells = one_csv_row(leaf, f"shop:{spec.key}", 51)
        digest = sha256(leaf)
        if digest == spec.before_sha256 and cells[7] == spec.before_name:
            states.append("before")
        elif digest == spec.after_sha256 and cells[7] == spec.after_name:
            states.append("after")
        else:
            raise MigrationError(f"shop:{spec.key}: foreign row drift")
    if set(states) != {source_state}:
        raise MigrationError("shop source and grouped row states disagree")
    if source_state == "after":
        return raw, False
    changed = list(rows)
    for spec in specs:
        index = positions[spec.key]
        before = one_csv_row(changed[index], f"shop:{spec.key}", 51)
        after = list(before)
        after[7] = spec.after_name
        encoded = core.write_csv_lines([after]).encode("utf-8")
        if sha256(encoded) != spec.after_sha256:
            raise MigrationError(f"shop:{spec.key}: frozen terminal row mismatch")
        changed[index] = encoded
    output = _build_flat(SHOP_LOGICAL, keys, changed)
    if _source(output) != contract.shop_terminal:
        raise MigrationError("event_item_shop terminal whole source mismatch")
    return output, True


def _migrate_server_rows(
    raw: bytes, relative: str, specs: Sequence[ServerRowSpec],
    client_rows: Mapping[tuple[str, str], list[str]],
) -> tuple[bytes, tuple[str, ...]]:
    value = strict_json_object(raw, relative)
    layout = _json_layout(raw, value, relative)
    updated = copy.deepcopy(value)
    source = CHARACTER_LOGICAL if relative == SERVER_CHARACTER else CHARACTER_TEXT_LOGICAL
    changes: list[str] = []
    for spec in specs:
        if spec.logical_path != relative or spec.key not in {"169998", "169999"}:
            raise MigrationError(f"invalid server character claim {relative}:{spec.key}")
        if spec.key not in value:
            raise MigrationError(f"{relative}: missing key {spec.key}")
        after = [copy.deepcopy(client_rows[(source, spec.key)])]
        if sha256(canonical(after)) != spec.after_sha256:
            raise MigrationError(f"{relative}:{spec.key}: contract/client mismatch")
        digest = sha256(canonical(value[spec.key]))
        if digest == spec.after_sha256:
            continue
        if digest != spec.before_sha256:
            raise MigrationError(f"{relative}:{spec.key}: foreign server row drift")
        updated[spec.key] = after
        changes.append(f"server:{relative}:{spec.key}")
    if not changes:
        return raw, ()
    output = _dump_json(updated, layout)
    check = strict_json_object(output, relative)
    owned = {spec.key for spec in specs}
    if list(check) != list(value) or any(
        check[key] != value[key] for key in value if key not in owned
    ):
        raise MigrationError(f"{relative}: unrelated data or key order changed")
    return output, tuple(changes)


def _migrate_lookup(raw: bytes, specs: tuple[NameJsonSpec, ...]) -> tuple[bytes, bool]:
    expected_keys = tuple(str(8_000_101 + offset) for offset in range(15))
    if tuple(spec.key for spec in specs) != expected_keys:
        raise MigrationError("lookup contract must contain the exact 15 ordered rows")
    value = strict_json_object(raw, SERVER_EQUIPMENT_LOOKUP)
    layout = _json_layout(raw, value, SERVER_EQUIPMENT_LOOKUP)
    states: list[str] = []
    for spec in specs:
        entry = value.get(spec.key)
        if not isinstance(entry, dict):
            raise MigrationError(f"lookup missing object {spec.key}")
        digest = sha256(canonical(entry))
        if digest == spec.before_sha256 and entry.get("name") == spec.before_name:
            states.append("before")
        elif digest == spec.after_sha256 and entry.get("name") == spec.after_name:
            states.append("after")
        else:
            raise MigrationError(f"lookup:{spec.key}: foreign row drift")
    if len(set(states)) != 1:
        raise MigrationError("lookup migration group mixes before and after rows")
    if states[0] == "after":
        return raw, False
    updated = copy.deepcopy(value)
    for spec in specs:
        entry = updated[spec.key]
        if not isinstance(entry, dict):
            raise MigrationError(f"lookup missing object {spec.key}")
        entry["name"] = spec.after_name
        if sha256(canonical(entry)) != spec.after_sha256:
            raise MigrationError(f"lookup:{spec.key}: frozen terminal row mismatch")
    output = _dump_json(updated, layout)
    check = strict_json_object(output, SERVER_EQUIPMENT_LOOKUP)
    owned = {spec.key for spec in specs}
    if list(check) != list(value) or any(
        check[key] != value[key] for key in value if key not in owned
    ):
        raise MigrationError("equipment_lookup unrelated data or key order changed")
    return output, True


def plan_terminal_migration(
    client_tables: Mapping[str, bytes], server_files: Mapping[str, bytes], *,
    contract: FrozenContract,
) -> MigrationPlan:
    """先在内存中验证并规划全部六个目标，不暴露半成品。"""
    if contract.source_member_count != 18:
        raise MigrationError("source migration contract must contain exactly 18 members")
    client_before = {
        logical: _required(client_tables, logical, "client table")
        for logical in CLIENT_LOGICALS
    }
    server_before = {
        relative: _required(server_files, relative, "server file")
        for relative in SERVER_FILES
    }
    client_rows = _extract_client_rows(client_before, contract)
    client_after, server_after = dict(client_before), dict(server_before)
    changes: list[str] = []
    client_after[SHOP_LOGICAL], changed = _migrate_shop(
        client_before[SHOP_LOGICAL], contract,
    )
    if changed:
        changes.append("client:event_item_shop:9700101..9700115")
    by_server: dict[str, list[ServerRowSpec]] = {}
    for spec in contract.server_rows:
        by_server.setdefault(spec.logical_path, []).append(spec)
    expected_server = {
        (relative, key)
        for relative in (SERVER_CHARACTER, SERVER_CHARACTER_TEXT)
        for key in ("169998", "169999")
    }
    if (
        len(contract.server_rows) != 4
        or {(spec.logical_path, spec.key) for spec in contract.server_rows}
        != expected_server
    ):
        raise MigrationError("server character migration contract is incomplete")
    for relative in (SERVER_CHARACTER, SERVER_CHARACTER_TEXT):
        server_after[relative], row_changes = _migrate_server_rows(
            server_before[relative], relative, by_server[relative], client_rows,
        )
        changes.extend(row_changes)
    server_after[SERVER_EQUIPMENT_LOOKUP], changed = _migrate_lookup(
        server_before[SERVER_EQUIPMENT_LOOKUP], contract.lookup_rows,
    )
    if changed:
        changes.append("server:equipment_lookup:8000101..8000115")
    return MigrationPlan(client_after, server_after, tuple(changes))
