"""Conservative, pure damage-zone rules. Conditional effects never lose their condition."""
from copy import deepcopy

import wf_describe

from .drafts import DraftError
from .variant_element import change_element_row

ZONES = {"skill": ("技能", 7), "power_flip": ("强化弹射", 5), "direct": ("直接攻击", 6),
         "ability": ("能力", 8), "all": ("全伤害", 9)}
ORDER = tuple(ZONES)
NORMAL = {"instant_content": ("34", "55", "33", "388", "723"),
          "during_content": ("2", "23", "1", "154", "421")}
SEPARATE = {"instant_content": ("694", "696", "693", "695", "723"),
            "during_content": ("411", "413", "410", "412", "421")}
UNIQUE = {"instant_content": ("565", "595", "519", "625"),
          "during_content": ("287", "317", "250", "347")}
CROSS_ELEMENT = "需人工：跨属性克隆仍被拦截；技能 DSL 的伤害/抗性降低、能力条件、音效及玛纳材料未完成联动验证"


def transform_row(row, table, zone):
    """Return copied row and manual reasons; unknowns remain byte-for-byte unchanged."""
    if zone not in ZONES or table not in ("ability", "leader_ability"):
        raise DraftError("未知乘区或词条表")
    layout = wf_describe.layout(table)
    if len(row) != layout["ncols"]:
        return list(row), ["词条列数不符合已知布局"]
    mode = row[5 if table == "ability" else 3]
    block = {"0": "instant_content", "1": "during_content"}.get(mode)
    if block is None:
        return list(row), ["开幕或未知触发方式需人工核对"]
    start = layout["blocks"][block]
    kind, target = row[start], ORDER.index(zone)
    options = wf_describe.enum_options()[block]
    name = options.get(kind, {}).get("en", "")
    if kind in SEPARATE[block]:
        replacement = SEPARATE[block][target]
    elif kind in NORMAL[block]:
        replacement = NORMAL[block][target]
    elif kind in UNIQUE.get(block, ()) and zone != "all":
        replacement = UNIQUE[block][target]
    elif "AttackSlayer" in name:
        return list(row), []
    elif any(word in name for word in ("Damage", "Slayer", "DirectAttack", "DirectAtttack")) or not name:
        return list(row), [f"{block} kind={kind}（{name or '未知'}）无已验证的等价映射；保留原值和固有条件"]
    else:
        # ATK and unrelated support effects stay exactly unchanged, including their targets.
        return list(row), []
    result = list(row)
    if row[start + 1] not in {"0", "5"}:
        return list(row), ["特殊效果目标不能自动扩为全队"]
    if block == "instant_content" and row[layout["blocks"]["instant_trigger"]] != "0":
        return list(row), ["瞬发触发的全队聚合语义未验证，保留原词条"]
    result[start] = replacement
    result[start + 1] = "5"
    result[start + 2] = row[start + 2] or "(None)"
    if table == "ability":
        result[1] = "true"
        for block_name in ("precondition1", "precondition2", "precondition3"):
            col = layout["blocks"][block_name]
            if result[col] == "202":
                result[col:col + 7] = ["0", "", "", "", "", "", ""]
    if block == "during_content":
        col = layout["blocks"]["during_trigger"]
        if (result[col] == "194" and result[col + 1] == "5" and result[col + 5] == "1"
                and result[col + 7] == "20" and result[col + 3:col + 5] == ["100000", "100000"]):
            # SumOfParty: aggregate before limit, do not multiply a party-wide bonus per holder.
            result[col + 1] = "9"
        elif result[col] != "0":
            return list(row), ["持续触发的全队聚合语义未验证，保留原词条"]
    return result, []


def remove_main_restriction(row, table):
    """Clone variants are unisonable: c1 is read from the FIRST row of an ability key."""
    result = list(row)
    if table == "ability":
        result[1] = "true"
        for col in (6, 13, 20):
            if result[col] == "202":
                result[col:col + 7] = ["0", "", "", "", "", "", ""]
    return result


def transform_skill(tree, zone):
    """Only exact four-field buff constructors; preserve duration, strength and count."""
    if zone not in ZONES:
        raise DraftError("未知乘区")
    buffs = ("ACSkillDamage", "ACPowerFlipDamage", "ACDirectDamage", "ACAbilityDamage")
    wanted = buffs[ORDER.index(zone)] if zone != "all" else "ACSkillDamage"
    manual = []
    def visit(node):
        if isinstance(node, dict):
            return {k: visit(v) for k, v in node.items()}
        if not isinstance(node, list):
            return deepcopy(node)
        if node and isinstance(node[0], str) and node[0] in buffs:
            if len(node) != 4:
                manual.append(f"{node[0]} 构造参数不是已验证的四字段")
                return deepcopy(node)
            return deepcopy(node) if zone == "all" else [wanted, *deepcopy(node[1:])]
        if node and isinstance(node[0], str) and node[0].startswith("AC") and (
                "Damage" in node[0] or node[0] in {"ACAdditionalDirectAttack", "ACAdversity", "ACOiuchi",
                                                   "ACSeparatedTerm", "ACSpecialEfficacy"}):
            manual.append(f"技能效果 {node[0]} 无等价映射")
        return [visit(v) for v in node]
    return visit(tree), manual
