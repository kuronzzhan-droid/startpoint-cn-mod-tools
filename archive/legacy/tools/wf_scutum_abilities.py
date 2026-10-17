"""盾牌座队长与六能力。仅构造数据，不操作 store、CDN 或设备。"""
from wf_scutum_abilities_rows import (
    CID, CODE, COLLECT_ICON, COLLECT_UID, COLLECT_HIT_UID, CHANGE_STRING, CHASE_STRING,
    COLLECT_CHASE_STRING,
    DASH_STRING, SCALE, during, helper, instant, pre, put, timed,
)
from wf_scutum_abilities_text import panel_string_rows

ABILITY_TABLE = "master/ability/ability.orderedmap"
LEADER_TABLE = "master/ability/leader_ability.orderedmap"
UNIQUE_TABLE = "master/character/unique_condition.orderedmap"
STRING_TABLE = "master/string/custom_ability_string.orderedmap"


def _floating_growth(source, content):
    return instant(source, content, 50_000, target=5, trigger=236,
                   threshold=1, threshold2=300, limit=4)


def _collect_grant(source, target):
    row = instant(source, 461, SCALE, target=target, group="(None)",
                  gates=("wind_resonance",), trigger=65, cooldown=300)
    return put(row, {59: SCALE, 60: SCALE, 68: COLLECT_UID, 74: 1, 75: 0})


def _collect_followup(source):
    """两个实际命中源汇入同一个原生 handler，共享冷却。"""
    markers = [put(instant(source, 461, SCALE, target=0,
                          gates=("collect",), trigger=20, puller=puller),
                   {59: SCALE, 60: SCALE, 68: COLLECT_HIT_UID, 74: 1, 75: 0})
               for puller in (0, 9)]
    chase = helper(source, COLLECT_CHASE_STRING, gates=("collect",),
                   trigger=185, puller=0, cooldown=300)
    clear = instant(source, 528, target=0, trigger=185, puller=0)
    for row in (chase, clear):
        row[37] = str(COLLECT_HIT_UID)
    clear[68] = str(COLLECT_HIT_UID)
    return markers + [chase, clear]


def ability_rows(source):
    """自身收集窗口内，自身与协力球直击共用一次5秒冷却追击。"""
    a1 = [
        _floating_growth(source, 33), _floating_growth(source, 32),
        during(source, 3, 15_000, condition=31),
        instant(source, 211, 50_000, target=5, gates=("wind_resonance",)),
        instant(source, 211, SCALE, target=0),
    ]
    for row in a1:
        pre(row, "wind_resonance")
    a2 = [
        instant(source, 227, 10_000, target=target, group="(None)",
                gates=("self_wind",), trigger=65)
        for target in (5, 8)
    ]
    a2 += [
        instant(source, content, 55_000, target=5, trigger=20,
                puller=0, threshold=30, limit=7)
        for content in (139, 506)
    ]
    a2 += [instant(source, 191, 15_000, gates=("self_wind",)),
           instant(source, 211, 2_500, target=5, trigger=51)]
    resist = instant(source, 442, -2_000, gates=("piercing",),
                     trigger=20, puller=0)
    timed(resist, 1500, maximum=20)
    a3 = [_collect_grant(source, target) for target in (5, 8)]
    a3 += [during(source, 410, 20_000, condition=72,
                  target=0, gates=("collect",))]
    a3 += _collect_followup(source)
    a3 += [resist, instant(source, 717, SCALE, target=0)]
    a4 = [timed(instant(source, 31, gates=("self_wind",), trigger=51), 180),
          _floating_growth(source, 32)]
    a5 = [timed(instant(source, 26, gates=("self_wind",), trigger=77,
                        threshold=300), 180),
          helper(source, CHASE_STRING, gates=("piercing",), trigger=23,
                 puller=7, puller_group="Green")]
    a6 = [put(instant(source, 536, gates=("wind_resonance",)), {70: CHANGE_STRING})]
    result = {}
    for number, rows in enumerate((a1, a2, a3, a4, a5, a6), 1):
        for row in rows:
            row[0] = f"{CODE}_{number}"
            row[1] = "false" if number in (1, 3) else "true"
        result[f"{CID}{number}"] = rows
    return result


def leader_rows(source):
    rows = [
        during(source, 1, 400_000, condition=31),
        instant(source, 200, 9 * SCALE),
        helper(source, DASH_STRING, gates=("wind_resonance",),
               trigger=21, threshold=10, puller=7,
               puller_group="(None)", cooldown=300),
        during(source, 0, 150_000, condition=30),
        during(source, 1, 150_000, condition=30),
        during(source, 410, 20_000, condition=30),
    ]
    return [[CODE, "0", ""] + row[5:] for row in rows]


def unique_rows():
    result = {str(COLLECT_UID): [[
        "unique_scutum_valentine_collect", "收集", COLLECT_ICON,
        "300", "1", "(None)", "(None)", "(None)", "(None)",
        "false", "true", "0", "0", "true", "(None)",
    ]]}
    marker = result[str(COLLECT_UID)][0].copy()
    marker[:5] = ["unique_scutum_valentine_collect_hit", "收集追击", COLLECT_ICON, "1", "1"]
    # Native I528 uses cancelableKind=0; only this private bridge is removable.
    marker[9] = "true"
    result[str(COLLECT_HIT_UID)] = [marker]
    return result


def flat_string_rows():
    return {
        DASH_STRING: [["向最近的敌人突进，并赋予队伍中角色及协力球贯通效果（5秒）"]],
        CHASE_STRING: [["对所有敌人造成自身攻击力35倍的伤害（按直接攻击伤害加成计算）"]],
        COLLECT_CHASE_STRING: [["向距离自身最近的敌人追加自身攻击力5倍的风属性伤害（按直接攻击伤害加成计算）"]],
        CHANGE_STRING: [["技能的连击效果强化为5次直接攻击，总和伤害提升50%"]],
        **panel_string_rows(),
    }


def metadata():
    return {
        "character_id": CID, "main_only_slots": [1, 3],
        "collect_unique_id": COLLECT_UID,
        "collect_duration_frames": 300, "collect_pf3_cooldown_frames": 300,
        "requires_collect_hit_resolution": False,
        "collect_followup": {
            "trigger": 20, "trigger_pullers": [0, 9],
            "shared_handler_trigger": 185, "shared_cooldown_frames": 300,
            "hit_marker_unique_id": COLLECT_HIT_UID,
            "hit_marker_duration_frames": 1,
            "cleanup": "self T185 -> I528 exact private marker; native impact queue and one-frame expiry",
            "gate": "owner holds collect UID14998801; one native 300-frame team window",
            "includes_new_multiballs_during_window": True,
            "individual_trigger_holder_required": False,
            "executor_and_attack_source": "Scutum ability owner",
            "target": "nearest enemy relative to Scutum",
            "attack_multiplier": 5, "element": "Green", "buff_target_as": 4,
            "damage_reference": "owner direct-damage additive modifier; native action source, independent multipliers and resistances retained",
            "not_actual_hit_enemy": True,
            "program": "battle/action/skill/action/ability_skill/scutum_valentine$" + COLLECT_CHASE_STRING,
        },
        "additional_unison_attack": {"content": 717, "additional_percent": 100,
            "source": "source.unisonAtk before ordinary battle attack modifiers",
            "native_normal_contribution_percent": 25},
        "flying_growth": {"trigger": 236, "period_frames": 300,
            "per_application_percent": 50, "limit": 4,
            "timer": "native cumulative held-Flying frames; partial period retained"},
        "skill_gauge_50": "initial wind-party charge under wind resonance",
        "wind_resonance_slots": [1, 6],
        "collect_grant_requires_wind_resonance": True,
        "panel_capability": "panel-description-override-v2",
        "leader_pf3_requirement_reduction": 9,
        "a3_wind_resistance": {"content": 442, "per_hit_percent": -2,
            "maximum_layers": 20, "duration_frames": 1500,
            "target": "actual triggering enemy"},
    }


def install(seed):
    source = seed.rows(ABILITY_TABLE)
    seed.table(ABILITY_TABLE, ability_rows(source))
    seed.table(LEADER_TABLE, {CID: leader_rows(source)})
    seed.table(UNIQUE_TABLE, unique_rows())
    seed.table(STRING_TABLE, flat_string_rows())
    return metadata()
