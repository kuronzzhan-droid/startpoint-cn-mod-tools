# -*- coding: utf-8 -*-
"""罗尔夫(中秋) 149986 能力2：非队长时全队无法获得能力/武器类技能槽（423 掩码 8）；深渊·裂空战镰 8000107 连击→技能槽 加 CT 5 秒。叠加在 1.4.182 上。"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "183")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.182-1.4.183-1-balance-wolf-scythe-local.zip"
LPS = {"ab": "master/ability/ability.orderedmap", "cas": "master/string/custom_ability_string.orderedmap",
       "soul": "master/ability/ability_soul.orderedmap", "enh": "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"}
NL = chr(10)
T = {k: load(v) for k, v in LPS.items()}; BASE = copy.deepcopy(T); files, LOG = {}, []
def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)
# 1) 罗尔夫 能力2
rs = [r for r in rows(T["ab"]["1499862"]) if r]; assert len(rs) == 2
tpl = [r for r in rows(T["ab"]["1499872"]) if r][3]; assert tpl[109] == "423" and tpl[118] == "12"
nr = list(tpl); nr[0] = rs[0][0]; nr[6] = "46"; nr[118] = "8"
rs.append(nr); T["ab"]["1499862"] = leaf(T["ab"]["1499862"], rs)
LOG.append("能力2 1499862 新增 #2：自身不是队长时 持续 → 全队 423 限制技能槽增加（掩码 8 = 所有能力类回槽，含角色/队长/武器/魂/EX）")
probs = [f"1499862#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("ability", r)]
v = T["cas"]["desc_override_black_wolf_knight_moon_2"]; s = rows(v)[0][0]
T["cas"]["desc_override_black_wolf_knight_moon_2"] = leaf(v, [[s + NL + "自身不是队长时，全队无法通过能力及武器效果获得技能槽"]])
# 2) 镰刀 连击→技能槽 CT 5 秒
sr = [r for r in rows(T["soul"]["8000107"]) if r]
assert sr[1][24] == "12" and sr[1][27] == "2500000" and sr[1][44] == "211" and sr[1][32] == "0"; sr[1][32] = "300"
T["soul"]["8000107"] = leaf(T["soul"]["8000107"], sr)
er = [r for r in rows(T["enh"]["8000107"]) if r]
assert er[1][27] == "12" and er[1][30] == "2500000" and er[1][47] == "211" and er[1][35] == "0"; er[1][35] = "300"
T["enh"]["8000107"] = leaf(T["enh"]["8000107"], er)
LOG.append("深渊·裂空战镰 8000107：魂 #1 / 觉醒强化 #1（风共鸣 每25连击 技能槽+3.75%）CT 0 → 300 帧（5 秒）")
assert not probs, probs
for k, lp in LPS.items():
    d = q.build_node(T[k]); back = q.parse_node(d); assert back == T[k] and set(back) == set(BASE[k])
    assert len([x for x in BASE[k] if back[x] != BASE[k][x]]) == 1
    files[lp] = d
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.182", "version": "1.4.183",
         "requires_client_capability": "gauge-gain-rules-v1 (ability-table 423; present in v17/v23 lineage)", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
