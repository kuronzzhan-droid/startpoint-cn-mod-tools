"""像素工坊：拆解（analyze）与母本映射（remap）。

只读视图，纯计算；写草稿由 :mod:`wf.studio.pixel_workshop_ops` 负责。

* 拆解：两族（pixelart / special）逐动作列出每张图（图集端点帧号、停留帧数、
  帧框内包围盒、dy/fy、复用的图集区域），未用到的图集区域，调色板（按出现的
  动作分组：本体 / 特效 / 入棺幽灵模板 / 描边），以及已知坑位。
* 母本映射：取另一个角色（母本）的整族四件，按精确 RGB→RGB 表逐像素改色，
  atlas 条目名与 frame.name 的 ``character/<母本>/`` 前缀换成本角色，timeline
  逐字节照搬（区间、锚点、frame.scale 都保留母本）。同输入同输出。

帧号语义沿用 ``wf_pixelart_vfx.entry_for_frame``：图集后缀是「持续到该帧为止」
的末帧号，位置 p 取 ≥p 的最小端点（flatomo FrameAnimationSource）。
"""
from __future__ import annotations

import copy
import hashlib
from bisect import bisect_left
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

import wf_atlas_budget_check as budget
from wf_pixelart_vfx import frame_index, restore_frame

from .deliver_media import encode_png, encode_tree, png, read_root, tree
from .drafts import DraftError

FAMILY_FILES = {"pixelart": ("sprite_sheet", "pixelart"), "special": ("special_sprite_sheet", "special")}
SQUAD_REQUIRED = ("neutral", "walk_back", "walk_front", "skill_ready", "kachidoki", "into_coffin",
                  "ghost_raise", "ghost_neutral", "revive")
SPECIAL_REQUIRED = ("special_land", "special_pose")
BODY_ACTIONS = {"neutral", "walk_back", "walk_front"}
TEMPLATE_ACTIONS = {"into_coffin", "ghost_raise", "ghost_neutral", "revive"}
GROUNDED_ACTIONS = {"neutral", "walk_back", "walk_front", "kachidoki"}
# 通用帧区间（官方全表一致；克隆母本时整族直替的前提）。
UNIVERSAL_RANGES = {
    "pixelart": {"neutral": (1, 2), "walk_back": (3, 26), "walk_front": (27, 50), "skill_ready": (51, 110),
                 "kachidoki": (111, 158), "into_coffin": (159, 200), "ghost_raise": (201, 225),
                 "ghost_neutral": (226, 386), "revive": (387, 428)},
    "special": {"special_land": (1, 187), "special_pose": (188, 292)},
}
OFFICIAL_SCALE = 6
OFFICIAL_LAYER0_MAX_PX = (247 + 2) * (738 + 2)
GROUP_LABELS = {"body": "本体", "fx": "特效", "template": "入棺/幽灵模板", "outline": "描边"}


def family_paths(code: str, family: str) -> list[str]:
    if family not in FAMILY_FILES:
        raise DraftError(f"未知像素族：{family}")
    sheet, stem = FAMILY_FILES[family]
    base = f"character/{code}/pixelart/"
    return [base + sheet + ".png", base + sheet + ".atlas.amf3.deflate",
            base + stem + ".frame.amf3.deflate", base + stem + ".timeline.amf3.deflate"]


def read_family_raw(source, code: str, family: str) -> list[bytes] | None:
    raws = [read_root(source, "common", logical) for logical in family_paths(code, family)]
    if all(raw is None for raw in raws):
        return None
    if any(raw is None for raw in raws):
        raise DraftError(f"{code} 的 {family} 像素族四件不全")
    return raws


def decode_family(raws: list[bytes]) -> dict:
    sheet, atlas, frame, timeline = png(raws[0]), tree(raws[1]), tree(raws[2]), tree(raws[3])
    keys, entries = frame_index(atlas, frame["name"])
    return {"sheet": sheet, "atlas": atlas, "frame": frame, "timeline": timeline, "keys": keys, "entries": entries}


def hexrgb(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb[:3])


def parse_hex(text: str) -> tuple[int, int, int]:
    value = str(text).strip().lstrip("#")
    if len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise DraftError(f"颜色格式应为 #rrggbb：{text!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def luma(rgb) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _region(entry) -> tuple[int, int, int, int, bool]:
    return int(entry["x"]), int(entry["y"]), int(entry["w"]), int(entry["h"]), bool(entry.get("r"))


def _visible(entry) -> tuple[int, int]:
    w, h = int(entry["w"]), int(entry["h"])
    return (h, w) if entry.get("r") else (w, h)


def _sequences(timeline) -> list[dict]:
    return [s for s in timeline.get("sequences", []) or []
            if type(s.get("begin")) is int and type(s.get("end")) is int and s["begin"] <= s["end"]]


def _cells(keys, sequence) -> list[tuple[int, int, int]]:
    """[(endpoint key, start offset, held frames)] for one sequence."""
    cells, position, begin, end = [], sequence["begin"], sequence["begin"], sequence["end"]
    while position <= min(end, keys[-1]):
        key = keys[bisect_left(keys, position)]
        finish = min(end, key)
        cells.append((key, position - begin, finish - position + 1))
        position = finish + 1
    return cells


# ---------------------------------------------------------------------------
# 拆解

def analyze_family(data: dict, family: str) -> dict:
    sheet, frame, keys, entries = data["sheet"], data["frame"], data["keys"], data["entries"]
    origin = (-float(frame.get("x", 0)), -float(frame.get("y", 0)))
    sequences = _sequences(data["timeline"])
    region_ids: dict[tuple, int] = {}
    regions: list[dict] = []
    key_region: dict[int, int] = {}
    restored: dict[int, Image.Image] = {}
    for key in keys:
        entry = entries[key]
        region = _region(entry)
        if region not in region_ids:
            region_ids[region] = len(regions)
            x, y, w, h, r = region
            regions.append({"id": len(regions), "x": x, "y": y, "w": w, "h": h, "rotated": r,
                            "keys": [], "actions": []})
        key_region[key] = region_ids[region]
        regions[region_ids[region]]["keys"].append(key)
        restored[key] = restore_frame(sheet, entry)

    # Identical pixels stored twice = packer did not deduplicate.
    digests: dict[str, list[int]] = defaultdict(list)
    region_alpha: dict[int, int] = {}
    for region in regions:
        x, y, w, h = region["x"], region["y"], region["w"], region["h"]
        tile = sheet.crop((x, y, x + w, y + h))
        digests[hashlib.sha1(tile.tobytes() + bytes([region["rotated"]])).hexdigest()].append(region["id"])
        region_alpha[region["id"]] = int(np.count_nonzero(np.asarray(tile.getchannel("A"))))
        region["alphaPx"] = region_alpha[region["id"]]
    duplicates = [ids for ids in digests.values() if len(ids) > 1]

    used_keys: set[int] = set()
    actions = []
    for sequence in sequences:
        cells = []
        for key, start, held in _cells(keys, sequence):
            used_keys.add(key)
            entry = entries[key]
            w, h = _visible(entry)
            fx, fy = int(entry.get("fx", 0)), int(entry.get("fy", 0))
            left, top = -fx, -fy
            box = restored[key].getbbox()
            region = key_region[key]
            if sequence["name"] not in regions[region]["actions"]:
                regions[region]["actions"].append(sequence["name"])
            cells.append({
                "key": key, "cell": keys.index(key), "start": start, "frames": held, "region": region,
                "fx": fx, "fy": fy, "w": w, "h": h,
                # dy: 脚底（可见底边）相对原点的下沉量；fy = -(originY - h + dy)
                "dy": round(top + h - origin[1], 2),
                "dx": round(left + w / 2 - origin[0], 2),
                "bbox": list(box) if box else None, "alphaPx": region_alpha[region],
            })
        actions.append({"name": sequence["name"], "kind": sequence.get("kind"), "begin": sequence["begin"],
                        "end": sequence["end"], "totalFrames": sequence["end"] - sequence["begin"] + 1,
                        "cells": cells,
                        "universal": UNIVERSAL_RANGES[family].get(sequence["name"]) ==
                                     (sequence["begin"], sequence["end"])})
    unused_keys = [k for k in keys if k not in used_keys]
    referenced = {key_region[k] for k in used_keys}
    unused_regions = [r["id"] for r in regions if r["id"] not in referenced]
    region_area = sum(r["w"] * r["h"] for r in regions)
    sheet_w, sheet_h = sheet.size
    layer0 = (sheet_w + 2) * (sheet_h + 2)
    return {
        "family": family, "sheet": {"width": sheet_w, "height": sheet_h, "fill": round(region_area / max(1, sheet_w * sheet_h), 4),
                                    "layer0Px": layer0 if family == "pixelart" else 0,
                                    "share": round(budget.rect_area((sheet_w, sheet_h)) / budget.CAPACITY * 100, 3)},
        "frame": {"name": frame.get("name"), "x": frame.get("x"), "y": frame.get("y"), "scale": frame.get("scale"),
                  "smoothing": bool(frame.get("smoothing", False))},
        "origin": list(origin), "keys": len(keys), "regions": regions, "actions": actions,
        "unusedKeys": unused_keys, "unusedRegions": unused_regions, "duplicateRegions": duplicates,
        "points": len(data["timeline"].get("points") or []), "sounds": len(data["timeline"].get("sounds") or []),
        "_restored": restored, "_keyRegion": key_region,
    }


def _palette(families: dict[str, dict]) -> list[dict]:
    """颜色 → 出现的动作、像素数；分组启发：本体动作里出现 = 本体。"""
    seen: dict[tuple, dict] = {}
    for family, info in families.items():
        restored = info["_restored"]
        counted_regions: set[int] = set()
        region_colors: dict[int, Counter] = {}
        for action in info["actions"]:
            for cell in action["cells"]:
                region = cell["region"]
                if region not in region_colors:
                    pixels = np.asarray(restored[cell["key"]])
                    mask = pixels[..., 3] > 0
                    colors = Counter(map(tuple, pixels[mask][:, :3].tolist()))
                    region_colors[region] = colors
                first = region not in counted_regions
                counted_regions.add(region)
                for rgb, count in region_colors[region].items():
                    item = seen.setdefault(rgb, {"count": 0, "actions": set(), "families": set(), "regions": 0})
                    item["actions"].add(action["name"])
                    item["families"].add(family)
                    if first:  # pixel counts per distinct atlas region, not per reuse
                        item["count"] += count
                        item["regions"] += 1
    palette = []
    for rgb, item in seen.items():
        actions = item["actions"]
        if max(rgb) < 48:
            group = "outline"
        elif actions & BODY_ACTIONS:
            group = "body"
        elif actions <= TEMPLATE_ACTIONS:
            group = "template"
        else:
            group = "fx"
        palette.append({"hex": hexrgb(rgb), "rgb": list(rgb), "count": item["count"], "regions": item["regions"],
                        "luma": round(luma(rgb), 1), "group": group,
                        "actions": sorted(actions), "families": sorted(item["families"])})
    order = {"body": 0, "outline": 1, "fx": 2, "template": 3}
    palette.sort(key=lambda p: (order[p["group"]], -p["count"], p["hex"]))
    return palette


def _traps(family: str, info: dict) -> list[dict]:
    checks: list[dict] = []
    actions = {a["name"]: a for a in info["actions"]}
    neutral = actions.get("neutral") or (info["actions"][0] if info["actions"] else None)
    required = SQUAD_REQUIRED if family == "pixelart" else SPECIAL_REQUIRED
    missing = [n for n in required if n not in actions]
    if missing:
        checks.append({"level": "warn" if family == "pixelart" else "error", "code": "workshop.missing_sequence",
                       "message": f"缺少必需动作 {', '.join(missing)}" + (
                           "：★4+ 获取演出硬读 special_land/special_pose，缺标签客户端直接 throw" if family == "special" else
                           "：队员只会播 9 个标准序列")})
    scale = info["frame"]["scale"]
    if scale != OFFICIAL_SCALE:
        checks.append({"level": "warn", "code": "workshop.scale",
                       "message": f"frame.scale = {scale}，官方全角色恒为 6；其它值意味着帧画大/画小了"})
    if (info["frame"]["x"], info["frame"]["y"]) != (-128, -128):
        checks.append({"level": "info", "code": "workshop.frame_origin",
                       "message": f"frame 原点 ({info['frame']['x']}, {info['frame']['y']}) 不是官方 (-128,-128)；"
                                  "角色格子里会偏移，见 wf_pixel_frame_align"})
    if neutral and neutral["cells"]:
        base_alpha = float(np.median([c["alphaPx"] for c in neutral["cells"]]))
        base_dy = float(np.median([c["dy"] for c in neutral["cells"]]))
        base_dx = float(np.median([c["dx"] for c in neutral["cells"]]))
        base_h = max(c["h"] for c in neutral["cells"])
        base_w = max(c["w"] for c in neutral["cells"])
        for name in ("walk_back", "walk_front"):
            action = actions.get(name)
            if not action:
                continue
            faint = [c for c in action["cells"] if c["alphaPx"] < 0.35 * base_alpha]
            if faint:
                checks.append({"level": "warn", "code": "workshop.walk_teleport",
                               "message": f"{name} 有 {len(faint)}/{len(action['cells'])} 张图可见像素不到待机的 35%"
                                          f"（端点 {', '.join(str(c['key']) for c in faint[:8])}）：这是瞬移消散式走路，"
                                          "队员移动时会一闪一闪（白虎实例）"})
        for name, action in actions.items():
            if name not in GROUNDED_ACTIONS or not action["cells"]:
                continue
            dy = float(np.median([c["dy"] for c in action["cells"]]))
            dx = float(np.median([c["dx"] for c in action["cells"]]))
            if abs(dy - base_dy) > 2 or abs(dx - base_dx) > 3:
                checks.append({"level": "warn", "code": "workshop.anchor_drift",
                               "message": f"{name} 脚底中位 dy={dy:g}、横心 dx={dx:g}，待机是 dy={base_dy:g}、dx={base_dx:g}："
                                          "锚点漂移（脚底锚应取逐帧底边中位数，不是全局最低点）"})
        big = [(a["name"], c["key"], c["w"], c["h"]) for a in info["actions"] for c in a["cells"]
               if a["name"] != "skill_ready" and (c["h"] > base_h * 1.6 or c["w"] > base_w * 2.5)]
        if big:
            sample = "；".join(f"{n}@{k} {w}×{h}" for n, k, w, h in big[:6])
            checks.append({"level": "info", "code": "workshop.oversized",
                           "message": f"{len(big)} 张图明显大于待机（{base_w}×{base_h}）：{sample}"})
    if family == "pixelart":
        layer0 = info["sheet"]["layer0Px"]
        if layer0 > 1_000_000:
            level, text = "error", "超过 1,000,000 px 问题阈值"
        elif layer0 > OFFICIAL_LAYER0_MAX_PX:
            level, text = "warn", f"超过官方最大 {OFFICIAL_LAYER0_MAX_PX} px（fox_oracle 247×738）"
        else:
            level, text = "info", "在官方范围内"
        checks.append({"level": level, "code": "workshop.atlas_budget",
                       "message": f"sprite_sheet {info['sheet']['width']}×{info['sheet']['height']}，layer0 (w+2)(h+2)="
                                  f"{layer0} px，{text}；填充率 {info['sheet']['fill'] * 100:.1f}%。三人房共享 layer0"})
    if info["duplicateRegions"]:
        extra = sum(len(ids) - 1 for ids in info["duplicateRegions"])
        checks.append({"level": "warn", "code": "workshop.no_dedup",
                       "message": f"{extra} 个图集区域与别的区域逐像素相同：打包器没去重（每 tick 一块矩形），白占图集"})
    if info["unusedRegions"]:
        checks.append({"level": "info", "code": "workshop.unused",
                       "message": f"{len(info['unusedRegions'])} 个图集区域没有任何动作用到"})
    if info["sounds"]:
        checks.append({"level": "info", "code": "workshop.sounds",
                       "message": f"timeline 带 {info['sounds']} 条 sounds：官方小人时间轴通常为空，克隆时别连声音一起搬"})
    return checks


def analyze(source, code: str) -> dict:
    families: dict[str, dict] = {}
    for family in FAMILY_FILES:
        raws = read_family_raw(source, code, family)
        if raws is None:
            continue
        families[family] = analyze_family(decode_family(raws), family)
    palette = _palette(families) if families else []
    result = {"code": code, "families": [], "palette": palette, "groupLabels": GROUP_LABELS,
              "universalRanges": UNIVERSAL_RANGES,
              "notes": ["dy = 可见底边相对原点的下沉（正 = 往下沉，负 = 离地）；fy = -(原点Y - h + dy)，fx = -(原点X - w//2)。",
                        "端点帧号 N 覆盖「上一端点+1 .. N」（flatomo END 语义）。",
                        "调色板分组是启发：在待机/走路里出现 = 本体；只在入棺/幽灵/复活出现 = 模板；其余 = 特效；"
                        "近黑（各通道 < 48）= 描边。可以在界面里改。"]}
    for family, info in families.items():
        public = {k: v for k, v in info.items() if not k.startswith("_")}
        public["checks"] = _traps(family, info)
        result["families"].append(public)
    return result


# ---------------------------------------------------------------------------
# 母本映射

def normalize_mapping(mapping) -> dict[tuple, tuple]:
    """[{from:'#..', to:'#..'}] or {'#..': '#..'} → {(r,g,b): (r,g,b)}."""
    pairs = mapping.items() if isinstance(mapping, dict) else (
        (item["from"], item["to"]) for item in mapping or [])
    result: dict[tuple, tuple] = {}
    for src, dst in pairs:
        key = parse_hex(src)
        value = parse_hex(dst)
        if key in result and result[key] != value:
            raise DraftError(f"颜色 {src} 映射了两次")
        result[key] = value
    return result


def recolor(image: Image.Image, mapping: dict[tuple, tuple]) -> tuple[Image.Image, int]:
    """逐像素精确改色，只动 alpha>0 的像素，alpha 原样保留。"""
    pixels = np.array(image.convert("RGBA"), dtype=np.uint8)
    if not mapping:
        return Image.fromarray(pixels, "RGBA"), 0
    packed = (pixels[..., 0].astype(np.uint32) << 16) | (pixels[..., 1].astype(np.uint32) << 8) | pixels[..., 2]
    visible = pixels[..., 3] > 0
    changed = 0
    out = pixels.copy()
    for (r, g, b), (nr, ng, nb) in sorted(mapping.items()):
        hit = visible & (packed == ((r << 16) | (g << 8) | b))
        count = int(np.count_nonzero(hit))
        if count and (r, g, b) != (nr, ng, nb):
            out[hit, 0], out[hit, 1], out[hit, 2] = nr, ng, nb
            changed += count
    return Image.fromarray(out, "RGBA"), changed


def _reprefix(value: str, old: str, new: str) -> str:
    return new + value[len(old):] if isinstance(value, str) and value.startswith(old) else value


def remap_family(base_raws: list[bytes], base_code: str, target_code: str, mapping: dict[tuple, tuple]) -> dict:
    """Return stored-state bytes of the 4 files plus the decoded pieces and stats."""
    data = decode_family(base_raws)
    old, new = f"character/{base_code}/", f"character/{target_code}/"
    sheet, changed = recolor(data["sheet"], mapping)
    atlas = copy.deepcopy(data["atlas"])
    renamed = 0
    for entry in atlas:
        if isinstance(entry, dict) and isinstance(entry.get("n"), str) and entry["n"].startswith(old):
            entry["n"] = _reprefix(entry["n"], old, new)
            renamed += 1
    frame = copy.deepcopy(data["frame"])
    frame["name"] = _reprefix(frame.get("name", ""), old, new)
    if base_code != target_code and not frame["name"].startswith(new):
        raise DraftError(f"母本 frame.name 不以 {old} 开头，无法改前缀：{data['frame'].get('name')}")
    frame_index(atlas, frame["name"])  # every endpoint must still resolve under the new prefix
    stored = [encode_png(sheet),
              base_raws[1] if base_code == target_code else encode_tree(atlas),
              base_raws[2] if base_code == target_code else encode_tree(frame),
              base_raws[3]]
    return {"stored": stored, "sheet": sheet, "atlas": atlas, "frame": frame,
            "changedPixels": changed, "renamedEntries": renamed}


def suggest_mapping(base_palette: list[dict], target_palette: list[dict]) -> list[dict]:
    """同组内按明度排名一一对应（描边与模板默认不改）。"""
    suggestions = []
    by_group = defaultdict(list)
    for item in target_palette:
        by_group[item["group"]].append(item)
    for group in ("body", "fx"):
        source = sorted([p for p in base_palette if p["group"] == group], key=lambda p: p["luma"])
        target = sorted(by_group[group], key=lambda p: p["luma"])
        if not source or not target:
            continue
        for index, item in enumerate(source):
            pick = target[min(len(target) - 1, round(index * (len(target) - 1) / max(1, len(source) - 1)))]
            suggestions.append({"from": item["hex"], "to": pick["hex"], "group": group})
    return suggestions
