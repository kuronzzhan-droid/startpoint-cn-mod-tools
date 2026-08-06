# -*- coding: utf-8 -*-
"""dev Catalog 适配层(wf_dev_catalog)回归:校验移植保真、扫描容错、发射与回填。

校验语义对照上游 origin/dev:
src/content/cdn/{patch-graph,catalog-builder,runtime-manifest}.ts。
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wf_dev_catalog as devcat  # noqa: E402


def archive(
    kind: str = "diff",
    from_version: str | None = "1.4.0",
    to_version: str = "1.4.1",
    layer: str = "common",
    order: int = 1,
    relative_path: str | None = None,
    sha256: str = "a" * 64,
    compressed_bytes: int = 10,
    platform: str = "android",
) -> devcat.ArchiveInput:
    if relative_path is None:
        segment = "full" if kind == "full" else "diff"
        directory = {"common": "common", "quality": "medium", "platform": "android"}[layer]
        relative_path = (
            f"archive-{directory}-{segment}/pinball-"
            + (f"{to_version}" if kind == "full" else f"{from_version}-{to_version}")
            + f"-{order}-abcd1234.zip"
        )
    return devcat.ArchiveInput(
        kind=kind,
        from_version=None if kind == "full" else from_version,
        to_version=to_version,
        platform=platform,
        layer=layer,
        order=order,
        relative_path=relative_path,
        compressed_bytes=compressed_bytes,
        sha256=sha256,
    )


def full_base(version: str = "1.4.0") -> list[devcat.ArchiveInput]:
    return [
        archive(kind="full", to_version=version, layer=layer)
        for layer in ("common", "quality", "platform")
    ]


def diff_edge(from_version: str, to_version: str) -> list[devcat.ArchiveInput]:
    return [
        archive(kind="diff", from_version=from_version, to_version=to_version,
                layer=layer)
        for layer in ("common", "quality", "platform")
    ]


def codes(issues: list[devcat.Issue]) -> set[str]:
    return {issue.code for issue in issues}


class BuildCatalogTest(unittest.TestCase):
    def test_clean_linear_chain(self) -> None:
        archives = full_base() + diff_edge("1.4.0", "1.4.1") + diff_edge("1.4.1", "1.4.2")
        catalog, issues = devcat.build_catalog(archives, 123, "EntityLists/a-android_medium.csv")
        self.assertEqual(issues, [])
        self.assertEqual(catalog["fullBaseVersion"], "1.4.0")
        self.assertEqual(catalog["targetVersion"], "1.4.2")
        # 每个物理边组 × (shortened, fulfill)
        self.assertEqual(len(catalog["edges"]), 6)
        self.assertEqual(catalog["installedBytes"], 123)

    def test_graph_fork_detected(self) -> None:
        archives = (
            full_base()
            + diff_edge("1.4.0", "1.4.1")
            + diff_edge("1.4.0", "1.4.2")  # 同起点第二条出边 = 分叉
        )
        _catalog, issues = devcat.build_catalog(archives, 0, "EntityLists/a-android_medium.csv")
        self.assertIn("GRAPH_FORK", codes(issues))

    def test_multi_in_edges_are_legal(self) -> None:
        """桥接语义:多个旧版本指向同一新版本(多入边)不是分叉。"""
        archives = (
            full_base()
            + diff_edge("1.4.0", "1.4.1")
            + diff_edge("1.4.1", "1.4.3")
            # 桥:1.4.2 是历史孤点,补一条 1.4.2->1.4.3 的入边
            + diff_edge("1.4.2", "1.4.3")
        )
        _catalog, issues = devcat.build_catalog(archives, 0, "EntityLists/a-android_medium.csv")
        self.assertNotIn("GRAPH_FORK", codes(issues))
        # 但 1.4.2 自身从 full base 不可达,dev 会报 MISSING_PATH
        self.assertIn("MISSING_PATH", codes(issues))

    def test_cycle_detected(self) -> None:
        archives = full_base() + diff_edge("1.4.1", "1.4.2")
        cyc = diff_edge("1.4.2", "1.4.1")
        for item in cyc:
            item.from_version, item.to_version = "1.4.2", "1.4.1"
        # 人为放行版本递增检查以构造环:2->1 已经会报 INVALID_VERSION,
        # 这里直接验证 validate_patch_graph 层的环检测。
        edges = [
            devcat.CatalogEdge("1.4.1", "1.4.2", "android", "fulfill",
                               [{"relativePath": "x.zip", "compressedBytes": 1,
                                 "sha256": "a" * 64, "layer": "common", "order": 1}]),
            devcat.CatalogEdge("1.4.2", "1.4.1", "android", "fulfill",
                               [{"relativePath": "y.zip", "compressedBytes": 1,
                                 "sha256": "a" * 64, "layer": "common", "order": 1}]),
        ]
        issues = devcat.validate_patch_graph(edges, "1.4.1")
        self.assertIn("GRAPH_CYCLE", codes(issues))

    def test_duplicate_and_conflicting_edge(self) -> None:
        base = devcat.CatalogEdge("1.4.0", "1.4.1", "android", "fulfill",
                                  [{"relativePath": "x.zip", "compressedBytes": 1,
                                    "sha256": "a" * 64, "layer": "common", "order": 1}])
        duplicate = devcat.CatalogEdge("1.4.0", "1.4.1", "android", "fulfill",
                                       list(base.archives))
        issues = devcat.validate_patch_graph([base, duplicate], "1.4.0")
        self.assertIn("DUPLICATE_EDGE", codes(issues))

        conflicting = devcat.CatalogEdge("1.4.0", "1.4.1", "android", "fulfill",
                                         [{"relativePath": "z.zip", "compressedBytes": 2,
                                           "sha256": "b" * 64, "layer": "common",
                                           "order": 1}])
        issues = devcat.validate_patch_graph([base, conflicting], "1.4.0")
        self.assertIn("CONFLICTING_EDGE", codes(issues))

    def test_missing_layer(self) -> None:
        archives = full_base() + [
            archive(kind="diff", from_version="1.4.0", to_version="1.4.1",
                    layer="common"),
        ]
        _catalog, issues = devcat.build_catalog(archives, 0, "EntityLists/a-android_medium.csv")
        missing = [issue for issue in issues if issue.code == "MISSING_ARCHIVE_LAYER"]
        self.assertEqual(len(missing), 2)  # quality + platform

    def test_invalid_sha_and_order(self) -> None:
        bad = full_base()
        bad[0].sha256 = "XYZ"
        bad[1].order = 0
        _catalog, issues = devcat.build_catalog(bad, 0, "EntityLists/a-android_medium.csv")
        self.assertIn("INVALID_SHA256", codes(issues))
        self.assertIn("INVALID_ARCHIVE_ORDER", codes(issues))

    def test_non_contiguous_order(self) -> None:
        archives = full_base() + [
            archive(kind="diff", from_version="1.4.0", to_version="1.4.1",
                    layer="common", order=1),
            archive(kind="diff", from_version="1.4.0", to_version="1.4.1",
                    layer="common", order=3,
                    relative_path="archive-common-diff/pinball-1.4.0-1.4.1-3-beef00.zip"),
            archive(kind="diff", from_version="1.4.0", to_version="1.4.1",
                    layer="quality"),
            archive(kind="diff", from_version="1.4.0", to_version="1.4.1",
                    layer="platform"),
        ]
        _catalog, issues = devcat.build_catalog(archives, 0, "EntityLists/a-android_medium.csv")
        self.assertIn("NON_CONTIGUOUS_ARCHIVE_ORDER", codes(issues))

    def test_multiple_full_bases_conflict(self) -> None:
        archives = full_base("1.4.0") + full_base("1.4.5") + diff_edge("1.4.0", "1.4.1")
        _catalog, issues = devcat.build_catalog(archives, 0, "EntityLists/a-android_medium.csv")
        self.assertIn("CONFLICTING_EDGE", codes(issues))

    def test_duplicate_archive_path(self) -> None:
        first = archive()
        twin = archive()
        _catalog, issues = devcat.build_catalog(
            full_base() + diff_edge("1.4.0", "1.4.1")[1:] + [first, twin],
            0, "EntityLists/a-android_medium.csv",
        )
        self.assertIn("DUPLICATE_ARCHIVE_PATH", codes(issues))


class EntityListTest(unittest.TestCase):
    def test_parse_rows_and_bytes(self) -> None:
        content = (
            "path,version,size,hash,layer\n"
            "production/upload/00/aa,1.4.0,100,h1,common\n"
            "production/upload/00/bb,1.4.1,50,h2,medium\n"
        )
        rows = devcat.parse_entity_list_rows(content)
        self.assertEqual(len(rows), 2)
        self.assertEqual(devcat.entity_rows_installed_bytes(rows), 150)

    def test_header_only_skipped_when_first(self) -> None:
        content = "production/upload/00/aa,1.4.0,100,h1,common\n"
        self.assertEqual(len(devcat.parse_entity_list_rows(content)), 1)

    def test_invalid_size_rejected(self) -> None:
        with self.assertRaises(ValueError):
            devcat.parse_entity_list_rows("a,1.4.0,notint,h,common\n")

    def test_merge_replaces_and_appends(self) -> None:
        official = [
            ("p/a", "1.4.0", 10, "h1", "common"),
            ("p/b", "1.4.0", 20, "h2", "common"),
        ]
        mods = {
            "p/b": ("p/b", "1.4.60", 25, "h3", "common"),
            "p/c": ("p/c", "1.4.55", 5, "h4", "common"),
        }
        merged = devcat.merge_entity_rows(official, mods)
        self.assertEqual([row[0] for row in merged], ["p/a", "p/b", "p/c"])
        self.assertEqual(merged[1][2], 25)
        self.assertEqual(devcat.entity_rows_installed_bytes(merged), 40)


class ScanAndEmitTest(unittest.TestCase):
    def _make_chain(self, root: Path) -> None:
        """最小合法官方链 + 一个 mod 边(宽松名)。"""
        payload = b"MODDATA-0123456789"
        digest43 = base64.urlsafe_b64encode(
            hashlib.sha256(b"OFFICIAL").digest()
        ).decode().rstrip("=")
        entities = root / "entities"
        entities.mkdir(parents=True)
        (entities / "10939-android_medium.csv").write_text(
            f"production/upload/aa/{'1' * 38},1.4.0,8,{digest43},common\n",
            encoding="utf-8",
        )
        def zip_at(rel: str, members: dict[str, bytes]) -> None:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "w") as bundle:
                for name, raw in members.items():
                    bundle.writestr(name, raw)
        member_official = f"production/upload/aa/{'1' * 38}"
        zip_at("archive-common-full/pinball-1.4.0-1-aa00.zip",
               {member_official: b"OFFICIAL"})
        zip_at("archive-medium-full/pinball-1.4.0-1-aa01.zip", {".empty": b"\n"})
        zip_at("archive-android-full/pinball-1.4.0-1-aa02.zip", {".empty": b"\n"})
        for layer_dir in ("common", "medium", "android"):
            zip_at(f"archive-{layer_dir}-diff/pinball-1.4.0-1.4.54-1-bb00.zip",
                   {".empty": b"\n"})
        # mod 边:宽松名(非 hex 后缀)+ 只有 common 层;
        # 同 zip 携带 medium_upload 成员(tag 应按成员前缀=medium,与 zip 层无关)
        self.mod_member = f"production/upload/cc/{'2' * 38}"
        self.mod_medium_member = f"production/medium_upload/dd/{'3' * 38}"
        zip_at("archive-common-diff/pinball-1.4.54-1.4.55-1-mod0725.zip",
               {self.mod_member: payload, self.mod_medium_member: b"MEDIUMPAYLOAD"})
        self.mod_payload = payload

    def test_scan_tolerates_legacy_names_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._make_chain(root)
            scan = devcat.scan_chain(root, None, digest_mode="skip")
            self.assertIn("DEV_LAYOUT_ENTITYLISTS", codes(scan.issues))
            self.assertIn("DEV_INVALID_ARCHIVE_NAME", codes(scan.issues))
            self.assertEqual(scan.stats["archives_total"], 7)
            self.assertEqual(scan.installed_bytes, 8)

    def test_emit_backfills_rows_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._make_chain(root)
            out = Path(tmp) / "out"
            manifest_path, issues, summary = devcat.emit_dev_catalog(
                root, None, out, digest_mode="cache", allow_issues=True,
            )
            self.assertIsNotNone(manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["baseline"], "cn-1.4.54")
            self.assertEqual(len(manifest["catalogInput"]["archives"]), 7)
            for item in manifest["catalogInput"]["archives"]:
                self.assertRegex(item["sha256"], r"^[a-f0-9]{64}$")
            csv_text = (out / "EntityLists" / "10939-android_medium.csv").read_text(
                encoding="utf-8"
            )
            expected_hash = base64.urlsafe_b64encode(
                hashlib.sha256(self.mod_payload).digest()
            ).decode().rstrip("=")
            self.assertIn(
                f"{self.mod_member},1.4.55,{len(self.mod_payload)},{expected_hash},common",
                csv_text,
            )
            medium_hash = base64.urlsafe_b64encode(
                hashlib.sha256(b"MEDIUMPAYLOAD").digest()
            ).decode().rstrip("=")
            self.assertIn(
                f"{self.mod_medium_member},1.4.55,13,{medium_hash},medium",
                csv_text,
            )
            self.assertEqual(
                manifest["catalogInput"]["installedBytes"],
                8 + len(self.mod_payload) + 13,
            )
            self.assertEqual(
                manifest["entityLists"]["sha256"],
                hashlib.sha256(
                    (out / "EntityLists" / "10939-android_medium.csv").read_bytes()
                ).hexdigest(),
            )

    def test_emit_blocked_without_allow_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._make_chain(root)
            manifest_path, issues, _summary = devcat.emit_dev_catalog(
                root, None, Path(tmp) / "out", digest_mode="skip",
            )
            self.assertIsNone(manifest_path)
            self.assertTrue(issues)

    def test_heal_layers_dry_run_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._make_chain(root)
            planned = devcat.heal_missing_layers(root, None, apply=False)
            self.assertEqual(len(planned), 2)  # mod 边缺 quality + platform
            done = devcat.heal_missing_layers(root, None, apply=True)
            self.assertEqual(planned, done)
            for rel in planned:
                self.assertTrue((root / rel).is_file(), rel)
            with zipfile.ZipFile(root / planned[0]) as bundle:
                self.assertEqual(bundle.namelist(), [".empty"])
            # 补层后重扫:缺层问题消失
            scan = devcat.scan_chain(root, None, digest_mode="skip")
            _catalog, issues = devcat.build_catalog(
                scan.archives, scan.installed_bytes, scan.entity_lists_relative_path,
            )
            self.assertNotIn("MISSING_ARCHIVE_LAYER", codes(issues))


class CanonicalizeTest(unittest.TestCase):
    def test_identical_bridge_deduplicated(self) -> None:
        """charbridge 硬链桥与 charpkg 同边同序同内容 → 去重保一份。"""
        charpkg = archive(order=1, sha256="c" * 64,
                          relative_path="archive-common-diff/pinball-1.4.0-1.4.1-1-charpkg-x.zip")
        bridge = archive(order=1, sha256="c" * 64,
                         relative_path="archive-common-diff/pinball-1.4.0-1.4.1-1-charbridge-x.zip")
        kept, stats = devcat.canonicalize_archives([charpkg, bridge])
        self.assertEqual(len(kept), 1)
        self.assertEqual(stats["deduplicated"], 1)
        catalog_input = full_base() + diff_edge("1.4.0", "1.4.1")[1:] + kept
        _catalog, issues = devcat.build_catalog(
            catalog_input, 0, "EntityLists/a-android_medium.csv",
        )
        self.assertNotIn("DUPLICATE_ARCHIVE_ORDER", codes(issues))

    def test_overlay_conflict_reordered_patch_last(self) -> None:
        """asset-patch 覆盖层与 common-diff 同名不同内容 → patch 排后并重排 1..n。"""
        base = archive(order=1, sha256="d" * 64)
        overlay = archive(order=1, sha256="e" * 64,
                          relative_path="asset-patch/active/pinball-1.4.0-1.4.1-1-x.zip")
        overlay.foreign_root = True
        kept, stats = devcat.canonicalize_archives([overlay, base])
        self.assertEqual([a.order for a in kept], [1, 2])
        self.assertFalse(kept[0].foreign_root)
        self.assertTrue(kept[1].foreign_root)
        self.assertEqual(stats["reordered"], 1)

    def test_skip_digest_mode_never_dedups(self) -> None:
        one = archive(order=1, sha256=devcat.DIGEST_PLACEHOLDER)
        two = archive(order=1, sha256=devcat.DIGEST_PLACEHOLDER,
                      relative_path="archive-common-diff/pinball-1.4.0-1.4.1-1-ff.zip")
        kept, stats = devcat.canonicalize_archives([one, two])
        self.assertEqual(len(kept), 2)
        self.assertEqual(stats["deduplicated"], 0)


class RelocateForeignTest(unittest.TestCase):
    def _make(self, tmp: Path) -> tuple[Path, Path]:
        cdn = tmp / "cn"
        patch = tmp / "asset-patch-active"
        (cdn / "archive-common-diff").mkdir(parents=True)
        patch.mkdir(parents=True)
        # 根内原件(内容 A)与外根覆盖层(同名同边,内容 B)
        with zipfile.ZipFile(
            cdn / "archive-common-diff" / "pinball-1.4.100-1.4.101-1-mod0713.zip", "w"
        ) as bundle:
            bundle.writestr("production/upload/aa/" + "1" * 38, b"CONTENT-A")
        with zipfile.ZipFile(
            patch / "pinball-1.4.100-1.4.101-1-mod0713.zip", "w"
        ) as bundle:
            bundle.writestr("production/upload/aa/" + "1" * 38, b"CONTENT-B")
        return cdn, patch

    def test_dry_run_plans_order_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))
            actions, issues = devcat.relocate_foreign_archives(cdn, patch, apply=False)
            self.assertEqual(issues, [])
            self.assertEqual(1, len(actions))
            self.assertEqual("plan", actions[0]["action"])
            self.assertRegex(
                actions[0]["target"],
                r"^archive-common-diff/pinball-1\.4\.100-1\.4\.101-2-[0-9a-f]{8}\.zip$",
            )
            # dry-run 不落盘
            self.assertEqual(
                1, len(list((cdn / "archive-common-diff").glob("*.zip"))),
            )

    def test_apply_is_idempotent_and_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))
            actions, issues = devcat.relocate_foreign_archives(cdn, patch, apply=True)
            self.assertEqual(issues, [])
            self.assertIn(actions[0]["action"], ("hardlink", "copy"))
            target = cdn / actions[0]["target"]
            source = patch / "pinball-1.4.100-1.4.101-1-mod0713.zip"
            self.assertEqual(source.read_bytes(), target.read_bytes())
            receipt = json.loads(
                (cdn / "dev-catalog" / "relocate-receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(1, len(receipt))
            # 幂等:重跑=exists,不再新增
            again, issues2 = devcat.relocate_foreign_archives(cdn, patch, apply=True)
            self.assertEqual(issues2, [])
            self.assertEqual("exists", again[0]["action"])

    def test_canonical_emit_swaps_foreign_for_in_root_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))
            devcat.relocate_foreign_archives(cdn, patch, apply=True)
            scan = devcat.scan_chain(cdn, patch, digest_mode="cache")
            kept, stats = devcat.canonicalize_archives(scan.archives)
            paths = sorted(a.relative_path for a in kept)
            # 外根原件被根内副本顶掉;原件+副本+根内原件 → 保 2(A 内容 + B 内容副本)
            self.assertEqual(1, stats["deduplicated"])
            self.assertTrue(all(p.startswith("archive-common-diff/") for p in paths))
            self.assertEqual(2, len(paths))
            # 覆盖层语义:B 内容副本 order 在后(后解压胜)
            orders = {a.relative_path: a.order for a in kept}
            copy_path = next(p for p in paths if "-2-" in p)
            self.assertEqual(2, orders[copy_path])


class ExportPackTest(unittest.TestCase):
    def _chain(self, root: Path) -> str:
        def zip_at(rel: str, members: dict[str, bytes]) -> None:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "w") as bundle:
                for name, raw in members.items():
                    bundle.writestr(name, raw)
        entities = root / "entities"
        entities.mkdir(parents=True)
        digest43 = base64.urlsafe_b64encode(hashlib.sha256(b"OFF").digest()).decode().rstrip("=")
        (entities / "10939-android_medium.csv").write_text(
            f"production/upload/aa/{'1' * 38},1.4.0,3,{digest43},common\n", encoding="utf-8",
        )
        zip_at("archive-common-full/pinball-1.4.0-1-aa00.zip",
               {f"production/upload/aa/{'1' * 38}": b"OFF"})
        zip_at("archive-medium-full/pinball-1.4.0-1-aa01.zip", {".empty": b"\n"})
        zip_at("archive-android-full/pinball-1.4.0-1-aa02.zip", {".empty": b"\n"})
        for layer_dir in ("common", "medium", "android"):
            zip_at(f"archive-{layer_dir}-diff/pinball-1.4.0-1.4.54-1-bb00.zip",
                   {".empty": b"\n"})
        member = f"production/upload/cc/{'2' * 38}"
        zip_at("archive-common-diff/pinball-1.4.54-1.4.55-1-mod0726.zip",
               {member: b"MODBYTES"})
        devcat.heal_missing_layers(root, None, apply=True)
        return member

    def test_export_cumulative_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._chain(root)
            pack_dir, stats, _issues = devcat.export_share_pack(
                root, None, Path(tmp) / "share", since="1.4.54",
            )
            self.assertIsNotNone(pack_dir)
            self.assertEqual(stats["edges"], 1)
            self.assertEqual(stats["tail"], "1.4.55")
            # 实包 + 补层后的 2 个占位包
            self.assertEqual(stats["files"], 3)
            self.assertTrue(
                (pack_dir / "archive-common-diff"
                 / "pinball-1.4.54-1.4.55-1-mod0726.zip").is_file()
            )
            # dev 材料在子目录;包根绝不能出现 EntityLists(main 收方雷)
            self.assertTrue((pack_dir / "dev-catalog" / "EntityLists"
                             / "10939-android_medium.csv").is_file())
            self.assertFalse((pack_dir / "EntityLists").exists())
            manifests = list((pack_dir / "dev-catalog").glob("catalog-cn-*.json"))
            self.assertEqual(1, len(manifests))
            readme = (pack_dir / "说明.txt").read_text(encoding="utf-8")
            self.assertIn("1.4.54 -> 1.4.55", readme)
            self.assertIn("main 服务端", readme)
            # 硬链/复制内容一致
            source = root / "archive-common-diff" / "pinball-1.4.54-1.4.55-1-mod0726.zip"
            target = pack_dir / "archive-common-diff" / "pinball-1.4.54-1.4.55-1-mod0726.zip"
            self.assertEqual(source.read_bytes(), target.read_bytes())

    def test_requires_json_pure_cdn_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._chain(root)
            pack_dir, stats, _issues = devcat.export_share_pack(
                root, None, Path(tmp) / "share", since="1.4.54",
            )
            requires = json.loads(
                (pack_dir / "requires.json").read_text(encoding="utf-8")
            )
            self.assertFalse(requires["requires"]["serverRestart"])
            self.assertFalse(stats["serverRestart"])
            # 本通道整 zip 原样搬运,只能是 full 变体,必须诚实声明带增强
            self.assertEqual(2, requires["schemaVersion"])
            self.assertEqual("full", requires["pack"]["variant"])
            self.assertTrue(requires["enhancement"])
            self.assertIn("content-only", requires["enhancementDetail"]["note"])
            readme = (pack_dir / "说明.txt").read_text(encoding="utf-8")
            self.assertIn("纯 CDN 内容包", readme)
            self.assertIn("变体: full", readme)

    def test_requires_auto_detects_character_table(self) -> None:
        import wf_mod_tool as core

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._chain(root)
            digest = core.sha1_path(core.CHARACTER_LOGICAL)
            member = f"production/upload/{digest[:2]}/{digest[2:]}"
            with zipfile.ZipFile(
                root / "archive-common-diff" / "pinball-1.4.55-1.4.56-1-cafe01.zip",
                "w",
            ) as bundle:
                bundle.writestr(member, b"NEWCHAR")
            devcat.heal_missing_layers(root, None, apply=True)
            pack_dir, stats, _issues = devcat.export_share_pack(
                root, None, Path(tmp) / "share", since="1.4.54",
                min_server="modes-20260714", server_features=("rush-mode",),
                client_patches=("seris-pcode-v2",),
            )
            requires = json.loads(
                (pack_dir / "requires.json").read_text(encoding="utf-8")
            )["requires"]
            self.assertTrue(requires["serverRestart"])
            self.assertIn("角色表", requires["restartReasons"][0])
            self.assertEqual("modes-20260714", requires["minServerVersion"])
            self.assertEqual(["rush-mode"], requires["serverFeatures"])
            self.assertEqual(["seris-pcode-v2"], requires["clientPatches"])
            self.assertIn("serverDataNote", requires)
            readme = (pack_dir / "说明.txt").read_text(encoding="utf-8")
            self.assertIn("需重启服务端: 是", readme)
            self.assertIn("rush-mode", readme)

    def test_export_nothing_above_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._chain(root)
            pack_dir, stats, _issues = devcat.export_share_pack(
                root, None, Path(tmp) / "share", since="1.4.55",
            )
            self.assertIsNone(pack_dir)
            self.assertEqual(stats["files"], 0)


class ExportOverlayTest(unittest.TestCase):
    LAYERS = {
        "common": ("common", "upload"),
        "medium": ("quality", "medium_upload"),
        "android": ("platform", "android_upload"),
    }

    def _zip_edge(
        self,
        root: Path,
        from_version: str,
        to_version: str,
        *,
        missing: str | None = None,
        empty: str | None = None,
    ) -> None:
        for index, (directory_layer, (_catalog_layer, member_root)) in enumerate(
            self.LAYERS.items(), start=1,
        ):
            if directory_layer == missing:
                continue
            name = f"pinball-{from_version}-{to_version}-1-{index:02x}aa.zip"
            path = root / f"archive-{directory_layer}-diff" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            digest_path = f"{index:02x}/" + str(index) * 38
            with zipfile.ZipFile(path, "w") as bundle:
                if directory_layer != empty:
                    bundle.writestr(
                        f"production/{member_root}/{digest_path}",
                        f"{from_version}->{to_version}:{directory_layer}".encode(),
                    )

    def _skip_chain(self, root: Path) -> None:
        self._zip_edge(root, "1.4.54", "1.4.55")
        self._zip_edge(root, "1.4.55", "1.4.58")

    def _outer_manifests(self, batch: Path) -> list[tuple[Path, dict]]:
        result = []
        for outer in sorted(batch.glob("*.zip")):
            with zipfile.ZipFile(outer) as bundle:
                result.append((outer, json.loads(bundle.read("patch-manifest.json"))))
        return result

    def test_skip_chain_splits_by_target_with_exact_overlay_payloads(self) -> None:
        """Catches collapsing a legal skip chain or emitting incomplete manifest bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._skip_chain(root)
            batch, stats, issues = devcat.export_patch_overlays(
                root, None, Path(tmp) / "out", from_version="1.4.54",
            )

            self.assertEqual(issues, [])
            self.assertEqual(stats["packages"], 2)
            packages = self._outer_manifests(batch)
            self.assertEqual([m["targetVersion"] for _p, m in packages], ["1.4.55", "1.4.58"])
            for outer, manifest in packages:
                self.assertEqual(manifest["schema"], 1)
                self.assertEqual(manifest["compatibleClient"], "CN 1.8.1")
                self.assertNotIn("baseVersion", manifest)
                self.assertEqual(len(manifest["archives"]), 3)
                with zipfile.ZipFile(outer) as bundle:
                    names = bundle.namelist()
                    self.assertEqual(names[-1], "patch-manifest.json")
                    self.assertIn("README.md", names)
                    self.assertIn("requires.json", names)
                    self.assertFalse(any(name.startswith(manifest["targetVersion"] + "/") for name in names))
                    for item in manifest["archives"]:
                        self.assertIn(item["layer"], ("common", "medium", "android"))
                        self.assertEqual(item["order"], 1)
                        self.assertRegex(
                            Path(item["relativePath"]).name,
                            r"^pinball-\d+\.\d+\.\d+-\d+\.\d+\.\d+-1-[a-f0-9]+\.zip$",
                        )
                        raw = bundle.read(item["relativePath"])
                        self.assertEqual(item["bytes"], len(raw))
                        self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
                with zipfile.ZipFile(outer) as bundle:
                    readme = bundle.read("README.md").decode("utf-8")
                self.assertIn("Overlay schema 1", readme)
                self.assertIn(f"CDN_DIR/patches/{manifest['targetVersion']}/", readme)
                self.assertIn("npm run start:cn", readme)
                self.assertIn("Content Sync", readme)
                self.assertIn("does not replace patch-manifest.json", readme)
                self.assertIn("do not merge", readme.lower())

    def test_unreachable_edge_is_rejected_without_final_artifacts(self) -> None:
        """Catches exporting a disconnected target that explicit --from-ver cannot reach."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            self._zip_edge(root, "1.4.56", "1.4.58")
            out = Path(tmp) / "out"
            with self.assertRaises(devcat.OverlayExportError) as caught:
                devcat.export_patch_overlays(
                    root, None, out, from_version="1.4.54",
                )
            self.assertEqual(caught.exception.code, "MISSING_PATH")
            self.assertEqual(caught.exception.category, "graph")
            self.assertEqual(caught.exception.target_version, "1.4.58")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_traversal_path_is_rejected_with_stable_context(self) -> None:
        """Catches accepting a catalog path that escapes the package root."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            root.mkdir()
            (base / "escape.zip").write_bytes(b"not-empty")
            unsafe = archive(
                from_version="1.4.54",
                to_version="1.4.55",
                relative_path="../escape.zip",
                compressed_bytes=9,
                sha256=hashlib.sha256(b"not-empty").hexdigest(),
            )
            scan = devcat.ScanResult(
                archives=[unsafe], installed_bytes=0,
                entity_lists_relative_path="EntityLists/x-android_medium.csv",
                entity_rows=[], entity_dir_name=None, issues=[], stats={},
            )
            out = base / "out"
            with mock.patch.object(devcat, "scan_chain", return_value=scan):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(
                        root, None, out, from_version="1.4.54",
                    )
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_PATH_INVALID")
            self.assertEqual(caught.exception.category, "archive")
            self.assertEqual(caught.exception.target_version, "1.4.55")
            self.assertEqual(caught.exception.relative_path, "../escape.zip")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_missing_layer_is_rejected_without_final_artifacts(self) -> None:
        """Catches publishing an edge without common, medium, and android archives."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55", missing="android")
            out = Path(tmp) / "out"
            with self.assertRaises(devcat.OverlayExportError) as caught:
                devcat.export_patch_overlays(
                    root, None, out, from_version="1.4.54",
                )
            self.assertEqual(caught.exception.code, "MISSING_ARCHIVE_LAYER")
            self.assertEqual(caught.exception.target_version, "1.4.55")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_manifest_publication_observes_complete_staging_and_outer_order(self) -> None:
        """Catches using the manifest completion marker before package bytes are durable."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            original = devcat._publish_overlay_manifest
            observed = []

            def checking(package_root: Path, manifest: dict) -> Path:
                self.assertTrue((package_root / "README.md").is_file())
                self.assertTrue((package_root / "requires.json").is_file())
                self.assertFalse((package_root / "patch-manifest.json").exists())
                for item in manifest["archives"]:
                    archive_path = package_root / item["relativePath"]
                    self.assertTrue(archive_path.is_file())
                    self.assertEqual(archive_path.stat().st_size, item["bytes"])
                    self.assertEqual(devcat.file_sha256(archive_path), item["sha256"])
                observed.append(manifest["targetVersion"])
                return original(package_root, manifest)

            with mock.patch.object(devcat, "_publish_overlay_manifest", side_effect=checking):
                batch, _stats, _issues = devcat.export_patch_overlays(
                    root, None, Path(tmp) / "out", from_version="1.4.54",
                )
            self.assertEqual(observed, ["1.4.55"])
            outer = next(batch.glob("*.zip"))
            with zipfile.ZipFile(outer) as bundle:
                self.assertEqual(bundle.namelist()[-1], "patch-manifest.json")

    def test_consolidate_is_opt_in_and_emits_one_true_edge(self) -> None:
        """Catches bundling historical edges together instead of consolidating their bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._skip_chain(root)
            batch, stats, _issues = devcat.export_patch_overlays(
                root, None, Path(tmp) / "out", from_version="1.4.54",
                base_version="1.4.0", consolidate=True,
            )
            self.assertEqual(stats["packages"], 1)
            [(outer, manifest)] = self._outer_manifests(batch)
            self.assertEqual(manifest["baseVersion"], "1.4.0")
            self.assertEqual(manifest["targetVersion"], "1.4.58")
            self.assertTrue(manifest["archives"])
            for item in manifest["archives"]:
                self.assertRegex(
                    Path(item["relativePath"]).name,
                    r"^pinball-1\.4\.54-1\.4\.58-\d+-[a-f0-9]+\.zip$",
                )
            with zipfile.ZipFile(outer) as bundle:
                self.assertFalse(any("1.4.54-1.4.55" in name for name in bundle.namelist()))
                self.assertFalse(any("1.4.55-1.4.58" in name for name in bundle.namelist()))

    def test_export_overlay_cli_requires_explicit_from_version(self) -> None:
        """Catches silently guessing the installed client start version."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            devcat.main(["--cdn-root", ".", "export-overlay"])
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--from-ver", stderr.getvalue())

    def test_foreign_root_archive_is_snapshotted_and_drives_dependencies(self) -> None:
        """Catches resolving asset-patch/active paths beneath cn or missing dependencies."""
        import wf_mod_tool as core

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            active = base / "server" / "assets" / "asset-patch" / "active"
            self._zip_edge(root, "1.4.54", "1.4.55")
            common = next((root / "archive-common-diff").glob("*.zip"))
            active.mkdir(parents=True)
            foreign = active / common.name
            common.replace(foreign)
            digest = core.sha1_path(core.CHARACTER_LOGICAL)
            with zipfile.ZipFile(foreign, "w") as bundle:
                bundle.writestr(f"production/upload/{digest[:2]}/{digest[2:]}", b"FOREIGN")

            batch, _stats, _issues = devcat.export_patch_overlays(
                root, active, base / "share", from_version="1.4.54",
            )
            outer = next(batch.glob("*.zip"))
            with zipfile.ZipFile(outer) as bundle:
                requires = json.loads(bundle.read("requires.json"))
                manifest = json.loads(bundle.read("patch-manifest.json"))
                self.assertTrue(requires["requires"]["serverRestart"])
                common_item = next(item for item in manifest["archives"] if item["layer"] == "common")
                self.assertEqual(
                    hashlib.sha256(bundle.read(common_item["relativePath"])).hexdigest(),
                    hashlib.sha256(foreign.read_bytes()).hexdigest(),
                )

    def test_source_swap_between_validation_and_open_is_rejected(self) -> None:
        """Catches path-based copying after validation instead of pinning an opened identity."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            source = next((root / "archive-common-diff").glob("*.zip"))
            replacement = base / "replacement.zip"
            with zipfile.ZipFile(replacement, "w") as bundle:
                bundle.writestr("production/upload/ff/" + "f" * 38, b"SWAPPED")
            original_open = devcat.os.open
            swapped = False

            def swap_then_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if not swapped and Path(path) == source:
                    replacement.replace(source)
                    swapped = True
                return original_open(path, flags, *args, **kwargs)

            out = base / "share"
            with mock.patch.object(devcat.os, "open", side_effect=swap_then_open):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(
                        root, None, out, from_version="1.4.54",
                    )
            self.assertTrue(swapped)
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_SYMLINK")
            self.assertEqual(caught.exception.relative_path, source.relative_to(root).as_posix())
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_outer_zip_rejects_unexpected_staged_file(self) -> None:
        """Catches rglob-based outer ZIP creation that packages undeclared files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            original = devcat._publish_overlay_manifest

            def inject(package_root: Path, manifest: dict) -> Path:
                result = original(package_root, manifest)
                (package_root / "unexpected.txt").write_text("unexpected", encoding="utf-8")
                return result

            out = base / "share"
            with mock.patch.object(devcat, "_publish_overlay_manifest", side_effect=inject):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(root, None, out, from_version="1.4.54")
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_FILE_TYPE")
            self.assertEqual(caught.exception.relative_path, "unexpected.txt")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_cleanup_failure_prevents_final_batch_publication(self) -> None:
        """Catches ignored private-work cleanup before the atomic publish point."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            out = base / "share"
            with mock.patch.object(
                devcat, "_remove_overlay_work", side_effect=OSError("cleanup denied"),
                create=True,
            ):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(root, None, out, from_version="1.4.54")
            self.assertEqual(caught.exception.code, "PATCH_OUTPUT_CLEANUP_FAILED")
            self.assertFalse(any(path.name.startswith("wf-overlay-") for path in out.iterdir()))

    def test_output_inside_live_roots_is_rejected_before_write(self) -> None:
        """Catches treating the live cn, patches, or asset-patch trees as export scratch."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            patches = base / "patches"
            active = base / "server" / "assets" / "asset-patch" / "active"
            self._zip_edge(root, "1.4.54", "1.4.55")
            patches.mkdir()
            active.mkdir(parents=True)
            for protected in (root, root / "exports", patches, patches / "exports", active):
                with self.subTest(protected=protected):
                    with self.assertRaises(devcat.OverlayExportError) as caught:
                        devcat.export_patch_overlays(
                            root, active, protected, from_version="1.4.54",
                        )
                    self.assertEqual(caught.exception.code, "PATCH_OUTPUT_PROTECTED")
            allowed = base / "share"
            batch, _stats, _issues = devcat.export_patch_overlays(
                root, active, allowed, from_version="1.4.54",
            )
            self.assertTrue(batch.is_dir())

    def test_overlay_path_grammar_rejects_space_and_nested_archive(self) -> None:
        """Catches paths outside upstream visible-ASCII/direct-layer grammar."""
        self.assertFalse(devcat._overlay_path_is_safe(
            "archive-common-diff/pinball-1.4.54-1.4.55-1-aa aa.zip"
        ))
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            nested = (
                package / "archive-common-diff" / "nested"
                / "pinball-1.4.54-1.4.55-1-aabb.zip"
            )
            nested.parent.mkdir(parents=True)
            with zipfile.ZipFile(nested, "w"):
                pass
            manifest = {
                "schema": 1, "targetVersion": "1.4.55", "compatibleClient": "CN 1.8.1",
                "archives": [{
                    "relativePath": nested.relative_to(package).as_posix(),
                    "layer": "common", "order": 1, "bytes": nested.stat().st_size,
                    "sha256": hashlib.sha256(nested.read_bytes()).hexdigest(),
                }],
            }
            with self.assertRaises(devcat.OverlayExportError) as caught:
                devcat._validate_staged_overlay(package, manifest)
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_PATH_INVALID")

    def test_safe_integer_boundaries_reject_version_order_and_bytes(self) -> None:
        """Catches Python integers exceeding the upstream JavaScript safe-integer contract."""
        huge = 2**53
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            root.mkdir()
            with self.assertRaises(devcat.OverlayExportError) as version_error:
                devcat.export_patch_overlays(
                    root, None, Path(tmp) / "share",
                    from_version=f"{huge}.4.54",
                )
            self.assertEqual(version_error.exception.code, "PATCH_TARGET_VERSION_INVALID")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            common = next((root / "archive-common-diff").glob("*.zip"))
            common.rename(common.with_name(
                f"pinball-1.4.54-1.4.55-{huge}-aabb.zip"
            ))
            with self.assertRaises(devcat.OverlayExportError) as order_error:
                devcat.export_patch_overlays(
                    root, None, Path(tmp) / "share", from_version="1.4.54",
                )
            self.assertEqual(order_error.exception.code, "PATCH_ARCHIVE_ORDER_INVALID")

        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            path = package / "archive-common-diff" / "pinball-1.4.54-1.4.55-1-aabb.zip"
            path.parent.mkdir(parents=True)
            with zipfile.ZipFile(path, "w"):
                pass
            manifest = {
                "schema": 1, "targetVersion": "1.4.55", "compatibleClient": "CN 1.8.1",
                "archives": [{
                    "relativePath": path.relative_to(package).as_posix(),
                    "layer": "common", "order": 1, "bytes": huge,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }],
            }
            with self.assertRaises(devcat.OverlayExportError) as bytes_error:
                devcat._validate_staged_overlay(package, manifest)
            self.assertEqual(bytes_error.exception.code, "PATCH_ARCHIVE_SIZE_INVALID")

    def test_publication_oserrors_are_normalized_and_leave_no_batch(self) -> None:
        """Catches raw OSError leakage at manifest, outer ZIP, and batch publication points."""
        cases = (
            ("manifest", "PATCH_MANIFEST_WRITE_FAILED"),
            ("outer", "PATCH_OUTER_ZIP_WRITE_FAILED"),
            ("batch", "PATCH_BATCH_PUBLISH_FAILED"),
        )
        for boundary, expected_code in cases:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "cn"
                self._zip_edge(root, "1.4.54", "1.4.55")
                out = base / "share"
                original_replace = devcat.os.replace

                def fail_boundary(source, target):
                    target_path = Path(target)
                    matched = (
                        (boundary == "manifest" and target_path.name == "patch-manifest.json")
                        or (boundary == "outer" and target_path.suffix == ".zip")
                        or (boundary == "batch" and target_path.name.startswith("wf-overlay-"))
                    )
                    if matched:
                        raise OSError(f"{boundary} denied")
                    return original_replace(source, target)

                with mock.patch.object(devcat.os, "replace", side_effect=fail_boundary):
                    with self.assertRaises(devcat.OverlayExportError) as caught:
                        devcat.export_patch_overlays(
                            root, None, out, from_version="1.4.54",
                        )
                self.assertEqual(caught.exception.code, expected_code)
                self.assertEqual(caught.exception.target_version, "1.4.55")
                self.assertFalse(any(
                    path.name.startswith("wf-overlay-") for path in out.iterdir()
                ))

    def test_consolidation_missing_layer_uses_zero_member_zip(self) -> None:
        """Catches adding a synthetic .empty content entry during consolidation."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55", empty="android")
            self._zip_edge(root, "1.4.55", "1.4.58", empty="android")
            batch, _stats, _issues = devcat.export_patch_overlays(
                root, None, base / "share", from_version="1.4.54", consolidate=True,
            )
            outer = next(batch.glob("*.zip"))
            with zipfile.ZipFile(outer) as bundle:
                manifest = json.loads(bundle.read("patch-manifest.json"))
                android = next(item for item in manifest["archives"] if item["layer"] == "android")
                with zipfile.ZipFile(io.BytesIO(bundle.read(android["relativePath"]))) as inner:
                    self.assertEqual(inner.namelist(), [])

    def test_source_open_uses_safe_flags_ctime_and_shared_reparse_check(self) -> None:
        """Catches blocking/following source opens and identities that omit ctime/reparse."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            source = next((root / "archive-common-diff").glob("*.zip"))
            original_open = devcat.os.open
            observed_flags = None

            def inspect_flags(path, flags, *args, **kwargs):
                nonlocal observed_flags
                if Path(path) == source:
                    observed_flags = flags
                return original_open(path, flags, *args, **kwargs)

            with mock.patch.object(devcat.os, "open", side_effect=inspect_flags):
                devcat.export_patch_overlays(
                    root, None, base / "share", from_version="1.4.54",
                )
            self.assertIsNotNone(observed_flags)
            for flag_name in ("O_NOFOLLOW", "O_NONBLOCK"):
                flag = getattr(devcat.os, flag_name, 0)
                if flag:
                    self.assertEqual(observed_flags & flag, flag)

        fake_stat = mock.Mock(
            st_dev=1, st_ino=2, st_size=3, st_mtime_ns=4, st_ctime_ns=5,
            st_mode=devcat.stat.S_IFREG,
            st_file_attributes=0x400,
        )
        self.assertEqual(devcat._overlay_file_identity(fake_stat), (1, 2, 3, 4, 5))
        self.assertTrue(devcat._is_link_or_reparse(fake_stat))

    def test_nonregular_swap_after_validation_is_rejected_before_open(self) -> None:
        """Catches opening a directory/device swapped in after path validation."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            source = next((root / "archive-common-diff").glob("*.zip"))
            original_validate = devcat._validated_overlay_file
            original_open = devcat.os.open
            swapped = opened = False

            def swap_after_validation(package_root, relative_path, target_version):
                nonlocal swapped
                path = original_validate(package_root, relative_path, target_version)
                if not swapped and path == source:
                    path.unlink()
                    path.mkdir()
                    swapped = True
                return path

            def observe_open(path, flags, *args, **kwargs):
                nonlocal opened
                if swapped and Path(path) == source:
                    opened = True
                return original_open(path, flags, *args, **kwargs)

            out = base / "share"
            with (
                mock.patch.object(
                    devcat, "_validated_overlay_file", side_effect=swap_after_validation,
                ),
                mock.patch.object(devcat.os, "open", side_effect=observe_open),
            ):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(root, None, out, from_version="1.4.54")
            self.assertTrue(swapped)
            self.assertFalse(opened)
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_FILE_TYPE")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_private_snapshot_swap_during_staging_is_rejected(self) -> None:
        """Catches path-based staging that accepts a replacement private snapshot."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            replacement = base / "replacement.zip"
            with zipfile.ZipFile(replacement, "w") as bundle:
                bundle.writestr("production/upload/ff/" + "f" * 38, b"REPLACED")
            original_open = devcat.os.open
            swapped = False

            def swap_then_open(path, flags, *args, **kwargs):
                nonlocal swapped
                source_path = Path(path)
                is_read_only = flags & (os.O_WRONLY | os.O_RDWR) == 0
                if not swapped and is_read_only and "sources" in source_path.parts:
                    replacement.replace(source_path)
                    swapped = True
                return original_open(path, flags, *args, **kwargs)

            out = base / "share"
            with mock.patch.object(devcat.os, "open", side_effect=swap_then_open):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(root, None, out, from_version="1.4.54")
            self.assertTrue(swapped)
            self.assertIn(caught.exception.code, {
                "PATCH_ARCHIVE_HASH_MISMATCH", "PATCH_ARCHIVE_SYMLINK",
            })
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_outer_stream_rejects_swapped_readme_and_archive(self) -> None:
        """Catches path-based ZipFile.write after staged allowlist validation."""
        for kind in ("README", "archive"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "cn"
                self._zip_edge(root, "1.4.54", "1.4.55")
                original_allowlist = devcat._overlay_package_files
                replacement = base / "replacement.zip"
                with zipfile.ZipFile(replacement, "w") as bundle:
                    bundle.writestr("production/upload/ff/" + "f" * 38, b"REPLACED")

                def swap_after_allowlist(package_root: Path, manifest: dict):
                    result = original_allowlist(package_root, manifest)
                    if kind == "README":
                        (package_root / "README.md").write_text("swapped", encoding="utf-8")
                    else:
                        target = package_root / manifest["archives"][0]["relativePath"]
                        replacement.replace(target)
                    return result

                out = base / "share"
                with mock.patch.object(
                    devcat, "_overlay_package_files", side_effect=swap_after_allowlist,
                ):
                    with self.assertRaises(devcat.OverlayExportError):
                        devcat.export_patch_overlays(
                            root, None, out, from_version="1.4.54",
                        )
                self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_candidate_file_and_root_swaps_are_rejected(self) -> None:
        """Catches candidate changes between enumeration and the final directory rename."""
        for kind in ("file", "root"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "cn"
                self._zip_edge(root, "1.4.54", "1.4.55")
                original_validate = devcat._validate_overlay_candidate

                def swap_candidate(candidate: Path, expected_names, target_version):
                    result = original_validate(candidate, expected_names, target_version)
                    if kind == "file":
                        next(candidate.glob("*.zip")).write_bytes(b"corrupt")
                    else:
                        moved = candidate.with_name(candidate.name + ".old")
                        candidate.replace(moved)
                        candidate.mkdir()
                        devcat.shutil.rmtree(moved)
                    return result

                out = base / "share"
                with mock.patch.object(
                    devcat, "_validate_overlay_candidate", side_effect=swap_candidate,
                ):
                    with self.assertRaises(devcat.OverlayExportError):
                        devcat.export_patch_overlays(
                            root, None, out, from_version="1.4.54",
                        )
                self.assertFalse(any(
                    path.name.startswith("wf-overlay-") for path in out.iterdir()
                ))

    def test_consolidator_outside_report_path_is_rejected(self) -> None:
        """Catches trusting a consolidator-reported file outside its private work root."""
        import wf_pack_consolidate as packcon

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._skip_chain(root)
            outside = base / "pinball-1.4.54-1.4.58-1-aabb.zip"
            with zipfile.ZipFile(outside, "w") as bundle:
                bundle.writestr("production/upload/ff/" + "f" * 38, b"OUTSIDE")
            report = {
                "from": "1.4.54", "to": "1.4.58",
                "outputs": [{"root": "common", "path": str(outside)}],
            }
            out = base / "share"
            with mock.patch.object(packcon, "consolidate", return_value=report):
                with self.assertRaises(devcat.OverlayExportError) as caught:
                    devcat.export_patch_overlays(
                        root, None, out, from_version="1.4.54", consolidate=True,
                    )
            self.assertEqual(caught.exception.code, "PATCH_ARCHIVE_PATH_INVALID")
            self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_staging_io_faults_are_normalized(self) -> None:
        """Catches raw snapshot/package/metadata OSError leakage."""
        for boundary in ("snapshot", "copy", "metadata"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "cn"
                self._zip_edge(root, "1.4.54", "1.4.55")
                out = base / "share"
                stack = contextlib.ExitStack()
                with stack:
                    if boundary == "snapshot":
                        stack.enter_context(mock.patch.object(
                            devcat, "_secure_private_leaf",
                            side_effect=OSError("snapshot leaf denied"),
                        ))
                    elif boundary == "copy":
                        stack.enter_context(mock.patch.object(
                            devcat, "_guarded_copy_file", create=True,
                            side_effect=OSError("copy denied"),
                        ))
                    else:
                        original_write_text = Path.write_text

                        def fail_metadata(path, *args, **kwargs):
                            if path.name == "README.md":
                                raise OSError("metadata denied")
                            return original_write_text(path, *args, **kwargs)

                        stack.enter_context(mock.patch.object(
                            Path, "write_text", autospec=True, side_effect=fail_metadata,
                        ))
                    caught = None
                    try:
                        devcat.export_patch_overlays(
                            root, None, out, from_version="1.4.54",
                        )
                    except Exception as exc:
                        caught = exc
                self.assertIsInstance(caught, devcat.OverlayExportError)
                self.assertEqual(caught.code, "PATCH_STAGING_IO_FAILED")
                self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)

    def test_base_version_cannot_self_depend_on_generated_target(self) -> None:
        """Catches a manifest whose optional content dependency points to itself."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._skip_chain(root)
            out = base / "share"
            with self.assertRaises(devcat.OverlayExportError) as caught:
                devcat.export_patch_overlays(
                    root, None, out, from_version="1.4.54", base_version="1.4.55",
                )
            self.assertEqual(caught.exception.code, "PATCH_BASE_VERSION_CYCLE")
            self.assertEqual(caught.exception.target_version, "1.4.55")
            self.assertFalse(out.exists())

    def test_outer_verification_streams_inner_archives(self) -> None:
        """Catches whole-buffer ZipFile.read calls for manifest-declared inner ZIPs."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "cn"
            self._zip_edge(root, "1.4.54", "1.4.55")
            original_read = zipfile.ZipFile.read

            def reject_inner_read(bundle, name, *args, **kwargs):
                if isinstance(name, str) and name.startswith("archive-"):
                    raise AssertionError("inner ZIP verification must stream")
                return original_read(bundle, name, *args, **kwargs)

            with mock.patch.object(
                zipfile.ZipFile, "read", autospec=True, side_effect=reject_inner_read,
            ):
                try:
                    batch, _stats, _issues = devcat.export_patch_overlays(
                        root, None, base / "share", from_version="1.4.54",
                    )
                except Exception as exc:  # expected to stay empty after GREEN
                    self.fail(f"outer verification buffered an inner ZIP: {exc}")
            self.assertTrue(batch.is_dir())

    def test_private_leaf_creation_rejects_replaced_parent_without_escape(self) -> None:
        """Catches snapshot/package leaf creation through a replaced parent directory."""
        for boundary in ("snapshot", "package"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "cn"
                self._zip_edge(root, "1.4.54", "1.4.55")
                external = base / "external"
                external.mkdir()
                sentinel = external / "sentinel.txt"
                sentinel.write_text("do-not-touch", encoding="utf-8")
                original_secure = getattr(devcat, "_secure_private_leaf", None)
                attacked = False
                expected_external_leaf: Path | None = None

                def make_directory_link(link: Path, target: Path) -> None:
                    try:
                        link.symlink_to(target, target_is_directory=True)
                        return
                    except OSError as symlink_error:
                        if os.name != "nt":
                            self.skipTest(
                                f"platform cannot create a directory link: {symlink_error}"
                            )
                    result = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                        capture_output=True, text=True, check=False,
                    )
                    if result.returncode != 0:
                        self.skipTest(
                            "platform cannot create a directory symlink or junction: "
                            f"{result.stderr.strip() or result.stdout.strip()}"
                        )

                def replace_parent_then_create(
                    trusted_root: Path, leaf: Path, *args, **kwargs,
                ):
                    nonlocal attacked, expected_external_leaf
                    is_snapshot = "sources" in leaf.parts
                    if not attacked and is_snapshot == (boundary == "snapshot"):
                        leaf.parent.mkdir(parents=True, exist_ok=True)
                        leaf.parent.rmdir()
                        make_directory_link(leaf.parent, external)
                        attacked = True
                        expected_external_leaf = external / leaf.name
                    if original_secure is None:
                        raise AssertionError("secure private leaf helper is missing")
                    return original_secure(trusted_root, leaf, *args, **kwargs)

                out = base / "share"
                with mock.patch.object(
                    devcat, "_secure_private_leaf", create=True,
                    side_effect=replace_parent_then_create,
                ):
                    with self.assertRaises(devcat.OverlayExportError):
                        devcat.export_patch_overlays(
                            root, None, out, from_version="1.4.54",
                        )
                self.assertTrue(attacked)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "do-not-touch")
                self.assertIsNotNone(expected_external_leaf)
                self.assertFalse(expected_external_leaf.exists())
                self.assertFalse(any(out.rglob("*.zip")) if out.exists() else False)
                self.assertFalse(any(
                    path.name.startswith("wf-overlay-") for path in out.iterdir()
                ) if out.exists() else False)


class MaterializeForeignRootTest(unittest.TestCase):
    """外根包的显示路径不是它的物理位置。

    `asset-patch/active/…` 是给报告和 catalog 看的展示路径,物理文件在 CDN 根之外。
    以前物化直接把它拼到 cdn_root 上,于是第一个外根包就让 shutil.copy2 抛
    FileNotFoundError——不是可读的错误,是整条命令的 traceback。真实链上 65 个外根包
    全部命中,`export-overlay` 前的准备步骤因此完全走不通。
    """

    def _make(self, tmp: Path) -> tuple[Path, Path]:
        cdn = tmp / "cn"
        patch = tmp / "asset-patch-active"
        (cdn / "archive-common-diff").mkdir(parents=True)
        (cdn / "archive-medium-diff").mkdir(parents=True)
        (cdn / "archive-android-diff").mkdir(parents=True)
        (cdn / "archive-common-full").mkdir(parents=True)
        patch.mkdir(parents=True)
        with zipfile.ZipFile(
            cdn / "archive-common-full" / "pinball-1.4.0-1-aaaaaaaa.zip", "w"
        ) as bundle:
            bundle.writestr("production/upload/aa/" + "1" * 38, b"BASE")
        with zipfile.ZipFile(
            patch / "pinball-1.4.0-1.4.1-1-foreign.zip", "w"
        ) as bundle:
            bundle.writestr("production/upload/bb/" + "2" * 38, b"FOREIGN")
        return cdn, patch

    def test_foreign_archive_is_materialized_from_its_real_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))

            view_root, stats, issues = devcat.materialize_dev_view(
                cdn, patch, Path(tmp) / "view",
            )

            self.assertEqual(0, stats["missing"])
            self.assertEqual(
                [], [i.line() for i in issues if i.code == "MATERIALIZE_SOURCE_MISSING"]
            )
            # 必须落在它自己的层目录里。用展示路径切目录会把外根包放进视图的
            # asset-patch/ 下:文件在磁盘上,扫描器看不见,该边就成了"缺 common 层"。
            self.assertFalse(
                (view_root / "asset-patch").exists(),
                "外根包不该在视图里重建出 asset-patch/ 目录",
            )
            diff_zips = sorted(
                (view_root / "archive-common-diff").glob("*.zip")
            )
            self.assertEqual(1, len(diff_zips))
            with zipfile.ZipFile(diff_zips[0]) as bundle:
                self.assertEqual(
                    [b"FOREIGN"],
                    [bundle.read(i) for i in bundle.infolist()],
                )
            materialized = list(view_root.rglob("*.zip"))
            self.assertEqual(2, len(materialized))
            payloads = set()
            for path in materialized:
                with zipfile.ZipFile(path) as bundle:
                    for info in bundle.infolist():
                        payloads.add(bundle.read(info))
            self.assertEqual({b"BASE", b"FOREIGN"}, payloads)

    def test_unavailable_foreign_root_resolves_to_nothing_not_to_the_cdn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))
            scan = devcat.scan_chain(cdn, patch, digest_mode="skip")
            foreign = [a for a in scan.archives if a.foreign_root]
            self.assertTrue(foreign)

            for archive in foreign:
                # 没有外根时必须返回 None。回落到 cdn_root/<展示路径> 是原来的 bug:
                # 那个路径永远不存在,而调用方以为拿到了有效路径。
                self.assertIsNone(devcat.archive_source_path(archive, cdn, None))
                self.assertIsNone(
                    devcat.archive_source_root_relative(archive, cdn, None)
                )
                resolved = devcat.archive_source_path(archive, cdn, patch)
                self.assertIsNotNone(resolved)
                self.assertTrue(resolved.is_file())
                self.assertFalse(
                    str(resolved).startswith(str(cdn)),
                    "外根包不该落在 CDN 根下",
                )

    def test_local_archive_still_resolves_under_the_cdn_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cdn, patch = self._make(Path(tmp))
            scan = devcat.scan_chain(cdn, patch, digest_mode="skip")
            local = [a for a in scan.archives if not a.foreign_root]
            self.assertTrue(local)

            for archive in local:
                self.assertEqual(
                    cdn / archive.relative_path,
                    devcat.archive_source_path(archive, cdn, patch),
                )


class MaterializeTest(unittest.TestCase):
    def test_view_is_scan_clean(self) -> None:
        """物化视图:旧名改合规、EntityLists 落位、自家扫描器全绿。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cn"
            fixture = ScanAndEmitTest()
            fixture._make_chain(root)
            devcat.heal_missing_layers(root, None, apply=True)
            view_root, stats, _issues = devcat.materialize_dev_view(
                root, None, Path(tmp) / "view",
            )
            self.assertEqual(stats["renamed"], 1)  # mod0725 旧名
            self.assertGreater(stats["linked"] + stats["copied"], 0)
            # 视图必须让本移植扫描器零问题(=dev 扫描器零问题的镜像)
            scan = devcat.scan_chain(view_root, None, digest_mode="cache")
            self.assertEqual(
                [issue.line() for issue in scan.issues], [],
            )
            catalog, issues = devcat.build_catalog(
                scan.archives, scan.installed_bytes, scan.entity_lists_relative_path,
            )
            self.assertEqual([issue.line() for issue in issues], [])
            self.assertEqual(catalog["targetVersion"], "1.4.55")
            # 合并 CSV 含 mod 行
            csv_text = (view_root / "EntityLists" / "10939-android_medium.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn(fixture.mod_member, csv_text)
            # 硬链字节一致
            renamed = [p for p in (view_root / "archive-common-diff").glob("*.zip")]
            self.assertTrue(renamed)


class DigestCacheTest(unittest.TestCase):
    def test_cache_reused_and_invalidated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "file.bin"
            target.write_bytes(b"one")
            cache = Path(tmp) / "cache.json"
            first = devcat.resolve_digests([("k", target)], "cache", cache)
            self.assertEqual(first["k"], hashlib.sha256(b"one").hexdigest())
            # 缓存命中
            again = devcat.resolve_digests([("k", target)], "cache", cache)
            self.assertEqual(again, first)
            # 内容变化 → 重算
            target.write_bytes(b"two-longer")
            changed = devcat.resolve_digests([("k", target)], "cache", cache)
            self.assertEqual(changed["k"], hashlib.sha256(b"two-longer").hexdigest())


if __name__ == "__main__":
    unittest.main()
