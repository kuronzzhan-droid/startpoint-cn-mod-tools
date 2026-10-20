# -*- coding: utf-8 -*-
"""护花使龙 休尔特 141099 —— 平衡表（水鱼）「刀一点」，作用在 1.4.225 之上。
队长技：强化弹射伤害 +15%（最大+150%）→ +30%（最大+150%，即 5 次）；能力5/6：删 225 新加的强化弹射伤害 +12% 行；
旋风：龙卷 ×15→×3、台风 ×30→×5。"""
from dsltools import commands
from common import *

P = "battle/action/skill/action/ability_skill/ability_skill_wind_dragon_wt22_ol_typhoon$ability_skill_wind_dragon_wt22_ol_typhoon"
NEW = {15.0: 3.0, 30.0: 5.0}

def apply(F):
    r = F.le("141099")[4]
    assert r[1] == "1" and r[45] == "55" and r[32] == "10"
    setv(r, [49], 11250, 22500); setv(r, [50], 15000, 30000); setv(r, [32], 10, 5)
    F.log("休尔特（超限后）队长技：每2次强化弹射 风属性角色强化弹射伤害 +15%（最大+150%）→ +30%（最大+150%）；攻击力 +40% 不变")
    for k in ("1410995", "1410996"):
        ab = F.ab(k)
        assert len(ab) == 3 and ab[2][3] == "1" and ab[2][4] == "1" and ab[2][47] == "55" and ab[2][52] == "12000"
        del ab[2]
    F.log("休尔特（超限后）能力5、能力6：去掉 1.4.225 新加的「强化弹射伤害+12%（最大+60%）」，只保留自身攻击力 +12%（最大+60%）")
    t = F.dsl(P)
    seen = {15.0: 0, 30.0: 0}
    for pp, c in commands(t, "CreateNormalAttack"):
        v = c[6]
        assert len(v) == 1 and v[0]["min"] == v[0]["max"] and v[0]["min"] in NEW, v
        seen[v[0]["min"]] += 1
        c[6] = [{"min": NEW[v[0]["min"]], "max": NEW[v[0]["min"]]}]
    assert seen == {15.0: 36, 30.0: 3}, seen
    F.log("休尔特 超限觉醒后的龙卷与台风：每道龙卷 ×15→×3，每圈台风 ×30→×5（1.4.225 刚加到 ×15/×30）")
