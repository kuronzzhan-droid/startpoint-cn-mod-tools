# -*- coding: utf-8 -*-
"""增量包整合器(wf_pack_consolidate)回归:后写覆盖先写、可见补齐、版本命名、上传链校验。"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_chain_squash as squash  # noqa: E402
import wf_pack_consolidate as pc  # noqa: E402
import wf_quest_lib as quest  # noqa: E402


def make_zip(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, raw in entries.items():
            zf.writestr(name, raw)


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as zf:
        return {info.filename: zf.read(info.filename)
                for info in zf.infolist() if not info.is_dir()}


class Fixture:
    """与 test_chain_squash 同构:官方段 53→54 + mod 链 54→57
    (legacy 双 root/patch 平行边/隐藏孤儿 charpkg/anchored charpkg)。"""

    def __init__(self, root: Path):
        self.cdn = root / "cdn" / "cn"
        self.repo = root / "repo"
        self.out = root / "out"
        self.common = self.cdn / "archive-common-diff"
        self.medium = self.cdn / "archive-medium-diff"
        self.android = self.cdn / "archive-android-diff"
        self.patch_dir = self.repo / "assets" / "asset-patch" / "active"
        for directory in (self.common, self.medium, self.android, self.patch_dir):
            directory.mkdir(parents=True, exist_ok=True)

        make_zip(self.common / "pinball-1.4.53-1.4.54-1-official.zip",
                 {"official.bin": b"OFFICIAL"})
        make_zip(self.common / "pinball-1.4.54-1.4.55-1-mod1.zip",
                 {"a.bin": b"A1", "shared.bin": b"S1"})
        make_zip(self.medium / "pinball-1.4.54-1.4.55-1-mod1.zip",
                 {"m.bin": b"M1"})
        make_zip(self.common / "pinball-1.4.55-1.4.56-1-mod2.zip",
                 {"a.bin": b"A2", "b.bin": b"B-common"})
        make_zip(self.patch_dir / "pinball-1.4.55-1.4.56-1-patchfix.zip",
                 {"b.bin": b"B-patch"})
        make_zip(self.common / "pinball-1.4.55-1.4.56-1-charpkg-ghost.zip",
                 {"c.bin": b"C-hidden"})
        self.anchored_name = (
            "pinball-1.4.56-1.4.57-1-charpkg-fixture-r1-common.zip"
        )
        anchored = self.common / self.anchored_name
        make_zip(anchored, {"d.bin": b"D1"})
        (self.cdn / "character-releases").mkdir(parents=True, exist_ok=True)
        (self.cdn / "character-releases" / "active.json").write_text(json.dumps({
            "schema_version": 1,
            "base_version": "1.4.56",
            "releases": [{
                "from_version": "1.4.56",
                "version": "1.4.57",
                "release_id": "r1",
                "package_id": "fixture",
                "archives": [{
                    "root": "common",
                    "relative_path": "archive-common-diff/" + anchored.name,
                    "size": anchored.stat().st_size,
                    "sha256": "0" * 64,
                }],
            }],
        }), encoding="utf-8")


class ConsolidateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fx = Fixture(self.root)

    def consolidate(self, **kwargs):
        kwargs.setdefault("tag", "mergetest")
        kwargs.setdefault("out_dir", self.fx.out)
        return pc.consolidate(self.fx.cdn, self.fx.repo, **kwargs)


class ScanTest(ConsolidateCase):
    def test_scan_lists_visible_packs_only(self):
        listing = pc.scan_selectable(self.fx.cdn, self.fx.repo)
        names = [p["name"] for p in listing["packs"]]
        self.assertNotIn("pinball-1.4.53-1.4.54-1-official.zip", names)   # 官方段在 base 前
        self.assertNotIn("pinball-1.4.55-1.4.56-1-charpkg-ghost.zip", names)  # 孤儿不可见
        self.assertIn("pinball-1.4.55-1.4.56-1-patchfix.zip", names)
        self.assertIn(self.fx.anchored_name, names)  # anchored 可见
        self.assertEqual(listing["base"], "1.4.54")
        self.assertEqual(listing["tail"], "1.4.57")
        by_name = {p["name"]: p for p in listing["packs"]}
        patch = by_name["pinball-1.4.55-1.4.56-1-patchfix.zip"]
        self.assertEqual((patch["origin"], patch["root"], patch["on_path"]),
                         ("patch", "patch", True))
        hero = by_name[self.fx.anchored_name]
        self.assertEqual(hero["origin"], "anchored")
        # legacy 同名双 root 都在
        self.assertEqual(sum(1 for n in names if n == "pinball-1.4.54-1.4.55-1-mod1.zip"), 2)

    def test_scan_sorts_sequences_numerically_before_name(self):
        for seq in (1, 2, 9, 10, 11):
            make_zip(
                self.fx.common / f"pinball-1.4.54-1.4.55-{seq}-order{seq}.zip",
                {"order.bin": str(seq).encode()},
            )

        listing = pc.scan_selectable(self.fx.cdn, self.fx.repo)
        ordered = [
            pack["seq"] for pack in listing["packs"]
            if pack["name"].endswith(tuple(f"-order{seq}.zip" for seq in (1, 2, 9, 10, 11)))
        ]

        self.assertEqual(ordered, [1, 2, 9, 10, 11])

    def test_upload_sequence_uses_the_shared_safe_integer_limit(self):
        max_seq = 9_007_199_254_740_991
        accepted = self.root / f"pinball-1.4.57-1.4.58-{max_seq}-max.zip"
        rejected = self.root / f"pinball-1.4.57-1.4.58-{max_seq + 1}-overflow.zip"
        make_zip(accepted, {"max.bin": b"max"})
        make_zip(rejected, {"overflow.bin": b"overflow"})

        archive, _frm, _to = pc._parse_upload(accepted, "common")
        self.assertEqual(archive.seq, max_seq)
        with self.assertRaisesRegex(ValueError, "sequence"):
            pc._parse_upload(rejected, "common")


class RangeConsolidateTest(ConsolidateCase):
    def test_later_wins_and_earliest_version_naming(self):
        report = self.consolidate(from_ver="1.4.54", to_ver="1.4.57")
        # 版本号取所选内容最早版本:pinball-1.4.54-1.4.57
        common_out = self.fx.out / "archive-common-diff" / "pinball-1.4.54-1.4.57-1-mergetest.zip"
        medium_out = self.fx.out / "archive-medium-diff" / "pinball-1.4.54-1.4.57-1-mergetest.zip"
        self.assertEqual(read_zip(common_out),
                         {"a.bin": b"A2", "shared.bin": b"S1",
                          "b.bin": b"B-patch", "d.bin": b"D1"})
        self.assertEqual(read_zip(medium_out), {"m.bin": b"M1"})
        stats = report["stats"]
        # 输入 7 entries(mod1 共2+媒1、mod2 共2、patch 1、anchored 1)→ 终态 5,冗余 2
        self.assertEqual((stats["input_zips"], stats["input_entries"],
                          stats["final_entries"], stats["removed_entries"]),
                         (5, 7, 5, 2))
        self.assertTrue((self.fx.out / "report.json").is_file())
        # 与整链重放逐 entry 等价(交叉验证)
        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        tail, edges = squash.find_path(graph, "1.4.54")
        expected, _ = squash.replay(graph, edges)
        merged = {**read_zip(common_out), **read_zip(medium_out)}
        self.assertEqual(set(merged), set(expected))
        # 原包一个都没动
        self.assertTrue((self.fx.common / "pinball-1.4.54-1.4.55-1-mod1.zip").is_file())
        self.assertTrue((self.fx.patch_dir / "pinball-1.4.55-1.4.56-1-patchfix.zip").is_file())
        # 中间版本 + charpkg 警告在位
        self.assertEqual(report["middle_versions"], ["1.4.55", "1.4.56"])
        self.assertTrue(any("中间版本" in w for w in report["warnings"]))
        self.assertTrue(any("charpkg" in w for w in report["warnings"]))

    def test_ids_selection_auto_includes_visible(self):
        ids = ["legacy:archive-common-diff/pinball-1.4.54-1.4.55-1-mod1.zip",
               "legacy:archive-medium-diff/pinball-1.4.54-1.4.55-1-mod1.zip",
               "legacy:archive-common-diff/pinball-1.4.55-1.4.56-1-mod2.zip",
               f"anchored:archive-common-diff/{self.fx.anchored_name}"]
        report = self.consolidate(ids=ids)
        auto = {m["id"] for m in report["auto_included"]}
        self.assertEqual(auto, {"patch:asset-patch/active/pinball-1.4.55-1.4.56-1-patchfix.zip"})
        common_out = self.fx.out / "archive-common-diff" / "pinball-1.4.54-1.4.57-1-mergetest.zip"
        self.assertEqual(read_zip(common_out)["b.bin"], b"B-patch")  # 自动纳入的 patch 生效

    def test_dry_run_writes_nothing(self):
        report = self.consolidate(from_ver="1.4.54", to_ver="1.4.57", dry_run=True)
        self.assertFalse(self.fx.out.exists())
        self.assertEqual({o["name"] for o in report["outputs"]},
                         {"pinball-1.4.54-1.4.57-1-mergetest.zip"})
        self.assertEqual({o["dir"] for o in report["outputs"]},
                         {"archive-common-diff", "archive-medium-diff"})

    def test_subrange_keeps_earliest_selected_version(self):
        report = self.consolidate(from_ver="1.4.55", to_ver="1.4.57", tag="sub")
        self.assertEqual((report["from"], report["to"]), ("1.4.55", "1.4.57"))
        common_out = self.fx.out / "archive-common-diff" / "pinball-1.4.55-1.4.57-1-sub.zip"
        self.assertEqual(read_zip(common_out),
                         {"a.bin": b"A2", "b.bin": b"B-patch", "d.bin": b"D1"})

    def test_nonempty_out_dir_requires_force(self):
        self.fx.out.mkdir(parents=True)
        (self.fx.out / "junk.txt").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "输出目录已存在"):
            self.consolidate(from_ver="1.4.54", to_ver="1.4.57")
        report = self.consolidate(from_ver="1.4.54", to_ver="1.4.57", force=True)
        self.assertFalse((self.fx.out / "junk.txt").exists())
        self.assertTrue(report["outputs"])

    def test_bad_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, "tag"):
            self.consolidate(from_ver="1.4.54", to_ver="1.4.57", tag="Merge07")
        with self.assertRaisesRegex(ValueError, "charpkg"):
            self.consolidate(from_ver="1.4.54", to_ver="1.4.57", tag="xcharpkgx")
        with self.assertRaisesRegex(ValueError, "未知的包 id"):
            self.consolidate(ids=["legacy:archive-common-diff/nope.zip"])
        with self.assertRaisesRegex(ValueError, "官方段"):
            self.consolidate(from_ver="1.4.53", to_ver="1.4.57")
        with self.assertRaisesRegex(ValueError, "没有选中"):
            self.consolidate()


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cdn = self.root / "cdn"          # 不存在也行:纯上传模式不读 CDN
        self.repo = self.root / "repo"
        self.out = self.root / "out"
        self.up = self.root / "uploads"

    def consolidate(self, files, **kwargs):
        kwargs.setdefault("tag", "uptest")
        kwargs.setdefault("out_dir", self.out)
        return pc.consolidate(self.cdn, self.repo, files=files, **kwargs)

    def test_upload_chain_merges_later_wins(self):
        z1 = self.up / "pinball-2.0.0-2.0.1-1-alpha.zip"
        z2 = self.up / "pinball-2.0.1-2.0.2-1-beta.zip"
        make_zip(z1, {"x.bin": b"X1", "y.bin": b"Y1"})
        make_zip(z2, {"x.bin": b"X2"})
        report = self.consolidate([(z1, "common"), (z2, "common")])
        out = self.out / "archive-common-diff" / "pinball-2.0.0-2.0.2-1-uptest.zip"
        self.assertEqual(read_zip(out), {"x.bin": b"X2", "y.bin": b"Y1"})
        self.assertEqual((report["from"], report["to"]), ("2.0.0", "2.0.2"))
        self.assertEqual(report["auto_included"], [])

    def test_upload_root_bucketing(self):
        z1 = self.up / "pinball-2.0.0-2.0.1-1-alpha.zip"
        z2 = self.up / "pinball-2.0.1-2.0.2-1-beta.zip"
        make_zip(z1, {"x.bin": b"X1"})
        make_zip(z2, {"m.bin": b"M1"})
        self.consolidate([(z1, "common"), (z2, "medium")])
        self.assertEqual(
            read_zip(self.out / "archive-common-diff" / "pinball-2.0.0-2.0.2-1-uptest.zip"),
            {"x.bin": b"X1"})
        self.assertEqual(
            read_zip(self.out / "archive-medium-diff" / "pinball-2.0.0-2.0.2-1-uptest.zip"),
            {"m.bin": b"M1"})

    def test_upload_gap_rejected(self):
        z1 = self.up / "pinball-2.0.0-2.0.1-1-alpha.zip"
        z2 = self.up / "pinball-2.0.2-2.0.3-1-beta.zip"
        make_zip(z1, {"x.bin": b"X1"})
        make_zip(z2, {"x.bin": b"X2"})
        with self.assertRaisesRegex(ValueError, "版本链断裂"):
            self.consolidate([(z1, "common"), (z2, "common")])

    def test_upload_off_path_rejected(self):
        z1 = self.up / "pinball-2.0.0-2.0.1-1-alpha.zip"    # 会被更短捷径甩下
        z2 = self.up / "pinball-2.0.0-2.0.2-1-beta.zip"
        z3 = self.up / "pinball-2.0.2-2.0.3-1-gamma.zip"
        for z in (z1, z2, z3):
            make_zip(z, {"x.bin": b"X"})
        with self.assertRaisesRegex(ValueError, "不在.*链路上"):
            self.consolidate([(z1, "common"), (z2, "common"), (z3, "common")])

    def test_upload_validation(self):
        bad_name = self.up / "notpinball.zip"
        make_zip(bad_name, {"x.bin": b"X"})
        with self.assertRaisesRegex(ValueError, "命名"):
            self.consolidate([(bad_name, "common")])
        not_zip = self.up / "pinball-2.0.0-2.0.1-1-alpha.zip"
        not_zip.parent.mkdir(parents=True, exist_ok=True)
        not_zip.write_bytes(b"garbage")
        with self.assertRaisesRegex(ValueError, "有效 zip"):
            self.consolidate([(not_zip, "common")])
        with self.assertRaisesRegex(ValueError, "root"):
            self.consolidate([(not_zip, "server")])
        ok = self.up / "pinball-2.0.0-2.0.1-1-ok.zip"
        make_zip(ok, {"x.bin": b"X"})
        with self.assertRaisesRegex(ValueError, "重复"):
            self.consolidate([(ok, "common"), (ok, "common")])


class SplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.up = self.root / "uploads"

    def test_split_and_single_modes(self):
        # 不可压缩内容:两个 ~1.2MiB entry,上限 2MiB → 拆两包;0 → 单包
        payload = {f"f{i}.bin": os.urandom(1_200_000) for i in range(2)}
        z1 = self.up / "pinball-2.0.0-2.0.1-1-big.zip"
        make_zip(z1, payload)
        report = pc.consolidate(
            self.root / "cdn", self.root / "repo", tag="split",
            files=[(z1, "common")], max_zip_mib=2, out_dir=self.out)
        self.assertEqual([(o["seq"], o["entries"]) for o in report["outputs"]],
                         [(1, 1), (2, 1)])
        merged = {}
        for out in report["outputs"]:
            merged.update(read_zip(Path(out["path"])))
        self.assertEqual({k: len(v) for k, v in merged.items()},
                         {k: len(v) for k, v in payload.items()})

        report2 = pc.consolidate(
            self.root / "cdn", self.root / "repo", tag="single",
            files=[(z1, "common")], max_zip_mib=0, out_dir=self.root / "out2")
        self.assertEqual(len(report2["outputs"]), 1)
        self.assertEqual(report2["outputs"][0]["name"], "pinball-2.0.0-2.0.1-1-single.zip")


class DropListTest(unittest.TestCase):
    """entry 级排除:按逻辑路径(sha1 正向算)或 store 相对路径剔除条目。"""

    KEEP = "character/seris_dragon_king/ui/full_shot_1440_1920_0.png"
    DROP = "battle/action/skill/action/rare4/white_tiger$white_tiger_2.action.dsl.amf3.deflate"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.upload = self.root / "uploads" / "pinball-2.0.0-2.0.1-1-src.zip"
        make_zip(self.upload, {
            f"production/upload/{quest.hashed_rel(self.KEEP)}": b"keep-me",
            f"production/upload/{quest.hashed_rel(self.DROP)}": b"drop-me",
        })

    def consolidate(self, **kwargs):
        return pc.consolidate(self.root / "cdn", self.root / "repo", tag="droptest",
                              files=[(self.upload, "common")], out_dir=self.out, **kwargs)

    def test_drop_by_logical_path(self):
        report = self.consolidate(drop_logicals=[self.DROP])
        self.assertEqual(1, report["stats"]["dropped_entries"])
        self.assertEqual(1, report["stats"]["final_entries"])
        self.assertEqual([], report["drop_not_found"])
        members = read_zip(Path(report["outputs"][0]["path"]))
        self.assertEqual([f"production/upload/{quest.hashed_rel(self.KEEP)}"],
                         list(members))
        self.assertTrue(any("drop 清单" in w for w in report["warnings"]))

    def test_drop_by_store_relative_path(self):
        report = self.consolidate(drop_entries=[quest.hashed_rel(self.DROP)])
        self.assertEqual(1, report["stats"]["dropped_entries"])

    def test_drop_by_full_member_name(self):
        report = self.consolidate(
            drop_entries=[f"production/upload/{quest.hashed_rel(self.DROP)}"])
        self.assertEqual(1, report["stats"]["dropped_entries"])

    def test_unknown_drop_is_reported_not_fatal(self):
        report = self.consolidate(drop_logicals=["master/nope/none.orderedmap"])
        self.assertEqual(0, report["stats"]["dropped_entries"])
        self.assertEqual(["master/nope/none.orderedmap"], report["drop_not_found"])
        self.assertTrue(any("终态里不存在" in w for w in report["warnings"]))

    def test_malformed_drop_entry_rejected(self):
        with self.assertRaises(ValueError):
            self.consolidate(drop_entries=["not-a-hashed-path"])

    def test_dropping_everything_is_rejected(self):
        with self.assertRaises(ValueError):
            self.consolidate(drop_logicals=[self.KEEP, self.DROP])

    def test_plan_previews_drops(self):
        report = self.consolidate(drop_logicals=[self.DROP], dry_run=True)
        self.assertEqual(1, report["stats"]["dropped_entries"])
        self.assertEqual([(1, 1)], [(o["seq"], o["entries"]) for o in report["outputs"]])


class CliTest(ConsolidateCase):
    def run_main(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = pc.main([*argv, "--cdn", str(self.fx.cdn), "--repo-root", str(self.fx.repo)])
        return rc, buf.getvalue()

    def test_list_plan_build(self):
        rc, out = self.run_main("list")
        self.assertEqual(rc, 0)
        self.assertIn("pinball-1.4.54-1.4.55-1-mod1.zip", out)
        rc, out = self.run_main("plan", "--from-ver", "1.4.54", "--to-ver", "1.4.57")
        self.assertEqual(rc, 0)
        self.assertIn("[预览]", out)
        self.assertFalse((pc.WORK_DIR / "clitest").exists())
        rc, out = self.run_main("build", "--from-ver", "1.4.54", "--to-ver", "1.4.57",
                                "--tag", "clitest", "--out", str(self.fx.out))
        self.assertEqual(rc, 0)
        self.assertTrue((self.fx.out / "archive-common-diff"
                         / "pinball-1.4.54-1.4.57-1-clitest.zip").is_file())

    def test_cli_error_returns_2(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = pc.main(["build", "--from-ver", "1.4.53", "--to-ver", "1.4.57",
                          "--cdn", str(self.fx.cdn), "--repo-root", str(self.fx.repo)])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
