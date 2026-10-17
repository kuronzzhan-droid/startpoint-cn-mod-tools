"""Magnus PF movement with a parallel native AbilitySkill damage action.

Native content 629 creates ActionKind.AbilitySkill. Unlike buffTargetAs=1 on
a PF action, this reaches the skill separated terms in NormalAttackCalculator.
The movement action alone owns suppression, visuals and NotifyPowerflipEnd.
"""
from __future__ import annotations

import copy

from wf_dsl import iter_dsl_commands


def skill_programs(code: str) -> tuple[str, ...]:
    return tuple(f"battle/action/skill/action/ability_skill/{code}_pf_skill$"
                 f"{code}_pf_skill_lv{level}" for level in (1, 2, 3))


def leader_plans(code: str, string_id: str) -> tuple:
    return tuple(("111183#4", "official", {
        0: code, 4: "2", 7: "600000", 8: "600000", 9: "Red",
        11: "0", 14: "", 15: "", 17: "", 18: "0",
        25: str(62 + level), 28: "100000", 29: "100000", 32: "(None)",
        33: "0", 45: "629", 46: "0", 68: string_id, 69: program,
    }, f"火·编成≥6 时: 强化弹射Lv{level}≥1 → 自身 发动技能动作[{string_id}]")
        for level, program in enumerate(skill_programs(code), 1))


def _strip(node, commands: set[str]):
    if not isinstance(node, list):
        return copy.deepcopy(node)
    if len(node) == 2 and node[0] == "Block":
        kept = []
        for item in node[1]:
            if item[0] == "Command" and item[1][0] in commands:
                continue
            changed = _strip(item, commands)
            if (changed[0] == "Event" and changed[1][0] == "Wait"
                    and changed[1][-1] == ["Block", []]):
                continue
            kept.append(changed)
        return ["Block", kept]
    return [_strip(value, commands) for value in node]


def split_tree(blueprint: list) -> tuple[list, list, dict]:
    """Preserve collision timing and hit areas; never leave a dummy PF hit.

    CreateOnlyHitAttack is not a safe PF marker: the client emits charge level
    zero, which OneOfEnemyBattleCountAbilityTriggerKind rejects with C2702.
    Zero-multiplier CreateNormalAttack is also not zero damage (minimum one).
    """
    areas = list(iter_dsl_commands(blueprint, "CreateHitArea"))
    if len(areas) != 2 or blueprint[10] != 0:
        raise ValueError("unexpected Magnus PF blueprint")
    for area in areas:
        if area[24] != 0 or area[14][0] != "CalculatedUsingMaxNumOfHits":
            raise ValueError("PF damage attribution or hit count drift")
    collisions = [e for e in blueprint[11][1]
                  if e[0] == "Event" and e[1][0] == "CollisionOfBallAndEnemy"]
    if len(collisions) != 1 or collisions[0][1][1:3] != [90, 1]:
        raise ValueError("PF first-contact window drift")

    movement = _strip(blueprint, {"CreateHitArea"})
    skill = copy.deepcopy(blueprint[:11]) + [["Block", [copy.deepcopy(collisions[0])]]]
    skill = _strip(skill, {"SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent",
                          "ShowEffect", "HideEffect", "PlaySound"})
    if list(iter_dsl_commands(movement, "CreateNormalAttack")):
        raise ValueError("PF action still deals damage")
    if list(iter_dsl_commands(skill, "CreateOnlyHitAttack")):
        raise ValueError("skill must use actual damage attacks")
    if len(list(iter_dsl_commands(skill, "CreateNormalAttack"))) != 2:
        raise ValueError("skill lost burst damage")
    mults = [list(iter_dsl_commands(a[23], "CreateNormalAttack"))[0][6][0]["max"]
             for a in areas]
    hits = [a[14][1] for a in areas]
    return movement, skill, {
        "damage_source": "AbilitySkill", "buff_target_as": 0,
        "skill_separated_terms": True, "pf_hit_count": False,
        "multipliers": mults, "hits": hits,
        "total": round(sum(m * n for m, n in zip(mults, hits)), 6),
        "collision_frames": 90, "visual_owner": "PowerFlip",
    }
