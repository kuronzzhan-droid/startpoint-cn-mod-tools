#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深渊武器的 629 InvokeSkill 载荷程序与文案键（装备主体安全版）。

纯数据模块：只返回 ActionDsl 树与字符串，不读 store、不写盘、不发布。

深渊·轰电战锤 8000106「自身发动技能时，立即获得强化弹射效果」（作者 2026-09-28）：
机制照自制角色澄波响 169988 队长技第 5 行（瞬发触发 23 SkillInvoke + 内容 629 InvokeSkill，
文案「立即获得强化弹射效果」）——载荷树在球的位置按强化弹射 Lv3 结算 3 段 19.2 倍 + 1 段 43.2 倍。
树形与 169988 的 ``ability_skill_psychic_teleport_moon_pf`` 逐节点相同（其来源是官方
``special_lv3`` 的 ``CollisionOfBallAndEnemy`` 命中块，见 wf_midautumn_kit_hibiki.build_invoke_tree），
只改两处，理由都是「装备词条的 DSL 主体恒为无属性（ownerElement=6）」：

1. ``CreateNormalAttack`` 元素 255（继承）→ **3**（显式雷属性；DSL 显式元素码 1-based＝内部元素+1，
   ``ActionEvaluationResolver.resolveElement``）。继承在装备上会解析成无属性，打不出雷属性伤害。
2. 命中特效 ``Fine`` → ``Explosion``：``ActionDslAssetResolver.resolveNormalAttackHitEffect``
   对 Fine/Coarse/Slash/CriticalSlash 按属性取素材，无属性直接抛 C10013（1.4.1057 终焉拳套实机）；
   Explosion 走固定素材 ``battle/effect/hit/normal_damage/explosion/explosion``，任何属性都安全。

根头 ``tree[10]`` = 133（``wf_battle_rules.segment_override("pf3")``）：damage-type-rules-v1 按强化弹射
Lv3 完整结算（通用强化弹射池、分档、413 独立乘区）；未装该补丁的客户端读成 0，按技能伤害结算，不崩。
这些命中计为真实 PF Lv3 命中 ⇒ 不能再用「强化弹射命中」类触发（183 LvAny、182 Lv3、15/16/17 PowerFlipHitLvNHigh，
见 ``wf_battle_rules.PF_SEGMENT_HIT_TRIGGERS``）触发本树（自我连锁），只能挂技能发动(23)。
"""
from __future__ import annotations

import copy

import wf_battle_rules as BR

#: 629 行 c67（custom_ability_string 键；缺键 = 详情页 C8601）与 c68（程序路径）。
THUNDER_HAMMER_PF_STRING = "ability_skill_abyss_thunder_hammer_pf"
THUNDER_HAMMER_PF_TEXT = "立即获得强化弹射效果"
THUNDER_HAMMER_PF_PROGRAM = (
    "battle/action/skill/action/ability_skill/abyss_weapon$abyss_thunder_hammer_pf"
)

#: DSL 显式元素码（1-based）：雷 = 内部 ElementKind 2 + 1。
THUNDER_DSL_ELEMENT = 3
#: 不按属性取素材的命中特效（装备主体无属性也不会 C10013）。
HIT_EFFECT = ["Explosion"]
#: 根头 buffTargetAs：按强化弹射 Lv3 结算（damage-type-rules-v1）。
PF3_BUFF_TARGET_AS = BR.segment_override("pf3")
#: 强化弹射段覆盖 131-133（segment_override pf1..pf3）→ 这类树的命中会驱动的「强化弹射命中」类瞬发触发；
#: 这些触发都不能用来触发打出这类命中的 629 树（门禁用 ``BR.pf_hit_triggers_driven_by(tree)``）。
PF_SEGMENT_HIT_TRIGGERS = BR.PF_SEGMENT_HIT_TRIGGERS
#: 与 169988 同倍率：官方 special_lv3 命中块 4× / 9× 各 ×4.8（作者 2026-09-24 定的 PF3 统一倍率）。
HIT_MULTIPLIERS = (19.2, 43.2)
HIT_COUNTS = (3, 1)
#: 每段削韧（CreateNormalAttack p13）：与 169988 第二批平衡口径相同，4 段合计 1。
HIT_DOWN = 0.25
PF_SPECIAL_EFFECT = (
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_three"
)

#: 本模块产出的全部 629 文案键（stage 脚本据此写 custom_ability_string）。
INVOKE_STRINGS = {THUNDER_HAMMER_PF_STRING: THUNDER_HAMMER_PF_TEXT}


def _slv(value) -> list[dict]:
    return [{"min": value, "max": value}]


def _normal_attack(subject: int, multiplier: float) -> list:
    return ["Command", [
        "CreateNormalAttack", subject, THUNDER_DSL_ELEMENT, [], [], 0,
        _slv(multiplier), _slv(0), False, False, False, False, False,
        _slv(HIT_DOWN), _slv(4.4), list(HIT_EFFECT), True,
    ]]


def _hit_area(lifetime: int, hits: int, area_id: int, hit_ids: tuple[int, int],
              multiplier: float) -> list:
    area_self, target = hit_ids
    return ["Command", [
        "CreateHitArea", "*", 1, ["AB"], 0, 0, 0, False, False,
        ["Circle", _slv(350)], ["Center"], ["Center"], ["Single"],
        ["SpecifyHitAreaLifetimeDirectly", lifetime],
        ["CalculatedUsingMaxNumOfHits", hits],
        ["None"], False, True, ["None"], area_id, ["Block", []], area_self, target,
        ["Block", [_normal_attack(target, multiplier), ["Command", ["ShakeCamera", 1]]]],
        0, 0, ["None"],
    ]]


def build_thunder_hammer_pf_tree() -> list:
    """8000106 的 629 载荷：球位置（主体 -18、坐标系 AB）两段判定，3×19.2 + 1×43.2，雷属性。"""
    first, second = HIT_MULTIPLIERS
    effect = ["Command", [
        "ShowEffect", "特殊演出", ["SpecifyEffectDirectly", PF_SPECIAL_EFFECT], 1,
        ["ForesideOfCharacter"], ["SpecifyEffectLifetimeDirectly", 30], ["AB"],
        0, 0, 0, True, True, ["Some", _slv(7)],
    ]]
    body = ["Block", [
        effect,
        _hit_area(22, HIT_COUNTS[0], 2, (3, 4), first),
        ["Event", ["Wait", 22, "*", ["Block", [
            _hit_area(7, HIT_COUNTS[1], 5, (6, 7), second),
        ]]]],
    ]]
    reference = ["Command", [
        "CreateReferencePoint", -18, ["AB"], 0, 0, 0, False, False, ["Single"], 30, 1, body,
    ]]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False,
            PF3_BUFF_TARGET_AS, ["Block", [reference]]]


#: 程序路径 → 构树函数（stage 脚本逐个编码为 ``<path>.action.dsl.amf3.deflate``）。
PROGRAMS = {THUNDER_HAMMER_PF_PROGRAM: build_thunder_hammer_pf_tree}


def build_programs() -> dict[str, list]:
    return {path: copy.deepcopy(build()) for path, build in PROGRAMS.items()}
