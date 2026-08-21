#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic fresh-workspace boundary for the abyss-gacha replacement package."""

from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any, Mapping

import wf_abyss_gacha_package_contract as contract
import wf_summer_thunder_package_workspace_commit as commit_io
from wf_summer_thunder_package_paths import assert_workspace_tree_safe
from wf_summer_thunder_package_workspace_state import manifest_bytes


WORKSPACE_NAME = "cnmod_thunder_dragon_ascendant_abyss_gacha"
LOCK_NAME = f".{WORKSPACE_NAME}.assemble.lock"
STAGING_NAME = f".{WORKSPACE_NAME}.assemble.staging"
_REPARSE_POINT = 0x0400


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _safe_parent(path: Path) -> Path:
    parent = Path(path)
    if not parent.is_absolute():
        raise contract.PackageAssemblyError("workspace parent must be absolute")
    try:
        for current in (parent, *parent.parents):
            info = os.lstat(current)
            if _is_reparse(info):
                raise OSError("reparse point")
        if not stat.S_ISDIR(os.lstat(parent).st_mode):
            raise OSError("not a directory")
        return parent.resolve(strict=True)
    except OSError as exc:
        raise contract.PackageAssemblyError(
            "workspace parent is unsafe or missing"
        ) from exc


def _fresh_target(workspace: Path) -> tuple[Path, Path]:
    target = Path(workspace)
    if not target.is_absolute() or target.name != WORKSPACE_NAME:
        raise contract.PackageAssemblyError(
            f"formal workspace must use the fixed name {WORKSPACE_NAME}"
        )
    parent = _safe_parent(target.parent)
    candidate = parent / WORKSPACE_NAME
    if os.path.lexists(candidate):
        raise contract.PackageAssemblyError("formal workspace already exists")
    return parent, candidate


def inspect_fresh_target(workspace: Path) -> Path:
    """Validate the fixed absent output path without creating anything."""

    _parent, target = _fresh_target(workspace)
    return target


def _workspace_json() -> bytes:
    return (
        json.dumps({
            "schema_version": 1,
            "package_id": contract.PACKAGE_ID,
            "template_character_id": 231001,
            "character_id": contract.CHARACTER_ID,
            "code_name": contract.CODE_NAME,
            "package_dir": "package",
        }, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )


def _remove_owned(path: Path, raw: bytes) -> None:
    try:
        info = os.lstat(path)
        if (
            stat.S_ISREG(info.st_mode)
            and not _is_reparse(info)
            and path.read_bytes() == raw
        ):
            path.unlink()
    except OSError:
        pass


class _ParentLease:
    def __init__(self, parent: Path):
        self.parent = parent
        self.lock = parent / LOCK_NAME
        self.staging = parent / STAGING_NAME
        self.token = uuid.uuid4().hex.encode("ascii")
        self.entered = False

    def __enter__(self):
        if os.path.lexists(self.lock) or os.path.lexists(self.staging):
            raise contract.PackageAssemblyError(
                "fresh workspace lock or staging already exists"
            )
        descriptor = -1
        try:
            descriptor = os.open(
                self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            with os.fdopen(descriptor, "wb") as output:
                descriptor = -1
                output.write(self.token)
                output.flush()
                os.fsync(output.fileno())
            os.mkdir(self.staging)
            assert_workspace_tree_safe(self.staging)
            self.entered = True
            return self
        except FileExistsError as exc:
            raise contract.PackageAssemblyError(
                "fresh workspace lock/staging race"
            ) from exc
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            self._release_lock()
            raise

    def _release_lock(self) -> None:
        try:
            info = os.lstat(self.lock)
            if (
                stat.S_ISREG(info.st_mode)
                and not _is_reparse(info)
                and self.lock.read_bytes() == self.token
            ):
                self.lock.unlink()
        except OSError:
            pass

    def __exit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback
        self._release_lock()
        self.entered = False


def _cleanup_staging(
    staging: Path, staged: Mapping[Path, bytes], workspace_raw: bytes
) -> None:
    commit_io.cleanup_staging(staging, staged)
    _remove_owned(staging / "workspace.json", workspace_raw)
    try:
        staging.rmdir()
    except OSError:
        pass


def _rollback_published(
    target: Path,
    image: contract.PackageImage,
    evidence_raw: bytes,
    manifest_raw: bytes,
    workspace_raw: bytes,
) -> None:
    paths: list[Path] = []
    for root, files in image.roots.items():
        for logical, raw in files.items():
            path = target / "package" / "roots" / root / Path(*logical.split("/"))
            _remove_owned(path, raw)
            paths.append(path)
    evidence = target / "evidence" / "package-source-locks.json"
    manifest = target / "package" / "manifest.json"
    workspace = target / "workspace.json"
    _remove_owned(evidence, evidence_raw)
    _remove_owned(manifest, manifest_raw)
    _remove_owned(workspace, workspace_raw)
    paths.extend((evidence, manifest, workspace))
    commit_io._remove_empty_parents(paths, target)  # type: ignore[attr-defined]
    try:
        target.rmdir()
    except OSError:
        pass


def write_fresh_workspace(
    workspace: Path,
    image: contract.PackageImage,
    *,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != contract.CONFIRMATION:
        raise contract.PackageAssemblyError(
            f"exact confirmation required: {contract.CONFIRMATION}"
        )
    audit = contract.audit_package_image(image)
    parent, target = _fresh_target(workspace)
    evidence_raw = contract.source_lock_evidence_bytes(
        image.source_report["source_locks"]
    )
    manifest_raw = manifest_bytes(image)
    workspace_raw = _workspace_json()
    staged: dict[Path, bytes] = {}
    published = False
    with _ParentLease(parent) as lease:
        try:
            commit_io._exclusive_bytes(  # type: ignore[attr-defined]
                lease.staging / "workspace.json", workspace_raw
            )
            staged = commit_io.stage_image(
                lease.staging, image, evidence_raw, manifest_raw
            )
            commit_io.readback_disk(
                lease.staging, image, evidence_raw, manifest_raw
            )
            if (lease.staging / "workspace.json").read_bytes() != workspace_raw:
                raise contract.PackageAssemblyError("workspace.json staged readback drift")
            if os.path.lexists(target):
                raise contract.PackageAssemblyError(
                    "formal workspace appeared before commit"
                )
            os.rename(lease.staging, target)
            published = True
            commit_io.readback_disk(target, image, evidence_raw, manifest_raw)
            if (target / "workspace.json").read_bytes() != workspace_raw:
                raise contract.PackageAssemblyError("workspace.json final readback drift")
        except Exception:
            if published:
                _rollback_published(
                    target, image, evidence_raw, manifest_raw, workspace_raw
                )
            else:
                _cleanup_staging(lease.staging, staged, workspace_raw)
            raise
    return {
        **audit,
        "apply": True,
        "workspace": str(target),
        "formal_workspace_written": True,
        "writes_live": False,
    }


def execute_fresh_workspace(
    workspace: Path,
    image: contract.PackageImage,
    *,
    apply: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    if apply and confirmation != contract.CONFIRMATION:
        raise contract.PackageAssemblyError(
            f"exact confirmation required: {contract.CONFIRMATION}"
        )
    audit = contract.audit_package_image(image)
    _parent, target = _fresh_target(workspace)
    if not apply:
        return {
            **audit,
            "apply": False,
            "workspace": str(target),
            "formal_workspace_written": False,
            "writes_live": False,
        }
    return write_fresh_workspace(
        target, image, confirmation=confirmation or ""
    )


__all__ = [
    "WORKSPACE_NAME", "LOCK_NAME", "STAGING_NAME", "execute_fresh_workspace",
    "write_fresh_workspace", "inspect_fresh_target",
]
