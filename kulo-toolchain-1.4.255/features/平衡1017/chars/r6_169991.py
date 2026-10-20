# -*- coding: utf-8 -*-
"""灯影戏兔的魔法师 蕾贝卡 169991（bearish_darkwitch_moon）—— 平衡表（Shazixnar 10-18 11:21）「技能给的抗性down太高」：
技能两档 暗属性抗性降低 28%/35% → 10%，全属性抗性降低 12%/15% → 10%。"""
from dsltools import commands

def apply(F):
    for lv, (d, a) in (("1", (-0.28, -0.12)), ("2", (-0.35, -0.15))):
        t = F.dsl(f"battle/action/skill/action/rare5/bearish_darkwitch_moon$bearish_darkwitch_moon_{lv}")
        seen = []
        for pp, c in commands(t, "CreateCondition"):
            k = c[2][0]
            if k[0] == "ACToleranceOfElement":
                exp = {255: d, 254: a}[k[2]]
                assert k[3] == [{"min": exp, "max": exp}], (lv, k)
                k[3] = [{"min": -0.1, "max": -0.1}]; seen.append(k[2])
        assert sorted(seen) == [254, 255], seen
    F.log("蕾贝卡 技能：命中敌人暗属性抗性降低 28%/35%（1档/＋档）→ 10%，全属性抗性降低 12%/15% → 10%")
