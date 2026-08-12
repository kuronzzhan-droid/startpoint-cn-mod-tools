"""CLI routing for modern, transition, and preparation-only legacy targets."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from wf_release_v1 import cli
from wf_release_v1.legacy_compatibility import LegacyInstallPlan
from wf_release_v1.transaction import InstallResult


RELEASE_ID = "sha256:" + "a" * 64


class LegacyCliTests(unittest.TestCase):
    def _run(self, *arguments: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = cli.main(list(arguments))
            except SystemExit as signal:
                result = int(signal.code)
        raw = stdout.getvalue() or stderr.getvalue()
        self.assertEqual(1, raw.count("\n"))
        return result, json.loads(raw), "stdout" if stdout.getvalue() else "stderr"

    def test_probe_emits_versioned_capability_level_without_absolute_paths(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/private/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/private/node.exe")),
        )
        capability = SimpleNamespace(to_wire=lambda: {
            "blockers": ["WFREL_LEGACY_PROCESS_NOT_OWNED"],
            "installable": False,
            "level": "legacy",
            "probeVersion": 2,
            "targetProtocol": "legacy",
            "writesLive": False,
        })
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
            mock.patch.object(local_cli, "inspect_target_capability", return_value=capability),
        ):
            code, wire, stream = self._run(
                "probe", "--target", "target.json", "--json"
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual("legacy", wire["level"])
        self.assertNotIn("C:/private", json.dumps(wire))

    def test_plan_install_routes_through_unified_read_only_planner(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        plan = SimpleNamespace(to_wire=lambda: {
            "installable": False,
            "previewOnly": True,
            "targetProtocol": "legacy",
            "writesLive": False,
        })
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
            mock.patch.object(local_cli, "plan_target_install", return_value=plan) as route,
        ):
            code, wire, stream = self._run(
                "plan-install", "--target", "target.json", "--release", "release.zip",
                "--json",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertFalse(wire["writesLive"])
        route.assert_called_once_with(Path("release.zip"), target, mock.ANY)

    def test_legacy_install_uses_distinct_confirmation_and_transition_only(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        transition = SimpleNamespace(level="transition")
        result = InstallResult(RELEASE_ID, "operation", "succeeded", None, ())
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
            mock.patch.object(local_cli, "inspect_target_capability", return_value=transition),
            mock.patch.object(local_cli, "install_legacy_release", return_value=result) as install,
        ):
            code, wire, stream = self._run(
                "install-legacy", "--target", "target.json", "--release", "release.zip",
                "--confirm", "INSTALL_LEGACY_RELEASE",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual("succeeded", wire["outcome"])
        install.assert_called_once_with(Path("release.zip"), target, mock.ANY)

        for wrong in ("INSTALL_WF_RELEASE", "install_legacy_release", ""):
            with self.subTest(wrong=wrong), mock.patch.object(
                local_cli.ManagedTarget, "load", side_effect=AssertionError("target read")
            ):
                code, wire, stream = self._run(
                    "install-legacy", "--target", "target.json", "--release", "release.zip",
                    "--confirm", wrong,
                )
            self.assertEqual((2, "stderr", "WFREL_CLI_ARGUMENTS"), (
                code, stream, wire["code"],
            ))

    def test_write_routes_reject_the_other_protocol_before_transaction(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        cases = (
            ("install", "legacy", "INSTALL_WF_RELEASE"),
            ("install-legacy", "modern", "INSTALL_LEGACY_RELEASE"),
            ("install-legacy", "legacy", "INSTALL_LEGACY_RELEASE"),
        )
        for command, level, confirmation in cases:
            with (
                self.subTest(command=command, level=level),
                mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
                mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
                mock.patch.object(
                    local_cli, "inspect_target_capability", return_value=SimpleNamespace(level=level)
                ),
                mock.patch.object(
                    local_cli, "install_release", side_effect=AssertionError("modern write")
                ),
                mock.patch.object(
                    local_cli, "install_legacy_release", side_effect=AssertionError("legacy write")
                ),
            ):
                code, wire, stream = self._run(
                    command, "--target", "target.json", "--release", "release.zip",
                    "--confirm", confirmation,
                )
            self.assertEqual((20, "stderr", "WFREL_TARGET_PROTOCOL"), (
                code, stream, wire["code"],
            ))


if __name__ == "__main__":
    unittest.main()
