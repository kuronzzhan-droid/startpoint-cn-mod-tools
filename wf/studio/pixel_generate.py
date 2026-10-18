"""程序化动作：从三张底图（正面 front / 背面 back / 躺倒 liedown）合成官方样式序列。

配方（2026-08-24 西蒙占位实测，官方逐帧对比）：

* 走路 walk_front/walk_back：内容几乎不变，交替下沉 dy=+1，底行左右摆 1px（裙摆）。
  端点 8/14/20/26、32/38/44/50（每张 6 帧）。
* 胜利 kachidoki：原姿 → 倾斜 12° 起跳 → 最高点 -16° + 金白火花 → 落地 6°。
  端点 116/122/152/158；客户端读 begin+18（动作第 19 帧）当举手帧，必须落在最高点那张：
  总长不是 48 时按比例缩放端点后再校正（起跳图 ≤ 第 18 帧、最高点图 ≥ 第 19 帧），总长至少 20。
* 入棺 into_coffin：本体逐步变淡 → 躺倒。
* 揭起 ghost_raise：躺倒垫底（同一地线），幽灵逐渐显形并升起到 dy=-12。
* 幽灵待机 ghost_neutral：幽灵 = 本体明度三档映射白/灰蓝（150/90 分档），底行收成中央波尾；
  悬浮 dy=-12 上下 1~2px 微浮动。端点 255/275/285/305/335/355/386。
* 复活 revive：幽灵下落 → 与本体交叠 → 全白闪 → 本体。

几何：每帧是 256² 帧框，原点 (128,128)。底图贴在 left = 128 - w//2、top = 128 - h + dy，
所以编译后 fx = -(128 - w//2)，fy = -(128 - h + dy)（与官方编码一致）。全部确定性：
同一底图与参数 → 同一组像素。
"""
from __future__ import annotations

import hashlib

from PIL import Image

from .drafts import DraftError

BOX = 256
ORIGIN = (128, 128)
GHOST_DY = -12
SPARK_GOLD = (252, 214, 96, 255)
SPARK_WHITE = (255, 255, 255, 255)

# 官方端点（相对动作起点的末帧号），只在动作总长等于官方总长时原样使用，否则按比例缩放。
RECIPES = {
    "walk_back": {"base": "back", "total": 24, "ends": [6, 12, 18, 24]},
    "walk_front": {"base": "front", "total": 24, "ends": [6, 12, 18, 24]},
    "kachidoki": {"base": "front", "total": 48, "ends": [6, 12, 42, 48]},
    "into_coffin": {"base": "front+liedown", "total": 42, "ends": [3, 6, 9, 12, 42]},
    "ghost_raise": {"base": "front+liedown", "total": 25, "ends": [5, 10, 15, 20, 25]},
    "ghost_neutral": {"base": "front", "total": 161, "ends": [30, 50, 60, 80, 110, 130, 161]},
    "revive": {"base": "front", "total": 42, "ends": [6, 12, 18, 24, 30, 42]},
}
KACHIDOKI_READ = 19  # begin + 18: the client's raised-hand frame (1-based within the action)
LABELS = {"walk_back": "向后移动", "walk_front": "向前移动", "kachidoki": "胜利", "into_coffin": "倒下入棺",
          "ghost_raise": "幽灵升起", "ghost_neutral": "幽灵待机", "revive": "复活"}


def trim(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box is None:
        raise DraftError("底图全透明")
    return image.crop(box)


def place(sprite: Image.Image, dy: int = 0, dx: int = 0) -> Image.Image:
    """把裁好的小人贴进 256² 帧框：脚底在 (128, 128+dy)，横向居中。"""
    canvas = Image.new("RGBA", (BOX, BOX))
    w, h = sprite.size
    left, top = ORIGIN[0] - w // 2 + dx, ORIGIN[1] - h + dy
    if left < 0 or top < 0 or left + w > BOX or top + h > BOX:
        raise DraftError("合成帧超出 256² 帧框")
    canvas.paste(sprite, (left, top))
    return canvas


def scaled_ends(ends: list[int], total: int, wanted: int) -> list[int]:
    if wanted == total:
        return list(ends)
    if wanted < len(ends):
        raise DraftError(f"动作只有 {wanted} 帧，放不下 {len(ends)} 张图")
    result, previous = [], 0
    for index, end in enumerate(ends):
        value = wanted if index == len(ends) - 1 else round(end * wanted / total)
        value = max(previous + 1, min(value, wanted - (len(ends) - 1 - index)))
        result.append(value)
        previous = value
    return result


def kachidoki_ends(ends: list[int], total: int) -> list[int]:
    """Keep the client's begin+18 frame on the apex image after scaling (A10)."""
    if total < KACHIDOKI_READ + 1:
        raise DraftError(f"胜利动作至少 {KACHIDOKI_READ + 1} 帧：客户端读第 {KACHIDOKI_READ} 帧（begin+18）当举手帧，"
                         "要落在最高点那张，之后还要留落地帧")
    first, lean, apex, end = ends
    lean = min(lean, KACHIDOKI_READ - 1)
    first = max(1, min(first, lean - 1))
    apex = max(apex, KACHIDOKI_READ)
    return [first, lean, apex, end]


def with_alpha(image: Image.Image, factor: float) -> Image.Image:
    out = image.copy()
    out.putalpha(image.getchannel("A").point(lambda a: int(round(a * factor))))
    return out


def sway_bottom(sprite: Image.Image, shift: int) -> Image.Image:
    """底行整体平移 1px（裙摆）。"""
    out = sprite.copy()
    w, h = sprite.size
    row = sprite.crop((0, h - 1, w, h))
    out.paste((0, 0, 0, 0), (0, h - 1, w, h))
    out.paste(row, (shift, h - 1))
    return out


def rotate(sprite: Image.Image, degrees: float) -> Image.Image:
    return trim(sprite.rotate(degrees, resample=Image.Resampling.NEAREST, expand=True))


def ghostify(sprite: Image.Image) -> Image.Image:
    """明度三档映射 白 / 浅灰蓝 / 灰蓝，底部三行收成中央波尾。"""
    out = sprite.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if not a:
                continue
            l = 0.299 * r + 0.587 * g + 0.114 * b
            px[x, y] = (255, 255, 255, a) if l > 150 else (196, 208, 232, a) if l > 90 else (112, 128, 168, a)
    for k in range(min(3, h - 1)):
        y = h - 1 - k
        half = max(1, (w // 2) * (k + 1) // 4)
        center = w // 2 + (1 if k == 1 else 0)
        for x in range(w):
            if abs(x - center) > half:
                px[x, y] = (0, 0, 0, 0)
    return trim(out)


def whiten(sprite: Image.Image) -> Image.Image:
    out = sprite.copy()
    white = Image.new("RGBA", sprite.size, (255, 255, 255, 255))
    white.putalpha(sprite.getchannel("A"))
    out.paste(white, (0, 0))
    return out


def sparks(canvas: Image.Image, sprite_box: tuple[int, int, int, int], seed: str) -> Image.Image:
    """确定性金白火花：位置来自 md5(seed)，围着头顶。"""
    out = canvas.copy()
    px = out.load()
    left, top, right, _ = sprite_box
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    for i in range(6):
        x = left - 3 + digest[i] % (right - left + 6)
        y = top - 4 + digest[i + 6] % 6
        colour = SPARK_GOLD if i % 2 == 0 else SPARK_WHITE
        for ox, oy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)) if i < 2 else ((0, 0),):
            if 0 <= x + ox < BOX and 0 <= y + oy < BOX and not px[x + ox, y + oy][3]:
                px[x + ox, y + oy] = colour
    return out


def _shift(image: Image.Image, dy: int) -> Image.Image:
    box = image.getchannel("A").getbbox()
    if box and (box[1] + dy < 0 or box[3] + dy > BOX):
        raise DraftError("地线偏移后超出 256² 帧框")
    out = Image.new("RGBA", (BOX, BOX))
    out.paste(image, (0, dy))
    return out


def _over(*layers: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (BOX, BOX))
    for layer in layers:
        canvas = Image.alpha_composite(canvas, layer)
    return canvas


def _need(bases: dict, name: str, action: str) -> Image.Image:
    image = bases.get(name)
    if image is None and name == "liedown" and bases.get("front") is not None:
        return rotate(trim(bases["front"]), -90)  # 近似：正面顺时针躺倒
    if image is None:
        raise DraftError(f"{action} 需要底图 {name}")
    return trim(image)


def generate(action: str, bases: dict[str, Image.Image], total: int | None = None, ground: int = 0) -> list[dict]:
    """Return ``[{image (256² RGBA), duration, dy, note}]`` whose durations sum to ``total``.

    ``ground`` shifts the whole action so the feet sit where this character's idle feet sit
    (its neutral median dy; official sheets are often 0 or +1 because of rotated atlas cells).
    """
    if action not in RECIPES:
        raise DraftError(f"没有 {action} 的程序化配方（可选：{', '.join(RECIPES)}）")
    recipe = RECIPES[action]
    total = total or recipe["total"]
    ends = scaled_ends(recipe["ends"], recipe["total"], total)
    if action == "kachidoki":
        ends = kachidoki_ends(ends, total)
    frames: list[tuple[Image.Image, int, str]] = []
    if action in ("walk_back", "walk_front"):
        sprite = _need(bases, recipe["base"], action)
        frames = [(place(sprite, 0), 0, "原姿"), (place(sway_bottom(sprite, 1), 1), 1, "下沉 1px，底行右摆"),
                  (place(sprite, 0), 0, "原姿"), (place(sway_bottom(sprite, -1), 1), 1, "下沉 1px，底行左摆")]
    elif action == "kachidoki":
        sprite = _need(bases, "front", action)
        lean, apex, land = rotate(sprite, 12), rotate(sprite, -16), rotate(sprite, 6)
        apex_frame = place(apex, -6)
        box = apex_frame.getchannel("A").getbbox()
        frames = [(place(sprite, 0), 0, "原姿"), (place(lean, -3), -3, "倾斜 12° 起跳"),
                  (sparks(apex_frame, box, "kachidoki-apex"), -6, "最高点 -16° + 金白火花（begin+18 读这张）"),
                  (place(land, 0), 0, "落地 6°")]
    elif action == "into_coffin":
        sprite, lie = _need(bases, "front", action), _need(bases, "liedown", action)
        frames = [(place(with_alpha(sprite, f), 0), 0, f"本体 {int(f * 100)}%") for f in (1.0, 0.75, 0.5, 0.25)]
        frames.append((place(lie, 0), 0, "躺倒"))
    elif action == "ghost_raise":
        sprite, lie = _need(bases, "front", action), _need(bases, "liedown", action)
        ghost = ghostify(sprite)
        for step, dy in enumerate((-2, -5, -8, -10, GHOST_DY)):
            factor = (step + 1) / 5
            frames.append((_over(place(lie, 0), place(with_alpha(ghost, factor), dy)), dy,
                           f"躺倒 + 幽灵 {int(factor * 100)}% 升到 dy={dy}"))
    elif action == "ghost_neutral":
        ghost = ghostify(_need(bases, "front", action))
        frames = [(place(ghost, dy), dy, f"悬浮 dy={dy}") for dy in (-12, -13, -14, -13, -12, -11, -12)]
    elif action == "revive":
        sprite = _need(bases, "front", action)
        ghost = ghostify(sprite)
        frames = [(place(ghost, -12), -12, "幽灵"), (place(ghost, -8), -8, "幽灵下落"), (place(ghost, -4), -4, "幽灵下落"),
                  (_over(place(sprite, 0), place(with_alpha(ghost, 0.5), -2)), 0, "幽灵与本体交叠"),
                  (place(whiten(sprite), 0), 0, "全白闪"), (place(sprite, 0), 0, "本体")]
    durations = [ends[0]] + [b - a for a, b in zip(ends, ends[1:])]
    if len(durations) != len(frames):
        raise AssertionError("recipe ends and frames disagree")
    if ground:
        frames = [(_shift(image, ground), dy + ground, note) for image, dy, note in frames]
    return [{"image": image, "duration": duration, "dy": dy, "note": note}
            for (image, dy, note), duration in zip(frames, durations)]
