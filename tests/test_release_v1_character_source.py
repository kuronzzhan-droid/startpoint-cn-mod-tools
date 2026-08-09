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
    make_patch_overlay,
    make_sealed_character_workspace,
    replace_first_inner_zip,
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

    def test_rejects_inner_zip_bomb_ratio(self) -> None:
        overlay = self._overlay("1.4.54", "1.4.55", folder="inner-bomb")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("production/bomb.bin", b"0" * (4 * 1024 * 1024))
        bomb = output.getvalue()

        with zipfile.ZipFile(overlay) as bundle:
            common = next(
                name for name in bundle.namelist() if name.startswith("archive-common-diff/")
            )

        def bind_bomb(manifest):
            item = next(entry for entry in manifest["archives"] if entry["layer"] == "common")
            item["bytes"] = len(bomb)
            item["sha256"] = hashlib.sha256(bomb).hexdigest()

        rewrite_overlay(
            overlay,
            manifest_mutator=bind_bomb,
            member_mutator=lambda ordered: [
                (name, bomb if name == common else raw) for name, raw in ordered
            ],
        )

        from wf_release_v1.character_source import inspect_character_source

        with self.assertRaises(ReleaseError) as raised:
            inspect_character_source(workspace=self.workspace, overlay_archives=[overlay])

        self.assertEqual("WFREL_OVERLAY_LIMIT", raised.exception.code)

    def test_rejects_noncanonical_duplicate_or_conflicting_inner_paths(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        cases = {
            "parent": ["../escape.txt"],
            "absolute": ["/absolute.txt"],
            "backslash": [r"production\backslash.txt"],
            "drive": ["C:/drive.txt"],
            "unc": [r"\\server\share.txt"],
            "empty": [""],
            "directory": ["production/"],
            "duplicate": ["production/same.txt", "production/same.txt"],
            "normalized-conflict": ["production/é.txt", "production/e\u0301.txt"],
        }
        for label, names in cases.items():
            with self.subTest(label=label):
                overlay = self._overlay("1.4.54", "1.4.55", folder=label)
                replace_first_inner_zip(overlay, names)
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[overlay],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_bool_schema_and_oversized_patch_manifest(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        bool_schema = self._overlay("1.4.54", "1.4.55", folder="bool-schema")
        rewrite_overlay(
            bool_schema,
            manifest_mutator=lambda manifest: manifest.update({"schema": True}),
        )
        oversized = make_patch_overlay(
            self.root / "oversized-manifest.zip",
            from_version="1.4.54",
            target_version="1.4.56",
            manifest_updates={"authorNotes": os.urandom(600_000).hex()},
        )

        for path in (bool_schema, oversized):
            with self.subTest(path=path.name):
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[path],
                    )
                self.assertIn(
                    raised.exception.code,
                    {"WFREL_OVERLAY_INVALID", "WFREL_OVERLAY_LIMIT"},
                )

    def test_rejects_manifest_path_escape_and_mismatched_payload_identity(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        for label, mutate in (
            (
                "escape",
                lambda manifest: manifest["archives"][0].update(
                    {"relativePath": "../escape.zip"}
                ),
            ),
            (
                "size",
                lambda manifest: manifest["archives"][0].update(
                    {"bytes": manifest["archives"][0]["bytes"] + 1}
                ),
            ),
            (
                "hash",
                lambda manifest: manifest["archives"][0].update({"sha256": "0" * 64}),
            ),
        ):
            with self.subTest(label=label):
                overlay = self._overlay("1.4.54", "1.4.55", folder=label)
                rewrite_overlay(overlay, manifest_mutator=mutate)
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[overlay],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_invalid_metadata_json_and_manifest_not_last(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        invalid_json = self._overlay("1.4.54", "1.4.55", folder="bad-json")

        def corrupt_requires(ordered):
            return [
                (name, b"{" if name == "requires.json" else raw)
                for name, raw in ordered
            ]

        rewrite_overlay(invalid_json, member_mutator=corrupt_requires)
        not_last = self._overlay("1.4.54", "1.4.56", folder="not-last")

        def move_manifest(ordered):
            manifest = next(item for item in ordered if item[0] == "patch-manifest.json")
            rest = [item for item in ordered if item[0] != "patch-manifest.json"]
            return [manifest, *rest]

        rewrite_overlay(not_last, member_mutator=move_manifest)

        for path in (invalid_json, not_last):
            with self.subTest(path=path.name):
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[path],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)

    def test_rejects_disconnected_forked_cyclic_or_duplicate_edges(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        duplicate_copy = self._overlay(
            "1.4.54", "1.4.55", folder="duplicate-edge-b"
        )
        duplicate_copy = duplicate_copy.rename(
            duplicate_copy.with_name("copy-of-1.4.54-to-1.4.55.zip")
        )
        cases = {
            "disconnected": [
                self._overlay("1.4.54", "1.4.55", folder="disconnected"),
                self._overlay("1.4.70", "1.4.71", folder="disconnected"),
            ],
            "fork": [
                self._overlay("1.4.54", "1.4.55", folder="fork"),
                self._overlay("1.4.54", "1.4.56", folder="fork"),
            ],
            "cycle": [
                self._overlay("1.4.54", "1.4.55", folder="cycle"),
                self._overlay("1.4.55", "1.4.54", folder="cycle"),
            ],
            "duplicate-edge": [
                self._overlay("1.4.54", "1.4.55", folder="duplicate-edge-a"),
                duplicate_copy,
            ],
        }
        for label, overlays in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=overlays,
                    )
                self.assertEqual("WFREL_OVERLAY_GRAPH", raised.exception.code)

    def test_rejects_missing_layer_or_noncontiguous_layer_order(self) -> None:
        from wf_release_v1.character_source import inspect_character_source

        missing = self._overlay("1.4.54", "1.4.55", folder="missing")

        def remove_android(manifest):
            manifest["archives"] = [
                item for item in manifest["archives"] if item["layer"] != "android"
            ]

        rewrite_overlay(
            missing,
            manifest_mutator=remove_android,
            member_mutator=lambda ordered: [
                item for item in ordered if not item[0].startswith("archive-android-diff/")
            ],
        )
        order = self._overlay("1.4.54", "1.4.56", folder="order")

        def bad_order(manifest):
            manifest["archives"][0]["order"] = 2

        rewrite_overlay(order, manifest_mutator=bad_order)

        for path in (missing, order):
            with self.subTest(path=path.name):
                with self.assertRaises(ReleaseError) as raised:
                    inspect_character_source(
                        workspace=self.workspace,
                        overlay_archives=[path],
                    )
                self.assertEqual("WFREL_OVERLAY_INVALID", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
