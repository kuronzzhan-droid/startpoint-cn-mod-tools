# -*- coding: utf-8 -*-
"""碧海的龙王 赛瑞斯 129999 —— 平衡表 1017（PPPP 10-16 10:17）：能力1「非FEVER中发动技能时 FEVER槽+35%」加水属性共鸣。"""
from .common import *

def apply(F):
    r = F.ab("1299991")[2]
    assert (r[6], r[27], r[47], r[52]) == ("186", "23", "724", "35000"), r[:53]
    gate(r, AB_P1, "Blue", AB_P2)
    assert (r[6], r[13]) == ("2", "186")
    F.log("赛瑞斯 能力1：「非FEVER模式中发动技能时，FEVER槽+35%」改为需水属性共鸣（水属性编成≥6）才生效，数值不变")
    F.cas_replace("desc_override_seris_dragon_king_1", [
        ("非FEVER模式中，发动技能时，FEVER槽＋35％", "水属性共鸣时，非FEVER模式中，发动技能时，FEVER槽＋35％")])
