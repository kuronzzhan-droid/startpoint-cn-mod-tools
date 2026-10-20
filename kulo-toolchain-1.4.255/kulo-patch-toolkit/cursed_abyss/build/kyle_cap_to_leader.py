# -*- coding: utf-8 -*-
"""凯尔 139990：「强化充能速度」发动行从能力6 移到队长技；队长文案 10 倍行去掉「200连击封顶」。叠加在 1.4.171 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "172")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.171-1.4.172-1-kyle-cap-to-leader-local.zip"
AB_LP, LD_LP, CAS_LP = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
P = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_charge_cap$ability_skill_kyle_moon_charge_cap"
CAPLINE = "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度上限提升至200%"
NEWCAP = "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度的上限提升至200%（不影响技能槽最大值）"
T = {lp: load(lp) for lp in (AB_LP, LD_LP, CAS_LP)}; BASE = copy.deepcopy(T); files, LOG, CHECK = {}, [], []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
# 能力6 删 #1
rs = [r for r in rows(T[AB_LP]["1399906"]) if r]; assert len(rs) == 2 and rs[1][47] == "629" and rs[1][71] == P
rs = rs[:1]; T[AB_LP]["1399906"] = leaf(T[AB_LP]["1399906"], rs); CHECK.append(("ability", "1399906", rs))
v = T[CAS_LP]["desc_override_kyle_moon_6"]; s = rows(v)[0][0]; assert s.endswith(NL + CAPLINE)
T[CAS_LP]["desc_override_kyle_moon_6"] = leaf(v, [[s[: -len(NL + CAPLINE)]]])
LOG.append("能力6 1399906 删除 #1（开局 629 强化充能速度）及面板行")
# 队长 新增 #9
rs = [r for r in rows(T[LD_LP]["139990"]) if r]; assert len(rs) == 9 and rs[8][45] == "722"
nr = list(rs[8])
for c in (80, 81, 82): nr[c] = ""
nr[25], nr[26], nr[28], nr[29], nr[33], nr[45], nr[46] = "0", "0", "100000", "100000", "36", "629", "0"
nr[68], nr[69] = "ability_skill_kyle_moon_charge_cap", P
rs.append(nr); T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs); CHECK.append(("leader_ability", "139990", rs))
LOG.append("队长 139990 新增 #9：开局（CT36 帧）→ 629 ability_skill_kyle_moon_charge_cap（自身强化充能速度 50 层 = 上限 200%）")
v = T[CAS_LP]["desc_override_kyle_moon"]; s = rows(v)[0][0]
old = "（每1连击＋0.5%，200连击封顶）"; new = "（每1连击＋0.5%，无上限）"
assert s.count(old) == 1
s = s.replace(old, new) + NL + NEWCAP
T[CAS_LP]["desc_override_kyle_moon"] = leaf(v, [[s]])
T[CAS_LP]["ability_skill_kyle_moon_charge_cap"] = leaf(T[CAS_LP]["ability_skill_kyle_moon_charge_cap"], [["战斗开始时，赋予自身「强化充能速度」（技能充能速度的上限提升至200%）"]])
LOG.append("desc_override_kyle_moon：10 倍行改「每1连击＋0.5%，无上限」；末尾加强化充能速度行")
probs = [f"{k}#{i}: {x}" for tb, k, rr in CHECK for i, r in enumerate(rr) for x in L.client_legality_problems(tb, r)]
assert not probs, probs
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data); assert back == T[lp] and set(back) == set(BASE[lp])
    files[lp] = data
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.171", "version": "1.4.172",
         "requires_client_capability": ["charge-cap-unique-v1", "kyle-direct-x10-combo-v1 (uncapped combo, v19)"], "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
