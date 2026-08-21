"""CLI routing for modern, transition, and preparation-only legacy targets."""

from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from wf_release_v1 import cli
from wf_release_v1.errors import ReleaseError
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
        install.assert_called_once_with(
            Path("release.zip"),
            target,
            mock.ANY,
            enforce_target_protocol=True,
        )

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

    def test_write_routes_delegate_protocol_rejection_to_the_reserved_transaction(self) -> None:
        import wf_release_v1._local_cli as local_cli

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        cases = (
            ("install", "INSTALL_WF_RELEASE", "install_release"),
            ("install-legacy", "INSTALL_LEGACY_RELEASE", "install_legacy_release"),
        )
        for command, confirmation, transaction_name in cases:
            protocol_error = ReleaseError(
                "WFREL_TARGET_PROTOCOL", "injected reserved protocol rejection"
            )
            with (
                self.subTest(command=command),
                mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
                mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
                mock.patch.object(local_cli, "inspect_target_capability") as inspect,
                mock.patch.object(
                    local_cli, transaction_name, side_effect=protocol_error
                ) as transaction,
            ):
                code, wire, stream = self._run(
                    command, "--target", "target.json", "--release", "release.zip",
                    "--confirm", confirmation,
                )
            self.assertEqual((20, "stderr", "WFREL_TARGET_PROTOCOL"), (
                code, stream, wire["code"],
            ))
            transaction.assert_called_once_with(
                Path("release.zip"),
                target,
                mock.ANY,
                enforce_target_protocol=True,
            )
            inspect.assert_not_called()

    def test_compatibility_adapter_has_no_second_wire_schema_parser(self) -> None:
        import wf_release_v1

        root = Path(wf_release_v1.__file__).parent
        modules = (
            "target_protocol.py",
            "target_capability.py",
            "target_planning.py",
            "legacy_compatibility.py",
            "legacy_transaction.py",
            "legacy_rollback.py",
        )
        forbidden = {
            "json", "zipfile", "load_json_strict_bytes", "parse_ownership",
            "parse_release_manifest", "parse_requirements",
        }
        found: set[str] = set()
        for name in modules:
            tree = ast.parse((root / name).read_text("utf-8"), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    found.update(alias.name for alias in node.names)
                elif isinstance(node, ast.Name):
                    found.add(node.id)
        self.assertEqual(set(), forbidden & found)

    def test_legacy_rollback_has_its_own_confirmation_and_route(self) -> None:
        import wf_release_v1._local_cli as local_cli
        from wf_release_v1.rollback import RollbackResult

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        result = RollbackResult("rollback-op", "succeeded", RELEASE_ID, None, False)
        with (
            mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
            mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
            mock.patch.object(
                local_cli, "rollback_legacy_to_previous", return_value=result
            ) as rollback,
        ):
            code, wire, stream = self._run(
                "rollback-legacy", "--target", "target.json",
                "--to-release", RELEASE_ID,
                "--confirm", "ROLLBACK_LEGACY_RELEASE",
            )
        self.assertEqual((0, "stdout", "succeeded"), (code, stream, wire["outcome"]))
        rollback.assert_called_once_with(target, mock.ANY, RELEASE_ID)

        with mock.patch.object(
            local_cli.ManagedTarget, "load", side_effect=AssertionError("target read")
        ):
            code, wire, stream = self._run(
                "rollback-legacy", "--target", "target.json",
                "--to-release", RELEASE_ID,
                "--confirm", "I_UNDERSTAND_DATA_DOWNGRADE_RISK",
            )
        self.assertEqual((2, "stderr", "WFREL_CLI_ARGUMENTS"), (
            code, stream, wire["code"],
        ))

    def test_legacy_non_commit_outcomes_use_transaction_exit_family(self) -> None:
        import wf_release_v1._local_cli as local_cli
        from wf_release_v1.rollback import RollbackResult

        target = SimpleNamespace(
            state_root=Path("C:/state"),
            launch_spec=lambda: SimpleNamespace(executable=Path("C:/node.exe")),
        )
        cases = (
            (
                "install-legacy",
                ("--release", "release.zip", "--confirm", "INSTALL_LEGACY_RELEASE"),
                "install_legacy_release",
                InstallResult(RELEASE_ID, "install-op", "recovered", "WFREL_REQUIRE_TARGET", ()),
            ),
            (
                "rollback-legacy",
                ("--to-release", RELEASE_ID, "--confirm", "ROLLBACK_LEGACY_RELEASE"),
                "rollback_legacy_to_previous",
                RollbackResult("rollback-op", "recovered", RELEASE_ID, "WFREL_REQUIRE_TARGET", False),
            ),
        )
        for command, extra, function, result in cases:
            with (
                self.subTest(command=command),
                mock.patch.object(local_cli.ManagedTarget, "load", return_value=target),
                mock.patch.object(local_cli, "WindowsPlatformAdapter", return_value=object()),
                mock.patch.object(
                    local_cli, "inspect_target_capability",
                    return_value=SimpleNamespace(level="transition"),
                ),
                mock.patch.object(local_cli, function, return_value=result),
            ):
                code, wire, stream = self._run(
                    command, "--target", "target.json", *extra,
                )
            self.assertEqual((40, "stderr", "WFREL_TRANSACTION_NOT_COMMITTED"), (
                code, stream, wire["code"],
            ))


if __name__ == "__main__":
    unittest.main()
