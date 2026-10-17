# -*- coding: utf-8 -*-
"""画「深渊代币」(2370099)的 20x20 像素图标。

规格照自制材料图标实测(2026-09-01):
  路径 `item/materials/mod/<包>/<名>`,20x20,c3 与 c4 指同一张。
  对照:10000145 深界结晶 = item/materials/mod/five_boss/deep_crystal (20x20)
        10000147 五王心核 = item/materials/mod/five_boss/five_king_core (20x20)
官方材料图标打包在 APK 里、CDN 取不到,所以只能换成新路径再投 CDN。

设计:深紫底金边古币,中心一枚青色深渊之眼,左上高光右下暗部。
逐像素画,不用抗锯齿 —— 20x20 上任何羽化都会糊成一团。
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

SIZE = 20
CX = CY = (SIZE - 1) / 2

# 调色板(深渊:紫底 + 金边 + 青芯)
GOLD_HI = (255, 231, 150, 255)
GOLD = (214, 164, 62, 255)
GOLD_LO = (138, 96, 28, 255)
FACE_HI = (86, 62, 140, 255)
FACE = (52, 34, 92, 255)
FACE_LO = (30, 18, 56, 255)
CYAN_HI = (186, 250, 255, 255)
CYAN = (95, 224, 255, 255)
CYAN_LO = (36, 138, 190, 255)
CLEAR = (0, 0, 0, 0)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    px = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - CX, y - CY
            r = math.hypot(dx, dy)
            if r > 9.3:
                continue
            # 光照方向:左上
            lit = (-dx - dy) / 13.0

            if r > 7.2:                                   # 金边
                c = GOLD_HI if lit > 0.30 else (GOLD_LO if lit < -0.28 else GOLD)
            elif r > 6.4:                                 # 边内侧压深一圈
                c = GOLD_LO
            elif r < 2.6:                                 # 深渊之眼
                c = CYAN_HI if lit > 0.10 else CYAN
            elif r < 3.5:
                c = CYAN_LO
            else:                                         # 币面
                c = FACE_HI if lit > 0.34 else (FACE_LO if lit < -0.30 else FACE)
            px[x, y] = c

    # 眼睛的竖瞳:两格暗芯,让它读起来是"眼"不是"珠子"
    for yy in range(int(CY) - 1, int(CY) + 2):
        px[int(CX), yy] = FACE_LO
    px[int(CX), int(CY)] = (12, 8, 26, 255)

    # 左上一点镜面高光,右下一点接触阴影
    px[6, 5] = GOLD_HI
    px[7, 4] = (255, 255, 255, 255)
    px[13, 15] = GOLD_LO
    px[12, 16] = GOLD_LO
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-scale", type=int, default=12)
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(out / "abyss_coin.png")
    icon.resize((SIZE * args.preview_scale, SIZE * args.preview_scale),
                Image.Resampling.NEAREST).save(out / "abyss_coin_preview.png")
    print(f"图标 {icon.size} -> {out / 'abyss_coin.png'}")
    print(f"预览 -> {out / 'abyss_coin_preview.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
