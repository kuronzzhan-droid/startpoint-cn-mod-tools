# -*- coding: utf-8 -*-
"""魂珠兑换横幅候选：仿官方领主币兑换横幅（1000x184，左侧像素物件 + 右侧放射光/棋盘带 + 货币大图标 + 白字粗描边标题）。
用法：python gen_banner.py  → cand_*.png + 预览 preview.png"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = Path(__file__).resolve().parent
REF = HERE / "ref"
W, H = 1000, 184
FONT = r"C:/Windows/Fonts/NotoSansSC-VF.ttf"


def font(size, wght=900):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def icon(name, scale):
    im = Image.open(REF / name).convert("RGBA")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def rounded_mask(r=14):
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, W - 1, H - 1), r, fill=255)
    return m


def build(theme, left_icons, title, subtitle, cur_icon, out):
    dark, mid, ray_a, ray_b, outline = theme["dark"], theme["mid"], theme["ray_a"], theme["ray_b"], theme["outline"]
    img = Image.new("RGBA", (W, H), dark + (255,))
    px = img.load()
    # 左侧面板：横向暗→中渐变
    for x in range(W):
        c = lerp(dark, mid, min(1, x / 620))
        for y in range(H):
            px[x, y] = c + (255,)
    # 左侧像素物件（像官方的头目像素画：大倍率、局部出画、略压暗）
    art = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name, scale, x, y, a in left_icons:
        ic = icon(name, scale)
        if a < 255:
            al = ic.getchannel("A").point(lambda v: v * a // 255)
            ic.putalpha(al)
        art.alpha_composite(ic, (x, y))
    shade = Image.new("RGBA", (W, H), dark + (0,))
    sd = ImageDraw.Draw(shade)
    for x in range(W):  # 物件往右逐渐淡出到标题区
        t = max(0.0, min(1.0, (x - 230) / 260))
        sd.line([(x, 0), (x, H)], fill=dark + (int(200 * t),))
    art = Image.alpha_composite(art, shade)
    art.putalpha(ImageChops.multiply(art.getchannel("A"), Image.new("L", (W, H), 255)))
    img.alpha_composite(art)
    # 右侧放射光（下方三角区）
    cx, cy = 905, 92
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    n = 28
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = 2 * math.pi * (i + 0.5) / n
        R = 900
        rd.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))],
                   fill=ray_a + (255,))
    base = Image.new("RGBA", (W, H), ray_b + (255,))
    base.alpha_composite(rays)
    # 中心光晕
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - 150, cy - 150, cx + 150, cy + 150), fill=(255, 255, 255, 120))
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    region = Image.new("L", (W, H), 0)
    ImageDraw.Draw(region).polygon([(470, H), (W, H), (W, 0), (720, 0)], fill=255)
    img.paste(base, (0, 0), region)
    # 顶部斜向暗带 + 棋盘格（官方「方格旗」带）
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.polygon([(600, 0), (W, 0), (W, 30), (630, 120)], fill=(24, 14, 6, 215))
    sq = 30
    for i in range(-2, 22):
        for j in range(0, 6):
            if (i + j) % 2:
                continue
            x0 = 640 + i * sq - j * sq * 0.55
            y0 = j * sq
            pts = [(x0, y0), (x0 + sq, y0), (x0 + sq - sq * 0.55, y0 + sq), (x0 - sq * 0.55, y0 + sq)]
            bd.polygon(pts, fill=(0, 0, 0, 235))
    bmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bmask).polygon([(600, 0), (W, 0), (W, 30), (630, 120)], fill=255)
    band.putalpha(ImageChops.multiply(band.getchannel("A"), bmask))
    img.alpha_composite(band)
    # 货币大图标（20px 像素图 ×6.25 ≈ 官方 125px），白色描边光
    ci = Image.open(REF / cur_icon).convert("RGBA")
    big = ci.resize((125, 125), Image.NEAREST)
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a.alpha_composite(big, (cx - 62, cy - 62))
    wa = a.getchannel("A").filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
    halo.paste((255, 255, 255, 255), (0, 0), wa)
    img.alpha_composite(halo)
    img.alpha_composite(a)
    # 标题与副标题
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(txt)
    ft = font(86)
    tw = td.textbbox((0, 0), title, font=ft)
    tx = 505 - (tw[2] - tw[0]) // 2 - tw[0]
    ty = 22 - tw[1]
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((tx + 2, ty + 4), title, font=ft, fill=outline + (230,), stroke_width=10, stroke_fill=outline + (230,))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
    td.text((tx, ty), title, font=ft, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=outline + (255,))
    fs = font(30, 800)
    sub = f"-  {subtitle}  -"
    sw = td.textbbox((0, 0), sub, font=fs)
    sx = 505 - (sw[2] - sw[0]) // 2 - sw[0]
    td.text((sx, 132 - sw[1]), sub, font=fs, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=outline + (255,))
    img.alpha_composite(txt)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), rounded_mask()))
    img.save(out)
    return img


THEMES = {
    "purple": dict(dark=(36, 14, 70), mid=(70, 28, 140), ray_a=(196, 120, 255), ray_b=(150, 70, 230), outline=(40, 10, 80)),
    "teal": dict(dark=(8, 40, 52), mid=(16, 92, 110), ray_a=(120, 230, 230), ray_b=(40, 170, 180), outline=(6, 40, 50)),
    "crimson": dict(dark=(60, 6, 18), mid=(120, 16, 36), ray_a=(255, 130, 130), ray_b=(220, 60, 70), outline=(60, 0, 12)),
    "gold": dict(dark=(60, 32, 4), mid=(130, 80, 10), ray_a=(255, 220, 120), ray_b=(235, 170, 40), outline=(70, 36, 0)),
}
LEFT = [("soul_5910120.png", 10, -40, -30, 255), ("soul_5920001.png", 7, 125, 28, 255), ("soul_5910129.png", 6, 255, 52, 215)]

if __name__ == "__main__":
    out = []
    specs = [
        ("cand_A_purple_steel", "purple", "禁忌星铁"),
        ("cand_B_purple_coin", "purple", "领主币"),
        ("cand_C_teal_steel", "teal", "禁忌星铁"),
        ("cand_D_crimson_steel", "crimson", "禁忌星铁"),
        ("cand_E_gold_steel", "gold", "禁忌星铁"),
    ]
    for name, th, sub in specs:
        out.append(build(THEMES[th], LEFT, "魂珠兑换", sub, "item_10000311_upload.png", HERE / f"{name}.png"))
    refs = [Image.open(REF / f).convert("RGBA") for f in ("boss_battle_33_evil_envy_upload.png", "boss_battle_31_empress_01_upload.png")]
    allim = refs + out
    sheet = Image.new("RGBA", (W, (H + 10) * len(allim)), (255, 255, 255, 255))
    for i, im in enumerate(allim):
        sheet.alpha_composite(im, (0, i * (H + 10)))
    sheet.save(HERE / "preview.png")
    print("ok", len(out))
