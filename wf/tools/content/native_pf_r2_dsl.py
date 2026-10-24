"""Pure composition of locked official special/ranged PF trees for Inaho."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from wf_client_legality import (action_dsl_element_problems,
                                action_dsl_hit_area_target_problems,
                                action_dsl_subject_binding_problems)
from wf_dsl import encode_amf3, iter_dsl_commands, parse_dsl

TREE_HASHES = {
    ("special", 1): "f3349331d0d69148cf4b77493b5976a97344a0af9dfa0364edac88a8d571ba82",
    ("special", 2): "b1ca5a8e45b6850e10e5cf06ce2d768c1860084e0dc05bcf5bf158669e96db57",
    ("special", 3): "28d7310bbadd2fc11b256471ef50a20a7ab7a6478662164231321642258e5797",
    ("ranged", 1): "92dc0d8593197bc02b6e6be3b49b37afe733115174ad934bea5f261ba2020cd0",
    ("ranged", 2): "0e44b1f7f536ddb35fdd55a13c63c47c7428679f40ecb60be56c748767b11763",
    ("ranged", 3): "9b91221b1cbcc4ae12546b2eb328c327a8ccf404c0062c949223fa030ae7ef1a",
}
SOURCE_HASHES = {
    ("special", 1): "569f2082c4633bae7e71610c296d6ab141cfabe1f3c4e5e0034c46dbf3e22961",
    ("special", 2): "4ed6440b9ded6d435e2c2fb9a640541b2c3fc43c5c0068de41077bab07ad73f2",
    ("special", 3): "7bebfdd5fc3ff46f2a789f7d631ac02084afa0cd11f4f19f71037f7faba3447d",
    ("ranged", 1): "df889eb90bce338709d3bf5b944e69fbb1934744bf74214dcbc3c7534a66640a",
    ("ranged", 2): "0e41175b937b4a3c98974f088b98687bd3948ec0b65bf04800bc0b3d332bcafc",
    ("ranged", 3): "3311340a58b4c92e3ba9793e3f23aa1edfd74716d366756d715b313e3e37db2a",
}
SHARED_FX_PREFIX = "battle/effect/powerflip/"
PRIVATE_FX_PREFIX = SHARED_FX_PREFIX + "fox_oracle_autumn_native/"


def private_path(path):
    for family in ("effect_powerflip_attack_special", "effect_powerflip_attack_beam"):
        if path.startswith(SHARED_FX_PREFIX + family + "/"):
            return PRIVATE_FX_PREFIX + path[len(SHARED_FX_PREFIX):]
    return path


def private_references(value):
    """Rewrite only the two stock texture namespaces, preserving every number."""
    if isinstance(value, str):
        return private_path(value)
    if isinstance(value, list):
        return [private_references(item) for item in value]
    if isinstance(value, dict):
        return {key: private_references(item) for key, item in value.items()}
    return value


def digest(tree):
    return hashlib.sha256(json.dumps(tree, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _ranged_commands(node):
    """Strip donor lifecycle; rename only known labels and typed subject slots."""
    if not isinstance(node, list) or not node:
        return
    if node[0] == "Block":
        kept = []
        for entry in node[1]:
            name = entry[1][0]
            if entry[0] == "Command" and name in {"SetPowerFilpSuppress", "NotifyPowerflipEnd"}:
                continue
            _ranged_commands(entry[1])
            if entry[0] == "Event" and name == "Wait" and not entry[1][3][1]:
                continue
            kept.append(entry)
        node[1] = kept
        return
    slots = {"CreateHitArea": (2, 19, 21, 22), "ShowEffect": (3,),
             "CreateNormalAttack": (1,), "Wait": (), "ShakeCamera": ()}
    if isinstance(node[0], str) and node[0] in slots:
        for index in slots[node[0]]:
            if 0 <= node[index] < 255:
                node[index] += 100
        labels = {"ShowEffect": 1, "CreateHitArea": 1, "Wait": 2}
        if node[0] in labels:
            index = labels[node[0]]
            if node[index] not in ("", "*"):
                node[index] += "_ranged"
    for child in node[1:]:
        if isinstance(child, list):
            _ranged_commands(child)


def _enlarge_collision(collision):
    for area in iter_dsl_commands(collision, "CreateHitArea"):
        if area[9][0] != "Circle":
            raise ValueError("special source contains an unexpected non-circle attack")
        for term in area[9][1]:
            term["min"] = round(term["min"] * 1.6)
            term["max"] = round(term["max"] * 1.6)
    for effect in iter_dsl_commands(collision, "ShowEffect"):
        if "effect_powerflip_attack_special/powerflip_attack_special_" not in effect[2][1]:
            raise ValueError("special source contains an unexpected sphere effect")
        for term in effect[12][1]:
            term["min"] = round(term["min"] * 1.6, 8)
            term["max"] = round(term["max"] * 1.6, 8)


def compose(special, ranged, level):
    """Keep one native collision listener at runtime, and one native PF lifecycle.

    ConditionalsCombo uses ActionEvaluationResolver.initialCombo. The package must
    require kyubi-pf-initial-combo-v1 to snapshot the combo consumed by this flip.
    """
    for kind, tree in (("special", special), ("ranged", ranged)):
        if digest(tree) != TREE_HASHES.get((kind, level)):
            raise ValueError(f"unrecognized official {kind} Lv{level} source")
    tree = deepcopy(special)
    collision = tree[11][1][-1]
    if collision[0] != "Event" or collision[1][0] != "CollisionOfBallAndEnemy":
        raise ValueError("official special collision event is not the final block")
    _enlarge_collision(collision)
    strong = deepcopy(collision)
    first, last = iter_dsl_commands(strong, "CreateHitArea")
    if last[14] != ["CalculatedUsingMaxNumOfHits", 1]:
        raise ValueError("official special final hit must remain one hit")
    first[14][1] += 2
    normal = lambda: ["Block", [deepcopy(collision)]]
    combo = ["Command", ["ConditionalsCombo", 35, ["Block", [strong]], normal()]]
    resonance = ["Command", ["ConditionalsUnifyElement", 3, 6, ["Block", [combo]], normal()]]
    tree[11][1][-1] = ["Command", ["ConditionalsFeverMode", ["Block", [resonance]], normal()]]
    donor = deepcopy(ranged[11])
    _ranged_commands(donor)
    tree[11][1].extend(donor[1])
    problems = (action_dsl_element_problems(tree, character_element=3)
                + action_dsl_hit_area_target_problems(tree)
                + action_dsl_subject_binding_problems(tree))
    if problems:
        raise ValueError("; ".join(problems))
    if parse_dsl(encode_amf3(tree))["tree"] != tree:
        raise ValueError("native PF AMF3 roundtrip failed")
    return tree
