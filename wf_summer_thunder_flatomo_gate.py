#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decoded Flatomo half of the summer-thunder skill-follow gate."""

from __future__ import annotations

import hashlib
import io
import zlib
from typing import Any, Mapping

from PIL import Image

import wf_assets
import wf_dsl
from wf_summer_thunder_package_contract import CODE_NAME, PackageAssemblyError


EFFECT_ROOT = f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning"
EFFECT_KEYS = {
    "atlas": f"{EFFECT_ROOT}/fan_lightning.atlas.amf3.deflate",
    "sheet": f"{EFFECT_ROOT}/fan_lightning.png",
    "parts": f"{EFFECT_ROOT}/fan_lightning_wave.parts.amf3.deflate",
    "timeline": f"{EFFECT_ROOT}/fan_lightning_wave.timeline.amf3.deflate",
}


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


def _image(payload: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(wf_assets.png_decode(payload))).convert("RGBA")
        image.load()
        return image
    except Exception as exc:
        raise PackageAssemblyError("Flatomo sheet is not a valid WF PNG") from exc


def _validate_sheet(sheet: Image.Image) -> list[int]:
    if sheet.size != (330, 132):
        raise PackageAssemblyError("Flatomo sheet must be exactly 330x132")
    get_pixels = getattr(sheet, "get_flattened_data", sheet.getdata)
    pixels = list(get_pixels())
    alpha_values = sorted({pixel[3] for pixel in pixels})
    if alpha_values != [0, 255]:
        raise PackageAssemblyError("Flatomo alpha must be binary {0,255}")
    if any(pixel[:3] != (0, 0, 0) for pixel in pixels if pixel[3] == 0):
        raise PackageAssemblyError("Flatomo hidden RGB must be zero")
    alpha = sheet.getchannel("A")
    for x in range(sheet.width):
        if x % 66 in {0, 65} and alpha.crop((x, 0, x + 1, sheet.height)).getbbox():
            raise PackageAssemblyError("Flatomo 1px vertical gutter is not transparent")
    for y in range(sheet.height):
        if y % 66 in {0, 65} and alpha.crop((0, y, sheet.width, y + 1)).getbbox():
            raise PackageAssemblyError("Flatomo 1px horizontal gutter is not transparent")
    return alpha_values


def _atlas_boxes(sheet: Image.Image, atlas: Any) -> tuple[list[str], list[int]]:
    if not isinstance(atlas, list) or len(atlas) != 10:
        raise PackageAssemblyError("Flatomo atlas must contain 10 cells")
    boxes: list[tuple[int, int, int, int]] = []
    names: list[str] = []
    for index, record in enumerate(atlas):
        expected = {
            "n": f"{EFFECT_ROOT}/.gen/fan_lightning_wave/f{index:02d}",
            "w": 64, "h": 64,
            "x": 1 + 66 * (index % 5), "y": 1 + 66 * (index // 5),
        }
        if record != expected:
            raise PackageAssemblyError(f"Flatomo atlas cell geometry drift at {index}")
        names.append(expected["n"])
        crop = sheet.crop(
            (expected["x"], expected["y"], expected["x"] + 64, expected["y"] + 64)
        )
        box = crop.getchannel("A").getbbox()
        if box is None:
            raise PackageAssemblyError(f"Flatomo cell {index} is empty")
        boxes.append(box)
    union = [
        min(box[0] for box in boxes), min(box[1] for box in boxes),
        max(box[2] for box in boxes), max(box[3] for box in boxes),
    ]
    if union != [3, 11, 62, 55]:
        raise PackageAssemblyError("Flatomo union bbox must be x3..61 y11..54")
    return names, union


def _validate_parts(parts: Any, names: list[str]) -> None:
    root_segments = [
        {"s": float(-2147483648 + start), "i": 1,
         "l": [{"m": 255, "t": 11, "r": 1073741824.0}]}
        for start in range(0, 110, 10)
    ]
    wave_segments = [
        {"s": index, "i": index, "l": [{"m": 4351}]} for index in range(10)
    ]
    if not isinstance(parts, dict) or parts.get("i") != [
        {"s": False, "p": name} for name in names
    ]:
        raise PackageAssemblyError("Flatomo image s=false/path closure drift")
    if (
        parts.get("g") != [
            {"t": 111, "s": root_segments}, {"t": 11, "s": wave_segments}
        ]
        or parts.get("m") != [] or parts.get("a") != [1] * 10
        or parts.get("o") != [] or parts.get("c") != [] or parts.get("s") != 1
        or parts.get("t") != [
            {"a": 4096, "b": 0, "c": 0, "d": 4096,
             "x": 0, "y": 0},
            {"a": 4096, "b": 0, "c": 0, "d": 4096,
             "x": -32768, "y": -131072}
        ]
    ):
        raise PackageAssemblyError(
            "Flatomo transform/blend/origin/timing structure drift"
        )


def build_flatomo_gate(effect_files: Mapping[str, bytes]) -> dict[str, Any]:
    if set(effect_files) != set(EFFECT_KEYS.values()):
        raise PackageAssemblyError("Flatomo four-file payload set drift")
    sheet = _image(effect_files[EFFECT_KEYS["sheet"]])
    alpha_values = _validate_sheet(sheet)
    atlas = _decode(effect_files[EFFECT_KEYS["atlas"]], "Flatomo atlas")
    parts = _decode(effect_files[EFFECT_KEYS["parts"]], "Flatomo parts")
    timeline = _decode(effect_files[EFFECT_KEYS["timeline"]], "Flatomo timeline")
    names, union = _atlas_boxes(sheet, atlas)
    _validate_parts(parts, names)
    if timeline != {
        "sequences": [
            {"begin": 1, "end": 111, "name": "neutral", "kind": "once"}
        ],
        "sounds": [], "points": [], "circles": [], "rectangles": [], "matrices": [],
    }:
        raise PackageAssemblyError("Flatomo timeline must be 111 with 110 visible ticks")
    forward = (union[2] - 8) * 6.5
    if forward != 351.0 or forward > 400:
        raise PackageAssemblyError("Flatomo scaled forward extent must remain within Sector")
    return {
        "payload_sha256": {
            logical: _sha256(raw) for logical, raw in sorted(effect_files.items())
        },
        "sheet_size": [330, 132], "frame_count": 10, "cell_size": [64, 64],
        "gutter_pixels": 1, "alpha_values": alpha_values, "hidden_rgb_zero": True,
        "material_alpha": 255, "blend": 0, "colors": [], "image_s": False,
        "origin": [8, 32], "union_bbox": union,
        "effect_scale": 6.5, "forward_scaled_max": forward, "sector_radius": 400,
        "visible_ticks": 110, "timeline_end_exclusive": 111,
    }


__all__ = ["EFFECT_ROOT", "EFFECT_KEYS", "build_flatomo_gate"]
