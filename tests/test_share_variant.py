#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""分享包双变体构建器的端到端测试(临时 CDN + 合成表,不碰真实 store/.cdn)。"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
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
OVERLAY_ASSET = "dynamic/degree/degree_overlay_test.png"
PNG = b"\x89PNG\r\n\x1a\nsynthetic-overlay"


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
                      foreign_lineage=True, client_profile="official")
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

    def overlay_manifest(
        self,
        entries: list[tuple[str, str, bytes, str]],
        *,
        source_tail: str = "1.4.55",
    ) -> Path:
        """写一个完全位于临时目录的 frozen-overlay 合同。"""
        overlay_dir = Path(self._tmp.name) / "overlay"
        store = overlay_dir / "store"
        pending = overlay_dir / "sync_pending.json"
        manifest_path = overlay_dir / "manifest.json"
        store.mkdir(parents=True, exist_ok=True)

        manifest_entries = []
        sequence = []
        for root, logical, payload, codec in entries:
            rel = quest.hashed_rel(logical)
            target = store / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            sequence.append(rel if root == "common" else f"{root}:{rel}")
            manifest_entries.append({
                "root": root,
                "logicalPath": logical,
                "hashedRel": rel,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "codec": codec,
                "owner": "rank-p5b-test-fixture",
            })

        pending_bytes = (json.dumps(sequence, ensure_ascii=False, separators=(",", ":"))
                         + "\n").encode("utf-8")
        pending.write_bytes(pending_bytes)
        manifest = {
            "schemaVersion": 1,
            "sourceChainTail": source_tail,
            "storePath": "store",
            "pendingPath": "sync_pending.json",
            "pendingSha256": hashlib.sha256(pending_bytes).hexdigest(),
            "pendingSequence": sequence,
            "entries": manifest_entries,
        }
        canonical = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest["overlayDigest"] = hashlib.sha256(canonical).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest_path

    @staticmethod
    def rewrite_manifest(path: Path, payload: dict, *, refresh_digest: bool = True) -> None:
        payload = dict(payload)
        if refresh_digest:
            payload.pop("overlayDigest", None)
            canonical = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            payload["overlayDigest"] = hashlib.sha256(canonical).hexdigest()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class PendingOverlayCliTest(VariantFixture):
    def test_plan_accepts_explicit_pending_overlay_manifest_without_writing(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                result = variant_mod.main([
                    "plan", "--variant", "full", "--tag", "overlay1",
                    "--cdn", str(self.cdn), "--repo-root", str(self.repo),
                    "--out", str(self.out), "--foreign-lineage",
                    "--pending-overlay-manifest", str(manifest), "--json",
                    "--client-profile", "official",
                ])
            except SystemExit as exc:
                result = int(exc.code)
        self.assertEqual(0, result, stderr.getvalue())
        report = json.loads(stdout.getvalue())
        self.assertTrue(report["unpublishedOverlay"])
        self.assertEqual(1, report["pendingOverlay"]["entryCount"])
        self.assertEqual(len(LIVE) + 1, report["variants"]["full"]["entries"])
        self.assertFalse(self.out.exists())


class PendingOverlayBuildTest(VariantFixture):
    def test_overlay_is_final_layer_and_content_only_rebuilds_overlay_table(self):
        overlay_ability = table({
            "111001": "overlay 仍改过官方词条",
            "10": "overlay 仍改过白虎",
            "1299991": "赛瑞斯词条",
            "1299992": "overlay 新内容词条",
        })
        manifest = self.overlay_manifest([
            ("common", ABILITY, overlay_ability, "orderedmap-flat-zlib"),
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        expected = dict(EXPECT)
        expected[ABILITY] = ["1299991", "1299992"]
        self.build(
            anchor_from="1.4.130", pending_overlay_manifest=manifest,
            expect_content_rows=expected)

        full = self.out / "wfshare-1.4.130-to-1.4.131-full"
        content = self.out / "wfshare-1.4.130-to-1.4.131-content-only"
        self.assertEqual(overlay_ability, self.member(full, ABILITY))
        self.assertEqual(PNG, self.member(full, OVERLAY_ASSET))
        self.assertEqual(PNG, self.member(content, OVERLAY_ASSET))

        rebuilt = quest.parse_node(self.member(content, ABILITY))
        self.assertEqual("官方词条", rebuilt["111001"])
        self.assertEqual("白虎官方词条", rebuilt["10"])
        self.assertEqual("赛瑞斯词条", rebuilt["1299991"])
        self.assertEqual("overlay 新内容词条", rebuilt["1299992"])

    def test_reports_and_requires_declare_unpublished_overlay_provenance(self):
        overlay_ability = table({
            "111001": "overlay 官方改动", "10": "overlay 白虎",
            "1299991": "赛瑞斯词条", "1299992": "新内容",
        })
        manifest = self.overlay_manifest([
            ("common", ABILITY, overlay_ability, "orderedmap-flat-zlib"),
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        expected_manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        frozen = json.loads(manifest.read_text(encoding="utf-8"))
        report = self.build(
            anchor_from="1.4.130", variants=("full",),
            pending_overlay_manifest=manifest)

        pack = self.out / "wfshare-1.4.130-to-1.4.131-full"
        on_disk = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        variant_report = json.loads((pack / "report.json").read_text(encoding="utf-8"))
        requires = json.loads((pack / "requires.json").read_text(encoding="utf-8"))
        for payload in (report, on_disk, variant_report, requires):
            self.assertIn("unpublishedOverlay", payload)
            self.assertIn("sourceChainTail", payload)
            self.assertIn("pendingOverlay", payload)
            self.assertTrue(payload["unpublishedOverlay"])
            self.assertEqual("1.4.55", payload["sourceChainTail"])
            overlay = payload["pendingOverlay"]
            self.assertEqual(2, overlay["entryCount"])
            self.assertEqual(expected_manifest_sha, overlay["manifestSha256"])
            self.assertEqual(frozen["overlayDigest"], overlay["overlayDigest"])
            self.assertEqual(frozen["pendingSha256"], overlay["pendingSha256"])
            self.assertFalse(overlay["publicationReceipt"])
            self.assertIn("不是发布回执", overlay["note"])

        self.assertEqual("1.4.55", report["chain"]["tail"])
        self.assertEqual(len(LIVE), report["chain"]["entries"])
        self.assertEqual(len(LIVE) + 1, report["variants"]["full"]["entries"])
        by_logical = {entry["logicalPath"]: entry
                      for entry in report["pendingOverlay"]["entries"]}
        replaced = by_logical[ABILITY]
        self.assertTrue(replaced["overridesChain"])
        self.assertEqual(hashlib.sha256(LIVE[ABILITY]).hexdigest(),
                         replaced["chainSha256"])
        self.assertEqual(hashlib.sha256(overlay_ability).hexdigest(), replaced["sha256"])
        added = by_logical[OVERLAY_ASSET]
        self.assertFalse(added["overridesChain"])
        self.assertIsNone(added["chainSha256"])
        readme = (pack / "说明.txt").read_text(encoding="utf-8")
        self.assertIn("未发布 overlay", readme)
        self.assertIn("不是发布回执", readme)
        self.assertIn("不得再叠加或重复应用", readme)

    def test_build_accepts_only_exact_manifest_store_and_pending_paths(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        report = self.build(
            anchor_from="1.4.130", variants=("full",), dry_run=True,
            pending_overlay_manifest=manifest,
            pending_overlay_store=(manifest.parent / "store").resolve(),
            pending_overlay_pending=(manifest.parent / "sync_pending.json").resolve())
        self.assertEqual(1, report["pendingOverlay"]["entryCount"])
        self.assertFalse(self.out.exists())

    def test_explicit_clean_copy_cannot_bypass_drifted_manifest_live_inputs(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        clean_store = manifest.parent.parent / "explicit-store"
        clean_pending = manifest.parent.parent / "explicit-pending.json"
        shutil.copytree(manifest.parent / "store", clean_store)
        shutil.copy2(manifest.parent / "sync_pending.json", clean_pending)
        live_payload = manifest.parent / "store" / quest.hashed_rel(OVERLAY_ASSET)
        live_payload.write_bytes(PNG[:-1] + b"X")
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_manifest=manifest,
                pending_overlay_store=clean_store.resolve(),
                pending_overlay_pending=clean_pending.resolve())
        self.assertIn("必须等于 manifest", str(ctx.exception))


class PendingOverlayGuardTest(VariantFixture):
    def assert_overlay_rejected(self, manifest: Path, message: str):
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_manifest=manifest)
        self.assertIn(message.lower(), str(ctx.exception).lower())

    def test_source_chain_tail_must_match_replayed_chain(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ], source_tail="1.4.999")
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_manifest=manifest)
        self.assertIn("sourceChainTail", str(ctx.exception))

    def test_store_or_pending_override_cannot_bypass_manifest(self):
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_store=Path(self._tmp.name),
                pending_overlay_pending=Path(self._tmp.name) / "pending.json")
        self.assertIn("manifest", str(ctx.exception).lower())

    def test_explicit_store_override_must_be_absolute(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_manifest=manifest,
                pending_overlay_store=Path("relative-store"))
        self.assertIn("绝对", str(ctx.exception))

    def test_manifest_entry_requires_non_empty_owner(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["entries"][0]["owner"] = ""
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "owner")

    def test_tmp_path_segment_is_forbidden(self):
        manifest = self.overlay_manifest([
            ("common", "dynamic/tmp/plate.png", PNG, "png"),
        ])
        self.assert_overlay_rejected(manifest, "tmp")

    def test_pending_sequence_drift_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        (manifest.parent / "sync_pending.json").write_text(
            json.dumps([quest.hashed_rel(OVERLAY_ASSET), "aa/" + "0" * 38]),
            encoding="utf-8")
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",), dry_run=True,
                pending_overlay_manifest=manifest)
        self.assertIn("pending", str(ctx.exception).lower())

    def test_pending_sequence_mismatch_fails_even_with_matching_file_sha(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        pending = manifest.parent / "sync_pending.json"
        sequence = [quest.hashed_rel(OVERLAY_ASSET), "aa/" + "0" * 38]
        pending_bytes = json.dumps(sequence, separators=(",", ":")).encode("utf-8")
        pending.write_bytes(pending_bytes)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["pendingSha256"] = hashlib.sha256(pending_bytes).hexdigest()
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "有序序列")

    def test_live_payload_sha_drift_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        target = manifest.parent / "store" / quest.hashed_rel(OVERLAY_ASSET)
        target.write_bytes(PNG[:-1] + b"X")
        self.assert_overlay_rejected(manifest, "sha-256")

    def test_logical_path_must_hash_to_declared_rel(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        wrong_rel = "aa/" + "0" * 38
        payload["entries"][0]["hashedRel"] = wrong_rel
        payload["pendingSequence"] = [wrong_rel]
        pending_bytes = (json.dumps([wrong_rel], separators=(",", ":")) + "\n").encode()
        (manifest.parent / "sync_pending.json").write_bytes(pending_bytes)
        payload["pendingSha256"] = hashlib.sha256(pending_bytes).hexdigest()
        target = manifest.parent / "store" / wrong_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG)
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "logicalpath")

    def test_invalid_root_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        rel = payload["entries"][0]["hashedRel"]
        payload["entries"][0]["root"] = "ios"
        payload["pendingSequence"] = [f"ios:{rel}"]
        pending_bytes = (json.dumps(payload["pendingSequence"], separators=(",", ":"))
                         + "\n").encode()
        (manifest.parent / "sync_pending.json").write_bytes(pending_bytes)
        payload["pendingSha256"] = hashlib.sha256(pending_bytes).hexdigest()
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "root")

    def test_forbidden_env_and_bot_paths_fail_closed(self):
        for logical in (".env", ".database/player.sqlite", ".database.sqlite",
                        "dynamic/foo.png.bak-1", "dynamic/bots/seed.png"):
            with self.subTest(logical=logical):
                manifest = self.overlay_manifest([
                    ("common", logical, PNG, "png"),
                ])
                self.assert_overlay_rejected(manifest, "禁入")

    def test_duplicate_entries_fail_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        self.assert_overlay_rejected(manifest, "重复")

    def test_unknown_codec_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "mystery-codec"),
        ])
        self.assert_overlay_rejected(manifest, "codec")

    def test_non_string_codec_fails_closed_as_contract_error(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["entries"][0]["codec"] = ["png"]
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "codec")

    def test_pending_path_without_overlay_entry_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["pendingSequence"].append("aa/" + "0" * 38)
        pending_bytes = (json.dumps(payload["pendingSequence"], separators=(",", ":"))
                         + "\n").encode()
        (manifest.parent / "sync_pending.json").write_bytes(pending_bytes)
        payload["pendingSha256"] = hashlib.sha256(pending_bytes).hexdigest()
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "未知")

    def test_manifest_digest_drift_fails_closed(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["overlayDigest"] = "0" * 64
        self.rewrite_manifest(manifest, payload, refresh_digest=False)
        self.assert_overlay_rejected(manifest, "overlaydigest")

    def test_relative_manifest_paths_cannot_traverse_parent(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        outside = manifest.parent.parent / "outside-store"
        source = manifest.parent / "store"
        source.replace(outside)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["storePath"] = "../outside-store"
        self.rewrite_manifest(manifest, payload)
        self.assert_overlay_rejected(manifest, "相对路径")

    def test_output_cannot_overlap_manifest_live_store(self):
        manifest = self.overlay_manifest([
            ("common", OVERLAY_ASSET, PNG, "png"),
        ])
        with self.assertRaises(VariantError) as ctx:
            self.build(
                anchor_from="1.4.130", variants=("full",),
                pending_overlay_manifest=manifest,
                out_dir=manifest.parent / "store")
        self.assertIn("输入路径", str(ctx.exception))


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
        cache_dir = policy_mod.CACHE_DIR
        self.assertFalse(cache_dir.exists())
        report = self.build(anchor_from="1.4.130", dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertFalse(self.out.exists())
        self.assertFalse(cache_dir.exists())

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

    def test_refuses_writing_into_database_or_env_paths(self):
        for forbidden in (".database", ".env"):
            with self.subTest(forbidden=forbidden), self.assertRaises(VariantError):
                self.build(
                    anchor_from="1.4.130", dry_run=True,
                    out_dir=self.repo / forbidden / "share-output")

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
                  foreign_lineage=True, anchor_from="1.4.130", client_profile="official")


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
