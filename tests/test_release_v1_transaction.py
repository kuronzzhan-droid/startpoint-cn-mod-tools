"""Install phase-machine and pre-acceptance recovery contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _active, _target, _verified
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1._target_facts import target_facts_from_wire, target_facts_to_wire
from wf_release_v1.canonical import FileIdentity
from wf_release_v1.compatibility import ActiveRelease
from wf_release_v1.errors import ReleaseError
from wf_release_v1.materialize import CandidateSet, StoredObject
from wf_release_v1.receipts import (
    commit_active_state,
    load_active_state,
    write_phase_receipt as persist_phase_receipt,
)
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
)
from wf_release_v1.transaction import InstallResult, install_release


OPERATION_ID = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"
SHA = "a" * 64


def _process(pid: int = 100) -> ManagedProcess:
    return ManagedProcess(pid, pid * 100, SHA, OPERATION_ID)


@dataclass
class FakeProbe:
    values: list[object]

    def run(self):
        if not self.values:
            raise AssertionError("probe called more often than expected")
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class FakePlatform:
    def __init__(self, current: ManagedProcess | None = None) -> None:
        self.current = current
        self.events: list[str] = []
        self.next_pid = 200
        self.fail_prepare: ReleaseError | None = None

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("stop")
        if process != self.current:
            raise AssertionError("transaction stopped an unowned process")
        self.current = None
        return False

    def prepare_content(self, launch: LaunchSpec, environment) -> None:
        self.events.append("prepare")
        if self.fail_prepare is not None:
            raise self.fail_prepare
        pointer = environment.data_root / "state" / "content" / "current.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_bytes(b'{"candidate":true}\n')

    def start_server(self, launch: LaunchSpec, environment, operation_id: str) -> ManagedProcess:
        self.events.append("start")
        self.next_pid += 1
        self.current = _process(self.next_pid)
        return self.current

    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("wait")
        return self.current != process


class TransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-transaction-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server-bundle", "runtime-pack", "data", "state", "active-cdn",
                "active-modes", "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for root in roots.values():
            root.mkdir()
        self.pointer = roots["data"] / "state" / "content" / "current.json"
        self.pointer.parent.mkdir(parents=True)
        self.pointer.write_bytes(b'{"baseline":true}\n')
        (roots["active-cdn"] / "cn").mkdir()
        (roots["active-cdn"] / "cn" / "official.bin").write_bytes(b"official")
        self.target = ManagedTarget(
            server_bundle=roots["server-bundle"], runtime_pack=roots["runtime-pack"],
            data_root=roots["data"], state_root=roots["state"],
            cdn_root=roots["active-cdn"], modes_root=roots["active-modes"],
            component_roots=ComponentRoots(
                roots["candidate-content"], roots["candidate-server"], roots["candidate-modes"]
            ),
            compatibility=TargetCompatibility("1.4.54", "1.4.53", True),
            server_url="http://127.0.0.1:8001",
        )
        self.release = self.root / "release.zip"
        self.release.write_bytes(b"fixture")
        self.verified = _verified()
        self.release_id = self.verified.manifest.release_id
        object_root = self.target.state_root / "objects" / self.release_id.replace(":", "-")
        object_root.mkdir(parents=True)
        archive = object_root / "release.wf-release.zip"
        archive.write_bytes(b"object")
        self.stored = StoredObject(self.release_id, archive, FileIdentity(6, SHA))
        candidate_root = self.target.component_roots.content / self.release_id.replace(":", "-")
        overlay = candidate_root / "patches" / "1.4.54" / "overlay.zip"
        overlay.parent.mkdir(parents=True)
        overlay.write_bytes(b"overlay")
        self.candidates = CandidateSet(
            self.release_id, candidate_root, None, None,
            (FileIdentity(7, SHA),), ("patches/1.4.54/overlay.zip",),
        )
        self.launch = LaunchSpec(
            self.target.runtime_pack / "node.exe",
            self.target.server_bundle / "prepare.js",
            self.target.server_bundle / "server.js",
            self.target.server_bundle,
        )
        self.before = _target(cdn_target_version="1.4.53")
        self.after = _target(cdn_target_version="1.4.54")
        self.phases: list[str] = []

    def _receipt(self) -> dict[str, object]:
        path = self.target.state_root / "receipts" / f"{OPERATION_ID}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _run(
        self,
        platform: FakePlatform,
        probes: list[object],
        *,
        materialize: object | None = None,
        receipt_failure_phase: str | None = None,
    ) -> InstallResult:
        import wf_release_v1.transaction as transaction

        probe = FakeProbe(probes)
        receipt_failed = False

        def record_receipt(root: Path, receipt) -> None:
            nonlocal receipt_failed
            self.phases.append(receipt.phase)
            if receipt.phase == receipt_failure_phase and not receipt_failed:
                receipt_failed = True
                raise ReleaseError("WFREL_STATE_IO", "injected receipt failure")
            persist_phase_receipt(root, receipt)

        with (
            mock.patch.object(transaction, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(transaction, "verify_release", return_value=SimpleNamespace(
                release_id=self.release_id,
            )),
            mock.patch.object(transaction, "import_verified_object", return_value=self.stored),
            mock.patch.object(transaction, "load_verified_release", return_value=self.verified),
            mock.patch.object(
                transaction,
                "materialize_candidates",
                return_value=self.candidates if materialize is None else mock.DEFAULT,
                side_effect=materialize if isinstance(materialize, BaseException) else None,
            ),
            mock.patch.object(transaction, "verify_candidates"),
            mock.patch.object(transaction, "wait_health_ready"),
            mock.patch.object(transaction, "write_phase_receipt", side_effect=record_receipt),
            mock.patch.object(ManagedTarget, "target_probe", return_value=probe),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
        ):
            return install_release(self.release, self.target, platform, health_timeout=2.0)

    def test_first_install_records_bootstrap_and_commits_only_after_double_acceptance(self) -> None:
        platform = FakePlatform()
        result = self._run(platform, [self.before, self.after])

        self.assertEqual(InstallResult(
            release_id=self.release_id, operation_id=OPERATION_ID,
            outcome="succeeded", error_code=None, warnings=(),
        ), result)
        self.assertEqual("succeeded", self._receipt()["outcome"])
        self.assertEqual("COMMITTED", self._receipt()["phase"])
        self.assertEqual([
            "CREATED", "VERIFIED", "BASE_STARTED", "PROBED", "STOPPED",
            "MATERIALIZED", "SWITCHED", "STARTED", "HEALTH_READY",
            "CAPABILITIES_ACCEPTED", "COMMITTED",
        ], self.phases)
        active = load_active_state(self.target.state_root)
        self.assertEqual((self.release_id,), tuple(item.release_id for item in active.releases))
        self.assertEqual((self.release_id,), active.known_release_ids)
        self.assertEqual(b"official", (self.target.cdn_root / "cn" / "official.bin").read_bytes())
        self.assertEqual(b"overlay", (
            self.target.cdn_root / "patches" / "1.4.54" / "overlay.zip"
        ).read_bytes())
        staging = self.target.state_root / "staging" / OPERATION_ID
        self.assertEqual(b"1.4.54\n", (staging / "content-target-version.txt").read_bytes())
        witness = json.loads((staging / "baseline-target-facts.json").read_text(encoding="utf-8"))
        self.assertEqual(self.before.content_digest, witness["contentDigest"])
        self.assertEqual(self.before.cdn_target_version, witness["cdnTargetVersion"])
        self.assertNotIn(str(self.target.data_root), repr(witness))
        self.assertIn("start", platform.events)
        self.assertIn("stop", platform.events)

    def test_same_active_release_is_explicit_noop_without_process_or_candidate_io(self) -> None:
        previous = _active()
        active = _active(ActiveRelease(self.release_id, self.verified.ownership))
        commit_active_state(self.target.state_root, previous=previous, active=active)
        platform = FakePlatform(_process())

        result = self._run(platform, [])

        self.assertEqual("noop", result.outcome)
        self.assertIsNone(result.operation_id)
        self.assertEqual(["current"], platform.events)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_missing_active_with_existing_previous_is_not_a_new_install(self) -> None:
        empty = _active()
        commit_active_state(self.target.state_root, previous=empty, active=empty)
        (self.target.state_root / "active.json").unlink()

        with self.assertRaises(ReleaseError) as caught:
            self._run(FakePlatform(), [])
        self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_invalid_timeout_fails_before_release_or_state_io(self) -> None:
        import wf_release_v1.transaction as transaction

        with (
            mock.patch.object(
                transaction, "verify_release", side_effect=AssertionError("release was read")
            ),
            self.assertRaises(ReleaseError) as caught,
        ):
            install_release(self.release, self.target, FakePlatform(), health_timeout=0)
        self.assertEqual("WFREL_SCHEMA_INVALID", caught.exception.code)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_persisted_baseline_facts_have_one_strict_path_free_shape(self) -> None:
        wire = target_facts_to_wire(self.before)
        self.assertEqual(self.before, target_facts_from_wire(wire))
        attacks: list[dict[str, object]] = []
        missing = dict(wire); del missing["contentDigest"]; attacks.append(missing)
        extra = dict(wire); extra["dataRoot"] = str(self.target.data_root); attacks.append(extra)
        duplicate = dict(wire); duplicate["capabilities"] = [
            *wire["capabilities"], wire["capabilities"][0],  # type: ignore[index]
        ]; attacks.append(duplicate)
        wrong_type = dict(wire); wrong_type["runtimeApi"] = True; attacks.append(wrong_type)
        for value in attacks:
            with self.subTest(keys=tuple(value)), self.assertRaises(ReleaseError) as caught:
                target_facts_from_wire(value)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)

    def test_initial_running_process_without_active_state_fails_before_probe(self) -> None:
        platform = FakePlatform(_process())
        result = self._run(platform, [])

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_STATE_CONFLICT", result.error_code)
        self.assertEqual("VERIFIED", self._receipt()["phase"])
        self.assertIsNotNone(platform.current)
        self.assertNotIn("stop", platform.events)

    def test_pre_switch_failure_restores_a_previously_running_service(self) -> None:
        previous = _active()
        commit_active_state(self.target.state_root, previous=previous, active=previous)
        platform = FakePlatform(_process())
        result = self._run(
            platform,
            [self.before, self.before],
            materialize=ReleaseError("WFREL_CANDIDATE_IO", "injected"),
        )

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_CANDIDATE_IO", result.error_code)
        self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())
        self.assertIsNotNone(platform.current)
        self.assertEqual("failed", self._receipt()["outcome"])
        self.assertEqual("STOPPED", self._receipt()["phase"])

    def test_post_switch_rejection_restores_bytes_candidate_and_previous_service(self) -> None:
        platform = FakePlatform()
        bad = _target(cdn_target_version="1.4.99")
        result = self._run(platform, [self.before, bad, self.before])

        self.assertEqual("recovered", result.outcome)
        self.assertEqual("WFREL_REQUIRE_EXPECTED_CDN_STATE", result.error_code)
        self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())
        self.assertTrue((
            self.candidates.content_root / "patches" / "1.4.54" / "overlay.zip"  # type: ignore[operator]
        ).is_file())
        self.assertFalse((self.target.cdn_root / "patches" / "1.4.54").exists())
        self.assertIsNotNone(platform.current)
        self.assertEqual("recovered", self._receipt()["outcome"])
        self.assertEqual("recovered", self._receipt()["recoveryOutcome"])
        self.assertFalse((self.target.state_root / "active.json").exists())

    def test_prepare_failure_after_switch_uses_the_same_recovery_path(self) -> None:
        platform = FakePlatform()
        platform.fail_prepare = ReleaseError("WFREL_PROCESS_START", "injected prepare failure")
        result = self._run(platform, [self.before, self.before])

        self.assertEqual("recovered", result.outcome)
        self.assertEqual("WFREL_PROCESS_START", result.error_code)
        self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())
        self.assertIsNotNone(platform.current)

    def test_recovery_restores_an_absent_current_pointer_as_absent(self) -> None:
        self.pointer.unlink()
        bad = _target(cdn_target_version="1.4.99")

        result = self._run(FakePlatform(), [self.before, bad, self.before])

        self.assertEqual("recovered", result.outcome)
        self.assertFalse(self.pointer.exists())
        staging = self.target.state_root / "staging" / OPERATION_ID
        self.assertEqual(b"absent\n", (staging / "content-current.absent").read_bytes())

    def test_existing_active_version_fails_without_overwriting_either_side(self) -> None:
        active = self.target.cdn_root / "patches" / "1.4.54"
        active.mkdir(parents=True)
        (active / "existing.zip").write_bytes(b"existing")

        result = self._run(FakePlatform(), [self.before])

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_STATE_CONFLICT", result.error_code)
        self.assertEqual(b"existing", (active / "existing.zip").read_bytes())
        self.assertTrue((
            self.candidates.content_root / "patches" / "1.4.54" / "overlay.zip"  # type: ignore[operator]
        ).is_file())
        self.assertEqual("MATERIALIZED", self._receipt()["phase"])

    def test_committed_state_is_not_downgraded_when_final_receipt_write_fails(self) -> None:
        result = self._run(
            FakePlatform(),
            [self.before, self.after],
            receipt_failure_phase="COMMITTED",
        )

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual(("WFREL_STATE_IO",), result.warnings)
        self.assertEqual(
            (self.release_id,),
            tuple(item.release_id for item in load_active_state(self.target.state_root).releases),
        )
        self.assertTrue((self.target.cdn_root / "patches" / "1.4.54").is_dir())

    def test_each_pre_switch_phase_write_failure_restores_original_runtime_state(self) -> None:
        cases = (
            ("VERIFIED", []),
            ("BASE_STARTED", []),
            ("PROBED", [self.before]),
            ("STOPPED", [self.before]),
            ("MATERIALIZED", [self.before]),
        )
        for phase, probes in cases:
            with self.subTest(phase=phase):
                self.setUp()
                result = self._run(
                    FakePlatform(), list(probes), receipt_failure_phase=phase,
                )
                self.assertEqual("failed", result.outcome)
                self.assertEqual("WFREL_STATE_IO", result.error_code)
                self.assertFalse((self.target.cdn_root / "patches" / "1.4.54").exists())
                self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())

    def test_each_post_switch_phase_write_failure_recovers_before_commit(self) -> None:
        cases = (
            ("SWITCHED", [self.before, self.before]),
            ("STARTED", [self.before, self.before]),
            ("HEALTH_READY", [self.before, self.before]),
            ("CAPABILITIES_ACCEPTED", [self.before, self.after, self.before]),
        )
        for phase, probes in cases:
            with self.subTest(phase=phase):
                self.setUp()
                result = self._run(
                    FakePlatform(), list(probes), receipt_failure_phase=phase,
                )
                self.assertEqual("recovered", result.outcome)
                self.assertEqual("WFREL_STATE_IO", result.error_code)
                self.assertFalse((self.target.state_root / "active.json").exists())
                self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())

    def test_recovery_failure_stays_stopped_and_retains_evidence(self) -> None:
        platform = FakePlatform()
        bad = _target(cdn_target_version="1.4.99")
        recovery_error = ReleaseError("WFREL_REQUIRE_TARGET", "recovery probe failed")
        result = self._run(platform, [self.before, bad, recovery_error])

        self.assertEqual("recovery_failed", result.outcome)
        self.assertEqual("WFREL_RECOVERY_FAILED", result.error_code)
        self.assertIsNone(platform.current)
        self.assertEqual("recovery_failed", self._receipt()["outcome"])
        self.assertEqual("failed", self._receipt()["recoveryOutcome"])
        self.assertTrue((self.target.state_root / "staging" / OPERATION_ID).is_dir())


if __name__ == "__main__":
    unittest.main()
