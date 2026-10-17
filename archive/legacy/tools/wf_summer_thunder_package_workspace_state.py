#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pristine formal-workspace identity and concurrent-WIP snapshots."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from wf_summer_thunder_package_contract import (
    CHARACTER_ID,
    CODE_NAME,
    PACKAGE_ID,
    ROOT_NAMES,
    PackageAssemblyError,
    PackageImage,
    draft_manifest,
)
from wf_summer_thunder_package_evidence import EVIDENCE_RELATIVE
from wf_summer_thunder_package_paths import (
    assert_workspace_tree_safe,
    safe_contained_target,
)


@dataclass(frozen=True)
class WorkspaceSnapshot:
    workspace_json: bytes
    draft_manifest: bytes


def read_file(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise PackageAssemblyError(f"{label} is unreadable") from exc


def _strict_json(raw: bytes, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageAssemblyError(f"{label} is unreadable") from exc
    if not isinstance(value, Mapping):
        raise PackageAssemblyError(f"{label} must be an object")
    return value


def manifest_bytes(image: PackageImage) -> bytes:
    return (
        json.dumps(
            image.manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _workspace_identity(raw: bytes) -> None:
    payload = _strict_json(raw, "workspace.json")
    expected = {
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_dir": "package",
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise PackageAssemblyError(f"workspace identity mismatch: {field}")


def existing_root_payload(workspace: Path) -> Path | None:
    roots = workspace / "package" / "roots"
    if not roots.exists():
        return None
    for root_name in ROOT_NAMES:
        root = roots / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                return path
    return None


def inspect_pristine_workspace(workspace: Path) -> WorkspaceSnapshot:
    workspace = Path(workspace)
    assert_workspace_tree_safe(workspace)
    workspace_path = safe_contained_target(workspace, "workspace.json")
    manifest_path = safe_contained_target(workspace, "package/manifest.json")
    evidence_path = safe_contained_target(workspace, EVIDENCE_RELATIVE)
    workspace_raw = read_file(workspace_path, "workspace.json")
    _workspace_identity(workspace_raw)
    manifest_raw = read_file(manifest_path, "existing manifest")
    if dict(_strict_json(manifest_raw, "existing manifest")) != draft_manifest():
        raise PackageAssemblyError("existing WIP: manifest is not the pristine draft")
    existing = existing_root_payload(workspace)
    if existing is not None:
        raise PackageAssemblyError(f"existing WIP under package roots: {existing}")
    if os.path.lexists(evidence_path):
        raise PackageAssemblyError(
            f"existing WIP at package source-lock evidence: {evidence_path}"
        )
    return WorkspaceSnapshot(workspace_raw, manifest_raw)


def assert_snapshot_unchanged(
    workspace: Path, snapshot: WorkspaceSnapshot
) -> None:
    assert_workspace_tree_safe(workspace)
    if read_file(workspace / "workspace.json", "workspace.json") != snapshot.workspace_json:
        raise PackageAssemblyError("concurrent WIP changed workspace.json")
    if (
        read_file(workspace / "package" / "manifest.json", "existing manifest")
        != snapshot.draft_manifest
    ):
        raise PackageAssemblyError("concurrent WIP changed the draft manifest")
    existing = existing_root_payload(workspace)
    if existing is not None:
        raise PackageAssemblyError(f"concurrent WIP appeared under package roots: {existing}")
    if os.path.lexists(workspace / EVIDENCE_RELATIVE):
        raise PackageAssemblyError("concurrent WIP created package source-lock evidence")


__all__ = [
    "WorkspaceSnapshot", "read_file", "manifest_bytes",
    "existing_root_payload", "inspect_pristine_workspace",
    "assert_snapshot_unchanged",
]
