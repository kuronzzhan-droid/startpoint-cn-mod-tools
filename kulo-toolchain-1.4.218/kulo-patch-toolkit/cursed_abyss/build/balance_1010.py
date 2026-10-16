# -*- coding: utf-8 -*-
"""角色平衡 1010（腾讯表「以下为 1.4.184 之后新增」各块），叠加在 kulo 1.4.195 视图上 → 1.4.196。
spec：research/balance_sheet_20261010_raw.md。能力行=目标值；「去掉/删除」=删行；新增行一律 append 到键尾（rec#0 c1/c2 不变，已断言）。
用法：WF_TIP=195 python balance_1010.py
"""
import copy
import hashlib
import json
import os
import zipfile

os.environ.setdefault("WF_TIP", "195")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands

import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.195-1.4.196-1-balance-1010-local.zip"
AB_LP, LE_LP = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"
T = {lp: load(lp) for lp in (AB_LP, LE_LP, CAS_LP)}
BASE = {lp: copy.deepcopy(v) for lp, v in T.items()}
DSL: dict[str, list] = {}
NEW_DSL: set[str] = set()
LOG: list[str] = []
NL = chr(10)
TOUCH = {AB_LP: set(), LE_LP: set(), CAS_LP: set()}


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


def scale_cna(tree, f, label):
    n = 0
    for pp, c in commands(tree, "CreateNormalAttack"):
        for cell in c[6]:
            for k in ("min", "max"):
                cell[k] = round(cell[k] * f, 6)
        n += 1
    LOG.append(f"{label}: CreateNormalAttack 倍率 ×{f:g}（{n} 处）")
    return n


# ============================================================ 1) 水灵幽魂 129998 能力5：冻结特攻 70% → 30%
rs = R(AB_LP, "1299985"); eq(rs[1], 47, "119"); setv(rs[1], [51, 52], "70000", "30000"); put(AB_LP, "1299985", rs, rs[0])
override("desc_override_ghost_girl_playable_5", [("水属性角色对冻结敌人的伤害+70%", "水属性角色对冻结敌人的伤害+30%")])
LOG.append("水灵幽魂 能力5 1299985#1 FrozenSlayer(119) 水属性 70% → 30%")

# ============================================================ 2) 克劳斯 129997 claude_wolf_assassin_ex
CL = "claude_wolf_assassin_ex"
# --- 队长：攻击力 +200% → 能力伤害 +200%；淬毒 攻击特攻行删除；淬毒 直击/能力 65%×3 → 60%×3（最大180%）；新增 强化弹射时 敌人受到直击伤害 2倍(15秒)
ls = R(LE_LP, "129997"); assert len(ls) == 10
eq(ls[1], 45, "32"); eq(ls[1], 49, "200000"); ls[1][45] = "388"
eq(ls[4], 107, "258"); eq(ls[5], 107, "159"); eq(ls[6], 107, "348")
for i in (5, 6):
    eq(ls[i], 100, "3"); setv(ls[i], [111, 112], "65000", "60000")
tpl = ls[9]; eq(tpl, 45, "629"); eq(tpl, 25, "77")
VULN = f"{CL}_poison_vuln"
VULN_P = f"battle/action/skill/action/ability_skill/{CL}${VULN}"
nr = list(tpl)
nr[25], nr[28], nr[29], nr[32], nr[33] = "2", "100000", "100000", "(None)", "0"
nr[68], nr[69] = VULN, VULN_P
ls = ls[:4] + ls[5:] + [nr]
put(LE_LP, "129997", ls, ls[0])
LOG.append("克劳斯 队长 #1 水属性 攻击力 +200% → 能力伤害 +200%（kind 32→388）；删除 #4 淬毒 攻击特攻 65%×3")
LOG.append("克劳斯 队长 #5/#6 淬毒 直击/能力伤害特攻 65% → 60%（限3 ⇒ 最大180%）")
LOG.append(f"克劳斯 队长 新增尾行：水共鸣 强化弹射时 → 629 {VULN}（全体敌人 直击伤害耐性 -100% 900帧 = 受到直击伤害 2倍 15秒）")
# 新 DSL：克隆时空裂痕，去 Fever 包装/演出/固有/能力耐性，只留 直击耐性 -1.0 / 900 帧
rift = copy.deepcopy(dsl_tree("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift"))
fever = rift[11][1][0]; assert fever[1][0] == "ConditionalsFeverMode"
find = fever[1][1][1][0]; assert find[1][0] == "FindAllSubjects" and find[1][1] == 0 and find[1][2] == 49
blk = find[1][9][1]; assert [c[1][0] for c in blk] == ["ShowEffect", "CreateCondition", "CreateCondition"]
cc = blk[2]; acs = cc[1][2]; assert [a[0] for a in acs] == ["ACAbilityDamageResistance", "ACDirectAttackDamageResistance"]
d = acs[1]; d[1] = [{"min": 900, "max": 900}]; d[2] = [{"min": -1.0, "max": -1.0}]
cc[1][2] = [d]
find[1][9][1] = [cc]
rift[11][1] = [find]
DSL[VULN_P] = rift; NEW_DSL.add(VULN_P)
assert VULN not in T[CAS_LP]
T[CAS_LP][VULN] = leaf(T[CAS_LP]["ability_skill_gerald_time_rift"], [["使全体敌人受到的直接攻击伤害增加为2倍（15秒）"]]); TOUCH[CAS_LP].add(VULN)
# --- 能力1：直击 +100% → +150%；攻击力 +100% → 能力伤害 +150%
rs = R(AB_LP, "1299971"); eq(rs[0], 47, "33"); eq(rs[1], 47, "32")
setv(rs[0], [51, 52], "100000", "150000"); rs[1][47] = "388"; setv(rs[1], [51, 52], "100000", "150000")
put(AB_LP, "1299971", rs, rs[0])
LOG.append("克劳斯 能力1 #0 水属性 直击伤害 100% → 150%；#1 攻击力 100% → 能力伤害 150%（kind 32→388）；冲刺/贯穿行不动")
# --- 能力2：每层淬毒 全伤害特攻 50%×20 → 直击伤害特攻 40%×10
rs = R(AB_LP, "1299972"); r = rs[1]; eq(r, 97, "171"); eq(r, 109, "158")
r[109] = "159"; setv(r, [102], "20", "10"); setv(r, [113, 114], "50000", "40000")
put(AB_LP, "1299972", rs, rs[0])
override(f"desc_override_{CL}_2", [("敌人每有1层「淬毒」，全队对其造成的伤害+50%（最多20层）", "敌人每有1层「淬毒」，全队对其造成的直接攻击伤害+40%（最多10层）"),
                                   ("强化中毒：技能与强化弹射附加的中毒伤害大幅提升", "强化中毒：中毒伤害大幅提升")])
LOG.append("克劳斯 能力2 #1 每层淬毒 全队 伤害特攻 50%（限20）→ 直击伤害特攻 40%（限10，kind 158→159）；强化中毒文案去「技能与强化弹射附加的」")
# --- 能力3（主位）：删 淬毒攻击特攻 250%/65%；新增 对淬毒敌人 能力伤害 +100%；淬毒 直击/能力 65%×3 → 50%×3；DA2 合计 +100% → +150%；中毒特攻 15% → 10%
rs = R(AB_LP, "1299973"); assert len(rs) == 6
eq(rs[0], 47, "520"); eq(rs[1], 109, "258"); eq(rs[2], 109, "159"); eq(rs[3], 47, "201"); eq(rs[4], 109, "348"); eq(rs[5], 47, "117")
old0 = rs[0]
na = list(rs[4]); na[0], na[1], na[2] = old0[0], old0[1], old0[2]
setv(na, [102], "3", "1"); setv(na, [113, 114], "65000", "100000")
for i in (2, 4):
    setv(rs[i], [113, 114], "65000", "50000")
setv(rs[3], [51, 52], "100000", "150000")
setv(rs[5], [51, 52], "15000", "10000")
rs = [na, rs[2], rs[3], rs[4], rs[5]]
put(AB_LP, "1299973", rs, old0)
LOG.append("克劳斯 能力3 删除 #0 淬毒(固有)攻击特攻 250% 与 #1 淬毒 攻击特攻 65%×3；新首行：持有淬毒的敌人 能力伤害特攻 +100%（during171 限1 → 348，c0-c2 沿用原首行）")
LOG.append("克劳斯 能力3 淬毒 直击/能力伤害特攻 65% → 50%（限3 ⇒ 最大150%）；DirectAttack2 合计伤害 +100% → +150%；中毒特攻 15% → 10%")
# --- 能力5：删连击两行 → 水属性角色直击每5次 水属性 直击伤害/能力伤害 +20%（限5 ⇒ 最大100%）
rs = R(AB_LP, "1299975"); assert len(rs) == 2 and rs[0][47] == rs[1][47] == "226"
old0 = rs[0]; new = []
for kind in ("33", "388"):
    r = list(old0)
    r[27], r[28], r[29], r[30], r[31], r[34], r[35] = "20", "7", "Blue", "500000", "500000", "5", "0"
    r[47], r[48], r[49], r[51], r[52] = kind, "5", "Blue", "20000", "20000"
    new.append(r)
put(AB_LP, "1299975", new, old0)
LOG.append("克劳斯 能力5 删除 技能发动 连击+10 / 冲刺 连击+5；改为 水属性角色直击每5次 → 水属性 直击伤害 +20%、能力伤害 +20%（各限5次 ⇒ 最大100%）")
# --- 能力6：删 攻击力 50%、技能发动 100倍/30倍；新增 自身直击15次 全体 50倍水属性能力伤害 CT5秒
rs = R(AB_LP, "1299976"); assert len(rs) == 4
eq(rs[1], 47, "32"); eq(rs[2], 47, "252"); eq(rs[3], 47, "264")
r = list(rs[2]); eq(r, 27, "23"); eq(r, 28, "0")
r[27], r[30], r[31], r[35] = "20", "1500000", "1500000", "300"
setv(r, [51, 52], "10000000", "5000000")
put(AB_LP, "1299976", [rs[0], r], rs[0])
LOG.append("克劳斯 能力6 保留 #0 技能槽 +50%；删除 #1 攻击力 +50%、#3 技能发动 30倍最大HP伤害；#2 技能发动 100倍 → 自身直击15次 50倍水属性能力伤害（CT 300帧=5秒）")

# ============================================================ 3) 拉夫马诺 151159 能力2 #3：暗属性角色受伤 Fever +300 → +100
rs = R(AB_LP, "1511592"); r = rs[3]; eq(r, 27, "21"); eq(r, 47, "213"); setv(r, [51, 52], "30000000", "10000000")
put(AB_LP, "1511592", rs, rs[0])
LOG.append("拉夫马诺 能力2 #3（觉醒替换·暗协力）暗属性角色每承受1次伤害 Fever +300 → +100")

# ============================================================ 4) 见岛勇希 129991 psychic_yuki_swim
rs = R(AB_LP, "1299912"); eq(rs[2], 47, "252"); eq(rs[2], 30, "7500000"); put(AB_LP, "1299912", rs[:2], rs[0])
LOG.append("见岛勇希 能力2 删除 #2 水共鸣 每75连击 全体 8倍水属性能力伤害")
rs = R(AB_LP, "1299913"); eq(rs[0], 47, "223"); setv(rs[0], [51, 52], "100000", "0"); put(AB_LP, "1299913", rs, rs[0])
LOG.append("见岛勇希 能力3（主位）#0 技能发动 15秒 ConditionDirectAttack2 合计伤害 +100% → +0%（2次判定保留）")
rs = R(AB_LP, "1299915")
for i, kind in ((0, "34"), (1, "32")):
    eq(rs[i], 47, kind); setv(rs[i], [34], "10", "2"); setv(rs[i], [51, 52], "10000", "25000")
put(AB_LP, "1299915", rs, rs[0])
LOG.append("见岛勇希 能力5 水属性角色发动技能 技能伤害/攻击力 +10%（限10 ⇒ 最大100%）→ +25%（限2 ⇒ 最大50%）")
rs = R(AB_LP, "1299916"); eq(rs[1], 47, "32"); eq(rs[1], 51, "50000"); setv(rs[1], [52], "100000", "50000"); put(AB_LP, "1299916", rs, rs[0])
LOG.append("见岛勇希 能力6 #1 水属性 攻击力 50%/100%（低/满级）→ 50%/50%")

# ============================================================ 5) 黑 139991 outlaw_panther_moon
rs = R(AB_LP, "1399912"); r = rs[1]; eq(r, 6, "187"); eq(r, 12, "13999102"); eq(r, 47, "32")
setv(r, [51, 52], "250000", "100000")
nd = list(r); nd[0], nd[1], nd[2] = rs[0][0], rs[0][1], rs[0][2]; nd[47] = "33"; nd[51] = nd[52] = "150000"
rs.append(nd); put(AB_LP, "1399912", rs, rs[0])
override("desc_override_outlaw_panther_moon_2", [("自身处于「豹步」状态时：雷属性角色攻击力＋250%", "自身处于「豹步」状态时：雷属性角色直接攻击伤害＋150%、攻击力＋100%")])
LOG.append("黑 能力2 #1 「豹步」中 雷属性 攻击力 +250% → +100%；新增尾行 #4「豹步」中 雷属性 直击伤害 +150%")
rs = R(AB_LP, "1399913"); r = rs[3]; eq(r, 47, "461"); eq(r, 68, "13999101"); setv(r, [30, 31], "50000000", "100000000")
put(AB_LP, "1399913", rs, rs[0])
override("desc_override_outlaw_panther_moon_3", [("雷属性角色每直击500次，自身「骰运」＋1层", "雷属性角色每直击1000次，自身「骰运」＋1层")])
LOG.append("黑 能力3 #3 雷属性角色直击每 500 次 → 每 1000 次 「骰运」+1；骰运6层 攻击力 +1000% 不变")

# ============================================================ 6) 魔王 169995：虚空魔弹/诅咒魔眼/逆光魔弹/粉碎流星 ×0.5
MP = "battle/action/skill/action/rare5/maou2_playable$maou2_playable_"
for nm, cnt in (("dash", 2), ("ability_followup", 3), ("meteor", 2)):
    assert scale_cna(dsl(MP + nm), 0.5, "魔王 " + nm) == cnt
np_ = 0
for pp, c in commands(dsl(MP + "eye"), "CreateCondition"):
    for ac in c[2]:
        if ac[0] == "ACPoison":
            assert ac[2] == [{"min": 6000.0, "max": 6000.0}]; ac[2] = [{"min": 3000.0, "max": 3000.0}]; np_ += 1
assert np_ == 1
assert not list(commands(dsl(MP + "eye"), "CreateNormalAttack"))
LOG.append("魔王 虚空魔弹(dash) / 逆光魔弹(ability_followup) / 粉碎流星(meteor) 倍率 ×0.5（回到 1.4.184 前）；诅咒魔眼(eye) 唯一伤害项 中毒 6000 → 3000")

# ============================================================ 7) 杰拉德 149999 时空裂痕 2倍 → 1倍（20秒）
t = dsl("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift"); n = 0
for pp, c in commands(t, "CreateCondition"):
    for ac in c[2]:
        if ac[0] in ("ACAbilityDamageResistance", "ACDirectAttackDamageResistance"):
            assert ac[1] == [{"min": 1200, "max": 1200}] and ac[2] == [{"min": -2.0, "max": -2.0}]
            ac[2] = [{"min": -1.0, "max": -1.0}]; n += 1
assert n == 2
override("ability_skill_gerald_time_rift", [("受到的能力伤害与直接攻击伤害增加2倍（20秒）", "受到的能力伤害与直接攻击伤害增加1倍（20秒）")])
LOG.append("杰拉德 时空裂痕 能力/直击伤害耐性 -200% → -100%（20秒不变）")


def main():
    files, probs = {}, []
    for lp in T:
        base, now = BASE[lp], T[lp]
        data = q.build_node(now)
        back = q.parse_node(data)
        assert back == now
        assert set(base) <= set(back), (lp, set(base) - set(back))
        added = set(back) - set(base)
        assert added <= {VULN}, added
        changed = sorted(k for k in base if back[k] != base[k])
        assert set(changed) | added == TOUCH[lp], (lp, set(changed) ^ TOUCH[lp])
        LOG.append(f"{lp}: 改动键 {changed} 新增键 {sorted(added)}；其余 {len(base) - len(changed)} 键逐字节相同")
        files[lp] = data
    for lp, tb in ((AB_LP, "ability"), (LE_LP, "leader_ability")):
        for key in sorted(TOUCH[lp]):
            for i, r in enumerate(R(lp, key)):
                probs += [f"{tb}:{key}#{i}: {p}" for p in L.client_legality_problems(tb, r)]
    for key in TOUCH[LE_LP] | TOUCH[AB_LP]:
        pass
    for p, tree in DSL.items():
        probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
        enc = encode_tree(tree)
        rt = wf_dsl.parse_dsl(__import__("zlib").decompress(enc, -15))["tree"]
        assert rt == tree, p
        files[wf_dsl.dsl_logical(p)] = enc
    # 629 行配 CAS 同键；DSL 路径存在于本包或视图
    for key in TOUCH[LE_LP]:
        for r in R(LE_LP, key):
            if r[45] == "629":
                assert r[68] in T[CAS_LP], r[68]
                assert r[69] in DSL or read_raw(wf_dsl.dsl_logical(r[69])), r[69]
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
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": sorted(wf_dsl.dsl_logical(p) for p in NEW_DSL),
             "applies_on": "1.4.195", "version": "1.4.196", "requires_client": "纯数据；直击段数沿用官方客户端逻辑", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
