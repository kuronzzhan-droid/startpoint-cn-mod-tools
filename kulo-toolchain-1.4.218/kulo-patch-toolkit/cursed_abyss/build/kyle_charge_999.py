# -*- coding: utf-8 -*-
"""凯尔 139990：充能速度上限 999%（v20 公式 上限=层数/100）+ 队长自身充能速度 +999%。叠加在 1.4.172 上，需 v20 APK。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "173")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.172-1.4.173-1-kyle-charge-999-local.zip"
LD_LP, CAS_LP, U_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap", "master/character/unique_condition.orderedmap"
P = "battle/action/skill/action/ability_skill/ability_skill_kyle_moon_charge_cap$ability_skill_kyle_moon_charge_cap"
NL = chr(10)
T = {lp: load(lp) for lp in (LD_LP, CAS_LP, U_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
u = rows(T[U_LP]["13999010"])[0]; assert u[4] == "99"; u[4] = "999"
T[U_LP]["13999010"] = leaf(T[U_LP]["13999010"], [u]); LOG.append("unique 13999010 叠加上限 99 → 999")
t = copy.deepcopy(dsl_tree(P)); ac = t[11][1][0][1][2][0]
assert ac[:2] == ["ACUnique", 13999010] and ac[2] == [{"min": 50, "max": 50}]
ac[2] = [{"min": 999, "max": 999}]
d = encode_tree(t); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == t
pr = W.dsl_signature_problems(t); assert not pr, pr
files[wf_dsl.dsl_logical(P)] = d; LOG.append("ability_skill_kyle_moon_charge_cap：ACUnique 50 → 999 层（v20：上限 = 层数/100 = 999%）")
rs = [r for r in rows(T[LD_LP]["139990"]) if r]; assert len(rs) == 10
tpl = rs[5]; assert tpl[45] == "35" and tpl[46] == "5"
nr = list(tpl); nr[4], nr[7], nr[8], nr[9] = "0", "0", "0", ""
nr[46], nr[47], nr[49], nr[50] = "0", "", "999000", "999000"
rs.append(nr); T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs)
LOG.append("队长 139990 新增 #10：自身 技能充能速度(35) +999%（常驻、仅队长）")
v = T[CAS_LP]["desc_override_kyle_moon"]; s = rows(v)[0][0]
old = "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度的上限提升至200%（不影响技能槽最大值）"
assert s.endswith(old)
s = s[: -len(old)] + "战斗开始时，赋予自身「强化充能速度」：自身技能充能速度的上限提升至999%（不影响技能槽最大值）" + NL + "自身技能充能速度＋999%"
T[CAS_LP]["desc_override_kyle_moon"] = leaf(v, [[s]])
T[CAS_LP]["ability_skill_kyle_moon_charge_cap"] = leaf(T[CAS_LP]["ability_skill_kyle_moon_charge_cap"], [["战斗开始时，赋予自身「强化充能速度」（技能充能速度的上限提升至999%）"]])
LOG.append("文案：上限 200% → 999%；新增「自身技能充能速度＋999%」")
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
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.172", "version": "1.4.173",
         "requires_client": "v20 (charge-cap formula stacks/100)",
         "old_client_behavior": "v18/v19 公式 1+n/50 → 999 层 = 2098% 上限（不崩）；无补丁客户端：100% 上限", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
