"""校园希尔媞六能力的原生表行；纯函数，不读写角色包或 live。"""
from __future__ import annotations

from copy import deepcopy

from wf_celtie_fever_stock import (
    ABILITY_STOCK_ACTION_PATH,
    ABILITY_STOCK_STRING_ID,
    ABILITY_SPEND_ACTION_PATH,
    ABILITY_SPEND_STRING_ID,
    GAIN_UID,
    SPEND_MARKERS,
    STOCK_UID,
)

CID = "149989"
CODE = "wind_spgirl_campus"
CHANGE_SKILL_STRING_ID = "change_skill_wind_spgirl_campus_fever"
#: 2026-09-27 第三轮（c，口径 U5/U6）：能力1 末尾追加 I704 开关（技能旗号 2），前置42 仅队长 + 风共鸣，
#: 瞬发无触发（同形 live 先例罗尔夫中秋 1499866#4）；行级 c1='false'，与能力1 其余行一致（kitlib 一键 c1 一致约束）。技能树按旗号 2 撤掉心得 10 层封顶（wf_celtie_skill_growth）。
LEADER_UNCAP_STRING_ID = "change_skill_wind_spgirl_campus_leader"
SCALE = 100_000
#: 2026-09-27 第二批（口径 A3）：能力3「每层星风心得」换成有上限的弱化版——during 134
#: 限次 c102 = 10（官方 1611231..6 blackflower_wiz_smr22 同为 D134 + 限 10），
#: 能力伤害 25%→8%/层、攻击力 25%→5%/层；无上限的逐层成长搬进队长
#: （wf_celtie_fever_leader.GAIN_GROWTH_STRENGTH，每层 2.5%）。
GAIN_BONUS_LIMIT = 10
GAIN_BONUS_STRENGTH = {154: 8_000, 0: 5_000}


def _pre(row, kind=None, *, offset=6):
    row[offset:offset + 7] = ["0", "", "", "", "", "", ""]
    if kind == "wind":
        row[offset] = "2"
        row[offset + 3:offset + 5] = ["600000", "600000"]
        row[offset + 5] = "Green"
    elif kind in ("fever", "not_fever"):
        row[offset] = "12" if kind == "fever" else "186"
    elif kind == "leader":
        row[offset] = "42"
    elif kind is not None:
        raise ValueError(f"unsupported precondition: {kind}")


def _instant(source, content, strength=None, *, pre=None, fever=None,
             trigger=0, threshold=1, wind_counter=False, target=None,
             limit=None):
    # 最新原版希尔媞开局充能行提供原生 126 列与 Option 哨兵。
    row = deepcopy(source["1412011"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    row[0:6] = [CODE, "true", "special", "0", "", "0"]
    row[27:39] = [""] * 12
    row[47:85] = [""] * 38
    _pre(row, pre)
    _pre(row, fever, offset=13)
    _pre(row, offset=20)
    row[27], row[47] = str(trigger), str(content)
    if trigger:
        row[30:32] = [str(threshold * SCALE)] * 2
        row[34:36] = ["(None)" if limit is None else str(limit), "0"]
    if wind_counter:
        row[28:30] = ["7", "Green"]
    if target is not None:
        row[48] = str(target)
        if target == 5:
            row[49] = "Green"
    if strength is not None:
        row[51:53] = [str(strength)] * 2
    return row


def _fever_status(source, content, strength=None):
    row = _instant(source, content, strength, pre="wind", fever="fever",
                   trigger=248, threshold=300)
    row[57:61] = [str(60 * SCALE)] * 2 + [str(SCALE)] * 2
    row[62:66] = ["(None)"] * 4
    row[67], row[72] = "0", "false"
    if content == 688:
        # I688 applies to the player ball; I689 would affect a multiball.
        row[61] = "(None)"
    return row


def _stock_gain_bonus(source, content=154, strength=None, limit=GAIN_BONUS_LIMIT):
    """每层星风心得（D134）→ 风队 content；limit=None 即 c102 (None) 不设限（仅队长行用）。"""
    # Official 1610633 counts Unique layers through native During D134.
    if strength is None:
        strength = GAIN_BONUS_STRENGTH[content]
    row = deepcopy(source["1610633"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    row[0:6] = [CODE, "false", "special", "0", "", "1"]
    _pre(row, "wind")
    _pre(row, "fever", offset=13)
    _pre(row, offset=20)
    for column, value in {97: 134, 98: 0, 100: SCALE, 101: SCALE,
                          102: "(None)" if limit is None else limit, 104: GAIN_UID,
                          109: content, 110: 5, 111: "Green",
                          113: strength, 114: strength}.items():
        row[column] = str(value)
    return row


def _consumed_stock_fever(source, marker_uid):
    # T185 belongs to A2: unlearned A2 cannot reward either consumer.
    row = _instant(source, 724, 5_000, pre="wind", fever="fever", trigger=185)
    row[28], row[37] = "0", str(marker_uid)
    return row


def _leader_uncap_switch(source):
    """I704（技能旗号 2）：仅队长（前置42）且风共鸣时打开，瞬发无触发。"""
    row = _instant(source, 704)
    _pre(row, "leader")
    _pre(row, "wind", offset=13)
    row[70] = LEADER_UNCAP_STRING_ID
    return row


def ability_rows(source: dict) -> dict:
    """返回 1499891..6；source 是只读的官方 ability 表解码结果。"""
    opening = _instant(source, 211, 50_000, target=0)
    enhance = _instant(source, 536, pre="wind")
    enhance[70] = CHANGE_SKILL_STRING_ID
    leader_uncap = _leader_uncap_switch(source)
    # 原版 1412012[2]：DirectAttack3 强度 0，三段分伤而非总伤害三倍。
    triple = _instant(source, 202, 0, pre="wind", target=5)
    ability_damage = _instant(source, 388, 200_000,
                              pre="wind", target=5)

    all_enemy = _instant(source, 254, 25 * SCALE, pre="wind", fever="fever",
                         trigger=20, threshold=35, wind_counter=True, target=0)
    all_enemy[69] = "(None)"  # None selects AllEnemyDamage, not NearestOrder.
    fever_charge = _instant(source, 724, 15_000, pre="wind", fever="not_fever",
                            trigger=20, threshold=35, wind_counter=True)
    # T12 listens to current combo crossing 7, 14...; both rewards have
    # independent limits, so reaching the attack cap does not stop charging.
    attack = _instant(source, 32, 70_000, pre="wind", fever="fever",
                      trigger=12, threshold=7, target=5, limit=10)
    charge = _instant(source, 211, 700, pre="wind", fever="fever",
                      trigger=12, threshold=7, target=5)
    charge[35] = '42'  # 0.7 seconds; only gauge reward is throttled.
    stock = _instant(source, 629, pre="wind", fever="fever",
                     trigger=23, wind_counter=True)
    stock[70:72] = [ABILITY_STOCK_STRING_ID, ABILITY_STOCK_ACTION_PATH]
    consume = _instant(source, 629, pre="wind", fever="fever",
                       trigger=26)
    # Native precontent consumes one layer first; no remaining layer means
    # no AddCombo. A leader consumer is a separate, intentional second call.
    for column, value in {39: 2, 40: 0, 42: SCALE, 43: SCALE, 45: STOCK_UID}.items():
        consume[column] = str(value)
    consume[70:72] = [ABILITY_SPEND_STRING_ID, ABILITY_SPEND_ACTION_PATH]

    slots = [
        [opening, enhance, leader_uncap],
        [triple, ability_damage,
         *[_consumed_stock_fever(source, uid) for uid, _, _ in SPEND_MARKERS]],
        [all_enemy, fever_charge, attack, charge, stock, consume,
         _stock_gain_bonus(source), _stock_gain_bonus(source, content=0)],
        [_fever_status(source, 26)],
        [_fever_status(source, 27)],
        [_fever_status(source, 688, 2 * SCALE)],
    ]
    result = {}
    for number, rows in enumerate(slots, 1):
        for row in rows:
            row[0] = f"{CODE}_{number}"
            row[1] = "false" if number in (1, 3) else "true"
        result[f"{CID}{number}"] = rows
    return result


def flat_string_rows() -> dict:
    """I536 必读 custom_ability_string 平表；缺键可引发 C8601。"""
    return {CHANGE_SKILL_STRING_ID: [[
        "技能强化：额外赋予全队贯穿效果（15秒）、"
        "风属性角色能力伤害提升100%效果（15秒），"
        "并赋予命中敌人风属性抗性降低25%效果（15秒）"
    ]], ABILITY_STOCK_STRING_ID: [[
        "获得1次「星风快门」（次数可累积；每次自身弹射消耗1次并增加7连击；"
        "非风属性共鸣或非Fever期间保留剩余次数）"
    ]], ABILITY_SPEND_STRING_ID: [["成功消耗1层星风快门时，增加7连击"]],
        # 技能强化条目不写数字、不写共鸣前缀（口径 U8）；官方格式点名技能（2026-09-27 技能强化文案规范）。
        LEADER_UNCAP_STRING_ID: [["强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升"]]}


def metadata() -> dict:
    return {
        "character_id": CID,
        "main_only_slots": [1, 3],
        "required_client_capabilities": ["kyubi-fever-ratio-v1"],
        "a1_enhancement": {
            "string_id": CHANGE_SKILL_STRING_ID,
            "flat_string_table": "master/string/custom_ability_string.orderedmap",
            "requires_skill_dsl_change_skill_flag_branch": True,
            "duration_seconds": 15,
            "piercing": True,
            "wind_party_ability_damage_percent": 100,
            "hit_enemy_wind_resistance_down_percent": 25,
        },
        "a1_leader_uncap": {
            "string_id": LEADER_UNCAP_STRING_ID,
            "content": 704, "skill_flag": 2,
            "preconditions": ["42 leader only", "wind resonance (6 members)"],
            "row_unisonable": True,
            "effect": "Starwind Insight skill multiplier layers uncapped (otherwise 10)",
            "source": "balance 2026-09-27 batch 3 (U5/U6)",
        },
        "direct_attack": {
            "times": 3,
            "additional_total_damage_percent": 0,
            "native_damage_is_divided_by_hit_count": True,
            "wind_counter": "total of wind party direct attacks",
            "fever_counters": "independent; fractional period carries across Fever",
        },
        "combo": {
            "trigger": "current combo crosses each multiple of 7 during Fever",
            "attack_target": "wind party",
            "attack_gain_percent": 70,
            "attack_max_percent": 700,
            "attack_persists_after_fever": True,
            "skill_gauge_gain_percent": 0.7,
            "skill_gauge_cooldown_seconds": 0.7,
            "skill_gauge_trigger_limit": None,
        },
        "a3_stock": {
            "main_only": True,
            "requires_wind_resonance_and_fever": True,
            "unique_id": STOCK_UID,
            "per_wind_skill": 1,
            "per_own_flip_cost": 1,
            "per_own_flip_combo": 7,
            "independent_of_leader_consumer": True,
            "with_leader_per_wind_skill": 3,
            "with_leader_max_cost_per_flip": 2,
            "with_leader_max_combo_per_flip": 14,
            "empty_stock_grants_no_combo": True,
        },
        "a2_consumed_stock_fever": {
            "requires_learned_a2": True,
            "requires_wind_resonance_and_fever": True,
            "percent_of_maximum_per_consumed_layer": 5,
            "with_both_consumers_max_percent_per_flip": 10,
            "empty_stock_grants_no_fever": True,
            "event_sources": [uid for uid, _, _ in SPEND_MARKERS],
            "event": "successful precontent consumption; not attempted flip",
        },
        "stock_gain_bonus": {
            "gain_unique_id": GAIN_UID,
            "per_layer_percent": GAIN_BONUS_STRENGTH[154] * 100 // SCALE,
            "attack_per_layer_percent": GAIN_BONUS_STRENGTH[0] * 100 // SCALE,
            "target": "wind party",
            "only_fever": True,
            "retain_after_fever": True,
            "stock_consume_preserves_bonus": True,
            "bonus_uses_cumulative_gained_layers": True,
            "during_trigger_limit": GAIN_BONUS_LIMIT,
            "uncapped_growth_moved_to_leader": "balance 2026-09-27 batch 2 (A3)",
        },
        "fever_ratio": "outside Fever add 15% per 35 wind direct hits; successful stock consumption adds 5%; neither raises maximum",
        "periodic_status": {
            "timer": "native cumulative Fever frames; fractional period carries",
            "period_frames": 300,
            "duration_frames": 60,
            "target": "whole player party ball",
            "expires_naturally_after_fever": True,
            "fixed_speed_strength": 2.0,
            "fixed_speed_skill_charging_strength": 0,
        },
    }
