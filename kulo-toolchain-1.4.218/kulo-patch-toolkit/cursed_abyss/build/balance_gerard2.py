# -*- coding: utf-8 -*-
"""杰拉尔 129992 追加：能力3 删 8倍追击、能力伤害 +200% → 技能伤害 +200%；能力5 删 12倍、技伤独立乘区 20% → 10%、删能伤独立乘区。叠加在 1.4.184 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "185")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.184-1.4.185-1-balance-gerard2-local.zip"
LP = "master/ability/ability.orderedmap"; NL = chr(10)
T = load(LP); BASE = copy.deepcopy(T); LOG = []
def R(k): return [r for r in rows(T[k]) if r]
def put(k, rs, old0):
    assert rs[0][1:3] == old0[1:3]; s = _csv(rs); T[k] = s if T[k].endswith(NL) else s.rstrip(NL)
rs = R("1299923"); assert rs[2][47] == "353" and rs[2][51] == "800000" and rs[3][47] == "388" and rs[3][51] == "200000"
rs[3][47] = "34"; old0 = rs[0]; rs = rs[:2] + rs[3:]; put("1299923", rs, old0)
LOG.append("能力3 1299923：删除 #2（水属性角色发动技能时 最近敌人 8倍水属性能力伤害）；#3 水属性能力伤害 +200% → 技能伤害 +200%（kind 388→34）；对决攻击特攻 +200% 保留")
r5 = R("1299925"); assert r5[0][47] == "252" and r5[1][47] == "694" and r5[2][47] == "695"
r5[1][51] = r5[1][52] = "10000"; put("1299925", [r5[1]], r5[0])
LOG.append("能力5 1299925：删除 #0（水共鸣 技能命中 全体 12倍 CT1秒）；技伤独立乘区 20% → 10%；删除能伤独立乘区 20%")
probs = [f"{k}#{i}: {x}" for k in ("1299923", "1299925") for i, r in enumerate(R(k)) for x in L.client_legality_problems("ability", r)]
assert not probs, probs
data = q.build_node(T); back = q.parse_node(data); assert back == T and set(back) == set(BASE)
assert sorted(k for k in BASE if back[k] != BASE[k]) == ["1299923", "1299925"]
members = {member(LP): data}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(LP): LP}, "applies_on": "1.4.184", "version": "1.4.185", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
