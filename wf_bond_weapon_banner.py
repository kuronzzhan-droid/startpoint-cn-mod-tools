# -*- coding: utf-8 -*-
"""合成「羁绊武器·觉醒」装备强化分类的 banner / header（规格照官方实测：1000×184 / 1440×556）。

素材：8 把羁绊武器的 20×20 觉醒图标（mod-tools/assets/bond-weapons/<stem>_lv120.png），NEAREST 整数倍放大。
版式沿用 wf_abyss_weapon_banner / wf_cursed_weapon_banner（左标题右图标带），底色换成暖金；只有中文（作者 0928「除武器名字，
其他地方都不要英文」），所以没有英文副标题。

用法：python mod-tools/wf_bond_weapon_banner.py [--out mod-tools/assets/bond-weapons]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_abyss_weapon_banner as abyss  # noqa: E402
import wf_bond_weapon_enhance as B  # noqa: E402

TITLE = "羁绊武器·觉醒"
SUBTITLE = "信赖之证兑换武器 · 强化解放"
BANNER_FILE, HEADER_FILE = "bond_weapon_banner.png", "bond_weapon_header.png"


def backdrop(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(30 + 62 * (1 - t) ** 2)
        g = int(20 + 40 * (1 - t) ** 2)
        b = int(14 + 18 * (1 - t) ** 2)
        for x in range(w):
            px[x, y] = (r, g, b, 255)
    streak = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(streak)
    for off, wid, a in ((-0.12, 0.09, 38), (0.30, 0.05, 28), (0.66, 0.07, 22)):
        x0 = int(w * off)
        d.polygon([(x0, h), (x0 + int(w * wid), h), (x0 + int(w * wid) + h, 0), (x0 + h, 0)], fill=(255, 196, 92, a))
    img.alpha_composite(streak.filter(ImageFilter.GaussianBlur(radius=max(2, h // 90))))
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, int(h * 0.55), w, h], fill=(0, 0, 0, 100))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(radius=h // 12)))
    return img


def compose(size: tuple[int, int], icons: list[Image.Image], *, rows: int, scale: int, title_px: int,
            sub_px: int) -> Image.Image:
    w, h = size
    img = backdrop(size)
    cell = 20 * scale
    gap = max(4, scale)
    per_row = math.ceil(len(icons) / rows)
    band = Image.new("RGBA", size, (0, 0, 0, 0))
    total_w = per_row * (cell + gap) - gap
    x0 = w - total_w - int(w * 0.03)
    total_h = rows * cell + (rows - 1) * gap
    y0 = int(h * 0.5 - total_h / 2)
    for i, icon in enumerate(icons):
        r, c = divmod(i, per_row)
        up = icon.resize((cell, cell), Image.Resampling.NEAREST)
        y = y0 + r * (cell + gap) + int(math.sin(i * 0.9) * cell * 0.07)
        band.alpha_composite(up, (x0 + c * (cell + gap), y))
    img.alpha_composite(band.filter(ImageFilter.GaussianBlur(radius=scale * 2)))
    img.alpha_composite(band)
    f_title = ImageFont.truetype(abyss.FONT_BOLD, title_px)
    f_sub = ImageFont.truetype(abyss.FONT, sub_px)
    tx, ty = int(w * 0.035), int(h * 0.5 - title_px * 0.72)
    abyss.glow_text(img, (tx, ty), TITLE, f_title, (255, 244, 214, 255), (255, 176, 60, 130), max(2, title_px // 22))
    ImageDraw.Draw(img).text((tx + 3, ty + int(title_px * 1.18) + int(h * 0.02)), SUBTITLE, font=f_sub,
                             fill=(255, 218, 150, 235), stroke_width=1, stroke_fill=(20, 10, 4, 255))
    return img


def load_icons(art: Path = B.ART) -> list[Image.Image]:
    """8 张 Lv120 图标，按官方 general_shop 顺序；缺图直接报错（横幅展示觉醒图，与深渊/诅咒先例一致）。"""
    baseline = B.load_baseline()
    icons = []
    for w in baseline.values():
        path = art / f"{w['stem']}_lv120.png"
        if not path.is_file():
            raise SystemExit(f"缺图：{path}")
        icons.append(Image.open(path).convert("RGBA"))
    return icons


def render(art: Path = B.ART) -> tuple[Image.Image, Image.Image]:
    icons = load_icons(art)
    banner = compose(B.BANNER_SIZE, icons, rows=2, scale=4, title_px=54, sub_px=22)
    header = compose(B.HEADER_SIZE, icons, rows=2, scale=8, title_px=96, sub_px=34)
    return banner, header


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(B.ART))
    args = ap.parse_args(argv)
    banner, header = render()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    banner.save(out / BANNER_FILE, optimize=True)
    header.save(out / HEADER_FILE, optimize=True)
    print(banner.size, header.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
