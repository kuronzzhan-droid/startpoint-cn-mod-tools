# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parents[1]
GUI_PATH = MOD_TOOLS / "wf_gui.py"
sys.path.insert(0, str(MOD_TOOLS))
try:
    import wf_mod_tool as core
finally:
    sys.path.remove(str(MOD_TOOLS))


def _load_gui() -> object:
    module_name = "_wf_gui_database_path_test"
    spec = importlib.util.spec_from_file_location(module_name, GUI_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GUI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(MOD_TOOLS))
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
        sys.path.remove(str(MOD_TOOLS))
    return module


class GuiDatabasePathTests(unittest.TestCase):
    def test_invalid_profile_store_is_reported_without_a_value_error_traceback(self) -> None:
        with mock.patch.object(
            core,
            "resolve_profile",
            side_effect=ValueError("profile store validation sentinel"),
        ), self.assertRaisesRegex(SystemExit, "profile store validation sentinel"):
            _load_gui()

    def test_store_resolution_uses_the_shared_core_chain(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target_store = root / "store"
            database_dir = root / "database"
            target_store.mkdir()
            database_dir.mkdir()
            with mock.patch.dict(
                os.environ,
                {
                    "WF_TARGET_STORE": str(target_store),
                    "WF_DATABASE_DIR": str(database_dir),
                },
                clear=False,
            ), mock.patch.object(
                core,
                "resolve_active_store",
                side_effect=ValueError("WF_TARGET_STORE shared resolver sentinel"),
            ), self.assertRaisesRegex(SystemExit, "shared resolver sentinel"):
                _load_gui()

    def test_explicit_database_directory_does_not_require_the_server_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target_store = root / "store"
            database_dir = root / "database"
            target_store.mkdir()
            database_dir.mkdir()
            environment = {
                "WF_TARGET_STORE": str(target_store),
                "WF_DATABASE_DIR": str(database_dir),
                "WF_SERVER_DIR": str(root / "missing-server"),
            }

            with mock.patch.dict(os.environ, environment, clear=False):
                gui = _load_gui()

            self.assertEqual(database_dir.resolve() / "wdfp_data.db", gui.SAVE_DB)
            self.assertFalse((root / "missing-server" / ".database").exists())

    def test_unset_database_directory_falls_back_to_the_resolved_server_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target_store = root / "store"
            server_root = root / "server"
            target_store.mkdir()
            server_root.mkdir()

            with mock.patch.dict(
                os.environ,
                {
                    "WF_TARGET_STORE": str(target_store),
                    "WF_SERVER_DIR": str(server_root),
                },
                clear=False,
            ):
                os.environ.pop("WF_DATABASE_DIR", None)
                gui = _load_gui()

            self.assertEqual(
                server_root.resolve() / ".database" / "wdfp_data.db",
                gui.SAVE_DB,
            )

    def test_invalid_explicit_database_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target_store = root / "store"
            target_store.mkdir()
            file_path = root / "not-a-directory"
            file_path.write_text("fixture", encoding="utf-8")

            for value in ("", "   ", "relative", str(root / "missing"), str(file_path)):
                with self.subTest(value=value), mock.patch.dict(
                    os.environ,
                    {
                        "WF_TARGET_STORE": str(target_store),
                        "WF_DATABASE_DIR": value,
                    },
                    clear=False,
                ), self.assertRaisesRegex(ValueError, "WF_DATABASE_DIR"):
                    _load_gui()


if __name__ == "__main__":
    unittest.main()
