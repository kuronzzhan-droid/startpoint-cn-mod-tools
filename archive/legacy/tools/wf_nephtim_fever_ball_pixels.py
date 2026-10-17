"""校园奈芙两种协力球的独立演员；保留官方图像与基础动作，不生成战斗逻辑。"""
from __future__ import annotations

from copy import deepcopy

from wf_nephtim_fever_pixels import _decode, _encode
from wf_pixelart_vfx import entry_for_frame, frame_index

DARK_SOURCE = "ruin_girl_3halfanv_multiball"
LIGHT_SOURCE = "ruin_girl_meteor"
DARK_CODE = "ruin_girl_campus_dark_ball"
LIGHT_CODE = "ruin_girl_campus_light_ball"
FALLBACKS = (("into_coffin", "pass"), ("ghost_raise", "pass"),
             ("ghost_neutral", "loop"), ("revive", "once"))
BASE_SEQUENCE_NAMES = ("neutral", "walk_back", "walk_front", "skill_ready", "kachidoki")


def _remap(value, source, target):
    if isinstance(value, str):
        return value.replace(f"character/{source}/", f"character/{target}/")
    if isinstance(value, list):
        return [_remap(item, source, target) for item in value]
    if isinstance(value, dict):
        return {key: _remap(item, source, target) for key, item in value.items()}
    return value


def _actor(official_loader, source, target):
    prefix = f"character/{source}/pixelart/"
    atlas = _decode(official_loader(prefix + "sprite_sheet.atlas.amf3.deflate"))
    frame = _decode(official_loader(prefix + "pixelart.frame.amf3.deflate"))
    timeline = _decode(official_loader(prefix + "pixelart.timeline.amf3.deflate"))
    if tuple(sequence["name"] for sequence in timeline["sequences"]) != BASE_SEQUENCE_NAMES:
        raise ValueError("official multiball sequence contract changed")
    index = frame_index(atlas, frame["name"])
    neutral = deepcopy(entry_for_frame(index, 1))
    end = timeline["sequences"][-1]["end"]
    if end != index[0][-1]:
        raise ValueError("official multiball endpoint mismatch")
    for name, kind in FALLBACKS:
        timeline["sequences"].append(dict(name=name, kind=kind, begin=end + 1, end=end + 2))
        next(c for c in timeline["circles"] if c["path"] == "unit_body")["frames"].append(
            dict(begin=end + 2, data=[]))
        end += 2
        alias = deepcopy(neutral)
        alias["n"] = frame["name"] + f"{end:04d}"
        atlas.append(alias)
    output_prefix = f"character/{target}/pixelart/"
    return {("common", output_prefix + name): raw for name, raw in {
        "sprite_sheet.png": official_loader(prefix + "sprite_sheet.png"),
        "sprite_sheet.atlas.amf3.deflate": _encode(_remap(atlas, source, target)),
        "pixelart.frame.amf3.deflate": _encode(_remap(frame, source, target)),
        "pixelart.timeline.amf3.deflate": _encode(_remap(timeline, source, target)),
    }.items()}


def assets(official_loader):
    """official_loader(logical)->bytes；只返回8项演员资产，没有store/角色包写入。"""
    return {**_actor(official_loader, DARK_SOURCE, DARK_CODE),
            **_actor(official_loader, LIGHT_SOURCE, LIGHT_CODE)}


def metadata():
    return {"dark": {"source": DARK_SOURCE, "target": DARK_CODE,
                     "original_ticks": 122, "output_ticks": 130},
            "light": {"source": LIGHT_SOURCE, "target": LIGHT_CODE,
                      "original_ticks": 51, "output_ticks": 59},
            "sprite_png_changed": False, "original_sequences_changed": False,
            "extra_sequences": [name for name, _ in FALLBACKS],
            "extra_frames": "alias of the source neutral pose; no extra visible effects",
            "battle_logic_included": False,
            "light_behavior": "ordinary Summons behavior supplied by caller; no Bomb action copied"}
