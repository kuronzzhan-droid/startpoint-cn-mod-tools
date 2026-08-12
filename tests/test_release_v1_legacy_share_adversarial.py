from __future__ import annotations

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from tests.release_v1_fixtures import corrupt_zip_member_crc, rewrite_outer_member_raw_name
from tests.test_release_v1_legacy_share import _inner_archive, _json, _member
from wf_release_v1.errors import ReleaseError
import wf_release_v1.legacy_share as legacy_share


def _requirements(
    archive_name: str,
    *,
    variant: str = "full",
    from_version: str = "1.4.324",
    target_version: str = "1.4.347",
) -> dict[str, object]:
    content_only = variant == "content-only"
    return {
        "schemaVersion": 2,
        "pack": {
            "variant": variant,
            "since": "1.4.323",
            "tail": "1.4.346",
            "sourceEdges": 23,
            "anchor": {"from": from_version, "to": target_version},
            "archives": [archive_name],
        },
        "enhancement": not content_only,
        "enhancementDetail": {
            "officialBaseline": "1.4.49" if content_only else None,
            "revertedRows": 1 if content_only else 0,
            "restoredRows": 0,
            "revertedTables": ["master/character.orderedmap"] if content_only else [],
            "droppedEntries": ["production/upload/aa/" + "f" * 38] if content_only else [],
            "note": "producer-shaped metadata",
            "serverSideEnhancements": [],
        },
        "requires": {
            "serverRestart": False,
            "restartReasons": [],
            "minServerVersion": None,
            "serverFeatures": [],
            "clientPatches": [],
        },
    }


def _report(
    archive_name: str,
    archive_raw: bytes,
    *,
    variant: str = "full",
    entries: int = 7,
    tag: str = "fixture",
) -> dict[str, object]:
    summary: dict[str, object] = {
        "entries": entries,
        "kept": entries,
        "dropped": 0,
        "rebuilt": 0,
    }
    if variant == "content-only":
        summary.update(
            {
                "entries": entries + 1,
                "kept": entries - 1,
                "dropped": 1,
                "rebuilt": 1,
                "revertedRows": 1,
                "restoredRows": 0,
                "nestedExtendedRows": 0,
                "droppedLogicals": ["production/upload/aa/" + "f" * 38],
                "rebuiltTables": [
                    {
                        "logical": "master/character.orderedmap",
                        "reverted": 1,
                        "restored": 0,
                        "nestedExtended": 0,
                        "kept": 1,
                    }
                ],
                "unrecognizedAdditions": {},
            }
        )
    from_version, target_version = archive_name.split("pinball-", 1)[1].split("-", 2)[:2]
    return {
        "variant": variant,
        "tag": tag,
        "pack": f"wfshare-{from_version}-to-{target_version}-{variant}",
        "entries": entries,
        "summary": summary,
        "outputs": [
            {
                "root": archive_name.split("archive-", 1)[1].split("-diff/", 1)[0],
                "path": archive_name,
                "entries": entries,
                "size": len(archive_raw),
                "sha256": hashlib.sha256(archive_raw).hexdigest(),
            }
        ],
    }


def _write_variant(
    path: Path,
    *,
    variant: str = "full",
    from_version: str = "1.4.324",
    target_version: str = "1.4.347",
    sequence: int = 1,
    tag: str = "fixture",
    inner_raw: bytes | None = None,
    requires_mutator=None,
    report_mutator=None,
    server_members: tuple[tuple[str, bytes], ...] = (),
) -> None:
    raw = inner_raw or _inner_archive()
    with zipfile.ZipFile(BytesIO(raw)) as inner:
        entries = sum(not info.is_dir() for info in inner.infolist())
    archive_name = (
        f"archive-common-diff/pinball-{from_version}-{target_version}-{sequence}-{tag}.zip"
    )
    requires = _requirements(
        archive_name,
        variant=variant,
        from_version=from_version,
        target_version=target_version,
    )
    report = _report(archive_name, raw, variant=variant, entries=entries, tag=tag)
    if requires_mutator is not None:
        requires_mutator(requires)
    if report_mutator is not None:
        report_mutator(report)
    members = [
        (archive_name, raw),
        ("requires.json", _json(requires)),
        ("report.json", _json(report)),
        ("README.txt", b"fixture\n"),
        *server_members,
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, payload in members:
            info, data = _member(f"wfshare-fixture/{name}", payload)
            bundle.writestr(info, data)


def _rewrite_method(path: Path, member_name: str, method: int) -> None:
    with zipfile.ZipFile(path) as bundle:
        info = bundle.getinfo(member_name)
        central = bundle.start_dir
    raw = bytearray(path.read_bytes())
    struct.pack_into("<H", raw, info.header_offset + 8, method)
    cursor = central
    while raw[cursor : cursor + 4] == b"PK\x01\x02":
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw, cursor + 28)
        if struct.unpack_from("<I", raw, cursor + 42)[0] == info.header_offset:
            struct.pack_into("<H", raw, cursor + 10, method)
            path.write_bytes(raw)
            return
        cursor += 46 + name_len + extra_len + comment_len
    raise AssertionError("central member not found")


class LegacyShareAdversarialCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wf-release-share-adversarial-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.share = self.root / "share.zip"

    def test_content_only_producer_summary_is_accepted(self) -> None:
        names = tuple(f"production/upload/{index:02x}/{'b' * 37}{index:x}" for index in range(6))
        _write_variant(self.share, variant="content-only", inner_raw=_inner_archive(names=names))
        plan = legacy_share.inspect_legacy_share(self.share).to_wire()
        self.assertEqual(plan["variant"], "content-only")
        self.assertEqual(plan["contentEntryCount"], 6)

    def test_catalog_export_dialect_without_report_is_accepted(self) -> None:
        raw = _inner_archive()
        archive_name = "archive-common-diff/pinball-1.4.324-1.4.347-1-catalog+safe.zip"
        requires = {
            "schemaVersion": 2,
            "pack": {"variant": "full", "since": "1.4.324", "tail": "1.4.347", "edges": 1},
            "enhancement": True,
            "enhancementDetail": {"note": "catalog export"},
            "requires": {
                "serverRestart": False,
                "restartReasons": [],
                "minServerVersion": None,
                "serverFeatures": [],
                "clientPatches": [],
            },
        }
        members = (
            (archive_name, raw),
            ("requires.json", _json(requires)),
            ("dev-catalog/EntityLists/character.csv", b"id,name\n179999,Rolf\n"),
            ("README.txt", b"catalog fixture\n"),
        )
        with zipfile.ZipFile(self.share, "w", compression=zipfile.ZIP_STORED) as bundle:
            for name, payload in members:
                info, data = _member(f"wfshare-catalog/{name}", payload)
                bundle.writestr(info, data)
        plan = legacy_share.inspect_legacy_share(self.share).to_wire()
        self.assertEqual(plan["sourceDialect"], "catalog-export")
        self.assertEqual((plan["fromVersion"], plan["targetVersion"]), ("1.4.324", "1.4.347"))

    def test_content_only_detailed_summary_closure_is_enforced(self) -> None:
        def mismatched_reverted(requires: dict[str, object]) -> None:
            requires["enhancementDetail"]["revertedRows"] = 999

        def mismatched_report_reverted(report: dict[str, object]) -> None:
            report["summary"]["revertedRows"] = 999

        def missing_dropped_logical(requires: dict[str, object]) -> None:
            requires["enhancementDetail"]["droppedEntries"] = []

        def missing_report_dropped_logical(report: dict[str, object]) -> None:
            report["summary"]["droppedLogicals"] = []

        def table_without_rebuild_count(report: dict[str, object]) -> None:
            summary = report["summary"]
            summary["kept"] = summary["kept"] + 1
            summary["rebuilt"] = 0

        def nested_total_below_table_detail(report: dict[str, object]) -> None:
            report["summary"]["rebuiltTables"][0]["nestedExtended"] = 1

        def empty_unrecognized_rows(report: dict[str, object]) -> None:
            report["summary"]["unrecognizedAdditions"] = {
                "master/example.orderedmap": []
            }

        cases = (
            (mismatched_reverted, mismatched_report_reverted),
            (missing_dropped_logical, missing_report_dropped_logical),
            (None, table_without_rebuild_count),
            (None, nested_total_below_table_detail),
            (None, empty_unrecognized_rows),
        )
        names = tuple(f"production/upload/{index:02x}/{'b' * 37}{index:x}" for index in range(6))
        for requires_mutator, report_mutator in cases:
            with self.subTest(report_mutator=report_mutator.__name__):
                _write_variant(
                    self.share,
                    variant="content-only",
                    inner_raw=_inner_archive(names=names),
                    requires_mutator=requires_mutator,
                    report_mutator=report_mutator,
                )
                with self.assertRaises(ReleaseError):
                    legacy_share.inspect_legacy_share(self.share)

    def test_strict_metadata_rejects_semantically_impossible_documents(self) -> None:
        mutations = {
            "empty requirements": lambda value: value.__setitem__("requires", {}),
            "empty enhancement detail": lambda value: value.__setitem__("enhancementDetail", {}),
            "enhancement mismatch": lambda value: value.__setitem__("enhancement", False),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                _write_variant(self.share, requires_mutator=mutation)
                with self.assertRaises(ReleaseError) as caught:
                    legacy_share.inspect_legacy_share(self.share)
                self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")

    def test_edge_tag_summary_and_part_invariants_are_enforced(self) -> None:
        cases = (
            ("decreasing edge", {"from_version": "1.4.347", "target_version": "1.4.324"}),
            ("noncontiguous part", {"sequence": 2}),
            ("tag mismatch", {"report_mutator": lambda report: report.__setitem__("tag", "other")}),
            (
                "summary arithmetic",
                {"report_mutator": lambda report: report["summary"].__setitem__("kept", 6)},
            ),
        )
        for label, kwargs in cases:
            with self.subTest(label=label):
                _write_variant(self.share, **kwargs)
                with self.assertRaises(ReleaseError):
                    legacy_share.inspect_legacy_share(self.share)

    def test_raw_nul_portable_alias_and_wrong_layer_are_rejected(self) -> None:
        _write_variant(self.share)
        rewrite_outer_member_raw_name(
            self.share,
            "wfshare-fixture/requires.json",
            "wfshare-fixture/requires.json\x00hidden",
        )
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

        aliases = (
            "production/upload/aa/" + "a" * 38,
            "production/upload/AA/" + "A" * 38,
        )
        _write_variant(self.share, inner_raw=_inner_archive(names=aliases))
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

        _write_variant(self.share, inner_raw=_inner_archive(prefix="production/medium_upload"))
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

    def test_all_directory_entries_share_the_same_portable_root(self) -> None:
        _write_variant(self.share)
        with zipfile.ZipFile(self.share, "a") as bundle:
            bundle.writestr(zipfile.ZipInfo("other-root/"), b"")
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

    def test_windows_superscript_device_aliases_are_rejected(self) -> None:
        for name in ("COM¹.txt", "COM².txt", "COM³.txt", "LPT¹.txt", "LPT².txt", "LPT³.txt"):
            with self.subTest(name=name):
                _write_variant(self.share, server_members=((f"server-data/{name}", b"x"),))
                with self.assertRaises(ReleaseError):
                    legacy_share.inspect_legacy_share(self.share)

    def test_crc_compression_ratio_and_unsupported_method_are_rejected(self) -> None:
        _write_variant(self.share, server_members=(("server-data/apply.py", b"print('no')\n"),))
        corrupt_zip_member_crc(self.share, "wfshare-fixture/server-data/apply.py")
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

        compressed = BytesIO()
        with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_DEFLATED) as inner:
            inner.writestr("production/upload/aa/" + "a" * 38, b"0" * (2 * 1024 * 1024))
        _write_variant(self.share, inner_raw=compressed.getvalue())
        with self.assertRaises(ReleaseError):
            legacy_share.inspect_legacy_share(self.share)

        _write_variant(self.share)
        _rewrite_method(self.share, "wfshare-fixture/requires.json", 99)
        with self.assertRaises(ReleaseError) as caught:
            legacy_share.inspect_legacy_share(self.share)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-m",
                "wf_release_v1",
                "inspect-share",
                "--share",
                str(self.share),
                "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 10)
        self.assertIn(b'"code":"WFREL_SHARE_INVALID"', result.stderr)
        self.assertNotIn(str(self.root).encode("utf-8"), result.stderr)

    def test_server_script_classification_and_absence_proof_remain_blocking(self) -> None:
        _write_variant(self.share, server_members=(("server-data/apply.vbs", b"WScript.Quit\n"),))
        plan = legacy_share.inspect_legacy_share(self.share).to_wire()
        self.assertEqual(plan["serverDataScripts"], 1)
        self.assertIn("server-data-script-review-required", plan["blockers"])

        _write_variant(self.share, server_members=(("server-assets/mode.mjs", b"export {};\n"),))
        plan = legacy_share.inspect_legacy_share(self.share).to_wire()
        self.assertEqual(plan["serverDataScripts"], 1)
        self.assertIn("server-data-script-review-required", plan["blockers"])

        _write_variant(self.share)
        plan = legacy_share.inspect_legacy_share(self.share).to_wire()
        self.assertIn("server-data-migration-required", plan["blockers"])

    def test_plan_digest_is_bound_to_the_bytes_that_were_parsed(self) -> None:
        _write_variant(self.share, tag="source")
        source_raw = self.share.read_bytes()
        replacement = self.root / "replacement.zip"
        _write_variant(replacement, tag="target")
        replacement_raw = replacement.read_bytes()
        self.assertEqual(len(source_raw), len(replacement_raw))
        source_stat = self.share.stat()
        real_zip = zipfile.ZipFile

        def replace_then_open(stream, *args, **kwargs):
            self.share.write_bytes(replacement_raw)
            os.utime(self.share, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
            return real_zip(stream, *args, **kwargs)

        with mock.patch.object(legacy_share, "ZipFile", side_effect=replace_then_open):
            with self.assertRaisesRegex(ReleaseError, "changed"):
                legacy_share.inspect_legacy_share(self.share)


if __name__ == "__main__":
    unittest.main()
