# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_offline_store as module


HASH = "1" * 38


class OfflineStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.stage = self.root / "stage"
        self.stage.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_roots(
        self,
        *,
        common: dict[str, bytes] | None = None,
        medium: dict[str, bytes] | None = None,
        android: dict[str, bytes] | None = None,
    ) -> module.StoreRoots:
        roots = module.StoreRoots(
            common=self.root / "upload",
            medium=self.root / "medium_upload",
            android=self.root / "android_upload",
        )
        for name, files in (
            ("common", common or {}),
            ("medium", medium or {}),
            ("android", android or {}),
        ):
            target = getattr(roots, name)
            target.mkdir()
            for relative, data in files.items():
                member = target / Path(relative)
                member.parent.mkdir(parents=True, exist_ok=True)
                member.write_bytes(data)
        return roots

    def scan_fixture(self) -> module.StoreScanReport:
        roots = self.make_roots(common={"aa/" + HASH: b"source bytes"})
        self.source_member = roots.common / "aa" / HASH
        return module.enumerate_hashed_members(roots)

    def make_tail_scan(self) -> tuple[module.StoreScanReport, dict[str, bytes]]:
        payloads = {
            f"{index:02x}/" + f"{index:038x}": f"tail-{index}".encode()
            for index in range(12)
        }
        return module.enumerate_hashed_members(self.make_roots(common=payloads)), payloads

    def test_resolve_store_roots_uses_profile_and_wf_asset_roots(self) -> None:
        store = self.root / "data" / "upload"
        store.parent.mkdir(parents=True)
        store.mkdir()
        profiles = self.root / "profiles.json"
        profiles.write_text(
            json.dumps({"active": "cn", "profiles": {"cn": {"store": "data/upload"}}}),
            encoding="utf-8",
        )

        roots = module.resolve_store_roots("cn", profiles_path=profiles)

        self.assertEqual(store, roots.common)
        self.assertEqual(store.parent / "medium_upload", roots.medium)
        self.assertEqual(store.parent / "android_upload", roots.android)

    def test_enumerate_uses_root_qualified_keys_and_rejects_unknown_files(self) -> None:
        roots = self.make_roots(
            common={"aa/" + HASH: b"x"}, medium={"aa/" + HASH: b"y"}
        )
        report = module.enumerate_hashed_members(roots)
        self.assertEqual(
            [(m.root, m.relative) for m in report.members],
            [("common", "aa/" + HASH), ("medium", "aa/" + HASH)],
        )
        (roots.android / "unexpected.txt").write_bytes(b"bad")
        with self.assertRaisesRegex(module.StoreError, "unknown non-hashed member"):
            module.enumerate_hashed_members(roots)

    def test_enumerate_requires_strict_lowercase_two_and_thirty_eight_hex(self) -> None:
        for index, relative in enumerate(("AA/" + HASH, "aa/" + "A" * 38, "a/" + HASH, "aa/" + "1" * 37)):
            with self.subTest(relative=relative):
                child = self.root / relative.replace("/", "_")
                child.mkdir()
                roots = module.StoreRoots(
                    child,
                    self.root / f"empty-medium-{index}",
                    self.root / f"empty-android-{index}",
                )
                roots.medium.mkdir()
                roots.android.mkdir()
                member = roots.common / Path(relative)
                member.parent.mkdir(parents=True, exist_ok=True)
                member.write_bytes(b"bad")
                with self.assertRaisesRegex(module.StoreError, "unknown non-hashed member"):
                    module.enumerate_hashed_members(roots)

    def test_enumerate_excludes_only_documented_backup_and_temporary_items(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"ok"})
        for name in (".bak", "table.bak-20260720", "download.tmp", "download.part", "partial_downloaded.json"):
            (roots.common / name).write_bytes(b"ignored")

        report = module.enumerate_hashed_members(roots)

        self.assertEqual(1, len(report.members))
        self.assertEqual(5, len(report.excluded))

    def test_enumerate_rejects_backup_named_directories(self) -> None:
        for index, name in enumerate(("secret.tmp", "save.dat")):
            with self.subTest(name=name):
                roots = module.StoreRoots(
                    self.root / f"directory-common-{index}",
                    self.root / f"directory-medium-{index}",
                    self.root / f"directory-android-{index}",
                )
                for root in (roots.common, roots.medium, roots.android):
                    root.mkdir()
                (roots.common / name).mkdir()

                with self.assertRaisesRegex(module.StoreError, "unknown non-hashed member"):
                    module.enumerate_hashed_members(roots)

    def test_enumerate_fails_closed_for_secret_save_bundle_and_unknown_items(self) -> None:
        for name in ("secret.key", "save.dat", "bundle.zip", "notes.txt"):
            with self.subTest(name=name):
                item_root = self.root / name.replace(".", "_")
                item_root.mkdir()
                roots = module.StoreRoots(item_root, self.root / f"m-{name}", self.root / f"a-{name}")
                roots.medium.mkdir()
                roots.android.mkdir()
                (roots.common / name).write_bytes(b"private")
                with self.assertRaisesRegex(module.StoreError, "unknown non-hashed member"):
                    module.enumerate_hashed_members(roots)

    def test_enumerate_rejects_windows_reparse_members_without_following(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"x"})
        member = roots.common / "aa" / HASH
        real_lstat = Path.lstat

        def fake_lstat(path: Path) -> os.stat_result | SimpleNamespace:
            metadata = real_lstat(path)
            if path == member:
                values = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith("st_")}
                values["st_file_attributes"] = stat.FILE_ATTRIBUTE_REPARSE_POINT
                return SimpleNamespace(**values)
            return metadata

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=fake_lstat):
            with self.assertRaisesRegex(module.StoreError, "reparse"):
                module.enumerate_hashed_members(roots)

    def test_enumerate_detects_source_drift_while_hashing(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"before"})
        member = roots.common / "aa" / HASH
        real_hash = module._stream_sha256

        def hash_then_change(stream: object) -> tuple[int, str]:
            result = real_hash(stream)
            member.write_bytes(b"after-longer")
            return result

        with mock.patch.object(module, "_stream_sha256", side_effect=hash_then_change):
            with self.assertRaisesRegex(module.StoreError, "changed during scan"):
                module.enumerate_hashed_members(roots)

    def test_enumerate_rejects_path_swap_to_different_open_file(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"expected"})
        member = roots.common / "aa" / HASH
        outside = self.root / "outside-secret"
        outside.write_bytes(b"outside")
        real_open = os.open

        def swapped_open(path: os.PathLike[str] | str, flags: int, *args: object) -> int:
            target = outside if Path(path) == member else path
            return real_open(target, flags, *args)

        with mock.patch.object(module.os, "open", side_effect=swapped_open):
            with self.assertRaisesRegex(module.StoreError, "changed while opening|final path"):
                module.enumerate_hashed_members(roots)

    def test_enumerate_rechecks_hash_directory_after_scandir(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"expected"})
        prefix = roots.common / "aa"
        real_lstat = Path.lstat
        prefix_checks = 0

        def reparse_after_scandir(path: Path) -> os.stat_result | SimpleNamespace:
            nonlocal prefix_checks
            metadata = real_lstat(path)
            if path == prefix:
                prefix_checks += 1
                if prefix_checks >= 2:
                    values = {
                        name: getattr(metadata, name)
                        for name in dir(metadata)
                        if name.startswith("st_")
                    }
                    values["st_file_attributes"] = stat.FILE_ATTRIBUTE_REPARSE_POINT
                    return SimpleNamespace(**values)
            return metadata

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=reparse_after_scandir):
            with self.assertRaisesRegex(module.StoreError, "reparse"):
                module.enumerate_hashed_members(roots)

    def test_enumerate_detects_swap_restore_that_hides_unknown_member(self) -> None:
        roots = self.make_roots(common={"aa/" + HASH: b"expected"})
        prefix = roots.common / "aa"
        (prefix / "secret.tmp-directory").mkdir()
        mirror = self.root / "mirror-aa"
        mirror.mkdir()
        (mirror / HASH).write_bytes(b"expected")
        parked = self.root / "parked-aa"
        real_scandir = os.scandir
        real_lstat = Path.lstat
        restored_metadata = {
            roots.common: real_lstat(roots.common),
            prefix: real_lstat(prefix),
        }

        class SwapRestoreScandir:
            def __init__(self) -> None:
                self.entries = None

            def __enter__(self):
                os.rename(prefix, parked)
                os.rename(mirror, prefix)
                self.entries = real_scandir(prefix)
                return self.entries

            def __exit__(self, exc_type, exc_value, traceback):
                if self.entries is not None:
                    self.entries.close()
                os.rename(prefix, mirror)
                os.rename(parked, prefix)
                return False

        def swapping_scandir(path):
            if not isinstance(path, int) and Path(path) == prefix:
                return SwapRestoreScandir()
            return real_scandir(path)

        def restored_lstat(path: Path):
            return restored_metadata.get(path, real_lstat(path))

        with mock.patch.object(module.os, "scandir", side_effect=swapping_scandir), mock.patch.object(
            Path, "lstat", autospec=True, side_effect=restored_lstat
        ):
            with self.assertRaisesRegex(module.StoreError, "unknown non-hashed member|cannot enumerate"):
                module.enumerate_hashed_members(roots)

    def test_inspect_legacy_zip_paths_parses_three_roots_and_ignores_markers(self) -> None:
        archive = self.root / "legacy.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("WorldFlipper/", b"")
            zf.writestr("WorldFlipper/dummy/download/.empty", b"0")
            zf.writestr("WorldFlipper/dummy/info.json", b"{}")
            zf.writestr("WorldFlipper/dummy/download/production/upload/aa/" + HASH, b"c")
            zf.writestr("WorldFlipper/dummy/download/production/medium_upload/bb/" + HASH, b"m")
            zf.writestr("WorldFlipper/dummy/download/production/android_upload/cc/" + HASH, b"a")

        report = module.inspect_legacy_zip_paths(archive)

        self.assertEqual(
            (("android", "cc/" + HASH), ("common", "aa/" + HASH), ("medium", "bb/" + HASH)),
            report.members,
        )

    def test_inspect_legacy_zip_paths_rejects_unknown_or_unsafe_members(self) -> None:
        archive = self.root / "bad-legacy.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("WorldFlipper/dummy/save.dat", b"secret")
        with self.assertRaisesRegex(module.StoreError, "unknown legacy ZIP member"):
            module.inspect_legacy_zip_paths(archive)

    def test_inspect_legacy_zip_paths_rejects_duplicate_marker_names(self) -> None:
        archive = self.root / "duplicate-marker.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("WorldFlipper/dummy/info.json", b"{}")
                zf.writestr("WorldFlipper/dummy/info.json", b"{}")

        with self.assertRaisesRegex(module.StoreError, "duplicate legacy ZIP member name"):
            module.inspect_legacy_zip_paths(archive)

    def test_inspect_legacy_zip_paths_rejects_unix_symlink_members(self) -> None:
        archive = self.root / "symlink-member.zip"
        info = zipfile.ZipInfo("WorldFlipper/dummy/info.json")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(info, b"outside")

        with self.assertRaisesRegex(module.StoreError, "special legacy ZIP member"):
            module.inspect_legacy_zip_paths(archive)

    def test_compare_path_sets_enforces_frozen_137820_to_138289_delta(self) -> None:
        legacy = tuple(("common", f"legacy-{index}") for index in range(137_820))
        current = legacy + tuple(("common", f"added-{index}") for index in range(469))

        diff = module.compare_path_sets(current, legacy)

        self.assertEqual((138_289, 137_820, 469, 0), (
            diff.current_count, diff.legacy_count, len(diff.added), len(diff.missing)
        ))
        with self.assertRaisesRegex(module.StoreError, "snapshot count mismatch"):
            module.compare_path_sets(current[:-1], legacy)

    def test_verify_tail_edge_accepts_exactly_twelve_strict_members(self) -> None:
        scan, payloads = self.make_tail_scan()
        archive = self.root / "pinball-1.4.195-1.4.196-1-test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for relative, data in payloads.items():
                zf.writestr("production/upload/" + relative, data)

        report = module.verify_tail_edge(archive, current=scan.members)

        self.assertEqual(12, report.member_count)
        self.assertEqual(12, len(report.members))

    def test_verify_tail_edge_rejects_wrong_count_or_non_common_member(self) -> None:
        archive = self.root / "pinball-1.4.195-1.4.196-1-bad.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for index in range(11):
                zf.writestr("production/upload/aa/" + f"{index:038x}", b"x")
            zf.writestr("production/medium_upload/bb/" + HASH, b"x")
        with self.assertRaisesRegex(module.StoreError, "tail edge"):
            module.verify_tail_edge(archive)

    def test_verify_tail_edge_rejects_same_paths_with_bad_bytes(self) -> None:
        scan, payloads = self.make_tail_scan()
        archive = self.root / "pinball-1.4.195-1.4.196-1-corrupt.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for index, (relative, data) in enumerate(payloads.items()):
                zf.writestr(
                    "production/upload/" + relative,
                    b"x" * len(data) if index == 0 else data,
                )

        with self.assertRaisesRegex(module.StoreError, "tail edge content mismatch"):
            module.verify_tail_edge(archive, current=scan.members)

    def test_verify_tail_edge_rejects_wrong_version_filename(self) -> None:
        scan, payloads = self.make_tail_scan()
        archive = self.root / "pinball-1.4.194-1.4.196-1-wrong.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for relative, data in payloads.items():
                zf.writestr("production/upload/" + relative, data)

        with self.assertRaisesRegex(module.StoreError, "tail edge version mismatch"):
            module.verify_tail_edge(archive, current=scan.members)

    def test_verify_tail_edge_rejects_symlink_even_when_payload_matches(self) -> None:
        scan, payloads = self.make_tail_scan()
        archive = self.root / "pinball-1.4.195-1.4.196-1-symlink.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for index, (relative, data) in enumerate(payloads.items()):
                name = "production/upload/" + relative
                if index == 0:
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    zf.writestr(info, data)
                else:
                    zf.writestr(name, data)

        with self.assertRaisesRegex(module.StoreError, "special tail ZIP member"):
            module.verify_tail_edge(archive, current=scan.members)

    def test_verify_tail_edge_rejects_declared_oversize_before_open(self) -> None:
        scan, payloads = self.make_tail_scan()
        archive = self.root / "pinball-1.4.195-1.4.196-1-oversize.zip"
        oversized_relative = next(iter(payloads))
        oversized_name = "production/upload/" + oversized_relative
        with zipfile.ZipFile(archive, "w") as zf:
            for relative, data in payloads.items():
                zf.writestr(
                    "production/upload/" + relative,
                    data + b"x" if relative == oversized_relative else data,
                )
        real_open = zipfile.ZipFile.open
        opened_oversized = False

        def tracking_open(zf, member, *args, **kwargs):
            nonlocal opened_oversized
            name = member.filename if isinstance(member, zipfile.ZipInfo) else member
            if name == oversized_name:
                opened_oversized = True
            return real_open(zf, member, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "open", autospec=True, side_effect=tracking_open):
            with self.assertRaisesRegex(module.StoreError, "declared size mismatch"):
                module.verify_tail_edge(archive, current=scan.members)
        self.assertFalse(opened_oversized)

    def test_required_free_bytes_uses_two_store_three_apk_and_two_gib_safety(self) -> None:
        self.assertEqual(
            11 * 2 + 13 * 3 + 2 * 1024**3,
            module.required_free_bytes(11, 13),
        )

    def test_preflight_direct_call_rejects_non_frozen_snapshot_version(self) -> None:
        args = SimpleNamespace(
            no_copy=True,
            snapshot_version="1.4.197",
            profile="missing",
            legacy_zip="missing.zip",
            tail_zip="missing-tail.zip",
        )

        with self.assertRaisesRegex(module.StoreError, "unsupported offline snapshot version"):
            module.preflight(args)

    def test_snapshot_is_a_real_copy_and_writes_generated_markers(self) -> None:
        scan = self.scan_fixture()

        report = module.materialize_snapshot(
            scan, self.stage / "WorldFlipper", snapshot_version="1.4.196"
        )

        self.assertEqual(b"0", (report.worldflipper_root / "dummy/download/.empty").read_bytes())
        info = json.loads((report.worldflipper_root / "dummy/info.json").read_text("utf-8"))
        self.assertEqual("1.4.196", info["version"])
        self.assertEqual(scan.total_bytes, info["totalSize"])
        self.assertNotEqual(os.stat(self.source_member).st_ino, os.stat(report.copied_members[0]).st_ino)
        self.assertEqual(self.source_member.read_bytes(), report.copied_members[0].read_bytes())
        self.assertEqual(2, len(report.generated_entries))

    def test_materialize_tolerates_windows_fstat_ctime_rounding(self) -> None:
        scan = self.scan_fixture()
        real_fstat = os.fstat

        def rounded_fstat(descriptor: int) -> SimpleNamespace:
            metadata = real_fstat(descriptor)
            values = {
                name: getattr(metadata, name)
                for name in dir(metadata)
                if name.startswith("st_")
            }
            values["st_ctime_ns"] = metadata.st_ctime_ns + 1_000_000
            return SimpleNamespace(**values)

        with mock.patch.object(module.os, "fstat", side_effect=rounded_fstat):
            report = module.materialize_snapshot(
                scan, self.stage / "WorldFlipper", snapshot_version="1.4.196"
            )

        self.assertEqual(1, len(report.copied_members))

    def test_materialize_tolerates_windows_invalid_owned_directory_stat_bit(self) -> None:
        scan = self.scan_fixture()
        worldflipper = self.stage / "WorldFlipper"
        settling_directory = worldflipper / "dummy/download/production/upload/aa"
        real_lstat = Path.lstat
        samples = 0

        def settling_lstat(path: Path) -> os.stat_result | SimpleNamespace:
            nonlocal samples
            metadata = real_lstat(path)
            if path != settling_directory:
                return metadata
            samples += 1
            if samples != 1:
                return metadata
            values = {
                name: getattr(metadata, name)
                for name in dir(metadata)
                if name.startswith("st_")
            }
            values["st_file_attributes"] = (
                getattr(metadata, "st_file_attributes", 0) | 0x10000000
            )
            return SimpleNamespace(**values)

        with mock.patch.object(
            Path, "lstat", autospec=True, side_effect=settling_lstat
        ):
            report = module.materialize_snapshot(
                scan, worldflipper, snapshot_version="1.4.196"
            )

        self.assertGreaterEqual(samples, 2)
        self.assertEqual(1, len(report.copied_members))

    def test_materialize_rejects_opened_inode_drift(self) -> None:
        scan = self.scan_fixture()
        real_fstat = os.fstat

        def changed_inode_fstat(descriptor: int) -> SimpleNamespace:
            metadata = real_fstat(descriptor)
            values = {
                name: getattr(metadata, name)
                for name in dir(metadata)
                if name.startswith("st_")
            }
            values["st_ino"] = metadata.st_ino + 1
            return SimpleNamespace(**values)

        with mock.patch.object(module.os, "fstat", side_effect=changed_inode_fstat):
            with self.assertRaisesRegex(module.StoreError, "changed while opening"):
                module.materialize_snapshot(
                    scan, self.stage / "WorldFlipper", snapshot_version="1.4.196"
                )

    def test_materialize_rejects_owned_directory_inode_drift(self) -> None:
        scan = self.scan_fixture()
        worldflipper = self.stage / "WorldFlipper"
        raced_directory = worldflipper / "dummy/download/production/upload/aa"
        destination = raced_directory / HASH
        real_lstat = Path.lstat
        samples = 0

        def changed_inode_lstat(path: Path) -> os.stat_result | SimpleNamespace:
            nonlocal samples
            metadata = real_lstat(path)
            if path != raced_directory:
                return metadata
            samples += 1
            if samples == 1:
                return metadata
            values = {
                name: getattr(metadata, name)
                for name in dir(metadata)
                if name.startswith("st_")
            }
            values["st_ino"] = metadata.st_ino + 1
            return SimpleNamespace(**values)

        with mock.patch.object(
            Path, "lstat", autospec=True, side_effect=changed_inode_lstat
        ):
            with self.assertRaisesRegex(module.StoreError, "changed during scan"):
                module.materialize_snapshot(
                    scan, worldflipper, snapshot_version="1.4.196"
                )

        self.assertGreaterEqual(samples, 2)
        self.assertFalse(destination.exists())

    def test_materialize_snapshot_requires_a_new_caller_owned_destination(self) -> None:
        scan = self.scan_fixture()
        existing = self.stage / "WorldFlipper"
        existing.mkdir()
        with self.assertRaisesRegex(module.StoreError, "must not already exist"):
            module.materialize_snapshot(scan, existing, snapshot_version="1.4.196")

    def test_materialize_snapshot_rejects_source_drift_since_scan(self) -> None:
        scan = self.scan_fixture()
        self.source_member.write_bytes(b"changed after scan")
        with self.assertRaisesRegex(module.StoreError, "source drift"):
            module.materialize_snapshot(
                scan, self.stage / "WorldFlipper", snapshot_version="1.4.196"
            )

    def test_materialize_rejects_destination_parent_reparse_race_before_write(self) -> None:
        scan = self.scan_fixture()
        worldflipper = self.stage / "WorldFlipper"
        raced_parent = worldflipper / "dummy/download/production/upload/aa"
        destination = raced_parent / HASH
        real_mkdir = os.mkdir
        real_lstat = Path.lstat
        raced = False

        def race_after_mkdir(path: os.PathLike[str] | str, mode: int = 0o777) -> None:
            nonlocal raced
            real_mkdir(path, mode)
            if Path(path) == raced_parent:
                raced = True

        def reparse_lstat(path: Path) -> os.stat_result | SimpleNamespace:
            metadata = real_lstat(path)
            if raced and path == raced_parent:
                values = {
                    name: getattr(metadata, name)
                    for name in dir(metadata)
                    if name.startswith("st_")
                }
                values["st_file_attributes"] = stat.FILE_ATTRIBUTE_REPARSE_POINT
                return SimpleNamespace(**values)
            return metadata

        with mock.patch.object(module.os, "mkdir", side_effect=race_after_mkdir), mock.patch.object(
            Path, "lstat", autospec=True, side_effect=reparse_lstat
        ):
            with self.assertRaisesRegex(module.StoreError, "reparse"):
                module.materialize_snapshot(scan, worldflipper, snapshot_version="1.4.196")

        self.assertFalse(destination.exists())

    def test_posix_exclusive_open_contract_is_relative_nofollow(self) -> None:
        helper = getattr(module, "_open_exclusive_at", None)
        self.assertIsNotNone(helper)
        calls = []

        def recording_open(path, flags, mode=0o777, *, dir_fd=None):
            calls.append((path, flags, mode, dir_fd))
            return 91

        sentinel_nofollow = 0x40000000
        with mock.patch.object(module.os, "open", side_effect=recording_open):
            descriptor = helper(41, "member", nofollow_flag=sentinel_nofollow)

        self.assertEqual(91, descriptor)
        self.assertEqual("member", calls[0][0])
        self.assertEqual(41, calls[0][3])
        self.assertTrue(calls[0][1] & os.O_CREAT)
        self.assertTrue(calls[0][1] & os.O_EXCL)
        self.assertTrue(calls[0][1] & sentinel_nofollow)

    @unittest.skipIf(os.name == "nt", "POSIX dirfd integration fixture")
    def test_materialize_posix_swap_restore_never_writes_payload_outside(self) -> None:
        scan = self.scan_fixture()
        worldflipper = self.stage / "WorldFlipper"
        destination_parent = worldflipper / "dummy/download/production/upload/aa"
        destination = destination_parent / HASH
        parked = self.root / "parked-destination-aa"
        outside = self.root / "outside-destination-aa"
        outside.mkdir()
        real_open = os.open
        raced = False

        def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal raced
            is_destination = bool(flags & os.O_CREAT) and (
                (dir_fd is not None and path == HASH)
                or (dir_fd is None and Path(path) == destination)
            )
            if not is_destination:
                if dir_fd is None:
                    return real_open(path, flags, mode)
                return real_open(path, flags, mode, dir_fd=dir_fd)
            os.rename(destination_parent, parked)
            os.rename(outside, destination_parent)
            try:
                if dir_fd is None:
                    descriptor = real_open(path, flags, mode)
                else:
                    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            finally:
                os.rename(destination_parent, outside)
                os.rename(parked, destination_parent)
            raced = True
            return descriptor

        with mock.patch.object(module.os, "open", side_effect=swapping_open):
            report = module.materialize_snapshot(
                scan, worldflipper, snapshot_version="1.4.196"
            )

        self.assertTrue(raced)
        self.assertEqual(b"source bytes", report.copied_members[0].read_bytes())
        self.assertFalse((outside / HASH).exists())


if __name__ == "__main__":
    unittest.main()
