# -*- coding: utf-8 -*-
"""画「全面限制」状态图标(48x48),用于 unique_condition 180002。

规格照 live 实测:`battle/common/unique_condition/<string_id>.png`,48x48,
79/79 官方行都走这个前缀(unique_wind_spgirl_1anv / unique_girl_and_mecha /
unique_zeta 逐个量过都是 48x48)。

设计语言:这是 **Bad 向**状态(condition_direction=1),所以走暗红紫底 + 断裂
锁链 + 禁止斜杠,和增益类的青金色系拉开。48x48 有足够空间画细节,但仍是
像素资产,不做抗锯齿。
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image

SIZE = 48
C = (SIZE - 1) / 2

VOID_HI = (96, 34, 78, 255)
VOID = (58, 18, 50, 255)
VOID_LO = (28, 8, 26, 255)
RING_HI = (214, 78, 96, 255)
RING = (162, 40, 62, 255)
RING_LO = (92, 18, 34, 255)
CHAIN_HI = (226, 210, 226, 255)
CHAIN = (158, 142, 166, 255)
CHAIN_LO = (92, 78, 102, 255)
SLASH = (255, 226, 232, 255)
CLEAR = (0, 0, 0, 0)


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    px = img.load()

    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - C, y - C
            r = math.hypot(dx, dy)
            if r > 22.4:
                continue
            lit = (-dx - dy) / 32.0
            if r > 18.6:                       # 外环
                c = RING_HI if lit > 0.22 else (RING_LO if lit < -0.22 else RING)
            elif r > 16.8:
                c = RING_LO
            else:                              # 深渊底
                c = VOID_HI if lit > 0.30 else (VOID_LO if lit < -0.26 else VOID)
            px[x, y] = c

    # 断裂的锁链:两段弧,中间断开 —— "限制"的读点
    for side in (-1, 1):
        for t in range(-38, 39):
            a = math.radians(t * 1.6)
            rr = 12.0
            x = int(round(C + side * rr * math.cos(a)))
            y = int(round(C + rr * math.sin(a)))
            if 0 <= x < SIZE and 0 <= y < SIZE:
                px[x, y] = CHAIN
                if 0 <= x + 1 < SIZE:
                    px[x + 1, y] = CHAIN_LO
                if 0 <= y - 1 < SIZE and abs(t) % 9 < 3:
                    px[x, y - 1] = CHAIN_HI

    # 禁止斜杠:左上到右下,压在锁链之上
    for i in range(-15, 16):
        for w in range(-2, 3):
            x = int(round(C + i)) + w
            y = int(round(C + i))
            if 0 <= x < SIZE and 0 <= y < SIZE:
                px[x, y] = SLASH if abs(w) <= 1 else RING_LO

    # 四角小刺,强调"封"
    for ax, ay in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        for k in range(19, 23):
            x = int(round(C + ax * k)); y = int(round(C + ay * k))
            if 0 <= x < SIZE and 0 <= y < SIZE:
                px[x, y] = RING_HI
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-scale", type=int, default=6)
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(out / "unique_boss_all_limit.png")
    icon.resize((SIZE * args.preview_scale, SIZE * args.preview_scale),
                Image.Resampling.NEAREST).save(out / "unique_boss_all_limit_preview.png")
    print(f"图标 {icon.size} -> {out / 'unique_boss_all_limit.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
