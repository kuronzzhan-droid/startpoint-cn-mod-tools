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

            updated = _receipt(phase="VERIFIED", updated_at=UPDATED)
            write_phase_receipt(root, updated)
            self.assertEqual("VERIFIED", _read_json(path)["phase"])  # type: ignore[index]

    def test_receipt_rejects_bad_shape_time_ids_and_operation_reuse(self) -> None:
        invalid_changes = (
            {"schema_version": 2},
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


class ActiveStatePersistenceTests(unittest.TestCase):
    def test_reparse_root_is_rejected_before_io(self) -> None:
        fake = SimpleNamespace(
            st_dev=1,
            st_ino=2,
            st_size=0,
            st_mtime_ns=0,
            st_mode=stat.S_IFDIR,
            st_file_attributes=0x0400,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(Path, "lstat", return_value=fake), mock.patch(
                "wf_release_v1.receipts._open_exclusive",
                side_effect=AssertionError("reparse root reached I/O"),
            ) as opened:
                with self.assertRaises(ReleaseError) as caught:
                    write_phase_receipt(root, _receipt())
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
            opened.assert_not_called()

    def test_noncanonical_user_root_alias_is_rejected_before_io(self) -> None:
        root = Path.home() / ".codex" / ".."
        self.assertTrue((Path.home() / ".codex").is_dir())
        with mock.patch(
            "wf_release_v1.receipts._open_exclusive",
            side_effect=AssertionError("root alias reached I/O"),
        ) as opened:
            with self.assertRaises(ReleaseError) as caught:
                write_phase_receipt(root, _receipt())
        self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
        opened.assert_not_called()

    def test_commit_rejects_malformed_in_memory_state_with_stable_error(self) -> None:
        malformed = (
            replace(_state(), releases=(object(),)),
            replace(
                _state(RELEASE_A),
                releases=(ActiveRelease(RELEASE_A, object()),),  # type: ignore[arg-type]
            ),
            replace(_state(), known_release_ids=[]),  # type: ignore[arg-type]
        )
        for state in malformed:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ReleaseError) as caught:
                    commit_active_state(root, previous=_state(), active=state)
                self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
                self.assertEqual([], list(root.iterdir()))

    def test_commit_and_load_preserve_exact_previous_and_active_state(self) -> None:
        empty = _state()
        first = _state(RELEASE_A)
        second = _state(RELEASE_A, RELEASE_B)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commit_active_state(root, previous=empty, active=first)
            self.assertEqual(first, load_active_state(root))
            self.assertEqual([], _read_json(root / "previous.json")["releases"])  # type: ignore[index]

            commit_active_state(root, previous=first, active=second)
            self.assertEqual(second, load_active_state(root))
            self.assertEqual([RELEASE_A], _read_json(root / "previous.json")["knownReleaseIds"])  # type: ignore[index]
            self.assertEqual(canonical_json_bytes(_read_json(root / "active.json")), (root / "active.json").read_bytes())

    def test_load_rejects_missing_noncanonical_unknown_and_duplicate_state(self) -> None:
        valid = {
            "clientPatchProfile": False,
            "clientVersion": "1.4.54",
            "knownReleaseIds": [RELEASE_A],
            "releases": [
                {
                    "ownership": _ownership("310099").to_wire(),
                    "releaseId": RELEASE_A,
                }
            ],
            "resourceBaseline": "1.4.54",
            "schemaVersion": 1,
        }
        cases = (
            ("missing", None),
            ("noncanonical", json.dumps(valid, indent=2).encode("utf-8")),
            ("unknown", canonical_json_bytes({**valid, "extra": 1})),
            (
                "duplicate release",
                canonical_json_bytes({**valid, "releases": valid["releases"] * 2}),
            ),
            (
                "duplicate known id",
                canonical_json_bytes({**valid, "knownReleaseIds": [RELEASE_A, RELEASE_A]}),
            ),
            ("oversized", b"{" + b" " * (256 * 1024) + b"}"),
        )
        for label, raw in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if raw is not None:
                    (root / "active.json").write_bytes(raw)
                with self.assertRaises(ReleaseError) as caught:
                    load_active_state(root)
                self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
                self.assertNotIn(directory, str(caught.exception))

    def test_commit_rejects_stale_or_corrupt_existing_state_without_switching_active(self) -> None:
        empty = _state()
        first = _state(RELEASE_A)
        second = _state(RELEASE_A, RELEASE_B)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commit_active_state(root, previous=empty, active=first)
            active_path = root / "active.json"
            old_active = active_path.read_bytes()

            with self.assertRaises(ReleaseError) as caught:
                commit_active_state(root, previous=empty, active=second)
            self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
            self.assertEqual(old_active, active_path.read_bytes())

            (root / "previous.json").write_bytes(b"not json")
            with self.assertRaises(ReleaseError) as caught:
                commit_active_state(root, previous=first, active=second)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)
            self.assertEqual(old_active, active_path.read_bytes())

    def test_active_replace_failure_keeps_old_active_as_commit_point(self) -> None:
        empty = _state()
        first = _state(RELEASE_A)
        second = _state(RELEASE_A, RELEASE_B)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commit_active_state(root, previous=empty, active=first)
            old_active = (root / "active.json").read_bytes()
            real_replace = os.replace
            calls = 0

            def fail_active(source: object, target: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected active replace failure")
                real_replace(source, target)

            with mock.patch("wf_release_v1.receipts.os.replace", side_effect=fail_active):
                with self.assertRaises(ReleaseError) as caught:
                    commit_active_state(root, previous=first, active=second)
            self.assertEqual("WFREL_STATE_IO", caught.exception.code)
            self.assertEqual(old_active, (root / "active.json").read_bytes())
            self.assertEqual(first, load_active_state(root))

    def test_symlink_state_root_and_active_leaf_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real_root = base / "real"
            real_root.mkdir()
            commit_active_state(real_root, previous=_state(), active=_state(RELEASE_A))
            linked_root = base / "linked"
            try:
                linked_root.symlink_to(real_root, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink unavailable: {error}")

            with self.assertRaises(ReleaseError) as caught:
                load_active_state(linked_root)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)

            leaf_root = base / "leaf-root"
            leaf_root.mkdir()
            (leaf_root / "active.json").symlink_to(real_root / "active.json")
            with self.assertRaises(ReleaseError) as caught:
                load_active_state(leaf_root)
            self.assertEqual("WFREL_STATE_INVALID", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
