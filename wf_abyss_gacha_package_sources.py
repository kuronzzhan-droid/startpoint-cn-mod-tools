#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable read-only inputs for the abyss-gacha replacement assembler."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import wf_abyss_gacha_package_contract as contract
import wf_abyss_gacha_compile as gacha_compile
import wf_abyss_gacha_contract as gacha_contract
import wf_abyss_ticket_compile as tickets
import wf_character_pack as character_pack
import wf_character_workspace as workspace_module
import wf_mod_tool as core
import wf_rogue_shop as shop
from wf_summer_thunder_package_evidence import (
    EVIDENCE_RELATIVE,
    source_lock_evidence_bytes,
)
from wf_summer_thunder_package_paths import (
    assert_workspace_tree_safe,
    safe_contained_target,
)


PackageAssemblyError = contract.PackageAssemblyError
_REPARSE_POINT = 0x0400


def _snapshot(info: os.stat_result) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def read_regular_stable(path: Path, label: str) -> bytes:
    """Read one regular file and reject identity/content races and reparses."""

    descriptor = -1
    try:
        before = os.lstat(path)
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        identity = _snapshot(before)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or _snapshot(opened) != identity:
            raise OSError("file identity changed before open")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read()
            after_open = os.fstat(stream.fileno())
        after_path = os.lstat(path)
        if (
            _snapshot(after_open) != identity
            or _snapshot(after_path) != identity
            or _is_reparse(after_path)
        ):
            raise OSError("file identity changed while reading")
        return raw
    except OSError as exc:
        raise PackageAssemblyError(f"stable input changed or is unsafe: {label}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _safe_read_root(path: Path, label: str) -> Path:
    root = Path(path)
    if not root.is_absolute():
        raise PackageAssemblyError(f"{label} must be an absolute directory")
    try:
        for current in (root, *root.parents):
            info = os.lstat(current)
            if _is_reparse(info):
                raise OSError("reparse point")
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            raise OSError("not a directory")
        return root.resolve(strict=True)
    except OSError as exc:
        raise PackageAssemblyError(f"{label} is unsafe or missing") from exc


def _safe_input_path(root: Path, relative: Path, label: str) -> Path:
    if relative.is_absolute() or relative.drive or not relative.parts:
        raise PackageAssemblyError(f"input path escapes {label}")
    candidate = root.joinpath(*relative.parts)
    cursor = root
    try:
        for part in relative.parts:
            cursor = cursor / part
            try:
                info = os.lstat(cursor)
            except FileNotFoundError:
                break
            if _is_reparse(info):
                raise OSError("reparse point")
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise PackageAssemblyError(f"input path is unsafe: {label}") from exc
    return candidate


def _store_input_path(store: Path, logical: str) -> Path:
    problem = character_pack.logical_path_problem(logical)
    if problem:
        raise PackageAssemblyError(f"invalid store logical path {logical}: {problem}")
    hashed = core.table_path(store, logical)
    return _safe_input_path(store, hashed.relative_to(store), f"store:{logical}")


def _server_input_path(server: Path, logical: str) -> Path:
    problem = character_pack.logical_path_problem(logical)
    if problem:
        raise PackageAssemblyError(f"invalid server logical path {logical}: {problem}")
    relative = Path(*logical.split("/"))
    return _safe_input_path(server, relative, f"server:{logical}")


def _probe_optional_store_file(store: Path, logical: str) -> bool:
    path = _store_input_path(store, logical)
    try:
        os.lstat(path)
    except FileNotFoundError:
        try:
            os.lstat(path)
        except FileNotFoundError:
            return False
        raise PackageAssemblyError(
            f"optional store input appeared during probe: {logical}"
        )
    read_regular_stable(path, f"optional store:{logical}")
    return True


def load_addition_sources(store_root: Path, server_assets_root: Path):
    """Read the explicit base347/store and server inputs without mutation."""

    from wf_abyss_gacha_package_compile import AdditionSources

    store = _safe_read_root(store_root, "base347 store root")
    server = _safe_read_root(server_assets_root, "server assets root")

    def store_read(logical: str) -> bytes:
        return read_regular_stable(
            _store_input_path(store, logical), f"store:{logical}"
        )

    def server_read(logical: str) -> bytes:
        return read_regular_stable(
            _server_input_path(server, logical), f"server:{logical}"
        )

    common = {
        logical: store_read(logical)
        for logical in gacha_compile.COMMON_SOURCE_PATHS
    }
    server_gacha = {
        logical: server_read(logical)
        for logical in gacha_compile.SERVER_SOURCE_PATHS
    }
    existing = list(common)
    existing.extend(
        logical for logical in gacha_contract.NEW_COMMON_PATHS
        if _probe_optional_store_file(store, logical)
    )
    return AdditionSources(
        gacha_common=common,
        gacha_server=server_gacha,
        existing_common_paths=tuple(existing),
        item_raw=store_read(tickets.ITEM_T),
        ticket_type_raw=store_read(tickets.GACHA_TICKET_TYPE_T),
        item_ids_raw=server_read(contract.ITEM_IDS_LOGICAL),
        item_sheet_raw=store_read(tickets.ITEM_SHEET_LOGICAL),
        item_atlas_raw=store_read(tickets.ITEM_ATLAS_LOGICAL),
        shop_client_raw=store_read(shop.SHOP_T),
        shop_server_raw=server_read(shop.SHOP_JSON),
        shop_id_map_raw=server_read(shop.SHOP_ID_MAP_JSON),
        rogue_event_raw=server_read(contract.ROGUE_EVENT_LOGICAL),
        rush_event_quest_raw=server_read("rush_event_quest.json"),
    )


def _strict_object(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str):
        raise ValueError(f"non-JSON constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PackageAssemblyError(f"invalid strict JSON input: {label}") from exc
    if not isinstance(value, dict):
        raise PackageAssemblyError(f"JSON input must be an object: {label}")
    return value


def _workspace_status(workspace: Path):
    try:
        current = workspace_module.load_workspace(workspace)
        status = workspace_module.workspace_status(current, persist=False)
    except (OSError, workspace_module.WorkspaceError) as exc:
        raise PackageAssemblyError("sealed source workspace is invalid") from exc
    if not status.release_ready:
        raise PackageAssemblyError("sealed source workspace is not release ready")
    return current, status


def load_sealed_source_workspace(workspace: Path) -> contract.SealedSourcePackage:
    """Authenticate and copy the exact old 83 payloads without any write."""

    workspace = Path(workspace)
    try:
        resolved = assert_workspace_tree_safe(workspace)
    except PackageAssemblyError:
        raise
    except Exception as exc:
        raise PackageAssemblyError("sealed source workspace path is unsafe") from exc
    current, before = _workspace_status(resolved)
    manifest_path = safe_contained_target(resolved, "package/manifest.json")
    evidence_path = safe_contained_target(resolved, EVIDENCE_RELATIVE)
    manifest_raw = read_regular_stable(manifest_path, "source manifest")
    evidence_raw = read_regular_stable(evidence_path, "source-lock evidence")
    manifest = _strict_object(manifest_raw, "source manifest")
    source_locks = _strict_object(evidence_raw, "source-lock evidence")
    try:
        expected_evidence = source_lock_evidence_bytes(source_locks)
    except contract.PackageAssemblyError:
        raise
    except Exception as exc:
        raise PackageAssemblyError("source-lock evidence contract is invalid") from exc
    evidence_sha = hashlib.sha256(evidence_raw).hexdigest()
    snapshot = manifest.get("snapshot")
    if (
        evidence_raw != expected_evidence
        or not isinstance(snapshot, dict)
        or snapshot.get("source_locks_sha256") != evidence_sha
    ):
        raise PackageAssemblyError("source-lock evidence is not manifest-bound")

    roots: dict[str, dict[str, bytes]] = {
        root: {} for root in contract.ROOT_NAMES
    }
    manifest_roots = manifest.get("roots")
    if not isinstance(manifest_roots, dict):
        raise PackageAssemblyError("sealed source manifest roots are invalid")
    for root in contract.ROOT_NAMES:
        entries = manifest_roots.get(root)
        if not isinstance(entries, list):
            raise PackageAssemblyError(f"sealed source manifest root is invalid: {root}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise PackageAssemblyError("sealed source manifest entry is invalid")
            logical = entry.get("logical_path")
            if not isinstance(logical, str):
                raise PackageAssemblyError("sealed source logical path is invalid")
            relative = f"package/roots/{root}/{logical}"
            path = safe_contained_target(resolved, relative)
            raw = read_regular_stable(path, f"{root}:{logical}")
            if (
                entry.get("size") != len(raw)
                or entry.get("sha256") != hashlib.sha256(raw).hexdigest()
            ):
                raise PackageAssemblyError(
                    f"sealed source payload hash drift: {root}:{logical}"
                )
            roots[root][logical] = raw

    _current_after, after = _workspace_status(resolved)
    if (
        after.input_digest != before.input_digest
        or not after.release_ready
        or read_regular_stable(manifest_path, "source manifest readback") != manifest_raw
        or read_regular_stable(evidence_path, "source-lock evidence readback")
        != evidence_raw
    ):
        raise PackageAssemblyError("sealed source workspace changed while being read")
    source = contract.SealedSourcePackage(
        roots=roots,
        manifest=manifest,
        workspace_input_sha256=before.input_digest,
        source_locks_sha256=evidence_sha,
        package_acceptance=source_locks.get("package_acceptance", {}),
        skill_follow_gate=source_locks.get("skill_follow_gate", {}),
    )
    contract._validate_source(source)
    return source


__all__ = [
    "PackageAssemblyError", "read_regular_stable", "load_sealed_source_workspace",
    "load_addition_sources",
]
