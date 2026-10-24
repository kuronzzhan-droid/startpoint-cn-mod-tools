"""奈芙提姆的全队增益与光暗协力球召唤，纯原生Action DSL。"""
from copy import deepcopy

from wf_bianca_dragon_skill import command, block, value
import wf_nephtim_fever_shield as shield

CODE = "ruin_girl_campus"
STATE_UID = 16998901
LIGHT_ID, DARK_ID = 1699891, 1699892
STATE_NAME = "星夜茶会"
STATE_ICON = "battle/common/unique_condition/" + CODE + "_starry_tea"
ACTIVE_PATHS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}"
                     for level in (1, 2))
SKILL_FX = "battle/effect/skill_unique/" + CODE + "_fever/"
BALL_FX = {kind: f"battle/effect/skill_unique/{CODE}_{kind}_call/" for kind in ("light", "dark")}
LIGHT_FADE_FX = f"battle/effect/skill_unique/{CODE}_light_fade/{CODE}_light_fade_disappear"
DURATION = 1200
BALL_LIFETIME = 1500
# 协力球同时在场上限；引擎自身对召唤数量没有任何限制（ActionEvaluator case 36 是纯循环），
# 必须由 ConditionalsMultiballNumber 自己卡。
MULTIBALL_CAP = 9
# 已满上限时这一次召唤改为给自身叠一层攻击力。
# 作者 2026-09-17：能力1 提供的攻击力减半（原 0.5 = +50%/层），机制与层数上限不动。
OVERFLOW_ATTACK_STRENGTH = 0.25
# ACAttackPoint 第三参 = maxAccumulation（叠加层数上限），不是段数；
# 官方 level_up.action.dsl 同样用 99。
OVERFLOW_ATTACK_STACKS = 99


def condition(subject, *contents, silent=False, magnification=1, force_apply=True):
    return command("CreateCondition", subject, list(contents), value(1),
                   ["None"] if silent else ["GenericConditionHitEffect"],
                   False, False, "", None, False, 3, value(magnification), force_apply)


def find(subject, selector, contents, elements=(), *, force_apply=True):
    return command("FindAllSubjects", subject, selector, list(elements), [], [], [], [],
                   ["DoNothing"], block(condition(subject, *contents, force_apply=force_apply)))


def dark_and_balls(*contents):
    # 82 is primary members only; 86 is multiball members only. No duplicate dark ball grant.
    # A queued ordinary buff must skip a ball that expires during a skill cut-in.
    return block(find(70, 82, contents, (6,)), find(71, 86, contents, force_apply=False))


def direct_buff():
    return ["ACDirectDamage", value(DURATION), value(2), value(1)]


def attack_buff():
    return ["ACAttackPoint", value(DURATION), value(2.5), value(1)]


def split_buff():
    # (1 + strength) / times = (1+1)/2 per hit; total direct damage is doubled.
    return ["ACAdditionalDirectAttack", value(DURATION), value(2), value(1), value(1)]


def show(name, subject=-18):
    return command("ShowEffect", name, ["SpecifyEffectDirectly", SKILL_FX + name],
                   subject, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"],
                   ["AB"], 0, 0, 0, False, False, ["None"])


def action(*expressions):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, block(*expressions)]


def _grant_state():
    # Adding zero accumulation refreshes an existing native Unique's duration,
    # preserving phase 1/2. It cannot recreate a condition removed before impact.
    unique = ["ACUnique", STATE_UID, value(1)]
    return command("ConditionalsConditionExist", -17, ["DCUnique", STATE_UID],
        block(condition(-17, unique, silent=True, magnification=0)),
        block(condition(-17, unique, silent=True)))


def build_skill(level):
    if level not in (1, 2):
        raise ValueError("skill level must be 1 or 2")
    piercing = ["ACPiercing", value(DURATION)]
    fever = command("ConditionalsFeverMode", block(
        find(70, 82, [split_buff()], (6,)),
        show(CODE + "_fever_2yellow")),
        block(show(CODE + "_fever_1blue")))
    enhanced = command("ConditionalsChangeSkillFlag", 1, block(
        dark_and_balls(attack_buff()),
        command("ConditionalsFeverMode", block(
            _grant_state(), shield.grant_barriers()), block())), block())
    return action(show(CODE + "_fever_all", -1),
        find(72, 33, [direct_buff(), piercing]),
        # Native co-op condition channel: remote primary members, local balls handled above.
        command("TargetMate", 73, [], [], [], [], []),
        condition(73, piercing), fever, enhanced)


def _advance_phase(kind):
    """Use the existing timed status as a two-state phase without refreshing its expiry.

    Native ConsumeUniqueCondition forwards signed limits: at one layer, -1 raises
    the count to two; at two layers, +1 lowers it to one. Guards keep the count
    within 1..2 and avoid recreating an expired/cleared condition in late callbacks.
    """
    increment = command("ConsumeUniqueCondition", -17, STATE_UID, ["Some", -1])
    decrement = command("ConsumeUniqueCondition", -17, STATE_UID, ["Some", 1])
    change = command("ConditionalsConditionAccumulationNumber", ["DCUnique", STATE_UID], 2,
                     block(decrement) if kind == "dark" else block(),
                     block(increment) if kind == "light" else block())
    return command("ConditionalsFeverMode", block(
        command("ConditionalsConditionExist", -17, ["DCUnique", STATE_UID],
                block(change), block())), block())


def summon(kind):
    uid = LIGHT_ID if kind == "light" else DARK_ID
    prefix = BALL_FX[kind]
    stem = CODE + "_" + kind + "_call"
    effect = lambda tail: ["SpecifyEffectDirectly", prefix + stem + tail]
    disappear = ["SpecifyEffectDirectly", LIGHT_FADE_FX] if kind == "light" else effect("_disappear")
    return command("CreateSummonsMultiball", 1, uid, value(BALL_LIFETIME),
        ["E2", effect("_ready_generation"), effect("_ready_left"), effect("_ready_right")],
        effect("_appear"), disappear, 0, False,
        "campus_nephtim_" + kind + "_spawn", 74, 75, block(
            condition(75, direct_buff(), attack_buff(), ["ACPiercing", value(DURATION)],
                      ["ACHealRejection", value(BALL_LIFETIME)]),
            _advance_phase(kind)), None)


def overflow_attack():
    """满上限时的替代效果：自身攻击力+25%，靠原生 maxAccumulation 叠层。

    同一条 CreateCondition 的 key 由 battleId + 词条地址决定，整场恒定，重复执行只会
    覆盖刷新；叠层唯一的原生通路是 ACAttackPoint 的第三参 maxAccumulation。
    """
    return condition(-17, ["ACAttackPoint", value(DURATION),
                           value(OVERFLOW_ATTACK_STRENGTH), value(OVERFLOW_ATTACK_STACKS)])


def overflow_attack_percent():
    """溢出攻击力的面板口径百分比；文案模块引用同一真源。"""
    percent = OVERFLOW_ATTACK_STRENGTH * 100
    return int(percent) if float(percent).is_integer() else percent


def build_spawn():
    """球未满上限时交替召唤，已满则把这一次召唤换成自身攻击力叠层。

    ConditionalsMultiballNumber 的 p0 必须显式列出要数的球 ID：只有 null 才是"全部"，
    空数组等于一个都匹配不到（SquadImpl.matchMultiball）。计数含还在弹板上等待出场的球，
    所以出场动画期间不会超召。
    """
    choose = command("ConditionalsConditionAccumulationNumber", ["DCUnique", STATE_UID], 2,
                     block(summon("dark")), block(summon("light")))
    capped = command("ConditionalsMultiballNumber", [LIGHT_ID, DARK_ID], [], MULTIBALL_CAP,
                     block(overflow_attack()), block(choose))
    return action(command("ConditionalsFeverMode", block(
        command("ConditionalsConditionExist", -17, ["DCUnique", STATE_UID],
                block(capped), block())), block()))


def unique_rows():
    return {
        str(STATE_UID): [[CODE + "_starry_tea", STATE_NAME, STATE_ICON, str(DURATION), "2",
                         "(None)", "(None)", "(None)", "(None)", "false", "true",
                         "0", "0", "true", "(None)"]],
    }


def multiball_rows(multiballs, levels):
    result, growth = {}, {}
    for uid, kind, element in ((LIGHT_ID, "light", 4), (DARK_ID, "dark", 5)):
        row = deepcopy(multiballs["1611772"][0])
        actor = CODE + "_" + kind + "_ball"
        row[0:2] = [actor + "_1", actor]
        row[3] = str(element)
        result[str(uid)] = [row]
        growth[str(uid)] = deepcopy(levels["1611772"])
    return {"master/battle/multiball/multiball.orderedmap": result,
            "master/battle/multiball/multiball_level.orderedmap": growth}


def metadata():
    return {"base_direct_percent": 200, "enhanced_attack_percent": 250,
            "duration_frames": DURATION, "additional_direct_times": 2,
            "additional_direct_total_ratio": 2,
            "spawn_unique_id": STATE_UID, "alternate_phase": "single timed Unique, guarded signed consumption 1/2",
            "spawn_order": ["light", "dark"], "each_ball_lifetime_frames": BALL_LIFETIME,
            "new_ball_heal_rejection_frames": BALL_LIFETIME,
            "multiball_cap": MULTIBALL_CAP,
            "overflow_attack_percent": overflow_attack_percent(),
            "overflow_attack_max_stacks": OVERFLOW_ATTACK_STACKS,
            "overflow_attack_frames": DURATION,
            "overflow_counts_ids": [LIGHT_ID, DARK_ID],
            "overflow_count_includes_inactive_balls": True,
            "overflow_count_origin_filtered": False,
            "ball_base_stats_unchanged": True, "ball_growth_curves_unchanged": True,
            "enhanced_fever_shield": shield.metadata(),
            "new_ball_buffs": "20s direct/attack/piercing and heal rejection; no multiple-hit buff",
            "light_appearance": "native ruin_girl_meteor; author-approved Summons conversion",
            "remote_piercing": "native TargetMate channel to primary members",
            "local_targets": "all primary members and all skill-targetable multiballs"}
