# -*- coding: utf-8 -*-
"""角色平衡 1008d（芙拉菲修正/索恩/杰拉德/稻穗/魔王/杰拉尔/黑；旧注：杰拉德 149999 / 稻穗 159991 / 白 149990 / 罗尔夫 179999），叠加在 kulo 1.4.158 视图上。
spec：research/balance_sheet_20261008.md。「去掉」= 删行（被删行均不是各键首行，或首行删除后新首行 c1/c2 不变，已断言）。
用法：WF_TIP=184 python balance_1008.py
"""
import copy
import hashlib
import json
import os
import zipfile

os.environ.setdefault("WF_TIP", "184")
from live149 import *  # noqa
from layout import col
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands, get

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.183-1.4.184-1-balance-1008d-local.zip"
AB_LP, LE_LP = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"
CAS_LP, AS_LP = "master/string/custom_ability_string.orderedmap", "master/skill/action_skill.orderedmap"
TX_LP, U_LP = "master/character/character_text.orderedmap", "master/character/unique_condition.orderedmap"
T = {lp: load(lp) for lp in (AB_LP, LE_LP, CAS_LP, AS_LP, TX_LP, U_LP)}
BASE = {lp: copy.deepcopy(v) for lp, v in T.items()}
DSL: dict[str, list] = {}
LOG: list[str] = []
NL = chr(10)


def leaf(v: str, rs):
    s = _csv(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


class Key:
    def __init__(self, lp, key):
        self.lp, self.key = lp, key
        self.rows = [r for r in rows(T[lp][key]) if r]
        self.drop = set()

    def r(self, i):
        return self.rows[i]

    def set(self, i, block, name, val, table="ability"):
        c = col(table, block, name)
        old = self.rows[i][c]
        self.rows[i][c] = str(val)
        LOG.append(f"{self.key}#{i} {block}.{name}: {old} → {val}")

    def remove(self, *idx):
        self.drop |= set(idx)

    def commit(self):
        keep = [r for i, r in enumerate(self.rows) if i not in self.drop]
        if 0 in self.drop:
            assert keep[0][1] == self.rows[0][1] and keep[0][2] == self.rows[0][2], (self.key, "c1/c2 改变")
        for i in sorted(self.drop):
            LOG.append(f"{self.key}#{i} 删除")
        T[self.lp][self.key] = leaf(T[self.lp][self.key], keep)


def text(lp, key, old, new, sub=None, colno=0):
    node = T[lp][key] if sub is None else T[lp][key][sub]
    rs = rows(node)
    rs = [r for r in rs if r]
    assert old in rs[0][colno], (key, sub, old)
    rs[0][colno] = rs[0][colno].replace(old, new)
    v = leaf(node, rs)
    if sub is None:
        T[lp][key] = v
    else:
        T[lp][key][sub] = v


def override(key, pairs):
    node = T[CAS_LP][key]
    s = rows(node)[0][0]
    for old, new in pairs:
        assert old in s, (key, old)
        s = s.replace(old, new)
    T[CAS_LP][key] = leaf(node, [[s]])


def dsl(program):
    if program not in DSL:
        DSL[program] = copy.deepcopy(dsl_tree(program))
    return DSL[program]


def delete_paths(tree, paths):
    for p in sorted(paths, reverse=True):
        parent = get(tree, p[:-1])
        del parent[p[-1]]


import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W

TOUCH_AB, TOUCH_LE = set(), set()


def R(lp, key):
    return [r for r in rows(T[lp][key]) if r]


def put(lp, key, rs, old0=None):
    if old0 is not None:
        assert rs[0][1:3] == old0[1:3], (key, "c1/c2")
    T[lp][key] = leaf(T[lp][key], rs)
    (TOUCH_AB if lp == AB_LP else TOUCH_LE).add(key)


def eq(r, c, v):
    assert r[c] == v, (r[0], c, r[c], v)


def scale_cna(tree, f, label):
    n = 0
    for pp, c in commands(tree, "CreateNormalAttack"):
        for cell in c[6]:
            for k in ("min", "max"):
                cell[k] = round(cell[k] * f, 6)
        n += 1
    LOG.append(f"{label}: CreateNormalAttack 倍率 ×{f:g}（{n} 处）")
    return n


# ============================================================ 芙拉菲 149987：能力6 → 队长技
CAP_P = "battle/action/skill/action/ability_skill/ability_skill_combat_animal_moon_charge_cap$ability_skill_combat_animal_moon_charge_cap"
rs = R(AB_LP, "1499876"); assert len(rs) == 3 and rs[1][47] == "629" and rs[2][47] == "35"
put(AB_LP, "1499876", rs[:1], rs[0]); LOG.append("芙拉菲 能力6 1499876 删除 1.4.182 加的 #1/#2，恢复原样")
del T[CAS_LP]["desc_override_combat_animal_moon_6"]; LOG.append("删除 desc_override_combat_animal_moon_6（恢复自动文案）")
ls = R(LE_LP, "149987"); assert len(ls) == 13
c1 = list(ls[1]); eq(c1, 45, "245")
a = list(c1)
a[25], a[26], a[28], a[29], a[33] = "0", "0", "100000", "100000", "36"
a[45], a[46], a[47], a[49], a[50] = "629", "0", "", "", ""
a[68], a[69] = "ability_skill_combat_animal_moon_charge_cap", CAP_P
b = list(ls[4]); eq(b, 25, "2"); eq(b, 45, "32")
b[25], b[26], b[28], b[29], b[32], b[33] = "23", "0", "100000", "100000", "99", "0"
b[45], b[46], b[47], b[49], b[50] = "35", "0", "", "10000", "10000"
ls += [a, b]; put(LE_LP, "149987", ls, ls[0])
LOG.append("芙拉菲 队长 149987 新增 #13：风共鸣 开局 → 629（自身 13999010×999 层 ⇒ v23 充能速度上限 999%）；#14：风共鸣 自身发动技能 → 自身充能速度 +10%（限 99 次）")
override("desc_override_combat_animal_moon", [("冲刺冷却时间进一步缩短", "冲刺冷却时间进一步缩短" + NL + "风属性共鸣时，自身技能充能速度上限提升至999%；自身发动技能时，自身技能充能速度+10%")])

# ============================================================ 索恩 159994
rs = R(AB_LP, "1599942"); eq(rs[0], 102, "4"); rs[0][102] = "6"; put(AB_LP, "1599942", rs, rs[0])
override("desc_override_tweyen_light_2", [("＋100%【最大+400%】", "＋100%（最大+600%）")])
rs = R(AB_LP, "1599944")
for r in rs:
    eq(r, 51, "15000"); r[51] = r[52] = "5000"
put(AB_LP, "1599944", rs, rs[0])
override("desc_override_tweyen_light_4", [("额外乘区＋15%", "额外乘区＋5%")])
LOG.append("索恩 能力2 弱体计数上限 4 → 6（最大 +600%）；能力4 麻痹/气绝/冻结特攻 15% → 5%")

# ============================================================ 杰拉德 149999
ls = R(LE_LP, "149999"); eq(ls[5], 45, "255"); eq(ls[5], 49, "1500000"); ls[5][49] = ls[5][50] = "300000"
put(LE_LP, "149999", ls, ls[0])
t = dsl("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift")
n = 0
for pp, c in commands(t, "CreateCondition"):
    for ac in c[2]:
        if ac[0] in ("ACAbilityDamageResistance", "ACDirectAttackDamageResistance"):
            assert ac[1] == [{"min": 900, "max": 900}] and ac[2] == [{"min": -0.05, "max": -0.05}]
            ac[1], ac[2] = [{"min": 1200, "max": 1200}], [{"min": -2.0, "max": -2.0}]; n += 1
assert n == 2
u = rows(T[U_LP]["1499990"])[0]; eq(u, 3, "900"); u[3] = "1200"; T[U_LP]["1499990"] = leaf(T[U_LP]["1499990"], [u])
override("ability_skill_gerald_time_rift", [("受到的能力伤害与直接攻击伤害增加5%（15秒）", "受到的能力伤害与直接攻击伤害增加2倍（20秒）")])
rs = R(AB_LP, "1499993"); eq(rs[1], 47, "255"); eq(rs[1], 51, "3500000"); rs[1][51] = rs[1][52] = "900000"
tpl = rs[3]; eq(tpl, 97, "4"); eq(tpl, 109, "46")
for kind in ("0", "1", "154"):
    nr = list(tpl); nr[109], nr[113], nr[114] = kind, "200000", "200000"; rs.append(nr)
put(AB_LP, "1499993", rs, rs[0])
rs = R(AB_LP, "1499994"); eq(rs[0], 47, "356"); eq(rs[0], 51, "1000000"); rs[0][51] = rs[0][52] = "200000"; put(AB_LP, "1499994", rs, rs[0])
LOG.append("杰拉德 队长 #5 直击35次全体 15倍 → 3倍（能力伤害归属保留）；时空裂痕 能力/直击伤害耐性 -5%(15秒) → -200%(20秒)，固有 1499990 时长 900→1200")
LOG.append("杰拉德 能力3 #1 PF Lv3 全体 35倍 → 9倍（归属保留）；新增 #7-#9 Fever 中光属性 攻击/直击伤害/能力伤害 +200%；能力4 冲刺 10倍 → 2倍")

# ============================================================ 稻穗 159991
rs = R(AB_LP, "1599911"); eq(rs[2], 47, "32"); eq(rs[3], 47, "388"); eq(rs[6], 109, "422")
moved = list(rs[6])
gtpl = R(AB_LP, "1499993")[3]
fev = []
for kind, v in (("0", "100000"), ("154", "300000"), ("1", "300000")):
    nr = list(gtpl); nr[0] = rs[0][0]; nr[1], nr[2] = rs[0][1], rs[0][2]
    nr[109], nr[110], nr[111], nr[113], nr[114] = kind, "5", "", v, v
    fev.append(nr)
rs = rs[:2] + fev + rs[4:6]
put(AB_LP, "1599911", rs, rs[0])
r2 = R(AB_LP, "1599912"); eq(r2[0], 47, "33"); eq(r2[1], 47, "693")
d1 = list(r2[1]); d1[6], d1[9], d1[10], d1[11], d1[51], d1[52] = "2", "600000", "600000", "White", "5000", "5000"
d2 = list(d1); d2[47] = "695"
moved[0] = r2[0][0]
put(AB_LP, "1599912", [d1, d2, moved], r2[0])
r3 = R(AB_LP, "1599913"); eq(r3[3], 47, "356"); eq(r3[3], 51, "1000000"); eq(r3[3], 35, "120")
r3[3][51] = r3[3][52] = "500000"; r3[3][35] = "30"; put(AB_LP, "1599913", r3, r3[0])
override("desc_override_cnmod_inaho_midautumn_1", [
    ("队伍全体攻击力＋50%、能力伤害＋50%", "Fever模式中，队伍全体攻击力＋100%、能力伤害＋300%、直接攻击伤害＋300%"),
    (NL + " <icon id='main'>  「月行」期间，自身冲刺冷却时间-30%", "")])
override("desc_override_cnmod_inaho_midautumn_2", [("队伍全体直接攻击伤害＋100%、对敌人造成的直接攻击伤害额外乘区＋15%",
          "光属性共鸣时，队伍全体对敌人造成的直接攻击伤害额外乘区＋5%、能力伤害额外乘区＋5%" + NL + " <icon id='main'>  「月行」期间，自身冲刺冷却时间-30%")])
override("desc_override_cnmod_inaho_midautumn_3", [("10倍威力的光属性能力伤害（冷却时间：2秒）", "5倍威力的光属性能力伤害（冷却时间：0.5秒）")])
LOG.append("稻穗 能力1 常驻 全队攻击/能力 +50% → Fever 中全队 攻击 +100%、能力伤害 +300%、直击伤害 +300%；「月行」冲刺冷却 -30% 移到能力2")
LOG.append("稻穗 能力2 全队直击 +100% / 直击独立乘区 15% → 光共鸣 全队 直击独立乘区 +5%、能力独立乘区 +5%（+ 月行行）；能力3 直击追击 10倍 CT2秒 → 5倍 CT0.5秒")

# ============================================================ 魔王 169995
ls = R(LE_LP, "169995"); eq(ls[0], 107, "421"); eq(ls[0], 111, "50000"); ls[0][111] = ls[0][112] = "25000"; put(LE_LP, "169995", ls, ls[0])
rs = R(AB_LP, "1699952")
for i in (0, 1, 2):
    eq(rs[i], 113, "15000"); rs[i][113] = rs[i][114] = "50000"
eq(rs[4], 109, "412"); rs[4][113] = rs[4][114] = "4000"
put(AB_LP, "1699952", rs, rs[0])
rs = R(AB_LP, "1699953")
eq(rs[2], 51, "100000"); rs[2][51] = rs[2][52] = "200000"
eq(rs[3], 51, "200000"); rs[3][51] = rs[3][52] = "300000"
eq(rs[4], 9, "9900000"); rs[4][9] = rs[4][10] = "2000000"; eq(rs[4], 51, "900000"); rs[4][51] = rs[4][52] = "600000"
eq(rs[5], 9, "9900000"); rs[5][9] = rs[5][10] = "2000000"; eq(rs[5], 51, "1800000")
for i in (2, 3, 4, 5):
    if rs[i][69] == "":
        rs[i][69] = "(None)"
LOG.append("魔王 能力3 #2-#5（255/256 能力伤害行）c69 空串 → (None)（官方写法；原值会被 parseAt69 读成 NaN，借改动顺手补齐）")
put(AB_LP, "1699953", rs, rs[0])
MP = "battle/action/skill/action/rare5/maou2_playable$maou2_playable_"
for nm, cnt in (("dash", 2), ("ability_followup", 3), ("meteor", 2)):
    assert scale_cna(dsl(MP + nm), 2.0, "魔王 " + nm) == cnt
eye = dsl(MP + "eye"); np_ = 0
for pp, c in commands(eye, "CreateCondition"):
    for ac in c[2]:
        if ac[0] == "ACPoison":
            assert ac[2] == [{"min": 3000.0, "max": 3000.0}]; ac[2] = [{"min": 6000.0, "max": 6000.0}]; np_ += 1
assert np_ == 1
LOG.append("魔王 队长 #0 魔王权能≥10 光/暗 独立乘区 50% → 25%")
LOG.append("魔王 能力1 虚空魔弹(dash) 倍率 ×2；诅咒魔眼(eye) 无直接伤害，唯一伤害项 中毒 3000 → 6000（×2）")
LOG.append("魔王 能力2 每层 攻/技伤/能伤 15% → 50%（限10 ⇒ 最大500%），能伤独立乘区 15% → 4%（最大40%）")
LOG.append("魔王 能力3 逆光魔弹(followup)/粉碎流星(meteor) 倍率 ×2；每1秒光 1→2倍；每2秒暗 2→3倍；权能≥99 → ≥20：每1秒光 9→6倍、每2秒暗 18倍保持")

# ============================================================ 杰拉尔 129992
US = "battle/action/skill/action/rare5/unicorn_lancer_rose$unicorn_lancer_rose_"
for lv, cnt in (("1", 3), ("2", 3)):
    assert scale_cna(dsl(US + lv), 2 / 3, "杰拉尔 技能 Lv" + lv) == cnt
text(AS_LP, "unicorn_lancer_rose", "合计60倍", "合计40倍", sub="1", colno=1)
text(AS_LP, "unicorn_lancer_rose", "合计75倍", "合计50倍", sub="2", colno=1)
text(TX_LP, "129992", "合计60倍", "合计40倍", colno=5)
text(TX_LP, "129992", "合计75倍", "合计50倍", colno=7)
ls = R(LE_LP, "129992")
eq(ls[0], 45, "721"); ls[0][49] = ls[0][50] = "20000"
eq(ls[1], 32, "10"); ls[1][32] = "5"
for i in (2, 3):
    eq(ls[i], 49, "300000"); ls[i][49] = ls[i][50] = "200000"
eq(ls[4], 45, "388"); ls = ls[:4] + ls[5:]
put(LE_LP, "129992", ls, ls[0])
r1 = R(AB_LP, "1299921"); eq(r1[0], 47, "629")
src = R(AB_LP, "1299922")[1]; eq(src, 47, "34")
nr = list(src); nr[0], nr[1], nr[2] = r1[0][0], r1[0][1], r1[0][2]
nr[6], nr[9], nr[10], nr[11] = "2", "600000", "600000", "Blue"
put(AB_LP, "1299921", [nr], r1[0])
r2 = R(AB_LP, "1299922"); eq(r2[3], 47, "388"); put(AB_LP, "1299922", r2[:3], r2[0])
LOG.append("杰拉尔 技能 Lv2 合计 75 → 50 倍（Lv1 60 → 40 倍，同比 ×2/3，连击加成不变）")
LOG.append("杰拉尔 队长 对决技伤独立乘区 50% → 20%；每50连击技伤 +100% 上限 10 次 → 5 次（最大500%）；水攻/技伤 300% → 200%，删除能力伤害 300%")
LOG.append("杰拉尔 能力1 发动技能 36倍能力追击 → 水共鸣 水属性技能伤害 +200%；能力2 删除能力伤害 +200%")

# ============================================================ 黑 139991
rs = R(AB_LP, "1399913"); eq(rs[0], 30, "4500000"); rs[0][30] = rs[0][31] = "50000000"; put(AB_LP, "1399913", rs, rs[0])
override("desc_override_outlaw_panther_moon_3", [("每达到45次", "每达到500次")])
LOG.append("黑 能力3 非Fever 直击合计 45 次 → 500 次 Fever +35%")


def main():
    files, probs = {}, []
    for lp in T:
        base, now = BASE[lp], T[lp]
        if now == base:
            continue
        data = q.build_node(now)
        back = q.parse_node(data)
        assert back == now
        lost = set(base) - set(back)
        assert lost <= {"desc_override_combat_animal_moon_6"}, (lp, lost)
        files[lp] = data
    for key in sorted(TOUCH_AB):
        for i, r in enumerate(R(AB_LP, key)):
            probs += [f"{key}#{i}: {p}" for p in L.client_legality_problems("ability", r)]
    for key in sorted(TOUCH_LE):
        for i, r in enumerate(R(LE_LP, key)):
            probs += [f"L{key}#{i}: {p}" for p in L.client_legality_problems("leader_ability", r)]
    for p, tree in DSL.items():
        probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
        files[wf_dsl.dsl_logical(p)] = encode_tree(tree)
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
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.183", "version": "1.4.184",
             "requires_client": "芙拉菲充能上限需 v23+；其余纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
