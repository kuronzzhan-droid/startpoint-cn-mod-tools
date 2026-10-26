#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the client special contract by aliasing locked normal sprite pixels.

The PNG payload is copied byte-for-byte.  Only special atlas aliases and the
special frame/timeline metadata are encoded, so this compiler cannot introduce
another character model or any new scene pixels.
"""
from __future__ import annotations

import hashlib
import io
import zlib
from collections.abc import Mapping

from PIL import Image

import wf_assets
import wf_dsl
from wf_pixelart_compile import SUMMER_THUNDER_TARGET, _raw_deflate, _validate_prefix


SPECIAL_SEQUENCES = (
    ("special_land", "pass", 51, 110),
    ("special_pose", "once", 111, 158),
)
SKILL_READY_TICKS = (51, 56, 62, 68, 74, 80, 86, 92, 98, 104, 110)
KACHIDOKI_TICKS = (111, 116, 122, 152, 158)
_GEOMETRY_KEYS = ("x", "y", "w", "h", "fx", "fy", "fw", "fh")
SUMMER_THUNDER_NORMAL_V3_SHA256 = {
    f"{SUMMER_THUNDER_TARGET}/sprite_sheet.png": "af3be179f0a2d38678131b015cdfe352fc7292bcac3684b34114717919a32b4e",
    f"{SUMMER_THUNDER_TARGET}/sprite_sheet.atlas.amf3.deflate": "7f3d2153d9788eebeb668041300667a7894255449da033f3ed853b9671738269",
    f"{SUMMER_THUNDER_TARGET}/pixelart.frame.amf3.deflate": "d6a9bed89a2db0c0c7dc5ca24767cbe02d43c7ddb56a786da7e7d1896c055ab1",
    f"{SUMMER_THUNDER_TARGET}/pixelart.timeline.amf3.deflate": "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b",
}


def _decode_amf(payload: bytes) -> object:
    return wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"]


def _normal_logicals(target: str) -> dict[str, str]:
    return {
        "sheet": f"{target}/sprite_sheet.png",
        "atlas": f"{target}/sprite_sheet.atlas.amf3.deflate",
        "frame": f"{target}/pixelart.frame.amf3.deflate",
        "timeline": f"{target}/pixelart.timeline.amf3.deflate",
    }


def _sequence_range(timeline: Mapping[str, object], name: str) -> tuple[int, int] | None:
    sequences = timeline.get("sequences")
    if not isinstance(sequences, list):
        return None
    for raw in sequences:
        if isinstance(raw, dict) and raw.get("name") == name:
            return int(raw["begin"]), int(raw["end"])
    return None


def _normal_tick(name: object, target: str) -> int:
    prefix = f"{target}/pixelart"
    if not isinstance(name, str) or not name.startswith(prefix):
        raise ValueError("normal atlas contains a non-target internal name")
    suffix = name[len(prefix):]
    if len(suffix) != 4 or not suffix.isdigit():
        raise ValueError("normal atlas contains a malformed pixelart tick")
    return int(suffix)


def _crop_pixel_sha256(sheet: Image.Image, entry: Mapping[str, object]) -> str:
    x = int(entry["x"])
    y = int(entry["y"])
    width = int(entry["w"])
    height = int(entry["h"])
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("normal atlas contains invalid crop geometry")
    if x + width > sheet.width or y + height > sheet.height:
        raise ValueError("normal atlas crop is outside the normal sprite sheet")
    crop = sheet.crop((x, y, x + width, y + height)).convert("RGBA")
    digest = hashlib.sha256()
    digest.update(f"{crop.width}x{crop.height}:".encode("ascii"))
    digest.update(crop.tobytes())
    return digest.hexdigest()


def compile_special_compatibility(
    normal_files: Mapping[str, bytes],
    *,
    target_prefix: str,
    expected_normal_sha256: Mapping[str, str] | None = None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Alias locked normal cels into the four-file 158-tick special contract."""
    target = _validate_prefix(target_prefix, "target_prefix")
    logicals = _normal_logicals(target)
    expected_keys = set(logicals.values())
    if set(normal_files) != expected_keys:
        missing = sorted(expected_keys.difference(normal_files))
        extra = sorted(set(normal_files).difference(expected_keys))
        raise ValueError(f"normal four-file contract mismatch: missing={missing}, extra={extra}")
    if expected_normal_sha256 is None:
        raise ValueError("normal SHA-256 lock is required")

    normal_sha256 = {
        logical: hashlib.sha256(normal_files[logical]).hexdigest()
        for logical in sorted(normal_files)
    }
    if set(expected_normal_sha256) != expected_keys:
        raise ValueError("normal SHA-256 lock must cover the exact four-file contract")
    for logical in sorted(expected_keys):
        if normal_sha256[logical] != expected_normal_sha256[logical]:
            raise ValueError(f"normal SHA-256 drift: {logical}")
    locked_summer_thunder_normal_v3 = (
        target == SUMMER_THUNDER_TARGET
        and dict(expected_normal_sha256) == SUMMER_THUNDER_NORMAL_V3_SHA256
    )

    try:
        decoded_png = wf_assets.png_decode(normal_files[logicals["sheet"]])
        with Image.open(io.BytesIO(decoded_png)) as opened:
            sheet = opened.convert("RGBA")
        atlas = _decode_amf(normal_files[logicals["atlas"]])
        normal_frame = _decode_amf(normal_files[logicals["frame"]])
        timeline = _decode_amf(normal_files[logicals["timeline"]])
    except Exception as error:
        raise ValueError("normal four-file payload cannot be decoded") from error
    if not isinstance(atlas, list) or not isinstance(timeline, dict):
        raise ValueError("normal atlas/timeline root type is invalid")
    if len(atlas) != 134:
        raise ValueError(f"normal atlas must contain exactly 134 records, got {len(atlas)}")
    if not isinstance(normal_frame, dict) or normal_frame.get("name") != f"{target}/pixelart":
        raise ValueError("normal frame internal name does not match target")
    if _sequence_range(timeline, "skill_ready") != (51, 110):
        raise ValueError("normal skill_ready sequence must span 51..110")
    if _sequence_range(timeline, "kachidoki") != (111, 158):
        raise ValueError("normal kachidoki sequence must span 111..158")

    by_tick: dict[int, dict[str, object]] = {}
    normal_records: list[tuple[int, dict[str, object]]] = []
    for raw in atlas:
        if not isinstance(raw, dict):
            raise ValueError("normal atlas record must be an object")
        normal_tick = _normal_tick(raw.get("n"), target)
        if normal_tick in by_tick:
            raise ValueError(f"normal atlas contains duplicate tick {normal_tick}")
        for key in _GEOMETRY_KEYS:
            if key not in raw:
                raise ValueError(f"normal atlas record {normal_tick} is missing {key}")
        by_tick[normal_tick] = raw
        normal_records.append((normal_tick, raw))
    for required_tick in (*SKILL_READY_TICKS, *KACHIDOKI_TICKS):
        if required_tick not in by_tick:
            raise ValueError(f"source atlas is missing required normal tick {required_tick}")

    special_atlas = []
    mappings = []
    for source_tick, source in normal_records:
        if 51 <= source_tick <= 110:
            sequence = "special_land"
            source_sequence = "skill_ready"
        elif 111 <= source_tick <= 158:
            sequence = "special_pose"
            source_sequence = "kachidoki"
        else:
            sequence = "outside_special_timeline"
            source_sequence = "normal_contract_passthrough"
        geometry = {key: value for key, value in source.items() if key != "n"}
        special_name = f"{target}/special{source_tick:04d}"
        special_atlas.append({"n": special_name, **geometry})
        mappings.append(
            {
                "special_name": special_name,
                "special_tick": source_tick,
                "special_sequence": sequence,
                "source_normal_name": source["n"],
                "source_normal_tick": source_tick,
                "source_normal_sequence": source_sequence,
                "source_crop_geometry": geometry,
                "source_crop_pixel_sha256": _crop_pixel_sha256(sheet, source),
                "transform": "identity",
            }
        )

    frame = dict(normal_frame)
    frame["name"] = f"{target}/special"
    special_timeline = {
        "sequences": [
            {"name": name, "kind": kind, "begin": begin, "end": end}
            for name, kind, begin, end in SPECIAL_SEQUENCES
        ],
        "circles": [],
        "points": [],
        "sounds": [],
    }
    files = {
        f"{target}/special_sprite_sheet.png": normal_files[logicals["sheet"]],
        f"{target}/special_sprite_sheet.atlas.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(special_atlas)
        ),
        f"{target}/special.frame.amf3.deflate": _raw_deflate(wf_dsl.encode_amf3(frame)),
        f"{target}/special.timeline.amf3.deflate": _raw_deflate(
            wf_dsl.encode_amf3(special_timeline)
        ),
    }
    output_sha256 = {
        logical: hashlib.sha256(payload).hexdigest()
        for logical, payload in sorted(files.items())
    }
    report: dict[str, object] = {
        "schema_version": 1,
        "mode": "deterministic_normal_pixel_compatibility_alias",
        "writes_live": False,
        "formal_workspace_written": False,
        "package_manifest_eligible": locked_summer_thunder_normal_v3,
        "locked_summer_thunder_normal_v3": locked_summer_thunder_normal_v3,
        "target_prefix": target,
        "normal_sha256": normal_sha256,
        "normal_sheet_size": list(sheet.size),
        "normal_sheet_stored_sha256": normal_sha256[logicals["sheet"]],
        "special_sheet_stored_sha256": output_sha256[f"{target}/special_sprite_sheet.png"],
        "png_byte_identical_to_normal": True,
        "new_art_pixels": 0,
        "all_atlas_geometry_from_normal": True,
        "all_transforms_identity": True,
        "atlas_records": len(special_atlas),
        "atlas_ticks": [tick for tick, _ in normal_records],
        "normal_internal_names_in_special_atlas": 0,
        "timeline_ticks": 158,
        "timeline_sequences": special_timeline["sequences"],
        "normal_timeline_labels_in_special_timeline": 0,
        "mapping_rule": {
            "atlas": "copy every normal atlas record in order; replace pixelart#### with special#### only",
            "frame": "copy normal frame; replace terminal name pixelart with special only",
            "timeline": "special_land reuses skill_ready 51..110; special_pose reuses kachidoki 111..158",
        },
        "special_key_mappings": mappings,
        "roots": {"common": sorted(files)},
        "output_sha256": output_sha256,
    }
    return files, report


def compile_summer_thunder_dragon_special_compatibility(
    normal_files: Mapping[str, bytes],
) -> tuple[dict[str, bytes], dict[str, object]]:
    """Compile only from the locked, hash-identical summer thunder normal v3."""
    return compile_special_compatibility(
        normal_files,
        target_prefix=SUMMER_THUNDER_TARGET,
        expected_normal_sha256=SUMMER_THUNDER_NORMAL_V3_SHA256,
    )
