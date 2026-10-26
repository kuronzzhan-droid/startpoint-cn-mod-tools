"""Static ActionDSL validation recovered from the B tool lineage.

Signature tables stay in wf_dsl_sig; imports are local to avoid a compatibility
module import cycle when callers import either module first.
"""
from __future__ import annotations


class DslSignatureError(ValueError):
    """ActionDSL 命令签名、参数类型或受控编辑范围不合法。"""


def _dsl_type_ok(value, expected: str) -> bool:
    """按反编译签名校验可静态确认的序列化类型。"""
    from wf_dsl_sig import ENUMS
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "Number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "Boolean":
        return isinstance(value, bool)
    if expected == "String":
        return isinstance(value, str)
    if expected == "Array":
        return isinstance(value, list)
    if expected == "Option<SLvValue>":
        # Native TypePacker retains this generic argument; the AS3 constructor
        # signature only says Option. Some(number) reaches concreteArray and
        # raises F1034 before the action can run.
        return (value == ["None"] or (
            isinstance(value, list) and len(value) == 2 and value[0] == "Some"
            and isinstance(value[1], list) and all(
                isinstance(term, dict) and all(
                    _dsl_type_ok(term.get(bound), "Number")
                    for bound in ("min", "max")
                ) for term in value[1]
            )
        ))
    if expected == "Object":
        return isinstance(value, dict)
    if expected == "Dynamic":
        return True
    if expected == "ActionDslExpression":
        return (isinstance(value, list) and bool(value)
                and value[0] in {"Block", "Command", "Event"})
    # 其余已知类型都是 Haxe enum，序列化为 [构造名, *参数]。
    constructors = ENUMS.get(expected)
    if constructors is not None:
        if not isinstance(value, list) or not value or not isinstance(value[0], str):
            return False
        signature = constructors.get(value[0])
        if signature is None or len(signature) != len(value) - 1:
            return False
        return all(_dsl_type_ok(item, item_type)
                   for item, item_type in zip(value[1:], signature))
    # 逆向签名可能含尚未登记构造表的抽象类型；数量仍由调用方严格校验，
    # 未知类型不在这里臆测序列化形状。
    return True


def _validate_expression(node, path: str) -> None:
    from wf_dsl_sig import COMMANDS, EVENTS, PARAM_CN, TYPE_CN

    if not isinstance(node, list) or not node or not isinstance(node[0], str):
        raise DslSignatureError(f"{path}: ActionDSL 表达式形状非法")
    tag = node[0]
    if tag == "Block":
        if len(node) != 2 or not isinstance(node[1], list):
            raise DslSignatureError(f"{path}: Block 形状非法")
        for index, child in enumerate(node[1]):
            _validate_expression(child, f"{path}/Block[{index}]")
        return
    if tag not in {"Command", "Event"} or len(node) != 2:
        raise DslSignatureError(f"{path}: 未知表达式构造 {tag!r}")
    body = node[1]
    if not isinstance(body, list) or not body or not isinstance(body[0], str):
        raise DslSignatureError(f"{path}/{tag}: 命令体形状非法")
    name, args = body[0], body[1:]
    table = COMMANDS if tag == "Command" else EVENTS
    signature = table.get(name)
    if signature is None:
        raise DslSignatureError(f"{path}/{tag}:{name}: 官方签名表没有该构造")
    if len(args) != len(signature):
        raise DslSignatureError(
            f"{path}/{tag}:{name}: 参数数量 {len(args)} != {len(signature)}")
    for index, (value, expected) in enumerate(zip(args, signature), start=1):
        if tag == "Command" and ((name == "ShowEffect" and index == 12)
                                 or (name == "CreateHitArea" and index == 15)):
            expected = "Option<SLvValue>"
        # ActionEvaluator CreateCondition passes p8 through as nullable
        # linkedHitCheckKind (official shark actions use null here).
        # This does not make other enum parameters nullable.
        if tag == "Command" and name == "CreateCondition" and index == 8 and value is None:
            continue
        if not _dsl_type_ok(value, expected):
            label = PARAM_CN.get(name, {}).get(index, TYPE_CN.get(expected, expected))
            raise DslSignatureError(
                f"{path}/{tag}:{name} 参数{index}({label})类型不符:"
                f" expected={expected}, value={value!r}")
        if expected == "ActionDslExpression":
            _validate_expression(value, f"{path}/{tag}:{name}/p{index}")


def validate_action_dsl(tree) -> None:
    """验证完整 ActionDSL 的命令名、位置参数数量、类型与嵌套表达式。"""
    if not isinstance(tree, list) or not tree or tree[0] != "ActionDsl":
        raise DslSignatureError("根节点不是 ActionDsl")
    blocks = [item for item in tree[1:]
              if isinstance(item, list) and item and item[0] == "Block"]
    if not blocks:
        raise DslSignatureError("ActionDsl 根节点没有 Block")
    for index, block in enumerate(blocks):
        _validate_expression(block, f"ActionDsl[{index}]")


def _named_command_args(tree, names: set[str]) -> dict[str, list[list]]:
    found = {name: [] for name in names}

    def walk(value) -> None:
        if isinstance(value, list):
            if (len(value) == 2 and isinstance(value[0], str)
                    and value[0] in {"Command", "Event"}
                    and isinstance(value[1], list) and value[1]
                    and value[1][0] in names):
                found[value[1][0]].append(value[1][1:])
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(tree)
    return found


def assert_command_parameter_edits(before, after, allowed: dict[str, set[int]]) -> None:
    """限制指定命令只能修改声明过的 1-based 参数位。

    该门禁用于“倍率/比例调整”这类补丁：调用方必须先查 ``COMMANDS`` 与
    ``PARAM_CN``，明确允许改动的参数位。它会阻止把同为 ``int`` 的对象 ID
    误当成数值，例如把 ``AddSkillPoint`` 的 p1=20 改成 15。
    """
    from wf_dsl_sig import COMMANDS, EVENTS, PARAM_CN

    validate_action_dsl(before)
    validate_action_dsl(after)
    normalized = {
        str(name): {int(index) for index in indexes}
        for name, indexes in allowed.items()
    }
    before_commands = _named_command_args(before, set(normalized))
    after_commands = _named_command_args(after, set(normalized))
    for name, mutable in normalized.items():
        left = before_commands[name]
        right = after_commands[name]
        if len(left) != len(right):
            raise DslSignatureError(
                f"{name}: 命令数量改变 {len(left)} -> {len(right)}")
        parameter_count = len(COMMANDS.get(name, EVENTS.get(name, ())))
        invalid = sorted(index for index in mutable
                         if index < 1 or index > parameter_count)
        if invalid:
            raise DslSignatureError(f"{name}: 允许改动的参数位非法 {invalid}")
        for occurrence, (before_args, after_args) in enumerate(
                zip(left, right), start=1):
            for index, (old, new) in enumerate(
                    zip(before_args, after_args), start=1):
                if old != new and index not in mutable:
                    label = PARAM_CN.get(name, {}).get(index, f"参数{index}")
                    raise DslSignatureError(
                        f"{name}#{occurrence} p{index}({label})未经授权被修改:"
                        f" {old!r} -> {new!r}")
