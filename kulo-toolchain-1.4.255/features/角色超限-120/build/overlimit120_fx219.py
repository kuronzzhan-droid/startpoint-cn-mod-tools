# -*- coding: utf-8 -*-
"""1.4.218 → 1.4.219：炎龙王觉醒技能特效回到原版亮度，只去掉造成闪烁的黑底（作者 1016）。

1.4.214 把火柱/开场光柱/爆炎整体降亮，作者反馈「还是原来好看」，怀疑闪烁来自黑色背景。
排查：官方 fire_dragon 火柱族里有一帧纯黑半透明阴影（fire_dragon/f、fire_dragon_end/j，30×29，RGB=0、alpha≈99），
原版瓦格纳只放 1 道看不出来；觉醒技能一次放 13 道，13 层黑影叠在一起整片压黑，
再被亮黄火柱/星芒顶亮，就成了一明一暗的闪烁。
做法：ol_beam 克隆族改回原版贴图，只把这两帧黑影的 alpha ×BLACK_ALPHA；
开场光柱、前方爆炎改回官方原件（不再指 ol_zenith）。形状、时长、判定、伤害不变。
用法：WF_BASE_ZIPS="a.zip;b.zip" python overlimit120_fx219.py [--write]
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
       str(OUT / "patch/pinball-1.4.210-1.4.211-1-wagner-overlimit-tweak-local.zip"),
       r"D:/WF/out/十项收尾-20261015/patch/pinball-1.4.211-1.4.212-1-ten-items-local.zip",
       r"D:/WF/out/凉月修复-20261016/handoff-213/pinball-1.4.212-1.4.213-1-liangyue-ability-columns-local.zip",
       str(OUT / "patch/pinball-1.4.213-1.4.214-1-wagner-overlimit-pillar-dim-local.zip"),
       r"D:/WF/out/平衡1016/patch/pinball-1.4.214-1.4.215-1-balance-1016-local.zip"] \
    + sorted(glob.glob(r"D:/WF/out/碧-1.4.216/patch/pinball-1.4.215-1.4.216-*-vyrn-character-local.zip")) \
    + [r"D:/WF/out/碧-1.4.216/patch/pinball-1.4.216-1.4.217-1-vyrn-illustration-sheet-local.zip",
       r"D:/WF/out/碧-1.4.216/patch/pinball-1.4.217-1.4.218-1-illustration-sheet-fix6-local.zip"] \
    + [x for x in os.environ.get("WF_BASE_ZIPS", "").split(";") if x]
os.environ["WF_TIP"] = "205"
os.environ["WF_EXTRA_ZIPS"] = ";".join(EXTRA)
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
sys.path.insert(0, str(OUT / "build"))
import rose_pf_fx as R  # noqa
import wf_dsl  # noqa
from wf_character_revision import encode_tree  # noqa

FROM, TO = os.environ.get("WF_FX_FROM", "1.4.218"), os.environ.get("WF_FX_TO", "1.4.219")
NAME = f"pinball-{FROM}-{TO}-1-wagner-overlimit-fx-restore-local.zip"
SRC = "battle/effect/skill_unique/fire_dragon"
DST = "battle/effect/skill_unique/fire_dragon_zenith/ol_beam"
RENAME = {"fire_dragon": "zenith_ol_beam", "fire_dragon_end": "zenith_ol_beam_end"}
ZEN = "battle/effect/skill_unique/fire_dragon_zenith"
ZDST = f"{ZEN}/ol_zenith"
P3 = "battle/action/skill/action/rare5/fire_dragon_zenith$fire_dragon_zenith_3"
BLACK_FRAMES = {f"{SRC}/.gen/fire_dragon/f", f"{SRC}/.gen/fire_dragon_end/j"}
BLACK_ALPHA = float(os.environ.get("WF_BLACK_ALPHA", "0.08"))   # 13 道叠起来 ≈ 原版 1 道的黑影

atlas = R.amf(read_raw(f"{SRC}/fire_dragon.atlas.amf3.deflate")[0])
rects = []
for e in atlas:
    if e["n"] in BLACK_FRAMES:
        rects.append((e["x"], e["y"], e["w"], e["h"]))
assert len(rects) == 2, rects


def fade_black(img):
    a = np.asarray(img).copy()
    for x, y, w, h in rects:
        c = a[y:y + h, x:x + w]
        m = c[..., 3] > 0
        assert c[..., :3][m].max() < 16, "黑影帧应为纯黑"
        c[..., 3] = (c[..., 3].astype(np.float32) * BLACK_ALPHA + .5).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


files, _ = R.clone_family(read_raw, SRC, "fire_dragon", DST, list(RENAME), RENAME, fade_black)
# 214 已上链的 ol_beam 帧名/parts/timeline 不变，本次只换贴图
for lp in list(files):
    if not lp.endswith(".png"):
        assert read_raw(lp)[0] == files[lp], lp
        del files[lp]
assert list(files) == [f"{DST}/ol_beam.png"], list(files)

BACK = {f"{ZDST}/{n.replace('fire_dragon_zenith_', 'zenith_ol_')}": f"{ZEN}/{n}" for n in
        ("fire_dragon_zenith_dot_part1", "fire_dragon_zenith_dot_part2",
         "fire_dragon_zenith_explosion_back", "fire_dragon_zenith_explosion_front")}
t = dsl_tree(P3)
n = {}


def walk(x):
    if isinstance(x, list):
        if x[:1] == ["SpecifyEffectDirectly"] and len(x) == 2:
            if x[1] in BACK:
                n[x[1]] = n.get(x[1], 0) + 1
                x[1] = BACK[x[1]]
            elif x[1].startswith(DST):
                n["beam"] = n.get("beam", 0) + 1
        for y in x:
            walk(y)


walk(t)
assert n == {**{k: 1 for k in BACK}, "beam": 26}, n
enc = encode_tree(t)
assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == t
files[wf_dsl.dsl_logical(P3)] = enc
LOG = [f"{DST}/ol_beam.png 回到原版贴图，只把火柱黑影两帧（fire_dragon/f、fire_dragon_end/j）alpha×{BLACK_ALPHA}",
       f"{P3}：开场光柱两段、前方爆炎两件改回官方 {ZEN} 原件；13 道火柱仍指 ol_beam；判定与伤害不变"]
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
