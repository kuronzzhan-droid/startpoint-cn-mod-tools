#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-workspace and fixed CLI tests for thunder hotfix 1.1.6."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_thunder_hotfix_package as package
import wf_thunder_hotfix_package_cli as cli
import wf_thunder_hotfix_package_workspace as workspace
from wf_summer_thunder_package_contract import PackageImage


class ThunderHotfixWorkspaceTests(unittest.TestCase):
    def test_uses_a_fresh_116_workspace_name(self):
        self.assertEqual("cnmod_thunder_dragon_hotfix_1_1_6", workspace.WORKSPACE_NAME)
        self.assertEqual(
            "ASSEMBLE_CNMOD_THUNDER_DRAGON_ABYSS_GACHA_1_1_6",
            package.CONFIRMATION,
        )
        self.assertEqual("1.1.6", package.PACKAGE_VERSION)

    def test_client_base_comes_from_one_flippable_constant(self):
        self.assertEqual(
            package.CLIENT_BASE_WITH_SWIM_PRINCESS_EX,
            package.REQUIRES_CLIENT_BASE,
        )
        self.assertEqual(
            package.CLIENT_BASE_WITH_SWIM_PRINCESS_EX,
            package.SHARED_ASSET_BASELINE_CLIENT_VERSION,
        )
        self.assertEqual("1.4.325", package.REQUIRES_CLIENT_BASE)

    def _image(self) -> PackageImage:
        roots = {root: {} for root in package.ROOT_NAMES}
        source_locks = {
            "schema_version": 1,
            "source_package": {},
            "repair_inputs": {},
            "repair_reports": {},
            "changed_payloads": [],
            "added_payloads": [],
            "acceptance": {},
            "writes_live": False,
            "formal_workspace_written": False,
        }
        return PackageImage(
            roots,
            {"package_id": package.PACKAGE_ID},
            {"source_locks": source_locks},
        )

    def test_default_execution_is_read_only_and_apply_is_exactly_confirmed(self):
        image = self._image()
        audit = {"apply_ready": True, "payload_count": 107}
        with tempfile.TemporaryDirectory() as temporary_name:
            target = Path(temporary_name) / workspace.WORKSPACE_NAME
            with mock.patch.object(package, "audit_hotfix_package", return_value=audit):
                report = workspace.execute_fresh_workspace(target, image)
                self.assertFalse(target.exists())
                self.assertFalse(report["apply"])
                with self.assertRaisesRegex(
                    package.PackageAssemblyError, "exact confirmation"
                ):
                    workspace.execute_fresh_workspace(
                        target, image, apply=True, confirmation="wrong"
                    )

    def test_apply_writes_exact_workspace_and_refuses_existing_target(self):
        image = self._image()
        audit = {"apply_ready": True, "payload_count": 0}
        with tempfile.TemporaryDirectory() as temporary_name:
            target = Path(temporary_name) / workspace.WORKSPACE_NAME
            with (
                mock.patch.object(package, "audit_hotfix_package", return_value=audit),
                mock.patch.object(
                    workspace.commit_io, "readback_disk", return_value=None
                ),
            ):
                report = workspace.execute_fresh_workspace(
                    target,
                    image,
                    apply=True,
                    confirmation=package.CONFIRMATION,
                )
                self.assertTrue(report["formal_workspace_written"])
                self.assertTrue((target / "workspace.json").is_file())
                self.assertTrue((target / "package" / "manifest.json").is_file())
                self.assertTrue(
                    (target / "evidence" / "package-source-locks.json").is_file()
                )
                with self.assertRaisesRegex(
                    package.PackageAssemblyError, "already exists"
                ):
                    workspace.execute_fresh_workspace(target, image)

    def test_fixed_workspace_handles_the_longest_action_payload_on_windows(self):
        image = self._image()
        logical = (
            "battle/action/skill/action/rare5/"
            "cnmod_thunder_dragon_ascendant$"
            "cnmod_thunder_dragon_ascendant_1.action.dsl.amf3.deflate"
        )
        image.roots["common"][logical] = b"action"
        with tempfile.TemporaryDirectory() as temporary_name:
            target = Path(temporary_name) / workspace.WORKSPACE_NAME
            with mock.patch.object(
                package, "audit_hotfix_package",
                return_value={"apply_ready": True, "payload_count": 1},
            ):
                report = workspace.execute_fresh_workspace(
                    target,
                    image,
                    apply=True,
                    confirmation=package.CONFIRMATION,
                )
            self.assertTrue(report["formal_workspace_written"])
            self.assertEqual(
                b"action",
                (target / "package" / "roots" / "common"
                 / Path(*logical.split("/"))).read_bytes(),
            )

    def test_cli_double_reads_inputs_and_defaults_to_dry_run(self):
        source = object()
        donor = object()
        image = self._image()
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            (root / "work" / "character_packs").mkdir(parents=True)
            (root / "work" / "builds").mkdir(parents=True)
            with (
                mock.patch.object(cli, "TOOL_ROOT", root),
                mock.patch.object(
                    cli.source_io, "load_sealed_source_workspace",
                    side_effect=[source, source],
                ) as load_source,
                mock.patch.object(
                    cli.source_io, "load_locked_donor_template",
                    side_effect=[donor, donor],
                ) as load_donor,
                mock.patch.object(
                    cli.package, "compile_hotfix_package",
                    side_effect=[image, image],
                ) as compile_image,
                mock.patch.object(cli, "_git_head", return_value="b" * 40),
                mock.patch.object(
                    cli.workspace, "execute_fresh_workspace",
                    return_value={"apply": False, "writes_live": False},
                ) as execute,
            ):
                report = cli.run(cli.parse_args([]))
        self.assertEqual({"apply": False, "writes_live": False}, report)
        self.assertEqual(2, load_source.call_count)
        self.assertEqual(2, load_donor.call_count)
        self.assertEqual(2, compile_image.call_count)
        self.assertFalse(execute.call_args.kwargs["apply"])


if __name__ == "__main__":
    unittest.main()
