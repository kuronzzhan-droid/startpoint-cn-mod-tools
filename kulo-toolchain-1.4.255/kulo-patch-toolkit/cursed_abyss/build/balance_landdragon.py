# -*- coding: utf-8 -*-
"""风巨蜥 149998：能力2 25连击回槽加 CT 1 秒；能力6 发动2次技能回槽加 CT 3 秒、Fever 能力伤害独立乘区 15→30% 改为 10%。叠加在 1.4.175 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "176")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.175-1.4.176-1-balance-landdragon-local.zip"
AB_LP, CAS_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
T = {lp: load(lp) for lp in (AB_LP, CAS_LP)}; BASE = copy.deepcopy(T); files, LOG, CHECK = {}, [], []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
def edit(key, fn):
    rs = [r for r in rows(T[AB_LP][key]) if r]; old = [list(r) for r in rs]; fn(rs)
    assert rs[0][1:3] == old[0][1:3]
    T[AB_LP][key] = leaf(T[AB_LP][key], rs); CHECK.append((key, rs))
def a2(rs):
    r = rs[2]; assert r[47] == "211" and r[30] == "2500000" and r[35] == "0" and r[51] == "5000"; r[35] = "60"
edit("1499982", a2); LOG.append("能力2 #2（风共鸣 每25连击 自身技能槽+5%）CT 0 → 60 帧（1 秒）")
def a6(rs):
    r = rs[1]; assert r[47] == "211" and r[30] == "200000" and r[35] == "0" and r[51] == "5000"; r[35] = "180"
    r = rs[2]; assert r[97] == "4" and r[109] == "412" and r[113] == "15000" and r[114] == "30000"; r[113] = r[114] = "10000"
edit("1499986", a6)
LOG.append("能力6 #1（风共鸣 发动技能2次 自身技能槽+5%）CT 0 → 180 帧（3 秒）")
LOG.append("能力6 #2（风共鸣 Fever 中 风属性角色 能力伤害独立乘区[412]）15%→30% → 10%")
v = T[CAS_LP]["desc_override_land_dragon_wind_playable_2"]; s = rows(v)[0][0]
old = "风属性共鸣时，每达成25连击，自身技能槽+5%。"; assert s.count(old) == 1
T[CAS_LP]["desc_override_land_dragon_wind_playable_2"] = leaf(v, [[s.replace(old, "风属性共鸣时，每达成25连击，自身技能槽+5%（CT：1秒）。")]])
LOG.append("desc_override_land_dragon_wind_playable_2：25连击行加「（CT：1秒）」；能力6 无覆盖文案（客户端按行自动生成）")
probs = [f"{k}#{i}: {x}" for k, rr in CHECK for i, r in enumerate(rr) for x in L.client_legality_problems("ability", r)]
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
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.175", "version": "1.4.176", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
