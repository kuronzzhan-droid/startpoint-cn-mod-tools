# -*- coding: utf-8 -*-
"""测试服专用 GM 武器 5 把（5990001–5990005），叠加在 kulo 1.4.152 视图上；全新键，不改任何已有键。

本体效果全部写在 ability_soul（魂珠与装备共用同一组行 ⇒ 魂珠数值与武器相同），觉醒 0 起满额，不需要强化。
用法：WF_TIP=152 python gm_weapons.py
产物：../patch/pinball-1.4.152-1.4.153-1-gm-weapons-local.zip + .integrity.json；../server4/*.json（全量副本，只追加键）
"""
import copy
import hashlib
import json
import os
import shutil
import sys
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "152")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text, detect_style, dump_like

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.152-1.4.153-1-gm-weapons-local.zip"
DSL_DIR = "battle/action/skill/action/ability_skill/gm_weapon"
TAG = "【测试服专用】"
DESC0 = "测试服专用GM武器，正式服不得投放。"
MAX = 99999
STAT_MAX = "99999,99999"
T_SELF, T_PARTY = W.T_SELF, W.T_PARTY

# (id, 名, 图标模板武器, lookup 类别, 说明尾巴)
SPECS = [
    ("5990001", "GM·全能", "5010073", "剑", "攻击/伤害/生命与全部独立乘区+99999%，HP/攻击99999。"),
    ("5990002", "GM·充能", "5090047", "饰品", "自身发动技能后全队技能槽+50%。"),
    ("5990003", "GM·槽上限", "5080032", "盾", "全队技能槽最大值+100%。"),
    ("5990004", "GM·直击", "5070044", "拳", "全队直接攻击判定+100次（共101段）。"),
    ("5990005", "GM·连击", "5020042", "斧", "每次弹射连击+9999。"),
]
HITS = f"{DSL_DIR}$direct_hits"


def soul_effects(wid: str) -> list:
    if wid == "5990001":
        return ([W.Eff("0", W.stat(k, None if k == "55" else T_SELF, MAX)) for k in ("32", "33", "34", "55", "388", "205")]
                + [W.Eff("0", W.stat(k, None if k == "696" else T_SELF, MAX)) for k in ("723", "693", "694", "695", "696")])
    if wid == "5990002":
        return [W.Eff("0", W.stat("211", T_PARTY, 50), trig=W.trig(W.IT_SKILL, trigger_puller=W.P_SELF))]
    if wid == "5990003":
        return [W.Eff("0", W.stat("245", T_PARTY, 100))]
    if wid == "5990004":
        return [W.Eff("0", W.invoke("gm_direct_hits", HITS)),
                W.Eff("0", W.invoke("gm_direct_hits", HITS), trig=W.trig(W.IT_REVIVAL, trigger_puller=W.P_ONE_OF_PARTY))]
    if wid == "5990005":
        return [W.Eff("0", ("226", {"strength": (W.times(9999), W.times(9999))}), trig=W.trig("6", threshold=W.times(1)))]
    raise KeyError(wid)


def main() -> int:
    problems: list[str] = []
    eq_t = flat(W.EQUIPMENT)["8000101"][0]
    item_t = flat(W.ITEM)["8000101"][0]
    EQ = flat(W.EQUIPMENT)
    status = nested(W.EQUIPMENT_STATUS)
    new = {W.EQUIPMENT: {}, W.ITEM: {}, W.SOUL: {}, W.CAS: {}}
    new_status = {}
    for wid, name, icon_from, cat, tail in SPECS:
        full = TAG + name
        desc = DESC0 + tail
        if len(desc) > 57 or "," in desc:
            problems.append(f"{wid} 说明 {len(desc)} 字")
        icon = EQ[icon_from][0][6]
        r = list(eq_t)
        assert r[2] == "0" and r[8] == "5" and r[11] == "5"
        r[0], r[1], r[6], r[7], r[9], r[10] = f"mod_gm_{wid}", full, icon, desc, "true", wid
        new[W.EQUIPMENT][wid] = [r]
        r = list(item_t)
        r[0], r[1], r[2], r[3], r[12] = f"mod_gm_{wid}", wid, f"{full}魂珠", icon, "0,3,2,1,4,5"
        new[W.ITEM][wid] = [r]
        new[W.SOUL][wid] = [W.build_row(W.SOUL_T, i, e) for i, e in enumerate(soul_effects(wid))]
        st = copy.deepcopy(status[icon_from])
        if wid == "5990001":
            st = {k: STAT_MAX for k in st}
        new_status[wid] = st
        for i, row_ in enumerate(new[W.SOUL][wid]):
            problems += [f"{wid}#{i}: {p}" for p in W.L.client_legality_problems(W.SOUL_T, row_)]
            problems += [f"{wid}#{i}: capability {c}" for c in W.row_capabilities(W.SOUL_T, row_)
                         if c not in W.PATCHED_CLIENT_CAPABILITIES]
    new[W.CAS]["gm_direct_hits"] = [["全队直接攻击判定额外+100次（共101段，伤害均分到各段）"]]
    tree = W.dsl_root(W.party(0, W.give(0, [["ACAdditionalDirectAttack", W.P(W.DSL_FOREVER), W.P(101), W.P(0.0), W.P(1)]],
                                        "gm_direct_hits", cancelable=False)))
    problems += W.dsl_signature_problems(tree) + W.colorless_hit_effect_problems(tree)
    assert not problems, problems
    # ------------------------------------------------ 表
    files = {}
    for lp, keys in new.items():
        node = load(lp)
        clash = set(node) & set(keys)
        assert not clash, (lp, clash)
        before = dict(node)
        for k, v in keys.items():
            node[k] = csv_text(v)
        data = q.build_node(node)
        back = q.parse_node(data)
        assert back == node and all(back[k] == v for k, v in before.items())
        files[lp] = data
    node = load(W.EQUIPMENT_STATUS)
    assert not set(node) & set(new_status)
    node.update(new_status)
    data = q.build_node(node)
    assert q.parse_node(data) == node
    files[W.EQUIPMENT_STATUS] = data
    lp = wf_dsl.dsl_logical(HITS)
    try:
        read_raw(lp)
        raise SystemExit(f"DSL 已存在 {lp}")
    except FileNotFoundError:
        files[lp] = encode_tree(tree)
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(members):
            z.writestr(n, members[n])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {n: hashlib.sha256(members[n]).hexdigest() for n in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.152", "version": "1.4.153"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    # ------------------------------------------------ 服务端
    ids = [int(s[0]) for s in SPECS]
    delta = {
        "equipment_ids.json": ids, "item_ids.json": ids,
        "equipment_lookup.json": {s[0]: {"name": TAG + s[1], "rarity": "5", "category": s[3]} for s in SPECS},
        "equipment_max_level.json": {s[0]: 5 for s in SPECS},
        "equipment_element.json": {s[0]: -1 for s in SPECS},
        "item_sale.json": {s[0]: {"category": 5, "sale_price": 500, "sellable": True} for s in SPECS},
        "equipment_dissolve.json": {s[0]: {"ability_soul_id": int(s[0]), "obtain_source": 1,
                                           "generate_ability_soul": True, "max_level": 5} for s in SPECS},
        "item_lookup_cnmod.json": {s[0]: f"{TAG}{s[1]}魂珠" for s in SPECS},
    }
    s4 = OUT / "server4"
    if s4.exists():
        shutil.rmtree(s4)
    s4.mkdir()
    for name, d in delta.items():
        raw = (ASSETS / name).read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8").replace("\r\n", "\n")
        value = json.loads(text)
        style = detect_style(text)
        assert dump_like(value, style) == text, name
        if isinstance(value, list):
            assert not set(value) & set(d), name
            value += d
        else:
            assert not set(value) & set(d), name
            value.update(d)
        out = dump_like(value, style)
        (s4 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "logical_paths")}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
