# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import os
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_offline_zip as module
from wf_offline_store import ManifestEntry


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class OfflineZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.stage = self.root / "stage" / "WorldFlipper"
        self.output = self.root / "data.zip"
        payloads = {
            "WorldFlipper/dummy/download/.empty": b"0",
            "WorldFlipper/dummy/info.json": b'{"version":"1.4.196"}\n',
            "WorldFlipper/dummy/download/production/upload/aa/" + "1" * 38: b"common",
            "WorldFlipper/dummy/download/production/medium_upload/bb/" + "2" * 38: b"medium",
            "WorldFlipper/dummy/download/production/android_upload/cc/" + "3" * 38: b"android",
        }
        self.entries = tuple(
            ManifestEntry(path, len(payload), sha256(payload), "fixture")
            for path, payload in sorted(payloads.items())
        )
        for entry, payload in zip(self.entries, (payloads[entry.path] for entry in self.entries)):
            target = self.stage.parent / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_unchecked_zip(self, members: list[tuple[str, bytes]]) -> None:
        with zipfile.ZipFile(self.output, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for name, payload in members:
                archive.writestr(module._zip_info(name), payload)

    def strip_zip64_end_records(self) -> None:
        raw = bytearray(self.output.read_bytes())
        zip64_offset = raw.rfind(zipfile.stringEndArchive64)
        classic_offset = raw.rfind(zipfile.stringEndArchive)
        self.assertGreaterEqual(zip64_offset, 0)
        self.assertGreater(classic_offset, zip64_offset)
        del raw[zip64_offset:classic_offset]
        self.output.write_bytes(raw)

    def write_physical_archive(
        self,
        entries: tuple[ManifestEntry, ...],
        *,
        preamble: bytes = b"",
        gap_after_first: bytes = b"",
    ) -> None:
        with self.output.open("x+b") as stream:
            stream.write(preamble)
            with zipfile.ZipFile(stream, "w", allowZip64=True) as archive:
                for index, entry in enumerate(entries):
                    payload = (self.stage.parent / entry.path).read_bytes()
                    with archive.open(
                        module._zip_info(entry.path), "w", force_zip64=True
                    ) as destination:
                        destination.write(payload)
                    if index == 0:
                        stream.write(gap_after_first)
                        archive.start_dir = stream.tell()
            module._force_zip64_eocd(stream)

    def sort_central_directory_records(self) -> None:
        with self.output.open("rb") as stream:
            zip64 = module._read_zip64_eocd(stream)
            self.assertIsNotNone(zip64)
        assert zip64 is not None
        raw = bytearray(self.output.read_bytes())
        position = zip64.central_offset
        end = position + zip64.central_size
        records: list[tuple[bytes, bytes]] = []
        while position < end:
            header = struct.unpack(
                zipfile.structCentralDir,
                raw[position : position + zipfile.sizeCentralDir],
            )
            filename_length = header[zipfile._CD_FILENAME_LENGTH]
            record_size = (
                zipfile.sizeCentralDir
                + filename_length
                + header[zipfile._CD_EXTRA_FIELD_LENGTH]
                + header[zipfile._CD_COMMENT_LENGTH]
            )
            record = bytes(raw[position : position + record_size])
            filename = record[
                zipfile.sizeCentralDir : zipfile.sizeCentralDir + filename_length
            ]
            records.append((filename, record))
            position += record_size
        self.assertEqual(position, end)
        raw[zip64.central_offset:end] = b"".join(
            record for _, record in sorted(records, key=lambda item: item[0])
        )
        self.output.write_bytes(raw)

    def make_production_manifest(
        self, *, common: int, medium: int, android: int
    ) -> tuple[ManifestEntry, ...]:
        entries: list[ManifestEntry] = [
            ManifestEntry(module.EMPTY_PATH, 1, sha256(b"0"), "generated-marker"),
            ManifestEntry(
                module.INFO_PATH,
                len(b'{"version":"1.4.196"}\n'),
                sha256(b'{"version":"1.4.196"}\n'),
                "generated-marker",
            ),
        ]
        for kind, count in (("common", common), ("medium", medium), ("android", android)):
            prefix = module.PRODUCTION_PREFIXES[kind]
            entries.extend(
                ManifestEntry(
                    f"{prefix}{index % 256:02x}/{index:038x}", 1, "0" * 64, kind
                )
                for index in range(count)
            )
        return tuple(entries)

    def test_zip_has_one_root_no_directories_and_fixed_metadata(self) -> None:
        report = module.write_data_zip(self.stage, self.output, self.entries, production=False)

        with zipfile.ZipFile(self.output) as archive:
            infos = archive.infolist()
        self.assertEqual([info.filename for info in infos], sorted(entry.path for entry in self.entries))
        self.assertTrue(all(info.filename.startswith("WorldFlipper/") for info in infos))
        self.assertTrue(all(not info.is_dir() for info in infos))
        self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos))
        self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in infos))
        self.assertTrue(all(info.create_system == 3 for info in infos))
        self.assertTrue(all(info.external_attr == module.FIXED_EXTERNAL_ATTR for info in infos))
        self.assertEqual(report.member_count, len(self.entries))
        self.assertEqual(report.counts, {"common": 1, "medium": 1, "android": 1, "markers": 2})

    def test_same_inputs_produce_the_same_archive_hash(self) -> None:
        first = module.write_data_zip(self.stage, self.output, self.entries, production=False)
        second_output = self.root / "data-again.zip"

        second = module.write_data_zip(
            self.stage, second_output, tuple(reversed(self.entries)), production=False
        )

        self.assertEqual(first.archive_sha256, second.archive_sha256)
        self.assertEqual(self.output.read_bytes(), second_output.read_bytes())

    def test_zip64_eocd_is_always_written(self) -> None:
        report = module.write_data_zip(self.stage, self.output, self.entries, production=False)

        self.assertTrue(report.zip64)
        self.assertIn(b"PK\x06\x06", self.output.read_bytes())

    def test_zip64_eocd_is_written_when_file_count_crosses_limit(self) -> None:
        with mock.patch.object(zipfile, "ZIP_FILECOUNT_LIMIT", 2):
            module.write_data_zip(self.stage, self.output, self.entries[:3], production=False)

        self.assertIn(b"PK\x06\x06", self.output.read_bytes())

    def test_duplicate_and_casefold_colliding_names_are_rejected(self) -> None:
        original = self.entries[0]
        duplicate = ManifestEntry(original.path, original.size, original.sha256, "duplicate")
        case_collision = ManifestEntry(original.path.swapcase(), original.size, original.sha256, "collision")

        with self.assertRaisesRegex(module.OfflineZipError, "duplicate"):
            module.write_data_zip(
                self.stage, self.output, (*self.entries, duplicate), production=False
            )
        with self.assertRaisesRegex(module.OfflineZipError, "casefold"):
            module.write_data_zip(
                self.stage, self.output, (*self.entries, case_collision), production=False
            )

    def test_unsafe_member_paths_are_rejected(self) -> None:
        bad_paths = (
            "/WorldFlipper/dummy/info.json",
            "C:/WorldFlipper/dummy/info.json",
            "WorldFlipper\\dummy\\info.json",
            "WorldFlipper/dummy/../info.json",
        )
        for index, path in enumerate(bad_paths):
            with self.subTest(path=path):
                entry = ManifestEntry(path, 1, sha256(b"x"), "bad")
                with self.assertRaisesRegex(module.OfflineZipError, "path"):
                    module.write_data_zip(
                        self.stage, self.root / f"bad-{index}.zip", (entry,), production=False
                    )

    def test_double_worldflipper_root_is_rejected(self) -> None:
        path = "WorldFlipper/WorldFlipper/dummy/info.json"
        entry = ManifestEntry(path, 1, sha256(b"x"), "bad")

        with self.assertRaisesRegex(module.OfflineZipError, "WorldFlipper"):
            module.write_data_zip(self.stage, self.output, (entry,), production=False)

    def test_wrong_empty_marker_is_rejected(self) -> None:
        entry = next(item for item in self.entries if item.path.endswith("/.empty"))
        target = self.stage.parent / entry.path
        target.write_bytes(b"x")
        wrong = ManifestEntry(entry.path, 1, sha256(b"x"), entry.source)

        with self.assertRaisesRegex(module.OfflineZipError, r"\.empty"):
            module.write_data_zip(
                self.stage,
                self.output,
                tuple(wrong if item == entry else item for item in self.entries),
                production=False,
            )

    def test_explicit_directory_member_is_rejected(self) -> None:
        self.write_unchecked_zip([("WorldFlipper/dummy/", b"")])
        entry = ManifestEntry("WorldFlipper/dummy/", 0, sha256(b""), "bad")

        with self.assertRaisesRegex(module.OfflineZipError, "director"):
            module.verify_data_zip(
                self.output, {entry.path: entry}, expected_members=1, production=False
            )

    def test_verifier_rejects_duplicate_and_casefold_colliding_names(self) -> None:
        members = [
            ("WorldFlipper/dummy/info.json", b"a"),
            ("worldflipper/dummy/info.json", b"b"),
        ]
        self.write_unchecked_zip(members)
        entries = {
            path: ManifestEntry(path, len(payload), sha256(payload), "fixture")
            for path, payload in members
        }

        with self.assertRaisesRegex(module.OfflineZipError, "casefold"):
            module.verify_data_zip(self.output, entries, expected_members=2, production=False)

    def test_verifier_rejects_true_duplicate_names(self) -> None:
        path = "WorldFlipper/dummy/download/production/upload/ee/" + "5" * 38
        payload = b"duplicate"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.write_unchecked_zip([(path, payload), (path, payload)])
        entry = ManifestEntry(path, len(payload), sha256(payload), "fixture")

        with self.assertRaisesRegex(module.OfflineZipError, "duplicate"):
            module.verify_data_zip(
                self.output, {path: entry}, expected_members=2, production=False
            )

    def test_verifier_rejects_unsorted_central_directory(self) -> None:
        members = [(entry.path, (self.stage.parent / entry.path).read_bytes()) for entry in self.entries]
        self.write_unchecked_zip(list(reversed(members)))
        with self.output.open("r+b") as stream:
            module._force_zip64_eocd(stream)

        with self.assertRaisesRegex(module.OfflineZipError, "sorted"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_rejects_reversed_physical_records_with_sorted_central_directory(
        self,
    ) -> None:
        self.write_physical_archive(tuple(reversed(self.entries)))
        self.sort_central_directory_records()

        with self.assertRaisesRegex(module.OfflineZipError, "physical local records"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_rejects_preamble_before_first_local_record(self) -> None:
        self.write_physical_archive(self.entries, preamble=b"JUNK")

        with self.assertRaisesRegex(module.OfflineZipError, "physical local records"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_rejects_gap_between_local_records(self) -> None:
        self.write_physical_archive(self.entries, gap_after_first=b"JUNK")

        with self.assertRaisesRegex(module.OfflineZipError, "physical local records"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_accepts_canonical_central_zip64_offset_extra(self) -> None:
        with mock.patch.object(zipfile, "ZIP64_LIMIT", 128):
            self.write_physical_archive(self.entries)
            with zipfile.ZipFile(self.output) as archive:
                offset_infos = [info for info in archive.infolist() if info.extra]
            self.assertTrue(offset_infos)
            for info in offset_infos:
                self.assertLess(info.file_size, 128)
                self.assertLess(info.compress_size, 128)
                self.assertEqual(
                    info.extra,
                    struct.pack("<HHQ", 1, 8, info.header_offset),
                )

            report = module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )
        self.assertTrue(report.zip64)

    def test_writer_accepts_required_central_zip64_offset_extra(self) -> None:
        with mock.patch.object(zipfile, "ZIP64_LIMIT", 128):
            report = module.write_data_zip(
                self.stage,
                self.output,
                self.entries,
                production=False,
            )

        self.assertTrue(report.zip64)

    def test_verifier_rejects_zip64_extra_without_raw_offset_sentinel(self) -> None:
        with mock.patch.object(zipfile, "ZIP64_LIMIT", 128):
            self.write_physical_archive(self.entries)

        with self.output.open("rb") as stream:
            zip64 = module._read_zip64_eocd(stream)
        self.assertIsNotNone(zip64)
        assert zip64 is not None
        raw = bytearray(self.output.read_bytes())
        position = zip64.central_offset
        end = position + zip64.central_size
        mutated = False
        while position < end:
            header = struct.unpack(
                zipfile.structCentralDir,
                raw[position : position + zipfile.sizeCentralDir],
            )
            filename_length = header[zipfile._CD_FILENAME_LENGTH]
            extra_length = header[zipfile._CD_EXTRA_FIELD_LENGTH]
            comment_length = header[zipfile._CD_COMMENT_LENGTH]
            extra_start = position + zipfile.sizeCentralDir + filename_length
            extra = bytes(raw[extra_start : extra_start + extra_length])
            if (
                header[zipfile._CD_LOCAL_HEADER_OFFSET] == 0xFFFFFFFF
                and len(extra) == 12
            ):
                tag, size, actual_offset = struct.unpack("<HHQ", extra)
                self.assertEqual((tag, size), (1, 8))
                self.assertLess(actual_offset, 0xFFFFFFFF)
                struct.pack_into(
                    "<L",
                    raw,
                    position + zipfile.sizeCentralDir - 4,
                    actual_offset,
                )
                mutated = True
                break
            position += (
                zipfile.sizeCentralDir
                + filename_length
                + extra_length
                + comment_length
            )
        self.assertTrue(mutated)
        self.output.write_bytes(raw)

        with mock.patch.object(zipfile, "ZIP64_LIMIT", 128):
            with self.assertRaisesRegex(module.OfflineZipError, "ZIP64 offset"):
                module.verify_data_zip(
                    self.output,
                    {entry.path: entry for entry in self.entries},
                    expected_members=len(self.entries),
                    production=False,
                )

    def test_verifier_rejects_central_extra_field(self) -> None:
        entry = self.entries[-1]
        payload = (self.stage.parent / entry.path).read_bytes()
        info = module._zip_info(entry.path)
        info.extra = b"\xfe\xca\x00\x00"
        with zipfile.ZipFile(self.output, "x", allowZip64=True) as archive:
            archive.writestr(info, payload)
        with self.output.open("r+b") as stream:
            module._force_zip64_eocd(stream)

        with self.assertRaisesRegex(module.OfflineZipError, "extra"):
            module.verify_data_zip(
                self.output, {entry.path: entry}, expected_members=1, production=False
            )

    def test_verifier_rejects_central_version_flags_and_internal_attr_drift(self) -> None:
        mutations = (
            ("create version", 4, "<B", 44),
            ("extract version", 6, "<B", 44),
            ("flag bits", 8, "<H", 0x0800),
            ("internal attr", 36, "<H", 1),
        )
        for index, (label, field_offset, field_format, value) in enumerate(mutations):
            with self.subTest(label=label):
                output = self.root / f"central-{index}.zip"
                module.write_data_zip(self.stage, output, self.entries, production=False)
                raw = bytearray(output.read_bytes())
                central_offset = raw.find(zipfile.stringCentralDir)
                struct.pack_into(field_format, raw, central_offset + field_offset, value)
                output.write_bytes(raw)

                with self.assertRaisesRegex(module.OfflineZipError, "metadata"):
                    module.verify_data_zip(
                        output,
                        {entry.path: entry for entry in self.entries},
                        expected_members=len(self.entries),
                        production=False,
                    )

    def test_verifier_rejects_local_header_metadata_drift(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        raw = bytearray(self.output.read_bytes())
        local_offset = raw.find(zipfile.stringFileHeader)
        struct.pack_into("<H", raw, local_offset + 6, 0x0800)
        self.output.write_bytes(raw)

        with self.assertRaisesRegex(module.OfflineZipError, "local header metadata"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_rejects_tampered_payload(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        raw = bytearray(self.output.read_bytes())
        offset = raw.index(b"common")
        raw[offset] ^= 1
        self.output.write_bytes(raw)

        with self.assertRaisesRegex(module.OfflineZipError, "SHA-256"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_writer_rejects_staged_size_or_hash_mismatch(self) -> None:
        entry = self.entries[-1]
        bad_size = ManifestEntry(entry.path, entry.size + 1, entry.sha256, entry.source)
        bad_hash = ManifestEntry(entry.path, entry.size, "0" * 64, entry.source)

        with self.assertRaisesRegex(module.OfflineZipError, "size"):
            module.write_data_zip(self.stage, self.output, (bad_size,), production=False)
        with self.assertRaisesRegex(module.OfflineZipError, "SHA-256"):
            module.write_data_zip(
                self.stage, self.root / "bad-hash.zip", (bad_hash,), production=False
            )

    def test_verifier_rejects_manifest_member_set_mismatch(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        expected = {entry.path: entry for entry in self.entries[:-1]}

        with self.assertRaisesRegex(module.OfflineZipError, "manifest"):
            module.verify_data_zip(
                self.output, expected, expected_members=len(self.entries), production=False
            )

    def test_output_creation_is_exclusive(self) -> None:
        self.output.write_bytes(b"keep")

        with self.assertRaises(FileExistsError):
            module.write_data_zip(self.stage, self.output, self.entries, production=False)

        self.assertEqual(self.output.read_bytes(), b"keep")

    def test_writer_uses_one_bound_output_handle_for_build_and_verification(self) -> None:
        real_path_open = Path.open

        def guarded_path_open(path: Path, *args: object, **kwargs: object):
            if path == self.output:
                raise AssertionError("output path was reopened")
            return real_path_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", guarded_path_open), mock.patch.object(
            module.os, "open", wraps=os.open
        ) as open_call:
            module.write_data_zip(self.stage, self.output, self.entries, production=False)

        output_opens = [call for call in open_call.call_args_list if Path(call.args[0]) == self.output]
        self.assertEqual(len(output_opens), 1)

    def test_public_verifier_uses_one_bound_archive_handle(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        real_path_open = Path.open

        def guarded_path_open(path: Path, *args: object, **kwargs: object):
            if path == self.output:
                raise AssertionError("archive path was reopened")
            return real_path_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", guarded_path_open), mock.patch.object(
            module.os, "open", wraps=os.open
        ) as open_call:
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

        output_opens = [call for call in open_call.call_args_list if Path(call.args[0]) == self.output]
        self.assertEqual(len(output_opens), 1)

    def test_cleanup_does_not_delete_an_atomic_replacement(self) -> None:
        self.output.write_bytes(b"owned")
        owned_identity = module._path_identity(self.output)
        moved = self.root / "moved.zip"
        os.replace(self.output, moved)
        self.output.write_bytes(b"replacement")

        module._cleanup_owned_output(self.output, owned_identity)

        self.assertEqual(self.output.read_bytes(), b"replacement")

    def test_writer_detects_identity_change_and_preserves_unowned_path(self) -> None:
        calls = 0

        def swapped_identity(path: Path):
            nonlocal calls
            actual = module._identity_from_stat(os.lstat(path))
            calls += 1
            if calls == 1:
                return actual
            return module._FileIdentity(actual.device, actual.inode + 1)

        with mock.patch.object(module, "_path_identity", side_effect=swapped_identity):
            with self.assertRaisesRegex(module.OfflineZipError, "identity changed"):
                module.write_data_zip(
                    self.stage, self.output, self.entries, production=False
                )

        self.assertTrue(self.output.exists())

    def test_verifier_requires_zip64_eocd(self) -> None:
        entry = self.entries[0]
        module.write_data_zip(self.stage, self.output, (entry,), production=False)
        self.strip_zip64_end_records()

        with self.assertRaisesRegex(module.OfflineZipError, "Zip64"):
            module.verify_data_zip(
                self.output, {entry.path: entry}, expected_members=1, production=False
            )

    def test_payload_zip64_signatures_do_not_count_as_a_zip64_end_record(self) -> None:
        path = "WorldFlipper/dummy/download/production/upload/dd/" + "4" * 38
        payload = b"PK\x06\x06payload-PK\x06\x07"
        entry = ManifestEntry(path, len(payload), sha256(payload), "fixture")
        target = self.stage.parent / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        module.write_data_zip(self.stage, self.output, (entry,), production=False)
        self.strip_zip64_end_records()

        with self.assertRaisesRegex(module.OfflineZipError, "Zip64"):
            module.verify_data_zip(
                self.output, {path: entry}, expected_members=1, production=False
            )

    def test_verifier_cross_checks_zip64_member_count(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        raw = bytearray(self.output.read_bytes())
        zip64_offset = raw.rfind(zipfile.stringEndArchive64)
        wrong_count = len(self.entries) + 1
        struct.pack_into("<Q", raw, zip64_offset + 24, wrong_count)
        struct.pack_into("<Q", raw, zip64_offset + 32, wrong_count)
        self.output.write_bytes(raw)

        with self.assertRaisesRegex(module.OfflineZipError, "Zip64.*count"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_cross_checks_classic_and_zip64_central_directory(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        raw = bytearray(self.output.read_bytes())
        eocd_offset = raw.rfind(zipfile.stringEndArchive)
        central_size = struct.unpack_from("<L", raw, eocd_offset + 12)[0]
        struct.pack_into("<L", raw, eocd_offset + 12, central_size + 1)
        self.output.write_bytes(raw)

        with self.assertRaisesRegex(module.OfflineZipError, "central directory"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_verifier_rejects_zip64_extensible_data_sector(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)
        raw = bytearray(self.output.read_bytes())
        zip64_offset = raw.rfind(zipfile.stringEndArchive64)
        locator_offset = raw.rfind(zipfile.stringEndArchive64Locator)
        struct.pack_into("<Q", raw, zip64_offset + 4, 48)
        raw[locator_offset:locator_offset] = b"JUNK"
        self.output.write_bytes(raw)

        with self.assertRaisesRegex(module.OfflineZipError, "extensible"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
                expected_members=len(self.entries),
                production=False,
            )

    def test_writer_rejects_non_worldflipper_staged_root(self) -> None:
        with self.assertRaisesRegex(module.OfflineZipError, "basename.*WorldFlipper"):
            module.write_data_zip(
                self.stage.parent, self.output, self.entries, production=False
            )

    def test_writer_rejects_wrong_info_version(self) -> None:
        entry = next(item for item in self.entries if item.path == module.INFO_PATH)
        payload = b'{"version":"1.4.195"}\n'
        (self.stage.parent / entry.path).write_bytes(payload)
        wrong = ManifestEntry(entry.path, len(payload), sha256(payload), entry.source)

        with self.assertRaisesRegex(module.OfflineZipError, "info.json.*1.4.196"):
            module.write_data_zip(
                self.stage,
                self.output,
                tuple(wrong if item == entry else item for item in self.entries),
                production=False,
            )

    def test_manifest_types_are_validated_before_values(self) -> None:
        valid = self.entries[-1]
        cases = (
            (ManifestEntry(True, valid.size, valid.sha256, valid.source), "path"),
            (ManifestEntry(valid.path, True, valid.sha256, valid.source), "size.*integer"),
            (ManifestEntry(valid.path, valid.size, b"0" * 64, valid.source), "SHA-256.*string"),
        )
        for index, (entry, message) in enumerate(cases):
            with self.subTest(message=message):
                with self.assertRaisesRegex(module.OfflineZipError, message):
                    module.write_data_zip(
                        self.stage,
                        self.root / f"type-{index}.zip",
                        (entry,),
                        production=False,
                    )

    def test_default_verifier_enforces_production_member_count(self) -> None:
        module.write_data_zip(self.stage, self.output, self.entries, production=False)

        with self.assertRaisesRegex(module.OfflineZipError, "138291"):
            module.verify_data_zip(
                self.output,
                {entry.path: entry for entry in self.entries},
            )

    def test_default_writer_rejects_138290_member_manifest(self) -> None:
        entries = self.make_production_manifest(
            common=113_821, medium=23_458, android=1_009
        )

        with self.assertRaisesRegex(module.OfflineZipError, "138291"):
            module.write_data_zip(self.stage, self.output, entries)

        self.assertFalse(self.output.exists())

    def test_default_writer_rejects_wrong_root_distribution_at_138291_total(self) -> None:
        entries = self.make_production_manifest(
            common=113_821, medium=23_459, android=1_009
        )

        with self.assertRaisesRegex(module.OfflineZipError, "production common"):
            module.write_data_zip(self.stage, self.output, entries)

        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
