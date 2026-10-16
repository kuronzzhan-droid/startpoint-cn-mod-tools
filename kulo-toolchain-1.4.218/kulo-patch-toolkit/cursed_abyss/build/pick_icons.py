# -*- coding: utf-8 -*-
"""挑选 RD 候选 → ../art/final/<slug>.png / <slug>_lv120.png（20×20）。
补两颗像素闪星（仿现有深渊图标：本体彩色小星、Lv120 白/金星），只画在全透明格上；alpha 二值化。"""
from pathlib import Path

from PIL import Image

ART = Path(__file__).resolve().parent.parent / "art"
PICK = {  # slug: (lv0 候选, lv120 候选)
    "light_03": ("light_03_lv0_a0", "light_03_lv120_b1"),
    "dark_03": ("dark_03_lv0_a0", "dark_03_lv120_a0"),
    "dark_04": ("dark_04_lv0_b0", "dark_04_lv120_a0"),
    "thunder_03": ("thunder_03_lv0_a0", "thunder_03_lv120_a0"),
    "wind_03": ("wind_03_lv0_a1", "wind_03_lv120_a0"),
    "wind_04": ("wind_04_lv0_a0", "wind_04_lv120_a0"),
    "fire_03": ("fire_03_lv0_a1", "fire_03_lv120_a0"),
    "fire_04": ("fire_04_lv0_a1", "fire_04_lv120_a0"),
    "water_03": ("water_03_lv0_a1", "water_03_lv120_b1"),
}
STAR0 = {"light": (255, 220, 120), "dark": (230, 90, 255), "thunder": (255, 230, 80), "wind": (120, 255, 170),
         "fire": (255, 90, 60), "water": (90, 200, 255)}


def sparkle(im: Image.Image, color, spots=((2, 17), (17, 2), (16, 16))) -> Image.Image:
    im = im.copy()
    px = im.load()
    drawn = 0
    for cx, cy in spots:
        cells = [(cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]
        if all(0 <= x < 20 and 0 <= y < 20 and px[x, y][3] == 0 for x, y in cells):
            for i, (x, y) in enumerate(cells):
                px[x, y] = (255, 255, 255, 255) if i == 0 else color + (255,)
            drawn += 1
            if drawn == 2:
                break
    return im


def binarize(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
    return im


def main() -> None:
    (ART / "final").mkdir(parents=True, exist_ok=True)
    for slug, (c0, c120) in PICK.items():
        el = slug.split("_")[0]
        im0 = binarize(Image.open(ART / "cand" / f"{c0}.png"))
        im120 = binarize(Image.open(ART / "cand" / f"{c120}.png"))
        assert im0.size == im120.size == (20, 20), slug
        sparkle(im0, STAR0[el]).save(ART / "final" / f"{slug}.png")
        sparkle(im120, (255, 215, 90)).save(ART / "final" / f"{slug}_lv120.png")
        print(slug, c0, c120)


if __name__ == "__main__":
    main()
