"""Extract non-visible skill values with branch and hit-area context.

Units and parameter positions follow ActionEvaluator/Environment and
AdditionalConditionKindTools from the local client. Node counts are never hits.
"""
from __future__ import annotations

from wf_wiki_skill_effects import condition_fields
from wf_wiki_skill_format import ELEMENTS, Formula, field
from wf_dsl_sig import AC_CN, CMD_CN


def hit_area(args, fmt):
    values = []
    shape = args[8] if len(args) > 8 else []
    if shape and shape[0] == "Circle":
        values.append(field("范围半径", fmt.value(shape[1])))
    elif shape and shape[0] == "Rectangle":
        values.append(field("范围宽×高", f"{fmt.value(shape[1])} × {fmt.value(shape[2])}"))
    lifetime = args[12] if len(args) > 12 else []
    if lifetime and len(lifetime) > 1:
        values.append(field("判定持续", fmt.value(lifetime[1], "秒")))
    elif lifetime and lifetime[0] == "RemainingFramesOfCurrentStateGroup":
        values.append(field("判定持续", "至当前动作组结束"))
    interval = args[13] if len(args) > 13 else []
    if len(interval) > 1:
        if interval[0] in {"CalculatedUsingMaxNumOfHits", "CalculatedUsingMaxNumOfHitsSLv"}:
            values.append(field("区间命中次数设定", fmt.value(interval[1])))
        elif interval[0] in {"SpecifyMinHitIntervalDirectly", "SpecifyMinHitIntervalSLv"}:
            values.append(field("最短命中间隔", fmt.value(interval[1], "秒")))
    maximum = args[14] if len(args) > 14 else []
    if maximum and maximum[0] == "Some":
        values.append(field("命中次数上限", fmt.value(maximum[1])))
    return values


def state_name(value, conditions):
    if isinstance(value, list) and value:
        if value[0] == "DCUnique" and len(value) > 1:
            rows = conditions.get(str(value[1]), [])
            return rows[0][1] if rows and len(rows[0]) > 1 else "固有状态"
        return AC_CN.get("AC" + value[0][2:], "指定状态")
    return "指定状态"


def branch_context(name, p, index, fmt, conditions):
    """ActionEvaluationResolver: binary predicates versus indexed branch choice."""
    if name == "ConditionalsNumCoffins":
        return f"棺材数量为 {index}"
    if name == "ConditionalsNumExecutionsOddOrEven":
        return "奇数次发动" if index == 0 else "偶数次发动"
    if name.startswith("ConditionalsNumExecutions") and name[-1:].isdigit():
        count = int(name[-1])
        if p[0]:
            return f"每 {count} 次循环的第 {index} 次发动"
        return f"第 {index} 次及以后发动" if index == count else f"第 {index} 次发动"
    if name == "ConditionalsProbability":
        return "概率选择分支"
    if name == "ConditionalsMainOrUnison":
        return "主位发动" if index == len(p) - 2 else "合击位发动"
    label = CMD_CN.get(name, "条件分支").replace("条件:", "")
    if name == "ConditionalsCombo":
        label = f"发动时连击 ≥ {fmt.value(p[0])}"
    elif name in {"ConditionalsHealthPointRatio", "ConditionalsHealthPointRatioOf"}:
        label = f"生命比例 ≥ {p[-3]}%"
    elif name == "ConditionalsConditionAccumulationNumber":
        label = f"{state_name(p[0], conditions)}层数 ≥ {p[1]}"
    elif name == "ConditionalsConditionExist":
        label = f"持有{state_name(p[1], conditions)}"
    elif name == "ConditionalsMultiballNumber":
        label = f"指定协力球数量 ≥ {p[2]}"
    elif name == "ConditionalsHitAreaHitCount":
        label = f"判定区累计命中 ≥ {p[1]} 次"
    return label + ("：成立" if index == len(p) - 2 else "：不成立")


def skill_numeric_details(tree, conditions=None):
    fmt, rows = Formula(), []
    conditions = conditions or {}

    def add(label, values, context, kind="effect"):
        rows.append({"node": len(rows) + 1, "kind": kind, "label": label,
                     "context": list(context), "values": values})

    def visit(value, context=(), area=()):
        if isinstance(value, dict):
            for child in value.values():
                visit(child, context, area)
            return
        if not isinstance(value, list):
            return
        if not (len(value) == 2 and value[0] in ("Command", "Event") and isinstance(value[1], list)):
            for child in value:
                visit(child, context, area)
            return
        name, *p = value[1]
        if name == "CreateHitArea":
            fields = hit_area(p, fmt)
            for index, child in enumerate(p):
                visit(child, context, fields if index == 22 else area)
            return
        if name == "CreateNormalAttack" and len(p) >= 6:
            add("伤害", [field("单次命中倍率", fmt.value(p[5], "倍")),
                         field("伤害属性", ELEMENTS.get(p[1], "指定属性")), *area], context, "damage")
        elif name in {"CreateRatioAttack", "CreateRatioHeal"} and len(p) >= 3:
            healing = name == "CreateRatioHeal"
            add("比例回复" if healing else "比例伤害", [field("计算基准", "目标当前生命" if p[1] == 1 else "目标最大生命"),
                field("比例", fmt.value(p[2], "%")), *area], context, "heal" if healing else "damage")
        elif name in {"CreateFixedAttack", "CreateNormalHeal"} and len(p) >= 2:
            label = {"CreateFixedAttack": "固定伤害", "CreateNormalHeal": "基础治疗"}[name]
            add(label, [field("数值", fmt.value(p[1])), *area], context)
        elif name == "CreateBarrier" and len(p) >= 2:
            add("屏障", [field("计算基准", "目标最大生命"), field("比例", fmt.value(p[1], "%"))], context)
        elif name == "CreateCondition" and len(p) >= 2:
            for ac in p[1]:
                if isinstance(ac, list) and ac and isinstance(ac[0], str):
                    label, fields = condition_fields(ac, fmt, conditions)
                    if len(p) > 2:
                        fields.append(field("基础施加概率", fmt.value(p[2], "%")))
                    if len(p) > 10:
                        fields.append(field("施加倍率", fmt.value(p[10], "倍")))
                    add(label, [*fields, *area], context, "condition")
        elif name in {"AddSkillPoint", "SubtractSkillPoint", "AddCombo", "AddFeverPoint"}:
            is_gauge = name in {"AddSkillPoint", "SubtractSkillPoint"}
            val = p[1] if is_gauge else p[0]
            label = {"AddSkillPoint": "技能充能", "SubtractSkillPoint": "技能扣槽", "AddCombo": "增加连击", "AddFeverPoint": "增加Fever值"}[name]
            add(label, [field("数值", fmt.value(val, "%" if is_gauge else ""))], context)
        elif name == "BindConditionAccumulationVariable" and len(p) >= 5:
            add("叠层成长规则", [field(fmt.variable(p[1]), f"min(状态层数 ÷ {fmt.value(p[3])}, {fmt.value(p[4])})")], context, "formula")
        for index, child in enumerate(p):
            branch = context
            if name.startswith("Conditionals") and isinstance(child, list) and child and child[0] in ("Block", "Command", "Event"):
                branch = (*context, branch_context(name, p, index, fmt, conditions))
            elif name == "Wait" and index == len(p) - 1:
                branch = (*context, f"延迟 {fmt.value(p[0], '秒')}")
            visit(child, branch, area)

    visit(tree)
    return {"rows": rows, "notes": [
        "箭头表示技能 Lv1→满级；能力成长、叠层成长另列。倍率是单次命中基础倍率，未计实战攻击力、增伤与耐性。",
        "多目标与条件分支会分别列出；条目数不等于攻击段数，不应直接相加。命中次数设定也不保证全部命中。",
        "持续时间按每秒60帧换算；超出客户端永久状态阈值的状态显示为持续至战斗结束。",
    ] if rows else []}
