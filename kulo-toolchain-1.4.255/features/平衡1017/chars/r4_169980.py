# -*- coding: utf-8 -*-
"""深渊之兽 169980 —— 平衡表（来点关注谢谢喵 10-17 14:32）「统一伤害类型」：技能、觉醒·崩坏、眷属唤起 全部改按能力伤害结算。
写法同白/风巨蜥：根头 buffTargetAs → 102、全部判定区 params[23] → 102（完整能力伤害，测试服 APK 已带）。"""
from dsltools import commands

PROGS = ["battle/action/skill/action/rare5/abyss_beast_playable$abyss_beast_playable",
         "battle/action/skill/action/rare5/abyss_beast_playable$abyss_beast_playable_awaken",
         "battle/action/skill/action/rare5/abyss_beast_playable$abyss_beast_playable_familiar"]

def apply(F):
    for p in PROGS:
        t = F.dsl(p)
        assert t[10] == 2, (p, t[10])
        has = [c for pp, c in commands(t, "CreateHitArea")]
        assert has and all(c[24] == 0 for c in has), (p, [c[24] for c in has])
        for c in has:
            c[24] = 102
        t[10] = 102
    F.log("深渊之兽：技能『四相崩界』、队长技「觉醒·崩坏」、能力5「眷属唤起」的伤害全部改为按能力伤害结算")
    F.skill_text("169980", "abyss_beast_playable",
                 [("对命中的敌人造成暗属性伤害", "对命中的敌人造成暗属性伤害（伤害量以能力伤害判定）"),
                  ("最后以崩坏对全体敌人造成暗属性伤害", "最后以崩坏对全体敌人造成暗属性伤害（伤害量以能力伤害判定）")])
