# -*- coding: utf-8 -*-
"""1.4.213 → 1.4.214：炎龙王觉醒技能（fire_dragon_zenith_3）火柱降亮（测试反馈「像闪光弹」）。

觉醒技能一次放 13 道官方 fire_dragon 火柱（竖直 1 + 两侧 12），亮黄/白芯叠在一起整屏发白。
做法：把官方 fire_dragon 族（火柱 + 收尾）整族克隆到 skill_unique/fire_dragon_zenith/ol_beam，
贴图保留原色相，只把白芯/纯黄压成橙黄并整体降明度与 alpha；parts/timeline 原样，形状、时长不变。
只改 _3 里 ShowEffect 的两个路径；判定、伤害、倍率一个字节不动。官方 fire_dragon（未觉醒/其他角色）不受影响。
用法：WF_BASE_ZIPS="a.zip;b.zip" python overlimit120_fx214.py [--write]
"""
import glob, hashlib, json, os, sys, zipfile, zlib
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(r"D:/WF/out/角色超限-120")
EXTRA = [r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/patch/pinball-1.4.205-1.4.206-1-rolf-moon-skill-rework-local.zip",
         str(OUT / "patch/pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip"),
         str(OUT / "patch/pinball-1.4.207-1.4.208-1-overlimit120-rose-dragon-local.zip")] \
    + sorted(glob.glob(r"D:/WF/out/赛瑞斯重做-20261015/patch/pinball-1.4.208-1.4.209-*-seris-rework-local.zip")) \
    + [str(OUT / "patch/pinball-1.4.209-1.4.210-1-overlimit-crystal-icon-fix-local.zip"),
       str(OUT / "patch/pinball-1.4.210-1.4.211-1-wagner-overlimit-tweak-local.zip")] \
    + [x for x in os.environ.get("WF_BASE_ZIPS", "").split(";") if x]
os.environ["WF_TIP"] = "205"
os.environ["WF_EXTRA_ZIPS"] = ";".join(EXTRA)
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
sys.path.insert(0, str(OUT / "build"))
import rose_pf_fx as R  # noqa
import wf_dsl  # noqa
from wf_character_revision import encode_tree  # noqa

FROM, TO = os.environ.get("WF_FX_FROM", "1.4.213"), os.environ.get("WF_FX_TO", "1.4.214")
NAME = f"pinball-{FROM}-{TO}-1-wagner-overlimit-pillar-dim-local.zip"
SRC = "battle/effect/skill_unique/fire_dragon"
DST = "battle/effect/skill_unique/fire_dragon_zenith/ol_beam"
RENAME = {"fire_dragon": "zenith_ol_beam", "fire_dragon_end": "zenith_ol_beam_end"}
P3 = "battle/action/skill/action/rare5/fire_dragon_zenith$fire_dragon_zenith_3"
SAT_MIN, YELLOW_SHIFT, WHITE_HUE, VAL, ALPHA = 0.75, 14, 36, 0.85, 0.7


def dim(img):
    """保留原色相（红/橙/品红都在），只压「白芯/纯黄」：亮部饱和度抬到 ≥SAT_MIN、
    纯黄往橙偏 YELLOW_SHIFT°、亮部明度 ×VAL、亮部 alpha ×ALPHA（按亮度渐变，暗部不动）。"""
    import colorsys
    a = np.asarray(img).astype(np.float32) / 255
    h, s, v = np.vectorize(colorsys.rgb_to_hsv)(a[..., 0], a[..., 1], a[..., 2])
    hot = np.clip((v - 0.5) / 0.3, 0, 1)                      # 亮部权重
    h = np.where(s < 0.25, WHITE_HUE / 360, h)                # 白芯没有色相，先给它金橙色相
    s = np.maximum(s, SAT_MIN * hot)
    yel = (h > 35 / 360) & (h < 70 / 360)
    h = np.where(yel, h - YELLOW_SHIFT / 360 * hot, h)
    v = v * (1 - (1 - VAL) * hot)                             # 只压亮部，暗部/像素小人原样
    r, g, b = np.vectorize(colorsys.hsv_to_rgb)(h, s, v)
    a[..., 0], a[..., 1], a[..., 2] = r, g, b
    a[..., 3] *= 1 - (1 - ALPHA) * hot
    return Image.fromarray((a * 255 + .5).clip(0, 255).astype(np.uint8), "RGBA")


files, _ = R.clone_family(read_raw, SRC, "fire_dragon", DST, list(RENAME), RENAME, dim)
# 开场竖直光柱（ドット演出）与前方爆炎也是整屏白闪的来源：只给 _3 换成同法降亮的克隆族
ZEN = "battle/effect/skill_unique/fire_dragon_zenith"
ZDST = f"{ZEN}/ol_zenith"
ZRENAME = {n: n.replace("fire_dragon_zenith_", "zenith_ol_") for n in
           ("fire_dragon_zenith_dot_part1", "fire_dragon_zenith_dot_part2",
            "fire_dragon_zenith_explosion_back", "fire_dragon_zenith_explosion_front")}
f2, _ = R.clone_family(read_raw, ZEN, "fire_dragon_zenith", ZDST, list(ZRENAME), ZRENAME, dim)
files.update(f2)
REMAP = {f"{SRC}/{k}": f"{DST}/{v}" for k, v in RENAME.items()}
REMAP.update({f"{ZEN}/{k}": f"{ZDST}/{v}" for k, v in ZRENAME.items()})

t = dsl_tree(P3)
n = {}


def walk(x):
    if isinstance(x, list):
        if x[:1] == ["SpecifyEffectDirectly"] and len(x) == 2 and x[1] in REMAP:
            n[x[1]] = n.get(x[1], 0) + 1
            x[1] = REMAP[x[1]]
        for y in x:
            walk(y)


walk(t)
assert n == {f"{SRC}/fire_dragon": 13, f"{SRC}/fire_dragon_end": 13, f"{ZEN}/fire_dragon_zenith_dot_part1": 1,
             f"{ZEN}/fire_dragon_zenith_dot_part2": 1, f"{ZEN}/fire_dragon_zenith_explosion_back": 1,
             f"{ZEN}/fire_dragon_zenith_explosion_front": 1}, n
enc = encode_tree(t)
assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == t
files[wf_dsl.dsl_logical(P3)] = enc
LOG = [f"克隆 {SRC} 火柱+收尾 → {DST}、{ZEN} 开场光柱两段+前方爆炎两件 → {ZDST}"
       f"（亮部提饱和、白/纯黄偏金橙、明度×{VAL}、alpha×{ALPHA}，parts/timeline 原样）",
       f"{P3}：上述 30 处特效改指新族，判定与伤害不变；未觉醒 _2 与其他角色不受影响"]
print("\n".join(LOG), len(files))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lp in sorted(files):
            zf.writestr(member(lp), files[lp])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "applies_on": FROM, "version": TO, "logical_paths": {member(lp): lp for lp in files}, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n",
                                                             "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
