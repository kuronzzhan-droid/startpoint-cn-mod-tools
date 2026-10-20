# -*- coding: utf-8 -*-
"""像素小人换色（保亮度，只改色相）+ ★3 母本补 special 槽（领取演出必需）。"""
from __future__ import annotations

import copy
import sys

import hw_color
import hw_env
import wf_seasonal7_common as C

sys.path.insert(0, str(hw_env.MODTOOLS))
from wf_nephtim_fever_pixels import _decode, _encode  # noqa: E402

RULES = {
    # 露迪：青色电光→万圣金橙，橙色点缀→紫
    "ludi": [{"from": [170, 215], "to": 38, "sat": 1.05}, {"from": [10, 40], "to": 285}],
    # 莫弥亚：青绿点缀→猎魔深红
    "momiya": [{"from": [95, 185], "to": 352}],
    # 塞里奥尔：绿叶→酒红（结晶青、粉发不动）
    "seriol": [{"from": [90, 165], "to": 348}],
    # 瑞西塔尔：蓝袍→南瓜橙，红宝石→藤绿
    "recital": [{"from": [195, 255], "to": 27, "sat": 1.05}, {"from": [340, 15], "to": 105}],
}


def recolor(pack):
    key, code = pack.spec.key, pack.spec.code
    tf = hw_color.transform(RULES[key])
    done = []
    for name in ("sprite_sheet.png", "special_sprite_sheet.png"):
        lg = f"character/{code}/pixelart/{name}"
        p = pack.pkg_path("common", lg)
        if not p.is_file():
            continue
        src_lg = f"character/{pack.spec.template_code}/pixelart/{name}"
        raw = pack.live_read(src_lg)                     # 永远从母本原图换色（可重跑）
        pack.write_asset("common", lg, C.png_store_bytes(tf(C.png_open(raw))), owner="pixel")
        done.append(lg)
    return done


def ensure_special(pack):
    """★3 母本（lich）没有 special 四件：用普通像素复制一套，special_land=skill_ready、special_pose=kachidoki。"""
    code = pack.spec.code
    base = f"character/{code}/pixelart/"
    if pack.pkg_path("common", base + "special.timeline.amf3.deflate").is_file():
        return None
    atlas = _decode(pack.pkg_path("common", base + "sprite_sheet.atlas.amf3.deflate").read_bytes())
    frame = _decode(pack.pkg_path("common", base + "pixelart.frame.amf3.deflate").read_bytes())
    tl = _decode(pack.pkg_path("common", base + "pixelart.timeline.amf3.deflate").read_bytes())
    seq = {s["name"]: s for s in tl["sequences"]}
    end = seq["kachidoki"]["end"]
    pre_old = f"character/{code}/pixelart/pixelart"
    sa = []
    for it in copy.deepcopy(atlas):
        num = int(it["n"][len(pre_old):])
        if num <= end:
            it["n"] = f"character/{code}/pixelart/special{num:04d}"
            sa.append(it)
    nums = sorted(int(it["n"][-4:]) for it in sa)
    if nums[-1] != end:      # 末帧号必须等于末序列 end（缺号=沿用上一帧，补一条别名）
        last = next(it for it in sa if int(it["n"][-4:]) == nums[-1])
        sa.append(dict(copy.deepcopy(last), n=f"character/{code}/pixelart/special{end:04d}"))
    sf = dict(frame, name=f"character/{code}/pixelart/special")
    st = copy.deepcopy(tl)
    st["sequences"] = [dict(name="special_land", kind="pass", begin=seq["skill_ready"]["begin"], end=seq["skill_ready"]["end"]),
                       dict(name="special_pose", kind="once", begin=seq["kachidoki"]["begin"], end=seq["kachidoki"]["end"])]
    st["sounds"] = []
    sheet = pack.pkg_path("common", base + "sprite_sheet.png").read_bytes()
    for name, data in (("special_sprite_sheet.atlas.amf3.deflate", _encode(sa)),
                       ("special.frame.amf3.deflate", _encode(sf)),
                       ("special.timeline.amf3.deflate", _encode(st)),
                       ("special_sprite_sheet.png", sheet)):
        pack.write_asset("common", base + name, data, owner="pixel")
    return {"special_land": st["sequences"][0], "special_pose": st["sequences"][1]}


def build(pack):
    return {"recolor": recolor(pack), "special": ensure_special(pack)}
