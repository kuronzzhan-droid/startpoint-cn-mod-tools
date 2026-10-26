"""Explicit quest stat assignment/scaling and replayable parameter diagnostics."""
from __future__ import annotations

from wf.rules.catalog import result

STAT_FAMILIES = {
    "hp": ("hpValue", "hpScale", "hpMultiplier"),
    "attack": ("attackValue", "attackScale", "attackMultiplier"),
}


def validate_stat_modes(parameters):
    for fields in STAT_FAMILIES.values():
        supplied = [field for field in fields if field in parameters]
        if len(supplied) > 1:
            raise ValueError("同一属性只允许一种写入方式：" + ", ".join(supplied))


def merge_parameters(common, specific):
    """An explicit tier setting replaces the common setting for that stat."""
    validate_stat_modes(common)
    validate_stat_modes(specific)
    merged = dict(common)
    for fields in STAT_FAMILIES.values():
        if any(field in specific for field in fields):
            for field in fields:
                merged.pop(field, None)
    return {**merged, **specific}


def record_parameters(state, kind, path, before, after, parameters, mapping):
    changes = getattr(state, "parameter_changes", [])
    checks = getattr(state, "parameter_checks", [])
    quest = f"{kind}:{'/'.join(path)}"
    for stat, fields in STAT_FAMILIES.items():
        for field in fields:
            if field not in parameters:
                continue
            mode = "scale" if field.endswith("Scale") else "absolute"
            deprecated = field.endswith("Multiplier")
            repeated = mode == "scale" and any(
                c["quest"] == quest and c["stat"] == stat and c["mode"] == "scale" for c in changes)
            entry = {"quest": quest, "parameter": field, "stat": stat,
                     "mode": mode, "input": parameters[field], "deprecated": deprecated,
                     "repeatScale": repeated,
                     "values": [{"target": target, "column": column,
                                 "before": before[column], "after": after[column]}
                                for target, column in zip(("zako", "funnel", "boss"), mapping[field])]}
            changes.append(entry)
            if deprecated:
                checks.append(result("boss.parameter-deprecated", "问题",
                    f"{field} 是绝对值、已弃用；直接覆盖当前值，请改用 {stat}Value。",
                    quest=quest, parameter=field, deprecated=True, mode=mode))
            if mode == "scale":
                message = (f"{field} 按当前草稿的值相乘；同一草稿再次写入会再乘一次。"
                           + ("本次已有此前的缩放操作，将继续累乘。" if repeated else ""))
                checks.append(result("boss.parameter-scale", "满足", message,
                                     quest=quest, parameter=field, repeatScale=repeated))
    state.parameter_changes, state.parameter_checks = changes, checks


def parameter_report(state):
    return {"parameterChanges": getattr(state, "parameter_changes", [])}
