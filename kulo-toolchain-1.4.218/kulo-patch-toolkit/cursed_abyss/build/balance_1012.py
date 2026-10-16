# -*- coding: utf-8 -*-
"""角色平衡 1012（腾讯表 1.4.196 之后新增各块），叠加在 kulo 1.4.196 视图上 → 1.4.197。
spec：research/balance_sheet_20261012_new.md。能力行=目标值；「删除/删掉」=删行。
用法：WF_TIP=196 python balance_1012.py
"""
import copy
import hashlib
import json
import os
import zipfile

os.environ.setdefault("WF_TIP", "196")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

assert TIP == 196, TIP
import base149 as _B
assert not os.environ.get("WF_EXTRA_ZIPS")
assert all(z.parent == ACTIVE for z in _B._ZIPS), [str(z) for z in _B._ZIPS if z.parent != ACTIVE]
assert not any("five-boss-atlas-slim" in z.name for z in _B._ZIPS)
assert _B._ZIPS[-1].name == "pinball-1.4.195-1.4.196-1-balance-1010-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.196-1.4.197-1-balance-1012-local.zip"
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


# ============================================================ 1) 魔王 169995
rs = R(AB_LP, "1699952"); assert len(rs) == 5
for i, kind in ((0, "0"), (1, "2"), (2, "154")):
    r = rs[i]; eq(r, 97, "134"); eq(r, 104, "1699950"); eq(r, 109, kind)
    setv(r, [102], "10", "100"); setv(r, [113, 114], "50000", "5000")
r = rs[4]; eq(r, 97, "134"); eq(r, 109, "412"); setv(r, [102], "10", "50"); setv(r, [113, 114], "4000", "500")
put(AB_LP, "1699952", rs, rs[0])
LOG.append("魔王 能力2 #0-#2 魔王权能每1级 攻击力/技能伤害/能力伤害 +50%（限10级⇒最大500%）→ +5%（限100级⇒最大500%；固有上限99级，实际封顶495%）")
LOG.append("魔王 能力2 #4 魔王权能每1级 独立乘区能力伤害(412) +4%（限10⇒最大40%）→ +0.5%（限50⇒最大25%）")
rs = R(AB_LP, "1699953"); assert len(rs) == 6
spec = {2: ("0", "6000000", "12000000", "200000", "100000", "255"),
        3: ("0", "12000000", "18000000", "300000", "200000", "256"),
        4: ("144", "6000000", "18000000", "600000", "400000", "255"),
        5: ("144", "12000000", "24000000", "1800000", "600000", "256")}
for i, (pre, t0, t1, m0, m1, kind) in spec.items():
    r = rs[i]; eq(r, 6, pre); eq(r, 27, "77"); eq(r, 47, kind)
    setv(r, [30, 31], t0, t1); setv(r, [51, 52], m0, m1)
    if pre == "144":
        eq(r, 12, "1699950"); setv(r, [9, 10], "2000000", "6600000")
put(AB_LP, "1699953", rs, rs[0])
LOG.append("魔王 能力3 #2 每1秒 全体 2倍光属性能力伤害 → 每2秒 1倍（Elapsed 60→120帧）")
LOG.append("魔王 能力3 #3 每2秒 全体 3倍暗属性能力伤害 → 每3秒 2倍（Elapsed 120→180帧）")
LOG.append("魔王 能力3 #4 权能≥20 每1秒 6倍光 → 权能≥66 每3秒 4倍（前置阈值 20→66，Elapsed 60→180帧）")
LOG.append("魔王 能力3 #5 权能≥20 每2秒 18倍暗 → 权能≥66 每4秒 6倍（前置阈值 20→66，Elapsed 120→240帧）")

# ============================================================ 2) 杰拉德 149999 时空裂痕：能力伤害 1倍、直击伤害 2倍、10 秒
t = dsl("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift"); n = 0
for pp, c in commands(t, "CreateCondition"):
    for ac in c[2]:
        if ac[0] in ("ACAbilityDamageResistance", "ACDirectAttackDamageResistance"):
            assert ac[1] == [{"min": 1200, "max": 1200}] and ac[2] == [{"min": -1.0, "max": -1.0}], ac
            ac[1] = [{"min": 600, "max": 600}]
            if ac[0] == "ACDirectAttackDamageResistance":
                ac[2] = [{"min": -2.0, "max": -2.0}]
            n += 1
        elif ac[0] == "ACUnique":
            assert ac[1] == 1499990
assert n == 2
u = R(UQ_LP, "1499990"); assert len(u) == 1 and u[0][0] == "unique_gerald_time_rift"; setv(u[0], [3], "1200", "600")
T[UQ_LP]["1499990"] = leaf(T[UQ_LP]["1499990"], u); TOUCH[UQ_LP].add("1499990")
override("ability_skill_gerald_time_rift", [("受到的能力伤害与直接攻击伤害增加1倍（20秒）", "受到的能力伤害增加1倍、受到的直接攻击伤害增加2倍（10秒）")])
LOG.append("杰拉德 时空裂痕 DSL：能力伤害耐性 -100% 不变、直击伤害耐性 -100% → -200%；持续 1200 → 600 帧（20→10秒）")
LOG.append("杰拉德 固有「时空裂痕」1499990 持续 1200 → 600 帧（图标与效果同步 10 秒）；CAS 文案同步")

# ============================================================ 3) 夏琳 139992（月兔）：目标值
rs = R(AB_LP, "1399921"); r = rs[2]; eq(r, 47, "53"); setv(r, [51, 52], "20000", "5000"); put(AB_LP, "1399921", rs, rs[0])
LOG.append("夏琳 能力1 #2 雷共鸣 眩晕畏缩特攻(53，追击伤害·乘区3) 20% → 5%")
rs = R(AB_LP, "1399922"); eq(rs[0], 47, "491"); eq(rs[0], 51, "200000"); eq(rs[1], 47, "124"); eq(rs[1], 51, "100000")
r = rs[2]; eq(r, 47, "96"); setv(r, [51, 52], "10000", "5000"); put(AB_LP, "1399922", rs, rs[0])
LOG.append("夏琳 能力2 #2 减益特攻(96，乘区2) 10% → 5%；#0 弱体攻击特攻 200%、#1 弱体直击特攻 100% 与目标值一致不动")
rs = R(AB_LP, "1399924"); r = rs[0]; eq(r, 97, "136"); eq(r, 109, "158")
setv(r, [102], "4", "5"); eq(r, 113, "2500"); eq(r, 114, "5000"); r[113], r[114] = "1000", "2000"
put(AB_LP, "1399924", rs, rs[0])
LOG.append("夏琳 能力4 雷共鸣 敌人每1个弱体 对其伤害特攻(158，乘区2) 2.5%/5%（低/满级，限4⇒最大20%）→ 1%/2%（限5⇒满级最大10%）")

# ============================================================ 4) 夏日白 149990：队长技目标值（只差 #3/#4）
ls = R(LE_LP, "149990"); assert len(ls) == 6
for i, kind in ((3, "32"), (4, "388")):
    r = ls[i]; eq(r, 25, "248"); eq(r, 45, kind); setv(r, [32], "3", "6"); setv(r, [49, 50], "45000", "60000")
put(LE_LP, "149990", ls, ls[0])
override("desc_override_white_tiger_summer", [("风属性角色攻击力＋45%、能力伤害＋45%（最多3次）", "风属性角色攻击力＋60%、能力伤害＋60%（最大360%）")])
LOG.append("夏日白 队长 #3/#4 风共鸣 Fever 每1.5秒 攻击力/能力伤害 +45%（限3次）→ +60%（限6次⇒最大360%）；其余 4 条与目标值一致不动")

# ============================================================ 5) 秋灯九尾 139995
rs = R(AB_LP, "1399951"); assert len(rs) == 4
r = rs[1]; eq(r, 47, "226"); setv(r, [27], "4", "2"); setv(r, [28], "", "0")
r = rs[2]; eq(r, 47, "724"); eq(r, 27, "2"); setv(r, [30, 31], "100000", "300000")
put(AB_LP, "1399951", rs, rs[0])
LOG.append("秋灯九尾 能力1 #1 追加连击500%：触发 冲刺1次 → 强化弹射1次（kind 4→2，puller 补 0）")
LOG.append("秋灯九尾 能力1 #2 Fever中 Fever槽 -10%：触发 强化弹射1次 → 强化弹射3次（阈值 1→3）")
rs = R(AB_LP, "1399952"); assert len(rs) == 3
r = rs[0]; eq(r, 47, "354"); eq(r, 35, "45"); setv(r, [27], "15", "182"); setv(r, [28], "", "0")
r = rs[1]; eq(r, 47, "226"); eq(r, 27, "6"); eq(r, 51, "250000"); eq(r, 52, "500000"); r[51], r[52] = "500000", "1000000"
put(AB_LP, "1399952", rs, rs[0])
override("desc_override_fox_oracle_autumn_2", [("强化弹射Lv1以上时", "强化弹射Lv3以上时"), ("弹射时，连击＋5", "弹射时，连击＋10")])
LOG.append("秋灯九尾 能力2 #0 20倍雷属性能力伤害(CT0.75秒)：触发 强化弹射HitLv1 → 强化弹射HitLv3（kind 15→182，同魔王/风巨蜥在用的 OneOfEnemyPowerFlipHitLv3）")
LOG.append("秋灯九尾 能力2 #1 Fever中弹射 连击 +2.5/+5（低/满级）→ +5/+10")
rs = R(AB_LP, "1399955"); r = rs[0]; eq(r, 47, "118"); eq(r, 51, "10000"); eq(r, 52, "20000"); r[51], r[52] = "5000", "10000"
eq(rs[1], 47, "695"); eq(rs[1], 52, "20000")
put(AB_LP, "1399955", rs, rs[0])
LOG.append("秋灯九尾 能力5 #0 雷共鸣 麻痹特攻 10%/20%（低/满级）→ 5%/10%；#1 独立乘区能力伤害 20% 不变")

# ============================================================ 6) 克劳斯 129997 队长
ls = R(LE_LP, "129997"); assert len(ls) == 10
r = ls[1]; eq(r, 45, "388"); setv(r, [49, 50], "200000", "400000")
r = ls[2]; eq(r, 45, "33"); setv(r, [49, 50], "200000", "600000")
eq(ls[3], 45, "211"); eq(ls[3], 49, "50000")
r = ls[4]; eq(r, 107, "159"); eq(r, 111, "60000"); setv(r, [100], "3", "6")
r = ls[5]; eq(r, 107, "348"); eq(r, 111, "60000"); setv(r, [100], "3", "4")
eq(ls[9], 68, "claude_wolf_assassin_ex_poison_vuln")
put(LE_LP, "129997", ls, ls[0])
LOG.append("克劳斯 队长 #1 水属性 能力伤害 +200% → +400%；#2 直击伤害 +200% → +600%；#3 技能槽 +50% 不变")
LOG.append("克劳斯 队长 #4 淬毒 直击伤害特攻 60%（限3⇒180%）→ 60%（限6⇒360%）；#5 淬毒 能力伤害特攻 60%（限3⇒180%）→ 60%（限4⇒240%）；淬毒固有上限20层")
LOG.append("克劳斯 队长 #9 强化弹射 受到直击伤害2倍(15秒) 保持 1.4.196 实现；能力6 不动")

# ============================================================ 7) 碧安卡 119989 能力3：删除 独立乘区能力伤害行
rs = R(AB_LP, "1199893"); assert len(rs) == 6
eq(rs[2], 109, "154"); eq(rs[2], 113, "65000"); eq(rs[2], 102, "3")
eq(rs[5], 109, "412"); eq(rs[5], 113, "1500")
put(AB_LP, "1199893", rs[:5], rs[0])
override("desc_override_lady_summoner_campus_3", [("每层「焰域研修」使火属性角色能力伤害+65%、能力伤害额外乘区+1.5%（最多计3层）", "每层「焰域研修」使火属性角色能力伤害+65%（最多计3层）")])
LOG.append("碧安卡 能力3 #2 每层焰域研修 能力伤害 +65%（最多3层）与目标值一致不动；删除 #5 每层 独立乘区能力伤害 +1.5%")

# ============================================================ 8) 风巨蜥 149998
P = "battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_"
for lv in ("1", "2"):
    t = dsl(P + lv)
    fever = [c for pp, c in commands(t, "ConditionalsFeverMode")]; assert len(fever) == 1
    prob = [c for pp, c in commands(fever[0][1], "ConditionalsProbability")]; assert len(prob) == 1
    hits = list(commands(prob[0], "CreateNormalAttack")); assert len(hits) == 17, len(hits)
    tot = 0.0
    for pp, c in hits:
        assert c[1] >= 2200, c[1]
        for cell in c[6]:
            cell["min"] = round(cell["min"] * 0.5, 6); cell["max"] = round(cell["max"] * 0.5, 6)
        tot += c[6][0]["max"]
    assert abs(tot - 120.0) < 1e-6, tot  # 三个首领技各 40（满级），合计 120
    allh = list(commands(t, "CreateNormalAttack")); assert len(allh) == 25
    assert all(c[6] == [{"min": 2.25, "max": 3.0}] for pp, c in allh if c[1] < 2200)
LOG.append("风巨蜥 技能 Fever 随机首领技（重爪/巨型激光 8 段/全场旋风 8 段，每种满级合计 80）倍率 ×0.5 → 每种合计 40；技能1档 60→30、满级 80→40；非 Fever 8×3 倍不动；两档 DSL 同改")
rs = R(AB_LP, "1499986"); r = rs[2]; eq(r, 97, "4"); eq(r, 109, "412"); setv(r, [113, 114], "10000", "5000")
put(AB_LP, "1499986", rs, rs[0])
LOG.append("风巨蜥 能力6 #2 风共鸣 Fever中 风属性 独立乘区能力伤害(412) 10% → 5%")

# ============================================================ 9) 墨斯伊克 149997
rs = R(AB_LP, "1499972"); r = rs[4]; eq(r, 97, "9"); eq(r, 109, "413"); setv(r, [113, 114], "15000", "5000")
put(AB_LP, "1499972", rs, rs[0])
LOG.append("墨斯伊克 能力2 #4 攻击力提升状态中 独立乘区强化弹射伤害(413) 15% → 5%（during 9 为有/无判定，不按层叠加，表中「最大15%」无对应列）")
rs = R(AB_LP, "1499976"); r = rs[1]; eq(r, 97, "171"); eq(r, 102, "5"); eq(r, 109, "158"); setv(r, [113, 114], "8000", "2000")
put(AB_LP, "1499976", rs, rs[0])
LOG.append("墨斯伊克 能力6 #1 风蚀每1层 全队对其伤害特攻(158，乘区2) 8%（限5⇒40%）→ 2%（限5⇒10%）")

# ============================================================ 10) 斩铁 159998
ls = R(LE_LP, "159998"); assert len(ls) == 10
for i, kind in ((7, "32"), (8, "34"), (9, "694")):
    eq(ls[i], 25, "12"); eq(ls[i], 28, "25000000"); eq(ls[i], 32, "3"); eq(ls[i], 45, kind)
put(LE_LP, "159998", ls[:7], ls[0])
LOG.append("斩铁 队长 删除 #7-#9 光共鸣 每250连击 攻击力/技能伤害 +100%（最大300%）、独立乘区技能伤害 +10%（最大30%）")
rs = R(AB_LP, "1599983"); assert len(rs) == 7
for i, kind in ((1, "32"), (2, "34")):
    r = rs[i]; eq(r, 27, "12"); eq(r, 30, "25000000"); eq(r, 47, kind)
    setv(r, [34], "4", "5"); eq(r, 51, "12500"); eq(r, 52, "25000"); r[51], r[52] = "40000", "80000"
r = rs[3]; eq(r, 47, "694"); eq(r, 34, "5"); eq(r, 51, "1000"); eq(r, 52, "2000"); r[51], r[52] = "3000", "6000"
put(AB_LP, "1599983", rs, rs[0])
LOG.append("斩铁 能力3 #1/#2 每250连击 攻击力/技能伤害 +12.5%/+25%（低/满级，限4⇒满级100%）→ +40%/+80%（限5⇒满级400%）")
LOG.append("斩铁 能力3 #3 每250连击 独立乘区技能伤害(694，乘区7) +1%/+2%（限5）→ +3%/+6%（限5⇒满级30%）")


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
             "applies_on": "1.4.196", "version": "1.4.197", "requires_client": "纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
