#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hash-locked accepted source artifacts and special-payload semantic gates."""

from __future__ import annotations

import hashlib
import io
import json
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

import wf_assets
import wf_mod_tool as core
from wf_summer_thunder_package_contract import (
    CODE_NAME,
    PackageAssemblyError,
    logical_segments,
    sha256_bytes,
)


NORMAL_V3_SPRITE_SHA256 = (
    "af3be179f0a2d38678131b015cdfe352fc7292bcac3684b34114717919a32b4e"
)
NORMAL_V3_ATLAS_SHA256 = (
    "7f3d2153d9788eebeb668041300667a7894255449da033f3ed853b9671738269"
)
NORMAL_V3_FRAME_SHA256 = (
    "d6a9bed89a2db0c0c7dc5ca24767cbe02d43c7ddb56a786da7e7d1896c055ab1"
)
NORMAL_V3_TIMELINE_SHA256 = (
    "23bee417315db0b49fa4bd87d62af39682a3ce9dd07b1409e01bf1c813232d8b"
)
SPECIAL_V3_ATLAS_SHA256 = (
    "d19eea107919191957b26ab9df7b3b40c07d7e7e50382a2d68da928171ef9ac7"
)
SPECIAL_V3_FRAME_SHA256 = (
    "effb3f6c141d9b239658bae4984b6c49c5e4faba483d096f3dc13026a01dc4b0"
)
SPECIAL_V3_TIMELINE_SHA256 = (
    "9fb7278e92961c5c12d0df8f100079c7ddc0ae032ca6f315e834b6c2eb8166db"
)

_PREFIX = f"character/{CODE_NAME}/pixelart/"
_SPECIAL_FRAME_NAME = _PREFIX + "special"
_SHA256_CHARS = frozenset("0123456789abcdef")
_SPECIAL_V2_MARKER = "special_production_api_v2"
_SPECIAL_OLD_V3_MARKER = "_api_v3"


@dataclass(frozen=True)
class ArtifactLock:
    """Hash-bound report and payload-set declaration for one build module."""

    name: str
    report_relative: str
    report_sha256: str
    payload_root_relative: str
    expected_count: int
    payload_sha256: tuple[tuple[str, str], ...] = ()
    acceptance_relative: str | None = None
    acceptance_sha256: str | None = None


_NORMAL_OUTPUT_SHA256 = (
    (_PREFIX + "pixelart.frame.amf3.deflate", NORMAL_V3_FRAME_SHA256),
    (_PREFIX + "pixelart.timeline.amf3.deflate", NORMAL_V3_TIMELINE_SHA256),
    (_PREFIX + "sprite_sheet.atlas.amf3.deflate", NORMAL_V3_ATLAS_SHA256),
    (_PREFIX + "sprite_sheet.png", NORMAL_V3_SPRITE_SHA256),
)
_SPECIAL_OUTPUT_SHA256 = (
    (_PREFIX + "special.frame.amf3.deflate", SPECIAL_V3_FRAME_SHA256),
    (_PREFIX + "special.timeline.amf3.deflate", SPECIAL_V3_TIMELINE_SHA256),
    (_PREFIX + "special_sprite_sheet.atlas.amf3.deflate", SPECIAL_V3_ATLAS_SHA256),
    (_PREFIX + "special_sprite_sheet.png", NORMAL_V3_SPRITE_SHA256),
)
_EFFECT_OUTPUT_SHA256 = (
    (
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning.atlas.amf3.deflate",
        "71c2feac443f66d716dc39329571546f9bb0abca7a2b9139e33de7dd92b9b47b",
    ),
    (
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/fan_lightning.png",
        "225fa8b9dd4b655464035121677ce6d2f5533e3525ef5fbe0794d298b7fb3d1d",
    ),
    (
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning_wave.parts.amf3.deflate",
        "38c5dc850404b61b393a8dd3c7385e003b69ec88dbcd5b7bfcdf83423df32d95",
    ),
    (
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning_wave.timeline.amf3.deflate",
        "1876a9f0896f005dfc40330657643fb5bf5c6e807bdd359da5cfdcd8321598d2",
    ),
)
_ICON_OUTPUT_SHA256 = ((
    "battle/common/unique_condition/unique_cnmod_thunder_dragon_ascendant_amp.png",
    "c6c2958ed0bea0396ef76c4efec89a76d05b61f1f6cbcee4838143766ec001a1",
),)
_UI_OUTPUT_SHA256 = (
    (f"character/{CODE_NAME}/ui/full_shot_1440_1920_0.png", "37a9c949d1249ff41bdf96b7d6fe66c62ae7d18818f965683f04b420d683db77"),
    (f"character/{CODE_NAME}/ui/skill_cutin_0.png", "9a245f095da6ab0f01623dd3db7ba2779065ce5c8410f2ac86b5cd3187601e9b"),
    (f"character/{CODE_NAME}/ui/square_0.png", "8a3eeebe60a6bcd517a4e38169e016b65e7a85027fbd652dbc72694723fa0a5e"),
    (f"character/{CODE_NAME}/ui/square_132_132_0.png", "d2f007d63dbab08b4b3968714061253db59872f43046a4511a401ccf676c32ce"),
    (f"character/{CODE_NAME}/ui/square_round_95_95_0.png", "abb33bd4dea17da8b7acd395e8d4deca1735d8c8b216f64a9778c44a683b41c1"),
    (f"character/{CODE_NAME}/ui/square_round_136_136_0.png", "e787bf5708cefccff5f83e7b084df47b7f576801a8095d35d18ea6623d536ac0"),
    (f"character/{CODE_NAME}/ui/thumb_level_up_0.png", "0499056bb1779a73cdf3efd5bd3cbea6f99f7c21d6f0fadcfe8430a7de2ee225"),
    (f"character/{CODE_NAME}/ui/thumb_party_main_0.png", "7dd836ca5402f4f9d68894d8a9d8c6dde678acea46fdf013610fd0be97f8962d"),
    (f"character/{CODE_NAME}/ui/thumb_party_unison_0.png", "9a95904b8c30acbf4d6fa5474dee24c4467c8b8013d07614aac89e2d33943078"),
    (f"character/{CODE_NAME}/ui/battle_control_board_0.png", "6ecd0e2e79b85e2c4e1dadfe24860e14ad92d53eb1d06f5d82c3f50e1bce50ad"),
    (f"character/{CODE_NAME}/ui/battle_member_status_0.png", "55bf61c6cbf7fe7b4a6523b56bbcd3ebb0df89c1e9b00e5a3a4f0b2e703a9841"),
    (f"character/{CODE_NAME}/ui/cutin_skill_chain_0.png", "df0d0a1799730fc414df2655bb09cd80b88ab8dcbbba0c34da1ab88fd780bd94"),
    (f"character/{CODE_NAME}/ui/full_shot_1440_1920_1.png", "f98925efa12589efa55a61c317a7a80fc926d71408af6b7829a4a05e38cafad6"),
    (f"character/{CODE_NAME}/ui/skill_cutin_1.png", "405f9c37239ddc25c2cfce5f59a67452ab2af47c0a45f8c79c4e604dfb601961"),
    (f"character/{CODE_NAME}/ui/square_1.png", "7ecdf7e3bc7c3d01f99331fe3468a1524ce7db5112024540bed0c49a67b882a7"),
    (f"character/{CODE_NAME}/ui/square_132_132_1.png", "8f4acf911d2de8ca82687964337a8c31153bb34b7756e9ee0fff4323ebea9b75"),
    (f"character/{CODE_NAME}/ui/square_round_95_95_1.png", "f072d61bffc3afee3d40ba0405502a629a7800549f39ba7f366a311899a5945f"),
    (f"character/{CODE_NAME}/ui/square_round_136_136_1.png", "6163e854ff86751ed6e5fd6a5a9c377c40d6a3998a1b336f487e60ee2e5f96ee"),
    (f"character/{CODE_NAME}/ui/thumb_level_up_1.png", "3af2d469bd62a7caed86811918a39b06caed33788d50f1215170c9ff1b8a2f61"),
    (f"character/{CODE_NAME}/ui/thumb_party_main_1.png", "1fec05a11de2fa859075e369233c8c57368f60bc3a230a62f282e1017daa8091"),
    (f"character/{CODE_NAME}/ui/thumb_party_unison_1.png", "263edbfe139224d62b86e6cd982adbef29872a7159b154d257b7fed4d4a6b6ac"),
    (f"character/{CODE_NAME}/ui/battle_control_board_1.png", "0ecf41ba69831b4e83c44e226d5ee34e0535368596226dfff838e31b23f913f5"),
    (f"character/{CODE_NAME}/ui/battle_member_status_1.png", "87c6eabb2ffd6c317c6aab5818f5539455152101aa63794c21221a4a7822ab5e"),
    (f"character/{CODE_NAME}/ui/cutin_skill_chain_1.png", "c857e5bf230b35fdb531c9b1bb7804655a4078815797aeb6422ecffda4dd2737"),
    (f"character/{CODE_NAME}/ui/illustration_setting_sprite_sheet.png", "91585771df9717accc2e554c00805a7775b8a3be7242b62ac122034e26d12066"),
    (f"character/{CODE_NAME}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "844f012072808c053e773ffc9e8ecbb07052d5f6cb09de27bbae4b621b36a2ec"),
    (f"character/{CODE_NAME}/ui/skill_cutin_0.atf.deflate", "cc088c952adfc3ff6aadc68eb16dc7ea141b62bad2de9a9836650d002216b37b"),
    (f"character/{CODE_NAME}/ui/skill_cutin_1.atf.deflate", "34b8559cd36d2c3475ae723619bbe9c9f3a64b0ffbe05dd87db170a0ffd15624"),
)

LOCKED_UI_V3 = ArtifactLock(
    "ui_v3", "art/ui/ui_assets_canary_v3/build_report.json",
    "ffccaa10f084e7adfa09e772f79707f6cdc540f5dac20e2d8986515afa6dccf7",
    "art/ui/ui_assets_canary_v3/roots", 28, _UI_OUTPUT_SHA256,
)
LOCKED_NORMAL_V3 = ArtifactLock(
    "normal_v3", "art/animations/normal/full_normal_candidate_v3/build_report.json",
    "60b24c93586f67f95cf339394237cc44c87d6b39413bc6e7aabc795f7a02e400",
    "art/animations/normal/full_normal_candidate_v3/roots/common", 4,
    _NORMAL_OUTPUT_SHA256,
    "art/animations/normal/full_normal_candidate_v3/acceptance_report_v1.json",
    "9a26558bfb553593d97cc12281bdb17502566d2eec5cdec4b890c61bb13211b3",
)
LOCKED_SPECIAL_COMPAT_V3 = ArtifactLock(
    "special_compatibility_v3",
    "art/animations/special/special_compatibility_v3/compile_report.json",
    "26811d657201a740df64679e8f7f439e55ab601ee57d91a463c32f9adf2f38f6",
    "art/animations/special/special_compatibility_v3/roots/common", 4,
    _SPECIAL_OUTPUT_SHA256,
    "art/animations/special/special_compatibility_v3/acceptance_report_v1.json",
    "973b2cb304db366d2dcceebf23cc558db544859646b143ee25ae69b395b523b5",
)
LOCKED_EFFECT_V1 = ArtifactLock(
    "fan_lightning_v1",
    "art/effects/skill_unique/fan_lightning_game_assets_v1/build_report.json",
    "a477cb84d91b364b427d9547731921fb20c7dc685b21886d464b2c0863d6e131",
    "art/effects/skill_unique/fan_lightning_game_assets_v1/roots/common", 4,
    _EFFECT_OUTPUT_SHA256,
)
LOCKED_ICON_V1 = ArtifactLock(
    "amp_icon_v1", "art/unique_condition/amp_icon_v1/build_report.json",
    "209d3d660c859d65d3616b998a683f5ba2ebe962534393cf39a561aa7f62d392",
    "art/unique_condition/amp_icon_v1/roots/common", 1, _ICON_OUTPUT_SHA256,
    "art/unique_condition/amp_icon_v1/acceptance_report_v1.json",
    "e1accdb7069cd6a19f670a58dcfc6eaac67fda8fefeb49c0f7a2e0256c26e5cd",
)
LOCKED_ARTIFACTS = (
    LOCKED_UI_V3, LOCKED_NORMAL_V3, LOCKED_SPECIAL_COMPAT_V3,
    LOCKED_EFFECT_V1, LOCKED_ICON_V1,
)


def validate_special_artifact_lock(
    lock: ArtifactLock, *, report: Mapping[str, Any]
) -> None:
    identity = f"{lock.report_relative}/{lock.payload_root_relative}".lower()
    if _SPECIAL_V2_MARKER in identity:
        raise PackageAssemblyError(
            "special v2 is production_forbidden even when its report claims eligibility"
        )
    if _SPECIAL_OLD_V3_MARKER in identity:
        raise PackageAssemblyError("special old v3 API is production_forbidden")
    if lock != LOCKED_SPECIAL_COMPAT_V3:
        raise PackageAssemblyError(
            "special compatibility identity must match the locked v3 report and acceptance"
        )
    expected_normal = dict(_NORMAL_OUTPUT_SHA256)
    expected_sequences = [
        {"name": "special_land", "kind": "pass", "begin": 51, "end": 110},
        {"name": "special_pose", "kind": "once", "begin": 111, "end": 158},
    ]
    expected_rule = {
        "atlas": "copy every normal atlas record in order; replace pixelart#### with special#### only",
        "frame": "copy normal frame; replace terminal name pixelart with special only",
        "timeline": "special_land reuses skill_ready 51..110; special_pose reuses kachidoki 111..158",
    }
    if (
        report.get("schema_version") != 1
        or report.get("mode") != "deterministic_normal_pixel_compatibility_alias"
        or report.get("writes_live") is not False
        or report.get("formal_workspace_written") is not False
        or report.get("package_manifest_eligible") is not True
        or report.get("target_prefix") != _PREFIX.rstrip("/")
        or report.get("normal_sha256") != expected_normal
        or report.get("output_sha256") != dict(_SPECIAL_OUTPUT_SHA256)
        or report.get("roots") != {"common": sorted(dict(_SPECIAL_OUTPUT_SHA256))}
    ):
        raise PackageAssemblyError("special compatibility report identity/hash closure drift")
    if (
        report.get("normal_sheet_stored_sha256") != NORMAL_V3_SPRITE_SHA256
        or report.get("special_sheet_stored_sha256") != NORMAL_V3_SPRITE_SHA256
        or report.get("png_byte_identical_to_normal") is not True
        or report.get("new_art_pixels") != 0
        or report.get("all_atlas_geometry_from_normal") is not True
        or report.get("all_transforms_identity") is not True
        or report.get("normal_internal_names_in_special_atlas") != 0
    ):
        raise PackageAssemblyError("special compatibility new-art/atlas reuse gate drift")
    if (
        report.get("atlas_records") != 134
        or report.get("timeline_ticks") != 158
        or report.get("timeline_sequences") != expected_sequences
        or report.get("normal_timeline_labels_in_special_timeline") != 0
        or report.get("mapping_rule") != expected_rule
    ):
        raise PackageAssemblyError(
            "special compatibility must preserve all 134 records and ticks 51..158"
        )
    mappings = report.get("special_key_mappings")
    ticks = report.get("atlas_ticks")
    if (
        not isinstance(mappings, list) or len(mappings) != 134
        or not isinstance(ticks, list) or len(ticks) != 134
        or len(set(ticks)) != 134
    ):
        raise PackageAssemblyError("special compatibility requires 134 unique mappings")
    mapping_fields = {
        "special_name", "special_tick", "special_sequence",
        "source_normal_name", "source_normal_tick", "source_normal_sequence",
        "source_crop_geometry", "source_crop_pixel_sha256", "transform",
    }
    geometry_fields = {"x", "y", "w", "h", "fx", "fy", "fw", "fh"}
    for index, (tick, mapping) in enumerate(zip(ticks, mappings, strict=True)):
        if not isinstance(tick, int) or not isinstance(mapping, dict) or set(mapping) != mapping_fields:
            raise PackageAssemblyError(f"special mapping fields drift at record {index}")
        geometry = mapping.get("source_crop_geometry")
        digest = mapping.get("source_crop_pixel_sha256")
        if (
            mapping.get("special_tick") != tick
            or mapping.get("source_normal_tick") != tick
            or mapping.get("special_name") != f"{_PREFIX}special{tick:04d}"
            or mapping.get("source_normal_name") != f"{_PREFIX}pixelart{tick:04d}"
            or mapping.get("transform") != "identity"
            or not isinstance(geometry, dict) or set(geometry) != geometry_fields
            or any(type(geometry[field]) is not int for field in geometry_fields)
            or geometry["w"] <= 0 or geometry["h"] <= 0
            or not isinstance(digest, str) or len(digest) != 64
            or any(char not in _SHA256_CHARS for char in digest)
        ):
            raise PackageAssemblyError(f"special mapping semantic drift at record {index}")
        if 51 <= tick <= 110:
            expected_pair = ("special_land", "skill_ready")
        elif 111 <= tick <= 158:
            expected_pair = ("special_pose", "kachidoki")
        else:
            expected_pair = ("outside_special_timeline", "normal_contract_passthrough")
        if (
            mapping.get("special_sequence"), mapping.get("source_normal_sequence")
        ) != expected_pair:
            raise PackageAssemblyError(f"special mapping sequence drift at record {index}")


def _decode_amf(raw: bytes, label: str) -> Any:
    try:
        return core.AMF3Reader(zlib.decompress(raw, -15)).read_value()
    except Exception as exc:
        raise PackageAssemblyError(f"{label} is not valid raw-deflate AMF3") from exc


def _rgba_image(stored: bytes, label: str) -> Image.Image:
    try:
        return Image.open(io.BytesIO(wf_assets.png_decode(stored))).convert("RGBA")
    except Exception as exc:
        raise PackageAssemblyError(f"{label} is not a valid WF PNG") from exc


def validate_special_reuse_payloads(
    normal_files: Mapping[str, bytes],
    special_files: Mapping[str, bytes],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Decode and prove official-style normal-cel reuse for all 134 records."""

    normal_keys = {
        "sheet": _PREFIX + "sprite_sheet.png",
        "atlas": _PREFIX + "sprite_sheet.atlas.amf3.deflate",
        "frame": _PREFIX + "pixelart.frame.amf3.deflate",
        "timeline": _PREFIX + "pixelart.timeline.amf3.deflate",
    }
    special_keys = {
        "sheet": _PREFIX + "special_sprite_sheet.png",
        "atlas": _PREFIX + "special_sprite_sheet.atlas.amf3.deflate",
        "frame": _PREFIX + "special.frame.amf3.deflate",
        "timeline": _PREFIX + "special.timeline.amf3.deflate",
    }
    missing_normal = set(normal_keys.values()) - set(normal_files)
    if missing_normal:
        raise PackageAssemblyError(f"normal reuse inputs missing: {sorted(missing_normal)}")
    if set(special_files) != set(special_keys.values()):
        raise PackageAssemblyError("special reuse payload set mismatch")
    if special_files[special_keys["sheet"]] != normal_files[normal_keys["sheet"]]:
        raise PackageAssemblyError("special sheet is not byte-identical to normal v3")
    normal_atlas = _decode_amf(normal_files[normal_keys["atlas"]], "normal v3 atlas")
    special_atlas = _decode_amf(special_files[special_keys["atlas"]], "special atlas")
    if (
        not isinstance(normal_atlas, list) or not isinstance(special_atlas, list)
        or len(normal_atlas) != 134 or len(special_atlas) != 134
    ):
        raise PackageAssemblyError("special reuse atlas must contain exactly 134 records")
    mappings = report.get("special_key_mappings")
    if not isinstance(mappings, list) or len(mappings) != 134:
        raise PackageAssemblyError("special report must map all 134 atlas records")
    normal_image = _rgba_image(normal_files[normal_keys["sheet"]], "normal sheet")
    special_image = _rgba_image(special_files[special_keys["sheet"]], "special sheet")
    crop_hashes: set[str] = set()
    for index, (normal, special, mapping) in enumerate(
        zip(normal_atlas, special_atlas, mappings, strict=True)
    ):
        if not all(isinstance(item, dict) for item in (normal, special, mapping)):
            raise PackageAssemblyError(f"special atlas record {index} is not an object")
        normal_name = normal.get("n")
        if not isinstance(normal_name, str) or not normal_name.startswith(_PREFIX + "pixelart"):
            raise PackageAssemblyError(f"normal atlas name drift at record {index}")
        expected_special = dict(normal)
        expected_special["n"] = (_PREFIX + "special") + normal_name[len(_PREFIX + "pixelart"):]
        if special != expected_special:
            raise PackageAssemblyError(f"special atlas geometry/alias drift at record {index}")
        try:
            x, y, width, height = (int(normal[key]) for key in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError) as exc:
            raise PackageAssemblyError(f"normal atlas crop invalid at record {index}") from exc
        box = (x, y, x + width, y + height)
        if x < 0 or y < 0 or width <= 0 or height <= 0 or box[2] > normal_image.width or box[3] > normal_image.height:
            raise PackageAssemblyError(f"normal atlas crop escapes sheet at record {index}")
        normal_crop = normal_image.crop(box).tobytes()
        if normal_crop != special_image.crop(box).tobytes():
            raise PackageAssemblyError(f"special decoded crop drift at record {index}")
        digest = hashlib.sha256()
        digest.update(f"{width}x{height}:".encode("ascii"))
        digest.update(normal_crop)
        crop_sha = digest.hexdigest()
        crop_hashes.add(crop_sha)
        tick = int(normal_name[-4:])
        expected_mapping = {
            "special_name": special["n"],
            "special_tick": tick,
            "special_sequence": "special_land" if 51 <= tick <= 110 else "special_pose" if 111 <= tick <= 158 else "outside_special_timeline",
            "source_normal_name": normal_name,
            "source_normal_tick": tick,
            "source_normal_sequence": "skill_ready" if 51 <= tick <= 110 else "kachidoki" if 111 <= tick <= 158 else "normal_contract_passthrough",
            "source_crop_geometry": {key: value for key, value in normal.items() if key != "n"},
            "source_crop_pixel_sha256": crop_sha,
            "transform": "identity",
        }
        if mapping != expected_mapping:
            if mapping.get("source_crop_pixel_sha256") != crop_sha:
                raise PackageAssemblyError(f"special source crop hash drift at record {index}")
            raise PackageAssemblyError(f"special report mapping/payload drift at record {index}")
    normal_frame = _decode_amf(normal_files[normal_keys["frame"]], "normal frame")
    special_frame = _decode_amf(special_files[special_keys["frame"]], "special frame")
    if not isinstance(normal_frame, dict) or normal_frame.get("name") != _PREFIX + "pixelart":
        raise PackageAssemblyError("normal v3 frame name is invalid")
    expected_frame = dict(normal_frame)
    expected_frame["name"] = _SPECIAL_FRAME_NAME
    if special_frame != expected_frame:
        raise PackageAssemblyError("special frame is not the exact normal-name alias")
    normal_timeline = _decode_amf(normal_files[normal_keys["timeline"]], "normal timeline")
    special_timeline = _decode_amf(special_files[special_keys["timeline"]], "special timeline")
    if not isinstance(normal_timeline, dict) or not isinstance(normal_timeline.get("sequences"), list):
        raise PackageAssemblyError("normal v3 timeline sequences are invalid")
    for sequence in (
        {"name": "skill_ready", "kind": "once", "begin": 51, "end": 110},
        {"name": "kachidoki", "kind": "loop", "begin": 111, "end": 158},
    ):
        if sequence not in normal_timeline["sequences"]:
            raise PackageAssemblyError("special timeline source sequence is absent from normal v3")
    expected_timeline = {
        "sequences": report.get("timeline_sequences"),
        "circles": [], "points": [], "sounds": [],
    }
    if special_timeline != expected_timeline:
        raise PackageAssemblyError("special timeline payload/report mismatch")
    return {
        "sheet_exact_same": True,
        "atlas_record_count": 134,
        "unique_crop_sha256": len(crop_hashes),
        "new_art_pixels": 0,
        "frame": special_frame,
        "timeline": special_timeline,
    }


def safe_child(root: Path, relative: str, label: str) -> Path:
    relative_path = Path(*logical_segments(relative))
    anchor = root.resolve(strict=True)
    candidate = (anchor / relative_path).resolve(strict=True)
    try:
        candidate.relative_to(anchor)
    except ValueError as exc:
        raise PackageAssemblyError(f"{label} escapes build root") from exc
    return candidate


def load_locked_artifact_bundle(
    build_root: Path, lock: ArtifactLock
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any] | None]:
    """Read exact report, acceptance, and all payloads for one accepted source."""

    root = Path(build_root)
    report_path = safe_child(root, lock.report_relative, f"{lock.name} report")
    report_raw = report_path.read_bytes()
    if sha256_bytes(report_raw) != lock.report_sha256:
        raise PackageAssemblyError(f"{lock.name} report drift")
    try:
        report = json.loads(report_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageAssemblyError(f"{lock.name} report is not JSON") from exc
    if not isinstance(report, dict) or report.get("writes_live") is not False:
        raise PackageAssemblyError(f"{lock.name} report must prove writes_live=false")
    if (lock.acceptance_relative is None) != (lock.acceptance_sha256 is None):
        raise PackageAssemblyError(f"{lock.name} acceptance lock is incomplete")
    acceptance: dict[str, Any] | None = None
    if lock.acceptance_relative is not None:
        acceptance_raw = safe_child(
            root, lock.acceptance_relative, f"{lock.name} acceptance"
        ).read_bytes()
        if sha256_bytes(acceptance_raw) != lock.acceptance_sha256:
            raise PackageAssemblyError(f"{lock.name} acceptance drift")
        try:
            acceptance = json.loads(acceptance_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PackageAssemblyError(f"{lock.name} acceptance is not JSON") from exc
        if (
            not isinstance(acceptance, dict)
            or acceptance.get("writes_live") is not False
            or acceptance.get("package_manifest_eligible") is not True
        ):
            raise PackageAssemblyError(f"{lock.name} acceptance is not eligible")
    if lock == LOCKED_SPECIAL_COMPAT_V3:
        validate_special_artifact_lock(lock, report=report)
        if (
            not isinstance(acceptance, dict)
            or acceptance.get("all_gates_pass") is not True
            or acceptance.get("formal_workspace_written") is not False
            or acceptance.get("new_art_pixels") != 0
            or acceptance.get("atlas_records") != 134
            or acceptance.get("timeline_sequences") != report.get("timeline_sequences")
        ):
            raise PackageAssemblyError("special acceptance semantics are not closed")
    if lock.payload_sha256:
        output_hashes = dict(lock.payload_sha256)
        if len(output_hashes) != len(lock.payload_sha256):
            raise PackageAssemblyError(f"{lock.name} payload lock contains duplicates")
    else:
        output_hashes = report.get("output_sha256")
        if not isinstance(output_hashes, dict):
            raise PackageAssemblyError(f"{lock.name} report lacks output_sha256")
    if len(output_hashes) != lock.expected_count:
        raise PackageAssemblyError(f"{lock.name} payload lock count drift")
    payload_root = safe_child(root, lock.payload_root_relative, f"{lock.name} root")
    if not payload_root.is_dir():
        raise PackageAssemblyError(f"{lock.name} payload root is not a directory")
    loaded: dict[str, bytes] = {}
    for logical, expected_sha in sorted(output_hashes.items()):
        path = safe_child(payload_root, logical, f"{lock.name} payload")
        if not path.is_file():
            raise PackageAssemblyError(f"{lock.name} payload missing: {logical}")
        raw = path.read_bytes()
        if sha256_bytes(raw) != expected_sha:
            raise PackageAssemblyError(f"{lock.name} payload drift for {logical}")
        loaded[logical] = raw
    disk_files = {
        path.relative_to(payload_root).as_posix()
        for path in payload_root.rglob("*") if path.is_file()
    }
    if disk_files != set(loaded):
        raise PackageAssemblyError(
            f"{lock.name} undeclared payloads: {sorted(disk_files - set(loaded))}"
        )
    return loaded, report, acceptance


def load_locked_artifact(build_root: Path, lock: ArtifactLock) -> dict[str, bytes]:
    return load_locked_artifact_bundle(build_root, lock)[0]


__all__ = [
    "ArtifactLock", "NORMAL_V3_SPRITE_SHA256", "NORMAL_V3_ATLAS_SHA256",
    "NORMAL_V3_FRAME_SHA256", "NORMAL_V3_TIMELINE_SHA256",
    "SPECIAL_V3_ATLAS_SHA256", "SPECIAL_V3_FRAME_SHA256",
    "SPECIAL_V3_TIMELINE_SHA256", "LOCKED_UI_V3", "LOCKED_NORMAL_V3",
    "LOCKED_SPECIAL_COMPAT_V3", "LOCKED_EFFECT_V1", "LOCKED_ICON_V1",
    "LOCKED_ARTIFACTS", "validate_special_artifact_lock",
    "validate_special_reuse_payloads", "safe_child", "load_locked_artifact_bundle",
    "load_locked_artifact",
]
