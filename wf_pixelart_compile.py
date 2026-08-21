#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure sprite compiler for a locked World Flipper ``skill_ready`` canary.

The canary deliberately preserves the template's other eight animation
sequences.  Its report therefore always marks the result as ineligible for a
production character manifest.  The compiler returns bytes and never writes a
store, package, CDN, server, or device.
"""
from __future__ import annotations

import copy
import hashlib
import io
import re
import zlib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from PIL import Image

import wf_assets
import wf_dsl


SUMMER_THUNDER_SOURCE = "character/thunder_dragon/pixelart"
SUMMER_THUNDER_TARGET = (
    "character/cnmod_thunder_dragon_ascendant/pixelart"
)
SUMMER_THUNDER_SKILL_READY_SHA256 = (
    "6dae3c0e34f36b3ee5a026730d8497a90928d0d2cb26fa81e0eda7775d168acb",
    "65df0935e95bfab5cd81ee76fb2bc44e66b6a732fc7ac9a3d2eb1f2e3ee4a417",
    "9ab89a2409383950007a4d372130589e0e5ffe06f9b94b7029da78ae8777b633",
    "59bd546838e8bbcb05c8b1f6a8dd8ec549a9d9296cbc7c73609051f95ac201e9",
    "2eb392e73453fb23cbc7d7a98fe91776b3ef362027b3e9b3c23e6ce4e55d61da",
    "3602214f724b143909ec7038d8dde47636586f3758bb0fb9004b5370a6545bd1",
    "f32e889dcfe777c12d5613e1ac7841e1710e48247f88f5153d7f44f696257984",
    "cf4aa07bc030a318b32e9169d2e6ba9815a92d51b05ca9cf2f53ae538d79d788",
    "6dae3c0e34f36b3ee5a026730d8497a90928d0d2cb26fa81e0eda7775d168acb",
)
SUMMER_THUNDER_TEMPLATE_SHA256 = {
    f"{SUMMER_THUNDER_SOURCE}/sprite_sheet.png": (
        "578f26226ae4681d51719e3d00640cad01b7a24b0c03222c51643bcd6b79cf28"
    ),
    f"{SUMMER_THUNDER_SOURCE}/sprite_sheet.atlas.amf3.deflate": (
        "76ca593252886f19ac8f8c9cd086d06ed4291eddd557a7a3fc6924fded395939"
    ),
    f"{SUMMER_THUNDER_SOURCE}/pixelart.frame.amf3.deflate": (
        "d2e6a74036fec03f04948b539a11adb742b9a848012fbf0251ad746c351adc1e"
    ),
    f"{SUMMER_THUNDER_SOURCE}/pixelart.timeline.amf3.deflate": (
        "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b"
    ),
}

_FILE_NAMES = (
    "sprite_sheet.png",
    "sprite_sheet.atlas.amf3.deflate",
    "pixelart.frame.amf3.deflate",
    "pixelart.timeline.amf3.deflate",
)
_SKILL_READY_TICKS = (51, 56, 62, 68, 74, 80, 86, 92, 98, 104, 110)
_SKILL_READY_CEL = (0, 1, 2, 3, 4, 5, 6, 7, 8, 8, 8)
_REPLACED_TEMPLATE_TICKS = frozenset(_SKILL_READY_TICKS[1:])
_SEQUENCES = (
    ("neutral", "loop", 1, 2),
    ("walk_back", "loop", 3, 26),
    ("walk_front", "loop", 27, 50),
    ("skill_ready", "once", 51, 110),
    ("kachidoki", "loop", 111, 158),
    ("into_coffin", "pass", 159, 200),
    ("ghost_raise", "pass", 201, 225),
    ("ghost_neutral", "loop", 226, 386),
    ("revive", "once", 387, 428),
)


def _raw_deflate(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _decode_raw_amf(payload: bytes, label: str):
    decompressor = zlib.decompressobj(-15)
    plain = decompressor.decompress(payload) + decompressor.flush()
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError(f"{label} is not one strict raw-deflate stream")
    return wf_dsl.parse_dsl(plain)["tree"]


def _encode_png(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", compress_level=9)
    return wf_assets.png_encode(stream.getvalue())


def _load_cels(
    cel_paths: Iterable[Path | str],
    expected_sha256: Sequence[str] | None,
) -> tuple[list[Image.Image], list[str]]:
    paths = [Path(path) for path in cel_paths]
    if len(paths) != 9:
        raise ValueError("skill_ready canary requires exactly 9 source cels")
    images: list[Image.Image] = []
    hashes: list[str] = []
    for index, path in enumerate(paths):
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256[index]:
            raise ValueError(
                f"skill_ready cel {index} does not match locked SHA-256"
            )
        with Image.open(io.BytesIO(payload)) as opened:
            if opened.format != "PNG" or opened.size != (64, 64):
                raise ValueError(f"skill_ready cel must be a 64x64 PNG: {path}")
            image = opened.convert("RGBA")
        alpha_values = set(image.getchannel("A").get_flattened_data())
        if not alpha_values or not alpha_values.issubset({0, 255}):
            raise ValueError(f"skill_ready cel must use binary alpha: {path}")
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"skill_ready cel is fully transparent: {path}")
        images.append(image)
        hashes.append(digest)
    return images, hashes


def _validate_prefix(prefix: str, label: str) -> str:
    if (
        not prefix
        or prefix.startswith("/")
        or "\\" in prefix
        or ".." in prefix.split("/")
        or any(not part for part in prefix.split("/"))
    ):
        raise ValueError(f"{label} must be a normalized logical path prefix")
    return prefix


def _decode_template(
    template_files: Mapping[str, bytes],
    source_prefix: str,
    expected_sha256: Mapping[str, str] | None,
) -> tuple[Image.Image, list, dict, dict]:
    expected = {f"{source_prefix}/{name}" for name in _FILE_NAMES}
    missing = sorted(expected.difference(template_files))
    if missing:
        raise ValueError(f"template is missing required files: {missing}")
    if expected_sha256 is not None:
        if set(expected_sha256) != expected:
            raise ValueError("template SHA-256 contract must cover exactly four files")
        for logical in sorted(expected):
            actual = hashlib.sha256(template_files[logical]).hexdigest()
            if actual != expected_sha256[logical]:
                raise ValueError(f"template file does not match locked SHA-256: {logical}")
    png = wf_assets.png_decode(template_files[f"{source_prefix}/sprite_sheet.png"])
    with Image.open(io.BytesIO(png)) as opened:
        sheet = opened.convert("RGBA")
    if sheet.size != (190, 58):
        raise ValueError(f"template sprite sheet must be 190x58, got {sheet.size}")
    atlas = _decode_raw_amf(
        template_files[f"{source_prefix}/sprite_sheet.atlas.amf3.deflate"],
        "template atlas",
    )
    frame = _decode_raw_amf(
        template_files[f"{source_prefix}/pixelart.frame.amf3.deflate"],
        "template frame",
    )
    timeline = _decode_raw_amf(
        template_files[f"{source_prefix}/pixelart.timeline.amf3.deflate"],
        "template timeline",
    )
    if not isinstance(atlas, list) or len(atlas) != 132:
        raise ValueError("template atlas must contain exactly 132 records")
    atlas_names: set[str] = set()
    for record in atlas:
        if not isinstance(record, dict):
            raise ValueError("template atlas record must be an object")
        name = record.get("n")
        if not isinstance(name, str) or name in atlas_names:
            raise ValueError("template atlas names must be unique strings")
        atlas_names.add(name)
        fields = {key: record.get(key) for key in ("x", "y", "w", "h", "fx", "fy", "fw", "fh")}
        if any(isinstance(value, bool) or not isinstance(value, int) for value in fields.values()):
            raise ValueError(f"template atlas geometry must use integers: {name}")
        x, y, width, height = fields["x"], fields["y"], fields["w"], fields["h"]
        fx, fy, full_width, full_height = fields["fx"], fields["fy"], fields["fw"], fields["fh"]
        if (
            x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or x + width > sheet.width
            or y + height > sheet.height
            or full_width <= 0
            or full_height <= 0
            or -fx < 0
            or -fy < 0
            or -fx + width > full_width
            or -fy + height > full_height
        ):
            raise ValueError(f"template atlas geometry is out of bounds: {name}")
    if frame != {
        "name": f"{source_prefix}/pixelart",
        "x": -128,
        "y": -128,
        "scale": 6,
        "smoothing": False,
    }:
        raise ValueError("template frame contract does not match thunder dragon")
    actual_sequences = [
        (entry.get("name"), entry.get("kind"), entry.get("begin"), entry.get("end"))
        for entry in timeline.get("sequences", [])
    ] if isinstance(timeline, dict) else []
    if tuple(actual_sequences) != _SEQUENCES:
        raise ValueError("template timeline does not contain the locked 9 sequences")
    return sheet, atlas, frame, timeline


def _pack_cels(
    template_sheet: Image.Image, cels: Sequence[Image.Image]
) -> tuple[Image.Image, list[dict]]:
    packed: list[dict] = []
    x = 1
    y = template_sheet.height + 1
    row_height = 0
    for image in cels:
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        left, top, right, bottom = bbox
        width = right - left
        height = bottom - top
        if width > 254 or height > 254:
            raise ValueError("trimmed skill_ready cel is too large for canary sheet")
        if x + width + 1 > 256:
            x = 1
            y += row_height + 2
            row_height = 0
        packed.append({
            "x": x,
            "y": y,
            "w": width,
            "h": height,
            "fx": -(96 + left),
            "fy": -(96 + top),
            "fw": 256,
            "fh": 256,
            "crop": image.crop(bbox),
        })
        x += width + 2
        row_height = max(row_height, height)
    output_height = y + row_height + 1
    sheet = Image.new("RGBA", (256, output_height), (0, 0, 0, 0))
    sheet.alpha_composite(template_sheet, (0, 0))
    for entry in packed:
        sheet.alpha_composite(entry["crop"], (entry["x"], entry["y"]))
    return sheet, packed


def compile_skill_ready_canary(
    template_files: Mapping[str, bytes],
    cel_paths: Iterable[Path | str],
    *,
    source_prefix: str,
    target_prefix: str,
    expected_sha256: Sequence[str] | None = None,
    expected_template_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], dict]:
    """Compile one locked ``skill_ready`` while preserving donor actions.

    The result is intentionally a structural canary and never production
    manifest eligible.
    """
    source = _validate_prefix(source_prefix, "source_prefix")
    target = _validate_prefix(target_prefix, "target_prefix")
    if source == target:
        raise ValueError("source_prefix and target_prefix must differ")
    if expected_sha256 is not None and len(expected_sha256) != 9:
        raise ValueError("expected_sha256 must contain exactly 9 hashes")

    cels, cel_hashes = _load_cels(cel_paths, expected_sha256)
    template_sheet, template_atlas, frame, timeline = _decode_template(
        template_files, source, expected_template_sha256
    )
    sheet, packed = _pack_cels(template_sheet, cels)

    name_pattern = re.compile(rf"{re.escape(source)}/pixelart(\d{{4}})\Z")
    kept: list[tuple[int, dict]] = []
    seen_ticks: set[int] = set()
    for original in template_atlas:
        if not isinstance(original, dict):
            raise ValueError("template atlas record must be an object")
        match = name_pattern.fullmatch(str(original.get("n", "")))
        if match is None:
            raise ValueError("template atlas contains an unexpected internal path")
        tick = int(match.group(1))
        if tick in seen_ticks:
            raise ValueError(f"template atlas contains duplicate tick {tick}")
        seen_ticks.add(tick)
        if tick == 51:
            raise ValueError("template atlas unexpectedly contains tick 51")
        if tick in _REPLACED_TEMPLATE_TICKS:
            continue
        entry = copy.deepcopy(original)
        entry["n"] = str(entry["n"]).replace(source + "/", target + "/", 1)
        kept.append((tick, entry))

    for tick, cel_index in zip(_SKILL_READY_TICKS, _SKILL_READY_CEL):
        geometry = packed[cel_index]
        entry = {
            "n": f"{target}/pixelart{tick:04d}",
            "w": geometry["w"],
            "h": geometry["h"],
            "x": geometry["x"],
            "y": geometry["y"],
            "fx": geometry["fx"],
            "fy": geometry["fy"],
            "fw": 256,
            "fh": 256,
        }
        kept.append((tick, entry))
    kept.sort(key=lambda item: item[0])
    atlas = [entry for _, entry in kept]
    passthrough_count = len(atlas) - len(_SKILL_READY_TICKS)
    if passthrough_count != 122:
        raise ValueError(
            f"compiled atlas must preserve 122 template records, got {passthrough_count}"
        )
    if len(atlas) != 133 or len({entry["n"] for entry in atlas}) != 133:
        raise ValueError("compiled atlas does not contain 133 unique records")

    target_frame = copy.deepcopy(frame)
    target_frame["name"] = f"{target}/pixelart"
    target_timeline = copy.deepcopy(timeline)
    files = {
        f"{target}/sprite_sheet.png": _encode_png(sheet),
        f"{target}/sprite_sheet.atlas.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(atlas)
        ),
        f"{target}/pixelart.frame.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(target_frame)
        ),
        f"{target}/pixelart.timeline.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(target_timeline)
        ),
    }
    report = {
        "schema_version": 1,
        "writes_live": False,
        "package_manifest_eligible": False,
        "target_prefix": target,
        "cel_sha256": cel_hashes,
        "official_passthrough_actions": [
            name for name, _, _, _ in _SEQUENCES if name != "skill_ready"
        ],
        "official_passthrough_atlas_records": passthrough_count,
        "atlas_records": len(atlas),
        "sheet_size": list(sheet.size),
        "output_sha256": {
            logical: hashlib.sha256(payload).hexdigest()
            for logical, payload in files.items()
        },
    }
    return files, report


def compile_summer_thunder_dragon_skill_ready_canary(
    template_files: Mapping[str, bytes],
    cel_paths: Iterable[Path | str],
) -> tuple[dict[str, bytes], dict]:
    """Compile the specifically approved summer thunder dragon cels."""
    return compile_skill_ready_canary(
        template_files,
        cel_paths,
        source_prefix=SUMMER_THUNDER_SOURCE,
        target_prefix=SUMMER_THUNDER_TARGET,
        expected_sha256=SUMMER_THUNDER_SKILL_READY_SHA256,
        expected_template_sha256=SUMMER_THUNDER_TEMPLATE_SHA256,
    )
