# -*- coding: utf-8 -*-
"""Focused unit tests for root-aware three-character archive construction."""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_TOOLS = REPO_ROOT / "mod-tools"
MODULE_PATH = MOD_TOOLS / "build_three_char_release_patch.py"
pass  # Imports resolve from this checkout/package, not external source copies.

spec = importlib.util.spec_from_file_location("build_three_char_release_patch", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestBuildThreeCharReleasePatch(unittest.TestCase):
    def test_build_parts_preserves_common_medium_android_roots(self) -> None:
        rel_a = "aa/" + "1" * 38
        rel_b = "bb/" + "2" * 38
        rel_c = "cc/" + "3" * 38
        members = {
            ("common", rel_a): (b"common", "fixture"),
            ("medium", rel_b): (b"medium", "fixture"),
            ("android", rel_c): (b"android", "fixture"),
        }
        name, raw = module.build_parts(members, max_part_bytes=1024)[0]
        self.assertEqual(name, "pinball-1.4.106-1.4.107-1-threechar0719.zip")
        archive = zipfile.ZipFile(io.BytesIO(raw))
        self.assertEqual(set(archive.namelist()), {
            f"production/upload/{rel_a}",
            f"production/medium_upload/{rel_b}",
            f"production/android_upload/{rel_c}",
        })

    def test_parse_archive_member_rejects_unknown_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown archive root"):
            module.parse_archive_member("production/other/aa/" + "1" * 38)

    def test_build_parts_keeps_identical_relative_hashes_in_separate_roots(self) -> None:
        relative = "aa/" + "1" * 38
        members = {
            ("common", relative): (b"common", "fixture"),
            ("medium", relative): (b"medium", "fixture"),
        }
        _name, raw = module.build_parts(members, max_part_bytes=1024)[0]
        archive = zipfile.ZipFile(io.BytesIO(raw))
        self.assertEqual(
            set(archive.namelist()),
            {
                f"production/upload/{relative}",
                f"production/medium_upload/{relative}",
            },
        )

    def test_parse_archive_member_accepts_all_legal_roots(self) -> None:
        relative = "aa/" + "1" * 38
        self.assertEqual(
            [
                module.parse_archive_member(f"production/upload/{relative}"),
                module.parse_archive_member(f"production/medium_upload/{relative}"),
                module.parse_archive_member(f"production/android_upload/{relative}"),
            ],
            [("common", relative), ("medium", relative), ("android", relative)],
        )

    def test_official_table_bytes_reads_common_root_not_matching_suffix(self) -> None:
        relative = "aa/" + "1" * 38
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = Path(temporary) / "official.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(f"production/medium_upload/{relative}", b"medium")
                archive.writestr(f"production/upload/{relative}", b"common")
                archive.writestr(f"production/android_upload/{relative}", b"android")
            original = module.OFFICIAL_FULL
            module.OFFICIAL_FULL = archive_path
            try:
                self.assertEqual(module.official_table_bytes(relative), b"common")
            finally:
                module.OFFICIAL_FULL = original


if __name__ == "__main__":
    unittest.main()
