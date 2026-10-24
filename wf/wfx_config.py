"""Registry-backed validation for shipped v35 configuration keys and tags."""
from __future__ import annotations

import re

import wfx_registry


def configuration_checks(table, key, value=None):
    """Return capability names, problems and warnings; None means key-only input."""
    collection = {"custom_ability_string": "custom_ability_string_patterns",
                  "character_tag": "character_tag_patterns"}.get(table)
    if collection is None:
        return [], [], []
    for rule in wfx_registry.load().get(collection, []):
        if table != "character_tag" and rule.get("status") != "shipped":
            continue
        if not key.startswith(rule["prefix"]):
            continue
        names, problems, warnings = [rule["capability"]], [], []
        prefix, suffix = rule["prefix"], key[len(rule["prefix"]):]
        if prefix == "ModDualForm":
            if not suffix:
                return [], [], []  # Bare tag predates the configurable UID patch.
            if not re.fullmatch(r":[1-9][0-9]*", suffix):
                problems.append("ModDualForm 参数须为 :<十进制正整数uid>")
            return names, problems, warnings
        if not suffix:
            problems.append("键缺少编号后缀")
        if prefix in {"wfx_pf4_", "wfx_cid_", "wfx_unlock_"} and not re.fullmatch(r"[1-9][0-9]*", suffix):
            problems.append("编号须为规范十进制正整数（不允许前导零）")
        if prefix == "wfx_unlock_":
            if value is None:
                names.append(rule["revision_capability"])
                warnings.append("未提供位掩码值，按包含bit8/16的v35f能力检查")
            elif not re.fullmatch(r"0|[1-9][0-9]*", value):
                problems.append("解锁位掩码须为十进制非负整数")
            else:
                mask = int(value)
                if mask & ~rule["known_mask"]:
                    problems.append(f"解锁位掩码含未登记位（允许 {rule['known_mask']}）")
                if mask & rule["revision_mask"]:
                    names.append(rule["revision_capability"])
        elif prefix == "wfx_pf4_" and value is not None:
            if not re.fullmatch(r"[1-9][0-9]*(?::[0-9A-Fa-f]{6})?", value):
                problems.append("PF4值须为正整数门槛[:RRGGBB]")
        return wfx_registry.capability_closure(names), problems, warnings
    return [], [], []
