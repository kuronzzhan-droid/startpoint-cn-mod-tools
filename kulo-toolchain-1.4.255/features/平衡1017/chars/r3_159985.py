# -*- coding: utf-8 -*-
"""塞里奥尔 159985（crystal_swordman_halloween）—— 平衡表（罐头）「加速效果不明显」。
技能强化分支（能力3 光队长时）给的「固定最大速度」：ACFixedSpeed [帧, 速度强度, 技能充能修正, ?] = [1500,1,0,1] → [1500,2,-0.4,1]。
速度强度 = 球速修正系数（客户端 BallImpl._getSpeedupCorrectionFactor，固定最大速度时直接取它）；
官方 silence_suzuka 两档：(1, -0.3)、(4, -0.65)，表要的「2档且衰减能量获取」按两点内插取 (2, -0.4)。普通分支 900 帧不动。"""
from dsltools import commands

def apply(F):
    for lv in ("1", "2"):
        p = f"battle/action/skill/action/rare5/crystal_swordman_halloween$crystal_swordman_halloween_{lv}"
        t = F.dsl(p)
        hits = []
        for pp, c in commands(t, "CreateCondition"):
            k = c[2][0]
            if k[0] == "ACFixedSpeed":
                hits.append(k)
        frames = sorted(k[1][0]["max"] for k in hits)
        assert frames == [900, 1500], (lv, frames)
        for k in hits:
            assert k[2] == [{"min": 1, "max": 1}] and k[3] == [{"min": 0, "max": 0}], k
            if k[1][0]["max"] == 1500:
                k[2] = [{"min": 2, "max": 2}]
                k[3] = [{"min": -0.4, "max": -0.4}]
    F.log("塞里奥尔 技能强化（能力3，队长为光属性时）：『伯爵之礼』给的「固定最大速度」从1档提升为2档，"
          "期间技能充能速度 -40%（普通版仍是1档、不影响充能）")
    for k in ("change_skill_crystal_swordman_halloween", "desc_override_crystal_swordman_halloween_3"):
        F.cas_replace(k, [("延长赋予的「固定最大速度」效果", "延长并提升赋予的「固定最大速度」效果")])
