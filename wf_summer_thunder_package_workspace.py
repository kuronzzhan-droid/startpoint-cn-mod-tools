#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dry-run by default and the sole guarded formal-workspace write boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import wf_summer_thunder_package_workspace_commit as commit_io
from wf_summer_thunder_package_contract import (
    CONFIRMATION,
    PackageAssemblyError,
    PackageImage,
    sha256_bytes,
)
from wf_summer_thunder_package_evidence import validate_source_lock_binding
from wf_summer_thunder_package_image import audit_package_image, require_apply_ready
from wf_summer_thunder_package_paths import ExclusiveWorkspaceLease
from wf_summer_thunder_package_workspace_state import (
    assert_snapshot_unchanged,
    inspect_pristine_workspace,
    manifest_bytes,
)


def write_package_atomic(
    workspace: Path,
    image: PackageImage,
    *,
    confirmation: str,
) -> dict[str, Any]:
    """Write only after all internal gates pass; manifest is the commit point."""

    if confirmation != CONFIRMATION:
        raise PackageAssemblyError(f"exact confirmation required: {CONFIRMATION}")
    workspace = Path(workspace)
    snapshot = inspect_pristine_workspace(workspace)
    audit = require_apply_ready(image)
    evidence_raw = validate_source_lock_binding(image.manifest, image.source_report)
    manifest_raw = manifest_bytes(image)
    staged: dict[Path, bytes] = {}
    with ExclusiveWorkspaceLease(workspace) as lease:
        try:
            assert_snapshot_unchanged(workspace, snapshot)
            staged = commit_io.stage_image(
                lease.staging, image, evidence_raw, manifest_raw
            )
            assert_snapshot_unchanged(workspace, snapshot)
            commit_io.commit_staged(
                workspace, lease.staging, image, snapshot, evidence_raw, manifest_raw
            )
        finally:
            commit_io.cleanup_staging(lease.staging, staged)
    return {
        **audit,
        "apply": True,
        "workspace": str(workspace.resolve(strict=True)),
        "manifest_sha256": sha256_bytes(manifest_raw),
        "source_locks_sha256": sha256_bytes(evidence_raw),
    }


def execute_package(
    workspace: Path,
    image: PackageImage,
    *,
    apply: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    """Audit a pristine workspace by default; apply requires the fixed phrase."""

    if apply and confirmation != CONFIRMATION:
        raise PackageAssemblyError(f"exact confirmation required: {CONFIRMATION}")
    workspace = Path(workspace)
    inspect_pristine_workspace(workspace)
    audit = audit_package_image(image)
    if not apply:
        return {
            **audit,
            "apply": False,
            "workspace": str(workspace.resolve(strict=True)),
        }
    return write_package_atomic(workspace, image, confirmation=confirmation or "")


__all__ = ["execute_package", "write_package_atomic"]
