# -*- coding: utf-8 -*-
"""传承心愿的冥龙 阿鲁玛德乌斯 261089（darkness_dragon）—— 平衡表 1016：光·暗属性抗性降低满层改为 30%（仍 10 层）。
落点 = 觉醒技能『魂魄终局＋＋』(darkness_dragon_3) 敌方块两条 ACToleranceOfElement（元素 6=暗 / 5=光）。
现值核对：每层 -3%、层数上限 10、一次 2 层 ⇒ 满层已经是 30%，与表的目标值一致 ⇒ 不改数据，只锁现值（见 c261089.md）。
_1/_2（未觉醒两档）没有任何抗性降低。
"""
import math
from fw import commands, dsl_tree

P = "battle/action/skill/action/rare4/darkness_dragon$darkness_dragon_"
PATH = (11, 1, 3, 1, 9, 1)
TARGET = -0.30


def apply(F):
    for lv in ("1", "2"):
        t = dsl_tree(P + lv)
        assert not [c for pp, c in commands(t, "CreateCondition")
                    if any(a[0] == "ACToleranceOfElement" for a in c[2])], lv
    t = dsl_tree(P + "3")
    hits = [(pp, c) for pp, c in commands(t, "CreateCondition")
            if len(c[2]) == 1 and c[2][0][0] == "ACToleranceOfElement"]
    assert [pp[:len(PATH)] for pp, c in hits] == [PATH, PATH], [pp for pp, c in hits]
    assert [c[2][0][2] for pp, c in hits] == [6, 5]
    for pp, c in hits:
        a = c[2][0]
        assert c[1] == 5 and a[1] == [{"min": 99999999, "max": 99999999}], a
        assert len(a[3]) == 1 and math.isclose(a[3][0]["min"], -0.03) and math.isclose(a[3][0]["max"], -0.03), a
        assert a[4] == [{"min": 10, "max": 10}] and c[11] == [{"min": 2, "max": 2}], (a, c[11])
        assert math.isclose(a[3][0]["max"] * a[4][0]["max"], TARGET)
    # 已等于目标值：不改、不写改动清单
