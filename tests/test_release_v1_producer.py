"""Deterministic, no-clobber wf-release-v1 producer tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests.release_v1_fixtures import (
    make_patch_overlay,
    make_sealed_character_workspace,
)
from tests.release_v1_schema_support import requirements_wire
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
                "wf-release-v1/release-manifest.json",
                "wf-release-v1/requires.json",
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

    def test_outer_zip_has_one_canonical_raw_encoding(self) -> None:
        from wf_release_v1.producer import build_character_release

        output = self.output_dir / "release.zip"
        build_character_release(self._request(output))

        raw = output.read_bytes()
        with zipfile.ZipFile(output) as bundle:
            infos = bundle.infolist()
            self.assertEqual(
                sorted((info.filename for info in infos), key=lambda item: item.encode("utf-8")),
                [info.filename for info in infos],
            )
            self.assertEqual(len(infos), len({info.filename for info in infos}))
            self.assertEqual(b"", bundle.comment)
            for info in infos:
                with self.subTest(member=info.filename):
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

        self.assertIn(raised.exception.code, {"WFREL_HASH_SOURCE_CHANGED", "WFREL_BUILD_SOURCE_CHANGED"})
        self.assertFalse((self.output_dir / "release.zip").exists())
        self.assertFalse(any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir)))

    def test_output_race_is_no_clobber_and_cleans_only_private_staging(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        marker = self.output_dir / "user-marker.txt"
        marker.write_bytes(b"user")
        real_publish = producer.publish_new

        def racing_publish(staging, destination, parent):
            Path(destination).write_bytes(b"racer")
            return real_publish(staging, destination, parent)

        with patch.object(producer, "publish_new", racing_publish):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertEqual(b"racer", output.read_bytes())
        self.assertEqual(b"user", marker.read_bytes())
        self.assertFalse(any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir)))

    def test_readback_failure_never_publishes_or_leaks_staging(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        with patch.object(
            producer,
            "reopen_for_readback",
            side_effect=ReleaseError("WFREL_ARCHIVE_INVALID", "readback failed", {"label": "archive"}),
        ):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())
        self.assertFalse(any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir)))

    def test_post_link_identity_failure_removes_only_the_owned_output(self) -> None:
        import wf_release_v1.release_archive as release_archive
        from wf_release_v1.producer import build_character_release

        output = self.output_dir / "release.zip"
        real_verify = release_archive.verify_parent
        calls = 0

        def fail_after_link(parent):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ReleaseError(
                    "WFREL_BUILD_OUTPUT_CHANGED",
                    "injected parent drift",
                    {"label": "output"},
                )
            return real_verify(parent)

        with patch.object(release_archive, "verify_parent", fail_after_link):
            with self.assertRaises(ReleaseError):
                build_character_release(self._request(output))

        self.assertFalse(output.exists())
        self.assertFalse(any(path.name.startswith(".wfrel-") for path in self._all_files(self.output_dir)))

    def test_staged_archive_replacement_after_readback_is_rejected(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_publish = producer.publish_new

        def replace_then_publish(staging, destination, parent):
            moved = staging.with_suffix(".original")
            staging.rename(moved)
            raw = bytearray(moved.read_bytes())
            raw[len(raw) // 2] ^= 1
            staging.write_bytes(raw)
            return real_publish(staging, destination, parent)

        with patch.object(producer, "publish_new", replace_then_publish):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())

    def test_mutated_staged_payload_is_rejected_by_independent_readback(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_metadata = producer._build_metadata

        def mutate_after_manifest(request, source, files, staging_root):
            release = real_metadata(request, source, files, staging_root)
            payload = next((staging_root / "content").iterdir())
            raw = bytearray(payload.read_bytes())
            raw[len(raw) // 2] ^= 1
            payload.write_bytes(raw)
            return release

        with patch.object(producer, "_build_metadata", mutate_after_manifest):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())

    def test_classic_zip_limit_fails_closed_without_output(self) -> None:
        import wf_release_v1.release_archive as release_archive
        from wf_release_v1.producer import build_character_release

        output = self.output_dir / "release.zip"
        with patch.object(release_archive, "_UINT32_MAX", 1):
            with self.assertRaises(ReleaseError) as raised:
                build_character_release(self._request(output))

        self.assertEqual("WFREL_BUILD_LIMIT", raised.exception.code)
        self.assertFalse(output.exists())

    @unittest.skipUnless(os.name == "nt", "junctions are Windows-specific")
    def test_rejects_reparse_points_in_output_parent_chain(self) -> None:
        from wf_release_v1.producer import build_character_release

        target = self.root / "real-output"
        junction = self.root / "output-junction"
        target.mkdir()
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode:
            self.skipTest(f"junction unavailable: {result.stderr or result.stdout}")

        with self.assertRaises(ReleaseError) as raised:
            build_character_release(self._request(junction / "release.zip"))

        self.assertFalse((target / "release.zip").exists())
        self.assertNotIn(str(self.root), str(raised.exception))

    def test_rejects_nonportable_overlay_member_names_before_staging(self) -> None:
        from wf_release_v1.producer import build_character_release

        nonportable = make_patch_overlay(
            self.root / "sources" / "CON.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        with self.assertRaises(ReleaseError):
            build_character_release(
                self._request(self.output_dir / "release.zip", overlays=(nonportable,))
            )
        self.assertEqual(set(), self._all_files(self.output_dir))

    def test_rejects_portable_casefold_collisions_between_content_members(self) -> None:
        from wf_release_v1.producer import build_character_release

        first = make_patch_overlay(
            self.root / "sources" / "one" / "A.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        second = make_patch_overlay(
            self.root / "sources" / "two" / "a.ZIP",
            from_version="1.4.55",
            target_version="1.4.56",
        )
        with self.assertRaises(ReleaseError) as raised:
            build_character_release(
                self._request(
                    self.output_dir / "release.zip",
                    overlays=(first, second),
                )
            )

        self.assertEqual("WFREL_BUILD_PATH_INVALID", raised.exception.code)
        self.assertEqual(set(), self._all_files(self.output_dir))


if __name__ == "__main__":
    unittest.main()
