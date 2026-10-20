# -*- coding: utf-8 -*-
"""测试服专用 GM 武器 5990006（GM·不屈连击），叠加在 kulo 1.4.192 视图上；全新键，不改任何已有键。

作者原文：「一把新的gm武器赋予全队，状态毅力100%*999次，每达成10连击，连击数＋50，持有者为主位 时:
连击≥7777 → 自身 Set连击 0 连击数达到35时回复全队20%充能」

实现（全部 ability_soul 行，魂珠与装备共用；觉醒 0 起满额；无 DSL）：
  #0 开局 → 瞬发 468 ConditionGuts 目标全队 strength=1 number=999，永续、不可驱散（官方 300001/5085000 同形，c64=1 同 8000113）
  #1 触发 18 复活(来源=全队任一) → 468 目标=触发者 ×999（复活后状态被清，补挂；官方 5050017 同款 18/5/目标7）
  #2 触发 12 Combo 阈值 10 冷却 1 帧 → 226 AddCombo +50（ThresholdComboListener：每跨过一个 10 的倍数计一次）
     冷却 1 帧：+50 自己会再跨 5 个 10 的倍数 ⇒ 无冷却时同帧 5^n 级联（1→5→25→125→625 次/帧，靠 9999 上限才停，
     并且与 #3 的同帧先后不定，可能每帧 0↔9999 振荡）。冷却把级联压成每帧最多 +50（countHandler 冷却时多计数截成 1）。
  #3 前置 202 OwnerIsMain + 触发 12 Combo 阈值 7777 → 390 SetCombo 0（官方 1410151 / 1499963 同形：12+390）
  #4 触发 70 ComboDisplay 阈值 35 → 211 全队技能槽 +20%（oncePerFlip：连击从 <35 升到 ≥35 时触发一次，降回 35 以下后重新武装）

用法：WF_TIP=192 python gm_weapon6.py
产物：../patch/pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip + .integrity.json；
      ../patch/gm-weapon6-members/（members 原样落盘 + members.json，供与语音包合并同版本）；
      ../server19/*.json（全量副本，只追加 5990006）
"""
import copy
import hashlib
import json
import os
import shutil
import sys

os.environ.setdefault("WF_TIP", "192")
assert os.environ["WF_TIP"] == "192", "必须在 1.4.192 视图上构建"
from live149 import *  # noqa
import base149
import wf_cursed_weapons_r4 as W
from stage_all import csv_text, detect_style, dump_like
import zipfile

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip"
APPLIES_ON, VERSION = "1.4.192", "1.4.193"
MEMBERS_DIR = OUT / "patch" / "gm-weapon6-members"
TAG = "【测试服专用】"
DESC0 = "测试服专用GM武器，正式服不得投放。"
T_SELF, T_PARTY, T_TRIGGER = W.T_SELF, W.T_PARTY, W.T_TRIGGER

WID, WNAME, ICON_FROM = "5990006", "GM·不屈连击", "5040009"   # 图标/状态模板：埃俄罗斯之弓
TAIL = "全队毅力999次。每10连击+50。主位≥7777清零。35连击全队槽+20%"

OWNER_IS_MAIN = ("202", {})
GUTS = 999


def soul_effects() -> list:
    def guts(target: str) -> tuple:
        # 目标 7（触发者）的角色组列官方留空（5050017/5900913），目标 5 写 (None)（8000113 在役）
        groups = "" if target == T_TRIGGER else "(None)"
        return ("468", {"target": target, "target.character_groups": groups, "strength": W.times(1),
                        "number": W.times(GUTS), "cancelable": "1"})
    return [
        W.Eff("0", guts(T_PARTY)),
        W.Eff("0", guts(T_TRIGGER), trig=W.trig(W.IT_REVIVAL, trigger_puller=W.P_ONE_OF_PARTY)),
        W.Eff("0", ("226", {"strength": W.times(50)}), trig=W.trig("12", threshold=W.times(10), cooltime="1")),
        W.Eff("0", ("390", {"strength": "0"}), trig=W.trig("12", threshold=W.times(7777)), pre=(OWNER_IS_MAIN,)),
        W.Eff("0", W.stat("211", T_PARTY, 20), trig=W.trig("70", threshold=W.times(35))),
    ]


def main() -> int:
    print("view zips 191→192:", [z.name for z in base149._ZIPS if "-1.4.191-1.4.192-" in z.name])
    assert any("-1.4.191-1.4.192-" in z.name for z in base149._ZIPS), "视图未含 1.4.192"
    assert not any("-1.4.192-1.4.193-" in z.name for z in base149._ZIPS)
    problems: list[str] = []
    eq_t = flat(W.EQUIPMENT)["8000101"][0]
    item_t = flat(W.ITEM)["8000101"][0]
    EQ = flat(W.EQUIPMENT)
    status = nested(W.EQUIPMENT_STATUS)
    lookup = json.loads((ASSETS / "equipment_lookup.json").read_text("utf-8"))
    category = lookup[ICON_FROM]["category"]
    new = {W.EQUIPMENT: {}, W.ITEM: {}, W.SOUL: {}}
    full = TAG + WNAME
    desc = DESC0 + TAIL
    if len(desc) > 57 or "," in desc:
        problems.append(f"说明 {len(desc)} 字")
    icon = EQ[ICON_FROM][0][6]
    r = list(eq_t)
    assert r[2] == "0" and r[8] == "5" and r[11] == "5"
    r[0], r[1], r[6], r[7], r[9], r[10] = f"mod_gm_{WID}", full, icon, desc, "true", WID
    new[W.EQUIPMENT][WID] = [r]
    r = list(item_t)
    r[0], r[1], r[2], r[3], r[12] = f"mod_gm_{WID}", WID, f"{full}魂珠", icon, "0,3,2,1,4,5"
    new[W.ITEM][WID] = [r]
    new[W.SOUL][WID] = [W.build_row(W.SOUL_T, i, e) for i, e in enumerate(soul_effects())]
    new_status = {WID: copy.deepcopy(status[ICON_FROM])}
    for i, row_ in enumerate(new[W.SOUL][WID]):
        problems += [f"#{i}: {p}" for p in W.L.client_legality_problems(W.SOUL_T, row_)]
        problems += [f"#{i}: capability {c}" for c in W.row_capabilities(W.SOUL_T, row_)
                     if c not in W.BASE_CLIENT_CAPABILITIES]
    assert not problems, problems
    # ------------------------------------------------ 表
    files = {}
    for lp, keys in new.items():
        node = load(lp)
        assert not set(node) & set(keys), lp
        before = dict(node)
        for k, v in keys.items():
            node[k] = csv_text(v)
        data = q.build_node(node)
        back = q.parse_node(data)
        assert back == node and all(back[k] == v for k, v in before.items())
        assert list(back)[-len(keys):] == list(keys)
        files[lp] = data
    node = load(W.EQUIPMENT_STATUS)
    before = copy.deepcopy(node)
    assert WID not in node
    node.update(new_status)
    data = q.build_node(node)
    back = q.parse_node(data)
    assert back == node and all(back[k] == v for k, v in before.items())
    files[W.EQUIPMENT_STATUS] = data
    members = {member(lp): d for lp, d in files.items()}
    logical = {member(lp): lp for lp in files}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(members):
            z.writestr(n, members[n])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {n: hashlib.sha256(members[n]).hexdigest() for n in sorted(members)},
             "logical_paths": {n: logical[n] for n in sorted(members)}, "applies_on": APPLIES_ON, "version": VERSION}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    # members 落盘（可复用：与语音包合并成同一版本时直接读这个目录）
    if MEMBERS_DIR.exists():
        shutil.rmtree(MEMBERS_DIR)
    for n, d in members.items():
        p = MEMBERS_DIR / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(d)
    (MEMBERS_DIR / "members.json").write_text(json.dumps(
        {"applies_on": APPLIES_ON, "version": VERSION, "weapon_id": WID,
         "members": {n: {"logical_path": logical[n], "sha256": hashlib.sha256(members[n]).hexdigest(),
                         "size": len(members[n])} for n in sorted(members)}},
        ensure_ascii=False, indent=2) + "\n", "utf-8")
    # ------------------------------------------------ 服务端
    ids = [int(WID)]
    delta = {
        "equipment_ids.json": ids, "item_ids.json": ids,
        "equipment_lookup.json": {WID: {"name": full, "rarity": "5", "category": category}},
        "equipment_max_level.json": {WID: 5},
        "equipment_element.json": {WID: -1},
        "item_sale.json": {WID: {"category": 5, "sale_price": 500, "sellable": True}},
        "equipment_dissolve.json": {WID: {"ability_soul_id": int(WID), "obtain_source": 1,
                                          "generate_ability_soul": True, "max_level": 5}},
        "item_lookup_cnmod.json": {WID: f"{full}魂珠"},
    }
    s19 = OUT / "server19"
    if s19.exists():
        shutil.rmtree(s19)
    s19.mkdir()
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
        (s19 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "logical_paths")}, ensure_ascii=False, indent=1))
    print("desc", len(desc), desc)
    for i, row_ in enumerate(new[W.SOUL][WID]):
        print(f"soul#{i}", "|".join(row_))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
