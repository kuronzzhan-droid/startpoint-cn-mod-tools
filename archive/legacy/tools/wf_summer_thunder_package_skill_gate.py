#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orchestrate and bind exact ActionDSL plus Flatomo skill-follow evidence."""

from __future__ import annotations

import math
from typing import Any, Mapping

from wf_summer_thunder_flatomo_gate import EFFECT_KEYS, build_flatomo_gate
from wf_summer_thunder_package_contract import PackageAssemblyError
from wf_summer_thunder_skill_action_gate import ACTION_SHA256, build_action_gate


def pending_skill_follow_gate() -> dict[str, Any]:
    return {
        "status": "pending_exact_contract",
        "package_manifest_eligible": False,
        "writes_live": False,
    }


def build_skill_follow_gate(
    action_files: Mapping[str, bytes], effect_files: Mapping[str, bytes]
) -> dict[str, Any]:
    """Decode both payload families and return the only eligible gate record."""

    return {
        "schema_version": 1,
        "status": "accepted_exact_runtime_follow_contract",
        "package_manifest_eligible": True,
        "action": build_action_gate(action_files),
        "flatomo": build_flatomo_gate(effect_files),
        "writes_live": False,
    }


def validate_skill_follow_gate(gate: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate the exact evidence shape; payload equality is checked separately."""

    if not isinstance(gate, Mapping):
        raise PackageAssemblyError("skill-follow exact contract is absent")
    if set(gate) != {
        "schema_version", "status", "package_manifest_eligible",
        "action", "flatomo", "writes_live",
    }:
        raise PackageAssemblyError("skill-follow exact contract fields drift")
    action = gate.get("action")
    flatomo = gate.get("flatomo")
    if (
        gate.get("schema_version") != 1
        or gate.get("status") != "accepted_exact_runtime_follow_contract"
        or gate.get("package_manifest_eligible") is not True
        or gate.get("writes_live") is not False
        or not isinstance(action, Mapping)
        or not isinstance(flatomo, Mapping)
    ):
        raise PackageAssemblyError("skill-follow exact contract is not eligible")
    expected_action = {
        "show_effect": {
            "subject": -18, "coordinate": "AB", "offset": [0, 0],
            "rotation": -math.pi / 2, "tracking_position": True,
            "tracking_direction": False, "scale": 6.5,
        },
        "hit_area": {
            "subject": -18, "coordinate": "AB", "offset": [0, 0],
            "rotation": 0.0, "tracking_position": True,
            "tracking_direction": False, "sector_radius": 400,
            "sector_angle": math.pi / 2, "lifetime": 110, "max_hits": 55,
        },
    }
    for name, expected in expected_action.items():
        if action.get(name) != expected:
            raise PackageAssemblyError(f"skill-follow exact contract {name} drift")
    if action.get("payload_sha256") != ACTION_SHA256:
        raise PackageAssemblyError("skill-follow exact contract ActionDSL identity drift")
    expected_flatomo = {
        "sheet_size": [330, 132], "frame_count": 10, "cell_size": [64, 64],
        "gutter_pixels": 1, "alpha_values": [0, 255], "hidden_rgb_zero": True,
        "material_alpha": 255, "blend": 0, "colors": [], "image_s": False,
        "origin": [8, 32], "union_bbox": [3, 11, 62, 55],
        "effect_scale": 6.5, "forward_scaled_max": 351.0, "sector_radius": 400,
        "visible_ticks": 110, "timeline_end_exclusive": 111,
    }
    for name, expected in expected_flatomo.items():
        if flatomo.get(name) != expected:
            raise PackageAssemblyError(f"skill-follow exact contract Flatomo {name} drift")
    hashes = flatomo.get("payload_sha256")
    if (
        not isinstance(hashes, Mapping)
        or set(hashes) != set(EFFECT_KEYS.values())
        or any(
            not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in hashes.values()
        )
    ):
        raise PackageAssemblyError("skill-follow exact contract Flatomo identity drift")
    return dict(gate)


def validate_skill_follow_assets(
    action_files: Mapping[str, bytes],
    effect_files: Mapping[str, bytes],
    gate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Recompute the gate from packaged bytes and require byte-for-byte evidence."""

    claimed = validate_skill_follow_gate(gate)
    actual = build_skill_follow_gate(action_files, effect_files)
    if claimed != actual:
        raise PackageAssemblyError("skill-follow exact contract/payload readback drift")
    return actual


def validate_skill_follow_roots(
    roots: Mapping[str, Mapping[str, bytes]],
    gate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Extract the two DSL and four effect payloads from package roots."""

    common = roots.get("common")
    if not isinstance(common, Mapping):
        raise PackageAssemblyError("skill-follow common root is absent")
    action_paths = set(ACTION_SHA256)
    effect_paths = set(EFFECT_KEYS.values())
    missing = (action_paths | effect_paths) - set(common)
    if missing:
        raise PackageAssemblyError(
            f"skill-follow packaged payloads are missing: {sorted(missing)}"
        )
    return validate_skill_follow_assets(
        {logical: common[logical] for logical in action_paths},
        {logical: common[logical] for logical in effect_paths},
        gate,
    )


__all__ = [
    "pending_skill_follow_gate", "build_skill_follow_gate",
    "validate_skill_follow_gate", "validate_skill_follow_assets",
    "validate_skill_follow_roots",
]
