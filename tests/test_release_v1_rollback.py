"""Manual recovery and explicit previous-state rollback contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.test_release_v1_compatibility import _active, _ownership, _target, _verified
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1._target_facts import target_facts_to_wire
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.compatibility import ActiveRelease
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import (
    OperationReceipt,
    commit_active_state,
    load_active_state,
    load_operation_receipt,
    operation_reservation,
    write_phase_receipt,
)
from wf_release_v1.rollback import (
    RollbackResult,
    recover_failed_operation,
    rollback_to_previous,
)
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
)


ORIGINAL_OPERATION = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"
ROLLBACK_OPERATION = "20260812T020304.000000Z-fedcba9876543210fedcba9876543210"
RELEASE_ID = "sha256:" + "a" * 64
OLD_ID = "sha256:" + "b" * 64
SHA = "c" * 64
NOW = datetime(2026, 8, 12, 1, 2, 3, tzinfo=timezone.utc)


class FakePlatform:
    def __init__(self, current: ManagedProcess | None = None) -> None:
        self.current = current
        self.events: list[str] = []

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def start_server(self, launch, environment, operation_id: str) -> ManagedProcess:
        self.events.append("start")
        self.current = ManagedProcess(500, 5000, SHA, operation_id)
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        self.events.append("stop")
        self.current = None
        return False

    def prepare_content(self, launch, environment) -> None:
        raise AssertionError("manual recovery must restore the saved pointer, not prepare new content")

    def wait_exited(self, process, timeout: float) -> bool:
        return self.current != process


class RollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-rollback-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "modes",
                "candidate-content", "candidate-server", "candidate-modes",
            )
        }
        for path in roots.values():
            path.mkdir()
        self.target = ManagedTarget(
            roots["server"], roots["runtime"], roots["data"], roots["state"],
            roots["cdn"], roots["modes"],
            ComponentRoots(
                roots["candidate-content"], roots["candidate-server"], roots["candidate-modes"]
            ),
            TargetCompatibility("1.4.54", "1.4.53", True),
            "http://127.0.0.1:8001",
        )
        self.pointer = self.target.data_root / "state" / "content" / "current.json"
        self.pointer.parent.mkdir(parents=True)
        self.pointer.write_bytes(b'{"candidate":true}\n')
        self.release_root = self.target.component_roots.content / RELEASE_ID.replace(":", "-")
        self.candidate_version = self.release_root / "patches" / "1.4.54"
        self.candidate_version.parent.mkdir(parents=True)
        self.active_version = self.target.cdn_root / "patches" / "1.4.54"
        self.active_version.mkdir(parents=True)
        (self.active_version / "overlay.zip").write_bytes(b"overlay")
        self.baseline = _target(cdn_target_version="1.4.53")
        self.launch = LaunchSpec(
            self.target.runtime_pack / "node.exe",
            self.target.server_bundle / "prepare.js",
            self.target.server_bundle / "server.js",
            self.target.server_bundle,
        )
        self._write_staging()

    def _write_staging(self) -> None:
        staging = self.target.state_root / "staging" / ORIGINAL_OPERATION
        staging.mkdir(parents=True)
        raw = b'{"baseline":true}\n'
        (staging / "content-current.json").write_bytes(raw)
        (staging / "content-current.sha256").write_bytes(
            hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n"
        )
        (staging / "content-target-version.txt").write_bytes(b"1.4.54\n")
        (staging / "baseline-target-facts.json").write_bytes(
            canonical_json_bytes(target_facts_to_wire(self.baseline))
        )

    def _receipt(
        self,
        *,
        outcome: str,
        phase: str = "HEALTH_READY",
        target_protocol: str = "capabilities-v1",
    ) -> None:
        write_phase_receipt(self.target.state_root, OperationReceipt(
            2, ORIGINAL_OPERATION, RELEASE_ID, phase, outcome, NOW, NOW,
            (OLD_ID,), (RELEASE_ID,),
            "WFREL_RECOVERY_FAILED" if outcome == "recovery_failed" else None,
            "failed" if outcome == "recovery_failed" else None,
            target_protocol,
        ))

    def _patch_runtime(self, facts: object | None = None):
        import wf_release_v1.rollback as rollback

        probe = SimpleNamespace(run=mock.Mock(return_value=facts or self.baseline))
        return (
            mock.patch.object(rollback, "new_operation_id", return_value=ROLLBACK_OPERATION),
            mock.patch.object(rollback, "wait_health_ready"),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(ManagedTarget, "target_probe", return_value=probe),
            mock.patch.object(
                rollback,
                "verify_release",
                return_value=SimpleNamespace(components=("content",)),
            ),
        )

    def test_modern_rollback_entrypoints_respect_operation_reservation(self) -> None:
        platform = FakePlatform()
        calls = (
            lambda: recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            ),
            lambda: rollback_to_previous(
                self.target, platform, OLD_ID, health_timeout=2.0
            ),
        )

        with operation_reservation(self.target.state_root, ORIGINAL_OPERATION):
            for call in calls:
                with self.subTest(call=call), self.assertRaises(ReleaseError) as caught:
                    call()
                self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)

        self.assertEqual([], platform.events)

    def test_retries_only_a_recovery_failed_operation_and_records_a_new_audit_receipt(self) -> None:
        self._receipt(outcome="recovery_failed")
        current = _active(ActiveRelease(OLD_ID, _verified().ownership))
        commit_active_state(self.target.state_root, previous=_active(), active=current)
        platform = FakePlatform()
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            )

        self.assertEqual(RollbackResult(
            ROLLBACK_OPERATION, "recovered", RELEASE_ID, None, False,
        ), result)
        self.assertEqual(b'{"baseline":true}\n', self.pointer.read_bytes())
        self.assertTrue((self.candidate_version / "overlay.zip").is_file())
        self.assertFalse(self.active_version.exists())
        self.assertIsNotNone(platform.current)
        self.assertTrue((
            self.target.state_root / "receipts" / f"{ROLLBACK_OPERATION}.json"
        ).is_file())
        audit = load_operation_receipt(self.target.state_root, ROLLBACK_OPERATION)
        self.assertEqual((2, "capabilities-v1"), (
            audit.schema_version, audit.target_protocol,
        ))
        self.assertEqual(current, load_active_state(self.target.state_root))

    def test_manual_rollback_accepts_only_the_exact_previous_release_set(self) -> None:
        old_ownership = _ownership(entities=("character:310099",), records=("characters:310099",))
        new_ownership = _ownership(entities=("character:310100",), records=("characters:310100",))
        previous = _active(ActiveRelease(OLD_ID, old_ownership))
        current = _active(
            ActiveRelease(RELEASE_ID, new_ownership),
            ActiveRelease(OLD_ID, old_ownership),
            known_release_ids=(OLD_ID,),
        )
        commit_active_state(self.target.state_root, previous=_active(), active=previous)
        commit_active_state(self.target.state_root, previous=previous, active=current)
        self._receipt(outcome="succeeded", phase="COMMITTED")
        platform = FakePlatform()
        patches = self._patch_runtime()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = rollback_to_previous(
                self.target, platform, OLD_ID, health_timeout=2.0
            )

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual(OLD_ID, result.to_release_id)
        self.assertFalse(result.data_compatibility_guaranteed)
        rolled = load_active_state(self.target.state_root)
        self.assertEqual((OLD_ID,), tuple(item.release_id for item in rolled.releases))
        self.assertEqual((RELEASE_ID, OLD_ID), rolled.known_release_ids)
        self.assertTrue((self.candidate_version / "overlay.zip").is_file())
        self.assertFalse(self.active_version.exists())
        audit = load_operation_receipt(self.target.state_root, ROLLBACK_OPERATION)
        self.assertEqual((2, "capabilities-v1"), (
            audit.schema_version, audit.target_protocol,
        ))

    def test_running_service_and_nonmatching_receipt_fail_before_switch(self) -> None:
        self._receipt(outcome="recovery_failed")
        empty = _active()
        commit_active_state(self.target.state_root, previous=empty, active=empty)
        platform = FakePlatform(ManagedProcess(10, 20, SHA, ORIGINAL_OPERATION))
        with self.assertRaises(ReleaseError) as running:
            recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            )
        self.assertEqual("WFREL_PROCESS_RUNNING", running.exception.code)
        self.assertTrue(self.active_version.is_dir())

    def test_modern_recovery_and_rollback_reject_legacy_receipts_before_switch(self) -> None:
        self._receipt(outcome="recovery_failed", target_protocol="legacy")
        empty = _active()
        commit_active_state(self.target.state_root, previous=empty, active=empty)
        platform = FakePlatform()
        with self.assertRaises(ReleaseError) as recovery:
            recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            )
        self.assertEqual("WFREL_TARGET_PROTOCOL", recovery.exception.code)
        self.assertTrue(self.active_version.is_dir())
        self.assertEqual([], platform.events)

        self.setUp()
        old_ownership = _ownership(entities=("character:310099",), records=("characters:310099",))
        new_ownership = _ownership(entities=("character:310100",), records=("characters:310100",))
        previous = _active(ActiveRelease(OLD_ID, old_ownership))
        current = _active(
            ActiveRelease(RELEASE_ID, new_ownership), ActiveRelease(OLD_ID, old_ownership)
        )
        commit_active_state(self.target.state_root, previous=_active(), active=previous)
        commit_active_state(self.target.state_root, previous=previous, active=current)
        self._receipt(outcome="succeeded", phase="COMMITTED", target_protocol="legacy")
        platform = FakePlatform()
        with self.assertRaises(ReleaseError) as rollback:
            rollback_to_previous(self.target, platform, OLD_ID, health_timeout=2.0)
        self.assertEqual("WFREL_TARGET_PROTOCOL", rollback.exception.code)
        self.assertTrue(self.active_version.is_dir())
        self.assertEqual([], platform.events)

        self.setUp()
        self._receipt(outcome="succeeded", phase="COMMITTED")
        platform = FakePlatform()
        with self.assertRaises(ReleaseError) as wrong_outcome:
            recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            )
        self.assertEqual("WFREL_STATE_CONFLICT", wrong_outcome.exception.code)
        self.assertTrue(self.active_version.is_dir())

    def test_active_commit_is_not_reversed_when_final_rollback_receipt_fails(self) -> None:
        import wf_release_v1.rollback as rollback

        old_ownership = _ownership(entities=("character:310099",), records=("characters:310099",))
        new_ownership = _ownership(entities=("character:310100",), records=("characters:310100",))
        previous = _active(ActiveRelease(OLD_ID, old_ownership))
        current = _active(
            ActiveRelease(RELEASE_ID, new_ownership), ActiveRelease(OLD_ID, old_ownership)
        )
        commit_active_state(self.target.state_root, previous=_active(), active=previous)
        commit_active_state(self.target.state_root, previous=previous, active=current)
        self._receipt(outcome="succeeded", phase="COMMITTED")
        platform = FakePlatform()
        patches = self._patch_runtime()
        with (
            patches[0], patches[1], patches[2], patches[3], patches[4],
            mock.patch.object(
                rollback,
                "write_phase_receipt",
                side_effect=ReleaseError("WFREL_STATE_IO", "injected"),
            ),
        ):
            result = rollback_to_previous(
                self.target, platform, OLD_ID, health_timeout=2.0
            )

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual("WFREL_STATE_IO", result.error_code)
        self.assertEqual(
            (OLD_ID,),
            tuple(item.release_id for item in load_active_state(self.target.state_root).releases),
        )
        self.assertIsNotNone(platform.current)

    def test_failed_manual_recovery_stays_stopped_and_keeps_active_commit_point(self) -> None:
        self._receipt(outcome="recovery_failed")
        current = _active(ActiveRelease(OLD_ID, _verified().ownership))
        commit_active_state(self.target.state_root, previous=_active(), active=current)
        platform = FakePlatform()
        error = ReleaseError("WFREL_REQUIRE_TARGET", "injected recovery rejection")
        patches = self._patch_runtime(error)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = recover_failed_operation(
                self.target, platform, ORIGINAL_OPERATION, health_timeout=2.0
            )

        self.assertEqual("recovery_failed", result.outcome)
        self.assertIsNone(platform.current)
        self.assertEqual(current, load_active_state(self.target.state_root))
        self.assertTrue((self.target.state_root / "staging" / ORIGINAL_OPERATION).is_dir())


if __name__ == "__main__":
    unittest.main()
