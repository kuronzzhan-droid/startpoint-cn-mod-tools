"""本次修改的能力组说明；机制表仍为原生字段，红M保留。"""
from wf_scutum_abilities_rows import CODE
from wf_featured_main_ability import main_description


def panel_string_rows():
    texts = {
        1: (
            "风属性共鸣时，浮游效果每持续5秒，风属性角色攻击力、直接攻击伤害+50%（各最大+200%）。\n"
            "风属性共鸣时，浮游效果中，风属性角色技能槽充能速度+15%。\n"
            "风属性共鸣时，战斗开始时，风属性角色技能槽+50%，自身技能槽额外+100%。"
        ),
        3: "\n".join(" <icon id='main'>  " + line for line in (
            "风属性共鸣时，发动强化弹射Lv3，赋予队伍中角色及协力球「收集」效果，持续5秒（CT：5秒）。",
            "自身持有「收集」且处于屏障效果中时，自身直接攻击伤害+20%（独立乘区）。",
            "自身持有「收集」时，自身或协力球直接攻击命中，向距离自身最近的敌人追加5倍风属性伤害，伤害量以直接攻击伤害加成判定（共用CT：5秒）。",
            "贯穿效果中，自身直接攻击命中时，赋予命中敌人风属性抗性降低2%效果，持续25秒（最大40%）。",
            "自身追加副位角色基础攻击力100%。",
        )),
        6: "风属性共鸣时，强化技能：连击效果变为5次直接攻击，总和伤害提升50%。",
    }
    texts[1] = main_description(texts[1])
    return {f"desc_override_{CODE}_{slot}": [[text]] for slot, text in texts.items()}
