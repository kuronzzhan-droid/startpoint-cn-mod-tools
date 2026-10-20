# -*- coding: utf-8 -*-
"""雷雨的夏日公主 莉莉丝 139997 —— 平衡表 1017（PPPP 10-17 4:26）：队长技、能力1、能力2 加雷属性共鸣并下调。"""
from common import *

def apply(F):
    le = F.le("139997")
    for i, k, o, n in ((1, "388", 450000, 400000), (2, "32", 250000, 150000)):
        r = le[i]
        assert r[45] == k and all(x in EMPTY for x in r[4:25]), (i, r[:50])
        gate(r, LE_P1, "Yellow")
        setv(r, [49, 50], o, n)
    F.log("莉莉丝 队长技：雷属性角色能力伤害 +450%→+400%、攻击力 +250%→+150%，并改为需雷属性共鸣")
    ab1 = F.ab("1399971")
    r = ab1[0]
    assert r[47] == "211" and all(x in EMPTY for x in r[6:27])
    gate(r, AB_P1, "Yellow")
    r = ab1[1]
    assert r[47] == "388" and all(x in EMPTY for x in r[6:27])
    gate(r, AB_P1, "Yellow")
    setv(r, [AB_IC_S1], 100000, 75000); setv(r, [AB_IC_S2], 200000, 150000)
    F.log("莉莉丝 能力1：战斗开始时自身技能槽+50%、雷属性角色能力伤害+200%→+150% —— 两条都改为需雷属性共鸣")
    ab2 = F.ab("1399972")
    for i, k, o, n in ((1, "154", 200000, 150000), (2, "0", 200000, 100000), (3, "23", 200000, 100000)):
        r = ab2[i]
        assert r[97] == "227" and r[109] == k and all(x in EMPTY for x in r[6:27]), (i, r[:115])
        gate(r, AB_P1, "Yellow")
        setv(r, [AB_DC_S1, AB_DC_S2], o, n)
    F.log("莉莉丝 能力2：生命值50%以下时 自身能力伤害 +200%→+150%、攻击力 +200%→+100%、强化弹射伤害 +200%→+100%，并改为需雷属性共鸣")
