#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile an original acquisition-special animation into four client assets.

The compiler owns the locked 34-key-cel / 204-tick Flatomo contract.  It does
not read or copy an official texture, atlas record, frame, or timeline payload.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

import wf_dsl
from .pixelart_compile import _encode_png, _raw_deflate, _validate_prefix


SPECIAL_TICKS = (
    6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 66, 72, 76, 80, 84, 88, 92,
    96, 102, 108, 114, 120, 126, 132, 138, 144, 150, 154, 158, 162, 166,
    170, 174, 204,
)
SPECIAL_SEQUENCES = (
    ("special_land", "pass", 1, 159),
    ("special_pose", "once", 160, 204),
)
SPECIAL_SHEET_SIZE = (512, 256)
SPECIAL_CEL_SIZE = (64, 64)



def _load_cels(
    cel_paths: Sequence[Path | str],
    expected_sha256: Sequence[str] | None,
) -> tuple[list[Image.Image], list[str], list[dict[str, object]]]:
    if len(cel_paths) != len(SPECIAL_TICKS):
        raise ValueError(f"special animation requires exactly 34 cels, got {len(cel_paths)}")
    if expected_sha256 is not None and len(expected_sha256) != len(SPECIAL_TICKS):
        raise ValueError("locked SHA-256 contract must cover exactly 34 cels")

    images: list[Image.Image] = []
    hashes: list[str] = []
    stats: list[dict[str, object]] = []
    for index, raw_path in enumerate(cel_paths):
        path = Path(raw_path)
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256[index]:
            raise ValueError(f"special cel does not match locked SHA-256: index {index}")
        with Image.open(path) as opened:
            if opened.format != "PNG" or opened.size != SPECIAL_CEL_SIZE:
                raise ValueError(f"special cel {index} must be a 64x64 PNG")
            image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        alpha_values = sorted(set(alpha.get_flattened_data()))
        if alpha_values != [0, 255]:
            raise ValueError(f"special cel {index} must use binary alpha")
        bbox = alpha.getbbox()
        if bbox is None:
            raise ValueError(f"special cel {index} is fully transparent")
        images.append(image)
        hashes.append(digest)
        stats.append(
            {
                "index": index,
                "tick": SPECIAL_TICKS[index],
                "size": list(SPECIAL_CEL_SIZE),
                "alpha_bbox": list(bbox),
                "alpha_values": alpha_values,
                "colors_rgba": len(image.getcolors(maxcolors=1_000_000) or []),
            }
        )
    return images, hashes, stats


def _pack_cels(images: Sequence[Image.Image]) -> tuple[Image.Image, list[dict[str, int]]]:
    width, height = SPECIAL_SHEET_SIZE
    x = 1
    y = 1
    row_height = 0
    packed: list[dict[str, int]] = []
    for image in images:
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        left, top, right, bottom = bbox
        crop_width = right - left
        crop_height = bottom - top
        if x + crop_width + 1 > width:
            x = 1
            y += row_height + 2
            row_height = 0
        if y + crop_height + 1 > height:
            raise ValueError("special cels do not fit the locked 512x256 sheet")
        packed.append(
            {
                "x": x,
                "y": y,
                "w": crop_width,
                "h": crop_height,
                "fx": -(96 + left),
                "fy": -(96 + top),
                "fw": 256,
                "fh": 256,
            }
        )
        x += crop_width + 2
        row_height = max(row_height, crop_height)

    sheet = Image.new("RGBA", SPECIAL_SHEET_SIZE, (0, 0, 0, 0))
    for image, geometry in zip(images, packed, strict=True):
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        sheet.alpha_composite(image.crop(bbox), (geometry["x"], geometry["y"]))
    return sheet, packed


def compile_special(
    cel_paths: Sequence[Path | str],
    *,
    target_prefix: str,
    expected_sha256: Sequence[str] | None = None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compile 34 original 64x64 key cels into a complete special asset set."""
    target = _validate_prefix(target_prefix, "target_prefix")
    images, hashes, stats = _load_cels(cel_paths, expected_sha256)
    sheet, packed = _pack_cels(images)

    atlas = [
        {"n": f"{target}/special{tick:04d}", **geometry}
        for tick, geometry in zip(SPECIAL_TICKS, packed, strict=True)
    ]
    frame = {
        "name": f"{target}/special",
        "x": -128,
        "y": -128,
        "scale": 6,
        "smoothing": False,
    }
    timeline = {
        "sequences": [
            {"name": name, "kind": kind, "begin": begin, "end": end}
            for name, kind, begin, end in SPECIAL_SEQUENCES
        ],
        "circles": [],
        "points": [],
        "sounds": [],
    }

    files = {
        f"{target}/special_sprite_sheet.png": _encode_png(sheet),
        f"{target}/special_sprite_sheet.atlas.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(atlas)
        ),
        f"{target}/special.frame.amf3.deflate": _raw_deflate(wf_dsl.encode_amf3(frame)),
        f"{target}/special.timeline.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(timeline)
        ),
    }
    output_sha256 = {
        logical: hashlib.sha256(payload).hexdigest() for logical, payload in files.items()
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": True,
        "target_prefix": target,
        "key_cel_count": len(images),
        "input_sha256": hashes,
        "unique_input_sha256": len(set(hashes)),
        "input_stats": stats,
        "sheet_size": list(SPECIAL_SHEET_SIZE),
        "atlas_records": len(atlas),
        "atlas_ticks": list(SPECIAL_TICKS),
        "sequence_count": len(SPECIAL_SEQUENCES),
        "timeline_ticks": 204,
        "timeline_sequences": [
            {"name": name, "kind": kind, "begin": begin, "end": end}
            for name, kind, begin, end in SPECIAL_SEQUENCES
        ],
        "template_payloads_read": False,
        "template_texture_pixels_copied": False,
        "donor_passthrough_frames": 0,
        "official_passthrough_atlas_records": 0,
        "roots": {"common": sorted(files)},
        "output_sha256": output_sha256,
    }
    return files, report
