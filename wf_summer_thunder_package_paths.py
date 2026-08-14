#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Filesystem containment, reparse rejection, and exclusive staging lease."""

from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

from wf_summer_thunder_package_contract import PackageAssemblyError


LOCK_NAME = ".summer-thunder-package-assemble.lock"
STAGING_NAME = ".summer-thunder-package-assemble.staging"
_OWNER_NAME = ".owner"


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PackageAssemblyError(f"cannot inspect path: {path}") from exc
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _assert_regular_path(path: Path, label: str) -> None:
    if _is_reparse(path):
        raise PackageAssemblyError(f"{label} contains a reparse point or symlink: {path}")


def _assert_existing_ancestor_chain_regular(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if _lexists(ancestor):
            _assert_regular_path(ancestor, "workspace ancestor")


def assert_workspace_tree_safe(workspace: Path) -> Path:
    """Reject every existing symlink/junction/reparse node in the workspace."""

    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir():
        raise PackageAssemblyError("workspace must be an existing absolute directory")
    _assert_existing_ancestor_chain_regular(root)

    def walk(directory: Path) -> None:
        _assert_regular_path(directory, "workspace")
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise PackageAssemblyError(f"workspace is unreadable: {directory}") from exc
        for entry in entries:
            child = Path(entry.path)
            _assert_regular_path(child, "workspace")
            if entry.is_dir(follow_symlinks=False):
                walk(child)

    walk(root)
    return root.resolve(strict=True)


def safe_contained_target(root: Path, relative: str) -> Path:
    """Resolve a future target and prove all existing ancestors are non-reparse."""

    anchor = Path(root)
    anchor_resolved = assert_workspace_tree_safe(anchor)
    relative_path = Path(relative)
    if (
        relative_path.is_absolute()
        or relative_path.drive
        or not relative_path.parts
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise PackageAssemblyError(f"target escapes workspace: {relative}")
    candidate = anchor.joinpath(*relative_path.parts)
    cursor = anchor
    for part in relative_path.parts:
        cursor = cursor / part
        if not _lexists(cursor):
            break
        _assert_regular_path(cursor, "target")
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(anchor_resolved)
    except ValueError as exc:
        raise PackageAssemblyError(f"target escapes workspace: {relative}") from exc
    return candidate


class ExclusiveWorkspaceLease:
    """Fixed-name O_EXCL lock plus owner-marked staging directory."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.lock = self.workspace / LOCK_NAME
        self.staging = self.workspace / STAGING_NAME
        self.owner = self.staging / _OWNER_NAME
        self._token = uuid.uuid4().hex
        self._entered = False

    def __enter__(self) -> "ExclusiveWorkspaceLease":
        assert_workspace_tree_safe(self.workspace)
        if _lexists(self.lock):
            raise PackageAssemblyError("exclusive workspace lock already exists")
        if _lexists(self.staging):
            raise PackageAssemblyError("exclusive staging already exists")
        lock_fd: int | None = None
        try:
            lock_fd = os.open(
                self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(lock_fd, self._token.encode("ascii"))
            os.close(lock_fd)
            lock_fd = None
            os.mkdir(self.staging)
            owner_fd = os.open(
                self.owner, os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(owner_fd, self._token.encode("ascii"))
            finally:
                os.close(owner_fd)
            assert_workspace_tree_safe(self.workspace)
            self._entered = True
            return self
        except FileExistsError as exc:
            raise PackageAssemblyError("exclusive workspace lock/staging race") from exc
        except Exception:
            if lock_fd is not None:
                os.close(lock_fd)
            self._release_owned_empty_paths()
            raise

    def _release_owned_empty_paths(self) -> None:
        if _lexists(self.owner) and not _is_reparse(self.owner):
            try:
                if self.owner.read_text(encoding="ascii") == self._token:
                    self.owner.unlink()
            except OSError:
                pass
        if _lexists(self.staging) and not _is_reparse(self.staging):
            try:
                self.staging.rmdir()
            except OSError:
                pass
        if _lexists(self.lock) and not _is_reparse(self.lock):
            try:
                if self.lock.read_text(encoding="ascii") == self._token:
                    self.lock.unlink()
            except OSError:
                pass

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        if self._entered:
            self._release_owned_empty_paths()
        self._entered = False


__all__ = [
    "LOCK_NAME", "STAGING_NAME", "assert_workspace_tree_safe",
    "safe_contained_target", "ExclusiveWorkspaceLease",
]
