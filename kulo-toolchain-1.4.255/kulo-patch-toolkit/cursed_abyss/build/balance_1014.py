# -*- coding: utf-8 -*-
"""角色平衡 1014（腾讯表 1.4.197 之后新增各块），叠加在 kulo 1.4.197 视图上 → 1.4.198。
spec：research/balance_sheet_20261014_new.md。能力行=目标值；「删除/删掉」=删行。
用法：WF_TIP=197 python balance_1014.py
"""
import copy
import hashlib
import json
import os
import zipfile

os.environ.setdefault("WF_TIP", "197")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

assert TIP == 197, TIP
import base149 as _B
assert not os.environ.get("WF_EXTRA_ZIPS")
assert all(z.parent == ACTIVE for z in _B._ZIPS), [str(z) for z in _B._ZIPS if z.parent != ACTIVE]
assert not any("five-boss-atlas-slim" in z.name for z in _B._ZIPS)
assert _B._ZIPS[-1].name == "pinball-1.4.196-1.4.197-1-balance-1012-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.197-1.4.198-1-balance-1014-local.zip"
AB_LP, LE_LP = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"
UQ_LP = "master/character/unique_condition.orderedmap"
T = {lp: load(lp) for lp in (AB_LP, LE_LP, CAS_LP, UQ_LP)}
BASE = {lp: copy.deepcopy(v) for lp, v in T.items()}
DSL: dict[str, list] = {}
LOG: list[str] = []
NL = chr(10)
TOUCH = {lp: set() for lp in T}


def leaf(v: str, rs):
    s = _csv(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def R(lp, key):
    return [r for r in rows(T[lp][key]) if r]


def put(lp, key, rs, old0):
    assert rs[0][1:3] == old0[1:3], (key, "c1/c2", rs[0][1:3], old0[1:3])
    T[lp][key] = leaf(T[lp][key], rs)
    TOUCH[lp].add(key)


def eq(r, c, v):
    assert r[c] == v, (r[0], c, r[c], v)


def setv(r, cols, old, new):
    for c in cols:
        eq(r, c, old)
        r[c] = new


def override(key, pairs):
    node = T[CAS_LP][key]
    s = rows(node)[0][0]
    for old, new in pairs:
        assert s.count(old) == 1, (key, old, s.count(old))
        s = s.replace(old, new)
    T[CAS_LP][key] = leaf(node, [[s]])
    TOUCH[CAS_LP].add(key)


def dsl(program):
    if program not in DSL:
        DSL[program] = copy.deepcopy(dsl_tree(program))
    return DSL[program]


def scale_cells(cells, f):
    for cell in cells:
        for k in ("min", "max"):
            cell[k] = round(cell[k] * f, 6)
        for v in cell.get("vlv", []):
            for k in ("min", "max"):
                v[k] = v[k] * f


# ============================================================ 1) 风巨蜥 149998
P = "battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_"
for lv in ("1", "2"):
    t = dsl(P + lv)
    fever = [c for pp, c in commands(t, "ConditionalsFeverMode")]; assert len(fever) == 1
    prob = [c for pp, c in commands(fever[0][1], "ConditionalsProbability")]; assert len(prob) == 1
    hits = list(commands(prob[0], "CreateNormalAttack")); assert len(hits) == 17, len(hits)
    before = sum(c[6][0]["max"] for pp, c in hits)
    assert abs(before - 120.0) < 1e-6, before
    for pp, c in hits:
        assert c[1] >= 2200 and len(c[6]) == 1 and "vlv" not in c[6][0], c[:7]
        scale_cells(c[6], 0.75)
    tot = sum(c[6][0]["max"] for pp, c in hits)
    assert abs(tot - 90.0) < 1e-6, tot  # 三个首领技各 30（满级），合计 90
    allh = list(commands(t, "CreateNormalAttack")); assert len(allh) == 25
    assert all(c[6] == [{"min": 2.25, "max": 3.0}] for pp, c in allh if c[1] < 2200)
LOG.append("风巨蜥 技能 Fever 随机首领技（重爪 1×40 / 巨型激光 8×5 / 全场旋风 8×5，每种满级合计 40）倍率 ×0.75 → 重爪 1×30、激光 8×3.75、旋风 8×3.75（每种合计 30）；技能1档同比例 ×0.75；非 Fever 8×3 倍不动；两档 DSL 同改")
rs = R(AB_LP, "1499982"); assert len(rs) == 4
r = rs[2]; eq(r, 6, "2"); eq(r, 27, "12"); eq(r, 30, "2500000"); eq(r, 47, "211"); eq(r, 51, "5000"); setv(r, [35], "60", "180")
put(AB_LP, "1499982", rs, rs[0])
override("desc_override_land_dragon_wind_playable_2", [("自身技能槽+5%（CT：1秒）", "自身技能槽+5%（CT：3秒）")])
LOG.append("风巨蜥 能力2 #2 风共鸣 每25连击 自身技能槽 +5%：CT 60帧 → 180帧（1秒 → 3秒）；CAS 文案同步")

# ============================================================ 2) 凯尔 kyle_moon 139990
t = dsl("battle/action/skill/action/ability_skill/ability_skill_kyle_moon_direct_params$ability_skill_kyle_moon_direct_params")
cc = list(commands(t, "CreateCondition")); assert len(cc) == 2
for (pp, c), (uid, old, new) in zip(cc, ((13999011, 10, 5), (13999012, 500, 1000))):
    ac = c[2]; assert len(ac) == 1 and ac[0][0] == "ACUnique" and ac[0][1] == uid, ac
    assert ac[0][2] == [{"min": old, "max": old}], ac
    ac[0][2] = [{"min": new, "max": new}]
for uid in ("13999011", "13999012"):
    u = R(UQ_LP, uid); assert len(u) == 1 and u[0][4] == "9999", u  # 层数上限 9999 ≥ 1000
LOG.append("凯尔 队长 #10 开局 629 ability_skill_kyle_moon_direct_params：固有 13999011（基础倍数）10 层 → 5 层、13999012（每连击 0.01%）500 层 → 1000 层；客户端补丁公式 B×(1+P/10000×连击) ⇒ 10×(1+5%×连击) → 5×(1+10%×连击)（纯数据，APK 不动）")
T[CAS_LP]["ability_skill_kyle_moon_direct_params"] = T[CAS_LP]["ability_skill_kyle_moon_direct_params"].replace("基础伤害10倍，每1连击再＋5%", "基础伤害5倍，每1连击再＋10%")
assert "基础伤害5倍，每1连击再＋10%" in T[CAS_LP]["ability_skill_kyle_moon_direct_params"]; TOUCH[CAS_LP].add("ability_skill_kyle_moon_direct_params")
override("desc_override_kyle_moon", [("自身为队长时，直接攻击基础伤害为通常的10倍，每1连击再＋5%（无上限）", "直接攻击基础伤害为通常的5倍，每1连击再＋10%（无上限）")])
LOG.append("凯尔 队长文案：「自身为队长时，…10倍，每1连击再＋5%」→「直接攻击基础伤害为通常的5倍，每1连击再＋10%（无上限）」（按覆盖文案规则去掉「自身为队长时」前缀）；629 CAS 同步")
rs = R(AB_LP, "1399903"); assert len(rs) == 7
r = rs[3]; eq(r, 6, "187"); eq(r, 12, "13999001"); eq(r, 47, "202"); setv(r, [51, 52], "300000", "150000")
put(AB_LP, "1399903", rs, rs[0])
override("desc_override_kyle_moon_3", [("合计伤害额外乘区＋300%", "合计伤害额外乘区＋150%")])
LOG.append("凯尔 能力3 #3 持有月牙 雷属性直击变3次(202) 合计伤害额外乘区 +300% → +150%")
rs = R(AB_LP, "1399905"); assert len(rs) == 6
r = rs[0]; eq(r, 27, "20"); eq(r, 30, "5000000"); eq(r, 47, "35"); setv(r, [34], "3", "4"); setv(r, [51, 52], "6500", "5000")
put(AB_LP, "1399905", rs, rs[0])
override("desc_override_kyle_moon_5", [("技能充能速度＋6.5%（最多3次）", "技能充能速度＋5%（最多4次）")])
LOG.append("凯尔 能力5 #0 雷共鸣 每50直击 雷属性技能充能速度 +6.5%（限3次⇒19.5%）→ +5%（限4次⇒20%）")

# ============================================================ 3) 黑 139991
rs = R(AB_LP, "1399912"); assert len(rs) == 5
r = rs[0]; eq(r, 27, "107"); eq(r, 34, "25"); eq(r, 51, "5000"); eq(r, 52, "5000")
setv(r, [47], "32", "33"); setv(r, [48], "2", "5"); setv(r, [49], "", "Yellow")
assert r[47:50] == rs[4][47:50], (r[47:50], rs[4][47:50])
r = rs[4]; eq(r, 6, "187"); eq(r, 12, "13999102"); eq(r, 47, "33"); setv(r, [51, 52], "150000", "250000")
d = rs[1]; eq(d, 6, "187"); eq(d, 12, "13999102"); eq(d, 47, "32"); eq(d, 51, "100000")
new = [rs[0], rs[2], rs[3], rs[4]]
put(AB_LP, "1399912", new, rs[0])
override("desc_override_outlaw_panther_moon_2", [("自身技能每命中1次，队长攻击力＋5%，最多25次", "自身技能每命中1次，全队直接攻击伤害＋5%，最多25次"),
                                             ("雷属性角色直接攻击伤害＋150%、攻击力＋100%", "雷属性角色直接攻击伤害＋250%")])
LOG.append("黑 能力2 #0 雷共鸣 技能每命中1次（限25次）：队长 攻击力 +5% → 全队(雷) 直接攻击伤害 +5%（kind 32→33，目标 2→5/Yellow，同 #4 豹步行的目标列）")
LOG.append("黑 能力2 豹步 #4 雷属性 直击伤害 +150% → +250%；删除原 #1 豹步 攻击力 +100%；CAS 文案同步")

# ============================================================ 4) 灼原的狮王 玛格诺斯 119996（lion_swordman_reborn）
ls = R(LE_LP, "119996"); assert len(ls) == 6
r = ls[5]; eq(r, 25, "23"); eq(r, 26, "7"); eq(r, 27, "Red"); eq(r, 45, "251"); setv(r, [49, 50], "7000000", "5500000")
put(LE_LP, "119996", ls, ls[0])
LOG.append("灼原的狮王 玛格诺斯 119996 队长 #5 火属性角色发动技能时 对所有敌人 自身攻击 70倍 → 55倍 火属性能力伤害（kind 251）；该角色无队长覆盖文案，面板自动生成")

# ============================================================ 5) 月下归途的机车骑士 玛格诺斯 119990（lion_swordman_moon）特殊强化弹射 ×0.5
for n in (1, 2, 3):
    t = dsl(f"battle/action/skill/action/ability_skill/lion_swordman_moon_pf_skill$lion_swordman_moon_pf_skill_lv{n}")
    hits = list(commands(t, "CreateNormalAttack")); assert len(hits) == 2
    old = [(c[6][0]["max"], c[6][0]["vlv"][0]["max"]) for pp, c in hits]
    for pp, c in hits:
        assert len(c[6]) == 1 and c[6][0]["vlv"][0]["vid"] == 11999005, c[6]
        scale_cells(c[6], 0.5)
    nw = [(c[6][0]["max"], c[6][0]["vlv"][0]["max"]) for pp, c in hits]
    LOG.append(f"机车玛格诺斯 特殊强化弹射 Lv{n}（629 lion_swordman_moon_pf_skill_lv{n}）两段倍率 ×0.5：基础 {old[0][0]:g}/{old[1][0]:g} → {nw[0][0]:g}/{nw[1][0]:g}，引擎点火每层加成满档 {old[0][1]:.4g}/{old[1][1]:.4g} → {nw[0][1]:.4g}/{nw[1][1]:.4g}")
LOG.append("机车玛格诺斯 722 覆盖树 lion_swordman_moon_pf_lv1-3 只有演出无伤害，不动；override_string 文案无数字不动")

# ============================================================ 6) 灼原的狮王 119996 技能 全属性抗性下降 ×0.6（表写在机车块，机车无此效果，协调者确认改到 119996）
for lv in ("1", "2"):
    t = dsl("battle/action/skill/action/rare5/lion_swordman_reborn$lion_swordman_reborn_" + lv)
    tol = [ac for pp, c in commands(t, "CreateCondition") for ac in c[2] if ac[0] == "ACToleranceOfElement"]
    allel = [ac for ac in tol if ac[2] == 254]; fire = [ac for ac in tol if ac[2] == 1]
    assert len(allel) == 1 and len(fire) == 1, tol
    assert allel[0][3] == [{"min": -0.25, "max": -0.25}] and allel[0][4] == [{"min": 1, "max": 1}], allel
    allel[0][3] = [{"min": -0.15, "max": -0.15}]
    assert fire[0][3] == [{"min": -0.05 if lv == "1" else -0.06, "max": -0.05 if lv == "1" else -0.06}]
LOG.append("灼原的狮王 119996 技能两档 领域命中附加 全属性(254)抗性 -25% → -15%（×0.6）；火属性 -5%/-6% 叠3层不动；技能文案无数字不动（表写在机车块，机车 119990 无此效果，经协调者确认改到 119996）")


def main():
    files, probs = {}, []
    for lp in T:
        base, now = BASE[lp], T[lp]
        data = q.build_node(now)
        back = q.parse_node(data)
        assert back == now
        assert set(base) == set(back), (lp, set(base) ^ set(back))
        changed = sorted(k for k in base if back[k] != base[k])
        assert set(changed) == TOUCH[lp], (lp, set(changed) ^ TOUCH[lp])
        if not changed:
            continue
        LOG.append(f"{lp}: 改动键 {changed}；其余 {len(base) - len(changed)} 键逐字节相同")
        files[lp] = data
    for lp, tb in ((AB_LP, "ability"), (LE_LP, "leader_ability")):
        for key in sorted(TOUCH[lp]):
            for i, r in enumerate(R(lp, key)):
                probs += [f"{tb}:{key}#{i}: {p}" for p in L.client_legality_problems(tb, r)]
                if tb == "ability" and r[47] == "629":
                    assert r[70] in T[CAS_LP], r[70]
                if tb == "leader_ability" and r[45] == "629":
                    assert r[68] in T[CAS_LP], r[68]
                    assert r[69] in DSL or read_raw(wf_dsl.dsl_logical(r[69])), r[69]
    for p, tree in DSL.items():
        probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
        enc = encode_tree(tree)
        rt = wf_dsl.parse_dsl(__import__("zlib").decompress(enc, -15))["tree"]
        assert rt == tree, p
        files[wf_dsl.dsl_logical(p)] = enc
    assert not probs, probs
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": [],
             "applies_on": "1.4.197", "version": "1.4.198", "requires_client": "纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
