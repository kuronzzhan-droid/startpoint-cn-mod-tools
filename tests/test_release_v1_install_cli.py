"""Focused CLI contracts for local probe and install operations."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _target
from wf_release_v1 import cli
from wf_release_v1.transaction import InstallResult


RELEASE_ID = "sha256:" + "a" * 64


class LocalInstallCliTests(unittest.TestCase):
    def _run(self, *arguments: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = cli.main(list(arguments))
            except SystemExit as exit_signal:
                result = int(exit_signal.code)
        raw = stdout.getvalue() or stderr.getvalue()
        self.assertTrue(raw.endswith("\n"))
        self.assertEqual(1, raw.count("\n"))
        return result, json.loads(raw), "stdout" if stdout.getvalue() else "stderr"

    def test_probe_emits_only_top_level_verified_target_facts(self) -> None:
        import wf_release_v1._local_cli as local_cli

        facts = _target()
        target = SimpleNamespace(
            target_probe=mock.Mock(return_value=SimpleNamespace(run=mock.Mock(return_value=facts)))
        )
        with mock.patch.object(local_cli.ManagedTarget, "load", return_value=target) as load:
            code, value, stream = self._run(
                "probe", "--target", "host-target.json", "--json"
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual({
            "arch", "bundleId", "capabilities", "cdnTargetVersion", "contentDigest",
            "dependencyLock", "modeDigest", "nodeAbi", "nodeVersion", "patchOverlaySchema",
            "platform", "runtimeApi", "runtimeId", "serverVersion",
        }, set(value))
        self.assertEqual(list(facts.capabilities), value["capabilities"])
        self.assertNotIn("modes", value)
        self.assertNotIn("features", value)
        load.assert_called_once_with(Path("host-target.json"))

    def test_install_requires_exact_confirmation_before_target_or_release_io(self) -> None:
        import wf_release_v1._local_cli as local_cli

        for confirmation in ("", "install_wf_release", "INSTALL_WF_RELEASE "):
            with self.subTest(confirmation=confirmation), mock.patch.object(
                local_cli.ManagedTarget,
                "load",
                side_effect=AssertionError("target was read"),
            ):
                code, value, stream = self._run(
                    "install", "--target", "target.json", "--release", "release.zip",
                    "--confirm", confirmation,
                )
                self.assertEqual((2, "stderr"), (code, stream))
                self.assertEqual("WFREL_CLI_ARGUMENTS", value["code"])

    def test_install_constructs_one_target_owned_adapter_and_emits_result(self) -> None:
        import wf_release_v1._local_cli as local_cli

        launch = SimpleNamespace(executable=Path("C:/managed/runtime/node.exe"))
        target = SimpleNamespace(
            state_root=Path("C:/managed/state"),
            launch_spec=mock.Mock(return_value=launch),
        )
        adapter = object()
        result = InstallResult(RELEASE_ID, "operation-1", "succeeded", None, ())
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=adapter) as create,
            mock.patch.object(local_cli, "install_release", return_value=result) as install,
        ):
            code, value, stream = self._run(
                "install", "--target", "target.json", "--release", "release.zip",
                "--confirm", "INSTALL_WF_RELEASE",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual({
            "errorCode": None,
            "operationId": "operation-1",
            "outcome": "succeeded",
            "releaseId": RELEASE_ID,
            "warnings": [],
        }, value)
        create.assert_called_once_with(target.state_root, launch.executable)
        install.assert_called_once_with(Path("release.zip"), target, adapter)

    def test_recovered_and_recovery_failed_installs_use_transaction_exit_family(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/managed/state"),
            launch_spec=mock.Mock(return_value=SimpleNamespace(
                executable=Path("C:/managed/runtime/node.exe")
            )),
        )
        for outcome in ("recovered", "recovery_failed"):
            with (
                self.subTest(outcome=outcome),
                mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
                mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
                mock.patch.object(local_cli, "install_release", return_value=InstallResult(
                    RELEASE_ID, "operation-1", outcome, "WFREL_RECOVERY_FAILED", (),
                )),
            ):
                code, value, stream = self._run(
                    "install", "--target", "target.json", "--release", "release.zip",
                    "--confirm", "INSTALL_WF_RELEASE",
                )
                self.assertEqual((40, "stderr"), (code, stream))
                self.assertEqual("WFREL_RECOVERY_FAILED", value["code"])


if __name__ == "__main__":
    unittest.main()
