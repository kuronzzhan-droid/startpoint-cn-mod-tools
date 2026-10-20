# -*- coding: utf-8 -*-
"""1.4.243 修复：对象=队伍全体(5)但角色组列为空串 → 客户端解析为 null 组，面板显示「null角色」且没人能匹配、效果不生效。官方写 (None)。
范围：协调者转来的清单 + 本人扫描（129989 水杰拉德由其线程自修，不碰）。"""
from common import *

AB_FIX = {"1599853": [(0, 48, 49)], "1599911": [(2, 110, 111), (3, 110, 111), (4, 110, 111)]}
LE_FIX = {"149998": [(5, 46, 47), (6, 46, 47)], "159992": [(3, 46, 47), (5, 46, 47)]}

def apply(F):
    F.owner = "r9_null"
    for tbl, fix, get in (("AB", AB_FIX, F.ab), ("LE", LE_FIX, F.le)):
        for k, items in fix.items():
            rs = get(k)
            for i, tc, gc in items:
                r = rs[i]
                assert r[tc] == "5" and r[gc] == "", (tbl, k, i, r[tc], r[gc])
                r[gc] = "(None)"
    F.log("修复「赋予全队」对象的角色组为空导致面板显示 null 角色、效果不生效：塞里奥尔能力3（每3次强化弹射全队技能槽+10%）、"
          "1599911 能力（Fever中全队攻击力/能力伤害/直击伤害）、风巨蜥 149998 队长技第6/7条、159992 队长技第4/6条，角色组改为不限（(None)）")
    F.owner = None
