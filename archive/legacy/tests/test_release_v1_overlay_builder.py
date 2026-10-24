from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import wf_character_workspace
from wf_release_v1.errors import ReleaseError
from wf_release_v1.patch_overlay_source import inspect_patch_overlay_chain
from tests.release_v1_fixtures import make_sealed_character_workspace


class OverlayBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = make_sealed_character_workspace(self.root / "workspaces")
        current = wf_character_workspace.load_workspace(self.workspace)
        manifest_path = current.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        logical = "platform/android-only.bin"
        raw = b"android-only"
        path = current.package_dir / "roots" / "android" / logical
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        import hashlib
        manifest["roots"]["android"].append({
            "logical_path": logical,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        })
        manifest["qa"]["workspace_input_sha256"] = ""
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        wf_character_workspace.seal_workspace(current)

    def test_builds_deterministic_verified_overlay_from_sealed_workspace(self) -> None:
        from wf_release_v1.overlay_builder import build_character_overlay

        first = self.root / "first.zip"
        second = self.root / "second.zip"
        receipt = build_character_overlay(
            self.workspace, "1.4.324", "1.4.347", first
        )
        build_character_overlay(self.workspace, "1.4.324", "1.4.347", second)

        self.assertEqual(first.read_bytes(), second.read_bytes())
        chain, tail = inspect_patch_overlay_chain([first])
        self.assertEqual("1.4.347", tail)
        self.assertEqual("1.4.324", chain[0].from_version)
        self.assertEqual(39, receipt.payload_file_count)
        with zipfile.ZipFile(first) as outer:
            manifest = json.loads(outer.read("patch-manifest.json"))
            self.assertEqual(["android", "common", "medium"], [
                item["layer"] for item in manifest["archives"]
            ])
            for item in manifest["archives"]:
                with zipfile.ZipFile(outer.open(item["relativePath"])) as inner:
                    self.assertTrue(all(name.startswith("production/") for name in inner.namelist()))

    def test_rejects_unsealed_drift_unsafe_versions_and_existing_output(self) -> None:
        from wf_release_v1.overlay_builder import build_character_overlay

        output = self.root / "existing.zip"
        output.write_bytes(b"keep")
        with self.assertRaisesRegex(ReleaseError, "new absolute path"):
            build_character_overlay(self.workspace, "1.4.324", "1.4.347", output)
        self.assertEqual(b"keep", output.read_bytes())

        with self.assertRaisesRegex(ReleaseError, "version"):
            build_character_overlay(
                self.workspace, "../1.4.324", "1.4.347", self.root / "bad-version.zip"
            )

        current = wf_character_workspace.load_workspace(self.workspace)
        asset = next((current.package_dir / "roots/medium").rglob("*.png"))
        asset.write_bytes(asset.read_bytes() + b"drift")
        with self.assertRaisesRegex(ReleaseError, "sealed"):
            build_character_overlay(
                self.workspace, "1.4.324", "1.4.347", self.root / "drift.zip"
            )
        self.assertFalse((self.root / "drift.zip").exists())

    def test_cli_builds_without_leaking_output_path(self) -> None:
        output = self.root / "cli.zip"
        result = subprocess.run(
            [
                sys.executable, "-X", "utf8", "-m", "wf_release_v1",
                "build-overlay", "--workspace", str(self.workspace),
                "--from-version", "1.4.324", "--target-version", "1.4.347",
                "--output", str(output), "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
        self.assertEqual(b"", result.stderr)
        self.assertNotIn(str(self.root), result.stdout.decode("utf-8"))
        self.assertTrue(json.loads(result.stdout)["verified"])
        self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
