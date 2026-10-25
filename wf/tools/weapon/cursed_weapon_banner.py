# -*- coding: utf-8 -*-
"""合成「诅咒武器·觉醒」装备强化分类的 banner / header（规格照官方实测：1000×184 / 1440×556）。

素材：23 把诅咒武器的 20×20 觉醒图标（mod-tools/assets/cursed-weapons/<slug>_lv120.png），NEAREST 整数倍放大。
版式沿用 wf_abyss_weapon_banner（左标题右图标带），底色换成暗红紫。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_abyss_weapon_banner as abyss  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402

ART = TOOLS / "assets" / "cursed-weapons"
TITLE = "诅咒武器·觉醒"
SUBTITLE = "CURSED ARMAMENT · AWAKENING"


def backdrop(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(20 + 58 * (1 - t) ** 2)
        g = int(6 + 8 * (1 - t) ** 2)
        b = int(22 + 40 * (1 - t) ** 2)
        for x in range(w):
            px[x, y] = (r, g, b, 255)
    streak = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(streak)
    for off, wid, a in ((-0.12, 0.09, 40), (0.30, 0.05, 30), (0.66, 0.07, 22)):
        x0 = int(w * off)
        d.polygon([(x0, h), (x0 + int(w * wid), h), (x0 + int(w * wid) + h, 0), (x0 + h, 0)], fill=(200, 40, 90, a))
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
    gap = max(3, scale)
    per_row = math.ceil(len(icons) / rows)
    band = Image.new("RGBA", size, (0, 0, 0, 0))
    total_w = per_row * (cell + gap) - gap
    x0 = w - total_w - int(w * 0.025)
    total_h = rows * cell + (rows - 1) * gap
    y0 = int(h * 0.5 - total_h / 2)
    for i, icon in enumerate(icons):
        r, c = divmod(i, per_row)
        up = icon.resize((cell, cell), Image.Resampling.NEAREST)
        dx = (cell // 2) if r % 2 else 0
        y = y0 + r * (cell + gap) + int(math.sin(i * 0.9) * cell * 0.08)
        band.alpha_composite(up, (min(w - cell, x0 + c * (cell + gap) + dx - (cell // 4 if r % 2 else 0)), y))
    img.alpha_composite(band.filter(ImageFilter.GaussianBlur(radius=scale * 2)))
    img.alpha_composite(band)
    f_title = ImageFont.truetype(abyss.FONT_BOLD, title_px)
    f_sub = ImageFont.truetype(abyss.FONT, sub_px)
    tx, ty = int(w * 0.035), int(h * 0.5 - title_px * 0.72)
    abyss.glow_text(img, (tx, ty), TITLE, f_title, (255, 236, 236, 255), (220, 40, 90, 130), max(2, title_px // 22))
    ImageDraw.Draw(img).text((tx + 3, ty + int(title_px * 1.18) + int(h * 0.02)), SUBTITLE, font=f_sub,
                             fill=(255, 150, 180, 235), stroke_width=1, stroke_fill=(10, 4, 12, 255))
    return img


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ART))
    args = ap.parse_args(argv)
    icons = []
    for w in W.weapons():
        path = ART / f"{w.slug}_lv120.png"
        if not path.exists():
            raise SystemExit(f"缺图：{path}")
        icons.append(Image.open(path).convert("RGBA"))
    out = Path(args.out)
    banner = compose((1000, 184), icons[:12], rows=2, scale=3, title_px=54, sub_px=19)
    header = compose((1440, 556), icons, rows=3, scale=4, title_px=90, sub_px=30)
    banner.save(out / "cursed_weapon_banner.png")
    header.save(out / "cursed_weapon_header.png")
    print(banner.size, header.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
