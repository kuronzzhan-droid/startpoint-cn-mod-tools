# -*- coding: utf-8 -*-
"""保亮度换色：只改色相（可选饱和度倍率），明度 V 不动，alpha 不动，alpha==0 像素不碰。

rules: [{"from": [lo, hi], "to": 目标色相(度) 或 "shift": 偏移, "sat": 倍率, "sat_min": 0.12, "val_min": 0.05}]
按顺序第一个命中生效；低饱和（白芯、灰、黑边）默认不动。
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(-1)
    mn = rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    h = h * 60.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0)
    return h, s, mx


def _hsv_to_rgb(h, s, v):
    h = (h % 360.0) / 60.0
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    out = np.zeros(h.shape + (3,))
    for k, (a, b, c) in enumerate(((v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q))):
        sel = i == k
        out[sel, 0], out[sel, 1], out[sel, 2] = a[sel], b[sel], c[sel]
    return out


def _hit(h, lo, hi):
    lo, hi = lo % 360, hi % 360
    return (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)


def recolor_array(arr: np.ndarray, rules) -> np.ndarray:
    a = arr.astype(np.float64) / 255.0
    rgb, alpha = a[..., :3], a[..., 3] if a.shape[-1] == 4 else np.ones(a.shape[:2])
    h, s, v = _rgb_to_hsv(rgb)
    vis = alpha > 0
    done = np.zeros(h.shape, bool)
    nh, ns = h.copy(), s.copy()
    for r in rules:
        lo, hi = r.get("from", (0, 360))
        sel = vis & ~done & _hit(h, lo, hi) & (s >= r.get("sat_min", 0.12)) & (v >= r.get("val_min", 0.05))
        if "to" in r:
            nh[sel] = r["to"]
        elif "shift" in r:
            nh[sel] = h[sel] + r["shift"]
        ns[sel] = np.clip(s[sel] * r.get("sat", 1.0), 0, 1)
        done |= sel
    out = _hsv_to_rgb(nh, ns, v)
    res = arr.copy()
    res[..., :3] = np.where(done[..., None], np.clip(np.round(out * 255), 0, 255).astype(arr.dtype), arr[..., :3])
    return res


def transform(rules):
    def fn(image: Image.Image) -> Image.Image:
        im = image.convert("RGBA")
        return Image.fromarray(recolor_array(np.asarray(im), rules), "RGBA")
    return fn
