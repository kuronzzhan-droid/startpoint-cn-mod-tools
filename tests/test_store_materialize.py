# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import importlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


COMMON_A = "production/upload/aa/" + "1" * 38
COMMON_B = "production/upload/ab/" + "2" * 38
MEDIUM_A = "production/medium_upload/ba/" + "3" * 38
ANDROID_A = "production/android_upload/ca/" + "4" * 38


def make_zip(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.cdn = root / "cdn" / "cn"
        self.server = root / "server"
        self.dest = root / "materialized"
        for root_name in ("common", "medium", "android"):
            (self.cdn / f"archive-{root_name}-full").mkdir(parents=True)
            (self.cdn / f"archive-{root_name}-diff").mkdir(parents=True)
        (self.server / "assets" / "asset-patch" / "active").mkdir(parents=True)

    def full(self, root_name: str, entries: dict[str, bytes], seq: int = 1) -> Path:
        path = self.cdn / f"archive-{root_name}-full" / f"pinball-1.4.0-{seq}-fixture.zip"
        make_zip(path, entries)
        return path

    def diff(
        self,
        root_name: str,
        frm: str,
        to: str,
        entries: dict[str, bytes],
        tag: str = "fixture",
    ) -> Path:
        path = (
            self.cdn
            / f"archive-{root_name}-diff"
            / f"pinball-{frm}-{to}-1-{tag}.zip"
        )
        make_zip(path, entries)
        return path

    def patch(
        self, frm: str, to: str, entries: dict[str, bytes], tag: str = "patch"
    ) -> Path:
        path = (
            self.server
            / "assets"
            / "asset-patch"
            / "active"
            / f"pinball-{frm}-{to}-1-{tag}.zip"
        )
        make_zip(path, entries)
        return path

    def args(self, *extra: str) -> list[str]:
        return [
            "--cdn", str(self.cdn),
            "--dest", str(self.dest),
            "--server-dir", str(self.server),
            "--workers", "1",
            *extra,
        ]


class StoreMaterializeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = Fixture(Path(self.tmp.name))

    def module(self):
        try:
            return importlib.import_module("wf_store_materialize")
        except ModuleNotFoundError:
            self.fail("wf_store_materialize CLI is missing")

    def run_cli(self, *extra: str):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.module().main(self.fx.args(*extra))
        lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
        summary = json.loads(lines[-1]) if lines else None
        return code, summary, stdout.getvalue(), stderr.getvalue()

    def test_default_dry_run_plans_full_archives_without_writing(self):
        self.fx.full("common", {COMMON_A: b"base", ".empty": b"0"})
        make_zip(
            self.fx.cdn / "archive-ios-full" / "pinball-1.4.0-1-ios.zip",
            {COMMON_A: b"must-be-ignored"},
        )

        code, summary, stdout, _stderr = self.run_cli()

        self.assertEqual(0, code)
        self.assertFalse(self.fx.dest.exists())
        self.assertEqual(
            ["ok", "tail", "files", "bytes", "rejected", "per_root"],
            list(summary),
        )
        self.assertIn(
            "[plan] tail=1.4.0 edges=0 files=1 bytes=4 rejected=0",
            stdout.splitlines(),
        )
        self.assertEqual(
            {
                "ok": True,
                "tail": "1.4.0",
                "files": 1,
                "bytes": 4,
                "rejected": 0,
                "per_root": {
                    "common": {"files": 1, "bytes": 4},
                    "medium": {"files": 0, "bytes": 0},
                    "android": {"files": 0, "bytes": 0},
                },
            },
            summary,
        )

    def test_apply_replays_diff_over_full_and_writes_each_final_winner(self):
        self.fx.full("common", {COMMON_A: b"old", COMMON_B: b"keep"})
        self.fx.full("android", {ANDROID_A: b"android"})
        self.fx.diff("common", "1.4.0", "1.4.1", {COMMON_A: b"new"})
        self.fx.diff("medium", "1.4.0", "1.4.1", {MEDIUM_A: b"medium"})

        code, summary, stdout, _stderr = self.run_cli("--workers", "2", "--apply")

        self.assertEqual(0, code)
        self.assertEqual("1.4.1", summary["tail"])
        self.assertEqual(4, summary["files"])
        self.assertIn("4/4", stdout.splitlines())
        self.assertEqual(
            b"new", (self.fx.dest / "production" / "upload" / "aa" / ("1" * 38)).read_bytes()
        )
        self.assertEqual(
            b"keep", (self.fx.dest / "production" / "upload" / "ab" / ("2" * 38)).read_bytes()
        )
        self.assertEqual(
            b"medium",
            (
                self.fx.dest
                / "production"
                / "medium_upload"
                / "ba"
                / ("3" * 38)
            ).read_bytes(),
        )
        self.assertEqual(
            b"android",
            (
                self.fx.dest
                / "production"
                / "android_upload"
                / "ca"
                / ("4" * 38)
            ).read_bytes(),
        )

    def test_active_charpkg_and_asset_patch_participate_in_visible_root_order(self):
        self.fx.full("common", {COMMON_A: b"base-a", COMMON_B: b"base-b"})
        self.fx.diff(
            "common",
            "1.4.0",
            "1.4.1",
            {COMMON_A: b"legacy-a", COMMON_B: b"legacy-b"},
            tag="aaa",
        )
        charpkg = self.fx.diff(
            "common",
            "1.4.0",
            "1.4.1",
            {COMMON_A: b"charpkg-a"},
            tag="charpkg-hero",
        )
        self.fx.patch("1.4.0", "1.4.1", {COMMON_B: b"patch-b"})
        active = self.fx.cdn / "character-releases" / "active.json"
        active.parent.mkdir(parents=True)
        active.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "base_version": "1.4.0",
                    "releases": [
                        {
                            "from_version": "1.4.0",
                            "version": "1.4.1",
                            "release_id": "hero",
                            "archives": [
                                {
                                    "root": "common",
                                    "relative_path": "archive-common-diff/" + charpkg.name,
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        code, _summary, _stdout, _stderr = self.run_cli("--apply")

        self.assertEqual(0, code)
        common = self.fx.dest / "production" / "upload"
        self.assertEqual(b"charpkg-a", (common / "aa" / ("1" * 38)).read_bytes())
        self.assertEqual(b"patch-b", (common / "ab" / ("2" * 38)).read_bytes())

    def test_invalid_archive_members_are_rejected_and_never_escape_destination(self):
        self.fx.full(
            "common",
            {
                COMMON_A: b"safe",
                "../outside-full": b"bad-full",
                "../.empty": b"not-a-placeholder",
                "production/upload/aa/": b"not-a-file",
            },
        )
        self.fx.diff(
            "common",
            "1.4.0",
            "1.4.1",
            {"production/upload/../../outside-diff": b"bad-diff"},
        )

        code, summary, _stdout, _stderr = self.run_cli("--apply")

        self.assertEqual(0, code)
        self.assertEqual(4, summary["rejected"])
        self.assertFalse((self.fx.root / "outside-full").exists())
        self.assertFalse((self.fx.root / "outside-diff").exists())

    def test_nonempty_destination_is_refused_without_touching_existing_file(self):
        self.fx.full("common", {COMMON_A: b"safe"})
        self.fx.dest.mkdir()
        marker = self.fx.dest / "keep.txt"
        marker.write_bytes(b"untouched")

        code, summary, _stdout, stderr = self.run_cli("--apply")

        self.assertEqual(2, code)
        self.assertFalse(summary["ok"])
        self.assertIn("nonexistent or empty", stderr)
        self.assertEqual(b"untouched", marker.read_bytes())

    def test_explicit_tail_uses_targeted_path_instead_of_highest_reachable(self):
        self.fx.full("common", {COMMON_A: b"base"})
        self.fx.diff("common", "1.4.0", "1.4.1", {COMMON_A: b"v1"})
        self.fx.diff("common", "1.4.1", "1.4.2", {COMMON_A: b"v2"})

        code, summary, _stdout, _stderr = self.run_cli(
            "--tail", "1.4.1", "--apply"
        )

        self.assertEqual(0, code)
        self.assertEqual("1.4.1", summary["tail"])
        self.assertEqual(
            b"v1",
            (
                self.fx.dest
                / "production"
                / "upload"
                / "aa"
                / ("1" * 38)
            ).read_bytes(),
        )

    def test_unreachable_tail_is_reported_without_creating_destination(self):
        self.fx.full("common", {COMMON_A: b"base"})

        code, summary, _stdout, stderr = self.run_cli("--tail", "1.4.99")

        self.assertEqual(2, code)
        self.assertEqual("1.4.99", summary["tail"])
        self.assertFalse(summary["ok"])
        self.assertIn("unreachable", stderr)
        self.assertFalse(self.fx.dest.exists())

    def test_official_only_stops_at_154_and_excludes_patch_and_mod_archives(self):
        self.fx.full("common", {COMMON_A: b"base-a", COMMON_B: b"base-b"})
        self.fx.diff(
            "common",
            "1.4.0",
            "1.4.54",
            {COMMON_A: b"official-a", COMMON_B: b"official-b"},
            tag="official",
        )
        self.fx.patch("1.4.0", "1.4.54", {COMMON_B: b"patch-b"})
        self.fx.diff(
            "common",
            "1.4.54",
            "1.4.55",
            {COMMON_A: b"mod-a"},
            tag="mod",
        )

        code, summary, _stdout, _stderr = self.run_cli(
            "--official-only", "--apply"
        )

        self.assertEqual(0, code)
        self.assertEqual("1.4.54", summary["tail"])
        common = self.fx.dest / "production" / "upload"
        self.assertEqual(b"official-a", (common / "aa" / ("1" * 38)).read_bytes())
        self.assertEqual(b"official-b", (common / "ab" / ("2" * 38)).read_bytes())

    def test_official_only_rejects_tail_after_canonical_official_end(self):
        self.fx.full("common", {COMMON_A: b"base"})

        code, summary, _stdout, stderr = self.run_cli(
            "--official-only", "--tail", "1.4.55"
        )

        self.assertEqual(2, code)
        self.assertFalse(summary["ok"])
        self.assertIn("--official-only tail", stderr)
        self.assertFalse(self.fx.dest.exists())

    def test_verify_detects_same_size_crc_corruption_after_materialization(self):
        self.fx.full("common", {COMMON_A: b"good"})
        module = self.module()
        self.assertTrue(
            hasattr(module, "_verify_plan"),
            "materializer has no post-write verifier",
        )
        plan = module._build_plan(self.fx.cdn, self.fx.server, None, False)
        with contextlib.redirect_stdout(io.StringIO()):
            module._write_plan(plan, self.fx.dest, 1)
        target = (
            self.fx.dest
            / "production"
            / "upload"
            / "aa"
            / ("1" * 38)
        )
        target.write_bytes(b"evil")

        with self.assertRaisesRegex(module.MaterializeError, "CRC"):
            module._verify_plan(plan, self.fx.dest, 1)

    def test_write_profile_updates_active_entry_and_preserves_fields_and_backup(self):
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "config" / "profiles.json"
        profiles.parent.mkdir()
        original_payload = {
            "_comment": "keep top level",
            "active": "alt",
            "custom": {"keep": True},
            "profiles": {
                "alt": {
                    "label": "Alternate",
                    "store": "old/store",
                    "res_version": "9.9.9",
                    "fallback": "keep/fallback",
                    "custom_entry": 7,
                },
                "cn": {"label": "CN", "store": "unchanged/cn"},
            },
        }
        original = json.dumps(original_payload, ensure_ascii=False, indent=2).encode("utf-8")
        profiles.write_bytes(original)

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        updated = json.loads(profiles.read_text(encoding="utf-8"))
        self.assertEqual("keep top level", updated["_comment"])
        self.assertEqual({"keep": True}, updated["custom"])
        self.assertEqual(original_payload["profiles"]["cn"], updated["profiles"]["cn"])
        self.assertEqual("9.9.9", updated["profiles"]["alt"]["res_version"])
        self.assertEqual("keep/fallback", updated["profiles"]["alt"]["fallback"])
        self.assertEqual(7, updated["profiles"]["alt"]["custom_entry"])
        self.assertEqual(
            str((self.fx.dest / "production" / "upload").resolve()),
            updated["profiles"]["alt"]["store"],
        )
        backups = list(profiles.parent.glob("profiles.json.bak-materialize-*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(original, backups[0].read_bytes())

    def test_write_profile_creates_default_cn_profile_with_official_version(self):
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "new-config" / "profiles.json"

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        payload = json.loads(profiles.read_text(encoding="utf-8"))
        self.assertEqual("cn", payload["active"])
        self.assertEqual("1.4.54", payload["profiles"]["cn"]["res_version"])
        self.assertEqual(
            str((self.fx.dest / "production" / "upload").resolve()),
            payload["profiles"]["cn"]["store"],
        )
        self.assertFalse(list(profiles.parent.glob("*.bak-materialize-*")))

    def test_write_profile_flag_in_default_dry_run_mutates_nothing(self):
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "profiles.json"
        original = b'{"active":"cn","profiles":{"cn":{"store":"old"}}}'
        profiles.write_bytes(original)

        code, _summary, _stdout, _stderr = self.run_cli(
            "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        self.assertEqual(original, profiles.read_bytes())
        self.assertFalse(list(profiles.parent.glob("*.bak-materialize-*")))

    def test_apply_verify_runs_post_write_scan_before_success_summary(self):
        self.fx.full("common", {COMMON_A: b"base"})

        code, summary, stdout, _stderr = self.run_cli("--apply", "--verify")

        self.assertEqual(0, code)
        self.assertTrue(summary["ok"])
        self.assertIn("[verify] files=1", stdout.splitlines())

    def test_post_plan_failure_reports_ok_false_but_keeps_plan_statistics(self):
        self.fx.full("common", {COMMON_A: b"base"})
        blocked_parent = self.fx.root / "blocked-parent"
        blocked_parent.write_bytes(b"not a directory")

        code, summary, _stdout, _stderr = self.run_cli(
            "--apply",
            "--write-profile",
            "--profiles",
            str(blocked_parent / "profiles.json"),
        )

        self.assertEqual(2, code)
        self.assertFalse(summary["ok"])
        self.assertEqual("1.4.0", summary["tail"])
        self.assertEqual(1, summary["files"])
        self.assertEqual(4, summary["bytes"])

    def test_corrupt_selected_diff_archive_is_a_stable_cli_error(self):
        self.fx.full("common", {COMMON_A: b"base"})
        corrupt = (
            self.fx.cdn
            / "archive-common-diff"
            / "pinball-1.4.0-1.4.1-1-corrupt.zip"
        )
        corrupt.write_bytes(b"not a zip")

        try:
            code, summary, _stdout, stderr = self.run_cli()
        except zipfile.BadZipFile:
            self.fail("corrupt diff archive escaped the CLI error contract")

        self.assertEqual(2, code)
        self.assertFalse(summary["ok"])
        self.assertIn("corrupt", stderr)
        self.assertFalse(self.fx.dest.exists())


if __name__ == "__main__":
    unittest.main()
