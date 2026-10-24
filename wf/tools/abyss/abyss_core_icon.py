# -*- coding: utf-8 -*-
"""画「深渊觉醒核」(2370100)的 20x20 像素图标。

三件深渊素材必须**靠轮廓**区分 —— 20x20 上只换配色是读不出来的:
    深渊代币 2370099 = 圆币 + 横向眼瞳
    深渊王印 2370101 = 菱形印 + 纵向王冠齿
    深渊觉醒核 2370100 = **纵向棱晶** + 白炽核心 + 上下金封端(本文件)
它是最终节点材料,所以做得最亮:核心用纯白,外圈青紫,金封端点睛。

原图标 `item/materials/equipment_enhancement_materials/steam_robot_material_none_r5`
是官方路径,**打包在 APK 里、CDN 取不到**,所以只能换成自制路径。
规格照自制材料图标惯例:`item/materials/mod/<包>/<名>`,20x20,c3=c4 同一张。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

SIZE = 20
CX = (SIZE - 1) / 2

GOLD_HI = (255, 238, 176, 255)
GOLD = (226, 176, 70, 255)
GOLD_LO = (140, 98, 30, 255)
SHELL_HI = (150, 110, 220, 255)
SHELL = (92, 58, 160, 255)
SHELL_LO = (44, 24, 82, 255)
CORE_HOT = (255, 255, 255, 255)
CORE = (176, 246, 255, 255)
CORE_MID = (86, 214, 255, 255)
CLEAR = (0, 0, 0, 0)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    px = img.load()

    # 棱晶轮廓:上下各一个尖,中段最宽 —— 纵向长条,和圆/菱形都不撞
    # half[y] = 该行从中心向外的半宽
    half = [0, 0, 1, 2, 3, 4, 5, 5, 6, 6, 6, 6, 5, 5, 4, 3, 2, 1, 0, 0]
    for y in range(SIZE):
        h = half[y]
        if h <= 0:
            continue
        for x in range(int(CX - h), int(CX + h) + 1):
            dx = x - CX
            edge = abs(dx) >= h - 0.5
            lit = (-dx - (y - CX) * 0.4) / 9.0
            if edge:
                c = SHELL_LO if lit < -0.20 else (SHELL_HI if lit > 0.32 else SHELL)
            else:
                c = SHELL_HI if lit > 0.30 else SHELL
            px[x, y] = c

    # 白炽核心:中段一个竖椭圆
    for y in range(7, 13):
        w = 2 if 8 <= y <= 11 else 1
        for x in range(int(CX - w), int(CX + w) + 1):
            px[x, y] = CORE_MID
    for y in range(8, 12):
        for x in range(int(CX - 1), int(CX + 1) + 1):
            px[x, y] = CORE
    px[int(CX), 9] = CORE_HOT
    px[int(CX), 10] = CORE_HOT

    # 上下金封端
    for y, hw in ((3, 1), (4, 2), (15, 2), (16, 1)):
        for x in range(int(CX - hw), int(CX + hw) + 1):
            px[x, y] = GOLD if y < 10 else GOLD_LO
    px[int(CX), 2] = GOLD_HI
    px[int(CX), 17] = GOLD_LO

    # 核心外溢的两点高光,让它读起来在"发光"
    px[int(CX) - 3, 9] = CORE_MID
    px[int(CX) + 3, 10] = CORE_MID
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-scale", type=int, default=12)
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(out / "abyss_core.png")
    icon.resize((SIZE * args.preview_scale, SIZE * args.preview_scale),
                Image.Resampling.NEAREST).save(out / "abyss_core_preview.png")
    print(f"图标 {icon.size} -> {out / 'abyss_core.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
