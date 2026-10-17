"""Managed-target resume ordering, identity, and cleanup contracts."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _target
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1.compatibility import ActiveState
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import commit_active_state, operation_reservation
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
    TargetNetwork,
)
from wf_release_v1.target_capability import TargetCapability


SHA = "a" * 64
OPERATION_ID = "20260815T020304.000000Z-0123456789abcdef0123456789abcdef"
RUNNING_OPERATION_ID = "20260815T010203.000000Z-fedcba9876543210fedcba9876543210"


class FakePlatform:
    def __init__(self) -> None:
        self.current: ManagedProcess | None = None
        self.events: list[str] = []
        self.started: ManagedProcess | None = None
        self.launch: LaunchSpec | None = None
        self.environment = None
        self.stop_error: ReleaseError | None = None
        self.exit_confirmed = False
        self.process_state_missing = False

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def prepare_content(self, launch: LaunchSpec, environment) -> None:
        raise AssertionError("resume must not prepare or mutate content")

    def start_server(
        self, launch: LaunchSpec, environment, operation_id: str
    ) -> ManagedProcess:
        self.events.append("start")
        self.launch = launch
        self.environment = environment
        self.started = ManagedProcess(201, 202, SHA, operation_id)
        self.current = self.started
        return self.started

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("stop")
        if self.stop_error is not None:
            raise self.stop_error
        if process != self.started or process != self.current:
            raise AssertionError("resume stopped a process it did not start")
        self.current = None
        return False

    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("wait-exited")
        if process != self.started or timeout != 0.0:
            raise AssertionError("resume checked the wrong started process")
        if self.process_state_missing:
            raise ReleaseError(
                "WFREL_PROCESS_IDENTITY", "managed process state is unavailable"
            )
        if self.current is None:
            if self.exit_confirmed:
                return True
            raise ReleaseError(
                "WFREL_PROCESS_IDENTITY", "managed process identity is unavailable"
            )
        if self.current != process:
            raise ReleaseError(
                "WFREL_PROCESS_IDENTITY", "managed process identity changed"
            )
        return False


class ResumeTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-resume-")
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
        self.empty = ActiveState("1.4.54", "1.4.346", True, (), ())

    def _bootstrap_state(self) -> tuple[bytes, bytes]:
        commit_active_state(
            self.target.state_root,
            previous=self.empty,
            active=self.empty,
        )
        return (
            (self.target.state_root / "active.json").read_bytes(),
            (self.target.state_root / "previous.json").read_bytes(),
        )

    def _module(self):
        try:
            import wf_release_v1.resume as resume
        except ModuleNotFoundError:
            self.fail("managed-target resume behavior is unavailable")
        return resume

    def _run(
        self,
        platform: FakePlatform,
        *,
        capability: TargetCapability | BaseException | None = None,
        capability_hook=None,
        health_error: BaseException | None = None,
        unbound_error: BaseException | None = None,
        observation_hook=None,
        expected_http_port: int = 8001,
    ):
        resume = self._module()
        expected_capability = capability or TargetCapability(
            "modern",
            "capabilities-v1",
            True,
            (),
            _modern_facts=self.facts,
        )

        def require_local(host: str, *, label: str) -> None:
            if observation_hook is not None:
                observation_hook()
            self.assertEqual(("10.0.0.130", "network.publicHost"), (host, label))
            platform.events.append("public-address")

        def require_unbound(host: str, port: int, *, label: str) -> None:
            if observation_hook is not None:
                observation_hook()
            self.assertIn(
                (host, port, label),
                (
                    ("0.0.0.0", expected_http_port, "http"),
                    ("0.0.0.0", 8003, "session"),
                ),
            )
            platform.events.append(f"{label}-endpoint")
            if unbound_error is not None:
                raise unbound_error

        def wait_ready(url: str, timeout: float, **identity: object) -> None:
            if observation_hook is not None:
                observation_hook()
            current = platform.started or platform.current
            self.assertIsNotNone(current)
            self.assertEqual(self.target.health_url, url)
            self.assertEqual(2.0, timeout)
            self.assertEqual(
                {
                    "expected_operation_id": current.operation_id,
                    "expected_pid": current.pid,
                    "expected_bindings": {
                        "http": {
                            "host": "0.0.0.0", "port": expected_http_port,
                            "publicHost": "10.0.0.130",
                        },
                        "session": {
                            "host": "0.0.0.0", "port": 8003,
                            "publicHost": "10.0.0.130",
                        },
                        "cdnBaseUrl": (
                            f"http://10.0.0.130:{expected_http_port}/patch/cn"
                        ),
                    },
                },
                identity,
            )
            platform.events.append("health")
            if health_error is not None:
                raise health_error

        def inspect(target: ManagedTarget, adapter: object) -> TargetCapability:
            if observation_hook is not None:
                observation_hook()
            self.assertIs(self.target, target)
            self.assertIs(platform, adapter)
            platform.events.append("capability")
            if capability_hook is not None:
                capability_hook()
            if isinstance(expected_capability, BaseException):
                raise expected_capability
            return expected_capability

        with (
            mock.patch.object(resume, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(resume, "require_local_address", side_effect=require_local),
            mock.patch.object(
                resume, "require_tcp_endpoint_unbound", side_effect=require_unbound,
            ),
            mock.patch.object(resume, "wait_health_ready", side_effect=wait_ready),
            mock.patch.object(resume, "inspect_target_capability", side_effect=inspect),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
        ):
            return resume.resume_target(self.target, platform, health_timeout=2.0)

    def test_stopped_target_starts_without_preparing_or_mutating_content(self) -> None:
        before_active, before_previous = self._bootstrap_state()
        marker = self.target.data_root / "content-marker"
        marker.write_bytes(b"unchanged")
        platform = FakePlatform()

        result = self._run(platform)

        self.assertEqual(("succeeded", OPERATION_ID), (result.outcome, result.operation_id))
        self.assertEqual(self.facts, result.target_facts)
        self.assertEqual(
            [
                "current", "public-address", "http-endpoint", "session-endpoint",
                "start", "health", "capability", "current",
            ],
            platform.events,
        )
        self.assertEqual(self.launch, platform.launch)
        self.assertEqual(self.target.data_root, platform.environment.data_root)
        self.assertEqual(self.target.cdn_root, platform.environment.cdn_root)
        self.assertEqual(self.target.modes_root, platform.environment.modes_root)
        self.assertEqual(before_active, (self.target.state_root / "active.json").read_bytes())
        self.assertEqual(before_previous, (self.target.state_root / "previous.json").read_bytes())
        self.assertEqual(b"unchanged", marker.read_bytes())
        wire = result.to_wire()
        self.assertEqual("capabilities-v1", wire["targetProtocol"])
        self.assertEqual(OPERATION_ID, wire["operationId"])
        self.assertNotIn("dataRoot", wire)
        self.assertNotIn("serverBundle", wire)
        self.assertNotIn("CN_ADMIN_TOKEN", repr(wire))

    def test_stopped_target_uses_the_configured_http_port_for_bind_and_health(self) -> None:
        self.target = replace(
            self.target,
            server_url="http://127.0.0.1:8123",
        )
        self._bootstrap_state()
        platform = FakePlatform()

        result = self._run(platform, expected_http_port=8123)

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual(8123, platform.environment.listen_port)

    def test_running_owned_target_is_verified_and_returns_noop_without_restart(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()
        running = ManagedProcess(301, 302, SHA, RUNNING_OPERATION_ID)
        platform.current = running

        result = self._run(platform)

        self.assertEqual(("noop", OPERATION_ID, self.facts), (
            result.outcome, result.operation_id, result.target_facts,
        ))
        self.assertEqual(["current", "health", "capability", "current"], platform.events)
        self.assertIs(running, platform.current)
        self.assertIsNone(platform.started)

    def test_unbootstrapped_or_invalid_state_fails_before_process_or_network_reads(self) -> None:
        scenarios = ("missing", "missing-previous", "invalid-previous")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                if scenario != "missing":
                    self._bootstrap_state()
                    previous = self.target.state_root / "previous.json"
                    if scenario == "missing-previous":
                        previous.unlink()
                    else:
                        previous.write_bytes(b"not-json")
                platform = FakePlatform()

                with self.assertRaises(ReleaseError) as caught:
                    self._run(platform)

                self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
                self.assertEqual([], platform.events)
                self.assertFalse(
                    (self.target.state_root / ".wf-release-v1.operation").exists()
                )
                for name in ("active.json", "previous.json"):
                    path = self.target.state_root / name
                    if path.exists():
                        path.unlink()

    def test_state_process_and_network_are_observed_only_inside_reservation(self) -> None:
        self._bootstrap_state()
        resume = self._module()
        platform = FakePlatform()
        reserved = False
        real_active = resume.load_active_state
        real_previous = resume.load_previous_state

        @contextmanager
        def reservation(_root: Path, _operation_id: str):
            nonlocal reserved
            reserved = True
            try:
                yield
            finally:
                reserved = False

        def guarded(loader):
            def read(root: Path):
                self.assertTrue(reserved)
                return loader(root)
            return read

        def current_process() -> ManagedProcess | None:
            self.assertTrue(reserved)
            platform.events.append("current")
            return platform.current

        platform.current_process = current_process  # type: ignore[method-assign]
        with (
            mock.patch.object(resume, "operation_reservation", side_effect=reservation),
            mock.patch.object(resume, "load_active_state", side_effect=guarded(real_active)),
            mock.patch.object(resume, "load_previous_state", side_effect=guarded(real_previous)),
        ):
            self._run(platform, observation_hook=lambda: self.assertTrue(reserved))

    def test_concurrent_resume_is_rejected_before_process_or_network_reads(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()

        with operation_reservation(self.target.state_root, RUNNING_OPERATION_ID):
            with self.assertRaises(ReleaseError) as caught:
                self._run(platform)

        self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
        self.assertEqual([], platform.events)

    def test_running_noop_reservation_release_failure_never_stops_the_process(self) -> None:
        self._bootstrap_state()
        resume = self._module()
        platform = FakePlatform()
        running = ManagedProcess(301, 302, SHA, RUNNING_OPERATION_ID)
        platform.current = running
        release_error = ReleaseError("WFREL_STATE_IO", "reservation release failed")

        @contextmanager
        def fail_on_release(_root: Path, _operation_id: str):
            yield
            raise release_error

        with (
            mock.patch.object(resume, "operation_reservation", side_effect=fail_on_release),
            self.assertRaises(ReleaseError) as caught,
        ):
            self._run(platform)

        self.assertIs(release_error, caught.exception)
        self.assertIs(running, platform.current)
        self.assertNotIn("start", platform.events)
        self.assertNotIn("stop", platform.events)

    def test_started_target_reservation_release_failure_retains_evidence(self) -> None:
        self._bootstrap_state()
        resume = self._module()
        platform = FakePlatform()
        release_error = ReleaseError("WFREL_STATE_IO", "reservation release failed")

        @contextmanager
        def fail_on_release(_root: Path, _operation_id: str):
            yield
            raise release_error

        with (
            mock.patch.object(resume, "operation_reservation", side_effect=fail_on_release),
            self.assertRaises(ReleaseError) as caught,
        ):
            self._run(platform)

        self.assertEqual("WFREL_RECOVERY_FAILED", caught.exception.code)
        self.assertIs(release_error, caught.exception.__cause__)
        self.assertIs(platform.started, platform.current)
        self.assertNotIn("stop", platform.events)

    def test_foreign_listener_is_rejected_before_start(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()
        occupied = ReleaseError("WFREL_PROCESS_RUNNING", "endpoint occupied")

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, unbound_error=occupied)

        self.assertIs(occupied, caught.exception)
        self.assertEqual(["current", "public-address", "http-endpoint"], platform.events)
        self.assertIsNone(platform.started)

    def test_health_or_nonmodern_capability_failure_stops_only_started_process(self) -> None:
        cases = (
            ("health", ReleaseError("WFREL_REQUIRE_TARGET", "health failed"), None),
            (
                "capability",
                None,
                TargetCapability("legacy", "legacy", False, ("WFREL_REQUIRE_TARGET",)),
            ),
        )
        for name, health_error, capability in cases:
            with self.subTest(name=name):
                self._bootstrap_state()
                platform = FakePlatform()

                with self.assertRaises(ReleaseError) as caught:
                    self._run(
                        platform,
                        health_error=health_error,
                        capability=capability,
                    )

                self.assertEqual("WFREL_REQUIRE_TARGET", caught.exception.code)
                self.assertEqual("stop", platform.events[-1])
                self.assertIsNone(platform.current)
                for state_name in ("active.json", "previous.json"):
                    (self.target.state_root / state_name).unlink()

    def test_noncanonical_target_facts_are_rejected_and_started_process_is_stopped(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()
        bad_facts = _target(capabilities=("content.sync@1", "content.sync@1"))
        capability = TargetCapability(
            "modern", "capabilities-v1", True, (), _modern_facts=bad_facts,
        )

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, capability=capability)

        self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
        self.assertEqual("stop", platform.events[-1])

    def test_failure_cleanup_treats_exit_as_stopped_but_never_kills_identity_drift(self) -> None:
        original = ReleaseError("WFREL_REQUIRE_TARGET", "capability failed")
        for drifted in (False, True):
            with self.subTest(drifted=drifted):
                self._bootstrap_state()
                platform = FakePlatform()
                replacement = ManagedProcess(999, 1000, SHA, RUNNING_OPERATION_ID)

                def change_identity() -> None:
                    if drifted:
                        platform.current = replacement
                    else:
                        platform.exit_confirmed = True
                        platform.current = None

                with self.assertRaises(ReleaseError) as caught:
                    self._run(
                        platform,
                        capability=original,
                        capability_hook=change_identity,
                    )

                self.assertEqual(
                    "WFREL_RECOVERY_FAILED" if drifted else "WFREL_REQUIRE_TARGET",
                    caught.exception.code,
                )
                self.assertNotIn("stop", platform.events)
                if drifted:
                    self.assertIs(replacement, platform.current)
                for state_name in ("active.json", "previous.json"):
                    (self.target.state_root / state_name).unlink()

    def test_missing_process_state_is_not_mistaken_for_a_confirmed_exit(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()
        original = ReleaseError("WFREL_REQUIRE_TARGET", "capability failed")

        def lose_process_state() -> None:
            platform.process_state_missing = True
            platform.current = None

        with self.assertRaises(ReleaseError) as caught:
            self._run(
                platform,
                capability=original,
                capability_hook=lose_process_state,
            )

        self.assertEqual("WFREL_RECOVERY_FAILED", caught.exception.code)
        self.assertIsNotNone(platform.started)
        self.assertNotIn("stop", platform.events)

    def test_cleanup_failure_is_reported_as_recovery_failed(self) -> None:
        self._bootstrap_state()
        platform = FakePlatform()
        platform.stop_error = ReleaseError("WFREL_PROCESS_STOP", "stop failed")

        with self.assertRaises(ReleaseError) as caught:
            self._run(
                platform,
                health_error=ReleaseError("WFREL_REQUIRE_TARGET", "health failed"),
            )

        self.assertEqual("WFREL_RECOVERY_FAILED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
