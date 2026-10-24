"""光杰拉德149999：将比例伤害移出碰撞回调，改为一次最近目标结算。"""
from copy import deepcopy
import hashlib
import math
import zlib

import wf_dsl
from wf_character_revision import encode_tree

CID, CODE = "149999", "white_wolf_gerald"
TARGET_SUBJECT = 301
NATIVE_DAMAGE_CAP = 9_999_999_999
SOURCE_SHA256 = {
    1: "a4287e3a4566ce8457ebf86d4a7f92d76f283e4d3eb52b097b820a8232c2a96e",
    2: "d83c4cc4cb0629c47e6bde4ae24863c709466c175a7b9fdcc5cb37d89f763b10",
}
ACTIVE_PATHS = {
    level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}.action.dsl.amf3.deflate"
    for level in (1, 2)
}


def _command(name, *arguments):
    return ["Command", [name, *arguments]]


def _block(*expressions):
    return ["Block", list(expressions)]


def nearest_percent_attack(rate, *, execute_below_percent=None, origin=-18,
                           target_subject=TARGET_SUBJECT):
    """返回单个原生选敌命令；供其他单次事件复用，不能放进逐碰撞回调。

    搜索原生 ALL_ENEMIES，排序后只保留一名主体；未找到目标不执行。
    原生HP条件的第一分支为>=，第二分支严格<，二者只创建一条攻击。
    RatioAttack始终遵守原生伤害上限、无敌、金属及转阶段保护。
    """
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 < rate <= 1:
        raise ValueError("rate must be finite and in (0, 1]")
    if not isinstance(target_subject, int) or isinstance(target_subject, bool) or target_subject <= 0:
        raise ValueError("target_subject must be a positive private binding")
    if not isinstance(origin, int) or isinstance(origin, bool) or origin == target_subject:
        raise ValueError("origin must be a distinct subject binding")

    def attack(ratio):
        return _command("CreateRatioAttack", target_subject, 1,
                        [{"min": float(ratio), "max": float(ratio)}])

    effect = attack(rate)
    if execute_below_percent is not None:
        if type(execute_below_percent) is not int or not 0 < execute_below_percent <= 100:
            raise ValueError("execute threshold must be an integer percentage in (0, 100]")
        effect = _command("ConditionalsHealthPointRatioOf", target_subject,
                          execute_below_percent, _block(effect), _block(attack(1)))
    return _command("FindNearSubjects", origin, 1, 49, ["DoNothing"], target_subject,
                    _block(effect))


def _walk(node, path=()):
    if isinstance(node, list):
        yield path, node
        for index, child in enumerate(node):
            yield from _walk(child, path + (index,))


def _at(tree, path):
    for index in path:
        tree = tree[index]
    return tree


def rewrite_skill(tree):
    """只删原强化全屏斩回调的比例命令，在同一时序块插入单次选敌。"""
    result = deepcopy(tree)
    nodes = list(_walk(result))
    ratios = [(path, node) for path, node in nodes if node and node[0] == "CreateRatioAttack"]
    if len(ratios) != 1:
        raise ValueError("expected exactly one legacy collision ratio command")
    ratio_path, ratio = ratios[0]
    if ratio != ["CreateRatioAttack", 2, 1, [{"min": 0.05, "max": 0.05}]]:
        raise ValueError("legacy percentage parameters changed")
    areas = [(path, node) for path, node in nodes if node and node[0] == "CreateHitArea"
             and ratio_path[:len(path)] == path]
    if len(areas) != 1:
        raise ValueError("legacy ratio must belong to one hit area")
    area_path, area = areas[0]
    if area[2] != -1 or area[9][0] != "Rectangle" or area[22] != ratio[1]:
        raise ValueError("legacy full-screen target binding changed")
    flags = [(path, node) for path, node in nodes if node and node[0] == "ConditionalsChangeSkillFlag"
             and ratio_path[:len(path) + 1] == path + (2,)]
    if len(flags) != 1 or flags[0][1][1] != 1:
        raise ValueError("legacy ratio must remain in enhanced flag 1 branch")
    if any(value == TARGET_SUBJECT for _path, node in nodes for value in node if type(value) is int):
        raise ValueError("private target binding already exists")
    # Both paths end in [expression_index, 1], because Command wraps its payload.
    if _at(result, ratio_path[:-1])[0] != "Command" or _at(result, area_path[:-1])[0] != "Command":
        raise ValueError("unexpected command wrapper")
    _at(result, ratio_path[:-2]).pop(ratio_path[-2])
    phase = _at(result, area_path[:-2])
    phase.insert(area_path[-2] + 1, nearest_percent_attack(0.05, execute_below_percent=5))
    return result


def patch_skill_bytes(raw, level):
    if level not in SOURCE_SHA256 or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256[level]:
        raise ValueError("skill source differs from the reviewed live baseline")
    return encode_tree(rewrite_skill(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]))


def metadata():
    return {
        "character_id": CID, "code_name": CODE,
        "enhanced_skill_only": True, "current_hp_ratio": 0.05,
        "execute_below_max_hp_percent": 5, "threshold_comparison": "strictly less than",
        "target_count_per_cast": 1, "native_selector": "ALL_ENEMIES, sorted and sliced to one",
        "damage_commands_per_selected_branch": 1, "normal_damage_and_effects_preserved": True,
        "native_damage_cap": NATIVE_DAMAGE_CAP,
        "unconditional_execute_guaranteed": False,
        "execute_method": "100% current HP through native RatioAttack",
        "native_cap_and_phase_rules_preserved": True,
        "native_protections": ["invincibility", "phase change", "metal enemies", "damage cap"],
        "requires_new_apk": False,
    }
