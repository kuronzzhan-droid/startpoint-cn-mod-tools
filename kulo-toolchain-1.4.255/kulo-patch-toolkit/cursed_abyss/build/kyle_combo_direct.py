# -*- coding: utf-8 -*-
"""凯尔 139990 队长技追加 1 行：连击数每 10，自身直击伤害 +15%（最多 10 次 = +150%）。叠加在 1.4.166 上。
列式照抄官方 during kind 2 ComboHigh（队长 241033#1 / 能力 elf_princess 1410151、1410156 的「每 N 连击、限 M 次」写法）：
c95=2, c96='', c98/c99=阈值(×100000=1 连击), c100=次数上限, c107=1 Direct伤害, c108=0 自身。
用法：WF_TIP=166 python kyle_combo_direct.py
"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "166")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_describe as D

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.166-1.4.167-1-kyle-combo-direct-local.zip"
LD_LP, CAS_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
STEP, PER, CAP = 10, 15000, 10          # 每 10 连击 +15%，最多 10 次（100 连击封顶 +150%）
LOG, files = [], {}
T = {lp: load(lp) for lp in (LD_LP, CAS_LP)}
BASE = copy.deepcopy(T)

def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)

rs = [r for r in rows(T[LD_LP]["139990"]) if r]
assert len(rs) == 11, len(rs)
tpl = rs[3]   # 自身 Direct伤害 25%/层（持续行，c3=1）
assert (tpl[3], tpl[95], tpl[107], tpl[108], tpl[111]) == ("1", "134", "1", "0", "25000"), tpl
assert rs[9][45] == "33" and rs[10][45] == "693"
nr = list(tpl)
nr[4], nr[7], nr[8], nr[9] = "0", "", "", ""                  # 无共鸣前置（与官方 241033#1 同）
nr[95], nr[96], nr[97] = "2", "", ""                           # during ComboHigh，puller 照官方留空
nr[98] = nr[99] = str(STEP * 100000)                           # 阈值 10 连击
nr[100], nr[101], nr[102], nr[103], nr[104], nr[105] = str(CAP), "", "", "", "", ""
nr[106], nr[107], nr[108], nr[109], nr[110] = "false", "1", "0", "", ""
nr[111] = nr[112] = str(PER)
assert len(nr) == 124
rs.append(nr)
T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], rs)
LOG.append("队长 139990 新增 #11: " + D.describe_line(nr, "leader_ability"))

line = f"连击数每达到{STEP}，自身直接攻击伤害＋{PER // 1000}%（最多{CAP}次，合计＋{PER // 1000 * CAP}%）"
assert len(line) <= 57, len(line)
s0 = rows(T[CAS_LP]["desc_override_kyle_moon"])[0][0]
assert s0.endswith("自身直接攻击伤害＋300%，直接攻击伤害额外乘区＋20%") and line not in s0
T[CAS_LP]["desc_override_kyle_moon"] = leaf(T[CAS_LP]["desc_override_kyle_moon"], [[s0 + NL + line]])
LOG.append("desc_override_kyle_moon 追加一行: " + line)

probs = [f"139990#{i}: {x}" for i, r in enumerate(rs) for x in L.client_legality_problems("leader_ability", r)]
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data)
    assert back == T[lp] and set(back) == set(BASE[lp])
    ch = sorted(k for k in BASE[lp] if back[k] != BASE[lp][k])
    LOG.append(f"{lp} 改动键: {ch}")
    files[lp] = data
ch_ld = [k for k in BASE[LD_LP] if q.parse_node(files[LD_LP])[k] != BASE[LD_LP][k]]
ch_cas = [k for k in BASE[CAS_LP] if q.parse_node(files[CAS_LP])[k] != BASE[CAS_LP][k]]
assert ch_ld == ["139990"] and ch_cas == ["desc_override_kyle_moon"], (ch_ld, ch_cas)
old = [r for r in rows(BASE[LD_LP]["139990"]) if r]
new = [r for r in rows(q.parse_node(files[LD_LP])["139990"]) if r]
assert new[:11] == old and len(new) == 12 and new[11] == nr       # 旧 11 行逐字不动，只追加
assert not probs, probs
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.166", "version": "1.4.167", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
