# -*- coding: utf-8 -*-
"""延续爱之龙 拉夫马诺 151159（golden_dragon_jr）—— 平衡表 1016：光·暗属性抗性降低满层 40% → 25%（仍 10 层）。
落点 = 觉醒技能『至天光辉＋＋』(golden_dragon_jr_3) 敌方减益判定区里两条 ACToleranceOfElement（元素 5=光 / 6=暗）。
层数上限 = AC 第 4 参 10；一次施加 2 层（CreateCondition magnification）；合计 = 每层强度 × min(累计层数, 10)。
"""
import math
from fw import commands

P3 = "battle/action/skill/action/rare5/golden_dragon_jr$golden_dragon_jr_3"
PATH = (11, 1, 4, 1, 3, 1, 0, 1, 23, 1)


def apply(F):
    t = F.dsl(P3)
    hits = []
    for pp, c in commands(t, "CreateCondition"):
        ac = c[2]
        if len(ac) == 1 and ac[0][0] == "ACToleranceOfElement" and ac[0][2] in (5, 6) and c[1] == 2:
            hits.append((pp, c))
    assert [h[0][:len(PATH)] for h in hits] == [PATH, PATH], [h[0] for h in hits]
    assert [h[1][2][0][2] for h in hits] == [5, 6]
    for pp, c in hits:
        a = c[2][0]
        assert a[1] == [{"min": 99999999, "max": 99999999}], a
        assert len(a[3]) == 1 and math.isclose(a[3][0]["min"], -0.04) and math.isclose(a[3][0]["max"], -0.04), a
        assert a[4] == [{"min": 10, "max": 10}], a          # 层数上限 10
        assert c[11] == [{"min": 2, "max": 2}], c[11]       # 一次 2 层
        a[3] = [{"min": -0.025, "max": -0.025}]
    # 其它等级技能（_1/_2 只有单光属性 3 层小减抗）不在表的范围内，不动
    F.log("拉夫马诺 觉醒技能『至天光辉＋＋』：光·暗属性抗性降低 每层 -4% → -2.5%（仍最多 10 层、每次施放叠 2 层），满层 40% → 25%")
