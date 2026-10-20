# -*- coding: utf-8 -*-
"""水杰拉德原创像素小人装包：pixel/orig/out 的两套图集（pixelart / special）→ 包内 character/<code>/pixelart/。
pixelart 时间轴沿用母本（官方标准区间 1-428），special 时间轴用自制 368 帧版（special_land 1-287 / special_pose 288-368）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import wg_env
import wf_seasonal7_common as C

sys.path.insert(0, str(wg_env.MODTOOLS))
from wf_nephtim_fever_pixels import _decode, _encode  # noqa: E402

SRC = wg_env.OUT / "pixel" / "orig" / "out"


def build(pack):
    code = pack.spec.code
    base = f"character/{code}/pixelart/"
    done = {}
    tl = _decode(pack.pkg_path("common", base + "pixelart.timeline.amf3.deflate").read_bytes())
    seq = {s["name"]: (s["begin"], s["end"]) for s in tl["sequences"]}
    need = {"neutral": (1, 2), "walk_back": (3, 26), "walk_front": (27, 50), "skill_ready": (51, 110),
            "kachidoki": (111, 158), "into_coffin": (159, 200), "ghost_raise": (201, 225),
            "ghost_neutral": (226, 386), "revive": (387, 428)}
    assert all(seq.get(k) == v for k, v in need.items()), seq
    for fam, sheet_name, atlas_name, frame_name in (
            ("pixelart", "sprite_sheet.png", "sprite_sheet.atlas.amf3.deflate", "pixelart.frame.amf3.deflate"),
            ("special", "special_sprite_sheet.png", "special_sprite_sheet.atlas.amf3.deflate", "special.frame.amf3.deflate")):
        atlas = json.loads((SRC / f"{fam}_atlas.json").read_text(encoding="utf-8"))
        assert all(e["n"].startswith(base) for e in atlas), atlas[0]["n"]
        png = C.png_store_bytes(C.png_open((SRC / f"{fam}_sheet.png").read_bytes()))
        pack.write_asset("common", base + sheet_name, png, owner="pixel")
        pack.write_asset("common", base + atlas_name, _encode(atlas), owner="pixel")
        frame = {"name": f"{base}{fam}", "x": -128, "y": -128, "scale": 6, "smoothing": False}
        pack.write_asset("common", base + frame_name, _encode(frame), owner="pixel")
        done[fam] = len(atlas)
    st = json.loads((SRC / "special_timeline.json").read_text(encoding="utf-8"))
    pack.write_asset("common", base + "special.timeline.amf3.deflate", _encode(st), owner="pixel")
    # pixelart 时间轴：母本标准区间不变，去掉母本自带音效（她的 SE 不属于水杰拉德）
    tl = dict(tl, sounds=[])
    pack.write_asset("common", base + "pixelart.timeline.amf3.deflate", _encode(tl), owner="pixel")
    return {"frames": done, "special": st["sequences"]}
