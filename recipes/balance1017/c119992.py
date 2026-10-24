# -*- coding: utf-8 -*-
"""桂灯寻宝虎娘 米娅 119992 —— 平衡表 1017（来点关注谢谢喵 10-16 16:36）：能力2 加火属性共鸣；能力6 队长独立乘区 20%→10%，另加火属性共鸣 +10%。"""
import copy
from .common import *

def apply(F):
    ab2 = F.ab("1199922")
    for i, k in ((0, "32"), (1, "55")):
        r = ab2[i]
        assert r[27] == "2" and r[34] == "20" and r[47] == k and all(x in EMPTY or (c == 11 and x == "Red") for c, x in enumerate(r[6:27], 6)), (i, r[:53])
        gate(r, AB_P1, "Red")
    F.log("米娅 能力2：强化弹射时自身攻击力+10%（最大+200%）、强化弹射伤害+7.5%（最大+150%）—— 改为需火属性共鸣，数值不变")
    ab6 = F.ab("1199926")
    r = ab6[0]
    assert (r[6], r[47]) == ("42", "696")
    setv(r, [AB_IC_S1, AB_IC_S2], 20000, 10000)
    nr = copy.deepcopy(r)
    nr[6:13] = [""] * 7
    gate(nr, AB_P1, "Red")
    ab6.insert(1, nr)
    F.log("米娅 能力6：自身为队长时独立乘区强化弹射伤害 +20%→+10%；新增「火属性共鸣时，独立乘区强化弹射伤害+10%」（两条可叠加，队长且共鸣时合计仍是+20%）")
