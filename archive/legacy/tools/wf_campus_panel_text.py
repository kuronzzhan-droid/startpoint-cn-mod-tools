"""两位校园角色的简洁说明；只返回文字，不修改任何战斗表行。

整组覆盖依赖 panel-description-override-v2，键取该组首行 c0。
原生 ability c3/c4、leader c1/c2 是觉醒字段，不能拿来写描述。
"""
from __future__ import annotations

from copy import deepcopy
from wf_featured_main_ability import main_description

REQUIRED_CAPABILITY = "panel-description-override-v2"
FLAT_STRING_TABLE = "master/string/custom_ability_string.orderedmap"
CODES = {"119989": "lady_summoner_campus", "149989": "wind_spgirl_campus"}

_BIANCA = {
    "active": (
        "幼龙不在场：召唤幼龙协力球，降低全场敌人攻击力；成功召唤后自身获得「幼龙回应」。\n"
        "幼龙在场：令其飞至上空向下吐息，对全场敌人造成火属性能力伤害，"
        "降低火属性抗性、增加FEVER槽，并使自身获得「幼龙吐息」，随后幼龙退场。\n"
        "幼龙持续驻场，直至被击倒或再次施放技能令其退场。"
    ),
    "leader": (
        "火属性共鸣时，火属性角色攻击力+200%、能力伤害+400%。\n"
        "火属性共鸣时，Fever模式中，火属性角色攻击力+200%。\n"
        "火属性共鸣时，每次获得「幼龙回应」：Fever槽+500，火属性角色技能槽+25%。\n"
        "火属性角色发动技能时：对全场敌人造成50倍火属性能力伤害。"
    ),
    # 2026-09-27 第二批（wf_balance_20260927b_bianca）：开局自充 75%→50%、吐息自充 50%→20%；a5 去主位后不带图标。
    # 2026-09-27 技能强化文案（wf_balance_20260927c_panels，R2）：第2行 = 536 开关行，写成官方格式、点明技能名、
    # 不写数值与秒数，与强化串 change_skill_lady_summoner_campus_dragon 同文（火共鸣是开关行的真实前置，保留）。
    "a1": (
        "战斗开始时：自身技能槽+50%。\n"
        "火属性共鸣时，强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性。\n"
        "火属性共鸣时，每次获得「幼龙吐息」，自身技能槽+20%，赋予队长攻击力提升200%效果，持续15秒。"
    ),
    "a2": (
        "火属性共鸣时，火属性角色发动技能时，对最近敌人造成10倍火属性能力伤害，冷却1秒。\n"
        "火属性共鸣时，火属性角色发动技能时，赋予队长攻击力提升100%效果，持续8秒。"
    ),
    # 2026-09-27 第三轮面板合并（wf_balance_20260927c_panels）：第3、4行数据同条件（持续·Fever、固有累积≥1）合并；
    # 「焰域研修」唯一来源（能力3 #1 的 629）带火属性共鸣，由它提供的效果不再写「火属性共鸣时，」。
    "a3": (
        " <icon id='main'>  火属性共鸣时，Fever模式中，火属性角色技能槽上限+20%。\n"
        " <icon id='main'>  火属性共鸣时，Fever模式中，每经过2秒，队长技能槽+5%，自身获得1层「焰域研修」。\n"
        " <icon id='main'>  Fever模式中，每层「焰域研修」使火属性角色能力伤害+50%、能力伤害额外乘区+1%。\n"
        " <icon id='main'>  Fever结束或自身倒下时，「焰域研修」清空。"
    ),
    "a4": "火属性共鸣时，Fever时间+15%。\nFever模式中，火属性角色技能充能速度+10%。",
    "a5": "火属性共鸣时，火属性角色发动技能：Fever槽+15%。",
    "a6": (
        "火属性角色发动技能时，火属性角色能力伤害+10%（最大+100%）。\n"
        "Fever模式中，火属性角色发动技能时，火属性角色攻击力+10%（最大+100%）。"
    ),
}

_CELTIE = {
    # 2026-09-27 技能强化文案规范（作者「技能里面不要重复描述强化后的效果」）：技能描述只写本体（最多10层），
    # 旗号 2 的不封顶只写在队长强化条目——wf_balance_20260927c_celtie。
    "active": (
        "向Boss突进并持续朝其释放十字双空牙（无Boss时选择最近敌人），对命中敌人造成基础合计75倍风属性伤害，"
        "伤害量以能力伤害加成判定。风属性共鸣且Fever模式中，技能倍率随「星风心得」成长，"
        "每层额外增加10倍（最多10层）。"
    ),
    # 2026-09-27 第二批：心得无上限逐层成长从能力3搬进队长，第4行注明队长同时给2层心得。
    # 2026-09-27 第三轮（c）：每层 2.5%→20%（口径 D1）；末行追加队长撤技能倍率封顶（能力1 I704，口径 U8）。
    # 2026-09-27 面板共鸣省略：「星风快门」「星风心得」只由带风共鸣的 629 授予，其层数/持有提供的效果不再写
    # 「风属性共鸣时，」（第5–6行；获取行第4行保留）；第7行是能力1 I704 开关行（前置 仅队长 + 风共鸣），
    # 共鸣是真实条件，保留——wf_balance_20260927c_celtie。
    # 2026-09-27 技能强化文案规范：第7行点名技能、与 change_skill_wind_spgirl_campus_leader 同文，去「Fever模式中，」
    # （开关行前置只有队长 + 风共鸣，Fever 判断在技能本体）。
    "leader": (
        "风属性角色攻击力+200%、能力伤害+400%。\n"
        "风属性共鸣时，强化弹射变为特殊剑士型，造成风属性伤害，伤害量以能力伤害加成判定。\n"
        "风属性共鸣时，Fever模式中，强化弹射时，对全场敌人追加10倍风属性能力伤害。\n"
        "风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得2层「星风快门」与2层「星风心得」。\n"
        "Fever模式中，弹射时消耗1层「星风快门」，连击+7。\n"
        "Fever模式中，每层「星风心得」使风属性角色能力伤害+20%、攻击力+20%。\n"
        "风属性共鸣时，强化『风中快门·十字双空牙』：技能倍率随「星风心得」层数持续提升。"
    ),
    # 2026-09-27 技能强化文案规范：第2行（能力1 I536 旗号 1 条目）改官方格式，点名技能、定性不写数字与秒数，
    # 与 change_skill_wind_spgirl_campus_fever 同文——wf_balance_20260927c_celtie。
    "a1": (
        "战斗开始时：自身技能槽+50%。\n"
        "风属性共鸣时，为『风中快门·十字双空牙』追加「赋予全队贯穿＋风属性角色能力伤害提升效果」"
        "与「赋予命中的敌人风属性抗性降低效果」。"
    ),
    # 2026-09-27 面板共鸣省略：「快门消费结算」「星风快门」「星风心得」的效果行不写「风属性共鸣时，」（获取行保留）。
    "a2": (
        "风属性共鸣时，风属性角色直接攻击分为3次，能力伤害+200%。\n"
        "Fever模式中，每消耗1层「星风快门」，Fever槽+5%。"
    ),
    "a3": (
        " <icon id='main'>  风属性共鸣时，Fever模式中，风属性角色合计每直接攻击35次，对全场敌人造成25倍风属性能力伤害。\n"
        " <icon id='main'>  风属性共鸣时，非Fever模式中，风属性角色合计每直接攻击35次，Fever槽+15%。\n"
        " <icon id='main'>  风属性共鸣时，Fever模式中，连击每达到7的倍数，风属性角色攻击力+70%（最大+700%）、技能槽+0.7%（回槽冷却时间：0.7秒）。\n"
        " <icon id='main'>  风属性共鸣时，Fever模式中，风属性角色发动技能时，自身获得1层「星风快门」。\n"
        " <icon id='main'>  Fever模式中，弹射时消耗1层「星风快门」，连击+7。\n"
        " <icon id='main'>  风属性共鸣时，每获得1层「星风快门」，自身获得1层「星风心得」。\n"
        " <icon id='main'>  Fever模式中，每层「星风心得」使风属性角色能力伤害+8%、攻击力+5%（最多10层）。"
    ),
    "a4": "风属性共鸣时，Fever模式中，每经过5秒，赋予全队贯穿效果，持续1秒。",
    "a5": "风属性共鸣时，Fever模式中，每经过5秒，赋予全队浮游效果，持续1秒。",
    "a6": (
        "风属性共鸣时，Fever模式中，每经过5秒，赋予全队1秒最大速度固定效果。"
    ),
}


def panel_descriptions(character_id):
    """返回主动、队长、A1–6全文；返回副本，调用方不会污染下次构建。"""
    cid = str(character_id)
    if cid not in CODES:
        raise ValueError(f"unsupported campus character: {cid}")
    texts = deepcopy(_BIANCA if cid == "119989" else _CELTIE)
    texts["a1"] = main_description(texts["a1"])
    # 2026-09-27 作者平衡第二批：碧安卡能力5 去主位限制，面板不再加主位图标（wf_balance_20260927b_bianca）。
    return texts


def active_description(character_id):
    """主动技能说明可直接写action_skill和character_text，不需要面板补丁。"""
    return panel_descriptions(character_id)["active"]


def native_flat_string_rows(character_id):
    """原生I536/I629/I722合法平表键；不靠空字符串隐藏任何能力行。"""
    cid = str(character_id)
    panel_descriptions(cid)  # 不支持的角色必须拒绝，不能落入另一角色的分支。
    if cid == "119989":
        return {
            # 2026-09-27 技能强化文案（wf_balance_20260927c_panels，R2）：官方格式，点明技能名。
            "change_skill_lady_summoner_campus_dragon": [[
                "强化『绯焰实习·幼龙点名』：幼龙吐息降低全场敌人的能力伤害抗性"
            ]],
            "lady_summoner_campus_fever_tick": [["获得1层「焰域研修」"]],
        }
    return {
        # 2026-09-27 技能强化文案规范：官方格式、点名技能、定性不写数字与秒数，与能力1 面板第2行同文。
        "change_skill_wind_spgirl_campus_fever": [[
            "为『风中快门·十字双空牙』追加「赋予全队贯穿＋风属性角色能力伤害提升效果」"
            "与「赋予命中的敌人风属性抗性降低效果」"
        ]],
        "wind_spgirl_campus_flip_stock": [["获得2层「星风快门」"]],
        "wind_spgirl_campus_flip_stock_ability": [["获得1层「星风快门」"]],
        "wind_spgirl_campus_fever_powerflip": [[
            "强化弹射变为特殊剑士型：风属性伤害（伤害量以能力伤害加成判定）"
        ]],
    }


def override_string_rows(character_id, ability_rows, leader_rows):
    """仅返回7个整组覆盖键；检查实际c0，不移动、删除或改写原战斗行。"""
    cid = str(character_id)
    texts = panel_descriptions(cid)
    code = CODES[cid]
    groups = {"leader": leader_rows}
    groups.update({f"a{slot}": ability_rows.get(cid + str(slot), [])
                   for slot in range(1, 7)})
    result = {}
    for slot, rows in groups.items():
        expected = code if slot == "leader" else code + "_" + slot[1:]
        if not rows or not rows[0] or rows[0][0] != expected:
            raise ValueError(f"{cid} {slot}: first-row string_id must be {expected}")
        result["desc_override_" + rows[0][0]] = [[texts[slot]]]
    return result


def metadata():
    return {
        "required_client_capabilities": [REQUIRED_CAPABILITY],
        "override_key_source": "first ability/leader row c0 (string_id)",
        "combat_rows_modified": False,
        "numeric_text": "fixed authored values at all ability levels; no dynamic level interpolation",
        "unsupported_client": "native generated ability text remains; active and native strings still work",
        "coverage": "character ability and leader panels; comparison and disabled-reason text remain native",
    }
