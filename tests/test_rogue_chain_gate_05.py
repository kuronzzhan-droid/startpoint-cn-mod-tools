"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

class BossLevelHpScalingCasePart3(unittest.TestCase):

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

    @staticmethod
    def _general_state_node(routine: str, percentage: str = "20") -> tuple[dict, dict]:
        general = [""] * 161
        general[42] = routine
        trial = [""] * 53
        trial[0] = "trial_state"
        trial[16] = percentage
        trial[17:22] = ["true", "false", "true", "false", "failed_state"]
        trial[29:33] = ["0", "", "success_state", ""]
        ordinary = list(trial)
        ordinary[0] = "ordinary_state"
        ordinary[16] = "(None)"
        # next_state test kind 9 is a different DamageCheck condition.  It is
        # intentionally present on the non-red state to pin that distinction.
        ordinary[29:33] = ["9", "", "17", "target_state"]
        return (
            {"100": rb.join(general, False)},
            {routine: {"1": {
                "trial": rb.join(trial, False),
                "ordinary": rb.join(ordinary, False),
            }}},
        )

    def test_mixed_plan_preserves_occurrence_order_across_general_and_standard(self):
        tree = {"au": [{"d": ["T1", 100]}, {"d": ["T1", 200]}]}
        logical = "battle/enemy/boss/mixed_standard.esdl.amf3.deflate"
        resources = {logical: rb.build_standard_enemy_dsl_blob(tree)}
        standard_boss = {
            "std": {"100": rb.join(
                ["混合 Standard", "battle/enemy/boss/mixed_standard"], False)},
        }
        evidence = rb.standard_boss_hp_evidence(
            "std", 100, standard_boss, resources)
        native = {
            "verified": True, "absolute_verified": True, "native_hp": 265.0,
            "components": [
                {"code": "hit", "kind": "general", "hp_curve_kind": "hit",
                 "evidence_kind": "absolute", "native_hp": 100.0,
                 "boss_occurrence": 1},
                {"code": "std", "kind": "standard", "form_index": 0,
                 "phase": "form[0]", "evidence_kind": "absolute",
                 "native_hp": 55.0, "boss_occurrence": 2,
                 "evidence": evidence},
                {"code": "std", "kind": "standard", "form_index": 1,
                 "phase": "form[1]", "evidence_kind": "absolute",
                 "native_hp": 110.0, "boss_occurrence": 2,
                 "evidence": evidence},
            ],
        }
        plan = rb.mixed_hp_scale_plan(
            ["hit", "std"], native,
            {"hit": self._general_node(100)}, {"hit": self._boss_level(10)},
            standard_boss, 100, target_hp=530.0, curse_hp=2.5,
            code_references=self.SAFE_REFS, resources=resources)
        self.assertEqual(plan["channel"], "mixed_hp")
        self.assertEqual(plan["baseline_scale"], 2.0)
        self.assertEqual(plan["baseline_component_hp"], (200.0, 110.0, 220.0))
        self.assertEqual(plan["final_component_hp"], (500.0, 275.0, 550.0))
        self.assertEqual(plan["baseline_true_hp"], 530.0)
        self.assertEqual(plan["true_hp"], 1325.0)

        strategy = rb.floor_hp_scaling_strategy(
            ["hit", "std"], native,
            {"hit": self._general_node(100)}, {"hit": self._boss_level(10)},
            100, required_c86=2.0, deep=True,
            code_references=self.SAFE_REFS, standard_boss=standard_boss)
        self.assertEqual(strategy["channel"], "mixed_hp")

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

    def test_only_identity_locked_standard_remains_c86_micro_adjust_only(self):
        standard_native = {
            "verified": True, "absolute_verified": True, "native_hp": 100.0,
            "components": [{"code": "s", "kind": "standard", "native_hp": 100.0}],
        }
        table = {"s": self._general_node(100)}
        got = rb.floor_hp_scaling_strategy(
            ["s"], standard_native, {}, {}, 100, required_c86=1.05,
            deep=True, code_references=self.SAFE_REFS, standard_boss=table)
        self.assertEqual(got["channel"], "standard_dsl")
        locked = {
            "hard": frozenset({"s"}), "soft": frozenset(), "degraded": False,
        }
        got = rb.floor_hp_scaling_strategy(
            ["s"], standard_native, {}, {}, 100, required_c86=1.05,
            deep=False, code_references=locked, standard_boss=table)
        self.assertEqual(got["channel"], "c86")
        self.assertEqual(got["baseline_c86"], 1.05)
        with self.assertRaisesRegex(ValueError, "0.9~1.1"):
            rb.floor_hp_scaling_strategy(
                ["s"], standard_native, {}, {}, 100,
                required_c86=1.1001, deep=False,
                code_references=locked, standard_boss=table)

    def test_general_plan_rejects_mixed_family_and_supports_absolute_fix_hp(self):
        general = self._general_node(100)
        mixed = {"verified": True, "native_hp": 400.0, "components": [
            {"code": "a", "kind": "general", "native_hp": 100.0},
            {"code": "s", "kind": "standard", "native_hp": 300.0}]}
        with self.assertRaisesRegex(ValueError, "混合"):
            rb.general_hp_scale_plan(["a", "s"], mixed, {"a": general},
                {"a": self._boss_level(10)}, 100, target_hp=1200.0, curse_hp=1.0,
                code_references=self.SAFE_REFS)
        pure = {"verified": True, "native_hp": 100.0, "components": [
            {"code": "a", "kind": "general", "native_hp": 100.0}]}
        source = self._boss_level(10, kind="1")
        plan = rb.general_hp_scale_plan(["a"], pure, {"a": general}, {"a": source},
            100, target_hp=1200.0, curse_hp=1.0, code_references=self.SAFE_REFS)
        self.assertEqual({"a": "boss_level.c5"}, plan["destinations"])
        before, after = rb.cells(source), rb.cells(plan["final_leaves"]["a"])
        self.assertEqual("120", after[5])
        self.assertEqual(before[:5] + before[6:], after[:5] + after[6:])

    def test_identity_locked_standard_micro_adjust_window_applies_at_every_depth(self):
        native = {"verified": True, "native_hp": 100.0, "components": [
            {"code": "s", "kind": "standard", "native_hp": 100.0}]}
        # A missing reference closure is identity-locked. Current online policy
        # allows the same bounded c86 window in deep floors too.
        for deep in (False, True):
            got = rb.floor_hp_scaling_strategy(["s"], native, {}, {}, 100,
                required_c86=1.05, deep=deep)
            self.assertEqual("c86", got["channel"])
            self.assertEqual("identity-locked-standard", got["family"])
            self.assertEqual(1.05, got["baseline_c86"])
            with self.assertRaises(ValueError):
                rb.floor_hp_scaling_strategy(["s"], native, {}, {}, 100,
                    required_c86=1.1001, deep=deep)


class TowerHpTargetCase(unittest.TestCase):
    def test_linear_boss_hp_is_default_and_ramp_retains_old_dps_endpoints(self):
        self.assertEqual(rb.target_dps(1, 30), rb.WARMUP_TARGET_DPS)
        self.assertEqual(rb.boss_target_hp(2, 30), 3_000_000_000.0)
        self.assertEqual(rb.boss_target_hp(16, 30), 9_000_000_000.0)
        self.assertEqual(rb.boss_target_hp(30, 30), 15_000_000_000.0)
        for r in range(2, 31):
            self.assertAlmostEqual(
                rb.target_dps(r, 30) * rb.TARGET_BASE_DURATION_S,
                rb.boss_target_hp(r, 30))
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
        # 显式 easy 仍相对 hell 缩放线性 HP profile；显式 --ramp 才恢复旧端点。
        self.assertAlmostEqual(
            rb.configured_target_dps(1, 30, easy0, easyg), 200_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(30, 30, easy0, easyg), 5_000_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(1, 30, easy0, easyg, ramp=True), 200_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(30, 30, easy0, easyg, ramp=True), 7_500_000.0)
        self.assertAlmostEqual(
            rb.configured_target_dps(15, 30, hell0, hellg, 1.15),
            rb.target_dps(15, 30))
        self.assertAlmostEqual(
            rb.configured_target_dps(
                15, 30, hell0, hellg, 1.15, ramp=True),
            rb.target_dps(15, 30, ramp=True) * 1.15)

    def test_deep_hp_anchor_expansion_is_general_c2_scalable(self):
        """深层锚必须能走 general_boss clone + Hit boss_level.c2。"""
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            gb = q.load_table(rb.GENERAL_BOSS)
            gbs = q.load_table(rb.GENERAL_BOSS_STATE)
            bl = q.load_table("master/battle/boss/boss_level.orderedmap")
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertIsNone(rb.deep_hp_anchor_field(25, 30))
        fields = [rb.deep_hp_anchor_field(r, 30) for r in range(26, 31)]
        self.assertEqual(len(set(fields)), 5)
        refs = rb.code_referenced_bosses(gb)
        resolved = []
        for r, field in zip(range(26, 31), fields):
            bosses, _ = rb._zone_pick(field)
            if not bosses:
                self.skipTest(f"effective store lacks current deep anchor: {field}")
            resolved.append((r, field, bosses))
        for r, field, bosses in resolved:
            got = rb.floor_native_hp(bosses, 100, sb)
            self.assertTrue(got["absolute_verified"], (field, got))
            plan = rb.general_hp_scale_plan(
                bosses, got, gb, bl, 100,
                target_hp=rb.target_dps(r, 30) * 900.0, curse_hp=1.0,
                code_references=refs, general_boss_state=gbs)
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
        # 全局 Boss HP 可以是官方 ×1，也可以由显式增强开关切成 ×4；本测试只证明
        # general 与 standard 两条独立通道会逐实例相加，不把环境状态写死进断言。
        self.assertGreater(got["components"][0]["native_hp"], 0)
        self.assertEqual(got["components"][1]["native_hp"], 385_000_000.0)
        self.assertEqual(
            got["native_hp"],
            math.fsum(component["native_hp"] for component in got["components"]),
        )
        self.assertTrue(got["verified"])
        self.assertIn(got["components"][0]["evidence_kind"], {"absolute", "proxy"})
        self.assertEqual(got["components"][1]["evidence_kind"], "absolute")
        self.assertEqual(
            got["absolute_verified"],
            got["components"][0]["evidence_kind"] == "absolute",
        )

    def test_fix_hp_general_boss_uses_its_fixed_curve_without_k_twice(self):
        """BossLevelValues kind=1 已是绝对 Fix HP；K 只用于统一 true_stat 坐标。"""
        try:
            boss_level = q.load_table(rb.BOSS_LEVEL)
            general_boss = q.load_table(rb.GENERAL_BOSS)
            general_boss_state = q.load_table(rb.GENERAL_BOSS_STATE)
            standard_boss = q.load_table(rb.STANDARD_BOSS)
            got = rb.floor_native_hp(
                ["middle_boss_dragon_smr20_raid3"], 89,
                standard_boss, boss_level)
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertTrue(got["verified"], got.get("reason"))
        self.assertTrue(got["absolute_verified"], got.get("reason"))
        self.assertEqual(got["components"][0]["hp_curve_kind"], "fix")
        fixed = rb.cells(boss_level["middle_boss_dragon_smr20_raid3"])
        self.assertEqual(got["native_hp"], float(fixed[5]) * float(fixed[6]))

        plan = rb.general_hp_scale_plan(
            ["middle_boss_dragon_smr20_raid3"], got,
            general_boss, boss_level, 89,
            target_hp=22_500_000_000.0, curse_hp=2.5,
            code_references=BossLevelHpScalingCase.SAFE_REFS,
            general_boss_state=general_boss_state)
        self.assertEqual(plan["hp_columns"], {
            "middle_boss_dragon_smr20_raid3": 5})
        clone_code = "mod_test_fix_hp"
        cloned_general = copy.deepcopy(general_boss)
        cloned_level = copy.deepcopy(boss_level)
        cloned_general[clone_code] = copy.deepcopy(
            general_boss["middle_boss_dragon_smr20_raid3"])
        cloned_level[clone_code] = plan["final_leaves"][
            "middle_boss_dragon_smr20_raid3"]
        readback = rb.floor_native_hp(
            [clone_code], 89, standard_boss, cloned_level)
        self.assertTrue(readback["absolute_verified"], readback.get("reason"))
        self.assertEqual(readback["components"][0]["hp_curve_kind"], "fix")
        self.assertAlmostEqual(
            rb._true_hp_at_c86(readback, 1.0), plan["true_hp"], delta=1.0)
        self.assertAlmostEqual(plan["true_hp"], 56_250_000_000.0, delta=1.0)

        sphere = rb.floor_native_hp(
            ["thunder_sphere"], 100, standard_boss)
        self.assertTrue(sphere["verified"], sphere.get("reason"))
        self.assertEqual(sphere["native_hp"], 125_000_000.0)

    def test_solved_record_keeps_hp_and_time_curses_real(self):
        native = {"native_hp": 385_000_000.0, "verified": True,
                  "components": [{"kind": "standard", "native_hp": 385_000_000.0}]}
        got = rb.solve_floor_hp_record(
            30, 30, native, base_duration_s=900.0, duration_s=180.0,
            curse_hp=2.5, raw_c86=6.5, family="standard")
        self.assertAlmostEqual(got["baseline_true_hp"], 15_000_000_000.0,
                               delta=100_000.0)
        self.assertAlmostEqual(got["true_hp"], 37_500_000_000.0,
                               delta=100_000.0)
        self.assertAlmostEqual(got["realized_dps"] / got["baseline_dps"], 12.5)
        self.assertEqual(got["curse_hp"], 2.5)
        self.assertLess(got["family_scale"], 10.0)

    def test_linear_curve_gate_exempts_only_round_one_and_checks_every_boss_floor(self):
        ok = [{"r": 1, "baseline_dps": 600_000.0,
               "target_dps": 600_000.0, "warmup": True}]
        ok += [{"r": r, "baseline_dps": rb.target_dps(r, 30),
                "target_dps": rb.target_dps(r, 30)} for r in range(2, 31)]
        self.assertEqual(rb.hp_curve_errors(ok, 30), [])
        low = [dict(x) for x in ok]
        low[1]["baseline_dps"] = (
            low[1]["target_dps"] * rb._TARGET_DPS_BAND_RATIOS[0] - 1.0)
        self.assertTrue(any("第2关" in e for e in rb.hp_curve_errors(low, 30)))
        high = [dict(x) for x in ok]
        high[-1]["baseline_dps"] = rb.TARGET_DPS_LAST_BAND[1] + 1.0
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
            {"r": 4, "family": "orochi", "c86": 1.0},
            {"r": 5, "family": "orochi_ex", "c86": 1.0},
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
        bad_orochi = [dict(x) for x in ok]
        bad_orochi[3]["c86"] = 1.0001
        self.assertTrue(any(
            "orochi" in e for e in rb.hp_correction_errors(bad_orochi, 30)))
        bad_orochi_ex = [dict(x) for x in ok]
        bad_orochi_ex[4]["c86"] = 1.0001
        self.assertTrue(any(
            "orochi_ex" in e
            for e in rb.hp_correction_errors(bad_orochi_ex, 30)))
        with self.subTest("identity-locked general shares the existing micro window"):
            locked = ok + [{"r": 6, "family": "identity-locked", "c86": 1.1}]
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


    def test_default_boss_hp_gradient_and_legacy_dps_ramp_have_distinct_endpoints(self):
        self.assertEqual(600_000.0, rb.target_dps(1, 30))
        self.assertEqual(3_000_000_000.0 / 900, rb.target_dps(2, 30))
        self.assertEqual(15_000_000_000.0 / 900, rb.target_dps(30, 30))
        self.assertEqual(600_000.0, rb.target_dps(1, 30, ramp=True))
        self.assertEqual(25_000_000.0, rb.target_dps(30, 30, ramp=True))
        self.assertGreater(rb.target_dps(30, 30), rb.target_dps(2, 30))

    def test_target_curve_gate_exempts_only_warmup_and_checks_every_boss_floor(self):
        ok = [{"r": 1, "baseline_dps": 600_000.0, "warmup": True}]
        ok += [{"r": r, "baseline_dps": rb.target_dps(r, 30),
                "target_dps": rb.target_dps(r, 30)} for r in range(2, 31)]
        self.assertEqual([], rb.hp_curve_errors(ok, 30))
        for index in (1, 29):
            bad = [dict(x) for x in ok]
            bad[index]["baseline_dps"] *= 2
            self.assertTrue(any(f"第{index+1}关" in e for e in rb.hp_curve_errors(bad, 30)))
        self.assertTrue(any("缺少" in e for e in rb.hp_curve_errors(ok[:-1], 30)))


@requires_store
class TaskCDryRunCase(unittest.TestCase):
    """主编排路径回归：纯函数单测不能代替 30 层随机/重抽/克隆整链。"""

    @staticmethod
    def run_build(*extra: str) -> subprocess.CompletedProcess:
        script = Path(rb.__file__).resolve()
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONUTF8="1")
        return subprocess.run(
            [sys.executable, "-m", "wf.tools.rogue.rogue_build", *extra], cwd=repo, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90)

    @staticmethod
    def run_build_with_plan(plan: dict, *extra: str,
                            ignore_high_threat: bool = False,
                            audit_table_mutations: bool = False) -> subprocess.CompletedProcess:
        script_dir = str(Path(__file__).resolve().parents[1])
        argv = [str(Path(rb.__file__).resolve()), *extra]
        driver = (
            "import copy, json, sys\n"
            "from unittest import mock\n"
            f"sys.path.insert(0, {script_dir!r})\n"
            "from wf.tools.rogue import rogue_build as rb\n"
            "from wf.tools.core import quest_lib as q\n"
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
        repo = Path(__file__).resolve().parents[1]
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
                "profile=linear-boss-hp",
                "第1战热身 600,000/s",
                "可归一 boss层 ",
                "未归一层 ",
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
        lo_ratio, hi_ratio = rb._TARGET_DPS_BAND_RATIOS
        by_round_line = {
            int(match.group(1)): line
            for line in out.splitlines()
            if (match := re.match(r"\s+第(\d+)战 ", line))
        }
        for round_no in range(2, 31):
            if "·未归一]" in by_round_line[round_no]:
                continue
            lo = rb.target_dps(round_no, 30) * lo_ratio
            hi = rb.target_dps(round_no, 30) * hi_ratio
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
        for round_no, expected in ((15, "机工神兵"), (29, "无幻之宴")):
            self.assertTrue(
                by_round.get(round_no, "").startswith(expected),
                f"第{round_no}战守门固定位被换掉了:{by_round.get(round_no)!r}")
        # 第30战保留旧 schedule 键只为兼容布局计划；实际 picker 已是安全高难
        # 终局池，终始之龙只是候选之一，不得再把它写成固定成品 Boss。
        self.assertTrue(
            by_round.get(30, "").startswith(("终局Boss", "终始之龙")),
            f"第30战未落入终局候选池:{by_round.get(30)!r}")
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
        self.assertIn("profile=legacy-dps-ramp", out)
        # Standard DSL Health 已可克隆并绝对回读，终始之龙不再是旧版的
        # “未归一保留原生”；ramp 端点现在必须实际命中目标带。
        self.assertIn("基线首尾 DPS 600,000→25,000,000", out)
        self.assertIn("第30战命中目标带", out)
        self.assertNotIn("第30战未归一，保留原生", out)
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
                # dark_matter_80 与正式 portable donor 目录不兼容；继续
                # 使用它会把本测试变成“绕过 ActionDSL/terrain 门禁”。
                # tower_dungeon_area_10_3_2 可由树妖 donor 通过正式
                # 兼容矩阵移植，同时仍会触发本用例关注的属性载体重排。
                "terrain": "tower_dungeon_area_10_3_2",
                "curses": ["元素禁壁"]}}},
            "--rounds", "8", "--seed", "2", "--difficulty", "hell")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertNotIn("round=5 reject=「元素禁壁」", out)
        self.assertIn("@ tower_dungeon_area_10_3_2", out)
        self.assertRegex(out, r"第5战 .*field=mod_rogue_f5")
        self.assertRegex(out, r"第5战 .*元素禁壁")
        self.assertIn("9 关解析链复核通过", out)

    def test_positive_element_resistance_does_not_reject_a_c36_true_pin(self):
        # c36 only prevents some non-positive changes; positive resistance is
        # accepted by the cumulative client's EnemyImpl.isConditionPrevented.
        # Seed 2 also draws an unrelated final Boss with a dynamic trial window;
        # its fail-closed HP gate is covered by StandardBossHpCase separately.
        result = self.run_build_with_plan(
            {"floors": {"5": {
                "boss": "dark_matter_single", "curses": ["元素禁壁"]}}},
            "--rounds", "8", "--seed", "3", "--difficulty", "hell")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertNotIn("钉选 boss dark_matter_single 与属性免疫冲突", out)
        self.assertIn("元素禁壁", out)

    def test_flat_hell_mix_build_has_at_least_one_real_safe_transplant(self):
        # The old seed selects a scripted DamageCheck threshold on floor 19.
        # Do not weaken that gate to exercise the independent transplant path.
        result = self.run_build(
            "--rounds", "30", "--seed", "20260806",
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


class RerollProfileForwardingCase(unittest.TestCase):
    def test_ramp_is_explicitly_forwarded_and_flat_remains_default(self):
        base = dict(rounds=30, enemy_level="ramp", curse=None, mix=True,
                    difficulty="hell", apply=False, strict_target_hp=True)
        flat = rr.build_command(mock.Mock(ramp=False, **base), seed=123)
        ramp = rr.build_command(mock.Mock(ramp=True, **base), seed=123)
        self.assertNotIn("--ramp", flat)
        self.assertIn("--ramp", ramp)
        self.assertIn("--strict-target-hp", flat)
        self.assertEqual(flat[1:3], ["-X", "utf8"])
        self.assertIn("--difficulty", flat)
        self.assertEqual(flat[flat.index("--difficulty") + 1], "hell")

    def test_legacy_unscaled_hp_must_be_explicitly_requested(self):
        args = mock.Mock(
            rounds=30, enemy_level="ramp", curse=None, mix=False,
            difficulty="hell", ramp=False, apply=False,
            strict_target_hp=False,
        )
        self.assertNotIn("--strict-target-hp", rr.build_command(args, seed=123))

    def test_strict_reroll_forwards_machine_and_human_audit_paths(self):
        args = mock.Mock(
            rounds=30, enemy_level="ramp", curse=None, mix=False,
            difficulty="hell", ramp=False, apply=False,
            strict_target_hp=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.json"
            report = Path(tmp) / "report.md"
            command = rr.build_command(
                args, seed=123, audit_json=audit, audit_report=report)
        self.assertEqual(command[command.index("--audit-json") + 1], str(audit))
        self.assertEqual(command[command.index("--audit-report") + 1], str(report))

    def test_gui_build_defaults_to_strict_hp_and_returns_report_paths(self):
        import wf_gui as gui
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(gui, "ROGUE_AUDIT_DIR", Path(tmp)), \
                mock.patch.object(
                    gui, "_rogue_run",
                    return_value={"ok": True, "rc": 0, "log": "ok"}) as run:
            result = gui.rogue_build_apply({
                "rounds": 30, "enemy_level": "ramp",
                "difficulty": "hell", "seed": 20260825,
            }, dry_run=True)
        command = run.call_args.args[1]
        self.assertIn("--strict-target-hp", command)
        self.assertIn("--audit-json", command)
        self.assertIn("--audit-report", command)
        self.assertTrue(result["audit_json"].endswith(".json"))
        self.assertTrue(result["audit_report"].endswith(".md"))
        self.assertEqual(result["verification_scope"], "static_dry_run")
        self.assertIs(result["gameplay_verified"], False)

        html = (Path(__file__).resolve().parents[1] / "wf_gui.html").read_text(
            encoding="utf-8")
        self.assertIn("静态门禁通过 · 未真机验证", html)
        self.assertIn("静态解析链通过 · 未真机验证", html)

    def test_reroll_help_is_utf8_safe_without_environment_override(self):
        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run(
            [sys.executable, "-m", "wf.tools.rogue.rogue_reroll", "--help"],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--ramp", result.stdout)
        self.assertIn("--strict-target-hp", result.stdout)
        self.assertIn("--allow-unscaled-hp", result.stdout)


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
