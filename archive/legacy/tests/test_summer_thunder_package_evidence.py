#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-lock evidence and manifest binding tests."""

from __future__ import annotations

import copy
import hashlib
import unittest

import wf_summer_thunder_package_evidence as module
from wf_summer_thunder_package_contract import PackageAssemblyError


def _source_locks() -> dict:
    return {
        "schema_version": 1,
        "artifacts": [],
        "authoring_table_sha256": {},
        "clean_release": {
            "client_base": "1.4.346",
            "table_count": 18,
            "writes_live": False,
        },
        "rebased_authoring_table_sha256": {},
        "server_shadow_sha256": {},
        "voice_source_sha256": {},
        "pure_output_sha256": {},
        "package_acceptance": {
            "package_manifest_eligible": True,
            "writes_live": False,
        },
        "skill_follow_gate": {
            "status": "pending_exact_contract",
            "package_manifest_eligible": False,
            "writes_live": False,
        },
    }


class SourceLockEvidenceTests(unittest.TestCase):
    def test_complete_report_bytes_are_the_manifest_bound_evidence(self):
        locks = _source_locks()
        evidence = module.source_lock_evidence_bytes(locks)
        digest = hashlib.sha256(evidence).hexdigest()
        manifest = {"snapshot": {"source_locks_sha256": digest}}
        report = {"source_locks": locks, "source_locks_sha256": digest}
        self.assertEqual(evidence, module.validate_source_lock_binding(manifest, report))
        self.assertTrue(evidence.endswith(b"\n"))

    def test_missing_full_report_section_or_manifest_digest_drift_is_rejected(self):
        locks = _source_locks()
        del locks["clean_release"]
        with self.assertRaisesRegex(PackageAssemblyError, "source-lock sections"):
            module.source_lock_evidence_bytes(locks)

        locks = _source_locks()
        evidence = module.source_lock_evidence_bytes(locks)
        digest = hashlib.sha256(evidence).hexdigest()
        manifest = {"snapshot": {"source_locks_sha256": "0" * 64}}
        report = {"source_locks": locks, "source_locks_sha256": digest}
        with self.assertRaisesRegex(PackageAssemblyError, "manifest binding"):
            module.validate_source_lock_binding(manifest, report)

    def test_package_acceptance_cannot_be_replaced_by_producer_writes_live_flag(self):
        locks = _source_locks()
        locks["package_acceptance"] = {
            "package_manifest_eligible": False,
            "writes_live": False,
        }
        with self.assertRaisesRegex(PackageAssemblyError, "package acceptance"):
            module.source_lock_evidence_bytes(locks)

        locks = _source_locks()
        drifted = copy.deepcopy(locks)
        drifted["clean_release"]["table_count"] = 17
        with self.assertRaisesRegex(PackageAssemblyError, "release-base evidence"):
            module.source_lock_evidence_bytes(drifted)


if __name__ == "__main__":
    unittest.main()
