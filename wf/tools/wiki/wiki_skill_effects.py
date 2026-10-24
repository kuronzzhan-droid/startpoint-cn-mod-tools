"""Readable numeric fields of additional conditions; no executable DSL output."""
from wf_dsl_sig import AC_CN
from wf_wiki_skill_format import ELEMENTS, field

PERCENT = {
    "ACAttackPoint", "ACSkillDamage", "ACAbilityDamage", "ACAbilityDamageResistance",
    "ACDirectAttackDamageResistance", "ACPowerFlipDamageResistance", "ACSkillDamageResistance",
    "ACFeverPoint", "ACStun", "ACOiuchi", "ACToleranceOfDebuff", "ACPowerFlipDamage",
    "ACDirectDamage", "ACSpeedup", "ACSkillGaugeCharging",
    "ACSeparatedTermPowerFlipDamage", "ACSeparatedTermDirectDamage",
}
BOOLEAN_STATES = {"ACParalysis", "ACFrozen"}


def condition_fields(ac, fmt, conditions):
    name, *args = ac
    label = AC_CN.get(name, "其他状态效果")
    values = []
    if name == "ACUnique":
        rows = conditions.get(str(args[0]), [])
        title = rows[0][1] if rows and len(rows[0]) > 1 else "固有状态"
        values = [field("增加层数", fmt.value(args[1]))]
        # UniqueConditionValues c3/c4 and ActionEvaluator resolveAdditionalCondition.
        if rows:
            row = rows[0]
            for column, label in ((3, "持续时间"), (4, "叠加上限"), (5, "弹射次数限制"),
                                  (6, "强化弹射次数限制"), (7, "结束强化弹射次数限制")):
                if len(row) > column and str(row[column]).lstrip("-").isdigit():
                    values.append(field(label, fmt.value(int(row[column]), "秒", permanent=True)
                                        if column == 3 else row[column]))
        return title, values
    if name in {"ACComboBoost", "ACGuts"}:
        values.append(field("弹射次数限制" if name == "ACComboBoost" else "不屈次数", fmt.value(args[0])))
        if len(args) > 1:
            values.append(field("连击增加", fmt.value(args[1])))
        return label, values
    if args:
        values.append(field("持续时间", fmt.value(args[0], "秒", permanent=True)))
    if name in PERCENT and len(args) >= 3:
        values.extend([field("效果量", fmt.value(args[1], "%")), field("叠加上限", fmt.value(args[2]))])
    elif name in {"ACToleranceOfElement", "ACDamageOfElement"} and len(args) >= 4:
        values.extend([field("属性", ELEMENTS.get(args[1], "指定属性")),
                       field("效果量", fmt.value(args[2], "%")), field("叠加上限", fmt.value(args[3]))])
    elif name in {"ACPoison", "ACRegeneration"}:
        values.append(field("每次基础伤害" if name == "ACPoison" else "每次基础回复", fmt.value(args[1])))
        if len(args) > 2:
            values.append(field("叠加上限", fmt.value(args[2])))
    elif name == "ACAdditionalDirectAttack":
        values.extend([field("追加直击次数", fmt.value(args[1])),
                       field("追加伤害修正", fmt.value(args[2], "%")),
                       field("叠加上限", fmt.value(args[3]))])
    elif name == "ACFixedSpeed":
        # FixedSpeedValues stores speedStrength, skillChargingStrength, in that order.
        values.extend([field("球速修正", fmt.value(args[1], "%")),
                       field("技能充能速度修正", fmt.value(args[2], "%")),
                       field("叠加上限", fmt.value(args[3]))])
    elif name not in BOOLEAN_STATES:
        # Preserve readable numeric evidence without inventing unverified units.
        values.extend(field(f"效果参数{i}", fmt.value(value)) for i, value in enumerate(args[1:], 1)
                      if isinstance(value, list) and all(isinstance(t, dict) for t in value))
    return label, values
