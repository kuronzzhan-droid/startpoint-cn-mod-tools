#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventory, claims, references, and manifest tests."""

from __future__ import annotations

import hashlib
import unittest

import wf_character_pack as character_pack
import wf_character_requirements as requirements
import wf_summer_thunder_package_assemble as module
from tests.summer_thunder_package_fixtures import (
    complete_claims,
    complete_roots,
    required_roots,
)


class ManifestContractTests(unittest.TestCase):
    def test_static_gacha_page_png_uses_medium_root(self):
        self.assertEqual(
            "medium",
            module.expected_client_root("dynamic/gacha_banner/example.png"),
        )
        self.assertEqual(
            "common",
            module.expected_client_root("dynamic/gacha_list_banner/example"),
        )

    def test_exact_37_required_assets_and_root_channels(self):
        roots = required_roots()
        report = module.validate_root_contract(roots)
        self.assertEqual(37, report["required_present"])
        self.assertEqual([], report["missing_required"])

        logical = next(iter(roots["medium"]))
        roots["common"][logical] = roots["medium"].pop(logical)
        with self.assertRaisesRegex(module.PackageAssemblyError, "root channel"):
            module.validate_root_contract(roots)

    def test_story_words_and_login_are_rejected(self):
        roots = required_roots()
        roots["common"][f"character/{module.CODE_NAME}/voice/words/line.mp3"] = b"x"
        with self.assertRaisesRegex(module.PackageAssemblyError, "forbidden segment"):
            module.validate_root_contract(roots)

    def test_complete_production_inventory_is_exact_83_with_22_claims(self):
        roots = complete_roots()
        report = module.validate_production_contract(roots, complete_claims())
        self.assertEqual(
            {"common": 52, "medium": 25, "android": 2, "server": 4},
            report["root_counts"],
        )
        self.assertEqual(83, report["payload_count"])
        self.assertEqual(22, report["table_claim_count"])
        self.assertFalse(report["custom_power_flip_assets"])

        roots["common"].pop(
            "battle/common/unique_condition/"
            "unique_cnmod_thunder_dragon_ascendant_amp.png"
        )
        with self.assertRaisesRegex(module.PackageAssemblyError, "inventory mismatch"):
            module.validate_production_contract(roots, complete_claims())

    def test_master_reference_closure_requires_all_owned_dependencies(self):
        roots = complete_roots()
        references = (
            requirements.MasterAssetReference(
                "unique_condition_icon",
                "battle/common/unique_condition/"
                "unique_cnmod_thunder_dragon_ascendant_amp",
                "unique:139998",
            ),
            requirements.MasterAssetReference(
                "unique_condition_id", "139998", "ability:1399981"
            ),
            requirements.MasterAssetReference(
                "skill_program",
                "battle/action/skill/action/rare5/"
                "cnmod_thunder_dragon_ascendant$"
                "cnmod_thunder_dragon_ascendant_1",
                "action:1",
            ),
            requirements.MasterAssetReference(
                "skill_effect",
                "battle/effect/skill_unique/"
                "cnmod_thunder_dragon_ascendant/fan_lightning/"
                "fan_lightning_wave",
                "dsl:1",
            ),
        )
        report = module.validate_reference_closure(
            roots, references, package_condition_ids=("139998",)
        )
        self.assertEqual([], report["missing"])

        roots["common"].pop(
            "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/"
            "fan_lightning/fan_lightning_wave.timeline.amf3.deflate"
        )
        with self.assertRaisesRegex(module.PackageAssemblyError, "reference closure"):
            module.validate_reference_closure(
                roots, references, package_condition_ids=("139998",)
            )

    def test_manifest_entries_are_exact_hashes_and_draft_is_unsealed(self):
        roots = required_roots()
        manifest = module.build_manifest(
            roots=roots,
            table_claims=[],
            package_version="1.0.0",
            requires_client_base="1.4.346",
            required_capabilities=("content.sync@1",),
            generator_git_head="b" * 40,
            source_locks_sha256="c" * 64,
        )
        self.assertFalse(manifest["qa"]["release_ready"])
        self.assertEqual("", manifest["qa"]["workspace_input_sha256"])
        entry = manifest["roots"]["medium"][0]
        payload = roots["medium"][entry["logical_path"]]
        self.assertEqual(len(payload), entry["size"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])

    def test_manifest_builder_accepts_only_explicit_server_extensions(self):
        roots = required_roots()
        extension = "gacha.json"
        roots["server"][extension] = b'{"990001":{}}'
        with self.assertRaisesRegex(module.PackageAssemblyError, "root channel"):
            module.build_manifest(
                roots=roots,
                table_claims=[],
                package_version="1.1.0",
                requires_client_base="1.4.347",
                required_capabilities=("content.sync@1",),
                generator_git_head="b" * 40,
                source_locks_sha256="c" * 64,
            )

        manifest = module.build_manifest(
            roots=roots,
            table_claims=[],
            package_version="1.1.0",
            requires_client_base="1.4.347",
            required_capabilities=("content.sync@1",),
            generator_git_head="b" * 40,
            source_locks_sha256="c" * 64,
            server_logicals=(*character_pack.SERVER_LOGICAL_PATHS, extension),
        )

        self.assertEqual(
            extension,
            next(
                entry["logical_path"] for entry in manifest["roots"]["server"]
                if entry["logical_path"] == extension
            ),
        )


if __name__ == "__main__":
    unittest.main()
