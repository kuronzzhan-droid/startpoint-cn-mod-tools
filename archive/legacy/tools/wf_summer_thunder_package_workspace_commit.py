#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exclusive staging, manifest-last commit, rollback, and disk readback."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Mapping

from wf_summer_thunder_package_contract import (
    ROOT_NAMES,
    PackageAssemblyError,
    PackageImage,
    logical_segments,
)
from wf_summer_thunder_package_evidence import EVIDENCE_RELATIVE
from wf_summer_thunder_package_paths import (
    assert_workspace_tree_safe,
    safe_contained_target,
)
from wf_summer_thunder_package_workspace_state import (
    WorkspaceSnapshot,
    assert_snapshot_unchanged,
    read_file,
)


def _identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)


def _remove_if_identity(path: Path, identity: tuple[int, int]) -> None:
    try:
        info = path.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            stat.S_ISREG(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and not attributes & reparse_flag
            and _identity(info) == identity
        ):
            path.unlink()
    except OSError:
        pass


def _exclusive_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise PackageAssemblyError(f"staging target already exists: {path}") from exc
    identity = _identity(os.fstat(descriptor))
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if read_file(path, "staged payload") != raw:
            raise PackageAssemblyError(f"staged payload readback failed: {path}")
    except Exception:
        _remove_if_identity(path, identity)
        raise


def _remove_if_ours(path: Path, raw: bytes) -> None:
    try:
        if path.is_file() and not path.is_symlink() and path.read_bytes() == raw:
            path.unlink()
    except OSError:
        pass


def _remove_empty_parents(paths: list[Path], stop: Path) -> None:
    candidates: set[Path] = set()
    for path in paths:
        cursor = path.parent
        while cursor != stop and stop in cursor.parents:
            candidates.add(cursor)
            cursor = cursor.parent
    for directory in sorted(candidates, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _cleanup_recorded_staging(
    staging: Path, staged: Mapping[Path, bytes]
) -> None:
    for path, raw in staged.items():
        _remove_if_ours(path, raw)
    _remove_empty_parents(list(staged), staging)


def stage_image(
    staging: Path, image: PackageImage, evidence_raw: bytes, manifest_raw: bytes
) -> dict[Path, bytes]:
    staged: dict[Path, bytes] = {}
    attempted: list[Path] = []
    try:
        for root_name in ROOT_NAMES:
            for logical_path, raw in sorted(image.roots[root_name].items()):
                relative = Path(
                    "package", "roots", root_name, *logical_segments(logical_path)
                )
                target = safe_contained_target(staging, relative.as_posix())
                attempted.append(target)
                _exclusive_bytes(target, raw)
                staged[target] = raw
        evidence = safe_contained_target(staging, EVIDENCE_RELATIVE)
        attempted.append(evidence)
        _exclusive_bytes(evidence, evidence_raw)
        staged[evidence] = evidence_raw
        manifest = safe_contained_target(staging, "package/manifest.json")
        attempted.append(manifest)
        _exclusive_bytes(manifest, manifest_raw)
        staged[manifest] = manifest_raw
    except Exception:
        _cleanup_recorded_staging(staging, staged)
        _remove_empty_parents(attempted, staging)
        raise
    return staged


def readback_disk(
    workspace: Path,
    image: PackageImage,
    evidence_raw: bytes,
    manifest_raw: bytes,
) -> None:
    assert_workspace_tree_safe(workspace)
    expected: dict[Path, bytes] = {}
    for root_name in ROOT_NAMES:
        root = workspace / "package" / "roots" / root_name
        for logical_path, raw in image.roots[root_name].items():
            expected[root.joinpath(*logical_segments(logical_path))] = raw
    actual = {
        path
        for root_name in ROOT_NAMES
        for path in (workspace / "package" / "roots" / root_name).rglob("*")
        if path.is_file()
    }
    if actual != set(expected):
        raise PackageAssemblyError("formal payload readback file-set mismatch")
    for path, raw in expected.items():
        if read_file(path, "formal payload") != raw:
            raise PackageAssemblyError(f"formal payload readback mismatch: {path}")
    if read_file(workspace / EVIDENCE_RELATIVE, "source-lock evidence") != evidence_raw:
        raise PackageAssemblyError("source-lock evidence readback mismatch")
    if read_file(workspace / "package" / "manifest.json", "manifest") != manifest_raw:
        raise PackageAssemblyError("manifest readback mismatch")


def _assert_precommit_state(
    workspace: Path,
    image: PackageImage,
    snapshot: WorkspaceSnapshot,
    evidence_raw: bytes,
) -> None:
    assert_workspace_tree_safe(workspace)
    if read_file(workspace / "workspace.json", "workspace.json") != snapshot.workspace_json:
        raise PackageAssemblyError("concurrent WIP changed workspace.json")
    manifest = workspace / "package" / "manifest.json"
    if read_file(manifest, "existing manifest") != snapshot.draft_manifest:
        raise PackageAssemblyError("concurrent WIP changed the draft manifest")
    expected: dict[Path, bytes] = {}
    for root_name in ROOT_NAMES:
        root = workspace / "package" / "roots" / root_name
        for logical_path, raw in image.roots[root_name].items():
            expected[root.joinpath(*logical_segments(logical_path))] = raw
    actual = {
        path
        for root_name in ROOT_NAMES
        for path in (workspace / "package" / "roots" / root_name).rglob("*")
        if path.is_file()
    }
    if actual != set(expected):
        raise PackageAssemblyError("concurrent WIP changed the precommit payload set")
    for path, raw in expected.items():
        if read_file(path, "precommit payload") != raw:
            raise PackageAssemblyError(f"concurrent WIP changed payload: {path}")
    if read_file(workspace / EVIDENCE_RELATIVE, "precommit source-lock evidence") != evidence_raw:
        raise PackageAssemblyError("concurrent WIP changed source-lock evidence")


def _link_exclusive(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except FileExistsError as exc:
        raise PackageAssemblyError(f"concurrent WIP occupied target: {target}") from exc
    except OSError as exc:
        raise PackageAssemblyError(f"cannot commit staged target: {target}") from exc


def commit_staged(
    workspace: Path,
    staging: Path,
    image: PackageImage,
    snapshot: WorkspaceSnapshot,
    evidence_raw: bytes,
    manifest_raw: bytes,
) -> None:
    committed: dict[Path, bytes] = {}
    backup = staging / "draft-manifest.backup"
    manifest_target = workspace / "package" / "manifest.json"
    try:
        assert_snapshot_unchanged(workspace, snapshot)
        for root_name in ROOT_NAMES:
            for logical_path, raw in sorted(image.roots[root_name].items()):
                relative = Path("package", "roots", root_name, *logical_segments(logical_path))
                target = safe_contained_target(workspace, relative.as_posix())
                _link_exclusive(staging / relative, target)
                committed[target] = raw
        evidence_target = safe_contained_target(workspace, EVIDENCE_RELATIVE)
        _link_exclusive(staging / EVIDENCE_RELATIVE, evidence_target)
        committed[evidence_target] = evidence_raw
        _assert_precommit_state(workspace, image, snapshot, evidence_raw)
        os.rename(manifest_target, backup)
        if read_file(backup, "draft manifest backup") != snapshot.draft_manifest:
            os.rename(backup, manifest_target)
            raise PackageAssemblyError("concurrent WIP changed manifest at commit point")
        try:
            _link_exclusive(staging / "package" / "manifest.json", manifest_target)
        except Exception:
            if not os.path.lexists(manifest_target):
                os.rename(backup, manifest_target)
            raise
        committed[manifest_target] = manifest_raw
        readback_disk(workspace, image, evidence_raw, manifest_raw)
        backup.unlink()
    except Exception:
        _remove_if_ours(manifest_target, manifest_raw)
        if os.path.lexists(backup) and not os.path.lexists(manifest_target):
            try:
                os.rename(backup, manifest_target)
            except OSError:
                pass
        for target, raw in reversed(list(committed.items())):
            if target != manifest_target:
                _remove_if_ours(target, raw)
        _remove_empty_parents(list(committed), workspace)
        raise


def cleanup_staging(staging: Path, staged: Mapping[Path, bytes]) -> None:
    _cleanup_recorded_staging(staging, staged)
    try:
        (staging / "draft-manifest.backup").unlink(missing_ok=True)
    except OSError:
        pass


__all__ = ["stage_image", "readback_disk", "commit_staged", "cleanup_staging"]
