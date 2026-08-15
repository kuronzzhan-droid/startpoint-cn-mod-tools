#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed-input dry-run-default replacement assembler CLI tests."""

from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wf_abyss_gacha_package_cli as module
import wf_abyss_gacha_package_compile as package_compile
import wf_abyss_gacha_package_contract as contract
import wf_abyss_gacha_package_workspace as workspace
from tests.test_abyss_gacha_package_compile import compile_sources, source_package
from tests import test_abyss_gacha_package_contract as package_fixtures


class PackageCliTests(unittest.TestCase):
    def test_parser_defaults_to_dry_run_and_exposes_no_path_override(self):
        args = module.parse_args([])
        self.assertFalse(args.apply)
        self.assertIsNone(args.confirm)
        with self.assertRaises(SystemExit):
            module.parse_args(["--workspace", "D:/escape"])

    def test_wrong_confirmation_fails_before_any_compilation(self):
        with mock.patch.object(module, "_compile_fixed_plan") as compiler:
            with self.assertRaisesRegex(contract.PackageAssemblyError, contract.CONFIRMATION):
                module.run(module.parse_args(["--apply", "--confirm", "WRONG"]))
        compiler.assert_not_called()

    def test_fixed_plan_reads_every_production_input_twice_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            source = source_package()
            sources = compile_sources()
            additions = package_compile.compile_additions(source, sources)
            with (
                mock.patch.object(
                    module.source_io, "load_sealed_source_workspace",
                    side_effect=(source, source),
                ) as load_source,
                mock.patch.object(
                    module.source_io, "load_addition_sources",
                    side_effect=(sources, sources),
                ) as load_inputs,
                mock.patch.object(
                    module.package_compile, "compile_additions",
                    side_effect=(additions, additions),
                ) as compile_additions,
                mock.patch.object(module, "_git_head", return_value="c" * 40),
            ):
                plan = module._compile_fixed_plan(root)
            old = root / "work" / "character_packs" / contract.PACKAGE_ID
            store = (
                root / "work" / "stores" / "cnmod_abyss_gacha_release_base"
                / "production" / "upload"
            )
            server = root.parent / "startpoint-cn" / "assets"
            self.assertEqual([mock.call(old), mock.call(old)], load_source.call_args_list)
            self.assertEqual(
                [mock.call(store, server), mock.call(store, server)],
                load_inputs.call_args_list,
            )
            self.assertEqual(
                [mock.call(source, sources), mock.call(source, sources)],
                compile_additions.call_args_list,
            )
            self.assertEqual(additions, plan.additions)

            changed = dataclasses.replace(
                additions,
                input_sha256={**additions.input_sha256, "drift": "d" * 64},
            )
            with (
                mock.patch.object(
                    module.source_io, "load_sealed_source_workspace",
                    side_effect=(source, source),
                ),
                mock.patch.object(
                    module.source_io, "load_addition_sources",
                    side_effect=(sources, sources),
                ),
                mock.patch.object(
                    module.package_compile, "compile_additions",
                    side_effect=(additions, changed),
                ),
                mock.patch.object(module, "_git_head", return_value="c" * 40),
            ):
                with self.assertRaisesRegex(contract.PackageAssemblyError, "changed"):
                    module._compile_fixed_plan(root)

    def test_reviewed_drop_runtime_returns_eligible_read_only_dry_run(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            target = root / "work" / "character_packs" / workspace.WORKSPACE_NAME
            target.parent.mkdir(parents=True)
            source = source_package()
            additions = package_compile.compile_additions(
                source, compile_sources()
            )
            plan = module.AssemblyPlan(source, additions, "c" * 40)
            with (
                mock.patch.object(module, "TOOL_ROOT", root),
                mock.patch.object(module, "_compile_fixed_plan", return_value=plan),
            ):
                report = module.run(module.parse_args([]))
                self.assertEqual(105, report["payload_count"])
                self.assertEqual(39, report["table_claim_count"])
                self.assertTrue(report["apply_ready"])
                self.assertTrue(report["drop_source_sync_closed"])
                self.assertFalse(report["writes_live"])
                self.assertEqual(
                    [contract.ITEM_SHEET_LOGICAL, contract.ITEM_ATLAS_LOGICAL],
                    [
                        item["logical_path"]
                        for item in report["accepted_asset_replacements"]
                    ],
                )
                self.assertFalse(target.exists())

    def test_eligible_apply_uses_only_fixed_fresh_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            target = root / "work" / "character_packs" / workspace.WORKSPACE_NAME
            target.parent.mkdir(parents=True)
            fixtures = package_fixtures.AbyssGachaPackageContractTests()
            source = fixtures._source()
            additions = fixtures._bundle()
            plan = module.AssemblyPlan(source, additions, "c" * 40)
            image = contract.build_package_image(
                source, additions, generator_git_head="c" * 40
            )
            with (
                mock.patch.object(module, "TOOL_ROOT", root),
                mock.patch.object(module, "_compile_fixed_plan", return_value=plan),
                mock.patch.object(
                    module.workspace_io, "execute_fresh_workspace",
                    return_value={"apply": True},
                ) as execute,
            ):
                self.assertEqual(
                    {"apply": True},
                    module.run(module.parse_args([
                        "--apply", "--confirm", contract.CONFIRMATION,
                    ])),
                )
            execute.assert_called_once_with(
                target,
                image,
                apply=True,
                confirmation=contract.CONFIRMATION,
            )


if __name__ == "__main__":
    unittest.main()
