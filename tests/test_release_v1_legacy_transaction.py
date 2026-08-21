"""Atomic legacy CDN transition and exact recovery contracts."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from tests.release_v1_fixtures import make_patch_overlay
from tests.test_release_v1_legacy_compatibility import _ownership, _verified
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1.canonical import FileIdentity
from wf_release_v1.errors import ReleaseError
from wf_release_v1.legacy_transaction import install_legacy_release
from wf_release_v1.materialize import CandidateSet, StoredObject
from wf_release_v1.receipts import load_active_state, operation_reservation
from wf_release_v1.target import ComponentRoots, LaunchSpec, ManagedTarget, TargetCompatibility
from wf_release_v1.verifier_overlay import inspect_overlay_chain


OPERATION_ID = "20260813T010203.000000Z-0123456789abcdef0123456789abcdef"
SECOND_OPERATION_ID = "20260813T020304.000000Z-11111111111111111111111111111111"
ROLLBACK_OPERATION_ID = "20260813T030405.000000Z-22222222222222222222222222222222"
SHA = "a" * 64


def _process(pid: int) -> ManagedProcess:
    return ManagedProcess(pid, pid * 100, SHA, OPERATION_ID)


class FakePlatform:
    def __init__(self) -> None:
        self.current: ManagedProcess | None = _process(100)
        self.events: list[str] = []
        self.next_pid = 200

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        del timeout
        self.events.append("stop")
        if process != self.current:
            raise AssertionError("transaction stopped an unowned process")
        self.current = None
        return False

    def prepare_content(self, launch: LaunchSpec, environment) -> None:
        del launch, environment
        raise AssertionError("legacy install must not invoke modern preparation")

    def start_server(self, launch: LaunchSpec, environment, operation_id: str) -> ManagedProcess:
        del launch, environment
        self.events.append("start")
        self.next_pid += 1
        self.current = ManagedProcess(
            self.next_pid, self.next_pid * 100, SHA, operation_id
        )
        return self.current

    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool:
        del process, timeout
        raise AssertionError("legacy install must use stop_owned")


class LegacyTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-legacy-transaction-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server-bundle", "runtime-pack", "data", "state", "cdn", "modes",
                "content-components", "server-components", "mode-components",
            )
        }
        for path in roots.values():
            path.mkdir()
        for layer in ("common", "medium", "android"):
            (roots["cdn"] / "cn" / f"archive-{layer}-diff").mkdir(parents=True)
        self.target = ManagedTarget(
            roots["server-bundle"],
            roots["runtime-pack"],
            roots["data"],
            roots["state"],
            roots["cdn"],
            roots["modes"],
            ComponentRoots(
                roots["content-components"],
                roots["server-components"],
                roots["mode-components"],
            ),
            TargetCompatibility("1.4.54", "1.4.54", True),
            "http://127.0.0.1:8001",
        )
        self.outer = make_patch_overlay(
            self.root / "source-overlay.zip",
            from_version="1.4.54",
            target_version="1.4.55",
        )
        overlay = inspect_overlay_chain((self.outer,))
        self.verified = _verified(overlay=overlay)
        self.release_id = self.verified.manifest.release_id
        candidate_root = self.target.component_roots.content / self.release_id.replace(":", "-")
        candidate_path = candidate_root / "patches" / "1.4.55" / "overlay.zip"
        candidate_path.parent.mkdir(parents=True)
        candidate_path.write_bytes(self.outer.read_bytes())
        raw = candidate_path.read_bytes()
        self.candidates = CandidateSet(
            self.release_id,
            candidate_root,
            None,
            None,
            (FileIdentity(len(raw), hashlib.sha256(raw).hexdigest()),),
            ("patches/1.4.55/overlay.zip",),
        )
        self.stored = StoredObject(
            self.release_id,
            self.root / "stored.zip",
            FileIdentity(1, SHA),
        )
        self.release = self.root / "release.zip"
        self.release.write_bytes(b"verified-by-test-double")
        self.launch = LaunchSpec(
            self.target.runtime_pack / "node.exe",
            self.target.server_bundle / "prepare.js",
            self.target.server_bundle / "server.js",
            self.target.server_bundle,
        )
        self.readiness_calls = 0

    def _archive_bytes(self) -> dict[str, bytes]:
        found: dict[str, bytes] = {}
        for layer in ("common", "medium", "android"):
            directory = self.target.cdn_root / "cn" / f"archive-{layer}-diff"
            for path in directory.iterdir():
                found[f"{layer}/{path.name}"] = path.read_bytes()
        return found

    def _run(
        self,
        platform: FakePlatform,
        *,
        readiness_failure: bool = False,
        link_failure_after: int | None = None,
        recovery_failure: bool = False,
        late_conflict: bool = False,
        operation_id: str = OPERATION_ID,
        capability_level: str = "transition",
    ):
        import wf_release_v1.legacy_transaction as transaction

        real_link = transaction.apply_legacy_switch
        real_restore = transaction.restore_legacy_switch
        link_calls = 0

        def readiness(target: ManagedTarget, timeout: float) -> None:
            del target, timeout
            self.readiness_calls += 1
            if readiness_failure and self.readiness_calls == 1:
                raise ReleaseError("WFREL_REQUIRE_TARGET", "injected readiness failure")

        def apply_with_failure(switch):
            nonlocal link_calls
            if link_failure_after is None:
                return real_link(switch)
            original = transaction._link_archive

            def fail_after(*args, **kwargs):
                nonlocal link_calls
                link_calls += 1
                if link_calls > link_failure_after:
                    raise ReleaseError("WFREL_LEGACY_CDN_IO", "injected link failure")
                return original(*args, **kwargs)

            with mock.patch.object(transaction, "_link_archive", side_effect=fail_after):
                return real_link(switch)

        def restore(switch) -> None:
            if recovery_failure:
                raise ReleaseError("WFREL_RECOVERY_FAILED", "injected recovery failure")
            real_restore(switch)

        def materialize(*_args, **_kwargs):
            if late_conflict:
                archive = self.verified.overlay.edges[0].archives[0]  # type: ignore[union-attr]
                target = self.target.cdn_root / "cn" / Path(archive.relative_path)
                target.write_bytes(b"unrelated-existing-bytes")
            return self.candidates

        def inspect_capability(target: ManagedTarget, reader: object) -> object:
            self.assertIs(self.target, target)
            self.assertIs(platform, reader)
            self.assertTrue(
                (self.target.state_root / ".wf-release-v1.operation").is_file(),
                "legacy capability inspection must happen inside the operation reservation",
            )
            return SimpleNamespace(level=capability_level)

        with (
            mock.patch.object(transaction, "new_operation_id", return_value=operation_id),
            mock.patch.object(
                transaction,
                "inspect_target_capability",
                side_effect=inspect_capability,
            ),
            mock.patch.object(
                transaction,
                "verify_release_contract",
                return_value=(SimpleNamespace(release_id=self.release_id), self.verified),
            ),
            mock.patch.object(transaction, "import_verified_object", return_value=self.stored),
            mock.patch.object(transaction, "materialize_candidates", side_effect=materialize),
            mock.patch.object(transaction, "verify_candidates"),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(transaction, "wait_legacy_ready", side_effect=readiness),
            mock.patch.object(transaction, "apply_legacy_switch", side_effect=apply_with_failure),
            mock.patch.object(transaction, "restore_legacy_switch", side_effect=restore),
        ):
            return install_legacy_release(
                self.release,
                self.target,
                platform,
                enforce_target_protocol=True,
            )

    def test_legacy_install_respects_operation_reservation(self) -> None:
        platform = FakePlatform()
        with operation_reservation(self.target.state_root, OPERATION_ID):
            with self.assertRaises(ReleaseError) as caught:
                self._run(platform)
        self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
        self.assertEqual([], platform.events)

    def test_wrong_protocol_is_rejected_inside_reservation_before_transaction_io(self) -> None:
        platform = FakePlatform()

        with self.assertRaises(ReleaseError) as caught:
            self._run(platform, capability_level="modern")

        self.assertEqual("WFREL_TARGET_PROTOCOL", caught.exception.code)
        self.assertEqual([], platform.events)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertEqual({}, self._archive_bytes())

    def test_installs_three_layers_commits_state_and_restarts_owned_server(self) -> None:
        platform = FakePlatform()
        result = self._run(platform)
        self.assertEqual(("succeeded", None), (result.outcome, result.error_code))
        self.assertEqual(3, len(self._archive_bytes()))
        self.assertEqual(["stop", "start"], [item for item in platform.events if item != "current"])
        self.assertEqual(1, self.readiness_calls)
        active = load_active_state(self.target.state_root)
        self.assertEqual((self.release_id,), tuple(item.release_id for item in active.releases))
        receipt = json.loads(
            (self.target.state_root / "receipts" / f"{OPERATION_ID}.json").read_text("utf-8")
        )
        self.assertEqual(("COMMITTED", "succeeded"), (receipt["phase"], receipt["outcome"]))
        self.assertEqual((2, "legacy"), (receipt["schemaVersion"], receipt["targetProtocol"]))
        self.assertFalse((self.target.state_root / "staging" / OPERATION_ID).exists())

    def test_mid_commit_failure_restores_exact_empty_layers_and_running_state(self) -> None:
        platform = FakePlatform()
        result = self._run(platform, link_failure_after=1)
        self.assertEqual(("recovered", "WFREL_LEGACY_CDN_IO"), (result.outcome, result.error_code))
        self.assertEqual({}, self._archive_bytes())
        self.assertIsNotNone(platform.current)
        self.assertFalse((self.target.state_root / "active.json").exists())

    def test_readiness_failure_restores_bytes_and_restarts_baseline(self) -> None:
        platform = FakePlatform()
        result = self._run(platform, readiness_failure=True)
        self.assertEqual(("recovered", "WFREL_REQUIRE_TARGET"), (result.outcome, result.error_code))
        self.assertEqual({}, self._archive_bytes())
        self.assertIsNotNone(platform.current)
        self.assertEqual(2, self.readiness_calls)

    def test_unowned_target_stops_before_receipt_or_candidate_writes(self) -> None:
        platform = FakePlatform()
        platform.current = None
        with self.assertRaises(ReleaseError) as raised:
            self._run(platform)
        self.assertEqual("WFREL_LEGACY_PROCESS_NOT_OWNED", raised.exception.code)
        self.assertFalse((self.target.state_root / "receipts").exists())
        self.assertEqual({}, self._archive_bytes())

    def test_recovery_failure_preserves_evidence_and_leaves_service_stopped(self) -> None:
        platform = FakePlatform()
        result = self._run(
            platform,
            readiness_failure=True,
            recovery_failure=True,
        )
        self.assertEqual(
            ("recovery_failed", "WFREL_RECOVERY_FAILED"),
            (result.outcome, result.error_code),
        )
        self.assertIsNone(platform.current)
        self.assertEqual(3, len(self._archive_bytes()))
        self.assertTrue((self.target.state_root / "staging" / OPERATION_ID).is_dir())

    def test_late_archive_conflict_never_overwrites_and_fails_recovery_closed(self) -> None:
        platform = FakePlatform()
        result = self._run(platform, late_conflict=True)
        self.assertEqual(
            ("recovery_failed", "WFREL_RECOVERY_FAILED"),
            (result.outcome, result.error_code),
        )
        self.assertEqual(1, len(self._archive_bytes()))
        self.assertEqual(
            {b"unrelated-existing-bytes"},
            set(self._archive_bytes().values()),
        )
        self.assertIsNone(platform.current)

    def test_two_releases_install_in_order_and_second_rolls_back_to_first(self) -> None:
        platform = FakePlatform()
        first = self._run(platform)
        self.assertEqual("succeeded", first.outcome)
        first_archives = self._archive_bytes()
        self.assertEqual(3, len(first_archives))

        second_outer = make_patch_overlay(
            self.root / "source-overlay-2.zip",
            from_version="1.4.55",
            target_version="1.4.56",
        )
        second_overlay = inspect_overlay_chain((second_outer,))
        self.verified = _verified(
            overlay=second_overlay,
            ownership=_ownership(entity="character:310100"),
        )
        second_raw = second_outer.read_bytes()
        second_file = replace(
            self.verified.manifest.files[0],
            path="content/overlay.zip",
            size=len(second_raw),
            sha256=hashlib.sha256(second_raw).hexdigest(),
        )
        self.verified = type(self.verified)(
            replace(self.verified.manifest, files=(second_file,)),
            self.verified.requirements,
            self.verified.ownership,
            self.verified.overlay,
        )
        self.release_id = self.verified.manifest.release_id
        candidate_root = (
            self.target.component_roots.content / self.release_id.replace(":", "-")
        )
        candidate_path = candidate_root / "patches" / "1.4.56" / "overlay.zip"
        candidate_path.parent.mkdir(parents=True)
        candidate_path.write_bytes(second_outer.read_bytes())
        raw = candidate_path.read_bytes()
        self.candidates = CandidateSet(
            self.release_id,
            candidate_root,
            None,
            None,
            (FileIdentity(len(raw), hashlib.sha256(raw).hexdigest()),),
            ("patches/1.4.56/overlay.zip",),
        )
        self.stored = StoredObject(
            self.release_id,
            self.root / "stored-2.zip",
            FileIdentity(1, SHA),
        )
        self.release = self.root / "release-2.zip"
        self.release.write_bytes(b"verified-second-by-test-double")
        second = self._run(platform, operation_id=SECOND_OPERATION_ID)
        self.assertEqual("succeeded", second.outcome)
        self.assertEqual(6, len(self._archive_bytes()))

        retained = (
            self.target.state_root / "objects" / self.release_id.replace(":", "-")
        )
        retained.mkdir(parents=True, exist_ok=True)
        (retained / "release.wf-release.zip").write_bytes(b"retained-second")
        from wf_release_v1.legacy_rollback import rollback_legacy_to_previous
        import wf_release_v1.legacy_rollback as rollback

        with (
            mock.patch.object(
                rollback, "new_operation_id", return_value=ROLLBACK_OPERATION_ID
            ),
            mock.patch.object(
                rollback,
                "verify_release_contract",
                return_value=(SimpleNamespace(release_id=self.release_id), self.verified),
            ),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch.object(rollback, "wait_legacy_ready"),
        ):
            rolled = rollback_legacy_to_previous(
                self.target, platform, first.release_id, health_timeout=2
            )

        self.assertEqual(("succeeded", first.release_id), (
            rolled.outcome, rolled.to_release_id,
        ), (rolled, platform.events, self._archive_bytes()))
        self.assertEqual(first_archives, self._archive_bytes())
        self.assertEqual((first.release_id,), tuple(
            item.release_id for item in load_active_state(self.target.state_root).releases
        ))
        self.assertIsNotNone(platform.current)


if __name__ == "__main__":
    unittest.main()
