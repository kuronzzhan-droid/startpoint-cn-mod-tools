# -*- coding: utf-8 -*-
"""Ink coverage per effect (alpha-only raster in battle units, 1px = U units)."""
import json, sys, time, math
import numpy as np
from PIL import Image
from pathlib import Path
import wfio, fxlib

U = 20.0           # battle units per raster px
FW, FH = 1080, 1920
WIN_X, WIN_Y = 1.5 * FW, 1.5 * FH   # half-extent of evaluation window around anchor (battle units)
THR = 0.12

d = json.loads(Path("fx_index.json").read_text(encoding="utf-8"))
E = d["effects"]
only = set(sys.argv[1:])

alpha_cache = {}
atlas_cache = {}

def textures_for(e):
    tex = {}
    for dpath in e["atlas_dirs"]:
        if dpath not in atlas_cache:
            nm = dpath.split("/")[-1]
            atlas, _ = wfio.load_amf(f"{dpath}/{nm}.atlas")
            png, _ = wfio.load_png(f"{dpath}/{nm}.png")
            t = fxlib.frame_textures(png, atlas)
            dd = {}
            for k, v in t.items():
                arr = np.asarray(v[0], np.float32)
                a = arr[..., 3] / 255.0
                wsum = a.sum()
                mean = tuple(float((arr[..., i] * a).sum() / wsum) if wsum > 0 else 0.0 for i in range(3))
                dd[k] = (v[0].getchannel("A"), v[1], v[2], mean, float(a.mean()))
            atlas_cache[dpath] = dd
        tex.update(atlas_cache[dpath])
    return tex

def ink_frame(parts, tex, frame, scale, ox, oy, overlays=None):
    """raster window centered on anchor; effect origin at anchor + (ox,oy) battle units."""
    W = int(2 * WIN_X / U); H = int(2 * WIN_Y / U)
    ink = np.zeros((H, W), np.float32)
    ink2 = np.zeros((H, W), np.float32)
    s = scale / U
    for comp, al, bl, ct, name in fxlib.placements(parts, frame):
        is_ov = False
        t = tex.get(name)
        if t is None:
            continue
        A, fw, fh, mean, acov = t
        if overlays is not None and max(fw, fh) <= 24:
            scr_area = abs(comp[0] * comp[3] - comp[1] * comp[2]) * fw * fh * scale * scale * acov
            if scr_area >= 0.4 * FW * FH:
                m, r, g, b = ct
                col = tuple(int(min(255, max(0, mean[i] * m + (r, g, b)[i]))) for i in range(3))
                overlays.append((frame, round(scr_area / (FW * FH), 2), col, round(al, 2), name.split("/")[-1]))
                is_ov = True
        a, b, c, dd, x, y = comp
        F = (a * s, c * s, x * s + (WIN_X + ox) / U, b * s, dd * s, y * s + (WIN_Y + oy) / U)
        det = F[0] * F[4] - F[1] * F[3]
        if abs(det) < 1e-12:
            continue
        # quick reject by corners
        cs = [(F[0] * px + F[1] * py + F[2], F[3] * px + F[4] * py + F[5]) for px, py in ((0, 0), (fw, 0), (0, fh), (fw, fh))]
        if max(p[0] for p in cs) < 0 or min(p[0] for p in cs) > W or max(p[1] for p in cs) < 0 or min(p[1] for p in cs) > H:
            continue
        ia, ib = F[4] / det, -F[1] / det
        ic, idd = -F[3] / det, F[0] / det
        itx = -(ia * F[2] + ib * F[5]); ity = -(ic * F[2] + idd * F[5])
        L = np.asarray(A.transform((W, H), Image.AFFINE, (ia, ib, itx, ic, idd, ity), resample=Image.BILINEAR), np.float32) / 255.0 * al
        ink = ink + L * (1 - ink)
        if not is_ov:
            ink2 = ink2 + L * (1 - ink2)
    return ink, ink2

def work(e):
    parts, _ = wfio.load_amf(e["path"] + ".parts")
    tex = textures_for(e)
    sc = [u["scale"] if u["scale"] is not None else (e["default_scale"] or 1) for u in e["usage"]] or [e["default_scale"] or 1]
    sm = max(sc)
    ox = oy = 0.0; anchor = "origin"
    for u in e["usage"]:
        if u["subject"] in (-1,):
            ox, oy = float(u["x"] or 0), float(u["y"] or 0); anchor = "field_center"; break
    nf = e["frames"]
    step = max(1, int(math.ceil(nf / 40)))
    best = None
    best2 = None
    series = []
    overlays = []
    def meas(ink):
        m = ink > THR
        area = float(m.sum()) * U * U / (FW * FH)
        H, W = ink.shape
        cx, cy = W // 2, H // 2
        hw, hh = int(FW / 2 / U), int(FH / 2 / U)
        cov = float(m[cy - hh:cy + hh, cx - hw:cx + hw].mean())
        if m.any():
            ys, xs = np.nonzero(m)
            iw = (xs.max() - xs.min() + 1) * U; ih = (ys.max() - ys.min() + 1) * U
        else:
            iw = ih = 0
        return area, cov, iw, ih
    for f in range(0, nf, step):
        ink, inkx = ink_frame(parts, tex, f, sm, ox, oy, overlays)
        a2, c2, w2, h2 = meas(inkx)
        if best2 is None or c2 > best2["cov"] or (c2 == best2["cov"] and a2 > best2["area"]):
            best2 = {"frame": f, "cov": round(c2, 4), "area": round(a2, 4), "ink_w": float(w2), "ink_h": float(h2)}
        m = ink > THR
        area = float(m.sum()) * U * U / (FW * FH)
        H, W = ink.shape
        cx, cy = W // 2, H // 2
        hw, hh = int(FW / 2 / U), int(FH / 2 / U)
        scr = m[cy - hh:cy + hh, cx - hw:cx + hw]
        cov = float(scr.mean())
        if m.any():
            ys, xs = np.nonzero(m)
            iw = (xs.max() - xs.min() + 1) * U; ih = (ys.max() - ys.min() + 1) * U
        else:
            iw = ih = 0
        series.append((f, round(area, 3), round(cov, 3)))
        if best is None or cov > best["cov"] or (cov == best["cov"] and area > best["area"]):
            best = {"frame": f, "cov": round(cov, 4), "area": round(area, 4), "ink_w": float(iw), "ink_h": float(ih)}
    long_cov = sum(step for f, a, c in series if c >= 0.3)
    ov = {}
    for fr, ar, col, al, nm in overlays:
        key = (col, nm)
        if key not in ov or ov[key][1] < ar:
            ov[key] = (fr, ar, col, al, nm)
    return e["path"], {"best": best, "best_nodim": best2, "scale": sm, "anchor": anchor, "frames_cov30": long_cov, "step": step,
                      "max_area": max(a for f, a, c in series) if series else 0, "series": series,
                      "overlays": sorted(ov.values(), key=lambda v: -v[1])[:6]}

out = {}
t0 = time.time()
todo = [e for e in E if not e.get("error") and e.get("bbox")]
if only:
    todo = [e for e in todo if e["path"] in only]
else:
    # prefilter: frame-box extent at max scale must reach >= 50% width or >= 40% height
    keep = []
    for e in todo:
        x0, y0, x1, y1 = e["bbox"]
        sc = [u["scale"] if u["scale"] is not None else (e["default_scale"] or 1) for u in e["usage"]] or [e["default_scale"] or 1]
        sm = max(sc)
        if (x1 - x0) * sm >= 0.5 * FW or (y1 - y0) * sm >= 0.4 * FH:
            keep.append(e)
    todo = keep
if __name__ == "__main__":
    print("to ink", len(todo), flush=True)
if __name__ == "__main__":
    from multiprocessing import Pool
    with Pool(20) as pool:
        for k, (pth, res) in enumerate(pool.imap_unordered(work, todo, chunksize=2)):
            out[pth] = res
            if k % 50 == 0:
                print(k, pth, res["best"], round(time.time() - t0, 1), flush=True)
    fn = "ink.json" if not only else "ink_part.json"
    Path(fn).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("done", len(out), round(time.time() - t0, 1))
