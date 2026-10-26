"""Bake native held-frame sequences to small lossless images, without game code."""
from __future__ import annotations

import io
from bisect import bisect_left
import zlib
from PIL import Image
import wf_assets
import wf_mod_tool as core
from wf_pixelart_vfx import entry_for_frame, frame_index, restore_frame

RENDER_VERSION = 2
ACTIONS = (("neutral", "idle", "待机"), ("walk_front", "move", "移动"),
           ("skill_ready", "skill_ready", "技能准备"), ("kachidoki", "victory", "胜利"))
LABELS = {kind: label for _, kind, label in ACTIONS} | {"skill": "技能动作", "special_pose": "特殊姿势"}


def tree(raw):
    decoder = zlib.decompressobj(-15)
    decoded = decoder.decompress(raw, 8 * 1024 * 1024)
    if not decoder.eof or decoder.unused_data:
        raise ValueError("像素元数据超出限额或不完整")
    return core.AMF3Reader(decoded).read_value()


def family(raw, special=False):
    sheet = "special_sprite_sheet" if special else "sprite_sheet"
    stem = "special" if special else "pixelart"
    image = Image.open(io.BytesIO(wf_assets.png_decode(raw[sheet + ".png"])))
    if max(image.size) > 8192 or image.width * image.height > 16_777_216:
        raise ValueError("像素图集超出尺寸限额")
    image.load()
    frame = tree(raw[stem + ".frame.amf3.deflate"])
    index = frame_index(tree(raw[sheet + ".atlas.amf3.deflate"]), frame["name"])
    timeline = tree(raw[stem + ".timeline.amf3.deflate"])
    return image, index, timeline["sequences"]


def sequence_frames(image, index, sequence):
    begin, end = sequence["begin"], sequence["end"]
    if (type(begin) is not int or type(end) is not int or not 1 <= begin <= end <= index[0][-1]
            or end - begin > 3600):
        raise ValueError("动作帧区间超出图集或预览限额")
    frames, durations, position, elapsed = [], [], begin, 0
    while position <= end:
        entry = entry_for_frame(index, position)
        finish = min(end, index[0][bisect_left(index[0], position)])
        picture = restore_frame(image, entry)
        duration = round((finish - begin + 1) * 1000 / 60) - elapsed
        elapsed += duration
        if frames and picture.size == frames[-1].size and picture.tobytes() == frames[-1].tobytes():
            durations[-1] += duration
        else:
            frames.append(picture); durations.append(duration)
        position = finish + 1
    bounds = [picture.getbbox() for picture in frames if picture.getbbox()]
    if not bounds:
        raise ValueError("动作没有可见像素")
    box = (min(b[0] for b in bounds) - 2, min(b[1] for b in bounds) - 2,
           max(b[2] for b in bounds) + 2, max(b[3] for b in bounds) + 2)
    return [picture.crop(box) for picture in frames], durations


def webp(frames, durations=None, loop=True):
    stream = io.BytesIO()
    frames[0].save(stream, "WEBP", lossless=True, exact=True, method=4,
                   save_all=len(frames) > 1, append_images=frames[1:],
                   duration=durations or 0, loop=0 if loop else 1)
    return stream.getvalue()


def render_actions(raw, save, unavailable=None):
    """save(bytes) returns a validated content-addressed URL; no source names escape."""
    result = []
    unavailable = unavailable if unavailable is not None else []
    families = [(False, ACTIONS + (("skill", "skill", "技能动作"),))]
    if "special_sprite_sheet.png" in raw:
        families.append((True, (("special_pose", "special_pose", "特殊姿势"),)))
    for special, choices in families:
        try:
            image, index, sequences = family(raw, special)
        except (OSError, ValueError, KeyError, zlib.error):
            if not special:
                raise
            unavailable.append({"kind": "special_pose", "label": "特殊姿势", "reason": "动作资源暂不能完整预览"})
            continue
        by_name = {sequence["name"]: sequence for sequence in sequences}
        for native, kind, label in choices:
            sequence = by_name.get(native)
            if not sequence:
                continue
            try:
                frames, durations = sequence_frames(image, index, sequence)
            except (OSError, ValueError, KeyError):
                if kind not in ("special_pose", "skill"):
                    raise
                unavailable.append({"kind": kind, "label": label, "reason": "动作资源暂不能完整预览"})
                continue
            loop = sequence.get("kind") == "loop"
            poster = {"url": save(webp(frames[:1])), "width": frames[0].width, "height": frames[0].height}
            animation = webp(frames, durations, loop)
            with Image.open(io.BytesIO(animation)) as check:
                animated = check.n_frames > 1
            result.append({"kind": kind, "label": label, "url": save(animation), "poster": poster,
                           "width": frames[0].width, "height": frames[0].height,
                           "durationMs": sum(durations), "animated": animated, "loop": loop})
    if not all(any(action["kind"] == kind for action in result) for _, kind, _ in ACTIONS):
        raise ValueError("缺少必要的小人动作")
    return result
