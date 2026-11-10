"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

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

    def test_exact_kind_gate_uses_selected_gv_tier_for_general_boss(self):
        tables = rb.boss_ref_validation_tables(
            standard_boss={},
            general_boss={"boss_g": {"80": "x"}},
            general_boss_variable={"boss_g": {"80": "x"}},
            special_tables={}, funnel_ok=lambda _code, _level: True)
        gate = rbb.validate_boss_ref(
            rbb.BossRef(1, "boss_g"), 100, tables)
        self.assertTrue(gate.ok, gate)
        self.assertEqual(80, gate.selected_level)

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
                # Standard directly upper-selects against c95 (90 -> 100).
                # General first lower-selects gv (90 -> 80), then upper-selects
                # GeneralBossValues against that selected variable tier.
                self.assertEqual(
                    result.selected_level, 100 if ref.kind == 0 else 80)

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
            self.assertNotIn(
                "SPECIAL_PHASE_HP_UNSCALABLE", by_code.get("orochi_ex", set()))
            self.assertTrue(any(
                rb.special_bundle_family(bundle) == "orochi_ex"
                for bundles in catalog.bundles.values() for bundle in bundles))

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
            ex_family_ids = [
                family for family, name in catalog.family_names.items()
                if name == "八岐大蛇 EX"
            ]
            self.assertEqual(len(ex_family_ids), 1)
            ex_bundles = [
                bundle
                for variant_id in catalog.variants.get(ex_family_ids[0], ())
                for bundle in catalog.bundles[variant_id]
            ]
            self.assertEqual(
                [(bundle.source_field, rb.special_bundle_family(bundle))
                 for bundle in ex_bundles],
                [("multi_normal_1_20_4", "orochi_ex")])

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


class QuestThumbnailEvidenceCase(unittest.TestCase):
    BOSS_QUEST = "master/quest/boss_battle_quest.orderedmap"
    TOWER_QUEST = "master/quest/event/tower_dungeon_event_quest.orderedmap"

    @staticmethod
    def direct_row(field, thumbnail, level):
        row = [""] * 12
        row[3] = thumbnail
        row[7] = str(level)
        row[10] = field
        return ",".join(row)

    @staticmethod
    def tower_row(floor_key, thumbnail, level):
        row = [""] * 100
        row[3] = thumbnail
        row[96] = str(level)
        row[99] = floor_key
        return ",".join(row)

    def evidence(self):
        field_data = {
            "boss_field": "boss_field,terrain,zone",
            "boss_alias_field": "boss_alias_field,terrain,zone_alias",
            "visual_alias_field": "visual_alias_field,terrain,zone_visual",
            "floor_only_field": "floor_only_field,terrain,zone_floor",
            "mod_rogue_f24": "mod_rogue_f24,terrain,zone",
        }
        zone = {
            "zone": {"0": wave(bosses=("same_boss",))},
            "zone_alias": {"0": wave(bosses=("same_boss",))},
            "zone_visual": {"0": wave(bosses=("same_boss_tower",))},
            "zone_floor": {"0": wave(bosses=("unmapped_boss",))},
        }
        floor = {
            "official_floor": (
                "floor_only_field,bgm,floor/icon_31x31\n"
                "boss_field,bgm,floor/wrong_icon"),
        }
        quest_tables = {
            self.BOSS_QUEST: {
                "low": self.direct_row(
                    "boss_field", "quest/thumbnail/boss_low", 50),
                "high": self.direct_row(
                    "boss_field", "quest/thumbnail/boss_high", 100),
                "generated": self.direct_row(
                    "mod_rogue_f24", "quest/thumbnail/stale", 100),
            },
            self.TOWER_QUEST: {
                "host": self.tower_row(
                    "official_floor", "quest/thumbnail/tower_host", 90),
            },
        }
        return rb.field_thumbnail_evidence_map(
            field_data=field_data, zone=zone,
            floor=floor,
            quest_tables=quest_tables,
            asset_exists=lambda logical: logical.endswith(".png"),
            boss_identity_of=lambda code: {
                "same_boss": "Same Boss\0battle/boss/same",
                "same_boss_tower": "Same Boss\0battle/boss/same",
            }.get(code, code),
        )

    def test_exact_highest_level_quest_cover_beats_floor_icon_and_host(self):
        evidence = self.evidence()["boss_field"]
        self.assertEqual("quest/thumbnail/boss_high", evidence["thumbnail"])
        self.assertEqual("exact_field", evidence["source_match"])
        self.assertEqual(100, evidence["source_level"])
        self.assertEqual(
            "quest/thumbnail/boss_high.png", evidence["asset_logical"])
        self.assertTrue(evidence["static_verified"])
        self.assertIs(evidence["runtime_simulated"], False)
        self.assertIs(evidence["gameplay_verified"], False)

    def test_floor_host_is_only_fallback_and_never_uses_floor_icon(self):
        evidence = self.evidence()["floor_only_field"]
        self.assertEqual("quest/thumbnail/tower_host", evidence["thumbnail"])
        self.assertEqual("floor_host_quest", evidence["source_match"])
        self.assertEqual("official_floor", evidence["floor_key"])
        with self.assertRaisesRegex(ValueError, "floor_host_quest"):
            rb.resolve_quest_thumbnail(
                "floor_only_field", "", self.evidence(), require=True)

    def test_exact_boss_identity_borrows_cover_from_direct_official_quest(self):
        evidence = self.evidence()["boss_alias_field"]
        self.assertEqual("quest/thumbnail/boss_high", evidence["thumbnail"])
        self.assertEqual("exact_boss_identity", evidence["source_match"])
        self.assertEqual("boss_field", evidence["cover_field"])
        self.assertEqual(["same_boss"], evidence["bosses"])
        thumbnail, resolved = rb.resolve_quest_thumbnail(
            "boss_alias_field", "quest/thumbnail/wrong", self.evidence(),
            require=True)
        self.assertEqual("quest/thumbnail/boss_high", thumbnail)
        self.assertEqual("exact_boss_identity", resolved["source_match"])

    def test_visual_boss_identity_covers_official_alias_ids(self):
        evidence = self.evidence()["visual_alias_field"]
        self.assertEqual("quest/thumbnail/boss_high", evidence["thumbnail"])
        self.assertEqual(
            "exact_boss_visual_identity", evidence["source_match"])
        self.assertEqual("boss_field", evidence["cover_field"])
        self.assertEqual(["same_boss_tower"], evidence["bosses"])
        self.assertEqual(
            ["Same Boss\0battle/boss/same"],
            evidence["boss_visual_identity"])
        thumbnail, resolved = rb.resolve_quest_thumbnail(
            "visual_alias_field", "quest/thumbnail/wrong", self.evidence(),
            require=True)
        self.assertEqual("quest/thumbnail/boss_high", thumbnail)
        self.assertEqual(
            "exact_boss_visual_identity", resolved["source_match"])

    def test_generated_field_cannot_launder_its_stale_cover_into_evidence(self):
        self.assertNotIn("mod_rogue_f24", self.evidence())

    def test_actual_boss_donor_cover_overrides_terrain_thumbnail(self):
        thumbnail, evidence = rb.resolve_quest_thumbnail(
            "boss_field", "quest/thumbnail/terrain_boss",
            self.evidence(), require=True)
        self.assertEqual("quest/thumbnail/boss_high", thumbnail)
        self.assertEqual("boss_field", evidence["field"])

    def test_boss_floor_without_evidence_cannot_keep_template_cover(self):
        with self.assertRaisesRegex(ValueError, "拒绝沿用模板/地形封面"):
            rb.resolve_quest_thumbnail(
                "unknown", "quest/thumbnail/template", {}, require=True)

        row = [""] * 100
        row[5] = "quest/thumbnail/template"
        with self.assertRaisesRegex(ValueError, "拒绝沿用模板旧封面"):
            rb.patch_quest_boss_fields(
                row, field="unknown", bosses=["boss"], thumbnail="",
                bgm=None, enemy_level=100, rng=random.Random(1),
                field_elements={}, boss_elements={}, require_thumbnail=True)

    def test_missing_png_is_rejected_before_c5_write(self):
        row = [""] * 100
        with self.assertRaisesRegex(ValueError, "封面资源不存在"):
            rb.patch_quest_boss_fields(
                row, field="boss_field", bosses=["boss"],
                thumbnail="quest/thumbnail/missing", bgm=None,
                enemy_level=100, rng=random.Random(1),
                field_elements={"boss_field": 0}, boss_elements={},
                require_thumbnail=True,
                thumbnail_asset_exists=lambda _logical: False)


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

    def test_native_special_slot_only_uses_an_unoccupied_deep_round(self):
        schedule = self.sched(30)
        before = dict(schedule)
        slot = rb.reserve_schedule_slot(
            schedule, 30, "八岐大蛇", fraction=0.8)
        self.assertIsNotNone(slot)
        self.assertNotIn(slot, before)
        self.assertEqual(schedule[slot], "八岐大蛇")
        self.assertEqual({key: schedule[key] for key in before}, before)
        self.assertNotIn(slot, (1, 29, 30))

        before_ex = dict(schedule)
        ex_slot = rb.reserve_schedule_slot(
            schedule, 30, "八岐大蛇EX", fraction=0.74)
        self.assertIsNotNone(ex_slot)
        self.assertNotEqual(ex_slot, slot)
        self.assertNotIn(ex_slot, before_ex)
        self.assertEqual(schedule[ex_slot], "八岐大蛇EX")
        self.assertEqual({key: schedule[key] for key in before_ex}, before_ex)
        self.assertNotIn(ex_slot, (1, 29, 30))

        full = {round_no: "occupied" for round_no in range(1, 31)}
        self.assertIsNone(rb.reserve_schedule_slot(full, 30, "八岐大蛇"))
        self.assertEqual(len(full), 30)

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
