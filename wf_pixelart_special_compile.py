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
from wf_pixelart_compile import (
    SUMMER_THUNDER_TARGET,
    _encode_png,
    _raw_deflate,
    _validate_prefix,
)


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

SUMMER_THUNDER_SPECIAL_SHA256 = (
    "7d41f7c1b8ea0ce3c33235bbd1341a326e198ed76214826a3471a2bca76f160b",
    "78f7431d629eb68e1705f07bc0c600ed12e8ff11438d13973b14d26ea2fe2030",
    "41ff5ca9356cf9207a951b0f664dbfac124ad45983a4a56cf9e1995d0fd3e3e9",
    "743762c768e4a369b5ed3bb2fd8d7f903236620053af0ce0640b9f44bf723bd9",
    "5b3aad54472f703e7d81aa3c243a13efd6f603836630806551f1c2e47306d5cf",
    "06055a1e624c3373815ac3340b3a28e0f9076fea0fe8feaabcc26286dc081987",
    "d541b6d7c96c7b6efefcb3742b3ec1cde49ff04e1f16fc751d0c0e88742c324b",
    "0af474d15c18d83dc0bc46b29faf23386ee7738f6ecb3758b22c043ae2dd07c3",
    "86ee0e4742cbb1d10e9dde771cdef8d2514c8a27d1d01e3051240d3bb5447630",
    "c372036ac949616c14c5562c085174d375416bb26b892be138c7ed9accc43aa3",
    "3362a10585b160baa4ecad821055b08d272f64aa0bc0a7ffc55ae0ba57b9acdc",
    "4e44314bfbcad24bcd34ee6476a5fcc033a786380beeba2535f6d270974b528e",
    "4d64b2ceca7b022a3d831764e3eed2112d994b704770091a9b553e15668a1e6a",
    "830759535521e6b0ce2e229b1c39e6ec71063a148437d498e52e034a9bb2bd1b",
    "00b374b956ed18afeb7f2bbe1e49eb47113b962d26a2b291a19b011f6b3f4813",
    "caefbe4f82fd51803ea7aec2c44878be93124741afd4c8f9d788d028a3620897",
    "07e2b018949bbae9a613d40a70f7775c5b754e88a4a54e449b8518093be4e02d",
    "d19fc6ae8b908d3d55f9bc87c9c262fe9388eb0cdd8050ace9ffea44055b874a",
    "33308eab384765f6511063398e76d1e5874e313ddaf2b5aba6aa7a08f54a1b47",
    "62107025acd0a6f11901d63c13a1be8cd2c72923100a228bc60b6fbc062313d6",
    "3a2fddc4dd83a7d59b70377eb9cf395a1f09697fc2eee591edef931231ad4b84",
    "455496bf43f33dd3197a018b68739693d21b0a8b222992c2abf932907109f316",
    "f0035f6a9a18f29526301453332a5554b5e680d85c4a87717b98a129ff3db32c",
    "07d01d74ffb957fbbe80ac44ae0b937231e48e10ad49fa8b79ff4f337e73b84e",
    "6e82275c41ebb02b811b3a7a8a5d96b993562215e6ea064912a39ed738060e7d",
    "ef071e660eb842640837cbce886a7422d517143fa6e3f3197ca4a016c1cdb31f",
    "b515664b139914caa94df1519d146b83a21ba94ae2ff3c29a58db56f3703b998",
    "8fbda29b4386a19b6bf600a5971005b69f5e4476e193283bbd074f51a8df86e6",
    "2423b5c9f1839ddd8fd13fec8c9bb617a5cb88d7d5182fda2e17879f0787b771",
    "2304b31f1388c4fb8441b3a99123702488ef9ac6fdc5c517304453f0483c90b2",
    "13134013beec923a62b0692802af2df0726dab1b7222ae1f730b4ab6d8ab1ae1",
    "ee75270529ec580d91abe75c7c268610c0abda08e26374df9a86a8f12903a54d",
    "4ec0833765ad1af0496d3ea50d296cdd3115b515d92f64ecc405dda90cc2eed5",
    "6b03f08bd8914320edb9987fd5529d76383ab93ca279663b539fc5a239b00350",
)


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


def compile_summer_thunder_dragon_special(
    cel_paths: Sequence[Path | str],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compile the hash-locked summer thunder dragon acquisition special."""
    return compile_special(
        cel_paths,
        target_prefix=SUMMER_THUNDER_TARGET,
        expected_sha256=SUMMER_THUNDER_SPECIAL_SHA256,
    )
