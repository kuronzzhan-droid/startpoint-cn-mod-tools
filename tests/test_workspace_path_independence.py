from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import wf_asset_archive
import wf_assets
import wf_decrypt_all
import wf_device_paths
import wf_export_assets
import wf_recover_pathlist
import wf_rogue_save
import wf_voice


ROOT = Path(__file__).resolve().parents[1]


class WorkspacePathIndependenceTests(unittest.TestCase):
    def test_production_sources_do_not_embed_the_maintainers_wf_drive(self) -> None:
        files = (
            "API.md",
            "wf_assets.py", "wf_decrypt_all.py", "wf_export_assets.py", "wf_extract_paths.py",
            "wf_gui.html", "wf_gui.py",
            "wf_recover_pathlist.py", "wf_rogue_save.py", "wf_voice.py",
        )
        for name in files:
            with self.subTest(name=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertNotIn("D:\\WF", text)

    def test_voice_dump_default_is_checkout_local_and_override_remains_explicit(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual((ROOT / "voice-dump").resolve(), wf_assets.resolve_voice_dump())

    def test_ffmpeg_has_no_maintainer_workspace_fallback(self) -> None:
        with (
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(wf_voice.shutil, "which", return_value=None),
        ):
            self.assertIsNone(wf_voice.find_ffmpeg())

    def test_7zip_uses_explicit_or_system_locations_without_fixed_drive(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            seven = root / "7z.exe"
            seven.write_bytes(b"fixture")
            self.assertEqual(
                seven.resolve(),
                wf_asset_archive.find_7zip({"WF_7ZIP": str(seven)}, finder=lambda _name: None),
            )
            self.assertIsNone(wf_asset_archive.find_7zip({}, finder=lambda _name: None))

    def test_adb_uses_explicit_or_path_and_invalid_explicit_value_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            adb = Path(raw) / "adb.exe"
            adb.write_bytes(b"fixture")
            self.assertEqual(
                str(adb.resolve()),
                wf_device_paths.find_adb({"WF_ADB": str(adb)}, finder=lambda _name: None),
            )
            self.assertIsNone(wf_device_paths.find_adb({}, finder=lambda _name: None))
            with self.assertRaisesRegex(ValueError, "WF_ADB"):
                wf_device_paths.find_adb({"WF_ADB": "missing.exe"}, finder=lambda _name: None)

    def test_mumu_manager_is_optional_until_restart_is_requested(self) -> None:
        self.assertIsNone(wf_rogue_save.resolve_mumu_manager({}, finder=lambda _name: None))
        with mock.patch.object(wf_rogue_save, "resolve_mumu_manager", return_value=None), \
                mock.patch.object(wf_rogue_save.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "WF_MUMU_MANAGER"):
                wf_rogue_save.mumu_sh("echo ready")
            run.assert_not_called()

    def test_reverse_tool_parsers_require_explicit_workspace_inputs(self) -> None:
        parser_cases = (
            (wf_decrypt_all.build_parser(),
             ["--base", "base", "--pathlist", "paths", "--out", "out"]),
            (wf_export_assets.build_parser(), ["--base", "base", "--out", "out"]),
            (wf_recover_pathlist.build_parser(),
             ["--base", "base", "--pathlist", "paths", "--out", "out"]),
        )
        for parser, argv in parser_cases:
            with self.subTest(prog=parser.prog):
                args = parser.parse_args(argv)
                self.assertIsNone(args.bundle)
                self.assertFalse(getattr(args, "voice", None))


if __name__ == "__main__":
    unittest.main()
