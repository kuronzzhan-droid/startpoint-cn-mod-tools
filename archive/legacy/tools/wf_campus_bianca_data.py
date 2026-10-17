"""校园碧安卡：原生龙群、龙息与火 FEVER 能力伤害组合。"""
from __future__ import annotations

import copy

CID = "119989"
CODE = "lady_summoner_campus"
TEMPLATE_ID = "111021"
TEMPLATE_CODE = "lady_summoner_xm20"
PIXEL_CODE = "lady_summoner"
PACKAGE_ID = "campus-bianca-20260911"
NAME = "碧安卡"
TITLE = "绯焰召唤学讲师"
LEADER = "女王的开放课堂"
SKILL = "绯焰实习·幼龙点名"
DESCRIPTION = ("召唤小龙掠过战场，随后以龙息对领域内的敌人造成火属性伤害"
               "（适用能力伤害加成）＋赋予火属性抗性降低和攻击力降低效果／"
               "赋予火属性角色能力伤害提升效果／非FEVER状态下发动时，增加FEVER槽。")
PROFILE = ("星见大学召唤学的客座教师。成熟从容、讲解严谨，唯独在给小龙点名时会露出笑意。"
           "她把旧日的女王威仪收进酒红色外套，要求学生学会的第一件事，却是温柔地回应召唤物。")


def text_row():
    return [NAME, "BIANKA", PROFILE, TITLE, SKILL, DESCRIPTION,
            SKILL + "＋", DESCRIPTION, "(None)", "(None)", LEADER, "赤崎千夏"]


def walk_commands(tree):
    if isinstance(tree, list):
        if len(tree) == 2 and tree[0] == "Command":
            yield tree[1]
        for value in tree:
            yield from walk_commands(value)
    elif isinstance(tree, dict):
        for value in tree.values():
            yield from walk_commands(value)


def remap(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [remap(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: remap(v, old, new) for k, v in value.items()}
    return value


# 参数索引由 ActionDslCommand 的真实签名核对；只平移变量槽，不平移帧数/枚举/坐标。
VARIABLE_ARGS = {"CreateHitArea": (2, 19, 21, 22), "ShowEffect": (3,),
                 "MoveHitArea": (1,), "CreateNormalAttack": (1,),
                 "CreateCondition": (1,), "FindAllSubjects": (1,)}


def offset_slots(tree, offset):
    out = copy.deepcopy(tree)
    for command in walk_commands(out):
        for index in VARIABLE_ARGS.get(command[0], ()):
            if command[index] >= 0:
                command[index] += offset
    return out


def skill_tree(dragon, breath, clarisse, ability_donor, fever_donor, level):
    """4星六路龙群+5星龙息命中；不宣称不存在的驻场多球。"""
    out = copy.deepcopy(dragon)
    # 普通能力伤害乘区；不会伪造 createdByAbility 或改写技能来源事件。
    out[10] = 2
    for command in walk_commands(out):
        if command[0] == "CreateNormalAttack":
            command[6] = [{"min": 2.0 if level == 1 else 2.5,
                           "max": 2.5 if level == 1 else 3.0}]
    donor = offset_slots(breath[11], 100)
    for command in walk_commands(donor):
        if command[0] == "CreateNormalAttack":
            command[6] = [{"min": 1.2 if level == 1 else 1.6,
                           "max": 1.6 if level == 1 else 2.0}]
    # 原版 FindAllSubjects mask=113、element=[1] 是火属性己方。
    buff = next(copy.deepcopy(command) for command in walk_commands(clarisse)
                if command[0] == "FindAllSubjects" and "ACSkillDamage" in str(command))
    buff = offset_slots(["Command", buff], 200)
    native_ability = next(copy.deepcopy(c[2][0]) for c in walk_commands(ability_donor)
                          if c[0] == "CreateCondition" and c[2][0][0] == "ACAbilityDamage")
    for command in walk_commands(buff):
        if command[0] == "CreateCondition":
            command[2] = [copy.deepcopy(native_ability)]
            effect = command[2][0]
            effect[1] = [{"min": 900, "max": 900}]
            effect[2] = [{"min": 0.6 if level == 1 else 0.8,
                          "max": 0.8 if level == 1 else 1.0}]
    # 幼龙先入场，龙息稍后覆盖，变量槽互不冲突。
    out[11][1].insert(0, buff)
    fever = next(copy.deepcopy(c) for c in walk_commands(fever_donor) if c[0] == "AddFeverPoint")
    fever[1] = [{"min": 80 if level == 1 else 100, "max": 80 if level == 1 else 100}]
    out[11][1].insert(1, ["Command", ["ConditionalsFeverMode", ["Block", []], ["Command", fever]]])
    out[11][1].append(["Event", ["Wait", 80, "campus_breath", donor]])
    for command in walk_commands(out):
        if command[0] == "CreateHitArea":
            # area 的 0 继承外层；显式 2 避免 donor 局部覆盖回技伤。
            command[24] = 2
    validate_skill(out)
    return out


def validate_skill(tree):
    import wf_client_legality as legality
    import wf_dsl_sig as sig
    errors = (legality.action_dsl_element_problems(tree, character_element=1)
              + legality.action_dsl_subject_binding_problems(tree)
              + legality.action_dsl_hit_area_target_problems(tree))

    def expression(value):
        if not isinstance(value, list) or len(value) != 2 or value[0] not in ("Block", "Command", "Event"):
            errors.append("invalid ActionDslExpression")
            return
        if value[0] == "Block":
            for item in value[1]:
                expression(item)
            return
        command = value[1]
        registry = sig.COMMANDS if value[0] == "Command" else sig.EVENTS
        if not command or command[0] not in registry or len(command) - 1 != len(registry[command[0]]):
            errors.append("invalid native command signature")
            return
        for kind, arg in zip(registry[command[0]], command[1:]):
            if kind == "ActionDslExpression":
                expression(arg)
    expression(tree[11])
    if errors:
        raise ValueError("; ".join(errors))


def ability_rows(source):
    """官方126列行；有限充能/叠层与原生 I251 攻击，避免 FEVER 自循环。"""
    def row(key, index=0, **patch):
        out = copy.deepcopy(source[key][index])
        out = ["Red" if v in ("White", "Yellow", "Green", "Blue", "Black") else v for v in out]
        for column, value in patch.items():
            out[int(column[1:])] = str(value)
        return out
    a1 = [row("1110211"), row("1510451", 1, c51=20000, c52=40000)]
    a2 = [row("1310202", c35=600, c47=251),
          row("1510013", c109=154, c110=0, c111="", c113=50000, c114=100000)]
    a3 = [row("1310203", c34=5, c35=1200, c51=25000, c52=50000),
          row("1310202", c27=8, c28="", c29="", c34=5, c35=1200,
              c47=251, c51=2500000, c52=5000000)]
    a4 = [row("1310202", 1, c6=186, c28=0, c29="", c34=10, c35=600,
              c51=2500000, c52=5000000)]
    a5 = [row("1510011", c51=5000, c52=10000),
          row("1510013", c109=154, c113=20000, c114=40000)]
    a6 = [row("1510273", 1, c51=10000, c52=20000),
          row("1310133", 2, c51=7500, c52=15000)]
    result = {}
    for slot, rows in enumerate((a1, a2, a3, a4, a5, a6), 1):
        for row in rows:
            row[0] = f"{CODE}_{slot}"
            row[1:5] = ["false" if slot in (2, 3) else "true", "attack_red", "0", ""]
            validate_row(row, "ability")
        result[f"{CID}{slot}"] = rows
    return result


def leader_rows(source):
    rows = [copy.deepcopy(source["151001"][0]), copy.deepcopy(source["151009"][1]),
            copy.deepcopy(source["151009"][0])]
    rows[0][49:51] = ["80000", "120000"]
    rows[2][107], rows[2][111:113] = "154", ["100000", "150000"]
    for row in rows:
        row[0] = CODE
        row[:] = ["Red" if v == "White" else v for v in row]
        validate_row(row, "leader_ability")
    return rows


def validate_row(row, table):
    import wf_client_legality as legality
    errors = (legality.client_legality_problems(table, row)
              + legality.declared_block_field_problems(table, row)
              + legality.ability_element_column_problems(table, row, 1))
    if errors:
        raise ValueError(f"invalid native {table} row: {errors}")


def snapshot():
    return dict(fire_support=False, fire_fever_ability_damage=True,
        native_dragon_summon_attack=True, persistent_multiball=False,
        skill_buff_target_as=2, hit_area_buff_target_as=2,
        active_source="Main/UnisonSkillAction; ordinary AbilityDamage multiplier only; source flags retained",
        passive_damage="I251 EnemyDamageByAttackRed; native createdByAbility=true",
        fever_guards=dict(active="outside FEVER only", passive_fill="self skill, outside FEVER, CT10s, max10",
                          entry_charge="25-50%, CT20s, max5", entry_damage="25-50x, CT20s, max5"))
