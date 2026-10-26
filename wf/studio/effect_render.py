"""Bake a flatomo PartsAnimation battle effect for the L2 timeline preview.

A battle effect is ``<dir>/<name>.parts`` + ``<dir>/<name>.timeline``; its images
are sub-textures ``.gen/<name>/<frame>`` of the directory atlas
``<dir>/<dirname>.png`` + ``.atlas``. The parts document is a tree of groups
whose segments place images (kind 0) or nested groups (kind 2) with 4096
fixed-point matrices, optional tweens, alpha and blend mode.

``bake`` flattens the root group into per-frame draw commands
``[cell, a, b, c, d, tx, ty, alpha, blend]`` and repacks the referenced images
(un-rotated) into one PNG. The browser composes ``container × matrix`` and draws
each cell at ``(-fx, -fy)``: the layer origin is the **frame box top-left**
(Starling trim offsets), so mirrored layers (a = -1) flip around the box corner
exactly like the client. This is the pivot fix from the old desktop renderer.

Approximations: colour transforms (``c``) and MovieClip segments are not applied;
the browser maps blend modes to canvas composite operations.
"""
from __future__ import annotations

import io
import math
import zlib

from PIL import Image

import wf_assets
import wf_mod_tool as core

RESOLUTION = 4096.0
MASK_30 = 0x3FFFFFFF
FRAME_CAP = 2400          # longest root group the preview bakes (40 s)
COMMAND_CAP = 400_000     # total draw commands per effect
SHEET_MAX = 4096
BLEND = {0: "inherit", 1: "add", 2: "multiply", 3: "overlay", 4: "screen"}


def _tree(raw: bytes):
    decoder = zlib.decompressobj(-15)
    data = decoder.decompress(raw, 32 * 1024 * 1024)
    if not decoder.eof:
        raise ValueError("特效元数据超出限额或不完整")
    return core.AMF3Reader(data).read_value()


def effect_files(path: str) -> dict[str, str]:
    directory, _, name = path.rpartition("/")
    folder = directory.rsplit("/", 1)[-1]
    return {"parts": f"{path}.parts.amf3.deflate", "timeline": f"{path}.timeline.amf3.deflate",
            "png": f"{directory}/{folder}.png", "atlas": f"{directory}/{folder}.atlas.amf3.deflate",
            "name": name}


def read_timeline(source, path: str) -> dict | None:
    raw = source.raw(effect_files(path)["timeline"])
    return None if raw is None else _tree(raw)


def read_parts(source, path: str) -> dict | None:
    raw = source.raw(effect_files(path)["parts"])
    return None if raw is None else _tree(raw)


def _u32(value) -> int:
    return int(value) & 0xFFFFFFFF


def _matrix(record) -> tuple:
    return tuple(float(record.get(key, 0)) / RESOLUTION for key in ("a", "b", "c", "d", "x", "y"))


def _key(key, matrices) -> tuple:
    packed = int(key.get("m", 255))
    index = packed >> 12
    matrix = matrices[index] if 0 <= index < len(matrices) else (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return matrix, (packed & 0xFF) / 255.0, (packed >> 8) & 0xF


def _ease(packed: int, progress: float, customs: list) -> float:
    kind = (packed >> 16) & 3
    value = packed >> 18
    if kind == 2:
        easing = (value - 63) / 100.0
        if easing == 0:
            return progress
        if easing < 0:
            return progress * (progress * -easing + (1.0 + easing))
        return progress * ((2.0 - progress) * easing + (1.0 - easing))
    if kind == 1 and 0 <= value < len(customs):
        return _custom(customs[value], progress)
    return progress


def _bezier(t, c1, c2):
    u = 1.0 - t
    return 3 * u * u * t * c1 + 3 * u * t * t * c2 + t * t * t


def _custom(resource, progress):
    top = 1_000_000.0
    count = (len(resource) + 2) // 6
    if count <= 0:
        return progress
    segment = 0
    for index in range(1, count):
        if progress < resource[index * 6 - 2] / top:
            break
        segment = index
    lx, ly = (0.0, 0.0) if segment == 0 else (resource[segment * 6 - 2] / top, resource[segment * 6 - 1] / top)
    rx, ry = (1.0, 1.0) if segment == count - 1 else (resource[segment * 6 + 4] / top, resource[segment * 6 + 5] / top)
    if rx == lx or ry == ly:
        return progress
    c1x = (resource[segment * 6] / top - lx) / (rx - lx)
    c1y = (resource[segment * 6 + 1] / top - ly) / (ry - ly)
    c2x = (resource[segment * 6 + 2] / top - lx) / (rx - lx)
    c2y = (resource[segment * 6 + 3] / top - ly) / (ry - ly)
    x = (progress - lx) / (rx - lx)
    low, high = 0.0, 1.0
    for _ in range(20):
        middle = (low + high) / 2
        if _bezier(middle, c1x, c2x) < x:
            low = middle
        else:
            high = middle
    y = _bezier((low + high) / 2, c1y, c2y)
    return ly * (1 - y) + ry * y


def _child_frame(loop_kind, start, offset, total):
    if loop_kind == 0:
        return start
    if loop_kind == 1:
        return min(start + offset, total - 1)
    if loop_kind == 2:
        return (start + offset) % total if total else 0
    return total


def build_states(parts: dict) -> tuple[list, bool]:
    """Per group, per frame: list of (kind, item, child_frame, matrix, alpha, blend)."""
    matrices = [_matrix(record) for record in parts.get("t", [])]
    customs = [list(map(int, resource)) for resource in parts.get("c", []) or []]
    groups = parts.get("g", [])
    frames = [[[] for _ in range(min(int(group.get("t", 0)), FRAME_CAP))] for group in groups]
    partial = False
    for gi, group in enumerate(groups):
        slots = frames[gi]
        for segment in group.get("s", []):
            packed = _u32(segment.get("s", 0))
            kind, start = packed >> 30, packed & MASK_30
            item = int(segment.get("i", 0))
            if kind == 1:
                partial = True  # MovieClip segment: not rendered by the preview
                continue
            child_total = len(frames[item]) if kind == 2 and 0 <= item < len(frames) else 0
            elapsed = 0
            keys = segment.get("l", [])
            for index, key in enumerate(keys):
                packed_t = int(key.get("t", 1))
                duration = packed_t & 0xFFFF
                tween = (packed_t >> 16) & 3
                matrix, alpha, blend = _key(key, matrices)
                nxt = _key(keys[index + 1], matrices) if tween and index + 1 < len(keys) else None
                for offset in range(duration):
                    at = start + elapsed + offset
                    if at >= len(slots):
                        break
                    m, a = matrix, alpha
                    if nxt and offset:
                        r = _ease(packed_t, offset / duration, customs)
                        m = tuple(p * (1 - r) + q * r for p, q in zip(matrix, nxt[0]))
                        a = alpha * (1 - r) + nxt[1] * r
                    child = 0
                    if kind == 2:
                        loop = _u32(key.get("r", 0))
                        child = _child_frame(loop >> 30, loop & MASK_30, offset, child_total)
                        if child >= child_total:
                            continue
                    slots[at].append((kind, item, child, m, a, blend))
                elapsed += duration
    return frames, partial


def _concat(local, parent):
    a, b, c, d, tx, ty = local
    pa, pb, pc, pd, ptx, pty = parent
    return (a * pa + b * pc, a * pb + b * pd, c * pa + d * pc, c * pb + d * pd,
            tx * pa + ty * pc + ptx, tx * pb + ty * pd + pty)


def flatten(frames, group, frame, parent=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0), alpha=1.0, blend=0, depth=0):
    if depth > 32 or group >= len(frames) or frame >= len(frames[group]):
        return []
    out = []
    for kind, item, child, matrix, a, b in frames[group][frame]:
        m = _concat(matrix, parent)
        mode = b or blend
        if kind == 0:
            out.append((item, m, alpha * a, mode))
        elif kind == 2:
            out.extend(flatten(frames, item, child, m, alpha * a, mode, depth + 1))
    return out


def _crop(sheet: Image.Image, record: dict) -> Image.Image:
    x, y, w, h = (int(record[k]) for k in ("x", "y", "w", "h"))
    tile = sheet.crop((x, y, x + w, y + h))
    if record.get("r"):
        tile = tile.transpose(Image.Transpose.ROTATE_90)
    return tile


def _shelf(sizes: list[tuple[int, int]]) -> tuple[list[tuple[int, int]], int, int]:
    width = 1024
    while True:
        positions, x, y, row = [], 0, 0, 0
        for w, h in sizes:
            if x + w > width:
                x, y, row = 0, y + row + 1, 0
            positions.append((x, y))
            x += w + 1
            row = max(row, h)
        height = y + row
        if height <= width or width >= SHEET_MAX:
            return positions, width, max(1, height)
        width *= 2


def bake(source, path: str) -> tuple[dict, bytes | None]:
    """Return (metadata, repacked PNG) for one effect path; metadata reports what is missing."""
    files = effect_files(path)
    meta: dict = {"path": path, "files": files, "ok": False, "issues": []}
    timeline = read_timeline(source, path)
    parts = read_parts(source, path)
    if timeline is None or parts is None:
        meta["issues"].append("当前视图里没有这个特效的 parts/timeline，只能画占位框")
        return meta, None
    meta["sequences"] = timeline.get("sequences", [])
    meta["sounds"] = timeline.get("sounds", [])
    meta["defaultScale"] = parts.get("s", 1)
    raw_png, raw_atlas = source.raw(files["png"]), source.raw(files["atlas"])
    if raw_png is None or raw_atlas is None:
        meta["issues"].append(f"目录图集缺失：{files['png']}")
        return meta, None
    sheet = Image.open(io.BytesIO(wf_assets.png_decode(raw_png))).convert("RGBA")
    atlas = {str(record.get("n")): record for record in _tree(raw_atlas)}
    cells, tiles, missing = [], [], []
    for image in parts.get("i", []):
        record = atlas.get(str(image.get("p")))
        if record is None:
            missing.append(str(image.get("p")))
            cells.append(None)
            tiles.append(None)
            continue
        tile = _crop(sheet, record)
        tiles.append(tile)
        cells.append({"w": tile.width, "h": tile.height, "fx": int(record.get("fx", 0)),
                      "fy": int(record.get("fy", 0))})
    if missing:
        meta["issues"].append(f"{len(missing)} 张贴图不在目录图集里（{missing[0]} 等），这些图层不画")
    frames, partial = build_states(parts)
    if partial:
        meta["issues"].append("含 MovieClip 段，预览未渲染这些段")
    total = len(frames[0]) if frames else 0
    if frames and int(parts["g"][0].get("t", 0)) > FRAME_CAP:
        meta["issues"].append(f"根组超过 {FRAME_CAP} 帧，只烘焙前 {FRAME_CAP} 帧")
    baked, count = [], 0
    bounds = [math.inf, math.inf, -math.inf, -math.inf]
    for frame in range(total):
        commands = []
        for item, (a, b, c, d, tx, ty), alpha, blend in flatten(frames, 0, frame):
            cell = cells[item] if 0 <= item < len(cells) else None
            if cell is None or alpha <= 0:
                continue
            commands.append([item, round(a, 4), round(b, 4), round(c, 4), round(d, 4),
                             round(tx, 2), round(ty, 2), round(alpha, 3), blend])
            x0, y0 = -cell["fx"], -cell["fy"]
            for x, y in ((x0, y0), (x0 + cell["w"], y0), (x0, y0 + cell["h"]), (x0 + cell["w"], y0 + cell["h"])):
                px, py = a * x + c * y + tx, b * x + d * y + ty
                bounds = [min(bounds[0], px), min(bounds[1], py), max(bounds[2], px), max(bounds[3], py)]
        count += len(commands)
        if count > COMMAND_CAP:
            meta["issues"].append("绘制指令过多，只烘焙到第 %d 帧" % frame)
            break
        baked.append(commands)
    used = [i for i, tile in enumerate(tiles) if tile is not None]
    positions, width, height = _shelf([tiles[i].size for i in used])
    packed = Image.new("RGBA", (width, height))
    for i, (x, y) in zip(used, positions):
        packed.paste(tiles[i], (x, y))
        cells[i].update(x=x, y=y)
    out = io.BytesIO()
    packed.save(out, "PNG", optimize=False)
    meta.update(ok=True, frameCount=total, frames=baked, cells=cells,
                bounds=[round(v, 1) for v in bounds] if bounds[0] != math.inf else None,
                blendModes=BLEND,
                note="图层原点 = 帧框左上角（atlas fx/fy 为负的裁剪偏移）；颜色变换与 MovieClip 段未应用。")
    return meta, out.getvalue()
