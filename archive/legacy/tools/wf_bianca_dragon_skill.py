"""碧安卡协力幼龙的原生两段技能；只返回候选数据，不写入商店或发布链。"""
from __future__ import annotations

import copy
import math
import zlib

import wf_dsl

DRAGON_ID = 1199891
DRAGON_CODE = "lady_summoner_campus_dragon"
SUMMON_MARKER = 11998901
BREATH_MARKER = 11998902
SUPPORT_ID = 11998991
CALL_EFFECT = "battle/effect/skill_unique/campus_bianca_dragon_call/"
BREATH_EFFECT = "battle/effect/skill_unique/campus_bianca_descent/"
FLIGHT_EFFECT = CALL_EFFECT + "campus_bianca_dragon_call_flight"
TIMER_FOREVER = 2147483647  # 原生召唤参数必为int；约414天，不使用立即过期的-1。
DRAGON_MAX_LEVEL_STAT = 5000
# 保留供体的等级曲线（1/10/80/100级：0.1/1/6/6.6），把100级归一为5000。
# Native以Number顺序计算basic * curve * correction，再floor(+2e-10)。
DRAGON_STAT_CORRECTION = "0.15151515151515152"


def value(number):
    return [{"min": number, "max": number}]


def command(name, *args):
    return ["Command", [name, *args]]


def block(*expressions):
    return ["Block", list(expressions)]


def wait(frames, label, *expressions):
    return ["Event", ["Wait", frames, label, block(*expressions)]]


def condition(subject, content, *, label="", force_apply=False):
    return command("CreateCondition", subject, [content], value(1),
                   ["GenericConditionHitEffect"], True, False, label, None,
                   False, 3, value(1), force_apply)


def mark(subject, marker):
    return condition(subject, ["ACUnique", marker, value(1)])


def enemies(*expressions):
    return command("FindAllSubjects", 40, 49, [], [], [], [], [],
                   ["DoNothing"], block(*expressions))


def effect(path):
    return ["SpecifyEffectDirectly", path]


def show_effect(label, path, *, subject=-1, angle=0):
    return command("ShowEffect", label, effect(path), subject,
                   ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"],
                   ["AB"], 0, 0, angle, False, False, ["None"])


def build_skill(level, *, summon_marker=SUMMON_MARKER, breath_marker=BREATH_MARKER):
    """真能力伤害由龙support I251产生；本程序没有CreateNormalAttack。

    FindMultiballSubjects同时按施术者origin与专属ID筛选。先授命所选龙，再给
    碧安卡吐息标记，等待impact/trigger结算后才移除龙，避免支持能力提前销毁。
    A1授予flag1；仅在已学习且满足火共鸣时应用额外能力抗性降低。
    """
    if level not in (1, 2):
        raise ValueError("skill level must be 1 or 2")
    summon = command("CreateSummonsMultiball", 1, DRAGON_ID, value(TIMER_FOREVER),
        ["E2", effect(CALL_EFFECT + "campus_bianca_dragon_call_effect_ready_generation"),
         effect(CALL_EFFECT + "campus_bianca_dragon_call_effect_ready_left"),
         effect(CALL_EFFECT + "campus_bianca_dragon_call_effect_ready_right")],
        effect(CALL_EFFECT + "campus_bianca_dragon_call_effect_appear"),
        effect(CALL_EFFECT + "campus_bianca_dragon_call_effect_disappear"),
        0, False, "campus_dragon_activated", 10, 11,
        block(mark(-17, summon_marker)), None)
    # A new dragon generation must not inherit the preceding one's callbacks.
    absent = block(*(command("RemoveEventFromOwner", name) for name in (
        "campus_dragon_breath_begin", "campus_dragon_breath_signal",
        "campus_dragon_depart", "campus_dragon_activated")), summon, enemies(condition(40,
        ["ACAttackPoint", value(900), value(-0.20), value(1)])))
    enhanced = command("ConditionalsChangeSkillFlag", 1,
        block(enemies(condition(40, ["ACAbilityDamageResistance", value(900),
                                     value(-0.20), value(1)]))), block())
    # 24帧上升演出后，从场地中心将原圣诞全屏喷息旋转180度。
    # AB的角度单位为弧度，0朝上，PI朝下；不能用180当弧度。
    flight = command("CreateReferencePoint", 10, ["AB"], 0, 0, 0,
        False, False, ["Single"], 25, 12,
        block(command("ShowEffect", "campus_dragon_flight", effect(FLIGHT_EFFECT), 12,
                      ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"],
                      0, 0, 0, True, False, ["None"]),
              command("MoveHitArea", 12, ["AB"], 0, 120, ["None"])))
    # Recasts keep their own breaths/signals, but share the latest departure.
    present = block(command("RemoveEventFromOwner", "campus_dragon_depart"),
        condition(11, ["ACInvincible", value(60)], force_apply=True),
        flight, command("HideCharacter", 11, 30),
        command("StopBall", 10, 30, ["Stop"], ["AB"], 0),
        wait(24, "campus_dragon_breath_begin",
            show_effect("campus_dragon_descent", BREATH_EFFECT + "campus_bianca_descent_all", angle=math.pi),
            command("ShakeCamera", 2),
            enemies(condition(40, ["ACToleranceOfElement", value(900), 1,
                                   value(-0.25), value(1)]),
                    show_effect("campus_dragon_hit", BREATH_EFFECT + "campus_bianca_descent_hit", subject=40)),
            enhanced,
            command("FindMultiballSubjects", 10, 11, True, [DRAGON_ID], block(),
                    block(mark(11, breath_marker))),
            wait(1, "campus_dragon_breath_signal", mark(-17, breath_marker),
                 command("AddFeverPoint", value(250)))),
        # Nested Wait counters start at -1: the old 24 -> 1 -> 2 chain ended at tick 29.
        wait(29, "campus_dragon_depart", command("RemoveMultiball", True, [DRAGON_ID])))
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, block(command("StopBall", -18, 10,
                ["RestoreToSpeedBeforeActionExecution"], ["EF"], 0),
                command("FindMultiballSubjects", 10, 11, True, [DRAGON_ID], absent, present))]


def build_multiball_tables(multiball_rows, level_rows, *, support_id=SUPPORT_ID):
    """保留原生成长比例，100级裸HP/ATK均为5000；像素和support独立。"""
    donor = "1111711"
    row = copy.deepcopy(multiball_rows[donor][0])
    row[0:2] = [DRAGON_CODE + "_1", DRAGON_CODE]
    row[3:6] = ["0", "Dragon", ""]
    row[20:24] = [str(support_id), "(None)", "(None)", "(None)"]
    levels = copy.deepcopy(level_rows[donor])
    for basic_index in (1, 4):
        levels[0][basic_index] = str(DRAGON_MAX_LEVEL_STAT)
        levels[0][basic_index + 1] = DRAGON_STAT_CORRECTION
    return {
        "master/battle/multiball/multiball.orderedmap": {str(DRAGON_ID): [row]},
        "master/battle/multiball/multiball_level.orderedmap": {
            str(DRAGON_ID): levels},
    }


def amf_bytes(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("AMF roundtrip mismatch")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()


def remap_strings(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [remap_strings(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: remap_strings(v, old, new) for k, v in value.items()}
    return value


def build_effect_assets(read):
    """read(logical)->官方bytes；所有效果按自有路径复制，PNG不改像素。"""
    files = {}
    for old, new, stems in [
        ("lady_summoner_xm20", "campus_bianca_descent",
         ["lady_summoner_xm20_all", "lady_summoner_xm20_hit"]),
    ]:
        prefix = "battle/effect/skill_unique/" + old + "/"
        paths = [prefix + old + suffix for suffix in (".png", ".atlas.amf3.deflate")]
        paths += [prefix + stem + suffix for stem in stems
                  for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate")]
        for source in paths:
            raw = read(source)
            target = source.replace(old, new)
            if source.endswith(".amf3.deflate"):
                tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                raw = amf_bytes(remap_strings(tree, old, new))
            files["common", target] = raw
    return files
