# -*- coding: utf-8 -*-
"""露迪 139985 —— 平衡表（罐头 10-18 11:23）能力1：新增「战斗开始时，自身技能槽+50%」。行照塞里奥尔能力4 那条（1599854#0）复制。
技能「全屏判定」没做（见说明）。"""
import copy
from common import *

def apply(F):
    ab = F.ab("1399851")
    assert len(ab) == 1
    tpl = F.ab("1599854")[0]
    assert tpl[47] == "211" and tpl[52] == "50000" and all(x in EMPTY for x in tpl[6:47])
    r = copy.deepcopy(tpl); r[0] = ab[0][0]; r[2] = ab[0][2]
    ab.insert(0, r)
    F.log("露迪 能力1：新增「战斗开始时，自身技能槽+50%」")
    F.cas_replace("desc_override_lady_android_halloween_1", [("雷属性共鸣时，雷属性角色每发动1次技能", "战斗开始时，自身技能槽+50%\n雷属性共鸣时，雷属性角色每发动1次技能")])
