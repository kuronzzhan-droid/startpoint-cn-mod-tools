"""暗版奈芙的校园配色与光版像素特效；纯函数生成独立角色资产。"""
from __future__ import annotations

from copy import deepcopy
import io
import zlib

from PIL import Image

import wf_assets
import wf_dsl
from wf_generated_vfx import pack_images
from wf_pixelart_vfx import entry_for_frame, frame_index, restore_frame

CODE = "ruin_girl_campus"
SOURCE = "ruin_girl_3halfanv"
LIGHT_BASE = "ruin_girl"
LIGHT_FESTIVAL = "ruin_girl_halfanv"
LIGHT_SUMMER = "ruin_girl_smr21"
STEMS = {"pixelart": "sprite_sheet", "special": "special_sprite_sheet"}

# 仅灰色衣服与青灰装置；肤色、脸部、发色、黑轮廓不在映射内。
PALETTE = {
    (142, 135, 157): (164, 222, 202),
    (136, 127, 154): (106, 190, 165),
    (114, 184, 186): (190, 235, 218),
    (88, 124, 128): (119, 177, 159),
    (61, 94, 98): (74, 129, 115),
}
PROTECTED = {
    (0, 0, 0), (237, 185, 139), (236, 196, 155), (213, 146, 86),
    (167, 48, 0), (206, 118, 98), (170, 80, 36), (205, 31, 23),
    (116, 95, 171), (93, 58, 143), (58, 35, 115), (134, 115, 199),
    (121, 148, 255), (171, 136, 171), (113, 109, 255), (116, 110, 210),
    (255, 247, 255), (63, 55, 76),
}
# 暗版外围紫焰的专用颜色。装置实体、黄色电光和人物各姿势全部保留。
DARK_FLAME = {
    (139, 53, 169), (93, 29, 115), (204, 66, 209), (222, 134, 255),
    (228, 156, 255), (124, 44, 151), (127, 45, 156), (181, 54, 196),
    (93, 29, 114),
}
FX_COLORS = {
    LIGHT_BASE: {(243, 235, 205), (237, 217, 177), (255, 242, 172),
                 (245, 190, 78), (255, 225, 88), (255, 202, 75),
                 (255, 215, 97), (255, 172, 50)},
    LIGHT_FESTIVAL: {(0, 145, 255), (37, 241, 255), (20, 219, 255),
                     (20, 142, 255), (0, 191, 255), (102, 236, 200)},
    LIGHT_SUMMER: {(34, 229, 112), (34, 231, 255), (255, 240, 119),
                   (255, 151, 78), (34, 255, 166)},
}
assert not PROTECTED & (PALETTE.keys() | DARK_FLAME)


def _decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def _encode(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("pixel metadata AMF roundtrip mismatch")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()


def _png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return wf_assets.png_encode(stream.getvalue())


def _remap(value):
    if isinstance(value, str):
        return value.replace("character/" + SOURCE + "/", "character/" + CODE + "/")
    if isinstance(value, list):
        return [_remap(item) for item in value]
    if isinstance(value, dict):
        return {key: _remap(item) for key, item in value.items()}
    return value


def _load(read, code, kind="pixelart"):
    prefix = f"character/{code}/pixelart/"
    stem = STEMS[kind]
    image = Image.open(io.BytesIO(wf_assets.png_decode(read(prefix + stem + ".png")))).convert("RGBA")
    atlas = _decode(read(prefix + stem + ".atlas.amf3.deflate"))
    frame = _decode(read(prefix + kind + ".frame.amf3.deflate"))
    timeline = _decode(read(prefix + kind + ".timeline.amf3.deflate"))
    index = frame_index(atlas, frame["name"])
    total = max(sequence["end"] for sequence in timeline["sequences"])
    if any(not entry["n"].startswith(frame["name"]) for entry in atlas):
        raise ValueError("unrecognised secondary atlas alias")
    if index[0][-1] != total or frame.get("scale") != 6:
        raise ValueError("unexpected native pixel geometry or endpoint")
    cache = {key: restore_frame(image, entry) for key, entry in index[1].items()}
    frames = [cache[int(entry_for_frame(index, tick)["n"][len(frame["name"]):])]
              for tick in range(1, total + 1)]
    return frames, index[0], frame, timeline


def recolor(frame, *, remove_flame=False):
    """只改逐项颜色；透明RGB、受保护人物像素保持。去焰用于特效重组。"""
    result = frame.copy()
    result.putdata([
        (0, 0, 0, 0) if remove_flame and pixel[3] and pixel[:3] in DARK_FLAME
        else (*PALETTE.get(pixel[:3], pixel[:3]), pixel[3]) if pixel[3] else pixel
        for pixel in frame.get_flattened_data()
    ])
    return result


def light_layer(frame, code):
    """仅取供体专用光效色，中心人物区再次排除；不借入另一套脸/身体。"""
    result = Image.new("RGBA", frame.size)
    source, target = frame.load(), result.load()
    box = frame.getbbox()
    if not box:
        return result
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            pixel = source[x, y]
            if pixel[3] and pixel[:3] in FX_COLORS[code] and not (110 <= x < 146 and 104 <= y < 148):
                target[x, y] = pixel
    return result


def _behind(body, layers, opacity):
    result = Image.new("RGBA", body.size)
    for layer in layers:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda alpha: round(alpha * opacity)))
        result.alpha_composite(layer)
    mask = body.getchannel("A").point(lambda alpha: 255 if alpha else 0)
    result.paste(body, (0, 0), mask)
    return result


def compose_frames(frames, timeline, light_frames, kind):
    """以暗版逐tick身体为主体，光效按动作局部时间取帧，首尾归零。"""
    allowed = {"skill_ready"} if kind == "pixelart" else {"special_land", "special_pose"}
    schedules = {}
    for sequence in timeline["sequences"]:
        if sequence["name"] not in allowed:
            continue
        begin, end = sequence["begin"], sequence["end"]
        for tick in range(begin, end + 1):
            local = tick - begin
            ratio = local / max(1, end - begin)
            opacity = min(1.0, local / 4, (end - tick) / 6) * 0.82
            if sequence["name"] == "special_pose":
                source_tick = 94 + round(ratio * 16)
                layers = [light_frames[LIGHT_SUMMER][source_tick - 1]]
            else:
                source_tick = 51 + round(ratio * 59)
                layers = [light_frames[code][source_tick - 1] for code in (LIGHT_BASE, LIGHT_FESTIVAL)]
            schedules[tick] = (layers, opacity)
    cache, output = {}, []
    for tick, original in enumerate(frames, 1):
        key = (id(original), tick in schedules)
        if key not in cache:
            cache[key] = recolor(original, remove_flame=tick in schedules)
        body = cache[key]
        output.append(_behind(body, *schedules[tick]) if tick in schedules else body)
    return output


def assets(official_loader):
    """official_loader(logical)->bytes；返回8项私有像素资产，无文件/包写入。"""
    lights = {}
    for code in FX_COLORS:
        originals, _, _, timeline = _load(official_loader, code)
        ready = next(s for s in timeline["sequences"] if s["name"] == "skill_ready")
        if (ready["begin"], ready["end"]) != (51, 110):
            raise ValueError("light donor skill_ready timing drift")
        cache = {}
        lights[code] = [cache.setdefault(id(frame), light_layer(frame, code))
                        if id(frame) not in cache else cache[id(frame)] for frame in originals]
    outputs = {}
    for kind, stem in STEMS.items():
        originals, old_ends, frame, timeline = _load(official_loader, SOURCE, kind)
        composed = compose_frames(originals, timeline, lights, kind)
        ends = set(old_ends)
        for tick in range(1, len(composed)):
            if composed[tick - 1].tobytes() != composed[tick].tobytes():
                ends.add(tick)
        ends = sorted(ends)
        renamed_frame = _remap(frame)
        names = [renamed_frame["name"] + f"{tick:04d}" for tick in ends]
        sheet, atlas = pack_images([composed[tick - 1] for tick in ends], names,
                                    trim=True, dedup=True, max_width=None)
        prefix = f"character/{CODE}/pixelart/"
        for logical, raw in {
            stem + ".png": _png(sheet),
            stem + ".atlas.amf3.deflate": _encode(atlas),
            kind + ".frame.amf3.deflate": _encode(renamed_frame),
            kind + ".timeline.amf3.deflate": _encode(_remap(timeline)),
        }.items():
            outputs["common", prefix + logical] = raw
    return outputs


def metadata():
    return deepcopy({
        "body_source": {"character_id": 161177, "code": SOURCE, "element": "Black"},
        "light_fx_sources": {LIGHT_BASE: 151001, LIGHT_FESTIVAL: 151009, LIGHT_SUMMER: 151063},
        "palette": {str(key): list(value) for key, value in PALETTE.items()},
        "preserved": ["skin", "face", "hair", "outline", "native body poses", "native timeline", "all original endpoint aliases"],
        "fx_actions": {"pixelart": ["skill_ready"], "special": ["special_land", "special_pose"]},
        "fx_source": "only selected light-donor RGB outside the protected central rectangle",
        "body_ticks": 428, "special_ticks": 174,
        "neutral_and_walk_fx": False, "ui_portraits_voice_changed": False,
    })
