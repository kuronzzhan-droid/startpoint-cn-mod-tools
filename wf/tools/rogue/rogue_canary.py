#!/usr/bin/env python3
"""Deterministic, read-only adapter canary for ``wf_rogue_build``.

The canary deliberately uses a 60-floor tower: the normal 30-floor curator
schedule does not have enough unoccupied slots to exercise all five Sphere
families in one run.  It writes only an audit JSON inside an OS temporary
directory, never passes ``--write``/``--publish``, and then independently
verifies both the strict receipt and a reviewed semantic snapshot.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from wf.tools.rogue import rogue_build as rb


CANARY_SCHEMA = "wf-rogue-adapter-canary/v2"
MULTISEED_SEEDS = (
    2026082622, 2026082623, 2026082624, 2026082625, 2026082626,
)
CANARY_CASES = ({
    "name": "all-current-strict-adapters",
    "seed": 2026082621,
    "rounds": 60,
    "arguments": (
        "--difficulty", "hell", "--enemy-level", "ramp",
        "--strict-target-hp", "--ignore-plan",
    ),
    "expected_adapter_counts": {
        "boss_level/general": 41,
        "special_bundle/conductor": 1,
        "special_bundle/fire_sphere": 1,
        "special_bundle/holy_sphere": 1,
        "special_bundle/kraken": 1,
        "special_bundle/orochi": 1,
        "special_bundle/orochi_ex": 1,
        "special_bundle/thunder_sphere": 1,
        "special_bundle/touyakiren_ceo": 1,
        "special_bundle/water_sphere": 1,
        "special_bundle/wind_sphere": 1,
        "standard_dsl/standard": 8,
    },
    "expected_special_components": {
        "conductor": ("main",),
        "fire_sphere": (
            "phase[1].crystal[1]", "phase[1].crystal[2]",
            "phase[1].crystal[3]", "main"),
        "holy_sphere": (
            "phase[1].crystal[1]", "phase[1].crystal[2]", "main"),
        "kraken": ("main",),
        "orochi": (
            "parent",),
        "orochi_ex": ("phase[1]", "phase[2]", "phase[3]"),
        "thunder_sphere": ("main",),
        "touyakiren_ceo": ("main",),
        "water_sphere": (
            "phase[1].crystal[1]", "phase[1].crystal[2]", "main"),
        "wind_sphere": ("main",),
    },
    "expected_sphere_triggers": {
        "fire_sphere": (
            "mandatory_gate_clear", "parent_hp_threshold",
            "parent_hp_threshold", "child_damage_threshold"),
        "holy_sphere": (
            "mandatory_gate_clear", "parent_hp_threshold",
            "child_damage_threshold", "parent_hp_depleted"),
        "thunder_sphere": (
            "parent_hp_threshold", "child_damage_threshold",
            "parent_hp_threshold", "child_damage_threshold"),
        "water_sphere": (
            "mandatory_gate_clear", "parent_hp_threshold",
            "child_damage_threshold", "parent_hp_depleted"),
        "wind_sphere": (
            "parent_hp_threshold", "parent_hp_threshold",
            "child_damage_threshold", "parent_hp_depleted"),
    },
    "expected_identity_reference_closures": (
        {
            "round": 33,
            "kind": "general_enemy_watch.partner_alias",
            "source_code": "spirit_beast_thunder",
            "clone_code": "mod_rogue_boss33",
            "source_reference_count": 1,
            "clone_reference_count": 1,
        },
        {
            "round": 46,
            "kind": "general_enemy_watch.partner_alias",
            "source_code": "benzaiten",
            "clone_code": "mod_rogue_boss46",
            "source_reference_count": 1,
            "clone_reference_count": 1,
        },
        {
            "round": 60,
            "kind": "general_enemy_watch.routine_alias",
            "source_code": "desert_bonds_big_boss_multi_ex",
            "clone_code": "mod_rogue_boss60",
            "source_routine_id": "desert_bonds_big_boss",
            "clone_routine_id": "mod_rogue_boss60_state",
        },
    ),
},)


def _canonical_sha(value) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _close(left, right, *, rel_tol: float = 1e-10,
           abs_tol: float = 1e-4) -> bool:
    try:
        return math.isclose(float(left), float(right),
                            rel_tol=rel_tol, abs_tol=abs_tol)
    except (TypeError, ValueError):
        return False


def _card_text(description: str, name: str) -> str:
    marker = f"「{name}」"
    start = str(description).find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = str(description).find(" 「", start)
    return str(description)[start:] if end < 0 else str(description)[start:end]


def validate_identity_reference_closures(document: dict) \
        -> tuple[dict, list[str]]:
    errors: list[str] = []
    floors = list(document.get("floors") or ())
    closures = []
    closure_rounds = set()
    for floor in floors:
        round_no = int(floor.get("round") or 0)
        source_bosses = set(map(str, floor.get("source_bosses") or ()))
        runtime_bosses = set(map(str, floor.get("runtime_bosses") or ()))
        damage_checks = (floor.get("adapter") or {}).get("damage_checks") or {}
        for raw in floor.get("identity_reference_closures") or ():
            item = dict(raw) if isinstance(raw, dict) else {}
            kind = str(item.get("kind") or "")
            source = str(item.get("source_code") or "")
            clone = str(item.get("clone_code") or "")
            label = f"round {round_no} identity closure {kind or '(missing)'}"
            if (kind not in {"general_enemy_watch.partner_alias",
                             "general_enemy_watch.routine_alias"}
                    or source not in source_bosses
                    or clone not in runtime_bosses
                    or source == clone
                    or item.get("verified") is not True):
                errors.append(f"{label} identity/source/runtime drift")
                continue
            if kind == "general_enemy_watch.partner_alias":
                try:
                    source_count = int(item["source_reference_count"])
                    clone_count = int(item["clone_reference_count"])
                except (KeyError, TypeError, ValueError):
                    source_count = clone_count = 0
                if source_count <= 0 or clone_count != source_count:
                    errors.append(f"{label} partner reference counts drift")
            else:
                source_routine = str(item.get("source_routine_id") or "")
                clone_routine = str(item.get("clone_routine_id") or "")
                contract = damage_checks.get(source) if isinstance(
                    damage_checks, dict) else None
                if (not source_routine or not clone_routine
                        or source_routine == clone_routine
                        or not clone_routine.startswith(clone)
                        or not isinstance(contract, dict)
                        or contract.get("schema")
                        != rb.GENERAL_DAMAGE_CHECK_SCHEMA
                        or contract.get("source_routine_id") != source_routine
                        or contract.get("final_routine_id") != clone_routine
                        or int(contract.get(
                            "enemy_watch_routine_alias_count") or 0) <= 0):
                    errors.append(f"{label} routine contract drift")
            closures.append((round_no, item))
            closure_rounds.add(round_no)
    summary = document.get("summary") or {}
    if int(summary.get("identity_reference_closures") or 0) != len(closures):
        errors.append("identity closure summary count drift")
    if int(summary.get("identity_reference_closure_rounds") or 0) \
            != len(closure_rounds):
        errors.append("identity closure round summary drift")
    return {
        "total": len(closures),
        "rounds": len(closure_rounds),
        "partner_aliases": sum(
            item.get("kind") == "general_enemy_watch.partner_alias"
            for _round, item in closures),
        "routine_aliases": sum(
            item.get("kind") == "general_enemy_watch.routine_alias"
            for _round, item in closures),
    }, errors


def validate_damage_check_contracts(document: dict) \
        -> tuple[dict, list[str]]:
    errors: list[str] = []
    contract_counts = Counter()
    occurrence_counts = Counter()
    floors_with_trials = set()
    for floor in document.get("floors") or ():
        round_no = int(floor.get("round") or 0)
        adapter = floor.get("adapter") or {}
        channel = str(adapter.get("channel") or "")
        contracts = adapter.get("damage_checks")
        if channel in {"boss_level", "standard_dsl", "mixed_hp"}:
            if not isinstance(contracts, dict) or not contracts:
                errors.append(f"round {round_no} {channel} missing DamageCheck contracts")
                continue
        elif contracts is not None and contracts != {}:
            errors.append(f"round {round_no} unexpected DamageCheck contracts")
            continue
        for code, contract in (contracts or {}).items():
            label = f"round {round_no} {code} DamageCheck"
            if not isinstance(contract, dict):
                errors.append(f"{label} is not an object")
                continue
            schema = str(contract.get("schema") or "")
            contract_counts[schema] += 1
            try:
                occurrence_count = int(contract.get("occurrence_count"))
            except (TypeError, ValueError):
                occurrence_count = -1
            checks = contract.get("checks")
            if (not isinstance(checks, list)
                    or occurrence_count != len(checks)
                    or occurrence_count < 0):
                errors.append(f"{label} occurrence/check count drift")
                continue
            occurrence_counts[schema] += occurrence_count
            if occurrence_count:
                floors_with_trials.add(round_no)
            if (contract.get("topology_preserved") is not True
                    or contract.get("absolute_thresholds_preserved") is not True
                    or contract.get("static_verified") is not True
                    or contract.get("runtime_simulated") is not False
                    or contract.get("gameplay_verified") is not False):
                errors.append(f"{label} evidence level/topology drift")
            if schema == rb.GENERAL_DAMAGE_CHECK_SCHEMA:
                if channel not in {"boss_level", "mixed_hp"}:
                    errors.append(f"{label} general schema on {channel}")
                try:
                    source_hp = float(contract["source_max_hp"])
                    baseline_hp = float(contract["baseline_max_hp"])
                    final_hp = float(contract["final_max_hp"])
                except (KeyError, TypeError, ValueError):
                    source_hp = baseline_hp = final_hp = float("nan")
                if (not all(math.isfinite(value) and value > 0 for value in
                            (source_hp, baseline_hp, final_hp))
                        or contract.get("non_percentage_columns_preserved")
                        is not True
                        or contract.get("materialized") is not True
                        or contract.get("enemy_watch_lookup_preserved")
                        is not True
                        or bool(contract.get("routine_cloned"))
                        != bool(occurrence_count)
                        or not _close(contract.get("baseline_hp_scale"),
                                      baseline_hp / source_hp)
                        or not _close(contract.get("final_hp_scale"),
                                      final_hp / source_hp)
                        or not _close(contract.get("hp_curse_multiplier"),
                                      final_hp / baseline_hp)):
                    errors.append(f"{label} general HP/routine contract drift")
                source_routine = str(contract.get("source_routine_id") or "")
                final_routine = str(contract.get("final_routine_id") or "")
                if (not source_routine or not final_routine
                        or (occurrence_count and source_routine == final_routine)
                        or (not occurrence_count
                            and source_routine != final_routine)):
                    errors.append(f"{label} general routine identity drift")
                for index, check in enumerate(checks, start=1):
                    try:
                        source_threshold = (
                            source_hp * float(check["source_percentage"]) / 100.0)
                        baseline_threshold = (
                            baseline_hp * float(check["baseline_percentage"]) / 100.0)
                        final_threshold = (
                            final_hp * float(check["final_percentage"]) / 100.0)
                    except (KeyError, TypeError, ValueError):
                        errors.append(f"{label}[{index}] numeric fields invalid")
                        continue
                    if (int(check.get("occurrence") or 0) != index
                            or not _close(check.get(
                                "source_absolute_threshold_hp"), source_threshold)
                            or not _close(check.get(
                                "baseline_absolute_threshold_hp"),
                                baseline_threshold)
                            or not _close(check.get(
                                "final_absolute_threshold_hp"), final_threshold)
                            or not _close(source_threshold, baseline_threshold)
                            or not _close(source_threshold, final_threshold)):
                        errors.append(f"{label}[{index}] absolute threshold drift")
            elif schema == rb.STANDARD_DAMAGE_CHECK_SCHEMA:
                if channel not in {"standard_dsl", "mixed_hp"}:
                    errors.append(f"{label} standard schema on {channel}")
                try:
                    runtime_scale = float(contract["runtime_hp_scale"])
                except (KeyError, TypeError, ValueError):
                    runtime_scale = float("nan")
                if not math.isfinite(runtime_scale) or runtime_scale <= 0:
                    errors.append(f"{label} standard runtime scale invalid")
                for index, check in enumerate(checks, start=1):
                    try:
                        source_threshold = (
                            float(check["source_max_hp"])
                            * float(check["source_percentage"]) / 100.0)
                        final_threshold = (
                            float(check["final_max_hp"])
                            * float(check["final_percentage"]) / 100.0)
                    except (KeyError, TypeError, ValueError):
                        errors.append(f"{label}[{index}] numeric fields invalid")
                        continue
                    if (int(check.get("occurrence") or 0) != index
                            or not _close(check.get(
                                "source_absolute_threshold_hp"), source_threshold)
                            or not _close(check.get(
                                "final_absolute_threshold_hp"), final_threshold)
                            or not _close(source_threshold, final_threshold)):
                        errors.append(f"{label}[{index}] absolute threshold drift")
            else:
                errors.append(f"{label} unknown schema:{schema or '(missing)'}")
    return {
        "contract_counts": dict(sorted(contract_counts.items())),
        "occurrence_counts": dict(sorted(occurrence_counts.items())),
        "floors_with_trials": len(floors_with_trials),
    }, errors


def validate_family_cooldowns(document: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    previous_group = None
    previous_round = None
    group_counts = Counter()
    for floor in sorted(document.get("floors") or (),
                        key=lambda item: int(item.get("round") or 0)):
        round_no = int(floor.get("round") or 0)
        group = rb.boss_family_cooldown_group(floor.get("source_bosses") or ())
        if group:
            group_counts[group] += 1
        if group and group == previous_group:
            errors.append(
                f"adjacent {group} families at rounds {previous_round}/{round_no}")
        previous_group = group
        previous_round = round_no
    return dict(sorted(group_counts.items())), errors


def validate_quest_hp_plans(document: dict) -> tuple[int, list[str]]:
    errors: list[str] = []
    checked = 0
    expected_columns = {
        "enemy": "c86", "device_or_summon": "c87", "boss": "c88"}
    for floor in document.get("floors") or ():
        round_no = int(floor.get("round") or 0)
        adapter = floor.get("adapter") or {}
        plan = floor.get("quest_hp_multipliers")
        if not isinstance(plan, dict):
            errors.append(f"round {round_no} missing independent c86/c87/c88 plan")
            continue
        try:
            baseline = {key: float(value)
                        for key, value in plan["baseline"].items()}
            final = {key: float(value)
                     for key, value in plan["final"].items()}
            readback = {key: float(value)
                        for key, value in plan["table_readback"].items()}
        except (KeyError, AttributeError, TypeError, ValueError):
            errors.append(f"round {round_no} invalid c86/c87/c88 values")
            continue
        if (plan.get("columns") != expected_columns
                or plan.get("has_boss") is not True
                or plan.get("active_target_class") != "boss"
                or plan.get("independent_verified") is not True
                or plan.get("mechanism_budget_separate") is not True
                or set(baseline) != set(expected_columns)
                or set(final) != set(expected_columns)
                or set(readback) != set(expected_columns)
                or not _close(baseline["boss"], adapter.get("baseline_c86"),
                              rel_tol=0.0, abs_tol=1e-12)
                or not _close(final["boss"], adapter.get("final_c86"),
                              rel_tol=0.0, abs_tol=1e-12)
                or not all(_close(values[key], 1.0,
                                  rel_tol=0.0, abs_tol=1e-12)
                           for values in (baseline, final)
                           for key in ("enemy", "device_or_summon"))
                or any(not _close(readback[key], final[key],
                                  rel_tol=0.0, abs_tol=1e-12)
                       for key in expected_columns)):
            errors.append(f"round {round_no} coupled or drifting c86/c87/c88 plan")
            continue
        checked += 1
    return checked, errors


def validate_curse_and_field_diversity(document: dict) \
        -> tuple[dict, list[str]]:
    errors: list[str] = []
    policy = (document.get("selection_policy") or {}).get("curse_diversity")
    if not isinstance(policy, dict):
        return {}, ["missing curse diversity receipt"]
    rounds = int((document.get("inputs") or {}).get("rounds") or 0)
    rows = list(policy.get("rounds") or ())
    by_round = {int(row.get("round") or 0): row
                for row in rows if isinstance(row, dict)}
    if set(by_round) != set(range(1, rounds + 1)) or len(rows) != rounds:
        errors.append("curse diversity round receipt coverage drift")
    selected_names = Counter()
    selected_fields = Counter()
    previous_names: set[str] = set()
    previous_fields: set[str] = set()
    for round_no in range(1, rounds + 1):
        row = by_round.get(round_no) or {}
        names = list(map(str, row.get("selected_names") or ()))
        fields = list(map(str, row.get("selected_field_programs") or ()))
        if len(names) != len(set(names)) or len(fields) != len(set(fields)):
            errors.append(f"round {round_no} duplicate curse/field selection")
        if len(fields) > 1:
            errors.append(f"round {round_no} has simultaneous field programs")
        name_set, field_set = set(names), set(fields)
        if "深渊重甲" in name_set and "深渊重甲" in previous_names:
            errors.append(f"round {round_no} repeats 深渊重甲 adjacently")
        if field_set & previous_fields:
            errors.append(f"round {round_no} repeats a field program adjacently")
        selected_names.update(name_set)
        selected_fields.update(field_set)
        previous_names, previous_fields = name_set, field_set
    declared_names = Counter({str(key): int(value) for key, value in
                              (policy.get("selected") or {}).items()})
    declared_fields = Counter({str(key): int(value) for key, value in
                               (policy.get("field_selected") or {}).items()})
    if selected_names != declared_names:
        errors.append("curse diversity selected counters drift")
    if selected_fields != declared_fields:
        errors.append("field diversity selected counters drift")
    caps = policy.get("frequency_caps") or {}
    eligible = {str(key): int(value) for key, value in
                (policy.get("eligible") or {}).items()}
    field_eligible = {str(key): int(value) for key, value in
                      (policy.get("field_eligible") or {}).items()}
    gate_selected = Counter({str(key): int(value) for key, value in
                             (policy.get("selection_gate_selected")
                              or policy.get("selected") or {}).items()})
    for name, count in gate_selected.items():
        cap = float(caps.get(name, caps.get("default", 0)))
        allowed = max(1, math.ceil(float(eligible.get(name, 0)) * cap - 1e-12))
        if cap <= 0 or count > allowed:
            errors.append(
                f"curse frequency cap exceeded:{name}={count}/{allowed}")
    field_cap = float(caps.get("field_program", 0))
    for program, count in selected_fields.items():
        allowed = max(1, math.ceil(
            float(field_eligible.get(program, 0)) * field_cap - 1e-12))
        if field_cap <= 0 or count > allowed:
            errors.append(
                f"field frequency cap exceeded:{program}={count}/{allowed}")
    field_receipt_count = 0
    for floor in document.get("floors") or ():
        round_no = int(floor.get("round") or 0)
        names = list(map(str, floor.get("curse_names") or ()))
        description = str(floor.get("curse_description") or "")
        field_receipts = floor.get("field_program_receipts")
        if not isinstance(field_receipts, list) or len(field_receipts) > 1:
            errors.append(f"round {round_no} invalid field receipt count")
            field_receipts = []
        expected_names = sorted(
            name for name in names if name != "深渊法阵")
        diversity_row = by_round.get(round_no) or {}
        if expected_names != sorted(map(
                str, diversity_row.get("selected_names") or ())):
            errors.append(f"round {round_no} curse receipt/diversity drift")
        receipt_programs = []
        for receipt in field_receipts:
            field_receipt_count += 1
            if not isinstance(receipt, dict):
                errors.append(f"round {round_no} field receipt is not an object")
                continue
            declared = str(receipt.get("declared_program") or "")
            applied = str(receipt.get("applied_program") or "")
            name = str(receipt.get("name") or "")
            field_description = str(receipt.get("description") or "")
            receipt_programs.append(applied)
            if (not declared or declared != applied
                    or receipt.get("readback_match") is not True
                    or not name or not field_description
                    or name not in description
                    or field_description not in description):
                errors.append(
                    f"round {round_no} field text/declaration/readback drift")
        if sorted(receipt_programs) != sorted(map(
                str, diversity_row.get("selected_field_programs") or ())):
            errors.append(f"round {round_no} field receipt/diversity drift")
        element_cards = [name for name in names
                         if name in rb.ELEMENT_CURSE_NAMES]
        if len(element_cards) > 1:
            errors.append(f"round {round_no} stacks multiple element walls")
        if "绝对壁垒" in names and "三重壁垒" in names:
            absolute_text = _card_text(description, "绝对壁垒")
            triple_text = _card_text(description, "三重壁垒")
            absolute_kind = next((label for label in rb.COND_KIND_CN.values()
                                  if f"{label}完全免疫" in absolute_text), None)
            open_kind = next((label for label in rb.COND_KIND_CN.values()
                              if f"只剩{label}能打" in triple_text), None)
            if absolute_kind is None or open_kind is None:
                errors.append(f"round {round_no} immunity exit text is unauditable")
            elif absolute_kind == open_kind:
                errors.append(f"round {round_no} closes the last damage exit")
    return {
        "distinct_curses": len(selected_names),
        "distinct_field_programs": len(selected_fields),
        "deep_armor_selected": int(selected_names.get("深渊重甲", 0)),
        "field_receipts": field_receipt_count,
        "curse_counts": dict(sorted(selected_names.items())),
        "selection_gate_curse_counts": dict(sorted(gate_selected.items())),
    }, errors


def validate_extended_invariants(document: dict) -> tuple[dict, list[str]]:
    identity, identity_errors = validate_identity_reference_closures(document)
    damage, damage_errors = validate_damage_check_contracts(document)
    cooldowns, cooldown_errors = validate_family_cooldowns(document)
    quest_count, quest_errors = validate_quest_hp_plans(document)
    diversity, diversity_errors = validate_curse_and_field_diversity(document)
    return {
        "identity_closures": identity,
        "damage_checks": damage,
        "cooldown_families": cooldowns,
        "independent_quest_hp_rounds": quest_count,
        "diversity": diversity,
    }, (identity_errors + damage_errors + cooldown_errors
        + quest_errors + diversity_errors)


def semantic_snapshot(document: dict) -> dict:
    """Extract reviewed behavior, excluding tool/digest byte churn."""

    floors = list(document.get("floors") or ())
    adapter_counts = Counter(
        f"{floor['adapter']['channel']}/{floor['adapter']['family']}"
        for floor in floors)
    special_components: dict[str, tuple[str, ...]] = {}
    sphere_triggers: dict[str, tuple[str, ...]] = {}
    for floor in floors:
        adapter = floor.get("adapter") or {}
        family = str(adapter.get("family") or "")
        if adapter.get("channel") != "special_bundle":
            continue
        phases = tuple(str(item.get("phase") or "")
                       for item in (adapter.get("components") or ()))
        old = special_components.setdefault(family, phases)
        if old != phases:
            raise ValueError(
                f"special family {family} has multiple component shapes")
        if family in rb.SPHERE_SPECS:
            lifecycle = ((adapter.get("phase_behavior") or {}).get(
                "final_lifecycle") or {})
            sphere_triggers[family] = tuple(
                str(step.get("trigger") or "")
                for step in (lifecycle.get("steps") or ()))
    summary = document.get("summary") or {}
    identity_reference_closures = []
    for floor in floors:
        for closure in floor.get("identity_reference_closures") or ():
            item = {
                "round": int(floor["round"]),
                "kind": str(closure.get("kind") or ""),
                "source_code": str(closure.get("source_code") or ""),
                "clone_code": str(closure.get("clone_code") or ""),
            }
            if item["kind"] == "general_enemy_watch.partner_alias":
                item.update({
                    "source_reference_count": int(
                        closure.get("source_reference_count") or 0),
                    "clone_reference_count": int(
                        closure.get("clone_reference_count") or 0),
                })
            elif item["kind"] == "general_enemy_watch.routine_alias":
                item.update({
                    "source_routine_id": str(
                        closure.get("source_routine_id") or ""),
                    "clone_routine_id": str(
                        closure.get("clone_routine_id") or ""),
                })
            identity_reference_closures.append(item)
    finale = max(floors, key=lambda floor: int(floor.get("round") or 0),
                 default={})
    return {
        "schema": CANARY_SCHEMA,
        "inputs": {
            "seed": int((document.get("inputs") or {}).get("seed") or 0),
            "rounds": int((document.get("inputs") or {}).get("rounds") or 0),
            "difficulty": str(
                (document.get("inputs") or {}).get("difficulty") or ""),
            "enemy_level": str(
                (document.get("inputs") or {}).get("enemy_level") or ""),
        },
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "special_components": {
            family: list(phases)
            for family, phases in sorted(special_components.items())
        },
        "sphere_triggers": {
            family: list(triggers)
            for family, triggers in sorted(sphere_triggers.items())
        },
        "strict_summary": {
            "expected_boss_rounds": int(
                summary.get("expected_boss_rounds") or 0),
            "audited_boss_rounds": int(
                summary.get("audited_boss_rounds") or 0),
            "absolute_boss_rounds": int(
                summary.get("absolute_boss_rounds") or 0),
            "proxy_components": int(summary.get("proxy_components") or 0),
            "target_exempt_rounds": int(
                summary.get("target_exempt_rounds") or 0),
            "chain_failures": int(summary.get("chain_failures") or 0),
            "baseline_first_boss_hp": float(
                summary.get("baseline_first_boss_hp") or 0),
            "baseline_last_boss_hp": float(
                summary.get("baseline_last_boss_hp") or 0),
        },
        "sphere_hp_multipliers": {
            str(floor["adapter"]["family"]): float(
                floor.get("curse_hp_multiplier") or 0)
            for floor in floors
            if floor.get("adapter", {}).get("family") in rb.SPHERE_SPECS
        },
        "identity_reference_closures": identity_reference_closures,
        "finale_source_bosses": list(map(
            str, finale.get("source_bosses") or ())),
        "gameplay_verified": document.get("gameplay_verified"),
    }


def validate_snapshot(case: dict, document: dict) -> tuple[dict, list[str]]:
    snapshot = semantic_snapshot(document)
    extended, errors = validate_extended_invariants(document)
    snapshot["extended_invariants"] = extended
    if snapshot["inputs"] != {
            "seed": case["seed"], "rounds": case["rounds"],
            "difficulty": "hell", "enemy_level": "ramp"}:
        errors.append(f"inputs drift:{snapshot['inputs']}")
    if snapshot["adapter_counts"] != case["expected_adapter_counts"]:
        errors.append(
            "adapter counts drift:"
            f"actual={snapshot['adapter_counts']},"
            f"expected={case['expected_adapter_counts']}")
    expected_components = {
        family: list(phases) for family, phases in
        case["expected_special_components"].items()}
    if snapshot["special_components"] != expected_components:
        errors.append(
            "special component shapes drift:"
            f"actual={snapshot['special_components']},"
            f"expected={expected_components}")
    expected_triggers = {
        family: list(triggers) for family, triggers in
        case["expected_sphere_triggers"].items()}
    if snapshot["sphere_triggers"] != expected_triggers:
        errors.append(
            "Sphere lifecycle triggers drift:"
            f"actual={snapshot['sphere_triggers']},"
            f"expected={expected_triggers}")
    expected_identity_closures = [
        dict(item) for item in case["expected_identity_reference_closures"]]
    if snapshot["identity_reference_closures"] != expected_identity_closures:
        errors.append(
            "identity reference closures drift:"
            f"actual={snapshot['identity_reference_closures']},"
            f"expected={expected_identity_closures}")
    strict = snapshot["strict_summary"]
    expected_rounds = int(case["rounds"]) - 1
    if (strict["expected_boss_rounds"] != expected_rounds
            or strict["audited_boss_rounds"] != expected_rounds
            or strict["absolute_boss_rounds"] != expected_rounds
            or strict["proxy_components"] != 0
            or strict["target_exempt_rounds"] != 0
            or strict["chain_failures"] != 0
            or strict["baseline_first_boss_hp"] != 3_000_000_000.0
            or strict["baseline_last_boss_hp"] != 15_000_000_000.0):
        errors.append(f"strict summary drift:{strict}")
    if (set(snapshot["sphere_hp_multipliers"]) != set(rb.SPHERE_SPECS)
            or any(value != 1.0 for value in
                   snapshot["sphere_hp_multipliers"].values())):
        errors.append(
            "Sphere HP curse capability drift:"
            f"{snapshot['sphere_hp_multipliers']}")
    if snapshot["gameplay_verified"] is not False:
        errors.append("canary static receipt must keep gameplay_verified=false")
    damage = extended.get("damage_checks") or {}
    contract_counts = damage.get("contract_counts") or {}
    occurrence_counts = damage.get("occurrence_counts") or {}
    if (int(contract_counts.get(rb.GENERAL_DAMAGE_CHECK_SCHEMA, 0)) <= 0
            or int(contract_counts.get(
                rb.STANDARD_DAMAGE_CHECK_SCHEMA, 0)) <= 0):
        errors.append(f"fixed canary lacks General/Standard contracts:{damage}")
    if int(occurrence_counts.get(rb.GENERAL_DAMAGE_CHECK_SCHEMA, 0)) <= 0:
        errors.append(f"fixed canary lacks a live General red trial:{damage}")
    return snapshot, errors


def _build_case_document(case: dict) -> tuple[dict | None, list[str], str]:
    build = Path(rb.MOD_DIR) / "wf_rogue_build.py"
    with tempfile.TemporaryDirectory(prefix="wf-rogue-canary-") as tmp:
        audit = Path(tmp) / "audit.json"
        command = [
            sys.executable, str(build), "--rounds", str(case["rounds"]),
            "--seed", str(case["seed"]), *case["arguments"],
            "--audit-json", str(audit),
        ]
        if "--write" in command or "--publish" in command:
            return None, ["canary command contains forbidden mutation flag"], ""
        process = subprocess.run(
            command, cwd=str(build.parent),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=240)
        combined = (process.stdout or "") + (process.stderr or "")
        if process.returncode != 0:
            return None, [
                f"build exit={process.returncode}",
                "tail=" + "\n".join(combined.splitlines()[-40:]),
            ], combined
        try:
            document = json.loads(audit.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            return None, [f"audit read failed:{exc}"], combined
        return document, [], combined


def run_case(case: dict) -> tuple[dict | None, list[str], str]:
    document, errors, combined = _build_case_document(case)
    if errors or document is None:
        return None, errors, combined
    build = Path(rb.MOD_DIR) / "wf_rogue_build.py"
    tool_hash = rb.tool_source_sha256()
    errors = rb.verify_hp_audit_document(
        document, expected_tool_sha256=tool_hash)
    snapshot, snapshot_errors = validate_snapshot(case, document)
    return snapshot, errors + snapshot_errors, combined


def validate_multiseed_document(document: dict, *, seed: int) \
        -> tuple[dict, list[str]]:
    """Validate strict invariants without pinning a random roster."""
    extended, errors = validate_extended_invariants(document)
    inputs = document.get("inputs") or {}
    summary = document.get("summary") or {}
    floors = document.get("floors") or []
    rounds = int(inputs.get("rounds") or 0)
    expected = max(0, rounds - 1)
    if (int(inputs.get("seed") or 0) != int(seed)
            or rounds != 30
            or inputs.get("difficulty") != "hell"
            or inputs.get("enemy_level") != "ramp"
            or inputs.get("strict_target_hp") is not True):
        errors.append(f"strict inputs drift:{inputs}")
    if (summary.get("expected_boss_rounds") != expected
            or summary.get("audited_boss_rounds") != expected
            or summary.get("absolute_boss_rounds") != expected
            or summary.get("proxy_components") != 0
            or summary.get("target_exempt_rounds") != 0
            or summary.get("chain_failures") != 0
            or summary.get("baseline_first_boss_hp") != 3_000_000_000.0
            or summary.get("baseline_last_boss_hp") != 15_000_000_000.0
            or summary.get("baseline_strictly_increasing") is not True):
        errors.append(f"strict summary drift:{summary}")
    if len(floors) != expected:
        errors.append(f"floor count drift:{len(floors)}/{expected}")
    if document.get("gameplay_verified") is not False:
        errors.append("multiseed static receipt must keep gameplay_verified=false")
    adapter_counts = Counter()
    special_families = set()
    for floor in floors:
        adapter = floor.get("adapter") or {}
        key = f"{adapter.get('channel')}/{adapter.get('family')}"
        adapter_counts[key] += 1
        if adapter.get("channel") == "special_bundle":
            special_families.add(str(adapter.get("family") or ""))
        if (floor.get("absolute_verified") is not True
                or floor.get("target_exempt") is not False
                or adapter.get("within_tolerance") is not True):
            errors.append(f"round {floor.get('round')} strict floor drift")
        if (adapter.get("family") in rb.SPHERE_SPECS
                and float(floor.get("curse_hp_multiplier") or 0) != 1.0):
            errors.append(
                f"round {floor.get('round')} Sphere received HP curse")
    result = {
        "seed": int(seed),
        "absolute_boss_rounds": int(
            summary.get("absolute_boss_rounds") or 0),
        "proxy_components": int(summary.get("proxy_components") or 0),
        "source_proxy_components": int(
            summary.get("source_proxy_components") or 0),
        "target_exempt_rounds": int(
            summary.get("target_exempt_rounds") or 0),
        "chain_failures": int(summary.get("chain_failures") or 0),
        "max_absolute_error_hp": float(
            summary.get("max_absolute_error_hp") or 0),
        "adapter_counts": dict(sorted(adapter_counts.items())),
        "special_families": sorted(special_families),
        "identity_reference_closures": int(
            summary.get("identity_reference_closures") or 0),
        "finale_source_bosses": list(map(
            str, (max(floors,
                      key=lambda floor: int(floor.get("round") or 0),
                      default={}).get("source_bosses") or ()))),
        "extended_invariants": extended,
        "gameplay_verified": document.get("gameplay_verified"),
    }
    return result, errors


def run_multiseed(seed: int) -> tuple[dict | None, list[str], str]:
    case = {
        "seed": int(seed), "rounds": 30,
        "arguments": (
            "--difficulty", "hell", "--enemy-level", "ramp",
            "--strict-target-hp", "--ignore-plan",
        ),
    }
    document, errors, combined = _build_case_document(case)
    if errors or document is None:
        return None, errors, combined
    build = Path(rb.MOD_DIR) / "wf_rogue_build.py"
    errors = rb.verify_hp_audit_document(
        document,
        expected_tool_sha256=rb.tool_source_sha256())
    result, invariant_errors = validate_multiseed_document(
        document, seed=int(seed))
    return result, errors + invariant_errors, combined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读运行固定严格塔并校验 HP 适配器语义快照")
    parser.add_argument(
        "--list", action="store_true", help="只打印金丝雀配置，不运行构建")
    parser.add_argument(
        "--json", action="store_true", help="成功时打印机器可读摘要")
    parser.add_argument(
        "--multiseed", action="store_true",
        help="只读运行 5 个固定 30 关 seed，验证严格不变量")
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps({
            "schema": CANARY_SCHEMA,
            "cases": [{
                key: value for key, value in case.items()
                if key not in {"expected_special_components",
                               "expected_sphere_triggers"}
            } for case in CANARY_CASES],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.multiseed:
        multiseed_results = []
        aggregate_families = set()
        aggregate_damage_contracts = Counter()
        aggregate_damage_occurrences = Counter()
        aggregate_curses = Counter()
        finale_rosters = set()
        for seed in MULTISEED_SEEDS:
            result, errors, _output = run_multiseed(seed)
            if errors:
                print(f"[MULTISEED-FAIL] seed={seed}")
                for error in errors:
                    print(f"  - {error}")
                return 1
            assert result is not None
            multiseed_results.append(result)
            aggregate_families.update(result["special_families"])
            extended = result["extended_invariants"]
            aggregate_damage_contracts.update(
                extended["damage_checks"]["contract_counts"])
            aggregate_damage_occurrences.update(
                extended["damage_checks"]["occurrence_counts"])
            aggregate_curses.update(
                extended["diversity"]["curse_counts"])
            finale_rosters.add(tuple(result["finale_source_bosses"]))
            print(
                f"[MULTISEED-OK] seed={seed} "
                f"boss={result['absolute_boss_rounds']}/29 "
                f"proxy={result['proxy_components']} "
                f"max_error={result['max_absolute_error_hp']:g}")
        aggregate_errors = []
        for schema in (rb.GENERAL_DAMAGE_CHECK_SCHEMA,
                       rb.STANDARD_DAMAGE_CHECK_SCHEMA):
            if aggregate_damage_contracts[schema] <= 0:
                aggregate_errors.append(
                    f"multiseed lacks DamageCheck schema:{schema}")
        if len(finale_rosters) < 2:
            aggregate_errors.append(
                f"round-30 finale did not vary:{sorted(finale_rosters)}")
        if len(aggregate_curses) < 8:
            aggregate_errors.append(
                f"multiseed curse diversity too narrow:{dict(aggregate_curses)}")
        if aggregate_errors:
            print("[MULTISEED-FAIL] aggregate invariants")
            for error in aggregate_errors:
                print(f"  - {error}")
            return 1
        payload = {
            "schema": CANARY_SCHEMA,
            "mode": "multiseed-strict-invariants",
            "seeds": list(MULTISEED_SEEDS),
            "results": multiseed_results,
            "aggregate_special_families": sorted(aggregate_families),
            "aggregate_damage_contracts": dict(sorted(
                aggregate_damage_contracts.items())),
            "aggregate_damage_occurrences": dict(sorted(
                aggregate_damage_occurrences.items())),
            "aggregate_curse_counts": dict(sorted(aggregate_curses.items())),
            "finale_rosters": [list(roster)
                               for roster in sorted(finale_rosters)],
            "gameplay_verified": False,
        }
        payload["semantic_sha256"] = _canonical_sha(payload)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(
            f"[MULTISEED] 5/5 隔离 dry-run 通过 "
            f"semantic_sha256={payload['semantic_sha256']} "
            "gameplay_verified=false")
        return 0
    results = []
    for case in CANARY_CASES:
        snapshot, errors, _output = run_case(case)
        if errors:
            print(f"[CANARY-FAIL] {case['name']}")
            for error in errors:
                print(f"  - {error}")
            return 1
        assert snapshot is not None
        results.append({
            "name": case["name"], "semantic_sha256": _canonical_sha(snapshot),
            "snapshot": snapshot,
        })
        print(
            f"[CANARY-OK] {case['name']} seed={case['seed']} "
            f"boss={snapshot['strict_summary']['absolute_boss_rounds']}/"
            f"{snapshot['strict_summary']['expected_boss_rounds']} "
            f"semantic_sha256={results[-1]['semantic_sha256']}")
    if args.json:
        print(json.dumps({"schema": CANARY_SCHEMA, "results": results},
                         ensure_ascii=False, indent=2))
    print("[CANARY] 仅临时目录 dry-run；gameplay_verified=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
