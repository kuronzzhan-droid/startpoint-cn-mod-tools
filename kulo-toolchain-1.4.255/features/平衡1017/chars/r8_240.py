# -*- coding: utf-8 -*-
"""平衡表 10-18 晚至 10-19 新块（1.4.240）：泽赫尔（水鱼）、克劳斯/贝尔赛蒂亚（P.P.P.P）、塞里奥尔（Shazixnar）、菲莉亚。"""
import copy
from dsltools import commands
from common import *
from fw import UQ, rows, join

S = lambda v: [{"min": v, "max": v}]


def _uq(F, uid, sid=None, name=None, dur=None, old_sid=None):
    uq = F.table(UQ)
    v = F.string(UQ, uid)
    r = list(rows(v)[0])
    if old_sid is not None:
        assert r[0] == old_sid, (uid, r[0])
    if sid is not None: r[0] = sid
    if name is not None: r[1] = name
    if dur is not None: r[3] = str(dur)
    F.set_string(UQ, uid, join(r) + ("\n" if v.endswith("\n") else ""))
    return r


def zeher(F):
    F.owner = "r8_159997"
    le = F.le("159997")
    assert len(le) == 9
    setv(le[0], [49, 50], 400000, 250000)
    assert (le[1][45], le[1][49]) == ("55", "200000")
    del le[1]                                            # 自身强化弹射伤害 → 能力2
    r = le[5]; assert (r[95], r[102], r[107]) == ("134", "1599971", "413")
    setv(r, [111, 112], 400, 100); setv(r, [100], 15, 60)
    ab2 = F.ab("1599972")
    assert len(ab2) == 2 and ab2[0][47] == "55"
    setv(ab2[0], [AB_IC_S1, AB_IC_S2], 50000, 25000)
    ab6 = F.ab("1599976")
    assert len(ab6) == 2 and ab6[1][47] == "55" and ab6[1][51] == "50000"
    moved = copy.deepcopy(ab6[1]); moved[0:5] = ab2[0][0:5]
    setv(moved, [AB_IC_S1, AB_IC_S2], 50000, 100000)
    ab2.append(moved)
    del ab6[1]
    ab1 = F.ab("1599971")
    for i in (2, 3):
        assert ab1[i][47] == "461"; setv(ab1[i], [AB_TRIG_CT], 300, 120)
    r = ab1[4]; assert r[104] == "1599971"
    setv(r, [AB_DC_S1, AB_DC_S2], 1000, 100); setv(r, [AB_DT_LIMIT], 10, 50)
    _uq(F, "159997", dur=480, old_sid="unique_guildknight_leader_tavern_lamp")
    ab3 = F.ab("1599973")
    assert len(ab3) == 7 and ab3[4][104] == "159997" and ab3[4][109] == "413" and ab3[6][109] == "23"
    r6 = ab3[6]; r6[109] = "413"; setv(r6, [AB_DC_S1, AB_DC_S2], 600, 100)
    del ab3[4]
    F.cas_replace("desc_override_guildknight_leader_tavern", [
        ("光属性角色攻击力+400%", "光属性角色攻击力+250%"),
        ("\n光属性共鸣时，自身强化弹射伤害+200%", ""),
        ("「灯芯」每1层，自身强化弹射伤害+0.4%（独立伤害乘区5）（最多15层）", "「灯芯」每1层，自身强化弹射伤害+0.1%（独立伤害乘区5）（最多60层）"),
        ("每达成15连击，自身攻击力+25%、强化弹射伤害+50%（最多10次）", "每达成15连击，自身攻击力+25%、强化弹射伤害+25%（最多10次）")])
    F.cas_replace("desc_override_guildknight_leader_tavern_2", [("效果写在队长技中", "光属性共鸣时，自身强化弹射伤害+100%")])
    F.cas_replace("desc_override_guildknight_leader_tavern_1", [
        ("（持续15秒），并累积1层「灯芯」（CT：5秒）", "（持续8秒），并累积1层「灯芯」（CT：2秒）"),
        ("「灯芯」每1层，自身强化弹射伤害+1%（独立伤害乘区5）（最多10层）", "「灯芯」每1层，自身强化弹射伤害+0.1%（独立伤害乘区5）（最多50层）")])
    F.cas_replace("desc_override_guildknight_leader_tavern_3", [
        ("自身处于「灯火正旺」状态时，自身强化弹射伤害+15%（独立伤害乘区5）",
         "自身处于「灯火正旺」状态时，每1连击，自身强化弹射伤害+0.1%（独立伤害乘区5）（最多55次）"),
        ("\n <icon id='main'>  自身处于「灯火正旺」状态时，每1连击，自身强化弹射伤害+0.6%（最多55次）", "")])
    F.cas_replace("desc_override_guildknight_leader_tavern_6", [("\n光属性共鸣时，自身强化弹射伤害+50%", "")])
    F.log("泽赫尔 队长技：光属性角色攻击力 +400%→+250%；「光属性共鸣时 自身强化弹射伤害」+200%→+100% 并移到能力2；"
          "「灯芯」每1层强化弹射伤害 +0.4%（最多15层）→+0.1%（最多60层，独立伤害乘区5）；每达成15连击 强化弹射伤害 +50%→+25%（攻击力+25%、最多10次不变）")
    F.log("泽赫尔 能力1：每达成55连击获得「灯火正旺」15秒→8秒、CT 5秒→2秒；「灯芯」每1层强化弹射伤害 +1%（最多10层）→+0.1%（最多50层，独立伤害乘区5）")
    F.log("泽赫尔 能力3：「灯火正旺」中强化弹射伤害 +15%（独立伤害乘区5）→ 每1连击+0.1%（独立伤害乘区5，最多55次）；删去「灯火正旺中每1连击强化弹射伤害+0.6%」")
    F.log("泽赫尔 能力6：删去「光属性共鸣时，自身强化弹射伤害+50%」")


def klaus(F):
    F.owner = "r8_129997"
    _uq(F, "12999702", sid="wfx:28:129997:9500:1:hidden_klaus_poison_reach",
        name="敌人「淬毒」等级达到1时，对其直接攻击的基础伤害变为2.5倍", old_sid="wfx:28:129997:2700:1:hidden_klaus_poison_reach")
    _uq(F, "12999703", sid="wfx:29:129997:5500:11:hidden_klaus_poison_layer",
        name="敌人「淬毒」等级从2级起每1级，对其直接攻击的基础伤害再+55%（最多10级）", old_sid="wfx:29:129997:300:11:hidden_klaus_poison_layer")
    p = "battle/action/skill/action/ability_skill/claude_wolf_assassin_ex$claude_wolf_assassin_ex_poison_hits"
    t = F.dsl(p)
    outer = t[11][1]
    assert len(outer) == 1 and outer[0][1][0] == "FindAllSubjects" and outer[0][1][1] == 10
    body = outer[0][1][9][1]
    assert body[0][1][0] == "BindConditionAccumulationVariable" and body[0][1][3] == ["DCUnique", 129997]
    party = body[1]
    assert party[1][0] == "FindAllSubjects" and party[1][1] == 11
    cc = party[1][9][1][0][1]
    ada = cc[2][0]
    assert ada[0] == "ACAdditionalDirectAttack" and ada[2][0]["vlv"][0]["vid"] == 1
    ada[2] = S(10)
    outer[0][1][9][1] = [["Command", ["ConditionalsConditionExist", 10, ["DCUnique", 129997], ["Block", [party]], ["Block", []]]]]
    F.cas_replace("claude_wolf_assassin_ex_poison_hits", [
        ("敌人的「淬毒」每2层，水属性角色直接攻击计算次数+1（按「淬毒」层数最多的敌人计算，最多计算为10次）",
         "敌人拥有「淬毒」时，水属性角色直接攻击计算次数+10")])
    F.log("克劳斯 队长技：「淬毒」等级达到1时全队对其直接攻击基础伤害 1.3倍→2.5倍，从2级起每级 +3%→+55%（最多10级）；"
          "直接攻击计算次数改为「敌人拥有淬毒时 +10」（原为每0.15秒按淬毒每2层+1、最多10次）")


def bel(F):
    F.owner = "r8_129952"
    _uq(F, "12995201", sid="wfx:24:2:5000:0:hidden_bel_weak_base",
        name="敌人弱体效果数量达到1时，自身对其直接攻击的基础伤害变为3倍", old_sid="wfx:24:2:9700:0:hidden_bel_weak_base")
    _uq(F, "12995202", sid="wfx:24:3:15000:6:hidden_bel_weak_each",
        name="敌人弱体效果数量从第2个起每多1个，自身对其直接攻击的基础伤害再+150%（最多5个）", old_sid="wfx:24:3:300:21:hidden_bel_weak_each")
    F.log("贝尔赛蒂亚 队长技：敌人弱体≥1时自身直击基础伤害 2倍→3倍；从第2个起每个 +3%（最多20个）→+150%（最多5个）")


def serio(F):
    F.owner = "r8_159985"
    r = F.ab("1599853")[0]
    assert (r[27], r[30], r[35], r[47]) == ("65", "300000", "360", "211")
    r[27] = "2"; setv(r, [AB_TRIG_CT], 360, 180)
    for lv in ("1", "2"):
        t = F.dsl(f"battle/action/skill/action/rare5/crystal_swordman_halloween$crystal_swordman_halloween_{lv}")
        hits = [c[2][0] for pp, c in commands(t, "CreateCondition") if c[2][0][0] == "ACFixedSpeed" and c[2][0][1] == S(1500)]
        assert len(hits) == 1 and hits[0][2] == S(3) and hits[0][3] == S(-0.55), hits
        hits[0][2] = S(4); hits[0][3] = S(-0.65)
    F.cas_replace("desc_override_crystal_swordman_halloween_3", [
        ("每发动3次强化弹射Lv3，队伍全体技能槽+10%（CT：6秒）", "每发动3次强化弹射，队伍全体技能槽+10%（CT：3秒）")])
    F.log("塞里奥尔 能力3：每发动3次强化弹射Lv3 → 每发动3次强化弹射，CT 6秒→3秒；技能强化的「固定最大速度」3档→4档（充能衰减 -55%→-65%）")


def filia(F):
    F.owner = "r8_159996"
    ab2 = F.ab("1599962")
    setv(ab2[0], [AB_IC_S1, AB_IC_S2], 6000, 3000); assert ab2[0][34] == "50"
    assert ab2[1][47] == "248"; setv(ab2[1], [AB_TRIG_CT], 600, 120)
    ab3 = F.ab("1599963")
    assert len(ab3) == 6 and ab3[0][47] == "724" and ab3[1][47] == "211" and ab3[1][48] == "2"
    setv(ab3[0], [AB_TRIG_CT], 600, 120)
    r = ab3[1]; setv(r, [AB_TRIG_CT], 600, 300); setv(r, [AB_IC_S1, AB_IC_S2], 5000, 10000); r[48] = "3"
    r2 = copy.deepcopy(r); r2[48] = "4"
    ab3.insert(2, r2)
    r = ab3[6]; assert (r[104], r[109]) == ("15999601", "23")
    r[109] = "413"; setv(r, [AB_DC_S1, AB_DC_S2], 100000, 10000)
    F.log("菲莉亚 能力2：每3次强化弹射 强化弹射伤害 +6%（最大+300%）→+3%（最大+150%）；强化弹射发动次数+2 的 CT 10秒→2秒")
    F.log("菲莉亚 能力3：强化弹射Lv3时 Fever槽+10% 的 CT 10秒→2秒；「队长技能槽+5%（CT 10秒）」→「除队长外的光属性角色技能槽+10%（CT 5秒）」；"
          "「风刃余势」期间 强化弹射伤害 +100% → +10%（独立伤害乘区5）")


def apply(F):
    zeher(F); klaus(F); bel(F); serio(F); filia(F)
    F.owner = None
