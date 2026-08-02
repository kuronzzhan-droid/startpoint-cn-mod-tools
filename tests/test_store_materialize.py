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


class MaterializeCase(unittest.TestCase):
    """共享的微型合成 zip 装置(本身不带用例)。"""

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


class StoreMaterializeTest(MaterializeCase):
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
            [
                "ok",
                "tail",
                "files",
                "bytes",
                "rejected",
                "per_root",
                "unreachable_edges",
                "unreachable_samples",
                "max_visible_version",
                "chain_issues",
            ],
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
                "unreachable_edges": 0,
                "unreachable_samples": [],
                "max_visible_version": "1.4.0",
                "chain_issues": [],
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

    def test_write_profile_creates_default_cn_profile_with_materialized_tail(self):
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "new-config" / "profiles.json"

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        payload = json.loads(profiles.read_text(encoding="utf-8"))
        self.assertEqual("cn", payload["active"])
        self.assertEqual("1.4.0", payload["profiles"]["cn"]["res_version"])
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


class BrokenChainTest(MaterializeCase):
    """收方官方基座停在 1.4.54,mod 边从 1.4.90 起 —— 2026-07-17 野外事故的形状。

    旧行为:静默产出纯官方 store,tail=1.4.54 却 ok:true / exit 0,
    拿去发布 = 把客户端滚回几十个版本。
    """

    def setUp(self) -> None:
        super().setUp()
        self.fx.full("common", {COMMON_A: b"base-a", COMMON_B: b"base-b"})
        self.fx.full("medium", {MEDIUM_A: b"base-medium"})
        self.fx.full("android", {ANDROID_A: b"base-android"})
        self.fx.diff(
            "common", "1.4.0", "1.4.54", {COMMON_A: b"official-a"}, tag="official"
        )
        # 够不到的 mod 边:起点 1.4.90 从 1.4.0 走不到
        self.fx.patch("1.4.90", "1.4.100", {COMMON_B: b"mod-b"}, tag="mod")

    def test_unreachable_mod_edges_fail_loudly_instead_of_silent_official_store(self):
        code, summary, _stdout, stderr = self.run_cli()

        self.assertEqual(3, code)
        self.assertFalse(summary["ok"])
        self.assertEqual("1.4.54", summary["tail"])
        self.assertEqual(1, summary["unreachable_edges"])
        self.assertEqual("1.4.100", summary["max_visible_version"])
        self.assertEqual(1, len(summary["unreachable_samples"]))
        self.assertIn("1.4.90->1.4.100", summary["unreachable_samples"][0])
        self.assertIn("[ERR]", stderr)
        self.assertIn("chain break", stderr)
        self.assertIn("--allow-partial-chain", stderr)

    def test_broken_chain_refuses_to_write_the_rollback_store(self):
        code, _summary, _stdout, stderr = self.run_cli("--apply", "--verify")

        self.assertEqual(3, code)
        self.assertIn("[ERR]", stderr)
        self.assertFalse(self.fx.dest.exists())

    def test_allow_partial_chain_downgrades_to_warning_and_still_materializes(self):
        code, summary, _stdout, stderr = self.run_cli(
            "--allow-partial-chain", "--apply"
        )

        self.assertEqual(0, code)
        self.assertTrue(summary["ok"])
        self.assertEqual("1.4.54", summary["tail"])
        self.assertEqual(1, summary["unreachable_edges"])
        self.assertIn("[WARN]", stderr)
        self.assertIn("chain break", stderr)
        self.assertNotIn("[ERR]", stderr)
        common = self.fx.dest / "production" / "upload"
        self.assertEqual(b"official-a", (common / "aa" / ("1" * 38)).read_bytes())
        self.assertEqual(b"base-b", (common / "ab" / ("2" * 38)).read_bytes())

    def test_explicit_tail_states_an_intent_and_only_warns(self):
        code, summary, _stdout, stderr = self.run_cli("--tail", "1.4.54", "--apply")

        self.assertEqual(0, code)
        self.assertEqual(1, summary["unreachable_edges"])
        self.assertIn("[WARN]", stderr)
        self.assertNotIn("[ERR]", stderr)
        self.assertTrue(self.fx.dest.exists())

    def test_bridge_edges_below_the_tail_are_not_a_chain_break(self):
        # wf_chain_squash 的硬链接桥:起点是链外的中间版本,终点 <= tail。
        # 实测本仓 CDN 有 7 条,按起点一刀切会在健康的链上误报。
        self.fx.diff("common", "1.4.54", "1.4.100", {COMMON_A: b"mod-a"}, tag="mod")
        for stranded in ("1.4.60", "1.4.70"):
            self.fx.diff(
                "common", stranded, "1.4.100", {COMMON_A: b"mod-a"}, tag="bridge"
            )

        code, summary, _stdout, stderr = self.run_cli()

        self.assertEqual(0, code)
        self.assertTrue(summary["ok"])
        self.assertEqual("1.4.100", summary["tail"])
        self.assertEqual(0, summary["unreachable_edges"])
        self.assertNotIn("[ERR]", stderr)
        self.assertNotIn("chain break", stderr)

    def test_official_only_is_unaffected_by_unreachable_mod_edges(self):
        code, summary, _stdout, stderr = self.run_cli("--official-only", "--apply")

        self.assertEqual(0, code)
        self.assertTrue(summary["ok"])
        self.assertEqual("1.4.54", summary["tail"])
        self.assertEqual(0, summary["unreachable_edges"])
        self.assertEqual([], summary["unreachable_samples"])
        self.assertNotIn("chain break", stderr)
        self.assertNotIn("[ERR]", stderr)
        self.assertEqual(
            b"official-a",
            (self.fx.dest / "production" / "upload" / "aa" / ("1" * 38)).read_bytes(),
        )


class ChainHealthRegressionTest(MaterializeCase):
    def test_intact_chain_reports_no_unreachable_edges(self):
        self.fx.full("common", {COMMON_A: b"base-a", COMMON_B: b"base-b"})
        self.fx.diff("common", "1.4.0", "1.4.54", {COMMON_A: b"official-a"})
        self.fx.diff("common", "1.4.54", "1.4.90", {COMMON_A: b"mod-a"}, tag="mod")
        self.fx.patch("1.4.90", "1.4.100", {COMMON_B: b"mod-b"}, tag="mod")

        code, summary, _stdout, stderr = self.run_cli("--apply")

        self.assertEqual(0, code)
        self.assertTrue(summary["ok"])
        self.assertEqual("1.4.100", summary["tail"])
        self.assertEqual("1.4.100", summary["max_visible_version"])
        self.assertEqual(0, summary["unreachable_edges"])
        self.assertEqual([], summary["chain_issues"])
        self.assertNotIn("[ERR]", stderr)
        self.assertNotIn("[WARN]", stderr)
        common = self.fx.dest / "production" / "upload"
        self.assertEqual(b"mod-a", (common / "aa" / ("1" * 38)).read_bytes())
        self.assertEqual(b"mod-b", (common / "ab" / ("2" * 38)).read_bytes())

    def test_graph_issues_surface_on_stderr_and_in_the_summary(self):
        self.fx.full("common", {COMMON_A: b"base"})
        broken = (
            self.fx.cdn / "archive-common-diff" / "pinball-1.4.0-1.4.1-0-badseq.zip"
        )
        make_zip(broken, {COMMON_A: b"never-applied"})

        code, summary, _stdout, stderr = self.run_cli()

        self.assertEqual(0, code)
        self.assertEqual(1, len(summary["chain_issues"]))
        self.assertIn("badseq", summary["chain_issues"][0])
        self.assertIn("[WARN] chain issue:", stderr)


class ProfileFieldsTest(MaterializeCase):
    def test_new_profile_records_the_materialized_tail_not_the_official_default(self):
        self.fx.full("common", {COMMON_A: b"base"})
        self.fx.diff("common", "1.4.0", "1.4.90", {COMMON_A: b"mod"}, tag="mod")
        profiles = self.fx.root / "fresh" / "profiles.json"

        code, summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        payload = json.loads(profiles.read_text(encoding="utf-8"))
        self.assertEqual("1.4.90", summary["tail"])
        self.assertEqual("1.4.90", payload["profiles"]["cn"]["res_version"])
        self.assertNotEqual(
            "1.4.54", payload["profiles"]["cn"]["res_version"]
        )

    def test_new_profile_records_server_dir_and_existing_cdndata_directory(self):
        self.fx.full("common", {COMMON_A: b"base"})
        cdndata = self.fx.server / "assets" / "cdndata"
        cdndata.mkdir(parents=True)
        profiles = self.fx.root / "fresh" / "profiles.json"

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        self.assertEqual(str(self.fx.server.resolve()), entry["server_dir"])
        self.assertEqual(str(cdndata.resolve()), entry["cdndata"])

    def test_new_profile_omits_cdndata_when_the_directory_does_not_exist(self):
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "fresh" / "profiles.json"

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        self.assertNotIn("cdndata", entry)
        self.assertEqual(str(self.fx.server.resolve()), entry["server_dir"])

    def test_existing_profile_keeps_own_values_but_gains_missing_keys(self):
        self.fx.full("common", {COMMON_A: b"base"})
        (self.fx.server / "assets" / "cdndata").mkdir(parents=True)
        profiles = self.fx.root / "profiles.json"
        profiles.write_text(
            json.dumps(
                {
                    "active": "cn",
                    "profiles": {
                        "cn": {
                            "label": "CN",
                            "store": "old/store",
                            "res_version": "1.4.125",
                            "cdndata": "my/own/cdndata",
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        # 用户已填的一律不动
        self.assertEqual("1.4.125", entry["res_version"])
        self.assertEqual("my/own/cdndata", entry["cdndata"])
        # 缺失的键补上(缺 server_dir 会让下次运行重新丢失 CDN 解析)
        self.assertEqual(str(self.fx.server.resolve()), entry["server_dir"])
        self.assertEqual(
            str((self.fx.dest / "production" / "upload").resolve()), entry["store"]
        )

    def test_existing_profile_without_cdndata_gets_it_filled(self):
        """缺 cdndata 的症状是 GUI 角色列表静默为空,补上它比留着更安全。"""
        self.fx.full("common", {COMMON_A: b"base"})
        cdndata = self.fx.server / "assets" / "cdndata"
        cdndata.mkdir(parents=True)
        profiles = self.fx.root / "profiles.json"
        profiles.write_text(
            json.dumps(
                {
                    "active": "cn",
                    "profiles": {"cn": {"label": "CN", "store": "old/store"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        code, _summary, _stdout, stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        self.assertEqual(str(cdndata.resolve()), entry["cdndata"])
        self.assertEqual(str(self.fx.server.resolve()), entry["server_dir"])
        self.assertIn("filled missing cdndata", stderr)

    def test_existing_profile_keeps_empty_string_untouched_when_dir_absent(self):
        """推导不出真实目录时宁可不写,绝不写空串或猜的路径。"""
        self.fx.full("common", {COMMON_A: b"base"})
        profiles = self.fx.root / "profiles.json"
        profiles.write_text(
            json.dumps(
                {
                    "active": "cn",
                    "profiles": {"cn": {"label": "CN", "store": "old/store"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        code, _summary, _stdout, _stderr = self.run_cli(
            "--apply", "--write-profile", "--profiles", str(profiles)
        )

        self.assertEqual(0, code)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        self.assertNotIn("cdndata", entry)

    def test_write_profile_accepts_a_missing_server_dir_without_writing_keys(self):
        module = self.module()
        profiles = self.fx.root / "gone" / "profiles.json"

        backup = module._write_profile(
            profiles, self.fx.dest / "production" / "upload", "1.4.7", None
        )

        self.assertIsNone(backup)
        entry = json.loads(profiles.read_text(encoding="utf-8"))["profiles"]["cn"]
        self.assertEqual("1.4.7", entry["res_version"])
        self.assertNotIn("server_dir", entry)
        self.assertNotIn("cdndata", entry)


if __name__ == "__main__":
    unittest.main()
