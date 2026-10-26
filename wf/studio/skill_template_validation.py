"""Strict, read-only validation for copied player ActionDSL programs."""
from __future__ import annotations

import copy
import math
import re

import wf_client_legality as legality
import wf_dsl
import wf_dsl_sig as signatures
from wf.rules.dsl_signature import _dsl_type_ok

BOUND = re.compile(r"(?:alv[2-6]?_)?(?:min|max)\Z")


def walk(value, path=""):
    """Yield every container with a stable JSON Pointer into the bare tree."""
    if isinstance(value, (list, dict)):
        yield path, value
        items = enumerate(value) if isinstance(value, list) else value.items()
        for key, child in items:
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            yield from walk(child, path + "/" + escaped)


def number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label}: 需要有限数值")
    return value


def slv(value, label):
    """SLvValue terms retain optional runtime multipliers, never scalar arrays."""
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}: 需要非空 SLvValue 数组，不能使用裸数值")
    for index, term in enumerate(value):
        if not isinstance(term, dict):
            raise ValueError(f"{label}/{index}: 需要含数值上下界的 SLvValue 项")
        bounds = [key for key in term if BOUND.fullmatch(key)]
        if not bounds and not term.get("vlv"):
            raise ValueError(f"{label}/{index}: SLvValue 缺少 min/max、alv 或 vlv 数值项")
        for bound in bounds:
            counterpart = bound[:-3] + ("max" if bound.endswith("min") else "min")
            if counterpart not in term:
                raise ValueError(f"{label}/{index}: SLvValue 数值上下界必须成对")
            number(term[bound], f"{label}/{index}/{bound}")
        if "vlv" in term:
            slv(term["vlv"], f"{label}/{index}/vlv")
    return value




def validate_tree(tree, character_element=None):
    """Reject known crash shapes before encode; return honest static check records."""
    if not isinstance(tree, list) or len(tree) != 12 or tree[0] != "ActionDsl":
        raise ValueError("DSL 必须是含 11 个参数的裸 ActionDsl 树，不能传解析结果包装对象")
    if (type(tree[1]) is not int or not isinstance(tree[2], list)
            or any(type(v) is not bool for v in tree[3:10]) or type(tree[10]) is not int):
        raise ValueError("ActionDsl 根参数形状错误")
    if not _dsl_type_ok(tree[2], "Option"):
        raise ValueError("ActionDsl 根条件 Option 构造名或形状错误")
    if tree[10] not in {0, 1, 2, 3, 4, 101, 102, 104, 131, 132, 133}:
        raise ValueError("ActionDsl params[9] 伤害归属编码非法")
    if not isinstance(tree[11], list) or tree[11][:1] != ["Block"]:
        raise ValueError("ActionDsl params[10] 必须为 Block，不能使用 DoNothing")
    # Native summon p13=null inherits context.slv. The historical signature
    # declares Object and rejects null; {} is only a private validation placeholder.
    checked = copy.deepcopy(tree)
    nullable = []
    for path, node in walk(checked):
        if not isinstance(node, list) or not node or not isinstance(node[0], str):
            continue
        if node[0] == "CreateSummonsMultiball" and len(node) == 14:
            # Native ActionEvaluator only registers the listener if p12 != null.
            # Its p13 is an optional integer ability-power binding ID; the AS3
            # signature's Object is a nullable boxed int, not a dictionary.
            if node[12] is None:
                node[12] = ["Block", []]
                nullable.append(path + "/12")
            if node[13] is None or type(node[13]) is int:
                node[13] = {}
                nullable.append(path + "/13")
            else:
                raise ValueError(f"{path}/13: 召唤能力等级需要 null 或整数能力绑定 ID")
    signatures.validate_action_dsl(checked)
    for path, node in walk(tree):
        if not isinstance(node, list) or not node or not isinstance(node[0], str):
            continue
        from .skill_template_slots import SLV_SLOTS
        slots = SLV_SLOTS.get(node[0], ())
        for slot in slots:
            # Empty optional numeric arrays are native zero/default values.
            if node[slot]:
                slv(node[slot], f"{path}/{slot}")
        if node[0] == "CreateNormalAttack":
            slv(node[6], path + "/6")
            if type(node[2]) is not int or node[2] not in {*range(1, 8), 255}:
                raise ValueError(f"{path}: 伤害元素必须为显式 1..7 或 255；内部元素需加 1")
        if node[0] == "CreateCondition":
            for effect in node[2]:
                if not _dsl_type_ok(effect, "AdditionalConditionKind"):
                    raise ValueError(f"{path}: 未知或形状错误的 AdditionalConditionKind 构造")
                for slot, expected in enumerate(signatures.ENUMS["AdditionalConditionKind"][effect[0]], 1):
                    if expected == "Array" and effect[slot]:
                        slv(effect[slot], f"{path}/condition/{slot}")
        if node[0] == "CreateHitArea":
            shape = node[9]
            for slot, expected in enumerate(signatures.ENUMS["Shape"][shape[0]], 1):
                if expected == "Array":
                    slv(shape[slot], f"{path}/shape/{slot}")
    from .skill_template_coordinates import coordinate_problems
    problems = (legality.action_dsl_element_problems(tree, character_element=character_element)
                + legality.action_dsl_hit_area_target_problems(tree) + wf_dsl.beam_direction_problems(tree)
                + legality.action_dsl_lookup_scope_problems(tree)
                + wf_dsl.coord_sys_source_problems(tree) + coordinate_problems(tree))
    if problems:
        raise ValueError("；".join(dict.fromkeys(problems)))
    checks = [{"level": "info", "code": "skill_template.dsl",
               "message": "裸树、构造签名、参数形状、元素码及主体坐标静态检查通过"}]
    if nullable:
        checks.append({"level": "info", "code": "skill_template.summon_nullable",
                       "message": "保留原生召唤空回调及 null/整数等级绑定；仅校验副本作类型占位并完整检查后续节点"})
    return checks
