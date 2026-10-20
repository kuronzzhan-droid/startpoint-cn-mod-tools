# -*- coding: utf-8 -*-
"""水杰拉德技能演出预览：按技能 DSL 的时间轴把 4 个全屏特效叠到同一张 1080×1920 画布（缩 1/4），出 GIF + 接触表。
只读官方特效族（雨丝按技能里的换色规则转色），不读包内文件；坐标/混合按 fx_survey 渲染器同一套算法。"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
TOOLS = Path(r"D:/WF/out/水杰拉德-20261018/fx_survey/tools")
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import wfio, fxlib  # noqa
import wg_color  # noqa

FW, FH, SC = 1080, 1920, 0.25
ROWS = {r["base"]: r for r in json.loads((TOOLS / "rows.json").read_text(encoding="utf-8"))}
# (名字, 官方路径, 起始帧, 层序, 换色规则)
TRACKS = [
    ("潮水垫底", "battle/effect/skill_unique/navy_officer/navy_officer_wave", 0, None),
    ("雨丝", "battle/effect/skill_unique/holy_mother/holy_mother_all", 18, [{"from": [150, 200], "to": 212}]),
    ("水浪", "battle/effect/skill_unique/drawing_witch/drawing_witch_all", 43, None),
    ("增益星光", "battle/effect/skill_unique/vesta_caster/vesta_caster_all", 60, None),
]


def load(path, rules):
    d = path.rsplit("/", 1)[0]; nm = d.split("/")[-1]
    atlas, _ = wfio.load_amf(f"{d}/{nm}.atlas")
    png, _ = wfio.load_png(f"{d}/{nm}.png")
    if rules:
        png = wg_color.transform(rules)(png)
    tex = fxlib.frame_textures(png, atlas)
    parts, _ = wfio.load_amf(path + ".parts")
    base = path.rsplit("/", 1)[1]
    return parts, tex, ROWS[base]["frames"]


def draw(canvas, parts, tex, frame):
    view = (-FW / 2, -FH / 2, FW / 2, FH / 2)
    minx, miny = view[0], view[1]
    H, W = canvas.shape[:2]
    for comp, al, bl, ct, name in fxlib.placements(parts, frame):
        t = tex.get(name)
        if t is None:
            continue
        img, fw, fh = t
        a, b, c, d, x, y = comp
        F = (a * SC, c * SC, (x - minx) * SC, b * SC, d * SC, (y - miny) * SC)
        det = F[0] * F[4] - F[1] * F[3]
        if abs(det) < 1e-12:
            continue
        ia, ib = F[4] / det, -F[1] / det
        ic, idd = -F[3] / det, F[0] / det
        itx = -(ia * F[2] + ib * F[5]); ity = -(ic * F[2] + idd * F[5])
        L = np.asarray(img.transform((W, H), Image.AFFINE, (ia, ib, itx, ic, idd, ity), resample=Image.BILINEAR), np.float32)
        if not L[..., 3].any():
            continue
        L = fxlib._apply_ct(L, ct)
        sa = (L[..., 3:4] / 255.0) * al
        canvas[...] = L[..., :3] * sa + canvas * (1 - sa)


def main(out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    tr = [(n, *load(p, r), s) for n, p, s, r in TRACKS]
    W, H = int(FW * SC), int(FH * SC)
    end = max(s + nf for _, _, _, nf, s in tr)
    frames = []
    for f in range(0, end, 2):
        cv = np.zeros((H, W, 3), np.float32); cv[...] = (24, 30, 44)
        for n, parts, tex, nf, s in tr:
            if s <= f < s + nf:
                draw(cv, parts, tex, f - s)
        im = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8))
        frames.append(im)
    frames[0].save(out / "技能演出预览.gif", save_all=True, append_images=frames[1:], duration=33, loop=0)
    pick = [int(i * (len(frames) - 1) / 9) for i in range(10)]
    sheet = Image.new("RGB", (W * 5, (H + 24) * 2), (255, 255, 255)); dr = ImageDraw.Draw(sheet)
    fnt = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    for i, k in enumerate(pick):
        X, Y = (i % 5) * W, (i // 5) * (H + 24)
        sheet.paste(frames[k], (X, Y + 24)); dr.text((X + 4, Y + 2), f"第{k * 2}帧", fill="black", font=fnt)
    sheet.save(out / "技能演出-分帧.png")
    print(len(frames), end)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"D:/WF/out/水杰拉德-20261018/art/skill_fx")
