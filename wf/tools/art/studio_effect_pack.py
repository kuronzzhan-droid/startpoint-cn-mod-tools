"""Lossless native atlas packing for authored Studio effects; never drops frames."""
from __future__ import annotations

import hashlib
import io
from PIL import Image

from wf.chars.support.common import amf_bytes, png_store_bytes


def pack_cells(cells):
    """Trim alpha borders, deduplicate cells, and retain their drawing origins."""
    unique, frames = {}, []
    for image, x, y in cells:
        image = image.convert("RGBA")
        box = image.getbbox()
        if box:
            cropped = image.crop(box)
            x, y = x + box[0], y + box[1]
        else:
            cropped = Image.new("RGBA", (1, 1))
        digest = hashlib.sha256(str(cropped.size).encode() + cropped.tobytes()).hexdigest()
        unique.setdefault(digest, cropped)
        frames.append((digest, x, y))
    candidates = []
    ordered = sorted(unique, key=lambda k: (-unique[k].height, -unique[k].width, k))
    for width in (256, 512, 1024, 2048, 4096):
        if any(im.width + 2 > width for im in unique.values()):
            continue
        rects, x, y, row_h = {}, 1, 1, 0
        for key in ordered:
            im = unique[key]
            if x + im.width + 1 > width:
                x, y, row_h = 1, y + row_h + 2, 0
            rects[key] = (x, y, im.width, im.height)
            x += im.width + 2
            row_h = max(row_h, im.height)
        height = y + row_h + 1
        if height <= 4096:
            candidates.append((width * height, width, height, rects))
    if not candidates:
        raise ValueError("Losslessly trimmed effect still exceeds 4096 atlas limit")
    _, width, height, rects = min(candidates, key=lambda c: c[0])
    sheet = Image.new("RGBA", (width, height))
    for key, im in unique.items():
        x, y, w, h = rects[key]
        sheet.paste(im, (x, y))
        assert sheet.crop((x, y, x + w, y + h)).tobytes() == im.tobytes()
    return sheet, [(rects[key], x, y) for key, x, y in frames]


def compile_effect(store, project, effect, code):
    """Drop-in adapter for Studio's native compiler, with identical frame timing."""
    from studio_compile import transformed_cell, compile_native_effect
    from audio_compile import effect_audio
    if effect.get("native"):
        return compile_native_effect(store, project, effect, code)
    clips = effect.get("clips", [])
    if not clips:
        return {}, "没有特效画稿"
    sheet, frames = pack_cells([transformed_cell(store, project, cl) for cl in clips])
    root = f"battle/effect/skill_unique/{code}/{effect['id']}"
    images, atlas, segments = [], [], []
    matrices = [{"a": 4096, "b": 0, "c": 0, "d": 4096, "x": 0, "y": 0}]
    tick = 0
    for i, (clip, ((x, y, w, h), left, top)) in enumerate(zip(clips, frames)):
        logical = f"{root}/.gen/effect/{i}"
        images.append({"s": False, "p": logical})
        atlas.append({"n": logical, "x": x, "y": y, "w": w, "h": h})
        matrices.append({"a": 4096, "b": 0, "c": 0, "d": 4096,
                         "x": left * 4096, "y": top * 4096})
        segments.append({"s": tick, "i": i, "l": [{"m": ((i + 1) << 12) | 255, "t": clip["hold"]}]})
        tick += clip["hold"]
    parts = {"i": images, "g": [{"t": tick, "s": segments}], "m": [], "a": [1] * len(images),
             "o": [], "t": matrices, "c": [], "s": effect.get("frameScale", 1)}
    sounds, audio, issues = effect_audio(store, project, effect, code)
    timeline = {"sequences": [{"begin": 1, "end": tick, "name": "neutral", "kind": effect["kind"]}],
                "sounds": sounds, "points": [], "circles": [], "rectangles": [], "matrices": []}
    return {**audio, f"{root}/{effect['id']}.png": png_store_bytes(sheet),
            f"{root}/{effect['id']}.atlas.amf3.deflate": amf_bytes(atlas),
            f"{root}/effect.parts.amf3.deflate": amf_bytes(parts),
            f"{root}/effect.timeline.amf3.deflate": amf_bytes(timeline)}, "；".join(issues) or None
