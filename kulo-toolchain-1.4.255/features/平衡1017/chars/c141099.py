# -*- coding: utf-8 -*-
"""护花使龙 休尔特 141099（wind_dragon_wt22）—— 用户 10-17「旋风倍率太低了加个0」。
超限觉醒后 PF 命中触发的龙卷/台风序列（1.4.208 上线，DSL ability_skill_wind_dragon_wt22_ol_typhoon）：
36 道龙卷 ×1.5 → ×15，3 个台风 ×3.0 → ×30。首撞爆发（PF 覆盖树里的 13/19.5/33）不在这棵树里，不动。"""
from dsltools import commands

P = "battle/action/skill/action/ability_skill/ability_skill_wind_dragon_wt22_ol_typhoon$ability_skill_wind_dragon_wt22_ol_typhoon"
NEW = {1.5: 15.0, 3.0: 30.0}

def apply(F):
    t = F.dsl(P)
    seen = {1.5: 0, 3.0: 0}
    for pp, c in commands(t, "CreateNormalAttack"):
        v = c[6]
        assert len(v) == 1 and v[0]["min"] == v[0]["max"] and v[0]["min"] in NEW, v
        seen[v[0]["min"]] += 1
        c[6] = [{"min": NEW[v[0]["min"]], "max": NEW[v[0]["min"]]}]
    assert seen == {1.5: 36, 3.0: 3}, seen
    F.log("休尔特 超限觉醒后强化弹射命中卷起的龙卷与台风：每道龙卷 ×1.5→×15（每圈 12 道、共三圈），每圈中心台风 ×3→×30；"
          "首撞爆发 13/19.5/33 不变")
