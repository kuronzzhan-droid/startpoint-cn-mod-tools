#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed-input, dry-run-default package assembler CLI tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_summer_thunder_package_cli as module
from tests.summer_thunder_package_fixtures import complete_image
from wf_summer_thunder_package_contract import CONFIRMATION, PackageAssemblyError


class PackageCliTests(unittest.TestCase):
    def test_parser_defaults_to_dry_run_and_exposes_no_path_override(self):
        args = module.parse_args([])
        self.assertFalse(args.apply)
        self.assertIsNone(args.confirm)
        with self.assertRaises(SystemExit):
            module.parse_args(["--workspace", "D:/escape"])

    def test_wrong_apply_confirmation_fails_before_compilation(self):
        with mock.patch.object(module, "_compile_fixed_image") as compiler:
            with self.assertRaisesRegex(PackageAssemblyError, CONFIRMATION):
                module.run(module.parse_args(["--apply", "--confirm", "WRONG"]))
        compiler.assert_not_called()

    def test_run_derives_all_inputs_and_workspace_from_tool_root(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            image = complete_image(accepted_skill=True)
            with (
                mock.patch.object(module, "TOOL_ROOT", root),
                mock.patch.object(module, "_compile_fixed_image", return_value=image) as compiler,
                mock.patch.object(module, "execute_package", return_value={"apply": False}) as execute,
            ):
                self.assertEqual(
                    {"apply": False}, module.run(module.parse_args([]))
                )
            compiler.assert_called_once_with(root)
            execute.assert_called_once_with(
                root / "work" / "character_packs" / module.PACKAGE_ID,
                image,
                apply=False,
                confirmation=None,
            )


if __name__ == "__main__":
    unittest.main()
