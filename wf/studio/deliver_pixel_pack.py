"""Reclaim replaced atlas regions and account for the battle layer0 margin."""
from __future__ import annotations

from PIL import Image, ImageChops

from .drafts import DraftError

# Same official maximum (fox_oracle, 247 x 738) as pixel_import's save check.
OFFICIAL_LAYER0_MAX_PX = (247 + 2) * (738 + 2)
LAYER0_PROBLEM_PX = 1_000_000


def _region(entry):
    x, y, w, h = (int(entry[k]) for k in ("x", "y", "w", "h"))
    return x, y, x + w, y + h


def _subtract(free, used):
    x, y, right, bottom = free
    a, b, c, d = used
    if c <= x or a >= right or d <= y or b >= bottom:
        return [free]
    return [box for box in ((x, y, min(a, right), bottom), (max(c, x), y, right, bottom),
                            (x, y, right, min(b, bottom)), (x, max(d, y), right, bottom))
            if box[2] > box[0] and box[3] > box[1]]


def _prune(rects):
    unique = sorted(set(rects))
    return [r for r in unique if not any(r != s and s[0] <= r[0] and s[1] <= r[1]
                                        and s[2] >= r[2] and s[3] >= r[3] for s in unique)]


def _cleared(original, atlas, retained):
    protected = {_region(entry) for entry in retained}
    removed = {_region(entry) for entry in atlas} - protected
    holes = list(removed)
    for region in protected:
        holes = [part for hole in holes for part in _subtract(hole, region)]
    cleaned = original.copy()
    for hole in holes:
        cleaned.paste((0, 0, 0, 0), hole)
    # Preserve even hidden RGB outside reclaimed regions, plus transparent
    # rectangles still referenced by the atlas. Only an unused tail is trimmed.
    occupied = Image.new("L", original.size)
    for channel in cleaned.split():
        occupied = ImageChops.lighter(occupied, channel)
    box = occupied.getbbox()
    width = max([1, box[2] + 1 if box else 1] + [r[2] + 1 for r in protected])
    height = max([1, box[3] + 1 if box else 1] + [r[3] + 1 for r in protected])
    width, height = min(original.width, width), min(original.height, height)
    return cleaned.crop((0, 0, width, height)), _prune(holes)


def _pack_positions(width, height, original, holes, images):
    # Inside the surviving original rectangle, only reclaimed regions are free.
    free = [(max(0, a), max(0, b), min(width, c), min(height, d)) for a, b, c, d in holes]
    free += [(original.width, 0, width, height), (0, original.height, width, height)]
    free = _prune([r for r in free if r[2] > r[0] and r[3] > r[1]])
    positions = [None] * len(images)
    for index in sorted(range(len(images)), key=lambda i: (-images[i].width * images[i].height, i)):
        image = images[index]
        available = [r for r in free if r[2] - r[0] >= image.width and r[3] - r[1] >= image.height]
        if not available:
            return None
        chosen = min(available, key=lambda r: (min(r[2] - r[0] - image.width, r[3] - r[1] - image.height),
                                               r[1], r[0]))
        x, y = chosen[:2]
        positions[index] = (x, y)
        # One blank pixel separates new frames; an exact old hole can be reused.
        used = (x, y, x + image.width + 1, y + image.height + 1)
        free = _prune([part for rect in free for part in _subtract(rect, used)])
    return positions


def repack(original, atlas, retained, images, maximum):
    cleaned, holes = _cleared(original, atlas, retained)
    candidates = []
    for width in sorted({cleaned.width, 128, 256, 384, 512, 768, 1024, 2048, maximum}):
        if not cleaned.width <= width <= maximum or cleaned.height > maximum:
            continue
        positions = _pack_positions(width, maximum, cleaned, holes, images)
        if positions is None:
            continue
        actual_w = max([cleaned.width] + [x + im.width for (x, y), im in zip(positions, images)])
        actual_h = max([cleaned.height] + [y + im.height for (x, y), im in zip(positions, images)])
        candidates.append((actual_w * actual_h, actual_w, actual_h, positions))
    if not candidates:
        raise DraftError("问题：像素图集预算超过 4096²（包含战斗图集 margin），不能生成")
    _, width, height, positions = min(candidates, key=lambda row: row[:3])
    packed = Image.new("RGBA", (width, height))
    packed.paste(cleaned, (0, 0))
    for image, point in zip(images, positions):
        packed.paste(image, point)
    return packed, positions


def budget_check(family, packed):
    width, height = packed.size
    battle = family == "pixelart"
    pixels = (width + 2) * (height + 2) if battle else 0
    state = "问题" if pixels > LAYER0_PROBLEM_PX else "待验证" if pixels > OFFICIAL_LAYER0_MAX_PX else "满足"
    message = (f"pixelart 实际图集 {width}×{height}，layer0 占用 (w+2)(h+2)={pixels} px；"
               f"官方最大 {OFFICIAL_LAYER0_MAX_PX} px，问题阈值 {LAYER0_PROBLEM_PX} px；"
               "三人房共享 layer0，编队总预算仍需验证；frame.scale/锚点保留") if battle else (
                   f"special 实际图集 {width}×{height}，战斗不加载、不占 layer0；frame.scale/锚点保留")
    return {"state": state, "code": "studio.pixel.budget", "message": message, "blocking": state == "问题",
            "family": family, "width": width, "height": height, "loadedInBattle": battle,
            "layer0Pixels": pixels, "officialLayer0MaxPixels": OFFICIAL_LAYER0_MAX_PX,
            "problemLayer0Pixels": LAYER0_PROBLEM_PX}
