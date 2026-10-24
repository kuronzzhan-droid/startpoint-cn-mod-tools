from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from wf_release_v1.errors import ReleaseError
from wf_release_v1.legacy_share import inspect_legacy_share


def _json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def _member(name: str, raw: bytes) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.create_system = 0
    info.external_attr = 0o100666 << 16
    return info, raw


def _inner_archive(
    *,
    prefix: str = "production/upload",
    names: tuple[str, ...] | None = None,
    payload: bytes = b"payload",
) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as bundle:
        actual_names = names or tuple(
            f"{prefix}/{index:02x}/{'a' * 37}{index:x}" for index in range(7)
        )
        for name in actual_names:
            info, raw = _member(name, payload)
            bundle.writestr(info, raw)
    return output.getvalue()


class LegacyShareCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wf-release-share-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.share = self.root / "rolf-share.zip"

    def _write_share(
        self,
        *,
        digest_override: str | None = None,
        extra_members: tuple[tuple[str, bytes], ...] = (),
        omit_report_archive: bool = False,
        summary_entries: int = 7,
    ) -> None:
        archive_name = "archive-common-diff/pinball-1.4.324-1.4.347-1-rolf.zip"
        archive_raw = _inner_archive()
        digest = digest_override or hashlib.sha256(archive_raw).hexdigest()
        requires = {
            "schemaVersion": 2,
            "pack": {
                "variant": "full",
                "since": "1.4.323",
                "tail": "1.4.346",
                "sourceEdges": 23,
                "anchor": {"from": "1.4.324", "to": "1.4.347"},
                "archives": [archive_name],
            },
            "enhancement": True,
            "enhancementDetail": {
                "officialBaseline": None,
                "revertedRows": 0,
                "restoredRows": 0,
                "revertedTables": [],
                "droppedEntries": [],
                "note": "contains local balancing",
                "serverSideEnhancements": [],
            },
            "requires": {
                "serverRestart": True,
                "restartReasons": ["character table"],
                "minServerVersion": None,
                "serverFeatures": [],
                "clientPatches": [],
                "serverDataNote": "server rows are separate",
            },
        }
        outputs = [] if omit_report_archive else [{
            "root": "common",
            "path": archive_name,
            "entries": 7,
            "size": len(archive_raw),
            "sha256": digest,
        }]
        report = {
            "variant": "full",
            "tag": "rolf",
            "pack": "wfshare-1.4.324-to-1.4.347-full",
            "entries": 7,
            "summary": {"entries": summary_entries, "kept": 7, "dropped": 0, "rebuilt": 0},
            "outputs": outputs,
        }
        rows = {"assets/character.json": {"179999": {"name": "罗尔夫"}}}
        members = (
            (archive_name, archive_raw),
            ("requires.json", _json(requires)),
            ("report.json", _json(report)),
            ("server-data/rolf_rows.json", _json(rows)),
            ("server-data/apply_rows.py", b"raise RuntimeError('must not execute')\n"),
            ("README.txt", "legacy share fixture\n".encode()),
            *extra_members,
        )
        with ZipFile(self.share, "w", compression=ZIP_STORED) as bundle:
            for name, raw in members:
                info, payload = _member(f"wfshare-rolf/{name}", raw)
                bundle.writestr(info, payload)

    def test_valid_share_reports_manual_migration_without_executing_scripts(self) -> None:
        self._write_share()
        plan = inspect_legacy_share(self.share).to_wire()
        self.assertEqual(plan["sourceFormat"], "wfshare-v2")
        self.assertEqual(plan["sourceDialect"], "variant-report")
        self.assertEqual(plan["variant"], "full")
        self.assertEqual(plan["fromVersion"], "1.4.324")
        self.assertEqual(plan["targetVersion"], "1.4.347")
        self.assertEqual(plan["contentArchiveCount"], 1)
        self.assertEqual(plan["contentEntryCount"], 7)
        self.assertEqual(plan["serverDataFiles"], 2)
        self.assertEqual(plan["serverDataScripts"], 1)
        self.assertEqual(plan["migrationStatus"], "blocked")
        self.assertEqual(
            plan["blockers"],
            [
                "release-requirements-mapping-required",
                "sealed-character-workspace-required",
                "server-data-migration-required",
                "server-data-script-review-required",
            ],
        )
        self.assertEqual(plan["warnings"], ["full-variant-includes-enhancements"])
        self.assertNotIn(str(self.root), json.dumps(plan, ensure_ascii=False))

    def test_reported_archive_digest_must_match_bytes(self) -> None:
        self._write_share(digest_override="0" * 64)
        with self.assertRaisesRegex(ReleaseError, "archive digest") as caught:
            inspect_legacy_share(self.share)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")

    def test_report_and_requires_archive_sets_must_match(self) -> None:
        self._write_share(omit_report_archive=True)
        with self.assertRaisesRegex(ReleaseError, "archive declarations") as caught:
            inspect_legacy_share(self.share)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")

    def test_report_summary_must_match_archive_entries(self) -> None:
        self._write_share(summary_entries=8)
        with self.assertRaisesRegex(ReleaseError, "summary") as caught:
            inspect_legacy_share(self.share)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")

    def test_outer_archive_rejects_traversal_before_metadata_use(self) -> None:
        self._write_share(extra_members=(("../escape.txt", b"no"),))
        with self.assertRaisesRegex(ReleaseError, "unsafe member") as caught:
            inspect_legacy_share(self.share)
        self.assertEqual(caught.exception.code, "WFREL_SHARE_INVALID")

    def test_cli_outputs_one_sanitized_json_plan(self) -> None:
        self._write_share()
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
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout.count(b"\n"), 1)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["sourceFormat"], "wfshare-v2")
        self.assertNotIn(str(self.root), result.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
