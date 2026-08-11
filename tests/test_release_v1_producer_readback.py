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


class ProducerReadbackTests(unittest.TestCase):
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

    def test_readback_rejects_tampered_raw_header_fields(self) -> None:
        import wf_release_v1.producer as producer

        real_flags = producer.force_utf8_flags
        mutations = (
            ("local-flags", 6, b"\x00\x00"),
            ("local-method", 8, b"\x08\x00"),
            ("local-time", 10, b"\x01\x00"),
            ("local-crc", 14, b"\x00\x00\x00\x00"),
            ("local-extra", 28, b"\x01\x00"),
            ("local-name", 30, b"x"),
        )
        for label, offset, replacement in mutations:
            with self.subTest(mutation=label):
                output = self.output_dir / f"{label}.zip"

                def tamper_after_writer(stream):
                    real_flags(stream)
                    stream.seek(offset)
                    stream.write(replacement)
                    stream.flush()

                with patch.object(producer, "force_utf8_flags", tamper_after_writer):
                    with self.assertRaises(ReleaseError):
                        producer.build_character_release(self._request(output))
                self.assertFalse(output.exists())

    def test_readback_rejects_noncanonical_release_manifest_bytes(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_metadata = producer._build_metadata

        def rewrite_manifest(request, source, files, members):
            release = real_metadata(request, source, files, members)
            value = release.to_wire()
            raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            members["release-manifest.json"] = producer._memory_member(
                "release-manifest.json", raw
            )
            return release

        with patch.object(producer, "_build_metadata", rewrite_manifest):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())

    def test_publish_link_is_the_last_commit_step_without_path_rollback(self) -> None:
        import wf_release_v1.release_archive as release_archive
        from wf_release_v1.producer import build_character_release

        output = self.output_dir / "release.zip"
        marker = self.root / "USER_MARKER"
        marker.write_bytes(b"user")
        moved = self.root / "published-before-takeover.zip"
        real_verify = release_archive.verify_parent
        real_lstat = release_archive.os.lstat
        verify_calls = 0
        output_lstats = 0

        def fail_after_link(parent):
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls == 2:
                raise ReleaseError(
                    "WFREL_BUILD_OUTPUT_CHANGED",
                    "injected parent drift",
                    {"label": "output"},
                )
            return real_verify(parent)

        def replace_after_rollback_lstat(path):
            nonlocal output_lstats
            metadata = real_lstat(path)
            if Path(path) == output:
                output_lstats += 1
                if output_lstats == 2:
                    output.rename(moved)
                    marker.rename(output)
            return metadata

        with (
            patch.object(release_archive, "verify_parent", fail_after_link),
            patch.object(release_archive.os, "lstat", replace_after_rollback_lstat),
        ):
            caught = None
            receipt = None
            try:
                receipt = build_character_release(self._request(output))
            except ReleaseError as error:
                caught = error

        self.assertTrue(marker.exists(), "path rollback deleted USER_MARKER")
        self.assertIsNone(caught)
        self.assertIsNotNone(receipt)
        self.assertEqual(output, receipt.output)
        with zipfile.ZipFile(output) as bundle:
            self.assertIn("wf-release-v1/release-manifest.json", bundle.namelist())
        self.assertEqual(b"user", marker.read_bytes())
        self.assertFalse(moved.exists())

    def test_staged_archive_replacement_after_readback_is_rejected(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_publish = producer.publish_new

        def replace_then_publish(staging, staging_path, destination, parent, readback):
            staging.seek(0, os.SEEK_END)
            middle = staging.tell() // 2
            staging.seek(middle)
            original = staging.read(1)
            self.assertTrue(original)
            staging.seek(middle)
            staging.write(bytes((original[0] ^ 1,)))
            staging.flush()
            return real_publish(staging, staging_path, destination, parent, readback)

        with patch.object(producer, "publish_new", replace_then_publish):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())

    def test_mutated_staged_payload_is_rejected_by_independent_readback(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_metadata = producer._build_metadata

        def mutate_after_manifest(request, source, files, members):
            release = real_metadata(request, source, files, members)
            payload = next(item for name, item in members.items() if name.startswith("content/"))
            payload.stream.seek(0)
            raw = bytearray(payload.stream.read())
            raw[len(raw) // 2] ^= 1
            payload.stream.seek(0)
            payload.stream.write(raw)
            payload.stream.truncate()
            payload.stream.seek(0)
            return release

        with patch.object(producer, "_build_metadata", mutate_after_manifest):
            with self.assertRaises(ReleaseError):
                producer.build_character_release(self._request(output))

        self.assertFalse(output.exists())

    def test_readback_rejects_hidden_bytes_between_locals_and_central_directory(self) -> None:
        import wf_release_v1.producer as producer

        output = self.output_dir / "release.zip"
        real_flags = producer.force_utf8_flags

        def insert_hidden_gap(stream):
            real_flags(stream)
            stream.seek(0)
            raw = bytearray(stream.read())
            eocd = len(raw) - 22
            central_at = struct.unpack_from("<I", raw, eocd + 16)[0]
            gap = b"PK\x06\x06" + b"\x00" * 25
            raw[central_at:central_at] = gap
            struct.pack_into("<I", raw, eocd + len(gap) + 16, central_at + len(gap))
            stream.seek(0)
            stream.write(raw)
            stream.truncate()
            stream.flush()

        with patch.object(producer, "force_utf8_flags", insert_hidden_gap):
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

    def test_posix_archive_inode_is_linkable_without_o_excl(self) -> None:
        import wf_release_v1.producer as producer

        fake_stream = object()
        with (
            patch.object(producer.os, "name", "posix"),
            patch.object(producer.os, "O_TMPFILE", 0x400000, create=True),
            patch.object(producer.os, "open", return_value=71) as opened,
            patch.object(producer.os, "fdopen", return_value=fake_stream),
        ):
            stream, path = producer._archive_temp(self.output_dir)

        self.assertIs(fake_stream, stream)
        self.assertIsNone(path)
        opened.assert_called_once()
        flags = opened.call_args.args[1]
        self.assertTrue(flags & 0x400000)
        self.assertFalse(flags & os.O_EXCL)

    @unittest.skipUnless(
        os.name == "posix" and sys.platform.startswith("linux"),
        "Linux /proc fd publication gate",
    )
    def test_linux_ordinary_user_procfd_fallback_links_real_open_file(self) -> None:
        script = r'''import ctypes
import errno
import os
from pathlib import Path
import tempfile
from wf_release_v1.release_archive import _posix_link_handle, capture_parent

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source_path = root / "source.bin"
    output = root / "release.zip"
    with source_path.open("w+b") as source:
        source.write(b"sealed-archive")
        source.flush()
        parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            linkat = libc.linkat
            linkat.argtypes = (
                ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                ctypes.c_char_p, ctypes.c_int,
            )
            linkat.restype = ctypes.c_int
            ctypes.set_errno(0)
            result = linkat(source.fileno(), b"", parent_fd, b"probe", 0x1000)
            if result == 0:
                (root / "probe").unlink()
                raise SystemExit(77)
            if ctypes.get_errno() != errno.EPERM:
                raise SystemExit(f"unexpected AT_EMPTY_PATH errno: {ctypes.get_errno()}")
        finally:
            os.close(parent_fd)
        _posix_link_handle(source, output, capture_parent(root))
    if output.read_bytes() != b"sealed-archive":
        raise SystemExit("procfd fallback published wrong bytes")
'''
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 77:
            self.skipTest("process has AT_EMPTY_PATH capability; ordinary-user gate unavailable")
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

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

        device_names = (
            "CON.zip", "com1.ZIP", "LPT9.data.zip",
            "COM¹.zip", "com².ZIP", "COM³.data.zip",
            "LPT¹.zip", "lpt².ZIP", "LPT³.data.zip",
            "CONIN$.zip", "conout$.ZIP",
        )
        for index, device_name in enumerate(device_names):
            with self.subTest(device_name=device_name):
                nonportable = make_patch_overlay(
                    self.root / "sources" / device_name,
                    from_version="1.4.54",
                    target_version="1.4.55",
                )
                with self.assertRaises(ReleaseError) as raised:
                    build_character_release(
                        self._request(
                            self.output_dir / f"release-{index}.zip",
                            overlays=(nonportable,),
                        )
                    )
                self.assertEqual("WFREL_BUILD_PATH_INVALID", raised.exception.code)
                self.assertNotIn(str(self.root), str(raised.exception.details))
        self.assertEqual(set(), self._all_files(self.output_dir))

    def test_accepts_nfc_unicode_overlay_filename_with_raw_utf8_flags(self) -> None:
        from wf_release_v1.producer import build_character_release

        overlay = make_patch_overlay(
            self.root / "sources" / "角色-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        output = self.output_dir / "unicode-release.zip"
        build_character_release(self._request(output, overlays=(overlay,)))

        raw = output.read_bytes()
        with zipfile.ZipFile(output) as bundle:
            info = bundle.getinfo(f"wf-release-v1/content/{overlay.name}")
            self.assertTrue(info.flag_bits & 0x800)
            self.assertEqual(0x800, struct.unpack_from("<H", raw, info.header_offset + 6)[0])
            cursor = bundle.start_dir
            central_flags = None
            for candidate in bundle.infolist():
                header = struct.unpack_from("<IHHHHHHIIIHHHHHII", raw, cursor)
                if candidate.filename == info.filename:
                    central_flags = header[3]
                    break
                cursor += 46 + header[10] + header[11] + header[12]
            self.assertEqual(0x800, central_flags)
            self.assertEqual(overlay.read_bytes(), bundle.read(info))

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
