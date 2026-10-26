# -*- coding: utf-8 -*-
"""纯白誓约的骑士 杰拉尔 129992 —— 平衡表 1017（PPPP）：能力6「直击一次连击+5」删除，搬到队长技并加 CT 0.5 秒。
队长 leader 行 = ability 行去掉 c1(unisonable)、c2(类别) 两列（124 = 126 - 2）。触发 20=MemberDirectAttack、来源 0=Myself 照原行；
队长表里 trigger 20 有官方先例（261053#1 等 9 行）。"""
from .common import *

def apply(F):
    ab = F.ab("1299926")
    assert len(ab) == 2
    src = ab[0]
    assert (src[6], src[11], src[27], src[47], src[51], src[52]) == (
        "2", "Blue", "20", "226", "500000", "500000") and src[28] in EMPTY and src[35] in EMPTY, src[:53]
    del ab[0]
    F.log("杰拉尔 能力6：删除「水属性共鸣时，直接攻击1次时连击+5」（原来副位时会被主位角色的直击触发）")
    le = F.le("129992")
    assert len(le) == 9 and le[8][45] == "722"
    nr = [ "unicorn_lancer_rose" ] + list(src[3:])
    assert len(nr) == 124
    assert nr[25] == "20" and nr[33] in EMPTY
    nr[33] = "30"   # cooltime 30 帧 = 0.5 秒
    le.insert(8, nr)
    F.log("杰拉尔 队长技：新增「水属性共鸣时，自身每直接攻击1次，连击+5（CT 0.5秒）」")
