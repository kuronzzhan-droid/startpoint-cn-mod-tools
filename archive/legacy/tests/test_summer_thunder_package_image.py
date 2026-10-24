#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unbypassable in-memory package image audit tests."""

from __future__ import annotations

import copy
import unittest

import wf_summer_thunder_package_image as module
from tests.summer_thunder_package_fixtures import complete_image
from wf_summer_thunder_package_contract import PackageAssemblyError, PackageImage


class PackageImageAuditTests(unittest.TestCase):
    def test_exact_83_22_37_and_source_locks_pass_integrity_but_skill_holds_apply(self):
        report = module.audit_package_image(complete_image())
        self.assertEqual(83, report["payload_count"])
        self.assertEqual(22, report["table_claim_count"])
        self.assertEqual(37, report["required_assets_present"])
        self.assertTrue(report["integrity_ready"])
        self.assertFalse(report["apply_ready"])
        self.assertRegex(report["blockers"][0], "skill-follow exact contract")
        with self.assertRaisesRegex(PackageAssemblyError, "skill-follow"):
            module.require_apply_ready(complete_image())

    def test_payload_manifest_or_source_lock_drift_is_rejected(self):
        image = complete_image()
        roots = {name: dict(files) for name, files in image.roots.items()}
        roots["common"].pop("master/ability/ability.orderedmap")
        with self.assertRaisesRegex(PackageAssemblyError, "manifest root entries"):
            module.audit_package_image(PackageImage(roots, image.manifest, image.source_report))

        image = complete_image()
        manifest = copy.deepcopy(image.manifest)
        manifest["roots"]["medium"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(PackageAssemblyError, "manifest root entries"):
            module.audit_package_image(PackageImage(image.roots, manifest, image.source_report))

        image = complete_image()
        source_report = copy.deepcopy(image.source_report)
        source_report["source_locks_sha256"] = "0" * 64
        with self.assertRaisesRegex(PackageAssemblyError, "manifest binding"):
            module.audit_package_image(PackageImage(image.roots, image.manifest, source_report))

    def test_generic_skill_eligible_claim_is_not_an_apply_bypass(self):
        image = complete_image(
            skill_follow_gate={
                "status": "accepted",
                "package_manifest_eligible": True,
                "writes_live": False,
            }
        )
        with self.assertRaisesRegex(PackageAssemblyError, "skill-follow exact contract"):
            module.audit_package_image(image)

    def test_apply_ready_requires_gate_recomputed_from_packaged_payloads(self):
        accepted = complete_image(accepted_skill=True)
        report = module.audit_package_image(accepted)
        self.assertTrue(report["apply_ready"])
        self.assertEqual([], report["blockers"])

        forged = complete_image(
            skill_follow_gate=copy.deepcopy(accepted.source_report["skill_follow_gate"])
        )
        with self.assertRaisesRegex(PackageAssemblyError, "payload|AMF3"):
            module.audit_package_image(forged)


if __name__ == "__main__":
    unittest.main()
