#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sealed-source and whole-image tests for thunder-dragon hotfix 1.1.1."""

from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path

try:
    import wf_thunder_hotfix_package as package
    import wf_thunder_hotfix_package_sources as sources
except ImportError:
    package = None
    sources = None


TOOL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_WORKSPACE = (
    TOOL_ROOT / "work" / "character_packs"
    / "cnmod_thunder_dragon_ascendant_abyss_gacha"
)
BUILD_ROOT = (
    TOOL_ROOT / "work" / "builds" / "cnmod_thunder_dragon_ascendant"
)


@unittest.skipUnless(
    SOURCE_WORKSPACE.exists() and BUILD_ROOT.exists(),
    "local sealed 1.1.0 production inputs are unavailable",
)
class ThunderHotfixPackageTests(unittest.TestCase):
    def _require_modules(self):
        if package is None or sources is None:
            self.fail("thunder hotfix package modules are missing")

    def _compile(self):
        self._require_modules()
        source = sources.load_sealed_source_workspace(SOURCE_WORKSPACE)
        donor = sources.load_locked_donor_template(BUILD_ROOT)
        return source, package.compile_hotfix_package(
            source, donor, generator_git_head="a" * 40
        )

    def test_builds_full_111_replacement_with_only_six_changed_payloads(self):
        source, image = self._compile()
        audit = package.audit_hotfix_package(image)
        self.assertEqual("1.1.1", image.manifest["package_version"])
        self.assertEqual("1.4.348", image.manifest["requires_client_base"])
        self.assertEqual(105, audit["payload_count"])
        self.assertEqual(39, audit["table_claim_count"])
        self.assertEqual({
            "common": 67, "medium": 25, "android": 2, "server": 11,
        }, audit["root_counts"])
        self.assertEqual(6, audit["changed_payload_count"])
        self.assertEqual(
            list(package.CHANGED_PAYLOADS), audit["changed_payloads"]
        )
        self.assertEqual(source.manifest["tables"], image.manifest["tables"])
        self.assertEqual(
            list(package.CURRENT_SHARED_ASSET_BASELINE),
            image.manifest["snapshot"]["accepted_asset_replacements"],
        )
        for root in package.ROOT_NAMES:
            for logical, raw in source.roots[root].items():
                if (root, logical) not in package.CHANGED_PAYLOADS:
                    self.assertEqual(raw, image.roots[root][logical])

    def test_rejects_source_payload_and_donor_drift(self):
        self._require_modules()
        source = sources.load_sealed_source_workspace(SOURCE_WORKSPACE)
        donor = sources.load_locked_donor_template(BUILD_ROOT)
        bad_roots = {
            root: dict(files) for root, files in source.roots.items()
        }
        logical = package.CHANGED_PAYLOADS[0][1]
        bad_roots["common"][logical] += b"drift"
        drifted = source.__class__(
            roots=bad_roots,
            manifest=source.manifest,
            source_locks=source.source_locks,
            workspace_input_sha256=source.workspace_input_sha256,
            manifest_sha256=source.manifest_sha256,
            evidence_sha256=source.evidence_sha256,
        )
        with self.assertRaisesRegex(package.PackageAssemblyError, "source payload"):
            package.compile_hotfix_package(
                drifted, donor, generator_git_head="a" * 40
            )

        donor_files = dict(donor.files)
        first = next(iter(donor_files))
        donor_files[first] += b"drift"
        bad_donor = donor.__class__(
            files=donor_files,
            report_sha256=donor.report_sha256,
            source_store=donor.source_store,
            input_sha256=donor.input_sha256,
        )
        with self.assertRaisesRegex(package.PackageAssemblyError, "donor"):
            package.compile_hotfix_package(
                source, bad_donor, generator_git_head="a" * 40
            )

    def test_audit_rejects_relabelled_extra_change(self):
        _source, image = self._compile()
        roots = {root: dict(files) for root, files in image.roots.items()}
        logical = "character/cnmod_thunder_dragon_ascendant/ui/square_0.png"
        roots["medium"][logical] += b"unexpected"
        mutated = image.__class__(roots, image.manifest, image.source_report)
        with self.assertRaisesRegex(
            package.PackageAssemblyError, "payload binding|unexpected change"
        ):
            package.audit_hotfix_package(mutated)


if __name__ == "__main__":
    unittest.main()
