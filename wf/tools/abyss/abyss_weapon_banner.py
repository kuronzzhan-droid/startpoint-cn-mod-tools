# -*- coding: utf-8 -*-
"""合成「深渊武装·觉醒」装备强化分类的 banner / header 两张图。

规格照官方实测(2026-09-01):
  dynamic/equipment_enhancement/<name>_banner.png  = 1000x184
  dynamic/equipment_enhancement/<name>_header.png  = 1440x556
素材:15 把觉醒武器自己的 20x20 像素图标(item/equipment/mod/abyss/*),
NEAREST 整数倍放大,不插值。
"""
from __future__ import annotations

import argparse
import io
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from wf.paths import REPOSITORY

TOOLS = REPOSITORY  # 仓库根；本文件已从根目录搬到 wf/tools/
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

PROD = Path(r"弹国服/WorldFlipper/dummy/download/production")
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT = "C:/Windows/Fonts/msyh.ttc"

BANNER = (1000, 184)
HEADER = (1440, 556)


def load_icons(salt: str) -> list[Image.Image]:
    logical = "master/equipment_enhancement/equipment_enhancement.orderedmap"
    rows = core.read_orderedmap_file(
        core.table_path(PROD / "upload", logical), logical).text_rows()
    icons = []
    for i in range(1, 16):
        key = f"80001{i:02d}"
        if key not in rows:
            continue
        path = core.read_csv_lines(rows[key])[0][4]
        if not path.endswith(".png"):
            path += ".png"
        for root in ("upload", "medium_upload", "android_upload"):
            f = rescale.store_path(PROD / root, path, salt)
            if f.exists():
                raw = f.read_bytes()
                icons.append(Image.open(io.BytesIO(raw[:1] + b"PNG" + raw[4:])).convert("RGBA"))
                break
    return icons


def backdrop(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 255))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        # 深渊:上方靛紫 -> 下方近黑,带一点青
        r = int(18 + 26 * (1 - t) ** 2)
        g = int(12 + 30 * (1 - t) ** 2)
        b = int(38 + 62 * (1 - t) ** 2)
        for x in range(w):
            px[x, y] = (r, g, b, 255)
    # 斜向光带
    streak = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(streak)
    for i, (off, wid, a) in enumerate(((-0.15, 0.10, 34), (0.28, 0.05, 26), (0.62, 0.08, 20))):
        x0 = int(w * off)
        d.polygon([(x0, h), (x0 + int(w * wid), h), (x0 + int(w * wid) + h, 0), (x0 + h, 0)],
                  fill=(120, 205, 255, a))
    streak = streak.filter(ImageFilter.GaussianBlur(radius=max(2, h // 90)))
    img.alpha_composite(streak)
    # 底部压暗,给文字留对比
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle([0, int(h * 0.55), w, h], fill=(0, 0, 0, 90))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(radius=h // 12)))
    return img


def glow_text(base: Image.Image, xy, text, font, fill, glow, outline_w: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=font, fill=glow, stroke_width=outline_w * 3, stroke_fill=glow)
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius=outline_w * 2.5)))
    d2 = ImageDraw.Draw(base)
    d2.text(xy, text, font=font, fill=fill,
            stroke_width=outline_w, stroke_fill=(8, 6, 20, 255))


def compose(size: tuple[int, int], icons: list[Image.Image], *, title: str,
            subtitle: str, icon_scale: int, title_px: int, sub_px: int) -> Image.Image:
    w, h = size
    img = backdrop(size)

    # 图标带:整数倍 NEAREST 放大,沿右侧排开,轻微上下错位
    if icons:
        cell = 20 * icon_scale
        gap = max(4, icon_scale)
        total = len(icons) * (cell + gap) - gap
        x = w - total - int(w * 0.03)
        base_y = int(h * 0.52 - cell / 2)
        band = Image.new("RGBA", size, (0, 0, 0, 0))
        for i, ic in enumerate(icons):
            up = ic.resize((cell, cell), Image.Resampling.NEAREST)
            y = base_y + int(math.sin(i * 0.9) * cell * 0.16)
            band.alpha_composite(up, (x + i * (cell + gap), y))
        # 图标层做一层柔光垫底
        img.alpha_composite(band.filter(ImageFilter.GaussianBlur(radius=icon_scale * 2)))
        img.alpha_composite(band)

    f_title = ImageFont.truetype(FONT_BOLD, title_px)
    f_sub = ImageFont.truetype(FONT, sub_px)
    tx = int(w * 0.035)
    ty = int(h * 0.5 - title_px * 0.72)
    glow_text(img, (tx, ty), title, f_title, (255, 246, 220, 255), (90, 200, 255, 120),
              max(2, title_px // 22))
    d = ImageDraw.Draw(img)
    d.text((tx + 3, ty + title_px + int(h * 0.03)), subtitle, font=f_sub,
           fill=(150, 215, 255, 235), stroke_width=1, stroke_fill=(6, 8, 22, 255))
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="输出目录")
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    salt = rescale.salt()
    icons = load_icons(salt)
    if len(icons) != 15:
        print(f"警告:只取到 {len(icons)} 个武器图标")

    banner = compose(BANNER, icons, title="深渊武装·觉醒", subtitle="ABYSS ARMAMENT · AWAKENING",
                     icon_scale=2, title_px=54, sub_px=19)
    header = compose(HEADER, icons, title="深渊武装·觉醒", subtitle="ABYSS ARMAMENT · AWAKENING",
                     icon_scale=5, title_px=108, sub_px=34)
    banner.save(out / "abyss_weapon_banner.png")
    header.save(out / "abyss_weapon_header.png")
    print(f"banner {banner.size} -> {out / 'abyss_weapon_banner.png'}")
    print(f"header {header.size} -> {out / 'abyss_weapon_header.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
