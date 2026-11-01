"""Conservative element proposals; cross-element cloning remains separately gated."""
import re
import wf_describe

from .ability_fields import active_fields
from .drafts import DraftError

NAMES = ("Red", "Blue", "Yellow", "Green", "White", "Black")


def change_element_row(row, table, old, new):
    if type(old) is not int or type(new) is not int or old not in range(6) or new not in range(6):
        raise DraftError("属性必须为 0–5")
    result = list(row)
    if len(row) != wf_describe.layout(table)["ncols"]:
        return result, ["词条列数不符合已知布局"]
    if old == new:
        return result, []
    fields = active_fields(row, table)
    options = wf_describe.enum_options()
    for col, (block, field) in fields.items():
        if field == "kind":
            group = "precondition" if block.startswith("precondition") else block
            if group in {"during_accumulation_trigger", "instant_trigger"}:
                group = "trigger"
            enums = options.get(group, {})
            enum = enums.get(row[col], {}).get("en", "")
            if not enum and block not in {"opening", "instant_precontent"} and row[col] != "(None)":
                return list(row), ["未知属性枚举需人工核对"]
            if block == "instant_content" and row[col] == "720":
                return list(row), ["属性覆写 720 的跨色条件及空转风险需人工核对"]
            if "EnemyDamageBy" in enum:
                return list(row), ["属性追伤的伤害闭包需人工核对"]
            if NAMES[new] in enum:
                return list(row), ["词条已引用目标属性，跨色条件需人工核对"]
            if NAMES[old] in enum:
                wanted = enum.replace(NAMES[old], NAMES[new])
                matches = [key for key, value in enums.items() if value["en"] == wanted]
                if len(matches) != 1:
                    return list(row), ["属性效果没有唯一等价枚举"]
                result[col] = matches[0]
        elif field.endswith("character_groups"):
            parts = re.split(r"([/,])", row[col])
            if NAMES[new] in parts:
                return list(row), ["角色组已引用目标属性，需人工核对跨色条件"]
            result[col] = "".join(NAMES[new] if p == NAMES[old] else p for p in parts)
        elif field == "element":
            if row[col] == str(new + 1):
                return list(row), ["效果已引用目标属性，需人工核对"]
            if row[col] == str(old + 1):
                result[col] = str(new + 1)
    if table == "ability":
        if row[2] == "attack_" + NAMES[new].lower():
            return list(row), ["雕像组已引用目标属性，需人工核对"]
        if row[2] == "attack_" + NAMES[old].lower():
            result[2] = "attack_" + NAMES[new].lower()
    return result, []
