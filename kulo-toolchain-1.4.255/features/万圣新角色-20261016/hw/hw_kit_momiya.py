# -*- coding: utf-8 -*-
"""莫弥亚「猎魔人装束的魔法剑士」169985 blade_witch_halloween：暗·协力球直击队长（特殊 PF）。

技能「猎魔人，出动！」= 母本 blade_witch 斩击演出与伤害保留；
- 赋予队伍（含召唤协力球，选择器 33）「贯通」15 秒；
- 场上没有召唤协力球：召唤 2 个「魔物万圣南瓜」(multiball 1699851，HP/ATK 666，存在 150 秒，带禁疗)；
- 场上有召唤协力球：先数后吞（官方 ginovi 同法：MultiballNumberVariable → RemoveMultiball），
  每吞 1 个：自身直接攻击伤害 +100%（最多 +500%）、攻击力 +60%（最多 +300%）、全队回复 5% 生命（最多 30%）；
  能力5 技能强化：再加自身技能槽 3%/个（最多 15%）。
队长技 L0：暗共鸣时每 30 连击召唤 1 个南瓜（场上最多 6 个，CT10 秒）= 队长 629。
"""
from __future__ import annotations

import copy

import hw_color
import hw_color
import hw_kitlib as K
import wf_seasonal7_common as C7
import wf_assets
import wf_midautumn_kitlib as KL
import wf_seasonal7_common as C

KEY = "momiya"
EL = 5  # 暗
PUMPKIN_ID = 1699851
PUMPKIN_CODE = "blade_witch_halloween_pumpkin"
PUMPKIN_SRC = "devil_princess_follower"
NAME_SKILL = "猎魔人，出动！"
SKILL_DESC = ("挥舞魔剑斩击最近的敌人，对周围的敌人造成暗属性伤害／赋予队伍中角色及协力球「贯通」效果（持续15秒）\n"
              "【场上没有协力球时】召唤2个「魔物万圣南瓜」协力球（存在150秒，带有禁疗状态）\n"
              "【场上有协力球时】吞噬场上所有被召唤的协力球，每吞噬1个，自身直接攻击伤害+100%（最多+500%）、"
              "攻击力+60%（最多+300%），队伍全体回复最大生命值的5%（最多30%）")
# 官方 ginovi 吞球名单（全部召唤系协力球）+ 本角色南瓜
SUMMON_IDS = [1110021, 1110022, 1110061, 1110062, 1110063, 1110064, 1110391, 1110392, 1110393, 1110394, 1110811,
              1110812, 1111351, 1111352, 1111471, 1111472, 1111711, 1111712, 1130011, 1399961, 1610391, 1610392,
              1610511, 1610512, 1610871, 1610872, 1611051, 1611291, 1611292, 1611771, 1611772, 1611891, 1611892,
              1611951, 1611952, 1699891, 1699892, 2510061, 2510062, 2510063, 2610011, 2610012, 2610651, 2610652,
              2630031, 2630032, 3510041, 3510042, PUMPKIN_ID]
PUMPKIN_RULES = [{"from": [215, 320], "to": 26, "sat": 1.9}, {"from": [330, 20], "to": 58}]
FRAMES = 900
BUFF = 1200
SUMMON_FX = "battle/effect/skill_unique/ruin_girl_campus_dark_call/ruin_girl_campus_dark_call"


def summon_cmd(n):
    eff = SUMMON_FX
    return K.C("CreateSummonsMultiball", n, PUMPKIN_ID, K.S(9000),
               ["E2", ["SpecifyEffectDirectly", f"{eff}_ready_generation"], ["SpecifyEffectDirectly", f"{eff}_ready_left"],
                ["SpecifyEffectDirectly", f"{eff}_ready_right"]],
               ["SpecifyEffectDirectly", f"{eff}_appear"], ["SpecifyEffectDirectly", f"{eff}_disappear"],
               0, False, "halloween_pumpkin_spawn", 74, 75,
               K.Blk(K.cond(75, ["ACHealRejection", K.S(9000)], cancel=False)), None)


def mul(v, var):
    return [{"min": v, "max": v, "mul": var}]


def skill_tree(base):
    t = copy.deepcopy(base)
    body = t[11][1]
    # 去掉母本的「赋予己方贯通」FindAll（换成含协力球的 33 版）
    body = [s for s in body if not (s[0] == "Command" and s[1][0] == "FindAllSubjects" and "ACPiercing" in repr(s))]
    assert len(body) == len(t[11][1]) - 1
    body.append(K.find_all(80, 33, K.cond(80, ["ACPiercing", K.S(FRAMES)])))
    devour = K.Blk(
        K.C("MultiballNumberVariable", 1, False, SUMMON_IDS, [], 1, 5.0),
        K.C("MultiballNumberVariable", 2, False, SUMMON_IDS, [], 1, 6.0),
        K.C("CreateCondition", -17, [["ACDirectDamage", K.S(BUFF), mul(1.0, 1), K.S(1)]], K.S(1),
            ["GenericConditionHitEffect"], True, False, "halloween_devour_direct", None, False, 3, K.S(1), False),
        K.C("CreateCondition", -17, [["ACAttackPoint", K.S(BUFF), mul(0.6, 1), K.S(1)]], K.S(1),
            ["GenericConditionHitEffect"], True, False, "halloween_devour_attack", None, False, 3, K.S(1), False),
        K.find_all(81, 82, K.C("CreateRatioHeal", 81, 2, mul(0.05, 2), [1], K.S(0.5), ["GenericHealHitEffect"])),
        K.C("ConditionalsChangeSkillFlag", 1, K.Blk(K.C("AddSkillPoint", -17, mul(0.03, 1))), K.Blk()),
        K.C("RemoveMultiball", False, SUMMON_IDS),
    )
    body.append(K.C("ConditionalsMultiballNumber", SUMMON_IDS, [], 1, devour, K.Blk(summon_cmd(2))))
    t[11][1] = body
    return t


def combo_summon_tree():
    """队长：每 30 连击召唤 1 个南瓜（场上南瓜满 6 个则不召唤）。"""
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            K.Blk(K.C("ConditionalsMultiballNumber", [PUMPKIN_ID], [], 6, K.Blk(), K.Blk(summon_cmd(1))))]


def pumpkin_assets(ctx):
    import sys
    sys.path.insert(0, str(K.hw_env.MODTOOLS))
    import wf_nephtim_fever_ball_pixels as NB

    def loader(lg):
        return wf_assets.locate(K.hw_env.STORE, lg)[1].read_bytes()
    files = NB._actor(loader, PUMPKIN_SRC, PUMPKIN_CODE)
    tf = hw_color.transform(PUMPKIN_RULES)
    for (root, lg), raw in files.items():
        if lg.endswith("sprite_sheet.png"):
            raw = C.png_store_bytes(tf(C.png_open(raw)))
        ctx.write_asset(root, lg, raw, owner="kit")
    # multiball 表：donor 南瓜同形的官方暗属性召唤球行
    mb = ctx.live_flat("master/battle/multiball/multiball.orderedmap")["1699892"]
    r = C.csv_split(mb)[0]
    r[0], r[1], r[22] = f"{PUMPKIN_CODE}_1", PUMPKIN_CODE, "(None)"
    ctx.write_flat("master/battle/multiball/multiball.orderedmap", {str(PUMPKIN_ID): [r]})
    lv = C.csv_split(ctx.live_flat("master/battle/multiball/multiball_level.orderedmap")["1699892"])[0]
    lv[1], lv[4] = "666", "666"
    ctx.write_flat("master/battle/multiball/multiball_level.orderedmap", {str(PUMPKIN_ID): [lv]})
    return sorted(lg for _r, lg in files)


FX_TPL_RULES = [{"from": [90, 175], "to": 28}]


def build(ctx):
    spec = ctx.spec
    code, cid = spec.code, spec.cid
    CHG = f"change_skill_{code}"
    SUM = f"ability_skill_{code}_combo_summon"
    SUM_PATH = f"battle/action/skill/action/ability_skill/{SUM}${SUM}"
    assets = pumpkin_assets(ctx)
    fam = ctx.clone_effect_family("battle/effect/skill_unique/blade_witch", "fx", png_transform=hw_color.transform(FX_TPL_RULES))
    for lv in ("1", "2"):
        base = K.load_tree(ctx, f"battle/action/skill/action/rare5/{spec.template_code}${spec.template_code}_{lv}")
        K.write_dsl(ctx, f"battle/action/skill/action/rare5/{code}${code}_{lv}", C7.rewrite_effect_refs(skill_tree(base), fam, strict=True)[0], EL)
    K.write_dsl(ctx, SUM_PATH, combo_summon_tree(), EL)
    inner = ctx.pkg_nested(code)
    out = {}
    for lv, cells in inner.items():
        cells = list(cells)
        cells[0] = NAME_SKILL + ("＋" if lv == "2" else "")
        cells[1] = SKILL_DESC
        out[lv] = [cells]
    ctx.write_nested(KL.ACTION, code, out, replace_inner=True)
    K.sync_skill_text(ctx)

    leader = [
        ("30连击召唤南瓜", ("trig", {
            "instant_trigger.kind": 12, "instant_trigger.trigger_puller": 0,
            "instant_trigger.trigger_puller.character_groups": "",
            "instant_trigger.threshold.power1": "3000000", "instant_trigger.threshold.first_max": "3000000",
            "instant_trigger.trigger_limit": "(None)", "instant_trigger.cooltime": 600,
            "instant_content.string_id": SUM, "instant_content.action_path": SUM_PATH,
            "pre": ("res", EL)}), "169988#5"),
        ("暗共鸣攻击", K.static(32, "party", 200, group=EL, pre=("res", EL))),
        ("协力球攻击", K.static(32, "multiball", 200, group="(None)", pre=("res", EL)), "311002#2"),
        ("暗共鸣直击", K.static(33, "party", 200, group=EL, pre=("res", EL))),
    ]
    lrows, lev = K.build_leader(ctx, leader)
    ctx.write_flat(KL.LEADER, {str(cid): lrows})

    plan = {
        1: ("true", [("开局技能槽", K.static(211, "self", 50), "1510334#0")]),
        2: ("true", [
            ("贯通攻击", K.during(30, 0, "party", 100, group=EL)),
            ("贯通协力球攻击", K.during(30, 0, "multiball", 100, group="")),
        ]),
        3: ("false", [
            ("每球充能", K.during(208, 3, "party", 5, threshold=1, limit=5, group=EL)),
            ("每球攻击", K.during(208, 0, "party", 20, threshold=1, limit=5, group=EL)),
        ]),
        4: ("true", [("有球贯通延长", K.static(190, "party", 100, group=EL, pre=("none",)), "1610046#0"),
                     ("有球直击3段", K.during(5, 46, "party", 25, threshold=1, group=EL))]),
        # 直击段数（取最大值类）不能和累积型触发同键（C2308，真机 10-16 实证）→ 挪到槽 4，用持续「有协力球」

        5: ("true", [("技能强化", ("static", {"instant_content.string_id": CHG, "pre": ("none",)}), "1411113#0")]),
        6: ("true", [("直击独立乘区", K.static(693, "party", 15, group=EL, pre=("res", EL)))]),
    }
    arows, aev = K.build_abilities(ctx, plan)
    ctx.write_flat(KL.ABILITY, arows)

    MAIN = " <icon id='main'>  "
    cas = {
        CHG: "强化『猎魔人，出动！』的协力球吞噬效果",
        SUM: "召唤1个「魔物万圣南瓜」协力球",
        f"desc_override_{code}": "\n".join([
            "暗属性共鸣时：每达成30连击，召唤1个「魔物万圣南瓜」协力球（场上最多6个，冷却时间10秒）",
            "暗属性共鸣时：暗属性角色及协力球攻击力＋200%、暗属性角色直接攻击伤害＋200%",
        ]),
        f"desc_override_{code}_1": "战斗开始时，自身技能槽＋50%",
        f"desc_override_{code}_2": "自身处于「贯通」状态时，暗属性角色及协力球攻击力＋100%",
        f"desc_override_{code}_3": "\n".join(MAIN + x for x in (
            "场上每有1个协力球，暗属性角色技能槽充能速度＋5%（最多＋25%）、攻击力＋20%（最多＋100%）",
            "场上每有1个协力球，暗属性角色攻击力＋20%（最多＋100%）")),
        f"desc_override_{code}_4": "暗属性角色「贯通」效果时间＋100%",
        f"desc_override_{code}_5": "强化『猎魔人，出动！』的协力球吞噬效果",
        f"desc_override_{code}_6": "暗属性共鸣时：暗属性角色直接攻击伤害额外乘区＋15%",
    }
    for k, v in cas.items():
        for line in v.split("\n"):
            KL.check_panel(line.replace(MAIN, ""), skill_flag=(k in (CHG, f"desc_override_{code}_5")), label=k)
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas.items()})
    ctx.report({"character": KEY, "leader": [e["describe"] for e in lev],
                "abilities": [f"{e['key']}:{e['describe']}" for e in aev], "cas": cas, "assets": assets})
    return {"leader": [e["describe"] for e in lev], "abilities": [f"{e['key']} {e['describe']}" for e in aev]}
