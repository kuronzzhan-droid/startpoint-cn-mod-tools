#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact replacement-package inventory and source-binding tests."""

from __future__ import annotations

import copy
import hashlib
import unittest

import wf_abyss_gacha_package_contract as module
from tests.summer_thunder_package_fixtures import complete_image


class AbyssGachaPackageContractTests(unittest.TestCase):
    def _source(self) -> module.SealedSourcePackage:
        image = complete_image(accepted_skill=True)
        manifest = copy.deepcopy(image.manifest)
        manifest["qa"].update({
            "release_ready": True,
            "workspace_input_sha256": "a" * 64,
        })
        return module.SealedSourcePackage(
            roots=image.roots,
            manifest=manifest,
            workspace_input_sha256="a" * 64,
            source_locks_sha256="b" * 64,
            package_acceptance={
                "package_manifest_eligible": True,
                "writes_live": False,
            },
            skill_follow_gate={
                "status": "accepted_exact_runtime_follow_contract",
                "package_manifest_eligible": True,
                "writes_live": False,
            },
        )

    def _bundle(self) -> module.AdditionBundle:
        roots = {name: {} for name in module.ROOT_NAMES}
        for root, logical in module.NEW_PATHS:
            roots[root][logical] = f"new:{root}:{logical}".encode()
        sheet_before_sha = hashlib.sha256(b"base347-sheet").hexdigest()
        atlas_before_sha = hashlib.sha256(b"base347-atlas").hexdigest()
        ticket_report = {
            "writes_live": False,
            "shared_asset_replacements": {
                module.ITEM_SHEET_LOGICAL: {
                    "before_sha256": sheet_before_sha,
                    "before_size": len(b"base347-sheet"),
                },
                module.ITEM_ATLAS_LOGICAL: {
                    "before_sha256": atlas_before_sha,
                    "before_size": len(b"base347-atlas"),
                },
            },
            "shared_asset_preservation": {
                "sheet_prefix": {
                    "before_dimensions": [1024, 2048],
                    "after_dimensions": [1024, 2070],
                    "before_rgba_sha256": "1" * 64,
                    "after_prefix_rgba_sha256": "1" * 64,
                },
                "atlas_prefix": {
                    "before_entry_count": 100,
                    "after_entry_count": 102,
                    "before_entries_sha256": "2" * 64,
                    "after_prefix_entries_sha256": "2" * 64,
                },
            },
        }
        return module.AdditionBundle(
            roots=roots,
            table_claims=tuple(module.expected_new_claims()),
            input_sha256={
                "fixture": hashlib.sha256(b"fixture").hexdigest(),
                f"tickets:{module.ITEM_SHEET_LOGICAL}": sheet_before_sha,
                f"tickets:{module.ITEM_ATLAS_LOGICAL}": atlas_before_sha,
            },
            component_reports={
                **{
                    name: {"writes_live": False}
                    for name in ("gacha", "shop", "banners")
                },
                "tickets": ticket_report,
                "drop": {
                    "writes_live": False,
                    "runtime_source_sync": copy.deepcopy(
                        module.DROP_RUNTIME_SOURCE_SYNC
                    ),
                },
            },
            acceptance={
                "all_references_closed": True,
                "eight_character_closure": True,
                "ticket_contract_closed": True,
                "shop_contract_closed": True,
                "drop_contract_closed": True,
                "drop_source_sync_closed": True,
                "art_contract_closed": True,
                "unresolved_art_payloads": [],
                "package_manifest_eligible": True,
                "writes_live": False,
            },
        )

    def test_builds_exact_derived_payload_and_claim_replacement_without_touching_old_bytes(self):
        source = self._source()
        image = module.build_package_image(
            source,
            self._bundle(),
            generator_git_head="c" * 40,
        )

        audit = module.audit_package_image(image)
        self.assertEqual(105, audit["payload_count"])
        self.assertEqual(39, audit["table_claim_count"])
        self.assertEqual(
            {"common": 66, "medium": 26, "android": 2, "server": 11},
            audit["root_counts"],
        )
        self.assertEqual(83, audit["old_payload_exact_count"])
        self.assertEqual(22, audit["new_payload_exact_count"])
        self.assertTrue(audit["old_payloads_byte_exact"])
        self.assertEqual(
            image.manifest["snapshot"]["accepted_asset_replacements"],
            audit["accepted_asset_replacements"],
        )
        self.assertEqual("1.1.0", image.manifest["package_version"])
        self.assertEqual("1.4.347", image.manifest["requires_client_base"])
        self.assertEqual(
            source.manifest["tables"], image.manifest["tables"][:22]
        )
        for root in module.ROOT_NAMES:
            for logical, raw in source.roots[root].items():
                self.assertEqual(raw, image.roots[root][logical])
        self.assertFalse(image.source_report["writes_live"])
        self.assertFalse(image.source_report["formal_workspace_written"])
        self.assertEqual([
            {
                "root": "common",
                "logical_path": module.ITEM_SHEET_LOGICAL,
                "before_sha256": hashlib.sha256(b"base347-sheet").hexdigest(),
                "before_size": len(b"base347-sheet"),
            },
            {
                "root": "common",
                "logical_path": module.ITEM_ATLAS_LOGICAL,
                "before_sha256": hashlib.sha256(b"base347-atlas").hexdigest(),
                "before_size": len(b"base347-atlas"),
            },
        ], image.manifest["snapshot"]["accepted_asset_replacements"])

    def test_rejects_unbound_or_non_preserving_shared_asset_acceptance(self):
        source = self._source()
        cases = {}
        missing_path = self._bundle()
        missing_reports = copy.deepcopy(missing_path.component_reports)
        missing_reports["tickets"]["shared_asset_replacements"].pop(
            module.ITEM_ATLAS_LOGICAL
        )
        cases["exact paths"] = (missing_path, missing_reports)

        changed_prefix = self._bundle()
        changed_reports = copy.deepcopy(changed_prefix.component_reports)
        changed_reports["tickets"]["shared_asset_preservation"][
            "sheet_prefix"
        ]["after_prefix_rgba_sha256"] = "3" * 64
        cases["prefix preservation"] = (changed_prefix, changed_reports)

        unbound = self._bundle()
        unbound_reports = copy.deepcopy(unbound.component_reports)
        unbound_reports["tickets"]["shared_asset_replacements"][
            module.ITEM_SHEET_LOGICAL
        ]["before_sha256"] = "4" * 64
        cases["input hash binding"] = (unbound, unbound_reports)

        for message, (bundle, reports) in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    module.PackageAssemblyError, message
                ):
                    module.build_package_image(
                        source,
                        module.AdditionBundle(
                            roots=bundle.roots,
                            table_claims=bundle.table_claims,
                            input_sha256=bundle.input_sha256,
                            component_reports=reports,
                            acceptance=bundle.acceptance,
                        ),
                        generator_git_head="c" * 40,
                    )

    def test_rejects_unreviewed_drop_runtime_source_sync_evidence(self):
        source = self._source()
        bundle = self._bundle()
        reports = copy.deepcopy(bundle.component_reports)
        reports["drop"]["runtime_source_sync"]["converter_version"] = 2

        with self.assertRaisesRegex(
            module.PackageAssemblyError, "runtime source sync"
        ):
            module.build_package_image(
                source,
                module.AdditionBundle(
                    roots=bundle.roots,
                    table_claims=bundle.table_claims,
                    input_sha256=bundle.input_sha256,
                    component_reports=reports,
                    acceptance=bundle.acceptance,
                ),
                generator_git_head="c" * 40,
            )

    def test_requires_the_exact_new_path_and_claim_sets(self):
        source = self._source()
        missing = self._bundle()
        roots = {name: dict(files) for name, files in missing.roots.items()}
        root, logical = module.NEW_PATHS[0]
        roots[root].pop(logical)
        with self.assertRaisesRegex(module.PackageAssemblyError, "new payload set"):
            module.build_package_image(
                source,
                module.AdditionBundle(
                    roots=roots,
                    table_claims=missing.table_claims,
                    input_sha256=missing.input_sha256,
                    component_reports=missing.component_reports,
                    acceptance=missing.acceptance,
                ),
                generator_git_head="c" * 40,
            )

        wrong_claims = list(missing.table_claims)
        wrong_claims[-1] = {**wrong_claims[-1], "outer_keys": ["700098"]}
        with self.assertRaisesRegex(module.PackageAssemblyError, "new table claims"):
            module.build_package_image(
                source,
                module.AdditionBundle(
                    roots=missing.roots,
                    table_claims=tuple(wrong_claims),
                    input_sha256=missing.input_sha256,
                    component_reports=missing.component_reports,
                    acceptance=missing.acceptance,
                ),
                generator_git_head="c" * 40,
            )

    def test_rejects_exact_and_windows_equivalent_old_path_clobber(self):
        source = self._source()
        bundle = self._bundle()
        old_logical = next(iter(source.roots["common"]))
        for conflicting in (old_logical, old_logical.upper()):
            with self.subTest(conflicting=conflicting):
                roots = {name: dict(files) for name, files in bundle.roots.items()}
                root, removed = module.NEW_PATHS[0]
                roots[root].pop(removed)
                roots["common"][conflicting] = b"clobber"
                with self.assertRaisesRegex(
                    module.PackageAssemblyError, "old payload"
                ):
                    module.build_package_image(
                        source,
                        module.AdditionBundle(
                            roots=roots,
                            table_claims=bundle.table_claims,
                            input_sha256=bundle.input_sha256,
                            component_reports=bundle.component_reports,
                            acceptance=bundle.acceptance,
                        ),
                        generator_git_head="c" * 40,
                    )

    def test_source_evidence_is_hash_bound_and_acceptance_is_not_optional(self):
        source = self._source()
        bundle = self._bundle()
        image = module.build_package_image(
            source, bundle, generator_git_head="c" * 40
        )
        tampered_report = copy.deepcopy(image.source_report)
        tampered_report["source_locks"]["input_sha256"]["fixture"] = "d" * 64
        tampered = module.PackageImage(
            image.roots, image.manifest, tampered_report
        )
        with self.assertRaisesRegex(module.PackageAssemblyError, "source-lock"):
            module.audit_package_image(tampered)

        tampered_manifest = copy.deepcopy(image.manifest)
        tampered_manifest["snapshot"]["accepted_asset_replacements"][0][
            "before_size"
        ] += 1
        with self.assertRaisesRegex(
            module.PackageAssemblyError, "accepted asset replacement"
        ):
            module.audit_package_image(module.PackageImage(
                image.roots, tampered_manifest, image.source_report
            ))

        rejected = copy.deepcopy(bundle.acceptance)
        rejected["shop_contract_closed"] = False
        with self.assertRaisesRegex(module.PackageAssemblyError, "acceptance"):
            module.build_package_image(
                source,
                module.AdditionBundle(
                    roots=bundle.roots,
                    table_claims=bundle.table_claims,
                    input_sha256=bundle.input_sha256,
                    component_reports=bundle.component_reports,
                    acceptance=rejected,
                ),
                generator_git_head="c" * 40,
            )


if __name__ == "__main__":
    unittest.main()
