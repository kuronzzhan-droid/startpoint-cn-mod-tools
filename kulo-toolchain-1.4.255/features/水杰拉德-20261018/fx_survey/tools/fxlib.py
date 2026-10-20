# -*- coding: utf-8 -*-
"""Offline .parts evaluator/renderer (read-only research).

Based on partsrender.py (wt26 staging, written against the decompiled client) and
extended with: per-keyframe ColorTransform `c` (GraphicsSource.as:172, default
0x64000000 = 100% multiplier, 0 offsets; applied PartsAnimationImageProvider.as:277-281
as rgb*mult + offset), blend modes (m>>8: 0 inherit/1 add/2 multiply/3 overlay_like/4 screen,
LayoutTools.as:34-50) with inheritance from parent graphics, and color-transform
composition through nested graphics (multiplier multiplies, offsets add scaled).
"""
from __future__ import annotations
import numpy as np
from PIL import Image

RES = 4096.0
MASK30 = 0x3FFFFFFF
DEFAULT_C = 0x64000000


def cut_region(sheet, e):
    box = sheet.crop((e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]))
    if e.get("r"):
        box = box.rotate(90, expand=True)
    return box


def frame_textures(sheet, atlas):
    out = {}
    for e in atlas:
        img = cut_region(sheet, e)
        fw = e.get("fw", img.width)
        fh = e.get("fh", img.height)
        fx = e.get("fx", 0)
        fy = e.get("fy", 0)
        if (fw, fh) == img.size and (fx, fy) == (0, 0):
            out[e["n"]] = (img, fw, fh)
            continue
        canvas = Image.new("RGBA", (int(fw), int(fh)), (0, 0, 0, 0))
        canvas.alpha_composite(img, (int(-fx), int(-fy)))
        out[e["n"]] = (canvas, fw, fh)
    return out


def _bezier_ratio(rec, t):
    try:
        vals = rec if isinstance(rec, (list, tuple)) else rec.get("p") or list(rec.values())
        x1, y1, x2, y2 = [float(v) / 1e6 for v in vals[:4]]
    except Exception:
        return t
    u = t
    for _ in range(8):
        x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u ** 3
        dx = 3 * (1 - u) ** 2 * x1 + 6 * (1 - u) * u * (x2 - x1) + 3 * u * u * (1 - x2)
        if abs(dx) < 1e-9:
            break
        u -= (x - t) / dx
        u = min(1.0, max(0.0, u))
    return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u ** 3


def _ratio(parts, tween, easing_raw, s):
    if tween == 2:
        e = (easing_raw - 63) / 100.0
        if e == 0:
            return s
        if e < 0:
            return s * (s * -e + (1 + e))
        return s * ((2 - s) * e + (1 - e))
    rec = parts.get("c") or []
    if 0 <= easing_raw < len(rec):
        return _bezier_ratio(rec[easing_raw], s)
    return s


def _lerp_mat(m0, m1, r):
    return {k: m0[k] * (1 - r) + m1[k] * r for k in ("a", "b", "c", "d", "x", "y")}


def _split_c(c):
    c = int(c) & 0xFFFFFFFF
    return ((c >> 24) & 0xFF) / 100.0, (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF


def _future_frame(kind, base, offset, total):
    if kind == 0:
        return base
    if kind == 1:
        return int(min(base + offset, total - 1))
    if kind == 2:
        return int((base + offset) % total) if total else 0
    return -1


def _state_at(parts, strip, local):
    start = int(strip["s"]) & MASK30
    if local < start:
        return None
    t = local - start
    acc = 0
    ks = strip["l"]
    for idx, k in enumerate(ks):
        tt = int(k.get("t", 0) or 0)
        dur = (tt & 0xFFFF) or 1
        if acc <= t < acc + dur:
            off = t - acc
            m = int(k["m"])
            mat = parts["t"][m >> 12]
            alpha = (m & 0xFF) / 255.0
            blend = (m >> 8) & 0xF
            c = k.get("c")
            c = DEFAULT_C if c is None else int(c)
            ct = _split_c(c)
            tween = (tt >> 16) & 3
            if tween and off > 0 and idx + 1 < len(ks):
                nk = ks[idx + 1]
                nm = int(nk["m"])
                r = _ratio(parts, tween, tt >> 18, off / dur)
                mat = _lerp_mat(mat, parts["t"][nm >> 12], r)
                alpha = alpha * (1 - r) + ((nm & 0xFF) / 255.0) * r
                nc = nk.get("c")
                nc = DEFAULT_C if nc is None else int(nc)
                if nc != c:
                    n2 = _split_c(nc)
                    ct = tuple(ct[i] * (1 - r) + n2[i] * r for i in range(4))
            return mat, alpha, blend, ct, off, k
        acc += dur
    return None


def collect(parts, gidx, frame, base_mat, base_alpha, base_blend, base_ct, acc, depth=0):
    """Append (matrix6, alpha, blend, ct(mult,r,g,b), image_name) in draw order."""
    if depth > 12:
        return
    g = parts["g"][gidx]
    for strip in g["s"]:
        kind = (int(strip["s"]) & 0xFFFFFFFF) >> 30
        st = _state_at(parts, strip, frame)
        if st is None:
            continue
        mat, alpha, blend, ct, off, kf = st
        a = base_mat[0] * mat["a"] / RES + base_mat[2] * mat["b"] / RES
        b = base_mat[1] * mat["a"] / RES + base_mat[3] * mat["b"] / RES
        c = base_mat[0] * mat["c"] / RES + base_mat[2] * mat["d"] / RES
        d = base_mat[1] * mat["c"] / RES + base_mat[3] * mat["d"] / RES
        x = base_mat[0] * mat["x"] / RES + base_mat[2] * mat["y"] / RES + base_mat[4]
        y = base_mat[1] * mat["x"] / RES + base_mat[3] * mat["y"] / RES + base_mat[5]
        comp = (a, b, c, d, x, y)
        al = base_alpha * alpha
        bl = base_blend if blend == 0 else blend
        # client: child mult = parent_mult * own_mult ; offset = parent_mult*own_off + parent_off
        pm, pr, pg, pb = base_ct
        om, orr, og, ob = ct
        cct = (pm * om, pm * orr + pr, pm * og + pg, pm * ob + pb)
        if al <= 0.002:
            continue
        if kind == 0:
            acc.append((comp, al, bl, cct, parts["i"][int(strip["i"])]["p"]))
        elif kind == 2:
            child = int(strip["i"])
            total = int(parts["g"][child]["t"])
            r = int(kf.get("r", 0) or 0) & 0xFFFFFFFF
            cf = _future_frame(r >> 30, r & MASK30, off, total)
            if 0 <= cf < total:
                collect(parts, child, cf, comp, al, bl, cct, acc, depth + 1)
        else:
            acc.append((comp, al, bl, cct, "__movie__%s" % strip.get("i")))


IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def placements(parts, frame):
    acc = []
    collect(parts, 0, frame, IDENT, 1.0, 0, (1.0, 0, 0, 0), acc)
    return acc


def corners(comp, fw, fh):
    a, b, c, d, x, y = comp
    return [(a * px + c * py + x, b * px + d * py + y) for px, py in ((0, 0), (fw, 0), (0, fh), (fw, fh))]


def frame_bbox(parts, textures, frame):
    lo = [1e18, 1e18]; hi = [-1e18, -1e18]
    n = 0
    for comp, al, bl, ct, name in placements(parts, frame):
        tex = textures.get(name)
        if tex is None:
            continue
        _, fw, fh = tex
        for wx, wy in corners(comp, fw, fh):
            lo[0] = min(lo[0], wx); lo[1] = min(lo[1], wy)
            hi[0] = max(hi[0], wx); hi[1] = max(hi[1], wy)
        n += 1
    if n == 0:
        return None
    return (lo[0], lo[1], hi[0], hi[1])


def _apply_ct(arr, ct):
    m, r, g, b = ct
    if abs(m - 1.0) < 1e-6 and r == 0 and g == 0 and b == 0:
        return arr
    out = arr.copy()
    out[..., 0] = np.clip(arr[..., 0] * m + r, 0, 255)
    out[..., 1] = np.clip(arr[..., 1] * m + g, 0, 255)
    out[..., 2] = np.clip(arr[..., 2] * m + b, 0, 255)
    return out


def render_frame(parts, textures, frame, view, scale, bg=(18, 22, 34), resample=Image.NEAREST, want_ink=False):
    """view=(minx,miny,maxx,maxy) in parts units, scale px/unit. Opaque RGB canvas on bg.
    Blend: 0/normal over, 1 add, 2 multiply, 3 overlay_like (src*dst + dst), 4 screen.
    Returns PIL RGB (and ink mask float array if want_ink)."""
    minx, miny, maxx, maxy = view
    W = max(1, int(round((maxx - minx) * scale)))
    H = max(1, int(round((maxy - miny) * scale)))
    canvas = np.empty((H, W, 3), np.float32)
    canvas[...] = bg
    ink = np.zeros((H, W, 1), np.float32) if want_ink else None
    for comp, al, bl, ct, name in placements(parts, frame):
        tex = textures.get(name)
        if tex is None:
            continue
        img, fw, fh = tex
        a, b, c, d, x, y = comp
        F = (a * scale, c * scale, (x - minx) * scale, b * scale, d * scale, (y - miny) * scale)
        det = F[0] * F[4] - F[1] * F[3]
        if abs(det) < 1e-12:
            continue
        ia, ib = F[4] / det, -F[1] / det
        ic, idd = -F[3] / det, F[0] / det
        itx = -(ia * F[2] + ib * F[5])
        ity = -(ic * F[2] + idd * F[5])
        layer = img.transform((W, H), Image.AFFINE, (ia, ib, itx, ic, idd, ity), resample=resample)
        L = np.asarray(layer, np.float32)
        if not L[..., 3].any():
            continue
        L = _apply_ct(L, ct)
        sa = (L[..., 3:4] / 255.0) * al
        src = L[..., :3]
        if bl == 1:
            canvas += src * sa
        elif bl == 4:
            canvas[...] = 255 - (255 - canvas) * (255 - src * sa) / 255.0
        elif bl == 2:
            canvas[...] = canvas * (1 - sa) + canvas * src / 255.0 * sa
        elif bl == 3:
            canvas[...] = canvas + canvas * src * sa / 255.0
        else:
            canvas[...] = src * sa + canvas * (1 - sa)
        np.clip(canvas, 0, 255, out=canvas)
        if want_ink:
            ink[...] = ink + sa * (1 - ink)
    im = Image.fromarray(canvas.astype(np.uint8), "RGB")
    if want_ink:
        return im, ink[..., 0]
    return im
