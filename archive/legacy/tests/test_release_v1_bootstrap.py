"""First managed-target bootstrap phase ordering and recovery."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
import threading
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
    TargetNetwork,
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
            network=TargetNetwork("10.0.0.130"),
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

        side_effect = facts if isinstance(facts, BaseException) or callable(facts) else None
        probe = SimpleNamespace(run=mock.Mock(
            side_effect=side_effect,
            return_value=self.facts if facts is None or callable(facts) else facts,
        ))
        events = platform.events

        def require_local(host: str, *, label: str) -> None:
            self.assertEqual(("10.0.0.130", "network.publicHost"), (host, label))
            events.append("public-address")

        def require_tcp_unbound(host: str, port: int, *, label: str) -> None:
            self.assertIn(
                (host, port, label),
                (("0.0.0.0", 8001, "http"), ("0.0.0.0", 8003, "session")),
            )
            events.append(f"{label}-endpoint")

        def wait_ready(url: str, timeout: float, **identity: object) -> None:
            self.assertEqual(self.target.health_url, url)
            self.assertEqual(
                {
                    "expected_operation_id": OPERATION_ID,
                    "expected_pid": 201,
                    "expected_bindings": {
                        "http": {
                            "host": "0.0.0.0", "port": 8001,
                            "publicHost": "10.0.0.130",
                        },
                        "session": {
                            "host": "0.0.0.0", "port": 8003,
                            "publicHost": "10.0.0.130",
                        },
                        "cdnBaseUrl": "http://10.0.0.130:8001/patch/cn",
                    },
                },
                identity,
            )
            events.append("health")

        with (
            mock.patch.object(bootstrap, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(bootstrap, "require_local_address", side_effect=require_local),
            mock.patch.object(
                bootstrap,
                "require_tcp_endpoint_unbound",
                side_effect=require_tcp_unbound,
            ),
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
            [
                "current", "public-address", "http-endpoint", "session-endpoint", "prepare",
                "start", "health", "current",
            ],
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
            [
                "current", "public-address", "http-endpoint", "session-endpoint", "prepare",
                "start", "health", "current", "stop",
            ],
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

    def test_state_is_not_observed_before_the_bootstrap_reservation(self) -> None:
        import wf_release_v1.bootstrap as bootstrap

        reserved = False
        actual_exists = Path.exists
        guarded = {
            self.target.state_root / "active.json",
            self.target.state_root / "previous.json",
        }

        @contextmanager
        def reservation(_root: Path, _operation_id: str):
            nonlocal reserved
            reserved = True
            try:
                yield
            finally:
                reserved = False

        def exists(path: Path) -> bool:
            if path in guarded and not reserved:
                raise AssertionError("bootstrap observed mutable state before reservation")
            return actual_exists(path)

        with (
            mock.patch.object(bootstrap, "operation_reservation", side_effect=reservation),
            mock.patch.object(Path, "exists", side_effect=exists, autospec=True),
            mock.patch.object(bootstrap, "require_local_address"),
            mock.patch.object(bootstrap, "require_tcp_endpoint_unbound"),
            mock.patch.object(bootstrap, "wait_health_ready"),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(
                ManagedTarget,
                "target_probe",
                return_value=SimpleNamespace(run=mock.Mock(return_value=self.facts)),
            ),
        ):
            result = bootstrap.bootstrap_target(
                self.target, FakePlatform(), health_timeout=2.0
            )

        self.assertEqual("succeeded", result.outcome)

    def test_foreign_listener_fails_before_prepare(self) -> None:
        import wf_release_v1.bootstrap as bootstrap

        platform = FakePlatform()
        with (
            mock.patch.object(bootstrap, "require_local_address"),
            mock.patch.object(
                bootstrap,
                "require_tcp_endpoint_unbound",
                side_effect=ReleaseError("WFREL_PROCESS_RUNNING", "endpoint occupied"),
            ),
        ):
            with self.assertRaises(ReleaseError) as caught:
                bootstrap.bootstrap_target(self.target, platform)
        self.assertEqual("WFREL_PROCESS_RUNNING", caught.exception.code)
        self.assertEqual(["current"], platform.events)

    def test_concurrent_second_bootstrap_never_reaches_prepare(self) -> None:
        import wf_release_v1.bootstrap as bootstrap

        prepared = threading.Event()
        release_prepare = threading.Event()

        class BlockingPlatform(FakePlatform):
            def prepare_content(self, launch: LaunchSpec, environment) -> None:
                super().prepare_content(launch, environment)
                prepared.set()
                self.assert_release(release_prepare.wait(2.0))

            @staticmethod
            def assert_release(released: bool) -> None:
                if not released:
                    raise AssertionError("test did not release bootstrap prepare")

        platform = BlockingPlatform()
        probe = SimpleNamespace(run=mock.Mock(return_value=self.facts))
        first_error: list[BaseException] = []

        def first() -> None:
            try:
                bootstrap.bootstrap_target(self.target, platform, health_timeout=2.0)
            except BaseException as error:  # pragma: no cover - diagnostic capture
                first_error.append(error)

        with (
            mock.patch.object(bootstrap, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(bootstrap, "require_local_address"),
            mock.patch.object(bootstrap, "require_tcp_endpoint_unbound"),
            mock.patch.object(bootstrap, "wait_health_ready"),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(ManagedTarget, "target_probe", return_value=probe),
        ):
            worker = threading.Thread(target=first)
            worker.start()
            self.assertTrue(prepared.wait(2.0))
            with self.assertRaises(ReleaseError) as caught:
                bootstrap.bootstrap_target(self.target, platform, health_timeout=2.0)
            self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
            self.assertEqual(1, platform.events.count("prepare"))
            release_prepare.set()
            worker.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual([], first_error)

    def test_failed_bootstrap_does_not_stop_an_already_exited_or_drifted_process(self) -> None:
        for drifted in (False, True):
            with self.subTest(drifted=drifted):
                platform = FakePlatform()

                def fail_probe() -> None:
                    platform.current = (
                        ManagedProcess(999, 1000, SHA, OPERATION_ID)
                        if drifted else None
                    )
                    raise ReleaseError("WFREL_REQUIRE_TARGET", "probe failed")

                with self.assertRaises(ReleaseError) as caught:
                    self._run(platform, fail_probe)
                self.assertEqual(
                    "WFREL_RECOVERY_FAILED" if drifted else "WFREL_REQUIRE_TARGET",
                    caught.exception.code,
                )
                self.assertNotIn("stop", platform.events)


if __name__ == "__main__":
    unittest.main()
