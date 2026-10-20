# -*- coding: utf-8 -*-
"""别扭的吸血鬼伯爵 塞里奥尔 159985（crystal_swordman_halloween）—— 平衡表（罐头 10-18 11:23）「还是太弱了」。"""
import copy
from dsltools import commands
from common import *
from fw import UQ, rows, join

S = lambda v: [{"min": v, "max": v}]

def apply(F):
    # ---------- 技能
    for lv in ("1", "2"):
        t = F.dsl(f"battle/action/skill/action/rare5/crystal_swordman_halloween$crystal_swordman_halloween_{lv}")
        hit = {"ACPiercing": 0, "ACFlying": 0, "fixed900": 0}
        enh = None
        for pp, c in commands(t, "CreateCondition"):
            k = c[2][0]
            if k[0] in ("ACPiercing", "ACFlying") and k[1] == S(900):
                k[1] = S(1200); hit[k[0]] += 1
            elif k[0] == "ACFixedSpeed" and k[1] == S(900):
                k[1] = S(1200); hit["fixed900"] += 1
        assert hit == {"ACPiercing": 1, "ACFlying": 1, "fixed900": 1}, (lv, hit)
        ac = [c for pp, c in commands(t, "AddCombo")]
        assert len(ac) == 1 and ac[0][1] == S(20); ac[0][1] = S(40)
        flags = [c for pp, c in commands(t, "ConditionalsChangeSkillFlag")]
        assert len(flags) == 1
        on = flags[0][2][1]
        assert len(on) == 1 and on[0][1][2][0][0] == "ACFixedSpeed" and on[0][1][2][0][2] == S(3)
        def cc(cond):
            return ["Command", ["CreateCondition", 90, [cond], S(1), ["GenericConditionHitEffect"], False, False, "", None, False, 3, S(1), False]]
        on.append(["Command", ["FindAllSubjects", 90, 49, [], [], [], [], [], ["DoNothing"], ["Block", [
            cc(["ACToleranceOfElement", S(600), 5, S(-0.1), S(1)]),
            cc(["ACPowerFlipDamageResistance", S(600), S(-0.1), S(1)])]]]])
    F.log("塞里奥尔 技能『伯爵之礼』：最大速度固定、贯穿、浮游 持续 15秒→20秒（强化后的最大速度固定仍是25秒），连击 +20→+40")
    F.log("塞里奥尔 能力3 技能强化（队长为光属性时）：追加赋予全体敌人「伯爵的余韵」（10秒，不可消除）：光属性抗性-10%、强化弹射抗性-10%（固定最大速度已是3档，不变）")
    F.skill_text("159985", "crystal_swordman_halloween", [("（持续15秒，不可消除）", "（持续20秒，不可消除）"), ("连击+20", "连击+40")])
    # ---------- 能力1
    ab1 = F.ab("1599851"); r = ab1[0]
    assert r[47] == "55"; setv(r, [AB_IC_S1, AB_IC_S2], 150000, 200000)
    tpl = F.ab("1299523")[0]; assert tpl[47] == "252"
    n = copy.deepcopy(tpl); n[0], n[1], n[2] = r[0], r[1], r[2]
    n[27] = "65"; n[30] = n[31] = "100000"; n[35] = "180"; n[51] = n[52] = "50000"
    ab1.append(n)
    F.log("塞里奥尔 能力1：光属性共鸣时，光属性角色强化弹射伤害 +150% → +200%；新增「发动强化弹射Lv3时，对全体敌人造成自身攻击力0.5倍的光属性能力伤害（CT：3秒）」")
    F.cas_replace("desc_override_crystal_swordman_halloween_1", [(
        "光属性角色强化弹射伤害+150%",
        "光属性角色强化弹射伤害+200%\n发动强化弹射Lv3时，对全体敌人造成自身攻击力0.5倍的光属性能力伤害（CT：3秒）")])
    # ---------- 能力2
    ab2 = F.ab("1599852"); r = ab2[0]
    assert (r[27], r[34]) == ("2", "10"); setv(r, [AB_TRIG_TH1, AB_TRIG_TH2], 300000, 200000); setv(r, [AB_TRIG_LIMIT], 10, 15)
    c9 = copy.deepcopy(r); c9[6:13] = ["", "", "", "", "", "", ""]; gate(c9, AB_P1, "White")
    c9[27] = "65"; c9[30] = c9[31] = "100000"; c9[34] = "(None)"
    c9[47:53] = ["226", "", "", "", "900000", "900000"]
    ab2.append(c9)
    F.log("塞里奥尔 能力2：队长为光属性时，每发动3次强化弹射 → 每2次，光属性角色强化弹射伤害+10%（最多 10→15 次）；新增「光属性共鸣时，发动强化弹射Lv3时，连击+9」")
    F.cas_replace("desc_override_crystal_swordman_halloween_2", [(
        "每发动3次强化弹射，光属性角色强化弹射伤害+10%（最多10次）",
        "每发动2次强化弹射，光属性角色强化弹射伤害+10%（最多15次）\n光属性共鸣时，发动强化弹射Lv3时，连击+9")])
    # ---------- 能力3
    ab3 = F.ab("1599853"); r = ab3[0]
    assert (r[27], r[34], r[47], r[48]) == ("23", "2", "211", "1")
    r[27] = "65"; r[30] = r[31] = "300000"; r[34] = "(None)"; setv0(r, [AB_TRIG_CT], 360)
    r[48] = "5"; r[49] = ""; setv(r, [AB_IC_S1, AB_IC_S2], 30000, 10000)
    le2 = F.le("159985")[2]; assert (le2[95], le2[107]) == ("214", "23")
    def during(kind):
        d = ["crystal_swordman_halloween_3", "false", r[2], "0", ""] + list(le2[3:])
        assert len(d) == 126
        d[6:13] = ["0", "", "", "", "", "", ""]
        d[109] = kind; d[113] = d[114] = "0"
        return d
    ab3.append(during("46"))    # DirectAttack3（计算为3次，合计伤害+0%）
    ab3.append(during("25"))    # DebuffPrevent（免疫弱体）
    F.log("塞里奥尔 能力3（主位）：「队长为光属性时，自身发动技能时，除自身外的队伍角色技能槽+30%（最多2次）」→「每发动3次强化弹射Lv3，队伍全体技能槽+10%（CT：6秒）」；"
          "新增「最大速度固定期间，光属性角色直接攻击计算为3次，并免疫弱体效果」")
    F.cas_replace("desc_override_crystal_swordman_halloween_3", [
        ("队长为光属性角色时，自身发动技能时，除自身外的队伍角色技能槽+30%（最多2次）", "队长为光属性角色时，每发动3次强化弹射Lv3，队伍全体技能槽+10%（CT：6秒）"),
        ("延长并提升赋予的「固定最大速度」效果", "延长并提升赋予的「固定最大速度」效果，并赋予全体敌人「伯爵的余韵」（持续10秒，不可消除）：光属性抗性-10%、强化弹射抗性-10%\n"
         " <icon id='main'>  「固定最大速度」效果中，光属性角色直接攻击计算为3次，并免疫弱体效果")])
    F.cas_replace("change_skill_crystal_swordman_halloween", [("延长并提升赋予的「固定最大速度」效果", "延长并提升赋予的「固定最大速度」效果，并赋予全体敌人「伯爵的余韵」")])
    # ---------- 能力5
    ab5 = F.ab("1599855"); r = ab5[0]
    assert (r[27], r[35], r[47]) == ("23", "600", "629") and r[28] in EMPTY
    r[28] = "5"; r[29] = "White"; setv(r, [AB_TRIG_CT], 600, 420)
    cb = copy.deepcopy(r); cb[47:85] = ["226", "", "", "", "1000000", "1000000"] + [""] * 32
    ab5.append(cb)
    F.log("塞里奥尔 能力5：光属性共鸣时，自身发动技能时 → 光属性角色发动技能时，发动强化弹射Lv3（CT 10秒→7秒），并连击+10")
    F.cas_replace("desc_override_crystal_swordman_halloween_5", [("自身发动技能时，发动强化弹射Lv3（CT：10秒）", "光属性角色发动技能时，发动强化弹射Lv3（CT：7秒），连击+10")])
    F.cas_replace("ability_skill_crystal_swordman_halloween_pf3", [("CT：10秒", "CT：7秒")])
    # ---------- 能力6
    ab6 = F.ab("1599856")
    r = ab6[1]; assert (r[104], r[102]) == ("15998501", "10")
    setv(r, [AB_DC_S1, AB_DC_S2], 500, 100); setv(r, [AB_DT_LIMIT], 10, 50)
    c10 = copy.deepcopy(ab6[0]); assert (c10[27], c10[47]) == ("65", "461")
    c10[47:85] = ["226", "", "", "", "1000000", "1000000"] + [""] * 32
    ab6.append(c10)
    uv = F.table(UQ)["15998501"]; ur = rows(uv)[0]; assert ur[4] == "10"; ur[4] = "50"
    F.set_string(UQ, "15998501", join(ur) + ("\n" if uv.endswith("\n") else ""))
    F.log("塞里奥尔 能力6（主位）：光属性共鸣时，每发动1次强化弹射Lv3，光属性角色强化弹射伤害 +0.5% → +0.1%（独立伤害乘区5，最大+5%不变，层数上限 10→50），并连击+10")
    F.cas_replace("desc_override_crystal_swordman_halloween_6", [("光属性角色强化弹射伤害+0.5%（独立伤害乘区5）（最大+5%）", "光属性角色强化弹射伤害+0.1%（独立伤害乘区5）（最大+5%），连击+10")])
