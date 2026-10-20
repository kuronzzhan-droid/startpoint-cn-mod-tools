# -*- coding: utf-8 -*-
"""凯尔 139990：删除 1.4.168 临时队长行 #9（693 直击独立乘区 +900%）/#10（每 10 连击 +50%）及两行文案，
改为描述 APK kyle-direct-x10-combo-v1 行为。叠加在 1.4.170 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "171")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.170-1.4.171-1-kyle-remove-interim-direct-local.zip"
LD_LP, CAS_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
T = {lp: load(lp) for lp in (LD_LP, CAS_LP)}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
rs = [r for r in rows(T[LD_LP]["139990"]) if r]
assert len(rs) == 11
assert rs[9][45] == "693" and rs[9][46] == "0" and rs[9][49] == rs[9][50] == "900000"
assert rs[10][95] == "2" and rs[10][100] == "20" and rs[10][107] == "410" and rs[10][111] == "50000"
old0 = list(rs[0]); rs = rs[:9]; assert rs[0][1:3] == old0[1:3]
T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs)
LOG.append("队长 139990 删除 #9（693 自身直击独立乘区 +900%）、#10（持续·连击≥10 限 20 次 → 410 +50%）；余 9 行")
v = T[CAS_LP]["desc_override_kyle_moon"]; s = rows(v)[0][0]
l1 = "自身直接攻击的基础伤害为通常的10倍（直击独立乘区＋900%）"
l2 = "连击数每达到10，自身直击基础倍率再＋0.5倍（200连击时最多＋10倍）"
new = "自身为队长时，直接攻击基础伤害为通常的10倍，并随连击数提升（每1连击＋0.5%，200连击封顶）"
assert s.endswith(NL + l1 + NL + l2)
s2 = s[: -len(l1 + NL + l2)] + new
T[CAS_LP]["desc_override_kyle_moon"] = leaf(v, [[s2]])
LOG.append("desc_override_kyle_moon：两行临时说明 → 「" + new + "」")
probs = [f"139990#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("leader_ability", r)]
assert not probs, probs
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data); assert back == T[lp] and set(back) == set(BASE[lp])
    ch = [k for k in BASE[lp] if back[k] != BASE[lp][k]]; assert len(ch) == 1, ch
    files[lp] = data
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.170", "version": "1.4.171",
         "requires_client_capability": "kyle-direct-x10-combo-v1",
         "old_client_behavior": "旧 APK 上凯尔直击回到无 10 倍/无连击加成（不崩，仅数值降低）", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
