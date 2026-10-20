# -*- coding: utf-8 -*-
"""露迪 139985（lady_android_halloween）—— 平衡表（罐头）「描述与机制修改」。
Fever 中对带标记敌人的落雷：原来「对迟缓中的敌人追加一段伤害」→ 改为「对迟缓中的敌人伤害提升」，
用 CreateNormalAttack 第4参（状态特攻目标）写 DCFrozen，加成固定 +25%（客户端 NormalAttackCalculator.CONDITION_SLAYER_BONUS=0.25，
官方雷龙 thunder_dragon 对麻痹同写法）。删掉追加段（ConditionalsConditionExist DCFrozen 整个节点）。
能力3/4 表里写的就是现状，不改；能力6「每层+%」表里没填数字，现状（每层伤害+5%，独立乘区9，最多3层）不动。"""
from dsltools import commands

def _strip_frozen_extra(node):
    """删掉 Block 里的 ConditionalsConditionExist(…, ["DCFrozen"], …) 节点，返回删除个数。"""
    n = 0
    if isinstance(node, list):
        for i in range(len(node) - 1, -1, -1):
            x = node[i]
            if (isinstance(x, list) and len(x) == 2 and x[0] == "Command" and isinstance(x[1], list)
                    and x[1][:1] == ["ConditionalsConditionExist"] and x[1][2] == ["DCFrozen"]):
                del node[i]; n += 1
            else:
                n += _strip_frozen_extra(x)
    return n

def apply(F):
    for lv, extra in (("1", (5, 6)), ("2", (6, 8))):
        p = f"battle/action/skill/action/rare5/lady_android_halloween$lady_android_halloween_{lv}"
        t = F.dsl(p)
        cnas = [c for pp, c in commands(t, "CreateNormalAttack")]
        assert len(cnas) == 2 and cnas[1][6] == [{"min": extra[0], "max": extra[1]}], [c[6] for c in cnas]
        main = cnas[0]
        assert main[3] == [] and main[4] == []
        assert _strip_frozen_extra(t) == 1
        main[4] = [["DCFrozen"]]
        assert len([1 for pp, c in commands(t, "CreateNormalAttack")]) == 1
    F.log("露迪 技能 Fever 中：对带「万圣糖果标记」敌人的落雷，原来对迟缓中的敌人追加一段伤害，改为对迟缓中的敌人伤害提升（+25%，与雷龙同一种加成）")
    F.skill_text("139985", "lady_android_halloween",
                 [("，对迟缓效果中的敌人追加雷属性伤害", "【对迟缓效果中的敌人伤害提升】")])
