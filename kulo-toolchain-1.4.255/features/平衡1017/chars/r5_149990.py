# -*- coding: utf-8 -*-
"""盛夏白虎兽人 白 149990 —— 平衡表（Shazixnar 10-18 00:14）「小削一下伤害」：能力2 假日 Fever 中每1秒全体能力伤害 10倍(CT5秒) → 1倍（去掉 CT）。"""
from common import *

def apply(F):
    r = F.ab("1499902")[0]
    assert (r[27], r[30], r[47]) == ("248", "6000000", "254")
    setv(r, [AB_TRIG_CT], 300, 0)
    setv(r, [AB_IC_S1, AB_IC_S2], 1000000, 100000)
    F.log("白 能力2：Fever模式中处于「假日」时，每经过1秒对全体敌人造成自身攻击力 10倍（CT 5秒）→ 1倍（无CT，每秒都打）的风属性能力伤害")
    F.cas_replace("desc_override_white_tiger_summer_2", [
        ("每经过1秒，对全体敌人造成自身攻击力10倍的风属性能力伤害（CT：5秒）", "每经过1秒，对全体敌人造成自身攻击力1倍的风属性能力伤害")])
