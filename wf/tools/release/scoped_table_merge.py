#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Joint claim-order merge for scoped full-table payloads."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence, TypeVar, cast

import wf_character_pack as character_pack
import wf_mod_tool as core
from wf_release_inventory_contract import InventoryMember


T = TypeVar("T")


class ScopedTableMergeError(RuntimeError):
    """Declared rows cannot be merged without changing unclaimed content."""


def _claimed(members: Sequence[InventoryMember]) -> tuple[str, set[str]]:
    codecs: set[str] = set()
    keys: set[str] = set()
    for member in members:
        if member.kind != "table" or member.claim is None:
            raise ScopedTableMergeError("joint table merge received a non-table member")
        claim = cast(character_pack.TableClaim, member.claim)
        codecs.add(claim.codec_id)
        keys.update(claim.outer_keys)
    if len(codecs) != 1 or not keys:
        raise ScopedTableMergeError("joint table claims have conflicting codecs or no keys")
    return next(iter(codecs)), keys


def _merge_rows(
    baseline_keys: Sequence[str],
    baseline_rows: Sequence[T],
    terminal_keys: Sequence[str],
    terminal_rows: Sequence[T],
    claimed: set[str],
    *,
    label: str,
) -> tuple[list[str], list[T]]:
    if len(baseline_keys) != len(baseline_rows):
        raise ScopedTableMergeError(f"baseline key/row mismatch: {label}")
    if len(terminal_keys) != len(terminal_rows):
        raise ScopedTableMergeError(f"terminal key/row mismatch: {label}")
    terminal_map = dict(zip(terminal_keys, terminal_rows, strict=True))
    missing = claimed - set(terminal_map)
    if missing:
        raise ScopedTableMergeError(
            f"terminal lacks claimed row: {label}:{sorted(missing)[0]}"
        )

    first_claimed = next(
        (index for index, key in enumerate(baseline_keys) if key in claimed), None
    )
    if first_claimed is None:
        anchor = sum(key not in claimed for key in baseline_keys)
    else:
        anchor = sum(key not in claimed for key in baseline_keys[:first_claimed])
    preserved = [
        (key, row)
        for key, row in zip(baseline_keys, baseline_rows, strict=True)
        if key not in claimed
    ]
    selected = [
        (key, terminal_map[key]) for key in terminal_keys if key in claimed
    ]
    result = [*preserved[:anchor], *selected, *preserved[anchor:]]
    keys = [key for key, _row in result]
    rows = [row for _key, row in result]

    actual_preserved = [
        (key, row)
        for key, row in zip(keys, rows, strict=True)
        if key not in claimed
    ]
    if actual_preserved != preserved:
        raise ScopedTableMergeError(f"unclaimed row drift: {label}")
    actual_selected = [
        (key, row)
        for key, row in zip(keys, rows, strict=True)
        if key in claimed
    ]
    if actual_selected != selected:
        raise ScopedTableMergeError(f"terminal claim order drift: {label}")
    return keys, rows


def _orderedmap(
    logical: str,
    keys: Sequence[str],
    rows: Sequence[bytes],
    *,
    compressed: bool,
) -> bytes:
    table = core.OrderedMap(
        logical, list(keys), list(rows), Path("<scoped-table-merge>")
    )
    return (
        core.build_orderedmap(table)
        if compressed
        else core.build_orderedmap_raw_rows(table)
    )


def _flat(
    members: Sequence[InventoryMember],
    terminal_raw: bytes,
    baseline_raw: bytes,
    codec: str,
) -> bytes:
    logical = members[0].logical_path
    compressed = codec == "flat"
    terminal_keys, terminal_rows = core._strict_orderedmap_rows(
        terminal_raw, label=f"terminal:{logical}", compressed_rows=compressed
    )
    baseline_keys, baseline_rows = core._strict_orderedmap_rows(
        baseline_raw, label=f"baseline:{logical}", compressed_rows=compressed
    )
    _codec, claimed = _claimed(members)
    keys, rows = _merge_rows(
        baseline_keys,
        baseline_rows,
        terminal_keys,
        terminal_rows,
        claimed,
        label=logical,
    )
    return _orderedmap(logical, keys, rows, compressed=compressed)


def _inner_claims(
    members: Sequence[InventoryMember], claimed_outer: set[str]
) -> dict[str, set[str]]:
    result = {outer: set() for outer in claimed_outer}
    for member in members:
        claim = cast(character_pack.TableClaim, member.claim)
        declared = dict(claim.inner_keys)
        if set(declared) != set(claim.outer_keys):
            raise ScopedTableMergeError(
                f"nested claims are incomplete: {member.logical_path}"
            )
        for outer, inner in declared.items():
            result[outer].update(inner)
    if any(not rows for rows in result.values()):
        raise ScopedTableMergeError("nested claim has no inner rows")
    return result


def _nested(
    members: Sequence[InventoryMember], terminal_raw: bytes, baseline_raw: bytes
) -> bytes:
    logical = members[0].logical_path
    terminal_keys, terminal_rows = core._strict_orderedmap_rows(
        terminal_raw, label=f"terminal:{logical}", compressed_rows=False
    )
    baseline_keys, baseline_rows = core._strict_orderedmap_rows(
        baseline_raw, label=f"baseline:{logical}", compressed_rows=False
    )
    terminal_outer = dict(zip(terminal_keys, terminal_rows, strict=True))
    baseline_outer = dict(zip(baseline_keys, baseline_rows, strict=True))
    _codec, claimed_outer = _claimed(members)
    inner_claims = _inner_claims(members, claimed_outer)
    merged_outer: dict[str, bytes] = {}
    for outer in claimed_outer:
        terminal_inner_raw = terminal_outer.get(outer)
        if terminal_inner_raw is None:
            raise ScopedTableMergeError(
                f"terminal lacks claimed nested row: {logical}:{outer}"
            )
        terminal_inner_keys, terminal_inner_rows = core._strict_orderedmap_rows(
            terminal_inner_raw,
            label=f"terminal:{logical}:{outer}",
            compressed_rows=True,
        )
        baseline_inner_raw = baseline_outer.get(outer)
        if baseline_inner_raw is None:
            baseline_inner_keys: list[str] = []
            baseline_inner_rows: list[bytes] = []
        else:
            baseline_inner_keys, baseline_inner_rows = core._strict_orderedmap_rows(
                baseline_inner_raw,
                label=f"baseline:{logical}:{outer}",
                compressed_rows=True,
            )
        keys, rows = _merge_rows(
            baseline_inner_keys,
            baseline_inner_rows,
            terminal_inner_keys,
            terminal_inner_rows,
            inner_claims[outer],
            label=f"{logical}:{outer}",
        )
        merged_outer[outer] = _orderedmap(
            f"{logical}#{outer}", keys, rows, compressed=True
        )

    terminal_merged_rows = [
        merged_outer.get(key, row)
        for key, row in zip(terminal_keys, terminal_rows, strict=True)
    ]
    keys, rows = _merge_rows(
        baseline_keys,
        baseline_rows,
        terminal_keys,
        terminal_merged_rows,
        claimed_outer,
        label=logical,
    )
    return _orderedmap(logical, keys, rows, compressed=False)


def _strict_object(raw: bytes, label: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise ValueError(f"non-JSON constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ScopedTableMergeError(f"invalid JSON table {label}: {error}") from error
    if not isinstance(value, dict):
        raise ScopedTableMergeError(f"JSON table must be an object: {label}")
    return value


def _json_table(
    members: Sequence[InventoryMember], terminal_raw: bytes, baseline_raw: bytes
) -> bytes:
    logical = members[0].logical_path
    terminal = _strict_object(terminal_raw, f"terminal:{logical}")
    baseline = _strict_object(baseline_raw, f"baseline:{logical}")
    _codec, claimed = _claimed(members)
    keys, values = _merge_rows(
        list(baseline),
        list(baseline.values()),
        list(terminal),
        list(terminal.values()),
        claimed,
        label=logical,
    )
    output = dict(zip(keys, values, strict=True))
    return json.dumps(
        output,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def merge_table_members(
    members: Iterable[InventoryMember], terminal_raw: bytes, baseline_raw: bytes
) -> bytes:
    selected = tuple(members)
    if not selected:
        raise ScopedTableMergeError("joint table merge requires members")
    codec, _keys = _claimed(selected)
    if codec in {"flat", "raw_outer"}:
        return _flat(selected, terminal_raw, baseline_raw, codec)
    if codec in {"action_nested", "switched_nested"}:
        return _nested(selected, terminal_raw, baseline_raw)
    if codec == "json_object":
        return _json_table(selected, terminal_raw, baseline_raw)
    raise ScopedTableMergeError(f"unsupported scoped table codec: {codec}")
