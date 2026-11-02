"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

class BossLevelHpScalingCasePart1(unittest.TestCase):

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

    def test_surjectivity_selects_the_first_level_not_below_the_enemy(self):
        node = self._general_node(79, 100)
        self.assertEqual(rb.select_surjective_level(node, 79), 79)
        self.assertEqual(rb.select_surjective_level(node, 80), 100)
        self.assertIsNone(rb.select_surjective_level(node, 101))

    def test_single_bar_special_clone_has_one_auditable_victory_component(self):
        clean_action = ["ActionDsl", ["Block", []]]
        self.assertTrue(rbb.audit_action_identity_closure(
            ["battle/action/test"], "boss_conductor_single",
            lambda _logical: clean_action, enemy_level=100).ok)
        identity_action = [
            "ActionDsl", ["Block", []], "boss_conductor_single"]
        rejected_identity = rbb.audit_action_identity_closure(
            ["battle/action/test"], "boss_conductor_single",
            lambda _logical: identity_action, enemy_level=100)
        self.assertFalse(rejected_identity.ok)
        self.assertIn("parent master id", rejected_identity.detail)

        # Kraken 使用客户端 bundled normal Hit 曲线；这条已由
        # 22 份客户端基线哈希交叉核对后固定，CI 无需携带 APK。
        self.assertAlmostEqual(
            rb.curve_value("hp", "hit_hp_correction_normal", 100),
            31.26519, places=6)

        try:
            catalog = rb.build_native_bundle_catalog(enemy_level=100)
            bundle = next(
                bundle for variants in catalog.bundles.values()
                for bundle in variants
                if rb.special_bundle_family(bundle) == "conductor")
            kraken_bundle = next(
                bundle for variants in catalog.bundles.values()
                for bundle in variants
                if rb.special_bundle_family(bundle) == "kraken")
            gb = q.load_table(rb.GENERAL_BOSS)
            gv = q.load_table(rb.GENERAL_BOSS_VARIABLE)
            sb = q.load_table(rb.STANDARD_BOSS)
            gz = q.load_table(rb.GENERAL_ZAKO)
            general_funnel = q.load_table(rb.GENERAL_FUNNEL)
            standard_funnel = q.load_table(rb.STANDARD_FUNNEL)
            special_tables = {
                family: q.load_table(str(spec["logical"]))
                for family, spec in rb.SINGLE_BAR_SPECIAL_SPECS.items()
            }
            validation = rb.boss_ref_validation_tables(
                standard_boss=sb, general_boss=gb,
                general_boss_variable=gv,
                special_tables=special_tables)

            def spawned_gate(source_kind, code, level):
                return rb.validate_spawned_ref(
                    source_kind, code, level,
                    validation_tables=validation,
                    general_zako=gz,
                    general_funnel=general_funnel,
                    standard_funnel=standard_funnel)

            tables = {
                **special_tables,
                "boss_level": q.load_table(rb.BOSS_LEVEL),
                "kraken_tentacle": q.load_table(rb.KRAKEN_TENTACLE),
                "kraken_funnel_level": q.load_table(rb.KRAKEN_FUNNEL_LEVEL),
                "__code_references__": rb.code_referenced_bosses(gb),
                "__action_loader__": rbb.load_store_action,
                "__spawned_ref_gate__": spawned_gate,
            }
            # The live source store may legitimately contain round-local rows
            # from an already materialized tower.  This unit test verifies a
            # fresh atomic clone and must not inherit those ambient outputs.
            for family, target in (("conductor", "mod_rogue_conductor28"),
                                   ("kraken", "mod_rogue_kraken27")):
                tables[family].pop(target, None)
                tables["boss_level"].pop(target, None)
        except FileNotFoundError:
            self.skipTest("store 不可用")

        source_code = rb.native_bundle_bosses(bundle)[0]
        source_dedicated = copy.deepcopy(
            tables["conductor"][source_code])
        source_level = copy.deepcopy(tables["boss_level"][source_code])
        native = rb.single_bar_special_native_hp_evidence(bundle, 100, tables)
        self.assertTrue(native["verified"], native)
        self.assertTrue(native["absolute_verified"])
        self.assertEqual(len(native["components"]), 1)
        self.assertEqual(native["components"][0]["phase"], "main")
        self.assertEqual(native["components"][0]["special_family"],
                         "conductor")

        plan = rb.single_bar_special_hp_scale_plan(
            native, tables["boss_level"],
            target_hp=float(native["native_hp"]) * 2,
            curse_hp=1.5)
        self.assertAlmostEqual(plan["baseline_scale"], 2.0)
        self.assertAlmostEqual(plan["final_scale"], 3.0)
        result = rb.clone_single_bar_special_bundle(
            bundle, 28, plan["final_scale"], tables)
        self.assertTrue(result.ok, result)
        self.assertEqual(result.parent_code, "mod_rogue_conductor28")
        self.assertEqual(result.bundle.slots[0].single,
                         rbb.BossRef(6, result.parent_code))
        readback = rb.single_bar_special_native_hp_evidence(
            result.bundle, 100, tables)
        self.assertTrue(readback["verified"], readback)
        self.assertAlmostEqual(float(readback["native_hp"]),
                               float(native["native_hp"]) * 3.0, places=4)
        self.assertEqual(tables["conductor"][source_code], source_dedicated)
        self.assertEqual(tables["boss_level"][source_code], source_level)

        kraken_code = rb.native_bundle_bosses(kraken_bundle)[0]
        kraken_source = copy.deepcopy(tables["kraken"][kraken_code])
        kraken_level = copy.deepcopy(tables["boss_level"][kraken_code])
        kraken_native = rb.single_bar_special_native_hp_evidence(
            kraken_bundle, 100, tables)
        self.assertTrue(kraken_native["verified"], kraken_native)
        self.assertEqual(len(kraken_native["components"]), 1)
        kraken_graph = kraken_native["graph"]
        self.assertEqual(len(kraken_graph.auxiliary_refs), 2)
        self.assertEqual(
            kraken_native["components"][0]["evidence"]["auxiliary_entities"],
            list(kraken_graph.auxiliary_refs))
        missing_tentacles = dict(tables, kraken_tentacle={})
        rejected_kraken = rb.single_bar_special_native_hp_evidence(
            kraken_bundle, 100, missing_tentacles)
        self.assertFalse(rejected_kraken["verified"])
        self.assertIn("tentacle dependency", rejected_kraken["detail"])
        kraken_result = rb.clone_single_bar_special_bundle(
            kraken_bundle, 27, 2.0, tables)
        self.assertTrue(kraken_result.ok, kraken_result)
        self.assertEqual(kraken_result.parent_code, "mod_rogue_kraken27")
        kraken_readback = rb.single_bar_special_native_hp_evidence(
            kraken_result.bundle, 100, tables)
        self.assertAlmostEqual(
            float(kraken_readback["native_hp"]),
            float(kraken_native["native_hp"]) * 2.0, places=4)
        self.assertEqual(tables["kraken"][kraken_code], kraken_source)
        self.assertEqual(tables["boss_level"][kraken_code], kraken_level)

        stale = {
            "kraken": {"mod_rogue_kraken2": "clone", "official": "keep"},
            "conductor": {"mod_rogue_conductor3": "clone", "official": "keep"},
            "touyakiren_ceo": {
                "mod_rogue_touyakiren_ceo4": "clone", "official": "keep"},
            "boss_level": {
                "mod_rogue_kraken2": "clone",
                "mod_rogue_conductor3": "clone",
                "mod_rogue_touyakiren_ceo4": "clone",
                "official": "keep",
            },
        }
        self.assertEqual(set(rb.purge_single_bar_special_clones(stale)), {
            "kraken", "conductor", "touyakiren_ceo", "boss_level"})
        self.assertEqual(stale["boss_level"], {"official": "keep"})
        write_plan = rb.rogue_battle_write_plan(
            gimmick_dirty=True, caster_dirty=False, orochi_dirty=False,
            enemy_watch_available=True,
            single_bar_special_dirty=(
                "kraken", "conductor", "touyakiren_ceo"))
        self.assertLess(write_plan.index(rb.BOSS_LEVEL),
                        write_plan.index(
                            rb.SINGLE_BAR_SPECIAL_SPECS["kraken"]["logical"]))
        self.assertLess(write_plan.index(rb.BOSS_LEVEL),
                        write_plan.index(
                            rb.SINGLE_BAR_SPECIAL_SPECS["conductor"]["logical"]))
        self.assertLess(write_plan.index(
            rb.SINGLE_BAR_SPECIAL_SPECS["touyakiren_ceo"]["logical"]),
            write_plan.index(rb.ZONE_T))

    def test_sphere_clones_preserve_proved_phase_damage_budgets(self):
        """All five Sphere families clone every client-proved HP conduit."""

        try:
            catalog = rb.build_native_bundle_catalog(enemy_level=100)
            sphere_tables = {
                family: q.load_table(str(spec["logical"]))
                for family, spec in rb.SPHERE_SPECS.items()
            }
            sphere_tables.update({
                name: q.load_table(logical)
                for name, logical in rb.SPHERE_AUX_LOGICALS.items()
            })
            sphere_tables.update({
                "boss_level": q.load_table(rb.BOSS_LEVEL),
                "__code_references__": rb.code_referenced_bosses(
                    q.load_table(rb.GENERAL_BOSS)),
                "__action_loader__": rbb.load_store_action,
            })
        except FileNotFoundError:
            self.skipTest("store 不可用")

        bundles = {}
        for variants in catalog.bundles.values():
            for bundle in variants:
                family = rb.special_bundle_family(bundle)
                if family in rb.SPHERE_SPECS:
                    bundles.setdefault(family, bundle)
        self.assertEqual(set(bundles), set(rb.SPHERE_SPECS))

        expected_components = {
            "water_sphere": [
                "phase[1].crystal[1]", "phase[1].crystal[2]", "main"],
            "holy_sphere": [
                "phase[1].crystal[1]", "phase[1].crystal[2]", "main"],
            "wind_sphere": ["main"],
            "thunder_sphere": ["main"],
            "fire_sphere": [
                "phase[1].crystal[1]", "phase[1].crystal[2]",
                "phase[1].crystal[3]", "main"],
        }
        expected_phase_contracts = {
            "water_sphere": (
                ["phase[3].micronucleus"], ["capped_child_hp"], [4], [4]),
            "holy_sphere": (
                ["phase[3].micronucleus"], ["capped_child_hp"], [5], [5]),
            "wind_sphere": (
                ["phase[3].damage_conduits"], ["capped_child_hp"], [3], [4]),
            "thunder_sphere": (
                ["phase[2].micronucleus", "phase[4].crystal"],
                ["capped_child_hp", "capped_child_hp"], [3, 2], [3, 3]),
            "fire_sphere": (
                ["phase[4].micronucleus"], ["raw_hit_overdamage"],
                [None], [8]),
        }
        native_by_family = {}
        for family, bundle in bundles.items():
            with self.subTest(native_family=family):
                native = rb.sphere_native_hp_evidence(
                    bundle, 100, sphere_tables)
                self.assertTrue(native["verified"], native)
                self.assertTrue(native["absolute_verified"])
                self.assertEqual(
                    [item["phase"] for item in native["components"]],
                    expected_components[family])
                native_by_family[family] = native
                graph = native["graph"]
                self.assertTrue(all(
                    item.native_hp is not None for item in graph.auxiliaries))
                self.assertTrue(graph.behavior_verified)
                self.assertIsNotNone(graph.lifecycle)
                self.assertTrue(graph.lifecycle.static_verified)
                self.assertFalse(graph.lifecycle.runtime_simulated)
                self.assertFalse(graph.lifecycle.gameplay_verified)
                self.assertEqual(
                    [step.source_phase for step in graph.lifecycle.steps],
                    [1, 2, 3, 4])
                self.assertEqual(
                    [step.target_phase for step in graph.lifecycle.steps],
                    [2, 3, 4, None])
                self.assertTrue(all(
                    step.verified for step in graph.lifecycle.steps))
                phases, models, completions, occurrences = (
                    expected_phase_contracts[family])
                self.assertEqual(
                    [budget.phase for budget in graph.phase_budgets], phases)
                self.assertEqual(
                    [budget.budget_model for budget in graph.phase_budgets],
                    models)
                self.assertEqual(
                    [budget.completion_count for budget in graph.phase_budgets],
                    completions)
                self.assertEqual(
                    [budget.entity_occurrence_count
                     for budget in graph.phase_budgets], occurrences)
                if family == "thunder_sphere":
                    self.assertEqual(
                        [step.trigger for step in graph.lifecycle.steps],
                        ["parent_hp_threshold", "child_damage_threshold",
                         "parent_hp_threshold", "child_damage_threshold"])
                    self.assertEqual(
                        graph.lifecycle.steps[1].expected_entities, 3)
                    self.assertEqual(
                        graph.lifecycle.steps[1].expected_completion_count, 3)
                    self.assertEqual(
                        graph.lifecycle.steps[1].next_state_entry,
                        "getInitialStateByNextPhase(3)")
                    self.assertEqual(
                        graph.lifecycle.steps[3].expected_entities, 3)
                    self.assertEqual(
                        graph.lifecycle.steps[3].expected_completion_count, 2)
                    self.assertEqual(
                        graph.lifecycle.steps[3].next_state_entry,
                        "Sphere.enterDeadState")
                    self.assertAlmostEqual(
                        graph.phase_budgets[0].required_damage_hp, 15_000_000)
                    self.assertAlmostEqual(
                        graph.phase_budgets[0].available_damage_hp, 15_000_000)
                    self.assertAlmostEqual(
                        graph.phase_budgets[1].required_damage_hp, 75_000_000)
                    self.assertAlmostEqual(
                        graph.phase_budgets[1].available_damage_hp, 112_500_000)
                elif family == "fire_sphere":
                    budget = graph.phase_budgets[0]
                    self.assertTrue(budget.overdamage)
                    self.assertEqual(budget.occurrences_per_entity, 2)
                    self.assertLess(budget.coverage_ratio, 1.0)

        thunder_contracts = rb.SPHERE_SPECS["thunder_sphere"][
            "lifecycle_contracts"]
        try:
            rb.SPHERE_SPECS["thunder_sphere"]["lifecycle_contracts"] = (
                thunder_contracts[:-1])
            lifecycle_broken = rb.inspect_sphere_bundle(
                bundles["thunder_sphere"], 100, sphere_tables)
        finally:
            rb.SPHERE_SPECS["thunder_sphere"]["lifecycle_contracts"] = (
                thunder_contracts)
        self.assertFalse(lifecycle_broken.ok)
        self.assertEqual(
            lifecycle_broken.reason, "SPECIAL_PHASE_BEHAVIOR_UNSAFE")
        self.assertIn("lifecycle edge count drift", lifecycle_broken.detail)

        family_rounds = {
            "water_sphere": 44, "holy_sphere": 45,
            "wind_sphere": 46, "fire_sphere": 47,
        }
        expected_parent_columns = {
            "water_sphere": {298},
            "holy_sphere": {317},
            "wind_sphere": {329, 330, 331, 337},
            "fire_sphere": {376, 377, 378, 379},
        }
        expected_touched = {
            "water_sphere": {"boss_level", "water_sphere"},
            "holy_sphere": {"boss_level", "holy_sphere"},
            "wind_sphere": {
                "boss_level", "wind_sphere_micronucleus", "wind_sphere"},
            "fire_sphere": {
                "boss_level", "fire_sphere_phase4_micronucleus",
                "fire_sphere"},
        }
        family_results = {}
        for family, round_no in family_rounds.items():
            with self.subTest(clone_family=family):
                native = native_by_family[family]
                graph = native["graph"]
                source_code = graph.parent_ref.code
                source_parent = copy.deepcopy(
                    sphere_tables[family][source_code])
                source_level = copy.deepcopy(
                    sphere_tables["boss_level"][source_code])
                source_auxiliary_leaves = {
                    (item.source_table, item.entity_id): copy.deepcopy(
                        sphere_tables[item.source_table][item.entity_id])
                    for item in graph.auxiliaries
                    if item.source_table in rb.SPHERE_AUX_LOGICALS
                }
                baseline_target = float(native["native_hp"]) * 2.0
                final_target = baseline_target * 1.25
                plan = rb.sphere_hp_scale_plan(
                    native, sphere_tables["boss_level"],
                    target_hp=baseline_target, curse_hp=1.25)
                result = rb.clone_sphere_bundle(
                    bundles[family], round_no, plan["final_scale"],
                    sphere_tables)
                self.assertTrue(result.ok, result)
                self.assertEqual(set(result.touched_tables),
                                 expected_touched[family])
                self.assertEqual(sphere_tables[family][source_code],
                                 source_parent)
                self.assertEqual(sphere_tables["boss_level"][source_code],
                                 source_level)
                for (table_name, entity_id), leaf in (
                        source_auxiliary_leaves.items()):
                    self.assertEqual(
                        sphere_tables[table_name][entity_id], leaf,
                        (family, table_name, entity_id))

                target_parent_row = rb.cells(
                    sphere_tables[family][result.parent_code][
                        str(graph.selected_level)])
                source_parent_row = rb.cells(
                    source_parent[str(graph.selected_level)])
                changed_columns = {
                    index for index, (before, after) in enumerate(
                        zip(source_parent_row, target_parent_row))
                    if before != after}
                self.assertEqual(
                    changed_columns, expected_parent_columns[family])

                readback = rb.sphere_native_hp_evidence(
                    result.bundle, 100, sphere_tables)
                self.assertTrue(readback["verified"], readback)
                self.assertTrue(readback["behavior_verified"])
                self.assertAlmostEqual(
                    float(readback["native_hp"]), final_target, delta=1.0)
                target_graph = readback["graph"]
                scalable_phases = {
                    str(group["phase"])
                    for group in (
                        *(rb.SPHERE_SPECS[family].get("embedded") or ()),
                        *(rb.SPHERE_SPECS[family].get("aux_groups") or ()))
                    if group.get("scale_with_parent")
                }
                for source_aux, target_aux in zip(
                        graph.auxiliaries, target_graph.auxiliaries):
                    expected_hp = float(source_aux.native_hp) * (
                        plan["final_scale"]
                        if source_aux.phase in scalable_phases else 1.0)
                    self.assertAlmostEqual(
                        float(target_aux.native_hp), expected_hp,
                        delta=max(
                            rb.HP_TARGET_ABS_TOLERANCE,
                            expected_hp * rb.HP_TARGET_REL_TOLERANCE))
                    if source_aux.phase in scalable_phases:
                        self.assertNotEqual(
                            target_aux.level_code, source_aux.level_code)
                    else:
                        self.assertEqual(
                            target_aux.level_code, source_aux.level_code)
                for source_budget, target_budget in zip(
                        graph.phase_budgets, target_graph.phase_budgets):
                    self.assertEqual(source_budget.budget_model,
                                     target_budget.budget_model)
                    self.assertEqual(source_budget.entity_occurrence_count,
                                     target_budget.entity_occurrence_count)
                    self.assertEqual(source_budget.completion_count,
                                     target_budget.completion_count)
                    self.assertAlmostEqual(source_budget.coverage_ratio,
                                           target_budget.coverage_ratio,
                                           places=6)
                family_results[family] = (result, readback, plan)

        fire_result, fire_readback, fire_plan = family_results["fire_sphere"]
        fire_native = native_by_family["fire_sphere"]
        fire_baseline_target = float(fire_native["native_hp"]) * 2.0
        fire_final_target = fire_baseline_target * 1.25
        # The clone loop above deliberately exercises arbitrary adapter scale.
        # A strict tower receipt must still model Sphere as curse_hp=1, so the
        # already-scaled readback is the curse-free base/final target here.
        fire_receipt = rb.build_hp_adaptation_audit(
            2, fire_native, family="fire_sphere", channel="special_bundle",
            destination=fire_plan["destinations"],
            baseline_target_hp=fire_final_target,
            final_target_hp=fire_final_target,
            baseline_c86=1.0, final_c86=1.0,
            readback_native=fire_readback,
            baseline_component_hp=fire_plan["final_component_hp"],
            baseline_component_target_hp=(
                fire_plan["final_component_target_hp"]),
            final_component_target_hp=fire_plan["final_component_target_hp"])
        fire_document = rb.build_hp_audit_document(
            seed=20260825, rounds=2, difficulty="hell", enemy_level="ramp",
            hp_audits=[{
                "r": 2, "adapter_audit": fire_receipt,
                "verified": True, "absolute_verified": True,
                "target_exempt": False,
                "quest_hp_multipliers": rb.quest_hp_multiplier_plan(
                    baseline=fire_receipt.baseline_c86,
                    final=fire_receipt.final_c86, has_boss=True),
                "phase_behavior": {
                    "verified": True,
                    "static_verified": True,
                    "runtime_simulated": False,
                    "gameplay_verified": False,
                    "source": copy.deepcopy(fire_native["phase_budgets"]),
                    "final_readback": copy.deepcopy(
                        fire_readback["phase_budgets"]),
                    "source_lifecycle": copy.deepcopy(
                        fire_native["phase_lifecycle"]),
                    "final_lifecycle": copy.deepcopy(
                        fire_readback["phase_lifecycle"]),
                },
            }],
            floor_records=[{
                "r": 2,
                "row": quest_hp_row(boss=fire_receipt.final_c86),
                "pick": {
                    "field": bundles["fire_sphere"].source_field,
                    "play_field": "mod_rogue_f2", "level": 100,
                    "bosses": [fire_native["graph"].parent_ref.code],
                    "runtime_bosses": [fire_result.parent_code],
                    **thumbnail_pick_fields(bundles["fire_sphere"].source_field),
                },
            }],
            chain_reports=[
                {"round": "1", "ok": True},
                {"round": "2", "ok": True},
                {"round": "99", "ok": True},
            ])
        self.assertEqual(rb.verify_hp_audit_document(fire_document), [])
        fire_tampered = copy.deepcopy(fire_document)
        fire_tampered["floors"][0]["adapter"]["phase_behavior"][
            "final_readback"][0]["entity_occurrence_count"] = 4
        fire_tampered["document_sha256"] = rb.hp_audit_document_digest(
            fire_tampered)
        self.assertTrue(any(
            "实际出现次数漂移" in error
            for error in rb.verify_hp_audit_document(fire_tampered)))

        bundle = bundles["thunder_sphere"]
        native = native_by_family["thunder_sphere"]
        graph = native["graph"]
        source_code = graph.parent_ref.code
        source_parent = copy.deepcopy(sphere_tables["thunder_sphere"][source_code])
        source_level = copy.deepcopy(sphere_tables["boss_level"][source_code])
        source_auxiliaries = {
            name: copy.deepcopy(sphere_tables[name])
            for name in (
                "thunder_sphere_micronucleus",
                "thunder_sphere_phase3_crystal",
                "thunder_sphere_phase4_crystal",
            )
        }

        # Recreate the exact 1.4.92 parent-only bug in memory.  Absolute parent
        # HP still reads, but phase 2 has only 15m of a required 411.43m budget.
        broken = copy.deepcopy(sphere_tables)
        broken_scale = 3_428_571_428.5714 / 125_000_000.0
        broken_code = "mod_rogue_thunder_sphere98"
        broken["thunder_sphere"][broken_code] = copy.deepcopy(source_parent)
        broken["boss_level"][broken_code], _column = (
            rb.clone_general_boss_level_hp(source_level, broken_scale))
        broken_ref = rbb.BossRef(12, broken_code)
        broken_bundle = replace(bundle, slots=tuple(
            replace(
                slot,
                single=(broken_ref if slot.single == graph.parent_ref
                        else slot.single),
                multi=(broken_ref if slot.multi == graph.parent_ref
                       else slot.multi))
            for slot in bundle.slots))
        broken_evidence = rb.sphere_native_hp_evidence(
            broken_bundle, 100, broken)
        self.assertFalse(broken_evidence["verified"])
        self.assertEqual(
            broken_evidence["graph"].reason, "SPECIAL_PHASE_BEHAVIOR_UNSAFE")
        broken_phase2 = broken_evidence["graph"].phase_budgets[0]
        self.assertAlmostEqual(
            broken_phase2.required_damage_hp, 411_428_571.428568, places=3)
        self.assertEqual(broken_phase2.available_damage_hp, 15_000_000)
        self.assertAlmostEqual(broken_phase2.coverage_ratio, 0.0364583333333)

        baseline_target = float(native["native_hp"]) * 2.0
        final_target = baseline_target * 1.25
        plan = rb.sphere_hp_scale_plan(
            native, sphere_tables["boss_level"],
            target_hp=baseline_target, curse_hp=1.25)
        self.assertTrue(plan["behavior_verified"])
        self.assertAlmostEqual(plan["baseline_true_hp"], baseline_target)
        self.assertAlmostEqual(plan["true_hp"], final_target)
        self.assertEqual(plan["final_scale"], 2.5)

        result = rb.clone_sphere_bundle(
            bundle, 43, plan["final_scale"], sphere_tables)
        self.assertTrue(result.ok, result)
        self.assertEqual(result.parent_code, "mod_rogue_thunder_sphere43")
        self.assertEqual(sphere_tables["thunder_sphere"][source_code], source_parent)
        self.assertEqual(sphere_tables["boss_level"][source_code], source_level)
        for name, snapshot in source_auxiliaries.items():
            for key, leaf in snapshot.items():
                self.assertEqual(sphere_tables[name][key], leaf, (name, key))

        source_parent_row = rb.cells(source_parent["100"])
        target_parent_row = rb.cells(
            sphere_tables["thunder_sphere"][result.parent_code]["100"])
        changed_columns = {
            index for index, (before, after) in enumerate(
                zip(source_parent_row, target_parent_row)) if before != after}
        self.assertEqual(changed_columns, {123, 124, 125, 217, 218, 219})

        cloned_entity_ids = []
        cloned_level_codes = []
        for group_ordinal, group in enumerate(
                rb.SPHERE_SPECS["thunder_sphere"]["aux_groups"], start=1):
            for entity_ordinal, parent_column in enumerate(
                    group["id_columns"], start=1):
                if not group.get("scale_with_parent"):
                    self.assertEqual(
                        target_parent_row[parent_column],
                        source_parent_row[parent_column])
                    continue
                target_entity = rb._sphere_aux_clone_id(
                    "thunder_sphere", 43, group_ordinal, entity_ordinal)
                target_level = rb._sphere_child_clone_code(
                    "thunder_sphere", 43, group_ordinal, entity_ordinal)
                self.assertEqual(target_parent_row[parent_column], target_entity)
                child_row = rb.cells(sphere_tables[group["table"]][target_entity])
                self.assertEqual(child_row[group["level_column"]], target_level)
                source_entity = source_parent_row[parent_column]
                source_child_row = rb.cells(
                    source_auxiliaries[group["table"]][source_entity])
                source_child_hp = rb.floor_native_hp(
                    [source_child_row[group["level_column"]]], 100,
                    standard_boss={}, boss_level=sphere_tables["boss_level"],
                    orochi_ex={})["native_hp"]
                target_child_hp = rb.floor_native_hp(
                    [target_level], 100, standard_boss={},
                    boss_level=sphere_tables["boss_level"],
                    orochi_ex={})["native_hp"]
                self.assertAlmostEqual(
                    target_child_hp, source_child_hp * plan["final_scale"],
                    delta=1.0)
                cloned_entity_ids.append((group["table"], target_entity))
                cloned_level_codes.append(target_level)

        readback = rb.sphere_native_hp_evidence(
            result.bundle, 100, sphere_tables)
        self.assertTrue(readback["verified"], readback)
        self.assertTrue(readback["behavior_verified"])
        self.assertEqual(
            [budget.completion_count
             for budget in readback["graph"].phase_budgets], [3, 2])
        for source_budget, final_budget in zip(
                graph.phase_budgets, readback["graph"].phase_budgets):
            self.assertAlmostEqual(
                final_budget.coverage_ratio, source_budget.coverage_ratio,
                places=6)
        receipt = rb.build_hp_adaptation_audit(
            2, native, family="thunder_sphere", channel="special_bundle",
            destination=plan["destinations"],
            # Adapter arithmetic above may scale by any factor, but Sphere is
            # forbidden from receiving an HP curse in a strict tower receipt.
            baseline_target_hp=final_target,
            final_target_hp=final_target,
            baseline_c86=1.0, final_c86=1.0,
            readback_native=readback,
            baseline_component_hp=plan["final_component_hp"],
            baseline_component_target_hp=plan["final_component_target_hp"],
            final_component_target_hp=plan["final_component_target_hp"])
        self.assertTrue(receipt.absolute_verified)
        self.assertTrue(receipt.within_tolerance, receipt)

        phase_behavior = {
            "verified": True,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
            "source": copy.deepcopy(native["phase_budgets"]),
            "final_readback": copy.deepcopy(readback["phase_budgets"]),
            "source_lifecycle": copy.deepcopy(native["phase_lifecycle"]),
            "final_lifecycle": copy.deepcopy(readback["phase_lifecycle"]),
        }
        audit_document = rb.build_hp_audit_document(
            seed=20260825, rounds=2, difficulty="hell", enemy_level="ramp",
            hp_audits=[{
                "r": 2, "adapter_audit": receipt,
                "verified": True, "absolute_verified": True,
                "target_exempt": False, "phase_behavior": phase_behavior,
                "quest_hp_multipliers": rb.quest_hp_multiplier_plan(
                    baseline=receipt.baseline_c86,
                    final=receipt.final_c86, has_boss=True),
            }],
            floor_records=[{
                "r": 2,
                "row": quest_hp_row(boss=receipt.final_c86),
                "pick": {
                    "field": bundle.source_field,
                    "play_field": "mod_rogue_f2", "level": 100,
                    "bosses": [source_code],
                    "runtime_bosses": [result.parent_code],
                    **thumbnail_pick_fields(bundle.source_field),
                },
            }],
            chain_reports=[
                {"round": "1", "ok": True},
                {"round": "2", "ok": True},
                {"round": "99", "ok": True},
            ])
        self.assertEqual(rb.verify_hp_audit_document(audit_document), [])
        self.assertTrue(
            audit_document["floors"][0]["adapter"]
            ["phase_behavior"]["verified"])
        tampered = copy.deepcopy(audit_document)
        tampered_budget = tampered["floors"][0]["adapter"][
            "phase_behavior"]["final_readback"][0]
        tampered_budget["available_damage_hp"] = 15_000_000.0
        tampered_budget["coverage_ratio"] = (
            tampered_budget["available_damage_hp"]
            / tampered_budget["required_damage_hp"])
        tampered["document_sha256"] = rb.hp_audit_document_digest(tampered)
        tamper_errors = rb.verify_hp_audit_document(tampered)
        self.assertTrue(any(
            "子体未与父体同比伸缩" in error
            or "最终可传递伤害不足" in error
            for error in tamper_errors), tamper_errors)
        lifecycle_tampered = copy.deepcopy(audit_document)
        lifecycle_tampered["floors"][0]["adapter"]["phase_behavior"][
            "final_lifecycle"]["steps"][1]["expected_completion_count"] = 2
        lifecycle_tampered["document_sha256"] = (
            rb.hp_audit_document_digest(lifecycle_tampered))
        lifecycle_errors = rb.verify_hp_audit_document(lifecycle_tampered)
        self.assertTrue(any(
            "静态推进契约漂移" in error
            or "子体预算计数不闭合" in error
            for error in lifecycle_errors), lifecycle_errors)

        gameplay_tampered = copy.deepcopy(audit_document)
        gameplay_tampered["floors"][0]["adapter"]["phase_behavior"][
            "gameplay_verified"] = True
        gameplay_tampered["document_sha256"] = (
            rb.hp_audit_document_digest(gameplay_tampered))
        self.assertTrue(any(
            "不得把离线审计标成真机通过" in error
            for error in rb.verify_hp_audit_document(gameplay_tampered)))

        interrupted = copy.deepcopy(sphere_tables)
        interrupted["thunder_sphere"].pop(result.parent_code)
        interrupted_touched = rb.purge_sphere_clones(interrupted)
        self.assertTrue({
            "boss_level", "thunder_sphere_micronucleus",
            "thunder_sphere_phase4_crystal",
        }.issubset(set(interrupted_touched)))
        for table_name, entity_id in cloned_entity_ids:
            self.assertNotIn(entity_id, interrupted[table_name])
        for level_code in cloned_level_codes:
            self.assertNotIn(level_code, interrupted["boss_level"])

        touched = rb.purge_sphere_clones(sphere_tables)
        self.assertTrue({
            "boss_level", "thunder_sphere", "thunder_sphere_micronucleus",
            "thunder_sphere_phase4_crystal",
        }.issubset(set(touched)))
        self.assertNotIn(result.parent_code, sphere_tables["thunder_sphere"])
        self.assertNotIn(result.parent_code, sphere_tables["boss_level"])
        for table_name, entity_id in cloned_entity_ids:
            self.assertNotIn(entity_id, sphere_tables[table_name])
        for level_code in cloned_level_codes:
            self.assertNotIn(level_code, sphere_tables["boss_level"])
        for family, (family_result, _readback, _plan) in (
                family_results.items()):
            self.assertNotIn(family_result.parent_code, sphere_tables[family])
            self.assertNotIn(
                family_result.parent_code, sphere_tables["boss_level"])

        write_plan = rb.rogue_battle_write_plan(
            gimmick_dirty=True, caster_dirty=False, orochi_dirty=False,
            enemy_watch_available=True, sphere_dirty=("thunder_sphere",))
        parent_logical = rb.SPHERE_SPECS["thunder_sphere"]["logical"]
        for table_name in (
                "thunder_sphere_micronucleus",
                "thunder_sphere_phase4_crystal"):
            auxiliary_logical = rb.SPHERE_AUX_LOGICALS[table_name]
            self.assertLess(write_plan.index(rb.BOSS_LEVEL),
                            write_plan.index(auxiliary_logical))
            self.assertLess(write_plan.index(auxiliary_logical),
                            write_plan.index(parent_logical))
        self.assertNotIn(
            rb.SPHERE_AUX_LOGICALS["thunder_sphere_phase3_crystal"],
            write_plan)
        for family in ("water_sphere", "holy_sphere"):
            shared_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=True, caster_dirty=False, orochi_dirty=False,
                enemy_watch_available=True, sphere_dirty=(family,))
            self.assertLess(
                shared_plan.index(rb.BOSS_LEVEL),
                shared_plan.index(rb.SPHERE_SPECS[family]["logical"]))
            self.assertNotIn(
                rb.SPHERE_AUX_LOGICALS["water_sphere_micronucleus"],
                shared_plan)
        for family, auxiliary_name in (
                ("wind_sphere", "wind_sphere_micronucleus"),
                ("fire_sphere", "fire_sphere_phase4_micronucleus")):
            conduit_plan = rb.rogue_battle_write_plan(
                gimmick_dirty=True, caster_dirty=False, orochi_dirty=False,
                enemy_watch_available=True, sphere_dirty=(family,))
            auxiliary_logical = rb.SPHERE_AUX_LOGICALS[auxiliary_name]
            family_parent_logical = rb.SPHERE_SPECS[family]["logical"]
            self.assertLess(conduit_plan.index(rb.BOSS_LEVEL),
                            conduit_plan.index(auxiliary_logical))
            self.assertLess(conduit_plan.index(auxiliary_logical),
                            conduit_plan.index(family_parent_logical))
        self.assertLess(write_plan.index(parent_logical),
                        write_plan.index(rb.ZONE_T))
        import wf_gui as gui
        for spec in rb.SPHERE_SPECS.values():
            self.assertIn(str(spec["logical"]), gui.ROGUE_BATTLE_LOGICALS)

    def test_sphere_native_action_identity_audit_is_recursive_and_fail_closed(self):
        actions = {
            "battle/action/root": ["ActionDsl", "battle/action/child"],
            "battle/action/child": ["Block", "water_sphere_single"],
        }
        rejected = rb.audit_native_action_identity(
            ("battle/action/root",), "water_sphere_single", actions.__getitem__)
        self.assertFalse(rejected.ok)
        self.assertIn("parent master id", rejected.detail)
        actions["battle/action/child"] = ["Block", "unrelated"]
        accepted = rb.audit_native_action_identity(
            ("battle/action/root",), "water_sphere_single", actions.__getitem__)
        self.assertTrue(accepted.ok, accepted)
        missing = rb.audit_native_action_identity(
            ("battle/action/missing",), "water_sphere_single", actions.__getitem__)
        self.assertFalse(missing.ok)

    def test_hit_hp_clone_changes_only_c2_and_preserves_the_source(self):
        source = self._boss_level(10, 2)
        clone = rb.clone_hit_boss_level_c2(source, 3.0)
        self.assertEqual(rb.cells(source)[2:5], ["10", "2", "hit_hp_boss"])
        self.assertEqual(rb.cells(clone)[2:5], ["30", "2", "hit_hp_boss"])
        self.assertNotEqual(source, clone)
