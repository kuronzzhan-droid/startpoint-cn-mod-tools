# -*- coding: utf-8 -*-
"""凯尔 139990「强化充能速度」：新固有 13999010（层数 n → 充能速度上限 1+n/50，需 APK charge-cap-unique-v1）。
能力6 追加一行：开局发动 629 → 自身 ACUnique(13999010, 50 层) = 上限 200%，常驻、不限队长。叠加在 1.4.169 上。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "170")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.169-1.4.170-1-kyle-charge-cap-local.zip"
AB_LP, CAS_LP, U_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap", "master/character/unique_condition.orderedmap"
NL = chr(10)
UID, STACKS = "13999010", 50
T = {lp: load(lp) for lp in (AB_LP, CAS_LP, U_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
assert UID not in T[U_LP]
T[U_LP][UID] = "unique_kyle_moon_charge_cap,强化充能速度,battle/common/unique_condition/unique_rec_android_seaside_surge,99999999,99,(None),(None),(None),(None),false,false,0,0,false,(None)"
LOG.append(f"unique {UID} 强化充能速度（99999999 帧、上限 99 层、图标借浪涌充能）")
P = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_charge_cap$ability_skill_kyle_moon_charge_cap"
tree = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
    ["Command", ["CreateCondition", -17, [["ACUnique", int(UID), [{"min": STACKS, "max": STACKS}]]],
                 [{"min": 1, "max": 1}], ["None"], False, False, "kyle_moon_charge_cap", None, False, 3,
                 [{"min": 1, "max": 1}], True]]]]]
d = encode_tree(tree); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == tree
files[wf_dsl.dsl_logical(P)] = d
rs = [r for r in rows(T[AB_LP]["1399906"]) if r]; assert len(rs) == 1
tpl = [r for r in rows(T[AB_LP]["1399903"]) if r][4]; assert tpl[47] == "629" and tpl[6] == "42"
nr = list(tpl)
nr[0], nr[1], nr[2] = rs[0][0], rs[0][1], rs[0][2]
nr[5], nr[6], nr[13] = "0", "0", "0"
for c in (9, 10, 11, 16, 17, 18, 29): nr[c] = ""
nr[27], nr[28], nr[30], nr[31], nr[35] = "0", "0", "100000", "100000", "36"   # 开局≥1（官方蓝本同 ring：CT 36 帧）
nr[70], nr[71] = "ability_skill_kyle_moon_charge_cap", P
rs.append(nr); T[AB_LP]["1399906"] = leaf(T[AB_LP]["1399906"], rs)
LOG.append("能力6 1399906 #1：开局 → 629 ability_skill_kyle_moon_charge_cap（自身「强化充能速度」50 层；无前置、不限队长）")
T[CAS_LP]["ability_skill_kyle_moon_charge_cap"] = "战斗开始时，赋予自身「强化充能速度」" + NL
v6 = T[CAS_LP]["desc_override_kyle_moon_6"]; s6 = rows(v6)[0][0]; assert NL not in s6
T[CAS_LP]["desc_override_kyle_moon_6"] = leaf(v6, [[s6 + NL + "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度上限提升至200%"]])
probs = [f"1399906#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("ability", r)]
probs += W.dsl_signature_problems(tree)
assert not probs, probs
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data); assert back == T[lp]
    assert set(BASE[lp]) <= set(back)
    files[lp] = data
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.169", "version": "1.4.170",
         "requires_client_capability": "charge-cap-unique-v1", "old_client_behavior": "固有状态只显示层数图标，充能上限仍 100%，不崩",
         "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
