# -*- coding: utf-8 -*-
"""凯尔 139990：删除队长 #10（自身充能速度 +999%）；强化充能速度 999 → 200 层（v20：上限 200%）。叠加在 1.4.173 上，仅 v20。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "174")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.173-1.4.174-1-kyle-charge-200-local.zip"
LD_LP, CAS_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap"
P = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_charge_cap$ability_skill_kyle_moon_charge_cap"
NL = chr(10)
T = {lp: load(lp) for lp in (LD_LP, CAS_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
t = copy.deepcopy(dsl_tree(P)); ac = t[11][1][0][1][2][0]
assert ac[:2] == ["ACUnique", 13999010] and ac[2] == [{"min": 999, "max": 999}]
ac[2] = [{"min": 200, "max": 200}]
d = encode_tree(t); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == t
assert not W.dsl_signature_problems(t)
files[wf_dsl.dsl_logical(P)] = d; LOG.append("ability_skill_kyle_moon_charge_cap：ACUnique 999 → 200 层（v20 上限 200%）")
rs = [r for r in rows(T[LD_LP]["139990"]) if r]; assert len(rs) == 11
assert rs[10][45] == "35" and rs[10][46] == "0" and rs[10][49] == "999000"
rs = rs[:10]; T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs); LOG.append("队长 139990 删除 #10（自身充能速度 +999%）")
v = T[CAS_LP]["desc_override_kyle_moon"]; s = rows(v)[0][0]
old = "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度的上限提升至999%（不影响技能槽最大值）" + NL + "自身技能充能速度＋999%"
assert s.endswith(old)
s = s[: -len(old)] + "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度的上限提升至200%（不影响技能槽最大值）"
T[CAS_LP]["desc_override_kyle_moon"] = leaf(v, [[s]])
T[CAS_LP]["ability_skill_kyle_moon_charge_cap"] = leaf(T[CAS_LP]["ability_skill_kyle_moon_charge_cap"], [["战斗开始时，赋予自身「强化充能速度」（技能充能速度的上限提升至200%）"]])
LOG.append("文案：上限 999% → 200%，删除「自身技能充能速度＋999%」")
probs = [f"139990#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("leader_ability", r)]
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
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.173", "version": "1.4.174",
         "requires_client": "v20 only (charge-cap formula stacks/100)", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
