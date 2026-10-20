# -*- coding: utf-8 -*-
"""水杰拉德附加件：超限 Lv120 属性行、「任意属性」圆标（台座图集追加子纹理 + icon_tag 行）。

超限（作者 10-18「杰拉德也加入超限吧」，照炎龙王 111183 / 护花使龙 141099）：
  客户端只需属性表补 120 级（APK O1 白名单 = ★5 且属性表最高键 ≥120）；倍率按两位先例 Lv100→120 ≈×1.11。
  服务端 assets/character_overlimit.json 的 characters 追加 129989（盒子按条目合并，见 wg_pack 的交接说明）。
  觉醒形态不做（没有 level_missions 行）。
圆标：tools 在 art/icon_any/tools/build_atlas.py（基线 = v35e APK 台座图集，原条目不动只加高画布）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import wg_env
import wf_mod_tool as core

STATUS = "master/character/character_status.orderedmap"
ICON_TAG = "master/string/icon_tag.orderedmap"
LV120 = "3845,768"                  # Lv100 3465/693 × 1.11
ICON_ID = "any_element"
ICON_PATH = "character_pedestal/common/wfx_round_ability_any"
# 同图集的主位标副本：同一行里 main（scene/general）+ any（台座）两张纹理会让第二个图标画成花纹（单纹理合批）
MAIN_ID = "wfx_main"
MAIN_PATH = "character_pedestal/common/wfx_round_main"
PED = wg_env.OUT / "art" / "icon_any" / "pedestal_out"


def overlimit(pack):
    cid = pack.spec.cid_s
    raw = pack.pkg_path("common", STATUS).read_bytes()
    om = core.read_orderedmap_raw_rows_from_bytes(raw, STATUS)
    blob = dict(zip(om.keys, om.rows))[cid]
    t = core.read_orderedmap_file_from_bytes(blob)
    assert sorted(t, key=int)[-1] in ("100", "120"), t
    t["120"] = LV120
    new = core.build_orderedmap(core.OrderedMap(cid, list(t), [v.encode() for v in t.values()], Path("<m>")))
    assert core.read_orderedmap_file_from_bytes(new) == t
    pack.write_raw_outer(STATUS, {cid: new})
    return t


def any_icon(pack):
    rep = json.loads((PED / "report.json").read_text(encoding="utf-8"))
    assert [e["n"] for e in rep["added"]] == [ICON_PATH, MAIN_PATH], rep
    pack.write_asset("android", "character_pedestal/sprite_sheet.png",
                     (PED / "sprite_sheet.png").read_bytes(), owner="icon")
    pack.write_asset("android", "character_pedestal/sprite_sheet.atlas.amf3.deflate",
                     (PED / "sprite_sheet.atlas.amf3.deflate").read_bytes(), owner="icon")
    pack.write_flat(ICON_TAG, {ICON_ID: [[ICON_PATH, "0xFFFFFF", "1"]], MAIN_ID: [[MAIN_PATH, "0xFFFFFF", "1"]]})
    return {"icon_tag": [ICON_ID, MAIN_ID], "atlas": rep["new_size"], "entries": rep["entries"]}


def profile(pack):
    """作者 10-19「种族性别声优也写的不对」：母本拉绮夏的 Human,Element / Female / 井上麻里奈 → 照光杰拉德 149999。"""
    import wf_seasonal7_common as C7
    cid = pack.spec.cid_s
    CH, TX = "master/character/character.orderedmap", "master/character/character_text.orderedmap"
    row = C7.csv_split(pack.pkg_flat(CH)[cid])[0]
    row[4], row[6], row[7] = "Human,Beast", "0", "Male"
    pack.write_flat(CH, {cid: [row]})
    tx = C7.csv_split(pack.pkg_flat(TX)[cid])[0]
    tx[11] = "AI声线"
    pack.write_flat(TX, {cid: [tx]})
    pack.sync_character_mirrors()
    return {"race": row[4], "c6": row[6], "gender": row[7], "cv": tx[11]}


def build(pack):
    return {"overlimit": overlimit(pack), "icon": any_icon(pack), "profile": profile(pack)}


if __name__ == "__main__":
    import wg_common as HC
    print(json.dumps(build(HC.pack_for(*(sys.argv[1:] or ["aqua"]))), ensure_ascii=False))
