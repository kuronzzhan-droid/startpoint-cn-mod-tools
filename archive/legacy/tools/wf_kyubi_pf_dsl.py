"""Pure, guarded Kyubi DSL revisions. Does not access stores or devices."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from wf_dsl import iter_dsl_commands
from wf_client_legality import (
    action_dsl_element_problems, action_dsl_hit_area_target_problems,
    action_dsl_subject_binding_problems,
)

MAIN = tuple(f"battle/action/skill/action/rare5/fox_oracle_autumn$fox_oracle_autumn_{lv}"
             for lv in (1, 2))
SPECIAL_KEY = "ability_skill_fox_oracle_autumn_fever_pf"
SPECIAL = f"battle/action/skill/action/ability_skill/{SPECIAL_KEY}${SPECIAL_KEY}"
SUFFIX = ".action.dsl.amf3.deflate"
MAIN_DAMAGE_HASHES = dict(zip(MAIN, (
    "aa6f2e8e64699edbb292884745c8af820c44247e22fcdd9e65b04a81b2f1e17d",
    "f3a967b3a01a5fd559731e6848c0c78ffb8f7483d582a664a0f2ac250d21b99b",
)))
SPECIAL_BASE = "3bea9174d78046ba414750bd2c4cb30bd01258a05abd03b585dedc4a21627388"
# The PF art integration (commit 5e9a0c2a, 2026-09-06 13:37) inserted exactly this node
# between the hoisted 雷华缠球 effect and the Fever branch of the revised special PF.
# Live since 1.4.765; author package 1.1.1 and the store carry the same tree. It is
# matched whole, so a different node, order or count is still an unknown shape.
NATIVE_PF_ART = ["Command", [
    "ShowEffect", "fox_oracle_autumn_api_pf",
    ["SpecifyEffectDirectly",
     "battle/effect/skill_unique/fox_oracle_autumn_api/fox_oracle_autumn_api"],
    -18, ["BacksideOfCharacter"], ["PlayOnlyFirstSequence"], ["AB"], 0, 0, 0, True, True,
    ["Some", [{"min": 4.0, "max": 4.0}]],
]]


def tree_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _normal_branch(leader):
    """Allocate distinct subjects for the new non-Fever branch."""
    normal = deepcopy(leader[3])
    area, = iter_dsl_commands(normal, "CreateHitArea")
    if (area[19], area[21], area[22]) != (9, 10, 11):
        raise ValueError("unexpected special-PF subject allocation")
    area[19], area[21], area[22] = 12, 13, 14
    attack, = iter_dsl_commands(normal, "CreateNormalAttack")
    if attack[1] != 11:
        raise ValueError("unexpected special-PF hit subject")
    attack[1] = 14
    return normal


def _revised_body(previous):
    """Return the hoisted effect and Fever wrapper of a revised tree.

    Two layouts are known, both pinned whole: the revision's own output
    ``[effect, fever]`` and the live layout ``[effect, NATIVE_PF_ART, fever]``.
    The art node is removed so the caller can reverse the rest to SPECIAL_BASE.
    """
    body = previous[11][1]
    if len(body) == 3:
        if body[1] != NATIVE_PF_ART:
            raise ValueError("unknown revised special-PF shape: the node between the "
                             "hoisted effect and Fever is not the pinned PF art")
        del body[1]
    if len(body) != 2:
        raise ValueError(f"unknown revised special-PF shape: {len(body)} top-level nodes")
    effect, wrapper = body
    if wrapper[0] != "Command":
        raise ValueError("unknown revised special-PF shape: Fever is not a Command")
    return effect, wrapper


def _special(tree):
    if tree[10] == 3:
        # Prove an already revised tree reverses exactly to the known baseline.
        previous = deepcopy(tree)
        effect, wrapper = _revised_body(previous)
        fever = wrapper[1]
        leader = fever[1][1][0][1]
        if fever[0] != "ConditionalsFeverMode" or fever[2] != _normal_branch(leader):
            raise ValueError("unknown revised special-PF shape")
        fever[1][1].insert(0, effect)
        fever[2] = ["Block", []]
        previous[11][1] = [wrapper]
        previous[10] = 0
        for area in iter_dsl_commands(previous, "CreateHitArea"):
            radius = area[9][1][0]
            if radius["min"] != radius["max"] or radius["max"] not in (320, 480):
                raise ValueError("unknown revised special-PF radius")
            radius["min"] = radius["max"] = {320: 240, 480: 400}[radius["max"]]
        if tree_hash(previous) != SPECIAL_BASE:
            raise ValueError("revised special-PF differs from the supported revision")
        return tree
    if tree_hash(tree) != SPECIAL_BASE:
        raise ValueError("unknown special-PF source; refusing to replace it")
    fever = tree[11][1][0][1]
    effect, leader_wrapper = fever[1][1]
    fever[1] = ["Block", [leader_wrapper]]
    fever[2] = _normal_branch(leader_wrapper[1])
    tree[11][1] = [effect, ["Command", fever]]
    for area in iter_dsl_commands(tree, "CreateHitArea"):
        radius = area[9][1][0]
        radius["min"] = radius["max"] = {240: 320, 400: 480}[radius["max"]]
    tree[10] = 3
    return tree


def revise_tree(source, program: str):
    tree = deepcopy(source)
    if not (isinstance(tree, list) and len(tree) == 12 and tree[0] == "ActionDsl"
            and tree[10] in (0, 3)):
        raise ValueError("unsupported ActionDsl header")
    if program in MAIN:
        # Art and unique visual status nodes may be composed by another generator.
        attacks = list(iter_dsl_commands(tree, "CreateNormalAttack"))
        if tree_hash(attacks) != MAIN_DAMAGE_HASHES[program]:
            raise ValueError("unknown main-skill damage shape")
        tree[10] = 3
    elif program == SPECIAL:
        tree = _special(tree)
    else:
        raise ValueError("program is outside the three Kyubi programs")
    problems = (action_dsl_element_problems(tree, character_element=3)
                + action_dsl_subject_binding_problems(tree)
                + action_dsl_hit_area_target_problems(tree))
    if problems:
        raise ValueError("; ".join(problems))
    return tree
