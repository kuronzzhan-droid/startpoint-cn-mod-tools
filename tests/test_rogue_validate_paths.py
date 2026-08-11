# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MOD_TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD_TOOLS))

import wf_rogue_validate as validate  # noqa: E402


class RogueValidatePathCase(unittest.TestCase):
    def test_plain_import_does_not_require_client_patch_until_apk_validation(self) -> None:
        environment = os.environ.copy()
        environment.pop("WF_CLIENT_PATCH_DIR", None)
        environment["WF_SERVER_DIR"] = str(MOD_TOOLS / "missing-server")
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", "import wf_rogue_validate"],
            cwd=MOD_TOOLS,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(b"", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(0, result.returncode)

    def test_builder_loader_uses_resolved_client_patch_directory(self) -> None:
        module_name = "abyss_task8_release_builder"
        previous = sys.modules.pop(module_name, None)

        def restore_module() -> None:
            sys.modules.pop(module_name, None)
            if previous is not None:
                sys.modules[module_name] = previous

        self.addCleanup(restore_module)

        with tempfile.TemporaryDirectory() as td:
            client_patch = Path(td) / "client-patch"
            builder_path = client_patch / "abyss-mode-equipment" / "build_apk.py"
            builder_path.parent.mkdir(parents=True)
            builder_path.write_text("MARKER = 'resolved'\n", encoding="utf-8")
            with mock.patch.object(
                validate,
                "_resolve_client_patch_dir",
                return_value=client_patch,
            ) as resolver:
                builder = validate._load_task7_builder()

        self.assertEqual("resolved", builder.MARKER)
        resolver.assert_called_once_with()

    def test_explicit_client_patch_directory_wins_without_server_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            client_patch = Path(td) / "client-patch"
            client_patch.mkdir()
            with (
                mock.patch.dict(
                    os.environ,
                    {"WF_CLIENT_PATCH_DIR": str(client_patch)},
                    clear=False,
                ),
                mock.patch.object(
                    validate.core,
                    "resolve_server_dir",
                    side_effect=AssertionError("server fallback must not run"),
                ),
            ):
                self.assertEqual(
                    client_patch.resolve(), validate._resolve_client_patch_dir()
                )

    def test_absent_client_patch_uses_shared_server_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            server = Path(td) / "server"
            client_patch = server / "client-patch"
            client_patch.mkdir(parents=True)
            with (
                mock.patch.dict(os.environ, {}, clear=False),
                mock.patch.object(
                    validate.core, "resolve_server_dir", return_value=server
                ) as resolver,
            ):
                os.environ.pop("WF_CLIENT_PATCH_DIR", None)
                self.assertEqual(
                    client_patch.resolve(), validate._resolve_client_patch_dir()
                )
            resolver.assert_called_once_with()

    def test_invalid_explicit_client_patch_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file_path = root / "file"
            file_path.write_text("not a directory", encoding="utf-8")
            values = ("", "relative/client-patch", str(root / "missing"), str(file_path))
            for value in values:
                with (
                    self.subTest(value=value),
                    mock.patch.dict(
                        os.environ, {"WF_CLIENT_PATCH_DIR": value}, clear=False
                    ),
                    mock.patch.object(
                        validate.core,
                        "resolve_server_dir",
                        side_effect=AssertionError("invalid explicit path fell back"),
                    ),
                    self.assertRaisesRegex(ValueError, "WF_CLIENT_PATCH_DIR"),
                ):
                    validate._resolve_client_patch_dir()

    def test_missing_derived_client_patch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            server = Path(td) / "server"
            server.mkdir()
            with (
                mock.patch.dict(os.environ, {}, clear=False),
                mock.patch.object(
                    validate.core, "resolve_server_dir", return_value=server
                ),
            ):
                os.environ.pop("WF_CLIENT_PATCH_DIR", None)
                with self.assertRaisesRegex(ValueError, "client-patch"):
                    validate._resolve_client_patch_dir()


if __name__ == "__main__":
    unittest.main()
