"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

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

    def test_weak_resistance_on_all_elements_does_not_count_as_six_bans(self):
        low = {"name": "低阻测试", "element_resistance": [
            (1, 1.0), (2, 9.0), (3, 1.0), (4, 9.0), (5, 1.0), (6, 9.0)]}
        self.assertEqual(rb.immunity_axes([low])[1], set())
        self.assertIsNone(rb.curse_conflict([low]))

    def test_overlapping_element_resistance_matches_client_addition(self):
        # 元素抗性跨卡累加，显式 cancelable=True 也统一钉死为不可驱散。
        picks = [
            {"name": "甲", "element_resistance": [(1, 1.0), (2, 99.0)]},
            {"name": "乙", "element_resistance": [(1, 9.0, False),
                                                     (2, 999.0, True),
                                                     (3, 1.0, True)]},
        ]
        self.assertEqual(rb._merged_resistance(picks, "element_resistance"),
                         [(1, 10.0, False), (2, 1098.0, False),
                          (3, 1.0, False)])

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

    def test_cross_curse_element_cards_cannot_merge_into_six_bans(self):
        a = {"name": "高阻甲", "element_resistance": [(1, 99.0), (2, 99.0), (3, 99.0)]}
        b = {"name": "高阻乙", "element_resistance": [(4, 999.0), (5, 99.0), (6, 99.0)]}
        why = rb.curse_conflict([a, b])
        self.assertIn("六属性", why or "")

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


    def test_subthreshold_element_resistance_does_not_close_the_exit(self):
        low = {"name": "低阻测试", "element_resistance": [
            (1, 1.0), (2, 9.0), (3, 1.0), (4, 9.0), (5, 1.0), (6, 9.0)]}
        self.assertEqual(set(), rb.immunity_axes([low])[1])
        self.assertIsNone(rb.curse_conflict([low]))

    def test_cross_curse_element_immunity_is_merged_before_gate(self):
        a = {"name": "高阻甲", "element_resistance": [(1, 99.0), (2, 99.0), (3, 99.0)]}
        b = {"name": "高阻乙", "element_resistance": [(4, 999.0), (5, 99.0), (6, 99.0)]}
        why = rb.curse_conflict([a, b])
        self.assertIn("六属性", why or "")
        self.assertIn("r≥99", why or "")


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
        self.assertTrue(all(
            atom[2] is False
            for card in soft_cards for atom in card["element_resistance"]
        ))
        hard = rb.mixed_element_entry(_r.Random(3), strengths=(99, 999))
        self.assertTrue(all(atom[2] is False for atom in hard["element_resistance"]))
        soft_names = ("深渊壁垒", "绝对壁垒", "三重壁垒")
        counts = dict.fromkeys(soft_names, 0)
        for seed in range(400):
            sampled = {c["name"]: c for c in rb._curse_pool(0, _r.Random(seed))}
            for soft_name in soft_names:
                key = ("element_resistance" if "元素" in soft_name or "三相" in soft_name
                       else "damage_resistance")
                counts[soft_name] += any(atom[2] for atom in sampled[soft_name][key])
        for soft_name, got in counts.items():
            self.assertTrue(70 <= got <= 130, (soft_name, got))
        for seed in range(400):
            sampled = {c["name"]: c for c in rb._curse_pool(0, _r.Random(seed))}
            for element_name in ("元素滞钝", "三相封界"):
                self.assertTrue(all(
                    atom[2] is False
                    for atom in sampled[element_name]["element_resistance"]
                ))
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
        self.assertEqual(names, ["ACSkillDamageResistance"])
        hard_params = hard_command[1:]
        self.assertIs(hard_params[4], False)              # 伤害硬墙/全部元素抗性不可驱散
        self.assertEqual([ac[0] for ac in hard_params[1]],
                         ["ACAbilityDamageResistance", "ACToleranceOfElement",
                          "ACToleranceOfElement"])
        self.assertEqual(hard_params[1][2][2], 6)         # 数据层 1-based
        self.assertEqual(hard_params[1][2][3][0]["min"], 999.0)

    def test_explicit_element_cancelable_request_is_forced_off(self):
        self.assertEqual(
            rb._normalize_resistance_atom((1, 1.0, True), "element_resistance"),
            (1, 1.0, False),
        )

    def test_blob_round_trip_preserves_constructor_names(self):
        tree = rb.build_immunity_dsl_tree(
            [(2, 0.7, True)], [(2, 9.0, True), (5, 99.0, False)])
        blob = rb.build_immunity_dsl_blob(tree)
        parsed = wf_dsl.parse_dsl(zlib.decompress(blob, -15))["tree"]
        self.assertEqual(parsed, tree)
        false_id = rb.immunity_program([], [(2, 9.0, False)])[0]
        true_id = rb.immunity_program([], [(2, 9.0, True)])[0]
        self.assertEqual(false_id, true_id)
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

    def test_c36_true_accepts_positive_resistance_on_the_actual_cloned_row(self):
        gb = {"source": self._node("true")}
        gb["mod_rogue_boss4"] = gb["source"]
        why = rb.general_boss_element_immunity_block(gb, "mod_rogue_boss4")
        self.assertIsNone(why)

    def test_false_is_allowed_but_unknown_values_fail_closed(self):
        self.assertIsNone(rb.general_boss_element_immunity_block(
            {"ok": self._node("False")}, "ok"))
        for code, node in (("bad", self._node("yes")),
                           ("short", self._node("false", short=True))):
            self.assertIsNotNone(rb.general_boss_element_immunity_block({code: node}, code))
        self.assertIsNotNone(rb.general_boss_element_immunity_block({}, "missing"))

    @requires_store
    def test_known_official_c36_prototypes_accept_positive_resistance(self):
        gb = q.load_table(rb.GENERAL_BOSS)
        gv = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
        # 2026-08-05 用户按 getSurjectivity 独立复算：具体塔层/clone ID 会随 seed
        # 与所选等级行变化，不能再钉“第4/13/20战”或当前 store 的 mod_rogue_boss4。
        # 门禁应先在官方原型实际等级行成立，克隆后另由构建期最终复核保证继承。
        for code, level in (("dark_matter_single", 80), ("smr21_big_boss_ex", 90),
                            ("beasts_big_boss_multi_80", 90)):
            why = rb.general_boss_element_immunity_block(gb, code, level, gv)
            self.assertIsNone(why, code)

    def test_only_the_runtime_selected_level_row_controls_c36(self):
        gb = {"mixed": {"79": self._node("false")["80"],
                         "100": self._node("true")["80"]}}
        gv = {"mixed": {"79": "dummy", "100": "dummy"}}
        # GeneralBossSource 直接按 enemy level 在 general_boss 上取首个 ≥level 的行；
        # gv 另行解析,不能拿 gv 的下取整结果替 c36 选行。
        self.assertIsNone(rb.general_boss_element_immunity_block(gb, "mixed", 79, gv))
        self.assertIsNone(rb.general_boss_element_immunity_block(gb, "mixed", 90, gv))
        gb["mixed"]["100"] = self._node("invalid")["80"]
        self.assertIn("gb[100]", rb.general_boss_element_immunity_block(gb, "mixed", 90, gv) or "")

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
        # 领域采用独立配额；静态闭包未证明顺序调度前只落 1 个领域。
        # 同时深层禁时限，所以 mock 池里的时之枷锁不能拿来凑数。
        ordinary = [c for c in out["picks"] if not c.get("caster")]
        fields = [c for c in out["picks"] if c.get("caster")]
        self.assertEqual(len(ordinary), 4)
        self.assertEqual(len(fields), 1)
        self.assertEqual(len(names), 5)
        self.assertIn("五相绝域", names)
        self.assertIn("血肉高墙", names)
        self.assertNotIn("元素禁壁", names)
        self.assertLess(len(rb.immunity_axes(out["picks"])[1]), 6)
        # Multiple cards are legal, but their union cannot close all six axes.
        self.assertTrue(any("六属性" in str(call)
                            and "redraw" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)


    def test_c36_true_allows_positive_resistance_on_actual_cloned_row(self):
        gb = {"source": self._node("true")}
        gb["mod_rogue_boss4"] = gb["source"]
        why = rb.general_boss_element_immunity_block(gb, "mod_rogue_boss4")
        self.assertIsNone(why)

    @requires_store
    def test_known_official_prototypes_accept_positive_resistance_before_cloning(self):
        gb = q.load_table(rb.GENERAL_BOSS)
        gv = q.load_table("master/battle/boss/general_boss_variable.orderedmap")
        # 2026-08-05 用户按 getSurjectivity 独立复算：具体塔层/clone ID 会随 seed
        # 与所选等级行变化，不能再钉“第4/13/20战”或当前 store 的 mod_rogue_boss4。
        # 门禁应先在官方原型实际等级行成立，克隆后另由构建期最终复核保证继承。
        for code, level in (("dark_matter_single", 80), ("smr21_big_boss_ex", 90),
                            ("beasts_big_boss_multi_80", 90)):
            why = rb.general_boss_element_immunity_block(gb, code, level, gv)
            self.assertIn("c36=true", why or "", code)


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
        for r, want in ((15, 0), (16, 1), (24, 1), (25, 1), (30, 1)):
            self.assertEqual(rb.required_field_slots(r, 30), want, r)

    def test_deep_random_roll_has_one_field_and_no_time_limit(self):
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
        # “第4个诅咒”与领域是两条独立机制：4 个非领域 + 1 个领域。
        self.assertEqual(len(out["picks"]), 5)
        self.assertEqual(sum(not c.get("caster") for c in out["picks"]), 4)
        self.assertEqual(len(out["casters"]), 1)
        self.assertEqual(len({m[1] for m in out["casters"]}), 1)
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
        self.assertEqual(out["field_requested"], 1)
        self.assertEqual(out["field_deficit"], 1)
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
        self.assertEqual(len(out["casters"]), 1)
        self.assertNotIn("元素禁壁", {c["name"] for c in ordinary})
        self.assertTrue(any("深层普通诅咒固定 4 个" in str(call)
                            for call in logger.call_args_list), logger.call_args_list)


    def test_deep_random_roll_uses_one_verified_field_and_no_time_limit(self):
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
        # Online policy caps field scheduling at one until multi-field closure is proven.
        self.assertEqual(len(out["picks"]), 5)
        self.assertEqual(sum(not c.get("caster") for c in out["picks"]), 4)
        self.assertEqual(len(out["casters"]), 1)
        self.assertEqual(len({m[1] for m in out["casters"]}), 1)
        self.assertFalse(any("time" in c for c in out["picks"]), out["picks"])
        self.assertEqual(out["field_deficit"], 0)
