#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clean-release/scaffold rebasing and claim-only diff validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import wf_mod_tool as core
import wf_summer_thunder_master_compile as master_compile
from wf_summer_thunder_package_contract import PackageAssemblyError


def _ordered_rows(raw: bytes, codec_id: str, logical: str) -> list[tuple[str, bytes]]:
    compressed = codec_id == "flat"
    if codec_id not in {"flat", "raw_outer", "action_nested"}:
        raise PackageAssemblyError(f"unsupported clean-rebase codec: {codec_id}")
    try:
        keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
            raw, label=logical, compressed_rows=compressed
        )
    except Exception as exc:
        raise PackageAssemblyError(f"cannot decode clean-rebase table: {logical}") from exc
    return list(zip(keys, rows, strict=True))


def validate_claimed_table_rebase(
    clean_raw: bytes,
    candidate_raw: bytes,
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove one full-table candidate differs from clean only at declared keys."""

    logical = claim.get("logical_path")
    codec_id = claim.get("codec_id")
    outer_keys = claim.get("outer_keys")
    if (
        not isinstance(logical, str)
        or not isinstance(codec_id, str)
        or not isinstance(outer_keys, list)
        or any(not isinstance(key, str) for key in outer_keys)
    ):
        raise PackageAssemblyError("clean-rebase claim is malformed")
    owned = set(outer_keys)
    clean_rows = _ordered_rows(clean_raw, codec_id, logical)
    candidate_rows = _ordered_rows(candidate_raw, codec_id, logical)
    clean_nonowned = [(key, row) for key, row in clean_rows if key not in owned]
    candidate_nonowned = [(key, row) for key, row in candidate_rows if key not in owned]
    if clean_nonowned != candidate_nonowned:
        raise PackageAssemblyError(f"non-owned clean-release rows changed: {logical}")
    clean_map = dict(clean_rows)
    candidate_map = dict(candidate_rows)
    missing_owned = sorted(owned - set(candidate_map))
    if missing_owned:
        raise PackageAssemblyError(
            f"candidate omits declared owned keys for {logical}: {missing_owned}"
        )
    added = sorted(key for key in owned if key not in clean_map)
    changed = sorted(
        key for key in owned if key in clean_map and clean_map[key] != candidate_map[key]
    )
    unchanged = sorted(
        key for key in owned if key in clean_map and clean_map[key] == candidate_map[key]
    )
    inner_claims = claim.get("inner_keys")
    if codec_id == "action_nested":
        if not isinstance(inner_claims, list):
            raise PackageAssemblyError("action nested claim inner_keys is malformed")
        for item in inner_claims:
            if not isinstance(item, dict) or set(item) != {"outer_key", "keys"}:
                raise PackageAssemblyError("action nested inner claim is malformed")
            outer = item["outer_key"]
            keys = item["keys"]
            if outer not in candidate_map or not isinstance(keys, list):
                raise PackageAssemblyError("action nested inner claim target is absent")
            try:
                inner_keys, _ = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
                    candidate_map[outer],
                    label=f"{logical}#{outer}",
                    compressed_rows=True,
                )
            except Exception as exc:
                raise PackageAssemblyError("action nested owned row is invalid") from exc
            if not set(keys).issubset(inner_keys):
                raise PackageAssemblyError("action nested declared inner keys are absent")
    return {
        "logical_path": logical,
        "codec_id": codec_id,
        "owned_added": added,
        "owned_changed": changed,
        "owned_unchanged": unchanged,
        "nonowned_changes": 0,
    }


def rebase_claimed_scaffold(
    clean_raw: bytes,
    authoring_raw: bytes,
    claim: Mapping[str, Any],
) -> bytes:
    """Copy only declared scaffold rows onto a clean full-table baseline."""

    logical = claim.get("logical_path")
    codec_id = claim.get("codec_id")
    outer_keys = claim.get("outer_keys")
    if (
        not isinstance(logical, str)
        or not isinstance(codec_id, str)
        or not isinstance(outer_keys, list)
    ):
        raise PackageAssemblyError("scaffold rebase claim is malformed")
    clean_rows = _ordered_rows(clean_raw, codec_id, logical)
    authoring_map = dict(_ordered_rows(authoring_raw, codec_id, logical))
    collisions = sorted(set(outer_keys) & {key for key, _row in clean_rows})
    if collisions:
        raise PackageAssemblyError(
            f"clean release already contains claimed scaffold keys for {logical}: "
            f"{collisions}"
        )
    rebased_rows = list(clean_rows)
    for key in outer_keys:
        if key in authoring_map:
            rebased_rows.append((key, authoring_map[key]))
    ordered = core.OrderedMap(
        logical,
        [key for key, _row in rebased_rows],
        [row for _key, row in rebased_rows],
        Path("<clean-scaffold-rebase>"),
    )
    if codec_id == "flat":
        return core.build_orderedmap(ordered)
    return core.build_orderedmap_raw_rows(ordered)


def rebase_authoring_scaffold(
    clean_tables: Mapping[str, bytes],
    authoring_tables: Mapping[str, bytes],
    claims: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build an in-memory clean base plus only the 21 existing scaffold rows."""

    expected = set(master_compile.TABLE_CODECS)
    if set(clean_tables) != expected or set(authoring_tables) != expected:
        raise PackageAssemblyError("scaffold rebase requires exact 18-table maps")
    by_logical = {
        claim.get("logical_path"): claim
        for claim in claims if claim.get("root") == "common"
    }
    if set(by_logical) != expected:
        raise PackageAssemblyError("scaffold rebase claims do not cover 18 tables")
    files: dict[str, bytes] = {}
    copied: dict[str, list[str]] = {}
    for logical in master_compile.TABLE_CODECS:
        claim = by_logical[logical]
        authoring_keys = {
            key for key, _row in _ordered_rows(
                authoring_tables[logical], claim["codec_id"], logical
            )
        }
        copied[logical] = [
            key for key in claim["outer_keys"] if key in authoring_keys
        ]
        files[logical] = rebase_claimed_scaffold(
            clean_tables[logical], authoring_tables[logical], claim
        )
    copied_count = sum(len(keys) for keys in copied.values())
    if copied_count != 21:
        raise PackageAssemblyError(
            f"locked authoring scaffold row count drift: expected 21, got {copied_count}"
        )
    return files, {
        "table_count": 18,
        "copied_scaffold_rows": copied_count,
        "copied_outer_keys": copied,
        "dropped_unclaimed_authoring_rows": True,
        "writes_live": False,
    }


def validate_clean_release_rebase(
    clean_tables: Mapping[str, bytes],
    candidate_tables: Mapping[str, bytes],
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run all 18 client candidates against the fresh 1.4.346 base in memory."""

    expected = set(master_compile.TABLE_CODECS)
    if set(clean_tables) != expected or set(candidate_tables) != expected:
        raise PackageAssemblyError("clean-release rebase requires exact 18-table maps")
    client_claims = [claim for claim in claims if claim.get("root") == "common"]
    if len(client_claims) != 18:
        raise PackageAssemblyError("clean-release rebase requires exact 18 claims")
    by_logical = {claim.get("logical_path"): claim for claim in client_claims}
    if set(by_logical) != expected:
        raise PackageAssemblyError("clean-release claim coverage is not exact")
    tables = [
        validate_claimed_table_rebase(
            clean_tables[logical], candidate_tables[logical], by_logical[logical]
        )
        for logical in master_compile.TABLE_CODECS
    ]
    owned_added = sum(len(item["owned_added"]) for item in tables)
    owned_changed = sum(len(item["owned_changed"]) for item in tables)
    if owned_added != 26 or owned_changed != 0:
        raise PackageAssemblyError(
            "clean release was expected to contain zero target/trim keys; "
            f"added={owned_added}, changed={owned_changed}"
        )
    return {
        "base": "1.4.346-clean",
        "table_count": 18,
        "owned_added": owned_added,
        "owned_changed": owned_changed,
        "nonowned_outer_changes": 0,
        "nonowned_inner_changes": 0,
        "writes_live": False,
        "tables": tables,
    }


__all__ = [
    "validate_claimed_table_rebase", "rebase_claimed_scaffold",
    "rebase_authoring_scaffold", "validate_clean_release_rebase",
]
