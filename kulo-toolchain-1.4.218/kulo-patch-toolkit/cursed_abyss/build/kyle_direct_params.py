# -*- coding: utf-8 -*-
"""凯尔 139990：直击倍率参数化（v21）——新固有 13999011（基础倍数）/13999012（每连击 0.01%），
队长开局脚本给 10 层 / 500 层 ⇒ 10×(1+5%×连击)。叠加在 1.4.174 上，只给 v21。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "175")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.174-1.4.175-1-kyle-direct-params-local.zip"
LD_LP, CAS_LP, U_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap", "master/character/unique_condition.orderedmap"
P = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_direct_params$ability_skill_kyle_moon_direct_params"
NL = chr(10)
BASE_N, PER_N = 10, 500
T = {lp: load(lp) for lp in (LD_LP, CAS_LP, U_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
for uid, code, name in (("13999011", "unique_kyle_moon_direct_base", "月狼直击倍率"), ("13999012", "unique_kyle_moon_direct_combo", "月狼连击增幅")):
    assert uid not in T[U_LP]
    T[U_LP][uid] = f"{code},{name},battle/common/unique_condition/unique_kyle_moon_crescent,99999999,9999,(None),(None),(None),(None),false,false,0,0,false,(None)"
LOG.append("unique 13999011 月狼直击倍率 / 13999012 月狼连击增幅（99999999 帧，上限 9999，图标借月牙）")
def cc(uid, n):
    return ["Command", ["CreateCondition", -17, [["ACUnique", uid, [{"min": n, "max": n}]]], [{"min": 1, "max": 1}], ["None"],
                        False, False, f"kyle_moon_direct_{uid}", None, False, 3, [{"min": 1, "max": 1}], True]]
tree = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0, ["Block", [cc(13999011, BASE_N), cc(13999012, PER_N)]]]
d = encode_tree(tree); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == tree
assert not W.dsl_signature_problems(tree)
files[wf_dsl.dsl_logical(P)] = d
rs = [r for r in rows(T[LD_LP]["139990"]) if r]; assert len(rs) == 10 and rs[9][45] == "629"
nr = list(rs[9]); nr[68], nr[69] = "ability_skill_kyle_moon_direct_params", P
rs.append(nr); T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs)
LOG.append(f"队长 139990 新增 #10：开局 → 629 ability_skill_kyle_moon_direct_params（13999011×{BASE_N}、13999012×{PER_N}）")
T[CAS_LP]["ability_skill_kyle_moon_direct_params"] = "战斗开始时，强化自身直接攻击（基础伤害10倍，每1连击再＋5%）" + NL
v = T[CAS_LP]["desc_override_kyle_moon"]; s = rows(v)[0][0]
old = "自身为队长时，直接攻击基础伤害为通常的10倍，并随连击数提升（每1连击＋0.5%，无上限）"
assert s.count(old) == 1
s = s.replace(old, "自身为队长时，直接攻击基础伤害为通常的10倍，每1连击再＋5%（无上限）")
T[CAS_LP]["desc_override_kyle_moon"] = leaf(v, [[s]])
LOG.append("队长文案：10 倍行 → 「直接攻击基础伤害为通常的10倍，每1连击再＋5%（无上限）」")
probs = [f"139990#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("leader_ability", r)]
assert not probs, probs
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data); assert back == T[lp] and set(BASE[lp]) <= set(back)
    files[lp] = data
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.174", "version": "1.4.175",
         "requires_client": "v21 only (kyle direct mult = n(13999011) * (1 + n(13999012)/10000 * combo))",
         "old_client_behavior": "v20：仍按写死的 10×(1+0.5%×连击)，两个新状态只显示图标；未打补丁客户端：无加成", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
