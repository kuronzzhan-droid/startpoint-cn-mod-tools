"""Install phase-machine and pre-acceptance recovery contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    operation_reservation,
    write_phase_receipt as persist_phase_receipt,
)
from wf_release_v1.schema import AssetReplacement, SourceEvidence
from wf_release_v1.target import (
    ComponentRoots,
    LaunchSpec,
    ManagedTarget,
    TargetCompatibility,
)
from wf_release_v1.transaction import InstallResult, install_release


OPERATION_ID = "20260812T010203.000000Z-0123456789abcdef0123456789abcdef"
SHA = "a" * 64
RELEASE_A = "sha256:" + "a" * 64
RELEASE_B = "sha256:" + "b" * 64


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
            raise ReleaseError(
                "WFREL_PROCESS_IDENTITY",
                "transaction tried to stop an unowned process",
            )
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
        empty = _active()
        commit_active_state(self.target.state_root, previous=empty, active=empty)
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
        self.baseline_facts: list[object] = []

    def _accepted_verified(self):
        replacement = AssetReplacement(
            "common",
            "item/sprite_sheet.png",
            "b" * 64,
            482079,
        )
        source = SourceEvidence(
            "character-workspace-v2",
            self.verified.manifest.source_evidence.workspace_input_sha256,
            (replacement,),
        )
        return replace(
            self.verified,
            manifest=replace(self.verified.manifest, source_evidence=source),
        )

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
        capability_level: str = "modern",
        capability_requires_started: bool = False,
        capability_replacement: ManagedProcess | None = None,
        baseline_error: ReleaseError | None = None,
        baseline_recheck_error: ReleaseError | None = None,
        baseline_disk_digest: str | None = None,
        verified=None,
    ) -> InstallResult:
        import wf_release_v1.transaction as transaction

        probe = FakeProbe(probes)
        effective_verified = self.verified if verified is None else verified
        receipt_failed = False
        health_ready = False

        def record_receipt(root: Path, receipt) -> None:
            nonlocal receipt_failed
            self.phases.append(receipt.phase)
            if receipt.phase == receipt_failure_phase and not receipt_failed:
                receipt_failed = True
                raise ReleaseError("WFREL_STATE_IO", "injected receipt failure")
            persist_phase_receipt(root, receipt)

        def inspect_capability(target: ManagedTarget, reader: object) -> object:
            self.assertIs(self.target, target)
            self.assertIs(platform, reader)
            platform.events.append("capability")
            self.assertTrue(
                (self.target.state_root / ".wf-release-v1.operation").is_file(),
                "modern capability inspection must happen inside the operation reservation",
            )
            if capability_requires_started:
                self.assertIsNotNone(
                    platform.current,
                    "a stopped managed target must start before protocol inspection",
                )
                self.assertTrue(
                    health_ready,
                    "a stopped managed target must become healthy before protocol inspection",
                )
            if capability_replacement is not None:
                platform.current = capability_replacement
            return SimpleNamespace(level=capability_level)

        def record_health(*args: object, **kwargs: object) -> None:
            nonlocal health_ready
            health_ready = True

        def verify_baseline(_verified, target: ManagedTarget, facts=None):
            self.assertIs(self.target, target)
            self.baseline_facts.append(facts)
            if baseline_error is not None:
                raise baseline_error
            if len(self.baseline_facts) > 1 and baseline_recheck_error is not None:
                raise baseline_recheck_error
            disk_digest = (
                baseline_disk_digest
                if baseline_disk_digest is not None
                else getattr(facts, "release_digest", None)
            )
            if facts is not None and disk_digest != facts.release_digest:
                raise ReleaseError(
                    "WFREL_ASSET_BASELINE_UNAVAILABLE",
                    "disk and runtime release digests disagree",
                )
            return SimpleNamespace(release_digest=disk_digest)

        with (
            mock.patch.object(transaction, "new_operation_id", return_value=OPERATION_ID),
            mock.patch.object(
                transaction,
                "inspect_target_capability",
                side_effect=inspect_capability,
            ),
            mock.patch.object(
                transaction,
                "verify_release_contract",
                return_value=(
                    SimpleNamespace(release_id=self.release_id),
                    effective_verified,
                ),
            ),
            mock.patch.object(
                transaction,
                "verify_asset_replacement_baseline",
                side_effect=verify_baseline,
            ),
            mock.patch.object(transaction, "import_verified_object", return_value=self.stored),
            mock.patch.object(
                transaction,
                "load_verified_release",
                return_value=effective_verified,
            ),
            mock.patch.object(
                transaction,
                "materialize_candidates",
                return_value=self.candidates if materialize is None else mock.DEFAULT,
                side_effect=materialize if isinstance(materialize, BaseException) else None,
            ),
            mock.patch.object(transaction, "verify_candidates"),
            mock.patch.object(
                transaction,
                "wait_health_ready",
                side_effect=record_health,
            ),
            mock.patch.object(transaction, "write_phase_receipt", side_effect=record_receipt),
            mock.patch.object(ManagedTarget, "target_probe", return_value=probe),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
        ):
            return install_release(
                self.release,
                self.target,
                platform,
                health_timeout=2.0,
                enforce_target_protocol=True,
            )

    def test_bootstrapped_empty_state_commits_first_release_after_double_acceptance(self) -> None:
        platform = FakePlatform()
        result = self._run(platform, [self.before, self.after])

        self.assertEqual(InstallResult(
            release_id=self.release_id, operation_id=OPERATION_ID,
            outcome="succeeded", error_code=None, warnings=(),
        ), result)
        self.assertEqual("succeeded", self._receipt()["outcome"])
        self.assertEqual("COMMITTED", self._receipt()["phase"])
        self.assertEqual(2, self._receipt()["schemaVersion"])
        self.assertEqual("capabilities-v1", self._receipt()["targetProtocol"])
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

    def test_stopped_managed_target_starts_before_protocol_inspection(self) -> None:
        platform = FakePlatform()

        result = self._run(
            platform,
            [self.before, self.after],
            capability_requires_started=True,
        )

        self.assertEqual("succeeded", result.outcome)
        self.assertLess(
            platform.events.index("start"),
            platform.events.index("capability"),
        )

    def test_stopped_target_without_bootstrap_state_is_rejected_before_start(self) -> None:
        (self.target.state_root / "active.json").unlink()
        (self.target.state_root / "previous.json").unlink()
        platform = FakePlatform()

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, [])

        self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
        self.assertEqual([], platform.events)
        self.assertEqual([], self.phases)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_concurrent_reservation_blocks_install_before_prepare_or_start(self) -> None:
        platform = FakePlatform()
        with operation_reservation(self.target.state_root, OPERATION_ID):
            with self.assertRaises(ReleaseError) as caught:
                self._run(platform, [self.before, self.after])
        self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
        self.assertNotIn("prepare", platform.events)
        self.assertNotIn("start", platform.events)
        self.assertEqual([], self.phases)

    def test_wrong_protocol_is_rejected_inside_reservation_before_transaction_io(self) -> None:
        platform = FakePlatform(_process())

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, [], capability_level="transition")

        self.assertEqual("WFREL_TARGET_PROTOCOL", caught.exception.code)
        self.assertEqual(["current", "capability"], platform.events)
        self.assertEqual([], self.phases)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_asset_baseline_mismatch_is_zero_write_before_import_or_receipt(self) -> None:
        accepted = self._accepted_verified()
        early = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_A,
        )
        before = tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        ))
        platform = FakePlatform(_process())

        with self.assertRaises(ReleaseError) as caught:
            self._run(
                platform,
                [early],
                baseline_error=ReleaseError(
                    "WFREL_ASSET_BASELINE_MISMATCH",
                    "injected before-byte mismatch",
                ),
                verified=accepted,
            )

        self.assertEqual("WFREL_ASSET_BASELINE_MISMATCH", caught.exception.code)
        self.assertNotIn("stop", platform.events)
        self.assertNotIn("start", platform.events)
        self.assertNotIn("prepare", platform.events)
        self.assertEqual([], self.phases)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertEqual(before, tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        )))

    def test_accepted_asset_install_requires_running_target_before_any_write(self) -> None:
        accepted = self._accepted_verified()
        before = tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        ))
        platform = FakePlatform()

        with self.assertRaises(ReleaseError) as caught:
            self._run(
                platform,
                [],
                verified=accepted,
                baseline_disk_digest=RELEASE_A,
            )

        self.assertEqual("WFREL_REQUIRE_TARGET", caught.exception.code)
        self.assertEqual(["current"], platform.events)
        self.assertEqual([], self.baseline_facts)
        self.assertEqual([], self.phases)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertEqual(before, tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        )))

    def test_running_accepted_asset_install_binds_fresh_runtime_authority(self) -> None:
        accepted = self._accepted_verified()
        early = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_A,
        )
        after = _target(
            cdn_target_version="1.4.54",
            release_digest=RELEASE_B,
        )
        platform = FakePlatform(_process())

        result = self._run(
            platform,
            [early, early, after],
            verified=accepted,
            baseline_disk_digest=RELEASE_A,
        )

        self.assertEqual("succeeded", result.outcome)
        self.assertEqual([early, early], self.baseline_facts)
        self.assertNotIn("BASE_STARTED", self.phases)
        self.assertEqual(1, platform.events.count("start"))

    def test_runtime_and_disk_release_digest_disagreement_is_zero_write(self) -> None:
        accepted = self._accepted_verified()
        runtime = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_A,
        )
        before = tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        ))
        platform = FakePlatform(_process())

        with self.assertRaises(ReleaseError) as caught:
            self._run(
                platform,
                [runtime],
                verified=accepted,
                baseline_disk_digest=RELEASE_B,
            )

        self.assertEqual("WFREL_ASSET_BASELINE_UNAVAILABLE", caught.exception.code)
        self.assertEqual([runtime], self.baseline_facts)
        self.assertNotIn("stop", platform.events)
        self.assertNotIn("start", platform.events)
        self.assertNotIn("prepare", platform.events)
        self.assertEqual([], self.phases)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertEqual(before, tuple(sorted(
            (path.relative_to(self.root).as_posix(), path.read_bytes())
            for path in self.root.rglob("*") if path.is_file()
        )))

    def test_release_digest_drift_before_stop_fails_without_materializing(self) -> None:
        accepted = self._accepted_verified()
        early = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_A,
        )
        drifted = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_B,
        )
        platform = FakePlatform(_process())

        result = self._run(
            platform,
            [early, drifted],
            verified=accepted,
            baseline_disk_digest=RELEASE_A,
        )

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_ASSET_BASELINE_UNAVAILABLE", result.error_code)
        self.assertEqual([early], self.baseline_facts)
        self.assertNotIn("stop", platform.events)
        self.assertNotIn("start", platform.events)
        self.assertNotIn("prepare", platform.events)
        self.assertNotIn("MATERIALIZED", self.phases)
        self.assertEqual(_process(), platform.current)
        self.assertEqual("failed", self._receipt()["outcome"])
        self.assertEqual("VERIFIED", self._receipt()["phase"])

    def test_disk_drift_after_initial_baseline_fails_before_stop(self) -> None:
        accepted = self._accepted_verified()
        runtime = _target(
            cdn_target_version="1.4.53",
            release_digest=RELEASE_A,
        )
        platform = FakePlatform(_process())

        result = self._run(
            platform,
            [runtime, runtime],
            verified=accepted,
            baseline_disk_digest=RELEASE_A,
            baseline_recheck_error=ReleaseError(
                "WFREL_ASSET_BASELINE_MISMATCH",
                "disk archive changed after initial baseline verification",
            ),
        )

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_ASSET_BASELINE_MISMATCH", result.error_code)
        self.assertEqual([runtime, runtime], self.baseline_facts)
        self.assertNotIn("stop", platform.events)
        self.assertNotIn("start", platform.events)
        self.assertNotIn("prepare", platform.events)
        self.assertNotIn("MATERIALIZED", self.phases)
        self.assertEqual(_process(), platform.current)
        self.assertEqual("failed", self._receipt()["outcome"])
        self.assertEqual("VERIFIED", self._receipt()["phase"])

    def test_stopped_wrong_protocol_cleans_started_baseline(self) -> None:
        platform = FakePlatform()

        result = self._run(
            platform,
            [],
            capability_level="transition",
            capability_requires_started=True,
        )

        self.assertEqual("failed", result.outcome)
        self.assertEqual("WFREL_TARGET_PROTOCOL", result.error_code)
        self.assertEqual(
            ["current", "start", "capability", "stop"],
            platform.events,
        )
        self.assertNotIn("MATERIALIZED", self.phases)
        self.assertIsNone(platform.current)

    def test_stopped_protocol_failure_never_stops_replacement_process(self) -> None:
        platform = FakePlatform()
        replacement = _process(999)

        result = self._run(
            platform,
            [],
            capability_level="transition",
            capability_requires_started=True,
            capability_replacement=replacement,
        )

        self.assertEqual("recovery_failed", result.outcome)
        self.assertEqual("WFREL_RECOVERY_FAILED", result.error_code)
        self.assertEqual(replacement, platform.current)
        self.assertNotIn("MATERIALIZED", self.phases)

    def test_same_active_release_is_explicit_noop_without_process_or_candidate_io(self) -> None:
        previous = _active()
        active = _active(ActiveRelease(self.release_id, self.verified.ownership))
        commit_active_state(self.target.state_root, previous=previous, active=active)
        platform = FakePlatform(_process())

        result = self._run(platform, [])

        self.assertEqual("noop", result.outcome)
        self.assertIsNone(result.operation_id)
        self.assertEqual(["current", "capability"], platform.events)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_stopped_same_active_release_is_noop_without_start_or_receipt(self) -> None:
        previous = _active()
        active = _active(ActiveRelease(self.release_id, self.verified.ownership))
        commit_active_state(self.target.state_root, previous=previous, active=active)
        platform = FakePlatform()

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
                transaction,
                "verify_release_contract",
                side_effect=AssertionError("release was read"),
            ),
            self.assertRaises(ReleaseError) as caught,
        ):
            install_release(self.release, self.target, FakePlatform(), health_timeout=0)
        self.assertEqual("WFREL_SCHEMA_INVALID", caught.exception.code)
        self.assertFalse((self.target.state_root / "receipts").exists())

    def test_persisted_baseline_facts_have_one_strict_path_free_shape(self) -> None:
        wire = target_facts_to_wire(self.before)
        self.assertIn("releaseDigest", wire)
        self.assertIsNone(wire["releaseDigest"])
        self.assertEqual(self.before, target_facts_from_wire(wire))
        attacks: list[dict[str, object]] = []
        missing_release = dict(wire)
        del missing_release["releaseDigest"]
        attacks.append(missing_release)
        missing = dict(wire); del missing["contentDigest"]; attacks.append(missing)
        extra = dict(wire); extra["dataRoot"] = str(self.target.data_root); attacks.append(extra)
        duplicate = dict(wire); duplicate["capabilities"] = [
            *wire["capabilities"], wire["capabilities"][0],  # type: ignore[index]
        ]; attacks.append(duplicate)
        malformed_release = dict(wire)
        malformed_release["releaseDigest"] = f"sha256:{SHA[:-1]}"
        attacks.append(malformed_release)
        wrong_type = dict(wire); wrong_type["runtimeApi"] = True; attacks.append(wrong_type)
        for value in attacks:
            with self.subTest(keys=tuple(value)), self.assertRaises(ReleaseError) as caught:
                target_facts_from_wire(value)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)

    def test_persisted_release_digest_round_trips_when_content_is_managed(self) -> None:
        wire = target_facts_to_wire(self.before)
        release_digest = f"sha256:{SHA}"
        wire["releaseDigest"] = release_digest

        try:
            facts = target_facts_from_wire(wire)
        except ReleaseError as error:
            self.fail(f"releaseDigest was rejected: {error.code}")

        self.assertEqual(release_digest, facts.release_digest)
        self.assertEqual(wire, target_facts_to_wire(facts))

    def test_initial_running_process_without_active_state_fails_before_probe(self) -> None:
        (self.target.state_root / "active.json").unlink()
        (self.target.state_root / "previous.json").unlink()
        platform = FakePlatform(_process())

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, [])

        self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertIsNotNone(platform.current)
        self.assertEqual([], platform.events)

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
        self.assertEqual((), load_active_state(self.target.state_root).releases)

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
                self.assertEqual(
                    (),
                    load_active_state(self.target.state_root).releases,
                )
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
