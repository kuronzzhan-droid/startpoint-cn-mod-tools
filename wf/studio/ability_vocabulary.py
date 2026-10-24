"""Shared glossary groups and field units, using the describe module's layout."""
from __future__ import annotations

import wf_describe as describe

GROUPS = {
    "precondition": ("前置条件", "AbilityPreconditionMasterValue", None, ["precondition"]),
    "trigger": ("瞬发 / 累积触发", "InstantAbilityTriggerMasterValue", None, ["instant_trigger"]),
    "during_trigger": ("持续触发", "DuringAbilityTriggerMasterValue", None, ["during_trigger"]),
    "instant_content": ("瞬发效果", "InstantAbilityContentMasterValue", None, ["instant_content"]),
    "during_content": ("持续效果", "CommonAbilityContentMasterValue", None, ["during_content"]),
    "target": ("效果目标", "AbilityTargetMasterValue", describe.TARGET_CN, ["target_instant", "target_during"]),
    "instant_puller": ("瞬发 / 累积来源", "InstantAbilityTriggerPullerMasterValue", describe.INSTANT_PULLER_CN, []),
    "during_puller": ("前置 / 持续来源", "DuringAbilityTriggerPullerMasterValue", describe.DURING_PULLER_CN, []),
    "precontent": ("瞬发前置效果", "InstantAbilityPrecontentMasterValue", describe.PRECONTENT_CN, []),
    "precontent_target": ("前置效果目标", "InstantAbilityPrecontentTarget",
                          {0: "自身", 1: "队长", 2: "2号位", 3: "3号位", 4: "沿用效果目标"}, []),
    "multiply": ("倍增触发", "InstantAbilityMultiplyTriggerMasterValue", {0: "无", **describe.MULTIPLY_CN}, ["multiply_trigger"]),
    "opening": ("开幕效果", "OpeningAbilityMasterValue", describe.OPENING_CN, ["opening"]),
    "mode": ("触发方式", "AbilityTriggerMasterValue", {0: "瞬发", 1: "持续", 2: "开幕"}, ["trigger"]),
    "element": ("属性", None, describe.ELEMENT_CN, []),
    "character_group": ("角色组", None, describe.GROUP_CN, []),
    "awake": ("觉醒方式", None, {0: "无", **describe.AWAKE_CN}, []),
    "boolean": ("布尔标记", None, {"false": "否", "true": "是"}, []),
    "cancelable": ("驱散标记", None, {0: "可驱散", 1: "不可驱散"}, []),
    "power_flip_levels": ("强化弹射计数等级", None, {1: "Lv1", 2: "Lv2", 3: "Lv3", 11: "Lv1以上", 12: "Lv2以上"}, []),
}

BLOCK_GROUPS = {"precondition": "precondition", "instant_trigger": "trigger", "during_accumulation_trigger": "trigger",
                "during_trigger": "during_trigger", "instant_content": "instant_content", "during_content": "during_content",
                "instant_precontent": "precontent", "opening": "opening"}


def enum_groups():
    result = describe.enum_options()
    enums = describe.enum_map()["enums"]
    extra_names = {"element": dict(enumerate(["All", "Red", "Blue", "Yellow", "Green", "White", "Black"])),
                   "awake": {0: "None", 1: "Switch", 2: "Addition"}}
    for group, (_, enum, cn, _) in GROUPS.items():
        if group in result:
            continue
        names = enums.get(enum, {}) if enum else {str(v): extra_names.get(group, {}).get(v, str(v)) for v in cn}
        result[group] = {v: {"en": en, "cn": cn.get(int(v) if v.isdigit() else v, en)} for v, en in names.items()}
    return result


def _unit(block, field):
    if field.startswith(("threshold.", "threshold2.", "start_threshold.", "mt.threshold.")):
        return "threshold"
    if field.startswith("strength."):
        return "strength" if block in ("instant_content", "during_content") else "percent"
    if field.startswith(("strength2.", "strength3.")) or field == "mt.additional_multiply":
        return "percent"
    if field.startswith("frame."):
        return "scaled_frames"
    if field.startswith("number."):
        return "scaled_count"
    if field == "cooltime":
        return "frames"
    if field == "instant_delay":
        return "seconds"
    if field in ("trigger_limit", "mt.trigger_limit", "flip_limit", "power_flip_limit", "end_power_flip_limit"):
        return "count"
    return None


def field_rules():
    result = {}
    for table in describe.table_kinds():
        layout = describe.layout(table)
        columns = {}
        for name, note in layout.get("head", []):
            field = note.split()[0]
            group = {"trigger": "mode", "awake_kind": "awake", "unisonable": "boolean"}.get(field)
            if group:
                columns[name[1:]] = {"enum": group}
        for raw_block, start in layout["blocks"].items():
            block = "precondition" if raw_block.startswith("precondition") else raw_block
            for offset, field, _ in describe.enum_map()["block_fields"].get(block, []):
                rule = {"block": raw_block, "field": field}
                group = None
                if field == "kind":
                    group = BLOCK_GROUPS.get(block)
                elif field == "target":
                    group = "precontent_target" if block == "instant_precontent" else "target"
                elif field in ("trigger_puller", "mt.trigger_puller"):
                    group = "instant_puller" if block in ("instant_trigger", "during_accumulation_trigger", "instant_content") else "during_puller"
                elif field.endswith("character_groups"):
                    group = "character_group"
                    rule["multiple"] = True
                else:
                    group = {"element": "element", "multiply_trigger": "multiply", "cancelable": "cancelable",
                             "by_each_trigger_puller": "boolean", "even_if_owner_dead": "boolean",
                             "end_power_flip_accepted_levels": "power_flip_levels"}.get(field)
                if group:
                    rule["enum"] = group
                elif unit := _unit(block, field):
                    rule["format"] = unit
                    if unit == "strength":
                        rule.update(kindColumn=start, group=block, endpoints=[start + 4, start + 5])
                if group or "format" in rule:
                    columns[str(start + offset)] = rule
        result[table] = columns
    return result


def strength_count_kinds():
    """Mirror _desc_content's count-like strength, including its endpoint guard."""
    result = {}
    for group in ("instant_content", "during_content"):
        result[group] = [value for value, entry in describe.enum_options()[group].items()
                         if not (group == "instant_content" and 251 <= int(value) <= 387)
                         and ((group == "instant_content" and int(value) in (203, 204, 413, 436, 459, 461, 468, 525))
                              or any(word in entry["cn"] for word in ("连击", "计数", "次数", "数量", "层", "等级")))]
    return result
