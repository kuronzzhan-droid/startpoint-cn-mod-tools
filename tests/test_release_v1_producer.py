"""Deterministic, no-clobber wf-release-v1 producer tests."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import wf_character_workspace

from tests.release_v1_fixtures import (
    make_patch_overlay,
    make_sealed_character_workspace,
)
from tests.release_v1_schema_support import ownership_wire, release_wire, requirements_wire
from wf_release_v1.canonical import canonical_json_bytes, load_json_strict_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.schema import (
    parse_ownership,
    parse_release_manifest,
    parse_requirements,
    verify_release_id,
)


ROOT_MEMBER = "wf-release-v1/"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_MODE = stat.S_IFREG | 0o644


class ProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = make_sealed_character_workspace(self.root / "workspace")
        self.overlay = make_patch_overlay(
            self.root / "sources" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        self.output_dir = self.root / "output"
        self.output_dir.mkdir()

    def _request(
        self,
        output: Path,
        *,
        overlays: tuple[Path, ...] | None = None,
        name: str = "seris-dragon-king",
        version: str = "1.0.0",
    ):
        from wf_release_v1.producer import BuildRequest

        return BuildRequest(
            name=name,
            version=version,
            workspace=self.workspace,
            overlay_archives=overlays or (self.overlay,),
            output=output,
            requirements=parse_requirements(requirements_wire()),
        )

    @staticmethod
    def _wire(bundle: zipfile.ZipFile, name: str) -> dict[str, object]:
        value = load_json_strict_bytes(bundle.read(name), label=name)
        if not isinstance(value, dict):
            raise AssertionError(f"{name} is not an object")
        return value

    @staticmethod
    def _all_files(root: Path) -> set[Path]:
        return {path for path in root.rglob("*") if path.is_file()}

    def test_builds_exact_content_only_archive_from_real_sources(self) -> None:
        from wf_release_v1.producer import build_character_release

        source_bytes = self.overlay.read_bytes()
        output = self.output_dir / "release.zip"
        receipt = build_character_release(self._request(output))

        self.assertEqual(output, receipt.output)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), receipt.archive_sha256)
        self.assertEqual(1, receipt.file_count)
        self.assertEqual(len(source_bytes), receipt.bytes_read)
        self.assertEqual(1, receipt.hash_count)

        with zipfile.ZipFile(output) as bundle:
            names = bundle.namelist()
            expected = [
                "wf-release-v1/content/worldflipper-overlay-1.4.54-to-1.4.55.zip",
                "wf-release-v1/ownership.json",
                "wf-release-v1/requires.json",
                "wf-release-v1/release-manifest.json",
            ]
            self.assertEqual(expected, names)
            self.assertEqual(source_bytes, bundle.read(expected[0]))
            self.assertFalse(any("/server/" in name or "/modes/" in name for name in names))

            release_wire = self._wire(bundle, f"{ROOT_MEMBER}release-manifest.json")
            requirements = self._wire(bundle, f"{ROOT_MEMBER}requires.json")
            ownership_wire = self._wire(bundle, f"{ROOT_MEMBER}ownership.json")
            release = parse_release_manifest(release_wire)
            verify_release_id(release)
            ownership = parse_ownership(ownership_wire)

            self.assertEqual(receipt.release_id, release.release_id)
            self.assertEqual(requirements_wire(), requirements)
            self.assertEqual(("content",), tuple(item.kind for item in release.components))
            self.assertEqual("1.4.55", release.expected_state.cdn_target_version)
            self.assertIsNone(release.expected_state.content_digest)
            self.assertIsNone(release.expected_state.mode_digest)
            self.assertEqual(
                [{
                    "path": "content/worldflipper-overlay-1.4.54-to-1.4.55.zip",
                    "size": len(source_bytes),
                    "sha256": hashlib.sha256(source_bytes).hexdigest(),
                }],
                release_wire["files"],
            )
            self.assertEqual(
                hashlib.sha256(canonical_json_bytes(requirements)).hexdigest(),
                release.metadata_sha256.requires,
            )
            self.assertEqual(
                hashlib.sha256(canonical_json_bytes(ownership_wire)).hexdigest(),
                release.metadata_sha256.ownership,
            )
            self.assertEqual(("character:129999",), ownership.entities)
            self.assertEqual(("character:129999",), ownership.records)
            self.assertIn("cdndata/character.json", ownership.paths)
            self.assertIn("master/character/character.orderedmap", ownership.paths)
            # Ownership is source-manifest semantics. It is intentionally not a
            # claim that these logical paths were mapped byte-for-byte inside
            # the independently validated outer Overlay archive.

    def test_sealed_accepted_asset_replacements_are_release_bound_and_exclusive(self) -> None:
        """Dropping accepted replacements during build would reopen shared-asset clobbers."""
        from wf_release_v1.producer import build_character_release
        from wf_release_v1.verifier import verify_release_contract

        current = wf_character_workspace.load_workspace(self.workspace)
        manifest_path = current.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assets = (
            (
                "item/sprite_sheet.atlas.amf3.deflate",
                b"atlas-after",
                b"atlas-before",
            ),
            ("item/sprite_sheet.png", b"sheet-after", b"sheet-before"),
        )
        accepted = []
        for logical_path, after, before in assets:
            candidate = current.package_dir / "roots" / "common" / Path(logical_path)
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(after)
            manifest["roots"]["common"].append({
                "logical_path": logical_path,
                "sha256": hashlib.sha256(after).hexdigest(),
                "size": len(after),
            })
            accepted.append({
                "root": "common",
                "logical_path": logical_path,
                "before_sha256": hashlib.sha256(before).hexdigest(),
                "before_size": len(before),
            })
        # The sealed workspace binds author order, while Release v2 emits one
        # canonical root/path order independent of that presentation detail.
        manifest["snapshot"]["accepted_asset_replacements"] = list(reversed(accepted))
        manifest["qa"]["workspace_input_sha256"] = ""
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        wf_character_workspace.seal_workspace(current)

        output = self.output_dir / "asset-replacements.zip"
        build_character_release(self._request(output))
        _report, verified = verify_release_contract(output)

        self.assertEqual("character-workspace-v2", verified.manifest.source_evidence.kind)
        self.assertEqual(
            [
                {
                    "beforeSha256": hashlib.sha256(before).hexdigest(),
                    "beforeSize": len(before),
                    "logicalPath": logical_path,
                    "root": "common",
                }
                for logical_path, _after, before in assets
            ],
            verified.manifest.source_evidence.to_wire()["acceptedAssetReplacements"],
        )
        self.assertEqual(
            {
                "asset:common/item/sprite_sheet.atlas.amf3.deflate",
                "asset:common/item/sprite_sheet.png",
            },
            {record for record in verified.ownership.records if record.startswith("asset:")},
        )

    def test_outer_zip_has_one_canonical_raw_encoding(self) -> None:
        from wf_release_v1.producer import build_character_release

        output = self.output_dir / "release.zip"
        build_character_release(self._request(output))

        raw = output.read_bytes()
        with zipfile.ZipFile(output) as bundle:
            infos = bundle.infolist()
            names = [info.filename for info in infos]
            self.assertEqual(
                sorted(names[:-1], key=lambda item: item.encode("utf-8")),
                names[:-1],
            )
            self.assertEqual("wf-release-v1/release-manifest.json", names[-1])
            self.assertEqual(len(infos), len({info.filename for info in infos}))
            self.assertEqual(b"", bundle.comment)
            for info in infos:
                with self.subTest(member=info.filename):
                    local = struct.unpack_from("<IHHHHHIIIHH", raw, info.header_offset)
                    local_name_at = info.header_offset + 30
                    local_name = raw[local_name_at:local_name_at + local[9]]
                    local_extra = raw[
                        local_name_at + local[9]:local_name_at + local[9] + local[10]
                    ]
                    self.assertEqual(FIXED_TIME, info.date_time)
                    self.assertEqual(zipfile.ZIP_STORED, info.compress_type)
                    self.assertEqual(3, info.create_system)
                    self.assertEqual(FIXED_MODE, info.external_attr >> 16)
                    self.assertEqual(b"", info.extra)
                    self.assertTrue(info.flag_bits & 0x800)
                    self.assertFalse(info.is_dir())
                    self.assertEqual(info.file_size, info.compress_size)
                    self.assertEqual(info.CRC, zipfile.crc32(bundle.read(info)))
                    self.assertTrue(info.filename.isascii())
                    self.assertEqual(0x04034B50, local[0])
                    self.assertEqual(0x800, local[2])
                    self.assertEqual(zipfile.ZIP_STORED, local[3])
                    self.assertEqual((0, 33), (local[4], local[5]))
                    self.assertEqual(
                        (info.CRC, info.compress_size, info.file_size),
                        (local[6], local[7], local[8]),
                    )
                    self.assertEqual(info.filename.encode("utf-8"), local_name)
                    self.assertEqual(b"", local_extra)
            cursor = bundle.start_dir
            for info in infos:
                central = struct.unpack_from("<IHHHHHHIIIHHHHHII", raw, cursor)
                central_name_at = cursor + 46
                central_name = raw[central_name_at:central_name_at + central[10]]
                central_extra = raw[
                    central_name_at + central[10]:
                    central_name_at + central[10] + central[11]
                ]
                with self.subTest(central_member=info.filename):
                    self.assertEqual(0x02014B50, central[0])
                    self.assertEqual((3 << 8) | 20, central[1])
                    self.assertEqual(20, central[2])
                    self.assertEqual(0x800, central[3])
                    self.assertEqual(zipfile.ZIP_STORED, central[4])
                    self.assertEqual((0, 33), (central[5], central[6]))
                    self.assertEqual(
                        (info.CRC, info.compress_size, info.file_size),
                        (central[7], central[8], central[9]),
                    )
                    self.assertEqual(info.filename.encode("utf-8"), central_name)
                    self.assertEqual(b"", central_extra)
                    self.assertEqual(0, central[12])
                    self.assertEqual(FIXED_MODE << 16, central[15])
                    self.assertEqual(info.header_offset, central[16])
                cursor += 46 + central[10] + central[11] + central[12]
            self.assertNotIn(b"PK\x06\x06", raw)
            self.assertNotIn(b"PK\x06\x07", raw)
            self.assertNotIn(b"\x01\x00", b"".join(info.extra for info in infos))

    def test_same_inputs_are_byte_identical_and_output_path_is_not_identity(self) -> None:
        from wf_release_v1.producer import build_character_release

        first = build_character_release(self._request(self.output_dir / "first.zip"))
        second = build_character_release(self._request(self.output_dir / "second.zip"))

        self.assertEqual(first.release_id, second.release_id)
        self.assertEqual(first.archive_sha256, second.archive_sha256)
        self.assertEqual(first.output.read_bytes(), second.output.read_bytes())

    def test_canonical_metadata_changes_release_identity(self) -> None:
        from wf_release_v1.producer import build_character_release

        first = build_character_release(self._request(self.output_dir / "first.zip"))
        second = build_character_release(
            self._request(
                self.output_dir / "second.zip",
                name="seris-dragon-king-next",
                version="1.0.1",
            )
        )

        self.assertNotEqual(first.release_id, second.release_id)
        self.assertNotEqual(first.archive_sha256, second.archive_sha256)

    def test_each_canonical_metadata_member_has_the_verifier_limit(self) -> None:
        from wf_release_v1 import producer

        fixtures = {
            "requires.json": canonical_json_bytes(requirements_wire()),
            "ownership.json": canonical_json_bytes(ownership_wire()),
            "release-manifest.json": canonical_json_bytes(
                release_wire(computed_id=True)
            ),
        }
        with patch.object(producer, "_MAX_METADATA_BYTES", 8, create=True):
            for name, raw in fixtures.items():
                with self.subTest(name=name):
                    with self.assertRaises(ReleaseError) as raised:
                        producer._memory_member(name, raw)
                    self.assertEqual("WFREL_BUILD_LIMIT", raised.exception.code)

    def test_public_build_rejects_oversized_canonical_requirements_before_publish(self) -> None:
        from wf_release_v1.producer import BuildRequest, build_character_release

        wire = requirements_wire()
        wire["serverCapabilities"] = [
            f"cap{index:05d}{'x' * 55}@1" for index in range(18000)
        ]
        requirements = parse_requirements(wire)
        self.assertGreater(len(canonical_json_bytes(requirements.to_wire())), 1024 * 1024)
        output = self.output_dir / "oversized-metadata.zip"
        request = BuildRequest(
            name="seris-dragon-king",
            version="1.0.0",
            workspace=self.workspace,
            overlay_archives=(self.overlay,),
            output=output,
            requirements=requirements,
        )

        with self.assertRaises(ReleaseError) as raised:
            build_character_release(request)
        self.assertEqual("WFREL_BUILD_LIMIT", raised.exception.code)
        self.assertFalse(output.exists())

    def test_public_build_rejects_unsupported_overlay_requirement_before_output(self) -> None:
        from wf_release_v1.producer import build_character_release

        wire = requirements_wire()
        wire["patchOverlaySchema"] = 2
        output = self.output_dir / "unsupported-requirement.zip"
        request = replace(
            self._request(output),
            workspace=self.output_dir / "missing-workspace",
            requirements=parse_requirements(wire),
        )

        with self.assertRaises(ReleaseError) as raised:
            build_character_release(request)
        self.assertEqual("WFREL_REQUIRE_UNSUPPORTED", raised.exception.code)
        self.assertEqual({"field": "patchOverlaySchema"}, raised.exception.details)
        self.assertFalse(output.exists())

    def test_rejects_existing_nested_or_source_overlapping_output_without_changes(self) -> None:
        from wf_release_v1.producer import build_character_release

        existing = self.output_dir / "existing.zip"
        existing.write_bytes(b"keep")
        nested = self.workspace / "package" / "release.zip"
        alias = self.output_dir / "overlay-alias.zip"
        os.link(self.overlay, alias)
        overlay_before = self.overlay.read_bytes()

        for output in (existing, nested, alias):
            with self.subTest(output=output.name):
                with self.assertRaises(ReleaseError) as raised:
                    build_character_release(self._request(output))
                self.assertNotIn(str(self.root), str(raised.exception))

        self.assertEqual(b"keep", existing.read_bytes())
        self.assertEqual(overlay_before, self.overlay.read_bytes())
        self.assertEqual(overlay_before, alias.read_bytes())

    def test_binds_the_task4_pinned_source_identity_before_copy(self) -> None:
        import wf_release_v1.producer as producer

        original_identity_check = producer._stable_source_identity
        replacement = self.root / "replacement.zip"
        shutil.copyfile(self.overlay, replacement)
        replacement_raw = bytearray(replacement.read_bytes())
        replacement_raw[len(replacement_raw) // 2] ^= 1
        replacement.write_bytes(replacement_raw)
        moved = self.overlay.with_suffix(".original")
        calls = 0

        def replace_then_restore(source):
            nonlocal calls
            calls += 1
            if calls == 1:
                original_identity_check(source)
                source.path.rename(moved)
                replacement.rename(source.path)
                return
            if calls == 2:
                source.path.rename(replacement)
                moved.rename(source.path)
            original_identity_check(source)

        with patch.object(producer, "_stable_source_identity", replace_then_restore):
            with self.assertRaises(ReleaseError) as raised:
                producer.build_character_release(self._request(self.output_dir / "release.zip"))

        self.assertIn(
            raised.exception.code,
            {"WFREL_HASH_SOURCE_CHANGED", "WFREL_BUILD_SOURCE_CHANGED"},
        )
        self.assertFalse((self.output_dir / "release.zip").exists())
        self.assertFalse(
            any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir))
        )

    def test_output_race_is_no_clobber_and_cleans_only_private_staging(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        marker = self.output_dir / "user-marker.txt"
        marker.write_bytes(b"user")
        real_publish = producer.publish_new

        def racing_publish(staging, staging_path, destination, parent, readback):
            Path(destination).write_bytes(b"racer")
            return real_publish(staging, staging_path, destination, parent, readback)

        with patch.object(producer, "publish_new", racing_publish):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertEqual(b"racer", output.read_bytes())
        self.assertEqual(b"user", marker.read_bytes())
        self.assertFalse(
            any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir))
        )

    def test_readback_failure_never_publishes_or_leaks_staging(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        with patch.object(
            producer,
            "reopen_for_readback",
            side_effect=ReleaseError(
                "WFREL_ARCHIVE_INVALID", "readback failed", {"label": "archive"}
            ),
        ):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())
        self.assertFalse(
            any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir))
        )

    def test_cleanup_path_takeover_never_deletes_user_directory(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        user_directory = self.root / "user-directory"
        user_directory.mkdir()
        marker = user_directory / "USER_MARKER"
        marker.write_bytes(b"keep")
        recursive_cleanup_called = False

        def reject_recursive_cleanup(path):
            nonlocal recursive_cleanup_called
            recursive_cleanup_called = True
            raise AssertionError(f"unsafe recursive cleanup attempted: {path}")

        with (
            patch.object(shutil, "rmtree", reject_recursive_cleanup),
            patch.object(
                producer,
                "reopen_for_readback",
                side_effect=ReleaseError(
                    "WFREL_ARCHIVE_INVALID",
                    "injected failure",
                    {"label": "archive"},
                ),
            ),
        ):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(recursive_cleanup_called)
        self.assertEqual(b"keep", marker.read_bytes())
        self.assertFalse(output.exists())



if __name__ == "__main__":
    unittest.main()
