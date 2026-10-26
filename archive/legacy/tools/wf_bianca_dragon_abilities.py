"""校园碧安卡龙协力球重做：只组装原生表行，不读写 store。

百分比均是用户指定满级值，各级固定；共鸣条件统一使用火属性
Member(Red, 6)。A1 的强化桥由装配方追加。
"""
from __future__ import annotations

import copy

CID = "119989"
CODE = "lady_summoner_campus"
SUMMON_UNIQUE_ID = 11998901
FEVER_STACK_UNIQUE_ID = 11998903
FEVER_TICK_STRING_ID = CODE + "_fever_tick"
FEVER_TICK_ACTION_PATH = ("battle/action/skill/action/ability_skill/"
                          + CODE + "$" + CODE + "_fever_tick")
UNIQUE_MAX_ACCUMULATION = 2_147_483_647
SCALE = 100_000
#: 整键 c1="false" 的主位限制槽；wf_campus_panel_text 覆盖串的主位图标须与之一致（test_campus_panel_text 校验）。
MAIN_ONLY_SLOTS = (1, 3)


def _set(row, values):
    for column, value in values.items():
        row[column] = str(value)
    return row


def _pre(row, kind="fire", *, offset=6):
    row[offset:offset + 7] = ["0", "", "", "", "", "", ""]
    if kind == "fire":
        row[offset] = "2"
        row[offset + 3:offset + 5] = ["600000", "600000"]
        row[offset + 5] = "Red"
    elif kind == "fever":
        row[offset] = "12"
    elif kind is not None:
        raise ValueError(f"unsupported precondition: {kind}")
    return row


def _instant(source, content, strength=None, *, trigger=0, puller=None,
             group=None, target=None, target_group=None, pre=None,
             fever=False, limit=None, cooldown=0, threshold=100_000):
    row = copy.deepcopy(source["1110211"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    # A known initial SkillGauge donor supplies valid sentinels. Clear its content.
    row[27:39] = [""] * 12
    row[47:85] = [""] * 38
    _set(row, {27: trigger, 47: content})
    if trigger:
        _set(row, {30: threshold, 31: threshold,
                   34: "(None)" if limit is None else limit, 35: cooldown})
    if puller is not None:
        row[28] = str(puller)
    if group is not None:
        row[29] = group
    if target is not None:
        row[48] = str(target)
    if target_group is not None:
        row[49] = target_group
    if strength is not None:
        row[51:53] = [str(strength)] * 2
    _pre(row, pre)
    if fever:
        _pre(row, "fever", offset=13)
    return row


def _during(source, content, strength, *, target=5, target_group="Red",
            pre=None, fever=True):
    row = copy.deepcopy(source["1510013"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    row[109:123] = [""] * 14
    _set(row, {109: content, 110: target, 111: target_group,
               113: strength, 114: strength})
    _pre(row, pre)
    if not fever:
        raise ValueError("a during row needs an explicit native trigger")
    return row


def _leader(ability_row):
    # Both tables have the same body from the trigger-mode column onward.
    return [CODE, "0", ""] + copy.deepcopy(ability_row[5:])


def _skill(source, content, strength, **kwargs):
    return _instant(source, content, strength, trigger=23, puller=7,
                    group="Red", **kwargs)


def _attack_buff(source, strength, frames, *, pre="fire"):
    row = _skill(source, 0, strength, target=2, pre=pre)
    # Timed ConditionAttackPoint fields follow official Christmas Bianca A1.
    return _set(row, {57: frames * SCALE, 58: frames * SCALE,
                     59: SCALE, 60: SCALE, 61: "(None)", 62: "(None)",
                     63: "(None)", 64: "(None)", 65: "(None)",
                     67: 0, 72: "false", 74: 1, 75: 0})


def fever_rows(source, *, fever_stack_unique_id=FEVER_STACK_UNIQUE_ID):
    """主位 A3。只删除本角色私有层数；Fever 帧余数沿用客户端原生。"""
    cap = _during(source, 124, 20_000, pre="fire")
    # InvokeSkill supplies native human-readable text without advertising the
    # private counter's int limit. Its private DSL only grants this counter.
    tick = _instant(source, 629, trigger=248, threshold=120 * SCALE,
                    pre="fire", fever=True)
    _set(tick, {70: FEVER_TICK_STRING_ID, 71: FEVER_TICK_ACTION_PATH})
    # A condition-count trigger multiplies the bonus by the live private stack.
    gain = copy.deepcopy(source["1610633"][0])
    _pre(gain, "fire")
    _pre(gain, "fever", offset=13)
    _set(gain, {97: 134, 98: 0, 100: SCALE, 101: SCALE, 102: "(None)",
                104: fever_stack_unique_id, 109: 154, 110: 5, 111: "Red",
                113: 50_000, 114: 50_000})
    clear = _instant(source, 528, trigger=184, target=0)
    clear[68] = str(fever_stack_unique_id)
    charge = _instant(source, 211, 5_000, trigger=248,
                      threshold=120 * SCALE, target=2, pre="fire", fever=True)
    # Native D412 is the ability-only separated term; it reads the same live
    # stack as D154, so the existing reset removes both bonuses immediately.
    separate = copy.deepcopy(gain)
    _set(separate, {109: 412, 113: 1_000, 114: 1_000})
    return [cap, tick, gain, clear, charge, separate]


def fever_tick_assets(*, fever_stack_unique_id=FEVER_STACK_UNIQUE_ID):
    """原生能力动作只给自身私有计数+1，不播放演出或造成伤害。"""
    from wf_bianca_dragon_skill import amf_bytes, block, command, mark
    tree = ["ActionDsl", 1, ["None"], False, False, False, False, False,
            False, False, 0, block(command("ConditionalsFeverMode",
                block(mark(-17, fever_stack_unique_id)), block()))]
    return {("common", FEVER_TICK_ACTION_PATH + ".action.dsl.amf3.deflate"): amf_bytes(tree)}


def fever_tick_string_rows():
    return {FEVER_TICK_STRING_ID: [["自身的「焰域研修」等级上升1级"]]}


def ability_rows(source, *, fever_stack_unique_id=FEVER_STACK_UNIQUE_ID):
    """返回 1199891…1199896；不修改输入，不包含另模块的 A1 强化桥。"""
    # 2026-09-27 作者平衡第二批：开局自身技能槽 75% → 50%（wf_balance_20260927b_bianca）。
    opening = [_instant(source, 211, 50_000, target=0)]
    nearest = _skill(source, 352, 1_000_000, target=0,
                     pre="fire", cooldown=60)
    nearest[69] = "(None)"
    a2 = [nearest, _attack_buff(source, 100_000, 480)]
    a3 = fever_rows(source, fever_stack_unique_id=fever_stack_unique_id)
    a4 = [_instant(source, 56, 15_000, pre="fire"),
          _during(source, 3, 10_000)]
    a5 = [_skill(source, 724, 15_000, pre="fire")]
    a6 = [_skill(source, 388, 10_000, target=5, target_group="Red", limit=10),
          _skill(source, 32, 10_000, target=5, target_group="Red",
                 fever=True, limit=10)]
    result = {}
    # 2026-09-27 作者平衡第二批：能力5 去主位限制，只剩能力1、3 主位（wf_balance_20260927b_bianca）。
    for slot, rows in enumerate((opening, a2, a3, a4, a5, a6), 1):
        for row in rows:
            row[:5] = [f"{CODE}_{slot}", "false" if slot in MAIN_ONLY_SLOTS else "true",
                       "attack_red", "0", ""]
        result[f"{CID}{slot}"] = rows
    return result


def leader_rows(ability_source, leader_source, *, summon_unique_id=SUMMON_UNIQUE_ID):
    """T185 仅监听 owner 的召唤标记；标记由成功召唤的小龙技能授予。"""
    if len(leader_source["151001"][0]) != 124:
        raise ValueError("official leader rows must have 124 columns")
    base_atk = _instant(ability_source, 32, 200_000, target=5,
                        target_group="Red", pre="fire")
    base_damage = _instant(ability_source, 388, 400_000, target=5,
                           target_group="Red", pre="fire")
    fever_atk = _during(ability_source, 0, 200_000, pre="fire")
    summon = _instant(ability_source, 213, 50_000_000, trigger=185,
                      puller=0, pre="fire")
    summon[37] = str(summon_unique_id)
    charge = _instant(ability_source, 211, 25_000, trigger=185,
                      puller=0, target=5, target_group="Red", pre="fire")
    charge[37] = str(summon_unique_id)
    damage = _skill(ability_source, 251, 5_000_000, target=0)
    # None produces AllEnemyDamage; Some(time) would select NearestOrder.
    damage[69] = "(None)"
    return [_leader(row) for row in (base_atk, base_damage, fever_atk,
                                    summon, charge, damage)]


def metadata(*, summon_unique_id=SUMMON_UNIQUE_ID,
             fever_stack_unique_id=FEVER_STACK_UNIQUE_ID):
    return {
        "required_client_capabilities": ["kyubi-fever-ratio-v1"],
        "main_only_slots": list(MAIN_ONLY_SLOTS),
        "resonance": "all resonance gates use fire pre2 Member(Red,6)",
        "summon_event": {"unique_id": summon_unique_id, "trigger": 185, "puller": 0,
                         "contract": "owner marker granted only after successful own-dragon summon"},
        "a1_enhancement_bridge": "supplied by wf_bianca_dragon_bridge",
        "fever_stack": {"unique_id": fever_stack_unique_id, "reset_trigger": 184,
                        "reset_content": 528, "removed_on_fever_end": True,
                        "required_unique_max_accumulation": UNIQUE_MAX_ACCUMULATION,
                        "required_unique_remove_if_encoffin": True,
                        "required_unique_duration_frame": 99_999_999,
                        "balance_cap": None, "bonus_per_stack": 0.5,
                        "separated_ability_bonus_per_stack": 0.01,
                        "separated_damage_kind": "ability only; native D412",
                        "tick_content": 629, "tick_action": FEVER_TICK_ACTION_PATH,
                        "timer": "native FeverFrame 248; pauses outside Fever; fractional period carries"},
        "skill_gauge_maximum": "D124 adds 20% only during Fever; native total clamp is +100%",
        "a6": "10 skill triggers each; persistent base-stat increases, ATK acquisition gated by Fever",
        "level_scaling": "user-specified values fixed at all ability levels",
    }
