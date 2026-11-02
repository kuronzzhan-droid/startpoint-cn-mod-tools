from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from wf.tools.rogue import rogue_canary as canary


class AdapterCanaryCase(unittest.TestCase):
    @staticmethod
    def general_contract(*, live: bool = False) -> dict:
        source_hp, baseline_hp, final_hp = 100.0, 200.0, 170.0
        checks = ([{
            "occurrence": 1,
            "source_percentage": 10.0,
            "baseline_percentage": 5.0,
            "final_percentage": 10.0 / 1.7,
            "source_absolute_threshold_hp": 10.0,
            "baseline_absolute_threshold_hp": 10.0,
            "final_absolute_threshold_hp": 10.0,
        }] if live else [])
        return {
            "schema": canary.rb.GENERAL_DAMAGE_CHECK_SCHEMA,
            "source_routine_id": "source_state",
            "final_routine_id": "clone_state" if live else "source_state",
            "occurrence_count": len(checks),
            "source_max_hp": source_hp,
            "baseline_max_hp": baseline_hp,
            "final_max_hp": final_hp,
            "baseline_hp_scale": baseline_hp / source_hp,
            "final_hp_scale": final_hp / source_hp,
            "hp_curse_multiplier": final_hp / baseline_hp,
            "checks": checks,
            "routine_cloned": live,
            "materialized": True,
            "enemy_watch_lookup_preserved": True,
            "enemy_watch_routine_alias_count": 0,
            "topology_preserved": True,
            "non_percentage_columns_preserved": True,
            "absolute_thresholds_preserved": True,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        }

    @staticmethod
    def standard_contract() -> dict:
        return {
            "schema": canary.rb.STANDARD_DAMAGE_CHECK_SCHEMA,
            "occurrence_count": 0,
            "runtime_hp_scale": 1.0,
            "checks": [],
            "topology_preserved": True,
            "absolute_thresholds_preserved": True,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        }

    @staticmethod
    def quest_plan() -> dict:
        values = {"enemy": 1.0, "device_or_summon": 1.0, "boss": 1.0}
        return {
            "columns": {
                "enemy": "c86", "device_or_summon": "c87", "boss": "c88"},
            "has_boss": True,
            "baseline": dict(values), "final": dict(values),
            "table_readback": dict(values),
            "active_target_class": "boss",
            "independent_verified": True,
            "mechanism_budget_separate": True,
        }

    def make_document(self) -> dict:
        case = canary.CANARY_CASES[0]
        floors = []
        round_no = 2
        for pair, count in case["expected_adapter_counts"].items():
            channel, family = pair.split("/", 1)
            phases = case["expected_special_components"].get(
                family, ("main",))
            triggers = case["expected_sphere_triggers"].get(family, ())
            for _index in range(count):
                adapter = {
                    "channel": channel, "family": family,
                    "round_no": round_no,
                    "baseline_c86": 1.0, "final_c86": 1.0,
                    "absolute_verified": True,
                    "within_tolerance": True,
                    "components": [{"phase": phase} for phase in phases],
                }
                source_code = f"source_{round_no}"
                if channel == "boss_level":
                    adapter["damage_checks"] = {
                        source_code: self.general_contract(live=round_no == 2)}
                elif channel == "standard_dsl":
                    adapter["damage_checks"] = {
                        source_code: self.standard_contract()}
                if triggers:
                    adapter["phase_behavior"] = {
                        "final_lifecycle": {
                            "steps": [{"trigger": trigger}
                                      for trigger in triggers],
                        },
                    }
                floors.append({
                    "round": round_no, "adapter": adapter,
                    "source_bosses": [source_code],
                    "runtime_bosses": [f"runtime_{round_no}"],
                    "absolute_verified": True, "target_exempt": False,
                    "curse_names": [], "curse_description": "",
                    "field_program_receipts": [],
                    "quest_hp_multipliers": self.quest_plan(),
                    "curse_hp_multiplier": (
                        1.0 if family.endswith("_sphere") else 0.85),
                })
                round_no += 1
        floors_by_round = {floor["round"]: floor for floor in floors}
        for expected in case["expected_identity_reference_closures"]:
            closure = dict(expected)
            closure_round = int(closure.pop("round"))
            closure["verified"] = True
            floor = floors_by_round[closure_round]
            if (closure["kind"] == "general_enemy_watch.routine_alias"
                    and floor["adapter"]["channel"] != "boss_level"):
                donor = next(
                    candidate for candidate in floors
                    if candidate["adapter"]["channel"] == "boss_level"
                    and not candidate.get("identity_reference_closures")
                    and candidate["round"] not in {
                        int(item["round"]) for item in
                        case["expected_identity_reference_closures"]})
                floor["adapter"], donor["adapter"] = (
                    donor["adapter"], floor["adapter"])
                floor["adapter"]["round_no"] = closure_round
                donor["adapter"]["round_no"] = donor["round"]
            floor["source_bosses"] = [closure["source_code"]]
            floor["runtime_bosses"] = [closure["clone_code"]]
            floor["identity_reference_closures"] = [closure]
            contracts = floor["adapter"].get("damage_checks") or {}
            if contracts:
                contract = next(iter(contracts.values()))
                if closure["kind"] == "general_enemy_watch.routine_alias":
                    contract = self.general_contract(live=True)
                    contract["source_routine_id"] = closure["source_routine_id"]
                    contract["final_routine_id"] = closure["clone_routine_id"]
                    contract["enemy_watch_routine_alias_count"] = 1
                floor["adapter"]["damage_checks"] = {
                    closure["source_code"]: contract}
        diversity = {
            "schema": canary.rb.CURSE_DIVERSITY_SCHEMA,
            "eligible": {}, "selected": {},
            "field_eligible": {}, "field_selected": {},
            "rounds": [{
                "round": r, "selected_names": [],
                "selected_field_programs": [],
            } for r in range(1, case["rounds"] + 1)],
            "frequency_caps": {
                "default": canary.rb.CURSE_RANDOM_FREQUENCY_CAP,
                "深渊重甲": canary.rb.DEEP_ARMOR_RANDOM_FREQUENCY_CAP,
                "field_program": canary.rb.FIELD_RANDOM_FREQUENCY_CAP,
            },
            "adjacent_cooldown": "strict_for_deep_armor_and_fields",
            "combo_uses_same_gate": True,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        }
        return {
            "inputs": {
                "seed": case["seed"], "rounds": case["rounds"],
                "difficulty": "hell", "enemy_level": "ramp",
            },
            "floors": floors,
            "selection_policy": {"curse_diversity": diversity},
            "summary": {
                "expected_boss_rounds": 59,
                "audited_boss_rounds": 59,
                "absolute_boss_rounds": 59,
                "proxy_components": 0,
                "target_exempt_rounds": 0,
                "chain_failures": 0,
                "identity_reference_closures": len(
                    case["expected_identity_reference_closures"]),
                "identity_reference_closure_rounds": len({
                    int(item["round"]) for item in
                    case["expected_identity_reference_closures"]}),
                "baseline_first_boss_hp": 3_000_000_000.0,
                "baseline_last_boss_hp": 15_000_000_000.0,
            },
            "gameplay_verified": False,
        }

    def test_reviewed_semantic_snapshot_passes(self):
        snapshot, errors = canary.validate_snapshot(
            canary.CANARY_CASES[0], self.make_document())
        self.assertEqual([], errors)
        self.assertEqual(59, snapshot["strict_summary"][
            "absolute_boss_rounds"])
        self.assertEqual(
            set(canary.CANARY_CASES[0]["expected_sphere_triggers"]),
            set(snapshot["sphere_triggers"]))

    def test_adapter_count_or_gameplay_claim_drift_fails(self):
        changed = self.make_document()
        changed["floors"][0]["adapter"]["family"] = "future_family"
        changed["gameplay_verified"] = True
        _snapshot, errors = canary.validate_snapshot(
            canary.CANARY_CASES[0], changed)
        self.assertTrue(any("adapter counts drift" in error for error in errors))
        self.assertTrue(any("gameplay_verified" in error for error in errors))

    def test_sphere_trigger_and_hp_curse_drift_fail(self):
        changed = copy.deepcopy(self.make_document())
        thunder = next(
            floor for floor in changed["floors"]
            if floor["adapter"]["family"] == "thunder_sphere")
        thunder["adapter"]["phase_behavior"]["final_lifecycle"]["steps"][1][
            "trigger"] = "parent_hp_threshold"
        thunder["curse_hp_multiplier"] = 2.5
        _snapshot, errors = canary.validate_snapshot(
            canary.CANARY_CASES[0], changed)
        self.assertTrue(any("lifecycle triggers drift" in error for error in errors))
        self.assertTrue(any("HP curse capability drift" in error for error in errors))

    def test_multiseed_validator_checks_strict_invariants_without_roster_pin(self):
        seed = canary.MULTISEED_SEEDS[0]
        document = self.make_document()
        document["inputs"].update({
            "seed": seed, "rounds": 30, "strict_target_hp": True})
        document["floors"] = [
            floor for floor in document["floors"]
            if int(floor["round"]) <= 30]
        diversity = document["selection_policy"]["curse_diversity"]
        diversity["rounds"] = [
            row for row in diversity["rounds"]
            if int(row["round"]) <= 30]
        closure_count = sum(len(
            floor.get("identity_reference_closures") or ())
            for floor in document["floors"])
        closure_rounds = sum(bool(
            floor.get("identity_reference_closures"))
            for floor in document["floors"])
        document["summary"].update({
            "expected_boss_rounds": 29,
            "audited_boss_rounds": 29,
            "absolute_boss_rounds": 29,
            "baseline_strictly_increasing": True,
            "max_absolute_error_hp": 0.5,
            "identity_reference_closures": closure_count,
            "identity_reference_closure_rounds": closure_rounds,
        })
        result, errors = canary.validate_multiseed_document(
            document, seed=seed)
        self.assertEqual([], errors)
        self.assertEqual(29, result["absolute_boss_rounds"])

        document["floors"][0]["adapter"]["within_tolerance"] = False
        document["gameplay_verified"] = True
        _result, errors = canary.validate_multiseed_document(
            document, seed=seed)
        self.assertTrue(any("strict floor drift" in error for error in errors))
        self.assertTrue(any("gameplay_verified" in error for error in errors))

    def test_showcase_policy_keeps_30_diverse_and_60_complete(self):
        import random

        available = {family for family, _fraction in
                     canary.rb.FULL_SPECIAL_SHOWCASE_SLOTS}
        short = canary.rb.special_showcase_slots(
            available, random.Random(9), rounds=30)
        short_families = {family for family, _fraction in short}
        self.assertEqual(5, len(short))
        self.assertEqual(1, len(short_families & {"orochi", "orochi_ex"}))
        self.assertEqual(1, len(short_families & set(canary.rb.SPHERE_SPECS)))
        self.assertTrue({"conductor", "touyakiren_ceo", "kraken"}
                        <= short_families)
        self.assertEqual(
            canary.rb.FULL_SPECIAL_SHOWCASE_SLOTS,
            canary.rb.special_showcase_slots(
                available, random.Random(9), rounds=60))

    def test_damage_check_and_routine_closure_drift_fail(self):
        changed = self.make_document()
        routine_floor = next(
            floor for floor in changed["floors"]
            if any(item.get("kind") == "general_enemy_watch.routine_alias"
                   for item in floor.get("identity_reference_closures") or ()))
        contract = next(iter(
            routine_floor["adapter"]["damage_checks"].values()))
        contract["checks"][0]["final_absolute_threshold_hp"] = 11.0
        contract["final_routine_id"] = "wrong_state"
        _stats, errors = canary.validate_extended_invariants(changed)
        self.assertTrue(any("absolute threshold drift" in error
                            for error in errors), errors)
        self.assertTrue(any("routine contract drift" in error
                            for error in errors), errors)

    def test_cooldown_field_receipt_and_last_damage_exit_fail(self):
        changed = self.make_document()
        first, second = changed["floors"][:2]
        first["source_bosses"] = ["water_sphere"]
        second["source_bosses"] = ["fire_sphere"]
        first["curse_names"] = ["绝对壁垒", "三重壁垒", "深渊法阵"]
        first["curse_description"] = (
            "「绝对壁垒」技能完全免疫 "
            "「三重壁垒」能力·直击·强化弹射三重免疫(只剩技能能打) "
            "「深渊法阵」连击领域·连击限制")
        first["field_program_receipts"] = [{
            "name": "连击领域", "description": "连击限制",
            "declared_program": "field/program/declared",
            "applied_program": "field/program/wrong",
            "readback_match": False,
        }]
        diversity = changed["selection_policy"]["curse_diversity"]
        row = diversity["rounds"][1]
        row["selected_names"] = ["绝对壁垒", "三重壁垒"]
        row["selected_field_programs"] = ["field/program/declared"]
        diversity["selected"] = {"绝对壁垒": 1, "三重壁垒": 1}
        diversity["selection_gate_selected"] = dict(diversity["selected"])
        diversity["eligible"] = {"绝对壁垒": 3, "三重壁垒": 3}
        diversity["field_selected"] = {"field/program/declared": 1}
        diversity["field_eligible"] = {"field/program/declared": 3}
        _stats, errors = canary.validate_extended_invariants(changed)
        self.assertTrue(any("adjacent sphere" in error for error in errors), errors)
        self.assertTrue(any("field text/declaration/readback drift" in error
                            for error in errors), errors)
        self.assertTrue(any("closes the last damage exit" in error
                            for error in errors), errors)

    def test_diversity_reconcile_preserves_gate_counts_and_final_names(self):
        state = canary.rb.new_curse_diversity_state()
        state["selected"] = {"玻璃深渊": 1}
        state["rounds"] = [{
            "round": 1, "selected_names": ["玻璃深渊"],
            "selected_field_programs": [], "combo": "速攻",
        }]
        records = [{
            "r": 1,
            "curse": {
                "picks": [{
                    "name": "玻璃深渊·残响", "hp": 0.5,
                    "text": "敌血-50%（攻击增幅已摘）",
                }],
                "combo": None,
            },
        }]
        canary.rb.reconcile_curse_diversity_state(state, records)
        self.assertEqual({"玻璃深渊": 1}, state["selection_gate_selected"])
        self.assertEqual({"玻璃深渊·残响": 1}, state["selected"])
        self.assertEqual(
            ["玻璃深渊·残响"], state["rounds"][0]["selected_names"])


if __name__ == "__main__":
    unittest.main()
