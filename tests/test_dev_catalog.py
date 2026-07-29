# -*- coding: utf-8 -*-
"""dev Catalog 适配层(wf_dev_catalog)回归:校验移植保真、扫描容错、发射与回填。

校验语义对照上游 origin/dev:
src/content/cdn/{patch-graph,catalog-builder,runtime-manifest}.ts。
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

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
