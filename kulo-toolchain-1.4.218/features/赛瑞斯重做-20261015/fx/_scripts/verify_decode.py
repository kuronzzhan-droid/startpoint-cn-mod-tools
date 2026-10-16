# -*- coding: utf-8 -*-
"""独立回读门禁：只用落盘的 game 文件（解混淆 PNG + atlas + parts + timeline）重渲染，与模型渲染逐像素比对；
并复核官方结构约束（键序、两段式、a 池、#1125、alpha==0、timeline 末帧 == g.t、SE 路径∈官方集合）。"""
import json
import math
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fxlib as X  # noqa: E402
from build_fx import FAMILIES  # noqa: E402

OFFICIAL_SE = set()
for line in open(HERE / "official_se.txt", encoding="utf8"):
    OFFICIAL_SE.add(line.strip())


def dec(p):
    return X.wf_dsl.parse_dsl(zlib.decompress(Path(p).read_bytes(), -15))["tree"]


def render_from_files(sheet, atlas, parts, f, origin=(540, 960)):
    im = Image.new("RGBA", (1080, 1920), (12, 14, 24, 255))
    rects = {a["n"]: a for a in atlas}
    g = parts["g"][0]
    for seg in g["s"]:
        k = f - seg["s"]
        if not (0 <= k < len(seg["l"])):
            continue
        kf = seg["l"][k]
        mi, al = kf["m"] >> 12, kf["m"] & 0xFF
        if al == 0:
            continue
        a = rects[parts["i"][seg["i"]]["p"]]
        src = sheet.crop((a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]))
        M = parts["t"][mi]
        A, B, C, D = (M[q] / 4096 for q in "abcd")
        tx, ty = M["x"] / 4096 + origin[0], M["y"] / 4096 + origin[1]
        det = A * D - B * C
        w, h = src.size
        cs = [(tx + A * u + C * v, ty + B * u + D * v) for u, v in ((0, 0), (w, 0), (0, h), (w, h))]
        x0 = max(0, int(math.floor(min(p[0] for p in cs)))); x1 = min(1080, int(math.ceil(max(p[0] for p in cs))))
        y0 = max(0, int(math.floor(min(p[1] for p in cs)))); y1 = min(1920, int(math.ceil(max(p[1] for p in cs))))
        if x1 <= x0 or y1 <= y0:
            continue
        ia, ib, ic, id_ = D / det, -B / det, -C / det, A / det
        ox, oy = x0 + 0.5 - tx, y0 + 0.5 - ty
        tile = src.transform((x1 - x0, y1 - y0), Image.AFFINE, (ia, ic, ia * ox + ic * oy, ib, id_, ib * ox + id_ * oy), resample=Image.NEAREST)
        if al < 255:
            tile.putalpha(tile.getchannel("A").point(lambda v, q=al: v * q // 255))
        im.alpha_composite(tile, (x0, y0))
    return im


def main():
    report = []
    for sub, fn in FAMILIES:
        F = fn()
        game = X.FX / sub / "game" / F.dir_lp
        sheet = X.png_read((game / f"{sub}.png").read_bytes())
        atlas = dec(game / f"{sub}.atlas.amf3.deflate")
        assert all(list(a.keys()) == ["n", "w", "h", "x", "y"] for a in atlas)
        for e in F.effects:
            parts = dec(game / f"{e.name}.parts.amf3.deflate")
            tl = dec(game / f"{e.name}.timeline.amf3.deflate")
            assert list(parts.keys()) == ["i", "g", "m", "a", "o", "t", "c", "s"]
            assert list(tl.keys()) == ["sequences", "sounds", "points", "circles", "rectangles", "matrices"]
            assert tl["sequences"][-1]["end"] == parts["g"][0]["t"] == e.total
            assert len(parts["a"]) == len(parts["i"])
            for s in tl["sounds"]:
                assert s["path"] in OFFICIAL_SE, s["path"]
            # a 池：每帧每图并发 ≤ a
            for f in range(e.total):
                cnt = [0] * len(parts["i"])
                for seg in parts["g"][0]["s"]:
                    if seg["s"] <= f < seg["s"] + len(seg["l"]):
                        cnt[seg["i"]] += 1
                assert all(c <= a for c, a in zip(cnt, parts["a"])), (e.name, f)
            bad = 0
            for f in sorted({0, e.main_len // 3, e.main_len // 2, e.main_len - 1, e.total - 1}):
                ref = X.render_frame(F, e, f, canvas=(1080, 1920), origin=(540, 960))
                got = render_from_files(sheet, atlas, parts, f)
                diff = ImageChops.difference(ref.convert("RGB"), got.convert("RGB")).getbbox()
                bad += diff is not None
            report.append((sub, e.name, len(parts["i"]), len(parts["t"]), len(parts["g"][0]["s"]), max(parts["a"]), bad))
            assert bad == 0, (e.name, bad)
    for r in report:
        print("OK", r)


if __name__ == "__main__":
    main()
