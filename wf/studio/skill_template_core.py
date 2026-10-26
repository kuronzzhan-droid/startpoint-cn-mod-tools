"""Lossless in-memory edits to an official skill skeleton."""
from __future__ import annotations

import copy
import zlib

import wf_dsl
from wf.tools.character.character_requirements import resolve_effect_by_element

from .skill_template_validation import BOUND, number, slv, validate_tree, walk

DAMAGE_SLOTS = {"CreateNormalAttack": (6, "attack_multiplier"),
                "CreateRatioAttack": (3, "hp_ratio"), "CreateFixedAttack": (2, "fixed_damage")}


def _resolved_effect(value, context_element):
    if value[0] == "SpecifyEffectDirectly":
        return value[1]
    code = value[2]
    element = code - 1 if type(code) is int and 1 <= code <= 7 else context_element if code == 255 else None
    if type(element) is not int or not 0 <= element <= 6:
        raise ValueError("ResolveByElement 需要明确的角色内部元素上下文或显式 1..7 属性码")
    return resolve_effect_by_element(value[1], element)


def effect_paths(tree, context_element=None):
    """Concrete effect paths, resolving native element colour suffixes."""
    found = set()
    for _, value in walk(tree):
        if (isinstance(value, list) and len(value) >= 2
                and value[0] in ("SpecifyEffectDirectly", "ResolveByElement")
                and isinstance(value[1], str) and value[1].startswith("battle/effect/")):
            found.add(_resolved_effect(value, context_element))
    return sorted(found)


def effect_families(tree, context_element=None):
    return sorted({path.rpartition("/")[0] for path in effect_paths(tree, context_element)})


def damage_nodes(tree):
    """Editable attack multipliers, with effective root/area attribution."""
    rows = []

    def visit(value, path, owner):
        if not isinstance(value, list):
            return
        if value and isinstance(value[0], str):
            name = value[0]
            if name in DAMAGE_SLOTS:
                slot, kind = DAMAGE_SLOTS[name]
                code = value[2] if name == "CreateNormalAttack" else None
                rows.append({"path": path, "constructor": name,
                             "coefficient": copy.deepcopy(value[slot]), "coefficientKind": kind,
                             "element": code - 1 if type(code) is int and 1 <= code <= 7 else None,
                             "elementCode": code, "elementInherited": code == 255,
                             "attribution": owner, "subject": value[1]})
            for index, child in enumerate(value[1:], 1):
                inherited = value[24] or owner if name == "CreateHitArea" and index == 23 else owner
                visit(child, f"{path}/{index}", inherited)
        else:
            for index, child in enumerate(value):
                visit(child, f"{path}/{index}", owner)

    visit(tree, "", tree[10])
    return rows


def _coefficient(value, original, label):
    if type(value) in (int, float):
        number(value, label)
        if value < 0:
            raise ValueError(f"{label}: 伤害系数不能为负")
        bounds = [key for key in original[0] if BOUND.fullmatch(key)] if len(original) == 1 else []
        if len(bounds) != 2 or original[0].get("vlv"):
            raise ValueError(f"{label}: 多项运行时倍率需要逐项上下界，不能用单个数替换")
        return [{**original[0], **{key: value for key in bounds}}]
    result = copy.deepcopy(slv(value, label))
    if len(result) != len(original):
        raise ValueError(f"{label}: 不能增删运行时倍率项")
    return _merge_coefficients(original, result, label)


def _merge_coefficients(before, after, label):
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [_merge_coefficients(a, b, label) for a, b in zip(before, after)]
    if isinstance(before, dict) and isinstance(after, dict):
        result = copy.deepcopy(before)
        for key, value in after.items():
            if key not in before:
                raise ValueError(f"{label}: 不能新增运行时倍率字段 {key}")
            if BOUND.fullmatch(key):
                number(value, label)
                result[key] = value
            elif key == "vlv":
                result[key] = _merge_coefficients(before[key], value, label)
            elif before[key] != value:
                raise ValueError(f"{label}: 只能改变数值上下界，不能改运行时倍率变量")
        return result
    raise ValueError(f"{label}: 不能改变运行时倍率项结构")


def _scale_coefficients(value, factor):
    if isinstance(value, list):
        return [_scale_coefficients(item, factor) for item in value]
    if isinstance(value, dict):
        return {key: val * factor if BOUND.fullmatch(key) else
                _scale_coefficients(val, factor) if key == "vlv" else copy.deepcopy(val)
                for key, val in value.items()}
    return copy.deepcopy(value)


def _pointer(tree, pointer):
    result = tree
    for item in pointer.lstrip("/").split("/"):
        result = result[int(item)]
    return result


def _rewrite_effects(tree, mapping, context_element):
    for _, node in walk(tree):
        if (isinstance(node, list) and len(node) >= 2
                and node[0] in ("SpecifyEffectDirectly", "ResolveByElement")):
            value = _resolved_effect(node, context_element)
            if not isinstance(value, str):
                continue
            for old, new in sorted(mapping.items(), key=lambda item: -len(item[0])):
                if value == old or value.startswith(old + "/"):
                    node[:] = ["SpecifyEffectDirectly", new + value[len(old):]]
                    break


def encode_tree(tree):
    """Validate and encode a bare tree without applying coefficient edits again."""
    checks = validate_tree(tree)
    encoded = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(encoded)["tree"] != tree:
        raise ValueError("技能 DSL 编码后读回不一致")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = compressor.compress(encoded) + compressor.flush()
    return {"tree": tree, "raw": raw, "damageNodes": damage_nodes(tree), "checks": checks}


def rewrite_effects(tree, mapping, *, context_element=None):
    """Detach and replace effect references; coefficient/timing edits are not replayed."""
    result = copy.deepcopy(tree)
    _rewrite_effects(result, mapping, context_element)
    return encode_tree(result)


def clone_tree(tree, *, scale=1.0, node_coefficients=None, element=None,
               attribution=None, summon=None, effect_mapping=None, context_element=None):
    """Return a detached tree and stored DSL bytes; never modify/write the source.

    ``node_coefficients`` uses original JSON pointers from ``damage_nodes``.
    Explicit node values take precedence over the global scale. Timing, hitboxes,
    other numeric fields and SLvValue runtime multiplier keys remain unchanged.
    Attribution is ActionDsl.params[9] (tree[10]), not an attack Boolean field.
    """
    validate_tree(tree)
    number(scale, "scale")
    if scale < 0:
        raise ValueError("scale 不能为负")
    if element is not None and (type(element) is not int or not 0 <= element <= 5):
        raise ValueError("element 必须是角色内部元素 0..5，DSL 将显式写入 element+1")
    if attribution is not None and (type(attribution) is not int or attribution not in range(5)):
        raise ValueError("attribution 必须为 0 自动 / 1 技能 / 2 能力 / 3 PF / 4 直击")
    edits = {} if node_coefficients is None else node_coefficients
    if not isinstance(edits, dict):
        raise ValueError("node_coefficients 必须为节点路径到系数的对象")
    original = damage_nodes(tree)
    paths = {entry["path"] for entry in original}
    if set(edits) - paths:
        raise ValueError("伤害节点路径不存在：" + ", ".join(sorted(set(edits) - paths)))
    result = copy.deepcopy(tree)
    for entry in original:
        node = _pointer(result, entry["path"])
        slot = DAMAGE_SLOTS[node[0]][0]
        if entry["path"] in edits:
            node[slot] = _coefficient(edits[entry["path"]], node[slot], entry["path"])
        else:
            node[slot] = _scale_coefficients(node[slot], scale)
        if element is not None and node[0] == "CreateNormalAttack":
            node[2] = element + 1
    if attribution is not None:
        result[10] = attribution
        # A local nonzero hit-area override wins over the root. Rewrite those
        # explicit overrides too, so the requested skill attribution is effective.
        for _, node in walk(result):
            if isinstance(node, list) and node[:1] == ["CreateHitArea"] and node[24]:
                node[24] = attribution
    summon_summary = None
    if summon is not None:
        from .skill_template_summon import opening_summon
        statement, summon_summary = opening_summon(result, summon)
        result[11][1].insert(0, statement)
    if effect_mapping:
        _rewrite_effects(result, effect_mapping, context_element)
    return {**encode_tree(result),
            "summary": {"damageNodeCount": len(original), "scale": scale,
                        "nodeOverrideCount": len(edits), "element": element,
                        "elementCode": element + 1 if element is not None else None,
                        "attribution": attribution, "summon": summon_summary,
                        "timingAndGeometryPreserved": True,
                        "effectFamilies": effect_families(result, context_element)}}
