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


class ReleaseCliTests(unittest.TestCase):
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

    def test_help_and_import_are_side_effect_free(self) -> None:
        imported = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", "import wf_release_v1.cli"],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, imported.returncode)
        self.assertEqual(b"", imported.stdout)
        self.assertEqual(b"", imported.stderr)

        for arguments in (("--help",), ("build", "--help"), ("verify", "--help"), ("inspect", "--help")):
            with self.subTest(arguments=arguments):
                result = self._run(*arguments)
                self.assertEqual(0, result.returncode)
                self.assertIn(b"usage:", result.stdout)
                self.assertEqual(b"", result.stderr)

    def test_argparse_failures_are_stable_single_line_json(self) -> None:
        for arguments in ((), ("unknown",), ("verify", "--release", "x.zip")):
            with self.subTest(arguments=arguments):
                result = self._run(*arguments)
                self._assert_safe_error(
                    result,
                    exit_code=2,
                    machine_code="WFREL_CLI_ARGUMENTS",
                )
                self.assertNotIn(b"usage:", result.stderr)

    def test_build_accepts_repeated_replacements_and_encodes_them(self) -> None:
        output = self.case_root / "replacement-release.zip"
        replaced = (
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
        )

        result = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(self.requirements),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.1.0",
            "--output",
            str(output),
            "--replaces",
            replaced[0],
            "--replaces",
            replaced[1],
        )

        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
        self.assertEqual(b"", result.stderr)
        with zipfile.ZipFile(output) as bundle:
            manifest = json.loads(
                bundle.read("wf-release-v1/release-manifest.json").decode("utf-8")
            )
        self.assertEqual(list(replaced), manifest["replaces"])

    def test_real_stdio_is_utf8_lf_under_hostile_default_encodings(self) -> None:
        unicode_release = self.case_root / "候选发行.zip"
        unicode_release.write_bytes(self.valid_release.read_bytes())
        for encoding in (None, "gbk", "utf-16", "cp1252"):
            for help_arguments in (
                ("--help",),
                ("build", "--help"),
                ("verify", "--help"),
                ("inspect", "--help"),
            ):
                with self.subTest(
                    encoding=encoding,
                    stream="help",
                    arguments=help_arguments,
                ):
                    help_result = self._run_with_encoding(
                        encoding, *help_arguments
                    )
                    self.assertEqual(0, help_result.returncode)
                    self.assertEqual(b"", help_result.stderr)
                    self.assertNotIn(b"\xff\xfe", help_result.stdout)
                    self.assertNotIn(b"\xfe\xff", help_result.stdout)
                    self.assertNotIn(b"\r\n", help_result.stdout)
                    help_text = help_result.stdout.decode("utf-8")
                    self.assertIn("usage:", help_text)

            with self.subTest(encoding=encoding, stream="success"):
                success = self._run_with_encoding(
                    encoding,
                    "verify",
                    "--release",
                    str(unicode_release),
                    "--json",
                )
                self.assertEqual(0, success.returncode)
                self.assertEqual(b"", success.stderr)
                success_value = json.loads(success.stdout.decode("utf-8"))
                self.assertEqual(
                    canonical_json_bytes(success_value),
                    success.stdout,
                )

            with self.subTest(encoding=encoding, stream="error"):
                failure = self._run_with_encoding(encoding)
                self.assertEqual(2, failure.returncode)
                self.assertEqual(b"", failure.stdout)
                failure_value = json.loads(failure.stderr.decode("utf-8"))
                self.assertEqual(
                    canonical_json_bytes(failure_value),
                    failure.stderr,
                )

    def test_closed_real_stdout_pipe_returns_clean_io_error_without_exit_120(self) -> None:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "wf_release_v1",
                "verify",
                "--release",
                str(self.valid_release),
                "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertIsNotNone(process.stdout)
        self.assertIsNotNone(process.stderr)
        process.stdout.close()  # type: ignore[union-attr]
        stderr = process.stderr.read()  # type: ignore[union-attr]
        process.stderr.close()  # type: ignore[union-attr]
        return_code = process.wait(timeout=30)

        self.assertEqual(30, return_code)
        value = json.loads(stderr.decode("utf-8"))
        self.assertEqual(
            {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
            value,
        )
        self.assertEqual(canonical_json_bytes(value), stderr)
        self.assertNotIn(b"Traceback", stderr)
        self.assertNotIn(str(self.root).encode("utf-8"), stderr)

    def test_closed_real_stdout_pipe_is_safe_for_every_help_command(self) -> None:
        for arguments in (
            ("--help",),
            ("build", "--help"),
            ("verify", "--help"),
            ("inspect", "--help"),
        ):
            with self.subTest(arguments=arguments):
                process = subprocess.Popen(
                    [sys.executable, "-m", "wf_release_v1", *arguments],
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertIsNotNone(process.stdout)
                self.assertIsNotNone(process.stderr)
                process.stdout.close()  # type: ignore[union-attr]
                stderr = process.stderr.read()  # type: ignore[union-attr]
                process.stderr.close()  # type: ignore[union-attr]
                return_code = process.wait(timeout=30)

                self.assertEqual(30, return_code)
                value = json.loads(stderr.decode("utf-8"))
                self.assertEqual(
                    {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
                    value,
                )
                self.assertEqual(canonical_json_bytes(value), stderr)
                self.assertNotIn(b"Traceback", stderr)
                self.assertNotIn(b"Exception ignored", stderr)

    def test_closed_real_stderr_pipe_on_argument_error_returns_30(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-m", "wf_release_v1"],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertIsNotNone(process.stdout)
        self.assertIsNotNone(process.stderr)
        process.stderr.close()  # type: ignore[union-attr]
        stdout = process.stdout.read()  # type: ignore[union-attr]
        process.stdout.close()  # type: ignore[union-attr]
        return_code = process.wait(timeout=30)

        self.assertEqual(30, return_code)
        self.assertEqual(b"", stdout)
        self.assertNotIn(b"Traceback", stdout)
        self.assertNotEqual(120, return_code)

    def test_parse_output_failures_return_30_but_healthy_systemexit_propagates(self) -> None:
        from wf_release_v1 import cli

        class HelpStream:
            def __init__(self, failure: str) -> None:
                self.failure = failure
                self.flushes = 0

            def write(self, value: str) -> int:
                if self.failure == "write-oserror":
                    raise OSError("private help path")
                return len(value)

            def flush(self) -> None:
                self.flushes += 1
                if self.failure == "flush-oserror" and self.flushes == 1:
                    raise OSError("private help path")
                if self.failure == "exit-flush-oserror" and self.flushes == 2:
                    raise OSError("private help path")

        for failure in ("write-oserror", "flush-oserror", "exit-flush-oserror"):
            with self.subTest(failure=failure):
                stdout = HelpStream(failure)
                stderr = io.StringIO()
                with patch.object(cli.sys, "stdout", stdout):
                    with redirect_stderr(stderr):
                        exit_code = cli.main(["--help"])
                self.assertEqual(30, exit_code)
                value = json.loads(stderr.getvalue())
                self.assertEqual(
                    {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
                    value,
                )
                self.assertNotIn("private", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

        healthy_stdout = io.StringIO()
        healthy_stderr = io.StringIO()
        with patch.object(cli.sys, "stdout", healthy_stdout):
            with patch.object(cli.sys, "stderr", healthy_stderr):
                with self.assertRaises(SystemExit) as help_exit:
                    cli.main(["--help"])
        self.assertEqual(0, help_exit.exception.code)
        self.assertIn("构建不可变发行物", healthy_stdout.getvalue())
        self.assertEqual("", healthy_stderr.getvalue())

        argument_stdout = io.StringIO()
        argument_stderr = io.StringIO()
        with patch.object(cli.sys, "stdout", argument_stdout):
            with patch.object(cli.sys, "stderr", argument_stderr):
                with self.assertRaises(SystemExit) as argument_exit:
                    cli.main([])
        self.assertEqual(2, argument_exit.exception.code)
        self.assertEqual("", argument_stdout.getvalue())
        self.assertEqual(
            {"code": "WFREL_CLI_ARGUMENTS", "message": "命令参数无效"},
            json.loads(argument_stderr.getvalue()),
        )

    def test_injected_binary_and_text_output_failures_map_to_io(self) -> None:
        from wf_release_v1 import cli

        class ScriptedBuffer:
            def __init__(self, failure: str) -> None:
                self.failure = failure

            def write(self, raw: bytes):
                if self.failure == "write-oserror":
                    raise OSError("private path")
                if self.failure == "write-none":
                    return None
                if self.failure == "write-short":
                    return len(raw) - 1
                return len(raw)

            def flush(self) -> None:
                if self.failure == "flush-oserror":
                    raise OSError("private path")

        class BinaryStream:
            def __init__(self, failure: str) -> None:
                self.buffer = ScriptedBuffer(failure)

        class TextStream:
            def __init__(self, failure: str) -> None:
                self.failure = failure

            def write(self, value: str):
                if self.failure == "write-oserror":
                    raise OSError("private path")
                if self.failure == "write-none":
                    return None
                if self.failure == "write-short":
                    return len(value) - 1
                return len(value)

            def flush(self) -> None:
                if self.failure == "flush-oserror":
                    raise OSError("private path")

        for stream_kind in (BinaryStream, TextStream):
            for failure in (
                "write-none",
                "write-short",
                "write-oserror",
                "flush-oserror",
            ):
                with self.subTest(stream=stream_kind.__name__, failure=failure):
                    stderr = io.StringIO()
                    with patch.object(cli.sys, "stdout", stream_kind(failure)):
                        with redirect_stderr(stderr):
                            exit_code = cli.main(
                                [
                                    "verify",
                                    "--release",
                                    str(self.valid_release),
                                    "--json",
                                ]
                            )
                    self.assertEqual(30, exit_code)
                    value = json.loads(stderr.getvalue())
                    self.assertEqual(
                        {"code": "WFREL_CLI_IO", "message": "本地执行失败"},
                        value,
                    )
                    self.assertNotIn("private", stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())

    def test_stderr_write_failure_is_suppressed_and_returns_io_exit(self) -> None:
        from wf_release_v1 import cli

        class FailingStderr:
            def write(self, value: str) -> int:
                del value
                raise OSError("private stderr path")

            def flush(self) -> None:
                raise OSError("private stderr path")

        stdout = io.StringIO()
        with patch.object(cli, "verify_release", side_effect=RuntimeError("private")):
            with patch.object(cli.sys, "stderr", FailingStderr()):
                with redirect_stdout(stdout):
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



if __name__ == "__main__":
    unittest.main()
