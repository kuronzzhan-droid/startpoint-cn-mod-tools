# -*- coding: utf-8 -*-
"""凯尔 139990：①自身直击伤害 +300% / 直击独立乘区 +20%（队长技追加 2 行）；
②特殊 PF（kyle_moon_thunder_ring lv1-3）追加一个判定区：月牙每 2 层 +1 次结算（最多 +49），无命中特效。叠加在 1.4.165 上。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "166")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands, get
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.165-1.4.166-1-kyle-direct-pf-local.zip"
AB_LP, CAS_LP = "master/ability/ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
LOG, files = [], {}
T = {lp: load(lp) for lp in (AB_LP, CAS_LP)}
BASE = copy.deepcopy(T)
UID, VID, DIV, CAP = 13999001, 1, 2, 49.0

def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)

def override(key, old, new):
    s = rows(T[CAS_LP][key])[0][0]
    assert s.count(old) == 1, (key, old)
    T[CAS_LP][key] = leaf(T[CAS_LP][key], [[s.replace(old, new)]])

# ① 直击强化（作者：绑定队长技）
LD_LP = "master/ability/leader_ability.orderedmap"
T[LD_LP] = load(LD_LP); BASE[LD_LP] = copy.deepcopy(T[LD_LP])
rs = [r for r in rows(T[LD_LP]["139990"]) if r]; tpl = rs[4]
assert tpl[45] == "245" and tpl[4] == "2" and tpl[9] == "Yellow"
for kind, val in (("33", "300000"), ("693", "20000")):
    nr = list(tpl)
    nr[4], nr[7], nr[8], nr[9] = "0", "", "", ""          # 无共鸣前置
    nr[45], nr[46], nr[47], nr[49], nr[50] = kind, "0", "", val, val
    rs.append(nr)
T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs)
CHECK = [("leader_ability", "139990", rs)]
s0 = rows(T[CAS_LP]["desc_override_kyle_moon"])[0][0]
assert s0.endswith("技能充能速度＋20%")
T[CAS_LP]["desc_override_kyle_moon"] = leaf(T[CAS_LP]["desc_override_kyle_moon"], [[s0 + NL + "自身直接攻击伤害＋300%，直接攻击伤害额外乘区＋20%"]])
LOG.append("队长 139990 新增 #9 自身 DirectDamage(33) +300%、#10 自身 SeparatedTermDirectDamage(693) +20%（常驻，无共鸣前置）")

# ② 特殊 PF 结算次数随月牙增长
PF = [f"battle/action/power_flip/action/override/kyle_moon_thunder_ring$kyle_moon_thunder_ring_lv{n}" for n in (1, 2, 3)]
for n, p in enumerate(PF, 1):
    t = copy.deepcopy(dsl_tree(p))
    hits = [(pp, c) for pp, c in commands(t, "CreateHitArea") if c[2] == 4]
    assert len(hits) == 1, hits
    pp, c = hits[0]
    assert c[13] == ["SpecifyHitAreaLifetimeDirectly", 10] and c[14][0] == "CalculatedUsingMaxNumOfHits" and c[15][0] == "Some"
    assert (c[19], c[21], c[22], c[24]) == (5, 6, 7, 104), c[19:25]
    cna = c[23][1][0][1]; assert cna[0] == "CreateNormalAttack" and cna[1] == 7 and cna[15] == ["Fine"], cna
    extra = copy.deepcopy(c)
    extra[13] = ["SpecifyHitAreaLifetimeDirectly", 50]
    extra[14] = ["SpecifyMinHitIntervalDirectly", 1.0]
    # 命中上限按 count >= X 截止 ⇒ 次数 = ceil(X)；X = 变量 - 0.5 ⇒ = floor(层/2)
    extra[15] = ["Some", [{"min": -0.5, "max": -0.5, "vlv": [{"vid": VID, "min": 0, "max": 1}]}]]
    extra[19], extra[21], extra[22] = 8, 9, 10
    ecna = copy.deepcopy(cna); ecna[1] = 10; ecna[15] = ["None"]
    extra[20] = ["Block", []]
    extra[23] = ["Block", [["Command", ecna]]]
    parent = get(t, pp[:-1]); assert parent[pp[-1]][1] is c
    parent.insert(pp[-1] + 1, ["Command", extra])
    root = t[11][1]
    root.insert(0, ["Command", ["BindConditionAccumulationVariable", -17, VID, ["DCUnique", UID], DIV, CAP]])
    data = encode_tree(t)
    back = wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"]; assert back == t
    files[wf_dsl.dsl_logical(p)] = data
    LOG.append(f"PF lv{n}: 新增判定区（同参照点、半径/倍率 {cna[6][0]['max']}/伤害归属 104 不变，间隔 1 帧、寿命 50 帧、无命中特效、无震屏），"
               f"上限 floor(min(月牙/2,49)) 次；原 {c[15][1][0]['max']} 次判定区不动")
override("override_string_kyle_moon_thunder_ring", "赋予自身特殊强化弹射", "赋予自身特殊强化弹射／自身“月牙”每2层，特殊强化弹射命中结算次数＋1（最多＋49次）")
override("desc_override_kyle_moon", "赋予自身特殊强化弹射" + NL + "强化自身冲刺", "赋予自身特殊强化弹射（自身“月牙”每2层，命中结算次数＋1，最多＋49次）" + NL + "强化自身冲刺")

probs = []
for tb, key, rs_ in CHECK:
    for i, r in enumerate(rs_):
        probs += [f"{key}#{i}: {x}" for x in L.client_legality_problems(tb, r)]
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data)
    assert back == T[lp] and set(back) == set(BASE[lp])
    ch = sorted(k for k in BASE[lp] if back[k] != BASE[lp][k])
    LOG.append(f"{lp} 改动键: {ch}")
    if ch: files[lp] = data
for lp, d in files.items():
    if lp.endswith(".deflate"):
        probs += W.dsl_signature_problems(wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"])
assert not probs, probs
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.165", "version": "1.4.166", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
