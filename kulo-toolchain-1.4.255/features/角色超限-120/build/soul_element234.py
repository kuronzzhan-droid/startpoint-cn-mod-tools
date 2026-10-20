# -*- coding: utf-8 -*-
"""1.4.233 → 1.4.234：悖论武器 / 诅咒武器魂珠的可装备属性（作者 1018「悖论武器的魂珠只能火用，应该是全部通用的」）。

根因：wf_paradox_weapon / wf_cursed_weapons 的魂珠道具行（item 表，c6=11 能力魂珠）用 8000101（深渊·灰烬巨剑魂珠，火）
做模板，c12「可装备属性」原样留了 "0"（火），从没按武器设计改。客户端 GeneralAbilitySoulLogic.get_elements 读 c12
（30=自动按能力推导；否则按列表），魂珠只对列表里的属性可用。服务端不校验魂珠属性（equipment_element.json 只给任务统计用）。
修：
- PARADOX 5920001 魂珠 c12 → 官方全属性写法 "0,3,2,1,4,5"。
- 诅咒武器 5910101–5910129 魂珠 c12 按服务端 equipment_element.json（= 生成器 Weapon.element_code()）：-1 → 全属性，单属性 → 该属性。
- 这些魂珠 c5 说明是模板带来的日文「アビリティソウル」，改成官方中文「能力魂珠」。
数值、能力行一律不动。用法：python soul_element234.py [--write]
"""
import hashlib, json, os, sys, zipfile
from pathlib import Path

OUT = Path(r"D:/WF/out/角色超限-120")
CHAIN = os.environ.get("WF_CHAIN_FILE", os.path.join(os.environ["TEMP"], "claude", "chain233.txt"))
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = open(CHAIN).read()
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *  # noqa
import wf_mod_tool as M  # noqa
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W  # noqa

FROM, TO = "1.4.233", "1.4.234"
NAME = f"pinball-{FROM}-{TO}-1-paradox-cursed-soul-elements-local.zip"
NL = chr(10)
ITEM = "master/item/item.orderedmap"
ALL = "0,3,2,1,4,5"                        # 官方全属性魂珠写法（131 件）
ORDER = [int(x) for x in ALL.split(",")]
JA, ZH = "アビリティソウル", "能力魂珠"

# 可装备属性以服务端 equipment_element.json 为准（同一份设计：单属性武器=该属性码，通用/多属性门控=-1）
ELEM = json.load(open(os.environ.get("WF_EQUIPMENT_ELEMENT", os.path.join(os.environ["TEMP"], "claude", "box",
                                                                           "equipment_element.json")), encoding="utf-8"))
targets = {}
for w in W.weapons():
    code = ELEM[w.id]
    assert code == w.element_code(), (w.id, code, w.element_code())
    targets[w.id] = ALL if code == -1 else str(code)
assert ELEM["5920001"] == -1
targets["5920001"] = ALL
assert len(targets) == 30, len(targets)

it = load(ITEM)
edits, log = {}, []
for k, want in sorted(targets.items()):
    r = row(it[k])
    assert r[6] == "11" and r[2].endswith("魂珠") and r[0].startswith(("mod_paradox_", "mod_cursed_")), (k, r[:7])
    assert r[12] == "0", (k, r[12])                       # 全部是模板遗留的「火」
    r2 = list(r)
    r2[12] = want
    if r2[5] == JA:
        r2[5] = ZH
    assert [i for i in range(len(r)) if r[i] != r2[i]] in ([12], [5, 12], [5], []), k
    if r2 == r:
        continue
    edits[k] = join(r2) + (NL if it[k].endswith(NL) else "")
    log.append(f"{k} {r[2]} c12 0→{want}" + ("，c5 日文→能力魂珠" if r[5] == JA else ""))


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    changed = [keys0[i] for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert sorted(changed) == sorted(edits), (lp, changed)
    parsed = q.parse_node(out)
    for k, node in edits.items():
        assert parsed[k] == node, (lp, k)
    return out


files = {ITEM: raw_replace(ITEM, edits)}
print(NL.join(log))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for lp in sorted(files):
            zf.writestr(member(lp), files[lp])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "applies_on": FROM, "version": TO, "logical_paths": {member(lp): lp for lp in files},
             "member_sha256": {member(lp): hashlib.sha256(files[lp]).hexdigest() for lp in files}, "log": log}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL,
                                                             "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
