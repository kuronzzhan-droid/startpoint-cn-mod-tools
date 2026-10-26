"""校园希尔媞冲刺十字剑风；纯构建，不写包或live。

采用官方异类技能的原生加成选择：伤害量按能力伤害加成判定。
技能/PF 来源标记、对应抗性与独立乘区仍遵循原生规则，不需要新 APK。
"""
from __future__ import annotations

from copy import deepcopy
import math
import zlib

import wf_dsl
import wf_dsl_sig
import wf_client_legality as legality
from wf_celtie_skill_growth import with_leader_uncapped_growth, with_starwind_growth

CODE = "wind_spgirl_campus"
PROGRAM_PATHS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in (1, 2))
REQUIRED_CAPABILITIES = ()
SUFFIX = ".action.dsl.amf3.deflate"
EFFECT_RENAMES = {"wind_spgirl_1anv": "campus_celtie_cross",
                  "wind_spgirl_4anv": "campus_celtie_dash"}
HORIZONTAL_EFFECT = "battle/effect/skill_unique/campus_celtie_cross/campus_celtie_cross_slash_horizontal"


def value(number):
    return [{"min": number, "max": number}]


def cmd(name, *args):
    return ["Command", [name, *args]]


def block(*nodes):
    return ["Block", list(nodes)]


def walk(tree):
    yield tree
    if isinstance(tree, list):
        for item in tree:
            yield from walk(item)


def nodes(tree, kind):
    return [n for n in walk(tree) if isinstance(n, list) and n and n[0] == kind]


def one(tree, kind):
    found = nodes(tree, kind)
    if len(found) != 1:
        raise ValueError(f"official donor must contain one {kind}; got {len(found)}")
    return found[0]


def ability_damage_reference(tree):
    """只修改加成选择字段；保留原生攻击、命中、倍率和演出。"""
    result = deepcopy(tree)
    result[10] = 2
    for area in nodes(result, "CreateHitArea"):
        if nodes(area[23], "CreateNormalAttack"):
            area[24] = 2
    return result


def parse(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def encode(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("AMF roundtrip differs")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()


def remap(tree):
    if isinstance(tree, str):
        for source, target in EFFECT_RENAMES.items():
            tree = tree.replace(source, target)
        return tree
    if isinstance(tree, list):
        return [remap(item) for item in tree]
    if isinstance(tree, dict):
        return {key: remap(item) for key, item in tree.items()}
    return tree


def condition(subject, status, target_kind=3):
    return cmd("CreateCondition", subject, [status], value(1),
               ["GenericConditionHitEffect"], True, False, "", None,
               False, target_kind, value(1), False)


def enhanced(*nodes_):
    return cmd("ConditionalsChangeSkillFlag", 1, block(*nodes_), block())


def allies(subject, target, elements, *actions):
    return cmd("FindAllSubjects", subject, target, elements, [], [], [], [],
               ["DoNothing"], block(*actions))


def _landing(slash_donor):
    """两条互斥的dash结局使用独立副本；超时块不读取碰撞绑定的敌人。"""
    body = deepcopy(slash_donor[11])
    stop = one(body, "StopBall")
    stop[2] = 87  # 27帧蓄势＋60帧两拍；恢复技能前速度，不带出dash速度40。
    reference = one(body, "CreateReferencePoint")
    vertical = next(n for n in nodes(reference, "ShowEffect")
                    if n[2][0] == "SpecifyEffectDirectly")
    horizontal = deepcopy(vertical)
    horizontal[1] = "campus_celtie_horizontal"
    horizontal[2][1] = HORIZONTAL_EFFECT
    horizontal[9] = math.pi / 2
    reference[11][1].insert(1, ["Command", horizontal])
    areas = nodes(reference, "CreateHitArea")
    if len(areas) != 2:
        raise ValueError("first-anniversary donor must have exactly two hit areas")
    for area, multiplier in zip(areas, (25 * 75 / 70, 45 * 75 / 70)):
        if area[9] != ["Rectangle", value(300), value(3000)]:
            raise ValueError("first-anniversary donor rectangle changed")
        area[1] = "*"  # 每拍独立组；组内两臂共享按敌人ID计数。
        area[6] = math.pi / 4
        area[12] = ["NWay", 2, math.pi / 2]
        area[14] = ["CalculatedUsingMaxNumOfHits", 1]
        area[15] = ["Some", value(1)]
        attack = one(area, "CreateNormalAttack")
        attack[2] = 4  # 原生元素编号4=风，非角色表元素编号3。
        attack[5:8] = [0, value(multiplier), value(0)]
        attack[8:13] = [False] * 5
        # 先施加命中减抗，命中的这次攻击即可受益。
        area[23][1].insert(0, enhanced(condition(area[22],
            ["ACToleranceOfElement", value(900), 4, value(-.25), value(1)])))
    # 不继承原1anv的神速剑技标记或加速；仅保留蓄势与两拍主体。
    body[1] = body[1][:3]
    cleanup = [cmd("HideEffect", "ダッシュ軌跡")]
    cleanup += [cmd("RemoveEvent", tag) for tag in
                ("花びらAリピート", "花びらBスタート", "花びらBリピート")]
    body[1][0:0] = cleanup
    return body


def build_skill(level, official_bytes_loader, *, boss_target=True):
    """返回两档原生 DSL；按能力主加成计算，保留技能来源规则。"""
    if level not in (1, 2):
        raise ValueError("skill evolution must be 1 or 2")
    def donor(code):
        path = f"battle/action/skill/action/rare5/{code}${code}_{level}{SUFFIX}"
        return parse(official_bytes_loader(path))
    dash, slash = donor("wind_spgirl_4anv"), donor("wind_spgirl_1anv")
    near = deepcopy(one(dash, "FindNearSubjects"))
    move = one(near, "MoveBall")
    if move != ["MoveBall", -18, ["GH", 0], 0, 60, 40, ["KeepGoing"], True]:
        raise ValueError("fourth-anniversary dash shape changed")
    collision = one(near, "CollisionOfBallAndSpecificEnemy")
    if collision[1:4] != [0, 60, 1]:
        raise ValueError("fourth-anniversary collision lifecycle changed")
    collision[6] = _landing(slash)
    collision[7] = _landing(slash)
    buffs = enhanced(
        allies(40, 97, [], condition(40, ["ACPiercing", value(900)], 2)),
        allies(41, 33, [4], condition(41,
            ["ACAbilityDamage", value(900), value(1), value(1)])))
    result = deepcopy(dash)
    result[11] = block(buffs, with_starwind_growth(near))
    result = ability_damage_reference(remap(result))
    if boss_target:
        from wf_celtie_boss_lock import boss_lock
        result = boss_lock(result)
    # 2026-09-27 第三轮（c）：当队长且风共鸣（能力1 I704 → 旗号 2）时心得层数不封顶。
    result = with_leader_uncapped_growth(result)
    validate(result)
    return result


def validate(tree):
    problems = (legality.action_dsl_element_problems(tree, character_element=3)
        + legality.action_dsl_subject_binding_problems(tree)
        + legality.action_dsl_lookup_scope_problems(tree)
        + legality.action_dsl_hit_area_target_problems(tree))
    for node in walk(tree):
        if not (isinstance(node, list) and len(node) == 2 and node[0] in ("Command", "Event")):
            continue
        registry = wf_dsl_sig.COMMANDS if node[0] == "Command" else wf_dsl_sig.EVENTS
        instruction = node[1]
        if instruction[0] not in registry or len(instruction)-1 != len(registry[instruction[0]]):
            problems.append("unknown instruction or arity: " + str(instruction[0]))
    if problems:
        raise ValueError("; ".join(problems))


def effect_assets(official_bytes_loader):
    """私有dash与双空牙资源；横向复制共享图集但静音，全部原始PNG不改。"""
    tree = build_skill(2, official_bytes_loader)
    effects = {n[1] for n in nodes(tree, "SpecifyEffectDirectly")}
    files = {}
    reverse = {target: source for source, target in EFFECT_RENAMES.items()}
    for effect in sorted(effects):
        source = effect.removesuffix("_horizontal")
        for target, donor in reverse.items():
            source = source.replace(target, donor)
        for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate"):
            data = remap(parse(official_bytes_loader(source + suffix)))
            if effect == HORIZONTAL_EFFECT and suffix.startswith(".timeline"):
                data["sounds"] = []
            files["common", effect + suffix] = encode(data)
        source_family = source.rsplit("/", 1)[0]
        source_atlas = source_family + "/" + source_family.rsplit("/", 1)[1]
        for suffix in (".png", ".atlas.amf3.deflate"):
            raw = official_bytes_loader(source_atlas + suffix)
            target = remap(source_atlas + suffix)
            files["common", target] = (encode(remap(parse(raw)))
                if suffix.endswith(".deflate") else raw)
    return files
