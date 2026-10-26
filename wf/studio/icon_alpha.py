"""Compare derived UI alpha with the exact production crop, inside shape masks."""
from __future__ import annotations

import json

import numpy as np
from PIL import Image

import wf_ui_derive_gate as gate
from wf.chars.support import images

THRESHOLD = 0.02
FILL_CODE = "ICON_BACKDROP_FILLS_TRANSPARENCY"


def inspect_icons(master, template, icons, masks, *, form=None, threshold=THRESHOLD):
    """Return one measurement per UI slot; skill_cutin has no UI background gate."""
    results = []
    explicit = template.get("backdrop") is not None
    for slots, (fx, fy, factor) in images.GROUPS:
        spec = template.get("groups", {}).get(slots[0], {})
        crop = images.crop_at(master.convert("RGBA"), template["face"],
                              template["squareHeight"] * spec.get("factor", factor),
                              gate.OFFICIAL_ICON_SIZES[slots[0]], spec.get("anchor", (fx, fy)))
        for slot in slots:
            if slot not in icons:
                continue
            row = {"slot": slot, "form": form, "threshold": threshold,
                   "authorBackdrop": explicit, "blocking": False}
            size = gate.OFFICIAL_ICON_SIZES[slot]
            actual = np.asarray(icons[slot].convert("RGBA"))[:, :, 3]
            if actual.shape != (size[1], size[0]):
                raise ValueError(f"图标尺寸不符：{slot}")
            if slot in gate.SHAPE_SLOTS and slot not in masks:
                results.append({**row, "status": "skipped", "level": "warn",
                                "state": "未执行",
                                "code": "ICON_ALPHA_NOT_CHECKED", "ratio": None,
                                "message": f"{slot}：缺少经校验的形状蒙版，未检查透明区"})
                continue
            alpha = np.asarray(crop.resize(size, Image.Resampling.LANCZOS))[:, :, 3]
            domain = np.ones(alpha.shape, dtype=bool)
            if slot in gate.SHAPE_SLOTS:
                mask = np.asarray(masks[slot])
                if mask.shape != alpha.shape:
                    raise ValueError(f"形状蒙版尺寸不符：{slot}")
                domain = mask >= 128
            transparent = (alpha < 128) & domain
            total = int(transparent.sum())
            filled = int((transparent & (actual >= 128)).sum())
            ratio = filled / total if total else 0.0
            exceeded = ratio > threshold
            note = "；作者选择了底色" if explicit else ""
            results.append({**row, "sourceTransparentPixels": total, "filledPixels": filled,
                            "ratio": ratio, "status": "info" if exceeded and explicit else
                            "warning" if exceeded else "ok",
                            "level": "warn" if exceeded and not explicit else "info",
                            "state": "待验证" if exceeded and not explicit else "满足",
                            "code": FILL_CODE if exceeded else "ICON_ALPHA_PRESERVED",
                            "message": f"{slot}：源透明区被填充 {ratio:.2%}（阈值 {threshold:.0%}）{note}"})
    return results


def cached_masks(store):
    """Only reuse the hash-checked masks saved by the portrait editor."""
    from .drafts import sha256
    cache = store.root / "_cache" / "official-shape-masks.npz"
    meta = cache.with_suffix(".json")
    if not cache.is_file() or not meta.is_file():
        return {}
    if json.loads(meta.read_text("utf-8")).get("sha256") != sha256(cache.read_bytes()):
        raise ValueError("形状蒙版缓存 SHA-256 不符，请重新派生立绘")
    with np.load(cache, allow_pickle=False) as data:
        return {slot: data[slot] for slot in gate.SHAPE_SLOTS}


def check_portrait_delivery(store, change, master, icons):
    template = change["params"].get("template")
    if template is None:
        return [{"code": "ICON_ALPHA_NOT_CHECKED", "level": "warn", "status": "skipped",
                 "state": "未执行",
                 "blocking": False, "form": change["target"]["form"],
                 "message": "旧立绘草稿缺少裁剪模板，未检查透明区，请重新保存立绘"}]
    return inspect_icons(master, template, icons, cached_masks(store), form=change["target"]["form"])


def report(checks):
    slots = [c for c in checks if c.get("code", "").startswith("ICON_")]
    checked = [c for c in slots if c.get("status") != "skipped"]
    # A filled transparent area outranks "not checked"; only an all-skipped run is skipped,
    # so the page never shows unchecked icons as passed.
    state = ("warning" if any(c.get("level") == "warn" for c in checked) else
             "skipped" if not checked else
             "partial" if len(checked) < len(slots) else
             "info" if any(c.get("status") == "info" for c in checked) else "ok")
    return {"status": state if slots else "skipped", "threshold": THRESHOLD, "slots": slots,
            **({"reason": "本次没有派生 UI 图标"} if not slots else {})}
