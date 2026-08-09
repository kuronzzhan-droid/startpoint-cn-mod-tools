"""Behavioural coverage for release-v1 canonical primitives."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from wf_release_v1.canonical import (
    canonical_json_bytes,
    load_json_strict_bytes,
    normalize_relative_path,
    stream_copy_and_hash_stable_file,
)
from wf_release_v1.errors import ReleaseError


class StrictJsonTests(unittest.TestCase):
    def assert_release_error(self, code: str, operation) -> None:
        with self.assertRaises(ReleaseError) as raised:
            operation()
        self.assertEqual(code, raised.exception.code)
        self.assertNotIn("C:\\", str(raised.exception.details))

    def test_rejects_bom_and_non_utf8(self) -> None:
        self.assert_release_error(
            "WFREL_JSON_BOM",
            lambda: load_json_strict_bytes(b"\xef\xbb\xbf{}", label="manifest"),
        )
        self.assert_release_error(
            "WFREL_JSON_UTF8",
            lambda: load_json_strict_bytes(b"\xff", label="manifest"),
        )

    def test_rejects_nonfinite_values_and_duplicate_keys(self) -> None:
        for raw in (
            b'{"value":NaN}',
            b'{"value":Infinity}',
            b'{"value":-Infinity}',
            b'{"value":1e999}',
        ):
            with self.subTest(raw=raw):
                self.assert_release_error(
                    "WFREL_JSON_NONFINITE",
                    lambda raw=raw: load_json_strict_bytes(raw, label="manifest"),
                )
        self.assert_release_error(
            "WFREL_JSON_DUPLICATE_KEY",
            lambda: load_json_strict_bytes(b'{"id":1,"id":2}', label="manifest"),
        )

    def test_loads_valid_json_and_writes_exact_canonical_form(self) -> None:
        value = load_json_strict_bytes(
            '{"z":"雪","a":[true,null,1]}'.encode("utf-8"), label="manifest"
        )
        self.assertEqual(
            b'{"a":[true,null,1],"z":"\xe9\x9b\xaa"}\n',
            canonical_json_bytes(value),
        )


class RelativePathTests(unittest.TestCase):
    def test_accepts_only_already_canonical_posix_relative_paths(self) -> None:
        self.assertEqual("nested/file.json", normalize_relative_path("nested/file.json"))
        self.assertEqual("雪/file.json", normalize_relative_path("雪/file.json"))

        rejected = (
            "",
            ".",
            "..",
            "../escape.json",
            "nested/../escape.json",
            "/absolute.json",
            "C:/drive.json",
            "\\\\server\\share\\file.json",
            "back\\slash.json",
            "nul\x00byte.json",
            "nested//empty.json",
            "nested/./dot.json",
            "nested/",
            "e\u0301.json",
        )
        for value in rejected:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ReleaseError) as raised:
                    normalize_relative_path(value)
                self.assertEqual("WFREL_PATH_INVALID", raised.exception.code)
                self.assertNotIn("C:\\", str(raised.exception.details))


class StableFileCopyTests(unittest.TestCase):
    def test_copies_and_hashes_a_regular_file(self) -> None:
        payload = b"release-v1\x00payload\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            destination = root / "destination.bin"
            source.write_bytes(payload)

            identity = stream_copy_and_hash_stable_file(source, destination)

            self.assertEqual(payload, destination.read_bytes())
            self.assertEqual(len(payload), identity.size)
            self.assertEqual(hashlib.sha256(payload).hexdigest(), identity.sha256)

    def test_rejects_a_symlink_source_without_leaking_its_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.bin"
            source = root / "source-link.bin"
            target.write_bytes(b"payload")
            try:
                os.symlink(target, source)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlink unavailable: {error}")

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(source, root / "output.bin")

            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertNotIn(str(root), str(raised.exception.details))

    @unittest.skipUnless(os.name == "nt", "junctions are Windows-specific")
    def test_rejects_a_junction_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target-directory"
            source = root / "source-junction"
            target.mkdir()
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(source), str(target)],
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode:
                self.skipTest(f"junction unavailable: {result.stderr or result.stdout}")

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(source, root / "output.bin")

            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertEqual({"relativePath": source.name}, raised.exception.details)


if __name__ == "__main__":
    unittest.main()
