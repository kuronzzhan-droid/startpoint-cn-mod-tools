"""已获授权的校园立绘本地透明底恢复；原始 source 永远只读。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checker_background(rgb):
    """仅删除中性棋盘区域：连边背景，及包含两阶灰色的内部空洞。

    限制最高亮度，避免将深灰棋盘旁的白色照片边框串入背景。
    皮肤、头发和衣服不按亮度直接删除。
    """
    gray = rgb.mean(2)
    chroma = np.ptp(rgb.astype(np.int16), axis=2)
    low, high = np.quantile(gray[:100, :100], [.15, .85])
    eligible = (chroma <= 4) & (gray > low - 25) & (gray < high + 15)
    labels, _ = ndimage.label(eligible)
    sizes = np.bincount(labels.ravel())
    border = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    background = np.isin(labels, border[border != 0])
    for label in np.flatnonzero(sizes > 25):
        if label == 0 or label in border:
            continue
        region = labels == label
        lo, hi = np.quantile(gray[region], [.15, .85])
        if lo < low + 12 and hi > high - 12 and hi - lo > (high - low) * .5:
            background |= region
    return background


def recover_effects(rgb, alpha, regions):
    """在人工圈定的透明魔法带内去掉中性底色串色，保留逐像素色相。

    RGB 三通道相减可消去烘焙棋盘的中性亮度。仅对指定彩色特效
    和色差足够的像素应用，白色描边与未圈定的角色本体不改变。
    """
    if not regions:
        return rgb, alpha, 0
    mask = Image.new("L", (rgb.shape[1], rgb.shape[0]))
    draw = ImageDraw.Draw(mask)
    polygons = regions.get("polygons", []) if isinstance(regions, dict) else regions
    for polygon in polygons:
        draw.polygon([tuple(point) for point in polygon], fill=255)
    if isinstance(regions, dict):
        for polygon in regions.get("exclude_polygons", []):
            draw.polygon([tuple(point) for point in polygon], fill=0)
        for x, y, radius in regions.get("exclude_circles", []):
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=0)
    values = rgb.astype(float)
    color = values - values.min(2, keepdims=True)
    chroma = color.max(2)
    selected = (np.asarray(mask) > 0) & (chroma > 20) & (alpha > 0)
    purple = isinstance(regions, dict) and regions.get("color") == "purple"
    if purple:
        selected &= (values[:, :, 2] > values[:, :, 1] + 20) & (values[:, :, 0] > values[:, :, 1] + 10)
        selected &= values.max(2) > 185
        foreground = np.array([193, 102, 255])
    else:
        selected &= (values[:, :, 1] > values[:, :, 0] + 20) & (values[:, :, 2] > values[:, :, 0] + 15)
        foreground = np.array([84, 250, 227])
    weights = ndimage.gaussian_filter(selected.astype(float), 7)
    smooth_chroma = ndimage.gaussian_filter(chroma * selected, 7) / np.maximum(weights, .001)
    opacity = np.clip(smooth_chroma / 145, 0, 1) ** .85 * 255
    rgb = rgb.copy(); alpha = alpha.copy()
    neutral_halo = ((np.asarray(mask) > 0) & (chroma < 20)
                    & (values.min(2) > 95) & (values.max(2) < 225))
    alpha[neutral_halo] = 0
    if purple:
        highlight = np.clip((ndimage.gaussian_filter(values.min(2), .65) - 200) / 50, 0, 1)
        restored = foreground * (1 - highlight[:, :, None]) + 255 * highlight[:, :, None]
        rgb[selected] = restored[selected].astype(np.uint8)
    else:
        rgb[selected] = foreground
    alpha[selected] = np.minimum(alpha[selected], opacity[selected])
    return rgb, alpha, int(selected.sum())


def repair_alpha(rgb, alpha, repairs):
    """人工 QA 的窄范围回填/清底；每项有明确颜色谓词，避免整框误抠。"""
    values = rgb.astype(float)
    for repair in repairs:
        mask = Image.new("L", (rgb.shape[1], rgb.shape[0]))
        draw = ImageDraw.Draw(mask)
        draw.polygon([tuple(point) for point in repair["polygon"]], fill=255)
        for x, y, radius in repair.get("exclude_circles", []):
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=0)
        selected = np.asarray(mask) > 0
        if repair["mode"] == "restore_warm_paper":
            selected &= ((values[:, :, 0] > 220) & (values[:, :, 1] > 200)
                         & (values[:, :, 2] > 170) & (values[:, :, 0] - values[:, :, 2] > 8))
            alpha[selected] = 255
        elif repair["mode"] == "restore_bright_paper":
            selected &= (values.min(2) > 215) & (values.max(2) > 230)
            alpha[selected] = 255
        elif repair["mode"] == "clear_neutral":
            selected &= ((np.ptp(values, axis=2) < repair.get("chroma", 30))
                         & (values.min(2) > 95) & (values.max(2) < repair.get("max_value", 225)))
            alpha[selected] = 0
        else:
            raise ValueError("unknown reviewed alpha repair")
    return alpha


def build(source, output, *, model, cache, regions=(), repairs=()):
    from rembg import new_session, remove
    if source.resolve() == output.resolve() or not source.stem.endswith("-source"):
        raise ValueError("source must stay read-only and retain -source name")
    raw = Image.open(source).convert("RGB")
    rgb = np.asarray(raw)
    cache.mkdir(parents=True, exist_ok=True)
    model_name = "isnet-anime" if model == "anime" else "isnet-general-use"
    mask_path = cache / f"{source.stem}-{model}-verified-mask.png"
    metadata_path = mask_path.with_suffix(".json")
    source_sha = digest(source)
    if mask_path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_bytes())
        if metadata["source_sha256"] != source_sha or metadata["mask_sha256"] != digest(mask_path):
            raise ValueError("matting model cache drift")
        mask = Image.open(mask_path).convert("L")
    else:
        session = new_session(model_name, providers=["CPUExecutionProvider"])
        mask = remove(raw, session=session, only_mask=True).convert("L")
        mask.save(mask_path)
        metadata_path.write_text(json.dumps(dict(source_sha256=source_sha,
            mask_sha256=digest(mask_path), model=model_name), indent=2), encoding="utf-8")
    # 模型倾向把独立纸张和地面压成半透明；恢复其实体不透明度。
    alpha = np.clip((np.asarray(mask).astype(float) - 10) * 255 / 120, 0, 255)
    background = checker_background(rgb)
    alpha[background] = 0
    rgb, alpha, corrected = recover_effects(rgb, alpha, regions)
    alpha = repair_alpha(rgb, alpha, repairs)
    components, _ = ndimage.label(alpha > 0)
    area = np.bincount(components.ravel())
    alpha[np.isin(components, np.flatnonzero(area < 8))] = 0
    rgba = np.dstack((rgb, alpha.astype(np.uint8)))
    rgba[rgba[:, :, 3] == 0, :3] = 0
    Image.fromarray(rgba).save(output, optimize=True)
    if digest(source) != source_sha:
        raise ValueError("source unexpectedly changed")
    report = dict(source=str(source), source_sha256=source_sha, output=str(output),
                  output_sha256=digest(output), model=model_name, size=list(raw.size),
                  transparent_ratio=float((alpha == 0).mean()),
                  solid_ratio=float((alpha > 240).mean()), corrected_effect_pixels=corrected,
                  reviewed_repairs=repairs,
                  local_alpha_processing=True, original_source_unchanged=True)
    output.with_suffix(".matte.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", choices=("anime", "general"), default="anime")
    parser.add_argument("--regions", type=Path)
    parser.add_argument("--repairs", type=Path)
    args = parser.parse_args()
    regions = json.loads(args.regions.read_bytes()) if args.regions else []
    repairs = json.loads(args.repairs.read_bytes()) if args.repairs else []
    print(json.dumps(build(args.source, args.output, model=args.model,
                           cache=args.output.parent / "matting", regions=regions, repairs=repairs)))
