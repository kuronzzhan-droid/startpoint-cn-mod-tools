#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict selectors for frozen client/server migration preimages and targets."""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import wf_character_pack as character_pack
import wf_mod_tool as core
from wf_contract_json import load_json_strict, parse_json_strict
from wf_release_inventory import projection_sha256
from wf_release_inventory_contract import validate_logical_path


SCHEMA = "wf-local-migration-contract/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class MigrationError(RuntimeError):
    """The migration contract or selected local state is outside its allowlist."""


@dataclass(frozen=True, slots=True)
class ClientState:
    source_size: int
    source_sha256: str
    projection_sha256: str
    rows: tuple[tuple[str, str | None, bytes], ...]


@dataclass(frozen=True, slots=True)
class ClientTableMigration:
    owner: str
    root: str
    logical_path: str
    claim: character_pack.TableClaim
    preimage: ClientState
    terminal: ClientState

    @property
    def preimage_sha256(self) -> str:
        return self.preimage.projection_sha256

    @property
    def terminal_sha256(self) -> str:
        return self.terminal.projection_sha256


@dataclass(frozen=True, slots=True)
class ServerSelector:
    kind: str
    path: tuple[str, ...]
    keys: tuple[str, ...] = ()
    values: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ServerMember:
    owner: str
    logical_path: str
    selector: ServerSelector
    preimage_sha256: str
    terminal_sha256: str
    preimage: Any
    terminal: Any


@dataclass(frozen=True, slots=True)
class MigrationContract:
    contract_id: str
    terminal_contract_id: str
    client_tables: tuple[ClientTableMigration, ...]
    server_members: tuple[ServerMember, ...]


def _exact(value: object, fields: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise MigrationError(f"{label}: fields must be exactly {sorted(fields)}")
    return value


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise MigrationError(f"{label}: invalid sha256")
    return value


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise MigrationError(f"cannot canonicalize server projection: {error}") from error


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _client_state(value: object, claim: character_pack.TableClaim, label: str) -> ClientState:
    obj = _exact(value, {
        "source_size", "source_sha256", "projection_sha256", "rows"
    }, label)
    size = obj["source_size"]
    if type(size) is not int or size < 0:
        raise MigrationError(f"{label}.source_size: invalid size")
    raw_rows = obj["rows"]
    if not isinstance(raw_rows, list):
        raise MigrationError(f"{label}.rows: must be an array")
    rows: list[tuple[str, str | None, bytes]] = []
    for index, raw in enumerate(raw_rows):
        row = _exact(raw, {"outer", "inner", "row_base64"}, f"{label}.rows[{index}]")
        if not isinstance(row["outer"], str) or row["inner"] is not None:
            raise MigrationError(f"{label}.rows[{index}]: invalid flat row key")
        encoded = row["row_base64"]
        if not isinstance(encoded, str):
            raise MigrationError(f"{label}.rows[{index}].row_base64: must be string")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise MigrationError(f"{label}.rows[{index}]: invalid base64") from error
        rows.append((row["outer"], None, decoded))
    if tuple(outer for outer, _inner, _raw in rows) != claim.outer_keys:
        raise MigrationError(f"{label}.rows: keys/order differ from claim")
    minimal = core.build_orderedmap(core.OrderedMap(
        label, list(claim.outer_keys), [raw for _outer, _inner, raw in rows],
        Path("<contract>"),
    ))
    expected = _sha(obj["projection_sha256"], f"{label}.projection_sha256")
    if projection_sha256(minimal, claim) != expected:
        raise MigrationError(f"{label}.projection_sha256: row digest mismatch")
    return ClientState(
        size, _sha(obj["source_sha256"], f"{label}.source_sha256"), expected,
        tuple(rows),
    )


def _client(value: object, label: str) -> ClientTableMigration:
    obj = _exact(value, {
        "owner", "root", "logical_path", "claim", "preimage", "terminal"
    }, label)
    if (
        obj["root"] != "common" or not isinstance(obj["owner"], str)
        or TOKEN_RE.fullmatch(obj["owner"]) is None
    ):
        raise MigrationError(f"{label}: unsupported owner/root")
    try:
        logical = validate_logical_path(obj["logical_path"], label)
    except Exception as error:
        raise MigrationError(str(error)) from error
    claim_obj = _exact(obj["claim"], {"codec_id", "outer_keys", "inner_keys"}, label)
    if claim_obj["codec_id"] != "flat" or claim_obj["inner_keys"] != {}:
        raise MigrationError(f"{label}.claim: only exact flat migration is supported")
    keys = claim_obj["outer_keys"]
    if (
        not isinstance(keys, list) or not keys
        or any(not isinstance(key, str) or not key for key in keys)
        or keys != list(dict.fromkeys(keys))
    ):
        raise MigrationError(f"{label}.claim.outer_keys: invalid keys")
    claim = character_pack.TableClaim("common", logical, "flat", tuple(keys))
    return ClientTableMigration(
        obj["owner"], "common", logical, claim,
        _client_state(obj["preimage"], claim, f"{label}.preimage"),
        _client_state(obj["terminal"], claim, f"{label}.terminal"),
    )


def _selector(value: object, label: str) -> ServerSelector:
    if not isinstance(value, dict):
        raise MigrationError(f"{label}: selector must be an object")
    kind = value.get("kind")
    fields = {"kind", "path", "keys"} if kind == "object_keys" else {
        "kind", "path", "values"
    }
    obj = _exact(value, fields, label)
    path = obj["path"]
    if not isinstance(path, list) or any(not isinstance(key, str) or not key for key in path):
        raise MigrationError(f"{label}.path: invalid path")
    if kind == "object_keys":
        keys = obj["keys"]
        if (
            not isinstance(keys, list) or not keys
            or any(not isinstance(key, str) or not key for key in keys)
            or keys != list(dict.fromkeys(keys))
        ):
            raise MigrationError(f"{label}.keys: invalid keys")
        return ServerSelector(kind, tuple(path), tuple(keys))
    if kind == "array_subsequence":
        values = obj["values"]
        if (
            not isinstance(values, list) or not values
            or any(type(item) is not int for item in values)
            or len(set(values)) != len(values)
        ):
            raise MigrationError(f"{label}.values: invalid values")
        return ServerSelector(kind, tuple(path), values=tuple(values))
    raise MigrationError(f"{label}: unsupported selector kind")


def _server(value: object, label: str) -> ServerMember:
    obj = _exact(value, {
        "owner", "logical_path", "selector", "preimage_sha256",
        "terminal_sha256", "preimage", "terminal",
    }, label)
    if (
        not isinstance(obj["owner"], str)
        or TOKEN_RE.fullmatch(obj["owner"]) is None
    ):
        raise MigrationError(f"{label}.owner: invalid owner")
    try:
        logical = validate_logical_path(obj["logical_path"], label)
    except Exception as error:
        raise MigrationError(str(error)) from error
    selector = _selector(obj["selector"], f"{label}.selector")
    before, after = obj["preimage"], obj["terminal"]
    if selector.kind == "object_keys":
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise MigrationError(f"{label}: object selector requires object projections")
        if tuple(before) != selector.keys or tuple(after) != selector.keys:
            raise MigrationError(f"{label}: selector keys do not match projections")
    elif before != list(selector.values) or after != list(selector.values):
        raise MigrationError(f"{label}: array selector differs from frozen subsequence")
    before_sha = _sha(obj["preimage_sha256"], label)
    after_sha = _sha(obj["terminal_sha256"], label)
    if _digest(before) != before_sha or _digest(after) != after_sha:
        raise MigrationError(f"{label}: selector projection digest mismatch")
    return ServerMember(
        obj["owner"], logical, selector, before_sha, after_sha, before, after
    )


def parse_contract(value: object) -> MigrationContract:
    obj = _exact(value, {
        "schema", "contract_id", "terminal_contract_id", "client_tables",
        "server_members",
    }, "migration")
    if obj["schema"] != SCHEMA:
        raise MigrationError("migration: unsupported schema")
    for field in ("contract_id", "terminal_contract_id"):
        token = obj[field]
        if not isinstance(token, str) or TOKEN_RE.fullmatch(token) is None:
            raise MigrationError(f"migration.{field}: invalid contract_id token")
    clients = obj["client_tables"]
    servers = obj["server_members"]
    if not isinstance(clients, list) or not isinstance(servers, list):
        raise MigrationError("migration: member fields must be arrays")
    result = MigrationContract(
        obj["contract_id"], obj["terminal_contract_id"],
        tuple(_client(item, f"migration.client_tables[{index}]") for index, item in enumerate(clients)),
        tuple(_server(item, f"migration.server_members[{index}]") for index, item in enumerate(servers)),
    )
    identities = [
        (member.owner, member.logical_path, member.selector.path, member.selector.keys)
        for member in result.server_members
    ]
    if len(set(identities)) != len(identities):
        raise MigrationError("migration.server_members: duplicate selector")
    return result


def load_contract(path: Path) -> MigrationContract:
    return parse_contract(load_json_strict(path, MigrationError, "migration contract"))


def project_server_member(member: ServerMember, raw: bytes) -> object:
    try:
        value: object = parse_json_strict(raw, MigrationError, member.logical_path)
        for key in member.selector.path:
            if not isinstance(value, dict):
                raise KeyError(key)
            value = value[key]
        if member.selector.kind == "object_keys":
            if not isinstance(value, dict):
                raise TypeError("selected node is not an object")
            return {key: value[key] for key in member.selector.keys}
        if not isinstance(value, list):
            raise TypeError("selected node is not an array")
        wanted = set(member.selector.values)
        selected = [item for item in value if item in wanted]
        if selected != list(member.selector.values):
            raise ValueError("array subsequence is missing or reordered")
        return selected
    except (UnicodeDecodeError, ValueError, TypeError, KeyError) as error:
        raise MigrationError(f"cannot project server member {member.logical_path}: {error}") from error


def classify_server_member(member: ServerMember, raw: bytes) -> str:
    digest = _digest(project_server_member(member, raw))
    if digest == member.terminal_sha256:
        return "terminal"
    if digest == member.preimage_sha256:
        return "preimage"
    raise MigrationError(f"unapproved server projection drift: {member.logical_path}")


def classify_client_table(member: ClientTableMigration, raw: bytes) -> str:
    try:
        digest = projection_sha256(raw, member.claim)
    except Exception as error:
        raise MigrationError(
            f"cannot project client table {member.logical_path}: {error}"
        ) from error
    source = len(raw), hashlib.sha256(raw).hexdigest()
    terminal_source = member.terminal.source_size, member.terminal.source_sha256
    preimage_source = member.preimage.source_size, member.preimage.source_sha256
    if digest == member.terminal_sha256 and source == terminal_source:
        return "terminal"
    if digest == member.preimage_sha256 and source == preimage_source:
        return "preimage"
    raise MigrationError(f"unapproved client source/projection drift: {member.logical_path}")
