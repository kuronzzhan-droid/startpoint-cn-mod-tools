#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stable read-only inputs for the thunder-dragon 1.1.6 hotfix package."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import wf_abyss_gacha_package_audit as abyss_audit
import wf_character_pack as character_pack
import wf_character_workspace as workspace_module
import wf_mod_tool as core
from wf_abyss_gacha_package_sources import read_regular_stable
from wf_pixelart_compile import SUMMER_THUNDER_TEMPLATE_SHA256
from wf_summer_thunder_package_contract import PackageAssemblyError, ROOT_NAMES
from wf_summer_thunder_package_paths import (
    assert_workspace_tree_safe,
    safe_contained_target,
)
from wf_summer_thunder_package_sources import LOCKED_NORMAL_V3, safe_child


_REPARSE_POINT = 0x0400
_SOURCE_IDENTITY = {
    "package_id": "cnmod_thunder_dragon_ascendant",
    "character_id": 139998,
    "code_name": "cnmod_thunder_dragon_ascendant",
    "package_version": "1.1.0",
    "requires_client_base": "1.4.347",
}


@dataclass(frozen=True)
class SealedHotfixSource:
    roots: Mapping[str, Mapping[str, bytes]]
    manifest: Mapping[str, Any]
    source_locks: Mapping[str, Any]
    workspace_input_sha256: str
    manifest_sha256: str
    evidence_sha256: str


@dataclass(frozen=True)
class LockedDonorTemplate:
    files: Mapping[str, bytes]
    report_sha256: str
    source_store: str
    input_sha256: Mapping[str, str]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _safe_directory(path: Path, label: str) -> Path:
    directory = Path(path)
    if not directory.is_absolute():
        raise PackageAssemblyError(f"{label} must be absolute")
    try:
        for current in (directory, *directory.parents):
            info = os.lstat(current)
            if _is_reparse(info):
                raise OSError("reparse point")
        if not stat.S_ISDIR(os.lstat(directory).st_mode):
            raise OSError("not a directory")
        return directory.resolve(strict=True)
    except OSError as exc:
        raise PackageAssemblyError(f"{label} is unsafe or missing") from exc


def _workspace_status(workspace: Path):
    try:
        current = workspace_module.load_workspace(workspace)
        return workspace_module.workspace_status(current, persist=False)
    except (OSError, workspace_module.WorkspaceError) as exc:
        raise PackageAssemblyError("sealed hotfix source workspace is invalid") from exc


def load_sealed_source_workspace(workspace: Path) -> SealedHotfixSource:
    """Authenticate and copy the exact sealed 1.1.0 package without writes."""

    resolved = assert_workspace_tree_safe(Path(workspace))
    before = _workspace_status(resolved)
    manifest_path = safe_contained_target(resolved, "package/manifest.json")
    evidence_path = safe_contained_target(
        resolved, "evidence/package-source-locks.json"
    )
    manifest_raw = read_regular_stable(manifest_path, "hotfix source manifest")
    evidence_raw = read_regular_stable(evidence_path, "hotfix source evidence")
    manifest = _strict_object(manifest_raw, "hotfix source manifest")
    source_locks = _strict_object(evidence_raw, "hotfix source evidence")
    if any(manifest.get(key) != value for key, value in _SOURCE_IDENTITY.items()):
        raise PackageAssemblyError("hotfix source package identity/version drift")
    qa = manifest.get("qa")
    if (
        not isinstance(qa, dict)
        or qa.get("release_ready") is not True
        or qa.get("workspace_input_sha256") != before.input_digest
        or before.release_ready is not True
    ):
        raise PackageAssemblyError("hotfix source package is not sealed/release-ready")
    if evidence_raw != abyss_audit.source_lock_evidence_bytes(source_locks):
        raise PackageAssemblyError("hotfix source evidence is not canonical")
    evidence_sha = _sha(evidence_raw)
    snapshot = manifest.get("snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("source_locks_sha256") != evidence_sha
    ):
        raise PackageAssemblyError("hotfix source evidence is not manifest-bound")
    manifest_errors = character_pack.validate_manifest(
        manifest, resolved / "package", require_referenced_assets=True
    )
    if manifest_errors:
        raise PackageAssemblyError(
            f"hotfix source manifest is invalid: {manifest_errors}"
        )

    roots: dict[str, dict[str, bytes]] = {root: {} for root in ROOT_NAMES}
    manifest_roots = manifest.get("roots")
    if not isinstance(manifest_roots, dict):
        raise PackageAssemblyError("hotfix source roots are invalid")
    for root in ROOT_NAMES:
        entries = manifest_roots.get(root)
        if not isinstance(entries, list):
            raise PackageAssemblyError(f"hotfix source root is invalid: {root}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("logical_path"), str
            ):
                raise PackageAssemblyError("hotfix source entry is invalid")
            logical = entry["logical_path"]
            path = safe_contained_target(
                resolved, f"package/roots/{root}/{logical}"
            )
            raw = read_regular_stable(path, f"source:{root}:{logical}")
            if entry.get("size") != len(raw) or entry.get("sha256") != _sha(raw):
                raise PackageAssemblyError(
                    f"hotfix source payload hash drift: {root}:{logical}"
                )
            roots[root][logical] = raw
    if (
        {root: len(files) for root, files in roots.items()}
        != {"common": 67, "medium": 25, "android": 2, "server": 11}
        or len(manifest.get("tables", [])) != 39
    ):
        raise PackageAssemblyError("hotfix source inventory/count drift")

    after = _workspace_status(resolved)
    if (
        after.input_digest != before.input_digest
        or after.release_ready is not True
        or read_regular_stable(manifest_path, "source manifest readback")
        != manifest_raw
        or read_regular_stable(evidence_path, "source evidence readback")
        != evidence_raw
    ):
        raise PackageAssemblyError("hotfix source changed while being read")
    return SealedHotfixSource(
        roots=roots,
        manifest=manifest,
        source_locks=source_locks,
        workspace_input_sha256=before.input_digest,
        manifest_sha256=_sha(character_pack.canonical_manifest_bytes(manifest)),
        evidence_sha256=evidence_sha,
    )


def load_locked_donor_template(build_root: Path) -> LockedDonorTemplate:
    """Read the original official thunder-dragon template through its v3 lock."""

    root = _safe_directory(Path(build_root), "thunder build root")
    report_path = safe_child(
        root, LOCKED_NORMAL_V3.report_relative, "normal v3 report"
    )
    report_raw = read_regular_stable(report_path, "normal v3 report")
    if _sha(report_raw) != LOCKED_NORMAL_V3.report_sha256:
        raise PackageAssemblyError("normal v3 donor report drift")
    report = _strict_object(report_raw, "normal v3 report")
    template = report.get("template")
    if not isinstance(template, dict) or set(template) != set(
        SUMMER_THUNDER_TEMPLATE_SHA256
    ):
        raise PackageAssemblyError("normal donor template declaration drift")
    store_value = report.get("source_store")
    if not isinstance(store_value, str):
        raise PackageAssemblyError("normal donor store declaration is missing")
    store = _safe_directory(Path(store_value), "normal donor store")
    files: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for logical in sorted(SUMMER_THUNDER_TEMPLATE_SHA256):
        record = template[logical]
        if not isinstance(record, dict) or set(record) != {
            "store_root", "physical_path", "stored_sha256"
        }:
            raise PackageAssemblyError(f"normal donor record drift: {logical}")
        path = core.table_path(store, logical)
        declared = Path(record["physical_path"])
        try:
            if declared.resolve(strict=True) != path.resolve(strict=True):
                raise OSError("path drift")
        except OSError as exc:
            raise PackageAssemblyError(
                f"normal donor physical path drift: {logical}"
            ) from exc
        raw = read_regular_stable(path, f"normal donor:{logical}")
        digest = _sha(raw)
        if (
            record["stored_sha256"] != digest
            or SUMMER_THUNDER_TEMPLATE_SHA256[logical] != digest
        ):
            raise PackageAssemblyError(f"normal donor SHA-256 drift: {logical}")
        files[logical] = raw
        hashes[logical] = digest
    return LockedDonorTemplate(
        files=files,
        report_sha256=_sha(report_raw),
        source_store=str(store),
        input_sha256=hashes,
    )


__all__ = [
    "SealedHotfixSource",
    "LockedDonorTemplate",
    "load_sealed_source_workspace",
    "load_locked_donor_template",
]
