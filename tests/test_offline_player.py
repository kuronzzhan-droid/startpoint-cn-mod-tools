#!/usr/bin/env python3
"""Focused tests for the offline Player 1000 initial-character overlay."""
from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import stat
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_mod_tool as core  # noqa: E402

try:  # Keep discovery alive so RED shows both missing interfaces clearly.
    import wf_offline_player as module  # type: ignore[import-not-found]  # noqa: E402
except ModuleNotFoundError:
    module = None


TARGET_RELATIVE = Path("51") / "b73a9401c1fae38366ee79f4274942254d389c"
INITIAL_CHARACTER_IDS = ("129999", "139999", "149999")
FORBIDDEN_WEAPON_IDS = tuple(str(value) for value in range(8_000_101, 8_000_116))


def build_orderedmap(
    entries: list[tuple[str, bytes]], *, compress_rows: bool, level: int = 9
) -> bytes:
    """Build a fixture with non-default compression to expose row re-encoding."""
    key_blob = b""
    row_blob = b""
    pairs: list[tuple[int, int]] = []
    for key, row in entries:
        key_blob += key.encode("utf-8")
        row_blob += zlib.compress(row, level) if compress_rows and row else row
        pairs.append((len(key_blob), len(row_blob)))
    index = bytearray(struct.pack("<I", len(entries)))
    for key_end, row_end in pairs:
        index += struct.pack("<II", key_end, row_end)
    index += key_blob
    packed_index = zlib.compress(bytes(index), level)
    return struct.pack("<I", len(packed_index)) + packed_index + row_blob


def raw_rows(raw: bytes) -> tuple[list[str], list[bytes]]:
    keys, pairs, index_len = core.parse_index(raw)
    blob = raw[4 + index_len :]
    rows: list[bytes] = []
    previous = 0
    for _, row_end in pairs:
        rows.append(blob[previous:row_end])
        previous = row_end
    return keys, rows


def mutate_index_pair(raw: bytes, pair_index: int, *, key_end=None, row_end=None) -> bytes:
    old_index_len = struct.unpack_from("<I", raw, 0)[0]
    index = bytearray(zlib.decompress(raw[4 : 4 + old_index_len]))
    pair_offset = 4 + pair_index * 8
    old_key_end, old_row_end = struct.unpack_from("<II", index, pair_offset)
    struct.pack_into(
        "<II",
        index,
        pair_offset,
        old_key_end if key_end is None else key_end,
        old_row_end if row_end is None else row_end,
    )
    packed = zlib.compress(bytes(index))
    return struct.pack("<I", len(packed)) + packed + raw[4 + old_index_len :]


def nested_bytes(players: dict[str, dict[str, str]]) -> bytes:
    outer: list[tuple[str, bytes]] = []
    for player_id, rows in players.items():
        inner = build_orderedmap(
            [(key, value.encode("utf-8")) for key, value in rows.items()],
            compress_rows=True,
        )
        outer.append((player_id, inner))
    return build_orderedmap(outer, compress_rows=False)


def parse_nested(raw: bytes) -> dict[str, dict[str, str]]:
    keys, rows = raw_rows(raw)
    return {
        key: core.read_orderedmap_file_from_bytes(row)
        for key, row in zip(keys, rows)
    }


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class OfflinePlayerOverlayTests(unittest.TestCase):
    def require_module(self):
        self.assertIsNotNone(module, "missing wf_offline_player module")
        return module

    def test_bytes_reader_preserves_raw_rows_and_key_order(self) -> None:
        self.assertTrue(
            hasattr(core, "read_orderedmap_raw_rows_from_bytes"),
            "missing read_orderedmap_raw_rows_from_bytes",
        )
        raw = build_orderedmap(
            [("z", b"first"), ("a", b"second")], compress_rows=True, level=9
        )
        expected_keys, expected_rows = raw_rows(raw)

        parsed = core.read_orderedmap_raw_rows_from_bytes(raw, "fixture")

        self.assertEqual(parsed.logical_path, "fixture")
        self.assertEqual(parsed.keys, expected_keys)
        self.assertEqual(parsed.rows, expected_rows)

    def test_bytes_reader_rejects_nonmonotonic_bounds_tail_and_duplicates(self) -> None:
        inner = build_orderedmap([("1", b"1")], compress_rows=True)
        valid = build_orderedmap(
            [("1000", inner), ("2000", inner)], compress_rows=False
        )
        keys, pairs, index_len = core.parse_index(valid)
        index = zlib.decompress(valid[4 : 4 + index_len])
        key_blob_length = len(index) - (4 + len(keys) * 8)
        blob_length = len(valid) - (4 + index_len)
        malformed = (
            mutate_index_pair(valid, 1, key_end=pairs[0][0] - 1),
            mutate_index_pair(valid, 1, row_end=pairs[0][1] - 1),
            mutate_index_pair(valid, 1, key_end=key_blob_length + 1),
            mutate_index_pair(valid, 1, row_end=blob_length + 1),
            valid + b"tail",
            build_orderedmap(
                [("1000", inner), ("2000", inner), ("2000", inner)],
                compress_rows=False,
            ),
        )

        for raw in malformed:
            with self.subTest(size=len(raw)):
                with self.assertRaisesRegex(ValueError, "length mismatch|duplicate"):
                    core.read_orderedmap_raw_rows_from_bytes(raw, "outer fixture")

    def test_overlay_rejects_malformed_inner_tail_and_duplicate_unrelated_character(self) -> None:
        overlay = self.require_module()
        valid_inner = build_orderedmap([("7", b"2")], compress_rows=True)
        duplicate_inner = build_orderedmap(
            [("7", b"2"), ("7", b"2")], compress_rows=True
        )
        malformed_rows = (valid_inner + b"tail", duplicate_inner)

        for inner in malformed_rows:
            raw = build_orderedmap([("1000", inner)], compress_rows=False)
            with self.subTest(size=len(inner)):
                with self.assertRaisesRegex(
                    overlay.PlayerOverlayError, "player 1000|duplicate|length mismatch"
                ):
                    overlay.add_initial_characters_to_bytes(raw)

    def test_overlay_preserves_existing_row_and_adds_only_three_level_one_rows(self) -> None:
        overlay = self.require_module()
        raw = nested_bytes({"1000": {"7": "2"}, "2000": {"8": "3"}})
        before_outer_keys, before_outer_rows = raw_rows(raw)
        before_inner_keys, before_inner_rows = raw_rows(before_outer_rows[0])

        output, report = overlay.add_initial_characters_to_bytes(raw)

        self.assertEqual(
            parse_nested(output),
            {
                "1000": {
                    "7": "2",
                    "129999": "1",
                    "139999": "1",
                    "149999": "1",
                },
                "2000": {"8": "3"},
            },
        )
        after_outer_keys, after_outer_rows = raw_rows(output)
        after_inner_keys, after_inner_rows = raw_rows(after_outer_rows[0])
        self.assertEqual(after_outer_keys, before_outer_keys)
        self.assertEqual(after_outer_rows[1], before_outer_rows[1])
        self.assertEqual(after_inner_keys[: len(before_inner_keys)], before_inner_keys)
        self.assertEqual(after_inner_rows[: len(before_inner_rows)], before_inner_rows)
        self.assertEqual(report.added_character_ids, INITIAL_CHARACTER_IDS)
        self.assertEqual(report.character_level, 1)

    def test_overlay_rejects_missing_player_and_non_idempotent_conflict(self) -> None:
        overlay = self.require_module()
        with self.assertRaisesRegex(overlay.PlayerOverlayError, "player 1000"):
            overlay.add_initial_characters_to_bytes(nested_bytes({"999": {"1": "2"}}))
        with self.assertRaisesRegex(
            overlay.PlayerOverlayError, "conflicting character level"
        ):
            overlay.add_initial_characters_to_bytes(
                nested_bytes({"1000": {"129999": "80"}})
            )

    def test_overlay_is_idempotent_and_reports_only_new_rows(self) -> None:
        overlay = self.require_module()
        raw = nested_bytes({"1000": {"139999": "1", "7": "2"}})

        first, first_report = overlay.add_initial_characters_to_bytes(raw)
        second, second_report = overlay.add_initial_characters_to_bytes(first)

        self.assertEqual(first_report.added_character_ids, ("129999", "149999"))
        self.assertEqual(second_report.added_character_ids, ())
        self.assertEqual(second, first)
        self.assertEqual(
            list(parse_nested(first)["1000"]),
            ["139999", "7", "129999", "149999"],
        )

    def test_staged_apply_changes_only_target_and_never_source_or_weapons(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source-common"
            staged = root / "staged-common"
            target = source / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))
            possession = source / "aa" / ("0" * 38)
            possession.parent.mkdir(parents=True)
            possession.write_bytes(nested_bytes({"1000": {"700001": "1"}}))
            shutil.copytree(source, staged)
            source_before = snapshot_tree(source)
            staged_before = snapshot_tree(staged)

            with mock.patch.object(overlay.os, "fsync", wraps=os.fsync) as fsync:
                report = overlay.apply_initial_player_overlay(staged)

            staged_after = snapshot_tree(staged)
            expected_after = dict(staged_before)
            expected_after[TARGET_RELATIVE.as_posix()] = report.after_sha256
            self.assertEqual(staged_after, expected_after)
            self.assertEqual(snapshot_tree(source), source_before)
            self.assertEqual(report.added_character_ids, INITIAL_CHARACTER_IDS)
            self.assertEqual(report.relative_path, TARGET_RELATIVE.as_posix())
            self.assertTrue(fsync.called)
            self.assertEqual(
                parse_nested((staged / TARGET_RELATIVE).read_bytes())["1000"]["149999"],
                "1",
            )
            for path in staged.rglob("*"):
                if not path.is_file():
                    continue
                decoded = parse_nested(path.read_bytes())
                flattened = repr(decoded)
                for weapon_id in FORBIDDEN_WEAPON_IDS:
                    self.assertNotIn(weapon_id, flattened)

    def test_staged_apply_does_not_scan_the_full_tree(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))

            with mock.patch.object(
                overlay,
                "_snapshot_tree",
                create=True,
                side_effect=AssertionError("production must not scan the staged tree"),
            ):
                report = overlay.apply_initial_player_overlay(staged)

            self.assertEqual(report.added_character_ids, INITIAL_CHARACTER_IDS)

    def test_idempotent_staged_apply_does_not_create_replace_or_touch_target(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            original = nested_bytes(
                {"1000": {character_id: "1" for character_id in INITIAL_CHARACTER_IDS}}
            )
            target.write_bytes(original)
            before = target.stat()
            temporary = target.with_name(target.name + ".wf-offline-new")

            with mock.patch.object(overlay.os, "replace") as replace:
                report = overlay.apply_initial_player_overlay(staged)

            after = target.stat()
            replace.assert_not_called()
            self.assertFalse(temporary.exists())
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual((after.st_dev, after.st_ino, after.st_mtime_ns),
                             (before.st_dev, before.st_ino, before.st_mtime_ns))
            self.assertEqual(report.added_character_ids, ())

    def test_existing_temp_is_never_overwritten_or_cleaned(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))
            temporary = target.with_name(target.name + ".wf-offline-new")
            temporary.write_bytes(b"caller-owned")

            with self.assertRaisesRegex(overlay.PlayerOverlayError, "temporary"):
                overlay.apply_initial_player_overlay(staged)

            self.assertEqual(temporary.read_bytes(), b"caller-owned")
            self.assertEqual(parse_nested(target.read_bytes()), {"1000": {"7": "2"}})

    def test_reparse_target_temp_and_parent_are_rejected(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))
            temporary = target.with_name(target.name + ".wf-offline-new")
            original_lstat = Path.lstat

            for forbidden in (staged, target.parent, target, temporary):
                if forbidden == temporary:
                    temporary.write_bytes(b"sentinel")

                def marked_lstat(path: Path, *, _forbidden=forbidden):
                    metadata = original_lstat(path)
                    if path == _forbidden:
                        return SimpleNamespace(
                            st_mode=metadata.st_mode,
                            st_file_attributes=getattr(metadata, "st_file_attributes", 0)
                            | getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
                        )
                    return metadata

                with self.subTest(path=forbidden):
                    with mock.patch.object(Path, "lstat", autospec=True, side_effect=marked_lstat):
                        with self.assertRaisesRegex(overlay.PlayerOverlayError, "reparse"):
                            overlay.apply_initial_player_overlay(staged)
                if temporary.exists():
                    temporary.unlink()

    def test_replace_failure_cleans_only_exact_new_temp(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            original = nested_bytes({"1000": {"7": "2"}})
            target.write_bytes(original)
            adjacent = target.with_name(target.name + ".wf-offline-new.keep")
            adjacent.write_bytes(b"keep")
            temporary = target.with_name(target.name + ".wf-offline-new")

            commit_patch = (
                mock.patch.object(
                    overlay, "_commit_windows_handle", side_effect=OSError("boom")
                )
                if os.name == "nt"
                else mock.patch.object(overlay.os, "replace", side_effect=OSError("boom"))
            )
            with commit_patch:
                with self.assertRaisesRegex(overlay.PlayerOverlayError, "atomic replace"):
                    overlay.apply_initial_player_overlay(staged)

            self.assertFalse(temporary.exists())
            self.assertEqual(adjacent.read_bytes(), b"keep")
            self.assertEqual(target.read_bytes(), original)

    def test_posix_file_operations_are_relative_nofollow(self) -> None:
        overlay = self.require_module()
        open_existing = getattr(overlay, "_open_existing_at", None)
        replace_relative = getattr(overlay, "_replace_relative", None)
        self.assertIsNotNone(open_existing)
        self.assertIsNotNone(replace_relative)
        calls = []
        sentinel_nofollow = 0x40000000

        def recording_open(path, flags, mode=0o777, *, dir_fd=None):
            calls.append((path, flags, mode, dir_fd))
            return 73

        with mock.patch.object(overlay.os, "open", side_effect=recording_open):
            descriptor = open_existing(41, "target", nofollow_flag=sentinel_nofollow)
        self.assertEqual(descriptor, 73)
        self.assertEqual(calls[0][0], "target")
        self.assertEqual(calls[0][3], 41)
        self.assertTrue(calls[0][1] & sentinel_nofollow)

        with mock.patch.object(overlay.os, "replace") as replace:
            replace_relative(41, "temporary", "target")
        replace.assert_called_once_with(
            "temporary", "target", src_dir_fd=41, dst_dir_fd=41
        )

    def test_posix_owned_temp_uses_private_0700_dir_and_relative_payload(self) -> None:
        overlay = self.require_module()
        directory_metadata = SimpleNamespace(
            st_dev=1, st_ino=2, st_mode=stat.S_IFDIR | 0o700,
            st_size=0, st_mtime_ns=3, st_file_attributes=0,
        )
        payload_metadata = SimpleNamespace(
            st_dev=1, st_ino=3, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=4, st_file_attributes=0,
        )
        with mock.patch.object(
            overlay.secrets, "token_hex", return_value="a" * 32
        ), mock.patch.object(overlay.os, "mkdir") as mkdir, mock.patch.object(
            overlay.os, "open", return_value=51
        ) as open_file, mock.patch.object(
            overlay.os, "fstat",
            side_effect=[directory_metadata, payload_metadata, payload_metadata],
        ), mock.patch.object(
            overlay.os, "stat", return_value=directory_metadata
        ), mock.patch.object(
            overlay.store, "_open_exclusive_at", return_value=52
        ) as open_payload, mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(
            overlay.os, "rmdir"
        ), mock.patch.object(
            overlay.os, "O_DIRECTORY", 0x100000, create=True
        ), mock.patch.object(
            overlay.os, "O_NOFOLLOW", 0x200000, create=True
        ):
            owned = overlay._PosixOwnedTemp.create(41)
            owned.finish_success()

        directory_name = ".wf-offline-txn-" + "a" * 32
        mkdir.assert_called_once_with(directory_name, 0o700, dir_fd=41)
        self.assertEqual(open_file.call_args.args[0], directory_name)
        self.assertEqual(open_file.call_args.kwargs["dir_fd"], 41)
        open_payload.assert_called_once_with(
            51, "payload", nofollow_flag=0x200000
        )
        contract = overlay._PosixOwnedTemp.__doc__ or ""
        self.assertIn("same-uid process", contract)
        self.assertIn("sticky parent owner", contract)

    def test_posix_owned_temp_commit_is_cross_dirfd_relative(self) -> None:
        overlay = self.require_module()
        owned = object.__new__(overlay._PosixOwnedTemp)
        owned.parent_descriptor = 41
        owned.directory_descriptor = 52

        with mock.patch.object(overlay.os, "replace") as replace:
            owned.commit("target")

        replace.assert_called_once_with(
            "payload", "target", src_dir_fd=52, dst_dir_fd=41
        )

    def test_posix_guard_rejects_nonsticky_shared_writable_parent_before_create(self) -> None:
        overlay = self.require_module()
        metadata = SimpleNamespace(
            st_dev=1, st_ino=2, st_mode=stat.S_IFDIR | 0o0775,
            st_size=0, st_mtime_ns=3, st_ctime_ns=4, st_file_attributes=0,
        )
        signature = overlay.store._stat_signature(metadata)
        with mock.patch.object(
            overlay.store, "_require_same_lstat", return_value=metadata
        ), mock.patch.object(
            overlay.os, "open", return_value=41
        ), mock.patch.object(
            overlay.os, "fstat", return_value=metadata
        ), mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(
            overlay.os, "O_DIRECTORY", 0x100000, create=True
        ), mock.patch.object(
            overlay.os, "O_NOFOLLOW", 0x200000, create=True
        ), mock.patch.object(
            overlay._PosixOwnedTemp, "create"
        ) as create:
            with self.assertRaisesRegex(
                overlay.PlayerOverlayError, "non-sticky.*writable"
            ):
                with overlay._posix_transaction_guard(Path("parent"), signature) as fd:
                    create(fd)

        create.assert_not_called()

    def test_posix_guard_allows_sticky_shared_writable_parent(self) -> None:
        overlay = self.require_module()
        metadata = SimpleNamespace(
            st_dev=1, st_ino=2,
            st_mode=stat.S_IFDIR | stat.S_ISVTX | 0o0777,
            st_size=0, st_mtime_ns=3, st_ctime_ns=4, st_file_attributes=0,
        )
        signature = overlay.store._stat_signature(metadata)
        with mock.patch.object(
            overlay.store, "_require_same_lstat", return_value=metadata
        ), mock.patch.object(
            overlay.os, "open", return_value=41
        ), mock.patch.object(
            overlay.os, "fstat", return_value=metadata
        ), mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(
            overlay.os, "O_DIRECTORY", 0x100000, create=True
        ), mock.patch.object(
            overlay.os, "O_NOFOLLOW", 0x200000, create=True
        ):
            with overlay._posix_transaction_guard(Path("parent"), signature) as fd:
                self.assertEqual(fd, 41)
        self.assertIn("sticky parent owner", overlay._PosixOwnedTemp.__doc__)

    def test_posix_abort_does_not_rmdir_replacement_transaction_directory(self) -> None:
        overlay = self.require_module()
        replacement = SimpleNamespace(
            st_dev=1, st_ino=99, st_mode=stat.S_IFDIR | 0o700,
            st_size=0, st_mtime_ns=20, st_file_attributes=0,
        )
        owned = object.__new__(overlay._PosixOwnedTemp)
        owned.parent_descriptor = 41
        owned.directory_name = ".txn"
        owned.directory_descriptor = 51
        owned.directory_ownership_identity = (1, 7, stat.S_IFDIR)
        owned.descriptor = None
        owned.ownership_identity = (1, 8, stat.S_IFREG)
        owned.content_identity = None
        with mock.patch.object(
            overlay.os, "stat",
            side_effect=[FileNotFoundError(), replacement],
        ), mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(overlay.os, "rmdir") as rmdir:
            cleanup_error = owned.abort()

        rmdir.assert_not_called()
        self.assertIn("directory ownership changed", str(cleanup_error))

    def test_posix_success_cleanup_does_not_rmdir_replacement_transaction_directory(self) -> None:
        overlay = self.require_module()
        replacement = SimpleNamespace(
            st_dev=1, st_ino=99, st_mode=stat.S_IFDIR | 0o700,
            st_size=0, st_mtime_ns=20, st_file_attributes=0,
        )
        owned = object.__new__(overlay._PosixOwnedTemp)
        owned.parent_descriptor = 41
        owned.directory_name = ".txn"
        owned.directory_descriptor = 51
        owned.directory_ownership_identity = (1, 7, stat.S_IFDIR)
        owned.descriptor = None
        with mock.patch.object(
            overlay.os, "stat", return_value=replacement
        ), mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(overlay.os, "rmdir") as rmdir:
            owned.finish_success()

        rmdir.assert_not_called()

    def test_posix_owned_temp_separates_stable_owner_from_content_signature(self) -> None:
        overlay = self.require_module()
        empty = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=10, st_file_attributes=0,
        )
        written = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=7, st_mtime_ns=20, st_file_attributes=0,
        )

        class Stream:
            closed = False

            def write(self, raw):
                return len(raw)

            def flush(self):
                return None

            def fileno(self):
                return 52

            def close(self):
                self.closed = True

        with mock.patch.object(
            overlay.os, "fstat", side_effect=[empty, empty, written]
        ), mock.patch.object(
            overlay.os, "fdopen", return_value=Stream()
        ), mock.patch.object(overlay.os, "fsync"):
            owned = overlay._PosixOwnedTemp(
                41, ".txn", 51, 52, (1, 6, stat.S_IFDIR)
            )
            final_identity = owned.write(b"payload")

        self.assertEqual(owned.ownership_identity, (1, 7, stat.S_IFREG))
        self.assertEqual(owned.content_identity, overlay._file_identity(written))
        self.assertEqual(final_identity, overlay._file_identity(written))

    def test_posix_partial_write_faults_cleanup_by_stable_owner(self) -> None:
        overlay = self.require_module()
        empty = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=10, st_file_attributes=0,
        )
        partial = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=1, st_mtime_ns=20, st_file_attributes=0,
        )
        transaction_directory = SimpleNamespace(
            st_dev=1, st_ino=6, st_mode=stat.S_IFDIR | 0o700,
            st_size=0, st_mtime_ns=20, st_file_attributes=0,
        )

        class FaultingStream:
            closed = False

            def __init__(self, stage):
                self.stage = stage

            def write(self, raw):
                if self.stage == "write":
                    raise OSError("write fault")
                return len(raw)

            def flush(self):
                if self.stage == "flush":
                    raise OSError("flush fault")

            def fileno(self):
                return 52

            def close(self):
                self.closed = True
                if self.stage == "close":
                    raise OSError("close fault")

        for stage in ("write", "flush", "fsync", "fstat", "close"):
            with self.subTest(stage=stage):
                fstat_calls = 0

                def faulting_fstat(descriptor):
                    nonlocal fstat_calls
                    fstat_calls += 1
                    if fstat_calls <= 2:
                        return empty
                    if stage == "fstat":
                        raise OSError("fstat fault")
                    return partial

                unlink = mock.Mock()
                with mock.patch.object(
                    overlay.os, "fstat", side_effect=faulting_fstat
                ), mock.patch.object(
                    overlay.os, "fdopen", return_value=FaultingStream(stage)
                ), mock.patch.object(
                    overlay.os, "fsync",
                    side_effect=OSError("fsync fault") if stage == "fsync" else None,
                ), mock.patch.object(
                    overlay.os, "stat",
                    side_effect=[partial, transaction_directory],
                ), mock.patch.object(
                    overlay.os, "unlink", unlink
                ), mock.patch.object(
                    overlay.os, "close"
                ), mock.patch.object(overlay.os, "rmdir"):
                    owned = overlay._PosixOwnedTemp(
                        41, ".txn", 51, 52, (1, 6, stat.S_IFDIR)
                    )
                    with self.assertRaises(OSError):
                        owned.write(b"payload")
                    self.assertIsNone(owned.abort())

                unlink.assert_called_once_with("payload", dir_fd=51)

    def test_posix_owner_change_before_write_is_rejected(self) -> None:
        overlay = self.require_module()
        original = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=10, st_file_attributes=0,
        )
        replacement = SimpleNamespace(
            st_dev=1, st_ino=8, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=10, st_file_attributes=0,
        )
        with mock.patch.object(
            overlay.os, "fstat", side_effect=[original, replacement]
        ), mock.patch.object(overlay.os, "fdopen") as fdopen:
            owned = overlay._PosixOwnedTemp(
                41, ".txn", 51, 52, (1, 6, stat.S_IFDIR)
            )
            with self.assertRaisesRegex(
                overlay.PlayerOverlayError, "owner changed before writing"
            ):
                owned.write(b"payload")

        fdopen.assert_not_called()

    def test_posix_abort_preserves_a_different_named_owner(self) -> None:
        overlay = self.require_module()
        original = SimpleNamespace(
            st_dev=1, st_ino=7, st_mode=stat.S_IFREG | 0o600,
            st_size=0, st_mtime_ns=10, st_file_attributes=0,
        )
        replacement = SimpleNamespace(
            st_dev=1, st_ino=8, st_mode=stat.S_IFREG | 0o600,
            st_size=3, st_mtime_ns=20, st_file_attributes=0,
        )
        transaction_directory = SimpleNamespace(
            st_dev=1, st_ino=6, st_mode=stat.S_IFDIR | 0o700,
            st_size=0, st_mtime_ns=20, st_file_attributes=0,
        )
        with mock.patch.object(
            overlay.os, "fstat", return_value=original
        ), mock.patch.object(
            overlay.os, "stat",
            side_effect=[replacement, transaction_directory],
        ), mock.patch.object(
            overlay.os, "unlink"
        ) as unlink, mock.patch.object(
            overlay.os, "close"
        ), mock.patch.object(
            overlay.os, "rmdir", side_effect=OSError("directory not empty")
        ):
            owned = overlay._PosixOwnedTemp(
                41, ".txn", 51, 52, (1, 6, stat.S_IFDIR)
            )
            cleanup_error = owned.abort()

        unlink.assert_not_called()
        self.assertIn("directory not empty", str(cleanup_error))

    @unittest.skipUnless(os.name == "posix", "real POSIX filesystem contract")
    def test_real_posix_success_leaves_no_private_transaction(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))

            report = overlay.apply_initial_player_overlay(staged)

            self.assertEqual(report.added_character_ids, INITIAL_CHARACTER_IDS)
            self.assertEqual(parse_nested(target.read_bytes())["1000"]["149999"], "1")
            self.assertEqual(list(target.parent.glob(".wf-offline-txn-*")), [])

    @unittest.skipUnless(os.name == "posix", "real POSIX filesystem contract")
    def test_real_posix_write_faults_leave_no_payload_or_private_transaction(self) -> None:
        overlay = self.require_module()

        class FaultingStream:
            def __init__(self, stream, stage):
                self.stream = stream
                self.stage = stage

            @property
            def closed(self):
                return self.stream.closed

            def write(self, raw):
                if self.stage == "write":
                    self.stream.write(raw[:1])
                    raise OSError("write fault")
                return self.stream.write(raw)

            def flush(self):
                if self.stage == "flush":
                    raise OSError("flush fault")
                return self.stream.flush()

            def fileno(self):
                return self.stream.fileno()

            def close(self):
                self.stream.close()
                if self.stage == "close":
                    raise OSError("close fault")

        for stage in ("write", "flush", "fsync", "fstat", "close"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                staged = Path(directory) / "staged"
                target = staged / TARGET_RELATIVE
                target.parent.mkdir(parents=True)
                original = nested_bytes({"1000": {"7": "2"}})
                target.write_bytes(original)
                real_fdopen = os.fdopen
                real_fstat = os.fstat
                state = {"payload_fd": None}

                def faulting_fdopen(descriptor, mode="r", *args, **kwargs):
                    stream = real_fdopen(descriptor, mode, *args, **kwargs)
                    if "w" in mode:
                        state["payload_fd"] = descriptor
                        return FaultingStream(stream, stage)
                    return stream

                def faulting_fstat(descriptor):
                    if stage == "fstat" and descriptor == state["payload_fd"]:
                        raise OSError("fstat fault")
                    return real_fstat(descriptor)

                with contextlib.ExitStack() as stack:
                    stack.enter_context(
                        mock.patch.object(overlay.os, "fdopen", side_effect=faulting_fdopen)
                    )
                    if stage == "fsync":
                        stack.enter_context(
                            mock.patch.object(
                                overlay.os, "fsync", side_effect=OSError("fsync fault")
                            )
                        )
                    if stage == "fstat":
                        stack.enter_context(
                            mock.patch.object(overlay.os, "fstat", side_effect=faulting_fstat)
                        )
                    with self.assertRaises(overlay.PlayerOverlayError):
                        overlay.apply_initial_player_overlay(staged)

                self.assertEqual(target.read_bytes(), original)
                self.assertEqual(list(target.parent.glob(".wf-offline-txn-*")), [])

    @unittest.skipUnless(os.name == "nt", "Windows CRT descriptor ownership")
    def test_windows_writer_descriptor_is_closed_exactly_once(self) -> None:
        overlay = self.require_module()
        metadata = SimpleNamespace(
            st_dev=3, st_ino=9, st_mode=stat.S_IFREG | 0o600,
            st_size=7, st_mtime_ns=20, st_file_attributes=0,
        )

        for close_fault in (False, True):
            with self.subTest(close_fault=close_fault):
                close_counts = {73: 0}

                class Stream:
                    closed = False

                    def __init__(self, closefd):
                        self.closefd = closefd

                    def write(self, raw):
                        return len(raw)

                    def flush(self):
                        return None

                    def fileno(self):
                        return 73

                    def close(self):
                        if self.closed:
                            return
                        self.closed = True
                        if self.closefd:
                            close_counts[73] += 1
                        if close_fault:
                            raise OSError("stream close fault")

                def tracked_fdopen(descriptor, mode, *, closefd=True):
                    self.assertEqual(descriptor, 73)
                    return Stream(closefd)

                def tracked_close(descriptor):
                    close_counts[descriptor] = close_counts.get(descriptor, 0) + 1

                owned = object.__new__(overlay._WindowsOwnedTemp)
                owned.path = Path("temporary")
                owned.handle = 99
                owned.file_id = (3, 9)
                owned.identity = None
                owned.writer_descriptor = None
                with mock.patch.object(
                    owned, "_new_descriptor", return_value=73
                ), mock.patch.object(
                    overlay.os, "fdopen", side_effect=tracked_fdopen
                ) as fdopen, mock.patch.object(
                    overlay.os, "fsync"
                ), mock.patch.object(
                    overlay.os, "fstat", return_value=metadata
                ), mock.patch.object(
                    overlay.os, "close", side_effect=tracked_close
                ):
                    if close_fault:
                        with self.assertRaisesRegex(OSError, "stream close fault"):
                            owned.write(b"payload")
                    else:
                        owned.write(b"payload")

                self.assertFalse(fdopen.call_args.kwargs.get("closefd", True))
                self.assertEqual(close_counts[73], 1)

    def test_posix_guard_close_cannot_turn_commit_into_failure(self) -> None:
        overlay = self.require_module()
        metadata = SimpleNamespace(
            st_dev=1,
            st_ino=2,
            st_mode=stat.S_IFDIR | 0o700,
            st_size=0,
            st_mtime_ns=3,
            st_ctime_ns=4,
            st_file_attributes=0,
        )
        signature = overlay.store._stat_signature(metadata)

        with mock.patch.object(
            overlay.store, "_require_same_lstat", return_value=metadata
        ), mock.patch.object(overlay.os, "open", return_value=41), mock.patch.object(
            overlay.os, "fstat", return_value=metadata
        ), mock.patch.object(
            overlay.os, "close", side_effect=OSError("late close")
        ), mock.patch.object(
            overlay.os, "O_DIRECTORY", 0x100000, create=True
        ), mock.patch.object(overlay.os, "O_NOFOLLOW", 0x200000, create=True):
            with overlay._posix_transaction_guard(Path("parent"), signature) as descriptor:
                self.assertEqual(descriptor, 41)

    @unittest.skipUnless(os.name == "nt", "Windows directory-handle contract")
    def test_windows_parent_guard_blocks_parent_swap_for_entire_transaction(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))
            moved_parent = target.parent.with_name("swapped-parent")
            real_fsync = os.fsync
            swap_errors = []

            def attempt_parent_swap(descriptor: int) -> None:
                real_fsync(descriptor)
                try:
                    target.parent.rename(moved_parent)
                except OSError as error:
                    swap_errors.append(error)

            with mock.patch.object(overlay.os, "fsync", side_effect=attempt_parent_swap):
                overlay.apply_initial_player_overlay(staged)

            self.assertTrue(swap_errors, "held Windows parent handle must deny rename")
            self.assertTrue(target.exists())
            self.assertFalse(moved_parent.exists())

    def test_target_swap_after_write_is_rejected_before_replace(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            original = nested_bytes({"1000": {"7": "2"}})
            target.write_bytes(original)
            displaced = target.with_name(target.name + ".displaced")
            replacement = target.with_name(target.name + ".replacement")
            replacement.write_bytes(nested_bytes({"1000": {"8": "3"}}))
            real_fsync = os.fsync

            def swap_target(descriptor: int) -> None:
                real_fsync(descriptor)
                os.replace(target, displaced)
                os.replace(replacement, target)

            with mock.patch.object(overlay.os, "fsync", side_effect=swap_target):
                with self.assertRaisesRegex(overlay.PlayerOverlayError, "target.*changed"):
                    overlay.apply_initial_player_overlay(staged)

            self.assertEqual(target.read_bytes(), nested_bytes({"1000": {"8": "3"}}))
            self.assertEqual(displaced.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "Windows handle-bound replace contract")
    def test_last_validation_temp_swap_commits_verified_handle_not_attacker_name(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            target.write_bytes(nested_bytes({"1000": {"7": "2"}}))
            temporary = target.with_name(target.name + ".wf-offline-new")
            displaced = target.with_name(target.name + ".verified-temp")
            real_read_bound = overlay._read_bound_file
            temp_reads = 0

            def swap_after_last_validation(*args, **kwargs):
                nonlocal temp_reads
                raw = real_read_bound(*args, **kwargs)
                path = args[1]
                if path == temporary:
                    temp_reads += 1
                    if temp_reads == 2:
                        os.replace(temporary, displaced)
                        temporary.write_bytes(b"attacker-bytes")
                return raw

            with mock.patch.object(
                overlay, "_read_bound_file", side_effect=swap_after_last_validation
            ):
                report = overlay.apply_initial_player_overlay(staged)

            self.assertEqual(report.added_character_ids, INITIAL_CHARACTER_IDS)
            self.assertEqual(parse_nested(target.read_bytes())["1000"]["149999"], "1")
            self.assertEqual(temporary.read_bytes(), b"attacker-bytes")
            self.assertFalse(displaced.exists())

    @unittest.skipUnless(os.name == "nt", "Windows owned-handle cleanup contract")
    def test_create_owned_temp_faults_never_leave_retry_blocker(self) -> None:
        overlay = self.require_module()

        class FaultingStream:
            def __init__(self, stream, stage: str):
                self.stream = stream
                self.stage = stage

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                self.close()

            def write(self, raw):
                if self.stage == "write":
                    raise OSError("write fault")
                return self.stream.write(raw)

            def flush(self):
                if self.stage == "flush":
                    raise OSError("flush fault")
                return self.stream.flush()

            def fileno(self):
                return self.stream.fileno()

            def close(self):
                self.stream.close()
                if self.stage == "close":
                    raise OSError("close fault")

        for stage in ("write", "flush", "fsync", "fstat", "close"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                staged = Path(directory) / "staged"
                target = staged / TARGET_RELATIVE
                target.parent.mkdir(parents=True)
                original = nested_bytes({"1000": {"7": "2"}})
                target.write_bytes(original)
                temporary = target.with_name(target.name + ".wf-offline-new")
                real_fdopen = os.fdopen
                real_fstat = os.fstat
                state = {"temp_fd": None}

                def faulting_fdopen(descriptor, mode="r", *args, **kwargs):
                    stream = real_fdopen(descriptor, mode, *args, **kwargs)
                    if "w" in mode:
                        state["temp_fd"] = descriptor
                        return FaultingStream(stream, stage)
                    return stream

                def faulting_fstat(descriptor):
                    if stage == "fstat" and descriptor == state["temp_fd"]:
                        raise OSError("fstat fault")
                    return real_fstat(descriptor)

                with contextlib.ExitStack() as stack:
                    if stage in ("write", "flush", "close", "fstat"):
                        stack.enter_context(
                            mock.patch.object(overlay.os, "fdopen", side_effect=faulting_fdopen)
                        )
                    if stage == "fsync":
                        stack.enter_context(
                            mock.patch.object(
                                overlay.os, "fsync", side_effect=OSError("fsync fault")
                            )
                        )
                    if stage == "fstat":
                        stack.enter_context(
                            mock.patch.object(overlay.os, "fstat", side_effect=faulting_fstat)
                        )
                    with self.assertRaises(overlay.PlayerOverlayError):
                        overlay.apply_initial_player_overlay(staged)

                self.assertFalse(temporary.exists(), f"{stage} left a retry blocker")
                self.assertEqual(target.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "Windows handle-bound cleanup contract")
    def test_cleanup_name_swap_after_identity_check_preserves_new_owner(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            original = nested_bytes({"1000": {"7": "2"}})
            target.write_bytes(original)
            temporary = target.with_name(target.name + ".wf-offline-new")
            displaced = target.with_name(target.name + ".owned-temp")
            real_replace = os.replace
            real_unlink = Path.unlink
            real_dispose = getattr(overlay, "_dispose_windows_handle", None)
            swapped = False

            def swap_name() -> None:
                nonlocal swapped
                if swapped:
                    return
                swapped = True
                real_replace(temporary, displaced)
                temporary.write_bytes(b"new-owner")

            def unlink_after_swap(path: Path, *args, **kwargs):
                if path == temporary:
                    swap_name()
                return real_unlink(path, *args, **kwargs)

            def dispose_after_swap(handle):
                swap_name()
                if real_dispose is None:
                    raise AssertionError("new implementation must dispose by handle")
                return real_dispose(handle)

            with mock.patch.object(
                overlay.os, "replace", side_effect=OSError("commit fault")
            ), mock.patch.object(
                overlay, "_commit_windows_handle", create=True,
                side_effect=OSError("commit fault")
            ), mock.patch.object(
                Path, "unlink", autospec=True, side_effect=unlink_after_swap
            ), mock.patch.object(
                overlay, "_dispose_windows_handle", create=True,
                side_effect=dispose_after_swap
            ):
                with self.assertRaisesRegex(overlay.PlayerOverlayError, "atomic replace"):
                    overlay.apply_initial_player_overlay(staged)

            self.assertEqual(temporary.read_bytes(), b"new-owner")
            self.assertEqual(target.read_bytes(), original)

    @unittest.skipUnless(os.name == "nt", "Windows cleanup failure composition")
    def test_replace_and_cleanup_failure_reports_both_without_losing_primary(self) -> None:
        overlay = self.require_module()
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            target = staged / TARGET_RELATIVE
            target.parent.mkdir(parents=True)
            original = nested_bytes({"1000": {"7": "2"}})
            target.write_bytes(original)

            with mock.patch.object(
                overlay.os, "replace", side_effect=OSError("commit fault")
            ), mock.patch.object(
                overlay, "_commit_windows_handle", create=True,
                side_effect=OSError("commit fault")
            ), mock.patch.object(
                Path, "unlink", autospec=True,
                side_effect=PermissionError("cleanup denied")
            ), mock.patch.object(
                overlay, "_dispose_windows_handle", create=True,
                side_effect=PermissionError("cleanup denied")
            ):
                with self.assertRaises(overlay.PlayerOverlayError) as raised:
                    overlay.apply_initial_player_overlay(staged)

            message = str(raised.exception)
            self.assertIn("atomic replace", message)
            self.assertIn("cleanup failed", message)
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
