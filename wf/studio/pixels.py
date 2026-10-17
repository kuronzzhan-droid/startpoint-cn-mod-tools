"""Pixel character (像素小人) data for the L1 preview player.

Each family (``pixelart`` / ``special``) is decoded from the native files:
``<sheet>.png`` + ``<sheet>.atlas`` (Starling sub-textures, possibly rotated
and trimmed) + ``<stem>.frame`` (anchor and display scale) + ``<stem>.timeline``
(named sequences in 60 fps frame numbers).

Every distinct atlas image is restored to its untrimmed frame box, all frames
of a family are cropped to their shared bounding box (so geometry stays
consistent), and packed in a grid sheet. The anchor is the display origin:
the frame box is placed at ``(frame.x, frame.y)`` relative to the origin, i.e.
the box *top-left* is offset, so the origin inside the box is ``(-x, -y)``.
"""
from __future__ import annotations

import io
import math
from bisect import bisect_left

from PIL import Image

import wf_assets
from wf_pixelart_vfx import frame_index, restore_frame
from wf_wiki_pixel_render import tree

from .source import StudioSource

FPS = 60
FAMILIES = (
    ("pixelart", "sprite_sheet", "基础动作"),
    ("special", "special_sprite_sheet", "特殊动作"),
)
# The 18 official action slots seen across the roster (9 base + 2 special
# for playable characters; 7 more only exist on boss-derived characters).
SLOTS = (
    ("neutral", "待机"), ("walk_front", "向前移动"), ("walk_back", "向后移动"),
    ("skill_ready", "技能准备"), ("kachidoki", "胜利"), ("into_coffin", "倒下入棺"),
    ("ghost_raise", "幽灵升起"), ("ghost_neutral", "幽灵待机"), ("revive", "复活"),
    ("special_land", "特殊登场"), ("special_pose", "特殊姿势"),
    ("wince_ready", "受击硬直"), ("stun_ready", "眩晕"), ("attack_initial", "攻击起手"),
    ("attack_charge", "攻击蓄力"), ("attack_action", "攻击动作"), ("attack_fire", "攻击释放"),
    ("dead", "死亡"),
)
SLOT_LABEL = dict(SLOTS)
KIND_LABEL = {"loop": "循环", "once": "单次（once）", "pass": "过渡（pass）", "stop": "停住（stop）"}


def _read(source: StudioSource, code: str, name: str) -> bytes | None:
    return source.raw(f"character/{code}/pixelart/{name}")


def _family(source: StudioSource, code: str, stem: str, sheet: str):
    files = {name: _read(source, code, name) for name in
             (sheet + ".png", sheet + ".atlas.amf3.deflate", stem + ".frame.amf3.deflate",
              stem + ".timeline.amf3.deflate")}
    if any(value is None for value in files.values()):
        return None
    image = Image.open(io.BytesIO(wf_assets.png_decode(files[sheet + ".png"])))
    image.load()
    frame = tree(files[stem + ".frame.amf3.deflate"])
    index = frame_index(tree(files[sheet + ".atlas.amf3.deflate"]), frame["name"])
    timeline = tree(files[stem + ".timeline.amf3.deflate"])
    return image, frame, index, timeline


def build_family(source: StudioSource, code: str, stem: str, sheet: str) -> tuple[dict, bytes] | None:
    loaded = _family(source, code, stem, sheet)
    if loaded is None:
        return None
    image, frame, (keys, entries), timeline = loaded
    restored = [restore_frame(image, entries[key]) for key in keys]
    boxes = [picture.getbbox() for picture in restored if picture.getbbox()]
    if not boxes:
        raise ValueError("像素图集没有可见像素")
    pad = 2
    fw, fh = restored[0].size
    box = (max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad),
           min(fw, max(b[2] for b in boxes) + pad), min(fh, max(b[3] for b in boxes) + pad))
    cw, ch = box[2] - box[0], box[3] - box[1]
    columns = max(1, min(len(restored), int(math.ceil(math.sqrt(len(restored))))))
    rows = int(math.ceil(len(restored) / columns))
    sheet_image = Image.new("RGBA", (columns * cw, rows * ch))
    for i, picture in enumerate(restored):
        sheet_image.paste(picture.crop(box), ((i % columns) * cw, (i // columns) * ch))
    out = io.BytesIO()
    sheet_image.save(out, "PNG", optimize=True)

    actions = []
    for sequence in timeline.get("sequences", []):
        begin, end = sequence.get("begin"), sequence.get("end")
        if type(begin) is not int or type(end) is not int or not 1 <= begin <= end <= keys[-1]:
            continue
        cells, position = [], begin
        while position <= end:
            slot = bisect_left(keys, position)
            finish = min(end, keys[slot])
            cells.append({"cell": slot, "frames": finish - position + 1, "start": position - begin})
            position = finish + 1
        name = sequence.get("name", "")
        actions.append({"name": name, "label": SLOT_LABEL.get(name, name), "kind": sequence.get("kind"),
                        "kindLabel": KIND_LABEL.get(sequence.get("kind"), sequence.get("kind")),
                        "begin": begin, "end": end, "totalFrames": end - begin + 1, "cells": cells})
    meta = {
        "family": stem, "cellWidth": cw, "cellHeight": ch, "columns": columns, "cellCount": len(restored),
        "frameBox": {"width": fw, "height": fh, "cropX": box[0], "cropY": box[1]},
        # Origin inside the cropped cell (display anchor).
        "anchor": {"x": -int(frame.get("x", 0)) - box[0], "y": -int(frame.get("y", 0)) - box[1]},
        "scale": frame.get("scale", 1), "smoothing": bool(frame.get("smoothing", False)),
        "fps": FPS, "actions": actions,
        "points": len(timeline.get("points", []) or []), "sounds": len(timeline.get("sounds", []) or []),
    }
    return meta, out.getvalue()


class PixelCache:
    def __init__(self, source: StudioSource):
        self.source = source
        self._cache: dict[str, dict] = {}

    def character(self, code: str) -> dict:
        if code not in self._cache:
            families, sheets = [], {}
            for stem, sheet, label in FAMILIES:
                try:
                    built = build_family(self.source, code, stem, sheet)
                except (OSError, ValueError, KeyError) as exc:
                    families.append({"family": stem, "label": label, "error": f"{type(exc).__name__}: {exc}"})
                    continue
                if built is None:
                    continue
                meta, png = built
                sheets[stem] = png
                families.append({**meta, "label": label})
            present = {a["name"] for f in families for a in f.get("actions", [])}
            slots = [{"name": n, "label": l, "present": n in present} for n, l in SLOTS]
            self._cache[code] = {"families": families, "sheets": sheets, "slots": slots}
        return self._cache[code]

    def meta(self, code: str) -> dict:
        data = self.character(code)
        return {"code": code, "families": data["families"], "slots": data["slots"],
                "note": "L1 素材级预览：只播放角色小人动作帧，不含特效、弹道或命中。帧时长按 60fps 时间轴。"}

    def sheet(self, code: str, family: str) -> bytes | None:
        return self.character(code)["sheets"].get(family)
