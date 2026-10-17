#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reparse, containment, and exclusive staging tests."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import wf_summer_thunder_package_paths as module
from wf_summer_thunder_package_contract import PackageAssemblyError


class PackagePathSafetyTests(unittest.TestCase):
    def test_workspace_with_reparse_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_parent = root / "real-parent"
            workspace = real_parent / "workspace"
            workspace.mkdir(parents=True)
            linked_parent = root / "linked-parent"
            try:
                os.symlink(real_parent, linked_parent, target_is_directory=True)
            except OSError as exc:
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(linked_parent), str(real_parent)],
                    capture_output=True,
                    check=False,
                )
                if created.returncode != 0:
                    self.skipTest(f"parent reparse creation unavailable: {exc}")
            try:
                with self.assertRaisesRegex(PackageAssemblyError, "reparse|symlink"):
                    module.assert_workspace_tree_safe(linked_parent / "workspace")
            finally:
                if os.path.lexists(linked_parent):
                    if linked_parent.is_symlink():
                        linked_parent.unlink()
                    else:
                        os.rmdir(linked_parent)

    def test_workspace_or_target_symlink_is_rejected_even_when_it_points_inside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            real_package = workspace / "real-package"
            real_package.mkdir(parents=True)
            link = workspace / "package"
            try:
                os.symlink(real_package, link, target_is_directory=True)
            except OSError as exc:
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(link), str(real_package)],
                    capture_output=True,
                    check=False,
                )
                if created.returncode != 0:
                    self.skipTest(f"reparse creation unavailable: {exc}")
            try:
                with self.assertRaisesRegex(PackageAssemblyError, "reparse|symlink"):
                    module.assert_workspace_tree_safe(workspace)
                with self.assertRaisesRegex(PackageAssemblyError, "reparse|symlink"):
                    module.safe_contained_target(workspace, "package/manifest.json")
            finally:
                if os.path.lexists(link):
                    os.rmdir(link)

    def test_resolved_target_must_remain_inside_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            root.mkdir()
            with self.assertRaisesRegex(PackageAssemblyError, "escapes"):
                module.safe_contained_target(root, "../outside.bin")
            target = module.safe_contained_target(root, "package/manifest.json")
            self.assertEqual(root / "package" / "manifest.json", target)

    def test_lock_and_staging_are_exclusive_and_foreign_wip_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            staging = workspace / module.STAGING_NAME
            staging.mkdir()
            mine = staging / "mine.bin"
            mine.write_bytes(b"user-wip")
            with self.assertRaisesRegex(PackageAssemblyError, "staging"):
                with module.ExclusiveWorkspaceLease(workspace):
                    self.fail("pre-existing staging must never be entered")
            self.assertEqual(b"user-wip", mine.read_bytes())

            staging.rmdir() if not any(staging.iterdir()) else None
            mine.unlink()
            staging.rmdir()
            with module.ExclusiveWorkspaceLease(workspace) as first:
                self.assertTrue(first.staging.is_dir())
                with self.assertRaisesRegex(PackageAssemblyError, "lock"):
                    with module.ExclusiveWorkspaceLease(workspace):
                        self.fail("second lease must not enter")
            self.assertFalse((workspace / module.LOCK_NAME).exists())
            self.assertFalse((workspace / module.STAGING_NAME).exists())


if __name__ == "__main__":
    unittest.main()
