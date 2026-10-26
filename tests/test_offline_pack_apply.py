# -*- coding: utf-8 -*-
"""离线整包投递器的回归测试。

覆盖的都是「静默毁数据」类的失效模式:
  * 服务端 JSON 顶层 update 抹掉同级子项(死亡使者 event_item_shop 的真实形状);
  * 整表快照覆盖把线上后来新增的行删掉(1.4.278 / 杰拉德包那两次事故的形状);
  * 裸跑 wf_publish 清空作者的 sync_pending.json。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_mod_tool as core  # noqa: E402
import wf_offline_pack_apply as apply_tool  # noqa: E402


def build_flat_table(logical: str, rows: dict[str, bytes]) -> bytes:
    table = core.OrderedMap(logical, list(rows), list(rows.values()), Path("<test>"))
    return core.build_orderedmap(table)


def flat_rows(payload: bytes, logical: str) -> dict[str, bytes]:
    keys, values = apply_tool.read_rows(payload, "flat", logical)
    return dict(zip(keys, values))


class DeepMergeCase(unittest.TestCase):
    def test_nested_container_keeps_existing_siblings(self):
        """死亡使者的真实形状:delta 写 ["2"]["59001"],而线上 "2" 已有 4 个子项。"""
        live = {"2": {"100001": {"a": 1}, "100003": {"a": 2},
                      "100004": {"a": 3}, "100006": {"a": 4}}}
        delta = {"2": {"59001": {"59001010": {"stock": 5}}}}
        ops: list[apply_tool.MergeOp] = []
        merged = apply_tool.deep_merge_json(live, delta, ops=ops)
        self.assertEqual(
            sorted(merged["2"]), ["100001", "100003", "100004", "100006", "59001"])
        self.assertEqual(merged["2"]["59001"]["59001010"], {"stock": 5})
        self.assertEqual([op.path for op in ops], [("2", "59001")])
        # 输入不被原地改写
        self.assertNotIn("59001", live["2"])

    def test_shallow_update_would_have_lost_siblings(self):
        """反向对照:顶层 update 就是会抹掉那 4 个 —— 证明上一条断言不是空转。"""
        live = {"2": {"100001": {}, "100003": {}}}
        naive = dict(live)
        naive.update({"2": {"59001": {}}})
        self.assertEqual(list(naive["2"]), ["59001"])

    def test_root_list_union_is_order_preserving_and_idempotent(self):
        ops: list[apply_tool.MergeOp] = []
        merged = apply_tool.deep_merge_json([1, 2, 3], [3, 4], ops=ops)
        self.assertEqual(merged, [1, 2, 3, 4])
        self.assertEqual(len(ops), 1)
        again = apply_tool.deep_merge_json(merged, [3, 4])
        self.assertEqual(again, [1, 2, 3, 4])

    def test_nested_array_mismatch_is_refused(self):
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.deep_merge_json(
                {"k": {"costs": [{"id": 1}]}}, {"k": {"costs": [{"id": 2}]}})
        self.assertIn("嵌套数组", str(ctx.exception))

    def test_scalar_conflict_is_refused_by_default(self):
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.deep_merge_json({"a": 1}, {"a": 2})
        self.assertEqual(
            apply_tool.deep_merge_json({"a": 1}, {"a": 2}, allow_overwrite=True), {"a": 2})

    def test_type_conflict_is_refused(self):
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.deep_merge_json({"a": {"b": 1}}, {"a": [1]})


class DiffAdditionsCase(unittest.TestCase):
    def test_full_file_is_reduced_to_a_delta(self):
        baseline = {"11": {"700099": {"1": {}}}, "2": {"x": {}}}
        candidate = {"11": {"700099": {"1": {}, "9700199": {"stock": 60}}}, "2": {"x": {}}}
        delta = apply_tool.diff_json_additions(baseline, candidate)
        self.assertEqual(delta, {"11": {"700099": {"9700199": {"stock": 60}}}})

    def test_identical_file_yields_no_delta(self):
        self.assertIsNone(apply_tool.diff_json_additions({"a": 1}, {"a": 1}))

    def test_full_file_missing_a_live_key_is_a_stale_snapshot(self):
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.diff_json_additions({"a": 1, "b": 2}, {"a": 1})
        self.assertIn("陈旧快照", str(ctx.exception))

    def test_full_file_missing_a_live_list_element_is_a_stale_snapshot(self):
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.diff_json_additions([1, 2, 3], [1, 3])


class JsonStyleCase(unittest.TestCase):
    """assets/*.json 的排版**不统一**;写回必须按各文件原样,别整文件重排。"""

    SAMPLES = (
        ('{"a": 1, "b": {"c": 2}}', "紧凑单行(热重载那一批)"),
        ('{\n "a": 1,\n "b": 2\n}', "indent=1"),
        ('{\n  "a": 1,\n  "b": 2\n}', "indent=2"),
        ('{\n    "a": 1,\n    "b": 2\n}', "indent=4"),
        ('[\n1,\n2,\n3\n]', "indent=0 的数组(equipment_ids 的形状)"),
        ('{"a": "老"}', "非 ASCII 原样保留"),
    )

    def test_every_observed_style_round_trips_byte_exact(self):
        for text, label in self.SAMPLES:
            with self.subTest(label):
                raw = text.encode("utf-8")
                value = json.loads(text)
                style = apply_tool.detect_json_style(raw, value)
                self.assertTrue(style["matched"], label)
                self.assertEqual(apply_tool.dump_json_like(value, style), raw)

    def test_trailing_newline_is_preserved(self):
        raw = b'{"a": 1}\n'
        style = apply_tool.detect_json_style(raw, {"a": 1})
        self.assertEqual(style["trailing"], "\n")
        self.assertEqual(apply_tool.dump_json_like({"a": 1}, style), raw)

    def test_unrecognised_style_is_flagged_not_guessed(self):
        raw = b'{  "a"  :  1  }'
        style = apply_tool.detect_json_style(raw, {"a": 1})
        self.assertFalse(style["matched"])

    def test_style_survives_a_json_round_trip_through_the_plan_file(self):
        """plan 存成 JSON 后 separators 会变 list,dump_json_like 必须还原成 tuple。"""
        raw = b'{"a": 1, "b": 2}'
        style = json.loads(json.dumps(apply_tool.detect_json_style(raw, {"a": 1, "b": 2})))
        self.assertIsInstance(style["separators"], list)
        self.assertEqual(apply_tool.dump_json_like({"a": 1, "b": 2}, style), raw)


class RowMergeCase(unittest.TestCase):
    LOGICAL = "master/item/item.orderedmap"

    def test_claimed_rows_land_and_untouched_rows_survive(self):
        live = build_flat_table(self.LOGICAL, {"1": b"live-1", "2": b"live-2"})
        # 包是「建包当时」的快照:它不知道线上后来多了 "2"
        candidate = build_flat_table(self.LOGICAL, {"1": b"live-1", "9": b"new-9"})
        merged = apply_tool.merge_rows(self.LOGICAL, "flat", ["9"], candidate, live)
        apply_tool.verify_merged(self.LOGICAL, "flat", ["9"], candidate, live, merged)
        rows = flat_rows(merged, self.LOGICAL)
        self.assertEqual(rows, {"1": b"live-1", "2": b"live-2", "9": b"new-9"})

    def test_whole_file_overwrite_would_have_dropped_a_live_row(self):
        """反向对照:直接落包里那份整表就会删掉线上的 "2"。"""
        candidate = build_flat_table(self.LOGICAL, {"1": b"live-1", "9": b"new-9"})
        self.assertNotIn("2", flat_rows(candidate, self.LOGICAL))

    def test_changed_row_is_replaced_in_place(self):
        live = build_flat_table(self.LOGICAL, {"1": b"old", "2": b"keep"})
        candidate = build_flat_table(self.LOGICAL, {"1": b"new", "2": b"keep"})
        merged = apply_tool.merge_rows(self.LOGICAL, "flat", ["1"], candidate, live)
        apply_tool.verify_merged(self.LOGICAL, "flat", ["1"], candidate, live, merged)
        self.assertEqual(flat_rows(merged, self.LOGICAL), {"1": b"new", "2": b"keep"})

    def test_verify_merged_catches_a_row_that_should_not_have_moved(self):
        live = build_flat_table(self.LOGICAL, {"1": b"live-1", "2": b"live-2"})
        candidate = build_flat_table(self.LOGICAL, {"1": b"tampered", "9": b"new-9"})
        # 只 claim 了 "9",但整表覆盖会把 "1" 也换掉 —— 复核必须发现
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.verify_merged(
                self.LOGICAL, "flat", ["9"], candidate, live, candidate)

    def test_detect_codec_prefers_flat_when_both_parse(self):
        live = build_flat_table(self.LOGICAL, {"1": b"a"})
        candidate = build_flat_table(self.LOGICAL, {"1": b"a", "2": b"b"})
        self.assertEqual(apply_tool.detect_codec(candidate, live, self.LOGICAL), "flat")

    def test_detect_codec_falls_back_to_raw_outer(self):
        logical = "master/item/equipment_status.orderedmap"
        table = core.OrderedMap(logical, ["1"], [b"not-zlib"], Path("<test>"))
        payload = core.build_orderedmap_raw_rows(table)
        self.assertEqual(apply_tool.detect_codec(payload, payload, logical), "raw_outer")


class PackPlanCase(unittest.TestCase):
    """用一个最小的合成包端到端跑 plan,不碰真仓任何字节。"""

    LOGICAL = "master/item/item.orderedmap"
    ASSET = "item_lookup.json"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        self.assets = self.root / "assets"
        self.assets.mkdir(parents=True)
        self.env = apply_tool.Environment(store=self.store, assets=self.assets)
        self.write_live({"1": b"live-1", "2": b"live-2"})
        # 用带缩进的排版落 assets,好验证写回不会把它压成一行
        (self.assets / self.ASSET).write_bytes(
            json.dumps({"1": "one"}, ensure_ascii=False, indent=2).encode("utf-8"))

    def write_live(self, rows: dict[str, bytes]) -> None:
        payload = build_flat_table(self.LOGICAL, rows)
        path = core.table_path(self.store, self.LOGICAL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def build_pack(self, rows: dict[str, bytes], *, delta: dict | None = None,
                   publishing_allowed: bool = False) -> Path:
        digest = core.sha1_path(self.LOGICAL)
        table_member = f"roots/common/{digest[:2]}/{digest[2:]}"
        table_bytes = build_flat_table(self.LOGICAL, rows)
        delta_member = f"roots/server/assets/{self.ASSET[:-5]}.delta.json"
        delta_bytes = json.dumps(
            delta if delta is not None else {"9": "nine"}, ensure_ascii=False
        ).encode("utf-8")
        evidence = json.dumps({"schema_version": 1, "assets": [], "references": []},
                              ensure_ascii=False).encode("utf-8")
        manifest = {
            "schema": "wf-five-boss-weapon-package/v1",
            "package_id": "synthetic_pack",
            "publishing_allowed": publishing_allowed,
            "client_logicals": [self.LOGICAL],
            "members": [
                {"path": table_member, "sha256": hashlib.sha256(table_bytes).hexdigest(),
                 "size": len(table_bytes)},
                {"path": delta_member, "sha256": hashlib.sha256(delta_bytes).hexdigest(),
                 "size": len(delta_bytes)},
                {"path": "evidence/resources.json",
                 "sha256": hashlib.sha256(evidence).hexdigest(), "size": len(evidence)},
            ],
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
        sums = "\n".join(
            f"{hashlib.sha256(body).hexdigest()}  {name}"
            for name, body in (
                (table_member, table_bytes), (delta_member, delta_bytes),
                ("evidence/resources.json", evidence), ("manifest.json", manifest_bytes),
            )
        ) + "\n"
        path = self.root / "pack.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", manifest_bytes)
            archive.writestr("SHA256SUMS", sums)
            archive.writestr("evidence/resources.json", evidence)
            archive.writestr(table_member, table_bytes)
            archive.writestr(delta_member, delta_bytes)
        return path

    def test_plan_derives_claims_and_stays_read_only(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        before = core.table_path(self.store, self.LOGICAL).read_bytes()
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["gate_overrides"], ["publishing_allowed=False"])
        table = report["tables"][0]
        self.assertEqual(table["status"], "ready")
        self.assertEqual(table["claimed_keys"], ["9"])
        self.assertEqual(table["dropped"], [])
        self.assertEqual(report["publish_logicals"], [self.LOGICAL])
        self.assertEqual(report["server"][0]["ops"], [{
            "action": "add", "path": ["9"], "detail": ""}])
        self.assertEqual(core.table_path(self.store, self.LOGICAL).read_bytes(), before)

    def test_declared_gate_blocks_without_author_approval(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=False)
        self.assertTrue(any("publishing_allowed" in b for b in report["blockers"]))
        self.assertEqual(report["gate_overrides"], [])

    def test_stale_snapshot_pack_is_blocked(self):
        # 包里没有线上的 "3" —— 正是那 5 个老包的形状
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        self.write_live({"1": b"live-1", "2": b"live-2", "3": b"live-3"})
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        table = report["tables"][0]
        self.assertEqual(table["status"], "stale-snapshot")
        self.assertEqual(table["dropped"], ["3"])
        self.assertTrue(any("陈旧快照" in b for b in report["blockers"]))

    def test_tolerated_live_key_turns_the_block_into_a_note(self):
        """同轮另一个包刚落地的行:包里没有它是正常的,合并会原样保留。"""
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        self.write_live({"1": b"live-1", "2": b"live-2", "8": b"sibling-8"})
        report = apply_tool.plan_pack(
            pack, self.env, author_approved=True, tolerate_live_keys=["8"])
        table = report["tables"][0]
        self.assertEqual(table["status"], "ready")
        self.assertEqual(table["tolerated_dropped"], ["8"])
        self.assertEqual(report["blockers"], [])
        receipt = apply_tool.apply_pack(
            pack, report, self.env, dry_run=False, backup_suffix=".bak-test")
        self.assertEqual(receipt["write_count"], 2)
        rows = flat_rows(
            core.table_path(self.store, self.LOGICAL).read_bytes(), self.LOGICAL)
        self.assertEqual(rows, {
            "1": b"live-1", "2": b"live-2", "8": b"sibling-8", "9": b"new-9"})

    def test_tampered_member_fails_the_checksum_gate(self):
        path = self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"})
        raw = path.read_bytes()
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            bodies = {name: archive.read(name) for name in names}
        digest = core.sha1_path(self.LOGICAL)
        bodies[f"roots/common/{digest[:2]}/{digest[2:]}"] += b"\x00"
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, bodies[name])
        self.assertNotEqual(raw, path.read_bytes())
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.load_pack(path)
        self.assertIn("哈希不符", str(ctx.exception))

    def test_apply_writes_backups_and_merges_onto_current_live(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        # plan 之后线上又多了一行(模拟同轮先落地的另一个包)
        self.write_live({"1": b"live-1", "2": b"live-2", "8": b"other-8"})
        receipt = apply_tool.apply_pack(
            pack, report, self.env, dry_run=False, backup_suffix=".bak-test")
        rows = flat_rows(core.table_path(self.store, self.LOGICAL).read_bytes(), self.LOGICAL)
        self.assertEqual(rows, {
            "1": b"live-1", "2": b"live-2", "8": b"other-8", "9": b"new-9"})
        self.assertEqual(len(receipt["backups"]), 2)
        written = (self.assets / self.ASSET).read_bytes()
        self.assertEqual(json.loads(written.decode("utf-8")), {"1": "one", "9": "nine"})
        # 排版按原样保留(indent=2),不被压成一行
        self.assertEqual(written, json.dumps(
            {"1": "one", "9": "nine"}, ensure_ascii=False, indent=2).encode("utf-8"))

    def test_apply_refuses_when_a_claimed_row_moved_since_plan(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        self.write_live({"1": b"live-1", "2": b"live-2", "9": b"someone-else"})
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.apply_pack(
                pack, report, self.env, dry_run=False, backup_suffix=".bak-test")
        self.assertIn("重跑 plan", str(ctx.exception))

    def test_apply_preserves_keys_live_gained_after_the_plan(self):
        """plan 之后同轮另一个包落地了新行 —— 合并必须原样带上,而不是当成陈旧拒绝。

        这就是「两个武器包同一轮先后落地」能成立的技术依据:投递顺序无关。
        """
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        self.write_live({"1": b"live-1", "2": b"live-2", "7": b"sibling-pack-row"})
        receipt = apply_tool.apply_pack(
            pack, report, self.env, dry_run=False, backup_suffix=".bak-test")
        rows = flat_rows(
            core.table_path(self.store, self.LOGICAL).read_bytes(), self.LOGICAL)
        self.assertEqual(rows, {
            "1": b"live-1", "2": b"live-2", "7": b"sibling-pack-row", "9": b"new-9"})
        self.assertEqual(receipt["live_moved"], [self.LOGICAL])

    def test_dry_run_apply_writes_nothing(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        before = core.table_path(self.store, self.LOGICAL).read_bytes()
        asset_before = (self.assets / self.ASSET).read_bytes()
        receipt = apply_tool.apply_pack(
            pack, report, self.env, dry_run=True, backup_suffix=".bak-test")
        self.assertEqual(receipt["write_count"], 2)
        self.assertEqual(core.table_path(self.store, self.LOGICAL).read_bytes(), before)
        self.assertEqual((self.assets / self.ASSET).read_bytes(), asset_before)

    def write_plan(self, report: dict) -> Path:
        plan = {
            "schema": apply_tool.PLAN_SCHEMA, "schema_version": apply_tool.SCHEMA_VERSION,
            "store": str(self.store), "assets": str(self.assets),
            "cross_pack_conflicts": [], "packs": [report],
        }
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        return path

    def test_cli_apply_needs_author_approval_a_second_time(self):
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        plan_path = self.write_plan(report)
        base = ["apply", "--plan", str(plan_path), "--pack-id", "synthetic_pack", "--dry-run"]
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.cmd_apply(apply_tool.build_parser().parse_args(base))
        self.assertIn("--author-approved", str(ctx.exception))
        self.assertEqual(
            apply_tool.cmd_apply(
                apply_tool.build_parser().parse_args(base + ["--author-approved"])), 0)

    def test_publish_refuses_before_apply(self):
        """apply 没跑就铸边 = 发一条只含线上原样字节的空边,链号白涨一格。"""
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        plan_path = self.write_plan(report)
        args = apply_tool.build_parser().parse_args([
            "publish", "--plan", str(plan_path), "--pack-id", "synthetic_pack", "--dry-run"])
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.cmd_publish(args)
        self.assertIn("先跑 apply", str(ctx.exception))

    def test_publish_runs_after_apply(self):
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=True)
        apply_tool.apply_pack(
            pack, report, self.env, dry_run=False, backup_suffix=".bak-test")
        plan_path = self.write_plan(report)
        args = apply_tool.build_parser().parse_args([
            "publish", "--plan", str(plan_path), "--pack-id", "synthetic_pack", "--dry-run"])
        self.assertEqual(apply_tool.cmd_publish(args), 0)

    def test_publish_refuses_a_plan_with_blockers(self):
        pack = apply_tool.load_pack(
            self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=False)
        plan_path = self.write_plan(report)
        args = apply_tool.build_parser().parse_args([
            "publish", "--plan", str(plan_path), "--pack-id", "synthetic_pack", "--dry-run"])
        with self.assertRaises(apply_tool.ApplyError) as ctx:
            apply_tool.cmd_publish(args)
        self.assertIn("阻断", str(ctx.exception))

    def test_apply_refuses_a_plan_with_blockers(self):
        pack = apply_tool.load_pack(self.build_pack({"1": b"live-1", "2": b"live-2", "9": b"new-9"}))
        report = apply_tool.plan_pack(pack, self.env, author_approved=False)
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.apply_pack(
                pack, report, self.env, dry_run=True, backup_suffix=".bak-test")


class CrossPackCase(unittest.TestCase):
    def test_same_key_from_two_packs_is_a_conflict(self):
        left = {"pack_id": "a", "tables": [
            {"logical": "t", "claimed_keys": ["1"], "candidate_sha256": "aa"}],
            "server": [], "resources": []}
        right = {"pack_id": "b", "tables": [
            {"logical": "t", "claimed_keys": ["1"], "candidate_sha256": "bb"}],
            "server": [], "resources": []}
        self.assertTrue(apply_tool.cross_pack_conflicts([left, right]))

    def test_disjoint_keys_are_clean(self):
        left = {"pack_id": "a", "tables": [
            {"logical": "t", "claimed_keys": ["1"], "candidate_sha256": "aa"}],
            "server": [], "resources": []}
        right = {"pack_id": "b", "tables": [
            {"logical": "t", "claimed_keys": ["2"], "candidate_sha256": "bb"}],
            "server": [], "resources": []}
        self.assertEqual(apply_tool.cross_pack_conflicts([left, right]), [])

    def test_same_server_path_from_two_packs_is_a_conflict(self):
        entry = {"asset": "item_lookup.json", "ops": [{"action": "add", "path": ["9"]}]}
        left = {"pack_id": "a", "tables": [], "server": [entry], "resources": []}
        right = {"pack_id": "b", "tables": [], "server": [entry], "resources": []}
        self.assertTrue(apply_tool.cross_pack_conflicts([left, right]))

    def test_appending_different_elements_to_one_root_list_is_not_a_conflict(self):
        """两个包各往 item_ids.json 根数组追加不同 id —— 那是并集,不是冲突。"""
        left = {"pack_id": "a", "tables": [], "resources": [], "server": [
            {"asset": "item_ids.json", "ops": [
                {"action": "append", "path": [], "detail": "10000144"}]}]}
        right = {"pack_id": "b", "tables": [], "resources": [], "server": [
            {"asset": "item_ids.json", "ops": [
                {"action": "append", "path": [], "detail": "2370100"}]}]}
        self.assertEqual(apply_tool.cross_pack_conflicts([left, right]), [])

    def test_appending_the_same_element_from_two_packs_is_reported(self):
        op = {"action": "append", "path": [], "detail": "2370100"}
        left = {"pack_id": "a", "tables": [], "resources": [], "server": [
            {"asset": "item_ids.json", "ops": [op]}]}
        right = {"pack_id": "b", "tables": [], "resources": [], "server": [
            {"asset": "item_ids.json", "ops": [op]}]}
        self.assertTrue(apply_tool.cross_pack_conflicts([left, right]))


class NestedRowCase(unittest.TestCase):
    """一行本身又是一张表时,外层整行替换 = 内层整表覆盖,必须先摊开。"""

    LOGICAL = "master/quest/boss_battle_quest.orderedmap"

    @staticmethod
    def nested_table(outer: dict[str, dict[str, bytes]]) -> bytes:
        rows = []
        for inner in outer.values():
            rows.append(core.build_orderedmap_raw_rows(core.OrderedMap(
                "inner", list(inner), list(inner.values()), Path("<test>"))))
        return core.build_orderedmap_raw_rows(
            core.OrderedMap("outer", list(outer), rows, Path("<test>")))

    def test_inner_diff_is_surfaced(self):
        live = self.nested_table({"1": {"a": b"1", "b": b"2"}})
        cand = self.nested_table({"1": {"a": b"1", "b": b"9", "c": b"3"}})
        live_row = core._strict_orderedmap_rows(live, label="l", compressed_rows=False)[1][0]
        cand_row = core._strict_orderedmap_rows(cand, label="c", compressed_rows=False)[1][0]
        diff = apply_tool.nested_inner_diff(cand_row, live_row)
        self.assertEqual(diff["added"], ["c"])
        self.assertEqual(diff["changed"], ["b"])
        self.assertEqual(diff["dropped"], [])

    def test_flat_row_is_not_mistaken_for_a_nested_table(self):
        self.assertIsNone(apply_tool.nested_inner_diff(b"plain-row", b"other-row"))


class PublishHandoffCase(unittest.TestCase):
    """裸跑 wf_publish 会清空作者的 pending —— 这条通道必须永远带 --tables。"""

    def test_publish_always_passes_tables(self):
        with mock.patch.object(apply_tool.subprocess, "run") as runner:
            runner.return_value = mock.Mock(returncode=0)
            with mock.patch.object(apply_tool, "pending_fingerprint", return_value="x"):
                apply_tool.run_publish(["master/item/item.orderedmap", "a/b.png"])
        command = runner.call_args[0][0]
        self.assertIn("--tables", command)
        self.assertEqual(
            command[command.index("--tables") + 1],
            "master/item/item.orderedmap,a/b.png")
        self.assertTrue(command[3].endswith("wf_publish.py"))

    def test_publish_refuses_an_empty_table_list(self):
        with self.assertRaises(apply_tool.ApplyError):
            apply_tool.run_publish([])

    def test_publish_reports_a_pending_change(self):
        fingerprints = iter(["before", "after"])
        with mock.patch.object(apply_tool.subprocess, "run") as runner:
            runner.return_value = mock.Mock(returncode=0)
            with mock.patch.object(
                apply_tool, "pending_fingerprint", side_effect=lambda *a, **k: next(fingerprints)
            ):
                with self.assertRaises(apply_tool.ApplyError) as ctx:
                    apply_tool.run_publish(["master/item/item.orderedmap"])
        self.assertIn("sync_pending.json", str(ctx.exception))

    def test_dry_run_does_not_spawn_wf_publish(self):
        with mock.patch.object(apply_tool.subprocess, "run") as runner:
            with mock.patch.object(apply_tool, "pending_fingerprint", return_value="x"):
                self.assertEqual(
                    apply_tool.run_publish(["a/b.orderedmap"], dry_run=True), 0)
        runner.assert_not_called()


class UnknownPackCase(unittest.TestCase):
    def test_unregistered_schema_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("manifest.json", json.dumps({"schema": "nope/v9"}))
            with self.assertRaises(apply_tool.ApplyError) as ctx:
                apply_tool.load_pack(path)
        self.assertIn("未登记", str(ctx.exception))

    def test_missing_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("readme.txt", "hi")
            with self.assertRaises(apply_tool.ApplyError):
                apply_tool.load_pack(path)


if __name__ == "__main__":
    unittest.main()
