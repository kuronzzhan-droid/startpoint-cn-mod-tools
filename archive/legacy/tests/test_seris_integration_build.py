# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = REPO_ROOT / "work" / "seris_v2" / "integration" / "build_candidate.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_source_package(root: Path) -> Path:
    source = root / "installed-package"
    payloads = {
        "manifest.json": b'{"package_id":"seris_dragon_king"}\n',
        "roots/common/character/seris_dragon_king/pixelart/sprite_sheet.png": (
            bytes.fromhex("89504e470d0a1a0a") + b"pixel-bytes"
        ),
        "roots/common/master/character/character.orderedmap": b"table\x00bytes",
        "roots/server/cdndata/character.json": "{\"129999\":\"赛瑞斯\"}\n".encode("utf-8"),
        "qa/empty.bin": b"",
    }
    for relative, raw in payloads.items():
        path = source / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return source


class TestSerisIntegrationBuild(unittest.TestCase):
    def _module(self):
        if not BUILD_SCRIPT.is_file():
            self.fail(f"Phase 2 build script is missing: {BUILD_SCRIPT}")
        spec = importlib.util.spec_from_file_location("seris_integration_build", BUILD_SCRIPT)
        if spec is None or spec.loader is None:
            self.fail(f"cannot load build script: {BUILD_SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_two_clean_builds_have_identical_path_sha256_and_exact_clone(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_package(root)
            integration = root / "integration"
            output = integration / "seris_dragon_king"
            evidence = integration / "evidence" / "reproducibility.json"

            report = module.build_candidate(
                source,
                output,
                evidence,
                allowed_output_root=integration,
            )

            persisted = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertTrue(report["reproducible"])
            self.assertTrue(report["source_unchanged"])
            self.assertEqual(report, persisted)
            self.assertEqual(
                report["build_a"]["path_sha256"],
                report["build_b"]["path_sha256"],
            )
            self.assertEqual(
                report["build_a"]["path_sha256"],
                report["final"]["path_sha256"],
            )
            self.assertEqual(5, report["file_count"])
            for relative, digest in report["source"]["path_sha256"].items():
                self.assertEqual(digest, _sha256(output / Path(*relative.split("/"))))
            self.assertTrue(evidence.read_bytes().endswith(b"\n"))

    def test_rebuild_removes_stale_output_without_touching_source(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_package(root)
            integration = root / "integration"
            output = integration / "seris_dragon_king"
            evidence = integration / "evidence.json"
            source_manifest_before = _sha256(source / "manifest.json")

            module.build_candidate(
                source, output, evidence, allowed_output_root=integration
            )
            (output / "stale.tmp").write_bytes(b"must disappear")
            report = module.build_candidate(
                source, output, evidence, allowed_output_root=integration
            )

            self.assertFalse((output / "stale.tmp").exists())
            self.assertEqual(source_manifest_before, _sha256(source / "manifest.json"))
            self.assertTrue(report["source_unchanged"])

    def test_rejects_output_outside_allowed_integration_root(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = _write_source_package(root)
            integration = root / "integration"
            outside = root / "outside"

            with self.assertRaisesRegex(module.BuildError, "outside integration root"):
                module.build_candidate(
                    source,
                    outside,
                    integration / "evidence.json",
                    allowed_output_root=integration,
                )
            self.assertFalse(outside.exists())

    def test_rejects_source_without_manifest(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "installed-package"
            source.mkdir()
            integration = root / "integration"

            with self.assertRaisesRegex(module.BuildError, "manifest.json"):
                module.build_candidate(
                    source,
                    integration / "seris_dragon_king",
                    integration / "evidence.json",
                    allowed_output_root=integration,
                )


if __name__ == "__main__":
    unittest.main()
