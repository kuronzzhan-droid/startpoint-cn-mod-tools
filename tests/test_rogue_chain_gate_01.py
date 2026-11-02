"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

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
        from wf.tools.core import field_catalog as fc
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
        钉住三条下载 hp 曲线在 lv100 的值；APK 内置默认曲线
        可以合并进来，不应再用“总数必须恰好为 3”拒绝它们。"""
        try:
            q.read_raw(rb.CURVE_TABLES["hp"])
        except FileNotFoundError:
            self.skipTest("configured store is missing downloaded HP growth-curve table")
        c = rb.growth_curves()
        self.assertTrue(
            {"hit_hp_correction_non_element", "hit_hp_boss", "hit_hp_funnel"}
            <= set(c["hp"])
        )
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

    def test_client_bundled_normal_curve_is_absolute(self):
        """normal Hit 基表由审计快照提供，不再冒充未知代理。"""
        self.assertEqual(rb.PROXY_CURVE, {"hp": "hit_hp_boss", "atk": "atk_single"})
        self.assertEqual(
            rb.client_bundled_curve_baseline_receipt()["member_sha256"],
            "713007008fc91f55555eefe72e913380a29664e23b8e0ac2cfdca95e450f5370")
        self.assertAlmostEqual(
            rb.curve_value("hp", "hit_hp_correction_normal", 100),
            31.26519, places=6)
        st = rb.boss_base_stats()
        if not st:
            self.skipTest("store 不可用")
        normal = [c for c, s in st.items()
                  if s["hpc"] == "hit_hp_correction_normal"]
        self.assertTrue(normal, "没有 normal 曲线 boss 了?")
        t = rb.true_stat(normal[0], "hp", 100)
        self.assertEqual(t[1], "*", "已知客户端曲线应进统一绝对组")

    def test_client_bundled_curve_conflict_fails_closed(self):
        old_curves, old_bundled = rb._CURVES, rb._BUNDLED_CURVES
        self.addCleanup(setattr, rb, "_CURVES", old_curves)
        self.addCleanup(setattr, rb, "_BUNDLED_CURVES", old_bundled)
        rb._CURVES = None
        rb._BUNDLED_CURVES = None
        with mock.patch.object(
                rb, "_bundled_curve_source", return_value=Path("client.apk")), \
                mock.patch.object(
                    rb, "_bundle_member_bytes", return_value=b"conflict"):
            with self.assertRaisesRegex(
                    ValueError, "CLIENT_BUNDLED_CURVE_CONFLICT"):
                rb.bundled_growth_curves()

    def test_standard_boss_really_has_no_stats(self):
        """钉住那条结论:standard_boss 的行只有名字+资产,没有数值列。"""
        from wf.tools.core import quest_lib as qlib
        try:
            sb = qlib.load_table(rb.STANDARD_BOSS)
        except Exception:
            self.skipTest("store 不可用")
        node = sb.get("chapter12_boss_story")
        if not isinstance(node, dict):
            self.skipTest("终始之龙不在 standard_boss")
        row = rb.cells(next(iter(node.values())))
        self.assertLessEqual(len(row), 3, f"standard_boss 行变长了:{row}")


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


class EndlessRerollSafetyCase(unittest.TestCase):
    def test_endless_reroll_rejects_every_non_700099_99_target_before_write(self):
        """目标门禁若被移除，首个官方 700007/8 fixture 会被旧实现真实改写。"""
        for event, quest_no in (("700007", "8"), ("700099", "8")):
            with self.subTest(event=event, quest_no=quest_no):
                target = [f"{event}{int(quest_no):03d}"] + [""] * 99
                quest_table = {event: {quest_no: ",".join(target)}}
                unsafe_pool = [
                    ("unsafe_field", "unsafe_field,bgm_unsafe", ["unsafe_boss"])]

                with mock.patch("wf.tools.content.chain_build.build_pool",
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
                 mock.patch.object(q, "exists_current", return_value=True), \
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
            observed_legacy_store = []

            def reject_preflight(_command, **kwargs):
                observed_original.append(quest_path.read_bytes() == original)
                observed_store.append(
                    kwargs.get("env", {}).get("WF_STORE"))
                observed_legacy_store.append(
                    "WF_TARGET_STORE" in kwargs.get("env", {}))
                return mock.Mock(returncode=7)

            with mock.patch.dict(os.environ, {"WF_TARGET_STORE": "stale-store"}), \
                 mock.patch.object(q, "store_path", return_value=quest_path), \
                 mock.patch.object(q, "exists_current", return_value=True), \
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
            self.assertEqual(observed_legacy_store, [False])
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
                 mock.patch.object(q, "exists_current", return_value=True), \
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


    def setUp(self):
        for name, value in (("resolve_server_dir", Path("configured-server")),
                            ("resolve_cdn_root", Path("configured-cdn"))):
            patch = mock.patch.object(rsave.core, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)
