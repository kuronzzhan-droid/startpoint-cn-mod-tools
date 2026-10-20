"""白底候选 → 透明母图：只删与画布边连通的近白区，边缘按白底反混求 alpha 与原色。"""
import json, sys
import numpy as np
from PIL import Image
from scipy import ndimage
import hw_env
A = hw_env.OUT / "art"
picks = json.loads((A / "candidates" / "picks.json").read_text("utf-8"))
for key, p in picks.items():
    for lv in ("0", "1"):
        src = A / "candidates" / key / f"{p[lv]}.png"
        rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float64)
        d = 255 - rgb.min(2)                      # 离白距离
        near = d < 14
        lab, _ = ndimage.label(near)
        border = np.unique(np.concatenate((lab[0], lab[-1], lab[:, 0], lab[:, -1])))
        bg = np.isin(lab, border[border != 0])
        # 被线条围住的大块纯白洞（闪电/手臂圈出的白底）也是背景；衣服高光多带灰阶，不会成片纯白
        pure = d < 6
        plab, n = ndimage.label(pure & ~bg)
        if n:
            sizes = ndimage.sum(np.ones_like(d), plab, index=np.arange(1, n + 1))
            big = np.flatnonzero(sizes > 1500) + 1
            bg |= np.isin(plab, big)
        # 过渡带：背景外 3 像素内，按离白距离给 alpha
        dist = ndimage.distance_transform_edt(~bg)
        band = (~bg) & (dist <= 3)
        alpha = np.where(bg, 0.0, 1.0)
        a_band = np.clip(d / 60.0, 0, 1)
        alpha[band] = np.maximum(a_band[band], (dist[band] - 0) / 3.0 * 0 + a_band[band])
        a = alpha[..., None]
        fg = np.where(a > 0.02, (rgb - 255 * (1 - a)) / np.maximum(a, 0.02), rgb)
        out = np.dstack([np.clip(fg, 0, 255), alpha * 255]).round().astype(np.uint8)
        im = Image.fromarray(out, "RGBA")
        im.save(A / "masters" / f"{key}-{lv}.png")
        print(key, lv, p[lv], "transparent", round(float((alpha == 0).mean()), 3))
