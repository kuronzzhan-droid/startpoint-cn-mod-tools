# -*- coding: utf-8 -*-
"""五重 boss/召唤物/特效/场地表：带 1px 外扩环的无损重排（只改 atlas 记录的 x/y）。

为什么要带环：官方表的区域外非透明像素全部落在区域外 1px 环内（打包器为双线性采样做的 bleed），
且 1px 外扩矩形两两不相交（fb_ring_probe.py 全表实测）。所以把「区域 + 1px 环」当整体搬走：
任何半径 ≤1px 的采样（最近邻/双线性）在新位置读到的像素与原位置逐个相同 ⇒ 屏幕输出逐像素不变。
环超出原表边界的部分按透明处理（原表在 layer0 里贴着别的表的 2px 透明 margin，读到的也是透明）。

证明链（每张表都断言，任一不过 ⇒ 该表不动）：
1. 记录逐条只差 x/y；n/w/h/r/fx/fy/fw/fh 与顺序全同；
2. 每个唯一区域的 (w+2)x(h+2) 邻域在新旧图中逐字节相同（RGBA）；
3. 新图在所有外扩块之外 alpha 全 0；外扩块两两不相交；
4. 新表面积 (W+2)(H+2) 比旧表小 ≥ MIN_GAIN。
不旋转、不裁帧、不重采样、不去重。只写 pickle overlay，不写 store。"""
import os, sys, json, pickle, io
os.environ.setdefault("WF_TIP", "195")
from fb_layer0_gate import *  # noqa
sys.path.insert(0, str(P.base149.TOOLS))
from wf_battle_atlas_repack import pack_regions, Rect, decode_png, decode_atlas, encode_atlas
from PIL import Image
import wf_assets

MIN_GAIN = 0.01
OUT = Path(__file__).resolve().parent.parent / "art" / "fb_slim196"


def crop_pad(img, x, y, w, h):
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    W, H = img.size
    sx0, sy0, sx1, sy1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if sx1 > sx0 and sy1 > sy0:
        c.paste(img.crop((sx0, sy0, sx1, sy1)), (sx0 - x, sy0 - y))
    return c


def norm(c):
    """透明像素的 RGB 不参与采样（Starling 预乘 alpha），比较时统一归零。"""
    px = [(0, 0, 0, 0) if p[3] == 0 else p for p in c.getdata()]
    return bytes(b for p in px for b in p)


def ring_repack(png, atl):
    img = decode_png(png); recs = decode_atlas(atl)
    W, H = img.size
    uniq = sorted({(r["x"], r["y"], r["w"], r["h"]) for r in recs})
    blocks = [Rect(x - 1, y - 1, w + 2, h + 2) for x, y, w, h in uniq]
    # 前置：区域外非透明像素都在 1px 环内；外扩块两两不相交
    cov = Image.new("L", img.size, 0)
    for b in blocks:
        cov.paste(255, (max(0, b.x), max(0, b.y), min(W, b.x + b.w), min(H, b.y + b.h)))
    a = img.getchannel("A")
    if any(av and not cv for av, cv in zip(a.getdata(), cov.getdata())):
        raise ValueError("opaque pixels beyond 1px ring")
    for i, p in enumerate(blocks):
        for q2 in blocks[i + 1:]:
            if not (p.x + p.w <= q2.x or q2.x + q2.w <= p.x or p.y + p.h <= q2.y or q2.y + q2.h <= p.y):
                raise ValueError("ring blocks overlap")
    maxw = max(b.w for b in blocks)
    best = None
    lo, hi = maxw, max(W + 2, maxw) + 64
    step = max(1, (hi - lo) // 80)
    for tw in sorted(set(list(range(lo, hi + 1, step)) + [W + 2, lo, hi])):
        for mode in ("height", "area"):
            try:
                placed, (ow, oh) = pack_regions(blocks, target_width=tw, max_height=8192, gap=0, sort_mode=mode)
            except ValueError:
                continue
            # 新图尺寸：外扩块右/下环超出部分可以裁掉（那一圈原本就该是透明且在 layer0 里由 margin 保证透明）
            nw = max(placed[b].x + placed[b].w - 1 for b in blocks)
            nh = max(placed[b].y + placed[b].h - 1 for b in blocks)
            # 环必须全透明才可省掉最右/最下那 1px；否则保留
            sc = (nw + 2) * (nh + 2)
            if best is None or sc < best[0]:
                best = (sc, placed, (nw, nh), tw, mode)
    sc, placed, (nw, nh), tw, mode = best
    # 新左上角统一 = 块位置（块 (0,0) 起，区域在 +1）。若某块左/上环落在负坐标外（块在 x=0），区域在 x=1，环列 x=0 存在。
    new = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    for (x, y, w, h), b in zip(uniq, blocks):
        nb = placed[b]
        blk = crop_pad(img, b.x, b.y, b.w, b.h)
        new.alpha_composite(blk, (nb.x, nb.y)) if False else new.paste(blk, (nb.x, nb.y))
    # 被裁掉的右/下 1px 环必须原本透明，否则把图扩回去
    need_w, need_h = nw, nh
    for (x, y, w, h), b in zip(uniq, blocks):
        nb = placed[b]
        blk = crop_pad(img, b.x, b.y, b.w, b.h)
        if nb.x + nb.w > nw and blk.crop((b.w - 1, 0, b.w, b.h)).getchannel("A").getbbox():
            need_w = max(need_w, nb.x + nb.w)
        if nb.y + nb.h > nh and blk.crop((0, b.h - 1, b.w, b.h)).getchannel("A").getbbox():
            need_h = max(need_h, nb.y + nb.h)
    if (need_w, need_h) != (nw, nh):
        big = Image.new("RGBA", (need_w, need_h), (0, 0, 0, 0)); big.paste(new, (0, 0)); new = big
        for (x, y, w, h), b in zip(uniq, blocks):
            new.paste(crop_pad(img, b.x, b.y, b.w, b.h), (placed[b].x, placed[b].y))
        nw, nh = need_w, need_h
    pos = {(x, y, w, h): (placed[b].x + 1, placed[b].y + 1) for (x, y, w, h), b in zip(uniq, blocks)}
    out_recs = []
    for r in recs:
        r2 = dict(r); r2["x"], r2["y"] = pos[(r["x"], r["y"], r["w"], r["h"])]; out_recs.append(r2)
    # ---- 证明
    assert len(out_recs) == len(recs)
    for r, r2 in zip(recs, out_recs):
        assert list(r) == list(r2) and {k: v for k, v in r.items() if k not in "xy"} == {k: v for k, v in r2.items() if k not in "xy"}
    nbk = []
    for (x, y, w, h) in uniq:
        X, Y = pos[(x, y, w, h)]
        assert norm(crop_pad(img, x - 1, y - 1, w + 2, h + 2)) == norm(crop_pad(new, X - 1, Y - 1, w + 2, h + 2)), (x, y, w, h)
        nbk.append((X - 1, Y - 1, w + 2, h + 2))
    for i, p in enumerate(nbk):
        for q2 in nbk[i + 1:]:
            assert p[0] + p[2] <= q2[0] or q2[0] + q2[2] <= p[0] or p[1] + p[3] <= q2[1] or q2[1] + q2[3] <= p[1]
    cov = Image.new("L", new.size, 0)
    for p in nbk:
        cov.paste(255, (max(0, p[0]), max(0, p[1]), min(nw, p[0] + p[2]), min(nh, p[1] + p[3])))
    assert not any(av and not cv for av, cv in zip(new.getchannel("A").getdata(), cov.getdata()))
    st = io.BytesIO(); new.save(st, format="PNG", optimize=True, compress_level=9)
    png2 = wf_assets.png_encode(st.getvalue())
    atl2 = encode_atlas(out_recs)
    assert decode_atlas(atl2) == out_recs
    assert decode_png(png2).tobytes() == new.tobytes()
    return png2, atl2, (W, H), (nw, nh), len(recs), len(uniq), mode


def round_sheets(v):
    sheets = {}
    for qid in R0 + R1:
        a, _ = round_assets(v, qid)
        for s, (d, o) in sheets_from_anims(v, a).items():
            sheets.setdefault(s, [d, set(), o])[1].add(qid)
    return sheets


def main():
    v = View()
    sheets = round_sheets(v)
    overlay, log = {}, []
    for s in sorted(sheets):
        d, qs, owner = sheets[s]
        if s == "battle/common/layer0":
            continue
        png, atl = v.file(s + ".png"), v.file(s + ".atlas.amf3.deflate")
        if png is None or atl is None:
            log.append(dict(sheet=s, skip="no atlas")); continue
        try:
            png2, atl2, before, after, nrec, nuni, mode = ring_repack(png, atl)
        except (ValueError, AssertionError) as e:
            log.append(dict(sheet=s, skip=f"{type(e).__name__}: {e}"[:200])); continue
        g = area(before) - area(after)
        if g < MIN_GAIN * area(before):
            continue
        overlay[s + ".png"] = png2
        overlay[s + ".atlas.amf3.deflate"] = atl2
        log.append(dict(sheet=s, before=list(before), after=list(after), gain_px=g, records=nrec, unique=nuni,
                        mode=mode, owner=owner, quests=sorted(qs), png_bytes=[len(png), len(png2)]))
        print(f"{s}  {before} -> {after}  -{g/1e6:.3f} Mpx ({100*g/area(before):.1f}%)  q={len(qs)}")
    OUT.mkdir(parents=True, exist_ok=True)
    pickle.dump(overlay, open(OUT / "repack_overlay.pkl", "wb"))
    json.dump(log, open(OUT / "repack_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(overlay) // 2, "sheets repacked;", sum(x.get("gain_px", 0) for x in log) / 1e6, "Mpx (union of sheets)")
    print("skipped:", [(x["sheet"], x["skip"]) for x in log if "skip" in x])


if __name__ == "__main__":
    main()
