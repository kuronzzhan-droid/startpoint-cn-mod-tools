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


class ReleaseCliOperationTests(unittest.TestCase):
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

    def test_verify_and_inspect_emit_only_verified_report_json(self) -> None:
        expected_keys = {"components", "fileCount", "payloadBytes", "releaseId"}
        reports: list[dict[str, object]] = []
        for command in ("verify", "inspect"):
            with self.subTest(command=command):
                result = self._run(
                    command,
                    "--release",
                    str(self.valid_release),
                    "--json",
                )
                self.assertEqual(0, result.returncode)
                self.assertEqual(b"", result.stderr)
                report = self._json_line(result.stdout)
                self.assertEqual(expected_keys, set(report))
                self.assertEqual(["content"], report["components"])
                self.assertEqual(1, report["fileCount"])
                self.assertGreater(report["payloadBytes"], 0)
                self.assertRegex(str(report["releaseId"]), _RELEASE_ID)
                reports.append(report)
        self.assertEqual(2, len(reports))
        if len(reports) == 2:
            self.assertEqual(reports[0], reports[1])

        corrupt = self.case_root / "corrupt-payload.zip"
        raw = bytearray(self.valid_release.read_bytes())
        with zipfile.ZipFile(self.valid_release) as bundle:
            payload = next(
                item for item in bundle.infolist() if "/content/" in item.filename
            )
        name_length, extra_length = struct.unpack_from(
            "<HH", raw, payload.header_offset + 26
        )
        payload_at = payload.header_offset + 30 + name_length + extra_length
        raw[payload_at] ^= 1
        corrupt.write_bytes(raw)
        rejected = self._run(
            "inspect", "--release", str(corrupt), "--json"
        )
        self._assert_safe_error(
            rejected,
            exit_code=10,
            machine_code="WFREL_ARCHIVE_INVALID",
        )

    def test_build_accepts_repeated_overlay_and_creates_only_new_output(self) -> None:
        overlay_two = make_patch_overlay(
            self.case_root / "sources" / "worldflipper-overlay-1.4.55-to-1.4.56.zip",
            from_version="1.4.55",
            target_version="1.4.56",
        )
        output = self.case_root / "release.zip"
        result = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--overlay",
            str(overlay_two),
            "--requirements",
            str(self.requirements),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.1",
            "--output",
            str(output),
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual(b"", result.stderr)
        receipt = self._json_line(result.stdout)
        self.assertEqual(
            {"archiveSha256", "bytesRead", "fileCount", "hashCount", "releaseId"},
            set(receipt),
        )
        self.assertRegex(str(receipt["releaseId"]), _RELEASE_ID)
        self.assertRegex(str(receipt["archiveSha256"]), r"[0-9a-f]{64}")
        self.assertEqual(2, receipt["fileCount"])
        self.assertEqual(2, receipt["hashCount"])
        self.assertGreater(receipt["bytesRead"], 0)
        self.assertTrue(output.is_file())

        before = output.read_bytes()
        repeated = self._run(
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
            "1.0.1",
            "--output",
            str(output),
        )
        self._assert_safe_error(
            repeated,
            exit_code=30,
            machine_code="WFREL_BUILD_OUTPUT_EXISTS",
        )
        self.assertEqual(before, output.read_bytes())

    def test_strict_requirements_and_missing_paths_use_stable_exit_families(self) -> None:
        duplicate = self.case_root / "duplicate.json"
        duplicate.write_bytes(b'{"schemaVersion":1,"schemaVersion":1}\n')
        invalid = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(duplicate),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.0",
            "--output",
            str(self.case_root / "invalid.zip"),
        )
        self._assert_safe_error(
            invalid,
            exit_code=10,
            machine_code="WFREL_JSON_DUPLICATE_KEY",
        )

        invalid_shape = self.case_root / "invalid-shape.json"
        invalid_wire = requirements_wire()
        invalid_wire["unexpected"] = True
        invalid_shape.write_bytes(canonical_json_bytes(invalid_wire))
        invalid_data = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(invalid_shape),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.0",
            "--output",
            str(self.case_root / "invalid-shape.zip"),
        )
        self._assert_safe_error(
            invalid_data,
            exit_code=10,
            machine_code="WFREL_SCHEMA_INVALID",
        )

        missing_requirements = self._run(
            "build",
            "--workspace",
            str(self.workspace),
            "--overlay",
            str(self.overlay),
            "--requirements",
            str(self.case_root / "missing.json"),
            "--name",
            "seris-dragon-king",
            "--version",
            "1.0.0",
            "--output",
            str(self.case_root / "missing.zip"),
        )
        self._assert_safe_error(
            missing_requirements,
            exit_code=30,
            machine_code="WFREL_CLI_IO",
        )

        missing_release = self._run(
            "verify",
            "--release",
            str(self.case_root / "missing-release.zip"),
            "--json",
        )
        self._assert_safe_error(
            missing_release,
            exit_code=30,
            machine_code="WFREL_ARCHIVE_INVALID",
        )

    def test_requirements_reader_rejects_open_descriptor_drift(self) -> None:
        from wf_release_v1 import cli

        actual_fstat = cli.os.fstat
        for drift in ("mtime", "growth"):
            with self.subTest(drift=drift):
                calls = 0

                def drifting_fstat(descriptor: int):
                    nonlocal calls
                    current = actual_fstat(descriptor)
                    calls += 1
                    if calls != 2:
                        return current
                    return SimpleNamespace(
                        st_dev=current.st_dev,
                        st_ino=current.st_ino,
                        st_size=current.st_size + (1 if drift == "growth" else 0),
                        st_mtime_ns=current.st_mtime_ns + 1,
                        st_mode=current.st_mode,
                        st_file_attributes=getattr(current, "st_file_attributes", 0),
                    )

                with patch.object(cli.os, "fstat", side_effect=drifting_fstat):
                    with self.assertRaisesRegex(ReleaseError, "WFREL_CLI_IO"):
                        cli._load_requirements(self.requirements)

    def test_requirements_reader_is_bounded_and_rejects_short_reads(self) -> None:
        from wf_release_v1 import cli

        oversized = self.case_root / "oversized-requirements.json"
        oversized.write_bytes(b"x" * (1024 * 1024 + 1))
        with self.assertRaises(ReleaseError) as too_large:
            cli._load_requirements(oversized)
        self.assertEqual("WFREL_REQUIRE_LIMIT", too_large.exception.code)

        actual_fdopen = cli.os.fdopen

        class ShortReader:
            def __init__(self, stream):
                self._stream = stream

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                self._stream.close()

            def read(self, size: int) -> bytes:
                raw = self._stream.read(size)
                return raw[:-1]

            def fileno(self) -> int:
                return self._stream.fileno()

        def short_fdopen(descriptor: int, *args, **kwargs):
            return ShortReader(actual_fdopen(descriptor, *args, **kwargs))

        with patch.object(cli.os, "fdopen", side_effect=short_fdopen):
            with self.assertRaises(ReleaseError) as short:
                cli._load_requirements(self.requirements)
        self.assertEqual("WFREL_CLI_IO", short.exception.code)



if __name__ == "__main__":
    unittest.main()
