# -*- coding: utf-8 -*-
"""程序化像素件（全部锁进 palette.WATER / palette.RED）。确定性：同参同输出。"""
import math
import random
from PIL import Image, ImageDraw
from palette import WATER, RED, rgb

W = [rgb(c) + (255,) for c in WATER]   # 0 最深 … 11 白
R = [rgb(c) + (255,) for c in RED]     # 0 最深 … 7 白
CLEAR = (0, 0, 0, 0)


def new(w, h):
    return Image.new("RGBA", (w, h), CLEAR)


# ------------------------------------------------------------------ 浪峰（横向可平铺）
def crest(w=140, h=56, phase=0, seed=1, big=False):
    im = new(w, h)
    px = im.load()
    rnd = random.Random(seed * 97 + phase)
    ph = phase * 2 * math.pi / 3
    amp1, amp2 = (7, 3) if not big else (9, 4)
    base = 16 if not big else 20
    tops = []
    for x in range(w):
        t = 2 * math.pi * x / w
        y = base + amp1 * math.sin(t + ph) + amp2 * math.sin(3 * t + 2 * ph) + 1.5 * math.sin(5 * t - ph)
        tops.append(int(round(y)))
    bands = [(2, 11), (4, 10), (7, 9), (11, 8), (17, 7), (25, 6), (34, 5), (999, 4)]
    for x in range(w):
        for y in range(tops[x], h):
            d = y - tops[x]
            for lim, ci in bands:
                if d < lim:
                    px[x, y] = W[ci]; break
    # 卷边泡沫：在峰顶附近加白色向前卷的唇
    for x in range(w):
        t = 2 * math.pi * x / w
        lip = math.sin(t + ph + 0.6)
        if lip > 0.55:
            for k in range(1, 3 + int(lip * 2)):
                y = tops[x] - k
                if 0 <= y < h:
                    px[x, y] = W[11] if k < 3 else W[10]
    # 泡沫斑与浪花
    for _ in range(w // 3):
        x = rnd.randrange(w); d = rnd.randrange(4, 15); y = tops[x] + d
        if y < h:
            px[x, y] = W[10] if rnd.random() < 0.5 else W[11]
            if x + 1 < w: px[(x + 1) % w, y] = W[9]
    for _ in range(w // 6):
        x = rnd.randrange(w)
        if math.sin(2 * math.pi * x / w + ph) > 0.2:
            y = tops[x] - rnd.randrange(4, 12)
            if 0 <= y < h:
                px[x, y] = W[11]
                if y + 1 < h and rnd.random() < 0.5: px[x, y + 1] = W[9]
    return im


def body_gradient(w=4, h=24):
    im = new(w, h); px = im.load()
    cols = [W[4], W[3], W[2], W[1]]
    for y in range(h):
        c = cols[min(3, y * 4 // h)]
        for x in range(w):
            px[x, y] = c
    return im


def streak(w=22):
    im = new(w, 2); px = im.load()
    for x in range(w):
        e = min(x, w - 1 - x)
        c = W[9] if e > 4 else W[7]
        px[x, 0] = c
        if 3 < e:
            px[x, 1] = W[8]
    return im


# ------------------------------------------------------------------ 水柱
def spout(stage, w=44, h=120, seed=3):
    im = new(w, h); px = im.load(); rnd = random.Random(seed + stage * 13)
    cx = w // 2
    top = {0: int(h * 0.55), 1: 18, 2: 26, 3: 52}[stage]
    for y in range(top, h):
        f = (y - top) / max(1, h - top)
        half = 5 + 10 * f + (2 if stage == 3 else 0) * math.sin(y * 0.4)
        if stage == 3:
            half *= 0.75
        for x in range(w):
            dx = abs(x - cx + 0.6 * math.sin(y * 0.25 + stage))
            if dx <= half:
                r = dx / half
                ci = 11 if r < 0.18 else 9 if r < 0.4 else 7 if r < 0.62 else 5 if r < 0.85 else 4
                if y > h - 6 and r > 0.5:
                    ci = 4
                px[x, y] = W[ci]
    # 冠
    crown_r = {0: 7, 1: 11, 2: 14, 3: 0}[stage]
    if crown_r:
        cy = top + 2
        for y in range(max(0, cy - crown_r), cy + crown_r):
            for x in range(w):
                d = math.hypot(x - cx, (y - cy) * 1.3)
                wob = crown_r + 1.5 * math.sin(math.atan2(y - cy, x - cx) * 5 + stage)
                if d <= wob:
                    px[x, y] = W[11] if d < wob * 0.45 else W[10] if d < wob * 0.75 else W[8]
    # 飞沫
    n = {0: 4, 1: 10, 2: 26, 3: 14}[stage]
    for _ in range(n):
        if stage == 3:
            x = cx + rnd.randint(-18, 18); y = rnd.randint(top - 10, h - 20)
        else:
            a = rnd.uniform(-math.pi * 0.95, -math.pi * 0.05)
            r = rnd.uniform(crown_r + 2, crown_r + (20 if stage == 2 else 10))
            x = int(cx + r * math.cos(a)); y = int(top + 2 + r * math.sin(a))
        if 1 <= x < w - 1 and 1 <= y < h - 1:
            px[x, y] = W[11]
            if rnd.random() < 0.5: px[x, y + 1] = W[8]
    return im


def droplet(size):
    if size == 1:
        im = new(3, 3); d = ImageDraw.Draw(im)
        d.point([(1, 0), (0, 1), (2, 1), (1, 2)], fill=W[8]); d.point((1, 1), fill=W[11]); return im
    if size == 2:
        im = new(5, 5); d = ImageDraw.Draw(im)
        d.ellipse((0, 0, 4, 4), fill=W[7]); d.point([(1, 1), (2, 1), (1, 2)], fill=W[11]); return im
    im = new(5, 8); d = ImageDraw.Draw(im)         # 泪滴（尖朝上）
    d.ellipse((0, 3, 4, 7), fill=W[6]); d.polygon([(2, 0), (0, 4), (4, 4)], fill=W[6])
    d.point([(1, 4), (1, 5), (2, 3)], fill=W[11]); d.point((3, 6), fill=W[4])
    return im


def foam_ring(w=60, h=18, seed=5):
    im = new(w, h); px = im.load(); rnd = random.Random(seed)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    for y in range(h):
        for x in range(w):
            e = ((x - cx) / (w / 2 - 0.5)) ** 2 + ((y - cy) / (h / 2 - 0.5)) ** 2
            if 0.62 <= e <= 1.0:
                ang = math.atan2((y - cy) * w / h, x - cx)
                if math.sin(ang * 7 + 0.5) > -0.75:
                    px[x, y] = W[11] if e > 0.82 else W[9]
    return im


def flash(r=20, col="water"):
    s = 2 * r + 1
    im = new(s, s); px = im.load()
    P = W if col == "water" else R
    hi, mid, lo = (11, 9, 7) if col == "water" else (7, 6, 4)
    for y in range(s):
        for x in range(s):
            dx, dy = x - r, y - r
            d = math.hypot(dx, dy)
            star = max(0.0, 1 - min(abs(dx), abs(dy)) / 2.2) * (1 - d / r)
            core = 1 - d / (r * 0.42)
            v = max(star * 1.4, core)
            if v > 0.66: px[x, y] = P[hi]
            elif v > 0.36: px[x, y] = P[mid]
            elif v > 0.14: px[x, y] = P[lo]
    return im


# ------------------------------------------------------------------ 吐息光柱（纵向可平铺）
def beam_tile(phase, w=44, h=64, seed=7):
    im = new(w, h); px = im.load(); rnd = random.Random(seed)
    edge = [rnd.choice([0, 0, 1, 1, 2]) for _ in range(h)]
    cx = (w - 1) / 2
    shift = phase * h // 3
    for y in range(h):
        e = edge[(y - shift) % h]
        half = 18 - e
        for x in range(w):
            dx = abs(x - cx)
            if dx > half:
                continue
            r = dx / half
            ci = 11 if r < 0.2 else 10 if r < 0.34 else 8 if r < 0.52 else 6 if r < 0.72 else 5 if r < 0.88 else 4
            # 斜向水流纹（随 phase 下移）
            s = (x * 0.55 + (y - shift)) % 16
            if 0.3 < r < 0.9 and s < 2.2:
                ci = min(11, ci + 2)
            elif 0.45 < r < 0.95 and 8 < s < 9.5:
                ci = max(3, ci - 1)
            px[x, y] = W[ci]
    for _ in range(10):                         # 外侧飞沫
        y = (rnd.randrange(h) + shift) % h
        side = rnd.choice([-1, 1])
        x = int(cx + side * (19 + rnd.randrange(3)))
        if 0 <= x < w:
            px[x, y] = W[9]
    return im


def ellipse_ring(w=56, h=16):
    im = new(w, h); d = ImageDraw.Draw(im)
    d.ellipse((0, 0, w - 1, h - 1), outline=W[9], width=2)
    d.arc((0, 0, w - 1, h - 1), 200, 340, fill=W[11], width=2)
    return im


# ------------------------------------------------------------------ 水翼
def wing(w=76, h=58, seed=11):
    im = new(w, h); d = ImageDraw.Draw(im)
    root = (6, h - 6)
    feathers = [(18, 70, 9), (36, 64, 9), (54, 56, 8), (72, 46, 7)]   # (角度°, 长, 半宽)
    for k, (ang, L, hw) in enumerate(feathers):
        a = math.radians(-ang)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        for layer, (scale, ci) in enumerate(((1.0, 4), (0.78, 6), (0.52, 8), (0.25, 11))):
            pts = []
            for i in range(13):
                t = i / 12
                wdt = hw * scale * math.sin(math.pi * min(1, t * 1.15)) ** 0.8
                pts.append((root[0] + ux * L * t + nx * wdt, root[1] + uy * L * t + ny * wdt))
            for i in range(12, -1, -1):
                t = i / 12
                wdt = hw * scale * math.sin(math.pi * min(1, t * 1.15)) ** 0.8
                pts.append((root[0] + ux * L * t - nx * wdt * 0.6, root[1] + uy * L * t - ny * wdt * 0.6))
            d.polygon(pts, fill=W[ci])
        tip = (root[0] + ux * L, root[1] + uy * L)
        d.point([(int(tip[0]), int(tip[1]))], fill=W[11])
    # 前缘白沫（单侧缘光）
    rnd = random.Random(seed)
    px = im.load()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if px[x, y][3] and not px[x, y - 1][3] and rnd.random() < 0.8:
                px[x, y] = W[11] if rnd.random() < 0.6 else W[10]
    return im


# ------------------------------------------------------------------ 红雷
def bolt(w, h, seed, branches=2, thick=1):
    rnd = random.Random(seed)
    im = new(w, h); d = ImageDraw.Draw(im)
    def path(x0, y0, x1, y1, n, jit):
        pts = [(x0, y0)]
        for i in range(1, n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t + rnd.uniform(-jit, jit), y0 + (y1 - y0) * t + rnd.uniform(-jit * 0.3, jit * 0.3)))
        pts.append((x1, y1))
        return pts
    cx = w / 2
    main = path(cx + rnd.uniform(-w * 0.1, w * 0.1), 0, cx + rnd.uniform(-w * 0.15, w * 0.15), h - 1, max(6, h // 14), w * 0.16)
    segs = [(main, 1.0)]
    for _ in range(branches):
        i = rnd.randrange(2, len(main) - 3)
        x0, y0 = main[i]
        x1 = x0 + rnd.choice([-1, 1]) * rnd.uniform(w * 0.2, w * 0.42)
        y1 = y0 + rnd.uniform(h * 0.12, h * 0.3)
        segs.append((path(x0, y0, max(1, min(w - 2, x1)), min(h - 2, y1), 4, w * 0.08), 0.6))
    for pts, k in segs:                     # 暗红晕 → 红 → 粉 → 白芯
        d.line(pts, fill=R[2], width=max(1, int(round((5 + thick) * k))))
    for pts, k in segs:
        d.line(pts, fill=R[3], width=max(1, int(round((3 + thick) * k))))
    for pts, k in segs:
        d.line(pts, fill=R[5], width=max(1, int(round((1 + thick) * k))))
    for pts, k in segs:
        if k == 1.0:
            d.line(pts, fill=R[7], width=thick)
    return im


def spark(r=6, seed=2):
    s = 2 * r + 1; im = new(s, s); d = ImageDraw.Draw(im); rnd = random.Random(seed)
    for k in range(5):
        a = rnd.uniform(0, 2 * math.pi); L = rnd.uniform(r * 0.5, r)
        mid = (r + math.cos(a) * L * 0.5 + rnd.uniform(-1.5, 1.5), r + math.sin(a) * L * 0.5 + rnd.uniform(-1.5, 1.5))
        d.line([(r, r), mid, (r + math.cos(a) * L, r + math.sin(a) * L)], fill=R[4], width=1)
    d.point((r, r), fill=R[7])
    return im


def quantize(im, pal):
    """把 AI 件吸进锁定色板；alpha 二值化（<96 透明，其余不透明）。"""
    cols = [rgb(c) for c in pal]
    im = im.convert("RGBA"); out = new(*im.size); po = out.load(); pi = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pi[x, y]
            if a < 96:
                continue
            best = min(cols, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            po[x, y] = best + (255,)
    return out


def dark_bg_key(im, thr=40):
    """RD vfx 输出若带近黑背景：按亮度键掉（辉光件惯例）。"""
    im = im.convert("RGBA"); px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a and max(r, g, b) < thr:
                px[x, y] = CLEAR
    return im


# ------------------------------------------------------------------ 固有状态图标 48×48（官方：白边圆角方+渐变底+白色字形）
def unique_icon():
    S = 4; N = 48 * S
    im = Image.new("RGBA", (N, N), CLEAR); d = ImageDraw.Draw(im)
    d.rounded_rectangle((2 * S, 2 * S, N - 2 * S - 1, N - 2 * S - 1), radius=9 * S, fill=(255, 255, 255, 255))
    grad = Image.new("RGBA", (N, N), CLEAR); gp = grad.load()
    top, bot = rgb(WATER[6]), rgb(WATER[2])
    for y in range(N):
        t = y / (N - 1)
        c = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)) + (255,)
        for x in range(N):
            gp[x, y] = c
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle((5 * S, 5 * S, N - 5 * S - 1, N - 5 * S - 1), radius=7 * S, fill=255)
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    k = N / 192
    head = [(36, 98), (66, 80), (90, 62), (112, 58), (146, 26), (130, 64), (166, 52), (146, 84), (150, 120),
            (126, 112), (102, 118), (74, 108), (52, 112), (38, 108)]
    d.polygon([(x * k, y * k) for x, y in head], fill=(255, 255, 255, 255))
    d.ellipse((100 * k, 72 * k, 112 * k, 84 * k), fill=rgb(WATER[3]) + (255,))       # 眼
    d.line([(60 * k, 102 * k), (86 * k, 98 * k)], fill=rgb(WATER[3]) + (255,), width=int(4 * k))  # 口线
    wave = []
    for i in range(41):
        x = 30 + i * 3.3
        wave.append((x * k, (146 + 9 * math.sin(i / 40 * 2 * math.pi * 1.5)) * k))
    d.line(wave, fill=(255, 255, 255, 255), width=int(11 * k), joint="curve")
    d.ellipse((150 * k, 128 * k, 166 * k, 144 * k), fill=(255, 255, 255, 255))
    return im.resize((48, 48), Image.LANCZOS)
