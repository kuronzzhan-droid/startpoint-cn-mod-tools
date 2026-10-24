"""Black-box contract tests for the wf-release-v1 command line interface."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tests.release_v1_fixtures import (
    make_patch_overlay,
    make_sealed_character_workspace,
)
from tests.release_v1_schema_support import requirements_wire
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.errors import ReleaseError
from wf_release_v1.producer import BuildRequest, build_character_release
from wf_release_v1.schema import parse_requirements


_RELEASE_ID = re.compile(r"sha256:[0-9a-f]{64}")


class ReleaseCliRequirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.workspace = make_sealed_character_workspace(cls.root / "workspace")
        cls.overlay = make_patch_overlay(
            cls.root / "sources" / "worldflipper-overlay-1.4.54-to-1.4.55.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        cls.requirements = cls.root / "requires.json"
        cls.requirements.write_bytes(canonical_json_bytes(requirements_wire()))
        cls.valid_release = cls.root / "valid.zip"
        build_character_release(
            BuildRequest(
                name="seris-dragon-king",
                version="1.0.0",
                workspace=cls.workspace,
                overlay_archives=(cls.overlay,),
                output=cls.valid_release,
                requirements=parse_requirements(requirements_wire()),
            )
        )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.case_root = Path(temporary.name)

    @staticmethod
    def _run(*arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "wf_release_v1", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    @staticmethod
    def _run_with_encoding(
        encoding: str | None, *arguments: str
    ) -> subprocess.CompletedProcess[bytes]:
        environment = os.environ.copy()
        if encoding is None:
            environment.pop("PYTHONIOENCODING", None)
        else:
            environment["PYTHONIOENCODING"] = encoding
        return subprocess.run(
            [sys.executable, "-m", "wf_release_v1", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _json_line(self, raw: bytes) -> dict[str, object]:
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(1, raw.count(b"\n"))
        value = json.loads(raw.decode("utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def _assert_safe_error(
        self,
        result: subprocess.CompletedProcess[bytes],
        *,
        exit_code: int,
        machine_code: str,
    ) -> dict[str, object]:
        self.assertEqual(exit_code, result.returncode)
        self.assertEqual(b"", result.stdout)
        value = self._json_line(result.stderr)
        self.assertEqual({"code", "message"}, set(value))
        self.assertEqual(machine_code, value["code"])
        self.assertRegex(str(value["message"]), r"[\u4e00-\u9fff]")
        rendered = result.stderr.decode("utf-8")
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn(str(self.case_root), rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("token", rendered.lower())
        return value

    def test_oversized_requirements_never_reach_the_producer(self) -> None:
        from wf_release_v1 import cli

        oversized = self.case_root / "oversized-requirements.json"
        oversized.write_bytes(b"x" * (1024 * 1024 + 1))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(
            cli,
            "build_character_release",
            side_effect=AssertionError("producer must not run"),
        ) as build:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "build",
                        "--workspace",
                        str(self.workspace),
                        "--overlay",
                        str(self.overlay),
                        "--requirements",
                        str(oversized),
                        "--name",
                        "seris-dragon-king",
                        "--version",
                        "1.0.0",
                        "--output",
                        str(self.case_root / "never.zip"),
                    ]
                )
        self.assertEqual(20, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("WFREL_REQUIRE_LIMIT", json.loads(stderr.getvalue())["code"])
        build.assert_not_called()

    def test_build_rejects_unsupported_overlay_requirement_as_incompatible(self) -> None:
        requirements = requirements_wire()
        requirements["patchOverlaySchema"] = 2
        requirements_path = self.case_root / "unsupported-requirements.json"
        requirements_path.write_bytes(canonical_json_bytes(requirements))
        output = self.case_root / "unsupported.zip"

        result = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(requirements_path),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.0",
            "--output",
            str(output),
        )

        self._assert_safe_error(
            result,
            exit_code=20,
            machine_code="WFREL_REQUIRE_UNSUPPORTED",
        )
        self.assertFalse(output.exists())

    def test_format_and_source_incompatibility_exit_codes_are_distinct(self) -> None:
        malformed = self.case_root / "malformed.zip"
        malformed.write_bytes(b"not a zip")
        bad_release = self._run(
            "inspect", "--release", str(malformed), "--json"
        )
        self._assert_safe_error(
            bad_release,
            exit_code=10,
            machine_code="WFREL_ARCHIVE_INVALID",
        )

        broken_workspace = make_sealed_character_workspace(
            self.case_root / "broken-workspace"
        )
        workspace_wire = json.loads(
            (broken_workspace / "workspace.json").read_text(encoding="utf-8")
        )
        workspace_wire["unexpected"] = True
        (broken_workspace / "workspace.json").write_text(
            json.dumps(workspace_wire) + "\n", encoding="utf-8"
        )
        source_failure = self._run(
            "build",
            "--workspace",
            str(broken_workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(self.requirements),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.0",
            "--output",
            str(self.case_root / "source-failure.zip"),
        )
        self._assert_safe_error(
            source_failure,
            exit_code=20,
            machine_code="WFREL_CHARACTER_SOURCE_INVALID",
        )

    def test_unknown_failures_and_keyboard_interrupt_do_not_escape(self) -> None:
        from wf_release_v1 import cli

        for failure in (RuntimeError("secret token at C:\\private"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch.object(cli, "verify_release", side_effect=failure):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        exit_code = cli.main(
                            [
                                "verify",
                                "--release",
                                str(self.valid_release),
                                "--json",
                            ]
                        )
                self.assertEqual(30, exit_code)
                self.assertEqual("", stdout.getvalue())
                value = json.loads(stderr.getvalue())
                self.assertEqual(
                    {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
                    value,
                )
                self.assertNotIn("private", stderr.getvalue())
                self.assertNotIn("token", stderr.getvalue().lower())

        for failure in (RuntimeError("parser secret"), KeyboardInterrupt()):
            with self.subTest(parser_failure=type(failure).__name__):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch.object(cli, "_parser", side_effect=failure):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        exit_code = cli.main([])
                self.assertEqual(30, exit_code)
                self.assertEqual("", stdout.getvalue())
                self.assertEqual(
                    {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
                    json.loads(stderr.getvalue()),
                )

        with patch.object(cli, "_parser", side_effect=SystemExit(2)):
            with self.assertRaises(SystemExit) as raised:
                cli.main([])
        self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
