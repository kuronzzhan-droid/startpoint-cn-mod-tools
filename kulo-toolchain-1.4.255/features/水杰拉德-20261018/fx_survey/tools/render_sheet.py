# -*- coding: utf-8 -*-
"""Render contact sheets of effects (screen-framed, peak + extra frames)."""
import json, sys, math, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import wfio, fxlib

FW, FH = 1080, 1920
d = json.loads(Path("fx_index.json").read_text(encoding="utf-8"))
ink = json.loads(Path("ink.json").read_text(encoding="utf-8"))
E = {e["path"]: e for e in d["effects"]}
chars = d["chars"]
import meta
names = meta.load_names()
FONT = "C:/Windows/Fonts/msyh.ttc"
ELEM = {"0": "火", "1": "水", "2": "雷", "3": "风", "4": "光", "5": "暗"}
ELEMC = {"0": (230, 80, 60), "1": (70, 150, 255), "2": (240, 200, 60), "3": (90, 210, 110), "4": (250, 240, 200), "5": (170, 110, 230)}

_tex = {}
def textures(e):
    t = {}
    for dp in e["atlas_dirs"]:
        if dp not in _tex:
            nm = dp.split("/")[-1]
            atlas, _ = wfio.load_amf(f"{dp}/{nm}.atlas")
            png, _ = wfio.load_png(f"{dp}/{nm}.png")
            _tex[dp] = fxlib.frame_textures(png, atlas)
        t.update(_tex[dp])
    return t

def anchor_of(e):
    for u in e["usage"]:
        if u["subject"] == -1:
            return float(u["x"] or 0), float(u["y"] or 0), "场地中心"
    # character anchored: put origin at lower-middle of screen (typical character zone)
    return 0.0, 0.0, "角色/参考点"

def render_screen(path, frame, w=180, oversample=2, bg=(18, 22, 34)):
    e = E[path]
    parts, _ = wfio.load_amf(path + ".parts")
    tex = textures(e)
    v = ink.get(path, {})
    s = v.get("scale") or (max([u["scale"] or (e["default_scale"] or 1) for u in e["usage"]] or [e["default_scale"] or 1]))
    ox, oy, an = anchor_of(e)
    W = w * oversample
    px_per_bu = W / FW
    view = ((-FW / 2 - ox) / s, (-FH / 2 - oy) / s, (FW / 2 - ox) / s, (FH / 2 - oy) / s)
    im = fxlib.render_frame(parts, tex, frame, view, s * px_per_bu, bg=bg, resample=Image.BILINEAR)
    if oversample > 1:
        im = im.resize((w, int(round(w * FH / FW))), Image.LANCZOS)
    return im

def pick_frames(path, n=3):
    e = E[path]; v = ink.get(path)
    nf = e["frames"]
    if not v:
        return [nf // 4, nf // 2, 3 * nf // 4][:n]
    ser = v["series"]
    peak = (v.get("best_nodim") or v["best"])["frame"]
    if n == 1:
        return [peak]
    # early = first frame with area>=30% of peak area, late = last such
    pa = max(a for f, a, c in ser) or 1
    act = [f for f, a, c in ser if a >= 0.3 * pa]
    early = act[0] if act else nf // 4
    late = act[-1] if act else 3 * nf // 4
    fr = sorted(set([early, peak, late]))
    while len(fr) < n:
        fr.append(min(nf - 1, fr[-1] + 1))
    return fr[:n]

def label_of(path):
    e = E[path]
    us = e["usage"]
    ch = us[0]["char"] if us else path.split("/")[3]
    c = chars.get(ch, {})
    nm = names.get(c.get("id", ""), {}).get("name", "")
    return ch, nm, c

def sheet(paths, out, cols=5, nfr=3, cw=120, title=None):
    font = ImageFont.truetype(FONT, 13); fontb = ImageFont.truetype(FONT, 15)
    ch_h = int(round(cw * FH / FW))
    cellw = nfr * cw + (nfr - 1) * 2 + 8
    cellh = ch_h + 40
    rows = math.ceil(len(paths) / cols)
    top = 34 if title else 0
    W = cols * cellw + 8
    H = top + rows * cellh + 8
    S = Image.new("RGB", (W, H), (8, 8, 12))
    dr = ImageDraw.Draw(S)
    if title:
        dr.text((8, 6), title, font=fontb, fill=(240, 240, 240))
    for k, p in enumerate(paths):
        r, c = divmod(k, cols)
        x0 = 4 + c * cellw; y0 = top + 4 + r * cellh
        frs = pick_frames(p, nfr)
        for j, f in enumerate(frs):
            try:
                im = render_screen(p, f, w=cw)
            except Exception as ex:
                im = Image.new("RGB", (cw, ch_h), (60, 0, 0))
            S.paste(im, (x0 + j * (cw + 2), y0))
            dr.text((x0 + j * (cw + 2) + 2, y0 + 1), f"f{f}", font=font, fill=(160, 160, 160))
        ch, nm, cc = label_of(p)
        el = cc.get("element", "")
        col = ELEMC.get(el, (200, 200, 200))
        e = E[p]
        lab1 = f"{ch} {nm} ★{cc.get('rarity','?')}{ELEM.get(el,'')} {cc.get('role','')}"
        lab2 = f"{p.split('/')[-1]}  {e['frames']}f s{ink.get(p,{}).get('scale','?')}"
        dr.text((x0, y0 + ch_h + 2), lab1, font=font, fill=col)
        dr.text((x0, y0 + ch_h + 19), lab2, font=font, fill=(200, 200, 200))
    S.save(out)
    return out

if __name__ == "__main__":
    lst = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = sys.argv[2]
    nfr = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    cols = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    cw = int(sys.argv[5]) if len(sys.argv) > 5 else 120
    title = sys.argv[6] if len(sys.argv) > 6 else None
    sheet(lst, out, cols=cols, nfr=nfr, cw=cw, title=title)
    print("wrote", out)
