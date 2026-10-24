"""图集重排优化：MaxRects 重排一族像素的 sprite_sheet，重排后证明与原图集等价。

只搬整块图集矩形（``wf_battle_atlas_repack``：不裁边、不旋转、不重采样、不合并
不同区域，每块前留 2px 间隙），在一组候选宽度 × 两种排序里挑面积最小的结果。

等价校验两道，任何一道不过都不给结果：

1. ``repack_atlas`` 自带：除 x/y 以外的 atlas 记录逐条相同，按记录顺序取出的
   像素块哈希（content signature）相同；
2. 这里再按游戏的还原方式（``restore_frame``：旋转、fx/fy 偏移、未裁剪帧框）
   把**每个端点**从新旧两张图各还原一遍，逐字节比对；frame / timeline 原样不动。

写进草稿时是一条整族替换（``pixel_family``，mode=import，来源记重排参数与
两个签名），生成时与「整族导入」走同一条编译路径。
"""
from __future__ import annotations

import math

import wf_assets
import wf_atlas_budget_check as budget
import wf_battle_atlas_repack as repack
from wf_pixelart_vfx import frame_index, restore_frame

from . import scratch
from .drafts import DraftError, sha256
from .pixel_workshop import decode_family, family_paths, read_family_raw

MAX_SIDE = 2048
GAP = 2
SORT_MODES = ("height", "area")


def candidate_widths(regions: list, current_width: int, gap: int = GAP, limit: int = 40) -> list[int]:
    widest = max(r.w for r in regions) + gap
    area = sum((r.w + gap) * (r.h + gap) for r in regions)
    top = min(MAX_SIDE, max(widest, current_width, int(math.sqrt(area) * 3)))
    widths = {widest, min(MAX_SIDE, max(widest, current_width))}
    widths.update(p for p in (64, 128, 256, 512, 1024, 2048) if widest <= p <= top)
    if top > widest:
        steps = limit - len(widths)
        ratio = (top / widest) ** (1 / max(1, steps))
        value = float(widest)
        for _ in range(steps):
            value *= ratio
            widths.add(min(top, int(round(value))))
    return sorted(widths)


def best_layout(regions: list, current_width: int, gap: int = GAP) -> dict | None:
    best = None
    for width in candidate_widths(regions, current_width, gap):
        for mode in SORT_MODES:
            try:
                _, size = repack.pack_regions(regions, target_width=width, max_height=MAX_SIDE, gap=gap, sort_mode=mode)
            except ValueError:
                continue
            score = (size[0] * size[1], max(size), abs(size[0] - size[1]))
            if best is None or score < best["score"]:
                best = {"score": score, "targetWidth": width, "sortMode": mode, "size": size}
    return best


def verify_frames(old_raws: list[bytes], new_png: bytes, new_atlas: bytes) -> int:
    """Restore every endpoint from the old and the new sheet the way the game does; compare bytes."""
    old = decode_family(old_raws)
    new_sheet = repack.decode_png(new_png)
    new_atlas_tree = repack.decode_atlas(new_atlas)
    keys, entries = frame_index(new_atlas_tree, old["frame"]["name"])
    if keys != old["keys"]:
        raise DraftError("等价校验失败：重排后端点列表变了")
    for key in keys:
        before = restore_frame(old["sheet"], old["entries"][key])
        after = restore_frame(new_sheet, entries[key])
        if before.size != after.size or before.tobytes() != after.tobytes():
            raise DraftError(f"等价校验失败：端点 {key} 还原后的像素不一致")
    return len(keys)


def optimize(source, code: str, family: str) -> dict:
    """Best repack of one family of the given view (no writes)."""
    raws = read_family_raw(source, code, family)
    if raws is None:
        raise DraftError(f"{code} 没有 {family} 像素族")
    sheet_raw, atlas_raw = raws[0], raws[1]
    try:
        image = repack.decode_png(sheet_raw)
        records = repack.decode_atlas(atlas_raw)
        regions = repack._validate_source(image, records)
    except ValueError as exc:
        raise DraftError(f"原图集不能安全重排：{exc}") from None
    layout = best_layout(regions, image.width)
    if layout is None:
        raise DraftError(f"{len(regions)} 块区域装不进 {MAX_SIDE}×{MAX_SIDE}")
    try:
        result = repack.repack_atlas(sheet_raw, atlas_raw, target_width=layout["targetWidth"],
                                     max_height=MAX_SIDE, gap=GAP, sort_mode=layout["sortMode"], exact_width=False)
    except (ValueError, AssertionError) as exc:
        raise DraftError(f"重排失败：{exc}") from None
    checked = verify_frames(raws, result.png_payload, result.atlas_payload)
    saving = 1 - result.output_area / result.source_area if result.source_area else 0
    battle = family == "pixelart"
    report = {
        "family": family, "code": code,
        "source": {"width": result.source_size[0], "height": result.source_size[1], "area": result.source_area,
                   "share": round(budget.rect_area(result.source_size) / budget.CAPACITY * 100, 3)},
        "output": {"width": result.output_size[0], "height": result.output_size[1], "area": result.output_area,
                   "share": round(budget.rect_area(result.output_size) / budget.CAPACITY * 100, 3)},
        "records": result.record_count, "regions": result.unique_region_count, "regionArea": result.region_area,
        "fill": round(result.region_area / result.output_area * 100, 1) if result.output_area else 0,
        "saving": round(saving * 100, 1), "worthIt": result.output_area < result.source_area,
        "targetWidth": layout["targetWidth"], "sortMode": layout["sortMode"], "gap": GAP,
        "loadedInBattle": battle,
        "equivalence": {"signature": result.content_signature, "framesCompared": checked,
                        "method": "atlas 记录除 x/y 外逐条相同 + 内容签名相同 + 每个端点按游戏方式还原后逐字节相同"},
    }
    return {"report": report, "png": result.png_payload, "atlas": result.atlas_payload, "raws": raws}


def preview(ops, cid: str, family: str) -> dict:
    if scratch.is_scratch(cid):
        raise DraftError("草稿角色的当前视图是母本整族：先绑定到真实角色再重排")
    code = ops.character(cid)["code"]
    return optimize(ops.source, code, family)


def apply(ops, cid: str, family: str) -> dict:
    """Write the repack as a whole-family replacement (mode=import) into the draft."""
    changeset = ops.store.load(cid)
    if any(c["kind"] == "pixel_family" and c["target"]["family"] == family for c in (changeset or {}).get("changes", [])):
        raise DraftError(f"草稿里已经有 {family} 整族替换：重排只对当前视图做，先撤销那条改动")
    done = preview(ops, cid, family)
    report = done["report"]
    if not report["worthIt"]:
        raise DraftError("重排后不比原图集小，不需要写入")
    code = report["code"]
    paths = family_paths(code, family)
    make = ops._file_maker(cid)
    note = f"图集重排 {report['source']['width']}×{report['source']['height']} → " \
           f"{report['output']['width']}×{report['output']['height']}"
    files = [make(paths[0], "common", wf_assets.png_decode(done["png"]), "png", approximate=False, note=note),
             make(paths[1], "common", done["atlas"], "amf3-deflate", approximate=False, note=note + "；只改 x/y"),
             make(paths[2], "common", done["raws"][2], "amf3-deflate", approximate=False, note="原样"),
             make(paths[3], "common", done["raws"][3], "amf3-deflate", approximate=False, note="原样")]
    checks = [{"level": "info", "code": "atlas.repack",
               "message": f"{note}，省 {report['saving']}%；{report['equivalence']['framesCompared']} 个端点逐字节等价"}]
    params = {"mode": "import", "source": {
        "name": "图集重排（MaxRects）", "code": code, "kind": "atlas_repack",
        "files": {p.rsplit("/", 1)[-1]: sha256(r) for p, r in zip(paths, done["raws"])},
        "repack": {k: report[k] for k in ("targetWidth", "sortMode", "gap", "saving")}
                  | {"from": [report["source"]["width"], report["source"]["height"]],
                     "to": [report["output"]["width"], report["output"]["height"]],
                     "signature": report["equivalence"]["signature"]}}}
    change = {"title": f"像素整族 {family}：图集重排（{note.removeprefix('图集重排 ')}）",
              "target": {"family": family}, "params": params, "files": files, "pending": [], "checks": checks}
    committed = ops._commit(cid, code, "pixel_family", change)
    return {"characterId": cid, "report": report, "change": committed["change"], "status": committed["status"]}
