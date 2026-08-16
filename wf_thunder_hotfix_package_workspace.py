#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atomic fresh-workspace boundary for thunder-dragon hotfix 1.1.6."""

from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any, Mapping

import wf_summer_thunder_package_workspace_commit as commit_io
import wf_thunder_hotfix_package as package
from wf_summer_thunder_package_paths import assert_workspace_tree_safe
from wf_summer_thunder_package_workspace_state import manifest_bytes


WORKSPACE_NAME = "cnmod_thunder_dragon_hotfix_1_1_6"
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
        raise package.PackageAssemblyError("workspace parent must be absolute")
    try:
        for current in (parent, *parent.parents):
            info = os.lstat(current)
            if _is_reparse(info):
                raise OSError("reparse point")
        if not stat.S_ISDIR(os.lstat(parent).st_mode):
            raise OSError("not a directory")
        return parent.resolve(strict=True)
    except OSError as exc:
        raise package.PackageAssemblyError(
            "workspace parent is unsafe or missing"
        ) from exc


def _fresh_target(workspace: Path) -> tuple[Path, Path]:
    target = Path(workspace)
    if not target.is_absolute() or target.name != WORKSPACE_NAME:
        raise package.PackageAssemblyError(
            f"formal workspace must use the fixed name {WORKSPACE_NAME}"
        )
    parent = _safe_parent(target.parent)
    candidate = parent / WORKSPACE_NAME
    if os.path.lexists(candidate):
        raise package.PackageAssemblyError("formal workspace already exists")
    return parent, candidate


def inspect_fresh_target(workspace: Path) -> Path:
    return _fresh_target(workspace)[1]


def _workspace_json() -> bytes:
    return (
        json.dumps({
            "schema_version": 1,
            "package_id": package.PACKAGE_ID,
            "template_character_id": 231001,
            "character_id": package.CHARACTER_ID,
            "code_name": package.CODE_NAME,
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
        self.lock = parent / LOCK_NAME
        self.staging = parent / STAGING_NAME
        self.token = uuid.uuid4().hex.encode("ascii")

    def __enter__(self):
        if os.path.lexists(self.lock) or os.path.lexists(self.staging):
            raise package.PackageAssemblyError(
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
            return self
        except FileExistsError as exc:
            raise package.PackageAssemblyError(
                "fresh workspace lock/staging race"
            ) from exc
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            self._release()
            raise

    def _release(self) -> None:
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
        self._release()


def _cleanup(staging: Path, staged: Mapping[Path, bytes], workspace_raw: bytes) -> None:
    commit_io.cleanup_staging(staging, staged)
    _remove_owned(staging / "workspace.json", workspace_raw)
    try:
        staging.rmdir()
    except OSError:
        pass


def _rollback(
    target: Path,
    image: package.PackageImage,
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
    for path, raw in (
        (target / "evidence" / "package-source-locks.json", evidence_raw),
        (target / "package" / "manifest.json", manifest_raw),
        (target / "workspace.json", workspace_raw),
    ):
        _remove_owned(path, raw)
        paths.append(path)
    commit_io._remove_empty_parents(paths, target)  # type: ignore[attr-defined]
    try:
        target.rmdir()
    except OSError:
        pass


def write_fresh_workspace(
    workspace: Path,
    image: package.PackageImage,
    *,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != package.CONFIRMATION:
        raise package.PackageAssemblyError(
            f"exact confirmation required: {package.CONFIRMATION}"
        )
    audit = package.audit_hotfix_package(image)
    parent, target = _fresh_target(workspace)
    evidence_raw = package.source_lock_evidence_bytes(
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
                raise package.PackageAssemblyError("workspace staged readback drift")
            if os.path.lexists(target):
                raise package.PackageAssemblyError(
                    "formal workspace appeared before commit"
                )
            os.rename(lease.staging, target)
            published = True
            commit_io.readback_disk(target, image, evidence_raw, manifest_raw)
            if (target / "workspace.json").read_bytes() != workspace_raw:
                raise package.PackageAssemblyError("workspace final readback drift")
        except Exception:
            if published:
                _rollback(target, image, evidence_raw, manifest_raw, workspace_raw)
            else:
                _cleanup(lease.staging, staged, workspace_raw)
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
    image: package.PackageImage,
    *,
    apply: bool = False,
    confirmation: str | None = None,
) -> dict[str, Any]:
    if apply and confirmation != package.CONFIRMATION:
        raise package.PackageAssemblyError(
            f"exact confirmation required: {package.CONFIRMATION}"
        )
    audit = package.audit_hotfix_package(image)
    target = _fresh_target(workspace)[1]
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
    "WORKSPACE_NAME", "LOCK_NAME", "STAGING_NAME", "inspect_fresh_target",
    "write_fresh_workspace", "execute_fresh_workspace",
]
