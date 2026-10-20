# -*- coding: utf-8 -*-
"""贝尔赛蒂亚 129952 队长技：敌人弱体≥1 时自身直接攻击计算次数+10，从第2个起每多1个+1（最多+5）。需 v35k（wfx 码 33）；旧客户端为普通固有状态、不生效不崩。"""
import copy
from common import *
from fw import UQ, rows, join

UID = "12995203"

def apply(F):
    F.owner = "r12_129952"
    uq = F.table(UQ)
    assert UID not in uq
    src = rows(uq["12995201"])[0]
    nr = list(src)
    nr[0] = "wfx:33:10:1:5:hidden_bel_weak_hits"
    nr[1] = "敌人弱体效果数量达到1时，自身对其直接攻击计算次数+10；从第2个起每多1个再+1（最多+5）"
    F.set_string(UQ, UID, join(nr) + ("\n" if uq["12995201"].endswith("\n") else ""))
    le = F.le("129952")
    tpl = [r for r in le if r[66] == "12995201"]
    assert len(tpl) == 1
    r = copy.deepcopy(tpl[0]); r[66] = UID
    le.append(r)
    F.log("贝尔赛蒂亚 队长技：新增敌人弱体效果数量达到1时，自身对其直接攻击计算次数+10；从第2个起每多1个再+1（最多+5）（需 v35k 客户端）")
    F.owner = None
