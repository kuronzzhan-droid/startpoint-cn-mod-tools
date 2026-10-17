"""碧安卡的原生协力球支援桥；只返回数据，不读写角色包或 live。"""
from __future__ import annotations

from copy import deepcopy

from wf_campus_bianca_data import validate_row

CID = "119989"
CODE = "lady_summoner_campus"
SUPPORT_ABILITY_ID = "11998991"
SUMMON_UNIQUE_ID = 11998901
BREATH_UNIQUE_ID = 11998902
CHANGE_SKILL_STRING_ID = "change_skill_lady_summoner_campus_dragon"
UNIQUE_TABLE = "master/character/unique_condition.orderedmap"
POWER_UP_TABLE = "master/string/custom_ability_power_up_string.orderedmap"
ICON_SOURCE = "battle/common/unique_condition/unique_zeta.png"


def _row(source, key, index=0, **changes):
    row = deepcopy(source[key][index])
    if len(row) != 126:
        raise ValueError("native ability row must have 126 columns")
    row[0:5] = [CODE + "_dragon_bridge", "true", "attack_red", "0", ""]
    for column, value in changes.items():
        row[int(column[1:])] = str(value)
    validate_row(row, "ability")
    return row


def support_damage_rows(source):
    """由小龙监听主队标记，却把真能力攻击交给标记持有者发射。

    技能必须先给 owner+ID 选中的小龙 Member 赋同一吐息标记，等一帧，
    再给施法者 Member 赋标记，等两帧再移除小龙。187 前置只检查小龙
    自己的受命状态；185 只监听主队成员，故给龙受命不会自己造成攻击。
    I251 target=7 把攻击交给 triggerPuller，保留碧安卡自己的 ATK 和
    能力伤害加成；支援槽按 SLv 装载，不依赖任何玛纳板能力是否学会。
    """
    row = _row(source, "1310202", c6=187, c7=0, c12=BREATH_UNIQUE_ID,
               c27=185, c28=5, c29="(None)", c30=100000, c31=100000,
               c34="(None)", c35=0, c37=BREATH_UNIQUE_ID,
               c47=251, c48=7, c51=5000000, c52=5000000, c69="(None)")
    return {SUPPORT_ABILITY_ID: [row]}


def a1_enhancement_rows(source):
    """追加到 A1：火共鸣强化旗、吐息自充和队长限时攻击力。"""
    flag = _row(source, "1111773", 1, c70=CHANGE_SKILL_STRING_ID)
    # 2026-09-27 作者平衡第二批：吐息自充 50% → 20%（wf_balance_20260927b_bianca）。
    charge = _row(source, "1110211", c6=2, c9=600000, c10=600000, c11="Red",
                  c27=185, c28=0, c30=100000, c31=100000, c34="(None)",
                  c35=0, c37=BREATH_UNIQUE_ID, c51=20000, c52=20000)
    attack = _row(source, "1110211", 1, c6=2, c9=600000, c10=600000, c11="Red",
                  c27=185, c37=BREATH_UNIQUE_ID, c51=200000, c52=200000,
                  c57=90000000, c58=90000000)
    for row in (flag, charge, attack):
        row[0] = CODE + "_1"
        row[1] = "false"
    return [flag, charge, attack]


def unique_condition_rows():
    """标记均为 15 秒单层；185 按赋予次数而非层数变化触发。"""
    result = {}
    for uid, suffix, label in ((SUMMON_UNIQUE_ID, "summon", "幼龙回应"),
                               (BREATH_UNIQUE_ID, "breath", "幼龙吐息")):
        sid = f"campus_bianca_dragon_{suffix}"
        result[str(uid)] = [[sid, label, f"battle/common/unique_condition/{sid}",
                             "900", "1", "(None)", "(None)", "(None)", "(None)",
                             "false", "true", "0", "0", "true", "(None)"]]
    return result


def icon_reuse_paths():
    """目标逻辑路径 → 官方 48px 图标逻辑路径；复制存储字节即可。"""
    return {rows[0][2] + ".png": ICON_SOURCE
            for rows in unique_condition_rows().values()}


def power_up_string_rows():
    return {CHANGE_SKILL_STRING_ID: {"1": [[
        "强化幼龙吐息：降低全场敌人的能力伤害抗性，"
        "恢复自身技能槽，并提升队长攻击力。"
    ]]}}


def flat_string_rows():
    # ChangeSkillFlag always resolves this flat key, including at level 1.
    # The power-up table is an additional lookup, not a replacement.
    return {CHANGE_SKILL_STRING_ID: [[
        "强化幼龙吐息：额外赋予全场敌人能力伤害抗性降低效果"
    ]]}
