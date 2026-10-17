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
            replace(
                _state(RELEASE_A),
                releases=(
                    ActiveRelease(
                        RELEASE_A,
                        OwnershipManifest(1, 7, (), ()),  # type: ignore[arg-type]
                    ),
                ),
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

    def test_commit_rejects_state_larger_than_the_reader_limit(self) -> None:
        ownership = OwnershipManifest(
            1,
            ("character:310099",),
            ("character:310099",),
            ("character/" + "a" * (256 * 1024),),
        )
        oversized = ActiveState(
            "1.4.54",
            "1.4.54",
            False,
            (ActiveRelease(RELEASE_A, ownership),),
            (RELEASE_A,),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ReleaseError) as caught:
                commit_active_state(root, previous=_state(), active=oversized)
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

    def test_initial_commit_rejects_a_retained_previous_without_active(self) -> None:
        empty = _state()
        first = _state(RELEASE_A)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "previous.json").write_bytes(canonical_json_bytes({
                "schemaVersion": 1,
                "clientVersion": empty.client_version,
                "resourceBaseline": empty.resource_baseline,
                "clientPatchProfile": empty.client_patch_profile,
                "releases": [],
                "knownReleaseIds": [],
            }))
            before = (root / "previous.json").read_bytes()

            with self.assertRaises(ReleaseError) as caught:
                commit_active_state(root, previous=empty, active=first)

            self.assertEqual("WFREL_STATE_CONFLICT", caught.exception.code)
            self.assertEqual(before, (root / "previous.json").read_bytes())
            self.assertFalse((root / "active.json").exists())

    def test_active_replace_failure_keeps_old_active_as_commit_point(self) -> None:
        empty, first = _state(), _state(RELEASE_A)
        second = _state(RELEASE_A, RELEASE_B)
        cases = (("failure", "WFREL_STATE_IO"), ("drift", "WFREL_STATE_INVALID"), ("restore-failure", "WFREL_STATE_IO"))
        for mode, code in cases:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                commit_active_state(root, previous=empty, active=first)
                old_active = (root / "active.json").read_bytes()
                real_replace = os.replace
                calls = 0

                def fail_active(source: Path, target: Path) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == 2 and mode == "failure":
                        raise OSError("injected active replace failure")
                    if calls == 2:
                        source.unlink()
                        source.write_bytes(b"not the synchronized active state")
                    if calls == 3 and mode == "restore-failure":
                        raise OSError("injected active restore failure")
                    real_replace(source, target)

                with mock.patch("wf_release_v1.receipts.os.replace", side_effect=fail_active):
                    with self.assertRaises(ReleaseError) as caught:
                        commit_active_state(root, previous=first, active=second)
                self.assertEqual(code, caught.exception.code)
                if mode == "restore-failure":
                    self.assertEqual([old_active], [item.read_bytes() for item in root.glob("*.rollback")])
                else:
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
