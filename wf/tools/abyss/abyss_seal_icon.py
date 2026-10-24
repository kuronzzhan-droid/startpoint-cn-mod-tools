# -*- coding: utf-8 -*-
"""画「深渊王印」(2370101)的 20x20 像素图标。

与「深渊代币」(2370099)刻意区分:代币是**圆币 + 横向眼瞳**,王印是
**菱形印章 + 纵向王冠齿**。20x20 上只有轮廓能读出来,颜色区分不够用。

规格照自制材料图标惯例:`item/materials/mod/<包>/<名>`,20x20,c3=c4 同一张。
逐像素画,不做抗锯齿。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

SIZE = 20
CX = CY = (SIZE - 1) / 2

GOLD_HI = (255, 236, 168, 255)
GOLD = (222, 172, 66, 255)
GOLD_LO = (142, 100, 30, 255)
FACE_HI = (108, 74, 168, 255)
FACE = (66, 42, 116, 255)
FACE_LO = (36, 20, 66, 255)
CYAN_HI = (198, 252, 255, 255)
CYAN = (104, 230, 255, 255)
CLEAR = (0, 0, 0, 0)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = abs(x - CX), abs(y - CY)
            d = dx + dy                      # 菱形距离(切比雪夫的对偶)
            if d > 9.6:
                continue
            lit = ((CX - x) + (CY - y)) / 14.0
            if d > 8.0:                      # 金边
                c = GOLD_HI if lit > 0.24 else (GOLD_LO if lit < -0.24 else GOLD)
            elif d > 7.0:
                c = GOLD_LO
            else:
                c = FACE_HI if lit > 0.30 else (FACE_LO if lit < -0.26 else FACE)
            px[x, y] = c

    # 王冠齿:三根竖芯,中间高 —— 这是与代币区分的主要读点
    cx = int(CX)
    for x, top, bot in ((cx - 3, 8, 12), (cx, 6, 13), (cx + 3, 8, 12)):
        for y in range(top, bot + 1):
            px[x, y] = CYAN
        px[x, top] = CYAN_HI

    # 齿座:一条横梁把三根齿连起来,免得读成三个点
    for x in range(cx - 4, cx + 5):
        px[x, 13] = CYAN if abs(x - cx) <= 3 else GOLD_HI
    px[cx, 14] = CYAN_HI

    # 顶角高光 / 底角压深
    px[cx, 1] = GOLD_HI
    px[cx, 2] = GOLD_HI
    px[cx, SIZE - 2] = GOLD_LO
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-scale", type=int, default=12)
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(out / "abyss_seal.png")
    icon.resize((SIZE * args.preview_scale, SIZE * args.preview_scale),
                Image.Resampling.NEAREST).save(out / "abyss_seal_preview.png")
    print(f"图标 {icon.size} -> {out / 'abyss_seal.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
