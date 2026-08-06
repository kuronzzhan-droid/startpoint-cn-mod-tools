# -*- coding: utf-8 -*-
"""链压缩器(wf_chain_squash)回归:合集等价、全端点桥接、退役不弃客户端。"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_chain_squash as squash  # noqa: E402


class SquashCase(unittest.TestCase):
    """公共夹具:假 CDN + 回执目录隔离到临时目录。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fx = Fixture(Path(self.tmp.name))
        patcher = mock.patch.object(squash, "WORK_DIR", Path(self.tmp.name) / "work")
        patcher.start()
        self.addCleanup(patcher.stop)


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
    """官方段 53→54 + mod 链 54→57(legacy/patch 并行/隐藏孤儿/anchored charpkg)。"""

    def __init__(self, root: Path):
        self.cdn = root / "cdn" / "cn"
        self.repo = root / "repo"
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
        # 同边平行 patch 归档:root 序在 common 之后 → b.bin 以 patch 为准
        make_zip(self.patch_dir / "pinball-1.4.55-1.4.56-1-patchfix.zip",
                 {"b.bin": b"B-patch"})
        # 孤儿 charpkg:文件名隐藏且不在 active.json → 客户端不可见,不得进合集
        make_zip(self.common / "pinball-1.4.55-1.4.56-1-charpkg-ghost.zip",
                 {"c.bin": b"C-hidden"})
        # anchored charpkg:文件名隐藏但 active.json 锚定 → 可见
        self.anchored_name = "pinball-1.4.56-1.4.57-1-charpkg-fixture-r1-common.zip"
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

    def args(self, *extra: str) -> list[str]:
        return [*extra, "--cdn", str(self.cdn), "--repo-root", str(self.repo),
                "--base", "1.4.54", "--tag", "squashtest"]


class GraphSemanticsTest(SquashCase):
    def test_sequence_accepts_max_safe_integer_and_rejects_the_next_value(self):
        frm, to = "1.4.107", "1.4.217"
        max_seq = 9_007_199_254_740_991
        make_zip(
            self.fx.common / f"pinball-{frm}-{to}-{max_seq}-max.zip",
            {"max.bin": b"max"},
        )
        make_zip(
            self.fx.common / f"pinball-{frm}-{to}-{max_seq + 1}-overflow.zip",
            {"overflow.bin": b"overflow"},
        )

        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)

        self.assertEqual(
            [archive.seq for archive in graph.edges[(frm, to)]],
            [max_seq],
        )
        self.assertRegex("\n".join(graph.issues), r"sequence.*9007199254740992")

    def test_invalid_anchored_archives_are_reported_and_skipped(self):
        frm, to = "1.4.107", "1.4.108"
        canonical = f"pinball-{frm}-{to}-1-charpkg-fixture-r1-common.zip"
        invalid_relatives = [
            f"archive-common-diff/pinball-{frm}-{to}-01-charpkg-fixture-r1-common.zip",
            f"archive-common-diff/pinball-{frm}-{to}-9-charpkg-fixture-r1-common.zip",
            f"archive-common-diff/pinball-1.4.106-{to}-1-charpkg-fixture-r1-common.zip",
            f"archive-common-diff/pinball-{frm}-{to}-1-charpkg-fixture-r1-medium.zip",
            f"archive-medium-diff/{canonical}",
            f"archive-common-diff/../archive-medium-diff/{canonical}",
            f"archive-common-diff\\{canonical}",
        ]
        for relative in invalid_relatives:
            make_zip(
                self.fx.cdn / relative.replace("\\", "/"),
                {"invalid.bin": relative.encode()},
            )
        (self.fx.cdn / "character-releases" / "active.json").write_text(
            json.dumps({
                "schema_version": 1,
                "base_version": frm,
                "releases": [{
                    "from_version": frm,
                    "version": to,
                    "release_id": "r1",
                    "package_id": "fixture",
                    "archives": [
                        {"root": "common", "relative_path": relative}
                        for relative in invalid_relatives
                    ],
                }],
            }),
            encoding="utf-8",
        )

        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)

        self.assertNotIn((frm, to), graph.edges)
        issues = "\n".join(graph.issues)
        self.assertGreaterEqual(
            issues.count("anchored archive invalid"),
            len(invalid_relatives),
        )

    def test_replay_uses_root_numeric_sequence_and_stable_fallbacks(self):
        frm, to = "1.4.106", "1.4.107"
        for seq in (1, 2, 9, 10, 11):
            make_zip(
                self.fx.common / f"pinball-{frm}-{to}-{seq}-numeric.zip",
                {"shared-sequence.bin": f"seq-{seq}".encode()},
            )
        make_zip(
            self.fx.common / f"pinball-{frm}-{to}-9-relative-a.zip",
            {"relative-tie.bin": b"relative-a"},
        )
        make_zip(
            self.fx.common / f"pinball-{frm}-{to}-9-relative-z.zip",
            {"relative-tie.bin": b"relative-z"},
        )
        make_zip(
            self.fx.common / f"pinball-{frm}-{to}-11-root-common.zip",
            {"root-tie.bin": b"common-seq-11"},
        )
        make_zip(
            self.fx.medium / f"pinball-{frm}-{to}-1-root-medium.zip",
            {"root-tie.bin": b"medium-seq-1"},
        )

        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        ordered = sorted(graph.edges[(frm, to)], key=squash.VisibleArchive.order_key)
        self.assertEqual(
            [archive.seq for archive in ordered if archive.path.name.endswith("-numeric.zip")],
            [1, 2, 9, 10, 11],
        )
        final, _ = squash.replay(graph, [(frm, to)])
        self.assertEqual(
            read_zip(final["shared-sequence.bin"].zip_path)["shared-sequence.bin"],
            b"seq-11",
        )
        self.assertEqual(
            read_zip(final["relative-tie.bin"].zip_path)["relative-tie.bin"],
            b"relative-z",
        )
        self.assertEqual(
            read_zip(final["root-tie.bin"].zip_path)["root-tie.bin"],
            b"medium-seq-1",
        )

        tied = [
            squash.VisibleArchive(
                "common",
                Path("pinball-1.4.107-1.4.108-9-source.zip"),
                "archive-common-diff/pinball-1.4.107-1.4.108-9-source.zip",
                "legacy:z",
            ),
            squash.VisibleArchive(
                "common",
                Path("pinball-1.4.107-1.4.108-9-source.zip"),
                "archive-common-diff/pinball-1.4.107-1.4.108-9-source.zip",
                "character:a",
            ),
        ]
        self.assertEqual(
            [archive.source for archive in sorted(tied, key=squash.VisibleArchive.order_key)],
            ["character:a", "legacy:z"],
        )

    def test_replay_matches_server_visibility_rules(self):
        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        tail, path_edges = squash.find_path(graph, "1.4.54")
        self.assertEqual(tail, "1.4.57")
        self.assertEqual(len(path_edges), 3)
        final, _ = squash.replay(graph, path_edges)
        self.assertEqual(
            {name: (entry.root) for name, entry in final.items()},
            {"a.bin": "common", "shared.bin": "common",
             "m.bin": "medium", "b.bin": "patch", "d.bin": "common"},
        )
        self.assertNotIn("c.bin", final)       # 隐藏孤儿 charpkg 不可见
        self.assertNotIn("official.bin", final)  # 官方段在 base 之前
        anchored = graph.edges[("1.4.56", "1.4.57")]
        self.assertEqual([(archive.seq, archive.source) for archive in anchored],
                         [(1, "character:r1")])

    def test_bridge_versions_exclude_official_and_tail(self):
        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        self.assertEqual(squash.bridge_versions(graph, "1.4.54", "1.4.57"),
                         ["1.4.54", "1.4.55", "1.4.56"])

    def test_part_rotation_by_size(self):
        entries = {
            f"f{i}.bin": squash.FinalEntry(f"f{i}.bin", "common", Path("x"), 0, 0, 2 << 20)
            for i in range(3)
        }
        parts = squash.plan_parts(entries, 5 << 20)
        self.assertEqual([len(p.entries) for p in parts], [2, 1])
        self.assertEqual([p.seq for p in parts], [1, 2])


class BuildVerifyTest(SquashCase):
    def test_dry_run_leaves_no_changes(self):
        before = sorted(p.name for p in self.fx.common.iterdir())
        self.assertEqual(squash.main(self.fx.args("build", "--dry-run")), 0)
        self.assertEqual(sorted(p.name for p in self.fx.common.iterdir()), before)
        self.assertFalse(list(self.fx.cdn.glob(".squash-staging-*")))

    def test_build_places_parts_and_bridges_then_verifies(self):
        self.assertEqual(squash.main(self.fx.args("build")), 0)
        # 合集主文件:common 桶(含 patch 归并)与 medium 桶
        primary_common = self.fx.common / "pinball-1.4.54-1.4.57-1-squashtest.zip"
        primary_medium = self.fx.medium / "pinball-1.4.54-1.4.57-1-squashtest.zip"
        self.assertEqual(read_zip(primary_common),
                         {"a.bin": b"A2", "shared.bin": b"S1",
                          "b.bin": b"B-patch", "d.bin": b"D1"})
        self.assertEqual(read_zip(primary_medium), {"m.bin": b"M1"})
        # 桥:55/56 各一份别名,53(官方)与 57(tail)没有
        for version in ("1.4.55", "1.4.56"):
            for directory in (self.fx.common, self.fx.medium):
                self.assertTrue(
                    (directory / f"pinball-{version}-1.4.57-1-squashtest.zip").is_file())
        self.assertFalse(list(self.fx.common.glob("pinball-1.4.53-1.4.57-*")))
        self.assertFalse(list(self.fx.common.glob("pinball-1.4.57-*")))
        # 中间版本一跳直达
        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        tail, edges = squash.find_path(graph, "1.4.55")
        self.assertEqual((tail, len(edges)), ("1.4.57", 1))
        self.assertEqual(squash.main(self.fx.args("verify")), 0)

    def test_verify_detects_corrupted_squash(self):
        self.assertEqual(squash.main(self.fx.args("build")), 0)
        primary = self.fx.common / "pinball-1.4.54-1.4.57-1-squashtest.zip"
        entries = read_zip(primary)
        entries["a.bin"] = b"WRONG"
        primary.unlink()
        make_zip(primary, entries)
        self.assertEqual(squash.main(self.fx.args("verify")), 1)

    def test_undo_build_removes_created_files(self):
        before = sorted(p.name for p in self.fx.common.iterdir())
        self.assertEqual(squash.main(self.fx.args("build")), 0)
        receipt = sorted(squash.WORK_DIR.glob("build-squashtest-*.json"))[-1]
        self.addCleanup(receipt.unlink)
        self.assertEqual(squash.main(["undo", "--receipt", str(receipt)]), 0)
        self.assertEqual(sorted(p.name for p in self.fx.common.iterdir()), before)


class RetireTest(SquashCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(squash.main(self.fx.args("build")), 0)

    def test_retire_refuses_without_verified_squash(self):
        primary = self.fx.common / "pinball-1.4.54-1.4.57-1-squashtest.zip"
        entries = read_zip(primary)
        entries["a.bin"] = b"WRONG"
        primary.unlink()
        make_zip(primary, entries)
        self.assertEqual(squash.main(self.fx.args("retire", "--yes")), 2)

    def test_retire_moves_only_redundant_legacy(self):
        self.assertEqual(squash.main(self.fx.args("retire", "--yes")), 0)
        remaining = sorted(p.name for p in self.fx.common.iterdir())
        self.assertIn("pinball-1.4.53-1.4.54-1-official.zip", remaining)   # 官方段不动
        self.assertIn("pinball-1.4.55-1.4.56-1-charpkg-ghost.zip", remaining)  # charpkg 不动
        self.assertIn(self.fx.anchored_name, remaining)
        self.assertIn("pinball-1.4.54-1.4.57-1-squashtest.zip", remaining)
        self.assertNotIn("pinball-1.4.54-1.4.55-1-mod1.zip", remaining)
        self.assertNotIn("pinball-1.4.55-1.4.56-1-mod2.zip", remaining)
        retired = self.fx.cdn / "retired" / "squashtest"
        self.assertTrue(any(retired.rglob("pinball-1.4.54-1.4.55-1-mod1.zip")))
        # asset-patch 平行边不碰
        self.assertTrue((self.fx.patch_dir / "pinball-1.4.55-1.4.56-1-patchfix.zip").is_file())
        # 退役后:中间版本仍一跳可达,verify 仍通过(等价降级为提示)
        graph = squash.build_visible_graph(self.fx.cdn, self.fx.repo)
        for version in ("1.4.54", "1.4.55", "1.4.56"):
            self.assertEqual(squash.find_path(graph, version)[0], "1.4.57")
        self.assertEqual(squash.main(self.fx.args("verify")), 0)

    def test_retire_dry_run_then_undo_round_trip(self):
        before = sorted(p.name for p in self.fx.common.iterdir())
        self.assertEqual(squash.main(self.fx.args("retire")), 0)  # 无 --yes
        self.assertEqual(sorted(p.name for p in self.fx.common.iterdir()), before)
        self.assertEqual(squash.main(self.fx.args("retire", "--yes")), 0)
        receipt = sorted(squash.WORK_DIR.glob("retire-squashtest-*.json"))[-1]
        self.addCleanup(receipt.unlink)
        self.assertEqual(squash.main(["undo", "--receipt", str(receipt)]), 0)
        self.assertEqual(sorted(p.name for p in self.fx.common.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
