#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""增强开关引擎的单元测试:全部用合成表,不依赖真实 store/.cdn。"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

MOD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as pol  # noqa: E402
import wf_enhancement_switch as sw  # noqa: E402
import wf_quest_lib as quest  # noqa: E402

ABILITY = sw.ABILITY
LEADER = sw.LEADER
SOUL = sw.SOUL
NCOLS = 126


def line(**cells: str) -> str:
    """126 列的一行,只填点名的列,其余留空。"""
    row = ["0"] * NCOLS
    row[1] = "true"
    for name, value in cells.items():
        row[int(name[1:])] = value
    return ",".join(row)


def table(rows: dict[str, object]) -> bytes:
    return quest.build_node(rows)


def parse(raw: bytes) -> dict:
    return quest.parse_node(raw)


class LayoutTest(unittest.TestCase):
    def test_layout_columns_match_the_pinned_widths(self):
        layouts = sw.load_layouts()
        self.assertEqual(126, layouts[ABILITY].ncols)
        self.assertEqual(124, layouts[LEADER].ncols)
        self.assertEqual(123, layouts[SOUL].ncols)

    def test_col_of_resolves_block_plus_field(self):
        layout = sw.load_layouts()[ABILITY]
        self.assertEqual(47, layout.col("instant_content", "kind"))
        self.assertEqual(51, layout.col("instant_content", "strength.power1"))
        self.assertEqual(6, layout.col("precondition1", "kind"))

    def test_field_at_is_the_inverse(self):
        layout = sw.load_layouts()[ABILITY]
        self.assertEqual(("instant_content", "kind"), layout.field_at(47))
        self.assertEqual(("precondition1", "kind"), layout.field_at(6))

    def test_sub_buckets_partition_the_tuning_fields(self):
        layout = sw.load_layouts()[ABILITY]
        self.assertEqual("power", sw._sub_of(layout, layout.col("instant_content", "strength.power1")))
        self.assertEqual("feel", sw._sub_of(layout, layout.col("instant_trigger", "cooltime")))
        self.assertEqual("gate", sw._sub_of(layout, layout.col("instant_trigger", "threshold.power1")))

    def test_sentinel_columns_are_recognised(self):
        layout = sw.load_layouts()[ABILITY]
        self.assertTrue(sw._is_sentinel(layout, layout.col("instant_content", "kind")))
        self.assertTrue(sw._is_sentinel(layout, layout.col("instant_trigger", "trigger_limit")))
        self.assertFalse(sw._is_sentinel(layout, layout.col("instant_content", "strength.power1")))


class LeafModelTest(unittest.TestCase):
    def test_leaf_holds_several_lines(self):
        leaf = "a,b\nc,d"
        self.assertEqual(["a,b", "c,d"], sw.split_lines(leaf))
        self.assertEqual(leaf, sw.join_lines(sw.split_lines(leaf)))

    def test_nested_rows_flatten_to_paths(self):
        self.assertEqual({("1",): "x", ("2",): "y"}, sw.leaves({"1": "x", "2": "y"}))
        self.assertEqual({(): "x"}, sw.leaves("x"))


class DiffFixture(unittest.TestCase):
    """官方 2 行 / 增强 3 行的一张 ability 表,覆盖各种地址类型。"""

    def setUp(self):
        layout = sw.load_layouts()[ABILITY]
        self.c_strength = layout.col("instant_content", "strength.power1")
        self.c_cool = layout.col("instant_trigger", "cooltime")
        self.c_kind = layout.col("instant_content", "kind")
        self.c_pre = layout.col("precondition1", "kind")

        official_main = line(**{f"c{self.c_strength}": "1000"})
        official_main_cells = official_main.split(",")
        official_main_cells[1] = "false"                 # 官方:仅主位
        official_main_cells[self.c_pre] = "202"          # 官方:主位前置
        self.official_main = ",".join(official_main_cells)

        enhanced_main_cells = list(official_main_cells)
        enhanced_main_cells[1] = "true"                  # 增强:解除主位限制
        enhanced_main_cells[self.c_pre] = "0"
        enhanced_main_cells[self.c_strength] = "5000"    # 增强:强度拉高
        self.enhanced_main = ",".join(enhanced_main_cells)

        self.official = table({
            "1000001": self.official_main,
            "1000002": line(**{f"c{self.c_strength}": "100"}),
            "1000003": line(**{f"c{self.c_cool}": "600"}),
        })
        self.enhanced = table({
            "1000001": self.enhanced_main + "\n" + line(**{f"c{self.c_strength}": "9"}),
            "1000002": line(**{f"c{self.c_strength}": "400"}),
            "1000003": line(**{f"c{self.c_cool}": "300"}),
        })
        self.diff = sw.diff_table(ABILITY, self.official, self.enhanced)

    def owners(self):
        return {address.owner for address in self.diff.addresses}

    def addresses_of(self, owner):
        return [a for a in self.diff.addresses if a.owner == owner]


class DiffTest(DiffFixture):
    def test_main_position_claims_unisonable_and_202_only(self):
        claimed = self.addresses_of("char.main_position")
        self.assertEqual({(1, "false", "true"), (self.c_pre, "202", "0")},
                         {(a.col, a.official, a.enhanced) for a in claimed})

    def test_strength_and_cooltime_fall_into_tuning_sub_buckets(self):
        tuning = {(a.col, a.sub) for a in self.addresses_of("char.tuning")}
        self.assertIn((self.c_strength, "power"), tuning)
        self.assertIn((self.c_cool, "feel"), tuning)

    def test_appended_line_belongs_to_extra_rows(self):
        appended = self.addresses_of("char.extra_rows")
        self.assertEqual(1, len(appended))
        self.assertEqual("appended", appended[0].kind)
        self.assertEqual(1, appended[0].line)

    def test_official_only_rows_are_untouched_when_identical(self):
        identical = table({"1000001": self.official_main})
        diff = sw.diff_table(ABILITY, identical, identical)
        self.assertEqual([], diff.addresses)

    def test_deleted_key_is_recorded(self):
        diff = sw.diff_table(ABILITY, self.official, table({"1000001": self.enhanced_main}))
        kinds = {a.kind for a in diff.addresses}
        self.assertIn("deleted_key", kinds)

    def test_fewer_lines_degrades_to_whole_key(self):
        official = table({"1000001": self.official_main + "\n" + self.official_main})
        enhanced = table({"1000001": self.enhanced_main})
        diff = sw.diff_table(ABILITY, official, enhanced)
        self.assertEqual(["key"], [a.kind for a in diff.addresses])
        self.assertEqual(["1000001"], diff.misaligned_keys)

    def test_sentinel_change_escalates_whole_line(self):
        official = table({"1000001": line(**{f"c{self.c_strength}": "1000"})})
        enhanced = table({"1000001": line(**{f"c{self.c_kind}": "31",
                                             f"c{self.c_strength}": "5000"})})
        diff = sw.diff_table(ABILITY, official, enhanced)
        self.assertEqual(1, diff.escalated["R1"])
        self.assertEqual({None}, {a.sub for a in diff.addresses})
        self.assertEqual({"char.tuning"}, {a.owner for a in diff.addresses})

    def test_cross_bucket_change_escalates_to_parent(self):
        official = table({"1000001": line(**{f"c{self.c_strength}": "1000",
                                             f"c{self.c_cool}": "600"})})
        enhanced = table({"1000001": line(**{f"c{self.c_strength}": "5000",
                                             f"c{self.c_cool}": "300"})})
        diff = sw.diff_table(ABILITY, official, enhanced)
        self.assertEqual(1, diff.escalated["R2"])
        self.assertEqual({None}, {a.sub for a in diff.addresses})

    def test_official_keys_are_never_treated_as_content(self):
        """商店官方商品 700099 与模式 id 撞号,不能被内容识别吃掉。"""
        official = table({"700099": "a,b", "1": "c,d"})
        enhanced = table({"1": "c,d"})
        diff = sw.diff_table(sw.EVENT_SHOP, official, enhanced)
        self.assertEqual(["deleted_key"], [a.kind for a in diff.addresses])
        self.assertEqual("other.shop_700099", diff.addresses[0].owner)


class ComposeTest(DiffFixture):
    def compose(self, desired, live=None, sub=None, allow_foreign=False):
        return sw.compose_table(
            official_raw=self.official, enhanced_raw=self.enhanced,
            live_raw=live if live is not None else self.enhanced,
            diff=self.diff, desired=desired, sub=sub or {}, allow_foreign=allow_foreign)

    def test_e1_all_off_reproduces_official(self):
        blob, _detail = self.compose({spec.id: False for spec in sw.TOGGLES})
        self.assertEqual(parse(self.official), parse(blob))

    def test_e2_all_on_reproduces_enhanced(self):
        blob, _detail = self.compose({spec.id: True for spec in sw.TOGGLES},
                                     live=self.official)
        self.assertEqual(parse(self.enhanced), parse(blob))

    def test_single_toggle_off_moves_only_its_cells(self):
        desired = {spec.id: True for spec in sw.TOGGLES}
        desired["char.main_position"] = False
        blob, detail = self.compose(desired)
        rows = parse(blob)
        first = sw.split_lines(rows["1000001"])[0].split(",")
        self.assertEqual("false", first[1])                       # 主位限制回官方
        self.assertEqual("202", first[self.c_pre])
        self.assertEqual("5000", first[self.c_strength])          # 其余仍是增强值
        self.assertEqual(2, detail.to_official)

    def test_sub_bucket_off_moves_only_that_bucket(self):
        official = table({"1000001": line(**{f"c{self.c_strength}": "1000"}),
                          "1000002": line(**{f"c{self.c_cool}": "600"})})
        enhanced = table({"1000001": line(**{f"c{self.c_strength}": "5000"}),
                          "1000002": line(**{f"c{self.c_cool}": "300"})})
        diff = sw.diff_table(ABILITY, official, enhanced)
        blob, _detail = sw.compose_table(
            official_raw=official, enhanced_raw=enhanced, live_raw=enhanced, diff=diff,
            desired={"char.tuning": True}, sub={"power": False, "feel": True, "gate": True})
        rows = parse(blob)
        self.assertEqual("1000", rows["1000001"].split(",")[self.c_strength])
        self.assertEqual("300", rows["1000002"].split(",")[self.c_cool])

    def test_extra_rows_off_drops_the_appended_line(self):
        desired = {spec.id: True for spec in sw.TOGGLES}
        desired["char.extra_rows"] = False
        blob, detail = self.compose(desired)
        self.assertEqual(1, len(sw.split_lines(parse(blob)["1000001"])))
        self.assertEqual(1, detail.rows_dropped)

    def test_deleted_key_is_restored_when_toggle_off(self):
        official = table({"700099": "a,b", "1": "c,d"})
        enhanced = table({"1": "c,d"})
        diff = sw.diff_table(sw.EVENT_SHOP, official, enhanced)
        blob, detail = sw.compose_table(
            official_raw=official, enhanced_raw=enhanced, live_raw=enhanced, diff=diff,
            desired={"other.shop_700099": False}, sub={})
        self.assertIn("700099", parse(blob))
        self.assertEqual(1, detail.rows_restored)

    def test_foreign_edit_is_preserved_and_reported(self):
        cells = self.enhanced_main.split(",")
        cells[self.c_strength] = "123456"          # 快照之后有人手改过
        live = table({"1000001": ",".join(cells) + "\n" + line(**{f"c{self.c_strength}": "9"}),
                      "1000002": line(**{f"c{self.c_strength}": "400"}),
                      "1000003": line(**{f"c{self.c_cool}": "300"})})
        blob, detail = self.compose({spec.id: False for spec in sw.TOGGLES}, live=live)
        self.assertEqual(1, len(detail.foreign))
        self.assertEqual("123456", parse(blob)["1000001"].split("\n")[0].split(",")[self.c_strength])

    def test_foreign_edit_can_be_overwritten_explicitly(self):
        cells = self.enhanced_main.split(",")
        cells[self.c_strength] = "123456"
        live = table({"1000001": ",".join(cells) + "\n" + line(**{f"c{self.c_strength}": "9"}),
                      "1000002": line(**{f"c{self.c_strength}": "400"}),
                      "1000003": line(**{f"c{self.c_cool}": "300"})})
        blob, _detail = self.compose({spec.id: False for spec in sw.TOGGLES},
                                     live=live, allow_foreign=True)
        self.assertEqual("1000", parse(blob)["1000001"].split(",")[self.c_strength])

    def test_custom_content_rows_are_never_touched(self):
        live = table({"1000001": self.enhanced_main, "1000002": line(),
                      "1000003": line(), "1299991": "自制角色词条"})
        blob, _detail = self.compose({spec.id: False for spec in sw.TOGGLES}, live=live)
        self.assertEqual("自制角色词条", parse(blob)["1299991"])


class VectorTest(unittest.TestCase):
    def test_preset_skips_guarded_and_excluded(self):
        current = {spec.id: True for spec in sw.TOGGLES}
        official = sw.preset_vector("official", current=current)
        self.assertFalse(official["char.tuning"])
        for guarded in (*sw.GUARDED_TOGGLES, *sw.PRESET_EXCLUDED):
            self.assertTrue(official[guarded], f"{guarded} 不该被一键预设改掉")

    def test_preset_scope_limits_the_change(self):
        current = {spec.id: True for spec in sw.TOGGLES}
        vector = sw.preset_vector("official", scope="weapon", current=current)
        self.assertFalse(vector["weapon.soul"])
        self.assertTrue(vector["char.tuning"])

    def test_observed_vector_reads_state_back(self):
        states = {
            "char.tuning": sw.ToggleState("char.tuning", "official", official=5),
            "weapon.soul": sw.ToggleState("weapon.soul", "enhanced", enhanced=3),
            "enemy.boss_hp": sw.ToggleState("enemy.boss_hp", "mixed", official=1, enhanced=4),
        }
        vector = sw.observed_vector(states)
        self.assertFalse(vector["char.tuning"])
        self.assertTrue(vector["weapon.soul"])
        self.assertTrue(vector["enemy.boss_hp"])


class ObserveTest(DiffFixture):
    def test_observe_classifies_store_bytes(self):
        states = sw.observe({ABILITY: self.diff}, {ABILITY: self.enhanced})
        self.assertEqual("enhanced", states["char.main_position"].state)
        states = sw.observe({ABILITY: self.diff}, {ABILITY: self.official})
        self.assertEqual("official", states["char.main_position"].state)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.store = base / "store"
        self._orig_dirs = (sw.SNAP_DIR, sw.PREIMAGE_DIR, sw.WORK_DIR, sw.STATE_PATH)
        sw.WORK_DIR = base / "work"
        sw.SNAP_DIR = sw.WORK_DIR / "snapshots"
        sw.PREIMAGE_DIR = sw.WORK_DIR / "preimages"
        sw.STATE_PATH = sw.WORK_DIR / "state.json"
        sw.WORK_DIR.mkdir(parents=True)
        self.addCleanup(self._restore_dirs)
        for logical, payload in ((ABILITY, table({"1": line()})),
                                 (sw.CHARACTER, table({"129999": "a", "139999": "b",
                                                       "149999": "c"}))):
            path = self.store / quest.hashed_rel(logical)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def _restore_dirs(self):
        sw.SNAP_DIR, sw.PREIMAGE_DIR, sw.WORK_DIR, sw.STATE_PATH = self._orig_dirs

    def ctx(self):
        return sw.Context(Path(self._tmp.name), self.store, Path(self._tmp.name) / "cdn",
                          "test", None)

    def test_snapshot_guard_rejects_a_store_missing_custom_content(self):
        path = self.store / quest.hashed_rel(sw.CHARACTER)
        path.write_bytes(table({"1": "官方"}))
        with self.assertRaises(sw.SwitchError) as ctx:
            sw.snapshot_freeze(self.ctx(), tag="bad")
        self.assertIn("自制内容行缺失", str(ctx.exception))

    def test_snapshot_guard_can_be_forced_but_leaves_a_trace(self):
        path = self.store / quest.hashed_rel(sw.CHARACTER)
        path.write_bytes(table({"1": "官方"}))
        snap = sw.snapshot_freeze(self.ctx(), tag="forced", force=True)
        manifest = (sw.SNAP_DIR / snap.name / "manifest.json").read_text(encoding="utf-8")
        self.assertIn("guardProblems", manifest)
        self.assertIn("自制内容行缺失", manifest)

    def test_snapshot_round_trips_bytes(self):
        snap = sw.snapshot_freeze(self.ctx(), tag="ok")
        self.assertEqual(table({"1": line()}), snap.get(ABILITY))
        self.assertEqual(snap.name, sw.load_snapshot().name)

    def test_bad_tag_is_rejected(self):
        with self.assertRaises(sw.SwitchError):
            sw.snapshot_freeze(self.ctx(), tag="bad tag!")


class ApplyRollbackTest(SnapshotTest):
    def test_apply_writes_and_rollback_restores_bytes(self):
        ctx = self.ctx()
        path = self.store / quest.hashed_rel(ABILITY)
        before = path.read_bytes()
        plan = sw.Plan(desired={}, sub={}, scope="all", details=[],
                       payloads={ABILITY: table({"1": line(c50="9")})},
                       selfcheck={"E1": True, "E2": True}, escalated={"R1": 0, "R2": 0},
                       misaligned={}, foreign=[], digest="deadbeef")
        result = sw.apply_plan(ctx, plan)
        self.assertNotEqual(before, path.read_bytes())
        sw.rollback(ctx, result["preimage"])
        self.assertEqual(before, path.read_bytes())

    def test_apply_refuses_when_selfcheck_fails(self):
        plan = sw.Plan({}, {}, "all", [], {ABILITY: b"x"},
                       {"E1": False, "E2": True, "e1_bad": ["x"]},
                       {"R1": 0, "R2": 0}, {}, [], "d")
        with self.assertRaises(sw.SwitchError) as ctx:
            sw.apply_plan(self.ctx(), plan)
        self.assertIn("自检等式不成立", str(ctx.exception))

    def test_apply_refuses_unconfirmed_foreign_drift(self):
        plan = sw.Plan({}, {}, "all", [], {ABILITY: b"x"},
                       {"E1": True, "E2": True}, {"R1": 0, "R2": 0}, {},
                       ["ability: 1#L0c50 第三方改动"], "d")
        with self.assertRaises(sw.ForeignDriftError):
            sw.apply_plan(self.ctx(), plan)


class ToggleContractTest(unittest.TestCase):
    def test_every_toggle_has_a_unique_id_and_known_scope(self):
        ids = [spec.id for spec in sw.TOGGLES]
        self.assertEqual(len(ids), len(set(ids)))
        for spec in sw.TOGGLES:
            self.assertIn(spec.scope, sw.SCOPES)

    def test_rest_buckets_have_the_lowest_priority(self):
        rest = {"char.tuning", "weapon.soul"}
        lowest = min(spec.priority for spec in sw.TOGGLES)
        for spec in sw.TOGGLES:
            if spec.id in rest:
                self.assertEqual(lowest, spec.priority)

    def test_guarded_toggles_are_marked_readonly_in_the_gui(self):
        for toggle_id in sw.GUARDED_TOGGLES:
            self.assertTrue(sw.TOGGLE_BY_ID[toggle_id].gui_readonly)

    def test_managed_tables_all_have_an_owner(self):
        owned = {logical for spec in sw.TOGGLES for logical in spec.tables}
        for logical in sw.MANAGED_TABLES:
            self.assertIn(logical, owned, f"{logical} 没有任何开关认领")


if __name__ == "__main__":
    unittest.main()
