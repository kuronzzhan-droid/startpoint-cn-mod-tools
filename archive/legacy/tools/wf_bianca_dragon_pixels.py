"""把碧安卡四星技能里的原始幼龙像素裁片装成独立协力球；不重绘。"""
from __future__ import annotations

import io
import zlib

from PIL import Image

import wf_assets
import wf_dsl
from wf_bianca_dragon_skill import CALL_EFFECT, DRAGON_CODE, amf_bytes
from wf_generated_vfx import build_parts, pack_images
from wf_pixelart_vfx import restore_frame

SOURCE = "battle/effect/skill_unique/lady_summoner/lady_summoner"
STILL_POSE = ("as",) * 4
FLIGHT_POSES = ("a", "f", "g", "f")
DISAPPEAR_POSES = ("as", "at", "as", "at")
SEQUENCES = {
    "neutral": STILL_POSE,
    "walk_back": STILL_POSE,
    "walk_front": STILL_POSE,
    "skill_ready": ("l", "m", "u", "m"),
    "kachidoki": STILL_POSE,
    "into_coffin": ("as", "aq", "ab", "g"),
    "ghost_raise": ("a", "f", "g", "f"),
    "ghost_neutral": STILL_POSE,
    "revive": ("g", "ab", "aq", "as"),
}
SEQUENCE_KINDS = {"skill_ready": "once", "into_coffin": "pass",
                  "ghost_raise": "pass", "revive": "once"}
# 只用有透明轮廓的原生火花；r/s/t是需加色混合的光晕，不适合普通sprite图层。
CALL_PARTICLE_KEYS = ("p", "k", "x", "ac")


def build_dragon_assets(read):
    """返回四件套、六种龙召回/放飞效果与逐帧source证据；没有其他角色像素。"""
    image = Image.open(io.BytesIO(wf_assets.png_decode(read(SOURCE + ".png")))).convert("RGBA")
    atlas = wf_dsl.parse_dsl(zlib.decompress(read(SOURCE + ".atlas.amf3.deflate"), -15))["tree"]
    entries = {e["n"].rsplit("/", 1)[-1]: e for e in atlas}
    prefix = f"character/{DRAGON_CODE}/pixelart/"
    frame_name = prefix + "pixelart"
    pictures, names, sequences, provenance = [], [], [], []
    tiles = {}
    source_keys = ({k for sequence in SEQUENCES.values() for k in sequence}
                   | set(CALL_PARTICLE_KEYS + FLIGHT_POSES + DISAPPEAR_POSES))
    for key in source_keys:
        original = restore_frame(image, entries[key])
        tile = original.crop(original.getchannel("A").getbbox())
        canvas = Image.new("RGBA", (32, 32))
        canvas.paste(tile, ((32-tile.width)//2, (32-tile.height)//2))
        tiles[key] = canvas
    tick = 0
    for sequence, keys in SEQUENCES.items():
        begin = tick + 1
        for key in keys:
            # 原像素内容居中，无缩放、无染色，黑色轮廓与紫色翼膜完全保留。
            pictures.append(tiles[key])
            tick += 6
            names.append(f"{frame_name}{tick:04d}")
            provenance.append(dict(sequence=sequence, source=entries[key]["n"], end=tick))
        sequences.append(dict(name=sequence, kind=SEQUENCE_KINDS.get(sequence, "loop"),
                              begin=begin, end=tick))
    sheet, packed = pack_images(pictures, names, trim=True, dedup=True, max_width=None)
    buf = io.BytesIO(); sheet.save(buf, format="PNG")
    timeline = dict(sequences=sequences,
        circles=[dict(path="unit_body", frames=[dict(begin=s["begin"]+1,
            data=[dict(x=0, y=0, r=8.3)] if s["name"] in
            ("neutral", "walk_back", "walk_front") else []) for s in sequences])],
        points=[dict(path="hp_gauge", frames=[dict(begin=1, data=[dict(x=0, y=-10)])])], sounds=[])
    frame = dict(name=frame_name, x=-16, y=-16, scale=6, smoothing=False)
    files = {
        ("common", prefix + "sprite_sheet.png"): wf_assets.png_encode(buf.getvalue()),
        ("common", prefix + "sprite_sheet.atlas.amf3.deflate"): amf_bytes(packed),
        ("common", prefix + "pixelart.frame.amf3.deflate"): amf_bytes(frame),
        ("common", prefix + "pixelart.timeline.amf3.deflate"): amf_bytes(timeline),
    }
    files.update(build_call_effects(tiles))
    return files, dict(source_atlas=SOURCE + ".atlas.amf3.deflate", frames=provenance,
                       pixel_content_changed=False, sheet_size=list(sheet.size), ticks=tick)


def build_call_effects(tiles):
    """召唤只播放火光粒子；完整龙只留给离场和飞升，避免与活动实体重复。"""
    name = "campus_bianca_dragon_call"
    files, images, names = {}, [], []
    for tail in ("effect_ready_generation", "effect_ready_left", "effect_ready_right",
                 "effect_appear", "effect_disappear", "flight"):
        keys = (FLIGHT_POSES if tail == "flight" else
                DISAPPEAR_POSES if tail == "effect_disappear" else
                CALL_PARTICLE_KEYS)
        prefix = CALL_EFFECT + ".gen/" + name + "_" + tail + "/"
        parts, timeline = build_parts(4, (32, 32), prefix.replace(".gen/", "generated/"), hold=6)
        for texture in parts["i"]:
            texture["p"] = texture["p"].replace("/generated/", "/.gen/")
        # 像素actor的frame.scale为6，flatomo效果须显式复制相同比例。
        matrix = parts["t"][0]
        for field in ("a", "d", "x", "y"):
            matrix[field] *= 6
        logical = CALL_EFFECT + name + "_" + tail
        files["common", logical + ".parts.amf3.deflate"] = amf_bytes(parts)
        files["common", logical + ".timeline.amf3.deflate"] = amf_bytes(timeline)
        images.extend(tiles[key] for key in keys)
        names.extend(prefix + f"{i+1:04d}" for i in range(4))
    sheet, atlas = pack_images(images, names, trim=True, dedup=True, max_width=None)
    buf = io.BytesIO(); sheet.save(buf, format="PNG")
    files["common", CALL_EFFECT + name + ".png"] = wf_assets.png_encode(buf.getvalue())
    files["common", CALL_EFFECT + name + ".atlas.amf3.deflate"] = amf_bytes(atlas)
    return files
