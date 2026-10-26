"""Python 3.11 path checks must keep junction and symlink export boundaries."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_paths import is_junction


@contextmanager
def legacy_path_api():
    method = Path.__dict__.get("is_junction")
    if method is not None:
        delattr(Path, "is_junction")
    try:
        yield
    finally:
        if method is not None:
            setattr(Path, "is_junction", method)


class JunctionChecks(unittest.TestCase):
    def test_regular_and_missing_paths_work_without_new_pathlib_api(self):
        with tempfile.TemporaryDirectory() as temporary, legacy_path_api():
            root = Path(temporary)
            file = root / "file.txt"
            file.write_text("unchanged", encoding="utf8")
            for path in (root, file, root / "missing", file / "not-a-directory"):
                with self.subTest(path=path):
                    self.assertFalse(is_junction(path))

    def test_mount_point_reparse_tag_is_detected_without_new_pathlib_api(self):
        with legacy_path_api():
            for tag, expected in ((0xA0000003, True), (0xA000000C, False), (0, False)):
                with self.subTest(tag=tag), patch.object(Path, "lstat", return_value=SimpleNamespace(st_reparse_tag=tag)):
                    self.assertEqual(is_junction(Path("example")), expected)
            with patch.object(Path, "lstat", return_value=SimpleNamespace(st_mode=stat.S_IFDIR)):
                self.assertFalse(is_junction(Path("posix-directory")))

    def test_permission_errors_fail_closed(self):
        with patch.object(Path, "lstat", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                is_junction(Path("unreadable"))


class ExportLinkChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.target = self.root / "target"
        self.target.mkdir()
        (self.target / "keep.txt").write_text("untouched", encoding="utf8")
        self.site = self.root / "site"
        self.site.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.store = self.repo / "game/upload"
        self.store.mkdir(parents=True)

    def junction(self, path):
        if os.name != "nt":
            self.skipTest("Windows junction integration check")
        # Both paths are fixed children of this test's resolved temporary root.
        for item in (path, self.target):
            self.assertTrue(item.is_relative_to(self.root))
        quoted = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = ("$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path "
                   + quoted(path) + " -Target " + quoted(self.target) + " | Out-Null")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest("Runner cannot create a Windows junction")
        self.addCleanup(path.rmdir)  # Remove only the link before TemporaryDirectory cleanup.
        self.assertTrue(is_junction(path))
        self.assertFalse(path.is_symlink())
        return path

    def test_real_junction_is_rejected_by_export_read_and_write_guards(self):
        from wf_wiki import prepare_output
        from wf_wiki_data import regular
        from wf_wiki_dungeons import export_dungeons
        from wf_wiki_dungeons_gray import gray_quest_lookup
        from wf_wiki_pixel_output import checked_path

        link = self.junction(self.site / "media")
        with legacy_path_api():
            calls = (
                lambda: prepare_output(self.site, self.repo, self.store),
                lambda: regular(link),
                lambda: gray_quest_lookup(link),
                lambda: checked_path(link / "new-file.webp"),
                lambda: export_dungeons(self.repo, self.site, store=self.store),
            )
            for index, call in enumerate(calls):
                with self.subTest(guard=index), self.assertRaises(ValueError):
                    call()
        self.assertEqual([path.name for path in self.target.iterdir()], ["keep.txt"])
        self.assertEqual((self.target / "keep.txt").read_text(encoding="utf8"), "untouched")

    def test_real_junction_is_rejected_by_variant_writer(self):
        from wf_wiki_variants import write_character_variants

        self.junction(self.site / "data")
        source = Mock()
        source.table.return_value = {"1": [["example", *([""] * 26), "1"]]}
        with legacy_path_api(), patch("wf_wiki_catalog_source.WikiSource", return_value=source):
            with self.assertRaisesRegex(ValueError, "目录不能是链接"):
                write_character_variants(self.repo, self.site, {"characters": []}, self.store)
        self.assertEqual([path.name for path in self.target.iterdir()], ["keep.txt"])

    def test_symlink_boundary_still_rejects_missing_target(self):
        from wf_wiki_data import regular
        from wf_wiki_pixel_output import checked_path

        link = self.site / "dangling"
        try:
            link.symlink_to(self.root / "missing")
        except OSError:
            self.skipTest("Runner cannot create symlinks")
        with legacy_path_api():
            with self.assertRaises(ValueError):
                regular(link)
            with self.assertRaises(ValueError):
                checked_path(link)

    def test_symlink_rejection_remains_active_without_junction_api(self):
        from wf_wiki_data import regular
        from wf_wiki_pixel_output import checked_path

        with legacy_path_api(), patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(ValueError):
                regular(self.site / "link")
            with self.assertRaises(ValueError):
                checked_path(self.site / "link")


if __name__ == "__main__":
    unittest.main()
