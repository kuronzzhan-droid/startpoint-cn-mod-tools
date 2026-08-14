#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decoded ActionDSL half of the summer-thunder skill-follow gate."""

from __future__ import annotations

import hashlib
import math
import zlib
from typing import Any, Iterable, Mapping

import wf_dsl
from wf_summer_thunder_package_contract import CODE_NAME, PackageAssemblyError


ACTION_SHA256 = {
    (
        "battle/action/skill/action/rare5/"
        f"{CODE_NAME}${CODE_NAME}_1.action.dsl.amf3.deflate"
    ): "84862c8e962e56c14685183aae11437b0404234a4af3a8584adf5aca0155add2",
    (
        "battle/action/skill/action/rare5/"
        f"{CODE_NAME}${CODE_NAME}_2.action.dsl.amf3.deflate"
    ): "84862c8e962e56c14685183aae11437b0404234a4af3a8584adf5aca0155add2",
}
EFFECT_PATH = (
    f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/fan_lightning_wave"
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decode(raw: bytes, label: str) -> Any:
    try:
        decoder = zlib.decompressobj(-15)
        decoded = decoder.decompress(raw) + decoder.flush()
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("raw-deflate framing drift")
        return wf_dsl.parse_dsl(decoded)["tree"]
    except Exception as exc:
        raise PackageAssemblyError(f"{label} is not exact raw-deflate AMF3") from exc


def _commands(value: Any) -> Iterable[list[Any]]:
    if isinstance(value, list):
        if len(value) == 2 and value[0] == "Command" and isinstance(value[1], list):
            yield value[1]
        for item in value:
            yield from _commands(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _commands(item)


def _one_command(tree: Any, name: str) -> list[Any]:
    matches = [command for command in _commands(tree) if command[:1] == [name]]
    if len(matches) != 1:
        raise PackageAssemblyError(f"ActionDSL must contain exactly one {name}")
    return matches[0]


def build_action_gate(action_files: Mapping[str, bytes]) -> dict[str, Any]:
    if set(action_files) != set(ACTION_SHA256):
        raise PackageAssemblyError("ActionDSL two-level payload set drift")
    for logical, raw in sorted(action_files.items()):
        tree = _decode(raw, logical)
        effect = _one_command(tree, "ShowEffect")
        hit = _one_command(tree, "CreateHitArea")
        if len(effect) != 13:
            raise PackageAssemblyError("ShowEffect field count drift")
        if effect[3] != -18 or effect[6] != ["AB"] or effect[7:9] != [0, 0]:
            raise PackageAssemblyError("ShowEffect ball anchor/coordinate drift")
        if effect[9] != -math.pi / 2:
            raise PackageAssemblyError("ShowEffect rotation must be -pi/2")
        if effect[10] is not True or effect[11] is not False:
            raise PackageAssemblyError("ShowEffect tracking position/direction drift")
        if effect[12] != ["Some", [{"min": 6.5, "max": 6.5}]]:
            raise PackageAssemblyError("ShowEffect scale must be exactly 6.5")
        if (
            effect[2] != ["SpecifyEffectDirectly", EFFECT_PATH]
            or effect[4] != ["ForesideOfCharacter"]
            or effect[5] != ["PlayOnlyFirstSequence"]
        ):
            raise PackageAssemblyError("ShowEffect runtime target/playback drift")
        if len(hit) < 16 or hit[2] != -18 or hit[3] != ["AB"] or hit[4:6] != [0, 0]:
            raise PackageAssemblyError("HitArea ball anchor/coordinate drift")
        if hit[6] != 0.0:
            raise PackageAssemblyError("HitArea rotation must remain exactly 0")
        if hit[7] is not True or hit[8] is not False:
            raise PackageAssemblyError("HitArea tracking position/direction drift")
        if hit[9] != [
            "Sector", [{"min": 400, "max": 400}],
            [{"min": math.pi / 2, "max": math.pi / 2}],
        ]:
            raise PackageAssemblyError("HitArea Sector(400,pi/2) drift")
        if (
            hit[13] != ["SpecifyHitAreaLifetimeDirectly", 110]
            or hit[14] != ["CalculatedUsingMaxNumOfHits", 55]
            or hit[15] != ["Some", [{"min": 55, "max": 55}]]
        ):
            raise PackageAssemblyError("HitArea lifetime/max55 drift")
    hashes = {logical: _sha256(raw) for logical, raw in sorted(action_files.items())}
    if hashes != ACTION_SHA256:
        raise PackageAssemblyError("ActionDSL literal identity drift")
    return {
        "payload_sha256": hashes,
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


__all__ = ["ACTION_SHA256", "EFFECT_PATH", "build_action_gate"]
