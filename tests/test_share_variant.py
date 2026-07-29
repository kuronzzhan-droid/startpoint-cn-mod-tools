#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分享包双变体构建器的端到端测试(临时 CDN + 合成表,不碰真实 store/.cdn)。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as policy_mod  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
import wf_share_variant as variant_mod  # noqa: E402
from wf_share_variant import VariantError, build  # noqa: E402

ABILITY = "master/ability/ability.orderedmap"
CHARACTER = "master/character/character.orderedmap"
WHITE_TIGER_DSL = policy_mod.DROP_LOGICALS[0]
CUSTOM_ASSET = "character/seris_dragon_king/ui/full_shot_1440_1920_0.png"
EXPECT = {CHARACTER: ["129999", "139999", "149999"]}


def table(rows: dict) -> bytes:
    return quest.build_node(rows)


def write_zip(path: Path, payloads: dict[str, bytes], prefix: str = "production/upload") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for logical, data in payloads.items():
            archive.writestr(f"{prefix}/{quest.hashed_rel(logical)}", data)


OFFICIAL = {
    ABILITY: table({"111001": "官方词条", "10": "白虎官方词条"}),
    CHARACTER: table({"10": "白虎官方行", "111001": "官方角色行"}),
    WHITE_TIGER_DSL: b"official-white-tiger-dsl",
}
LIVE = {
    ABILITY: table({"111001": "平衡总包改过", "10": "白虎重做",
                    "1299991": "赛瑞斯词条"}),
    CHARACTER: table({"10": "白虎重做行", "111001": "官方角色行",
                      "129999": "赛瑞斯", "139999": "史黛拉", "149999": "杰拉德"}),
    WHITE_TIGER_DSL: b"our-modified-white-tiger-dsl",
    CUSTOM_ASSET: b"seris-art",
}


class VariantFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.cdn = base / "cdn"
        self.repo = base / "repo"
        self.out = base / "out"
        (self.repo / "assets" / "asset-patch" / "active").mkdir(parents=True)
        for name in ("archive-common-diff", "archive-medium-diff", "archive-android-diff"):
            (self.cdn / name).mkdir(parents=True)
        write_zip(self.cdn / "archive-common-full" / "pinball-1.4.0-1-abcdef01.zip",
                  OFFICIAL)
        write_zip(self.cdn / "archive-common-diff" / "pinball-1.4.54-1.4.55-1-mod07290101.zip",
                  LIVE)
        self.addCleanup(self._tmp.cleanup)
        # 合成官方表不可能对上真实钉死哈希,测试里关掉这道校验;
        # 基准索引缓存也改到临时目录,别污染 mod-tools/work
        self._orig = (policy_mod.PINNED_BASELINES, policy_mod.CACHE_DIR)
        policy_mod.PINNED_BASELINES = {}
        policy_mod.CACHE_DIR = base / "baseline-cache"
        self.addCleanup(self._restore_globals)

    def _restore_globals(self):
        policy_mod.PINNED_BASELINES, policy_mod.CACHE_DIR = self._orig

    def build(self, **kwargs):
        params = dict(tag="t0729", out_dir=self.out, expect_content_rows=EXPECT,
                      foreign_lineage=True)
        params.update(kwargs)
        return build(self.cdn, self.repo, **params)

    @staticmethod
    def members(pack_dir: Path) -> dict[str, bytes]:
        state: dict[str, bytes] = {}
        for zip_path in sorted(pack_dir.rglob("pinball-*.zip")):
            with zipfile.ZipFile(zip_path) as archive:
                for member in archive.namelist():
                    state[member] = archive.read(member)
        return state

    def member(self, pack_dir: Path, logical: str) -> bytes | None:
        return self.members(pack_dir).get(
            f"production/upload/{quest.hashed_rel(logical)}")


class BuildTest(VariantFixture):
    def test_both_variants_are_produced(self):
        report = self.build(anchor_from="1.4.130")
        self.assertEqual({"full", "content-only"}, set(report["variants"]))
        self.assertEqual({"from": "1.4.130", "to": "1.4.131"}, report["anchor"])
        for variant in ("full", "content-only"):
            pack = self.out / f"wfshare-1.4.130-to-1.4.131-{variant}"
            self.assertTrue((pack / "requires.json").is_file())
            self.assertTrue((pack / "说明.txt").is_file())
            self.assertTrue((pack / "report.json").is_file())

    def test_content_only_reverts_official_rows_and_keeps_content(self):
        self.build(anchor_from="1.4.130")
        pack = self.out / "wfshare-1.4.130-to-1.4.131-content-only"
        ability = quest.parse_node(self.member(pack, ABILITY))
        self.assertEqual("官方词条", ability["111001"])
        self.assertEqual("白虎官方词条", ability["10"])       # 白虎回官方(用户拍板)
        self.assertEqual("赛瑞斯词条", ability["1299991"])    # 内容行保留
        character = quest.parse_node(self.member(pack, CHARACTER))
        self.assertEqual("白虎官方行", character["10"])
        for cid in ("129999", "139999", "149999"):
            self.assertIn(cid, character)

    def test_content_only_drops_white_tiger_dsl_but_full_keeps_it(self):
        self.build(anchor_from="1.4.130")
        content = self.out / "wfshare-1.4.130-to-1.4.131-content-only"
        full = self.out / "wfshare-1.4.130-to-1.4.131-full"
        self.assertIsNone(self.member(content, WHITE_TIGER_DSL))
        self.assertEqual(b"our-modified-white-tiger-dsl",
                         self.member(full, WHITE_TIGER_DSL))

    def test_full_variant_is_byte_identical_to_the_chain(self):
        self.build(anchor_from="1.4.130")
        full = self.out / "wfshare-1.4.130-to-1.4.131-full"
        members = self.members(full)
        self.assertEqual(len(LIVE), len(members))
        for logical, data in LIVE.items():
            self.assertEqual(
                data, members[f"production/upload/{quest.hashed_rel(logical)}"])

    def test_custom_assets_survive_both_variants(self):
        self.build(anchor_from="1.4.130")
        for variant in ("full", "content-only"):
            pack = self.out / f"wfshare-1.4.130-to-1.4.131-{variant}"
            self.assertEqual(b"seris-art", self.member(pack, CUSTOM_ASSET))

    def test_requires_declares_enhancement_flag(self):
        self.build(anchor_from="1.4.130", min_server="modes-20260714",
                   server_features=("rush-mode",), client_patches=("five-in-one-v2",))
        for variant, expected in (("full", True), ("content-only", False)):
            pack = self.out / f"wfshare-1.4.130-to-1.4.131-{variant}"
            payload = json.loads((pack / "requires.json").read_text(encoding="utf-8"))
            self.assertEqual(2, payload["schemaVersion"])
            self.assertEqual(variant, payload["pack"]["variant"])
            self.assertEqual(expected, payload["enhancement"])
            self.assertEqual({"from": "1.4.130", "to": "1.4.131"}, payload["pack"]["anchor"])
            self.assertEqual("modes-20260714", payload["requires"]["minServerVersion"])
            self.assertEqual(["rush-mode"], payload["requires"]["serverFeatures"])
            self.assertEqual(["five-in-one-v2"], payload["requires"]["clientPatches"])
        content = json.loads(
            (self.out / "wfshare-1.4.130-to-1.4.131-content-only" / "requires.json")
            .read_text(encoding="utf-8"))
        detail = content["enhancementDetail"]
        self.assertEqual("1.4.54", detail["officialBaseline"])
        self.assertIn(ABILITY, detail["revertedTables"])
        self.assertIn(WHITE_TIGER_DSL, detail["droppedEntries"])
        # 服务端侧的白虎行不在客户端包里,只能声明给收方
        server_side = detail["serverSideEnhancements"]
        self.assertTrue(server_side)
        self.assertEqual({"assets/character.json", "assets/cdndata/character.json"},
                         {item["file"] for item in server_side})
        readme = (self.out / "wfshare-1.4.130-to-1.4.131-content-only" / "说明.txt")
        self.assertIn("assets/character.json", readme.read_text(encoding="utf-8"))

    def test_requires_flags_server_restart_for_character_tables(self):
        self.build(anchor_from="1.4.130")
        payload = json.loads(
            (self.out / "wfshare-1.4.130-to-1.4.131-full" / "requires.json")
            .read_text(encoding="utf-8"))
        self.assertTrue(payload["requires"]["serverRestart"])
        self.assertTrue(payload["requires"]["restartReasons"])

    def test_readme_names_both_tags_so_receivers_do_not_mix_variants(self):
        self.build(anchor_from="1.4.130")
        readme = (self.out / "wfshare-1.4.130-to-1.4.131-content-only" / "说明.txt")
        text = readme.read_text(encoding="utf-8")
        self.assertIn("t0729", text)
        self.assertIn("t0729co", text)
        self.assertIn("二选一", text)

    def test_variant_zip_tags_differ(self):
        report = self.build(anchor_from="1.4.130")
        self.assertEqual("t0729", report["variants"]["full"]["tag"])
        self.assertEqual("t0729co", report["variants"]["content-only"]["tag"])

    def test_single_variant_selection(self):
        report = self.build(anchor_from="1.4.130", variants=("content-only",))
        self.assertEqual(["content-only"], list(report["variants"]))
        self.assertFalse((self.out / "wfshare-1.4.130-to-1.4.131-full").exists())

    def test_plan_writes_nothing(self):
        report = self.build(anchor_from="1.4.130", dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertFalse(self.out.exists())

    def test_default_anchor_spans_our_own_edge(self):
        report = self.build()
        self.assertEqual({"from": "1.4.54", "to": "1.4.55"}, report["anchor"])


class GuardTest(VariantFixture):
    def test_refuses_existing_edge_without_foreign_lineage(self):
        with self.assertRaises(VariantError) as ctx:
            self.build(anchor_from="1.4.54", anchor_to="1.4.55", foreign_lineage=False)
        self.assertIn("已经存在", str(ctx.exception))

    def test_allows_existing_edge_with_foreign_lineage_but_warns(self):
        report = self.build(anchor_from="1.4.54", anchor_to="1.4.55")
        self.assertTrue(any("外血统" in warning for warning in report["warnings"]))

    def test_refuses_writing_into_cdn(self):
        with self.assertRaises(VariantError) as ctx:
            self.build(anchor_from="1.4.130", out_dir=self.cdn / "share")
        self.assertIn("我方自己的链必须零改动", str(ctx.exception))

    def test_refuses_writing_into_asset_patch(self):
        with self.assertRaises(VariantError):
            self.build(anchor_from="1.4.130",
                       out_dir=self.repo / "assets" / "asset-patch" / "active")

    def test_refuses_backwards_anchor(self):
        with self.assertRaises(VariantError):
            self.build(anchor_from="1.4.130", anchor_to="1.4.129")

    def test_refuses_bad_tag(self):
        with self.assertRaises(VariantError):
            self.build(anchor_from="1.4.130", tag="Share-0729")

    def test_refuses_existing_non_empty_output(self):
        self.build(anchor_from="1.4.130")
        with self.assertRaises(VariantError):
            self.build(anchor_from="1.4.130")
        self.build(anchor_from="1.4.130", force=True)   # --force 可覆盖

    def test_missing_content_row_fails_the_build(self):
        with self.assertRaises(VariantError) as ctx:
            self.build(anchor_from="1.4.130", variants=("content-only",),
                       expect_content_rows={CHARACTER: ["129999", "999999"]})
        self.assertIn("内容行缺失", str(ctx.exception))
        self.assertFalse(
            (self.out / "wfshare-1.4.130-to-1.4.131-content-only").exists())

    def test_content_only_needs_official_baseline(self):
        empty = Path(self._tmp.name) / "cdn-no-official"
        for name in ("archive-common-diff", "archive-medium-diff", "archive-android-diff"):
            (empty / name).mkdir(parents=True)
        write_zip(empty / "archive-common-diff" / "pinball-1.4.54-1.4.55-1-mod07290101.zip",
                  LIVE)
        with self.assertRaises(policy_mod.BaselineUnavailable):
            build(empty, self.repo, tag="t0729", out_dir=self.out,
                  variants=("content-only",), expect_content_rows=EXPECT,
                  foreign_lineage=True, anchor_from="1.4.130")


class SplitTest(VariantFixture):
    def test_parts_split_by_size_cap(self):
        parts = variant_mod.plan_parts(
            [variant_mod.VariantEntry("common", f"aa/{index:038x}", 400_000,
                                      lambda: b"x")
             for index in range(6)],
            1 << 20)
        self.assertGreater(len(parts), 1)
        self.assertEqual([1, 2, 3], [part.seq for part in parts])
        self.assertEqual(6, sum(len(part.entries) for part in parts))


if __name__ == "__main__":
    unittest.main()
