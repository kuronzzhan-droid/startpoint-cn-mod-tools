#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure payload repairs for the thunder-dragon 1.1.6 hotfix."""

from __future__ import annotations

import copy
import hashlib
import zlib
from collections.abc import Mapping

import wf_dsl
from wf_pixelart_normal_compile import _BASE_TICK_SLOT
from wf_pixelart_special_compat_compile import compile_special_compatibility
from wf_thunder_hotfix_gacha import repair_gacha_contract


_BASE_TICKS = tuple(_BASE_TICK_SLOT)
_GEOMETRY = ("x", "y", "w", "h", "fx", "fy", "fw", "fh")
_EFFECT_ROOT = (
    "battle/effect/skill_unique/cnmod_thunder_dragon_ascendant/"
    "fan_lightning"
)
_EFFECT_PARTS = f"{_EFFECT_ROOT}/fan_lightning_wave.parts.amf3.deflate"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _verify_hashes(
    files: Mapping[str, bytes], expected: Mapping[str, str] | None, label: str
) -> None:
    if expected is None:
        raise ValueError(f"{label} SHA-256 lock is required")
    if set(files) != set(expected):
        raise ValueError(f"{label} SHA-256 lock must cover the exact file set")
    for logical, raw in files.items():
        if not isinstance(logical, str) or not isinstance(raw, bytes):
            raise TypeError(f"{label} files must map logical paths to bytes")
        if _sha(raw) != expected[logical]:
            raise ValueError(f"{label} SHA-256 drift: {logical}")


def _decode_amf(raw: bytes, label: str):
    try:
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    except Exception as exc:
        raise ValueError(f"{label} is not raw-deflate AMF3") from exc


def _encode_amf(tree: object) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    encoded = wf_dsl.encode_amf3(tree)
    return compressor.compress(encoded) + compressor.flush()


def _tick_map(atlas: object, *, prefix: str, label: str) -> dict[int, dict]:
    if not isinstance(atlas, list):
        raise ValueError(f"{label} atlas root must be a list")
    result: dict[int, dict] = {}
    name_prefix = f"{prefix}/pixelart"
    for raw in atlas:
        if not isinstance(raw, dict) or not isinstance(raw.get("n"), str):
            raise ValueError(f"{label} atlas record is invalid")
        name = raw["n"]
        if not name.startswith(name_prefix):
            raise ValueError(f"{label} atlas internal name drift")
        suffix = name[len(name_prefix):]
        if len(suffix) != 4 or not suffix.isdigit():
            raise ValueError(f"{label} atlas tick is malformed")
        tick = int(suffix)
        if tick in result or any(type(raw.get(key)) is not int for key in _GEOMETRY):
            raise ValueError(f"{label} atlas geometry/tick is invalid")
        result[tick] = raw
    return result


def repair_normal_and_special(
    normal_files: Mapping[str, bytes],
    special_files: Mapping[str, bytes],
    donor_template_files: Mapping[str, bytes],
    *,
    source_prefix: str,
    target_prefix: str,
    expected_normal_sha256: Mapping[str, str] | None,
    expected_special_sha256: Mapping[str, str] | None = None,
    expected_template_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, object]]:
    """Repair target movement pivots and regenerate the byte-reuse special alias."""

    normal = dict(normal_files)
    special = dict(special_files)
    donor = dict(donor_template_files)
    normal_keys = {
        f"{target_prefix}/sprite_sheet.png",
        f"{target_prefix}/sprite_sheet.atlas.amf3.deflate",
        f"{target_prefix}/pixelart.frame.amf3.deflate",
        f"{target_prefix}/pixelart.timeline.amf3.deflate",
    }
    special_keys = {
        f"{target_prefix}/special_sprite_sheet.png",
        f"{target_prefix}/special_sprite_sheet.atlas.amf3.deflate",
        f"{target_prefix}/special.frame.amf3.deflate",
        f"{target_prefix}/special.timeline.amf3.deflate",
    }
    donor_keys = {
        f"{source_prefix}/sprite_sheet.png",
        f"{source_prefix}/sprite_sheet.atlas.amf3.deflate",
        f"{source_prefix}/pixelart.frame.amf3.deflate",
        f"{source_prefix}/pixelart.timeline.amf3.deflate",
    }
    if set(normal) != normal_keys or set(special) != special_keys:
        raise ValueError("normal/special four-file contract mismatch")
    if set(donor) != donor_keys:
        raise ValueError("donor template four-file contract mismatch")
    _verify_hashes(normal, expected_normal_sha256, "normal")
    if expected_special_sha256 is not None:
        _verify_hashes(special, expected_special_sha256, "special")
    if expected_template_sha256 is not None:
        _verify_hashes(donor, expected_template_sha256, "donor template")

    atlas_logical = f"{target_prefix}/sprite_sheet.atlas.amf3.deflate"
    donor_atlas_logical = f"{source_prefix}/sprite_sheet.atlas.amf3.deflate"
    atlas = copy.deepcopy(_decode_amf(normal[atlas_logical], "normal atlas"))
    target_by_tick = _tick_map(atlas, prefix=target_prefix, label="normal")
    donor_by_tick = _tick_map(
        _decode_amf(donor[donor_atlas_logical], "donor atlas"),
        prefix=source_prefix,
        label="donor",
    )
    if not all(tick in target_by_tick and tick in donor_by_tick for tick in _BASE_TICKS):
        raise ValueError("normal/donor base tick contract is incomplete")

    tick_two = target_by_tick[2]
    tick_32 = target_by_tick[32]
    for field in ("x", "y", "w", "h"):
        tick_32[field] = tick_two[field]
    for tick in _BASE_TICKS:
        target = target_by_tick[tick]
        donor_record = donor_by_tick[tick]
        if (target["w"], target["h"]) != (
            tick_two["w"], tick_two["h"]
        ) and tick == 32:
            raise ValueError("tick 32 did not reuse the tick 2 crop")
        for field in ("fx", "fy", "fw", "fh"):
            target[field] = donor_record[field]
    repaired_normal = dict(normal)
    repaired_normal[atlas_logical] = _encode_amf(atlas)

    repaired_hashes = {
        logical: _sha(raw) for logical, raw in repaired_normal.items()
    }
    repaired_special, special_report = compile_special_compatibility(
        repaired_normal,
        target_prefix=target_prefix,
        expected_normal_sha256=repaired_hashes,
    )
    unchanged_normal = normal_keys - {atlas_logical}
    if any(repaired_normal[path] != normal[path] for path in unchanged_normal):
        raise ValueError("normal repair changed a non-atlas payload")
    special_atlas = f"{target_prefix}/special_sprite_sheet.atlas.amf3.deflate"
    unchanged_special = special_keys - {special_atlas}
    if any(repaired_special[path] != special[path] for path in unchanged_special):
        raise ValueError("special repair changed a non-atlas payload")
    report: dict[str, object] = {
        "schema_version": 1,
        "status": "repaired_official_dragon_pivots",
        "writes_live": False,
        "official_anchor_records": len(_BASE_TICKS),
        "tick_32_source": "base_0002",
        "changed_normal_paths": [atlas_logical],
        "changed_special_paths": [special_atlas],
        "normal_output_sha256": dict(sorted(repaired_hashes.items())),
        "special_output_sha256": {
            logical: _sha(raw) for logical, raw in sorted(repaired_special.items())
        },
        "special_alias_records": special_report["atlas_records"],
        "special_new_art_pixels": special_report["new_art_pixels"],
    }
    return repaired_normal, repaired_special, report


def repair_travelling_wave_effect(
    effect_files: Mapping[str, bytes],
    *,
    expected_sha256: Mapping[str, str] | None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Move the 8,32 anchor from the root layer to each child image layer."""

    files = dict(effect_files)
    expected_paths = {
        f"{_EFFECT_ROOT}/fan_lightning.png",
        f"{_EFFECT_ROOT}/fan_lightning.atlas.amf3.deflate",
        _EFFECT_PARTS,
        f"{_EFFECT_ROOT}/fan_lightning_wave.timeline.amf3.deflate",
    }
    if set(files) != expected_paths:
        raise ValueError("travelling-wave four-file contract mismatch")
    _verify_hashes(files, expected_sha256, "effect")
    parts = copy.deepcopy(_decode_amf(files[_EFFECT_PARTS], "effect parts"))
    if not isinstance(parts, dict) or len(parts.get("g", [])) != 2:
        raise ValueError("effect parts group contract drift")
    transforms = parts.get("t")
    anchor = {
        "a": 4096, "b": 0, "c": 0, "d": 4096,
        "x": -32768, "y": -131072,
    }
    if transforms != [anchor]:
        raise ValueError("effect source anchor contract drift")
    wave = parts["g"][1]
    segments = wave.get("s") if isinstance(wave, dict) else None
    if (
        not isinstance(segments, list)
        or len(segments) != 10
        or any(segment.get("l") != [{"m": 255}] for segment in segments)
    ):
        raise ValueError("effect child layer contract drift")
    identity = {
        "a": 4096, "b": 0, "c": 0, "d": 4096,
        "x": 0, "y": 0,
    }
    parts["t"] = [identity, anchor]
    for segment in segments:
        segment["l"] = [{"m": 4351}]
    repaired = dict(files)
    repaired[_EFFECT_PARTS] = _encode_amf(parts)
    return repaired, {
        "schema_version": 1,
        "status": "repaired_single_anchor_application",
        "writes_live": False,
        "root_identity_transform": 1,
        "child_anchor_layers": len(segments),
        "changed_paths": [_EFFECT_PARTS],
        "output_sha256": {
            logical: _sha(raw) for logical, raw in sorted(repaired.items())
        },
    }


__all__ = [
    "repair_normal_and_special",
    "repair_travelling_wave_effect",
    "repair_gacha_contract",
]
