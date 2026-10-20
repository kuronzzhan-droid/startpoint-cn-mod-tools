# -*- coding: utf-8 -*-
"""1.4.230：麻痹／气绝／追击 按客户端官方口径写清。底稿=1.4.229。
- kind 118 ParalysisSlayer → ConditionTargetKind.Paralysis，官方名 ability_description_condition_target_paralysis＝「麻痹・气绝效果」（乘区2）。
- kind 53 StunWinceSlayer＝追击伤害（乘区3），只在目标虚弱（isStunned）或畏缩时生效（NormalAttackCalculator.as:647-656），
  官方说明 trigger_enemy_disguise_stun_wince_slayer：「追击伤害提升」不论是否处于虚弱中都有效。"""
import re
from fw import CAS, rows, leaf

NOTE = "追击伤害（对虚弱中的敌人）"
REPL = [("对处于麻痹状态的敌人造成的伤害", "对麻痹·气绝效果中的敌人造成的伤害"), ("对处于「麻痹」状态的敌人伤害", "对麻痹·气绝效果中的敌人造成的伤害"),  # 官方游戏内原文格式
        ("自身眩晕积蓄+", "自身使敌人进入Down效果的容易程度+")]


def apply(F):
    n = 0
    for k in list(F.table(CAS)):
        if not k.startswith("desc_override_"): continue
        v = F.string(CAS, k); t = rows(v)[0][0]
        t2 = re.sub(r"追击伤害(?=[+＋-])", NOTE, t)
        for a, b in REPL: t2 = t2.replace(a, b)
        if t2 == t: continue
        F.set_string(CAS, k, leaf(v, [[t2]])); n += 1
    F.log(f"麻痹・气绝／追击伤害写法修正：{n} 个覆盖文案")
