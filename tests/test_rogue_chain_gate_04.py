"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

class BossLevelHpScalingCasePart2(unittest.TestCase):

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

    def test_fix_hp_clone_changes_only_c5_and_preserves_c6_and_source(self):
        source = self._boss_level(10, 2, kind="1")
        clone = rb.clone_fix_boss_level_hp(source, 3.0)
        self.assertEqual(rb.cells(source)[5:7], ["10", "2"])
        self.assertEqual(rb.cells(clone)[5:7], ["30", "2"])
        self.assertEqual(
            rb.cells(source)[:5] + rb.cells(source)[7:],
            rb.cells(clone)[:5] + rb.cells(clone)[7:])
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

            original_expanded = rb.expand_bundle_hp_members(bundle, 100, tables)
            self.assertTrue(original_expanded.ok, original_expanded)
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
            self.assertAlmostEqual(
                result.expanded.total_hp,
                original_expanded.total_hp * 3.0,
                places=5,
            )

            self.assertEqual(tables["orochi"][source_parent], parent_before)
            for table, original in sources_before.items():
                for key, value in original.items():
                    self.assertEqual(tables[table][key], value, (table, key))

        with self.subTest("Orochi unified plan separates baseline and curse final HP"):
            planned_tables = {
                key: copy.deepcopy(value) for key, value in sources_before.items()
            }
            planned_tables["__code_references__"] = {
                "hard": frozenset(), "soft": frozenset(), "degraded": False,
            }
            native = rb.orochi_native_hp_evidence(bundle, 100, planned_tables)
            self.assertTrue(native["verified"], native)
            self.assertTrue(native["absolute_verified"])
            self.assertEqual(len(native["components"]), 1)
            self.assertEqual(
                [component["phase"] for component in native["components"]],
                ["parent"])
            self.assertEqual(len(native["mechanism_components"]), 8)
            self.assertFalse(
                native["mechanism_budget"]["counts_toward_boss_target"])
            baseline_target = float(native["native_hp"]) * 2.0
            final_target = baseline_target * 1.5
            plan = rb.orochi_hp_scale_plan(
                native, planned_tables["boss_level"],
                target_hp=baseline_target, curse_hp=1.5)
            self.assertEqual(plan["channel"], "special_bundle")
            self.assertEqual(plan["family"], "orochi")
            self.assertAlmostEqual(plan["baseline_scale"], 2.0)
            self.assertAlmostEqual(plan["final_scale"], 3.0)
            self.assertEqual(len(plan["baseline_component_hp"]), 1)
            self.assertEqual(plan["mechanism_budget"]["occurrences"], 8)

            result = rb.clone_orochi_parent_bundle(
                bundle, 9, plan["final_scale"], planned_tables)
            self.assertTrue(result.ok, result)
            final_native = rb.orochi_native_hp_evidence(
                result.bundle, 100, planned_tables)
            receipt = rb.build_hp_adaptation_audit(
                2, native, family="orochi", channel="special_bundle",
                destination=plan["destinations"],
                baseline_target_hp=baseline_target,
                final_target_hp=final_target,
                baseline_c86=1.0, final_c86=1.0,
                readback_native=final_native,
                baseline_component_hp=plan["baseline_component_hp"],
            )
            self.assertEqual(len(receipt.components), 1)
            self.assertTrue(receipt.absolute_verified)
            self.assertTrue(receipt.within_tolerance, receipt)
            self.assertAlmostEqual(receipt.baseline_readback_hp,
                                   plan["baseline_true_hp"], places=5)
            self.assertAlmostEqual(receipt.final_readback_hp,
                                   plan["true_hp"], places=5)

            audit_document = rb.build_hp_audit_document(
                seed=20260825, rounds=2, difficulty="hell",
                enemy_level="ramp",
                hp_audits=[{
                    "r": 2, "adapter_audit": receipt,
                    "verified": True, "absolute_verified": True,
                    "target_exempt": False,
                    "quest_hp_multipliers": rb.quest_hp_multiplier_plan(
                        baseline=receipt.baseline_c86,
                        final=receipt.final_c86, has_boss=True),
                    "mechanism_budget": plan["mechanism_budget"],
                }],
                floor_records=[{
                    "r": 2,
                    "row": quest_hp_row(boss=receipt.final_c86),
                    "pick": {
                        "field": bundle.source_field,
                        "play_field": "mod_rogue_f2",
                        "level": 100,
                        "bosses": ["orochi_all_head_single"],
                        "runtime_bosses": [result.parent_code],
                        **thumbnail_pick_fields(bundle.source_field),
                    },
                }],
                chain_reports=[
                    {"round": "1", "ok": True},
                    {"round": "2", "ok": True},
                    {"round": "99", "ok": True},
                ],
            )
            self.assertEqual(rb.verify_hp_audit_document(audit_document), [])
            self.assertIn({
                "match": "exact", "value": "orochi_ex",
                "family": "orochi_ex", "channel": "special_bundle",
                "field_policy": "native_only",
                "closure": (
                    "parent+six_children+three_hp_phases+"
                    "signed_int32_threshold_icon"),
            }, audit_document["selection_policy"]["native_special_only"])

            digest_tamper = copy.deepcopy(audit_document)
            digest_tamper["summary"]["proxy_components"] = 1
            self.assertTrue(any(
                "摘要不一致" in error
                for error in rb.verify_hp_audit_document(digest_tamper)))

            arithmetic_tamper = copy.deepcopy(audit_document)
            arithmetic_tamper["floors"][0]["adapter"]["final_target_hp"] += 1000
            arithmetic_tamper["document_sha256"] = \
                rb.hp_audit_document_digest(arithmetic_tamper)
            arithmetic_errors = rb.verify_hp_audit_document(arithmetic_tamper)
            self.assertTrue(any(
                "组件和不一致" in error or "总误差不能回代" in error
                for error in arithmetic_errors), arithmetic_errors)

            policy_tamper = copy.deepcopy(audit_document)
            policy_tamper["selection_policy"]["boss_exclusions"] = []
            policy_tamper["document_sha256"] = \
                rb.hp_audit_document_digest(policy_tamper)
            self.assertTrue(any(
                "重抽政策不一致" in error
                for error in rb.verify_hp_audit_document(policy_tamper)))

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
            standard_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=True, caster_dirty=False,
                orochi_dirty=False, enemy_watch_available=True,
                standard_dirty=True)
            self.assertLess(
                standard_plan.index(rb.STANDARD_BOSS),
                standard_plan.index(rb.ZONE_T),
                "standard_boss 必须先于引用克隆代号的 zone 保存")
            stale_ex = {
                "orochi_ex": {
                    "mod_rogue_orochi_ex4": {"100": "parent"},
                    "orochi_ex": {"100": "keep"},
                },
                "orochi_ex_head": {
                    "mod_rogue_orochi_ex4_head1": {"100": "head"},
                    "orochi_ex_phase1_left": {"100": "keep"},
                },
                "boss_level": {
                    "mod_rogue_orochi_ex4": "parent",
                    "mod_rogue_orochi_ex4_head1": "head",
                    "orochi_ex": "keep",
                },
            }
            self.assertEqual(set(rb.purge_orochi_ex_clones(stale_ex)), {
                "orochi_ex", "orochi_ex_head", "boss_level",
            })
            self.assertIn("orochi_ex", stale_ex["orochi_ex"])
            self.assertIn("orochi_ex_phase1_left", stale_ex["orochi_ex_head"])
            ex_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=True, caster_dirty=False,
                orochi_dirty=False, enemy_watch_available=True,
                orochi_ex_dirty=True)
            self.assertLess(ex_plan.index(rb.BOSS_LEVEL),
                            ex_plan.index(rb.OROCHI_EX))
            self.assertLess(ex_plan.index(rb.OROCHI_EX_HEAD),
                            ex_plan.index(rb.OROCHI_EX))
            self.assertLess(ex_plan.index(rb.OROCHI_EX),
                            ex_plan.index(rb.ZONE_T))
            import wf_gui as gui
            self.assertIn("master/battle/boss/orochi.orderedmap",
                          gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(rb.OROCHI_EX_HEAD, gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(rb.OROCHI_EX, gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(
                rb.SINGLE_BAR_SPECIAL_SPECS["kraken"]["logical"],
                gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(
                rb.SINGLE_BAR_SPECIAL_SPECS["conductor"]["logical"],
                gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(
                rb.SINGLE_BAR_SPECIAL_SPECS["touyakiren_ceo"]["logical"],
                gui.ROGUE_BATTLE_LOGICALS)
            self.assertIn(rb.STANDARD_BOSS, gui.ROGUE_BATTLE_LOGICALS)
            forged = rb.live_forged_dsl_logicals(
                gb={}, sb={
                    "mod_rogue_standard1": {
                        "80": rb.join(["name", "battle/enemy/boss/official"], False),
                        "100": rb.join([
                            "name", "battle/enemy/boss/mod_rogue/standard_r1_1"
                        ], False),
                    },
                    "official": {"100": rb.join([
                        "name", "battle/enemy/boss/mod_rogue/not_a_clone"
                    ], False)},
                })
            self.assertEqual(forged, [
                "battle/enemy/boss/mod_rogue/standard_r1_1.esdl.amf3.deflate"
            ])
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

    def test_fix_hp_clone_rejects_hit_malformed_or_nonpositive_scaling(self):
        bad_inputs = (
            (self._boss_level(10, 2), 3.0),
            ("1,short", 3.0),
            (self._boss_level(10, 2, kind="1"), 0.0),
            (self._boss_level(10, 2, kind="1"), float("inf")),
        )
        for leaf, scale in bad_inputs:
            with self.assertRaises(ValueError, msg=(leaf, scale)):
                rb.clone_fix_boss_level_hp(leaf, scale)

    def test_ex_final_bosses_have_equal_budgets_despite_different_native_hp(self):
        native = {"verified": True, "absolute_verified": True, "native_hp": 400.0,
                  "components": [{"code": "a", "kind": "general", "native_hp": 100.0},
                                 {"code": "b", "kind": "general", "native_hp": 300.0}]}
        args = (["a", "b"], native,
                {"a": self._general_node(100), "b": self._general_node(100)},
                {"a": self._boss_level(10), "b": self._boss_level(30)}, 100)
        budgets = {"a": 25_000_000_000.0, "b": 25_000_000_000.0}
        plan = rb.general_hp_scale_plan(*args, target_hp=50_000_000_000.0,
            curse_hp=2.5, component_budgets=budgets, code_references=self.SAFE_REFS)
        self.assertEqual(plan["baseline_component_hp"], (25_000_000_000.0,)*2)
        self.assertEqual(plan["final_component_hp"], (62_500_000_000.0,)*2)
        self.assertEqual(plan["baseline_component_target_hp"], (25_000_000_000.0,)*2)
        for invalid in ({"a": 50_000_000_000.0}, {"a": 25e9, "b": 24e9},
                        {"a": -25e9, "b": 75e9}):
            with self.assertRaises(ValueError):
                rb.general_hp_scale_plan(*args, target_hp=50e9, curse_hp=1,
                    component_budgets=invalid, code_references=self.SAFE_REFS)

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

        with self.subTest("watch-partner-only reference has an additive clone closure"):
            partner_only = {
                "hard": frozenset({"a"}), "soft": frozenset(),
                "damage_share": frozenset(),
                "enemy_watch_partner": frozenset({"a"}),
                "boss_alive": frozenset(), "degraded": False,
            }
            closed = rb.general_hp_scale_plan(
                ["a", "b"], native,
                {"a": self._general_node(79, 100),
                 "b": self._general_node(100)},
                {"a": self._boss_level(10), "b": self._boss_level(30)},
                80, target_hp=1_200.0, curse_hp=2.5,
                code_references=partner_only)
            self.assertEqual(closed["channel"], "boss_level")
            self.assertEqual(closed["true_hp"], 3_000.0)

    def test_general_red_trial_scales_c16_from_final_hp_including_curse(self):
        general_node, state_table = self._general_state_node("trial_routine")
        source_state = copy.deepcopy(state_table)
        native = {
            "verified": True, "absolute_verified": True,
            "native_hp": 100.0,
            "components": [{
                "code": "trial_boss", "kind": "general",
                "native_hp": 100.0, "evidence_kind": "absolute",
            }],
        }
        plan = rb.general_hp_scale_plan(
            ["trial_boss"], native, {"trial_boss": general_node},
            {"trial_boss": self._boss_level(10)}, 100,
            target_hp=1_000.0, curse_hp=0.5,
            code_references=self.SAFE_REFS,
            general_boss_state=state_table)

        damage_plan = plan["damage_check_plans"]["trial_boss"]
        self.assertEqual(
            rb.general_damage_check_records(
                damage_plan["baseline_routine_tree"])[0]["percentage"], 2.0)
        self.assertEqual(
            rb.general_damage_check_records(
                damage_plan["final_routine_tree"])[0]["percentage"], 4.0)
        self.assertEqual(state_table, source_state, "规划阶段不得污染官方 routine")

        cloned_states = copy.deepcopy(state_table)
        cloned_general, contract = rb.materialize_general_damage_check_clone(
            copy.deepcopy(general_node), cloned_states, damage_plan,
            clone_code="mod_rogue_boss24")
        selected = rb.cells(cloned_general["100"])
        self.assertEqual(selected[42], "mod_rogue_boss24_state")
        self.assertEqual(
            rb.general_damage_check_records(
                cloned_states["mod_rogue_boss24_state"])[0]["percentage"], 4.0)
        self.assertEqual(contract["occurrence_count"], 1)
        self.assertEqual(contract["hp_curse_multiplier"], 0.5)
        self.assertEqual(
            contract["checks"][0]["source_absolute_threshold_hp"], 20.0)
        self.assertEqual(
            contract["checks"][0]["baseline_absolute_threshold_hp"], 20.0)
        self.assertEqual(
            contract["checks"][0]["final_absolute_threshold_hp"], 20.0)
        self.assertTrue(contract["non_percentage_columns_preserved"])
        self.assertFalse(contract["runtime_simulated"])
        self.assertFalse(contract["gameplay_verified"])

        watch = {"trial_routine": {"keep": "watch"}}
        self.assertEqual(rb.clone_enemy_watch_routine_alias(
            watch, "trial_routine", "mod_rogue_boss24_state"), 1)
        self.assertEqual(
            watch["trial_routine"], watch["mod_rogue_boss24_state"])

    @mock.patch.object(rb, "_CURVES", {"hp": {"hit_hp_boss": {"100": 78.271875}}, "atk": {}})
    def test_general_red_trial_rejects_proxy_origin_hp_curve(self):
        general_node, state_table = self._general_state_node("trial_routine")
        native = {
            "verified": True, "absolute_verified": False,
            "native_hp": 100.0,
            "components": [{
                "code": "trial_boss", "kind": "general",
                "hp_curve_kind": "hit", "native_hp": 100.0,
                "evidence_kind": "proxy",
            }],
        }
        with self.assertRaisesRegex(ValueError, "源 HP 曲线仍是代理"):
            rb.general_hp_scale_plan(
                ["trial_boss"], native, {"trial_boss": general_node},
                {"trial_boss": self._boss_level(10)}, 100,
                target_hp=1_000.0, curse_hp=1.0,
                code_references=self.SAFE_REFS,
                general_boss_state=state_table)

    def test_general_state_write_precedes_general_boss_reference(self):
        write_plan = rb.rogue_battle_write_plan(
            gimmick_dirty=True, caster_dirty=True, orochi_dirty=False,
            enemy_watch_available=True, general_state_dirty=True)
        self.assertLess(write_plan.index(rb.GENERAL_BOSS_STATE),
                        write_plan.index(rb.GENERAL_BOSS))
        self.assertLess(write_plan.index(rb.GENERAL_BOSS),
                        write_plan.index(rb.ZONE_T))

    def test_real_general_damage_check_table_round_trips(self):
        try:
            general_boss = q.load_table(rb.GENERAL_BOSS)
            general_state = q.load_table(rb.GENERAL_BOSS_STATE)
            boss_level = q.load_table(rb.BOSS_LEVEL)
            standard_boss = q.load_table(rb.STANDARD_BOSS)
        except FileNotFoundError:
            self.skipTest("store 不可用")
        refs = rb.code_referenced_bosses(general_boss)
        chosen = None
        for code, node in general_boss.items():
            selected = rb.select_surjective_level(node, 100)
            if selected is None:
                continue
            row = rb.cells(node[str(selected)])
            if len(row) <= 42 or row[42] not in general_state:
                continue
            if not rb.general_damage_check_records(general_state[row[42]]):
                continue
            if rb.identity_clone_locked_boss_reason(
                    [code], code_references=refs):
                continue
            native = rb.floor_native_hp(
                [code], 100, standard_boss, boss_level)
            if (native.get("absolute_verified")
                    and {component.get("kind")
                         for component in native.get("components") or ()}
                    == {"general"}):
                chosen = (str(code), native)
                break
        if chosen is None:
            self.skipTest("当前真实表没有可克隆且绝对 HP 的 General 红条 Boss")
        code, native = chosen
        plan = rb.general_hp_scale_plan(
            [code], native, general_boss, boss_level, 100,
            target_hp=float(native["native_hp"]) * 10.0,
            curse_hp=0.5, code_references=refs,
            general_boss_state=general_state)
        cloned_states = copy.deepcopy(general_state)
        _node, contract = rb.materialize_general_damage_check_clone(
            copy.deepcopy(general_boss[code]), cloned_states,
            plan["damage_check_plans"][code],
            clone_code="mod_rogue_boss98")
        self.assertGreater(contract["occurrence_count"], 0)
        self.assertTrue(contract["absolute_thresholds_preserved"])
        for check in contract["checks"]:
            self.assertAlmostEqual(
                check["source_absolute_threshold_hp"],
                check["baseline_absolute_threshold_hp"], delta=1e-4)
            self.assertAlmostEqual(
                check["source_absolute_threshold_hp"],
                check["final_absolute_threshold_hp"], delta=1e-4)

    @mock.patch.object(rb, "_CURVES", {"hp": {"hit_hp_boss": {"100": 78.271875}}, "atk": {}})
    def test_proxy_hit_plan_rewrites_curve_and_proves_absolute_readback(self):
        def proxy_leaf(c2, c3=1):
            row = rb.cells(self._boss_level(c2, c3))
            row[4] = "hit_hp_correction_client_builtin_unknown"
            return rb.join(row, False)

        native = {
            "verified": True, "absolute_verified": False,
            # These are diagnostic proxy estimates only.  Unequal values pin
            # that target allocation does not inherit their fake ratio.
            "native_hp": 500.0,
            "components": [
                {"code": "a", "kind": "general", "hp_curve_kind": "hit",
                 "evidence_kind": "proxy", "native_hp": 100.0,
                 "boss_occurrence": 1},
                {"code": "a", "kind": "general", "hp_curve_kind": "hit",
                 "evidence_kind": "proxy", "native_hp": 100.0,
                 "boss_occurrence": 2},
                {"code": "b", "kind": "general", "hp_curve_kind": "hit",
                 "evidence_kind": "proxy", "native_hp": 300.0,
                 "boss_occurrence": 3},
            ],
        }
        target = 22_500_000_000.0
        curse = 2.5
        plan = rb.general_hp_scale_plan(
            ["a", "a", "b"], native,
            {"a": self._general_node(100), "b": self._general_node(100)},
            {"a": proxy_leaf(10, 2), "b": proxy_leaf(30)},
            100, target_hp=target, curse_hp=curse,
            code_references=self.SAFE_REFS)

        self.assertEqual(plan["adapter_mode"], "target_authoritative_hit")
        self.assertTrue(plan["absolute_after_adaptation"])
        self.assertEqual(plan["destinations"], {
            "a": "boss_level.c2+c4", "b": "boss_level.c2+c4"})
        self.assertEqual(
            {rb.cells(leaf)[4] for leaf in plan["final_leaves"].values()},
            {rb.AUTHORITATIVE_HIT_HP_CURVE})
        self.assertEqual(
            plan["baseline_component_target_hp"],
            (target / 3, target / 3, target / 3))
        self.assertAlmostEqual(plan["baseline_true_hp"], target, delta=100.0)
        self.assertAlmostEqual(plan["true_hp"], target * curse, delta=100.0)

        cloned_level = {
            "clone_a": plan["final_leaves"]["a"],
            "clone_b": plan["final_leaves"]["b"],
        }
        readback = rb.floor_native_hp(
            ["clone_a", "clone_a", "clone_b"], 100,
            standard_boss={}, boss_level=cloned_level, orochi_ex={})
        self.assertTrue(readback["absolute_verified"], readback.get("reason"))
        self.assertAlmostEqual(
            rb._true_hp_at_c86(readback, 1.0), plan["true_hp"], delta=1.0)

        receipt = rb.build_hp_adaptation_audit(
            8, native, family="general", channel="boss_level",
            destination=plan["destinations"],
            baseline_target_hp=target, final_target_hp=target * curse,
            baseline_c86=1.0, final_c86=1.0,
            readback_native=readback,
            baseline_component_hp=plan["baseline_component_hp"],
            baseline_component_target_hp=plan["baseline_component_target_hp"],
            final_component_target_hp=plan["final_component_target_hp"])
        self.assertTrue(receipt.absolute_verified)
        self.assertEqual(
            {part.source_evidence_kind for part in receipt.components}, {"proxy"})
        self.assertEqual(
            {part.evidence_kind for part in receipt.components}, {"absolute"})
        self.assertTrue(receipt.within_tolerance)

        metrics = {
            "native": native, "hp_channel": "boss_level",
            "absolute_after_adaptation": True,
        }
        self.assertIsNone(rb.strict_hp_candidate_error(metrics))

    def test_proxy_target_adapter_does_not_convert_fix_rows(self):
        native = {
            "verified": True, "absolute_verified": False, "native_hp": 100.0,
            "components": [
                {"code": "fix", "kind": "general", "hp_curve_kind": "fix",
                 "evidence_kind": "proxy", "native_hp": 100.0},
            ],
        }
        with self.assertRaisesRegex(ValueError, "仅支持 Hit"):
            rb.general_hp_scale_plan(
                ["fix"], native, {"fix": self._general_node(100)},
                {"fix": self._boss_level(10, kind="1")}, 100,
                target_hp=1_000.0, curse_hp=1.0,
                code_references=self.SAFE_REFS)

    def test_general_plan_rejects_mixed_standard_family(self):
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

    def test_general_plan_scales_hit_and_fix_through_their_own_columns(self):
        native = {
            "verified": True, "native_hp": 400.0,
            "components": [
                {"code": "hit", "kind": "general", "hp_curve_kind": "hit",
                 "native_hp": 100.0},
                {"code": "fix", "kind": "general", "hp_curve_kind": "fix",
                 "native_hp": 300.0},
            ],
        }
        plan = rb.general_hp_scale_plan(
            ["hit", "fix"], native,
            {"hit": self._general_node(100), "fix": self._general_node(100)},
            {"hit": self._boss_level(10, 2),
             "fix": self._boss_level(30, 10, kind="1")},
            100, target_hp=1_200.0, curse_hp=2.5,
            code_references=self.SAFE_REFS)
        self.assertEqual(plan["hp_columns"], {"hit": 2, "fix": 5})
        self.assertEqual(plan["destinations"], {
            "hit": "boss_level.c2", "fix": "boss_level.c5"})
        self.assertEqual(rb.cells(plan["baseline_leaves"]["hit"])[2], "30")
        self.assertEqual(rb.cells(plan["baseline_leaves"]["fix"])[5:7],
                         ["90", "10"])
        self.assertEqual(rb.cells(plan["final_leaves"]["hit"])[2], "75")
        self.assertEqual(rb.cells(plan["final_leaves"]["fix"])[5:7],
                         ["225", "10"])
        self.assertEqual(plan["baseline_component_hp"], (300.0, 900.0))
        self.assertEqual(plan["final_component_hp"], (750.0, 2250.0))
        self.assertEqual(plan["baseline_true_hp"], 1_200.0)
        self.assertEqual(plan["true_hp"], 3_000.0)

    def test_standard_dsl_plan_scales_each_health_form_and_redecodes(self):
        source_tree = {
            "au": [
                {"d": ["T1", 100]},
                {"d": ["T2"]},
                {"d": ["T1", 200]},
            ],
            "keep": {"value": 7},
        }
        source_before = copy.deepcopy(source_tree)
        source_logical = "battle/enemy/boss/test_standard.esdl.amf3.deflate"
        resources = {
            source_logical: rb.build_standard_enemy_dsl_blob(source_tree),
        }
        standard_boss = {
            "std": {"100": rb.join(
                ["测试 Standard", "battle/enemy/boss/test_standard"], False)},
        }
        native = rb.floor_native_hp(
            ["std"], 100, standard_boss, {},
            standard_resources=resources)
        self.assertTrue(native["absolute_verified"], native.get("reason"))
        self.assertEqual(native["native_hp"], 165.0)
        plan = rb.standard_hp_scale_plan(
            ["std"], native, standard_boss, 100,
            target_hp=330.0, curse_hp=2.5,
            code_references=self.SAFE_REFS, resources=resources)
        self.assertEqual(source_tree, source_before)
        self.assertEqual(plan["channel"], "standard_dsl")
        self.assertEqual(plan["baseline_component_hp"], (110.0, 220.0))
        self.assertEqual(plan["final_component_hp"], (275.0, 550.0))
        self.assertEqual(plan["baseline_true_hp"], 330.0)
        self.assertEqual(plan["true_hp"], 825.0)

        clone_code = "mod_rogue_standard_test"
        resource_base = "battle/enemy/boss/mod_rogue/standard_test"
        final_logical = resource_base + ".esdl.amf3.deflate"
        cloned_table = copy.deepcopy(standard_boss)
        cloned_table[clone_code] = rb.clone_standard_boss_node(
            standard_boss["std"], 100, resource_base)
        readback = rb.floor_native_hp(
            [clone_code], 100, cloned_table, {},
            standard_resources={final_logical: plan["final_blobs"]["std"]})
        self.assertTrue(readback["absolute_verified"], readback.get("reason"))
        self.assertEqual(rb._true_hp_at_c86(readback, 1.0), 825.0)

    def test_standard_strategy_uses_dsl_beyond_the_old_c86_window(self):
        native = {
            "verified": True, "absolute_verified": True, "native_hp": 100.0,
            "components": [
                {"code": "std", "kind": "standard", "native_hp": 100.0},
            ],
        }
        got = rb.floor_hp_scaling_strategy(
            ["std"], native, {}, {}, 100, required_c86=100.0,
            deep=True, code_references=self.SAFE_REFS,
            standard_boss={"std": self._general_node(100)})
        self.assertEqual(got["channel"], "standard_dsl")
        self.assertEqual(got["baseline_c86"], 1.0)
        self.assertEqual(got["baseline_scale"], 100.0)
