# -*- coding: utf-8 -*-
"""凯尔 139990 直击「基础倍率」改造，叠加在 1.4.167 上（作者纠偏：不是加数值，是凯尔一碰=别人 10 碰，再吃其他加成；随连击像斩铁那样涨）。
① 撤掉 1.4.166 #9(直击+300%) / #10(直击独立乘区+20%) 与 1.4.167 #11(每10连击直击+15%) 及其面板文案。
② 队长技新增：自身直击独立乘区 +900%（instant 693，触发 0=常驻）⇒ 直击单次结算 ×(1+9)=10 倍。
   机制：MemberImpl 直击 NormalAttack 固定 multiplierOfAttackPoint=1、enablesComboBonus=false；
   唯一按角色乘在直击上的数据杠杆 = NormalAttackCalculator:713-718 的 (1 + 追加直击伤害 + 直击独立乘区)/段数。
③ 连击成长照斩铁·寒梅一闪（samurai_robot_plum）的 enablesComboBonus 曲线：×(1+0.5%×连击) 线性；
   套到凯尔基础 10 倍上 = 每 1 连击 +0.05 倍 ⇒ 每 10 连击 +0.5 倍（during 410 +50%），封顶 200 连击（×2 ⇒ 20 倍）。
   列式照抄官方 during 2 ComboHigh（elf_princess 1410151 每 N 连击限 M 次）+ 官方队长 410 先例 121153。
用法：WF_TIP=167 python kyle_direct_base.py
"""
import copy, hashlib, json, os, zipfile
os.environ.setdefault("WF_TIP", "167")
from live149 import *  # noqa
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_describe as D

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.167-1.4.168-1-kyle-direct-base-local.zip"
LD_LP, CAS_LP = "master/ability/leader_ability.orderedmap", "master/string/custom_ability_string.orderedmap"
NL = chr(10)
BASE_X = 10                      # 直击基础倍率（别人 = 1）
COMBO_RATE = 0.005               # 斩铁 COMBO_BONUS（NormalAttackCalculator.COMBO_BONUS = 0.005 / 连击）
STEP, CAP_COMBO = 10, 200        # 每 10 连击结算一次，200 连击封顶
PER = round(BASE_X * COMBO_RATE * STEP * 100000)          # 0.5 倍 = 50000（1000=1%）
LIMIT = CAP_COMBO // STEP                                  # 20 次
LOG, files = [], {}
T = {lp: load(lp) for lp in (LD_LP, CAS_LP)}
BASE = copy.deepcopy(T)

def leaf(v, rs):
    s = _csv(rs); return s if v.endswith(NL) else s.rstrip(NL)

rs = [r for r in rows(T[LD_LP]["139990"]) if r]
assert len(rs) == 12, len(rs)
r9, r10, r11 = rs[9], rs[10], rs[11]
assert (r9[3], r9[45], r9[49]) == ("0", "33", "300000"), r9[:50]
assert (r10[3], r10[45], r10[49], r10[25]) == ("0", "693", "20000", "0"), r10[:50]
assert (r11[3], r11[95], r11[107], r11[111]) == ("1", "2", "1", "15000"), r11[95:113]
keep = rs[:9]
# ② 基础 10 倍：沿用 #10 的 instant 常驻骨架（官方同族先例：1410876/1310866 instant 696 触发0 常驻）
nb = list(r10); nb[49] = nb[50] = str((BASE_X - 1) * 100000)
# ③ 连击成长：沿用 #11 的 during ComboHigh 骨架，只换内容 kind / 数值 / 次数
nc = list(r11); nc[107] = "410"; nc[100] = str(LIMIT); nc[111] = nc[112] = str(PER)
assert nc[98] == nc[99] == str(STEP * 100000) and nc[96] == "" and nc[108] == "0"
new_rows = keep + [nb, nc]
T[LD_LP]["139990"] = leaf(T[LD_LP]["139990"], new_rows)
LOG.append("删除 #9 " + D.describe_line(r9, "leader_ability") + " / #10 " + D.describe_line(r10, "leader_ability")
           + " / #11 " + D.describe_line(r11, "leader_ability"))
LOG.append("新增 #9 " + D.describe_line(nb, "leader_ability"))
LOG.append("新增 #10 " + D.describe_line(nc, "leader_ability"))

s0 = rows(T[CAS_LP]["desc_override_kyle_moon"])[0][0]
old_lines = ["自身直接攻击伤害＋300%，直接攻击伤害额外乘区＋20%", "连击数每达到10，自身直接攻击伤害＋15%（最多10次，合计＋150%）"]
lines = s0.split(NL)
assert lines[-2:] == old_lines, lines[-2:]
add = [f"自身直接攻击的基础伤害为通常的{BASE_X}倍（直击独立乘区＋{(BASE_X - 1) * 100}%）",
       f"连击数每达到{STEP}，自身直击基础倍率再＋{PER / 100000:g}倍（{CAP_COMBO}连击时最多＋{PER * LIMIT // 100000}倍）"]
for x in add: assert len(x) <= 57, (len(x), x)
T[CAS_LP]["desc_override_kyle_moon"] = leaf(T[CAS_LP]["desc_override_kyle_moon"], [[NL.join(lines[:-2] + add)]])
LOG.append("desc_override_kyle_moon 去掉旧两行，追加: " + " / ".join(add))

probs = [f"139990#{i}: {x}" for i, r in enumerate(new_rows) for x in L.client_legality_problems("leader_ability", r)]
for lp in T:
    data = q.build_node(T[lp]); back = q.parse_node(data)
    assert back == T[lp] and set(back) == set(BASE[lp])
    files[lp] = data
ch = {lp: [k for k in BASE[lp] if q.parse_node(files[lp])[k] != BASE[lp][k]] for lp in files}
assert ch == {LD_LP: ["139990"], CAS_LP: ["desc_override_kyle_moon"]}, ch
LOG.append(f"改动键: {ch}")
got = [r for r in rows(q.parse_node(files[LD_LP])["139990"]) if r]
assert got[:9] == rs[:9] and got[9:] == [nb, nc] and all(len(r) == 124 for r in got)
assert not probs, probs
members = {member(lp): d for lp, d in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.167", "version": "1.4.168", "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
