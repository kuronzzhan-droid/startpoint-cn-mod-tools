# -*- coding: utf-8 -*-
"""赛瑞斯特效装配库：逐帧烘焙矩阵的 PartsAnimation 写出器 + 打包 + 预览 + 静态门禁。

结构约定（全部来自项目卡片与官方件实读）：
- 一个族 = 一个目录 battle/effect/skill_unique/seris_dragon_king/<sub>/，共用 <sub>.png + <sub>.atlas；
- 帧名两段式 <dir>/.gen/<parts基名>/<token>；同族不同 parts 共用像素时用「别名条目」（同 x,y,w,h，不同 n），零图集成本；
- .parts：g[0] 单个 graphics，多条 image 段（kind 0，可时间重叠＝多层），每段逐帧关键帧 {m:(矩阵idx<<12)|alpha, t:1}；
- 矩阵 4096 定点；贴图左上角锚矩阵原点；居中写法 tx = cx - (a*w/2 + c*h/2)；
- a[] = 每图最大并发实例（按引用段数取上界，宁多勿崩）；起点+关键帧总长 ≤ g.t（防 #1125）；
- .timeline：neutral(once) 主体 + end(once) 收尾淡出；寿命直写=neutral 长度，被终止/寿命到即跳 end 播完。
"""
import io
import json
import math
import os
import sys
import zlib
import hashlib
from pathlib import Path

from PIL import Image

BUILD = r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"
_cwd = os.getcwd()
os.chdir(BUILD)
sys.path.insert(0, BUILD)
from live149 import *  # noqa: E402,F401  (wf_dsl 路径)
import wf_dsl  # noqa: E402
os.chdir(_cwd)

ROOT_LP = "battle/effect/skill_unique/seris_dragon_king"
FX = Path(r"D:/WF/out/赛瑞斯重做-20261015/fx")


# ------------------------------------------------------------------ 编码
def deflate(b: bytes) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(b) + co.flush()


def enc_amf(tree) -> bytes:
    raw = wf_dsl.encode_amf3(tree)
    assert wf_dsl.parse_dsl(raw)["tree"] == tree
    return deflate(raw)


def png_obf(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    d = bytearray(b.getvalue())
    assert d[1:4] == b"PNG"
    d[1:4] = b"png"
    return bytes(d)


def png_read(data: bytes) -> Image.Image:
    d = bytearray(data)
    d[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(d))).convert("RGBA")


# ------------------------------------------------------------------ 模型
class Layer:
    """一条 image 段：image=族内图键；start=起始帧；frames=[(cx,cy,sx,sy,rot,alpha)]，每帧一项。"""

    def __init__(self, image, start, frames, note=""):
        self.image, self.start, self.frames, self.note = image, int(start), list(frames), note


class Effect:
    def __init__(self, name, total, main_len, sounds=(), note="", seqs=None):
        self.name, self.total, self.main_len = name, int(total), int(main_len)
        self.seqs = seqs
        self.layers: list[Layer] = []
        self.sounds = list(sounds)
        self.note = note

    def add(self, image, start, frames, note=""):
        frames = [f for f in frames]
        assert frames, (self.name, image)
        self.layers.append(Layer(image, start, frames, note))


class Family:
    def __init__(self, sub):
        self.sub = sub
        self.dir_lp = f"{ROOT_LP}/{sub}"
        self.images: dict[str, Image.Image] = {}
        self.effects: list[Effect] = []
        self.solid: set[str] = set()

    def img(self, key, im, pad=True, solid=False):
        im = im.convert("RGBA")
        assert im.getbbox(), key
        if pad:
            p = Image.new("RGBA", (im.width + 2, im.height + 2), (0, 0, 0, 0))
            p.alpha_composite(im, (1, 1))
            im = p
        self.images[key] = im
        if solid:
            self.solid.add(key)
        return key

    def effect(self, name, total, main_len, sounds=(), note="", seqs=None):
        e = Effect(name, total, main_len, sounds, note, seqs)
        self.effects.append(e)
        return e


# ------------------------------------------------------------------ 打包（MaxRects-BSSF 简版，宽度定、高度最小）
def pack(sizes, width):
    free = [(0, 0, width, 1 << 20)]
    out = {}
    order = sorted(sizes, key=lambda k: (-sizes[k][1], -sizes[k][0], k))
    for k in order:
        w, h = sizes[k][0] + 2, sizes[k][1] + 2          # 1px 透明边距 ×2，防 bleed
        best = None
        for fx, fy, fw, fh in free:
            if w <= fw and h <= fh:
                score = (fy + h, fx)
                if best is None or score < best[0]:
                    best = (score, fx, fy)
        assert best, k
        _, x, y = best
        out[k] = (x + 1, y + 1)
        nf = []
        for fx, fy, fw, fh in free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                nf.append((fx, fy, fw, fh)); continue
            if x > fx: nf.append((fx, fy, x - fx, fh))
            if x + w < fx + fw: nf.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy: nf.append((fx, fy, fw, y - fy))
            if y + h < fy + fh: nf.append((fx, y + h, fw, fy + fh - y - h))
        free = [a for a in nf if not any(a != b and a[0] >= b[0] and a[1] >= b[1] and a[0] + a[2] <= b[0] + b[2]
                                          and a[1] + a[3] <= b[1] + b[3] for b in nf)]
    H = max(out[k][1] + sizes[k][1] + 1 for k in out)
    W = max(out[k][0] + sizes[k][0] + 1 for k in out)
    return out, W, H


def best_pack(sizes):
    best = None
    tot = sum((w + 2) * (h + 2) for w, h in sizes.values())
    lo = max(w for w, h in sizes.values()) + 2
    for width in range(lo, max(lo, int(math.sqrt(tot) * 2.2)) + 1, 4):
        pos, W, H = pack(sizes, width)
        asp = max(W, H) / min(W, H)
        sc = (W + 2) * (H + 2) * (1 + max(0.0, asp - 1.6) * 0.25)   # 面积优先，长宽比>1.6 罚分（细长件是列阻塞者）
        if best is None or sc < best[0]:
            best = (sc, pos, W, H)
    return best[1], best[2], best[3]


# ------------------------------------------------------------------ 矩阵
def mat(cx, cy, sx, sy, rot, w, h):
    co, si = math.cos(rot), math.sin(rot)
    a, b, c, d = sx * co, sx * si, -sy * si, sy * co
    tx = cx - (a * w / 2 + c * h / 2)
    ty = cy - (b * w / 2 + d * h / 2)
    return {"a": int(round(a * 4096)), "b": int(round(b * 4096)), "c": int(round(c * 4096)),
            "d": int(round(d * 4096)), "x": int(round(tx * 4096)), "y": int(round(ty * 4096))}


# ------------------------------------------------------------------ 写出
def build(fam: Family, outdir: Path):
    sizes = {k: im.size for k, im in fam.images.items()}
    pos, W, H = best_pack(sizes)
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for k, (x, y) in pos.items():
        sheet.alpha_composite(fam.images[k], (x, y))
    files = {}
    atlas = []
    parts_out = {}
    for e in fam.effects:
        used = []
        for L in e.layers:
            if L.image not in used:
                used.append(L.image)
        names = {}
        for k in used:
            n = f"{fam.dir_lp}/.gen/{e.name}/{k}"
            names[k] = n
            x, y = pos[k]
            w, h = sizes[k]
            atlas.append({"n": n, "w": w, "h": h, "x": x, "y": y})
        mats, midx = [], {}
        segs = []
        for L in e.layers:
            w, h = sizes[L.image]
            ii = used.index(L.image)
            kf = []
            for (cx, cy, sx, sy, rot, al) in L.frames:
                m = mat(cx, cy, sx, sy, rot, w, h)
                key = tuple(m.values())
                if key not in midx:
                    midx[key] = len(mats); mats.append(m)
                al = max(0, min(255, int(round(al))))
                kf.append({"m": (midx[key] << 12) | al, "t": 1})
            assert L.start + len(kf) <= e.total, (e.name, L.image, L.start, len(kf), e.total)   # F1125
            segs.append({"s": L.start, "i": ii, "l": kf})
        assert len(mats) < (1 << 16)
        pools = [0] * len(used)
        for f in range(e.total):
            cnt = [0] * len(used)
            for s in segs:
                if s["s"] <= f < s["s"] + len(s["l"]):
                    cnt[s["i"]] += 1
            pools = [max(p, c) for p, c in zip(pools, cnt)]
        a = [max(1, p + 1) for p in pools]                 # 并发上界 +1 余量
        parts = {"i": [{"s": False, "p": names[k]} for k in used],
                 "g": [{"t": e.total, "s": segs}],
                 "m": [], "a": a, "o": [], "t": mats, "c": [], "s": 1}
        seqs = [{"begin": 1, "end": e.main_len, "name": "neutral", "kind": "once"}]
        if e.seqs:
            seqs = [dict(q) for q in e.seqs]
        elif e.total > e.main_len:
            seqs.append({"begin": e.main_len + 1, "end": e.total, "name": "end", "kind": "once"})
        tl = {"sequences": seqs, "sounds": [dict(s) for s in e.sounds], "points": [], "circles": [],
              "rectangles": [], "matrices": []}
        files[f"{fam.dir_lp}/{e.name}.parts.amf3.deflate"] = enc_amf(parts)
        files[f"{fam.dir_lp}/{e.name}.timeline.amf3.deflate"] = enc_amf(tl)
        parts_out[e.name] = parts
    files[f"{fam.dir_lp}/{fam.sub}.atlas.amf3.deflate"] = enc_amf(atlas)
    files[f"{fam.dir_lp}/{fam.sub}.png"] = png_obf(sheet)
    verify(fam, files, sheet, atlas, parts_out)
    game = outdir / "game"
    for lp, data in files.items():
        p = game / lp
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    sheet.save(outdir / f"{fam.sub}_sheet_preview.png")
    return {"files": files, "sheet": (W, H), "atlas": atlas, "parts": parts_out, "pos": pos, "sizes": sizes}


def verify(fam, files, sheet, atlas, parts_out):
    W, H = sheet.size
    names = {a["n"] for a in atlas}
    for a in atlas:
        seg = a["n"].split("/.gen/")
        assert seg[0] == fam.dir_lp and len(seg[1].split("/")) == 2, a["n"]          # 两段式
        assert 0 <= a["x"] and a["x"] + a["w"] <= W and 0 <= a["y"] and a["y"] + a["h"] <= H, a
        crop = sheet.crop((a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]))
        if a["n"].rsplit("/", 1)[1] in fam.solid:
            continue
        assert min(crop.getchannel("A").getdata()) == 0, ("rect 无透明像素(未抠底?)", a["n"])
    for e in fam.effects:
        p = parts_out[e.name]
        for i in p["i"]:
            assert i["p"] in names and i["p"].split("/.gen/")[1].split("/")[0] == e.name
        g = p["g"][0]
        for s in g["s"]:
            assert s["s"] + sum(k["t"] & 0xFFFF for k in s["l"]) <= g["t"]
        tl = wf_dsl.parse_dsl(zlib.decompress(files[f"{fam.dir_lp}/{e.name}.timeline.amf3.deflate"], -15))["tree"]
        assert tl["sequences"][-1]["end"] == g["t"]
        for snd in tl["sounds"]:
            assert snd["path"].startswith("sound_effect/")
    # 解码回读
    for lp, data in files.items():
        if lp.endswith(".png"):
            assert png_read(data).size == sheet.size
        else:
            wf_dsl.parse_dsl(zlib.decompress(data, -15))


# ------------------------------------------------------------------ 预览（逐帧按矩阵合成，最近邻）
def render_frame(fam, effect, f, canvas=(1080, 1920), origin=(540, 960), scale=1.0, bg=(12, 14, 24, 255), base=None):
    im = base.copy() if base is not None else Image.new("RGBA", canvas, bg)
    for L in effect.layers:
        k = f - L.start
        if not (0 <= k < len(L.frames)):
            continue
        cx, cy, sx, sy, rot, al = L.frames[k]
        al = max(0, min(255, int(round(al))))
        if al <= 0:
            continue
        src = fam.images[L.image]
        w, h = src.size
        m = mat(cx, cy, sx, sy, rot, w, h)
        a, b, c, d = (m[q] / 4096 * scale for q in "abcd")
        tx, ty = m["x"] / 4096 * scale + origin[0], m["y"] / 4096 * scale + origin[1]
        det = a * d - b * c
        if abs(det) < 1e-9:
            continue
        corners = [(tx + a * u + c * v, ty + b * u + d * v) for u, v in ((0, 0), (w, 0), (0, h), (w, h))]
        x0 = max(0, int(math.floor(min(p[0] for p in corners)))); x1 = min(im.width, int(math.ceil(max(p[0] for p in corners))))
        y0 = max(0, int(math.floor(min(p[1] for p in corners)))); y1 = min(im.height, int(math.ceil(max(p[1] for p in corners))))
        if x1 <= x0 or y1 <= y0:
            continue
        ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
        # 输出(X,Y)->源(u,v)：u = ia*(X-tx)+ic*(Y-ty), v = ib*(X-tx)+id*(Y-ty)
        ox, oy = x0 + 0.5 - tx, y0 + 0.5 - ty
        coeffs = (ia, ic, ia * ox + ic * oy, ib, id_, ib * ox + id_ * oy)
        tile = src.transform((x1 - x0, y1 - y0), Image.AFFINE, coeffs, resample=Image.NEAREST)
        if al < 255:
            A = tile.getchannel("A").point(lambda v, q=al: v * q // 255)
            tile.putalpha(A)
        im.alpha_composite(tile, (x0, y0))
    return im


def save_gif(frames, path, ms=33):
    pal = [fr.convert("RGB").quantize(colors=255, method=Image.Quantize.MEDIANCUT) for fr in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=ms, loop=0, disposal=1, optimize=False)


def sha256(b):
    return hashlib.sha256(b).hexdigest()
