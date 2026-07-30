# -*- coding: utf-8 -*-
"""引用完整性门禁 + 发布完整性自检回归测试。

事故背景(2026-07-26):
  缺陷1 关13 被随机到 field water_sphere,其 boss water_sphere_single 在
        general_boss/standard_boss/general_zako 三表全缺 → 真机 U_50fc52 进本崩;
  缺陷2 构建写了 mod_rogue_f9 等克隆进 store,发布清单没带 battle 表 →
        客户端 C8601「指定的Key不存在。key=mod_rogue_f9」。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_quest_lib as q  # noqa: E402
import wf_rogue_build as rb  # noqa: E402


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
            self.assertGreater(atk_end, atk0, f"{diff} 曲线必须递增")

    def test_atk_ceiling_guards_curse_stacking(self):
        """诅咒叠乘 + 工坊 ×1.15 会把 atk 冲高,硬上限兜底。

        ⚠ 2026-07-30 反向收紧:旧值 8.0 **从未触发过**(现役塔最高 6.58),
        所以它压不到中位,只是个摆设。新值 6.6 卡在官方全库孤例 6.63 之下 ——
        真正干活的是 ATK_COMBO_CAP / NOBASE_ATK_CAP / TRUE_DMG_CAP / 分位闸,
        ceiling 只当最后一道兜底。别再往上放。"""
        self.assertLessEqual(rb.ATK_MULT_CEILING, 6.63, "不许超官方全库孤例")
        self.assertGreaterEqual(rb.ATK_MULT_CEILING, 4.0)
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
        # 下取整:80 级取 ≤80 的最大档(79)
        self.assertAlmostEqual(rb.curve_value("hp", "hit_hp_boss", 80), 17.24699977, 4)
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
            imm = {k for k, v in out["conds"] if str(v) in ("1", "1.0")}
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

    def test_resistance_below_one_never_locks(self):
        a = {"name": "深渊壁垒", "cond": [(str(k), "0.3") for k in range(4)]}
        self.assertIsNone(rb.curse_conflict([a]))

    def test_live_sampling_has_no_softlock(self):
        """真抽 4000 次,不允许出现无解层或槽位溢出。"""
        import random as _r
        for seed in range(4000):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell", caps={"boss": True})
            conds = out["conds"]
            self.assertLessEqual(len(conds), 5, seed)
            immune = {k for k, v in conds if str(v) in ("1", "1.0")}
            self.assertFalse(immune >= {"0", "1", "2", "3"}, f"seed {seed} 无解层")


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

    def test_non_hell_keeps_the_blank_warmup(self):
        import random as _r
        out = rb.abyss_curses(2, 30, _r.Random(2), "standard", caps={"boss": True})
        self.assertEqual(out["desc"], "")

    def test_hell_count_ramp(self):
        import random as _r

        def n_curses(r):
            d = rb.abyss_curses(r, 30, _r.Random(r), "hell", caps={"boss": True})["desc"]
            return d.count("「")

        self.assertEqual(n_curses(3), 1)     # d=0.10 ≤0.15
        self.assertEqual(n_curses(9), 2)     # d=0.30
        self.assertEqual(n_curses(28), 3)    # d=0.93 >0.6


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
        self.assertEqual(len(c["cond"]), 3)
        self.assertEqual({k for k, _v in c["cond"]}, {"1", "2", "3"})   # 放行 0
        self.assertTrue(all(v == rb.fmt(1.0) for _k, v in c["cond"]))
        self.assertIn("三重免疫", c["text"])

    def test_lower_tiers_are_resistance_not_immunity(self):
        for t, want in ((0, 0.5), (1, 0.7)):
            c = self.pool(t)["三重壁垒"]
            self.assertTrue(all(v == rb.fmt(want) for _k, v in c["cond"]), t)
            self.assertNotIn("三重免疫", c["text"])

    def test_fits_the_five_condition_slots(self):
        # 三重壁垒(3 条)+ 亡者不屈(2 条)= 5,正好塞满,不会被 conds[:5] 截断
        p = self.pool(2)
        self.assertLessEqual(len(p["三重壁垒"]["cond"]) + len(p["亡者不屈"]["cond"]), 5)


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

    槽位 = (门, 单人列, 多人列):(23,24,26)/(27,28,30)/(31,32,34)。
    """
    row = [""] * 41
    for n, b in enumerate(bosses):
        gate, single, multi = ((23, 24, 26), (27, 28, 30), (31, 32, 34))[n]
        row[gate] = "1"
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

    def test_plain_field_allowed(self):
        why = rb.caster_carrier_block("f_single", ["lone_boss"],
                                      self.FD, self.ZONE, frozenset())
        self.assertIsNone(why)

    def test_multi_entity_zone_blocked(self):
        why = rb.caster_carrier_block("f_pair", ["form1", "form2"],
                                      self.FD, self.ZONE, frozenset())
        self.assertIsNotNone(why)
        self.assertIn("boss 实体", why)

    def test_phase_linked_boss_blocked_even_when_alone(self):
        """索拉斯型:这层只摆了一只,但它的转场按代号找同伴,克隆即断链。"""
        why = rb.caster_carrier_block("f_ph1", ["lich"],
                                      self.FD, self.ZONE, frozenset({"lich", "owl"}))
        self.assertIsNotNone(why)
        self.assertIn("分阶段", why)

    def test_unknown_field_falls_back_to_boss_check(self):
        self.assertIsNone(rb.caster_carrier_block("f_ghost", ["lone_boss"],
                                                  self.FD, self.ZONE, frozenset()))
        self.assertIsNotNone(rb.caster_carrier_block("f_ghost", ["lich"],
                                                     self.FD, self.ZONE,
                                                     frozenset({"lich"})))


class ZoneBossSlotsCase(unittest.TestCase):
    def test_counts_entities_not_columns(self):
        zn = {"0": wave_pair(bosses=("a", "b"))}
        self.assertEqual(rb.zone_boss_slots(zn), [{"a"}, {"b"}])

    def test_single_multi_variants_are_one_entity(self):
        wc = wave_pair(bosses=("x_single",)).split(",")
        wc[26] = "x_multi"                      # 官方 78 处这样写
        zn = {"0": ",".join(wc)}
        self.assertEqual(rb.zone_boss_slots(zn), [{"x_single", "x_multi"}])

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
        """烈狱档端点 = 用户 2026-07-30 指定的 1.7 / 1.8 / 2.6(旧 2.0/2.2/3.0)。"""
        self.assertEqual(rb.ATK_CURSE_TIERS["嗜血狂潮"][2], 1.7)
        self.assertEqual(rb.ATK_CURSE_TIERS["深渊逆鳞"][2], 1.8)
        self.assertEqual(rb.ATK_CURSE_TIERS["玻璃深渊"][2], 2.6)

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
        self.assertIn("敌攻×2.6", curse["desc"])
        rb.downgrade_atk_curse(curse)
        self.assertIn("敌攻×2.3", curse["desc"])
        self.assertNotIn("敌攻×2.6", curse["desc"])

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


class SolveAtkCase(unittest.TestCase):
    def _rec(self, **kw):
        base = {"r": 30, "ba": 1.0, "curse": {"atk": 1.0}, "st_mult": 1.0,
                "no_base": False, "anchor": None}
        base.update(kw)
        return base

    def test_combo_cap_binds_on_base_times_curse(self):
        """单项都不越界、乘起来越界的层(第26战 基础2.99×逆鳞2.2=6.58)。"""
        rec = self._rec(ba=3.0, curse={"atk": 2.2})
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), rb.ATK_COMBO_CAP)

    def test_nobase_floor_is_capped_harder(self):
        rec = self._rec(ba=3.0, curse={"atk": 1.0}, no_base=True)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), rb.NOBASE_ATK_CAP)

    def test_true_damage_cap_catches_the_invisible_spike(self):
        """青之女王:col 只有 1.90 却是全塔每跳最疼的一层(原生 atk ≈ 中位 3 倍)。"""
        rec = self._rec(ba=1.9, anchor=(3.0, 1.0))       # 原生是中位的 3 倍
        got = rb.solve_atk(rec, 1.0, 1.0)
        self.assertAlmostEqual(got * 3.0 / 1.0, rb.TRUE_DMG_CAP)

    def test_ceiling_is_the_last_backstop(self):
        rec = self._rec(ba=100.0, st_mult=100.0)
        self.assertLessEqual(rb.solve_atk(rec, 1.0, 1.0), rb.ATK_MULT_CEILING)

    def test_scale_is_applied_to_the_curve(self):
        rec = self._rec(ba=1.0)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0, scale=0.5), 0.5)


class AtkBandCase(unittest.TestCase):
    def _tower(self, cols, n=30):
        """构造中后段 col = cols 的假塔(每层都带一个顶格玻璃深渊可供降档)。"""
        recs = []
        for i, col in enumerate(cols):
            curse = rb.apply_picks({}, [rb.atk_curse_entry("玻璃深渊", 2)])
            recs.append({"r": n - len(cols) + 1 + i, "ba": col / 2.6,
                         "curse": curse, "st_mult": 1.0, "no_base": False,
                         "anchor": None})
        return recs

    def test_band_violation_reports_the_worst_metric_first(self):
        self.assertIsNone(rb.band_violation([1.0, 1.5, 2.0]))
        self.assertEqual(rb.band_violation([1.0, 1.0, 99.0])[0], "max")
        self.assertEqual(rb.band_violation([9.0] * 10)[0], "max")

    def test_p90_uses_nearest_rank(self):
        cols = [1.0] * 18 + [2.9, 2.9]            # n=20 → P90 = 第 18 小
        self.assertIsNone(rb.band_violation(cols))

    def test_enforce_converges_into_the_band(self):
        recs = self._tower([6.0] * 20)
        rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))

    def test_enforce_prefers_downgrade_over_hard_clamp(self):
        """闸门是"降档"不是"闷头夹":有诅咒可降就别直接砍数值。"""
        recs = self._tower([4.0] * 20)
        _scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertTrue(log)
        self.assertTrue(any("×2.6→×2.3" in ln for ln in log), log[:3])
        self.assertFalse(any("单层夹到" in ln for ln in log), log[:3])

    def test_curve_scale_kicks_in_when_no_curse_left(self):
        """中后段已无攻击诅咒可降 = 基础曲线本身太热,全塔等比缩放。"""
        recs = []
        for i in range(20):
            recs.append({"r": 11 + i, "ba": 5.0, "curse": rb.apply_picks({}, []),
                         "st_mult": 1.0, "no_base": False, "anchor": None})
        scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertLess(scale, 1.0)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))
        self.assertTrue(any("全塔曲线" in ln for ln in log))

    def test_early_floors_are_out_of_scope(self):
        """闸门只管中后段(进度 > 1/3);前段玩家反馈「都不算强」,别再削。"""
        recs = [{"r": 1, "ba": 5.0, "curse": rb.apply_picks({}, []), "st_mult": 1.0,
                 "no_base": False, "anchor": None}]
        rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertGreater(recs[0]["atk"], rb.BAND_TARGET["median"])


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
