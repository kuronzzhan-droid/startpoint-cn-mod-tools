"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

class CursePacingAndFallbackCase(unittest.TestCase):
    """高墙节奏软闸与无属性硬通道专场的安全补池。"""

    def test_blood_wall_pacing_blocks_consecutive_and_caps_deep_window(self):
        empty = [set() for _ in range(29)]
        empty[23] = {rb.BLOOD_WALL_NAME}  # 第24层；第25层必须禁连续
        blocked = rb.curse_pacing_blocks(25, 30, empty[:24], "hell")
        self.assertIn("禁止连续", blocked[rb.BLOOD_WALL_NAME])

        empty[24] = {rb.BLOOD_WALL_NAME}  # 第25层
        empty[26] = {rb.BLOOD_WALL_NAME}  # 第27层
        blocked = rb.curse_pacing_blocks(30, 30, empty, "hell")
        self.assertIn("上限2次", blocked[rb.BLOOD_WALL_NAME])
        self.assertEqual(rb.curse_pacing_blocks(30, 30, empty, "abyss"), {})

    def test_random_towers_never_repeat_wall_or_exceed_deep_cap(self):
        import random as _r
        for seed in range(40):
            history = []
            for r in range(1, 31):
                blocks = rb.curse_pacing_blocks(r, 30, history, "hell")
                out = rb.abyss_curses(
                    r, 30, _r.Random(seed * 100 + r), "hell",
                    caps={"boss": False, "element": False},
                    random_forbidden=blocks)
                history.append({c["name"] for c in out["picks"]})
            for left, right in zip(history, history[1:]):
                self.assertFalse(
                    rb.BLOOD_WALL_NAME in left and rb.BLOOD_WALL_NAME in right,
                    (seed, history))
            self.assertLessEqual(
                sum(rb.BLOOD_WALL_NAME in names for names in history[24:]),
                rb.BLOOD_WALL_DEEP_MAX, (seed, history[24:]))

    def test_explicit_pin_can_override_soft_pacing_but_counts_for_later(self):
        import random as _r
        history = [set() for _ in range(8)] + [{rb.BLOOD_WALL_NAME}]
        blocks = rb.curse_pacing_blocks(10, 30, history, "hell")
        out = rb.abyss_curses(
            10, 30, _r.Random(10), "hell",
            caps={"boss": False, "element": False},
            forced={"curses": [rb.BLOOD_WALL_NAME]},
            random_forbidden=blocks)
        self.assertIn(rb.BLOOD_WALL_NAME, {c["name"] for c in out["picks"]})

    def test_soft_fallbacks_use_only_verified_quest_condition_slots(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(5))}
        for name, kind in zip(rb.SOFT_CHANNEL_CURSE_NAMES, ("0", "1", "3")):
            entry = pool[name]
            self.assertTrue(entry["soft_channel_fallback"])
            self.assertEqual(entry["cond"], [(kind, "0.4")])
            self.assertFalse(set(entry) & {
                "damage_resistance", "element_resistance", "stacked_resistance",
                "caster", "gimmick", "hp", "atk", "time"})

    def test_soft_fallbacks_only_enter_no_element_channel_pool(self):
        import random as _r
        seen_carrierless = set()
        seen_element = set()
        for seed in range(160):
            seen_carrierless.update(c["name"] for c in rb.abyss_curses(
                29, 30, _r.Random(seed), "hell",
                caps={"boss": False, "element": False})["picks"])
            seen_element.update(c["name"] for c in rb.abyss_curses(
                29, 30, _r.Random(seed), "hell",
                caps={"boss": True, "element": True, "panel": True})["picks"])
        self.assertTrue(set(rb.SOFT_CHANNEL_CURSE_NAMES) <= seen_carrierless)
        self.assertFalse(set(rb.SOFT_CHANNEL_CURSE_NAMES) & seen_element)

    def test_soft_fallback_combos_are_complete_and_conflict_free(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(0))}
        combos = [combo for combo in rb.CURSE_COMBOS if combo.get("soft_fallback")]
        self.assertEqual({combo["name"] for combo in combos}, {"偏转阵列", "迟滞战线"})
        for combo in combos:
            entries = [pool[name] for name in combo["curses"]]
            self.assertIsNone(rb.curse_conflict(entries), combo["name"])

    def test_element_capable_floor_prefers_an_allowed_element_curse(self):
        import random as _r
        with mock.patch.object(rb, "ELEMENT_CURSE_PREFERENCE_RATE", 1.0):
            for seed in range(40):
                out = rb.abyss_curses(
                    20, 30, _r.Random(seed), "hell",
                    caps={"boss": True, "element": True, "panel": True})
                element_picks = [c for c in out["picks"]
                                 if c["name"] in rb.ELEMENT_CURSE_NAMES]
                self.assertEqual(len(element_picks), 1, (seed, out["picks"]))
                self.assertTrue(all(c.get("element_resistance") for c in element_picks))
                self.assertIsNone(rb.curse_conflict(out["picks"]))

    def test_random_refill_never_stacks_two_element_curse_cards(self):
        import random as _r
        with mock.patch.object(rb, "ELEMENT_CURSE_PREFERENCE_RATE", 0.0):
            for seed in range(240):
                out = rb.abyss_curses(
                    29, 30, _r.Random(seed), "hell",
                    caps={"boss": True, "element": True, "panel": True})
                element_picks = [c for c in out["picks"]
                                 if c["name"] in rb.ELEMENT_CURSE_NAMES]
                self.assertLessEqual(len(element_picks), 1, (seed, out["picks"]))

    def test_forced_multiple_element_cards_keep_all_legal_bans(self):
        import random as _r
        pool = {c["name"]: c for c in rb._curse_pool(2, _r.Random(7))}
        reason = rb.curse_conflict([pool["五相绝域"], pool["元素禁壁"]])
        combined = rb.immunity_axes([pool["五相绝域"], pool["元素禁壁"]])[1]
        if len(combined) == 6:
            self.assertIn("六属性", reason)
        else:
            self.assertIsNone(reason)
        out = rb.abyss_curses(
            29, 30, _r.Random(7), "hell",
            caps={"boss": True, "element": True, "panel": True},
            forced={"curses": ["五相绝域", "元素禁壁"]})
        element_names = {c["name"] for c in out["picks"]
                         if c["name"] in rb.ELEMENT_CURSE_NAMES}
        expected = {"五相绝域"} if len(combined) == 6 else {"五相绝域", "元素禁壁"}
        self.assertEqual(element_names, expected)

    def test_element_preference_never_bypasses_missing_carrier(self):
        import random as _r
        with mock.patch.object(rb, "ELEMENT_CURSE_PREFERENCE_RATE", 1.0):
            for seed in range(40):
                out = rb.abyss_curses(
                    20, 30, _r.Random(seed), "hell",
                    caps={"boss": False, "element": False})
                self.assertFalse(
                    {c["name"] for c in out["picks"]}
                    & set(rb.ELEMENT_CURSE_NAMES), (seed, out["picks"]))

    def test_all_sphere_families_forbid_hp_changing_curses(self):
        import random as _r
        self.assertEqual(
            rb.SPHERE_HP_CURSE_FORBIDDEN_FAMILIES,
            frozenset({"fire_sphere", "water_sphere", "holy_sphere",
                       "wind_sphere", "thunder_sphere"}))
        for family in rb.SPHERE_SPECS:
            profile = rb.resolve_curse_capabilities(
                "special_bundle", family,
                {"boss": False, "element": False, "panel": False})
            self.assertFalse(profile["declared"]["hp_multiplier"])
            self.assertFalse(profile["effective"]["hp_multiplier"])
            self.assertIn(
                "sphere_phase_budget_forbids_hp_multiplier",
                profile["restrictions"])
            for seed in range(64):
                out = rb.abyss_curses(
                    29, 30, _r.Random(seed), "hell",
                    caps={"boss": False, "element": False},
                    capability_profile=profile)
                self.assertAlmostEqual(out["hp"], 1.0, places=12)
                self.assertNotIn("hp_multiplier", out["used_capabilities"])
                self.assertTrue(all(math.isclose(
                    float(c.get("hp", 1.0)), 1.0,
                    rel_tol=0.0, abs_tol=1e-12)
                    for c in out["picks"]), (family, seed, out["picks"]))

    def test_forced_sphere_hp_curses_are_rejected_and_refilled(self):
        import random as _r
        out = rb.abyss_curses(
            29, 30, _r.Random(19), "hell",
            caps={"boss": False, "element": False},
            forced={"curses": ["血肉高墙", "玻璃深渊", "嗜血狂潮"]},
            capability_profile=rb.resolve_curse_capabilities(
                "special_bundle", "thunder_sphere",
                {"boss": False, "element": False, "panel": False}))
        self.assertAlmostEqual(out["hp"], 1.0, places=12)
        self.assertFalse({"血肉高墙", "玻璃深渊", "嗜血狂潮"}
                         & {c["name"] for c in out["picks"]})

    def test_curse_capability_matrix_is_explicit_and_fail_closed(self):
        expected = {
            ("boss_level", "general"),
            ("standard_dsl", "standard"),
            ("mixed_hp", "mixed"),
            ("special_bundle", "orochi"),
            ("special_bundle", "orochi_ex"),
            *(("special_bundle", family)
              for family in rb.SINGLE_BAR_SPECIAL_SPECS),
            *(("special_bundle", family) for family in rb.SPHERE_SPECS),
        }
        self.assertTrue(expected <= set(rb.CURSE_CAPABILITY_MATRIX))
        with self.assertRaisesRegex(
                ValueError, "UNDECLARED_CURSE_CAPABILITY"):
            rb.resolve_curse_capabilities(
                "special_bundle", "future_unreviewed_boss", {})

        general = rb.resolve_curse_capabilities(
            "boss_level", "general",
            {"boss": True, "element": True, "panel": True})
        self.assertTrue(all(general["effective"][axis] for axis in (
            "hp_multiplier", "hard_damage_resistance",
            "hard_element_resistance", "stacked_resistance",
            "field_action", "panel_gimmick")))
        carrierless = rb.resolve_curse_capabilities(
            "boss_level", "general",
            {"boss": False, "element": False, "panel": False})
        self.assertTrue(carrierless["effective"]["hp_multiplier"])
        self.assertTrue(carrierless["effective"]["soft_quest_condition"])
        self.assertFalse(carrierless["effective"]["field_action"])
        self.assertFalse(
            carrierless["effective"]["hard_element_resistance"])

    def test_capability_profile_cannot_enable_an_undeclared_axis(self):
        import random as _r
        profile = rb.resolve_curse_capabilities(
            "special_bundle", "thunder_sphere", {})
        profile["effective"]["hp_multiplier"] = True
        with self.assertRaisesRegex(ValueError, "能力轴非法"):
            rb.abyss_curses(
                29, 30, _r.Random(1), "hell",
                caps={"boss": False, "element": False},
                capability_profile=profile)


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

    def test_formal_mix_gate_rejects_missing_named_positions(self):
        slot = rbb.ActiveBossSlot(
            "0", 1, 0, rbb.BossRef(1, "boss"), rbb.BossRef(1, "boss"))
        requirements = rbb.BossTerrainRequirements(
            layers=(rbb.LayerTerrainRequirements(
                "0", custom_positions=("p0", "p1", "p2")),),
            action_roots=("battle/action/boss",),
            action_closure=("battle/action/boss",),
        )

        def bundle(field, positions, *, portable=True, reason=None):
            return rbb.NativeBossBundle(
                "family", "family", f"variant-{field}", field,
                field, f"zone-{field}", f"terrain/{field}", ("0",),
                (slot,), None, "", "test", portable=portable,
                native_only_reason=reason,
                terrain_caps=(rbb.TerrainLayerCaps(
                    "0", (1,), (0,), (), tuple((name, 1) for name in positions),
                    ()),),
                terrain_requirements=requirements if portable else None,
            )

        source = bundle("source", ("p0", "p1", "p2"))
        missing = bundle("target-missing", ("p0",))
        accepted = bundle("target-ok", ("p0", "p1", "p2"))

        rejected = rb.checked_mix_terrain_compatibility(
            "source", "target-missing",
            {item.source_field: item for item in (source, missing)},
            strict_transplant=False, transplant_safe=())
        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.reason, "CUSTOM_POSITION_MISSING")
        self.assertIn("p1", rejected.detail)

        compatible = rb.checked_mix_terrain_compatibility(
            "source", "target-ok",
            {item.source_field: item for item in (source, accepted)},
            strict_transplant=False, transplant_safe=())
        self.assertTrue(compatible.ok, compatible)

        unaudited = bundle(
            "source-native-only", ("p0", "p1", "p2"), portable=False,
            reason="ACTION_CLOSURE_UNAUDITED")
        closed = rb.checked_mix_terrain_compatibility(
            "source-native-only", "target-ok",
            {item.source_field: item for item in (unaudited, accepted)},
            strict_transplant=False, transplant_safe=())
        self.assertFalse(closed.ok)
        self.assertEqual(closed.reason, "ACTION_CLOSURE_UNAUDITED")

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
