# -*- coding: utf-8 -*-
"""猎魔人装束的魔法剑士 莫弥亚 169985 —— 平衡表（罐头 10-18 12:02）：吞噬协力球给的直接攻击伤害提升＋攻击力提升＋最大速度固定 从自身改为全队
（含协力球，选择器 33，同技能里贯穿的给法）。能力3「自身直接攻击基础伤害变为2倍…」要新客户端补丁，这次没做。"""
from dsltools import commands

def apply(F):
    for lv in ("1", "2"):
        t = F.dsl(f"battle/action/skill/action/rare5/blade_witch_halloween$blade_witch_halloween_{lv}")
        blocks = []
        def walk(n):
            if isinstance(n, list):
                if len(n) == 2 and n[0] == "Command" and n[1][0] == "ConditionalsMultiballNumber":
                    blocks.append(n[1][4][1])
                for x in n: walk(x)
        walk(t)
        assert len(blocks) == 1
        dev = blocks[0]
        moved = []
        for c in list(dev):
            if c[0] == "Command" and c[1][0] == "CreateCondition" and c[1][1] == -17 and c[1][2][0][0] in ("ACDirectDamage", "ACAttackPoint", "ACFixedSpeed"):
                moved.append(c)
        assert [m[1][2][0][0] for m in moved] == ["ACDirectDamage", "ACFixedSpeed", "ACAttackPoint"] or sorted(m[1][2][0][0] for m in moved) == ["ACAttackPoint", "ACDirectDamage", "ACFixedSpeed"], moved
        i = dev.index(moved[0])
        for m in moved:
            dev.remove(m); m[1][1] = 91
        dev.insert(i, ["Command", ["FindAllSubjects", 91, 33, [], [], [], [], [], ["DoNothing"], ["Block", moved]]])
    F.log("莫弥亚 技能『猎魔人，出动！』：吞噬协力球给的直接攻击伤害提升＋攻击力提升＋最大速度固定 从自身改为队伍全体及协力球（数值不变）")
    F.skill_text("169985", "blade_witch_halloween", [("赋予自身直接攻击伤害提升＋攻击力提升＋最大速度固定效果", "赋予队伍全体及协力球直接攻击伤害提升＋攻击力提升＋最大速度固定效果")])
