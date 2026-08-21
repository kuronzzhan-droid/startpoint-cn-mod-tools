from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from wf_release_v1.canonical import canonical_json_bytes
from wf_release_v1.compatibility import ActiveRelease, ActiveState
from wf_release_v1.errors import ReleaseError
from wf_release_v1 import receipts as receipts_module
from wf_release_v1.receipts import (
    OperationReceipt,
    commit_active_state,
    load_active_state,
    new_operation_id,
    operation_reservation,
    write_phase_receipt,
)
from wf_release_v1.schema import OwnershipManifest


UTC = timezone.utc
STARTED = datetime(2026, 8, 12, 1, 2, 3, 456789, tzinfo=UTC)
UPDATED = STARTED + timedelta(seconds=1)
NONCE = bytes.fromhex("00112233445566778899aabbccddeeff")
OPERATION_ID = "20260812T010203.456789Z-00112233445566778899aabbccddeeff"
RELEASE_A = f"sha256:{'a' * 64}"
RELEASE_B = f"sha256:{'b' * 64}"


def _ownership(character_id: str) -> OwnershipManifest:
    return OwnershipManifest(
        schema_version=1,
        entities=(f"character:{character_id}",),
        records=(f"character:{character_id}",),
        paths=(f"character/custom_{character_id}/ui/square_0.png",),
    )


def _state(*release_ids: str) -> ActiveState:
    characters = ("310099", "310100")
    releases = tuple(
        ActiveRelease(release_id, _ownership(characters[index]))
        for index, release_id in enumerate(release_ids)
    )
    return ActiveState(
        client_version="1.4.54",
        resource_baseline="1.4.54",
        client_patch_profile=False,
        releases=releases,
        known_release_ids=tuple(release_ids),
    )


def _receipt(**changes: object) -> OperationReceipt:
    values: dict[str, object] = {
        "schema_version": 1,
        "operation_id": OPERATION_ID,
        "release_id": RELEASE_A,
        "phase": "CREATED",
        "outcome": "in_progress",
        "started_at": STARTED,
        "updated_at": STARTED,
        "before_release_ids": (),
        "candidate_release_ids": (RELEASE_A,),
        "error_code": None,
        "recovery_outcome": None,
    }
    values.update(changes)
    return OperationReceipt(**values)  # type: ignore[arg-type]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class OperationIdAndReceiptTests(unittest.TestCase):
    def test_operation_reservation_is_exclusive_and_nofollow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reservation = root / ".wf-release-v1.operation"
            with operation_reservation(root, OPERATION_ID):
                self.assertTrue(reservation.is_file())
                with self.assertRaises(ReleaseError) as caught:
                    with operation_reservation(root, OPERATION_ID):
                        pass
                self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
            self.assertFalse(reservation.exists())

            target = root / "outside"
            target.write_text("foreign", encoding="utf-8")
            try:
                reservation.symlink_to(target)
            except OSError:
                return
            with self.assertRaises(ReleaseError) as caught:
                with operation_reservation(root, OPERATION_ID):
                    pass
            self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
            self.assertEqual("foreign", target.read_text(encoding="utf-8"))

    def test_operation_id_is_deterministic_utc_and_path_safe(self) -> None:
        offset_now = STARTED.astimezone(timezone(timedelta(hours=10)))
        self.assertEqual(OPERATION_ID, new_operation_id(offset_now, NONCE))
        self.assertNotIn("/", OPERATION_ID)
        self.assertNotIn("\\", OPERATION_ID)

        for label, now, nonce in (
            ("naive time", STARTED.replace(tzinfo=None), NONCE),
            ("short nonce", STARTED, b"short"),
            ("long nonce", STARTED, NONCE + b"x"),
        ):
            with self.subTest(label=label), self.assertRaises(ReleaseError) as caught:
                new_operation_id(now, nonce)
            self.assertEqual("WFREL_RECEIPT_INVALID", caught.exception.code)

    def test_receipt_write_is_canonical_exact_private_and_updatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_phase_receipt(root, _receipt())
            path = root / "receipts" / f"{OPERATION_ID}.json"
            expected = {
                "beforeReleaseIds": [],
                "candidateReleaseIds": [RELEASE_A],
                "errorCode": None,
                "operationId": OPERATION_ID,
                "outcome": "in_progress",
                "phase": "CREATED",
                "recoveryOutcome": None,
                "releaseId": RELEASE_A,
                "schemaVersion": 1,
                "startedAt": "2026-08-12T01:02:03.456789Z",
                "updatedAt": "2026-08-12T01:02:03.456789Z",
            }
            self.assertEqual(expected, _read_json(path))
            self.assertEqual(canonical_json_bytes(expected), path.read_bytes())
            self.assertNotIn(directory.encode("utf-8"), path.read_bytes())
            self.assertNotIn(b"CN_ADMIN_TOKEN", path.read_bytes())
            self.assertNotIn(b"admin-token-must-stay-process-only", path.read_bytes())

            updated = _receipt(phase="VERIFIED", updated_at=UPDATED)
            write_phase_receipt(root, updated)
            self.assertEqual("VERIFIED", _read_json(path)["phase"])  # type: ignore[index]

    def test_receipt_rejects_bad_shape_time_ids_and_operation_reuse(self) -> None:
        invalid_changes = (
            {"schema_version": 3},
            {"release_id": "release-a"},
            {"phase": "created"},
            {"outcome": "warning"},
            {"updated_at": STARTED - timedelta(microseconds=1)},
            {"before_release_ids": (RELEASE_A, RELEASE_A)},
            {"candidate_release_ids": (RELEASE_B, RELEASE_A)},
            {"error_code": "C:/private/path"},
            {"recovery_outcome": "maybe"},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes), self.assertRaises(ReleaseError) as caught:
                _receipt(**changes)
            self.assertEqual("WFREL_RECEIPT_INVALID", caught.exception.code)

        for field, value in (("phase", []), ("outcome", {}), ("recovery_outcome", [])):
            with self.subTest(field=field):
                with self.assertRaises(ReleaseError) as caught:
                    _receipt(**{field: value})
                self.assertEqual("WFREL_RECEIPT_INVALID", caught.exception.code)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_phase_receipt(root, _receipt())
            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(root, _receipt(release_id=RELEASE_B))
            self.assertEqual("WFREL_RECEIPT_CONFLICT", caught.exception.code)
            self.assertEqual(RELEASE_A, _read_json(root / "receipts" / f"{OPERATION_ID}.json")["releaseId"])  # type: ignore[index]

    def test_baseline_bootstrap_is_an_explicit_monotonic_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_phase_receipt(root, _receipt(phase="VERIFIED"))
            write_phase_receipt(root, _receipt(
                phase="BASE_STARTED", updated_at=UPDATED,
            ))
            path = root / "receipts" / f"{OPERATION_ID}.json"
            self.assertEqual("BASE_STARTED", _read_json(path)["phase"])  # type: ignore[index]

            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(root, _receipt(
                    phase="VERIFIED", updated_at=UPDATED + timedelta(seconds=1),
                ))
            self.assertEqual("WFREL_RECEIPT_CONFLICT", caught.exception.code)

            write_phase_receipt(root, _receipt(
                phase="PROBED", updated_at=UPDATED + timedelta(seconds=1),
            ))
            self.assertEqual("PROBED", _read_json(path)["phase"])  # type: ignore[index]

    def test_receipt_atomic_faults_preserve_complete_old_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "receipts" / f"{OPERATION_ID}.json"
            write_phase_receipt(root, _receipt())
            old = path.read_bytes()
            updated = _receipt(phase="VERIFIED", updated_at=UPDATED)

            def failed_lock_write(writer: object, raw: bytes) -> None:
                writer.write(raw[:7])  # type: ignore[attr-defined]
                raise OSError("injected lock write")

            with mock.patch("wf_release_v1.receipts._write_exact", side_effect=failed_lock_write):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertEqual(old, path.read_bytes())
            self.assertFalse((root / ".wf-release-v1.lock").exists())

            real_write = receipts_module._write_exact
            write_calls = 0

            def partial_payload_write(writer: object, raw: bytes) -> None:
                nonlocal write_calls
                write_calls += 1
                if write_calls == 2:
                    writer.write(raw[:7])  # type: ignore[attr-defined]
                    raise OSError("injected partial payload write")
                real_write(writer, raw)  # type: ignore[arg-type]

            with mock.patch("wf_release_v1.receipts._write_exact", side_effect=partial_payload_write):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertEqual(old, path.read_bytes())

            with mock.patch("wf_release_v1.receipts.os.replace", side_effect=OSError("replace")):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertEqual(old, path.read_bytes())

            real_fsync = os.fsync
            fsync_calls = 0

            def fail_payload_fsync(descriptor: int) -> None:
                nonlocal fsync_calls
                fsync_calls += 1
                if fsync_calls == 2:
                    raise OSError("injected payload fsync failure")
                real_fsync(descriptor)

            with mock.patch("wf_release_v1.receipts.os.fsync", side_effect=fail_payload_fsync):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertEqual(old, path.read_bytes())
            self.assertEqual([], list((root / "receipts").glob(".*.tmp")))

    def test_receipt_rejects_temp_and_lock_identity_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "receipts" / f"{OPERATION_ID}.json"
            write_phase_receipt(root, _receipt())
            old = path.read_bytes()
            updated = _receipt(phase="VERIFIED", updated_at=UPDATED)
            real_replace = os.replace

            def replace_payload_temp(source: Path, destination: Path) -> None:
                if source.suffix == ".tmp":
                    source.unlink()
                    source.write_bytes(b"not the synchronized receipt")
                real_replace(source, destination)

            with mock.patch("wf_release_v1.receipts.os.replace", side_effect=replace_payload_temp):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
            self.assertEqual(old, path.read_bytes())
            self.assertEqual([], list((root / "receipts").glob(".*")))

            real_atomic = receipts_module._atomic_write

            def replace_lock(*args: object) -> None:
                real_atomic(*args)  # type: ignore[arg-type]
                lock = root / ".wf-release-v1.lock"
                lock.unlink()
                lock.write_bytes(b"unknown lock owner")

            with mock.patch("wf_release_v1.receipts._atomic_write", side_effect=replace_lock):
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, updated)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
            self.assertEqual(b"unknown lock owner", (root / ".wf-release-v1.lock").read_bytes())

    def test_receipt_rejects_oversized_or_regressive_updates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(root, _receipt(error_code="WFREL_" + "A" * (256 * 1024)))
            self.assertEqual("WFREL_RECEIPT_INVALID", caught.exception.code)
            self.assertEqual([], list(root.iterdir()))

            write_phase_receipt(root, _receipt())
            completed = _receipt(phase="VERIFIED", outcome="succeeded", updated_at=UPDATED)
            write_phase_receipt(root, completed)
            path = root / "receipts" / f"{OPERATION_ID}.json"
            old = path.read_bytes()
            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(
                    root,
                    _receipt(updated_at=UPDATED + timedelta(seconds=1)),
                )
            self.assertEqual("WFREL_RECEIPT_CONFLICT", caught.exception.code)
            self.assertEqual(old, path.read_bytes())

    def test_existing_lock_is_never_guessed_stale_or_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / ".wf-release-v1.lock"
            raw = canonical_json_bytes(
                {"createdAt": "2000-01-01T00:00:00.000000Z", "nonce": "11" * 16}
            )
            lock.write_bytes(raw)
            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(root, _receipt())
            self.assertEqual("WFREL_STATE_LOCKED", caught.exception.code)
            self.assertEqual(raw, lock.read_bytes())




if __name__ == "__main__":
    unittest.main()
