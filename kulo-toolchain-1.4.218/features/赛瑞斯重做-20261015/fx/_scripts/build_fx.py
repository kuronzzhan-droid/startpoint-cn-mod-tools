# -*- coding: utf-8 -*-
"""赛瑞斯（129999 seris_dragon_king）原创像素特效五族 + 固有状态图标。
用法：python build_fx.py      → 写 fx/<族>/game/...、预览 GIF、drop_manifest.json、budget.json
"""
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fxlib as X  # noqa: E402
import art  # noqa: E402
from palette import WATER, RED  # noqa: E402

FX = X.FX
RD = FX / "_src" / "rd"
DRAGON = HERE / "dragon_special.png"


def snd(path, begin, volume=-1, end=-1):
    """volume：Playhead.playSoundWhenExists 里 volume!=-1 时增益=volume*0.1（-1=1.0）；end!=-1 时播放头离开 [begin,end) 即停。"""
    return {"path": path, "begin": begin, "loop": 1, "end": end, "volume": volume}


def ease_out(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 2


def ease_in(t):
    t = max(0.0, min(1.0, t)); return t * t


def lerp(a, b, t):
    return a + (b - a) * t


def fade(k, n, fin=2, fout=4):
    a = 255
    if k < fin: a = 255 * (k + 1) / (fin + 1)
    if k >= n - fout: a = min(a, 255 * (n - k) / (fout + 1))
    return a


def rd_frames(name, idxs, pal=WATER):
    sheet = Image.open(RD / f"{name}.png").convert("RGBA")
    out = []
    for i in idxs:
        fr = sheet.crop(((i % 4) * 96, (i // 4) * 96, (i % 4) * 96 + 96, (i // 4) * 96 + 96))
        fr = art.quantize(fr, pal)
        out.append(fr.crop(fr.getbbox()))
    # 质心对齐（防循环件抖动，>4px 必矫正）：统一画布、按 alpha 质心居中
    cents = []
    for fr in out:
        a = fr.getchannel("A"); w, h = fr.size; sx = sy = n = 0
        for y in range(h):
            for x in range(w):
                if a.getpixel((x, y)):
                    sx += x; sy += y; n += 1
        cents.append((sx / n, sy / n))
    W = max(fr.width for fr in out) + 8; H = max(fr.height for fr in out) + 8
    res = []
    for fr, (cx, cy) in zip(out, cents):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c.alpha_composite(fr, (int(round(W / 2 - cx)), int(round(H / 2 - cy))))
        res.append(c.crop((0, 0, W, H)))
    return res


def dragon_frames():
    """新龙形像素（final_USER_DB special_sprite_sheet）里 neutral/展翼帧；按帧号取图，脚底对齐。"""
    import zlib
    P = Path(r"D:/WF/out/赛瑞斯重做-20261015/pixel/final_USER_DB/game/character/seris_dragon_king/pixelart/")
    at = X.wf_dsl.parse_dsl(zlib.decompress((P / "special_sprite_sheet.atlas.amf3.deflate").read_bytes(), -15))["tree"]
    sheet = X.png_read((P / "special_sprite_sheet.png").read_bytes())
    want = {1: None, 38: None, 50: None, 110: None}
    for a in at:
        n = int(a["n"][-4:])
        if n in want:
            c = sheet.crop((a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]))
            if a.get("r"):
                c = c.rotate(90, expand=True)
            want[n] = (c, a)
    out = {}
    for n, (c, a) in want.items():
        canvas = Image.new("RGBA", (24, 22), (0, 0, 0, 0))
        canvas.alpha_composite(c, ((24 - c.width) // 2, 22 - c.height))
        out[n] = canvas
    return out


# ================================================================== 1 苍海潮涌（人形技能，全屏 3 段）
def fam_tide():
    F = X.Family("tide")
    for p in range(3):
        F.img(f"crest{p}", art.crest(phase=p, seed=11), pad=False)
    F.img("body", art.body_gradient(), pad=False, solid=True)
    F.img("streak", art.streak())
    for s in range(4):
        F.img(f"spout{s}", art.spout(s))
    for i, fr in enumerate(rd_frames("splash", [0, 5, 10, 14])):
        F.img(f"splash{i}", fr)
    F.img("drop1", art.droplet(1)); F.img("drop2", art.droplet(2)); F.img("drop3", art.droplet(3))
    F.img("ring", art.foam_ring())
    F.img("flash", art.flash(20))

    MAIN, TOT = 32, 44
    e = F.effect("seris_tide", TOT, MAIN, sounds=[snd("sound_effect/water/se_wave_splash", 9, volume=6)],
                 note="苍海潮涌：海潮自屏底涌起覆盖全场，命中帧 8/12/16 三根潮柱迸发")
    CS = 2.5                      # 浪峰像素倍率
    cw, ch = F.images["crest0"].size

    def crest_y(f):
        if f <= 16: return lerp(1000, -690, ease_out(f / 16))
        if f < MAIN: return -690 - 14 * math.sin((f - 16) / 16 * math.pi)
        return -690 - 50 * (f - MAIN) / (TOT - MAIN)

    def crest_a(f):
        if f < MAIN: return 255
        return 255 * (1 - (f - MAIN + 1) / (TOT - MAIN + 1))

    # 水体（渐变件拉伸）：上沿跟浪峰底，下沿钉屏底
    body = []
    for f in range(TOT):
        top = crest_y(f) + ch * CS / 2 - 6
        bot = 1000
        h = max(4, bot - top)
        a = 135 if f < 10 else lerp(135, 70, (f - 10) / 14) if f < 24 else 70
        if f >= 24: a = 70 * max(0.0, 1 - (f - 24) / (TOT - 24))
        body.append((0, (top + bot) / 2, 1120 / F.images["body"].width, h / F.images["body"].height, 0, a))
    e.add("body", 0, body, "水体渐变（4×24 拉伸，纯色件白名单）")
    # 水流条纹
    rnd = random.Random(5)
    for k in range(12):
        x0 = rnd.uniform(-500, 500); st = rnd.randrange(0, 14); n = rnd.randrange(8, 14)
        fr = []
        for j in range(n):
            f = st + j
            y = 980 - (j + 1) * 70 - rnd.uniform(0, 20)
            if y < crest_y(f) + 40: y = crest_y(f) + 40 + (k * 37 % 200)
            fr.append((x0 + j * 6, y, 3, 2, -0.12, 200 * (1 - j / n)))
        e.add("streak", st, fr)
    # 浪峰 4 列平铺，帧轮换（3 帧/每 2 游戏帧）
    xs = [(i - 1.5) * (cw * CS - 2) for i in range(4)]
    for i, x in enumerate(xs):
        for p in range(3):
            fr = []
            for f in range(TOT):
                show = ((f // 2) % 3) == p
                fr.append((x + 6 * math.sin(f / 5), crest_y(f), CS, CS, 0, crest_a(f) if show else 0))
            e.add(f"crest{p}", 0, fr, f"浪峰列{i}")
    # 三根潮柱 + 水花 + 泡沫环 + 飞沫
    for hi, (hf, hx, sc) in enumerate(((8, -300, 3.0), (12, 300, 3.0), (16, 0, 3.9))):
        base_y = -120
        sp_h = F.images["spout0"].height
        for s, (o, n) in enumerate(((0, 2), (2, 3), (5, 3), (8, 4))):
            fr = [(hx, base_y - sp_h * sc / 2, sc, sc, 0, 255 if s < 3 else 255 * (1 - j / n)) for j in range(n)]
            e.add(f"spout{s}", hf - 2 + o, fr)
        for j in range(8):
            k = j // 2
            fr = [(hx, base_y - 30 * sc / 2, sc * 1.1, sc * 1.1, 0, 255 if j < 6 else 140)]
            e.add(f"splash{k}", hf + j, fr)
        fr = [(hx, base_y, sc * (1 + j * 0.45), sc * (1 + j * 0.45), 0, 255 * (1 - j / 10)) for j in range(10)]
        e.add("ring", hf, fr)
        if hi == 2:
            fr = [(0, base_y - 140, 2.5 + j * 1.2, 2.5 + j * 1.2, j * 0.15, 255 * (1 - j / 7)) for j in range(7)]
            e.add("flash", hf, fr)
        rr = random.Random(100 + hi)
        for d in range(14 if hi < 2 else 22):
            ang = rr.uniform(-math.pi * 0.92, -math.pi * 0.08); v = rr.uniform(14, 34) * (1.3 if hi == 2 else 1)
            vx, vy = v * math.cos(ang), v * math.sin(ang)
            n = rr.randrange(12, 20); img = rr.choice(["drop1", "drop2", "drop2", "drop3"]); s = rr.choice([2, 2.5, 3])
            fr = []
            x, y = hx + rr.uniform(-20, 20), base_y - 60 * sc
            for j in range(n):
                fr.append((x, y, s, s, 0, 255 if j < n - 3 else 255 * (n - j) / 4))
                x += vx; y += vy; vy += 3.2
            e.add(img, hf + 1, fr)
    return F


# ================================================================== 2 龙王吐息・苍潮（龙形技能 + 升空）
def fam_breath():
    F = X.Family("breath")
    for p in range(3):
        F.img(f"beam{p}", art.beam_tile(p), pad=False)
    rings = rd_frames("ring", [0, 4, 8, 12])
    for i, fr in enumerate(rings):
        F.img(f"vortex{i}", fr)
    for i, fr in enumerate(rd_frames("splash", [1, 6, 9, 13])):
        F.img(f"splash{i}", fr)
    F.img("flash", art.flash(22))
    F.img("ering", art.ellipse_ring())
    F.img("drop2", art.droplet(2)); F.img("drop3", art.droplet(3))
    dr = dragon_frames()
    for n, im in dr.items():
        F.img(f"dragon{n}", im)

    # ---- 吐息一段（原点 = 龙口；DSL 偏移把原点放到龙口；scale 1.0/1.3/1.6 = 三段递增）
    MAIN, TOT = 36, 46
    e = F.effect("seris_breath", TOT, MAIN, sounds=[snd("sound_effect/water/se_water_short_splash", 3, volume=7)],
                 note="龙王吐息：原点=龙口，水柱向下贯穿敌带，末端水花")
    BS = 2.5
    th = F.images["beam0"].height * BS
    LEN = 1060
    ntile = int(math.ceil(LEN / th)) + 1

    def beam_w(f):
        if f < 3: return 0.5 + f * 0.25
        if f < 26: return 1.3 + 0.08 * math.sin(f * 1.3)
        if f < MAIN: return lerp(1.1, 0.55, (f - 26) / (MAIN - 26))
        return 0.55 * (1 - (f - MAIN) / (TOT - MAIN))

    def beam_front(f):
        return min(LEN, (f + 1) * 150)

    for t in range(ntile):
        y_c = t * (th - 2) + th / 2
        for p in range(3):
            fr = []
            for f in range(TOT):
                vis = beam_front(f) >= t * th and ((f + 3 - p) % 3 == 0)      # 每帧换 phase = 下行水流
                a = 255 if f < MAIN else 255 * (1 - (f - MAIN + 1) / (TOT - MAIN + 1))
                fr.append((0, y_c, BS * beam_w(f), BS, 0, a if vis else 0))
            e.add(f"beam{p}", 0, fr, f"光柱段{t}")
    # 龙口闪光 + 聚潮环
    e.add("flash", 0, [(0, 0, 2.0 + j * 0.5, 2.0 + j * 0.5, j * 0.2, 255 if j < 5 else 255 * (9 - j) / 4) for j in range(9)])
    for j in range(MAIN):
        k = (j // 3) % 4
        e.add(f"vortex{k}", j, [(0, 10, 1.6, 0.7, 0, 220 if j < MAIN - 6 else 220 * (MAIN - j) / 6)])
    # 螺旋环沿柱下行
    for r in range(6):
        st = 2 + r * 5
        fr = []
        for j in range(16):
            y = j * 70
            if st + j >= TOT: break
            fr.append((0, y, 2.2 + y / 600, 2.2 + y / 600, 0, 230 * (1 - j / 16)))
        e.add("ering", st, fr)
    # 末端水花
    for j in range(4, TOT):
        k = (j // 2) % 4
        a = 255 if j < MAIN else 255 * (1 - (j - MAIN + 1) / (TOT - MAIN + 1))
        e.add(f"splash{k}", j, [(0, LEN - 40, 2.6, 2.6, 0, a)])
    rr = random.Random(9)
    for d in range(26):
        st = rr.randrange(4, 30); ang = rr.uniform(-math.pi * 0.95, -math.pi * 0.05); v = rr.uniform(12, 28)
        vx, vy = v * math.cos(ang), v * math.sin(ang); x, y = rr.uniform(-40, 40), LEN - 60
        fr = []
        for j in range(min(14, TOT - st)):
            fr.append((x, y, 2.5, 2.5, 0, 255 if j < 10 else 120)); x += vx; y += vy; vy += 3
        e.add(rr.choice(["drop2", "drop3"]), st, fr)

    # ---- 静音龙息（第 2/3 段与化龙自动龙息用；图名别名同 rect，零图集成本）
    q = F.effect("seris_breath_mute", TOT, MAIN, sounds=[], note="同 seris_breath，无音效")
    q.layers = e.layers
    # ---- 升空真龙（原点 = 场地中心 -1；龙身烘焙在 y=-820，同旧版位置）
    seqs = [{"begin": 1, "end": 16, "name": "start", "kind": "pass"},
            {"begin": 17, "end": 64, "name": "loop", "kind": "loop"},
            {"begin": 65, "end": 84, "name": "end", "kind": "once"}]
    g = F.effect("seris_flight", 84, 16, sounds=[],
                 note="真龙升空：start 现身 / loop 悬停 48 帧无缝 / end 冲天淡出；寿命直写 220", seqs=seqs)
    DY, DS = -830, 10.0
    order = [1, 38, 50, 38]
    for f in range(84):
        if f < 16:
            t = f / 15; y = lerp(DY + 120, DY, ease_out(t)); a = 255 * min(1, t * 1.5); s = DS * lerp(0.6, 1, ease_out(t))
        elif f < 64:
            y = DY + 8 * math.sin((f - 16) / 48 * 2 * math.pi * 2); a = 255; s = DS
        else:
            t = (f - 64) / 19; y = DY - 300 * ease_in(t); a = 255 * (1 - t); s = DS * (1 + 0.2 * t)
        n = order[(f // 6) % 4] if f >= 16 else 1
        g.add(f"dragon{n}", f, [(0, y, s, s, 0, a)])
        # 背后水环（压扁的 RD 漩涡环）
        k = (f // 3) % 4
        if f < 16:
            ra = 200 * f / 15; rs = lerp(1.2, 3.4, ease_out(f / 15))
        elif f < 64:
            ra = 170; rs = 3.4
        else:
            ra = 170 * (1 - (f - 64) / 19); rs = 3.4 + (f - 64) * 0.08
        g.layers.insert(0, X.Layer(f"vortex{k}", f, [(0, DY + 46, rs, rs * 0.42, 0, ra)]))
    return F


# ================================================================== 3 龙翼冲撞（冲刺 629，命中最近敌人）
def fam_dash():
    F = X.Family("dash")
    F.img("wing", art.wing())
    for i, fr in enumerate(rd_frames("splash", [2, 7, 11, 15])):
        F.img(f"splash{i}", fr)
    F.img("flash", art.flash(18))
    F.img("ring", art.foam_ring(w=48, h=48 // 3))
    F.img("drop1", art.droplet(1)); F.img("drop2", art.droplet(2))
    MAIN, TOT = 22, 30
    e = F.effect("seris_dash", TOT, MAIN, sounds=[snd("sound_effect/water/se_water_short_splash", 3, volume=5)],
                 note="龙翼冲撞：双水翼合拢扑击，第 3 帧爆开水花")
    ww, wh = F.images["wing"].size
    for side in (-1, 1):
        fr = []
        for j in range(16):
            t = min(1.0, j / 3)
            ang = lerp(-1.1, 0.25, ease_out(t)) + (0.12 * (j - 3) / 12 if j > 3 else 0)
            dist = lerp(170, 60, ease_out(t)) + (j - 3) * 3 * (j > 3)
            s = 2.4 * (1 + 0.04 * max(0, j - 3))
            a = 255 if j < 6 else 255 * (1 - (j - 5) / 11)
            cx = side * dist; cy = -20 + lerp(-40, 10, t)
            # 左翼：镜像（sx 取负），根部朝向中心
            fr.append((cx, cy, -s * side, s, ang * -side, a))
        e.add("wing", 0, fr)
    e.add("flash", 3, [(0, 0, 2.2 + j * 0.9, 2.2 + j * 0.9, j * 0.2, 255 * (1 - j / 6)) for j in range(6)])
    for j in range(3, TOT):
        k = min(3, (j - 3) // 3)
        a = 255 if j < MAIN else 255 * (1 - (j - MAIN + 1) / (TOT - MAIN + 1))
        e.add(f"splash{k}", j, [(0, 0, 2.2, 2.2, 0, a)])
    e.add("ring", 3, [(0, 20, 2.0 + j * 0.55, 2.0 + j * 0.55, 0, 255 * (1 - j / 12)) for j in range(12)])
    rr = random.Random(21)
    for d in range(16):
        ang = rr.uniform(0, 2 * math.pi); v = rr.uniform(10, 22); vx, vy = v * math.cos(ang), v * math.sin(ang) - 6
        x = y = 0; fr = []
        for j in range(14):
            fr.append((x, y, 2.5, 2.5, 0, 255 if j < 10 else 110)); x += vx; y += vy; vy += 2.2
        e.add(rr.choice(["drop1", "drop2"]), 3, fr)
    return F


# ================================================================== 4 苍海怒涛（PF Lv4）+ 红雷
def fam_lv4():
    F = X.Family("lv4")
    for p in range(3):
        F.img(f"crest{p}", art.crest(w=120, h=50, phase=p, seed=31, big=True), pad=False)
    F.img("body", art.body_gradient(), pad=False, solid=True)
    bolts = [art.bolt(52, 210, s, branches=2, thick=3) for s in (3, 7, 12)]
    for i, b in enumerate(bolts):
        F.img(f"bolt{i}", b)
    F.img("sbolt", art.bolt(28, 84, 5, branches=1, thick=1))
    F.img("rflash", art.flash(18, col="red"))
    F.img("wflash", art.flash(18))
    for i, fr in enumerate(rd_frames("splash", [3, 8, 12, 15])):
        F.img(f"splash{i}", fr)
    F.img("spark", art.spark(7))
    F.img("drop2", art.droplet(2))

    def wave(e, MAIN, TOT, x_shift=0.0, delay=0, extra_scale=1.0):
        CS = 3.0 * extra_scale
        cw, ch = F.images["crest0"].size

        def cy(f):
            f -= delay
            if f < 0: return 1100
            if f <= 20: return lerp(1100, -650, ease_out(f / 20))
            if f <= 34: return -650 - 10 * math.sin((f - 20) / 14 * math.pi)
            return lerp(-650, 1100, ease_in((f - 34) / (MAIN + 10 - 34)))

        def ca(f):
            if f < MAIN: return 255
            return 255 * max(0.0, 1 - (f - MAIN + 1) / (TOT - MAIN + 1))

        body = []
        for f in range(TOT):
            top = cy(f) + ch * CS / 2 - 8
            h = max(4, 1100 - top)
            a = 145 if f < MAIN else 145 * max(0.0, 1 - (f - MAIN + 1) / (TOT - MAIN + 1))
            body.append((x_shift, (top + 1100) / 2, 1160 / 4, h / 24, 0, a))
        e.add("body", 0, body)
        n = int(math.ceil(1160 / (cw * CS))) + 1
        for i in range(n):
            x = x_shift + (i - (n - 1) / 2) * (cw * CS - 3)
            for p in range(3):
                fr = []
                for f in range(TOT):
                    show = ((f // 2) % 3) == p
                    fr.append((x + 8 * math.sin(f / 4), cy(f), CS, CS, 0, ca(f) if show else 0))
                e.add(f"crest{p}", 0, fr)
        return cy

    def strikes(e, seed, n, t0, t1, scale=3.4, xs=(-420, 420), ys=(-560, 120)):
        rr = random.Random(seed)
        for k in range(n):
            st = int(lerp(t0, t1, k / max(1, n - 1)))
            x = rr.uniform(*xs); y = rr.uniform(*ys); b = rr.randrange(3)
            flip = rr.choice([-1, 1])
            bh = F.images["bolt0"].height * scale
            for j in range(6):
                img = f"bolt{(b + (j // 2)) % 3}" if j % 2 == 0 else f"bolt{b}"
                e.add(img, st + j, [(x, y - bh / 2 + 40, scale * flip, scale, 0, 255 if j < 4 else 150)])
            e.add("rflash", st + 1, [(x, y + 40, 2.4 + j * 0.8, 2.4 + j * 0.8, j * 0.25, 255 * (1 - j / 6)) for j in range(6)])
            for s in range(3):
                e.add("spark", st + 2 + s, [(x + rr.uniform(-60, 60), y + rr.uniform(-20, 70), 3, 3, rr.uniform(0, 6), 230)])

    def crawl(e, cy, seed, t0=12, t1=46):
        """浪峰上爬行的红电（横置短雷），把红雷和浪绑在一起。"""
        rr = random.Random(seed)
        for f in range(t0, t1, 2):
            for i in range(3):
                if rr.random() < 0.35:
                    continue
                x = rr.uniform(-500, 500)
                e.add("sbolt", f, [(x, cy(f) + rr.uniform(-10, 30), 2.6, 2.6 * rr.choice([-1, 1]), math.pi / 2, 235),
                                   (x + 6, cy(f + 1) + 10, 2.6, -2.6, math.pi / 2, 150)])

    def crash(e, cy, seed, at=30):
        rr = random.Random(seed)
        for i, x in enumerate((-380, -130, 130, 380)):
            for j in range(10):
                e.add(f"splash{(j // 2 + i) % 4}", at + i + j, [(x, cy(at + i + j) - 60, 3.0, 3.0, 0, 255 if j < 7 else 130)])
        for d in range(30):
            st = at + rr.randrange(0, 8); ang = rr.uniform(-math.pi * 0.95, -math.pi * 0.05); v = rr.uniform(16, 36)
            vx, vy = v * math.cos(ang), v * math.sin(ang); x, y = rr.uniform(-480, 480), -620
            fr = []
            for j in range(16):
                fr.append((x, y, 3, 3, 0, 255 if j < 12 else 120)); x += vx; y += vy; vy += 3.4
            e.add("drop2", st, fr)

    MAIN, TOT = 60, 74
    sounds = [snd("sound_effect/thunder/se_thunderbolt_single", 2, volume=8)]
    eh = F.effect("seris_lv4_human", TOT, MAIN, sounds=sounds, note="苍海怒涛（龙人形）：红雷先落→巨浪漫过全场→浪内红雷连闪→拍落")
    strikes(eh, 1, 3, 0, 4)
    cy = wave(eh, MAIN, TOT)
    strikes(eh, 2, 10, 10, 44)
    crawl(eh, cy, 4)
    crash(eh, cy, 3)
    ed = F.effect("seris_lv4_dragon", TOT, MAIN, sounds=sounds,
                  note="苍海怒涛（真龙形）：龙人形版 + 第二道浪 + 中央红雷柱")
    strikes(ed, 11, 4, 0, 5)
    cy2 = wave(ed, MAIN, TOT, delay=6, extra_scale=0.85)
    wave(ed, MAIN, TOT)
    strikes(ed, 12, 13, 8, 48)
    # 中央红雷柱：三根粗雷纵向接龙
    for j in range(14):
        a = 255 if j < 10 else 255 * (14 - j) / 5
        for seg in range(3):
            b = (seg + j // 2) % 3
            ed.add(f"bolt{b}", 22 + j, [(0, -720 + seg * 560 + 280, 4.0 * (1 if (j + seg) % 2 else -1), 2.7, 0, a)])
    ed.add("rflash", 22, [(0, -100, 4 + j * 1.4, 4 + j * 1.4, j * 0.2, 255 * (1 - j / 8)) for j in range(8)])
    crawl(ed, cy, 14)
    crawl(ed, cy2, 15)
    crash(ed, cy, 13)

    # 弹板红电（APK HitEffect 用，也在 Lv4 DSL 里挂一次保证预载）
    b = F.effect("seris_red_bolt", 14, 10, sounds=[], note="Lv4 就绪弹板红电：短雷+火花，单播 10 帧+收尾 4 帧")
    for j in range(10):
        img = "sbolt"
        b.add(img, j, [(0, -40, 2.2 * (1 if (j // 2) % 2 else -1), 2.2, 0, 255 if j % 3 != 2 else 140)])
    b.add("rflash", 0, [(0, 40, 1.4 + j * 0.3, 1.4 + j * 0.3, j * 0.3, 255 * (1 - j / 14)) for j in range(14)])
    for s in range(4):
        b.add("spark", 1 + s * 2, [(rr, 30, 2.5, 2.5, s, 230) for rr in [(-30, 30, -10, 20)[s]]])
    b.add("wflash", 10, [(0, 0, 1.0, 1.0, 0, 120 * (1 - j / 4)) for j in range(4)])
    return F


# ================================================================== 5 化龙/回龙人（审计新增）
def fam_transform():
    F = X.Family("transform")
    rings = rd_frames("ring", [2, 6, 10, 14])
    for i, fr in enumerate(rings):
        F.img(f"vortex{i}", fr)
    for s in range(4):
        F.img(f"spout{s}", art.spout(s, w=40, h=100, seed=8))
    for i, fr in enumerate(rd_frames("splash", [4, 9])):
        F.img(f"splash{i}", fr)
    F.img("flash", art.flash(20))
    F.img("drop2", art.droplet(2)); F.img("drop3", art.droplet(3))
    MAIN, TOT = 36, 46
    e = F.effect("seris_transform", TOT, MAIN, sounds=[snd("sound_effect/water/se_splash_launch", 4, volume=6)],
                 note="化龙：水漩环升起包住本体→潮柱冲天（遮住换形帧）→爆散")
    for f in range(TOT):
        k = (f // 2) % 4
        t = min(1, f / 10)
        s = lerp(1.0, 2.4, ease_out(t)) + (0.6 * (f - 14) / 10 if f > 14 else 0)
        a = 230 * min(1, f / 3) if f < 18 else 230 * max(0, 1 - (f - 18) / 8)
        if a > 0:
            e.add(f"vortex{k}", f, [(0, lerp(40, -30, t), s, s * 0.5, 0, a)])
    sp_h = F.images["spout0"].height
    for s_, (o, n) in enumerate(((4, 3), (7, 5), (12, 4), (16, 6))):
        sc = 3.2
        e.add(f"spout{s_}", o, [(0, 30 - sp_h * sc / 2, sc, sc, 0, 255 if s_ < 3 else 255 * (1 - j / n)) for j in range(n)])
    e.add("flash", 14, [(0, -60, 2.5 + j * 1.1, 2.5 + j * 1.1, j * 0.2, 255 * (1 - j / 8)) for j in range(8)])
    for j in range(14, TOT):
        a = 255 if j < MAIN - 6 else max(0, 255 * (TOT - j) / (TOT - MAIN + 6))
        e.add(f"splash{(j // 3) % 2}", j, [(0, 30, 2.4, 2.4, 0, a * (1 if j < 28 else 0.6))])
    rr = random.Random(41)
    for d in range(22):
        ang = rr.uniform(-math.pi * 0.95, -math.pi * 0.05); v = rr.uniform(12, 26); vx, vy = v * math.cos(ang), v * math.sin(ang)
        x, y = 0, -120; fr = []
        for j in range(16):
            fr.append((x, y, 2.5, 2.5, 0, 255 if j < 12 else 110)); x += vx; y += vy; vy += 2.6
        e.add(rr.choice(["drop2", "drop3"]), 15 + rr.randrange(4), fr)

    MAIN2, TOT2 = 24, 32
    r = F.effect("seris_revert", TOT2, MAIN2, sounds=[],
                 note="回龙人：水环收拢落地溅起水冠（与化龙同图集别名，零新增像素）")
    for f in range(TOT2):
        k = (f // 2) % 4; t = min(1, f / 14)
        s = lerp(2.6, 0.9, ease_in(t)); a = 220 if f < 14 else max(0, 220 * (1 - (f - 14) / 6))
        if a > 0:
            r.add(f"vortex{k}", f, [(0, lerp(-80, 30, t), s, s * 0.5, 0, a)])
    for j in range(10, TOT2):
        a = 255 if j < MAIN2 else 255 * (TOT2 - j) / (TOT2 - MAIN2 + 1)
        r.add(f"splash{(j // 3) % 2}", j, [(0, 30, 2.0, 2.0, 0, a)])
    rr = random.Random(43)
    for d in range(12):
        ang = rr.uniform(-math.pi * 0.9, -math.pi * 0.1); v = rr.uniform(10, 18); vx, vy = v * math.cos(ang), v * math.sin(ang)
        x, y = 0, 10; fr = []
        for j in range(12):
            fr.append((x, y, 2.2, 2.2, 0, 255 if j < 9 else 110)); x += vx; y += vy; vy += 2.4
        r.add("drop2", 11, fr)
    return F


FAMILIES = [("tide", fam_tide), ("breath", fam_breath), ("dash", fam_dash), ("lv4", fam_lv4), ("transform", fam_transform)]
