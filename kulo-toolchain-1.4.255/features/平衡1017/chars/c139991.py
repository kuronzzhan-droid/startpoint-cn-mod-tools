# -*- coding: utf-8 -*-
"""月下博饼的黑豹 黑 139991（outlaw_panther_moon）—— 平衡表（水鱼）：能力2 隐藏效果移到队长技；能力5 技能槽 25%→10%。
能力2#2「队长 且 雷·编成≥6：技能命中(限3次)→自身攻击力+45%」搬进队长技（leader = ab[0] 改键名 + ab[3:]），
去掉「队长」前置（在队长表里本来就只对队长生效），雷共鸣前置挪到 precondition1。队长面板第4行本来就写着这条。"""
from common import *

def apply(F):
    ab2 = F.ab("1399912")
    r = ab2[2]
    assert (r[6], r[13], r[18], r[27], r[34], r[47], r[52]) == ("42", "2", "Yellow", "107", "3", "32", "45000"), r[:53]
    del ab2[2]
    nr = ["outlaw_panther_moon"] + list(r[3:])
    assert len(nr) == 124
    blk2 = nr[LE_P2:LE_P2 + 7]
    nr[LE_P1:LE_P1 + 7] = blk2
    nr[LE_P2:LE_P2 + 7] = ["0", "", "", "", "", "", ""]   # 原队长前置（kind 42）丢弃，precondition2 置空
    assert (nr[4], nr[7], nr[9]) == ("2", "600000", "Yellow") and nr[25] == "107"
    le = F.le("139991")
    assert len(le) == 5
    le.insert(4, nr)
    F.log("黑 能力2：去掉「自身为队长、雷属性共鸣时，技能每命中1次自身攻击力+45%（最多3次）」；"
          "队长技新增同一条「雷属性共鸣时，自身技能每命中1次，自身攻击力+45%（最多3次，最大+135%）」（队长面板原本就写着这条）")
    r = F.ab("1399915")[0]
    assert (r[27], r[47]) == ("10", "211")
    setv(r, [AB_IC_S1, AB_IC_S2], 25000, 10000)
    F.log("黑 能力5：击败敌人时雷属性角色技能槽 +25%→+10%，连击+50 不变")
    F.cas_replace("desc_override_outlaw_panther_moon_5", [("雷属性角色技能槽＋25%", "雷属性角色技能槽＋10%")])
