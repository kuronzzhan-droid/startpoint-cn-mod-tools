"""Read-only sealed character source and Patch Overlay contract tests."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import wf_character_workspace
from wf_release_v1.errors import ReleaseError
from tests.release_v1_fixtures import (
    corrupt_zip_member_crc,
    make_patch_overlay,
    make_sealed_character_workspace,
    replace_first_inner_zip,
    rewrite_outer_member_raw_name,
    rewrite_overlay,
)


class CharacterSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = make_sealed_character_workspace(self.root / "workspaces")

    @staticmethod
    def _tree_bytes(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def _overlay(self, from_version: str, target_version: str, *, folder="overlays") -> Path:
        return make_patch_overlay(
            self.root / folder
            / f"worldflipper-overlay-{from_version}-to-{target_version}.zip",
            from_version=from_version,
            target_version=target_version,
        )

    def test_inspects_real_sealed_workspace_and_sorts_one_continuous_chain(self) -> None:
        first = self._overlay("1.4.54", "1.4.55")
        second = self._overlay("1.4.55", "1.4.58")
        before = self._tree_bytes(self.root)

        from wf_release_v1.character_source import inspect_character_source

        source = inspect_character_source(
            workspace=self.workspace,
            overlay_archives=[second, first],
        )

        self.assertEqual("1.4.58", source.cdn_target_version)
        self.assertEqual(64, len(source.workspace_input_sha256))
        self.assertEqual(129999, source.package_manifest["character_id"])
        self.assertEqual(
            [first.name, second.name],
            [item.relative_path for item in source.overlay_files],
        )
        self.assertTrue(all(len(item.manifest_sha256) == 64 for item in source.overlay_files))
        self.assertEqual(before, self._tree_bytes(self.root))

    def test_server_roots_are_seal_evidence_not_first_slice_payload(self) -> None:
        overlay = self._overlay("1.4.54", "1.4.55")

        from wf_release_v1.character_source import inspect_character_source

        source = inspect_character_source(
            workspace=self.workspace,
            overlay_archives=[overlay],
        )

        server_paths = {
            item["logical_path"] for item in source.package_manifest["roots"]["server"]
        }
        self.assertEqual(
            {"character.json", "cdndata/character.json", "cdndata/character_text.json"},
            server_paths,
        )
        self.assertEqual((overlay.name,), tuple(item.relative_path for item in source.overlay_files))
        self.assertFalse(hasattr(source, "server_files"))

    def test_package_manifest_reads_are_deep_caller_isolated(self) -> None:
        overlay = self._overlay("1.4.54", "1.4.55")

        from wf_release_v1.character_source import inspect_character_source

        source = inspect_character_source(
            workspace=self.workspace,
            overlay_archives=[overlay],
        )
        original = copy.deepcopy(source.package_manifest)
        exposed = source.package_manifest
        exposed["caller_only"] = True
        exposed["character_id"] = 1
        exposed["code_name"] = "changed"
        exposed["package_id"] = "changed"
        exposed["roots"]["server"][0]["logical_path"] = "changed.json"
        exposed["roots"]["server"].append({"logical_path": "added.json"})

        self.assertEqual(original, source.package_manifest)
        self.assertIsNot(exposed, source.package_manifest)
        self.assertIsNot(exposed["roots"], source.package_manifest["roots"])
        twin = inspect_character_source(
            workspace=self.workspace,
            overlay_archives=[overlay],
        )
        self.assertEqual(source, twin)
        with self.assertRaises(TypeError):
            hash(source)

    def test_rejects_workspace_that_is_not_the_same_sealed_production_identity(self) -> None:
        manifest_path = self.workspace / "package" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["character_id"] = 139999
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as raised:
            inspect_character_source(
                workspace=self.workspace,
                overlay_archives=[self._overlay("1.4.54", "1.4.55")],
            )

        self.assertEqual("WFREL_CHARACTER_SOURCE_INVALID", raised.exception.code)

    def test_rejects_runtime_test_delivery_even_if_other_qa_fields_claim_ready(self) -> None:
        manifest_path = self.workspace / "package" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["qa"]["delivery_mode"] = "runtime_test"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as raised:
            inspect_character_source(
                workspace=self.workspace,
                overlay_archives=[self._overlay("1.4.54", "1.4.55")],
            )

        self.assertEqual("WFREL_CHARACTER_SOURCE_INVALID", raised.exception.code)

    def test_rejects_workspace_changes_between_read_only_status_checks(self) -> None:
        overlay = self._overlay("1.4.54", "1.4.55")
        real_status = wf_character_workspace.workspace_status
        calls = 0

        def changing_status(workspace, *, persist=True):
            nonlocal calls
            calls += 1
            status = real_status(workspace, persist=persist)
            if calls == 1:
                target = self.workspace / "package" / "roots" / "server" / "character.json"
                target.write_bytes(b'{"changed":true}')
            return status

        from wf_release_v1 import character_source as source_module

        with patch.object(source_module, "workspace_status", side_effect=changing_status):
            with self.assertRaises(ReleaseError) as raised:
                source_module.inspect_character_source(
                    workspace=self.workspace,
                    overlay_archives=[overlay],
                )

        self.assertEqual("WFREL_CHARACTER_SOURCE_CHANGED", raised.exception.code)
        self.assertGreaterEqual(calls, 2)

    def test_requires_at_least_one_unique_regular_outer_zip(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as empty:
            inspect_character_source(workspace=self.workspace, overlay_archives=[])
        self.assertEqual("WFREL_OVERLAY_INVALID", empty.exception.code)

        overlay = self._overlay("1.4.54", "1.4.55")
        with self.assertRaises(ReleaseError) as duplicate:
            inspect_character_source(
                workspace=self.workspace,
                overlay_archives=[overlay, overlay],
            )
        self.assertEqual("WFREL_OVERLAY_INVALID", duplicate.exception.code)

        directory = self.root / "not-a-zip"
        directory.mkdir()
        with self.assertRaises(ReleaseError) as wrong_type:
            inspect_character_source(
                workspace=self.workspace,
                overlay_archives=[directory],
            )
        self.assertEqual("WFREL_OVERLAY_INVALID", wrong_type.exception.code)

    def test_rejects_outer_zip_duplicates_extra_members_and_truncation(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        duplicate = make_patch_overlay(
            self.root / "duplicate.zip",
            from_version="1.4.54",
            target_version="1.4.55",
            duplicate_member="README.md",
        )
        extra = make_patch_overlay(
            self.root / "extra.zip",
            from_version="1.4.54",
            target_version="1.4.55",
            extra_members={"unexpected.txt": b"no"},
        )
        truncated = self._overlay("1.4.54", "1.4.56", folder="truncated")
        raw = truncated.read_bytes()
        truncated.write_bytes(raw[:-12])

        for label, path in (("duplicate", duplicate), ("extra", extra), ("truncated", truncated)):
            with self.subTest(label=label):
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[path],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_nul_truncated_outer_metadata_manifest_and_payload_names(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        for label in ("readme", "manifest", "payload"):
            with self.subTest(label=label):
                overlay = self._overlay("1.4.54", "1.4.55", folder=f"nul-{label}")
                with zipfile.ZipFile(overlay) as bundle:
                    manifest = json.loads(bundle.read("patch-manifest.json"))
                member = {
                    "readme": "README.md",
                    "manifest": "patch-manifest.json",
                    "payload": manifest["archives"][0]["relativePath"],
                }[label]
                rewrite_outer_member_raw_name(overlay, member, f"{member}\x00evil")
                with zipfile.ZipFile(overlay) as bundle:
                    info = next(item for item in bundle.infolist() if item.filename == member)
                    self.assertEqual(member, info.filename)
                    self.assertEqual(f"{member}\x00evil", info.orig_filename)

                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[overlay],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_outer_readme_with_invalid_crc(self) -> None:
        overlay = self._overlay("1.4.54", "1.4.55", folder="readme-crc")
        corrupt_zip_member_crc(overlay, "README.md")
        with zipfile.ZipFile(overlay) as bundle:
            with self.assertRaises(zipfile.BadZipFile):
                bundle.read("README.md")

        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as raised:
            inspect_character_source(
                workspace=self.workspace,
                overlay_archives=[overlay],
            )

        self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_outer_zip_bomb_ratio_before_reading_payload(self) -> None:
        overlay = make_patch_overlay(
            self.root / "bomb.zip",
            from_version="1.4.54",
            target_version="1.4.55",
            bomb_bytes=4 * 1024 * 1024,
        )

        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as raised:
            inspect_character_source(workspace=self.workspace, overlay_archives=[overlay])

        self.assertEqual("WFREL_OVERLAY_LIMIT", raised.exception.code)



if __name__ == "__main__":
    unittest.main()
