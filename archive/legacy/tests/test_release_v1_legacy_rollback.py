"""Explicit rollback of one committed transition legacy CDN install."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
import zipfile

from tests.release_v1_fixtures import make_patch_overlay
from tests.test_release_v1_compatibility import _active, _ownership
from tests.test_release_v1_legacy_compatibility import _verified
from wf_release_v1._platform_state import ManagedProcess
from wf_release_v1._receipt_contract import OperationReceipt
from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.compatibility import ActiveRelease
from wf_release_v1.errors import ReleaseError
from wf_release_v1.receipts import (
    commit_active_state,
    load_active_state,
    load_operation_receipt,
    operation_reservation,
    write_phase_receipt,
)
from wf_release_v1.target import ComponentRoots, LaunchSpec, ManagedTarget, TargetCompatibility
from wf_release_v1.verifier_overlay import inspect_overlay_chain


INSTALL_OPERATION = "20260813T010203.000000Z-0123456789abcdef0123456789abcdef"
ROLLBACK_OPERATION = "20260813T020304.000000Z-fedcba9876543210fedcba9876543210"
NEW_ID = "sha256:" + "a" * 64
OLD_ID = "sha256:" + "b" * 64
SHA = "c" * 64
NOW = datetime(2026, 8, 13, 1, 2, 3, tzinfo=timezone.utc)


class FakePlatform:
    def __init__(self) -> None:
        self.current: ManagedProcess | None = ManagedProcess(10, 100, SHA, INSTALL_OPERATION)
        self.events: list[str] = []

    def current_process(self) -> ManagedProcess | None:
        self.events.append("current")
        return self.current

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        del timeout
        self.events.append("stop")
        if process != self.current:
            raise AssertionError("unowned process stop")
        self.current = None
        return False

    def start_server(self, launch, environment, operation_id: str) -> ManagedProcess:
        del launch, environment
        self.events.append("start")
        self.current = ManagedProcess(11, 101, SHA, operation_id)
        return self.current


class LegacyRollbackTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wfrel-legacy-rollback-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        roots = {
            name: self.root / name
            for name in (
                "server", "runtime", "data", "state", "cdn", "modes",
                "content", "server-components", "mode-components",
            )
        }
        for path in roots.values():
            path.mkdir()
        for layer in ("common", "medium", "android"):
            (roots["cdn"] / "cn" / f"archive-{layer}-diff").mkdir(parents=True)
        self.target = ManagedTarget(
            roots["server"], roots["runtime"], roots["data"], roots["state"],
            roots["cdn"], roots["modes"],
            ComponentRoots(roots["content"], roots["server-components"], roots["mode-components"]),
            TargetCompatibility("1.4.54", "1.4.54", True),
            "http://127.0.0.1:8001",
        )
        self.outer = make_patch_overlay(
            self.root / "overlay.zip", from_version="1.4.54", target_version="1.4.55"
        )
        overlay = inspect_overlay_chain((self.outer,))
        original = _verified(overlay=overlay)
        outer_raw = self.outer.read_bytes()
        content_file = replace(
            original.manifest.files[0],
            path="content/overlay.zip",
            size=len(outer_raw),
            sha256=hashlib.sha256(outer_raw).hexdigest(),
        )
        self.verified = type(original)(
            replace(original.manifest, release_id=NEW_ID, files=(content_file,)),
            original.requirements,
            original.ownership,
            overlay,
        )
        candidate = roots["content"] / NEW_ID.replace(":", "-") / "patches" / "1.4.55"
        candidate.mkdir(parents=True)
        (candidate / "overlay.zip").write_bytes(self.outer.read_bytes())
        with zipfile.ZipFile(self.outer) as bundle:
            for archive in overlay.edges[0].archives:
                destination = roots["cdn"] / "cn" / Path(archive.relative_path)
                destination.write_bytes(bundle.read(archive.relative_path))

        old_ownership = _ownership(entities=("character:100001",), records=("characters:100001",))
        new_ownership = _ownership(entities=("character:100002",), records=("characters:100002",))
        previous = _active(ActiveRelease(OLD_ID, old_ownership))
        current = _active(
            ActiveRelease(NEW_ID, new_ownership), ActiveRelease(OLD_ID, old_ownership),
            known_release_ids=(OLD_ID,),
        )
        commit_active_state(self.target.state_root, previous=_active(), active=previous)
        commit_active_state(self.target.state_root, previous=previous, active=current)
        write_phase_receipt(self.target.state_root, OperationReceipt(
            2, INSTALL_OPERATION, NEW_ID, "COMMITTED", "succeeded", NOW, NOW,
            (OLD_ID,), (NEW_ID,), None, None, "legacy",
        ))
        obj = self.target.state_root / "objects" / NEW_ID.replace(":", "-")
        obj.mkdir(parents=True)
        (obj / "release.wf-release.zip").write_bytes(b"retained-object")
        self.launch = LaunchSpec(
            self.target.runtime_pack / "node.exe",
            self.target.server_bundle / "prepare.js",
            self.target.server_bundle / "server.js",
            self.target.server_bundle,
        )

    def _run(self, platform: FakePlatform, **patches: object):
        from wf_release_v1.legacy_rollback import rollback_legacy_to_previous

        module = "wf_release_v1.legacy_rollback"
        injected = [
            mock.patch(f"{module}.new_operation_id", return_value=ROLLBACK_OPERATION),
            mock.patch(
                f"{module}.verify_release_contract",
                return_value=(SimpleNamespace(release_id=NEW_ID), self.verified),
            ),
            mock.patch.object(ManagedTarget, "launch_spec", return_value=self.launch),
            mock.patch(f"{module}.wait_legacy_ready"),
        ]
        for name, value in patches.items():
            injected.append(mock.patch(f"{module}.{name}", side_effect=value))
        with ExitStack() as stack:
            for patcher in injected:
                stack.enter_context(patcher)
            return rollback_legacy_to_previous(self.target, platform, OLD_ID, health_timeout=2)

    def _cdn_files(self) -> tuple[str, ...]:
        return tuple(sorted(
            path.name
            for layer in ("common", "medium", "android")
            for path in (self.target.cdn_root / "cn" / f"archive-{layer}-diff").iterdir()
        ))

    def test_legacy_rollback_respects_operation_reservation(self) -> None:
        platform = FakePlatform()
        with operation_reservation(self.target.state_root, INSTALL_OPERATION):
            with self.assertRaises(ReleaseError) as caught:
                self._run(platform)
        self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
        self.assertEqual([], platform.events)

    def test_removes_exact_last_release_restarts_and_commits_previous_state(self) -> None:
        previous_overlay = make_patch_overlay(
            self.root / "previous-overlay.zip",
            from_version="1.4.53",
            target_version="1.4.54",
        )
        previous_names: list[str] = []
        with zipfile.ZipFile(previous_overlay) as bundle:
            for name in bundle.namelist():
                if not name.endswith(".zip"):
                    continue
                destination = self.target.cdn_root / "cn" / Path(name)
                destination.write_bytes(bundle.read(name))
                previous_names.append(destination.name)
        self.target = replace(
            self.target,
            compatibility=TargetCompatibility("1.4.54", "1.4.53", True),
        )
        platform = FakePlatform()
        result = self._run(platform)
        self.assertEqual(("succeeded", OLD_ID), (result.outcome, result.to_release_id))
        self.assertEqual(tuple(sorted(previous_names)), self._cdn_files())
        self.assertEqual(["stop", "start"], [event for event in platform.events if event != "current"])
        self.assertEqual((OLD_ID,), tuple(
            item.release_id for item in load_active_state(self.target.state_root).releases
        ))
        receipt = load_operation_receipt(self.target.state_root, ROLLBACK_OPERATION)
        self.assertEqual((2, "legacy", "COMMITTED"), (
            receipt.schema_version, receipt.target_protocol, receipt.phase,
        ))

    def test_mid_removal_or_readiness_failure_restores_all_archives_and_running_state(self) -> None:
        expected = self._cdn_files()
        platform = FakePlatform()
        from wf_release_v1.errors import ReleaseError
        calls = 0

        def fail_once(*_args: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ReleaseError("WFREL_REQUIRE_TARGET", "injected")

        result = self._run(
            platform,
            wait_legacy_ready=fail_once,
        )
        self.assertEqual("recovered", result.outcome)
        self.assertEqual(expected, self._cdn_files())
        self.assertIsNotNone(platform.current)

    def test_partial_removal_is_restored(self) -> None:
        from wf_release_v1.errors import ReleaseError

        expected = self._cdn_files()

        def remove_one_then_fail(switch) -> None:
            switch.archives[0].target_path.unlink()
            raise ReleaseError("WFREL_LEGACY_CDN_IO", "injected partial removal")

        platform = FakePlatform()
        result = self._run(platform, remove_legacy_archives=remove_one_then_fail)
        self.assertEqual("recovered", result.outcome)
        self.assertEqual(expected, self._cdn_files())
        self.assertIsNotNone(platform.current)

    def test_recovery_failure_stays_stopped_with_evidence(self) -> None:
        from wf_release_v1.errors import ReleaseError

        def remove_one_then_fail(switch) -> None:
            switch.archives[0].target_path.unlink()
            raise ReleaseError("WFREL_LEGACY_CDN_IO", "injected partial removal")

        platform = FakePlatform()
        result = self._run(
            platform,
            remove_legacy_archives=remove_one_then_fail,
            restore_removed_archives=ReleaseError(
                "WFREL_RECOVERY_FAILED", "injected recovery failure"
            ),
        )
        self.assertEqual("recovery_failed", result.outcome)
        self.assertIsNone(platform.current)
        self.assertTrue((
            self.target.state_root / "staging" / ROLLBACK_OPERATION
        ).is_dir())

    def test_changed_installed_archive_is_rejected_before_removal(self) -> None:
        from wf_release_v1._legacy_rollback_files import prepare_legacy_removal
        from wf_release_v1.errors import ReleaseError

        archive = next(
            path
            for layer in ("common", "medium", "android")
            for path in (self.target.cdn_root / "cn" / f"archive-{layer}-diff").iterdir()
        )
        original = archive.read_bytes()
        archive.write_bytes(b"X" * len(original))
        with self.assertRaises(ReleaseError) as raised:
            prepare_legacy_removal(
                self.verified,
                self.target.component_roots.content,
                self.target.state_root,
                self.target.cdn_root,
                ROLLBACK_OPERATION,
            )
        self.assertEqual("WFREL_LEGACY_CDN_IO", raised.exception.code)
        self.assertEqual(b"X" * len(original), archive.read_bytes())

    def test_unowned_or_wrong_protocol_fails_before_removing_archives(self) -> None:
        expected = self._cdn_files()
        platform = FakePlatform()
        platform.current = None
        from wf_release_v1.errors import ReleaseError
        from wf_release_v1.legacy_rollback import rollback_legacy_to_previous
        with self.assertRaises(ReleaseError) as unowned:
            self._run(platform)
        self.assertEqual("WFREL_LEGACY_PROCESS_NOT_OWNED", unowned.exception.code)
        self.assertEqual(expected, self._cdn_files())

        receipt_path = self.target.state_root / "receipts" / f"{INSTALL_OPERATION}.json"
        value = json.loads(receipt_path.read_text("utf-8"))
        value["targetProtocol"] = "capabilities-v1"
        receipt_path.write_bytes(canonical_json_bytes(value))
        platform.current = ManagedProcess(10, 100, SHA, INSTALL_OPERATION)
        with self.assertRaises(ReleaseError) as protocol:
            rollback_legacy_to_previous(self.target, platform, OLD_ID, health_timeout=2)
        self.assertEqual("WFREL_TARGET_PROTOCOL", protocol.exception.code)
        self.assertEqual(expected, self._cdn_files())


if __name__ == "__main__":
    unittest.main()
