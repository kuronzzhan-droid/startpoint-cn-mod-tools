#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal-workspace dry-run and non-bypassable apply boundary tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_summer_thunder_package_workspace as module
import wf_summer_thunder_package_workspace_commit as commit_io
from tests.summer_thunder_package_fixtures import complete_image
from wf_summer_thunder_package_contract import (
    CONFIRMATION,
    PACKAGE_ID,
    PackageAssemblyError,
    draft_manifest,
)
from wf_summer_thunder_package_evidence import EVIDENCE_RELATIVE
from wf_summer_thunder_package_paths import LOCK_NAME, STAGING_NAME


class AtomicWorkspaceWriteTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        workspace = root / PACKAGE_ID
        package = workspace / "package"
        evidence = workspace / "evidence"
        package.mkdir(parents=True)
        evidence.mkdir()
        (workspace / "workspace.json").write_text(
            json.dumps({
                "schema_version": 1,
                "package_id": PACKAGE_ID,
                "template_character_id": 231001,
                "character_id": 139998,
                "code_name": PACKAGE_ID,
                "package_dir": "package",
            }),
            encoding="utf-8",
        )
        (package / "manifest.json").write_text(
            json.dumps(draft_manifest()), encoding="utf-8"
        )
        (evidence / "status.json").write_bytes(b"user-status")
        return workspace

    def test_default_is_dry_run_and_pending_skill_never_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            before = (workspace / "package" / "manifest.json").read_bytes()
            report = module.execute_package(workspace, complete_image())
            self.assertEqual(83, report["payload_count"])
            self.assertEqual(22, report["table_claim_count"])
            self.assertFalse(report["apply"])
            self.assertFalse(report["apply_ready"])
            self.assertFalse((workspace / "package" / "roots").exists())
            self.assertFalse((workspace / EVIDENCE_RELATIVE).exists())
            self.assertEqual(before, (workspace / "package" / "manifest.json").read_bytes())
            self.assertEqual(b"user-status", (workspace / "evidence" / "status.json").read_bytes())

    def test_apply_requires_fixed_confirmation_and_has_no_validator_bypass(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            with self.assertRaisesRegex(PackageAssemblyError, CONFIRMATION):
                module.execute_package(
                    workspace, complete_image(), apply=True, confirmation="WRONG",
                )
            with self.assertRaisesRegex(PackageAssemblyError, "skill-follow"):
                module.execute_package(
                    workspace, complete_image(), apply=True, confirmation=CONFIRMATION,
                )
            with self.assertRaises(TypeError):
                module.write_package_atomic(
                    workspace, complete_image(), confirmation=CONFIRMATION,
                    validator=lambda *_: None,
                )
            self.assertFalse((workspace / "package" / "roots").exists())
            self.assertFalse((workspace / EVIDENCE_RELATIVE).exists())

    def test_workspace_wip_is_rejected_and_preserved_even_in_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            mine = workspace / "package" / "roots" / "common" / "mine.bin"
            mine.parent.mkdir(parents=True)
            mine.write_bytes(b"user-wip")
            with self.assertRaisesRegex(PackageAssemblyError, "existing WIP"):
                module.execute_package(workspace, complete_image())
            self.assertEqual(b"user-wip", mine.read_bytes())

    def test_apply_commits_83_payloads_evidence_and_manifest_with_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            image = complete_image(accepted_skill=True)
            report = module.execute_package(
                workspace, image, apply=True, confirmation=CONFIRMATION,
            )
            self.assertTrue(report["apply"])
            self.assertTrue(report["apply_ready"])
            payloads = [
                path
                for root in (workspace / "package" / "roots").iterdir()
                for path in root.rglob("*")
                if path.is_file()
            ]
            self.assertEqual(83, len(payloads))
            self.assertEqual(
                image.manifest,
                json.loads((workspace / "package" / "manifest.json").read_text(encoding="utf-8")),
            )
            self.assertEqual(
                image.source_report["source_locks_sha256"],
                report["source_locks_sha256"],
            )
            self.assertTrue((workspace / EVIDENCE_RELATIVE).is_file())
            self.assertEqual(b"user-status", (workspace / "evidence" / "status.json").read_bytes())

    def test_concurrent_wip_is_preserved_and_prevents_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            original = commit_io.stage_image

            def stage_then_race(*args, **kwargs):
                staged = original(*args, **kwargs)
                foreign = workspace / "package" / "roots" / "common" / "foreign.bin"
                foreign.parent.mkdir(parents=True, exist_ok=True)
                foreign.write_bytes(b"foreign-wip")
                return staged

            with mock.patch.object(commit_io, "stage_image", side_effect=stage_then_race):
                with self.assertRaisesRegex(PackageAssemblyError, "concurrent WIP"):
                    module.execute_package(
                        workspace, complete_image(accepted_skill=True),
                        apply=True, confirmation=CONFIRMATION,
                    )
            foreign = workspace / "package" / "roots" / "common" / "foreign.bin"
            self.assertEqual(b"foreign-wip", foreign.read_bytes())
            self.assertEqual(
                draft_manifest(),
                json.loads((workspace / "package" / "manifest.json").read_text()),
            )
            self.assertFalse((workspace / EVIDENCE_RELATIVE).exists())

    def test_mid_stage_failure_removes_recorded_bytes_but_preserves_foreign_wip(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            staging = workspace / STAGING_NAME
            foreign = staging / "foreign-wip.bin"
            original = commit_io._exclusive_bytes
            calls = 0

            def fail_on_second_write(path, raw):
                nonlocal calls
                calls += 1
                if calls == 2:
                    foreign.write_bytes(b"foreign-wip")
                    raise OSError("forced staging failure")
                original(path, raw)

            with mock.patch.object(
                commit_io, "_exclusive_bytes", side_effect=fail_on_second_write,
            ):
                with self.assertRaisesRegex(OSError, "forced staging failure"):
                    module.execute_package(
                        workspace, complete_image(accepted_skill=True),
                        apply=True, confirmation=CONFIRMATION,
                    )

            files = {
                path.relative_to(staging).as_posix(): path.read_bytes()
                for path in staging.rglob("*")
                if path.is_file()
            }
            self.assertEqual({"foreign-wip.bin": b"foreign-wip"}, files)
            self.assertFalse((workspace / LOCK_NAME).exists())
            self.assertEqual(
                draft_manifest(),
                json.loads((workspace / "package" / "manifest.json").read_text()),
            )

    def test_staged_payload_readback_failure_removes_the_just_written_file(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            staging = workspace / STAGING_NAME
            original = commit_io.read_file
            injected = False

            def fail_first_staged_readback(path, label):
                nonlocal injected
                if label == "staged payload" and not injected:
                    injected = True
                    return path.read_bytes() + b"corrupt-readback"
                return original(path, label)

            with mock.patch.object(
                commit_io, "read_file", side_effect=fail_first_staged_readback,
            ):
                with self.assertRaisesRegex(
                    PackageAssemblyError, "staged payload readback failed",
                ):
                    module.execute_package(
                        workspace, complete_image(accepted_skill=True),
                        apply=True, confirmation=CONFIRMATION,
                    )

            self.assertFalse(staging.exists())
            self.assertFalse((workspace / LOCK_NAME).exists())
            self.assertEqual(
                draft_manifest(),
                json.loads((workspace / "package" / "manifest.json").read_text()),
            )

    def test_partial_staged_write_failure_removes_its_own_incomplete_file(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            staging = workspace / STAGING_NAME
            original_fdopen = commit_io.os.fdopen
            injected = False

            class PartialWrite:
                def __init__(self, output):
                    self.output = output

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    del exc_type, exc, traceback
                    self.output.close()

                def write(self, raw):
                    self.output.write(raw[:1])
                    self.output.flush()
                    raise OSError("forced partial staging write")

            def fail_first_fdopen(descriptor, mode):
                nonlocal injected
                output = original_fdopen(descriptor, mode)
                if not injected:
                    injected = True
                    return PartialWrite(output)
                return output

            with mock.patch.object(
                commit_io.os, "fdopen", side_effect=fail_first_fdopen,
            ):
                with self.assertRaisesRegex(OSError, "forced partial staging write"):
                    module.execute_package(
                        workspace, complete_image(accepted_skill=True),
                        apply=True, confirmation=CONFIRMATION,
                    )

            self.assertFalse(staging.exists())
            self.assertFalse((workspace / LOCK_NAME).exists())
            self.assertEqual(
                draft_manifest(),
                json.loads((workspace / "package" / "manifest.json").read_text()),
            )

    def test_failed_post_commit_readback_restores_draft_without_deleting_foreign_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self._workspace(Path(temp))
            with mock.patch.object(
                commit_io, "readback_disk",
                side_effect=PackageAssemblyError("forced readback failure"),
            ):
                with self.assertRaisesRegex(PackageAssemblyError, "forced readback"):
                    module.execute_package(
                        workspace, complete_image(accepted_skill=True),
                        apply=True, confirmation=CONFIRMATION,
                    )
            self.assertEqual(
                draft_manifest(),
                json.loads((workspace / "package" / "manifest.json").read_text()),
            )
            self.assertFalse((workspace / EVIDENCE_RELATIVE).exists())
            roots = workspace / "package" / "roots"
            self.assertFalse(any(path.is_file() for path in roots.rglob("*")))


if __name__ == "__main__":
    unittest.main()
