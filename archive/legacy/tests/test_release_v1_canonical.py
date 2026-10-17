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


def _nested_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _nested_strings(key)
            yield from _nested_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _nested_strings(item)


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

    def test_rejects_lone_surrogates_before_canonical_round_trip(self) -> None:
        raw = b'"\\ud800"'
        self.assert_release_error(
            "WFREL_JSON_VALUE",
            lambda: load_json_strict_bytes(raw, label="manifest"),
        )
        self.assert_release_error(
            "WFREL_JSON_VALUE",
            lambda: canonical_json_bytes("\ud800"),
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
                self.assertEqual({"field": "relativePath"}, raised.exception.details)

    def test_rejects_ascii_control_characters(self) -> None:
        for value in (
            "line\nfeed.json",
            "carriage\r\nreturn.json",
            "tab\tcharacter.json",
            "control\x01character.json",
            "delete\x7fcharacter.json",
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ReleaseError) as raised:
                    normalize_relative_path(value)
                self.assertEqual("WFREL_PATH_INVALID", raised.exception.code)
                self.assertEqual({"field": "relativePath"}, raised.exception.details)

    def test_redacts_untrusted_invalid_paths_from_errors(self) -> None:
        rejected = (
            r"C:\Users\Alice\secret.json",
            "C:/Users/Alice/secret.json",
            r"\\server\share\secret.json",
            "/Users/Alice/secret.json",
            "C:secret.json",
        )
        for value in rejected:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ReleaseError) as raised:
                    normalize_relative_path(value)
                error = raised.exception
                self.assertEqual("WFREL_PATH_INVALID", error.code)
                self.assertEqual({"field": "relativePath"}, error.details)

                rendered = [str(error), *_nested_strings(error.details)]
                forbidden = (value, "Alice", "secret", "Users", "server", "share")
                for text in rendered:
                    for fragment in forbidden:
                        self.assertNotIn(fragment, text)


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

    def test_rejects_opened_source_replacement_even_when_path_is_restored(self) -> None:
        """Exercise an actual rename race without mocks or fake file handles."""
        original = b"original source bytes"
        replacement = b"replacement source bytes"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            alternate = root / "alternate.bin"
            parked = root / "parked.bin"
            destination = root / "destination.bin"
            source.write_bytes(original)
            alternate.write_bytes(replacement)
            did_replace = False

            class ReplacingPath(type(Path())):
                def open(self, *args, **kwargs):
                    nonlocal did_replace
                    if not did_replace:
                        did_replace = True
                        os.replace(source, parked)
                        os.replace(alternate, source)
                        if os.name == "nt":
                            import ctypes
                            import msvcrt

                            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                            kernel32.CreateFileW.restype = ctypes.c_void_p
                            handle = kernel32.CreateFileW(
                                str(self),
                                0x80000000,
                                0x00000007,
                                None,
                                3,
                                0x00000080,
                                None,
                            )
                            if handle == ctypes.c_void_p(-1).value:
                                raise ctypes.WinError(ctypes.get_last_error())
                            descriptor = msvcrt.open_osfhandle(
                                handle, os.O_RDONLY | os.O_BINARY
                            )
                            opened = os.fdopen(descriptor, "rb")
                        else:
                            opened = super().open(*args, **kwargs)
                        os.replace(source, alternate)
                        os.replace(parked, source)
                        return opened
                    return super().open(*args, **kwargs)

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(ReplacingPath(source), destination)

            self.assertTrue(did_replace)
            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertEqual(original, source.read_bytes())
            self.assertFalse(destination.exists())

    def test_rejects_same_file_destination_before_any_write(self) -> None:
        payload = b"must not be truncated"
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.bin"
            source.write_bytes(payload)

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(source, source)

            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertEqual(payload, source.read_bytes())

    def test_rejects_hardlink_destination_before_any_write(self) -> None:
        payload = b"hardlink must not be truncated"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            destination = root / "source-alias.bin"
            source.write_bytes(payload)
            try:
                os.link(source, destination)
            except OSError as error:
                self.skipTest(f"hardlink unavailable: {error}")

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(source, destination)

            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertEqual(payload, source.read_bytes())
            self.assertEqual(payload, destination.read_bytes())

    def test_rejects_destination_replacement_before_open_without_writes(self) -> None:
        source_payload = b"source payload"
        destination_payload = b"original destination"
        victim_payload = b"unrelated victim"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            destination = root / "destination.bin"
            parked_destination = root / "parked-destination.bin"
            victim = root / "victim.bin"
            source.write_bytes(source_payload)
            destination.write_bytes(destination_payload)
            victim.write_bytes(victim_payload)
            did_replace = False

            class ReplacingDestination(type(Path())):
                def lstat(self):
                    nonlocal did_replace
                    snapshot = super().lstat()
                    if not did_replace:
                        did_replace = True
                        os.replace(destination, parked_destination)
                        os.link(victim, destination)
                    return snapshot

            with self.assertRaises(ReleaseError) as raised:
                stream_copy_and_hash_stable_file(
                    source, ReplacingDestination(destination)
                )

            self.assertTrue(did_replace)
            self.assertEqual("WFREL_HASH_SOURCE_CHANGED", raised.exception.code)
            self.assertEqual(source_payload, source.read_bytes())
            self.assertEqual(destination_payload, parked_destination.read_bytes())
            self.assertEqual(victim_payload, victim.read_bytes())
            self.assertEqual(victim_payload, destination.read_bytes())

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
