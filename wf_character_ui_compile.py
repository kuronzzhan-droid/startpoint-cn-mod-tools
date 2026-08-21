#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure UI compiler for the locked summer thunder dragon portraits.

The compiler accepts in-memory PNG/atlas/ATF payloads and returns logical
paths mapped to stored bytes.  It never writes a store, workspace, package,
CDN, server, or device.  Asset-specific source boxes are intentional: the two
approved compositions place the dragon's face at very different coordinates.
"""
from __future__ import annotations

import copy
import hashlib
import io
import re
import zlib
from collections.abc import Mapping

from PIL import Image, ImageChops

import wf_assets
import wf_atf
import wf_dsl


SUMMER_THUNDER_SOURCE = "character/thunder_dragon"
SUMMER_THUNDER_TARGET = "character/cnmod_thunder_dragon_ascendant"
SUMMER_THUNDER_MASTER_SHA256 = {
    0: "ab842d15fb2a9e70162a86f2291a4cda5191456be276aeabfd59f65e75b27dac",
    1: "cb553428246fe1cd12b11b0bbba7523360ff06ea9f976b3e1d97492a03ca8eed",
}
SUMMER_THUNDER_DONOR_ATLAS_SHA256 = (
    "2dbbe3af5ed508e87606373a4f2fff2cc831099c9ea2913e84d750fc265b8fc9"
)
SUMMER_THUNDER_DONOR_ATF_SHA256 = {
    0: "7b0a70eb5a5462f85976ac4238fa5673f647f2123475e7fe3603c1781b80d0de",
    1: "630fb68b2da2a8065799962e02004fb8eb1b2c86b2bce33e0b37a6e1365756a3",
}
SUMMER_THUNDER_SHAPE_MASK_SHA256 = {
    "round_95": "08905639407af0a17d5f19ae995b2541e2aff2b95471f0444278de1247a08d4d",
    "round_136": "11e9cd99bb90d787ccdb9eac1098b0b4888cea6976d6384e04234f5e9ba0d388",
    "level_up": "561b9524b1960ce07723cc8ca326ae0a6444e2c1de18a9b0b676d620edb2a32a",
    "party_main": "0b1ef1f70d5412c634237bea233dc667f9d08847c1dd2243961719357e90bd70",
    "party_unison": "92cf558b0bd9f4359ddd3e44e379d67ef341c2f47a445d72c6a7104727e15904",
    "control_board": "45b06451e25f05fb7858a03b4d160903f283bb9d058bac3a19ddffb4a6bbcb9c",
    "member_status": "b8bf0ab68310373479181a720100c75553623773d9e46bdf95d5e751f7d25814",
    "chain": "a7abab2acd2dbff5d5e480e87234dd5cea6ca9cf6630f41a545f8fc1bade6f28",
}

UI_ASSETS = {
    "skill_cutin": "ui/skill_cutin_{form}.png",
    "square_212": "ui/square_{form}.png",
    "square_132": "ui/square_132_132_{form}.png",
    "round_95": "ui/square_round_95_95_{form}.png",
    "round_136": "ui/square_round_136_136_{form}.png",
    "level_up": "ui/thumb_level_up_{form}.png",
    "party_main": "ui/thumb_party_main_{form}.png",
    "party_unison": "ui/thumb_party_unison_{form}.png",
    "control_board": "ui/battle_control_board_{form}.png",
    "member_status": "ui/battle_member_status_{form}.png",
    "chain": "ui/cutin_skill_chain_{form}.png",
}
MASKED_UI_ASSETS = frozenset(
    {
        "round_95",
        "round_136",
        "level_up",
        "party_main",
        "party_unison",
        "control_board",
        "member_status",
        "chain",
    }
)

SUMMER_THUNDER_UI_SIZES = {
    "skill_cutin": (1024, 512),
    "square_212": (212, 212),
    "square_132": (132, 132),
    "round_95": (95, 95),
    "round_136": (136, 136),
    "level_up": (252, 329),
    "party_main": (186, 392),
    "party_unison": (144, 188),
    "control_board": (104, 268),
    "member_status": (58, 58),
    "chain": (276, 319),
}

SUMMER_THUNDER_CROP_BOXES = {
    0: {
        "skill_cutin": (250, 0, 1070, 410),
        "square_212": (430, 20, 760, 350),
        "square_132": (435, 30, 755, 350),
        "round_95": (440, 60, 720, 340),
        "round_136": (425, 30, 745, 350),
        "level_up": (420, 20, 720, 412),
        "party_main": (430, 20, 709, 608),
        "party_unison": (420, 20, 720, 412),
        "control_board": (455, 40, 650, 542),
        "member_status": (450, 90, 710, 350),
        "chain": (405, 20, 735, 401),
    },
    1: {
        "skill_cutin": (0, 220, 1080, 760),
        "square_212": (230, 270, 570, 610),
        "square_132": (235, 280, 555, 600),
        "round_95": (245, 290, 525, 570),
        "round_136": (230, 280, 550, 600),
        "level_up": (225, 270, 525, 662),
        "party_main": (245, 270, 524, 858),
        "party_unison": (225, 270, 525, 662),
        "control_board": (285, 280, 480, 782),
        "member_status": (250, 300, 530, 580),
        "chain": (210, 270, 540, 651),
    },
}


def _validate_prefix(prefix: str, label: str) -> str:
    if not isinstance(prefix, str) or not prefix or prefix.startswith("/"):
        raise ValueError(f"{label} must be a normalized logical prefix")
    parts = prefix.split("/")
    unsafe = re.compile(r"[\\:\x00-\x1f<>\"|?*]")
    if any(
        not part
        or part in {".", ".."}
        or part.endswith((" ", "."))
        or unsafe.search(part)
        for part in parts
    ):
        raise ValueError(f"{label} must be a normalized logical prefix")
    return prefix


def _strict_inflate(payload: bytes, label: str) -> bytes:
    decompressor = zlib.decompressobj(-15)
    plain = decompressor.decompress(payload) + decompressor.flush()
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError(f"{label} is not one strict raw-deflate stream")
    return plain


def _raw_deflate(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(payload) + compressor.flush()


def _standard_png(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.convert("RGBA").save(stream, format="PNG", compress_level=9)
    return stream.getvalue()


def _stored_png(image: Image.Image) -> bytes:
    return wf_assets.png_encode(_standard_png(image))


def _load_masters(
    masters: Mapping[int, bytes],
    expected_sha256: Mapping[int, str] | None,
) -> tuple[dict[int, Image.Image], dict[int, bytes], dict[int, str]]:
    if set(masters) != {0, 1}:
        raise ValueError("masters must contain exactly forms 0 and 1")
    if expected_sha256 is not None and set(expected_sha256) != {0, 1}:
        raise ValueError("master SHA-256 contract must contain forms 0 and 1")
    images: dict[int, Image.Image] = {}
    standard: dict[int, bytes] = {}
    hashes: dict[int, str] = {}
    for form in (0, 1):
        payload = masters[form]
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256[form]:
            raise ValueError(f"master form {form} does not match locked SHA-256")
        decoded = wf_assets.png_decode(payload)
        with Image.open(io.BytesIO(decoded)) as opened:
            if opened.format != "PNG":
                raise ValueError(f"master form {form} is not PNG")
            image = opened.convert("RGBA")
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"master form {form} is fully transparent")
        images[form] = image
        standard[form] = decoded
        hashes[form] = digest
    return images, standard, hashes


def _validate_contract(
    images: Mapping[int, Image.Image],
    boxes: Mapping[int, Mapping[str, tuple[int, int, int, int]]],
    sizes: Mapping[str, tuple[int, int]],
) -> None:
    keys = set(UI_ASSETS)
    if set(sizes) != keys or set(boxes) != {0, 1}:
        raise ValueError("UI sizes/boxes must cover the exact asset contract")
    for key, size in sizes.items():
        if (
            not isinstance(size, tuple)
            or len(size) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in size)
        ):
            raise ValueError(f"invalid UI size for {key}: {size!r}")
    for form in (0, 1):
        if set(boxes[form]) != keys:
            raise ValueError(f"form {form} boxes do not cover the asset contract")
        width, height = images[form].size
        for key, box in boxes[form].items():
            if (
                not isinstance(box, tuple)
                or len(box) != 4
                or any(isinstance(value, bool) or not isinstance(value, int) for value in box)
            ):
                raise ValueError(f"invalid source box for form {form} {key}")
            left, top, right, bottom = box
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError(f"source box is outside master for form {form} {key}")
            box_ratio = (right - left) / (bottom - top)
            target_ratio = sizes[key][0] / sizes[key][1]
            if abs(box_ratio / target_ratio - 1.0) > 0.003:
                raise ValueError(
                    f"source box aspect ratio drifts over 0.3% for form {form} {key}"
                )


def _decode_illustration_atlas(
    payload: bytes,
    source_prefix: str,
    expected_sha256: str | None,
) -> list[dict]:
    if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError("illustration donor atlas does not match locked SHA-256")
    tree = wf_dsl.parse_dsl(_strict_inflate(payload, "illustration atlas"))["tree"]
    if not isinstance(tree, list) or len(tree) != 2:
        raise ValueError("illustration donor atlas must contain exactly two records")
    output = []
    for form, raw in enumerate(tree):
        if not isinstance(raw, dict):
            raise ValueError("illustration atlas record must be an object")
        expected_name = f"{source_prefix}/ui/full_shot_illustration_setting_{form}"
        if raw.get("n") != expected_name:
            raise ValueError("illustration donor atlas names/order do not match")
        fields = {key: raw.get(key) for key in ("x", "y", "w", "h", "fx", "fy", "fw", "fh")}
        if any(isinstance(value, bool) or not isinstance(value, int) for value in fields.values()):
            raise ValueError("illustration atlas geometry must use integers")
        x, y, width, height = fields["x"], fields["y"], fields["w"], fields["h"]
        fx, fy, full_width, full_height = fields["fx"], fields["fy"], fields["fw"], fields["fh"]
        if (
            x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or full_width <= 0
            or full_height <= 0
            or -fx < 0
            or -fy < 0
            or -fx + width > full_width
            or -fy + height > full_height
        ):
            raise ValueError("illustration atlas geometry is invalid")
        output.append(copy.deepcopy(raw))
    first, second = output
    if not (
        first["x"] + first["w"] <= second["x"]
        or second["x"] + second["w"] <= first["x"]
        or first["y"] + first["h"] <= second["y"]
        or second["y"] + second["h"] <= first["y"]
    ):
        raise ValueError("illustration atlas records overlap")
    return output


def _decode_shape_masks(
    shape_masks: Mapping[str, bytes],
    sizes: Mapping[str, tuple[int, int]],
    expected_sha256: Mapping[str, str] | None,
) -> tuple[dict[str, Image.Image], dict[str, str]]:
    if set(shape_masks) != MASKED_UI_ASSETS:
        raise ValueError("shape masks must cover the exact shaped UI contract")
    if expected_sha256 is not None and set(expected_sha256) != MASKED_UI_ASSETS:
        raise ValueError("mask SHA-256 contract must cover the exact shaped UI contract")
    masks: dict[str, Image.Image] = {}
    hashes: dict[str, str] = {}
    for key in sorted(MASKED_UI_ASSETS):
        payload = shape_masks[key]
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256[key]:
            raise ValueError(f"shape mask {key} does not match locked SHA-256")
        standard = wf_assets.png_decode(payload)
        with Image.open(io.BytesIO(standard)) as opened:
            if opened.format != "PNG" or opened.size != sizes[key]:
                raise ValueError(f"shape mask {key} has wrong dimensions")
            alpha = opened.convert("RGBA").getchannel("A")
        if alpha.getbbox() is None:
            raise ValueError(f"shape mask {key} is empty")
        pixels = alpha.load()
        for y in range(alpha.height):
            occupied = [x for x in range(alpha.width) if pixels[x, y] > 0]
            if occupied and any(
                pixels[x, y] == 0 for x in range(occupied[0], occupied[-1] + 1)
            ):
                raise ValueError(f"shape mask {key} has a hole in row {y}")
        masks[key] = alpha
        hashes[key] = digest
    return masks, hashes


def _clear_hidden_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    cleaned = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    cleaned.alpha_composite(rgba)
    return cleaned


def _render_skill_cutin(
    image: Image.Image,
    box: tuple[int, int, int, int],
    size: tuple[int, int],
) -> Image.Image:
    """Resize one form-specific cut-in without borrowing another alpha shape."""
    resized = (
        image.crop(box)
        .convert("RGBa")
        .resize(size, Image.Resampling.LANCZOS)
        .convert("RGBA")
    )
    alpha = bytearray(resized.getchannel("A").tobytes())
    width, height = size
    gains = []
    for distance in range(5):
        fraction = min(distance / 4, 1.0)
        smooth = fraction * fraction * (3.0 - 2.0 * fraction)
        gains.append(0.875 + 0.125 * smooth)
    for y in range(height):
        for x in range(width):
            distance = min(x, y, width - 1 - x, height - 1 - y, 4)
            offset = y * width + x
            alpha[offset] = round(alpha[offset] * gains[distance])
    resized.putalpha(Image.frombytes("L", size, bytes(alpha)))
    return _clear_hidden_rgb(resized)


def compile_ui_png_assets(
    masters: Mapping[int, bytes],
    boxes: Mapping[int, Mapping[str, tuple[int, int, int, int]]],
    sizes: Mapping[str, tuple[int, int]],
    donor_atlas: bytes,
    *,
    shape_masks: Mapping[str, bytes],
    source_prefix: str,
    target_prefix: str,
    expected_master_sha256: Mapping[int, str] | None = None,
    expected_atlas_sha256: str | None = None,
    expected_mask_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], dict]:
    """Compile 25 PNGs plus the illustration atlas in memory."""
    source = _validate_prefix(source_prefix, "source_prefix")
    target = _validate_prefix(target_prefix, "target_prefix")
    if source == target:
        raise ValueError("source_prefix and target_prefix must differ")
    images, standard_masters, master_hashes = _load_masters(
        masters, expected_master_sha256
    )
    _validate_contract(images, boxes, sizes)
    atlas = _decode_illustration_atlas(
        donor_atlas, source, expected_atlas_sha256
    )
    shape_masks, mask_hashes = _decode_shape_masks(
        shape_masks, sizes, expected_mask_sha256
    )

    files: dict[str, bytes] = {}
    rendered: dict[int, dict[str, Image.Image]] = {0: {}, 1: {}}
    for form in (0, 1):
        full_logical = f"{target}/ui/full_shot_1440_1920_{form}.png"
        files[full_logical] = wf_assets.png_encode(standard_masters[form])
        for key, relative_template in UI_ASSETS.items():
            if key == "skill_cutin":
                resized = _render_skill_cutin(
                    images[form], boxes[form][key], sizes[key]
                )
            else:
                crop = images[form].crop(boxes[form][key])
                resized = crop.resize(sizes[key], Image.Resampling.LANCZOS)
            if key in shape_masks:
                resized.putalpha(
                    ImageChops.multiply(resized.getchannel("A"), shape_masks[key])
                )
            resized = _clear_hidden_rgb(resized)
            rendered[form][key] = resized
            logical = f"{target}/{relative_template.format(form=form)}"
            files[logical] = _stored_png(resized)

    sheet_width = max(entry["x"] + entry["w"] for entry in atlas)
    sheet_height = max(entry["y"] + entry["h"] for entry in atlas)
    sheet = Image.new("RGBA", (sheet_width, sheet_height), (0, 0, 0, 0))
    for form, entry in enumerate(atlas):
        illustration_source = images[form].crop(boxes[form]["square_212"])
        full_frame = illustration_source.resize(
            (entry["fw"], entry["fh"]),
            Image.Resampling.LANCZOS,
        )
        cell_left, cell_top = -entry["fx"], -entry["fy"]
        cell = full_frame.crop(
            (
                cell_left,
                cell_top,
                cell_left + entry["w"],
                cell_top + entry["h"],
            )
        )
        cell = _clear_hidden_rgb(cell)
        sheet.alpha_composite(cell, (entry["x"], entry["y"]))
        entry["n"] = f"{target}/ui/full_shot_illustration_setting_{form}"

    sheet_logical = f"{target}/ui/illustration_setting_sprite_sheet.png"
    atlas_logical = (
        f"{target}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
    )
    files[sheet_logical] = _stored_png(sheet)
    files[atlas_logical] = _raw_deflate(wf_dsl.encode_amf3(atlas))
    if len(files) != 26:
        raise ValueError(f"UI PNG compiler produced {len(files)} files, expected 26")

    report = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "source_prefix": source,
        "target_prefix": target,
        "master_sha256": master_hashes,
        "png_count": 25,
        "atlas_count": 1,
        "shape_masks": sorted(shape_masks),
        "mask_source_sha256": mask_hashes,
        "illustration_sheet_size": [sheet_width, sheet_height],
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in files.items()
        },
        "roots": {
            "medium": sorted(
                logical for logical in files if logical.endswith(".png")
            ),
            "common": [atlas_logical],
            "android": [],
        },
    }
    return files, report


def compile_cutin_atf_assets(
    png_files: Mapping[str, bytes],
    donor_atfs: Mapping[int, bytes],
    *,
    target_prefix: str,
    expected_atf_sha256: Mapping[int, str] | None = None,
) -> tuple[dict[str, bytes], dict]:
    """Encode the two platform cut-in ATFs from compiled PNG payloads."""
    target = _validate_prefix(target_prefix, "target_prefix")
    if set(donor_atfs) != {0, 1}:
        raise ValueError("donor_atfs must contain exactly forms 0 and 1")
    if expected_atf_sha256 is not None and set(expected_atf_sha256) != {0, 1}:
        raise ValueError("ATF SHA-256 contract must contain forms 0 and 1")
    files: dict[str, bytes] = {}
    for form in (0, 1):
        png_logical = f"{target}/ui/skill_cutin_{form}.png"
        if png_logical not in png_files:
            raise ValueError(f"missing compiled cut-in PNG: {png_logical}")
        reference_payload = donor_atfs[form]
        if (
            expected_atf_sha256 is not None
            and hashlib.sha256(reference_payload).hexdigest()
            != expected_atf_sha256[form]
        ):
            raise ValueError(f"donor ATF form {form} does not match locked SHA-256")
        reference = _strict_inflate(reference_payload, f"donor ATF form {form}")
        standard_png = wf_assets.png_decode(png_files[png_logical])
        compiled = wf_atf.build_cutin_atf(standard_png, reference)
        logical = f"{target}/ui/skill_cutin_{form}.atf.deflate"
        files[logical] = wf_atf.deflate(compiled)
    report = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "target_prefix": target,
        "atf_count": 2,
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in files.items()
        },
        "roots": {
            "medium": [],
            "common": [],
            "android": sorted(files),
        },
    }
    return files, report


def compile_summer_thunder_dragon_ui_assets(
    masters: Mapping[int, bytes],
    donor_atlas: bytes,
    donor_atfs: Mapping[int, bytes],
    shape_masks: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict]:
    """Compile the locked pair to 28 isolated, still-unapproved UI assets."""
    png_files, png_report = compile_ui_png_assets(
        masters,
        SUMMER_THUNDER_CROP_BOXES,
        SUMMER_THUNDER_UI_SIZES,
        donor_atlas,
        shape_masks=shape_masks,
        source_prefix=SUMMER_THUNDER_SOURCE,
        target_prefix=SUMMER_THUNDER_TARGET,
        expected_master_sha256=SUMMER_THUNDER_MASTER_SHA256,
        expected_atlas_sha256=SUMMER_THUNDER_DONOR_ATLAS_SHA256,
        expected_mask_sha256=SUMMER_THUNDER_SHAPE_MASK_SHA256,
    )
    atf_files, atf_report = compile_cutin_atf_assets(
        png_files,
        donor_atfs,
        target_prefix=SUMMER_THUNDER_TARGET,
        expected_atf_sha256=SUMMER_THUNDER_DONOR_ATF_SHA256,
    )
    files = {**png_files, **atf_files}
    if len(files) != 28:
        raise ValueError(f"locked UI compiler produced {len(files)} files, expected 28")
    return files, {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "reason": "requires visual QA and three-table framing declarations",
        "png": png_report,
        "atf": atf_report,
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in files.items()
        },
    }
