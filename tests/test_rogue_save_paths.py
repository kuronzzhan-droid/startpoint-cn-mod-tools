# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parents[1]
if str(MOD_TOOLS) not in sys.path:
    sys.path.insert(0, str(MOD_TOOLS))

import wf_rogue_save as rogue_save  # noqa: E402


class RogueSavePathTests(unittest.TestCase):
    def test_explicit_database_directory_wins_when_legacy_root_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy_root = root / "missing-server"
            configured = root / "isolated-database"
            configured.mkdir()

            resolved = rogue_save.resolve_database_path(
                {"WF_DATABASE_DIR": str(configured)},
                server_root=legacy_root,
            )

            self.assertEqual(configured.resolve() / "wdfp_data.db", resolved)
            self.assertFalse((legacy_root / ".database").exists())

    def test_database_directory_defaults_to_server_root_only_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            self.assertEqual(
                root / ".database" / "wdfp_data.db",
                rogue_save.resolve_database_path({}, server_root=root),
            )

    def test_explicit_database_directory_rejects_blank_missing_and_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file_path = root / "not-a-directory"
            file_path.write_text("x", encoding="utf-8")
            for value in ("", "   ", str(root / "missing"), str(file_path)):
                with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "WF_DATABASE_DIR"
                ):
                    rogue_save.resolve_database_path(
                        {"WF_DATABASE_DIR": value},
                        server_root=root / "legacy",
                    )

    def test_explicit_mumu_manager_wins_when_legacy_executable_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manager = root / "MuMuManager.exe"
            manager.write_bytes(b"fixture")

            self.assertEqual(
                manager.resolve(),
                rogue_save.resolve_mumu_manager(
                    {"WF_MUMU_MANAGER": str(manager)},
                    finder=lambda _name: None,
                ),
            )

    def test_mumu_manager_is_optional_when_unset_and_not_on_path(self) -> None:
        self.assertIsNone(rogue_save.resolve_mumu_manager({}, finder=lambda _name: None))

    def test_explicit_mumu_manager_rejects_blank_missing_and_directory_values(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            directory = root / "directory"
            directory.mkdir()
            for value in ("", "   ", str(root / "missing.exe"), str(directory)):
                with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "WF_MUMU_MANAGER"
                ):
                    rogue_save.resolve_mumu_manager(
                        {"WF_MUMU_MANAGER": value},
                        finder=lambda _name: None,
                    )

    def test_explicit_paths_must_not_depend_on_the_process_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            relative_database = root / "relative-database"
            relative_database.mkdir()
            relative_manager = root / "relative-manager.exe"
            relative_manager.write_bytes(b"fixture")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(ValueError, "WF_DATABASE_DIR.*absolute"):
                    rogue_save.resolve_database_path(
                        {"WF_DATABASE_DIR": relative_database.name},
                        server_root=root / "legacy",
                    )
                with self.assertRaisesRegex(ValueError, "WF_MUMU_MANAGER.*absolute"):
                    rogue_save.resolve_mumu_manager(
                        {"WF_MUMU_MANAGER": relative_manager.name},
                        finder=lambda _name: None,
                    )
            finally:
                os.chdir(previous)

    def test_mumu_shell_uses_the_resolved_manager_without_starting_a_real_process(self) -> None:
        manager = Path("X:/configured/MuMuManager.exe")
        with (
            mock.patch.object(rogue_save, "resolve_mumu_manager", return_value=manager),
            mock.patch.object(rogue_save.subprocess, "run") as run,
        ):
            rogue_save.mumu_sh("echo ready")

        run.assert_called_once_with(
            [str(manager), "sh", "-v", "1", "-c", "echo ready"],
            capture_output=True,
        )

    def test_fresh_process_binds_module_constants_to_explicit_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            database = root / "database"
            database.mkdir()
            manager = root / "MuMuManager.exe"
            manager.write_bytes(b"fixture")
            environment = dict(os.environ)
            environment.update({
                "WF_DATABASE_DIR": str(database),
                "WF_MUMU_MANAGER": str(manager),
            })

            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-c",
                    "import json, os, wf_rogue_save as r; "
                    "print(json.dumps([r.DB_PATH, os.fspath(r.resolve_mumu_manager())]))",
                ],
                cwd=MOD_TOOLS,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(
                [str(database.resolve() / "wdfp_data.db"), str(manager.resolve())],
                json.loads(result.stdout),
            )


if __name__ == "__main__":
    unittest.main()
