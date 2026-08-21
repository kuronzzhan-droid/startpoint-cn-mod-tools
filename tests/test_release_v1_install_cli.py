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
from wf_release_v1._target_facts import target_facts_to_wire
from wf_release_v1.errors import ReleaseError
from wf_release_v1.transaction import InstallResult
from wf_release_v1.bootstrap import BootstrapResult
from wf_release_v1.rollback import RollbackResult
from wf_release_v1.resume import ResumeResult


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
            state_root=Path("C:/managed/state"),
            launch_spec=mock.Mock(return_value=SimpleNamespace(
                executable=Path("C:/managed/runtime/node.exe")
            )),
        )
        wire = {
            **target_facts_to_wire(facts),
            "blockers": [], "installable": True, "level": "modern",
            "probeVersion": 2, "targetProtocol": "capabilities-v1", "writesLive": False,
        }
        capability = SimpleNamespace(to_wire=mock.Mock(return_value=wire))
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target) as load,
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
            mock.patch.object(local_cli, "inspect_target_capability", return_value=capability),
        ):
            code, value, stream = self._run(
                "probe", "--target", "host-target.json", "--json"
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual({
            "arch", "bundleId", "capabilities", "cdnTargetVersion", "contentDigest",
            "dependencyLock", "modeDigest", "nodeAbi", "nodeVersion", "patchOverlaySchema",
            "platform", "releaseDigest", "runtimeApi", "runtimeId", "serverVersion", "blockers",
            "installable", "level", "probeVersion", "targetProtocol", "writesLive",
        }, set(value))
        self.assertEqual(list(facts.capabilities), value["capabilities"])
        self.assertIsNone(value["releaseDigest"])
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

    def test_bootstrap_requires_exact_confirmation_before_target_io(self) -> None:
        import wf_release_v1._local_cli as local_cli

        for confirmation in ("", "bootstrap_wf_target", "BOOTSTRAP_WF_TARGET "):
            with self.subTest(confirmation=confirmation), mock.patch.object(
                local_cli.ManagedTarget,
                "load",
                side_effect=AssertionError("target was read"),
            ):
                code, value, stream = self._run(
                    "bootstrap", "--target", "target.json", "--confirm", confirmation,
                )
                self.assertEqual((2, "stderr"), (code, stream))
                self.assertEqual("WFREL_CLI_ARGUMENTS", value["code"])

    def test_resume_requires_exact_confirmation_before_target_io(self) -> None:
        import wf_release_v1._local_cli as local_cli

        for confirmation in ("", "resume_wf_target", "RESUME_WF_TARGET "):
            with self.subTest(confirmation=confirmation), mock.patch.object(
                local_cli.ManagedTarget,
                "load",
                side_effect=AssertionError("target was read"),
            ):
                code, value, stream = self._run(
                    "resume", "--target", "target.json", "--confirm", confirmation,
                )
                self.assertEqual((2, "stderr"), (code, stream))
                self.assertEqual("WFREL_CLI_ARGUMENTS", value["code"])

    def test_resume_valid_confirmation_reaches_target_handler(self) -> None:
        import wf_release_v1._local_cli as local_cli

        with mock.patch.object(
            local_cli.ManagedTarget,
            "load",
            side_effect=ReleaseError("WFREL_REQUIRE_TARGET", "target unavailable"),
        ) as load:
            code, value, stream = self._run(
                "resume", "--target", "target.json", "--confirm", "RESUME_WF_TARGET",
            )

        self.assertEqual((20, "stderr"), (code, stream))
        self.assertEqual("WFREL_REQUIRE_TARGET", value["code"])
        load.assert_called_once_with(Path("target.json"))

    def test_resume_success_emits_only_path_free_target_facts(self) -> None:
        import wf_release_v1._local_cli as local_cli

        facts = _target(cdn_target_version="1.4.346")
        operation_id = "20260815T020304.000000Z-0123456789abcdef0123456789abcdef"
        secret = "admin-token-must-stay-process-only"
        launch = SimpleNamespace(executable=Path("C:/managed/runtime/node.exe"))
        target = SimpleNamespace(
            state_root=Path("C:/managed/state"),
            data_root=Path("C:/private/data"),
            cn_admin_token=secret,
            launch_spec=mock.Mock(return_value=launch),
        )
        adapter = object()
        result = ResumeResult("noop", operation_id, facts)

        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target) as load,
            mock.patch.object(
                local_cli, "WindowsPlatformAdapter", return_value=adapter,
            ) as create,
            mock.patch.object(local_cli, "resume_target", return_value=result) as resume,
        ):
            code, value, stream = self._run(
                "resume", "--target", "C:/private/target.json",
                "--confirm", "RESUME_WF_TARGET",
            )

        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual({
            "arch", "bundleId", "capabilities", "cdnTargetVersion", "contentDigest",
            "dependencyLock", "modeDigest", "nodeAbi", "nodeVersion", "operationId",
            "outcome", "patchOverlaySchema", "platform", "runtimeApi", "runtimeId",
            "releaseDigest", "serverVersion", "targetProtocol",
        }, set(value))
        self.assertEqual("noop", value["outcome"])
        self.assertEqual(operation_id, value["operationId"])
        self.assertEqual("capabilities-v1", value["targetProtocol"])
        self.assertIsNone(value["releaseDigest"])
        raw = json.dumps(value, sort_keys=True)
        self.assertNotIn("C:/private", raw)
        self.assertNotIn(secret, raw)
        load.assert_called_once_with(Path("C:/private/target.json"))
        create.assert_called_once_with(target.state_root, launch.executable)
        resume.assert_called_once_with(target, adapter)

    def test_bootstrap_constructs_adapter_without_a_preflight_live_probe(self) -> None:
        import wf_release_v1._local_cli as local_cli

        facts = _target(cdn_target_version="1.4.346")
        launch = SimpleNamespace(executable=Path("C:/managed/runtime/node.exe"))
        target = SimpleNamespace(
            state_root=Path("C:/managed/state"),
            launch_spec=mock.Mock(return_value=launch),
        )
        adapter = object()
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=adapter) as create,
            mock.patch.object(local_cli, "inspect_target_capability") as inspect,
            mock.patch.object(
                local_cli,
                "bootstrap_target",
                return_value=BootstrapResult("succeeded", facts),
            ) as bootstrap,
        ):
            code, value, stream = self._run(
                "bootstrap", "--target", "target.json",
                "--confirm", "BOOTSTRAP_WF_TARGET",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual("succeeded", value["outcome"])
        self.assertEqual("capabilities-v1", value["targetProtocol"])
        self.assertEqual("1.4.346", value["cdnTargetVersion"])
        self.assertNotIn("dataRoot", value)
        create.assert_called_once_with(target.state_root, launch.executable)
        bootstrap.assert_called_once_with(target, adapter)
        inspect.assert_not_called()

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
            mock.patch.object(
                local_cli, "inspect_target_capability",
                return_value=SimpleNamespace(level="modern"),
            ),
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
        install.assert_called_once_with(
            Path("release.zip"), target, adapter, enforce_target_protocol=True
        )

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
                mock.patch.object(
                    local_cli, "inspect_target_capability",
                    return_value=SimpleNamespace(level="modern"),
                ),
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

    def test_rollback_routes_operation_retry_and_explicit_previous_release(self) -> None:
        import wf_release_v1._local_cli as local_cli

        launch = SimpleNamespace(executable=Path("C:/managed/runtime/node.exe"))
        target = SimpleNamespace(
            state_root=Path("C:/managed/state"), launch_spec=mock.Mock(return_value=launch),
        )
        adapter = object()
        recovered = RollbackResult("recovery-op", "recovered", RELEASE_ID, None, False)
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=adapter),
            mock.patch.object(local_cli, "recover_failed_operation", return_value=recovered) as retry,
        ):
            code, value, stream = self._run(
                "rollback", "--target", "target.json", "--operation", "failed-op",
                "--confirm", "RECOVER_FAILED_INSTALL",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual("recovery-op", value["operationId"])
        self.assertFalse(value["dataCompatibilityGuaranteed"])
        retry.assert_called_once_with(target, adapter, "failed-op")

        previous = RollbackResult("rollback-op", "succeeded", RELEASE_ID, None, False)
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=adapter),
            mock.patch.object(local_cli, "rollback_to_previous", return_value=previous) as rollback,
        ):
            code, value, stream = self._run(
                "rollback", "--target", "target.json", "--to-release", RELEASE_ID,
                "--confirm", "I_UNDERSTAND_DATA_DOWNGRADE_RISK",
            )
        self.assertEqual((0, "stdout"), (code, stream))
        self.assertEqual("succeeded", value["outcome"])
        rollback.assert_called_once_with(target, adapter, RELEASE_ID)

    def test_rollback_rejects_ambiguous_mode_and_wrong_confirmation_before_io(self) -> None:
        import wf_release_v1._local_cli as local_cli

        cases = (
            (
                "--operation", "op", "--to-release", RELEASE_ID,
                "--confirm", "RECOVER_FAILED_INSTALL",
            ),
            ("--operation", "op", "--confirm", "I_UNDERSTAND_DATA_DOWNGRADE_RISK"),
            ("--to-release", RELEASE_ID, "--confirm", "RECOVER_FAILED_INSTALL"),
        )
        for suffix in cases:
            with self.subTest(suffix=suffix), mock.patch.object(
                local_cli.ManagedTarget, "load", side_effect=AssertionError("target was read")
            ):
                code, value, stream = self._run(
                    "rollback", "--target", "target.json", *suffix,
                )
            self.assertEqual((2, "stderr"), (code, stream))
            self.assertEqual("WFREL_CLI_ARGUMENTS", value["code"])


if __name__ == "__main__":
    unittest.main()
