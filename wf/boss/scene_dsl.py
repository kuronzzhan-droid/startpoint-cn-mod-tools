"""Constructor signatures and actual action-reference slots for scene graphs."""
from __future__ import annotations

import wf_dsl_sig as sig
from .scene_import import walk
from .schema import iter_leaves
from wf.rules.multiplayer_inputs import ACTION_REFERENCES

EXTRA = {"ActionDsl", "Block", "Command", "Event", "None", "Some", "Immediate"}
ENUMS = {name for enum in sig.ENUMS.values() if isinstance(enum, dict) for name in enum}


def constructors(tree):
    errors = []
    def visit(node):
        if isinstance(node, dict):
            for value in node.values():
                visit(value)
        elif isinstance(node, list) and node:
            tag = node[0]
            if tag in ("Command", "Event"):
                if len(node) != 2 or not isinstance(node[1], list) or not node[1]:
                    errors.append("无效 " + tag + " 结构")
                    return
                command = node[1]
                known = sig.COMMANDS if tag == "Command" else sig.EVENTS
                if not isinstance(command[0], str) or command[0] not in known:
                    errors.append("未知 " + tag + " " + str(command[0]))
                    return
                if len(command) - 1 != len(known[command[0]]):
                    errors.append(command[0] + " 参数数量不匹配签名")
                for argument in command[1:]:
                    visit(argument)
                return
            if isinstance(tag, str) and tag[:1].isupper() and tag not in EXTRA | ENUMS:
                errors.append("未知构造 " + tag)
            for child in node:
                visit(child)
    visit(tree)
    if not isinstance(tree, list) or len(tree) != 12 or tree[0] != "ActionDsl" or not isinstance(tree[11], list) or tree[11][:1] != ["Block"]:
        errors.append("根必须为完整 ActionDsl/Block")
    return sorted(set(errors))


def references(state, resources):
    errors, tables = [], {}
    def table(logical):
        if logical not in tables:
            tables[logical] = state.table(logical)
        return tables[logical]
    for logical, tree in resources.items():
        if not logical.endswith(".action.dsl.amf3.deflate"):
            continue
        errors.extend(logical + ": " + issue for issue in constructors(tree))
        for _, expression in walk(tree):
            if not (isinstance(expression, list) and len(expression) == 2 and expression[0] == "Command"
                    and isinstance(expression[1], list) and expression[1]):
                continue
            node = expression[1]
            if not isinstance(node[0], str):
                errors.append(logical + " 命令名必须是字符串")
                continue
            action_column = ACTION_REFERENCES.get(node[0])
            if action_column is not None and len(node) > action_column:
                action = node[action_column]
                if isinstance(action, str) and action:
                    target = action if action.endswith(".deflate") else action + ".action.dsl.amf3.deflate"
                    if state.raw(target) is None:
                        errors.append(logical + " 程序缺失：" + target)
            if node[0] == "SpawnFunnel":
                if len(node) < 2 or not isinstance(node[1], list) or len(node[1]) != 2:
                    errors.append(logical + " 召唤目标格式无效")
                    continue
                kind, code = node[1]
                target = {"Funnel": "boss/funnel/general_funnel", "StandardFunnel": "boss/funnel/standard_funnel",
                          "Zako": "zako/general_zako"}.get(kind)
                if target is None or code not in table("master/battle/" + target + ".orderedmap"):
                    errors.append(logical + " 召唤物不存在：" + str(kind) + "/" + str(code))
            if node[0] == "ChangeBgm" and len(node) > 1:
                bgm = node[1]
                bgms = table("master/asset/bgm_asset.orderedmap")
                if not isinstance(bgm, str) or bgm not in bgms:
                    errors.append(logical + " BGM 未登记：" + str(bgm))
            if node[0] == "ChangeFieldAssets":
                if any(type(value) is not int or value < 0 for value in node[1:4]):
                    errors.append(logical + " 场地切换帧数须为非负整数")
                for option in node[4:]:
                    if not isinstance(option, list) or option[:1] not in (["None"], ["Some"]):
                        errors.append(logical + " 场地素材必须为 None 或 Some")
                    elif option[:1] == ["Some"]:
                        if len(option) != 2 or not isinstance(option[1], str):
                            errors.append(logical + " 场地 Some 素材格式无效")
                            continue
                        for suffix in (".png", ".parts.amf3.deflate", ".atlas.amf3.deflate", ".timeline.amf3.deflate"):
                            if state.raw(option[1] + suffix) is None:
                                errors.append(logical + " 场地素材缺失：" + option[1] + suffix)
    return sorted(set(errors))
