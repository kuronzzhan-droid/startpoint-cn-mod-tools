# -*- coding: utf-8 -*-
"""引用完整性门禁 + 发布完整性自检回归测试。

事故背景(2026-07-26):
  缺陷1 关13 被随机到 field water_sphere,其 boss water_sphere_single 在
        general_boss/standard_boss/general_zako 三表全缺 → 真机 U_50fc52 进本崩;
  缺陷2 构建写了 mod_rogue_f9 等克隆进 store,发布清单没带 battle 表 →
        客户端 C8601「指定的Key不存在。key=mod_rogue_f9」。
"""
from __future__ import annotations

import copy
import csv
import os
import json
import random
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_quest_lib as q  # noqa: E402
import wf_rogue_build as rb  # noqa: E402
import wf_rogue_bundle as rbb  # noqa: E402
import wf_rogue_reroll as rr  # noqa: E402
import wf_rogue_save as rsave  # noqa: E402
import wf_dsl  # noqa: E402


def _store_available() -> bool:
    """本机/CI 是否装了数据包。没装时依赖 store 的用例只能跳过,不能算失败。"""
    try:
        q.store_path(rb.GENERAL_BOSS)
    except FileNotFoundError:
        return False
    return True


# 装饰器形式的守卫:比在用例体内 skipTest 更可靠 —— 后者若写在 subTest 里,
# 只中止当前 subTest,平级 subTest 照跑并引用未赋值的局部变量。
requires_store = unittest.skipUnless(_store_available(), "store 不可用")


def wave(zakos: tuple = (), bosses: tuple = ()) -> str:
    """41 列 zone wave 行:zako 填 c2/4/…偶数列,boss 填 (c23,c24)/(c27,c28)/(c31,c32)。"""
    row = [""] * 41
    for n, z in enumerate(zakos):
        row[2 + 2 * n] = z
    slots = ((23, 24), (27, 28), (31, 32))
    for n, b in enumerate(bosses):
        gate, code = slots[n]
        row[gate] = "1"
        row[code] = b
    return ",".join(row)


FD = {
    "f_ok": "f_ok,terrain_a,z_ok",
    "f_bad": "f_bad,terrain_a,z_bad",              # boss 三表全缺且无专用表 = 真悬空
    "f_std": "f_std,terrain_a,z_std",              # boss 只在 standard_boss(误报回归)
    "f_zk": "f_zk,terrain_a,z_zk",                 # boss 槽放 zako 代号(并集第三表)
    "f_nozone": "f_nozone,terrain_a,z_ghost",      # zone 缺失
    "f_badzako": "f_badzako,terrain_a,z_badzako",  # zako 槽悬空
    "f_sp": "f_sp,terrain_a,z_sp",                 # boss 只在专用表(orochi/kraken 型)
}
ZONE = {
    "z_ok": {"0": wave(zakos=("zk1",), bosses=("boss_g",))},
    "z_bad": {"0": wave(bosses=("ghost_boss",))},
    "z_std": {"0": wave(bosses=("boss_s",))},
    "z_zk": {"0": wave(bosses=("zk1",))},
    "z_badzako": {"0": wave(zakos=("zk_ghost",))},
    "z_sp": {"0": wave(bosses=("sp_boss",))},
}
ENEMIES = {"boss_g", "boss_s", "zk1"}   # general ∪ standard ∪ zako
ZAKOS = {"zk1"}


def quest_row(field: str) -> list[str]:
    row = ["700099001"] + [""] * 98
    row[98] = field
    return row


def native_bundle(field: str, boss: str, *, family: str = "family",
                  kind: int = 1, bgm: str = "bgm_safe",
                  thumbnail: str = "thumb_safe") \
        -> rbb.NativeBossBundle:
    return rbb.NativeBossBundle(
        family_id=family,
        family_name=family,
        variant_id=f"{family}-variant",
        variant_name=f"{family}-variant",
        source_field=field,
        source_zone=f"zone-{field}",
        terrain_logical=f"battle/field/{field}.terrain.amf3.deflate",
        active_layers=("0",),
        slots=(rbb.ActiveBossSlot(
            "0", 1, 0, rbb.BossRef(kind, boss), rbb.BossRef(kind, boss)),),
        bgm=bgm,
        thumbnail=thumbnail,
        source_category="rush",
        selected_levels=(("0", 1, 100),),
        terrain_requirements=rbb.BossTerrainRequirements(
            layers=(rbb.LayerTerrainRequirements(
                "0",
                funnels=(rbb.FunnelRequirement("1", 1, ("safe_funnel",)),),
                spawned_refs=(rbb.SpawnedRef("AlterEgo", "safe_shadow"),)),),
            action_roots=("battle/action/safe",),
            action_closure=("battle/action/safe",)),
    )


class FieldChainCase(unittest.TestCase):
    def check(self, field):
        return rb.check_field_chain(field, FD, ZONE, ENEMIES, ZAKOS)

    def test_resolvable_chain_passes(self):
        rep = self.check("f_ok")
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertEqual(rep["zone"], "z_ok")
        self.assertEqual(rep["bosses"], ["boss_g"])
        self.assertEqual(rep["zakos"], ["zk1"])

    def test_dangling_boss_rejected(self):
        rep = self.check("f_bad")
        self.assertFalse(rep["ok"])
        self.assertTrue(any("ghost_boss" in e and "悬空" in e for e in rep["errors"]),
                        rep["errors"])

    def test_standard_boss_union_no_false_positive(self):
        # 只查 general_boss 会把 standard_boss 的 7 个官方楼层误判悬空
        self.assertTrue(self.check("f_std")["ok"])

    def test_zako_table_counts_for_boss_slot(self):
        self.assertTrue(self.check("f_zk")["ok"])

    def test_boss_slot_checked_even_without_union_membership_in_zako_set(self):
        # boss 槽用三表并集,zako 槽只认 general_zako:zk_ghost 不在其中 → 拒
        rep = self.check("f_badzako")
        self.assertFalse(rep["ok"])
        self.assertIn("zako", rep["errors"][0])

    def test_missing_field_rejected(self):
        rep = self.check("mod_rogue_f9")      # 缺陷2 的客户端视角:C8601
        self.assertFalse(rep["ok"])
        self.assertIn("field_data[mod_rogue_f9] 缺失", rep["errors"][0])

    def test_missing_zone_rejected(self):
        rep = self.check("f_nozone")
        self.assertFalse(rep["ok"])
        self.assertIn("zone[z_ghost]", rep["errors"][0])

    def test_empty_field_rejected(self):
        self.assertFalse(rb.check_field_chain("", FD, ZONE, ENEMIES, ZAKOS)["ok"])
        self.assertFalse(rb.check_field_chain("(None)", FD, ZONE, ENEMIES, ZAKOS)["ok"])


class LevelCoverageCase(unittest.TestCase):
    """U_50fc52 二号根因(2026-07-26 关11/关16 双实锤,规则不对称):
    standard 路径查 standard_boss 内层键须有 ≥c95 的(取≥请求的最小键,
    关11 wind[20..80]@90 崩/@80 通);general 路径查 general_boss_variable
    内层键须有 ≤c95 的(成长曲线,关16 gv[100]@90 崩,关5 gv[80]@90 通)。"""

    CEIL = {"boss_s": {"20": "x", "50": "x", "70": "x", "80": "x"}}
    FLOOR = {"boss_g": {"100": "x"}}      # 关16 wind 型:最低 100
    GB = {"boss_g": {"80": "x"}}          # 关16 wind 型:gb 变体最高 80

    def check_std(self, level):
        return rb.check_field_chain("f_std", FD, ZONE, ENEMIES, ZAKOS,
                                    level=level, lv_ceil=self.CEIL, lv_floor=self.FLOOR)

    def check_gen(self, level, floor=None, gb=None):
        return rb.check_field_chain("f_ok", FD, ZONE, ENEMIES, ZAKOS, level=level,
                                    lv_ceil=self.CEIL,
                                    lv_floor=self.FLOOR if floor is None else floor,
                                    lv_gb=self.GB if gb is None else gb)

    def test_standard_level_above_max_key_rejected(self):
        rep = self.check_std(90)                  # wind 型:sb 最高 80 < 90 → 崩
        self.assertFalse(rep["ok"])
        self.assertIn("无法解析", rep["errors"][0])

    def test_standard_level_covered_passes(self):
        self.assertTrue(self.check_std(80)["ok"])
        self.assertTrue(self.check_std(30)["ok"])  # 取≥请求的最小键=50,存在即可

    def test_general_gv_floor_missing_rejected(self):
        # 关16 实锤:gv 只有 [100],敌等级 90 找不到 ≤90 的键 → 崩
        rep = self.check_gen(90)
        self.assertFalse(rep["ok"])
        self.assertIn("无法解析", rep["errors"][0])
        # c95=100 也崩:gv[100] 单档缺低档基准 —— 2026-07-29 关25 火废龙
        # (gv[100]+gb[100])实锤推翻了"补上 gb 就能通"的旧认知,gb 齐全也照崩
        self.assertFalse(self.check_gen(100)["ok"])
        self.assertFalse(self.check_gen(100, gb={"boss_g": {"100": "x"}})["ok"])
        # 真正可用的形态见 test_general_gv_floor_covered_passes(gv 有 <100 的档)

    def test_general_gv_floor_covered_passes(self):
        # 关5 实锤:gv[80]+gb[80] 在 90 级正常;悲魔型 gv[49,100]+gb[100] 同样通
        self.assertTrue(self.check_gen(90, floor={"boss_g": {"80": "x"}},
                                       gb={"boss_g": {"80": "x"}})["ok"])
        self.assertTrue(self.check_gen(90, floor={"boss_g": {"49": "x", "100": "x"}},
                                       gb={"boss_g": {"100": "x"}})["ok"])

    def test_gv_single_100_tier_always_rejected(self):
        """gv 只有 100 单档 = 客户端缺低档基准,任何等级都崩(2026-07-29 火/风废龙实锤);
        对照:gv[80] 单档(水/雷龙)与 gv[20..100] 多档(暗/光龙)均可用。"""
        only100 = {"boss_g": {"100": "x"}}
        gb100 = {"boss_g": {"100": "x"}}
        for level in (80, 90, 100):
            rep = self.check_gen(level, floor=only100, gb=gb100)
            self.assertFalse(rep["ok"], f"lv{level} 应被拒")
        self.assertTrue(self.check_gen(100, floor={"boss_g": {"80": "x"}},
                                       gb={"boss_g": {"80": "x"}})["ok"])
        self.assertTrue(self.check_gen(100, floor={"boss_g": {"20": "x", "100": "x"}},
                                       gb={"boss_g": {"100": "x"}})["ok"])

    def test_general_without_gv_not_gated(self):
        rep = self.check_gen(999, floor={}, gb={})
        self.assertTrue(rep["ok"], rep["errors"])

    def test_no_level_given_skips_check(self):
        self.assertTrue(rb.check_field_chain("f_std", FD, ZONE, ENEMIES, ZAKOS,
                                             lv_ceil=self.CEIL, lv_floor=self.FLOOR)["ok"])

    def test_built_rows_use_per_row_c95(self):
        row_hi = quest_row("f_std"); row_hi[95] = "90"
        row_ok = quest_row("f_std"); row_ok[95] = "80"
        reports = rb.validate_built_rows({"11": row_hi, "4": row_ok},
                                         FD, ZONE, ENEMIES, ZAKOS,
                                         lv_ceil=self.CEIL, lv_floor=self.FLOOR)
        by_round = {r["round"]: r for r in reports}
        self.assertFalse(by_round["11"]["ok"])
        self.assertTrue(by_round["4"]["ok"])


class SpecialBossTableCase(unittest.TestCase):
    """专用表 boss(orochi/kraken/*_sphere/conductor/touyakiren_ceo)= 第四类合法来源。

    实证边界(2026-07-29):orochi_ex 专用表仅 100 档,@敌等级 100 真机通关
    (1.4.234 第3战实验);water_sphere_single 数据形态完全相同,@敌等级 90
    真机 U_50fc52 崩(关13)。⇒ 判据是"有没有 ≤敌等级的档",不是"官方能不能打"。
    """

    ONLY_100 = {"sp_boss": {"100": "x"}}            # orochi_ex / water_sphere 型
    LOW_TIER = {"sp_boss": {"49": "x", "100": "x"}}  # kraken / orochi_all_head_multi 型

    def check(self, table, level=None):
        with mock.patch.object(rb, "_SPECIAL_LV", table):
            return rb.check_field_chain("f_sp", FD, ZONE, ENEMIES, ZAKOS, level=level)

    def test_special_table_boss_not_dangling(self):
        rep = self.check(self.ONLY_100)
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertEqual(rep["bosses"], ["sp_boss"])

        with self.subTest("BossKind must resolve through its exact constructor table"):
            tables = {
                "standard_boss": {},
                "general_boss": {"general_only": {"100": "row"}},
                "orochi": {"orochi_parent": {"100": "row"}},
                "orochi_ex": {"orochi_ex_head": {"100": "row"}},
            }
            wrong_standard = rbb.validate_boss_ref(
                rbb.BossRef(0, "general_only"), 100, tables)
            self.assertFalse(wrong_standard.ok)
            self.assertEqual(wrong_standard.reason, "KIND_CODE_MISMATCH")
            wrong_general = rbb.validate_boss_ref(
                rbb.BossRef(1, "orochi_parent"), 100, tables)
            self.assertFalse(wrong_general.ok)
            self.assertEqual(wrong_general.reason, "KIND_CODE_MISMATCH")
            unsupported_head = rbb.validate_boss_ref(
                rbb.BossRef(5, "orochi_ex_head"), 100, tables)
            self.assertFalse(unsupported_head.ok)
            self.assertEqual(unsupported_head.reason, "SPECIAL_TABLE_UNAUDITED")

        with self.subTest("general constructors require injected level and funnel adapters"):
            missing = rbb.validate_boss_ref(
                rbb.BossRef(1, "general"), 90,
                {"general_boss": {"general": {"100": "row"}}})
            self.assertFalse(missing.ok)
            self.assertEqual(missing.reason, "LEVEL")
            self.assertIn("adapter", missing.detail)
            missing_funnel = rbb.validate_boss_ref(
                rbb.BossRef(0, "standard"), 90,
                {"standard_boss": {"standard": {"100": "row"}},
                 "__level_validator__": lambda _ref, _level, _tables: 100})
            self.assertFalse(missing_funnel.ok)
            self.assertEqual(missing_funnel.reason, "FUNNEL_LEVEL")

            tables = rb.boss_ref_validation_tables(
                standard_boss={"standard": {"80": "row", "100": "row"}},
                general_boss={"general": {"80": "row", "100": "row"}},
                general_boss_variable={"general": {"80": "row", "100": "row"}},
                special_tables={},
                funnel_ok=lambda _code, _level: True,
            )
            for ref in (rbb.BossRef(0, "standard"),
                        rbb.BossRef(1, "general"),
                        rbb.BossRef(8, "general")):
                result = rbb.validate_boss_ref(ref, 90, tables)
                self.assertTrue(result.ok, (ref, result))
                self.assertEqual(result.selected_level, 100)

            blocked_funnel = rb.boss_ref_validation_tables(
                standard_boss={"standard": {"100": "row"}},
                general_boss={}, general_boss_variable={}, special_tables={},
                funnel_ok=lambda _code, _level: False,
            )
            result = rbb.validate_boss_ref(
                rbb.BossRef(0, "standard"), 90, blocked_funnel)
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "FUNNEL_LEVEL")

        with self.subTest("spawned references keep their exact source and level"):
            validation = rb.boss_ref_validation_tables(
                standard_boss={"shadow": {"100": "row"}},
                general_boss={"general": {"100": "row"}},
                general_boss_variable={"general": {"80": "row"}},
                special_tables={}, funnel_ok=lambda _code, _level: True)
            tables = dict(
                validation_tables=validation,
                general_zako={
                    "z80": {"80": "row"}, "z100": {"100": "row"},
                    "shadow": {"100": "row"}},
                general_funnel={"gf": {"100": "row"}},
                standard_funnel={"sf": {"100": "row"}},
            )
            self.assertFalse(rb.validate_spawned_ref(
                "Zako", "z80", 100, **tables).ok)
            self.assertTrue(rb.validate_spawned_ref(
                "Zako", "z100", 100, **tables).ok)
            self.assertFalse(rb.validate_spawned_ref(
                "AlterEgo", "shadow", 100, **tables).ok,
                "AlterEgo 固定 GeneralBossSource，不得由 standard/zako 同码顶替")
            self.assertTrue(rb.validate_spawned_ref(
                "AlterEgo", "general", 100, **tables).ok)
            self.assertTrue(rb.validate_spawned_ref(
                "GeneralBoss", "general", 100, **tables).ok)

        with self.subTest("Orochi kind 3 selects the first tier at or above enemy level"):
            tables = {"orochi": {"orochi_parent": {"100": "row"}}}
            for level in (79, 80, 90, 99, 100):
                result = rbb.validate_boss_ref(
                    rbb.BossRef(3, "orochi_parent"), level, tables)
                self.assertTrue(result.ok, (level, result))
                self.assertEqual(result.selected_level, 100)
            result = rbb.validate_boss_ref(
                rbb.BossRef(3, "orochi_parent"), 101, tables)
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "LEVEL")

        with self.subTest("final chain uses injected exact special table instead of global cache"):
            kind3_wave = rb.cells(wave(bosses=("mod_rogue_orochi6",)))
            kind3_wave[23] = "3"
            local_fd = {"f_clone": "f_clone,terrain_a,z_clone"}
            local_zone = {"z_clone": {"0": rb.join(kind3_wave, False)}}
            validation = rb.boss_ref_validation_tables(
                standard_boss={}, general_boss={}, general_boss_variable={},
                special_tables={
                    "orochi": {"mod_rogue_orochi6": {"100": "row"}},
                }, funnel_ok=lambda _code, _level: True)
            with mock.patch.object(
                    rb, "_SPECIAL_LV",
                    {"mod_rogue_orochi6": {"49": "stale-store-row"}}):
                row79 = quest_row("f_clone")
                row79[95] = "79"
                passed = rb.validate_built_rows(
                    {"6": row79}, local_fd, local_zone, set(), set(),
                    lv_ceil={}, lv_floor={}, lv_gb={},
                    validation_tables=validation)
                self.assertTrue(passed[0]["ok"], passed[0]["errors"])

                row101 = quest_row("f_clone")
                row101[95] = "101"
                rejected = rb.validate_built_rows(
                    {"6": row101}, local_fd, local_zone, set(), set(),
                    lv_ceil={}, lv_floor={}, lv_gb={},
                    validation_tables=validation)
                self.assertFalse(rejected[0]["ok"])
                self.assertTrue(any(
                    "kind=3" in error and "mod_rogue_orochi6" in error
                    for error in rejected[0]["errors"]), rejected[0]["errors"])

        with self.subTest("catalog keeps explicit exclusions as structured reasons"):
            try:
                catalog = rb.build_native_bundle_catalog(enemy_level=100)
            except FileNotFoundError:
                self.skipTest("store 不可用")
            by_code = {}
            for rejection in catalog.rejections:
                for ref in rejection.boss_refs:
                    by_code.setdefault(ref.code, set()).add(rejection.reason)
            for code in rbb.MULTI_ONLY_REGRESSION:
                self.assertIn("NO_SINGLE_FIELD", by_code.get(code, set()), code)
            no_single_codes = {
                ref.code for rejection in catalog.rejections
                if rejection.reason == "NO_SINGLE_FIELD"
                for ref in rejection.boss_refs
            }
            self.assertEqual(no_single_codes, set(rbb.MULTI_ONLY_REGRESSION),
                             "合法 single bundle 的 multi 镜像不得污染 rejection")
            self.assertTrue(any(
                code.startswith("arch_evil") and "C8016" in reasons
                for code, reasons in by_code.items()), by_code)
            self.assertIn(
                "SPECIAL_PHASE_HP_UNSCALABLE", by_code.get("orochi_ex", set()))

        with self.subTest("catalog invokes the exact-slot reference gate after level selection"):
            general = {"boss": {"100": "row"}}
            validation = rb.boss_ref_validation_tables(
                standard_boss={}, general_boss=general,
                general_boss_variable={}, special_tables={},
                funnel_ok=lambda _code, _level: True)
            calls = []

            def reference_gate(field, slots, selected, level):
                calls.append((field, slots, selected, level))
                return rbb.GateResult(False, "REFERENCE", detail="synthetic broken ref")

            catalog = rbb.build_native_bundle_catalog(
                {"f": "f,terrain/path,z"},
                {"z": {"0": wave(bosses=("boss",))}},
                lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]},
                enemy_level=90, validation_tables=validation,
                display_names={"boss": "同名"},
                identity_of=lambda _ref, _selected: {
                    "display": "同名", "model": "model", "actions": ("root",)},
                hp_gate=lambda _slots, _level: rbb.GateResult(True),
                reference_gate=reference_gate, zako_codes=set(),
            )
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][2], (("0", 1, 100),))
            self.assertFalse(catalog.family_ids)
            self.assertEqual(catalog.rejections[0].reason, "REFERENCE")

        with self.subTest("successful reference and zako gates must not skip HP"):
            general = {"boss": {"100": "row"}}
            validation = rb.boss_ref_validation_tables(
                standard_boss={}, general_boss=general,
                general_boss_variable={}, special_tables={},
                funnel_ok=lambda _code, _level: True)
            hp_calls = []

            def hp_gate(slots, level):
                hp_calls.append((slots, level))
                return rbb.GateResult(False, "HP_UNVERIFIED",
                                      detail="synthetic missing HP proof")

            catalog = rbb.build_native_bundle_catalog(
                {"f": "f,terrain/path,z"},
                {"z": {"0": wave(zakos=("zako",), bosses=("boss",))}},
                lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]},
                enemy_level=90, validation_tables=validation,
                display_names={"boss": "同名"},
                identity_of=lambda _ref, _selected: {
                    "display": "同名", "model": "model", "actions": ("root",)},
                hp_gate=hp_gate,
                reference_gate=lambda *_args: rbb.GateResult(True),
                zako_codes={"zako"},
            )
            self.assertEqual(len(hp_calls), 1)
            self.assertFalse(catalog.family_ids)
            self.assertEqual(catalog.rejections[0].reason, "HP_UNVERIFIED")

        with self.subTest("catalog factory accepts fresh in-memory tables without cache"):
            # Deliberately cap the colliding standard source below enemy lv100:
            # kind 1 must still select general@100 rather than being hijacked by
            # code membership in the wrong table.
            shared_standard = {"shared": {"80": "shared,battle/enemy/boss/shared"}}
            shared_general = {"shared": {"100": "shared,同名"}}
            shared_variable = {"shared": {"80": "row"}}
            shared_level = {"shared": "0,hp,1,1,hit_hp_boss,,,,1,1,atk,,,"}
            injected = dict(
                zone={"z": {"0": wave(bosses=("shared",))}},
                sb=shared_standard, gb=shared_general, gv=shared_variable,
                bl=shared_level, gz={}, special_tables={},
                funnel_ok=lambda _code, _level: True,
                display_names={"shared": "同名"},
                terrain_loader=lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]},
                metadata_of=lambda _field_id: {},
            )
            with mock.patch.object(rb.q, "load_table") as load_table, \
                 mock.patch.object(rb, "floor_native_hp",
                                   return_value={"verified": True}) as native_hp:
                empty = rb.build_native_bundle_catalog(fd={}, **injected)
                fresh = rb.build_native_bundle_catalog(
                    fd={"f": "f,terrain/path,z"}, **injected)
            self.assertEqual(empty.scanned_fields, 0)
            self.assertEqual(fresh.scanned_fields, 1)
            self.assertEqual(len(fresh.family_ids), 1)
            self.assertEqual(load_table.call_count, 0,
                             "全套内存表已注入时不得偷偷重读 live store")
            self.assertEqual(native_hp.call_count, 1)
            self.assertEqual(native_hp.call_args.kwargs["standard_boss"], {},
                             "kind 1 即使与 standard 同码也必须走 general HP")
            self.assertIs(native_hp.call_args.kwargs["boss_level"], shared_level)

    def test_absent_from_special_table_still_dangling(self):
        rep = self.check({})
        self.assertFalse(rep["ok"])
        self.assertIn("悬空", rep["errors"][0])

    def test_only_100_tier_needs_level_100(self):
        # water_sphere@90 崩 / orochi_ex@100 通 —— 分界线就在这里
        self.assertFalse(self.check(self.ONLY_100, level=90)["ok"])
        self.assertFalse(self.check(self.ONLY_100, level=80)["ok"])
        self.assertTrue(self.check(self.ONLY_100, level=100)["ok"])

    def test_low_tier_special_boss_passes_below_100(self):
        for level in (49, 80, 100):
            self.assertTrue(self.check(self.LOW_TIER, level=level)["ok"], level)
        self.assertFalse(self.check(self.LOW_TIER, level=20)["ok"])

    def test_resolve_level_sees_special_tiers(self):
        with mock.patch.object(rb, "_SPECIAL_LV", self.ONLY_100):
            # 最强档模式:专用表只有 100,应落 100 而不是 None
            self.assertEqual(rb.resolve_level(["sp_boss"], 80, None, None, None,
                                              prefer_max=True), 100)
            # 就近模式:want=80 无可行档时也要能升到 100
            self.assertEqual(rb.resolve_level(["sp_boss"], 80, None, None, None), 100)

    def test_special_table_bypasses_gv_single_100_rule(self):
        """gv 只有 100 单档=必崩(火废龙),但专用表 100 单档@100 是实测可用的
        —— 两条规则各管各的表,别混用。"""
        with mock.patch.object(rb, "_SPECIAL_LV", self.ONLY_100):
            self.assertTrue(rb.boss_level_ok("sp_boss", 100, None, None, None))
        self.assertFalse(rb.boss_level_ok("boss_g", 100, None,
                                          {"boss_g": {"100": "x"}},
                                          {"boss_g": {"100": "x"}}))


class MainStoryPoolCase(unittest.TestCase):
    """主线boss 池:手挑名单 + 「已有加强版就不要主线版」。

    追忆试炼/单人挑战、极时试炼给的是同一角色的 expert/EX 强化档,主线版留着
    只会白占一个锚位。判据 = 显示名 ∪ 模型族 —— 强化版换了攻击程序签名,
    `_family()` 那套去重认不出它俩是同一个角色。
    """

    def test_model_reads_both_path_shapes(self):
        # general_boss: battle/boss/<族>/…   standard_boss: battle/enemy/boss/<族>…
        try:
            model = rb.boss_model("lich_wind_expert_80")
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(model, "lich")
        self.assertEqual(rb.boss_model("不存在的代号"), "")

    def test_upgraded_source_cats(self):
        self.assertEqual(rb.UPGRADED_SRC_CATS, ("expert_single", "solo_time_attack"))

    def test_allowlist_excludes_blacklisted_and_minions(self):
        # arch_evil 在 C8016 黑名单里,加了也会被门禁剔掉 → 名单里不该有
        self.assertFalse([b for b in rb.MAIN_STORY_BOSSES if b.startswith("arch_evil")])
        # 杂兵提拔族归第2战杂鱼层,不该混进主线池
        for code in ("curse_eye", "dog_soldier", "harpy", "spirit", "killer_whale"):
            self.assertNotIn(code, rb.MAIN_STORY_BOSSES, code)

    def test_admin_human_dropped_for_expert_version(self):
        """实测唯一命中:主线人型「管理者」admin_human vs 追忆
        administrator_light_expert_80/100 —— 同名不同模型,靠名字判出来。"""
        self.assertIn("admin_human", rb.MAIN_STORY_BOSSES)
        try:
            pooled = {b for e in rb.main_story_boss_pool() for b in e["bosses"]}
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertNotIn("admin_human", pooled)
        # 其余名单成员不该被误伤
        for code in ("maou2", "eye_dragon_boss", "epuration_boss_variant_ver_single"):
            self.assertIn(code, pooled, code)


class FunnelLevelCase(unittest.TestCase):
    """第六根因(2026-07-29 关14 真机 U_3be147):技能召唤物 funnel 的等级覆盖。

    堆栈 `GeneralEnemySourceHelper.getSurjectivity ← ActionDslHandler.resolveActionDsl`
    —— 崩在技能 DSL 里的召唤物,不是 zone 里的 boss 本体,前五个根因全查不到。
    `discarded_dragon_dark` 本体 gv/gb 都有 100 档、门禁全绿,但它召的
    `discarded_dragon_dark_funnel` 只有 [20,40,60,80] → 请求 100 崩。
    funnel 走 **ceil**(须有 ≥敌等级的键),与 standard_boss 同款、与 general 相反。
    """

    LV = {"boss_g_funnel": [20, 40, 60, 80],       # 关14 型:封顶 80
          "boss_g_funnel_tower": [100],
          "other_boss_funnel": [20]}               # 别的 boss 的,不该被误伤

    def ok(self, code, level):
        with mock.patch.object(rb, "_FUNNEL_LV", self.LV):
            return rb.boss_funnel_ok(code, level)

    def test_ceil_rule(self):
        self.assertFalse(self.ok("boss_g", 100))   # 无 ≥100 的键
        self.assertFalse(self.ok("boss_g", 90))
        self.assertTrue(self.ok("boss_g", 80))     # 恰好命中
        self.assertTrue(self.ok("boss_g", 30))     # 取 ≥30 的最小键=40

    def test_boss_without_funnel_not_gated(self):
        self.assertTrue(self.ok("boss_s", 100))

    def test_prefix_scoping(self):
        # other_boss_funnel 只封顶 20,但它不以 boss_g 打头,不该拖累 boss_g
        self.assertTrue(self.ok("boss_g", 80))
        self.assertFalse(self.ok("other_boss", 30))

    def test_boss_level_ok_consults_funnel_first(self):
        """本体三表全绿也要被 funnel 否掉 —— 关14 就是这么漏网的。"""
        with mock.patch.object(rb, "_FUNNEL_LV", self.LV), \
             mock.patch.object(rb, "_SPECIAL_LV", {}):
            gvt = {"boss_g": {"20": "x", "40": "x", "60": "x", "100": "x"}}
            gbt = {"boss_g": {"20": "x", "40": "x", "60": "x", "100": "x"}}
            self.assertFalse(rb.boss_level_ok("boss_g", 100, None, gvt, gbt))
            self.assertTrue(rb.boss_level_ok("boss_g", 60, None, gvt, gbt))

    def test_resolve_level_backs_off_to_a_funnel_safe_tier(self):
        with mock.patch.object(rb, "_FUNNEL_LV", self.LV), \
             mock.patch.object(rb, "_SPECIAL_LV", {}):
            gvt = {"boss_g": {"20": "x", "40": "x", "60": "x", "79": "x", "100": "x"}}
            gbt = dict(gvt)
            self.assertEqual(
                rb.resolve_level(["boss_g"], 100, None, gvt, gbt, prefer_max=True), 79)


class BossSeriesCase(unittest.TestCase):
    """元素变体系列整族压成一个去重键(2026-07-29 用户「XX系列收到一起」)。

    六元素变体招式一模一样、只换属性换色,同塔出两个是重复内容 ——
    实测 1.4.237 同塔出了雷龟+暗凤两只精灵兽、1.4.236 出了苍机兵+闪机兵。
    """

    def test_four_series_grouped(self):
        for code, want in (
                ("spirit_beast_thunder", "精灵兽"),
                ("spirit_beast_dark_multi", "精灵兽"),
                ("advent_spirit_beast_water", None),          # 这是 field 不是 boss 代号
                ("variant_empress", "女王"),
                ("variant_empress_light_form2_single", "女王"),
                ("discarded_dragon_dark", "荒龙"),
                ("discarded_dragon_fire_RE", "荒龙"),
                ("steampunk_fire_multi", "机兵"),
                ("steampunk_light_hard_multi", "机兵")):
            self.assertEqual(rb.boss_series_of(code), want, code)

    def test_phenomena_excluded_from_steampunk(self):
        """机工神兵菲诺梅那是决战级独立 boss(塔腰常驻位),并进机兵会让
        常驻位和机兵锚位互相顶掉。"""
        for code in ("steampunk_another", "steampunk_another_multi",
                     "steampunk_another_foom2_multi"):
            self.assertIsNone(rb.boss_series_of(code), code)

    def test_orochi_heads_untouched(self):
        """大蛇各头靠 progs 签名共存(模型名本来就是 orochi),不该被系列规则误伤。"""
        for code in ("orochi_beam_head_single", "orochi_fire_head_multi",
                     "orochi_ex", "orochi_all_head_single"):
            self.assertIsNone(rb.boss_series_of(code), code)

        with self.subTest("catalog discovers exactly three parent variants without head tickets"):
            try:
                catalog = rb.build_native_bundle_catalog(enemy_level=100)
            except FileNotFoundError:
                self.skipTest("store 不可用")
            family_ids = [family_id for family_id, name in catalog.family_names.items()
                          if name == "八岐大蛇"]
            self.assertEqual(len(family_ids), 1)
            family_id = family_ids[0]
            variant_ids = catalog.discovered_variants[family_id]
            self.assertEqual(
                {catalog.variant_names[variant_id] for variant_id in variant_ids},
                {"single", "multi", "multi_plus"},
            )
            bundles = [bundle for variant_id in variant_ids
                       for bundle in catalog.discovered_bundles[variant_id]]
            single_codes = {slot.single.code for bundle in bundles for slot in bundle.slots
                            if slot.single is not None}
            self.assertEqual(single_codes, {
                "orochi_all_head_single", "orochi_all_head_multi",
                "orochi_all_head_multi_plus",
            })
            # parent 自身命名也含 ``all_head``；上面的精确集合才是“八头不加票”
            # 的可靠判据，不能按 ``_head_`` 子串误伤三个合法 parent。
            expected_fields = {
                "orochi_all_head_single": {
                    "main_6_10_4", "main_6_10_4ex", "orochi_all_head_single",
                },
                "orochi_all_head_multi": {
                    "multi_normal_1_20_1", "multi_normal_1_20_2",
                },
                "orochi_all_head_multi_plus": {"multi_normal_1_20_3"},
            }
            actual_fields = {}
            for bundle in bundles:
                code = next(slot.single.code for slot in bundle.slots
                            if slot.single is not None)
                actual_fields.setdefault(code, set()).add(bundle.source_field)
            self.assertEqual(actual_fields, expected_fields)
            self.assertEqual(len(bundles), 6, "六个官方 field 是发现覆盖，不是六张票")

            eligible_variants = catalog.variants.get(family_id, ())
            self.assertEqual(
                {catalog.variant_names[variant_id] for variant_id in eligible_variants},
                {"single", "multi", "multi_plus"},
            )
            eligible_bundles = [bundle for variant_id in eligible_variants
                                for bundle in catalog.bundles[variant_id]]
            self.assertEqual(len(eligible_bundles), 5,
                             "multi 的 _1/_2 是同一 grade chain，只保留最高档票")
            self.assertTrue(all(not bundle.portable for bundle in eligible_bundles))
            self.assertTrue(all(
                bundle.native_only_reason == "ACTION_CLOSURE_UNAUDITED"
                for bundle in eligible_bundles))
            self.assertTrue(any(
                rejection.reason == "SPECIAL_PHASE_HP_UNSCALABLE"
                and any(ref.code == "orochi_ex" for ref in rejection.boss_refs)
                for rejection in catalog.rejections))

            orochi_table = q.load_table(rbb.TABLE_LOGICALS["orochi"])
            hard_heads = set()
            for parent_code in single_codes:
                parent_row = rb.cells(orochi_table[parent_code]["100"])
                hard_heads.update(parent_row[24].split(","))
            blocked_catalog = rb.build_native_bundle_catalog(
                enemy_level=100,
                code_references={
                    "hard": frozenset(hard_heads),
                    "soft": frozenset(),
                    "degraded": False,
                },
            )
            blocked_family_id = next(
                family for family, name in blocked_catalog.family_names.items()
                if name == "八岐大蛇")
            self.assertNotIn(
                blocked_family_id, blocked_catalog.family_ids,
                "九实体 code-reference 无法克隆时不得先进入 eligible catalog")
            self.assertTrue(any(
                rejection.family_id == blocked_family_id
                and rejection.reason == "SPECIAL_HP_CHANNEL_UNSUPPORTED"
                for rejection in blocked_catalog.rejections))

    def test_unrelated_bosses_unaffected(self):
        for code in ("white_tiger_ghost_thunder_single", "kraken_single",
                     "maou2", "chapter12_boss_story"):
            self.assertIsNone(rb.boss_series_of(code), code)

    def test_model_side_match(self):
        # standard_boss 系没有模型路径,代号即模型;general 系两条路都要认
        self.assertEqual(rb.boss_series_of("x", "spirit_beast_fire"), "精灵兽")
        self.assertEqual(rb.boss_series_of("x", "orochi"), None)

    def test_series_caps_at_base_rounds(self):
        """用户指定的原始配额是按 30 层给的:女王2 / 机兵3 / 精灵兽2(荒龙同档 2)。"""
        for series, want in (("精灵兽", 2), ("女王", 2), ("荒龙", 2), ("机兵", 3)):
            self.assertEqual(rb.series_cap(series, 30), want, series)

    def test_series_caps_scale_with_rounds(self):
        """「都可以根据层数动态调整」= 以 30 层为基准线性缩放,下限 1。"""
        self.assertEqual(rb.series_cap("机兵", 60), 6)
        self.assertEqual(rb.series_cap("机兵", 15), 2)
        self.assertEqual(rb.series_cap("精灵兽", 60), 4)
        self.assertEqual(rb.series_cap("精灵兽", 15), 1)
        for n in (2, 5, 8):                       # 小塔不能压到 0
            for s in rb.SERIES_CAPS:
                self.assertGreaterEqual(rb.series_cap(s, n), 1, (s, n))

    def test_non_series_cap_is_one(self):
        """普通 boss 不吃系列配额,恒 1 次(等级/单多人变体同名同灭)。"""
        for name in ("白虎", "不在名单里", ""):
            self.assertEqual(rb.series_cap(name, 30), 1, name)


class FieldBlacklistCase(unittest.TestCase):
    """宝物域等非 boss 战场地:剔出候选池,但门禁不拦(手动钉选仍可用)。"""

    def test_treasure_cave_blocked(self):
        self.assertTrue(rb.field_blocked("treasure_cave_area"))

    def test_normal_field_not_blocked(self):
        for field in ("main_12_10_01", "multi_normal_1_20_4", "tower_dungeon_area_9_9_3"):
            self.assertFalse(rb.field_blocked(field), field)

    def test_blacklist_is_pool_policy_not_chain_gate(self):
        # 黑名单不写进 check_field_chain:钉选一层宝物域仍能通过引用完整性
        self.assertTrue(rb.check_field_chain("f_ok", FD, ZONE, ENEMIES, ZAKOS)["ok"])


class QuestLevelColumnCase(unittest.TestCase):
    """敌等级列 = field 列 − 3(全库 15 类 2903 行实测 100% 命中)。

    旧代码硬编码 cs[95] 只对 rush schema 成立,领主战表 c95 是 HP 修正,
    索拉斯场地因此被读成「lv1560 · 地狱级」。
    """

    def row(self, length, fidx, level):
        cs = [""] * length
        cs[fidx] = "some_field"
        cs[fidx - 3] = str(level)
        return cs

    def test_rush_schema(self):                    # field c98 → 等级 c95
        self.assertEqual(rb.quest_level_of(self.row(132, 98, 80), 98), "80")

    def test_boss_battle_schema(self):             # field c109 → 等级 c106
        cs = self.row(124, 109, 80)
        cs[95] = "1560"                            # HP 修正:旧代码就是读到了它
        self.assertEqual(rb.quest_level_of(cs, 109), "80")
        self.assertEqual(rb.rank_of(rb.quest_level_of(cs, 109)), "超级")

    def test_advent_schema(self):                  # field c115 → 等级 c112
        self.assertEqual(rb.quest_level_of(self.row(132, 115, 100), 115), "100")

    def test_out_of_range_values_rejected(self):
        self.assertEqual(rb.quest_level_of(self.row(124, 109, 1560), 109), "")
        self.assertEqual(rb.quest_level_of(self.row(124, 109, 0), 109), "")

    def test_non_numeric_and_bounds(self):
        cs = self.row(124, 109, 80)
        cs[106] = "(None)"
        self.assertEqual(rb.quest_level_of(cs, 109), "")
        self.assertEqual(rb.quest_level_of(["a", "b"], 1), "")   # fidx-3 < 0


class ScheduleV8Case(unittest.TestCase):
    """骨架 v8:任意层数自适应;小怪房仅第1战固定,第2战 20% 概率。"""

    def sched(self, n, roll=0.99):
        class R:
            def random(self):
                return roll
        return rb.build_schedule(n, R())

    def test_anchors_any_rounds(self):
        for n in (4, 5, 8, 15, 20, 33, 50):
            s = self.sched(n)
            self.assertEqual(s[1], "小怪房", n)
            self.assertEqual(s[n], "终始之龙", n)
            if n >= 5:
                self.assertEqual(s[n - 1], "无幻之宴", n)
            self.assertLessEqual(max(s), n)

    def test_round2_is_minion_boss(self):
        """v11:第2战不再是 20% 概率的第二间小怪房,而是固定「杂鱼boss」层
        (主线里的杂兵提拔族)。热身节奏 = 小怪房 → 杂鱼boss。"""
        for roll in (0.1, 0.9):
            self.assertEqual(self.sched(20, roll=roll).get(2), "杂鱼boss", roll)
        self.assertEqual(self.sched(4).get(2), "杂鱼boss")
        self.assertNotIn("杂鱼boss", set(self.sched(3).values()))   # 3 层塔塞不下

    def test_phenomena_stands_at_mid_tower(self):
        """机工神兵菲诺梅那(地狱级)= 常驻位,落**塔腰** n//2
        (2026-07-29 用户指定:15层→7、30层→15、50层→25);
        末尾留给 无幻之宴 + 终始之龙 的双守门。"""
        for n, want in ((15, 7), (30, 15), (50, 25)):
            self.assertEqual(self.sched(n).get(want), "机工神兵", n)
        for n in (7, 12, 30, 50):
            s = self.sched(n)
            self.assertEqual(s.get(max(3, n // 2)), "机工神兵", n)
            self.assertEqual(s.get(n - 1), "无幻之宴", n)
            self.assertEqual(s.get(n), "终始之龙", n)
        self.assertNotIn("机工神兵", set(self.sched(6).values()))

    def test_haniwa_up_to_three_slots(self):
        """土俑嘉年华一座塔最多 3 个位(用户需求),全塔去重保证是不同变体。"""
        for n, want in ((25, 0), (26, 1), (28, 2), (30, 3), (50, 3)):
            got = sum(1 for v in self.sched(n).values() if v == "土俑嘉年华")
            self.assertEqual(got, want, f"{n} 层塔应有 {want} 个土俑位,实得 {got}")

    def test_main_story_boss_has_a_slot(self):
        for n in (19, 30, 50):
            self.assertIn("主线boss", set(self.sched(n).values()), n)
        self.assertNotIn("主线boss", set(self.sched(18).values()))

    def test_big_tower_has_all_sources(self):
        """v10:6 类高价值来源(战阵之宴/单人挑战/极时试炼/剧情boss/元素试炼/
        土俑嘉年华)以前整类抽不到,现在大塔每类保底一位。"""
        s = self.sched(33)
        labels = set(s.values())
        for lab in ("领主战", "机兵", "降临讨伐", "女帝歼灭者", "无幻之宴", "终始之龙",
                    "战阵之宴", "单人挑战", "极时试炼", "剧情boss", "元素试炼", "土俑嘉年华"):
            self.assertIn(lab, labels, lab)
        # 锚位变多后塔池层相应变少,但仍须占大头(≥1/3),否则塔就不是塔了
        self.assertGreaterEqual(33 - len(s), 11)

    def test_new_sources_gated_by_tower_size(self):
        """小塔不该被新锚位挤爆:8 层塔只有老锚位,27 层才全开。"""
        small = set(self.sched(8).values())
        for lab in ("战阵之宴", "单人挑战", "极时试炼", "剧情boss", "元素试炼", "土俑嘉年华"):
            self.assertNotIn(lab, small, lab)
        self.assertIn("战阵之宴", set(self.sched(16).values()))
        self.assertIn("土俑嘉年华", set(self.sched(27).values()))

    def test_tower_pool_reserve(self):
        """锚位预算:塔池(崩坏域)是底色,**至少留 1/5 楼层**给塔层/拼接层。
        10 层塔曾被锚位吃满(一层崩坏域都不剩),预算就是为这个加的。"""
        for n in (5, 8, 10, 15, 20, 25, 30, 50, 98):
            free = n - len(self.sched(n))
            self.assertGreaterEqual(free, max(1, round(n * 0.2)) if n >= 8 else 1,
                                    f"{n} 层塔只剩 {free} 层塔池")

    def test_small_tower_no_out_of_range(self):
        s = self.sched(8)
        self.assertTrue(all(1 <= r <= 8 for r in s))

    def test_lord_slots_scale_with_tower_size(self):
        """v9:领主战池 143 个场地却只给 1 个位 → 单塔抽中特定 boss ≈5.6%。
        大塔多开位(<15 → 1、15-24 → 2、≥25 → 3),全塔去重保证不重样。"""
        for n, want in ((8, 1), (16, 1), (17, 2), (23, 2), (24, 3), (30, 3)):
            got = sum(1 for lab in self.sched(n).values() if lab == "领主战")
            self.assertEqual(got, want, f"{n} 层应有 {want} 个领主战位,实得 {got}")

    def test_lord_slots_do_not_evict_anchors(self):
        labels = list(self.sched(30).values())
        for lab in ("小怪房", "无幻之宴", "终始之龙", "机兵", "降临讨伐", "女帝歼灭者"):
            self.assertIn(lab, labels, lab)


class QuestElementEnumCase(unittest.TestCase):
    """quest c69(battle_recommended_element)与 general_boss c0 是**两套枚举**。

    c69 = 0风 1火 2水 3雷 4暗 5光(2026-07-29 测绘:advent 六属性精灵兽/六属性废龙
    交叉验证,再与 ranking 五元素试炼、carnival 六色土俑、solo_time_attack 六色
    试炼、expert_single 三例全部自洽);general_boss c0 = 0继承 1火 2水 3雷 4风 5光 6暗。
    以前 boss_element_map 按 kind-1 换算 → 六个元素全错,写进 c69 就是错元素,
    正是 C8016 的触发路径。
    """

    def test_kind_to_quest_elem_table(self):
        want = {1: 1, 2: 2, 3: 3, 4: 0, 5: 5, 6: 4}   # 火水雷风光暗
        self.assertEqual(rb.GB_KIND_TO_QUEST_ELEM, want)

    def test_cn_labels_follow_quest_enum(self):
        self.assertEqual(rb.QUEST_ELEM_CN,
                         ["风", "火", "水", "雷", "暗", "光"])

    def test_round_trip_每个元素都能对上中文(self):
        kind_cn = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗"}
        for kind, cn in kind_cn.items():
            self.assertEqual(rb.QUEST_ELEM_CN[rb.GB_KIND_TO_QUEST_ELEM[kind]], cn, kind)

    def test_inherit_kind_has_no_fixed_element(self):
        self.assertIsNone(rb.GB_KIND_TO_QUEST_ELEM.get(0))
        self.assertIsNone(rb.GB_KIND_TO_QUEST_ELEM.get(7))   # Colorless


class FeaturedWeightCase(unittest.TestCase):
    """精选 boss 加权:命中前缀的候选重复 N 份,概率 ×N(不是硬钉)。"""

    PREF = ("orochi_", "kraken_")

    def test_prefix_match(self):
        self.assertTrue(rb.is_featured(["orochi_ex"], self.PREF))
        self.assertTrue(rb.is_featured(["zk1", "kraken_multi"], self.PREF))
        self.assertFalse(rb.is_featured(["boss_g"], self.PREF))
        self.assertFalse(rb.is_featured([], self.PREF))

    def test_empty_list_means_no_weighting(self):
        self.assertFalse(rb.is_featured(["orochi_ex"], ()))

    def test_weight_floor_is_one(self):
        with mock.patch("builtins.open", mock.mock_open(
                read_data='{"featured_bosses": ["orochi_"], "featured_weight": 0}')):
            self.assertEqual(rb.load_featured_bosses(), (("orochi_",), 1))

    def test_missing_config_is_inert(self):
        with mock.patch("builtins.open", side_effect=OSError):
            self.assertEqual(rb.load_featured_bosses()[0], ())


class CollapseGradesCase(unittest.TestCase):
    """难度分级去重:同 boss(显示名)只留尾号最大的版本(2026-07-27 索拉斯连出两次)。"""

    NAMES = {"solas_1": "索拉斯", "solas_x": "索拉斯", "shark_a": "鲨鱼"}

    def name_of(self, bosses):
        return {self.NAMES.get(b, b) for b in bosses}

    def test_keeps_highest_grade_only(self):
        entries = [
            {"field": "multi_normal_1_16_1", "bosses": ["solas_1"]},
            {"field": "multi_normal_1_16_4", "bosses": ["solas_x"]},   # 超级+
            {"field": "multi_normal_1_16_2", "bosses": ["solas_1"]},
            {"field": "shark_bay", "bosses": ["shark_a"]},
        ]
        out = rb.collapse_grades(entries, self.name_of)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["field"], "multi_normal_1_16_4")       # 索拉斯只剩最高档
        self.assertEqual(out[1]["field"], "shark_bay")

        with self.subTest("family draw is not weighted by its bundle count"):
            def bundle(family_id, variant_id, index, *, field=None, source_level=0,
                       terrain=None, zone_rows=()):
                return rbb.NativeBossBundle(
                    family_id=family_id, family_name=family_id,
                    variant_id=variant_id, variant_name=variant_id,
                    source_field=field or f"f{index}", source_zone=f"z{index}",
                    terrain_logical=terrain or f"terrain/{index}", active_layers=("0",),
                    slots=(rbb.ActiveBossSlot(
                        "0", 1, 0, rbb.BossRef(1, f"boss{index}"),
                        rbb.BossRef(1, f"boss{index}")),),
                    bgm=None, thumbnail="", source_category="test",
                    source_level=source_level, active_zone_rows=zone_rows,
                )

            family_a = rbb.stable_id("family", {"name": "A", "model": "a"})
            family_b = rbb.stable_id("family", {"name": "B", "model": "b"})
            variant_a = rbb.stable_id("variant", {"family": family_a, "shape": "a"})
            variant_b = rbb.stable_id("variant", {"family": family_b, "shape": "b"})
            catalog = rbb.catalog_from_bundles(tuple(
                [bundle(family_a, variant_a, index) for index in range(9)]
                + [bundle(family_b, variant_b, 9)]))

            class RecordingRng:
                def __init__(self):
                    self.ranges = []

                def randrange(self, size):
                    self.ranges.append(size)
                    return 0

            rng = RecordingRng()
            selection = rbb.choose_family_variant_bundle(catalog, rng, policy=None)
            self.assertEqual(rng.ranges[0], 2)
            self.assertEqual(rng.ranges[1], len(catalog.variants[selection.family_id]))
            self.assertEqual(rng.ranges[2], len(catalog.bundles[selection.variant_id]))
            self.assertNotIn("#", selection.family_id)
            again = rbb.choose_family_variant_bundle(
                catalog, RecordingRng(), policy=None)
            self.assertEqual(selection.family_id, again.family_id)
            self.assertEqual(
                rbb.stable_id("family", {"name": "é"}),
                rbb.stable_id("family", {"name": "e\u0301"}),
                "stable ID 必须先做 Unicode NFC",
            )
            self.assertEqual(len(selection.family_id.rsplit("_", 1)[1]), 64)

            solo = rbb.catalog_from_bundles((bundle(family_b, variant_b, 10),))
            solo_rng = RecordingRng()
            rbb.choose_family_variant_bundle(solo, solo_rng, policy=None)
            self.assertEqual(solo_rng.ranges, [1, 1, 1],
                             "单候选层也必须保留三次 RNG 调用")

            empty = rbb.catalog_from_bundles(())
            empty_rng = RecordingRng()
            with self.assertRaisesRegex(ValueError, "empty catalog level"):
                rbb.choose_family_variant_bundle(empty, empty_rng, policy=None)
            self.assertEqual(empty_rng.ranges, [], "空 catalog 不得消耗 RNG")

            variant_c = rbb.stable_id("variant", {"family": family_a, "shape": "c"})
            graded = rbb.catalog_from_bundles((
                bundle(family_a, variant_a, 20, field="multi_normal_test_1", source_level=80,
                       terrain="terrain/grade", zone_rows=(("0", ("same",)),)),
                bundle(family_a, variant_a, 20, field="multi_normal_test_2", source_level=90,
                       terrain="terrain/grade", zone_rows=(("0", ("same",)),)),
                bundle(family_a, variant_a, 20, field="multi_normal_test_3", source_level=100,
                       terrain="terrain/grade", zone_rows=(("0", ("same",)),)),
                bundle(family_a, variant_c, 20, field="multi_normal_test_4", source_level=100,
                       terrain="terrain/grade", zone_rows=(("0", ("same",)),)),
            ))
            self.assertEqual(
                [item.source_field for item in graded.bundles[variant_a]],
                ["multi_normal_test_3"], "同 variant 的编号难度只留最高档")
            self.assertEqual(
                [item.source_field for item in graded.bundles[variant_c]],
                ["multi_normal_test_4"], "机制不同的 variant 不得被难度收敛误删")
            self.assertEqual(len(graded.discovered_bundles[variant_a]), 3,
                             "discovered 审计仍须保留三条原生来源")

        with self.subTest("field placement belongs to bundle, not variant identity"):
            validation = rb.boss_ref_validation_tables(
                standard_boss={}, general_boss={"boss": {"100": "row"}},
                general_boss_variable={}, special_tables={},
                funnel_ok=lambda _code, _level: True)
            trees = {
                "terrain/zero": {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]},
                "terrain/one": {
                    "layers": [{"type": "objectgroup", "name": "1", "objects": []}]},
            }
            placement = rbb.build_native_bundle_catalog(
                {"place_zero": "place_zero,terrain/zero,z0",
                 "place_one": "place_one,terrain/one,z1"},
                {"z0": {"0": wave(bosses=("boss",))},
                 "z1": {"1": wave(bosses=("boss",))}},
                trees.__getitem__, enemy_level=100,
                validation_tables=validation, display_names={"boss": "同名"},
                identity_of=lambda _ref, _selected: {
                    "display": "同名", "model": "same", "actions": ("root",)},
                hp_gate=lambda *_args: rbb.GateResult(True),
                reference_gate=lambda *_args: rbb.GateResult(True),
                zako_codes=set(),
            )
            self.assertEqual(len(placement.family_ids), 1)
            family_id = placement.family_ids[0]
            self.assertEqual(len(placement.variants[family_id]), 1)
            variant_id = placement.variants[family_id][0]
            self.assertEqual(len(placement.bundles[variant_id]), 2)

        with self.subTest("portable verdict requires source self-compatibility"):
            validation = rb.boss_ref_validation_tables(
                standard_boss={}, general_boss={"boss": {"100": "row"}},
                general_boss_variable={}, special_tables={},
                funnel_ok=lambda _code, _level: True)
            self_check = rbb.build_native_bundle_catalog(
                {"self": "self,terrain/self,z"},
                {"z": {"0": wave(bosses=("boss",))}},
                lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0", "objects": []}]},
                enemy_level=100, validation_tables=validation,
                display_names={"boss": "同名"},
                identity_of=lambda _ref, _selected: {
                    "display": "同名", "model": "same", "actions": ("root",)},
                hp_gate=lambda *_args: rbb.GateResult(True),
                reference_gate=lambda *_args: rbb.GateResult(True),
                zako_codes=set(),
                portability_gate=lambda _bundle: rbb.RequirementResult(
                    True, rbb.BossTerrainRequirements(layers=(
                        rbb.LayerTerrainRequirements(
                            "0", custom_positions=("missing",)),))),
            )
            self_bundle = next(
                item for values in self_check.bundles.values() for item in values)
            self.assertFalse(self_bundle.portable)
            self.assertEqual(
                self_bundle.native_only_reason, "CUSTOM_POSITION_MISSING")

        with self.subTest("display alone defines family and metadata remains aliases"):
            try:
                real = rb.build_native_bundle_catalog(enemy_level=100)
            except FileNotFoundError:
                self.skipTest("store 不可用")
            by_name = {}
            for family_id, name in real.family_names.items():
                by_name.setdefault(name, set()).add(family_id)
            self.assertFalse({name: ids for name, ids in by_name.items() if len(ids) > 1})
            discovered = [bundle for values in real.discovered_bundles.values()
                          for bundle in values]
            aliased = [bundle for bundle in discovered if len(bundle.metadata_aliases) > 1]
            self.assertTrue(aliased, "多 quest field 的 metadata aliases 不应被压没")
            self.assertTrue(any(bundle.bgm for bundle in discovered),
                            "官方裸 BGM token 不得因缺少 bgm/ 前缀而全部丢失")
            representative = [bundle for bundle in discovered
                              if bundle.source_field == "multi_normal_1_1_1"]
            self.assertTrue(representative)
            self.assertTrue(any(bundle.bgm == "grass_battle_middle_boss_zone2"
                                for bundle in representative))
            eligible_fields = {bundle.source_field for values in real.bundles.values()
                               for bundle in values}
            self.assertTrue({"valen_20_08", "valen_20_09", "valen_20_10"}
                            <= eligible_fields,
                            "不同 terrain/BGM 的剧情场不得按尾号误当难度档")
            self.assertTrue({"main_4_6_2", "main_4_6_3", "main_4_6_5"}
                            <= eligible_fields)
            self.assertEqual(
                eligible_fields & {"multi_normal_1_1_1", "multi_normal_1_1_2",
                                   "multi_normal_1_1_3", "multi_normal_1_1_4"},
                {"multi_normal_1_1_4"},
                "同 terrain/zone/variant 的官方编号档必须按尾号留最高档")
            self.assertEqual(
                eligible_fields & {"multi_normal_1_13_1", "multi_normal_1_13_2",
                                   "multi_normal_1_13_3"},
                {"multi_normal_1_13_1", "multi_normal_1_13_2",
                 "multi_normal_1_13_3"},
                "A-prime 必须保留命中难度 schema 但 terrain 不同的完整原生包",
            )
            self.assertEqual(
                eligible_fields & {
                    "advent_spirit_beast_dark_1", "advent_spirit_beast_dark_2",
                    "advent_spirit_beast_dark_3", "advent_spirit_beast_dark_4",
                    "advent_spirit_beast_dark_5",
                },
                {"advent_spirit_beast_dark_5"},
                "advent metadata 必须按等级选 lv100，而不是盲按尾号",
            )
            self.assertEqual(
                eligible_fields & {
                    "advent_spirit_beast_wind_1", "advent_spirit_beast_wind_2",
                    "advent_spirit_beast_wind_3", "advent_spirit_beast_wind_4",
                },
                {"advent_spirit_beast_wind_1"},
                "advent metadata 可证明 _1 才是最高等级档",
            )
            for bundle in aliased[:20]:
                category, bgm, thumbnail = bundle.metadata_aliases[0]
                self.assertEqual(bundle.source_category, category)
                self.assertEqual(bundle.bgm or "", bgm)
                self.assertEqual(bundle.thumbnail, thumbnail)
            coverage = rbb.audit_bundle_coverage(real)
            family_coverage = coverage["family_coverage"]
            self.assertEqual(
                family_coverage["complete"] + family_coverage["partial"]
                + family_coverage["rejected"],
                coverage["discovered"]["families"])
            for key in ("fields", "families", "variants", "bundles", "codes"):
                self.assertIn(key, coverage["rejected"])
            eligible_bundles = [bundle for values in real.bundles.values()
                                for bundle in values]
            self.assertTrue(eligible_bundles)
            portable = [bundle for bundle in eligible_bundles if bundle.portable]
            native_only = [bundle for bundle in eligible_bundles
                           if not bundle.portable]
            self.assertTrue(portable, "Task3 后真实 catalog 至少须有一个可审闭包")
            self.assertFalse([
                bundle.source_field for bundle in portable
                if any(slot.single is not None and slot.single.kind == 0
                       for slot in bundle.slots)],
                "Task3 v1 未完整证明 Standard ESDL state/pre-action schema，kind0 不得 portable")
            self.assertTrue(all(
                bundle.terrain_requirements is not None
                and bundle.native_only_reason is None
                for bundle in portable))
            native_reasons = {
                bundle.native_only_reason for bundle in native_only}
            self.assertLessEqual(
                native_reasons,
                {"ACTION_CLOSURE_UNAUDITED", "CUSTOM_POSITION_MISSING"})
            rejection_reasons = {
                rejection.reason for rejection in real.rejections}
            self.assertFalse(
                native_reasons & rejection_reasons,
                "portability 门禁结果不得污染 native rejection")
            for reason in native_reasons:
                self.assertEqual(
                    coverage["native_only"].get(reason, 0),
                    sum(bundle.native_only_reason == reason
                        for bundle in native_only))
            strict, safe = rb.load_transplant_policy()
            real_pair = next((
                (source, target)
                for source in portable
                if all(slot.single is None or slot.single.code in safe
                       for slot in source.slots)
                for target in eligible_bundles
                if source.source_field != target.source_field
                and rbb.terrain_compatibility(
                    source, target, source.terrain_requirements,
                    strict_transplant=strict,
                    transplant_safe=safe).ok
            ), None)
            self.assertIsNotNone(real_pair,
                                 "静态闭包 + strict_transplant 后至少应有一对真实可移植包")

    def test_different_bosses_same_prefix_kept(self):
        entries = [
            {"field": "zone_area_1", "bosses": ["solas_1"]},
            {"field": "zone_area_2", "bosses": ["shark_a"]},
        ]
        self.assertEqual(len(rb.collapse_grades(entries, self.name_of)), 2)


class BossHistoryCase(unittest.TestCase):
    """boss 出场历史:近 3 座塔轮转记账,抽取端 80% 降权(prefer_fresh 在 main 闭包)。"""

    def test_rotation_caps_at_three_towers(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with mock.patch.object(rb, "BOSS_HISTORY_PATH",
                               str(Path(temp.name) / "h.json")):
            for tower in (["a", "b"], ["c"], ["d"], ["e", "e", "a"]):
                rb.save_boss_history(tower)
            history = rb.load_boss_history()
        self.assertEqual(history, [["a", "e"], ["d"], ["c"]])   # 去重排序+最多3座

    def test_missing_file_is_empty(self):
        with mock.patch.object(rb, "BOSS_HISTORY_PATH", "Z:/no/such/file.json"):
            self.assertEqual(rb.load_boss_history(), [])


class DifficultyPresetCase(unittest.TestCase):
    """端点式难度曲线:任意层数起终点恒定;诅咒档四类型。"""

    def test_endpoint_invariant_across_rounds(self):
        """不变式:起终点与层数无关(8 层和 33 层同样的起终难度)。
        端点具体数值读 DIFF_PRESETS,调难度时不用改这条。"""
        for diff, (hp_a, hp_b, atk_a, atk_b, _t) in rb.DIFF_PRESETS.items():
            for n in (8, 20, 33):
                hp0, hpg, atk0, atkg = rb.difficulty_curve(diff, n)
                self.assertAlmostEqual(hp0, hp_a, places=6, msg=(diff, n))
                self.assertAlmostEqual(hp0 * hpg ** (n - 1), hp_b, places=6, msg=(diff, n))
                self.assertAlmostEqual(atk0 * atkg ** (n - 1), atk_b, places=6, msg=(diff, n))

    def test_curve_stays_inside_the_official_band(self):
        """2026-07-29 用户「不要太高或者太低」+ 指定参照『无幻之宴/机工神兵』。

        查官方原值:这两个 boss 在 lv100 的 quest 修正是**全 1.0**(菲诺梅那在降临
        讨伐甚至 0.7),难度全来自 enemy_level + 自带数值。而旧曲线给同一场战斗写的是
        无幻之宴 hp×40.02 / atk×16.29 —— 官方战斗的 40 倍血。
        新口径:**×1.0 ≈ 无幻之宴/菲诺梅那 那一档**,曲线只负责深度推进。
        ⚠ 这两个是 standard 系(不参与归一),拿到的就是裸曲线值,所以端点本身必须压。
        """
        for diff in ("easy", "normal", "hell", "gradient"):
            hp0, hpg, atk0, atkg = rb.difficulty_curve(diff, 30)
            hp_end, atk_end = hp0 * hpg ** 29, atk0 * atkg ** 29
            # 末层不得超过官方 lv100 的 atk 天花板(6.63,且那是全库孤例)
            # 端点求幂有浮点残差(4.0 会算成 4.00000000000001),留 1e-9 容差
            self.assertLessEqual(atk_end, 3.5 + 1e-9, f"{diff} atk 终点越界")
            # 血量终点参照:无幻之宴/菲诺梅那 官方 ×1.0,末层最多几倍,不是几十倍
            self.assertLessEqual(hp_end, 4.0 + 1e-9, f"{diff} hp 终点越界")
            self.assertGreater(hp_end, hp0, f"{diff} 曲线必须递增")
            if diff == "hell":
                self.assertAlmostEqual(atk_end, atk0, places=9,
                                       msg="hell 攻击曲线应保持平坦")
            else:
                self.assertGreater(atk_end, atk0, f"{diff} 曲线必须递增")

    def test_atk_ceiling_guards_curse_stacking(self):
        """诅咒叠乘 + 工坊 ×1.15 会把 atk 冲高,硬上限兜底。

        2026-08-05 硬上限改为 1.5；兼容常量不得再保留旧 6.6 门槛。"""
        self.assertEqual(rb.ATK_MULT_CEILING, 1.5)
        self.assertLessEqual(rb.ATK_COMBO_CAP, rb.ATK_MULT_CEILING)
        self.assertLessEqual(rb.NOBASE_ATK_CAP, rb.ATK_COMBO_CAP)

    def test_easy_below_hell(self):
        e = rb.difficulty_curve("easy", 20)
        h = rb.difficulty_curve("hell", 20)
        self.assertLess(e[0] * e[1] ** 19, h[0] * h[1] ** 19)

    def test_uniform_tiers(self):
        self.assertEqual(rb.tier_for_round("hell", 1, 33), "hell")
        self.assertEqual(rb.tier_for_round("hell", 33, 33), "hell")
        self.assertEqual(rb.tier_for_round("easy", 33, 33), "off")

    def test_gradient_escalates(self):
        n = 32
        tiers = [rb.tier_for_round("gradient", r, n) for r in (4, 12, 20, 30)]
        self.assertEqual(tiers, ["off", "standard", "abyss", "hell"])


class EnvFieldGateCase(unittest.TestCase):
    """环境场(刮风/重力)——2026-07-29 真机实验通过后已放行随机池。

    实验:1.4.238 钉第3战刮风 / 第4战重力(第5战淹水=已验证对照组),用户实测
    「第三战刮风正常出现,第四关场地内有重力效果」⇒ 两个新命令 resolver 都能吃。
    放行依据不止那两个样本:73 项全单命令、零资产路径参数、重力定位用语义锚
    (Top/Left/Center/Right)+相对偏移而非烤死坐标。
    CreateTornado 仍黑名单——它带绝对坐标 + 外部特效路径,本次结论**不迁移**。
    """

    def test_env_released_to_random_pool(self):
        self.assertIn("环境", rb.FIELD_RANDOM_CATS)
        for cat in ("加成", "诅咒", "场地", "领域"):
            self.assertIn(cat, rb.FIELD_RANDOM_CATS)

    def test_random_curse_can_pick_env(self):
        menu = [("狂风领域", "p_wind", "全场刮风·推球", "环境")]

        class R:
            def randrange(self, n):
                return 0

            def sample(self, seq, k):
                return list(seq)[:k]

            def random(self):
                return 0.99

        with mock.patch.object(rb, "_FIELD_MENU_ALL", menu):
            caster = next(c for c in rb._curse_pool(2, R()) if c.get("caster"))
            self.assertEqual(caster["caster"][1], "p_wind")

    def test_field_pick_is_uniform_per_entry(self):
        """每个条目一票。曾按 √条目数 在分类间加权,理由是"刮风/重力只是数值变体、
        观感就两种"——用户当场纠正:观感不一样(强度跨 20 倍、时长跨 10 倍、
        重力四种锚点)。不替玩家判断"这些看起来都一样"。"""
        menu = ([("w", f"p_wind{i}", "刮风", "环境") for i in range(70)]
                + [("b", "p_buff", "加成", "加成")])
        import random as _r
        rng = _r.Random(12345)
        picks = [rb.pick_field_program(menu, rng) for _ in range(4000)]
        env = sum(1 for p in picks if p[3] == "环境") / len(picks)
        self.assertGreater(env, 0.95, f"70/71 条目应约 98.6%,实得 {env:.1%}")
        self.assertGreater(len({p[1] for p in picks}), 60)   # 变体都抽得到

    def test_env_notes_distinguish_variants(self):
        """73 项环境场的 note 必须能分出变体 —— 全写「全场刮风·推球」的话,
        计划表和图鉴里根本看不出抽到的是微风还是狂风。"""
        env = [m for m in rb.field_menu_all() if len(m) > 3 and m[3] == "环境"]
        if not env:
            self.skipTest("rogue_field_menu.json 未生成")
        notes = {m[2] for m in env}
        self.assertGreater(len(notes), 20, f"note 只有 {len(notes)} 种,分不出变体")
        self.assertTrue(any("微风" in n for n in notes))
        self.assertTrue(any("狂风" in n for n in notes))
        self.assertTrue(any("中心" in n or "左侧" in n for n in notes))

    def test_unknown_cat_still_filtered(self):
        """筛子还在:没登记的分类(将来新命令)默认进不了随机池。"""
        menu = [("龙卷领域", "p_tornado", "龙卷", "未验证"),
                ("连击法阵", "p_combo", "连击加成领域", "加成")]

        class R:
            def randrange(self, n):
                return 0

            def sample(self, seq, k):
                return list(seq)[:k]

            def random(self):
                return 0.99

        with mock.patch.object(rb, "_FIELD_MENU_ALL", menu):
            caster = next(c for c in rb._curse_pool(2, R()) if c.get("caster"))
            self.assertEqual(caster["caster"][1], "p_combo")

    def test_tornado_stays_blacklisted(self):
        import wf_field_catalog as fc
        self.assertIn("CreateTornado", fc.DIRTY_CMDS)
        self.assertEqual(fc.ENV_CMDS,
                         {"CreateWindAttack", "CreateGravitationalField"})
        self.assertEqual(fc.SCAN_CMDS, fc.FIELD_CMDS | fc.ENV_CMDS)


class StatNormalizeCase(unittest.TestCase):
    """怪物基础数值归一化(2026-07-29 用户「有些副本数值显著低于其他副本」)。

    `boss_level` 行 c2×c3 = 基数,c4 = 修正曲线名。基数只在**同曲线组内**可比,
    但实测同一条 `hit_hp_boss` 组 230 个 boss 极差 **15485×**
    (白虎 460 vs 闪火必杀巨土俑 114000 差 250 倍),组内归一就能吃掉绝大部分。
    ⚠ standard 系 boss 的行只有 [名字, 资产路径] —— **没有任何数值**,
      血攻烤在客户端资产二进制里,读不到也改不了,归一化对它们返回 1.0。
    """

    HP_MED = {"c_boss": 1000.0}
    ATK_MED = {"c_atk": 20.0}
    STATS = {
        "weak": {"hp": 250.0, "hpc": "c_boss", "atk": 5.0, "atkc": "c_atk"},
        "mid": {"hp": 1000.0, "hpc": "c_boss", "atk": 20.0, "atkc": "c_atk"},
        "fat": {"hp": 100000.0, "hpc": "c_boss", "atk": 80.0, "atkc": "c_atk"},
    }

    def norm(self, bosses, lo=0.25, hi=4.0):
        # 同时把曲线表清空:让 true_stat 走"曲线未知"分支,回落到裸基数 + 曲线名分组,
        # 这样断言只测归一逻辑本身,不受真实曲线数值影响
        with mock.patch.object(rb, "_BASE_STATS", self.STATS), \
             mock.patch.object(rb, "_CURVES", {"hp": {}, "atk": {}}):
            return rb.stat_normalize(bosses, self.HP_MED, self.ATK_MED, lo, hi)

    def test_weak_boss_gets_boosted(self):
        self.assertAlmostEqual(self.norm(["weak"])[0], 4.0)      # 1000/250=4,不触顶

    def test_fat_boss_gets_cut_to_the_clamp(self):
        self.assertAlmostEqual(self.norm(["fat"])[0], 0.25)      # 1000/100000 触底

    def test_median_boss_untouched(self):
        self.assertEqual(self.norm(["mid"]), (1.0, 1.0))

    def test_clamp_is_respected(self):
        self.assertAlmostEqual(self.norm(["fat"], lo=0.1)[0], 0.1)
        self.assertAlmostEqual(self.norm(["weak"], hi=2.0)[0], 2.0)

    def test_hp_can_open_its_ceiling_without_opening_the_atk_ceiling(self):
        """任务 C 按族抬 general HP；攻击仍沿用旧 10× 安全上限。"""
        stats = {"tiny": {"hp": 1.0, "hpc": "c_boss",
                           "atk": 0.02, "atkc": "c_atk"}}
        with mock.patch.object(rb, "_BASE_STATS", stats), \
             mock.patch.object(rb, "_CURVES", {"hp": {}, "atk": {}}):
            got = rb.stat_normalize(
                ["tiny"], self.HP_MED, self.ATK_MED, 0.1, 100.0,
                hi_by_kind={"atk": 10.0})
        self.assertEqual(got, (100.0, 10.0))

    def test_unknown_boss_is_left_alone(self):
        """standard 系没有 boss_level 条目 —— 无数据不瞎补。"""
        self.assertEqual(self.norm(["chapter12_boss_story"]), (1.0, 1.0))
        self.assertEqual(self.norm([]), (1.0, 1.0))

    def test_multi_boss_floor_uses_the_fattest(self):
        """一层多个 boss 时按血最厚的算 —— 它决定这层的手感。"""
        self.assertAlmostEqual(self.norm(["weak", "fat"])[0], 0.25)

    def test_compression_defaults_keep_atk_variance(self):
        """血量全拉平、**伤害只压一半** —— 用户 2026-07-29:
        「不要太高或者太低,可以高低有别」。一刀切归一会把全池 atk 的 86× 跨度
        压到 1.9×,boss 之间"这个打得疼"的手感就没了。"""
        self.assertEqual(rb.COMPRESS_DEFAULT["hp"], 1.0)
        self.assertLess(rb.COMPRESS_DEFAULT["atk"], 1.0)
        self.assertGreater(rb.COMPRESS_DEFAULT["atk"], 0.3)

    def test_compress_exponent_semantics(self):
        """指数 0 = 完全不动;1 = 完全拉平到锚点;中间按幂次压缩。"""
        med = {"*": 100.0}
        with mock.patch.object(rb, "_BASE_STATS",
                               {"x": {"hp": 10.0, "hpc": "c", "atk": 10.0, "atkc": "c"}}), \
             mock.patch.object(rb, "_CURVES", {"hp": {}, "atk": {}}):
            med2 = {"c": 100.0}
            f0 = rb.stat_normalize(["x"], med2, med2, 0.01, 100, 100, {"hp": 0.0, "atk": 0.0})
            f1 = rb.stat_normalize(["x"], med2, med2, 0.01, 100, 100, {"hp": 1.0, "atk": 1.0})
            fh = rb.stat_normalize(["x"], med2, med2, 0.01, 100, 100, {"hp": 0.5, "atk": 0.5})
            self.assertEqual(f0, (1.0, 1.0))                 # 不动
            self.assertAlmostEqual(f1[0], 10.0)              # 100/10 全补
            self.assertAlmostEqual(fh[0], 10.0 ** 0.5, 5)    # 幂次压缩

    def test_growth_curves_decode(self):
        """曲线容器逆向(2026-07-29):中间节点带 4 字节长度前缀,**叶子是裸 zlib 流**。
        钉住三条 hp 曲线在 lv100 的值 —— 解析器再改坏这里会立刻炸。"""
        c = rb.growth_curves()
        if not c.get("hp"):
            self.skipTest("store 不可用")
        self.assertEqual(set(c["hp"]), {"hit_hp_correction_non_element",
                                        "hit_hp_boss", "hit_hp_funnel"})
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_boss", 100), 78.271875, 4)
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_correction_non_element", 100),
                               31.656625, 4)
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_funnel", 100), 12.808125, 4)
        # **上取整**:取第一个 ≥level 的档 —— 客户端 GeneralEnemySourceHelper
        # .getSurjectivity:23 `if(key >= level) return`,取不到就 throw(=U_50fc52)。
        # 2026-08-04 修:原来这里钉的是下取整(80→79档=17.247),把 bug 一起钉住了;
        # 方向反了会让 lv80 层的归一化补偿虚高 3.038×、lv90 虚高 1.292×,
        # 正好抵消 hell 预设 0.9→4.0 的爬坡 ⇒ 难度曲线整条失效。别再改回去。
        # hit_hp_boss 键位 = [9,19,29,39,49,59,69,79,89,99,100]
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_boss", 79), 17.24699977, 4)
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_boss", 80), 52.3908, 4)
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_boss", 90), 67.70176875, 4)
        # 超出最大档 = 客户端 throw 的那种情况,这里以 None 表达,交调用方按"查不到"处理
        self.assertIsNone(rb.curve_value("hp", "hit_hp_boss", 101))
        self.assertIsNone(rb.curve_value("hp", "不存在的曲线", 100))

    def test_unknown_curve_falls_back_to_proxy(self):
        """`hit_hp_correction_normal`(240 boss)不在任何曲线表里 —— 客户端内置默认。
        不代理的话它和已知曲线组用的不是同一个单位,残差 379× 纯属构造出来的。"""
        self.assertEqual(rb.PROXY_CURVE, {"hp": "hit_hp_boss", "atk": "atk_single"})
        st = rb.boss_base_stats()
        if not st:
            self.skipTest("store 不可用")
        unknown = [c for c, s in st.items() if s["hpc"] == "hit_hp_correction_normal"]
        self.assertTrue(unknown, "没有未知曲线的 boss 了?")
        t = rb.true_stat(unknown[0], "hp", 100)
        self.assertEqual(t[1], "*", "未知曲线应被代理进统一组")

    def test_standard_boss_really_has_no_stats(self):
        """钉住那条结论:standard_boss 的行只有名字+资产,没有数值列。"""
        import wf_quest_lib as qlib
        try:
            sb = qlib.load_table(rb.STANDARD_BOSS)
        except Exception:
            self.skipTest("store 不可用")
        node = sb.get("chapter12_boss_story")
        if not isinstance(node, dict):
            self.skipTest("终始之龙不在 standard_boss")
        row = rb.cells(next(iter(node.values())))
        self.assertLessEqual(len(row), 3, f"standard_boss 行变长了:{row}")


class EndlessRerollSafetyCase(unittest.TestCase):
    def test_endless_reroll_rejects_every_non_700099_99_target_before_write(self):
        """目标门禁若被移除，首个官方 700007/8 fixture 会被旧实现真实改写。"""
        for event, quest_no in (("700007", "8"), ("700099", "8")):
            with self.subTest(event=event, quest_no=quest_no):
                target = [f"{event}{int(quest_no):03d}"] + [""] * 99
                quest_table = {event: {quest_no: ",".join(target)}}
                unsafe_pool = [
                    ("unsafe_field", "unsafe_field,bgm_unsafe", ["unsafe_boss"])]

                with mock.patch("wf_chain_build.build_pool",
                                return_value=unsafe_pool), \
                     mock.patch.object(q, "load_table", return_value=quest_table), \
                     mock.patch.object(q, "save_table",
                                       return_value=Path("fixture")) as save, \
                     mock.patch.object(rsave.subprocess, "run",
                                       return_value=mock.Mock(returncode=0)):
                    with self.assertRaisesRegex(ValueError, "700099.*99"):
                        rsave.reroll_endless_field(event, quest_no, apply=True)

                save.assert_not_called()
                self.assertEqual(quest_table[event][quest_no], ",".join(target))

    def test_endless_selector_chooses_only_from_post_gate_catalog(self):
        safe = native_bundle("safe_field", "safe_boss", family="safe")
        blocked = native_bundle(
            "treasure_cave_area", "blocked_boss", family="zz-blocked")
        rejected = native_bundle("unsafe_field", "unsafe_boss", family="unsafe")
        rejected = replace(
            rejected, portable=False,
            native_only_reason="ACTION_CLOSURE_UNAUDITED",
            terrain_requirements=None)
        catalog = rbb.BundleCatalog(
            family_ids=(safe.family_id, blocked.family_id, rejected.family_id),
            variants={safe.family_id: (safe.variant_id,),
                      blocked.family_id: (blocked.variant_id,),
                      rejected.family_id: (rejected.variant_id,)},
            bundles={safe.variant_id: (safe,), blocked.variant_id: (blocked,),
                     rejected.variant_id: (rejected,)},
            family_names={safe.family_id: safe.family_name,
                          blocked.family_id: blocked.family_name,
                          rejected.family_id: rejected.family_name},
            variant_names={safe.variant_id: safe.variant_name,
                           blocked.variant_id: blocked.variant_name,
                           rejected.variant_id: rejected.variant_name},
            rejections=(rbb.BundleRejection(
                rejected.source_field, rejected.source_zone,
                "ACTION_CLOSURE_UNAUDITED", "GeneralBossAlive target invalid"),),
            discovered_family_ids=(safe.family_id, blocked.family_id,
                                   rejected.family_id),
            discovered_variants={
                safe.family_id: (safe.variant_id,),
                blocked.family_id: (blocked.variant_id,),
                rejected.family_id: (rejected.variant_id,),
            },
            discovered_bundles={
                safe.variant_id: (safe,), blocked.variant_id: (blocked,),
                rejected.variant_id: (rejected,),
            },
        )

        class LastRng:
            @staticmethod
            def randrange(size):
                return size - 1

        selector = getattr(rb, "choose_endless_native_bundle", None)
        self.assertIsNotNone(selector, "正式构建器尚未导出无尽层安全选择接口")
        with mock.patch.object(rb, "build_native_bundle_catalog",
                               return_value=catalog):
            selected = selector(LastRng(), enemy_level=90)

        self.assertIs(selected, safe)

    def test_real_fixture_catalog_carries_nested_actions_to_ordered_publish(self):
        general = [""] * 161
        general[42] = "routine"
        general[109] = "battle/action/a_root"
        state = [""] * 53
        actions = {
            "battle/action/a_root": [
                "ActionDsl", 1, ["None"], False, False, False, False,
                False, False, False, 0, ["Block", [["Command", [
                    "CreateTargetAttack", 0, 0, 0, ["None"],
                    "battle/action/z_child"]]]]],
            "battle/action/z_child": [
                "ActionDsl", 1, ["None"], False, False, False, False,
                False, False, False, 0, ["Block", [["Command", [
                    "SpawnFunnel", ["Funnel", "safe_funnel"], 1,
                    ["FunnelGroup", 1], []]]]]],
        }
        validation = {
            "general_boss": {"safe_boss": {
                "100": rb.join(general, False)}},
            "__level_validator__": lambda *_args: 100,
            "__funnel_ok__": lambda *_args: True,
        }

        def portability(bundle):
            return rbb.boss_terrain_requirements(bundle, 90, {
                "general_boss": validation["general_boss"],
                "general_boss_state": {
                    "routine": {"1": {"start": rb.join(state, False)}}},
                "action_loader": actions.__getitem__,
                "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
            })

        catalog = rbb.build_native_bundle_catalog(
            {"safe_field": (
                "safe_field,battle/field/safe.terrain.amf3.deflate,safe_zone")},
            {"safe_zone": {"0": wave(bosses=("safe_boss",))}},
            lambda _logical: {"layers": [{
                "type": "objectgroup", "name": "0",
                "objects": [{"type": "FUNNEL_SPAWN1"}],
            }]},
            enemy_level=90,
            validation_tables=validation,
            display_names={"safe_boss": "安全首领"},
            identity_of=lambda _ref, _selected: {
                "display": "安全首领", "model": "safe_model",
                "actions": ("battle/action/a_root",)},
            hp_gate=lambda *_args: rbb.GateResult(True),
            reference_gate=lambda *_args: rbb.GateResult(True),
            zako_codes=set(),
            metadata_of=lambda _field: {
                "bgm": "bgm_safe", "thumbnail": "thumb_safe",
                "category": "rush"},
            portability_gate=portability,
        )

        class FirstRng:
            @staticmethod
            def randrange(_size):
                return 0

        with mock.patch.object(rb, "build_native_bundle_catalog",
                               return_value=catalog):
            selected = rb.choose_endless_native_bundle(
                FirstRng(), enemy_level=90)

        self.assertTrue(selected.portable)
        self.assertEqual(
            rb.endless_bundle_publish_logicals(selected),
            (
                "battle/field/safe.terrain.amf3.deflate",
                "battle/action/z_child.action.dsl.amf3.deflate",
                "battle/action/a_root.action.dsl.amf3.deflate",
                "master/battle/boss/general_boss.orderedmap",
                "master/battle/boss/boss_level.orderedmap",
                "master/battle/zako/general_zako.orderedmap",
                "master/battle/zako/zako_level.orderedmap",
                "master/battle/boss/general_boss_variable.orderedmap",
                "master/battle/boss/general_boss_state.orderedmap",
                "master/battle/boss/general_enemy_watch.orderedmap",
                "master/battle/boss/funnel/general_funnel.orderedmap",
                "master/battle/zone.orderedmap",
                "master/battle/field_data.orderedmap",
                "master/quest/event/rush_event_quest.orderedmap",
            ),
        )

    def test_endless_reroll_syncs_fields_and_publishes_bundle_dependencies(self):
        bundle = native_bundle("safe_field", "safe_boss", kind=2)
        target = ["700099099"] + [""] * 99
        target[5] = "old_thumb"
        target[69] = "5"
        target[95] = "90"
        target[98] = "old_field"
        target[99] = "old_bgm"
        quest_table = {"700099": {"99": ",".join(target)}}

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store"
            store.mkdir()
            quest_path = store / q.hashed_rel(rsave.RUSH_QUEST_LOGICAL)
            quest_path.parent.mkdir(parents=True)
            quest_path.write_bytes(q.build_node(quest_table))
            commands = []

            def publish(command, **_kwargs):
                commands.append(tuple(command))
                return mock.Mock(returncode=0)

            with mock.patch.object(q, "store_path", return_value=quest_path), \
                 mock.patch.object(rb, "choose_endless_native_bundle",
                                   return_value=bundle) as selector, \
                 mock.patch.object(rb, "field_official_elem_map",
                                   return_value={"safe_field": 2}), \
                 mock.patch.object(rb, "boss_element_map", return_value={}), \
                 mock.patch.object(rsave.subprocess, "run", side_effect=publish):
                rsave.reroll_endless_field("700099", "99", apply=True)

            selector.assert_called_once()
            self.assertEqual(selector.call_args.kwargs["enemy_level"], 90)
            written_tree = q.load_table(
                rsave.RUSH_QUEST_LOGICAL, path=quest_path)
            written = next(csv.reader([written_tree["700099"]["99"]]))
            self.assertEqual(
                {index: written[index] for index in (5, 69, 95, 98, 99)},
                {5: "thumb_safe", 69: "2", 95: "90",
                 98: "safe_field", 99: "bgm_safe"},
            )
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[0][-1], "--list")
            self.assertEqual(
                commands[1][3].split(","),
                [
                    "battle/field/safe_field.terrain.amf3.deflate",
                    "battle/action/safe.action.dsl.amf3.deflate",
                    "master/battle/boss/kraken.orderedmap",
                    "master/battle/boss/boss_level.orderedmap",
                    "master/battle/zako/general_zako.orderedmap",
                    "master/battle/zako/zako_level.orderedmap",
                    "master/battle/boss/general_boss.orderedmap",
                    "master/battle/boss/general_boss_variable.orderedmap",
                    "master/battle/boss/general_boss_state.orderedmap",
                    "master/battle/boss/general_enemy_watch.orderedmap",
                    "master/battle/boss/funnel/general_funnel.orderedmap",
                    "master/battle/zone.orderedmap",
                    "master/battle/field_data.orderedmap",
                    "master/quest/event/rush_event_quest.orderedmap",
                ],
            )

    def test_publish_preflight_failure_happens_before_real_store_write(self):
        bundle = native_bundle("safe_field", "safe_boss")
        target = ["700099099"] + [""] * 99
        target[5] = "old_thumb"
        target[69] = "5"
        target[95] = "90"
        target[98] = "old_field"
        target[99] = "old_bgm"
        quest_table = {"700099": {"99": ",".join(target)}}

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store"
            store.mkdir()
            quest_path = store / q.hashed_rel(rsave.RUSH_QUEST_LOGICAL)
            quest_path.parent.mkdir(parents=True)
            original = q.build_node(quest_table)
            quest_path.write_bytes(original)
            observed_original = []
            observed_store = []

            def reject_preflight(_command, **kwargs):
                observed_original.append(quest_path.read_bytes() == original)
                observed_store.append(
                    kwargs.get("env", {}).get("WF_TARGET_STORE"))
                return mock.Mock(returncode=7)

            with mock.patch.object(q, "store_path", return_value=quest_path), \
                 mock.patch.object(rb, "choose_endless_native_bundle",
                                   return_value=bundle), \
                 mock.patch.object(rb, "field_official_elem_map",
                                   return_value={"safe_field": 2}), \
                 mock.patch.object(rb, "boss_element_map", return_value={}), \
                 mock.patch.object(rsave.subprocess, "run",
                                   side_effect=reject_preflight):
                with self.assertRaisesRegex(RuntimeError, "preflight|预检|发布"):
                    rsave.reroll_endless_field("700099", "99", apply=True)

            self.assertEqual(observed_original, [True])
            self.assertEqual(observed_store, [str(store.resolve())])
            self.assertEqual(quest_path.read_bytes(), original)

    def test_publish_failure_restores_real_store_file_to_original_bytes(self):
        bundle = native_bundle("safe_field", "safe_boss")
        target = ["700099099"] + [""] * 99
        target[5] = "old_thumb"
        target[69] = "5"
        target[95] = "90"
        target[98] = "old_field"
        target[99] = "old_bgm"
        quest_table = {"700099": {"99": ",".join(target)}}

        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "store"
            store.mkdir()
            quest_path = store / q.hashed_rel(rsave.RUSH_QUEST_LOGICAL)
            quest_path.parent.mkdir(parents=True)
            original = q.build_node(quest_table)
            quest_path.write_bytes(original)
            observed_bytes = []
            commands = []

            def publish(command, **_kwargs):
                commands.append(tuple(command))
                observed_bytes.append(quest_path.read_bytes())
                return mock.Mock(returncode=0 if "--list" in command else 9)

            with mock.patch.object(q, "store_path", return_value=quest_path), \
                 mock.patch.object(rb, "choose_endless_native_bundle",
                                   return_value=bundle), \
                 mock.patch.object(rb, "field_official_elem_map",
                                   return_value={"safe_field": 2}), \
                 mock.patch.object(rb, "boss_element_map", return_value={}), \
                 mock.patch.object(rsave.subprocess, "run", side_effect=publish):
                with self.assertRaisesRegex(RuntimeError, "退出码 9"):
                    rsave.reroll_endless_field("700099", "99", apply=True)

            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[0][-1], "--list")
            self.assertNotIn("--list", commands[1])
            self.assertEqual(observed_bytes[0], original)
            self.assertNotEqual(observed_bytes[1], original)
            self.assertEqual(quest_path.read_bytes(), original)

    def test_random_boss_cli_defaults_to_700099_endless_99(self):
        db = mock.MagicMock()
        with mock.patch.object(
                rsave.sys, "argv",
                ["wf_rogue_save.py", "--reset", "1", "--random-boss"]), \
             mock.patch.object(rsave.sqlite3, "connect", return_value=db), \
             mock.patch.object(rsave, "reset_run", return_value=0), \
             mock.patch.object(rsave, "reroll_endless_field") as reroll:
            code = rsave.main()

        self.assertEqual(code, 0)
        reroll.assert_called_once_with("700099", "99", False)

    def test_random_boss_cli_rejects_invalid_target_before_any_side_effect(self):
        for event, quest_no in (("700007", "8"), ("700099", "8")):
            with self.subTest(event=event, quest_no=quest_no), \
                 mock.patch.object(
                     rsave.sys, "argv",
                     ["wf_rogue_save.py", "--reset", "1", "--random-boss",
                      "--restart-game", "--apply", "--event", event,
                      "--quest-no", quest_no]), \
                 mock.patch.object(rsave, "mumu_sh") as game, \
                 mock.patch.object(rsave.sqlite3, "connect") as connect, \
                 mock.patch.object(rsave, "reset_run") as reset:
                reset.return_value = 0
                with self.assertRaisesRegex(ValueError, "700099.*99"):
                    rsave.main()

                game.assert_not_called()
                connect.assert_not_called()
                reset.assert_not_called()


class StandardBossHpCase(unittest.TestCase):
    """standard_boss 数值不在 master 行，但其 `.esdl` 的 forms 可按客户端公式审计。"""

    def test_health_termination_forms_are_summed_once(self):
        # StandardEnemySource.as:523-538：只累加 Health(index 0 / packed T1)，
        # Defeat(index 1 / packed T2) 不代表一条额外血条，不能混进基数。
        tree = {"au": [
            {"d": ["T1", 100.0]},
            {"d": ["T2", 99, "phase"]},
            {"d": ["T1", 35.5]},
        ]}
        got = rb.standard_enemy_hp_base(tree)
        self.assertEqual(got["form_count"], 3)
        self.assertEqual(got["health_terms"], (100.0, 35.5))
        self.assertEqual(got["base_hp"], 135.5)

    def test_unknown_or_malformed_termination_fails_closed(self):
        for tree in ({}, {"au": []}, {"au": [{"d": ["T9", 100]}]},
                     {"au": [{"d": ["T1", float("nan")]}]}):
            with self.assertRaises(ValueError, msg=tree):
                rb.standard_enemy_hp_base(tree)

    def test_live_chapter12_resource_decodes_to_700m(self):
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            got = rb.standard_boss_hp_evidence("chapter12_boss_story", 80, sb)
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(got["selected_level"], 80)
        self.assertTrue(got["logical"].endswith("chapter12_boss_main.esdl.amf3.deflate"))
        self.assertEqual(got["base_hp"], 700_000_000.0)
        self.assertEqual(got["health_terms"], (700_000_000.0,))

    def test_zone_pick_uses_single_battle_side_of_each_boss_slot(self):
        """rush event 是单人战：c24/28/32 与 c26/30/34 是镜像，不是两只。"""
        try:
            chapter, _ = rb._zone_pick("main_12_10_01")
            anv3, _ = rb._zone_pick("anv3")
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(chapter, ["chapter12_boss_story"])
        # anv3 的 single/multi 镜像代号不同；按字符串去重仍会误算成两只。
        self.assertEqual(anv3, ["anv3_big_boss_single"])

        with self.subTest("terrain inactive zone rows are ignored"):
            active = wave(bosses=("active",)).split(",")
            inactive = wave(bosses=("inactive",)).split(",")
            inactive[23] = "0"
            slots = rbb.active_boss_slots(
                "f",
                {"f": "f,terrain/path,z"},
                {"z": {"0": ",".join(active), "1": ",".join(inactive)}},
                terrain_loader=lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                },
            )
            self.assertEqual(
                [(slot.layer, slot.single.kind, slot.single.code) for slot in slots],
                [("0", 1, "active")],
            )

        with self.subTest("live treasure cave only activates terrain layer zero"):
            try:
                fd = q.load_table(rb.FIELD_DATA_T)
                zone = q.load_table(rb.ZONE_T)
                caps = rbb.load_terrain_layer_caps(
                    "treasure_cave_area", fd, zone, rbb.load_store_terrain)
                slots = rbb.active_boss_slots(
                    "treasure_cave_area", fd, zone, rbb.load_store_terrain)
            except FileNotFoundError:
                self.skipTest("store 不可用")
            self.assertEqual(tuple(cap.layer for cap in caps), ("0",))
            self.assertEqual(slots, ())

    def test_floor_native_hp_keeps_two_real_instances_with_the_same_code(self):
        """跨 wave/不同实体槽若真的重复同代号，仍须逐实体累加。"""
        try:
            got = rb.floor_native_hp(
                ["chapter12_boss_story", "chapter12_boss_story"], 80,
                q.load_table(rb.STANDARD_BOSS))
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(len(got["components"]), 2)
        self.assertEqual(got["native_hp"], 770_000_000.0)

        with self.subTest("Orochi expands one parent plus eight ordered head instances"):
            try:
                catalog = rb.build_native_bundle_catalog(enemy_level=100)
                tables = {
                    "orochi": q.load_table(rbb.TABLE_LOGICALS["orochi"]),
                    "general_boss": q.load_table(rb.GENERAL_BOSS),
                    "general_boss_variable": q.load_table(
                        "master/battle/boss/general_boss_variable.orderedmap"),
                    "boss_level": q.load_table(
                        "master/battle/boss/boss_level.orderedmap"),
                }
            except FileNotFoundError:
                self.skipTest("store 不可用")
            family_id = next(
                family_id for family_id, name in catalog.family_names.items()
                if name == "八岐大蛇")
            discovered = [
                bundle for variant_id in catalog.discovered_variants[family_id]
                for bundle in catalog.discovered_bundles[variant_id]
            ]
            bundles = {}
            for bundle in discovered:
                bundles.setdefault(bundle.variant_name, bundle)
            expected = {
                "single": 60_780.72,
                "multi": 164_107.944,
                "multi_plus": 321_719.94855,
            }
            for variant, total in expected.items():
                expanded = rb.expand_bundle_hp_members(
                    bundles[variant], 100, tables)
                self.assertTrue(expanded.ok, (variant, expanded))
                self.assertEqual(len(expanded.members), 9)
                self.assertEqual(expanded.members[0].role, "parent")
                self.assertEqual(
                    [member.ordinal for member in expanded.members[1:]],
                    list(range(1, 9)))
                self.assertAlmostEqual(expanded.total_hp, total, places=5)
                self.assertEqual(expanded.selected_parent_level, 100)

            for level in (79, 80, 90, 99, 100):
                expanded = rb.expand_bundle_hp_members(
                    bundles["single"], level, tables)
                self.assertTrue(expanded.ok, (level, expanded))
                self.assertEqual(expanded.selected_parent_level, 100)
            rejected = rb.expand_bundle_hp_members(
                bundles["single"], 101, tables)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")

        with self.subTest("duplicate head code is accumulated by occurrence"):
            duplicate_tables = copy.deepcopy(tables)
            parent = "orochi_all_head_single"
            row = rb.cells(duplicate_tables["orochi"][parent]["100"])
            heads = row[24].split(",")
            heads[-1] = heads[1]
            row[24] = ",".join(heads)
            duplicate_tables["orochi"][parent]["100"] = rb.join(row, False)
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, duplicate_tables)
            self.assertTrue(expanded.ok, expanded)
            self.assertEqual(
                [member.code for member in expanded.members].count(
                    "orochi_recovery_head_single"), 2)
            self.assertAlmostEqual(expanded.total_hp, 59_514.455, places=5)

        with self.subTest("one malformed head rejects the whole special HP channel"):
            malformed = copy.deepcopy(tables)
            malformed["boss_level"]["orochi_beam_head_single"] = \
                BossLevelHpScalingCase._boss_level(10, kind="1")
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, malformed)
            self.assertFalse(expanded.ok)
            self.assertEqual(expanded.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertEqual(expanded.members, ())
            self.assertIsNone(expanded.total_hp)

        with self.subTest("unknown Hit curve is not silently replaced by proxy HP"):
            unknown = copy.deepcopy(tables)
            leaf = rb.cells(unknown["boss_level"]["orochi_beam_head_single"])
            leaf[4] = "hit_hp_unknown_task4_fixture"
            unknown["boss_level"]["orochi_beam_head_single"] = rb.join(leaf, False)
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, unknown)
            self.assertFalse(expanded.ok)
            self.assertEqual(expanded.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertIn("curve", expanded.detail.lower())

    def test_training_dummy_proxy_family_is_not_a_tower_candidate(self):
        """practice_waraboss_tough* 是无攻击行为的练习木桩，代理榜首不能入塔。"""
        self.assertFalse(rb._pool_safe(["practice_waraboss_tough"]))
        self.assertFalse(rb._pool_safe(["practice_waraboss_tough_attack_funnel_colorless"]))
        self.assertTrue(rb._pool_safe(["guardian_totem_single"]))


class BossLevelHpScalingCase(unittest.TestCase):
    SAFE_REFS = {
        "hard": frozenset(), "soft": frozenset(), "degraded": False,
    }

    @staticmethod
    def _boss_level(c2: float, c3: float = 1.0, *, kind: str = "0") -> str:
        row = [kind, "hit_hp_basic_normal", str(c2), str(c3), "hit_hp_boss",
               "", "", "atk_basic_normal", "10", "1", "atk_single",
               "tp_basic_normal", "100"]
        if kind == "1":
            row[5], row[6] = str(c2), str(c3)
        return rb.join(row, False)

    @staticmethod
    def _general_node(*levels: int) -> dict:
        return {str(level): f"general@{level}" for level in levels}

    def test_surjectivity_selects_the_first_level_not_below_the_enemy(self):
        node = self._general_node(79, 100)
        self.assertEqual(rb.select_surjective_level(node, 79), 79)
        self.assertEqual(rb.select_surjective_level(node, 80), 100)
        self.assertIsNone(rb.select_surjective_level(node, 101))

    def test_hit_hp_clone_changes_only_c2_and_preserves_the_source(self):
        source = self._boss_level(10, 2)
        clone = rb.clone_hit_boss_level_c2(source, 3.0)
        self.assertEqual(rb.cells(source)[2:5], ["10", "2", "hit_hp_boss"])
        self.assertEqual(rb.cells(clone)[2:5], ["30", "2", "hit_hp_boss"])
        self.assertNotEqual(source, clone)

        # 取数放在 subTest 之外:skipTest 若在 subTest 里抛出,只中止当前这个 subTest,
        # 后面几个平级 subTest 照跑,再引用这里才赋值的 catalog/tables/sources_before
        # 就是 UnboundLocalError(CI 无数据包时实测 11 条红)。
        try:
            catalog = rb.build_native_bundle_catalog(enemy_level=100)
            tables = {
                "orochi": q.load_table(rbb.TABLE_LOGICALS["orochi"]),
                "general_boss": q.load_table(rb.GENERAL_BOSS),
                "general_boss_variable": q.load_table(
                    "master/battle/boss/general_boss_variable.orderedmap"),
                "boss_level": q.load_table(
                    "master/battle/boss/boss_level.orderedmap"),
                "general_enemy_watch": q.load_table(rb.ENEMY_WATCH),
                "__code_references__": {
                    "hard": frozenset(), "soft": frozenset(),
                    "degraded": False,
                },
            }
        except FileNotFoundError:
            self.skipTest("store 不可用")

        with self.subTest("Orochi clone stages and commits all nine entities together"):
            family_id = next(
                family_id for family_id, name in catalog.family_names.items()
                if name == "八岐大蛇")
            bundle = next(
                bundle
                for variant_id in catalog.discovered_variants[family_id]
                for bundle in catalog.discovered_bundles[variant_id]
                if bundle.variant_name == "single")
            source_parent = "orochi_all_head_single"
            parent_before = copy.deepcopy(tables["orochi"][source_parent])
            parent_row = rb.cells(parent_before["100"])
            source_heads = parent_row[24].split(",")
            sources_before = {
                table: copy.deepcopy(tables[table])
                for table in ("orochi", "general_boss", "general_boss_variable",
                              "boss_level", "general_enemy_watch")
            }

            result = rb.clone_orochi_parent_bundle(bundle, 6, 3.0, tables)
            self.assertTrue(result.ok, result)
            self.assertEqual(result.parent_code, "mod_rogue_orochi6")
            self.assertEqual(result.head_codes, tuple(
                f"mod_rogue_orochi6_head{i}" for i in range(1, 9)))
            self.assertEqual(result.bundle.slots[0].single,
                             rbb.BossRef(3, "mod_rogue_orochi6"))

            cloned_parent = tables["orochi"][result.parent_code]
            self.assertEqual(list(cloned_parent), ["100"])
            cloned_parent_row = rb.cells(cloned_parent["100"])
            self.assertEqual(cloned_parent_row[24].split(","),
                             list(result.head_codes))
            for index, (source_code, target_code) in enumerate(
                    zip(source_heads, result.head_codes), start=1):
                self.assertIn(target_code, tables["general_boss"])
                self.assertIn(target_code, tables["general_boss_variable"])
                source_cells = rb.cells(sources_before["boss_level"][source_code])
                target_cells = rb.cells(tables["boss_level"][target_code])
                self.assertEqual(source_cells[:2] + source_cells[3:],
                                 target_cells[:2] + target_cells[3:], index)
                self.assertEqual(float(target_cells[2]),
                                 float(source_cells[2]) * 3.0)
            source_cells = rb.cells(sources_before["boss_level"][source_parent])
            target_cells = rb.cells(tables["boss_level"][result.parent_code])
            self.assertEqual(source_cells[:2] + source_cells[3:],
                             target_cells[:2] + target_cells[3:])
            self.assertEqual(float(target_cells[2]), float(source_cells[2]) * 3.0)
            self.assertAlmostEqual(result.expanded.total_hp, 182_342.16, places=5)

            self.assertEqual(tables["orochi"][source_parent], parent_before)
            for table, original in sources_before.items():
                for key, value in original.items():
                    self.assertEqual(tables[table][key], value, (table, key))

        with self.subTest("a final malformed head leaves every input table unchanged"):
            malformed = {
                key: copy.deepcopy(value) for key, value in sources_before.items()
            }
            malformed["__code_references__"] = {
                "hard": frozenset(), "soft": frozenset(), "degraded": False,
            }
            malformed["boss_level"][source_heads[-1]] = self._boss_level(
                10, kind="1")
            before = copy.deepcopy(malformed)
            rejected = rb.clone_orochi_parent_bundle(bundle, 7, 3.0, malformed)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertEqual(malformed, before)

        with self.subTest("soft enemy-watch dependency cannot be silently dropped"):
            missing_watch = {
                key: copy.deepcopy(value) for key, value in sources_before.items()
                if key != "general_enemy_watch"
            }
            missing_watch["__code_references__"] = {
                "hard": frozenset(),
                "soft": frozenset({source_heads[0]}),
                "degraded": False,
            }
            before = copy.deepcopy(missing_watch)
            rejected = rb.clone_orochi_parent_bundle(
                bundle, 8, 3.0, missing_watch)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertIn("enemy_watch", rejected.detail)
            self.assertEqual(missing_watch, before)

        with self.subTest("stale Orochi clone purge and write plan cover five tables only"):
            stale = {
                "orochi": {"mod_rogue_orochi4": {"100": "parent"},
                            "official": {"100": "keep"}},
                "general_boss": {"mod_rogue_orochi4_head1": "head",
                                 "mod_rogue_boss4": "keep"},
                "general_boss_variable": {"mod_rogue_orochi4_head1": "head"},
                "boss_level": {"mod_rogue_orochi4": "parent",
                               "mod_rogue_orochi4_head1": "head"},
                "general_enemy_watch": {
                    "1": {"mod_rogue_orochi4_head1": {"routine": "watch"},
                          "official": {"routine": "keep"}},
                },
            }
            touched = rb.purge_orochi_clones(stale)
            self.assertEqual(set(touched), {
                "orochi", "general_boss", "general_boss_variable",
                "boss_level", "general_enemy_watch",
            })
            self.assertIn("official", stale["orochi"])
            self.assertIn("mod_rogue_boss4", stale["general_boss"])
            self.assertNotIn("mod_rogue_orochi4_head1",
                             stale["general_enemy_watch"]["1"])
            write_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=False, caster_dirty=False,
                orochi_dirty=True, enemy_watch_available=True)
            self.assertEqual(write_plan, (
                "master/battle/boss/general_boss.orderedmap",
                "master/battle/boss/boss_level.orderedmap",
                "master/battle/boss/general_boss_variable.orderedmap",
                "master/battle/boss/general_enemy_watch.orderedmap",
                "master/battle/boss/orochi.orderedmap",
            ))
            self.assertNotIn("master/battle/zako/general_zako.orderedmap",
                             write_plan)
            self.assertNotIn("master/battle/zako/zako_level.orderedmap",
                             write_plan)
            combined_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=True, caster_dirty=False,
                orochi_dirty=True, enemy_watch_available=True)
            self.assertLess(
                combined_plan.index(rb.ZONE_T),
                combined_plan.index(rb.FIELD_DATA_T),
                "field_data.c2 引用 zone，必须先保存 zone 再保存 field")
            import wf_gui as gui
            self.assertIn("master/battle/boss/orochi.orderedmap",
                          gui.ROGUE_BATTLE_LOGICALS)
            with mock.patch.object(
                    rb, "live_forged_dsl_logicals", return_value=[]), \
                    mock.patch.object(rb, "verify_cdn_chain", return_value=[]), \
                    mock.patch.object(
                        gui, "_rogue_run",
                        return_value={"ok": True, "log": "", "returncode": 0}):
                published = gui.rogue_publish()
            self.assertIn(
                f"battle {len(gui.ROGUE_BATTLE_LOGICALS)}表",
                published["log"])

    def test_hit_hp_clone_rejects_fix_malformed_or_nonpositive_scaling(self):
        bad_inputs = (
            (self._boss_level(10, 2, kind="1"), 3.0),
            ("0,short", 3.0),
            (self._boss_level(10, 2), 0.0),
            (self._boss_level(10, 2), float("inf")),
        )
        for leaf, scale in bad_inputs:
            with self.assertRaises(ValueError, msg=(leaf, scale)):
                rb.clone_hit_boss_level_c2(leaf, scale)

    def test_pure_general_plan_scales_every_code_and_keeps_c86_at_one(self):
        native = {
            "verified": True,
            "native_hp": 400.0,
            "components": [
                {"code": "a", "kind": "general", "native_hp": 100.0},
                {"code": "b", "kind": "general", "native_hp": 300.0},
            ],
        }
        plan = rb.general_hp_scale_plan(
            ["a", "b"], native,
            {"a": self._general_node(79, 100),
             "b": self._general_node(100)},
            {"a": self._boss_level(10), "b": self._boss_level(30)},
            80, target_hp=1_200.0, curse_hp=2.5,
            code_references=self.SAFE_REFS)
        self.assertEqual(plan["selected_levels"], {"a": 100, "b": 100})
        self.assertEqual(plan["baseline_scale"], 3.0)
        self.assertEqual(plan["final_scale"], 7.5)
        self.assertEqual(rb.cells(plan["baseline_leaves"]["a"])[2], "30")
        self.assertEqual(rb.cells(plan["baseline_leaves"]["b"])[2], "90")
        self.assertEqual(rb.cells(plan["final_leaves"]["a"])[2], "75")
        self.assertEqual(rb.cells(plan["final_leaves"]["b"])[2], "225")
        self.assertEqual(plan["baseline_true_hp"], 1_200.0)
        self.assertEqual(plan["true_hp"], 3_000.0)
        self.assertEqual(plan["c86"], 1.0)

        with self.subTest("identity-locked pure HP clone is rejected at the plan boundary"):
            locked = {
                "hard": frozenset({"a"}), "soft": frozenset(),
                "degraded": False,
            }
            with self.assertRaisesRegex(
                    ValueError, r"identity-locked.*a.*master id"):
                rb.general_hp_scale_plan(
                    ["a", "b"], native,
                    {"a": self._general_node(79, 100),
                     "b": self._general_node(100)},
                    {"a": self._boss_level(10), "b": self._boss_level(30)},
                    80, target_hp=1_200.0, curse_hp=2.5,
                    code_references=locked)

    def test_general_plan_rejects_mixed_family_and_fix_hp(self):
        general = self._general_node(100)
        mixed = {
            "verified": True, "native_hp": 400.0,
            "components": [
                {"code": "a", "kind": "general", "native_hp": 100.0},
                {"code": "s", "kind": "standard", "native_hp": 300.0},
            ],
        }
        with self.assertRaisesRegex(ValueError, "混合"):
            rb.general_hp_scale_plan(
                ["a", "s"], mixed, {"a": general},
                {"a": self._boss_level(10)}, 100,
                target_hp=1_200.0, curse_hp=1.0,
                code_references=self.SAFE_REFS)

        pure = {
            "verified": True, "native_hp": 100.0,
            "components": [{"code": "a", "kind": "general", "native_hp": 100.0}],
        }
        with self.assertRaisesRegex(ValueError, "Hit"):
            rb.general_hp_scale_plan(
                ["a"], pure, {"a": general},
                {"a": self._boss_level(10, kind="1")}, 100,
                target_hp=1_200.0, curse_hp=1.0,
                code_references=self.SAFE_REFS)

    def test_family_strategy_removes_the_general_c86_ceiling(self):
        general_native = {
            "verified": True, "native_hp": 100.0,
            "components": [{"code": "a", "kind": "general", "native_hp": 100.0}],
        }
        got = rb.floor_hp_scaling_strategy(
            ["a"], general_native, {"a": self._general_node(100)},
            {"a": self._boss_level(10)}, 100, required_c86=100.0,
            deep=True, code_references=self.SAFE_REFS)
        self.assertEqual(got["channel"], "boss_level")
        self.assertEqual(got["baseline_c86"], 1.0)
        self.assertEqual(got["baseline_scale"], 100.0)

        locked = {
            "hard": frozenset({"a"}), "soft": frozenset(),
            "degraded": False,
        }
        with self.subTest("identity-locked general uses only same-id c86 micro tuning"):
            got = rb.floor_hp_scaling_strategy(
                ["a"], general_native, {"a": self._general_node(100)},
                {"a": self._boss_level(10)}, 100, required_c86=1.05,
                deep=True, code_references=locked)
            self.assertEqual(got["channel"], "c86")
            self.assertEqual(got["family"], "identity-locked")
            self.assertEqual(got["baseline_c86"], 1.05)
            self.assertEqual(got["selected_levels"], {})
        with self.subTest("identity-locked candidate outside c86 window is redrawn"):
            with self.assertRaisesRegex(
                    ValueError, r"identity-locked.*a.*0\.9~1\.1"):
                rb.floor_hp_scaling_strategy(
                    ["a"], general_native, {"a": self._general_node(100)},
                    {"a": self._boss_level(10)}, 100, required_c86=100.0,
                    deep=True, code_references=locked)

    def test_hp_reorder_preserves_a_pinned_element_immunity_intent(self):
        self.assertTrue(rb.element_immunity_requested(
            {"curses": ["血肉高墙", "元素禁壁"]}))
        self.assertTrue(rb.element_immunity_requested(
            {"curses": ["五相绝域"]}))
        self.assertTrue(rb.element_immunity_requested(
            {"curses": ["元素滞钝"]}))
        self.assertTrue(rb.element_immunity_requested(
            {"curses": ["混相禁域"]}))
        self.assertFalse(rb.element_immunity_requested(
            {"curses": ["血肉高墙"]}))
        self.assertTrue(rb.hard_condition_carrier_requested(
            {"curses": ["层叠龙鳞"]}))
        self.assertTrue(rb.hard_condition_carrier_requested(
            {"curses": ["不屈龙心"]}))
        self.assertTrue(rb.hard_condition_carrier_requested(
            {"curses": ["绝对壁垒"]}))
        self.assertTrue(rb.hard_condition_carrier_requested(
            {"curses": ["混相禁域"]}))
        self.assertFalse(rb.hard_condition_carrier_requested(
            {"curses": ["血肉高墙"]}))

        ineligible = ((1,), {"element_immunity_block": "没有 general_boss 实际代号"})
        eligible = ((2,), {"element_immunity_block": None})
        picked, downgraded = rb.prefer_element_immunity_hp_candidates(
            [ineligible, eligible])
        self.assertEqual(picked, [eligible])
        self.assertFalse(downgraded)

        prefixes, exact = (("guardian_golem",),
                           frozenset({"lich_wind_expert_100"}))
        tower_candidates = [
            ("threat", "line", ["guardian_golem_fire_single"]),
            ("ordinary", "line", ["safe_boss"]),
        ]
        hp_candidates = [
            ((0,), {"bosses": ["lich_wind_expert_100"]}, {}),
            ((1,), {"bosses": ["safe_boss"]}, {}),
        ]
        self.assertEqual(
            rb.prefer_non_threat_candidates(
                tower_candidates, 6, 30, lambda item: item[2], prefixes, exact),
            tower_candidates[1:])
        self.assertEqual(
            rb.prefer_non_threat_candidates(
                hp_candidates, 6, 30, lambda item: item[1]["bosses"],
                prefixes, exact),
            hp_candidates[1:])
        self.assertEqual(
            rb.prefer_non_threat_candidates(
                tower_candidates[:1], 6, 30, lambda item: item[2], prefixes, exact),
            tower_candidates[:1], "只剩高威胁候选时不得伪造候选")
        self.assertEqual(
            rb.prefer_non_threat_candidates(
                tower_candidates, 7, 30, lambda item: item[2], prefixes, exact),
            tower_candidates, "前 20% 之后不得继续过滤")

    def test_hp_reorder_explicitly_reports_when_element_carriers_are_exhausted(self):
        ranked = [
            ((1,), {"element_immunity_block": "c36=true"}),
            ((2,), {"element_immunity_block": "没有 general_boss 实际代号"}),
        ]
        picked, downgraded = rb.prefer_element_immunity_hp_candidates(ranked)
        self.assertEqual(picked, ranked)
        self.assertTrue(downgraded)

    def test_standard_strategy_is_micro_adjust_only_and_never_deep(self):
        standard_native = {
            "verified": True, "native_hp": 100.0,
            "components": [{"code": "s", "kind": "standard", "native_hp": 100.0}],
        }
        got = rb.floor_hp_scaling_strategy(
            ["s"], standard_native, {}, {}, 100, required_c86=1.05,
            deep=False)
        self.assertEqual(got["channel"], "c86")
        self.assertEqual(got["baseline_c86"], 1.05)
        for required, deep in ((1.1001, False), (1.0, True)):
            with self.assertRaises(ValueError, msg=(required, deep)):
                rb.floor_hp_scaling_strategy(
                    ["s"], standard_native, {}, {}, 100,
                    required_c86=required, deep=deep)


class TowerHpTargetCase(unittest.TestCase):
    def test_flat_is_default_and_ramp_retains_the_old_author_endpoints(self):
        for r in (1, 2, 15, 30):
            self.assertEqual(rb.target_dps(r, 30), 25_000_000.0)
        first = rb.target_dps(1, 30, ramp=True)
        last = rb.target_dps(30, 30, ramp=True)
        self.assertEqual(first, 600_000.0)
        self.assertEqual(last, 25_000_000.0)
        self.assertGreaterEqual(last / first, 35.0)
        self.assertLessEqual(last / first, 50.0)

    def test_configured_hp_curve_keeps_cli_difficulty_and_stage_controls_live(self):
        hell0, hellg, _a0, _ag = rb.difficulty_curve("hell", 30)
        for r in (1, 15, 30):
            self.assertAlmostEqual(
                rb.configured_target_dps(r, 30, hell0, hellg),
                rb.target_dps(r, 30))
        easy0, easyg, _a0, _ag = rb.difficulty_curve("easy", 30)
        # 显式 easy 仍相对 hell 缩放 flat profile；显式 --ramp 才恢复旧端点。
        self.assertAlmostEqual(
            rb.configured_target_dps(1, 30, easy0, easyg), 25_000_000.0 / 3.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(30, 30, easy0, easyg), 7_500_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(1, 30, easy0, easyg, ramp=True), 200_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(30, 30, easy0, easyg, ramp=True), 7_500_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(15, 30, hell0, hellg, 1.15),
            rb.target_dps(15, 30) * 1.15)

    def test_deep_hp_anchor_expansion_is_general_c2_scalable(self):
        """深层锚必须能走 general_boss clone + Hit boss_level.c2。"""
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            gb = q.load_table(rb.GENERAL_BOSS)
            bl = q.load_table("master/battle/boss/boss_level.orderedmap")
        except FileNotFoundError:
            self.skipTest("store 不可用")
        fields = [rb.deep_hp_anchor_field(r, 30) for r in range(25, 31)]
        self.assertEqual(len(set(fields)), 6)
        refs = rb.code_referenced_bosses(gb)
        for r, field in zip(range(25, 31), fields):
            bosses, _ = rb._zone_pick(field)
            self.assertTrue(bosses, field)
            got = rb.floor_native_hp(bosses, 100, sb)
            self.assertTrue(got["absolute_verified"], (field, got))
            plan = rb.general_hp_scale_plan(
                bosses, got, gb, bl, 100,
                target_hp=rb.target_dps(r, 30) * 900.0, curse_hp=1.0,
                code_references=refs)
            self.assertEqual(plan["c86"], 1.0)
            self.assertEqual(set(plan["final_leaves"]), set(bosses))

    def test_standard_c86_is_only_a_ten_percent_micro_adjustment(self):
        self.assertEqual(rb.STANDARD_C86_LIMITS, (0.9, 1.1))

    def test_hp_correction_round_trips_to_required_dps(self):
        correction = rb.solve_hp_correction(2_000_000.0, 900.0, 125_000_000.0)
        self.assertAlmostEqual(correction, 14.4)
        self.assertAlmostEqual(125_000_000.0 * correction / 900.0, 2_000_000.0)

    def test_native_hp_combines_general_formula_and_standard_esdl(self):
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            got = rb.floor_native_hp(
                ["guardian_totem_single", "chapter12_boss_story"], 80, sb)
        except FileNotFoundError:
            self.skipTest("store 不可用")
        # guardian_totem: true_stat=26,195.4，按规格 K[80]=2250；
        # chapter12: esdl 700,000,000 × 单人 standard 折扣 0.55。
        self.assertEqual(got["components"][0]["native_hp"], 58_939_650.0)
        self.assertEqual(got["components"][1]["native_hp"], 385_000_000.0)
        self.assertEqual(got["native_hp"], 443_939_650.0)
        self.assertTrue(got["verified"])
        self.assertEqual(got["components"][0]["evidence_kind"], "proxy")
        self.assertEqual(got["components"][1]["evidence_kind"], "absolute")
        self.assertFalse(got["absolute_verified"])

    def test_fix_hp_general_boss_uses_its_fixed_curve_without_k_twice(self):
        """BossLevelValues kind=1 已是绝对 Fix HP；K 只用于统一 true_stat 坐标。"""
        try:
            got = rb.floor_native_hp(
                ["middle_boss_dragon_smr20_raid3"], 89,
                q.load_table(rb.STANDARD_BOSS))
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertTrue(got["verified"], got.get("reason"))
        self.assertTrue(got["absolute_verified"], got.get("reason"))
        self.assertEqual(got["components"][0]["hp_curve_kind"], "fix")
        self.assertEqual(got["native_hp"], 192_000_000.0)

        sphere = rb.floor_native_hp(
            ["thunder_sphere"], 100, q.load_table(rb.STANDARD_BOSS))
        self.assertTrue(sphere["verified"], sphere.get("reason"))
        self.assertEqual(sphere["native_hp"], 125_000_000.0)

    def test_solved_record_keeps_hp_and_time_curses_real(self):
        native = {"native_hp": 385_000_000.0, "verified": True,
                  "components": [{"kind": "standard", "native_hp": 385_000_000.0}]}
        got = rb.solve_floor_hp_record(
            30, 30, native, base_duration_s=900.0, duration_s=180.0,
            curse_hp=2.5, raw_c86=6.5, family="standard")
        self.assertEqual(got["baseline_c86"], 58.4416)
        self.assertEqual(got["c86"], 146.104)
        self.assertEqual(got["true_hp"], 56_250_040_000.0)
        self.assertAlmostEqual(got["realized_dps"] / got["baseline_dps"], 12.5)
        self.assertEqual(got["curse_hp"], 2.5)
        self.assertLess(got["family_scale"], 10.0)

    def test_flat_curve_gate_exempts_only_round_one_and_checks_every_boss_floor(self):
        ok = [{"r": 1, "baseline_dps": 600_000.0, "warmup": True}]
        ok += [{"r": r, "baseline_dps": 25_000_000.0} for r in range(2, 31)]
        self.assertEqual(rb.hp_curve_errors(ok, 30), [])
        low = [dict(x) for x in ok]
        low[1]["baseline_dps"] = 21_940_624.0
        self.assertTrue(any("第2关" in e for e in rb.hp_curve_errors(low, 30)))
        high = [dict(x) for x in ok]
        high[-1]["baseline_dps"] = 30_716_876.0
        self.assertTrue(any("第30关" in e for e in rb.hp_curve_errors(high, 30)))
        missing = ok[:-1]
        self.assertTrue(any("缺少" in e for e in rb.hp_curve_errors(missing, 30)))

    def test_ramp_curve_gate_alone_keeps_jitter_and_endpoint_ratio(self):
        ok = [
            {"r": 1, "baseline_dps": 600_000.0},
            {"r": 2, "baseline_dps": 510_000.0},
            {"r": 30, "baseline_dps": 25_000_000.0},
        ]
        self.assertEqual(rb.hp_curve_errors(ok, 30, ramp=True), [])
        bad = [dict(x) for x in ok]
        bad[1]["baseline_dps"] = 509_999.0
        self.assertTrue(any(
            "下跌" in e for e in rb.hp_curve_errors(bad, 30, ramp=True)))

    def test_short_time_gate_uses_realized_dps_on_every_floor(self):
        self.assertEqual(rb.hp_short_time_errors([
            {"r": 20, "duration_s": 180.0, "realized_dps": 20_000_000.0},
        ]), [])
        errors = rb.hp_short_time_errors([
            {"r": 20, "duration_s": 180.0, "realized_dps": 20_000_001.0},
        ])
        self.assertEqual(len(errors), 1)
        self.assertIn("第20战", errors[0])

    def test_hp_correction_gate_is_channel_aware(self):
        ok = [
            {"r": 1, "family": "no-boss", "c86": 9.0, "warmup": True},
            {"r": 2, "family": "general", "c86": 1.0},
            {"r": 3, "family": "standard", "c86": 1.1},
        ]
        self.assertEqual(rb.hp_correction_errors(ok, 30), [])
        bad_general = [dict(x) for x in ok]
        bad_general[1]["c86"] = 1.0001
        self.assertTrue(any(
            "general" in e for e in rb.hp_correction_errors(bad_general, 30)))
        bad_standard = [dict(x) for x in ok]
        bad_standard[2]["c86"] = 1.1001
        self.assertTrue(any(
            "standard" in e for e in rb.hp_correction_errors(bad_standard, 30)))
        with self.subTest("identity-locked general shares the existing micro window"):
            locked = ok + [{"r": 4, "family": "identity-locked", "c86": 1.1}]
            self.assertEqual(rb.hp_correction_errors(locked, 30), [])
            locked[-1]["c86"] = 1.1001
            self.assertTrue(any(
                "identity-locked" in e
                for e in rb.hp_correction_errors(locked, 30)))

    def test_only_the_fixed_no_boss_warmup_may_use_an_hp_proxy(self):
        no_boss = {"r": 1, "pick": {"bosses": []},
                   "native_hp": {"verified": False, "reason": None}}
        bad_boss = {"r": 10, "pick": {"bosses": ["unknown"]},
                    "native_hp": {"verified": False, "reason": "missing"}}
        self.assertEqual(rb.native_hp_coverage_errors([no_boss]), [])
        errors = rb.native_hp_coverage_errors([no_boss, bad_boss])
        self.assertEqual(len(errors), 1)
        self.assertIn("第10战", errors[0])


@requires_store
class TaskCDryRunCase(unittest.TestCase):
    """主编排路径回归：纯函数单测不能代替 30 层随机/重抽/克隆整链。"""

    @staticmethod
    def run_build(*extra: str) -> subprocess.CompletedProcess:
        script = Path(rb.__file__).resolve()
        repo = script.parent.parent
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, str(script), *extra], cwd=repo, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)

    @staticmethod
    def run_build_with_plan(plan: dict, *extra: str,
                            ignore_high_threat: bool = False,
                            audit_table_mutations: bool = False) -> subprocess.CompletedProcess:
        script_dir = str(Path(rb.__file__).resolve().parent)
        argv = [str(Path(rb.__file__).resolve()), *extra]
        driver = (
            "import copy, json, sys\n"
            "from unittest import mock\n"
            f"sys.path.insert(0, {script_dir!r})\n"
            "import wf_rogue_build as rb\n"
            "import wf_quest_lib as q\n"
            f"sys.argv = {argv!r}\n"
            "original_load = q.load_table\n"
            "held_fd = copy.deepcopy(original_load(rb.FIELD_DATA_T))\n"
            "held_zone = copy.deepcopy(original_load(rb.ZONE_T))\n"
            "before_fd = set(held_fd)\n"
            "before_zone = set(held_zone)\n"
            "def held_load(logical, *args, **kwargs):\n"
            "    if logical == rb.FIELD_DATA_T:\n"
            "        return held_fd\n"
            "    if logical == rb.ZONE_T:\n"
            "        return held_zone\n"
            "    return original_load(logical, *args, **kwargs)\n"
            f"with mock.patch.object(rb, 'layout_plan', return_value={plan!r}), \\\n"
            "     mock.patch.object(rb, 'load_boss_history', return_value=[]), \\\n"
            "     mock.patch.object(q, 'load_table', side_effect=held_load), \\\n"
            "     mock.patch.object(rb, 'is_high_threat_bosses', "
            f"return_value=False) if {ignore_high_threat!r} else mock.patch.object("
            "rb, 'is_high_threat_bosses', wraps=rb.is_high_threat_bosses):\n"
            "    result = rb.main()\n"
            f"if {audit_table_mutations!r}:\n"
            "    print('[TEST-AUDIT] table-delta=' + json.dumps({\n"
            "        'field': sorted(set(held_fd) - before_fd),\n"
            "        'zone': sorted(set(held_zone) - before_zone),\n"
            "        'round_field_present': 'mod_rogue_f5' in held_fd,\n"
            "        'round_zone_present': 'mod_rogue_z5' in held_zone,\n"
            "    }, ensure_ascii=False))\n"
            "raise SystemExit(result)\n"
        )
        repo = Path(rb.__file__).resolve().parent.parent
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, "-c", driver], cwd=repo, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)

    def test_canonical_30_floor_dry_run_hits_all_task_c_gates(self):
        result = self.run_build(
            "--rounds", "30", "--seed", "20260805",
            "--difficulty", "hell", "--ignore-plan")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        for marker in (
                "profile=flat",
                "第1战热身 600,000/s",
                "boss层 2~30 全部命中 21,940,625~30,716,875/s",
                "general c86=1",
                "boss_level.c2",
                # ⚠ 这里曾断言 "领域保底完成 21/21"。那个 100% 覆盖率只有靠
                # 「载体不合格就把整层的 boss 换掉」才达得到,而那正是 2026-08-05
                # 起把机兵/女帝歼灭者/土俑嘉年华/五元素球连同终始之龙、无幻之宴、
                # 菲诺梅那三个守门固定位一起扫出塔外的机制(30 层里 20 层被换)。
                # 作者从未要求过按血量/载体换 boss(原始需求 6d7dec0 是压低敌方攻击)。
                # 现在的契约:法阵载体只挂得上 general 系 boss,挂不上就欠配——
                # 这与「深渊连战-随机方案-当前.md」第九节写的「静默落不上,不是崩溃」
                # 一致。所以只断言这行存在,覆盖率交给下面的策展位断言。
                "领域保底完成 ",
                "深层时限诅咒 0 层",
                "identity-locked source clone 0",
                "31 关解析链复核通过",
                "[DRY-RUN] 未写入"):
            self.assertIn(marker, out)

        baselines = {
            int(round_no): int(dps.replace(",", ""))
            for round_no, dps in re.findall(
                r"第(\d+)战 .*?基线\(c86=[^,]+,HP=[^,]+,DPS=([\d,]+)/s\)",
                out)
        }
        self.assertEqual(set(baselines), set(range(1, 31)))
        self.assertEqual(baselines[1], rb.WARMUP_TARGET_DPS)
        lo, hi = rb.TARGET_DPS_LAST_BAND
        for round_no in range(2, 31):
            self.assertLessEqual(lo, baselines[round_no], round_no)
            self.assertLessEqual(baselines[round_no], hi, round_no)
        boss_lines = [line for line in out.splitlines()
                      if re.match(r"\s+第(?:[2-9]|[12]\d|30)战 ", line)]
        self.assertEqual(len(boss_lines), 29)
        for line in boss_lines:
            self.assertNotIn("补偿hp×", line,
                             "general HP 已走 boss_level.c2，不得再把 raw bh 冒充落表补偿")

        # 策展位不得被 HP 重排扫掉(2026-08-07 回归)。build_schedule 排的锚位与
        # 三个守门固定位必须原样出现在成品塔里；它们大多没有可审计的 HP 通道,
        # 一旦「血量按不动就换 boss」复活,这一组断言会立刻红。
        labels = re.findall(r"第\s*(\d+)战 \[([^\]]*)\]", out)
        by_round = {int(r): label for r, label in labels}
        for round_no, expected in ((15, "机工神兵"), (29, "无幻之宴"),
                                   (30, "终始之龙")):
            self.assertTrue(
                by_round.get(round_no, "").startswith(expected),
                f"第{round_no}战守门固定位被换掉了:{by_round.get(round_no)!r}")
        for source in ("机兵", "女帝歼灭者", "土俑嘉年华", "元素试炼"):
            self.assertTrue(
                any(label.startswith(source) for label in by_round.values()),
                f"策展来源「{source}」整类没出现在成品塔里")

    def test_explicit_ramp_keeps_the_old_geometric_profile(self):
        result = self.run_build(
            "--rounds", "30", "--seed", "20260805",
            "--difficulty", "hell", "--ignore-plan", "--ramp")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("profile=ramp", out)
        self.assertIn("基线首尾 DPS 600,000→25,000,000", out)
        self.assertIn("31 关解析链复核通过", out)

    def test_pinned_shallow_immunity_survives_hp_reorder(self):
        # 本用例只隔离验证“钉选免疫→HP 重排仍保载体”。高威胁 boss 拒绝
        # r>=99 高档免疫由 HighMobilityCase 的专用断言覆盖，不能让随机命中的
        # guardian_golem 把两个独立门禁耦合成 seed 依赖。
        result = self.run_build_with_plan(
            {"floors": {"12": {"curses": ["元素禁壁"]}}},
            "--rounds", "30", "--seed", "20260805", "--difficulty", "hell",
            ignore_high_threat=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("[HP重排] round=12", out)
        self.assertNotIn("round=12 reject=「元素禁壁」", out)
        self.assertRegex(out, r"第12战 .*元素禁壁")
        self.assertIn("31 关解析链复核通过", out)

    def test_pinned_terrain_does_not_bypass_immunity_aware_hp_reorder(self):
        # 真机回归：旧的 `not (pin_t or pin_b)` 会整段跳过 HP 重排，
        # 于是钉地形的浅层拿到不可挂 c109 的 donor，元素诅咒随后被吞掉。
        result = self.run_build_with_plan(
            {"floors": {"5": {
                "terrain": "dark_matter_80", "curses": ["元素禁壁"]}}},
            "--rounds", "8", "--seed", "2", "--difficulty", "hell")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertNotIn("round=5 reject=「元素禁壁」", out)
        self.assertIn("@ dark_matter_80", out)
        self.assertRegex(out, r"第5战 .*field=mod_rogue_f5")
        self.assertRegex(out, r"第5战 .*元素禁壁")
        self.assertIn("9 关解析链复核通过", out)

    def test_ineligible_pinned_boss_and_immunity_fails_instead_of_eating_pin(self):
        # 显式 boss 与显式诅咒同属用户意图；两者冲突时不能成功返回后
        # 把属性免疫随机替换掉。dark_matter_single 的实际 c36=true。
        result = self.run_build_with_plan(
            {"floors": {"5": {
                "boss": "dark_matter_single", "curses": ["元素禁壁"]}}},
            "--rounds", "8", "--seed", "2", "--difficulty", "hell")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, out)
        self.assertIn("钉选 boss dark_matter_single 与属性免疫冲突", out)
        self.assertIn("c36=true", out)
        self.assertIn("resist_element_resistance", out)

    def test_flat_hell_mix_build_has_at_least_one_real_safe_transplant(self):
        result = self.run_build(
            "--rounds", "30", "--seed", "20260805",
            "--difficulty", "hell", "--ignore-plan", "--mix")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        match = re.search(r"\[MIX\] 实际拼接 (\d+) 层", out)
        self.assertIsNotNone(match, out)
        self.assertGreater(int(match.group(1)), 0, out)
        donors = re.findall(r"第\d+战 \[拼·([^ ]+) @", out)
        self.assertEqual(len(donors), int(match.group(1)), out)
        strict, safe = rb.load_transplant_policy()
        self.assertTrue(strict)
        for donor_group in donors:
            self.assertTrue(set(donor_group.split(",")) <= safe, donor_group)

        with self.subTest("foreign terrain pin cannot relocate an identity-locked boss"):
            pinned = self.run_build_with_plan(
                {"floors": {"5": {
                    "terrain": "dark_matter_80", "boss": "shark"}}},
                "--rounds", "8", "--seed", "2", "--difficulty", "normal",
                audit_table_mutations=True)
            pinned_out = pinned.stdout + pinned.stderr
            self.assertNotEqual(pinned.returncode, 0, pinned_out)
            self.assertIn("identity-locked", pinned_out)
            self.assertIn("shark", pinned_out)
            self.assertIn("异地", pinned_out)
            self.assertNotIn("mod_rogue_boss5", pinned_out)
            self.assertNotIn("field=mod_rogue_f5", pinned_out)
            self.assertIn(
                '"round_field_present": false, "round_zone_present": false',
                pinned_out)

        with self.subTest("native terrain keeps identity-locked boss wholly original"):
            native = self.run_build_with_plan(
                {"floors": {"5": {
                    "terrain": "multi_normal_1_23_4", "boss": "shark"}}},
                "--rounds", "8", "--seed", "2", "--difficulty", "normal",
                "--curse", "off", "--hp-base", "0.0556",
                audit_table_mutations=True)
            native_out = native.stdout + native.stderr
            self.assertEqual(native.returncode, 0, native_out)
            self.assertIn("[身份锁] round=5", native_out)
            self.assertRegex(
                native_out,
                r"第5战 \[原味·shark\].*field=multi_normal_1_23_4\b")
            self.assertNotIn("mod_rogue_boss5", native_out)
            self.assertNotIn("field=mod_rogue_f5", native_out)
            self.assertIn(
                '"round_field_present": false, "round_zone_present": false',
                native_out)
            self.assertIn("9 关解析链复核通过", native_out)


class RerollProfileForwardingCase(unittest.TestCase):
    def test_ramp_is_explicitly_forwarded_and_flat_remains_default(self):
        base = dict(rounds=30, enemy_level="ramp", curse=None, mix=True,
                    difficulty="hell", apply=False)
        flat = rr.build_command(mock.Mock(ramp=False, **base), seed=123)
        ramp = rr.build_command(mock.Mock(ramp=True, **base), seed=123)
        self.assertNotIn("--ramp", flat)
        self.assertIn("--ramp", ramp)
        self.assertEqual(flat[1:3], ["-X", "utf8"])
        self.assertIn("--difficulty", flat)
        self.assertEqual(flat[flat.index("--difficulty") + 1], "hell")

    def test_reroll_help_is_utf8_safe_without_environment_override(self):
        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run(
            [sys.executable, str(Path(rr.__file__).resolve()), "--help"],
            cwd=Path(rr.__file__).resolve().parent.parent, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--ramp", result.stdout)


class FixedSlotQuotaCase(unittest.TestCase):
    """固定位 boss 必须**预登记配额**(2026-07-29 交叉核查抓到的真 bug)。

    楼层按 r 升序生成、used_counts 选完才写,而 `steampunk_another` 仍是
    领主战(44)/降临讨伐(36)两个池的成员(lv100,四道筛子刷不掉),
    于是塔腰固定位之前的锚位能把它抽走 → 一座塔出两次(1.4.238 实际发生过)。
    """

    def test_phenomena_still_lives_in_the_source_pools(self):
        """这条是 bug 的前提:它**没有**被从池里剔除,所以必须靠配额挡。"""
        for cat in ("boss_battle", "advent"):
            try:
                fields = {e["field"] for e in rb.quest_pool(cat)}
            except FileNotFoundError:
                self.skipTest("store 不可用")
            self.assertIn("steampunk_another", fields, cat)

    def test_phenomena_and_dragon_are_scheduled_as_fixed_slots(self):
        class R:
            def random(self):
                return 0.99
        s = rb.build_schedule(30, R())
        self.assertEqual(s[15], "机工神兵")
        self.assertEqual(s[30], "终始之龙")


class CurseConflictCase(unittest.TestCase):
    """诅咒冲突闸(2026-07-29,全塔烈狱前的必修)。

    「三重壁垒」上线后实测:深层烈狱 20000 次采样里
      · 绝对壁垒+三重壁垒 同层 5.9%
      · **四系全免疫 = 无解层 1.26%**(绝对壁垒免疫的那系正好是三重壁垒放行的那系)
      · 条件槽被填满 30.3%(超出的被 conds[:5] 静默截断)
    全塔烈狱会放大这两个概率,所以拦在抽取环节。
    """

    def test_all_four_immune_is_a_conflict(self):
        a = {"name": "绝对壁垒", "cond": [("0", "1")]}
        b = {"name": "三重壁垒", "cond": [("1", "1"), ("2", "1"), ("3", "1")]}
        why = rb.curse_conflict([a, b])
        self.assertIsNotNone(why)
        self.assertIn("无解", why)

    def test_same_kind_opposite_signs_is_a_conflict(self):
        """同 kind 正负并存 = 自相矛盾。⚠ 判据看**符号**,不是"是不是 1.0"——
        第一版只拦「完全免疫 1.0 + 易伤」,漏掉 0.3/0.4/0.5 三档抗性配易伤。
        全库两两普查:深渊壁垒+深渊逆鳞 **16/16 恒冲突**。"""
        weak = {"name": "深渊逆鳞", "cond": [("0", "-0.5")]}
        for other, why in (
                ({"name": "三重壁垒", "cond": [("0", "1"), ("1", "1"), ("3", "1")]}, "免疫"),
                ({"name": "深渊壁垒", "cond": [(str(k), "0.3") for k in range(4)]}, "0.3 抗性"),
                ({"name": "亡者不屈", "cond": [("4", ""), ("0", "0.5")]}, "0.5 抗性"),
                ({"name": "深渊重甲", "cond": [("0", "0.4")]}, "0.4 抗性")):
            self.assertIn("自相矛盾", rb.curse_conflict([other, weak]) or "", why)

    def test_merge_collapses_same_sign_duplicates(self):
        """同 kind 同号取绝对值最大的一条,腾出槽位。"""
        a = {"name": "深渊壁垒", "cond": [(str(k), "0.3") for k in range(4)]}
        b = {"name": "亡者不屈", "cond": [("4", ""), ("0", "0.5")]}
        merged = rb.merge_conds([a, b])
        self.assertEqual(len(merged), 5)                    # 减益免疫 + 四系
        self.assertIn(("4", ""), merged)
        self.assertEqual(dict(merged)["0"], rb.fmt(0.5))    # 0.3 被 0.5 盖住
        self.assertEqual(dict(merged)["1"], rb.fmt(0.3))
        self.assertIsNone(rb.curse_conflict([a, b]))        # 合并后装得下,不算冲突

    def test_merge_keeps_the_stronger_immunity(self):
        a = {"name": "亡者不屈", "cond": [("4", ""), ("0", "0.5")]}
        b = {"name": "绝对壁垒", "cond": [("0", "1")]}
        self.assertEqual(dict(rb.merge_conds([a, b]))["0"], rb.fmt(1.0))

    def test_no_duplicate_kind_survives_to_output(self):
        """9000 层采样级不变式:输出的条件槽里同一 kind 不该出现两次。"""
        import random as _r
        for seed in range(2500):
            cs = rb.abyss_curses(29, 30, _r.Random(seed), "hell",
                                 caps={"boss": True})["conds"]
            kinds = [k for k, _v in cs]
            self.assertEqual(len(kinds), len(set(kinds)), f"seed {seed} 同 kind 重复")

    def test_single_channel_combo_is_coherent(self):
        """【单通道】的易伤必须落在三重壁垒**放行**的那一系(weak 绑定 wall_open)。"""
        import random as _r
        checked = 0
        for seed in range(1500):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell", caps={"boss": True})
            if not out["desc"].startswith("【单通道】"):
                continue
            checked += 1
            # 2026-08-05 需求:伤害类型免疫也必须不可驱散,因此三重壁垒已从
            # quest c71-80 迁到 CreateCondition 硬通道；断言必须读合并后的双轴。
            imm, _elements = rb.immunity_axes(out["picks"])
            weak = {k for k, v in out["conds"]
                    if v not in ("", "(None)") and float(v) < 0}
            self.assertEqual(len(imm), 3, seed)
            self.assertTrue(weak and not (weak & imm), f"seed {seed} 易伤落在免疫系上")
        self.assertGreater(checked, 20, "样本太少,没真正验到")

    def test_three_immune_plus_a_spared_type_is_fine(self):
        # 绝对壁垒免疫的是三重壁垒**已经免疫**的那系 → 仍剩一系能打
        a = {"name": "绝对壁垒", "cond": [("1", "1")]}
        b = {"name": "三重壁垒", "cond": [("1", "1"), ("2", "1"), ("3", "1")]}
        self.assertIsNone(rb.curse_conflict([a, b]))

    def test_merge_makes_slot_overflow_unreachable(self):
        """合并同 kind 之后最多 5 条(伤害四系 + 减益免疫),槽位再也溢不出去。

        深渊壁垒(4条) + 三重壁垒(3条) 原本 7 条会被 `conds[:5]` 截断,
        合并后是 4 条(能力0.3 + 其余三系免疫),装得下 ⇒ 不再算冲突。
        `curse_conflict` 里的溢出分支因此成了防御性代码(kind 枚举扩了才会触发)。
        """
        a = {"name": "深渊壁垒", "cond": [(str(k), "0.3") for k in range(4)]}
        b = {"name": "三重壁垒", "cond": [("1", "1"), ("2", "1"), ("3", "1")]}
        merged = rb.merge_conds([a, b])
        self.assertEqual(len(merged), 4)
        self.assertIsNone(rb.curse_conflict([a, b]))
        # 不变式:任意诅咒组合合并后都 ≤5
        import random as _r
        pool = rb._curse_pool(2, _r.Random(0))
        import itertools
        for n in (2, 3):
            for combo in itertools.combinations(pool, n):
                self.assertLessEqual(len(rb.merge_conds(list(combo))), 5)

    def test_damage_resistance_below_one_never_locks(self):
        a = {"name": "深渊壁垒", "cond": [(str(k), "0.3") for k in range(4)]}
        self.assertIsNone(rb.curse_conflict([a]))

    def test_any_positive_element_resistance_consumes_the_unaffected_exit(self):
        # r=1/9 不是高阻断，但仍算“受影响”；六属性全受影响也必须拒绝。
        low = {"name": "低阻测试", "element_resistance": [
            (1, 1.0), (2, 9.0), (3, 1.0), (4, 9.0), (5, 1.0), (6, 9.0)]}
        self.assertEqual(rb.immunity_axes([low])[1], set())
        self.assertIn("完全不受影响", rb.curse_conflict([low]) or "")

    def test_overlapping_element_resistance_matches_client_addition(self):
        # 同 cancelable 组内累加；两组必须分开落树，但可解性仍跨组求和。
        picks = [
            {"name": "甲", "element_resistance": [(1, 1.0), (2, 99.0)]},
            {"name": "乙", "element_resistance": [(1, 9.0, False),
                                                     (2, 999.0, True),
                                                     (3, 1.0, True)]},
        ]
        self.assertEqual(rb._merged_resistance(picks, "element_resistance"),
                         [(1, 10.0, False), (2, 1098.0, False),
                          (3, 1.0, True)])

    def test_live_sampling_has_no_softlock(self):
        """真抽 4000 次,双轴都至少留一个出口,且条件槽不溢出。"""
        import random as _r
        for seed in range(4000):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell",
                                  caps={"boss": True, "element": True})
            conds = out["conds"]
            self.assertLessEqual(len(conds), 5, seed)
            damage, elements = rb.immunity_axes(out["picks"])
            self.assertLess(len(damage), 4, f"seed {seed} 四伤害类型全免疫")
            self.assertLess(len(elements), 6, f"seed {seed} 六属性高阻断")
            affected = {e for e, value in rb._resistance_totals_by_target(
                out["picks"], "element_resistance").items() if value > 0}
            self.assertLess(len(affected), 6, f"seed {seed} 六属性全受影响")

    def test_cross_curse_element_immunity_is_merged_before_gate(self):
        a = {"name": "高阻甲", "element_resistance": [(1, 99.0), (2, 99.0), (3, 99.0)]}
        b = {"name": "高阻乙", "element_resistance": [(4, 999.0), (5, 99.0), (6, 99.0)]}
        why = rb.curse_conflict([a, b])
        self.assertIn("六属性", why or "")
        self.assertIn("完全不受影响", why or "")

    def test_five_element_immunities_still_leave_one_exit(self):
        a = {"name": "五相绝域", "element_resistance": [(e, 999.0) for e in range(1, 6)]}
        self.assertIsNone(rb.curse_conflict([a]))

    def test_hard_damage_immunities_share_the_same_gate(self):
        a = {"name": "三重壁垒", "damage_resistance": [(0, 1.0), (1, 1.0), (2, 1.0)]}
        self.assertIsNone(rb.curse_conflict([a]))
        b = {"name": "绝对壁垒", "damage_resistance": [(3, 1.0)]}
        self.assertIn("四种伤害类型", rb.curse_conflict([a, b]) or "")

    def test_runtime_gate_rejects_c86_overflow_and_dangerous_short_time(self):
        wall = {"name": "血肉高墙", "hp": 2.5}
        why = rb.curse_runtime_conflict(
            [wall], baseline_c86=5.0, c86_limits=(0.1, 10.0),
            baseline_dps=5_000_000.0, base_duration_s=900.0)
        self.assertIn("c86", why or "")

        timed = {"name": "时之枷锁", "time": 10_800}
        why = rb.curse_runtime_conflict(
            [timed], baseline_c86=2.0, c86_limits=(0.1, 30.0),
            baseline_dps=5_000_000.0, base_duration_s=900.0)
        self.assertIn("短时限", why or "")

        glass_timed = [timed, {"name": "玻璃深渊", "hp": 0.5}]
        self.assertIsNone(rb.curse_runtime_conflict(
            glass_timed, baseline_c86=2.0, c86_limits=(0.1, 30.0),
            baseline_dps=5_000_000.0, base_duration_s=900.0))

    def test_general_hp_curse_uses_boss_level_without_moving_c86(self):
        wall = {"name": "血肉高墙", "hp": 2.5}
        self.assertIsNone(rb.curse_runtime_conflict(
            [wall], baseline_c86=1.0, c86_limits=(1.0, 1.0),
            baseline_dps=5_000_000.0, base_duration_s=900.0,
            hp_channel="boss_level"))
        why = rb.curse_runtime_conflict(
            [wall, {"name": "时之枷锁", "time": 10_800}],
            baseline_c86=1.0, c86_limits=(1.0, 1.0),
            baseline_dps=5_000_000.0, base_duration_s=900.0,
            hp_channel="boss_level")
        self.assertIn("短时限", why or "")

    def test_stacked_and_one_shot_damage_resistance_merge_before_exit_gate(self):
        """叠层 90% + 单条 10% 已封死该伤害类型，不能各看各的。"""
        stacked = [
            {"name": f"叠层{k}", "stacked_resistance": [
                (rb.DAMAGE_RESISTANCE_AC[k], 0.01, 90)]}
            for k in range(4)
        ]
        one_shot = {"name": "补足", "damage_resistance": [
            (k, 0.1) for k in range(4)]}
        why = rb.curse_conflict(stacked + [one_shot])
        self.assertIn("四种伤害类型", why or "")
        self.assertEqual(rb.immunity_axes(stacked)[0], set())


class StackedResistanceCase(unittest.TestCase):
    def test_depth_schedule_is_20_50_90(self):
        self.assertEqual(rb.stacked_resistance_layers_for_depth(1, 30), 20)
        self.assertEqual(rb.stacked_resistance_layers_for_depth(6, 30), 20)
        self.assertEqual(rb.stacked_resistance_layers_for_depth(7, 30), 50)
        self.assertEqual(rb.stacked_resistance_layers_for_depth(24, 30), 50)
        self.assertEqual(rb.stacked_resistance_layers_for_depth(25, 30), 90)
        self.assertEqual(rb.stacked_resistance_layers_for_depth(30, 30), 90)

    def test_damage_entry_text_is_derived_from_layers_and_strength(self):
        entry = rb.stacked_resistance_entry(
            "层叠龙鳞", "ACDirectAttackDamageResistance", 0.01, 70)
        self.assertEqual(entry["stacked_resistance"], [
            ("ACDirectAttackDamageResistance", 0.01, 70)])
        self.assertEqual(entry["text"], "直击抗性×70层（减70%）")

    def test_debuff_entry_derives_hit_rate_penalty_and_discloses_force_apply(self):
        # ConditionChangeCalculator.as:93 是 hitRate-r；随机数包含 0，故 r=1、
        # hitRate=1 仍有约十万分之一漏过，不能钉死成“单层完全免疫”。
        entry = rb.stacked_resistance_entry(
            "不屈龙心", "ACToleranceOfDebuff", 1.0, 20)
        self.assertIn("×20层", entry["text"])
        self.assertIn("普通减益几乎无法命中", entry["text"])
        self.assertIn("强制赋予除外", entry["text"])
        self.assertNotIn("百分点", entry["text"])

    def test_pool_contains_one_damage_variant_and_debuff_variant(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(
            2, _r.Random(5), stack_layers=50)}
        self.assertEqual(pool["层叠龙鳞"]["stacked_resistance"][0][2], 50)
        self.assertEqual(pool["不屈龙心"]["stacked_resistance"], [
            ("ACToleranceOfDebuff", 1.0, 50)])

    def test_tree_repeats_official_create_condition_shape_per_layer(self):
        spec = [("ACDirectAttackDamageResistance", 0.01, 3)]
        tree = rb.build_immunity_dsl_tree([], [], spec)
        commands = tree[-1][1]
        self.assertEqual(len(commands), 3)
        for wrapper in commands:
            command = wrapper[1]
            self.assertEqual(command[0], "CreateCondition")
            self.assertEqual(command[1], -17)
            self.assertEqual(command[2], [[
                "ACDirectAttackDamageResistance",
                rb._slv(9_999_999), rb._slv(0.01), rb._slv(99)]])
            self.assertEqual(command[4], ["None"])
            self.assertIs(command[5], False)       # cancelable=false
            self.assertIs(command[6], True)        # 官方允许同帧同条件重复，才能叠层
            self.assertEqual(command[10], 3)
            self.assertEqual(command[11], rb._slv(1))

    def test_debuff_constructor_round_trips_without_silent_index_fallback(self):
        tree = rb.build_immunity_dsl_tree(
            [], [], [("ACToleranceOfDebuff", 1.0, 2)])
        blob = rb.build_immunity_dsl_blob(tree)
        parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
        self.assertEqual(parsed, tree)
        names = [cmd[1][2][0][0] for cmd in tree[-1][1]]
        self.assertEqual(names, ["ACToleranceOfDebuff"] * 2)

    def test_invalid_constructor_strength_and_layer_count_fail_loudly(self):
        for spec in [
                [("NoSuchCondition", 0.01, 20)],
                [("ACSkillDamageResistance", 0, 20)],
                [("ACSkillDamageResistance", 0.01, 0)],
                [("ACSkillDamageResistance", 0.01, 100)]]:
            with self.assertRaises(ValueError, msg=spec):
                rb.build_immunity_dsl_tree([], [], spec)


class HighMobilityCase(unittest.TestCase):
    def test_loader_accepts_nonempty_prefixes_and_rejects_malformed_values(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "special.json"
            valid = {"high_threat": {
                "prefixes": ["guardian_golem"],
                "exact": ["lich_wind_expert_100"],
            }}
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(
                rb.load_high_threat_rules(path),
                (("guardian_golem",), frozenset({"lich_wind_expert_100"})))
            malformed = [
                {},
                {"high_threat": None},
                {"high_threat": {"exact": []}},
                {"high_threat": {"prefixes": []}},
                {"high_threat": {"prefixes": "guardian_golem", "exact": []}},
                {"high_threat": {"prefixes": [], "exact": "lich_wind_expert_100"}},
                {"high_threat": {"prefixes": [""], "exact": []}},
                {"high_threat": {"prefixes": [], "exact": [1]}},
            ]
            for bad in malformed:
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises((ValueError, TypeError), msg=bad):
                    rb.load_high_threat_rules(path)

    @requires_store
    def test_guardian_golem_family_matches_after_hp_pick_before_clone(self):
        prefixes = ("guardian_golem",)
        exact = frozenset({"lich_wind_expert_100"})
        self.assertTrue(rb.is_high_threat_bosses(
            ["guardian_golem_fire_single"], prefixes, exact))
        self.assertTrue(rb.is_high_threat_bosses(
            ["guardian_golem_another_water_ex"], prefixes, exact))
        self.assertTrue(rb.is_high_threat_bosses(
            ["lich_wind_expert_100"], prefixes, exact))
        self.assertFalse(rb.is_high_threat_bosses(
            ["lich_wind_expert_80"], prefixes, exact))
        self.assertFalse(rb.is_high_threat_bosses(
            ["mod_rogue_boss5"], prefixes, exact))

        # --test-field 的首抽 water_sphere 无法挂法阵，retry 固定换成 guardian。
        # 分类若仍在 retry 前执行，abyss_curses 会收到旧 pick 的 threat=False。
        state = {"tower_calls": 0, "chosen": [], "probe": None}
        original_schedule = rb.build_schedule
        original_prefer = rb.prefer_non_threat_candidates
        original_curses = rb.abyss_curses

        def schedule(n, rng):
            result = original_schedule(n, rng)
            result.pop(1, None)  # 让第1战走 tower_pick，且避开 HP 重排干扰
            return result

        def prefer(candidates, r, n, bosses_of, rule_prefixes, rule_exact):
            if r == 1 and candidates and isinstance(candidates[0][0], str):
                state["tower_calls"] += 1
                needle = ("water_sphere_single" if state["tower_calls"] == 1
                          else "guardian_golem_fire_single")
                chosen = next(item for item in candidates if needle in item[2])
                state["chosen"].append(tuple(chosen[2]))
                return [chosen]
            return original_prefer(
                candidates, r, n, bosses_of, rule_prefixes, rule_exact)

        def classify(_bosses, _prefixes, _exact):
            return state["tower_calls"] >= 2

        def curses(r, n, rng, tier, caps=None, forced=None, no_base=False,
                   **kwargs):
            if r == 1:
                state["probe"] = (state["tower_calls"], kwargs.get("high_threat"))
            return original_curses(
                r, n, rng, tier, caps, forced, no_base, **kwargs)

        argv = [rb.__file__, "--rounds", "30", "--seed", "20260805",
                "--difficulty", "hell", "--ignore-plan", "--test-field", "1"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(rb, "build_schedule", schedule), \
                mock.patch.object(rb, "prefer_non_threat_candidates", prefer), \
                mock.patch.object(rb, "is_high_threat_bosses", classify), \
                mock.patch.object(rb, "abyss_curses", curses), \
                mock.patch.object(rb, "load_boss_history", return_value=[]), \
                mock.patch("builtins.print"):
            rb.main()
        self.assertEqual(state["chosen"], [
            ("water_sphere_single",), ("guardian_golem_fire_single",)])
        self.assertEqual(state["probe"], (2, True),
                         "最终 guardian 必须在派生 high_threat 状态前完成 retry")

    def test_shared_gate_bans_time_high_element_wall_and_hp_above_1_5(self):
        self.assertIn("高威胁", rb.high_threat_curse_conflict([
            {"name": "时之枷锁", "time": 10_800}]) or "")
        self.assertIsNone(rb.high_threat_curse_conflict([
            {"name": "元素滞钝", "element_resistance": [(1, 1.0)]}]))
        self.assertIsNone(rb.high_threat_curse_conflict([
            {"name": "三相封界", "element_resistance": [(1, 9.0)]}]))
        self.assertIn("高档属性", rb.high_threat_curse_conflict([
            {"name": "元素禁壁", "element_resistance": [(1, 99.0)]}]) or "")
        self.assertIsNone(rb.high_threat_curse_conflict([
            {"name": "混相软墙", "element_resistance": [
                (1, 1.0, False), (1, 9.0, True)]}]))
        self.assertIn("高档属性", rb.high_threat_curse_conflict([
            {"name": "混相跨组硬墙", "element_resistance": [
                (1, 50.0, False), (1, 49.0, True)]}]) or "")
        self.assertIsNone(rb.high_threat_curse_conflict([
            {"name": "上限", "hp": 1.5}]))
        self.assertIn("1.5", rb.high_threat_curse_conflict([
            {"name": "越界", "hp": 1.5001}]) or "")

    def test_high_threat_hp_cap_uses_final_product_and_forced_order_is_irrelevant(self):
        """2.5×0.5=1.25 合法；门禁不能按单个词条错杀或受钉选顺序影响。"""
        import random as _r
        pool = [
            {"name": "血肉高墙", "hp": 2.5, "text": "敌血×2.5"},
            {"name": "玻璃深渊", "hp": 0.5, "atk": 2.6,
             "atk_tier": 2, "text": "敌攻×2.6·血-50%"},
            {"name": "填充甲", "text": "甲"},
            {"name": "填充乙", "text": "乙"},
        ]
        self.assertIsNone(rb.high_threat_curse_conflict(pool[:2]))
        outputs = []
        for forced_names in (["血肉高墙", "玻璃深渊"],
                             ["玻璃深渊", "血肉高墙"]):
            with mock.patch.object(rb, "_curse_pool", return_value=pool):
                out = rb.abyss_curses(
                    5, 30, _r.Random(9), "hell",
                    {"boss": True, "element": True, "panel": True},
                    forced={"curses": forced_names}, high_threat=True)
            outputs.append(out)
        for out in outputs:
            self.assertEqual({p["name"] for p in out["picks"]},
                             {"血肉高墙", "玻璃深渊"})
            self.assertAlmostEqual(out["hp"], 1.25)

    def test_forced_forbidden_terms_log_and_redraw_without_underfill(self):
        import random as _r
        pool = [
            {"name": "时之枷锁", "time": 10_800, "text": "限时3分"},
            {"name": "五相绝域", "element_resistance": [(e, 999.0)
                                                       for e in range(1, 6)],
             "text": "高档属性"},
            {"name": "血肉高墙", "hp": 2.5, "text": "敌血×2.5"},
            {"name": "填充甲", "text": "甲"},
            {"name": "填充乙", "text": "乙"},
            {"name": "填充丙", "text": "丙"},
            {"name": "填充丁", "text": "丁"},
        ]
        with mock.patch.object(rb, "_curse_pool", return_value=pool), \
                mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(
                5, 30, _r.Random(9), "hell",
                {"boss": True, "element": True, "panel": True},
                forced={"curses": ["时之枷锁", "五相绝域", "血肉高墙"]},
                high_threat=True)
        self.assertEqual(len(out["picks"]), 3)
        self.assertLessEqual(out["hp"], 1.5)
        self.assertIsNone(rb.high_threat_curse_conflict(out["picks"]))
        logged = "\n".join(str(c.args[0]) for c in logger.call_args_list)
        for name in ("时之枷锁", "五相绝域", "血肉高墙"):
            self.assertIn(name, logged)
        self.assertIn("高威胁", logged)


class ElementImmunityDslCase(unittest.TestCase):
    def test_wall_family_uses_non_dispellable_channel(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(5))}
        for name in ("深渊壁垒", "绝对壁垒", "三重壁垒"):
            self.assertIn("damage_resistance", pool[name], name)
            self.assertNotIn("cond", pool[name], name)

    def test_element_resistance_labels_follow_division_formula(self):
        self.assertEqual(rb.resistance_label(1.0), "伤害减半")
        self.assertEqual(rb.resistance_label(9.0), "伤害降至1/10")
        self.assertEqual(rb.resistance_label(99.0), "伤害降至1%")
        self.assertEqual(rb.resistance_label(999.0), "伤害降至0.1%")
        for value in (0.0, -1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=value):
                rb.resistance_label(value)

    def test_new_family_covers_four_strength_tiers(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(7))}
        expected = {
            "元素滞钝": (1, 1.0, "伤害减半"),
            "元素禁壁": (1, 99.0, "伤害降至1%"),
            "三相封界": (3, 9.0, "伤害降至1/10"),
            "五相绝域": (5, 999.0, "伤害降至0.1%"),
        }
        self.assertTrue(set(expected) <= set(pool))
        for name, (count, strength, label) in expected.items():
            vals = pool[name]["element_resistance"]
            self.assertEqual(len(vals), count, name)
            self.assertTrue(all(1 <= e <= 6 and value == strength
                                for e, value, _cancelable in vals), name)
            self.assertIn(label, pool[name]["text"], name)
            self.assertNotIn("完全免疫", pool[name]["text"], name)
        forced = [
            {"element": 1, "strength": 1.0},
            {"element": 2, "strength": 999.0},
            {"element": 3, "strength": 999.0},
            {"element": 6, "strength": 999.0},
        ]
        mixed = rb.mixed_element_entry(
            _r.Random(1), strengths=(1, 9, 99, 999), forced=forced)
        self.assertEqual(mixed["element_resistance"], [
            (1, 1.0, False), (2, 999.0, False),
            (3, 999.0, False), (6, 999.0, False)])
        self.assertIn("火伤害减半", mixed["text"])
        self.assertIn("水伤害降至0.1%", mixed["text"])
        self.assertNotIn("风", mixed["text"])
        self.assertNotIn("光", mixed["text"])
        self.assertNotIn("可驱散", mixed["text"])
        soft_cards = [rb.mixed_element_entry(_r.Random(seed), strengths=(1,))
                      for seed in range(400)]
        dispellable = sum(any(atom[2] for atom in card["element_resistance"])
                          for card in soft_cards)
        self.assertTrue(75 <= dispellable <= 125, dispellable)
        hard = rb.mixed_element_entry(_r.Random(3), strengths=(99, 999))
        self.assertTrue(all(atom[2] is False for atom in hard["element_resistance"]))
        soft_names = ("深渊壁垒", "绝对壁垒", "三重壁垒", "元素滞钝", "三相封界")
        counts = dict.fromkeys(soft_names, 0)
        for seed in range(400):
            sampled = {c["name"]: c for c in rb._curse_pool(0, _r.Random(seed))}
            for soft_name in soft_names:
                key = ("element_resistance" if "元素" in soft_name or "三相" in soft_name
                       else "damage_resistance")
                counts[soft_name] += any(atom[2] for atom in sampled[soft_name][key])
        for soft_name, got in counts.items():
            self.assertTrue(70 <= got <= 130, (soft_name, got))
        hard_pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(88))}
        for hard_name in ("绝对壁垒", "三重壁垒", "元素禁壁", "五相绝域"):
            key = "element_resistance" if "元素" in hard_name or "五相" in hard_name else "damage_resistance"
            self.assertTrue(all(atom[2] is False for atom in hard_pool[hard_name][key]))

    def test_random_element_tiers_are_depth_scheduled(self):
        self.assertEqual(rb.element_curse_names_for_depth(1, 30), {"元素滞钝", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(6, 30), {"元素滞钝", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(7, 30),
                         {"元素滞钝", "三相封界", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(15, 30),
                         {"元素滞钝", "三相封界", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(16, 30),
                         {"三相封界", "元素禁壁", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(24, 30),
                         {"三相封界", "元素禁壁", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(25, 30),
                         {"元素禁壁", "五相绝域", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(30, 30),
                         {"元素禁壁", "五相绝域", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(30, 30, "standard"),
                         {"元素滞钝", "混相禁域"})
        self.assertEqual(rb.element_curse_names_for_depth(30, 30, "abyss"),
                         {"元素滞钝", "三相封界", "混相禁域"})
        for r, want in ((1, (1,)), (7, (1, 9)),
                        (16, (1, 9, 99)), (25, (1, 9, 99, 999))):
            self.assertEqual(rb.element_strengths_for_depth(r, 30), want)

    def test_forced_high_tier_survives_shallow_random_schedule(self):
        import random as _r
        out = rb.abyss_curses(
            5, 30, _r.Random(20260805), "hell",
            {"boss": True, "element": True, "panel": True},
            forced={"curses": ["五相绝域"]})
        self.assertIn("五相绝域", [c["name"] for c in out["picks"]])
        forced_mix = [
            {"element": 1, "strength": 1}, {"element": 2, "strength": 999},
            {"element": 3, "strength": 999}, {"element": 6, "strength": 999},
        ]
        mixed = rb.abyss_curses(
            5, 30, _r.Random(20260805), "hell",
            {"boss": True, "element": True, "panel": True},
            forced={"curses": ["混相禁域"], "element_mix": forced_mix})
        card = next(c for c in mixed["picks"] if c["name"] == "混相禁域")
        self.assertEqual(card["element_resistance"], [
            (1, 1.0, False), (2, 999.0, False),
            (3, 999.0, False), (6, 999.0, False)])

    def test_random_selection_uses_the_depth_filtered_pool(self):
        import random as _r
        fillers = [{"name": f"填充{i}", "text": f"填充{i}"} for i in range(4)]
        element_entries = [
            {"name": "元素滞钝", "text": "低", "element_resistance": [(1, 1.0)]},
            {"name": "元素禁壁", "text": "高", "element_resistance": [(2, 99.0)]},
            {"name": "三相封界", "text": "中", "element_resistance": [(3, 9.0)]},
            {"name": "五相绝域", "text": "极", "element_resistance": [(4, 999.0)]},
        ]
        with mock.patch.object(rb, "_curse_pool", return_value=fillers + element_entries):
            shallow = rb.abyss_curses(
                5, 30, _r.Random(1), "hell", {"element": True})
            deep = rb.abyss_curses(
                29, 30, _r.Random(1), "hell", {"element": True})
        self.assertFalse({"元素禁壁", "三相封界", "五相绝域"} &
                         {c["name"] for c in shallow["picks"]})
        self.assertFalse({"元素滞钝", "三相封界"} &
                         {c["name"] for c in deep["picks"]})

    def test_tree_uses_the_pinned_create_condition_shape(self):
        tree = rb.build_immunity_dsl_tree(
            [(0, 1.0, True), (3, 0.7, True)],
            [(1, 1.0, True), (6, 999.0, True)])
        self.assertEqual(len(tree[-1][1]), 2)
        hard_command = tree[-1][1][0][1]
        command = tree[-1][1][1][1]
        params = command[1:]
        self.assertEqual(tree[1], 1)                       # enemy action DSL 版本
        self.assertEqual(command[0], "CreateCondition")
        self.assertEqual(params[0], -17)                 # subject=自身
        self.assertIs(params[4], True)                   # 软原子共享可驱散组
        self.assertEqual(params[9], 3)                   # 目标种类必填 3
        names = [ac[0] for ac in params[1]]
        self.assertEqual(names, ["ACSkillDamageResistance", "ACToleranceOfElement"])
        hard_params = hard_command[1:]
        self.assertIs(hard_params[4], False)              # r>=1/r>=99 强制不可驱散
        self.assertEqual([ac[0] for ac in hard_params[1]],
                         ["ACAbilityDamageResistance", "ACToleranceOfElement"])
        self.assertEqual(hard_params[1][1][2], 6)         # 数据层 1-based
        self.assertEqual(hard_params[1][1][3][0]["min"], 999.0)

    def test_blob_round_trip_preserves_constructor_names(self):
        tree = rb.build_immunity_dsl_tree(
            [(2, 0.7, True)], [(2, 9.0, True), (5, 99.0, False)])
        blob = rb.build_immunity_dsl_blob(tree)
        parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
        self.assertEqual(parsed, tree)
        false_id = rb.immunity_program([], [(2, 9.0, False)])[0]
        true_id = rb.immunity_program([], [(2, 9.0, True)])[0]
        self.assertNotEqual(false_id, true_id)
        self.assertEqual(
            rb.immunity_program([], [(5, 99.0, True)])[0],
            rb.immunity_program([], [(5, 99.0, False)])[0],
            "硬墙 true 必须先规范化为 false，不得多锻一个等价程序")

    def test_invalid_element_codes_fail_loudly(self):
        for element in (0, 7, 254, 255):
            with self.assertRaises(ValueError, msg=element):
                rb.build_immunity_dsl_tree([], [(element, 1.0)])
        import random as _r
        bad_forced = [
            [],
            [{"element": 0, "strength": 1}],
            [{"element": 1, "strength": 7}],
            [{"element": 1, "strength": 1}, {"element": 1, "strength": 9}],
            [{"element": e, "strength": 1} for e in range(1, 7)],
        ]
        for forced in bad_forced:
            with self.assertRaises(ValueError, msg=forced):
                rb.mixed_element_entry(_r.Random(1), (1, 9, 99, 999), forced)

    def test_invalid_element_strengths_fail_loudly(self):
        for strength in (0.0, -1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError, msg=strength):
                rb.build_immunity_dsl_tree([], [(1, strength)])

    def test_pre_action_is_appended_and_rerun_is_enabled(self):
        row = [""] * 162
        row[109] = "official/pre,official/pre2"
        row[110] = "false"
        row[111] = "official/action"
        node = {"80": rb.join(row, False)}
        got = rb.rewrite_boss_carrier_node(
            node, action_program="mod/field", pre_action_program="mod/immunity")
        cols = rb.cells(got["80"])
        self.assertEqual(cols[109], "official/pre,official/pre2,mod/immunity")
        self.assertEqual(cols[110], "true")
        self.assertEqual(cols[111], "official/action,mod/field")

    def test_two_field_programs_share_one_carrier_without_duplication(self):
        row = [""] * 162
        row[111] = "official/action"
        node = {"80": rb.join(row, False)}
        got = rb.rewrite_boss_carrier_node(
            node, action_programs=("mod/field_a", "mod/field_b", "mod/field_a"))
        programs = rb.cells(got["80"])[111].split(",")
        self.assertEqual(programs, ["official/action", "mod/field_a", "mod/field_b"])


class GeneralBossElementResistanceCase(unittest.TestCase):
    @staticmethod
    def _node(value: str, *, short: bool = False):
        row = [""] * (20 if short else 162)
        if not short:
            row[36] = value
            row[109] = "official/pre,with-comma"
            row[110] = "false"
        return {"80": {"variant": rb.join(row, False)}}

    def test_c36_true_blocks_the_actual_cloned_row(self):
        gb = {"source": self._node("true")}
        gb["mod_rogue_boss4"] = gb["source"]
        why = rb.general_boss_element_immunity_block(gb, "mod_rogue_boss4")
        self.assertIn("c36=true", why or "")

    def test_false_is_allowed_but_unknown_values_fail_closed(self):
        self.assertIsNone(rb.general_boss_element_immunity_block(
            {"ok": self._node("False")}, "ok"))
        for code, node in (("bad", self._node("yes")),
                           ("short", self._node("false", short=True))):
            self.assertIsNotNone(rb.general_boss_element_immunity_block({code: node}, code))
        self.assertIsNotNone(rb.general_boss_element_immunity_block({}, "missing"))

    @requires_store
    def test_known_official_prototypes_are_blocked_before_cloning(self):
        gb = q.load_table(rb.GENERAL_BOSS)
        gv = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
        # 2026-08-05 用户按 getSurjectivity 独立复算：具体塔层/clone ID 会随 seed
        # 与所选等级行变化，不能再钉“第4/13/20战”或当前 store 的 mod_rogue_boss4。
        # 门禁应先在官方原型实际等级行成立，克隆后另由构建期最终复核保证继承。
        for code, level in (("dark_matter_single", 80), ("smr21_big_boss_ex", 90),
                            ("beasts_big_boss_multi_80", 90)):
            why = rb.general_boss_element_immunity_block(gb, code, level, gv)
            self.assertIn("c36=true", why or "", code)

    def test_only_the_runtime_selected_level_row_controls_c36(self):
        gb = {"mixed": {"79": self._node("false")["80"],
                         "100": self._node("true")["80"]}}
        gv = {"mixed": {"79": "dummy", "100": "dummy"}}
        # GeneralBossSource 直接按 enemy level 在 general_boss 上取首个 ≥level 的行；
        # gv 另行解析,不能拿 gv 的下取整结果替 c36 选行。
        self.assertIsNone(rb.general_boss_element_immunity_block(gb, "mixed", 79, gv))
        self.assertIn("gb[100]", rb.general_boss_element_immunity_block(
            gb, "mixed", 90, gv) or "")

    def test_auto_high_level_future_score_attack_is_a_hard_gate(self):
        rb.assert_element_immunity_runtime_safe(rb.Q_QUEST, 100)
        with self.assertRaises(RuntimeError):
            rb.assert_element_immunity_runtime_safe(
                "master/quest/event/score_attack_event_battle_quest.orderedmap", 80)

    def test_c36_blocked_forced_curse_is_replaced_and_logged(self):
        import random as _r
        caps = {"boss": True, "element": False,
                "element_reason": "mod_rogue_boss4 c36=true"}
        forced_mix = [{"element": 1, "strength": 1},
                      {"element": 2, "strength": 999}]
        with mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(4, 30, _r.Random(20260805), "hell", caps,
                                  forced={"curses": ["混相禁域", "血肉高墙"],
                                          "element_mix": forced_mix})
        self.assertNotIn("混相禁域", [c["name"] for c in out["picks"]])
        self.assertIn("血肉高墙", [c["name"] for c in out["picks"]])
        # 被 c36 拒掉的名额必须真正换成别的诅咒，不能只记 redraw 后少发一条。
        self.assertEqual(len(out["picks"]), 2)
        self.assertTrue(any("c36=true" in str(call) and "redraw" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)

    def test_forced_cross_curse_lock_is_redrawn_to_full_quota(self):
        import random as _r
        pool = [
            {"name": "五相绝域", "text": "五免", "element_resistance":
             [(e, 999.0) for e in range(1, 6)]},
            {"name": "元素禁壁", "text": "暗免", "element_resistance": [(6, 99.0)]},
            {"name": "血肉高墙", "text": "血量", "hp": 2.0},
            {"name": "时之枷锁", "text": "限时", "time": 120},
            {"name": "深渊重甲", "text": "韧性", "tp": 9},
            {"name": "魔力枯竭", "text": "FEVER", "fever": 1200},
            {"name": "亡者不屈", "text": "减益", "cond": [("4", "")]},
        ]
        with mock.patch.object(rb, "_curse_pool", return_value=pool), \
                mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(
                29, 30, _r.Random(1), "hell",
                {"boss": True, "element": True, "panel": True},
                forced={"curses": ["五相绝域", "元素禁壁", "血肉高墙"]})
        names = [c["name"] for c in out["picks"]]
        # 任务 C：第 29 战属于最后 20%，即使工坊只钉 3 项也须回补到第 4 格；
        # 领域采用独立配额，最终应是 4 个普通诅咒 + 2 个领域，而不是总共 4 条。
        # 同时深层禁时限，所以 mock 池里的时之枷锁不能拿来凑数。
        ordinary = [c for c in out["picks"] if not c.get("caster")]
        fields = [c for c in out["picks"] if c.get("caster")]
        self.assertEqual(len(ordinary), 4)
        self.assertEqual(len(fields), 2)
        self.assertEqual(len(names), 6)
        self.assertIn("五相绝域", names)
        self.assertIn("血肉高墙", names)
        self.assertNotIn("元素禁壁", names)
        self.assertLess(len(rb.immunity_axes(out["picks"])[1]), 6)
        self.assertTrue(any("完全不受影响" in str(call) and "redraw" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)


class CurseComboCase(unittest.TestCase):
    """诅咒组合:名额 ≥2 时 55% 概率整套落地,剩余名额独立随机补。"""

    def test_combos_are_conflict_free_by_construction(self):
        """手搭的 8 套组合本身不能自带冲突。"""
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(0))}
        for cb in rb.CURSE_COMBOS:
            got = [pool[nm] for nm in cb["curses"] if nm in pool and nm != "深渊法阵"]
            self.assertIsNone(rb.curse_conflict(got), cb["name"])

    def test_combo_sizes_fit_the_deepest_quota(self):
        for cb in rb.CURSE_COMBOS:
            self.assertLessEqual(len(cb["curses"]), 3, cb["name"])

    def test_field_cat_combos_reference_real_categories(self):
        cats = {m[3] if len(m) > 3 else "领域" for m in rb.field_menu_all()}
        for cb in rb.CURSE_COMBOS:
            if cb.get("field_cat"):
                self.assertIn(cb["field_cat"], cats, cb["name"])
                self.assertIn("深渊法阵", cb["curses"], cb["name"])

    def test_combo_needs_a_boss_carrier(self):
        """没有 general 系载体的层,带「深渊法阵」的组合不该被选中。"""
        import random as _r
        for seed in range(300):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell", caps={"boss": False})
            self.assertNotIn("深渊法阵", out["desc"], seed)


class HellEverywhereCase(unittest.TestCase):
    """全塔烈狱(用户主推):没有白板层,最浅也给 1 个诅咒。"""

    def test_hell_has_no_blank_floors(self):
        import random as _r
        for r in (1, 2, 3, 4):
            out = rb.abyss_curses(r, 30, _r.Random(r), "hell", caps={"boss": True})
            self.assertTrue(out["desc"], f"第{r}战是白板")

        menu = [
            ("加成甲", "battle/action/boon_a", "加成甲", "加成"),
            ("加成乙", "battle/action/boon_b", "加成乙", "加成"),
            ("可见诅咒", "battle/action/curse", "可见效果", "诅咒"),
        ]
        with mock.patch.object(rb, "_FIELD_MENU_ALL", menu):
            paired = rb.abyss_curses(
                5, 30, _r.Random(12), "hell",
                caps={"boss": True, "element": True, "panel": True},
                forced={"curses": ["不屈龙心"]})
        fields = [c for c in paired["picks"] if c.get("caster")]
        self.assertEqual(len(fields), 1)
        self.assertNotEqual(fields[0]["caster"][3], "加成")
        self.assertEqual(paired["field_requested"], 1)

        dragon = rb.stacked_resistance_entry(
            "不屈龙心", "ACToleranceOfDebuff", 1.0, 20)
        boons = [
            {"name": "深渊法阵", "caster": menu[0], "text": "加成甲"},
            {"name": "深渊法阵", "caster": menu[1], "text": "加成乙"},
        ]
        replaced = rb.ensure_dragon_heart_companion(
            [dragon, *boons], _r.Random(1), True, menu)
        replaced_fields = [c for c in replaced if c.get("caster")]
        self.assertEqual(len(replaced_fields), 2, "替换加成 field 时不得新增第三个")
        self.assertEqual(sum(c["caster"][3] != "加成" for c in replaced_fields), 1)
        with self.assertRaises(RuntimeError):
            rb.ensure_dragon_heart_companion([dragon], _r.Random(1), False, menu)
        with self.assertRaises(RuntimeError):
            rb.ensure_dragon_heart_companion(
                [dragon, *boons], _r.Random(1), True, menu[:2])

    def test_non_hell_keeps_the_blank_warmup(self):
        import random as _r
        out = rb.abyss_curses(2, 30, _r.Random(2), "standard", caps={"boss": True})
        self.assertEqual(out["desc"], "")

    def test_hell_count_ramp(self):
        import random as _r

        def n_curses(r):
            return len(rb.abyss_curses(
                r, 30, _r.Random(r), "hell",
                caps={"boss": False, "element": False})["picks"])

        # 2026-08-05 任务 C 最终裁定：≤20%/≤50%/>50%，最后 20% 再开第 4 格。
        for r, want in ((1, 1), (6, 1), (7, 2), (15, 2),
                        (16, 3), (24, 3), (25, 4), (30, 4)):
            self.assertEqual(n_curses(r), want, r)

    def test_deep_round_boundaries_and_field_slots(self):
        self.assertFalse(rb.is_deep_round(24, 30))
        self.assertTrue(rb.is_deep_round(25, 30))
        for r, want in ((15, 0), (16, 1), (24, 1), (25, 2), (30, 2)):
            self.assertEqual(rb.required_field_slots(r, 30), want, r)

    def test_deep_random_roll_has_two_distinct_fields_and_no_time_limit(self):
        import random as _r
        menu = [
            ("领域甲", "battle/action/a", "效果甲", "领域"),
            ("领域乙", "battle/action/b", "效果乙", "领域"),
            ("领域丙", "battle/action/c", "效果丙", "领域"),
        ]
        with mock.patch.object(rb, "_FIELD_MENU_ALL", menu):
            out = rb.abyss_curses(
                25, 30, _r.Random(20260805), "hell",
                caps={"boss": True, "element": True, "panel": True})
        # “第4个诅咒”与“双领域”是两条独立机制：4 个非领域 + 2 个领域。
        self.assertEqual(len(out["picks"]), 6)
        self.assertEqual(sum(not c.get("caster") for c in out["picks"]), 4)
        self.assertEqual(len(out["casters"]), 2)
        self.assertEqual(len({m[1] for m in out["casters"]}), 2)
        self.assertFalse(any("time" in c for c in out["picks"]), out["picks"])
        self.assertEqual(out["field_deficit"], 0)

    def test_deep_forced_time_limit_is_rejected_logged_and_refilled(self):
        import random as _r
        with mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(
                25, 30, _r.Random(17), "hell",
                caps={"boss": False, "element": False,
                      "carrier_reason": "no general_boss"},
                forced={"curses": ["时之枷锁"]})
        self.assertEqual(len(out["picks"]), 4)
        self.assertFalse(any("time" in c for c in out["picks"]), out["picks"])
        self.assertEqual(out["field_requested"], 2)
        self.assertEqual(out["field_deficit"], 2)
        self.assertTrue(any("深层禁时限" in str(call) and "redraw" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)

    def test_deep_forced_plan_cannot_expand_past_four_ordinary_curses(self):
        import random as _r
        menu = [
            ("领域甲", "battle/action/a", "效果甲", "领域"),
            ("领域乙", "battle/action/b", "效果乙", "领域"),
            ("领域丙", "battle/action/c", "效果丙", "领域"),
        ]
        forced = ["深渊重甲", "魔力枯竭", "亡者不屈", "血肉高墙", "元素禁壁"]
        with mock.patch.object(rb, "_FIELD_MENU_ALL", menu), \
             mock.patch.object(rb, "log") as logger:
            out = rb.abyss_curses(
                25, 30, _r.Random(31), "hell",
                caps={"boss": True, "element": True, "panel": True},
                forced={"curses": forced})
        ordinary = [c for c in out["picks"] if not c.get("caster")]
        self.assertEqual(len(ordinary), 4)
        self.assertEqual(len(out["casters"]), 2)
        self.assertNotIn("元素禁壁", {c["name"] for c in ordinary})
        self.assertTrue(any("深层普通诅咒固定 4 个" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)


class TripleWallCurseCase(unittest.TestCase):
    """三重壁垒(2026-07-29 用户「免疫可以不止一种,比如三种」):
    四系里随机放行一系,其余三系同时高耐性 / 炼狱档完全免疫。"""

    class R:
        """确定性 rng:randrange 恒 0、sample 保序、random 恒 0.99(不触发法阵加权)。"""
        def randrange(self, n):
            return 0

        def sample(self, seq, k):
            return list(seq)[:k]

        def random(self):
            return 0.99

    def pool(self, t):
        return {c["name"]: c for c in rb._curse_pool(t, self.R())}

    def test_three_kinds_immune(self):
        c = self.pool(2)["三重壁垒"]
        # 2026-08-05 需求:伤害类型与属性免疫都必须不可驱散,故不再钉死 c71。
        self.assertNotIn("cond", c)
        self.assertEqual(len(c["damage_resistance"]), 3)
        self.assertEqual({k for k, _v, _cancelable in c["damage_resistance"]},
                         {1, 2, 3})   # 放行 0
        self.assertTrue(all(v == 1.0 and cancelable is False
                            for _k, v, cancelable in c["damage_resistance"]))
        self.assertIn("三重免疫", c["text"])

    def test_lower_tiers_are_resistance_not_immunity(self):
        for t, want in ((0, 0.5), (1, 0.7)):
            c = self.pool(t)["三重壁垒"]
            self.assertTrue(all(v == want for _k, v, _cancelable
                                in c["damage_resistance"]), t)
            self.assertNotIn("三重免疫", c["text"])

    def test_fits_the_five_condition_slots(self):
        # 三重壁垒已迁硬通道,不占 quest 五槽；亡者不屈的 2 条完整保留。
        p = self.pool(2)
        self.assertNotIn("cond", p["三重壁垒"])
        self.assertEqual(len(p["亡者不屈"]["cond"]), 2)


class SwapZoneBossesCase(unittest.TestCase):
    """--mix 模块化拼接:boss 槽整组换血,zako/其余列原样保留。"""

    def test_boss_slots_swapped_zakos_kept(self):
        zn = {"0": wave(zakos=("zk1", "zk2"), bosses=("old_a", "old_b"))}
        out = rb.swap_zone_bosses(zn, ["new_x"])
        cells = out["0"].split(",")
        self.assertEqual(cells[24], "new_x")
        self.assertEqual(cells[28], "new_x")          # 循环填充
        self.assertEqual(cells[2], "zk1")
        self.assertEqual(cells[4], "zk2")

        with self.subTest("unknown closure is native-only rather than a native rejection"):
            general = [""] * 162
            general[41] = "p0"
            general[42] = "routine"
            general[109] = "action/unknown"
            general[110] = "false"
            bundle = rbb.NativeBossBundle(
                "family", "family", "variant", "variant",
                "source", "source_zone", "terrain/source", ("0",),
                (rbb.ActiveBossSlot(
                    "0", 1, 0, rbb.BossRef(1, "boss"), None),),
                None, "", "test", selected_levels=(("0", 1, 100),),
            )
            result = rbb.boss_terrain_requirements(
                bundle, 100, {
                    "general_boss": {"boss": {"100": rb.join(general, False)}},
                    "general_boss_state": {"routine": {}},
                    "action_loader": lambda _program: [
                        "ActionDsl", 1, ["None"], False, False, False,
                        False, False, False, False, 0,
                        ["Block", [["Command", ["FutureUnknownCommand", 1]]]]],
                    "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
                })
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "ACTION_CLOSURE_UNAUDITED")
            self.assertNotEqual(result.reason, "REFERENCE")

            callback = ["Block", [["Command", ["SpawnFunnel",
                ["Funnel", "funnel"], 1, ["FunnelGroup", 1], []]]]]
            callback_commands = {
                "CreateReferencePoint": [
                    "CreateReferencePoint", 0, ["World"], 0, 0, 0.0,
                    False, False, ["None"], 0, 0, callback],
                "CreateHitArea": [
                    "CreateHitArea", "", 0, ["World"], 0, 0, 0.0,
                    False, False, ["Circle", 1], ["Center"], ["Center"],
                    ["None"], ["Infinite"], ["None"], ["None"], False,
                    False, ["None"], 0, callback, 0, 0, ["Block", []],
                    0, 0, ["None"]],
            }
            for command_name, command in callback_commands.items():
                with self.subTest(command_callback=command_name):
                    callback_result = rbb.boss_terrain_requirements(
                        bundle, 100, {
                            "general_boss": {
                                "boss": {"100": rb.join(general, False)}},
                            "general_boss_state": {"routine": {}},
                            "action_loader": lambda _program, command=command: [
                                "ActionDsl", 1, ["None"], False, False,
                                False, False, False, False, False, 0,
                                ["Block", [["Command", command]]]],
                            "spawned_ref_gate": (
                                lambda *_args: rbb.GateResult(True)),
                        })
                    self.assertFalse(callback_result.ok)
                    self.assertEqual(
                        callback_result.reason, "ACTION_CLOSURE_UNAUDITED")

            summons_command = [
                "CreateSummonsMultiball", 1, 7, [], ["None"], ["None"],
                ["None"], 0, False, "activated_event_id", 0, 0,
                ["Block", []], {}]
            summons_result = rbb.boss_terrain_requirements(
                bundle, 100, {
                    "general_boss": {
                        "boss": {"100": rb.join(general, False)}},
                    "general_boss_state": {"routine": {}},
                    "action_loader": lambda _program: [
                        "ActionDsl", 1, ["None"], False, False, False,
                        False, False, False, False, 0,
                        ["Block", [["Command", summons_command]]]],
                    "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
                })
            self.assertFalse(summons_result.ok)
            self.assertIn("MultiballTable", summons_result.detail)

            lifecycle_commands = {
                "CreateTornado": [
                    "CreateTornado", 0, 0, 0, 0.0, 0, 0,
                    "battle/action/lifecycle", False],
            }
            for command_name, command in lifecycle_commands.items():
                with self.subTest(unbounded_lifecycle=command_name):
                    def lifecycle_loader(program, command=command):
                        if program == "action/unknown":
                            body = [["Command", command]]
                        else:
                            body = [["Command", [
                                "SpawnFunnel", ["Funnel", "funnel"], 1,
                                ["FunnelGroup", 1], []]]]
                        return [
                            "ActionDsl", 1, ["None"], False, False, False,
                            False, False, False, False, 0, ["Block", body]]

                    lifecycle_result = rbb.boss_terrain_requirements(
                        bundle, 100, {
                            "general_boss": {
                                "boss": {"100": rb.join(general, False)}},
                            "general_boss_state": {"routine": {}},
                            "action_loader": lifecycle_loader,
                            "spawned_ref_gate": (
                                lambda *_args: rbb.GateResult(True)),
                        })
                    self.assertFalse(lifecycle_result.ok)
                    self.assertEqual(
                        lifecycle_result.reason, "ACTION_CLOSURE_UNAUDITED")

            membership_general = list(general)
            membership_general[109] = ""
            membership_state = [""] * 53
            membership_state[29] = "15"
            membership_state[30] = "other_layer_boss"
            membership_result = rbb.boss_terrain_requirements(
                bundle, 100, {
                    "general_boss": {
                        "boss": {"100": rb.join(membership_general, False)}},
                    "general_boss_state": {
                        "routine": {"1": rb.join(membership_state, False)}},
                    "action_loader": lambda _program: None,
                    "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
                })
            self.assertFalse(
                membership_result.ok,
                "GeneralBossAlive 不得引用非同层 active/AlterEgo 成员")
            self.assertEqual(
                membership_result.reason, "ACTION_CLOSURE_UNAUDITED")

        with self.subTest("standard resources use the exact double extension"):
            requested_esdl = []
            standard_bundle = rbb.NativeBossBundle(
                "family", "family", "variant", "variant",
                "source", "source_zone", "terrain/source", ("0",),
                (rbb.ActiveBossSlot(
                    "0", 1, 0, rbb.BossRef(0, "std"), None),),
                None, "", "test", selected_levels=(("0", 1, 100),),
            )

            def load_esdl(logical):
                requested_esdl.append(logical)
                return {
                    "bH": "battle/action/std$",
                    "ae": ["T1", "std_pos"],
                    "bx": ["T1", {"g": ["pre_action01"], "h": True}],
                    "au": [{
                        "c": ["T1", "part_pos"],
                        "g": [{
                            "i": [{"b": "attack"}],
                            "k": [["T1", ["T1", "move_pos"], 6, 0]],
                        }],
                    }],
                }

            std_result = rbb.boss_terrain_requirements(
                standard_bundle, 100, {
                    "standard_boss": {
                        "std": {"100": "std,battle/enemy/boss/std"}},
                    "esdl_loader": load_esdl,
                    "action_loader": lambda _program: [
                        "ActionDsl", 1, ["None"], False, False, False,
                        False, False, False, False, 0, ["Block", []]],
                    "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
                })
            self.assertFalse(std_result.ok)
            self.assertEqual(
                std_result.reason, "ACTION_CLOSURE_UNAUDITED")
            self.assertEqual(
                requested_esdl,
                ["battle/enemy/boss/std.esdl.amf3.deflate"])

    def test_multi_boss_source_cycles(self):
        zn = {"0": wave(bosses=("old_a", "old_b", "old_c"))}
        out = rb.swap_zone_bosses(zn, ["x", "y"])
        cells = out["0"].split(",")
        self.assertEqual([cells[24], cells[28], cells[32]], ["x", "y", "x"])

    def test_empty_slots_untouched(self):
        zn = {"0": wave(bosses=("old_a",))}
        out = rb.swap_zone_bosses(zn, ["x"])
        cells = out["0"].split(",")
        self.assertEqual(cells[28], "")               # 原本空的槽不注入
        self.assertEqual(cells[32], "")

    def test_single_slot_mix_reports_only_the_realized_donor_entity(self):
        """Task C 按地形实际槽审 HP，不把 donor 未出场的第2只算进去。"""
        out = rb.swap_zone_bosses(
            {"0": wave_pair(bosses=("old_a",))}, ["donor_a", "donor_b"])
        self.assertEqual(rb.zone_single_bosses(out), ["donor_a"])
        cells = out["0"].split(",")
        self.assertEqual([cells[24], cells[26]], ["donor_a", "donor_a"])

        with self.subTest("c109 is an unconditional action root and state movement is a position requirement"):
            general = [""] * 162
            general[41] = "p0"
            general[42] = "routine"
            general[109] = "action/pre"
            general[110] = "false"  # only controls rerun; it must not hide c109
            general[111] = "action/attack"
            general[112] = "action/repeat"
            general[113] = "action/nested"
            general[114] = "action/flow"
            state = [""] * 53
            state[29] = "15"
            state[30] = "clone"  # same-layer SpawnAlterEgo is valid membership
            state[49] = "0"
            state[50] = "move_p"
            bundle = rbb.NativeBossBundle(
                family_id="family", family_name="family",
                variant_id="variant", variant_name="variant",
                source_field="source", source_zone="source_zone",
                terrain_logical="terrain/source", active_layers=("0",),
                slots=(rbb.ActiveBossSlot(
                    "0", 1, 0, rbb.BossRef(1, "boss"),
                    rbb.BossRef(1, "boss_multi")),),
                bgm=None, thumbnail="", source_category="test",
                terrain_caps=(rbb.TerrainLayerCaps(
                    "0", (1,), (0,), (("1", 2),),
                    (("clone_p", 1), ("move_p", 1), ("p0", 1)), ()),),
                selected_levels=(("0", 1, 100),),
            )
            actions = {
                "action/pre": ["ActionDsl", 1, ["None"], False, False,
                               False, False, False, False, False, 0,
                               ["Block", [["Command", ["SpawnFunnel",
                                 ["Funnel", "funnel"], 2,
                                 ["FunnelGroup", 1], []]]]]],
                "action/attack": ["ActionDsl", 1, ["None"], False, False,
                                  False, False, False, False, False, 0,
                                  ["Block", [["Command", ["SpawnAlterEgo",
                                    "clone", ["CustomPosition", "clone_p"],
                                    False, False]]]]],
                # ListeningEvent.as: Repeat params[0] is the frame interval;
                # params[1] is the finite eval count. Counting the former
                # would inflate this closure from 3 summons to 60.
                "action/repeat": ["ActionDsl", 1, ["None"], False, False,
                                  False, False, False, False, False, 0,
                                  ["Block", [["Event", ["Repeat", 60, 3, "*",
                                    ["Block", [["Command", ["SpawnFunnel",
                                      ["Funnel", "funnel"], 1,
                                      ["FunnelGroup", 1], []]]]]]]]]],
                "action/nested": ["ActionDsl", 1, ["None"], False, False,
                                  False, False, False, False, False, 0,
                                  ["Block", [
                                    ["Command", ["CreateBombMultiball", 2, "",
                                      ["None"], ["None"], ["None"],
                                      "battle/action/bomb", 0, False]],
                                    ["Command", ["CreateTornado", 0, 0, 0, 0.0,
                                      120, 60, "battle/action/tornado", False]],
                                    ["Command", ["CreateTargetAttack", 0, 0, 0,
                                      ["None"], "battle/action/target"]],
                                  ]]],
                # Sibling Wait callbacks add, whereas mutually exclusive
                # conditional arms contribute only their finite maximum.
                "action/flow": ["ActionDsl", 1, ["None"], False, False,
                                False, False, False, False, False, 0,
                                ["Block", [
                                  ["Event", ["Wait", 1, "*", ["Block", [[
                                    "Command", ["SpawnFunnel", ["Funnel", "funnel"],
                                    1, ["FunnelGroup", 1], []]]]]]],
                                  ["Event", ["Wait", 2, "*", ["Block", [[
                                    "Command", ["SpawnFunnel", ["Funnel", "funnel"],
                                    2, ["FunnelGroup", 1], []]]]]]],
                                  ["Command", ["ConditionalsFeverMode",
                                    ["Block", [["Command", ["SpawnFunnel",
                                      ["Funnel", "funnel"], 1,
                                      ["FunnelGroup", 1], []]]]],
                                    ["Block", [["Command", ["SpawnFunnel",
                                      ["Funnel", "funnel"], 4,
                                      ["FunnelGroup", 1], []]]]]]],
                                ]]],
                "battle/action/bomb": [
                    "ActionDsl", 1, ["None"], False, False, False, False,
                    False, False, False, 0, ["Block", [["Command", [
                        "SpawnFunnel", ["Funnel", "funnel"], 1,
                        ["FunnelGroup", 1], []]]]]],
                **{
                    path: ["ActionDsl", 1, ["None"], False, False,
                           False, False, False, False, False, 0,
                           ["Block", [["Command", ["SpawnFunnel",
                             ["Funnel", "funnel"], 1,
                             ["FunnelGroup", 1], []]]]]]
                    for path in ("battle/action/tornado",
                                 "battle/action/target")
                },
            }
            result = rbb.boss_terrain_requirements(
                bundle, 100, {
                    "general_boss": {"boss": {"100": rb.join(general, False)}},
                    "general_boss_state": {
                        "routine": {"1": {"start": rb.join(state, False)}}},
                    "action_loader": actions.__getitem__,
                    "spawned_ref_gate": lambda *_args: rbb.GateResult(True),
                })
            self.assertTrue(result.ok, result)
            layer = result.requirements.layers[0]
            self.assertEqual(layer.custom_positions,
                             ("clone_p", "move_p", "p0"))
            self.assertEqual(
                [(item.group, item.max_commands) for item in layer.funnels],
                [("1", 17)])
            self.assertIn("action/pre", result.requirements.action_roots)
            self.assertEqual(
                getattr(result.requirements, "action_closure", ()),
                ("action/attack", "action/flow", "battle/action/bomb",
                 "battle/action/target", "battle/action/tornado",
                 "action/nested", "action/pre", "action/repeat"),
            )

            def target_bundle(*, caps, slots=None, layers=("0",)):
                return rbb.NativeBossBundle(
                    family_id="target-family", family_name="target-family",
                    variant_id="target-variant", variant_name="target-variant",
                    source_field="target", source_zone="target_zone",
                    terrain_logical="terrain/target", active_layers=layers,
                    slots=slots or bundle.slots, bgm=None, thumbnail="",
                    source_category="test", terrain_caps=caps,
                )

            compatible = rbb.terrain_compatibility(
                bundle, target_bundle(caps=bundle.terrain_caps),
                result.requirements)
            self.assertTrue(compatible.ok, compatible)

            missing_position = rbb.terrain_compatibility(
                bundle,
                target_bundle(caps=(rbb.TerrainLayerCaps(
                    "0", (1,), (0,), (("1", 2),),
                    (("move_p", 1), ("p0", 1)), ()),)),
                result.requirements)
            self.assertEqual(missing_position.reason, "CUSTOM_POSITION_MISSING")

            wrong_group = rbb.terrain_compatibility(
                bundle,
                target_bundle(caps=(rbb.TerrainLayerCaps(
                    "0", (1,), (0,), (("2", 2),),
                    (("clone_p", 1), ("move_p", 1), ("p0", 1)), ()),)),
                result.requirements)
            self.assertEqual(wrong_group.reason, "FUNNEL_ANCHOR_MISMATCH")

            wrong_count = rbb.terrain_compatibility(
                bundle,
                target_bundle(caps=(rbb.TerrainLayerCaps(
                    "0", (1,), (0,), (("1", 1),),
                    (("clone_p", 1), ("move_p", 1), ("p0", 1)), ()),)),
                result.requirements)
            self.assertEqual(wrong_count.reason, "FUNNEL_ANCHOR_MISMATCH")

            target_group_slot = rbb.ActiveBossSlot(
                "0", 1, 1, rbb.BossRef(1, "boss"),
                rbb.BossRef(1, "boss_multi"))
            wrong_topology = rbb.terrain_compatibility(
                bundle,
                target_bundle(
                    slots=(target_group_slot,),
                    caps=(rbb.TerrainLayerCaps(
                        "0", (1,), (1,), (("1", 2),),
                        (("clone_p", 1), ("move_p", 1), ("p0", 1)), ()),)),
                result.requirements)
            self.assertEqual(wrong_topology.reason, "BOSS_GROUP_MISMATCH")

        with self.subTest("equal total slots cannot hide different per-layer shapes"):
            source_slots = (
                rbb.ActiveBossSlot("0", 1, 0, rbb.BossRef(1, "a"), None),
                rbb.ActiveBossSlot("1", 1, 0, rbb.BossRef(1, "b"), None),
            )
            target_slots = (
                rbb.ActiveBossSlot("0", 1, 0, rbb.BossRef(1, "a"), None),
                rbb.ActiveBossSlot("0", 2, 0, rbb.BossRef(1, "b"), None),
            )
            source = rbb.NativeBossBundle(
                "f", "f", "v", "v", "sf", "sz", "terrain/s",
                ("0", "1"), source_slots, None, "", "test",
                terrain_caps=(
                    rbb.TerrainLayerCaps("0", (1,), (0,), (), (), ()),
                    rbb.TerrainLayerCaps("1", (1,), (0,), (), (), ())),
            )
            target = rbb.NativeBossBundle(
                "tf", "tf", "tv", "tv", "tf", "tz", "terrain/t",
                ("0", "1"), target_slots, None, "", "test",
                terrain_caps=(
                    rbb.TerrainLayerCaps("0", (1, 2), (0,), (), (), ()),
                    rbb.TerrainLayerCaps("1", (), (), (), (), ())),
            )
            requirements = rbb.BossTerrainRequirements(layers=(
                rbb.LayerTerrainRequirements("0"),
                rbb.LayerTerrainRequirements("1"),
            ))
            compatibility = rbb.terrain_compatibility(
                source, target, requirements)
            self.assertEqual(compatibility.reason, "SLOT_SHAPE_MISMATCH")


class BuiltRowsCase(unittest.TestCase):
    def test_generator_refuses_dangling_output(self):
        rows = {"1": quest_row("f_ok"), "13": quest_row("f_bad")}
        reports = rb.validate_built_rows(rows, FD, ZONE, ENEMIES, ZAKOS)
        by_round = {r["round"]: r for r in reports}
        self.assertTrue(by_round["1"]["ok"])
        self.assertFalse(by_round["13"]["ok"])       # main() 对任一 not-ok 拒绝写入

    def test_short_row_rejected(self):
        reports = rb.validate_built_rows({"1": ["700099001"]}, FD, ZONE, ENEMIES, ZAKOS)
        self.assertFalse(reports[0]["ok"])
        self.assertIn("c98", reports[0]["errors"][0])


class EventChainCase(unittest.TestCase):
    def test_reports_per_round(self):
        qt = {"700099": {
            "1": ",".join(quest_row("f_ok")),
            "13": ",".join(quest_row("f_bad")),
        }}
        reports = rb.validate_event_chain(
            "700099", qt=qt, fd=FD, zone=ZONE, enemies=ENEMIES, zakos=ZAKOS)
        by_round = {r["round"]: r for r in reports}
        self.assertTrue(by_round["1"]["ok"])
        self.assertFalse(by_round["13"]["ok"])
        self.assertEqual(by_round["13"]["field"], "f_bad")

    def test_missing_event_reported(self):
        reports = rb.validate_event_chain(
            "999999", qt={}, fd=FD, zone=ZONE, enemies=ENEMIES, zakos=ZAKOS)
        self.assertEqual(len(reports), 1)
        self.assertFalse(reports[0]["ok"])


class CdnChainCase(unittest.TestCase):
    """verify_cdn_chain:store 字节必须等于 CDN diff 链最新版包内字节。"""

    LOGICAL = "master/battle/field_data.orderedmap"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = root / "store"
        self.cdn_diff = root / "archive-common-diff"
        self.cdn_diff.mkdir(parents=True)
        patcher = mock.patch.object(q, "_store_base", return_value=self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.member = f"production/upload/{q.hashed_rel(self.LOGICAL)}"
        sp = self.store / q.hashed_rel(self.LOGICAL)
        sp.parent.mkdir(parents=True)
        sp.write_bytes(b"current-bytes")

    def zip_with(self, name: str, payload: bytes | None) -> None:
        with zipfile.ZipFile(self.cdn_diff / name, "w") as zf:
            if payload is None:
                zf.writestr(".empty", b"\n")
            else:
                zf.writestr(self.member, payload)

    def verify(self):
        return rb.verify_cdn_chain([self.LOGICAL], cdn_diff=self.cdn_diff)

    def test_never_published_reported(self):
        self.zip_with("pinball-1.4.99-1.4.100-1-aabb0101.zip", None)
        problems = self.verify()
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], self.LOGICAL)
        self.assertIn("未发布", problems[0][1])

    def test_current_bytes_on_chain_pass(self):
        self.zip_with("pinball-1.4.99-1.4.100-1-aabb0101.zip", b"current-bytes")
        self.assertEqual(self.verify(), [])

    def test_latest_version_wins_over_stale(self):
        # 旧版有正确字节、新版是旧字节(发布顺序错乱)→ 客户端有效态=新版 → 必须报
        self.zip_with("pinball-1.4.99-1.4.100-1-aabb0101.zip", b"current-bytes")
        self.zip_with("pinball-1.4.100-1.4.101-1-aabb0102.zip", b"stale-bytes")
        problems = self.verify()
        self.assertEqual(len(problems), 1)
        self.assertIn("不一致", problems[0][1])

    def test_stale_then_republished_pass(self):
        self.zip_with("pinball-1.4.99-1.4.100-1-aabb0101.zip", b"stale-bytes")
        self.zip_with("pinball-1.4.100-1.4.101-1-aabb0102.zip", b"current-bytes")
        self.assertEqual(self.verify(), [])

    def test_same_version_split_packs_any_match(self):
        # 同一版本边拆多包(卫生门禁≤5MiB 先例):任一包字节一致即通过
        self.zip_with("pinball-1.4.99-1.4.100-1-aabb0101.zip", b"stale-bytes")
        self.zip_with("pinball-1.4.99-1.4.100-2-aabb0101.zip", b"current-bytes")
        self.assertEqual(self.verify(), [])

    def test_store_file_missing_reported(self):
        (self.store / q.hashed_rel(self.LOGICAL)).unlink()
        problems = self.verify()
        self.assertEqual(len(problems), 1)
        self.assertIn("store 文件缺失", problems[0][1])


def wave_pair(bosses: tuple = ()) -> str:
    """41 列 zone wave 行,boss 槽的**单人+多人两列**都填(官方常态)。

    槽位 = (单人kind, 单人列, 多人kind, 多人列)。
    """
    row = [""] * 41
    for n, b in enumerate(bosses):
        single_kind, single, multi_kind, multi = (
            (23, 24, 25, 26), (27, 28, 29, 30), (31, 32, 33, 34))[n]
        row[single_kind] = "1"
        row[multi_kind] = "1"
        row[single] = b
        row[multi] = b
    return ",".join(row)


class BossSwapColumnPairCase(unittest.TestCase):
    """法阵载体克隆:单人/多人两列必须同步换(2026-07-30「打不死」根因之一)。

    客户端 ZoneSourceValues.get_bossN() 按 isSingleBattle 二选一读列,
    只换 c24/28/32 的话多人模式仍指向原 boss。
    """

    def test_both_columns_swapped(self):
        wc = wave_pair(bosses=("old_a",)).split(",")
        rb.apply_boss_swap(wc, "old_a", "mod_rogue_boss7")
        self.assertEqual(wc[24], "mod_rogue_boss7")
        self.assertEqual(wc[26], "mod_rogue_boss7")   # ← 修复前这里还是 old_a

    def test_second_slot_pair_swapped(self):
        wc = wave_pair(bosses=("old_a", "old_b")).split(",")
        rb.apply_boss_swap(wc, "old_b", "clone_b")
        self.assertEqual([wc[28], wc[30]], ["clone_b", "clone_b"])
        self.assertEqual([wc[24], wc[26]], ["old_a", "old_a"])   # 别的槽不动

    def test_unrelated_code_untouched(self):
        wc = wave_pair(bosses=("old_a",)).split(",")
        rb.apply_boss_swap(wc, "not_here", "x")
        self.assertEqual([wc[24], wc[26]], ["old_a", "old_a"])

    def test_swap_zone_bosses_keeps_pair_in_sync(self):
        """姊妹路径(--mix)一直是六列全换,回归锁住。"""
        out = rb.swap_zone_bosses({"0": wave_pair(bosses=("old_a",))}, ["new_x"])
        cells = out["0"].split(",")
        self.assertEqual([cells[24], cells[26]], ["new_x", "new_x"])


class PhaseLinkedBossCase(unittest.TestCase):
    """成对/分阶段 boss 检测(数据驱动,不认名字)。"""

    ZONE = {
        "z_single": {"0": wave_pair(bosses=("lone_boss",))},
        "z_pair": {"0": wave_pair(bosses=("form1", "form2"))},
        "z_ph1": {"0": wave_pair(bosses=("lich",))},      # 阶段链第 1 阶段
        "z_ph2": {"0": wave_pair(bosses=("owl",))},       # 阶段链第 2 阶段
        "mod_rogue_z3": {"0": wave_pair(bosses=("cloneA", "cloneB"))},  # 自家克隆
    }
    FD = {
        "f_single": "f_single,terrain_a,z_single",
        "f_pair": "f_pair,terrain_a,z_pair",
        "f_ph1": "f_ph1,terrain_a,z_ph1",
        "f_ph2": "f_ph2,terrain_a,z_ph2",
    }

    @staticmethod
    def bbq_row(field: str) -> str:
        row = [""] * 124
        row[109] = field
        return ",".join(row)

    def chain_table(self) -> dict:
        """章 → 战斗 → 阶段(三层嵌套,c109=field)。"""
        return {
            "1": {
                "1": {"1": self.bbq_row("f_ph1"), "2": self.bbq_row("f_ph2")},
                "2": {"1": self.bbq_row("f_single")},      # 单阶段战斗,不算链
            }
        }

    def flagged(self):
        return rb.phase_linked_bosses(self.ZONE, self.FD, self.chain_table())

    def test_same_wave_pair_flagged(self):
        f = self.flagged()
        self.assertIn("form1", f)
        self.assertIn("form2", f)

    def test_quest_phase_chain_flagged(self):
        """zone 各自单实体,只有 boss_battle_quest 阶段链能抓到(索拉斯型)。"""
        f = self.flagged()
        self.assertIn("lich", f)
        self.assertIn("owl", f)

    def test_plain_boss_not_flagged(self):
        self.assertNotIn("lone_boss", self.flagged())

    def test_own_clone_zone_ignored(self):
        """mod_rogue_* 是本工具自己写的层,不能拿来当判据(否则名单自我膨胀)。"""
        f = self.flagged()
        self.assertNotIn("cloneA", f)
        self.assertNotIn("cloneB", f)

    def test_missing_bbq_table_degrades_quietly(self):
        f = rb.phase_linked_bosses(self.ZONE, self.FD, {})
        self.assertIn("form1", f)          # 信号 A 仍在
        self.assertNotIn("lich", f)


class CasterCarrierGateCase(unittest.TestCase):
    """「深渊法阵」载体门禁:成对/分阶段层拒发(2026-07-30 玩家第10战打不死)。"""

    ZONE = PhaseLinkedBossCase.ZONE
    FD = PhaseLinkedBossCase.FD
    # 合成的代号引用名单:显式传进去,门禁就完全不碰 store —— 保持用例密闭,
    # 让没有数据包的环境(CI / 上游 fork / 别人的克隆)也能跑。
    REFS = {"hard": frozenset({"shared_boss"}), "soft": frozenset({"watched_boss"}),
            "degraded": False}

    def test_plain_field_allowed(self):
        why = rb.caster_carrier_block("f_single", ["lone_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNone(why)

    def test_multi_entity_zone_blocked(self):
        why = rb.caster_carrier_block("f_pair", ["form1", "form2"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("boss 实体", why)

    def test_phase_linked_boss_blocked_even_when_alone(self):
        """索拉斯型:这层只摆了一只,但它的转场按代号找同伴,克隆即断链。"""
        why = rb.caster_carrier_block("f_ph1", ["lich"],
                                      self.FD, self.ZONE, frozenset({"lich", "owl"}),
                                      refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("分阶段", why)

    def test_unknown_field_falls_back_to_boss_check(self):
        self.assertIsNone(rb.caster_carrier_block("f_ghost", ["lone_boss"],
                                                  self.FD, self.ZONE, frozenset(),
                                                  refs=self.REFS))
        self.assertIsNotNone(rb.caster_carrier_block("f_ghost", ["lich"],
                                                     self.FD, self.ZONE,
                                                     frozenset({"lich"}), refs=self.REFS))

    def test_hard_code_reference_blocked(self):
        """damage_share/enemy_watch partner 型:随从按代号认爹,克隆改名即断链
        (2026-08-03 玩家实锤:背鳍三兄弟 / 旋风巨土俑「血量下不去」)。"""
        why = rb.caster_carrier_block("f_single", ["shared_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("按代号引用", why)

        with self.subTest("the same hard set is the single identity-lock source"):
            reason = rb.identity_locked_boss_reason(
                ["shared_boss"], code_references=self.REFS)
            self.assertIsNotNone(reason)
            self.assertIn("identity-locked", reason)
            self.assertIn("shared_boss", reason)
            self.assertIsNone(rb.identity_locked_boss_reason(
                ["watched_boss"], code_references=self.REFS))
            self.assertIsNone(rb.identity_locked_mix_reason(
                ["shared_boss"], "native_field", "native_field",
                code_references=self.REFS))
            foreign = rb.identity_locked_mix_reason(
                ["shared_boss"], "native_field", "foreign_field",
                code_references=self.REFS)
            self.assertIsNotNone(foreign)
            self.assertIn("native_field", foreign)
            self.assertIn("foreign_field", foreign)

        with self.subTest("current store keeps shark native action and damage-share links"):
            try:
                refs = rb.code_referenced_bosses()
                gb = q.load_table(rb.GENERAL_BOSS)
                gf = q.load_table(rb.GENERAL_FUNNEL)
            except FileNotFoundError:
                return
            if refs.get("degraded") or "shark" not in gb:
                return
            self.assertIn("shark", refs["hard"])
            self.assertTrue(any(
                code.startswith("haniwa_great_wind") for code in refs["hard"]))
            selected = rb.select_surjective_level(gb["shark"], 100)
            self.assertIsNotNone(selected)
            shark_row = rb.cells(gb["shark"][str(selected)])
            self.assertIn(
                "battle/action/enemy/action/boss_shark/boss_shark$ea1",
                shark_row[109:161])
            for fin in ("shark_blue", "shark_red", "shark_brown"):
                self.assertIn(fin, gf)
                self.assertTrue(any(
                    len(cells := rb.cells(leaf)) > rb.FUNNEL_DMGSHARE_COL
                    and cells[rb.FUNNEL_DMGSHARE_COL] == "shark"
                    for leaf in rb._leaf_rows(gf[fin])), fin)

    def test_soft_code_reference_allowed_because_watch_is_cloned(self):
        """只有 enemy_watch 自身条目的:make_caster_boss 会把 self 侧一并克隆,放行。"""
        why = rb.caster_carrier_block("f_single", ["watched_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNone(why)

    def test_degraded_refs_block_everything(self):
        """引用名单没扫全就一律拒发——名单只会偏小=漏拦,漏拦的代价是线上打不死。"""
        degraded = dict(self.REFS, degraded=True)
        why = rb.caster_carrier_block("f_single", ["lone_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=degraded)
        self.assertIsNotNone(why)
        self.assertIn("降级", why)
        identity = rb.identity_locked_boss_reason(
            ["lone_boss"], code_references=degraded)
        self.assertIsNotNone(identity)
        self.assertIn("identity-locked", identity)
        self.assertIn("扫描降级", identity)


class ZoneBossSlotsCase(unittest.TestCase):
    def test_counts_entities_not_columns(self):
        zn = {"0": wave_pair(bosses=("a", "b"))}
        self.assertEqual(rb.zone_boss_slots(zn), [{"a"}, {"b"}])

        with self.subTest("terrain BOSS_GROUP objects are not a client capability"):
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": zn},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [{"type": "BOSS_GROUP", "name": "fake"}],
                    }]
                })
            self.assertEqual(caps[0].boss_groups, ())

        with self.subTest("unsupported c22 topology fails closed"):
            row = wave_pair(bosses=("a", "b")).split(",")
            row[22] = "2"
            slots = rbb.active_boss_slots(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(row)}},
                terrain_loader=lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                })
            source = rbb.NativeBossBundle(
                "f", "f", "v", "v", "f", "z", "terrain/path", ("0",),
                slots, None, "", "test",
                terrain_caps=(rbb.TerrainLayerCaps(
                    "0", (1, 2), (2,), (), (), ()),))
            result = rbb.terrain_compatibility(
                source, source,
                rbb.BossTerrainRequirements(layers=(
                    rbb.LayerTerrainRequirements("0"),)))
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "BOSS_GROUP_MISMATCH")

    def test_single_multi_variants_are_one_entity(self):
        wc = wave_pair(bosses=("x_single",)).split(",")
        wc[26] = "x_multi"                      # 官方 78 处这样写
        zn = {"0": ",".join(wc)}
        self.assertEqual(rb.zone_boss_slots(zn), [{"x_single", "x_multi"}])

        with self.subTest("complete slot retains both BossKind/code pairs"):
            wc[22] = "7"
            wc[23], wc[25] = "1", "0"
            slots = rbb.active_boss_slots(
                "f",
                {"f": "f,terrain/path,z"},
                {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup",
                        "name": "0",
                        "objects": [
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "CUSTOM_POSITION", "name": "p0"},
                            {"type": "BOSS_GROUP", "name": "pack"},
                        ],
                    }]
                },
            )
            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].boss_group_kind, 7)
            self.assertEqual(slots[0].single, rbb.BossRef(1, "x_single"))
            self.assertEqual(slots[0].multi, rbb.BossRef(0, "x_multi"))
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "CUSTOM_POSITION", "name": "p0"},
                            {"type": "BOSS_GROUP", "name": "pack"},
                        ],
                    }]
                },
            )
            self.assertEqual(caps[0].funnel_groups, (("3", 2),))
            self.assertEqual(caps[0].custom_positions, (("p0", 1),))
            self.assertEqual(caps[0].boss_slots, (1,))

        with self.subTest("duplicate CUSTOM_POSITION names retain exact counts"):
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [
                            {"type": "CUSTOM_POSITION", "name": "same"},
                            {"type": "CUSTOM_POSITION", "name": "same"},
                        ],
                    }]
                },
            )
            self.assertEqual(caps[0].custom_positions, (("same", 2),))

        with self.subTest("non-empty code without BossKind fails closed"):
            malformed = wc.copy()
            malformed[25] = ""
            with self.assertRaisesRegex(rbb.TerrainGateError, "BossKind"):
                rbb.active_boss_slots(
                    "f", {"f": "f,terrain/path,z"},
                    {"z": {"0": ",".join(malformed)}},
                    terrain_loader=lambda _logical: {
                        "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                    },
                )
            self.assertEqual(rb.zone_boss_slots({"0": ",".join(malformed)}), [])

    def test_nested_wave_skipped(self):
        self.assertEqual(rb.zone_boss_slots({"0": {"weird": "nested"}}), [])

    def test_non_dict_zone_empty(self):
        self.assertEqual(rb.zone_boss_slots("not-a-zone"), [])


# ---------------------------------------------------------------- 伤害硬闸
# 2026-07-30 玩家「连战 boss 伤害过高」审计后落地。审计实测(现役 249 塔):
# col 中位 2.91、中后段中位 4.03、20/30 层超官方全库第二名 1.8;col>4 的层
# **全部**是攻击诅咒层;同 field 锚点 = 把官方原版战斗做成 4.7~6.8 倍每跳。
class AtkCurseTierCase(unittest.TestCase):
    def test_hell_tier_matches_the_agreed_numbers(self):
        """烈狱攻击曲线、词条三级台阶与分布闸使用 2026-08-05 定档。"""
        self.assertEqual(rb.DIFF_PRESETS["hell"][2:4], (1.1, 1.1))
        self.assertEqual(rb.ATK_CURSE_TIERS["嗜血狂潮"], (1.05, 1.10, 1.15))
        self.assertEqual(rb.ATK_CURSE_TIERS["深渊逆鳞"], (1.10, 1.20, 1.30))
        self.assertEqual(rb.ATK_CURSE_TIERS["玻璃深渊"], (1.20, 1.30, 1.40))
        self.assertEqual(rb.BAND_TARGET, {"median": 1.1, "p90": 1.35, "max": 1.5})

    def test_tiers_are_a_monotone_ladder(self):
        """阶梯本身就是降档闸的台阶,不单调就降不下去。"""
        for name, tiers in rb.ATK_CURSE_TIERS.items():
            self.assertEqual(len(tiers), 3, name)
            self.assertLess(tiers[0], tiers[1], name)
            self.assertLess(tiers[1], tiers[2], name)
            self.assertGreater(tiers[0], 1.0, name)

    def test_text_always_matches_the_number(self):
        """落表值与文案同源 —— 降档后 desc 写 ×1.4 就必须真的是 ×1.4。"""
        for name in rb.ATK_CURSE_TIERS:
            for t in range(3):
                e = rb.atk_curse_entry(name, t)
                self.assertIn(f"敌攻×{e['atk']}", e["text"], (name, t))
                self.assertEqual(e["atk_tier"], t)


class DowngradeAtkCurseCase(unittest.TestCase):
    def _hell_floor(self, name):
        e = rb.atk_curse_entry(name, 2, weak=1)
        return rb.apply_picks({}, [e, {"name": "深渊重甲", "tp": 9, "text": "韧性×9"}],
                              "绞肉机")

    def test_每次调用都严格下降并最终摘除(self):
        for name in rb.ATK_CURSE_TIERS:
            curse = self._hell_floor(name)
            seen = [curse["atk"]]
            while rb.downgrade_atk_curse(curse) is not None:
                self.assertLess(curse["atk"], seen[-1], (name, seen))
                seen.append(curse["atk"])
            self.assertEqual(curse["atk"], 1.0, name)     # 收敛到无攻击诅咒
            self.assertLessEqual(len(seen), 5, name)      # 2→1→0→摘,最多 4 步

    def test_desc_follows_the_downgrade(self):
        curse = self._hell_floor("玻璃深渊")
        self.assertIn("敌攻×1.4", curse["desc"])
        rb.downgrade_atk_curse(curse)
        self.assertIn("敌攻×1.3", curse["desc"])
        self.assertNotIn("敌攻×1.4", curse["desc"])

    def test_removal_drops_the_combo_label(self):
        """【绞肉机】的承诺(血厚攻高)没了就别再挂这个名,别骗玩家。"""
        curse = self._hell_floor("嗜血狂潮")
        for _ in range(3):
            rb.downgrade_atk_curse(curse)
        self.assertNotIn("绞肉机", curse["desc"])
        self.assertIsNone(curse["combo"])

    def test_no_atk_curse_returns_none(self):
        curse = rb.apply_picks({}, [{"name": "深渊重甲", "tp": 9, "text": "韧性×9"}])
        self.assertIsNone(rb.downgrade_atk_curse(curse))

    def test_other_effects_survive_the_downgrade(self):
        """降的是攻击项,韧性/词条槽不该被顺手抹掉。"""
        curse = self._hell_floor("深渊逆鳞")
        rb.downgrade_atk_curse(curse)
        self.assertEqual(curse["tp"], 9)
        self.assertTrue(any(k == "1" for k, _v in curse["conds"]))

    def test_fixed_seed_removal_preserves_the_floor_hp_multiplier(self):
        """2026-08-05 实测陷阱:第12战血肉高墙叠玻璃深渊,摘攻击不能把血量翻倍。"""
        import random as _r
        for name in ("玻璃深渊", "嗜血狂潮", "深渊逆鳞"):
            curse = rb.abyss_curses(
                12, 30, _r.Random(20260805), "hell",
                caps={"boss": True, "element": False},
                forced={"curses": [name, "血肉高墙"]})
            hp_before = curse["hp"]
            while rb.downgrade_atk_curse(curse) is not None:
                self.assertEqual(curse["hp"], hp_before, name)
            self.assertEqual(curse["atk"], 1.0, name)

    def test_hp_audit_is_identical_before_and_after_attack_component_removal(self):
        """任务 C 不能再用目标反解绕空任务 A：摘攻击后最终 HP/DPS 必须逐项不变。"""
        curse = rb.apply_picks({}, [
            rb.atk_curse_entry("玻璃深渊", 2),
            {"name": "血肉高墙", "hp": 2.5, "text": "敌血×2.5"},
        ])
        native = {
            "native_hp": 125_000_000.0, "verified": True,
            "components": [
                {"code": "boss_a", "kind": "general",
                 "native_hp": 125_000_000.0},
            ],
        }
        general_boss = {"boss_a": {"100": "general@100"}}
        boss_level = {
            "boss_a": BossLevelHpScalingCase._boss_level(10_000, 1.0),
        }

        def audit():
            return rb.general_hp_scale_plan(
                ["boss_a"], native, general_boss, boss_level, 100,
                target_hp=22_500_000_000.0, curse_hp=curse["hp"],
                code_references=BossLevelHpScalingCase.SAFE_REFS)

        before = audit()
        while rb.downgrade_atk_curse(curse) is not None:
            pass
        after = audit()
        self.assertEqual(curse["atk"], 1.0)
        for key in ("curse_hp", "c86", "baseline_true_hp", "true_hp",
                    "baseline_leaves", "final_leaves"):
            self.assertEqual(before[key], after[key], key)


class SolveAtkCase(unittest.TestCase):
    def _rec(self, **kw):
        base = {"r": 30, "ba": 1.0, "curse": {"atk": 1.0}, "st_mult": 1.0,
                "no_base": False, "anchor": None}
        base.update(kw)
        return base

    def test_combo_cap_binds_on_base_times_curse(self):
        """solve_atk 只报告真实乘积，显式降档由 enforce_atk_band 负责。"""
        rec = self._rec(ba=3.0, curse={"atk": 2.2})
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), 6.6)

    def test_nobase_floor_is_capped_harder(self):
        rec = self._rec(ba=3.0, curse={"atk": 1.0}, no_base=True)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), 3.0)

    def test_true_damage_cap_catches_the_invisible_spike(self):
        """青之女王:col 只有 1.90 却是全塔每跳最疼的一层(原生 atk ≈ 中位 3 倍)。"""
        rec = self._rec(ba=1.9, anchor=(3.0, 1.0))       # 原生是中位的 3 倍
        got = rb.solve_atk(rec, 1.0, 1.0)
        self.assertAlmostEqual(got, 1.9)

    def test_ceiling_is_the_last_backstop(self):
        rec = self._rec(ba=100.0, st_mult=100.0)
        self.assertEqual(rb.solve_atk(rec, 1.0, 1.0), 100.0)

    def test_scale_is_applied_to_the_curve(self):
        rec = self._rec(ba=1.0)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0, scale=0.5), 0.5)


class AtkBandCase(unittest.TestCase):
    def _tower(self, cols, n=30):
        """构造中后段 col = cols 的假塔(每层都带一个顶格玻璃深渊可供降档)。"""
        recs = []
        for i, col in enumerate(cols):
            curse = rb.apply_picks({}, [rb.atk_curse_entry("玻璃深渊", 2)])
            recs.append({"r": n - len(cols) + 1 + i,
                         "ba": col / rb.ATK_CURSE_TIERS["玻璃深渊"][2],
                         "curse": curse, "st_mult": 1.0, "no_base": False,
                         "anchor": None})
        return recs

    def test_band_violation_reports_the_worst_metric_first(self):
        self.assertIsNone(rb.band_violation([1.0, 1.1, 1.35]))
        self.assertEqual(rb.band_violation([1.0, 1.0, 99.0])[0], "max")
        self.assertEqual(rb.band_violation([9.0] * 10)[0], "max")

    def test_p90_uses_nearest_rank(self):
        cols = [1.0] * 18 + [1.34, 1.5]           # n=20 → P90 = 第 18 小
        self.assertIsNone(rb.band_violation(cols))

    def test_enforce_converges_into_the_band(self):
        recs = []
        for r in range(1, 32):
            for name in rb.ATK_CURSE_TIERS:
                for tier in range(3):
                    recs.append({
                        "r": r, "ba": 1.0,
                        "curse": rb.apply_picks({}, [rb.atk_curse_entry(name, tier)]),
                        "st_mult": 9.0, "no_base": False, "anchor": None,
                    })
        _scale, log = rb.enforce_atk_band(recs, 1.1, 1.0, 31)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))
        self.assertTrue(all(r["atk"] <= 1.5 + 1e-9 for r in recs))
        self.assertFalse(any("单层夹到" in line for line in log), log)

    def test_enforce_prefers_downgrade_over_hard_clamp(self):
        """闸门是"降档"不是"闷头夹":有诅咒可降就别直接砍数值。"""
        recs = self._tower([4.0] * 20)
        _scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertTrue(log)
        self.assertTrue(any("×1.4→×1.3" in ln for ln in log), log[:3])
        self.assertFalse(any("单层夹到" in ln for ln in log), log[:3])

    def test_curve_scale_kicks_in_when_no_curse_left(self):
        """中后段已无攻击诅咒可降 = 基础曲线本身太热,全塔等比缩放。"""
        recs = []
        for i in range(20):
            recs.append({"r": 11 + i, "ba": 5.0, "curse": rb.apply_picks({}, []),
                         "st_mult": 1.0, "no_base": False, "anchor": None})
        scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertEqual(scale, 1.0)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))
        self.assertTrue(any("攻击来源" in ln for ln in log))

    def test_early_floors_are_out_of_scope(self):
        """硬上限覆盖浅层；攻击来源超标时也必须显式降档并留痕。"""
        recs = [{"r": 1, "ba": 5.0, "curse": rb.apply_picks({}, []), "st_mult": 1.0,
                 "no_base": False, "anchor": None}]
        _scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertLessEqual(recs[0]["atk"], rb.BAND_TARGET["max"])
        self.assertTrue(any("攻击来源" in line for line in log), log)


class NoBaseFloorCase(unittest.TestCase):
    def test_nobase_floor_never_gets_an_atk_curse(self):
        """standard 表 boss 归一化返回 1.0,拿到裸曲线值,原生数值不在审计视野内。
        第15/18/26/29/30 战都是这种,还叠了攻击诅咒 —— 直接从池子里摘掉。"""
        import random as _r
        for seed in range(40):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell",
                                  caps={"boss": True}, no_base=True)
            names = [c["name"] for c in out["picks"]]
            self.assertFalse(set(names) & set(rb.ATK_CURSE_TIERS), (seed, names))
            self.assertEqual(out["atk"], 1.0, seed)

    def test_normal_floor_still_gets_them(self):
        import random as _r
        hit = 0
        for seed in range(40):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell", caps={"boss": True})
            hit += bool(set(c["name"] for c in out["picks"]) & set(rb.ATK_CURSE_TIERS))
        self.assertGreater(hit, 0, "有基数的层不该被一起误伤")


class LevelRampCase(unittest.TestCase):
    def test_ramp_is_monotone_and_tops_out_at_100(self):
        self.assertEqual(list(rb.LEVEL_RAMP), sorted(rb.LEVEL_RAMP))
        self.assertEqual(rb.LEVEL_RAMP[-1], 100)
        self.assertLess(rb.LEVEL_RAMP[0], 100)

    def test_funnel_column_is_downgraded(self):
        """炮台弹幕同吃 boss 倍率,玩家会把它算进"boss 伤害"。"""
        self.assertLess(rb.FUNNEL_ATK_SCALE, 1.0)
        self.assertGreater(rb.FUNNEL_ATK_SCALE, 0.0)


if __name__ == "__main__":
    unittest.main()
