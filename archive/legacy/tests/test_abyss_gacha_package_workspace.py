#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh replacement-workspace atomic writer tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_abyss_gacha_package_contract as contract
import wf_abyss_gacha_package_workspace as module
import wf_summer_thunder_package_workspace_commit as commit_io
from tests import test_abyss_gacha_package_contract as package_fixtures
from wf_summer_thunder_package_evidence import EVIDENCE_RELATIVE


def eligible_image():
    fixtures = package_fixtures.AbyssGachaPackageContractTests()
    return contract.build_package_image(
        fixtures._source(), fixtures._bundle(), generator_git_head="c" * 40
    )


class FreshWorkspaceTests(unittest.TestCase):
    def _target(self, root: Path) -> Path:
        return root / module.WORKSPACE_NAME

    def test_default_dry_run_audits_without_creating_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            target = self._target(Path(temporary_name))
            report = module.execute_fresh_workspace(target, eligible_image())

            self.assertFalse(report["apply"])
            self.assertEqual(contract.EXPECTED_PAYLOAD_COUNT, report["payload_count"])
            self.assertFalse(target.exists())
            self.assertFalse(report["writes_live"])

    def test_apply_requires_fixed_confirmation_and_writes_manifest_last(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            target = self._target(Path(temporary_name))
            image = eligible_image()
            with self.assertRaisesRegex(contract.PackageAssemblyError, contract.CONFIRMATION):
                module.execute_fresh_workspace(
                    target, image, apply=True, confirmation="WRONG"
                )
            order: list[str] = []
            original = commit_io._exclusive_bytes
            staging = target.parent / module.STAGING_NAME

            def record(path, raw):
                order.append(path.relative_to(staging).as_posix())
                return original(path, raw)

            with mock.patch.object(commit_io, "_exclusive_bytes", side_effect=record):
                report = module.execute_fresh_workspace(
                    target,
                    image,
                    apply=True,
                    confirmation=contract.CONFIRMATION,
                )

            self.assertTrue(report["apply"])
            self.assertEqual("package/manifest.json", order[-1])
            self.assertEqual(
                image.manifest,
                json.loads((target / "package" / "manifest.json").read_text()),
            )
            self.assertTrue((target / EVIDENCE_RELATIVE).is_file())
            payloads = [
                path for path in (target / "package" / "roots").rglob("*")
                if path.is_file()
            ]
            self.assertEqual(contract.EXPECTED_PAYLOAD_COUNT, len(payloads))

    def test_existing_output_is_never_clobbered_even_in_dry_run(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            target = self._target(Path(temporary_name))
            target.mkdir()
            mine = target / "mine.txt"
            mine.write_bytes(b"user-wip")
            with self.assertRaisesRegex(contract.PackageAssemblyError, "already exists"):
                module.execute_fresh_workspace(target, eligible_image())
            self.assertEqual(b"user-wip", mine.read_bytes())

    def test_stage_failure_rolls_back_owned_files_and_preserves_foreign_wip(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            parent = Path(temporary_name)
            target = self._target(parent)
            staging = parent / module.STAGING_NAME
            original = commit_io._exclusive_bytes
            calls = 0

            def fail_with_foreign(path, raw):
                nonlocal calls
                calls += 1
                if calls == 2:
                    foreign = staging / "foreign.bin"
                    foreign.write_bytes(b"foreign-wip")
                    raise OSError("forced stage failure")
                return original(path, raw)

            with mock.patch.object(
                commit_io, "_exclusive_bytes", side_effect=fail_with_foreign
            ):
                with self.assertRaisesRegex(OSError, "forced stage failure"):
                    module.execute_fresh_workspace(
                        target,
                        eligible_image(),
                        apply=True,
                        confirmation=contract.CONFIRMATION,
                    )
            self.assertFalse(target.exists())
            self.assertEqual(b"foreign-wip", (staging / "foreign.bin").read_bytes())
            self.assertFalse((parent / module.LOCK_NAME).exists())

    def test_final_readback_failure_removes_owned_output_but_preserves_new_wip(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            parent = Path(temporary_name)
            target = self._target(parent)
            original = commit_io.readback_disk

            def fail_final(workspace, *args):
                if workspace == target:
                    (target / "foreign.bin").write_bytes(b"foreign-wip")
                    raise contract.PackageAssemblyError("forced final readback")
                return original(workspace, *args)

            with mock.patch.object(commit_io, "readback_disk", side_effect=fail_final):
                with self.assertRaisesRegex(
                    contract.PackageAssemblyError, "forced final readback"
                ):
                    module.execute_fresh_workspace(
                        target,
                        eligible_image(),
                        apply=True,
                        confirmation=contract.CONFIRMATION,
                    )
            self.assertEqual(b"foreign-wip", (target / "foreign.bin").read_bytes())
            self.assertFalse((target / "workspace.json").exists())
            self.assertFalse((parent / module.LOCK_NAME).exists())


if __name__ == "__main__":
    unittest.main()
