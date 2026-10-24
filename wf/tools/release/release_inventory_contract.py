#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema and orderedmap projection primitives for release inventories."""
from __future__ import annotations

import hashlib
import json
import re
import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast

import wf_character_pack as character_pack
import wf_mod_tool as core


SCHEMA = "wf-release-inventory/v1"
ROOTS = ("common", "medium", "android", "server")
CLIENT_ROOTS = ("common", "medium", "android")
TABLE_CODECS = frozenset({
    "flat", "raw_outer", "action_nested", "switched_nested", "json_object"
})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TOP_FIELDS = frozenset({"schema", "contract_id", "members"})
BASE_MEMBER_FIELDS = frozenset({"owner", "kind", "root", "logical_path"})
TABLE_MEMBER_FIELDS = BASE_MEMBER_FIELDS | {"claim", "projection_sha256", "source"}
FILE_MEMBER_FIELDS = BASE_MEMBER_FIELDS | {"size", "sha256"}
CLAIM_FIELDS = frozenset({"codec_id", "outer_keys", "inner_keys"})
SOURCE_FIELDS = frozenset({"size", "sha256"})
MemberKey = tuple[str, str]


class InventoryError(RuntimeError):
    """The frozen inventory or its read-only evidence is unsafe."""


@dataclass(frozen=True, slots=True)
class InventoryMember:
    owner: str
    kind: str
    root: str
    logical_path: str
    size: int | None = None
    sha256: str | None = None
    claim: character_pack.TableClaim | None = None
    projection_sha256: str | None = None
    source_size: int | None = None
    source_sha256: str | None = None

    @property
    def key(self) -> MemberKey:
        return self.root, self.logical_path


@dataclass(frozen=True, slots=True)
class InventoryContract:
    contract_id: str
    members: tuple[InventoryMember, ...]


@dataclass(frozen=True, slots=True)
class Projection:
    rows: tuple[tuple[str, str | None, bytes], ...]


def _duplicate_free_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def _json(raw: bytes, label: str) -> object:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_free_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise InventoryError(f"{label}: {error}") from error


def _fields(value: object, allowed: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InventoryError(f"{label}: must be an object")
    extra = sorted(set(value) - allowed)
    if extra:
        raise InventoryError(f"{label}: unexpected field {extra[0]!r}")
    return value


def validate_logical_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise InventoryError(f"{label}: logical_path must be non-empty")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        value.startswith("/") or windows.is_absolute() or windows.drive
        or "\\" in value or posix.as_posix() != value
        or ":" in value
        or any(unicodedata.category(character) == "Cc" for character in value)
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise InventoryError(f"{label}: unsafe logical_path {value!r}")
    return value


def _strings(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise InventoryError(f"{label}: must be a non-empty array")
    if any(not isinstance(item, str) or not item for item in value):
        raise InventoryError(f"{label}: keys must be non-empty strings")
    result = tuple(cast(list[str], value))
    if len(set(result)) != len(result):
        raise InventoryError(f"{label}: duplicate key")
    return result


def _claim(value: object, root: str, logical: str, label: str) -> character_pack.TableClaim:
    obj = _fields(value, CLAIM_FIELDS, label)
    missing = sorted(CLAIM_FIELDS - set(obj))
    if missing:
        raise InventoryError(f"{label}: {missing[0]} is required")
    codec = obj["codec_id"]
    if not isinstance(codec, str) or codec not in TABLE_CODECS:
        raise InventoryError(f"{label}: unsupported codec_id {codec!r}")
    outer = _strings(obj["outer_keys"], f"{label}.outer_keys")
    inner_obj = obj["inner_keys"]
    if not isinstance(inner_obj, dict):
        raise InventoryError(f"{label}.inner_keys: must be an object")
    inner = tuple(
        (key, _strings(rows, f"{label}.inner_keys.{key}"))
        for key, rows in inner_obj.items()
        if isinstance(key, str) and key
    )
    if len(inner) != len(inner_obj):
        raise InventoryError(f"{label}.inner_keys: keys must be non-empty strings")
    nested = codec in {"action_nested", "switched_nested"}
    if nested and set(key for key, _rows in inner) != set(outer):
        raise InventoryError(f"{label}: inner_keys must exactly match outer_keys")
    if not nested and inner:
        raise InventoryError(f"{label}: inner_keys are only valid for nested codecs")
    return character_pack.TableClaim(
        cast(character_pack.RootName, root), logical, codec, outer, inner
    )


def parse_contract(raw: bytes) -> InventoryContract:
    payload = _fields(_json(raw, "inventory"), TOP_FIELDS, "inventory")
    missing = sorted(TOP_FIELDS - set(payload))
    if missing:
        raise InventoryError(f"inventory: {missing[0]} is required")
    if payload["schema"] != SCHEMA:
        raise InventoryError(f"unsupported schema: {payload['schema']!r}")
    contract_id = payload["contract_id"]
    if not isinstance(contract_id, str) or TOKEN_RE.fullmatch(contract_id) is None:
        raise InventoryError("inventory.contract_id: invalid token")
    raw_members = payload["members"]
    if not isinstance(raw_members, list) or not raw_members:
        raise InventoryError("inventory.members: must be a non-empty array")

    members: list[InventoryMember] = []
    seen: set[tuple[str, str, str]] = set()
    kinds: dict[MemberKey, set[str]] = {}
    codecs: dict[MemberKey, set[str]] = {}
    for index, raw_member in enumerate(raw_members):
        label = f"inventory.members[{index}]"
        if not isinstance(raw_member, dict):
            raise InventoryError(f"{label}: must be an object")
        kind = raw_member.get("kind")
        if kind not in {"table", "file"}:
            raise InventoryError(f"{label}: kind must be table or file")
        if kind == "file" and ({"claim", "projection_sha256", "source"} & set(raw_member)):
            raise InventoryError(f"{label}: file member cannot declare claim fields")
        if kind == "table" and ({"size", "sha256"} & set(raw_member)):
            raise InventoryError(f"{label}: table member cannot declare whole-file fields")
        allowed = TABLE_MEMBER_FIELDS if kind == "table" else FILE_MEMBER_FIELDS
        obj = _fields(raw_member, allowed, label)
        missing = sorted(allowed - set(obj))
        if missing:
            raise InventoryError(f"{label}: {missing[0]} is required")
        owner, root = obj["owner"], obj["root"]
        if not isinstance(owner, str) or TOKEN_RE.fullmatch(owner) is None:
            raise InventoryError(f"{label}.owner: invalid token")
        if not isinstance(root, str) or root not in ROOTS:
            raise InventoryError(f"{label}.root: invalid root {root!r}")
        logical = validate_logical_path(obj["logical_path"], label)
        size: int | None = None
        digest: str | None = None
        claim = None
        projection_digest: str | None = None
        source_size: int | None = None
        source_digest: str | None = None
        if kind == "file":
            size, digest = cast(int, obj["size"]), cast(str, obj["sha256"])
            if type(size) is not int or size < 0:
                raise InventoryError(f"{label}.size: must be a non-negative integer")
            if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
                raise InventoryError(f"{label}.sha256: invalid sha256")
        else:
            claim = _claim(obj["claim"], root, logical, f"{label}.claim")
            projection_digest = cast(str, obj["projection_sha256"])
            if (
                not isinstance(projection_digest, str)
                or SHA256_RE.fullmatch(projection_digest) is None
            ):
                raise InventoryError(f"{label}.projection_sha256: invalid sha256")
            source = _fields(obj["source"], SOURCE_FIELDS, f"{label}.source")
            missing_source = sorted(SOURCE_FIELDS - set(source))
            if missing_source:
                raise InventoryError(
                    f"{label}.source: {missing_source[0]} is required"
                )
            source_size = cast(int, source["size"])
            source_digest = cast(str, source["sha256"])
            if type(source_size) is not int or source_size < 0:
                raise InventoryError(
                    f"{label}.source.size: must be a non-negative integer"
                )
            if (
                not isinstance(source_digest, str)
                or SHA256_RE.fullmatch(source_digest) is None
            ):
                raise InventoryError(f"{label}.source.sha256: invalid sha256")
        identity = (cast(str, owner), cast(str, root), logical)
        if identity in seen:
            raise InventoryError(f"{label}: duplicate logical path for owner {owner}")
        seen.add(identity)
        kinds.setdefault((cast(str, root), logical), set()).add(cast(str, kind))
        if claim is not None:
            codecs.setdefault((cast(str, root), logical), set()).add(claim.codec_id)
        members.append(InventoryMember(
            cast(str, owner), cast(str, kind), cast(str, root), logical,
            size, digest, claim, projection_digest, source_size, source_digest,
        ))
    for key, member_kinds in kinds.items():
        if len(member_kinds) > 1:
            raise InventoryError(f"file/table ownership conflict: {key[0]}:{key[1]}")
    for key, member_codecs in codecs.items():
        if len(member_codecs) > 1:
            raise InventoryError(f"table codec conflict: {key[0]}:{key[1]}")
    return InventoryContract(cast(str, contract_id), tuple(members))


def load_contract(path: Path) -> InventoryContract:
    try:
        return parse_contract(Path(path).read_bytes())
    except OSError as error:
        raise InventoryError(f"cannot read inventory contract {path}: {error}") from error


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def project_claim(raw: bytes, claim: character_pack.TableClaim) -> Projection:
    wanted = set(claim.outer_keys)
    rows: list[tuple[str, str | None, bytes]] = []
    try:
        if claim.codec_id in {"flat", "raw_outer"}:
            keys, values = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                raw, label=claim.logical_path, compressed_rows=claim.codec_id == "flat"
            )
            rows = [(key, None, value) for key, value in zip(keys, values) if key in wanted]
        elif claim.codec_id in {"action_nested", "switched_nested"}:
            outer_keys, outer_values = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                raw, label=claim.logical_path, compressed_rows=False
            )
            inner_claims = dict(claim.inner_keys)
            for outer, inner_raw in zip(outer_keys, outer_values):
                if outer not in wanted:
                    continue
                keys, values = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                    inner_raw, label=f"{claim.logical_path}:{outer}", compressed_rows=True
                )
                selected = set(inner_claims[outer])
                selected_rows = [
                    (outer, key, value)
                    for key, value in zip(keys, values)
                    if key in selected
                ]
                found = {inner for _outer, inner, _raw in selected_rows}
                if selected - found:
                    missing = sorted(selected - found)[0]
                    raise InventoryError(
                        f"claim missing inner row {claim.logical_path}:{outer}/{missing}"
                    )
                rows.extend(selected_rows)
        elif claim.codec_id == "json_object":
            value = _json(raw, claim.logical_path)
            if not isinstance(value, dict):
                raise InventoryError(f"{claim.logical_path}: JSON table must be an object")
            rows = [
                (key, None, _canonical_json(item))
                for key, item in value.items()
                if key in wanted
            ]
        else:
            raise InventoryError(f"unsupported projection codec: {claim.codec_id}")
    except InventoryError:
        raise
    except Exception as error:
        raise InventoryError(f"cannot project {claim.logical_path}: {error}") from error
    missing_outer = wanted - {outer for outer, _inner, _raw in rows}
    if missing_outer:
        raise InventoryError(
            f"claim missing outer row {claim.logical_path}:{sorted(missing_outer)[0]}"
        )
    return Projection(tuple(rows))


def _frame(raw: bytes) -> bytes:
    return struct.pack(">Q", len(raw)) + raw


def projection_sha256(raw: bytes, claim: character_pack.TableClaim) -> str:
    digest = hashlib.sha256(b"wf-release-projection-v1\0")
    digest.update(_frame(claim.codec_id.encode("utf-8")))
    for outer, inner, row in project_claim(raw, claim).rows:
        digest.update(_frame(outer.encode("utf-8")))
        digest.update(b"\0" if inner is None else b"\1" + _frame(inner.encode("utf-8")))
        digest.update(_frame(row))
    return digest.hexdigest()
