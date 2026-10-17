"""Production primitives extracted from wf_seasonal7_art.py (C baseline)."""
from __future__ import annotations
import json


from pathlib import Path


import io


import numpy as np


import wf_assets


from wf.chars.support import images as images


from wf.chars.support import common as C


from wf.chars.support import specs as S


import wf_ui_derive_gate as gate


MASK_SAMPLE = 120                 # 每槽每立绘槽取的官方角色数（两槽合并 = 240 张）


MASK_METHOD = "official-baseline median alpha, levels 0+1 pooled"


def default_mask_cache(root: Path) -> Path:
    return root / S.BATCH_DIR / "art" / "official-shape-masks.npz"


def shape_masks_from_samples(samples: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    """槽 -> 官方 alpha 样本列表 ⇒ 逐像素中位数（uint8）。中位数 >127 ⇔ 过半样本该像素不透明：
    共享框的抗锯齿边保留，个别角色的剪影/出框头发被多数票抹掉。"""
    masks = {}
    for slot, stack in samples.items():
        want = gate.OFFICIAL_ICON_SIZES[slot]
        good = [a for a in stack if a.shape[::-1] == want]
        if len(good) < 16:
            raise ValueError(f"too few official samples for {slot}: {len(good)}")
        masks[slot] = np.median(np.stack(good), axis=0).astype(np.uint8)
    return masks


def _official_samples(pack: C.S7Pack, sample: int) -> tuple[dict[str, list[np.ndarray]], dict]:
    from PIL import Image
    raw_table = pack.official_read("master/character/character.orderedmap", "common")
    if raw_table is None:
        raise ValueError("official baseline unavailable: cannot derive shape masks")
    rows = C.core.read_orderedmap_file_from_bytes(raw_table)
    codes = []
    for _cid, text in sorted(rows.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        cells = C.csv_split(text)
        if cells and cells[0] and cells[0][0]:
            codes.append(cells[0][0])
    samples: dict[str, list[np.ndarray]] = {slot: [] for slot in gate.SHAPE_SLOTS}
    used: dict[str, list[str]] = {slot: [] for slot in gate.SHAPE_SLOTS}
    for slot in gate.SHAPE_SLOTS:
        want = gate.OFFICIAL_ICON_SIZES[slot]
        per_level = {"0": 0, "1": 0}
        for code in codes:
            if min(per_level.values()) >= sample:
                break
            for level in ("0", "1"):
                if per_level[level] >= sample:
                    continue
                raw = pack.official_read(f"character/{code}/ui/{slot}_{level}.png", "medium")
                if raw is None:
                    continue
                alpha = np.asarray(Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA"))[:, :, 3]
                if alpha.shape[::-1] != want:
                    continue
                samples[slot].append(alpha)
                per_level[level] += 1
                if not used[slot] or used[slot][-1] != code:
                    used[slot].append(code)
    return samples, {"characters": {slot: len(v) for slot, v in used.items()},
                     "samples": {slot: len(v) for slot, v in samples.items()},
                     "character_list_sha256": {slot: images.sha(json.dumps(v).encode("utf-8"))
                                               for slot, v in used.items()}}


def official_shape_masks(pack: C.S7Pack, *, cache: Path | None = None,
                         sample: int = MASK_SAMPLE) -> tuple[dict[str, np.ndarray], dict]:
    """官方统计形状蒙版（与母本无关），批目录缓存；缓存 sha 不符即报错（不静默重算）。"""
    cache = Path(cache) if cache is not None else default_mask_cache(pack.root)
    meta_path = cache.with_suffix(".json")
    if cache.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("cache_sha256") != images.sha(cache.read_bytes()):
            raise ValueError(f"official shape mask cache changed: {cache}")
        data = np.load(cache)
        return {slot: data[slot] for slot in gate.SHAPE_SLOTS}, meta
    samples, info = _official_samples(pack, sample)
    masks = shape_masks_from_samples(samples)
    stats = {}
    for slot, mask in masks.items():
        on = mask > 127
        ious = [float(((a > 127) & on).sum() / max(1, ((a > 127) | on).sum())) for a in samples[slot]]
        stats[slot] = {"coverage": round(float((mask > gate.ALPHA_ON).mean()), 4),
                       "sample_iou_p10": round(float(np.percentile(ious, 10)), 3),
                       "sample_iou_p50": round(float(np.median(ious)), 3)}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **masks)
    meta = {"method": MASK_METHOD, "sample_per_level": sample, **info, "stats": stats,
            "cache_sha256": images.sha(cache.read_bytes())}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return masks, meta


def _load_masks(pack: C.S7Pack, level: int, mask_cache: Path | None = None) -> tuple[dict, dict]:
    masks, meta = official_shape_masks(pack, cache=mask_cache)
    source = {"method": meta["method"], "cache": str(mask_cache or default_mask_cache(pack.root)),
              "cache_sha256": meta["cache_sha256"], "level": level,
              "coverage": {slot: v["coverage"] for slot, v in meta.get("stats", {}).items()}}
    return masks, source
