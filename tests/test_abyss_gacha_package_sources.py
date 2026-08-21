#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only sealed-source and stable-input tests for replacement assembly."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import wf_abyss_gacha_package_sources as module
import wf_character_workspace as workspace_module
from tests.summer_thunder_package_fixtures import complete_image
from wf_summer_thunder_package_contract import PACKAGE_ID
from wf_summer_thunder_package_evidence import source_lock_evidence_bytes


class SealedSourceTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        target = root / PACKAGE_ID
        image = complete_image(accepted_skill=True)
        (target / "package").mkdir(parents=True)
        (target / "evidence").mkdir()
        (target / "workspace.json").write_text(json.dumps({
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "template_character_id": 231001,
            "character_id": 139998,
            "code_name": PACKAGE_ID,
            "package_dir": "package",
        }), encoding="utf-8")
        for root_name, files in image.roots.items():
            for logical, raw in files.items():
                path = target / "package" / "roots" / root_name / Path(
                    *logical.split("/")
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        (target / "package" / "manifest.json").write_text(
            json.dumps(image.manifest, ensure_ascii=False), encoding="utf-8"
        )
        (target / "evidence" / "package-source-locks.json").write_bytes(
            source_lock_evidence_bytes(image.source_report["source_locks"])
        )
        workspace_module.seal_workspace(target)
        return target

    def test_loads_exact_sealed_83_payload_source_without_persisting_status(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            workspace = self._workspace(Path(temporary_name))
            status_path = workspace / "evidence" / "status.json"
            status_before = status_path.read_bytes()

            source = module.load_sealed_source_workspace(workspace)

            self.assertEqual(83, sum(len(files) for files in source.roots.values()))
            self.assertEqual(22, len(source.manifest["tables"]))
            self.assertEqual("1.0.0", source.manifest["package_version"])
            self.assertTrue(source.package_acceptance["package_manifest_eligible"])
            self.assertTrue(source.skill_follow_gate["package_manifest_eligible"])
            self.assertEqual(status_before, status_path.read_bytes())

    def test_rejects_unsealed_or_source_lock_tampered_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_name:
            workspace = self._workspace(Path(temporary_name))
            manifest_path = workspace / "package" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["qa"]["release_ready"] = False
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(module.PackageAssemblyError, "sealed"):
                module.load_sealed_source_workspace(workspace)

        with tempfile.TemporaryDirectory() as temporary_name:
            workspace = self._workspace(Path(temporary_name))
            evidence = workspace / "evidence" / "package-source-locks.json"
            evidence.write_bytes(evidence.read_bytes() + b" ")
            with self.assertRaisesRegex(module.PackageAssemblyError, "source-lock"):
                module.load_sealed_source_workspace(workspace)


if __name__ == "__main__":
    unittest.main()
