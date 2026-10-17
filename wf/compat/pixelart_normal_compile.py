#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure compiler for a complete original normal character sprite set.

The template contributes the validated frame/timeline contract and the base
movement cels' pivot geometry.  No template texture pixels are copied.
"""
from __future__ import annotations

import copy
import hashlib
from collections.abc import Mapping
from pathlib import Path

from PIL import Image

import wf_dsl
from .pixelart_compile import _decode_template, _encode_png, _raw_deflate, _validate_prefix


TEMPLATE_TICKS = (
    2, 8, 14, 20, 26, 32, 38, 44, 50,
    56, 62, 68, 74, 80, 86, 92, 98, 104, 110,
    116, 122, 152, 158,
    *range(159, 219), 225,
    255, 275, 285, 305, 335, 355, 386,
    *range(387, 427), 428,
)

FULL_NORMAL_SLOT_SIZES = {
    "base_0002": (17, 18),
    "base_0008": (17, 19),
    "base_0014": (17, 19),
    "base_0026": (17, 19),
    "base_0038": (17, 17),
    "base_0050": (17, 17),
    **{f"skill_{index}": (64, 64) for index in range(9)},
    **{f"kachidoki_{index}": (32, 32) for index in range(5)},
    **{f"collapse_{index}": (32, 32) for index in range(9)},
    **{f"ghost_{index}": (32, 32) for index in range(3)},
}


_OUTPUT_TICKS = tuple(sorted((*TEMPLATE_TICKS, 51, 111)))
_BASE_TICK_SLOT = {
    2: "base_0002",
    8: "base_0008",
    14: "base_0014",
    20: "base_0008",
    26: "base_0026",
    32: "base_0002",
    38: "base_0038",
    44: "base_0002",
    50: "base_0050",
}
_SKILL_TICK_INDEX = {
    51: 0, 56: 1, 62: 2, 68: 3, 74: 4, 80: 5,
    86: 6, 92: 7, 98: 8, 104: 8, 110: 8,
}
_KACHIDOKI_TICK_INDEX = {111: 0, 116: 1, 122: 2, 152: 3, 158: 4}
_GHOST_NEUTRAL_TICK_INDEX = {
    255: 1, 275: 0, 285: 1, 305: 2, 335: 1, 355: 0, 386: 1,
}


def _load_slots(
    cel_paths: Mapping[str, Path | str],
    expected_sha256: Mapping[str, str] | None,
) -> tuple[dict[str, Image.Image], dict[str, str], dict[str, dict[str, object]]]:
    expected_slots = set(FULL_NORMAL_SLOT_SIZES)
    if set(cel_paths) != expected_slots:
        missing = sorted(expected_slots.difference(cel_paths))
        extra = sorted(set(cel_paths).difference(expected_slots))
        raise ValueError(f"full normal slot contract mismatch: missing={missing}, extra={extra}")
    if expected_sha256 is not None and set(expected_sha256) != expected_slots:
        raise ValueError("locked SHA-256 contract must cover the exact full normal slot set")

    images: dict[str, Image.Image] = {}
    hashes: dict[str, str] = {}
    stats: dict[str, dict[str, object]] = {}
    for slot, expected_size in FULL_NORMAL_SLOT_SIZES.items():
        path = Path(cel_paths[slot])
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256[slot]:
            raise ValueError(f"full normal slot does not match locked SHA-256: {slot}")
        with Image.open(path) as opened:
            if opened.format != "PNG" or opened.size != expected_size:
                raise ValueError(
                    f"full normal slot {slot} must be {expected_size[0]}x{expected_size[1]} PNG"
                )
            image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        alpha_values = set(alpha.get_flattened_data())
        allowed_alpha = {0, 51, 255} if slot.startswith("base_") else {0, 255}
        if not alpha_values or not alpha_values.issubset(allowed_alpha):
            raise ValueError(f"full normal slot violates allowed alpha contract: {slot}")
        bbox = alpha.getbbox()
        if bbox is None:
            raise ValueError(f"full normal slot is fully transparent: {slot}")
        images[slot] = image
        hashes[slot] = digest
        stats[slot] = {
            "size": list(expected_size),
            "alpha_bbox": list(bbox),
            "alpha_values": sorted(alpha_values),
            "colors_rgba": len(image.getcolors(maxcolors=1_000_000) or []),
        }
    return images, hashes, stats


def _pack_slots(images: Mapping[str, Image.Image]) -> tuple[Image.Image, dict[str, dict[str, int]]]:
    width = 256
    x = 1
    y = 1
    row_height = 0
    packed: dict[str, dict[str, int]] = {}
    for slot in FULL_NORMAL_SLOT_SIZES:
        image = images[slot]
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        left, top, right, bottom = bbox
        crop_width = right - left
        crop_height = bottom - top
        if x + crop_width + 1 > width:
            x = 1
            y += row_height + 2
            row_height = 0
        offset_x = (256 - image.width) // 2
        offset_y = (256 - image.height) // 2
        packed[slot] = {
            "x": x,
            "y": y,
            "w": crop_width,
            "h": crop_height,
            "fx": -(offset_x + left),
            "fy": -(offset_y + top),
            "fw": 256,
            "fh": 256,
        }
        x += crop_width + 2
        row_height = max(row_height, crop_height)
    height = y + row_height + 1
    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for slot in FULL_NORMAL_SLOT_SIZES:
        image = images[slot]
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        geometry = packed[slot]
        sheet.alpha_composite(image.crop(bbox), (geometry["x"], geometry["y"]))
    return sheet, packed


def _progress_index(value: int, begin: int, end: int, maximum: int) -> int:
    return min(maximum, max(0, round((value - begin) * maximum / (end - begin))))


def _slot_for_tick(tick: int) -> str:
    if tick in _BASE_TICK_SLOT:
        return _BASE_TICK_SLOT[tick]
    if tick in _SKILL_TICK_INDEX:
        return f"skill_{_SKILL_TICK_INDEX[tick]}"
    if tick in _KACHIDOKI_TICK_INDEX:
        return f"kachidoki_{_KACHIDOKI_TICK_INDEX[tick]}"
    if 159 <= tick <= 200:
        return f"collapse_{_progress_index(tick, 159, 200, 8)}"
    ghost_raise_ticks = (*range(201, 219), 225)
    if tick in ghost_raise_ticks:
        index = ghost_raise_ticks.index(tick)
        return f"ghost_{round(index * 2 / (len(ghost_raise_ticks) - 1))}"
    if tick in _GHOST_NEUTRAL_TICK_INDEX:
        return f"ghost_{_GHOST_NEUTRAL_TICK_INDEX[tick]}"
    if 387 <= tick <= 428:
        return f"collapse_{8 - _progress_index(tick, 387, 428, 8)}"
    raise ValueError(f"full normal atlas tick has no original slot mapping: {tick}")


def compile_full_normal(
    template_files: Mapping[str, bytes],
    cel_paths: Mapping[str, Path | str],
    *,
    source_prefix: str,
    target_prefix: str,
    expected_sha256: Mapping[str, str] | None = None,
    expected_template_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compile all nine normal sequences from original target-character cels."""
    source = _validate_prefix(source_prefix, "source_prefix")
    target = _validate_prefix(target_prefix, "target_prefix")
    if source == target:
        raise ValueError("source_prefix and target_prefix must differ")

    images, hashes, stats = _load_slots(cel_paths, expected_sha256)
    _, template_atlas, frame, timeline = _decode_template(
        template_files, source, expected_template_sha256
    )
    ticks = tuple(
        int(str(entry["n"]).rsplit("pixelart", 1)[1]) for entry in template_atlas
    )
    if ticks != TEMPLATE_TICKS:
        raise ValueError("template atlas must contain the locked 132 records and tick order")

    sheet, packed = _pack_slots(images)
    tick_slots = {tick: _slot_for_tick(tick) for tick in _OUTPUT_TICKS}
    template_by_tick = {
        int(str(entry["n"]).rsplit("pixelart", 1)[1]): entry
        for entry in template_atlas
    }
    atlas = []
    for tick in _OUTPUT_TICKS:
        geometry = dict(packed[tick_slots[tick]])
        if tick in _BASE_TICK_SLOT:
            donor = template_by_tick[tick]
            if (geometry["w"], geometry["h"]) != (donor["w"], donor["h"]):
                raise ValueError(f"base donor crop geometry drift at tick {tick}")
            for key in ("fx", "fy", "fw", "fh"):
                geometry[key] = donor[key]
        atlas.append({"n": f"{target}/pixelart{tick:04d}", **geometry})
    if len(atlas) != 134 or len({entry["n"] for entry in atlas}) != 134:
        raise ValueError("compiled full normal atlas must contain 134 unique records")

    target_frame = copy.deepcopy(frame)
    target_frame["name"] = f"{target}/pixelart"
    target_timeline = copy.deepcopy(timeline)
    sequences = target_timeline.get("sequences", [])
    if len(sequences) != 9 or max(entry["end"] for entry in sequences) != 428:
        raise ValueError("template timeline must close nine sequences at tick 428")

    files = {
        f"{target}/sprite_sheet.png": _encode_png(sheet),
        f"{target}/sprite_sheet.atlas.amf3.deflate": _raw_deflate(wf_dsl.encode_amf3(atlas)),
        f"{target}/pixelart.frame.amf3.deflate": _raw_deflate(wf_dsl.encode_amf3(target_frame)),
        f"{target}/pixelart.timeline.amf3.deflate": _raw_deflate(wf_dsl.encode_amf3(target_timeline)),
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": True,
        "target_prefix": target,
        "input_sha256": hashes,
        "input_stats": stats,
        "template_contract_only": True,
        "template_texture_pixels_copied": False,
        "official_passthrough_actions": [],
        "official_passthrough_atlas_records": 0,
        "official_anchor_records": len(_BASE_TICK_SLOT),
        "sequence_count": 9,
        "timeline_ticks": 428,
        "atlas_records": len(atlas),
        "atlas_tick_slots": {str(tick): slot for tick, slot in tick_slots.items()},
        "sheet_size": list(sheet.size),
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest() for logical, payload in files.items()
        },
    }
    return files, report
