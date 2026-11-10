#!/usr/bin/env python3
"""Dedicated HP read/replace channel for ``orochi_ex`` family bosses.

Orochi EX is not a normal ``boss_level``-only boss.  Its first and third
phase HP live in columns 24/25 of ``orochi_ex.orderedmap`` while the middle
bar still uses ``boss_level``.  Keeping this adapter separate makes callers
handle all three bars deliberately instead of silently scaling only one.
"""
from __future__ import annotations

import copy
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


MOD_DIR = Path(__file__).resolve().parent

import wf_mod_tool as core  # noqa: E402


OROCHI_EX_LOGICAL = "master/battle/boss/orochi_ex.orderedmap"
BOSS_LEVEL_LOGICAL = "master/battle/boss/boss_level.orderedmap"
PHASE1_HP_COLUMN = 24
PHASE3_HP_COLUMN = 25
PARENT_COLUMNS = 128
BOSS_LEVEL_COLUMNS = 13
CLIENT_SIGNED_INT_MAX = 2_147_483_647


class OrochiExHpError(ValueError):
    """The dedicated Orochi EX HP channel cannot prove a safe operation."""


def validate_phase_damage_capacity(
    required_hp: float,
    carrier_hp: dict[str, float],
    *,
    label: str,
    primary_carrier: str | None = None,
    required_coverage_ratio: float = 1.0,
) -> dict[str, Any]:
    """Prove that mortal phase actors can supply a phase's required damage.

    Orochi EX advances its fixed phases from damage accumulated on the three
    heads, while every head has an independent ``boss_level`` HP pool.  Raising
    only parent c24/c25 can therefore retire all damage carriers before the
    parent reaches the phase gate.  ``required_coverage_ratio`` lets builders
    reserve a small formatting/runtime margin without changing the gate itself.
    """

    required = _positive(str(required_hp), label=f"{label}.required_hp")
    try:
        coverage = float(required_coverage_ratio)
    except (TypeError, ValueError) as exc:
        raise OrochiExHpError(
            f"{label}.required_coverage_ratio is not numeric"
        ) from exc
    if not math.isfinite(coverage) or coverage < 1.0:
        raise OrochiExHpError(
            f"{label}.required_coverage_ratio must be finite and >= 1"
        )
    if not carrier_hp:
        raise OrochiExHpError(f"{label} has no damage carriers")
    parsed = {
        str(name): _positive(str(value), label=f"{label}.{name}")
        for name, value in carrier_hp.items()
    }
    required_capacity = required * coverage
    total = math.fsum(parsed.values())
    if total + 1e-6 < required_capacity:
        raise OrochiExHpError(
            f"{label} damage carriers total {total:g} HP, below phase gate "
            f"coverage {required_capacity:g}"
        )
    primary_ratio = None
    if primary_carrier is not None:
        primary = str(primary_carrier)
        if primary not in parsed:
            raise OrochiExHpError(
                f"{label} primary damage carrier is missing: {primary}"
            )
        if parsed[primary] + 1e-6 < required_capacity:
            raise OrochiExHpError(
                f"{label} primary carrier {primary} has {parsed[primary]:g} HP, "
                f"below phase gate coverage {required_capacity:g}"
            )
        primary_ratio = parsed[primary] / required
    return {
        "label": label,
        "required_hp": required,
        "required_coverage_ratio": coverage,
        "required_capacity_hp": required_capacity,
        "carrier_hp": parsed,
        "total_carrier_hp": total,
        "total_coverage_ratio": total / required,
        "primary_carrier": primary_carrier,
        "primary_carrier_hp": (
            parsed[str(primary_carrier)]
            if primary_carrier is not None else None
        ),
        "primary_coverage_ratio": primary_ratio,
    }


@dataclass(frozen=True, slots=True)
class FixedPhaseHp:
    code: str
    requested_level: int
    selected_level: int
    phase1_hp: float
    phase3_hp: float

    @property
    def total(self) -> float:
        return math.fsum((self.phase1_hp, self.phase3_hp))

    def evidence(self) -> dict[str, Any]:
        return dict(asdict(self), total_fixed_hp=self.total)


def _cells(leaf: str | bytes | bytearray, *, label: str, size: int) -> list[str]:
    if isinstance(leaf, (bytes, bytearray)):
        text = bytes(leaf).decode("utf-8")
    elif isinstance(leaf, str):
        text = leaf
    else:
        raise OrochiExHpError(f"{label} is not a CSV leaf")
    rows = core.read_csv_lines(text)
    if len(rows) != 1 or len(rows[0]) != size:
        raise OrochiExHpError(
            f"{label} has an invalid CSV shape: "
            f"rows={len(rows)} columns={len(rows[0]) if rows else 0}"
        )
    return rows[0]


def _leaf(row: list[str]) -> str:
    return core.write_csv_lines([row])


def _positive(value: str, *, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise OrochiExHpError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise OrochiExHpError(f"{label} must be finite and positive: {parsed!r}")
    return parsed


def _positive_client_int(value: str | int | float, *, label: str) -> int:
    """Parse one ActionScript ``int`` HP field without allowing wraparound."""
    try:
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError(value)
            parsed = int(value)
        else:
            parsed = int(str(value).strip(), 10)
    except (TypeError, ValueError) as exc:
        raise OrochiExHpError(
            f"{label} is not an integer client HP value: {value!r}"
        ) from exc
    if parsed <= 0 or parsed > CLIENT_SIGNED_INT_MAX:
        raise OrochiExHpError(
            f"{label} exceeds signed int32 HP range: {parsed} "
            f"(allowed 1..{CLIENT_SIGNED_INT_MAX})"
        )
    return parsed


def _factor(value: float, *, label: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise OrochiExHpError(f"{label} must be finite and positive: {parsed!r}")
    return parsed


def select_parent_row(
    dedicated: dict[str, Any], code: str, level: int,
) -> tuple[int, list[str]]:
    """Select the first dedicated row whose numeric key is ``>= level``."""
    node = dedicated.get(str(code))
    if not isinstance(node, dict):
        raise OrochiExHpError(f"{code} is missing from the Orochi EX table")
    requested = int(level)
    eligible = sorted(
        int(key) for key in node
        if str(key).isdigit() and int(key) >= requested
    )
    if not eligible:
        raise OrochiExHpError(f"{code} has no dedicated row for level {requested}")
    selected = eligible[0]
    return selected, _cells(
        node[str(selected)], label=f"orochi_ex[{code}][{selected}]",
        size=PARENT_COLUMNS,
    )


def read_fixed_phase_hp(
    dedicated: dict[str, Any], code: str, level: int,
) -> FixedPhaseHp:
    """Read the two HP bars that bypass ordinary quest HP correction."""
    selected, row = select_parent_row(dedicated, code, level)
    return FixedPhaseHp(
        code=str(code),
        requested_level=int(level),
        selected_level=selected,
        phase1_hp=_positive_client_int(
            row[PHASE1_HP_COLUMN], label=f"{code}.phase1_health_point"
        ),
        phase3_hp=_positive_client_int(
            row[PHASE3_HP_COLUMN], label=f"{code}.phase3_health_point"
        ),
    )


def phase_threshold_icon_contract(
    phase1_hp: float, middle_hp: float, phase3_hp: float,
) -> dict[str, Any]:
    """Prove the client phase thresholds and their two-digit icon frames.

    ``OrochiExValues`` parses phase 1/3 through ``Std.parseInt``.  The battle
    then derives two fractional thresholds and passes ``int(ratio * 100)`` to
    ``PhaseThresholdIcon``.  A wrapped negative fixed phase therefore becomes
    an invalid MovieClip frame.  This receipt keeps that client contract in the
    build gate while deliberately retaining the lack of real-device coverage.
    """
    phase1 = _positive_client_int(phase1_hp, label="phase1_health_point")
    phase3 = _positive_client_int(phase3_hp, label="phase3_health_point")
    middle = _positive(str(middle_hp), label="middle_health_point")
    total = math.fsum((float(phase1), middle, float(phase3)))
    if not math.isfinite(total) or total <= 0:
        raise OrochiExHpError(f"Orochi EX total HP is invalid: {total!r}")
    thresholds = (
        math.fsum((middle, float(phase3))) / total,
        float(phase3) / total,
    )
    if not all(math.isfinite(value) and 0 < value < 1
               for value in thresholds):
        raise OrochiExHpError(
            f"Orochi EX phase threshold is outside (0,1): {thresholds!r}"
        )
    icon_numbers = tuple(int(value * 100) for value in thresholds)
    icon_frames = tuple((number // 10 % 10, number % 10)
                        for number in icon_numbers)
    if (not all(0 <= number <= 99 for number in icon_numbers)
            or not all(0 <= frame <= 9
                       for pair in icon_frames for frame in pair)):
        raise OrochiExHpError(
            "Orochi EX PhaseThresholdIcon frame is outside 0..9:"
            f"numbers={icon_numbers},frames={icon_frames}"
        )
    return {
        "client_contract": (
            "client-1.8.1:OrochiExValues.Std.parseInt(c24,c25)+"
            "OrochiEx.init.thresholds+PhaseThresholdIcon.setNumber"
        ),
        "phase1_hp": phase1,
        "middle_hp": middle,
        "phase3_hp": phase3,
        "total_hp": total,
        "phase1_hp_threshold": thresholds[0],
        "phase2_hp_threshold": thresholds[1],
        "icon_numbers": icon_numbers,
        "icon_frames_tens_ones": icon_frames,
        "signed_int32_verified": True,
        "static_verified": True,
        "runtime_simulated": False,
        "gameplay_verified": False,
    }


def hp_components(profile: FixedPhaseHp, middle_hp: float, *,
                  middle_evidence_kind: str = "absolute") -> tuple[dict[str, Any], ...]:
    """Return three auditable components with their quest-correction policy."""
    middle = _positive(str(middle_hp), label=f"{profile.code}.middle_hp")
    return (
        {
            "code": profile.code,
            "kind": "orochi_ex_phase1",
            "phase": 1,
            "evidence_kind": "absolute",
            "apply_quest_hp_correction": False,
            "native_hp": profile.phase1_hp,
            "selected_level": profile.selected_level,
        },
        {
            "code": profile.code,
            "kind": "orochi_ex_middle",
            "phase": 2,
            "evidence_kind": str(middle_evidence_kind),
            "apply_quest_hp_correction": True,
            "native_hp": middle,
            "selected_level": profile.selected_level,
        },
        {
            "code": profile.code,
            "kind": "orochi_ex_phase3",
            "phase": 3,
            "evidence_kind": "absolute",
            "apply_quest_hp_correction": False,
            "native_hp": profile.phase3_hp,
            "selected_level": profile.selected_level,
        },
    )


def _scaled_text(value: str, factor: float, *, label: str) -> str:
    scaled = _positive_client_int(value, label=label) * factor
    if not math.isfinite(scaled) or scaled <= 0:
        raise OrochiExHpError(f"{label} scaled to an invalid value: {scaled!r}")
    rounded = int(round(scaled))
    if rounded <= 0:
        raise OrochiExHpError(f"{label} rounded to a non-positive value: {rounded}")
    if rounded > CLIENT_SIGNED_INT_MAX:
        raise OrochiExHpError(
            f"{label} scaled beyond signed int32 HP range: {rounded} "
            f"(max {CLIENT_SIGNED_INT_MAX})"
        )
    return str(rounded)


def _scaled_number_text(value: str, factor: float, *, label: str) -> str:
    """Scale a numeric coefficient without quantizing it to an integer.

    Dedicated phase HP columns are integer health points, but ``boss_level.c2``
    is a floating-point coefficient (the general Boss adapter already writes
    it as such).  Rounding c2 to an integer can miss a strict final HP target by
    almost one full client curve step.
    """
    scaled = _positive(value, label=label) * factor
    if not math.isfinite(scaled) or scaled <= 0:
        raise OrochiExHpError(f"{label} scaled to an invalid value: {scaled!r}")
    rendered = format(scaled, ".12g")
    if _positive(rendered, label=label) <= 0:
        raise OrochiExHpError(f"{label} formatted to a non-positive value")
    return rendered


def build_scaled_hp_rows(
    dedicated: dict[str, Any], boss_level: dict[str, Any],
    source_code: str, target_code: str, *,
    fixed_phase_scale: float, middle_scale: float,
    allow_replace: bool = False,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Build, but do not install, a complete dedicated+middle HP replacement.

    The returned dedicated node and ``boss_level`` leaf are safe to install
    together.  Callers cloning to a new code still own zone/head references;
    this function deliberately covers only the three HP bars.
    """
    source = str(source_code)
    target = str(target_code)
    fixed_factor = _factor(fixed_phase_scale, label="fixed_phase_scale")
    middle_factor = _factor(middle_scale, label="middle_scale")
    source_node = dedicated.get(source)
    if not isinstance(source_node, dict) or not source_node:
        raise OrochiExHpError(f"source dedicated row is missing: {source}")
    if target in dedicated and not allow_replace:
        raise OrochiExHpError(f"target dedicated row already exists: {target}")

    level_leaf = boss_level.get(source)
    level_row = _cells(
        level_leaf, label=f"boss_level[{source}]", size=BOSS_LEVEL_COLUMNS
    )
    if level_row[0] != "0":
        raise OrochiExHpError(
            f"boss_level[{source}] is not Hit HP and cannot scale c2 safely"
        )

    target_node = copy.deepcopy(source_node)
    phase_before: dict[str, tuple[int, int]] = {}
    phase_after: dict[str, tuple[int, int]] = {}
    for level_key, leaf in target_node.items():
        row = _cells(
            leaf, label=f"orochi_ex[{source}][{level_key}]", size=PARENT_COLUMNS
        )
        before = (
            _positive_client_int(
                row[PHASE1_HP_COLUMN], label=f"{source}.phase1"),
            _positive_client_int(
                row[PHASE3_HP_COLUMN], label=f"{source}.phase3"),
        )
        row[PHASE1_HP_COLUMN] = _scaled_text(
            row[PHASE1_HP_COLUMN], fixed_factor, label=f"{source}.phase1"
        )
        row[PHASE3_HP_COLUMN] = _scaled_text(
            row[PHASE3_HP_COLUMN], fixed_factor, label=f"{source}.phase3"
        )
        target_node[level_key] = _leaf(row)
        phase_before[str(level_key)] = before
        phase_after[str(level_key)] = (
            int(row[PHASE1_HP_COLUMN]), int(row[PHASE3_HP_COLUMN])
        )

    old_middle = _positive(level_row[2], label=f"boss_level[{source}].c2")
    level_row[2] = _scaled_number_text(
        level_row[2], middle_factor, label=f"boss_level[{source}].c2"
    )
    report = {
        "source_code": source,
        "target_code": target,
        "fixed_phase_scale": fixed_factor,
        "middle_scale": middle_factor,
        "phase_hp_before": phase_before,
        "phase_hp_after": phase_after,
        "middle_c2_before": old_middle,
        "middle_c2_after": float(level_row[2]),
    }
    return target_node, _leaf(level_row), report


def replace_hp_profile(
    dedicated: dict[str, Any], boss_level: dict[str, Any], code: str, *,
    fixed_phase_scale: float, middle_scale: float,
) -> dict[str, Any]:
    """Atomically replace all three HP channels of one existing code in memory."""
    node, level_leaf, report = build_scaled_hp_rows(
        dedicated, boss_level, code, code,
        fixed_phase_scale=fixed_phase_scale,
        middle_scale=middle_scale,
        allow_replace=True,
    )
    dedicated[str(code)] = node
    boss_level[str(code)] = level_leaf
    return report
