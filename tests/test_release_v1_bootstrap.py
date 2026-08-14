"""First managed-target bootstrap phase ordering and recovery."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _target
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import load_active_state
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
)


SHA = "a" * 64
OPERATION_ID = "20260815T010203.000000Z-0123456789abcdef0123456789abcdef"


class FakePlatform:
    def __init__(self) -> None:
        self.current: ManagedProcess | None = None
        self.events: list[str] = []
        self.stop_error: ReleaseError | None = None

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def prepare_content(self, launch: LaunchSpec, environment) -> None:
        self.events.append("prepare")

    def start_server(
        self, launch: LaunchSpec, environment, operation_id: str
    ) -> ManagedProcess:
        self.events.append("start")
        self.current = ManagedProcess(201, 202, SHA, operation_id)
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("stop")
        if self.stop_error is not None:
            raise self.stop_error
        if process != self.current:
            raise AssertionError("bootstrap stopped a process it did not start")
        self.current = None
        return False


class BootstrapTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-bootstrap-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "modes",
                "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for root in roots.values():
            root.mkdir()
        self.target = ManagedTarget(
            server_bundle=roots["server"],
            runtime_pack=roots["runtime"],
            data_root=roots["data"],
            state_root=roots["state"],
            cdn_root=roots["cdn"],
            modes_root=roots["modes"],
            component_roots=ComponentRoots(
                roots["candidate-content"],
                roots["candidate-server"],
                roots["candidate-modes"],
            ),
            compatibility=TargetCompatibility("1.4.54", "1.4.346", True),
            server_url="http://127.0.0.1:8001",
        )
        self.launch = LaunchSpec(
            roots["runtime"] / "node/bin/node",
            roots["server"] / "out/content/sync/entry.js",
            roots["server"] / "out/cn-server.js",
            roots["server"],
        )
        self.facts = _target(cdn_target_version="1.4.346")

    def _run(self, platform: FakePlatform, facts: object | None = None):
        import wf_release_v1.bootstrap as bootstrap

        probe = SimpleNamespace(run=mock.Mock(
            side_effect=facts if isinstance(facts, BaseException) else None,
            return_value=self.facts if facts is None else facts,
        ))
        events = platform.events

        def wait_ready(url: str, timeout: float) -> None:
            self.assertEqual(self.target.health_url, url)
            events.append("health")

        with (
            mock.patch.object(bootstrap, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(bootstrap, "wait_health_ready", side_effect=wait_ready),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(ManagedTarget, "target_probe", return_value=probe),
        ):
            return bootstrap.bootstrap_target(
                self.target, platform, health_timeout=2.0
            )

    def test_prepares_starts_accepts_and_commits_empty_baseline(self) -> None:
        platform = FakePlatform()

        result = self._run(platform)

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual(self.facts, result.target_facts)
        self.assertEqual(
            ["current", "prepare", "start", "health", "current"],
            platform.events,
        )
        active = load_active_state(self.target.state_root)
        self.assertEqual("1.4.54", active.client_version)
        self.assertEqual("1.4.346", active.resource_baseline)
        self.assertTrue(active.client_patch_profile)
        self.assertEqual((), active.releases)
        self.assertEqual((), active.known_release_ids)
        self.assertTrue((self.target.state_root / "previous.json").is_file())

    def test_probe_failure_stops_only_the_process_started_by_bootstrap(self) -> None:
        platform = FakePlatform()
        failure = ReleaseError("WFREL_REQUIRE_TARGET", "probe failed")

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, failure)

        self.assertIs(failure, caught.exception)
        self.assertEqual(
            ["current", "prepare", "start", "health", "stop"],
            platform.events,
        )
        self.assertIsNone(platform.current)
        self.assertFalse((self.target.state_root / "active.json").exists())

    def test_rejects_live_content_version_that_disagrees_with_target_baseline(self) -> None:
        platform = FakePlatform()

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, _target(cdn_target_version="1.4.345"))

        self.assertEqual("WFREL_REQUIRE_TARGET", caught.exception.code)
        self.assertEqual("content.resourceBaseline", caught.exception.details["label"])
        self.assertEqual("stop", platform.events[-1])
        self.assertFalse((self.target.state_root / "active.json").exists())

    def test_recovery_failure_is_explicit_and_leaves_target_uncommitted(self) -> None:
        platform = FakePlatform()
        platform.stop_error = ReleaseError("WFREL_PROCESS_STOP", "stop failed")

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, ReleaseError("WFREL_REQUIRE_TARGET", "probe failed"))

        self.assertEqual("WFREL_RECOVERY_FAILED", caught.exception.code)
        self.assertFalse((self.target.state_root / "active.json").exists())

    def test_existing_state_or_managed_process_fails_before_prepare(self) -> None:
        import wf_release_v1.bootstrap as bootstrap

        for state_name in ("active.json", "previous.json"):
            with self.subTest(state=state_name):
                (self.target.state_root / state_name).write_text("sentinel", encoding="utf-8")
                platform = FakePlatform()
                with self.assertRaises(ReleaseError) as caught:
                    bootstrap.bootstrap_target(self.target, platform)
                self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
                self.assertEqual([], platform.events)
                (self.target.state_root / state_name).unlink()

        platform = FakePlatform()
        platform.current = ManagedProcess(99, 100, SHA, OPERATION_ID)
        with self.assertRaises(ReleaseError) as caught:
            bootstrap.bootstrap_target(self.target, platform)
        self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
        self.assertEqual(["current"], platform.events)


if __name__ == "__main__":
    unittest.main()
