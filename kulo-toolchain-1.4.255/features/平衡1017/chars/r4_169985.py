# -*- coding: utf-8 -*-
"""猎魔人装束的魔法剑士 莫弥亚 169985（blade_witch_halloween）—— 平衡表（罐头）「数值问题」。
- 技能吞噬：每个协力球 直击伤害 +100%→+60%（最大 +500%→+300%），攻击力 +60%（最大+300%）不变；新增：自身最大速度固定（20秒，1档），
  每吞噬1个协力球获得1层「猎魔标记」（新固有 16998501，永久，上限 111 层，图标借用万圣糖果标记）。
- 队长：连击召唤 CT 10→6 秒；新增协力球直接攻击伤害 +200%（照队长#2 协力球攻击力行，kind 33）。
- 能力2：贯穿中 暗属性角色及协力球攻击力 +100%→+150%。
- 能力3（主位）：原「场上每有1个协力球 充能+5%/攻击+20%（最多5个）」改为按「猎魔标记」层数：
  暗属性角色技能充能速度 +0.5%（最多12层=6%）、攻击力 +6%、直接攻击伤害 +6%（最多111层=666%）。
- 能力5 技能强化（吞噬每个 +3% 技能槽，最多15%）表里写的就是现状。"""
import copy
from dsltools import commands
from common import *
from fw import UQ, CAS, rows, join, leaf

UID = "16998501"

def apply(F):
    # ---- 固有状态「猎魔标记」
    uq = F.table(UQ)
    assert UID not in uq
    src = rows(uq["15998501"])[0]
    nr = list(src); nr[0] = "unique_halloween_hunter_mark"; nr[1] = "猎魔标记"
    nr[2] = "battle/common/unique_condition/unique_halloween_candy"; nr[3] = "99999999"; nr[4] = "111"
    F.set_string(UQ, UID, join(nr) + ("\n" if uq["15998501"].endswith("\n") else ""))
    # ---- 技能
    for lv in ("1", "2"):
        p = f"battle/action/skill/action/rare5/blade_witch_halloween$blade_witch_halloween_{lv}"
        t = F.dsl(p)
        blocks = []
        def walk(n):
            if isinstance(n, list):
                if len(n) == 2 and n[0] == "Command" and n[1][0] == "ConditionalsMultiballNumber":
                    blocks.append(n[1][4][1])
                for x in n: walk(x)
        walk(t)
        assert len(blocks) == 1, lv
        dev = blocks[0]
        dd = [c for c in dev if c[0] == "Command" and c[1][0] == "CreateCondition" and c[1][2][0][0] == "ACDirectDamage"]
        assert len(dd) == 1 and dd[0][1][2][0][2] == [{"min": 1.0, "max": 1.0, "mul": 1}]
        dd[0][1][2][0][2] = [{"min": 0.6, "max": 0.6, "mul": 1}]
        i = dev.index(dd[0])
        uniq = copy.deepcopy(dd[0]); uniq[1][2] = [["ACUnique", int(UID), [{"min": 1, "max": 1, "mul": 1}]]]; uniq[1][7] = ""
        fixed = copy.deepcopy(dd[0]); fixed[1][2] = [["ACFixedSpeed", [{"min": 1200, "max": 1200}], [{"min": 1, "max": 1}],
                                                     [{"min": 0, "max": 0}], [{"min": 1, "max": 1}]]]; fixed[1][7] = ""
        dev[i + 1:i + 1] = [fixed, uniq]
    F.log("莫弥亚 技能『猎魔人，出动！』吞噬协力球时：每个协力球自身直接攻击伤害 +100%→+60%（最大+300%），"
          "新增自身最大速度固定（持续20秒）与每个协力球1层「猎魔标记」")
    F.skill_text("169985", "blade_witch_halloween", [
        ("赋予自身直接攻击伤害提升＋攻击力提升效果（吞噬数量越多效果越高，最多计入5个，持续20秒），",
         "赋予自身直接攻击伤害提升＋攻击力提升＋最大速度固定效果（吞噬数量越多效果越高，最多计入5个，持续20秒），每吞噬1个协力球获得1层「猎魔标记」，")])
    # ---- 队长
    le = F.le("169985")
    r = le[0]; assert r[45] == "629"
    setv(r, [33], 600, 360)
    assert (le[2][45], le[2][46], le[3][45], le[3][46]) == ("32", "8", "33", "5")
    mb = copy.deepcopy(le[3]); mb[46] = "8"; mb[47] = ""
    le.insert(4, mb)
    F.log("莫弥亚 队长技：每30连击召唤南瓜 CT 10秒→6秒；新增暗属性共鸣时协力球直接攻击伤害+200%")
    F.cas_replace("desc_override_blade_witch_halloween", [
        ("（CT：10秒）", "（CT：6秒）"),
        ("暗属性共鸣时，暗属性角色直接攻击伤害+200%", "暗属性共鸣时，暗属性角色及协力球直接攻击伤害+200%")])
    F.cas_replace("ability_skill_blade_witch_halloween_combo_summon", [("CT：10秒", "CT：6秒")])
    # ---- 能力2
    for r in F.ab("1699852"):
        assert r[97] == "30"
        setv(r, [AB_DC_S1, AB_DC_S2], 100000, 150000)
    F.log("莫弥亚 能力2：贯穿效果中，暗属性角色及协力球攻击力 +100%→+150%")
    F.cas_replace("desc_override_blade_witch_halloween_2", [("攻击力+100%", "攻击力+150%")])
    # ---- 能力3
    ab3 = F.ab("1699853")
    assert len(ab3) == 2
    for r, (s, lim) in zip(ab3, ((5000, 12), (20000, 111))):
        assert r[97] == "208" and r[102] == "5"
        r[97] = "134"; r[102] = str(lim); r[104] = UID
    setv(ab3[0], [AB_DC_S1, AB_DC_S2], 5000, 500)
    setv(ab3[1], [AB_DC_S1, AB_DC_S2], 20000, 6000)
    d = copy.deepcopy(ab3[1]); d[109] = "1"
    ab3.append(d)
    F.log("莫弥亚 能力3（主位）：改为「猎魔标记」每1层，暗属性角色技能充能速度+0.5%（最大+6%）、攻击力+6%、直接攻击伤害+6%（最大+666%）"
          "（原为场上每有1个协力球，技能充能速度+5%、攻击力+20%，最多计入5个）")
    v = F.string(CAS, "desc_override_blade_witch_halloween_3")
    old = " <icon id='main'>  场上每有1个协力球，暗属性角色技能充能速度+5%、攻击力+20%（最多计入5个协力球）"
    assert rows(v)[0][0] == old, rows(v)[0][0]
    new = (" <icon id='main'>  自身每吞噬1个协力球获得1层「猎魔标记」，「猎魔标记」每1层，暗属性角色技能充能速度+0.5%（最大+6%）\n"
           " <icon id='main'>  「猎魔标记」每1层，暗属性角色攻击力+6%、直接攻击伤害+6%（最大+666%）")
    F.set_string(CAS, "desc_override_blade_witch_halloween_3", leaf(v, [[new]]))
