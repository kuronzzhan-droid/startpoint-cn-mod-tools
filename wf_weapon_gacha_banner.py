# -*- coding: utf-8 -*-
"""武器扭蛋（gacha 990003）的列表横幅和卡池封面：纯 PIL 程序化生成，确定性，不联网。

规格照官方实测（out/武器扭蛋-20260928/banner-specs）：
  dynamic/gacha_list_banner/cnmod_weapon_gacha.png  510×180 RGBA（官方 387/387 张同尺寸，
                                                     卡片 x20–489 / y15–166，四周透明，徽记可溢出上下沿）
  dynamic/gacha_banner/cnmod_weapon_gacha.png       1440×1789 RGBA 不透明（官方 76 张装备封面同尺寸，medium 层）
官方装备封面实测分区：英文小字 y≈790、标题 y≈820–1000、飘带 y≈1090、说明 y≈1150–1210，以下只有背景（按钮区）。

视觉：五重/深渊暗色系（暗紫黑底、血红裂纹、金色描边、金色发光字），与官方金色装备扭蛋明显区分。
只用抽象元素：封印法阵、锁链、宝箱轮廓光、符文粒子。**不画任何武器图标、剪影或像素件。**
底色复用 wf_cursed_weapon_banner.backdrop()，发光字复用 wf_abyss_weapon_banner.glow_text()；
两者的 compose() 会画武器图标，这里不调用。

本工具只写源图（默认 mod-tools/assets/weapon-gacha/），不写 store、不发布。

用法（项目根）：
  python mod-tools/wf_weapon_gacha_banner.py
  python mod-tools/wf_weapon_gacha_banner.py --preview out/预览.png --ref-list 官方列表.png --ref-cover 官方封面.png
参考图可以是普通 PNG，也可以是 store 里魔数为小写 \\x89png 的混淆 PNG。
"""
from __future__ import annotations

import argparse
import io
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_abyss_weapon_banner as abyss  # noqa: E402  glow_text() / 微软雅黑路径
import wf_cursed_weapon_banner as cursed  # noqa: E402  backdrop() 暗红紫底色

OUT = TOOLS / "assets" / "weapon-gacha"
LIST_SIZE = (510, 180)
COVER_SIZE = (1440, 1789)
#: 封面内容整体下移量（作者 0928 真机反馈「图稍微往下挪一点」：卡池页顶部的横幅列表压住了宝箱与法阵上半）。
#: 真机约按 0.92 倍显示、顶部裁掉约 54px；下移 120 后说明块下沿 ≈ y1382，仍在抽取按钮（≈ y1550 起）之上。
COVER_SHIFT = 120
SS = 2  # 线稿超采样倍数（PIL 画线不抗锯齿，先画 2 倍再 BOX 缩回）
SEED = 990003

FONT_DIR = Path("C:/Windows/Fonts")
# 标题用思源宋体 Black（系统自带），缺失时回落到现有工具用的微软雅黑粗体
TITLE_FONTS = ((FONT_DIR / "NotoSerifSC-VF.ttf", "Black"), (Path(abyss.FONT_BOLD), None))
LATIN_FONTS = ((FONT_DIR / "CASTELAR.TTF", None), (FONT_DIR / "palab.ttf", None), (Path(abyss.FONT_BOLD), None))
# 小字号下 Castellar 的内刻线会糊，列表横幅改用 Palatino 粗体
LATIN_SMALL_FONTS = ((FONT_DIR / "palab.ttf", None), (FONT_DIR / "BOD_B.TTF", None), (Path(abyss.FONT_BOLD), None))
BODY_FONTS = ((Path(abyss.FONT_BOLD), None),)

GOLD_HI = (255, 242, 200)
GOLD = (244, 202, 110)
GOLD_MID = (218, 160, 66)
GOLD_DEEP = (150, 96, 34)
GOLD_DARK = (92, 54, 18)
BLOOD = (200, 22, 46)
BLOOD_HOT = (255, 96, 86)
IRON = (40, 26, 46)
INK = (10, 4, 14)
CREAM = (248, 236, 244)

TITLE = "武器扭蛋"
LIST_EN = ("WEAPON", "GACHA")
LIST_RIBBON = "诅咒武器每把{0.3%}[｜]死亡使者·终式 {UP}"
COVER_EN = "WEAPON GACHA"
COVER_RIBBON = "{★5} 合计 {15%}！诅咒武器每把 {0.3%}"
COVER_NOTES = (
    "{死亡使者·终式} 概率UP {0.1%}",
    "10连第10抽必得{★4以上}",
    "{250点}可兑换任选诅咒武器",
    "仅限{武器扭蛋券}（五重决战兑换）",
)


# ---------------------------------------------------------------- 字体与字形

def load_font(cands, px: int) -> ImageFont.FreeTypeFont:
    for path, variation in cands:
        if path.exists():
            font = ImageFont.truetype(str(path), px)
            if variation:
                font.set_variation_by_name(variation)
            return font
    raise SystemExit(f"找不到字体：{[str(p) for p, _ in cands]}")


def _glyph_bitmap(font: ImageFont.FreeTypeFont, ch: str) -> tuple[tuple[int, int], bytes]:
    left, top, right, bottom = font.getbbox(ch)
    im = Image.new("L", (max(1, right - left) + 4, max(1, bottom - top) + 4), 0)
    ImageDraw.Draw(im).text((2 - left, 2 - top), ch, font=font, fill=255)
    return im.size, im.tobytes()


def assert_glyphs(font: ImageFont.FreeTypeFont, text: str) -> None:
    """缺字会渲染成 .notdef（豆腐块），和私用区哨兵字符的位图完全相同。"""
    tofu = _glyph_bitmap(font, "\U0010FFFD")
    missing = sorted({ch for ch in text if not ch.isspace() and _glyph_bitmap(font, ch) == tofu})
    if missing:
        raise SystemExit(f"字体 {font.getname()} 缺字：{''.join(missing)}")


def runs(markup: str, base, hi, dim):
    """{…} 高亮金色，[…] 暗金分隔符，其余正文色。"""
    out, buf, mode = [], "", base
    for ch in markup:
        if ch in "{[":
            if buf:
                out.append((buf, mode))
            buf, mode = "", hi if ch == "{" else dim
        elif ch in "}]":
            if buf:
                out.append((buf, mode))
            buf, mode = "", base
        else:
            buf += ch
    if buf:
        out.append((buf, mode))
    return out


# ---------------------------------------------------------------- 像素工具

def rgba_from_alpha(size, color, alpha) -> Image.Image:
    w, h = size
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color[:3]
    arr[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def tint(alpha: Image.Image, color, gain: float = 1.0) -> Image.Image:
    a = np.asarray(alpha, np.float32) * gain * ((color[3] / 255.0) if len(color) > 3 else 1.0)
    return rgba_from_alpha(alpha.size, color, a)


def glow(layer: Image.Image, radius: float, color, gain: float = 1.0) -> Image.Image:
    return tint(layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius)), color, gain)


def radial(size, center, radius, color, amax: float, power: float = 2.0) -> Image.Image:
    w, h = size
    rx, ry = radius if isinstance(radius, tuple) else (radius, radius)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - center[0]) / rx) ** 2 + ((yy - center[1]) / ry) ** 2)
    return rgba_from_alpha(size, color, np.clip(1.0 - d, 0.0, 1.0) ** power * amax)


def vramp(size, y0: float, y1: float, color, a0: float, a1: float) -> Image.Image:
    w, h = size
    t = np.clip((np.arange(h, dtype=np.float32) - y0) / max(1.0, y1 - y0), 0.0, 1.0)
    a = np.repeat((a0 + (a1 - a0) * t)[:, None], w, axis=1)
    return rgba_from_alpha(size, color, a)


def vignette(size, amax: float, power: float = 2.4) -> Image.Image:
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx / w - 0.5) * 2) ** 2 + ((yy / h - 0.5) * 2) ** 2) / math.sqrt(2)
    return rgba_from_alpha(size, (0, 0, 0), np.clip(d, 0, 1) ** power * amax)


def over(dst: Image.Image, src: Image.Image, x: int, y: int) -> None:
    """alpha_composite 的越界安全版本。"""
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dst.alpha_composite(src.crop((sx0, sy0, sx1, sy1)), (x + sx0, y + sy0))


class Art:
    """超采样画布：坐标一律用成品像素，内部乘 SS。"""

    def __init__(self, size):
        self.size = size
        self.im = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def p(pts):
        return [(x * SS, y * SS) for x, y in pts]

    @staticmethod
    def w(v: float) -> int:
        return max(1, round(v * SS))

    def line(self, pts, fill, width: float, closed: bool = False):
        pts = list(pts)
        if closed:
            pts = pts + pts[:1]
        self.d.line(self.p(pts), fill=fill, width=self.w(width), joint="curve")

    def poly(self, pts, fill):
        self.d.polygon(self.p(pts), fill=fill)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width: float = 1):
        box = [(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS]
        self.d.ellipse(box, fill=fill, outline=outline, width=self.w(width) if outline else 0)

    def done(self) -> Image.Image:
        return self.im.resize(self.size, Image.Resampling.BOX)


def ring_pts(cx, cy, r, squash=1.0, n=None, a0=0.0):
    n = n or max(96, int(r * 1.2))
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / n), cy + r * squash * math.sin(a0 + 2 * math.pi * i / n))
            for i in range(n)]


# ---------------------------------------------------------------- 抽象元素

def rune_alphabet(rnd: random.Random, n: int = 28):
    """程序化符文字母表：竖干 + 斜枝（仿卢恩），少量菱形/叉形。坐标在 [-0.5, 0.5]。"""
    out = []
    for _ in range(n):
        strokes = []
        if rnd.random() < 0.72:
            strokes.append(((0.0, -0.5), (0.0, 0.5)))
            for _ in range(rnd.randint(1, 3)):
                v0 = rnd.choice((-0.5, -0.25, 0.0, 0.2))
                side = rnd.choice((-1, 1)) * 0.36
                dv = rnd.choice((-0.3, 0.3, 0.0))
                strokes.append(((0.0, v0), (side, max(-0.5, min(0.5, v0 + dv)))))
        else:
            kind = rnd.randrange(3)
            if kind == 0:
                strokes += [((0, -0.5), (0.36, 0)), ((0.36, 0), (0, 0.5)), ((0, 0.5), (-0.36, 0)), ((-0.36, 0), (0, -0.5))]
            elif kind == 1:
                strokes += [((-0.36, -0.5), (0.36, 0.5)), ((0.36, -0.5), (-0.36, 0.5))]
            else:
                strokes += [((-0.36, -0.5), (0, 0.1)), ((0, 0.1), (0.36, -0.5)), ((0, 0.1), (0, 0.5))]
        out.append(strokes)
    return out


def draw_rune(art: Art, strokes, x, y, size, ang, fill, width, squash=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    for (u0, v0), (u1, v1) in strokes:
        pts = []
        for u, v in ((u0, v0), (u1, v1)):
            px = (u * ca - v * sa) * size
            py = (u * sa + v * ca) * size
            pts.append((x + px, y + py * squash))
        art.line(pts, fill, width)


def draw_seal(art: Art, rnd: random.Random, alphabet, cx, cy, r, *, gold, red, squash=1.0, rot=0.0):
    """封印法阵：双外环 + 刻度 + 符文带 + 六芒星（血红）+ 内符文环。"""
    u = r / 100.0
    art.line(ring_pts(cx, cy, r, squash), gold, max(1.2, 1.3 * u), closed=True)
    art.line(ring_pts(cx, cy, r * 0.955, squash), gold, max(0.8, 0.5 * u), closed=True)
    for i in range(90):
        a = rot + 2 * math.pi * i / 90
        r0 = r * (0.93 if i % 5 else 0.91)
        art.line([(cx + r0 * math.cos(a), cy + r0 * squash * math.sin(a)),
                  (cx + r * 0.955 * math.cos(a), cy + r * 0.955 * squash * math.sin(a))], gold, max(0.7, 0.35 * u))
    n = max(12, int(2 * math.pi * 0.855 / 0.105))
    for i in range(n):
        a = rot + 2 * math.pi * (i + 0.5) / n
        draw_rune(art, alphabet[rnd.randrange(len(alphabet))], cx + r * 0.855 * math.cos(a),
                  cy + r * 0.855 * squash * math.sin(a), r * 0.085, a + math.pi / 2, gold, max(0.8, 0.55 * u), squash)
    art.line(ring_pts(cx, cy, r * 0.78, squash), gold, max(1.0, 0.9 * u), closed=True)
    art.line(ring_pts(cx, cy, r * 0.755, squash), gold, max(0.7, 0.35 * u), closed=True)
    for tri in range(2):
        pts = []
        for j in range(3):
            a = rot - math.pi / 2 + tri * math.pi / 3 + j * 2 * math.pi / 3
            pts.append((cx + r * 0.755 * math.cos(a), cy + r * 0.755 * squash * math.sin(a)))
        art.line(pts, red, max(1.0, 0.8 * u), closed=True)
    for j in range(6):
        a = rot - math.pi / 2 + j * math.pi / 3
        vx, vy = cx + r * 0.755 * math.cos(a), cy + r * 0.755 * squash * math.sin(a)
        art.ellipse(vx, vy, r * 0.042, r * 0.042 * squash, fill=(70, 16, 34, 255), outline=gold, width=max(0.8, 0.6 * u))
        art.ellipse(vx, vy, r * 0.016, r * 0.016 * squash, fill=red)
    art.line(ring_pts(cx, cy, r * 0.37, squash), gold, max(0.8, 0.6 * u), closed=True)
    m = 12
    for i in range(m):
        a = rot + 2 * math.pi * (i + 0.5) / m
        draw_rune(art, alphabet[rnd.randrange(len(alphabet))], cx + r * 0.3 * math.cos(a),
                  cy + r * 0.3 * squash * math.sin(a), r * 0.06, a + math.pi / 2, red, max(0.7, 0.4 * u), squash)
    art.line(ring_pts(cx, cy, r * 0.23, squash), gold, max(0.7, 0.45 * u), closed=True)


def crack_segments(rnd: random.Random, x, y, ang, length, step, w, depth=0):
    segs, base, walked = [], ang, 0.0
    while walked < length:
        ang = base + max(-0.55, min(0.55, (ang - base) + rnd.uniform(-0.5, 0.5)))
        nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
        segs.append((x, y, nx, ny, w))
        if depth < 2 and rnd.random() < 0.15:
            side = rnd.choice((-1, 1))
            segs += crack_segments(rnd, x, y, ang + side * rnd.uniform(0.5, 1.1),
                                   (length - walked) * rnd.uniform(0.3, 0.6), step * 0.8, w * 0.6, depth + 1)
        x, y = nx, ny
        walked += step
        w = max(0.5, w * 0.968)
    return segs


def render_cracks(size, segs, scale: float, strength: float = 1.0) -> Image.Image:
    """血红裂纹：宽暗红缝 + 近/远两层红光 + 细亮芯。"""
    wide, core = Art(size), Art(size)
    for x0, y0, x1, y1, w in segs:
        wide.line([(x0, y0), (x1, y1)], (255, 255, 255, 255), w)
        wide.ellipse(x1, y1, w / 2, w / 2, fill=(255, 255, 255, 255))
        core.line([(x0, y0), (x1, y1)], (255, 255, 255, 255), max(0.5, w * 0.35))
    wide, core = wide.done(), core.done()
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow(wide, 9 * scale, (150, 0, 26, 190), 1.6 * strength))
    out.alpha_composite(glow(wide, 2.5 * scale, BLOOD + (230,), 1.3 * strength))
    out.alpha_composite(tint(wide.getchannel("A"), (96, 4, 18, 255), strength))
    out.alpha_composite(tint(core.getchannel("A"), (255, 150, 120, 255), strength))
    return out


def draw_chain(art: Art, p0, p1, sag, link, *, dark=GOLD_DARK, rim=GOLD, iron=IRON):
    """锁链：沿二次曲线交替画正面环和侧面环。"""
    c = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 + sag)
    pts = []
    for i in range(401):
        t = i / 400
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]))
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + math.dist(a, b))
    step = link * 0.74
    L, W, t = link * SS, link * 0.56 * SS, max(2.0, link * 0.17 * SS)
    tile_side = int(L * 1.5) + 4
    j, s, idx = 0, 0.0, 0
    while s <= acc[-1]:
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        (xa, ya), (xb, yb) = pts[j], pts[j + 1]
        f = (s - acc[j]) / max(1e-6, acc[j + 1] - acc[j])
        x, y = xa + (xb - xa) * f, ya + (yb - ya) * f
        ang = math.degrees(math.atan2(yb - ya, xb - xa))
        tile = Image.new("RGBA", (tile_side, tile_side), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        m = tile_side / 2
        if idx % 2 == 0:
            box = [m - L / 2, m - W / 2, m + L / 2, m + W / 2]
            td.ellipse(box, outline=iron + (255,), width=round(t * 1.35))
            td.ellipse(box, outline=dark + (255,), width=round(t))
            inset = t * 0.28
            td.ellipse([box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset],
                       outline=rim + (255,), width=max(1, round(t * 0.3)))
        else:
            td.rounded_rectangle([m - L / 2, m - t * 0.8, m + L / 2, m + t * 0.8], radius=t * 0.8,
                                 fill=dark + (255,), outline=iron + (255,), width=max(1, round(t * 0.25)))
            td.line([(m - L / 2 + t, m - t * 0.2), (m + L / 2 - t, m - t * 0.2)], fill=rim + (255,),
                    width=max(1, round(t * 0.3)))
        tile = tile.rotate(-ang, resample=Image.Resampling.BICUBIC)
        over(art.im, tile, round(x * SS - m), round(y * SS - m))
        s += step
        idx += 1


def chest_geometry(cx, base_y, w, gap):
    hb = w * 0.44
    top = base_y - hb
    lid_bottom = top - gap
    lid_h = w * 0.34
    straight = lid_bottom - lid_h * 0.42
    ow = w * 0.52
    arch = []
    for i in range(49):
        a = math.pi + math.pi * i / 48
        arch.append((cx + ow * math.cos(a), straight + (lid_h * 0.58) * math.sin(a)))
    lid = [(cx - ow, lid_bottom), *arch, (cx + ow, lid_bottom)]
    body = [(cx - w / 2, top), (cx + w / 2, top), (cx + w / 2, base_y), (cx - w / 2, base_y)]
    return dict(hb=hb, top=top, lid_bottom=lid_bottom, lid_h=lid_h, straight=straight, ow=ow, lid=lid, body=body,
                arch_y=lambda x: straight - (lid_h * 0.58) * math.sqrt(max(0.0, 1 - ((x - cx) / ow) ** 2)))


def render_chest(size, cx, base_y, w, gap, *, lw, fill_alpha=225, lock_plate=True):
    """宝箱轮廓光：只有描边（金）+ 暗底，盖缝漏光。返回 (箱体层, 缝光层)。"""
    g = chest_geometry(cx, base_y, w, gap)
    fill = Art(size)
    fill.poly(g["body"], INK + (fill_alpha,))
    fill.poly(g["lid"], INK + (fill_alpha,))
    lines = Art(size)
    lines.line(g["body"], GOLD + (255,), lw, closed=True)
    lines.line(g["lid"], GOLD + (255,), lw, closed=True)
    thin = lw * 0.55
    rim_y = g["top"] + g["hb"] * 0.15
    lines.line([(cx - w / 2, rim_y), (cx + w / 2, rim_y)], GOLD_MID + (255,), thin)
    band_y = g["lid_bottom"] - g["lid_h"] * 0.13
    lines.line([(cx - g["ow"], band_y), (cx + g["ow"], band_y)], GOLD_MID + (255,), thin)
    for sx in (-0.31, 0.31):
        x = cx + w * sx
        lines.line([(x - w * 0.035, rim_y), (x - w * 0.035, base_y)], GOLD_MID + (255,), thin)
        lines.line([(x + w * 0.035, rim_y), (x + w * 0.035, base_y)], GOLD_MID + (255,), thin)
        for dx in (-0.035, 0.035):
            xx = x + w * dx
            lines.line([(xx, g["lid_bottom"]), (xx, g["arch_y"](xx))], GOLD_MID + (255,), thin)
    for sx in (-1, 1):
        x = cx + sx * w / 2
        c = w * 0.09
        lines.line([(x - sx * c, base_y - lw), (x, base_y - lw), (x, base_y - c)], GOLD_HI + (255,), thin)
        lines.line([(x, g["top"] + c), (x, g["top"] + lw), (x - sx * c, g["top"] + lw)], GOLD_HI + (255,), thin)
    if lock_plate:  # 锁扣：盾形小牌 + 血红锁孔
        pw, py0, py1 = w * 0.085, g["top"] - gap * 0.2, g["top"] + g["hb"] * 0.42
        plate = [(cx - pw, py0), (cx + pw, py0), (cx + pw, py1 - pw * 0.7), (cx, py1), (cx - pw, py1 - pw * 0.7)]
        fill.poly(plate, (26, 10, 22, 255))
        lines.line(plate, GOLD_HI + (255,), thin, closed=True)
        ky = py0 + (py1 - py0) * 0.38
        kr = w * 0.02
        lines.ellipse(cx, ky, kr, kr, fill=BLOOD_HOT + (255,))
        lines.poly([(cx - kr * 0.55, ky), (cx + kr * 0.55, ky), (cx + kr * 0.9, ky + kr * 2.6),
                    (cx - kr * 0.9, ky + kr * 2.6)], BLOOD_HOT + (255,))
    slit = Art(size)
    sy = g["top"] - gap * 0.5
    slit.ellipse(cx, sy, w * 0.5, max(1.0, gap * 0.55), fill=(255, 250, 225, 255))
    body = Image.new("RGBA", size, (0, 0, 0, 0))
    fl = fill.done()
    body.alpha_composite(fl)
    # 盖缝的光打在箱面上：暖色径向光，只落在箱体/箱盖内部
    spill = radial(size, (cx, sy), (w * 0.62, g["hb"] * 0.95), (255, 176, 84), 120, 1.8)
    spill.putalpha(Image.fromarray(np.minimum(np.asarray(spill.getchannel("A")),
                                              np.asarray(fl.getchannel("A"))), "L"))
    body.alpha_composite(spill)
    ln = lines.done()
    body.alpha_composite(glow(ln, max(2.0, lw * 3.5), (255, 170, 60, 200), 1.4))
    body.alpha_composite(ln)
    return body, slit.done(), g


def render_rays(size, rnd: random.Random, apex, spread_x, n, length, color, *, arc=(-165, -15), blur=6.0):
    art = Art(size)
    for _ in range(n):
        ang = math.radians(rnd.uniform(*arc))
        hw = math.radians(rnd.uniform(0.8, 3.2))
        ax = apex[0] + rnd.uniform(-spread_x, spread_x)
        L = length * rnd.uniform(0.55, 1.0)
        a = rnd.randint(22, 70)
        art.poly([(ax, apex[1]), (ax + L * math.cos(ang - hw), apex[1] + L * math.sin(ang - hw)),
                  (ax + L * math.cos(ang + hw), apex[1] + L * math.sin(ang + hw))], color + (a,))
    return art.done().filter(ImageFilter.GaussianBlur(blur))


def render_particles(size, rnd, alphabet, n, box, size_rng, *, alpha_rng=(90, 220), red_ratio=0.3, width=1.0,
                     avoid=None) -> Image.Image:
    art = Art(size)
    x0, y0, x1, y1 = box
    placed = 0
    while placed < n:
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and any(ax0 <= x <= ax1 and ay0 <= y <= ay1 for ax0, ay0, ax1, ay1 in avoid):
            continue
        s = rnd.uniform(*size_rng)
        col = (BLOOD_HOT if rnd.random() < red_ratio else GOLD) + (rnd.randint(*alpha_rng),)
        draw_rune(art, alphabet[rnd.randrange(len(alphabet))], x, y, s, rnd.uniform(-0.35, 0.35), col,
                  max(0.6, width * s / 14))
        placed += 1
    layer = art.done()
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow(layer, max(1.5, size_rng[1] * 0.25), (255, 150, 60, 170), 1.3))
    out.alpha_composite(layer)
    return out


def render_embers(size, rnd, n, box, r_rng, *, avoid=None) -> Image.Image:
    art = Art(size)
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        if avoid and any(ax0 <= x <= ax1 and ay0 <= y <= ay1 for ax0, ay0, ax1, ay1 in avoid):
            continue
        r = rnd.uniform(*r_rng)
        col = (GOLD_HI if rnd.random() < 0.6 else BLOOD_HOT) + (rnd.randint(110, 255),)
        art.ellipse(x, y, r, r, fill=col)
    layer = art.done()
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow(layer, r_rng[1] * 2.2, (255, 160, 70, 200), 1.6))
    out.alpha_composite(layer)
    return out


def render_ribbon(size, x0, x1, yc, h, *, tail, notch, border) -> Image.Image:
    """暗血红飘带，金色上下边，燕尾端。"""
    top, bot = yc - h / 2, yc + h / 2
    tails, band, lines = Art(size), Art(size), Art(size)
    for sx, xe in ((-1, x0), (1, x1)):
        drop = h * 0.16
        xt = xe + sx * tail
        pts = [(xe, top + drop), (xt, top + drop), (xt - sx * notch, yc + drop), (xt, bot + drop), (xe, bot + drop)]
        tails.poly(pts, (70, 8, 24, 255))
        tails.line(pts, GOLD_DEEP + (255,), border * 0.8, closed=True)
    band.poly([(x0, top), (x1, top), (x1, bot), (x0, bot)], (255, 255, 255, 255))
    for y in (top + border * 0.5, bot - border * 0.5):
        lines.line([(x0, y), (x1, y)], GOLD + (255,), border)
    for y in (top + border * 2.6, bot - border * 2.6):
        lines.line([(x0 + h * 0.3, y), (x1 - h * 0.3, y)], GOLD_DEEP + (200,), max(0.6, border * 0.45))
    for xe in (x0, x1):
        d = h * 0.2
        lines.poly([(xe, yc - d), (xe + d * 0.7, yc), (xe, yc + d), (xe - d * 0.7, yc)], GOLD + (255,))
    w, hh = size
    ys = np.arange(hh, dtype=np.float32)
    t = np.clip((ys - top) / max(1.0, h), 0, 1)[:, None, None]
    c_top, c_mid, c_bot = np.array([128, 20, 44]), np.array([92, 10, 32]), np.array([54, 4, 20])
    col = np.where(t < 0.5, c_top + (c_mid - c_top) * (t / 0.5), c_mid + (c_bot - c_mid) * ((t - 0.5) / 0.5))
    grad = np.repeat(col, w, axis=1).astype(np.uint8)
    band_mask = np.asarray(band.done().getchannel("A"))
    arr = np.dstack([grad, band_mask[..., None]])
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(tails.done())
    out.alpha_composite(Image.fromarray(arr, "RGBA"))
    ln = lines.done()
    out.alpha_composite(glow(ln, 3, (255, 170, 60, 150), 1.2))
    out.alpha_composite(ln)
    return out


# ---------------------------------------------------------------- 文字

def gold_title(img: Image.Image, cx: float, ink_top: float, text: str, font, tracking: float, *,
               outline_w: int, glow_color=(255, 150, 40, 150), ember=(200, 20, 50, 150)) -> tuple[int, int]:
    """居中发光金字：abyss.glow_text 打底（辉光 + 暗描边），再叠竖向金属渐变。返回墨迹上下沿。"""
    adv = [font.getlength(ch) for ch in text]
    total = sum(adv) + tracking * (len(text) - 1)
    _, t_top, _, t_bot = font.getbbox(text)
    x = cx - total / 2
    y = ink_top - t_top
    pad = outline_w * 12
    box = (int(x - pad), int(ink_top - pad), int(x + total + pad), int(ink_top + (t_bot - t_top) + pad))
    canvas = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    ember_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    mask = Image.new("L", canvas.size, 0)
    md, ed = ImageDraw.Draw(mask), ImageDraw.Draw(ember_layer)
    pos = []
    xi = x
    for ch, a in zip(text, adv):
        pos.append(((xi - box[0], y - box[1]), ch))
        xi += a + tracking
    for xy, ch in pos:
        ed.text(xy, ch, font=font, fill=ember, stroke_width=outline_w * 4, stroke_fill=ember)
    canvas.alpha_composite(ember_layer.filter(ImageFilter.GaussianBlur(outline_w * 5)))
    for xy, ch in pos:
        abyss.glow_text(canvas, xy, ch, font, GOLD, glow_color, outline_w)
        md.text(xy, ch, font=font, fill=255)
    h = canvas.height
    ink0, ink1 = ink_top - box[1], ink_top - box[1] + (t_bot - t_top)
    ys = np.arange(h, dtype=np.float32)
    t = np.clip((ys - ink0) / max(1.0, ink1 - ink0), 0, 1)
    stops = [(0.0, (255, 250, 226)), (0.38, (255, 222, 132)), (0.55, (232, 164, 58)), (0.72, (255, 206, 108)),
             (1.0, (196, 120, 36))]
    col = np.zeros((h, 3), np.float32)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        sel = (t >= t0) & (t <= t1)
        f = ((t[sel] - t0) / (t1 - t0))[:, None]
        col[sel] = np.array(c0) + (np.array(c1) - np.array(c0)) * f
    grad = np.repeat(col[:, None, :], canvas.width, axis=1).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(np.dstack([grad, np.asarray(mask)[..., None]]), "RGBA"))
    over(img, canvas, box[0], box[1])
    return round(ink_top), round(ink_top + t_bot - t_top)


def tracked_width(font, text: str, tracking: float) -> float:
    return sum(font.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def draw_tracked(img, x, y_center, text, font, tracking, fill, *, stroke=1, stroke_fill=INK + (255,),
                 glow_color=None, glow_r=3.0):
    """逐字加字距的小字，按墨迹竖直居中。"""
    _, t_top, _, t_bot = font.getbbox(text)
    y = y_center - (t_top + t_bot) / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    xi = x
    for ch in text:
        d.text((xi, y), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        xi += font.getlength(ch) + tracking
    if glow_color:
        img.alpha_composite(glow(layer, glow_r, glow_color, 1.5))
    img.alpha_composite(layer)


def draw_runs(img, cx, y_center, parts, font, *, stroke, glow_color=None):
    """多色一行文字（高亮片段），整体水平居中、墨迹竖直居中。"""
    full = "".join(t for t, _ in parts)
    total = font.getlength(full)
    _, t_top, _, t_bot = font.getbbox(full)
    y = y_center - (t_top + t_bot) / 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = cx - total / 2
    for text, color in parts:
        d.text((x, y), text, font=font, fill=color, stroke_width=stroke, stroke_fill=INK + (255,))
        x += font.getlength(text)
    if glow_color:
        img.alpha_composite(glow(layer, stroke * 2.5, glow_color, 1.2))
    img.alpha_composite(layer)
    return cx - total / 2, cx + total / 2


def flourish(art: Art, x0, x1, y, *, width, toward_center: int):
    """细金线 + 菱形端点，toward_center 指向文字一侧（-1 左 / +1 右）。"""
    art.line([(x0, y), (x1, y)], GOLD + (230,), width)
    xs = x1 if toward_center > 0 else x0
    xo = x0 if toward_center > 0 else x1
    d = width * 3.2
    art.poly([(xs, y - d), (xs + d * 0.8, y), (xs, y + d), (xs - d * 0.8, y)], GOLD_HI + (255,))
    art.ellipse(xo, y, width * 1.3, width * 1.3, fill=GOLD + (255,))


# ---------------------------------------------------------------- 成品

def make_list_banner() -> Image.Image:
    rnd = random.Random(SEED)
    alphabet = rune_alphabet(random.Random(SEED + 1))
    W, H = LIST_SIZE
    cx0, cy0, cx1, cy1 = 20, 15, 490, 166  # 卡片对齐官方 20–489 / 15–166；左右 15px 安全边外全透明
    cw, ch = cx1 - cx0, cy1 - cy0
    card = cursed.backdrop((cw, ch))
    card.alpha_composite(radial((cw, ch), (cw / 2, ch * 0.46), (cw * 0.42, ch * 0.8), (150, 34, 96), 120, 1.6))
    card.alpha_composite(radial((cw, ch), (cw / 2, ch * 0.42), (cw * 0.2, ch * 0.5), (255, 170, 80), 38, 2.0))
    segs = []
    for sx, sy, a in ((0, ch * 0.3, 0.12), (0, ch * 0.78, -0.2), (cw, ch * 0.25, math.pi - 0.1),
                      (cw, ch * 0.8, math.pi + 0.18), (cw * 0.3, ch, -math.pi / 2 - 0.4),
                      (cw * 0.72, ch, -math.pi / 2 + 0.35)):
        segs += crack_segments(rnd, sx, sy, a, cw * 0.26, 6, 2.2)
    card.alpha_composite(render_cracks((cw, ch), segs, 0.7, 0.9))
    seal = Art((cw, ch))
    draw_seal(seal, rnd, alphabet, cw / 2, ch * 0.5, 84, gold=GOLD + (150,), red=BLOOD_HOT + (150,), rot=0.08)
    seal_l = seal.done()
    card.alpha_composite(glow(seal_l, 3, (255, 160, 60, 120)))
    card.alpha_composite(seal_l)
    chains = Art((cw, ch))
    draw_chain(chains, (-8, 10), (cw + 8, ch - 2), 10, 12)
    draw_chain(chains, (cw + 8, 10), (-8, ch - 2), 10, 12)
    ch_l = chains.done()
    card.alpha_composite(glow(ch_l, 3, (0, 0, 0, 200), 1.5))
    card.alpha_composite(ch_l)
    card.alpha_composite(render_particles((cw, ch), rnd, alphabet, 20, (6, 6, cw - 6, ch - 30), (5, 9),
                                          alpha_rng=(90, 190), avoid=[(cw * 0.2, 18, cw * 0.8, 100)]))
    card.alpha_composite(render_embers((cw, ch), rnd, 26, (4, 4, cw - 4, ch - 4), (0.5, 1.3)))
    card.alpha_composite(radial((cw, ch), (cw / 2, ch * 0.5), (cw * 0.34, ch * 0.38), (8, 2, 12), 150, 1.2))
    card.alpha_composite(vignette((cw, ch), 170, 2.6))

    img = Image.new("RGBA", LIST_SIZE, (0, 0, 0, 0))
    m = Art(LIST_SIZE)
    m.d.rounded_rectangle([cx0 * SS, cy0 * SS, cx1 * SS, cy1 * SS], radius=10 * SS, fill=(255, 255, 255, 255))
    card_full = Image.new("RGBA", LIST_SIZE, (0, 0, 0, 0))
    card_full.paste(card, (cx0, cy0))
    card_full.putalpha(m.done().getchannel("A"))
    img.alpha_composite(card_full)

    frame = Art(LIST_SIZE)
    frame.d.rounded_rectangle([cx0 * SS, cy0 * SS, cx1 * SS, cy1 * SS], radius=10 * SS,
                              outline=GOLD_DARK + (255,), width=round(3.2 * SS))
    frame.d.rounded_rectangle([(cx0 + 1) * SS, (cy0 + 1) * SS, (cx1 - 1) * SS, (cy1 - 1) * SS], radius=9 * SS,
                              outline=GOLD + (255,), width=round(1.3 * SS))
    frame.d.rounded_rectangle([(cx0 + 5) * SS, (cy0 + 5) * SS, (cx1 - 5) * SS, (cy1 - 5) * SS], radius=6 * SS,
                              outline=GOLD_DEEP + (170,), width=round(0.6 * SS))
    for x, y in ((cx0 + 5, cy0 + 5), (cx1 - 5, cy0 + 5), (cx0 + 5, cy1 - 5), (cx1 - 5, cy1 - 5)):
        frame.poly([(x, y - 5), (x + 4, y), (x, y + 5), (x - 4, y)], GOLD_HI + (255,))
    fr = frame.done()
    img.alpha_composite(glow(fr, 2.5, (255, 160, 60, 110)))
    img.alpha_composite(fr)

    # 顶部徽记：宝箱轮廓光（溢出上沿，同官方盾徽的位置）
    chest_cx, chest_base, chest_w = W / 2, 37, 44
    img.alpha_composite(radial(LIST_SIZE, (chest_cx, chest_base - 19), (44, 26), (255, 190, 100), 110, 1.6))
    rays = render_rays(LIST_SIZE, rnd, (chest_cx, chest_base - 20), 14, 18, 40, (255, 222, 150),
                       arc=(-165, -15), blur=1.6)
    img.alpha_composite(rays)
    img.alpha_composite(rays)
    body, slit, _ = render_chest(LIST_SIZE, chest_cx, chest_base, chest_w, 3.2, lw=1.7, fill_alpha=245)
    img.alpha_composite(glow(body, 3, (0, 0, 0, 200), 1.2))
    img.alpha_composite(body)
    img.alpha_composite(glow(slit, 4, (255, 200, 110, 255), 2.4))
    img.alpha_composite(slit)

    f_en = load_font(LATIN_SMALL_FONTS, 14)
    assert_glyphs(f_en, "".join(LIST_EN))
    tr = 2.6
    lw_ = tracked_width(f_en, LIST_EN[0], tr)
    draw_tracked(img, chest_cx - 32 - lw_, 26, LIST_EN[0], f_en, tr, GOLD_HI + (255,), stroke=0,
                 glow_color=(255, 150, 50, 190), glow_r=2.0)
    draw_tracked(img, chest_cx + 33, 26, LIST_EN[1], f_en, tr, GOLD_HI + (255,), stroke=0,
                 glow_color=(255, 150, 50, 190), glow_r=2.0)
    fl = Art(LIST_SIZE)
    flourish(fl, cx0 + 26, chest_cx - 38 - lw_, 26, width=0.8, toward_center=1)
    flourish(fl, chest_cx + 39 + tracked_width(f_en, LIST_EN[1], tr), cx1 - 26, 26, width=0.8, toward_center=-1)
    img.alpha_composite(fl.done())

    f_title = load_font(TITLE_FONTS, 66)
    assert_glyphs(f_title, TITLE)
    gold_title(img, W / 2, 40, TITLE, f_title, 7, outline_w=3)

    rib_y, rib_h = 135, 25
    img.alpha_composite(render_ribbon(LIST_SIZE, 44, W - 44, rib_y, rib_h, tail=16, notch=6, border=1.3))
    f_rib = load_font(BODY_FONTS, 17)
    parts = runs(LIST_RIBBON, CREAM + (255,), GOLD + (255,), GOLD_MID + (255,))
    assert_glyphs(f_rib, "".join(t for t, _ in parts))
    draw_runs(img, W / 2, rib_y, parts, f_rib, stroke=1)
    alpha = np.asarray(img.getchannel("A")).copy()
    alpha[:, :15] = 0
    alpha[:, W - 15:] = 0
    img.putalpha(Image.fromarray(alpha, "L"))
    return img


def make_cover() -> Image.Image:
    rnd = random.Random(SEED + 7)
    alphabet = rune_alphabet(random.Random(SEED + 1))
    W, H = COVER_SIZE
    oy = COVER_SHIFT  # 上部与文字区整体下移；底部按钮区装饰仍贴底
    img = cursed.backdrop(COVER_SIZE)
    img.alpha_composite(radial(COVER_SIZE, (W / 2, 360 + oy), (900, 760), (140, 26, 90), 150, 1.5))
    img.alpha_composite(radial(COVER_SIZE, (W / 2, 420 + oy), (520, 420), (255, 160, 70), 46, 2.0))
    img.alpha_composite(vramp(COVER_SIZE, 1150 + oy, 1789, (6, 2, 8), 0, 150))

    seal_c, seal_r = (W / 2, 350 + oy), 316
    segs = []
    base = (W / 2, 640 + oy)
    for a in (-2.95, -2.6, -0.5, -0.18, 2.75, 2.35, 0.45, 0.8, 1.35, 1.8):
        segs += crack_segments(rnd, base[0] + rnd.uniform(-160, 160), base[1] + rnd.uniform(-10, 20), a,
                               rnd.uniform(420, 760), 16, 6.5)
    for sx, sy, a in ((0, 140, 0.3), (W, 90, math.pi - 0.25), (0, 560, -0.15), (W, 620, math.pi + 0.1)):
        segs += crack_segments(rnd, sx, sy + oy, a, 380, 14, 5.0)
    img.alpha_composite(render_cracks(COVER_SIZE, segs, 2.2, 1.0))
    # 底部按钮区：只放极淡的大法阵弧和血色雾，不抢按钮
    deep = Art(COVER_SIZE)
    draw_seal(deep, rnd, alphabet, W / 2, 1720, 760, gold=GOLD + (60,), red=BLOOD_HOT + (70,), squash=0.3, rot=0.6)
    img.alpha_composite(deep.done())
    img.alpha_composite(radial(COVER_SIZE, (W / 2, 1789), (980, 420), (150, 10, 40), 70, 1.4))

    # 远景立面法阵 + 地面法阵
    seal = Art(COVER_SIZE)
    draw_seal(seal, rnd, alphabet, *seal_c, seal_r, gold=GOLD + (225,), red=BLOOD_HOT + (230,), rot=0.05)
    sl = seal.done()
    img.alpha_composite(glow(sl, 14, (255, 140, 50, 150), 1.2))
    img.alpha_composite(glow(sl, 4, (255, 190, 90, 200), 1.0))
    img.alpha_composite(sl)
    floor = Art(COVER_SIZE)
    draw_seal(floor, rnd, alphabet, W / 2, 648 + oy, 430, gold=GOLD + (200,), red=BLOOD_HOT + (210,), squash=0.23,
              rot=0.3)
    fl = floor.done()
    img.alpha_composite(glow(fl, 8, (255, 90, 60, 150), 1.3))
    img.alpha_composite(fl)

    chest_base, chest_w, gap = 628 + oy, 400, 18
    g = chest_geometry(W / 2, chest_base, chest_w, gap)
    slit_y = g["top"] - gap / 2
    img.alpha_composite(radial(COVER_SIZE, (W / 2, slit_y), (560, 300), (255, 200, 110), 90, 2.2))
    img.alpha_composite(render_rays(COVER_SIZE, rnd, (W / 2, slit_y), chest_w * 0.42, 46, 760, (255, 196, 104),
                                    blur=7))

    chains = Art(COVER_SIZE)
    lock = (W / 2, g["top"] + g["hb"] * 0.4)
    draw_chain(chains, (-70, 150 + oy), (lock[0] + 30, lock[1] + 12), 28, 46)
    draw_chain(chains, (W + 70, 150 + oy), (lock[0] - 30, lock[1] + 12), 28, 46)
    draw_chain(chains, (-70, 690 + oy), (lock[0] + 20, lock[1] - 4), -24, 46)
    draw_chain(chains, (W + 70, 690 + oy), (lock[0] - 20, lock[1] - 4), -24, 46)
    body, slit, _ = render_chest(COVER_SIZE, W / 2, chest_base, chest_w, gap, lw=6.5, lock_plate=False)
    img.alpha_composite(glow(body, 18, (0, 0, 0, 230), 1.4))
    img.alpha_composite(body)
    cl = chains.done()
    img.alpha_composite(glow(cl, 9, (0, 0, 0, 230), 1.6))
    img.alpha_composite(glow(cl, 3, (255, 150, 60, 110), 1.0))
    img.alpha_composite(cl)
    img.alpha_composite(glow(slit, 16, (255, 196, 100, 255), 2.2))
    img.alpha_composite(glow(slit, 5, (255, 236, 180, 255), 2.0))
    img.alpha_composite(slit)

    # 封印锁印：链条交汇处的圆形印章（血红符文）
    medal = Art(COVER_SIZE)
    mr = 44
    medal.ellipse(*lock, mr, mr, fill=(24, 8, 20, 255), outline=GOLD + (255,), width=5)
    medal.ellipse(*lock, mr * 0.78, mr * 0.78, outline=GOLD_MID + (255,), width=2)
    algiz = [((0, -0.5), (0, 0.5)), ((0, -0.02), (-0.34, -0.42)), ((0, -0.02), (0.34, -0.42))]  # ᛉ 守护
    draw_rune(medal, algiz, lock[0], lock[1] + mr * 0.04, mr * 0.95, 0.0, BLOOD_HOT + (255,), 5.5)
    ml = medal.done()
    img.alpha_composite(glow(ml, 12, (220, 30, 50, 220), 1.6))
    img.alpha_composite(ml)

    text_zone = (160, 700 + oy, W - 160, 1290 + oy)
    img.alpha_composite(render_particles(COVER_SIZE, rnd, alphabet, 64, (30, 30, W - 30, 740 + oy), (14, 30),
                                         avoid=[(W / 2 - 250, 200 + oy, W / 2 + 250, 660 + oy)]))
    img.alpha_composite(render_particles(COVER_SIZE, rnd, alphabet, 22, (30, 740 + oy, W - 30, H - 40), (12, 24),
                                         alpha_rng=(50, 120), avoid=[text_zone]))
    img.alpha_composite(render_embers(COVER_SIZE, rnd, 150, (0, 0, W, H), (1.2, 3.4), avoid=[text_zone]))

    # 文字区压暗，保证可读
    img.alpha_composite(radial(COVER_SIZE, (W / 2, 1000 + oy), (860, 330), (6, 2, 10), 205, 0.9))
    img.alpha_composite(vignette(COVER_SIZE, 190, 2.4))

    f_en = load_font(LATIN_FONTS, 46)
    assert_glyphs(f_en, COVER_EN)
    tr = 12
    ew = tracked_width(f_en, COVER_EN, tr)
    en_y = 778 + oy
    draw_tracked(img, W / 2 - ew / 2, en_y, COVER_EN, f_en, tr, GOLD_HI + (255,), stroke=0,
                 glow_color=(255, 150, 50, 220), glow_r=5)
    fla = Art(COVER_SIZE)
    flourish(fla, 150, W / 2 - ew / 2 - 34, en_y, width=2.4, toward_center=1)
    flourish(fla, W / 2 + ew / 2 + 34, W - 150, en_y, width=2.4, toward_center=-1)
    img.alpha_composite(fla.done())

    f_title = load_font(TITLE_FONTS, 196)
    assert_glyphs(f_title, TITLE)
    gold_title(img, W / 2, 810 + oy, TITLE, f_title, 22, outline_w=8)

    rib_y, rib_h = 1072 + oy, 58
    img.alpha_composite(render_ribbon(COVER_SIZE, 250, W - 250, rib_y, rib_h, tail=46, notch=16, border=3))
    f_rib = load_font(BODY_FONTS, 38)
    parts = runs(COVER_RIBBON, CREAM + (255,), GOLD + (255,), GOLD_MID + (255,))
    assert_glyphs(f_rib, "".join(t for t, _ in parts))
    draw_runs(img, W / 2, rib_y, parts, f_rib, stroke=2)

    f_note = load_font(BODY_FONTS, 28)
    notes = [runs(n, (236, 224, 238, 255), GOLD + (255,), GOLD_MID + (255,)) for n in COVER_NOTES]
    widest = max(f_note.getlength("".join(t for t, _ in parts)) for parts in notes)
    bx = W / 2 - (widest + 30) / 2  # 说明块整体居中、行内左对齐，菱形项目符号成一列
    bullets = Art(COVER_SIZE)
    for i, parts in enumerate(notes):
        full = "".join(t for t, _ in parts)
        assert_glyphs(f_note, full)
        y = 1136 + oy + i * 37
        draw_runs(img, bx + 30 + f_note.getlength(full) / 2, y, parts, f_note, stroke=2)
        d = 6.5
        bullets.poly([(bx + 8, y - d), (bx + 8 + d * 0.8, y), (bx + 8, y + d), (bx + 8 - d * 0.8, y)], GOLD + (255,))
    bl = bullets.done()
    img.alpha_composite(glow(bl, 3, (255, 150, 50, 160)))
    img.alpha_composite(bl)
    return img


# ---------------------------------------------------------------- 预览与校验

def load_png_any(path: Path) -> Image.Image:
    raw = Path(path).read_bytes()
    if raw[1:4] != b"PNG":  # store 里的混淆魔数是小写 \x89png
        raw = raw[:1] + b"PNG" + raw[4:]
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def checker(size, a=(58, 54, 64), b=(46, 42, 52), cell=10) -> Image.Image:
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    sel = ((xx // cell + yy // cell) % 2).astype(bool)
    arr = np.where(sel[..., None], np.array(a, np.uint8), np.array(b, np.uint8))
    return Image.fromarray(np.dstack([arr, np.full((h, w, 1), 255, np.uint8)]).astype(np.uint8), "RGBA")


def build_preview(list_img, cover_img, ref_list, ref_cover) -> Image.Image:
    f_h = load_font(BODY_FONTS, 30)
    f_s = ImageFont.truetype(abyss.FONT, 20)
    cw, chh = 720, round(COVER_SIZE[1] * 720 / COVER_SIZE[0])
    gap, top = 40, 70
    W = gap * 3 + cw * 2
    H = top + 40 + 180 * 2 + 30 + 60 + 40 + chh + 50
    sheet = Image.new("RGBA", (W, H), (22, 18, 26, 255))
    d = ImageDraw.Draw(sheet)
    d.text((gap, 20), "武器扭蛋 横幅/封面预览（左：本作  右：官方装备扭蛋，同比例）", font=f_h, fill=(240, 230, 240))
    cols = [(gap, "本作 list_banner.png 510×180（1x / 2x）", list_img),
            (gap * 2 + cw, "官方 equipment_gacha_list 510×180（1x / 2x）", ref_list)]
    y = top + 30
    for x, label, im in cols:
        d.text((x, y - 28), label, font=f_s, fill=(200, 190, 210))
        if im is None:
            d.text((x, y + 60), "（未提供参考图）", font=f_s, fill=(160, 150, 170))
            continue
        bg = checker((510, 180))
        bg.alpha_composite(im)
        sheet.alpha_composite(bg, (x, y))
        big = checker((720, 254), cell=12)
        big.alpha_composite(im.resize((720, 254), Image.Resampling.LANCZOS))
        sheet.alpha_composite(big, (x, y + 190))
    y += 190 + 254 + 60
    cols = [(gap, "本作 cover.png 1440×1789（50%，虚线=官方文字下沿 y≈1210）", cover_img),
            (gap * 2 + cw, "官方 equipment_gacha 1440×1789（50%）", ref_cover)]
    for x, label, im in cols:
        d.text((x, y - 28), label, font=f_s, fill=(200, 190, 210))
        if im is None:
            d.text((x, y + 60), "（未提供参考图）", font=f_s, fill=(160, 150, 170))
            continue
        sheet.alpha_composite(im.resize((cw, chh), Image.Resampling.LANCZOS), (x, y))
        yy = y + round(1210 * cw / COVER_SIZE[0])
        for xx in range(x - 16, x - 2, 6):
            d.line([(xx, yy), (xx + 3, yy)], fill=(120, 220, 255), width=2)
    return sheet.crop((0, 0, W, y + chh + 20))


def verify(path: Path, size, *, opaque: bool) -> str:
    im = Image.open(path)
    im.load()
    if im.size != size or im.mode != "RGBA":
        raise SystemExit(f"{path}: {im.size} {im.mode}，期望 {size} RGBA")
    amin = im.getchannel("A").getextrema()[0]
    if opaque and amin != 255:
        raise SystemExit(f"{path}: 存在非不透明像素（alpha 最小 {amin}）")
    return f"{path} {im.size[0]}x{im.size[1]} {im.mode} alpha_min={amin}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT), help="输出目录（默认 mod-tools/assets/weapon-gacha）")
    ap.add_argument("--preview", help="额外输出对比拼板 PNG")
    ap.add_argument("--ref-list", help="官方列表横幅（普通 PNG 或 store 混淆 PNG）")
    ap.add_argument("--ref-cover", help="官方卡池封面（普通 PNG 或 store 混淆 PNG）")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    list_img = make_list_banner()
    cover_img = make_cover()
    if list_img.size != LIST_SIZE or cover_img.size != COVER_SIZE:
        raise SystemExit("尺寸不符")
    cover_img = cover_img.copy()
    cover_img.putalpha(255)
    list_path, cover_path = out / "list_banner.png", out / "cover.png"
    list_img.save(list_path, optimize=True)
    cover_img.save(cover_path, optimize=True)
    print(verify(list_path, LIST_SIZE, opaque=False))
    print(verify(cover_path, COVER_SIZE, opaque=True))

    if args.preview:
        ref_list = load_png_any(Path(args.ref_list)) if args.ref_list else None
        ref_cover = load_png_any(Path(args.ref_cover)) if args.ref_cover else None
        prev = Path(args.preview)
        prev.parent.mkdir(parents=True, exist_ok=True)
        build_preview(Image.open(list_path).convert("RGBA"), Image.open(cover_path).convert("RGBA"),
                      ref_list, ref_cover).convert("RGB").save(prev, optimize=True)
        print(f"preview {prev}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
