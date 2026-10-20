# -*- coding: utf-8 -*-
"""Final contact sheets per visual type -> fx_survey/预览_<类型>.png"""
import json, math, sys
from multiprocessing import Pool
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import render_sheet as R
import classify

OUT = Path(r"D:/WF/out/水杰拉德-20261018/fx_survey")
rows = json.load(open("rows.json", encoding="utf-8"))
FILE = {"flash": "全屏闪光压暗", "radial": "放射光爆", "fall": "从天而降", "wave": "波浪涟漪漩涡", "field": "场地覆盖边框",
        "giant": "巨物召唤", "stage": "舞台烟花", "scatter": "散布粒子", "slash": "巨型斩击", "beam": "贯穿光柱长线"}
TORD = {"A": 0, "D": 1, "E": 2, "B": 3, "C": 4}
FONT = R.FONT

def cell(args):
    p, nfr, cw = args
    frs = R.pick_frames(p, nfr)
    ims = []
    for f in frs:
        try:
            ims.append((f, R.render_screen(p, f, w=cw)))
        except Exception:
            ims.append((f, Image.new("RGB", (cw, int(cw * 1920 / 1080)), (60, 0, 0))))
    return p, ims

def build(rs, out, title, nfr=3, cw=110, cols=5, pool=None):
    font = ImageFont.truetype(FONT, 13); fontb = ImageFont.truetype(FONT, 17)
    ch_h = int(round(cw * 1920 / 1080))
    cellw = nfr * cw + (nfr - 1) * 2 + 10
    cellh = ch_h + 44
    rowsn = math.ceil(len(rs) / cols)
    top = 40
    W = cols * cellw + 10
    Hh = top + rowsn * cellh + 10
    S = Image.new("RGB", (W, Hh), (8, 8, 12))
    dr = ImageDraw.Draw(S)
    dr.text((10, 8), title, font=fontb, fill=(240, 240, 240))
    res = dict(pool.map(cell, [(r["path"], nfr, cw) for r in rs], chunksize=1))
    for k, r in enumerate(rs):
        rr, cc = divmod(k, cols)
        x0 = 6 + cc * cellw; y0 = top + rr * cellh
        if r["water"]:
            dr.rectangle([x0 - 3, y0 - 3, x0 + nfr * (cw + 2) + 1, y0 + ch_h + 40], outline=(70, 150, 255), width=2)
        for j, (f, im) in enumerate(res[r["path"]]):
            S.paste(im, (x0 + j * (cw + 2), y0))
            dr.text((x0 + j * (cw + 2) + 2, y0 + 1), f"f{f}", font=font, fill=(150, 150, 150))
        col = R.ELEMC.get(r["element"], (200, 200, 200))
        tags = f"[{r['tiername']}]" + ("[辅助]" if r["supporter"] else "") + ("[治疗]" if r["healer"] else "")
        lab1 = f"{r['char']} {r['cn']} ★{r['rarity']}{r['elem']} {tags}"
        lab2 = f"{r['base']} {r['frames']}f s{'/'.join(str(s) for s in r['scales'])}"
        dr.text((x0, y0 + ch_h + 2), lab1, font=font, fill=col)
        dr.text((x0, y0 + ch_h + 20), lab2, font=font, fill=(205, 205, 205))
    S.save(out, optimize=True)
    print("wrote", out, S.size, flush=True)

def sortkey(r):
    return (TORD[r["tier"]], 0 if r["water"] else 1, r["char"], r["base"])

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(16) as pool:
        for cat, fn in FILE.items():
            rs = sorted([r for r in rows if r["cat"] == cat], key=sortkey)
            if cat == "beam":
                main = [r for r in rs if r["tier"] != "C"]
                cs = [r for r in rs if r["tier"] == "C"]
                build(main, OUT / f"预览_{fn}_1.png", f"{classify.CATS[cat]}  (全屏/半屏级 {len(main)} 个,每格3帧;蓝框=水属性)", pool=pool)
                half = math.ceil(len(cs) / 2)
                build(cs[:half], OUT / f"预览_{fn}_2.png", f"{classify.CATS[cat]}  跨屏长线(C 档,{len(cs)} 个中第 1-{half} 个,每格2帧)", nfr=2, cw=90, cols=8, pool=pool)
                build(cs[half:], OUT / f"预览_{fn}_3.png", f"{classify.CATS[cat]}  跨屏长线(C 档,第 {half+1}-{len(cs)} 个,每格2帧)", nfr=2, cw=90, cols=8, pool=pool)
            else:
                build(rs, OUT / f"预览_{fn}.png", f"{classify.CATS[cat]}  ({len(rs)} 个,每格3帧:起/峰/收;蓝框=水属性)", pool=pool)
        # water + supporter overview
        ws = sorted([r for r in rows if (r["water"] or r["supporter"]) and r["tier"] in "ADEB"], key=sortkey)
        build(ws, OUT / "预览_水属性与辅助角色.png", f"水属性 / 辅助(Supporter)角色的全屏~半屏特效 ({len(ws)} 个;蓝框=水属性)", pool=pool)
