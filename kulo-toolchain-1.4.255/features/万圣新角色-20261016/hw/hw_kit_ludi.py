# -*- coding: utf-8 -*-
"""露迪「万圣第一的公主殿下」139985 lady_android_halloween：雷·Fever 外 DB 辅助 / Fever 内副 C。

技能「公主大人驾到！」两形态（ConditionalsFeverMode）：
- Fever 外：全屏判定区（破坏所有弱点）给全体敌人刻「万圣糖果标记」(固有 13998501，20 秒) + 迟缓(=Frozen，20 秒)
  + 消除 2 个强化效果；Fever 槽 +200。
- Fever 内：对带标记的敌人逐个落雷造成大量雷属性伤害，处于迟缓的敌人追加一段；随后移除标记
  （能力6 技能强化：不移除，改为再叠 1 层，最多 3 层）。
特效：官方万圣版 sing_android_hw20（音符/糖果）+ fox_scientist_hw20（雷射/命中），换成橙紫色。
"""
from __future__ import annotations

import copy

import hw_color
import hw_kitlib as K
import wf_assets
import wf_midautumn_kitlib as KL

KEY = "ludi"
EL = 2  # 雷
CAND = 13998501
NAME_SKILL = "公主大人驾到！"
SKILL_DESC = ("【Fever外】向全场撒下万圣糖果，破坏所有敌人的弱点，赋予「万圣糖果标记」与迟缓效果（持续20秒）＋消除2个强化效果／Fever槽增加\n"
              "【Fever中】对带有「万圣糖果标记」的敌人造成大量雷属性伤害，对处于迟缓状态的敌人追加伤害，随后移除「万圣糖果标记」")
FX_SING = "battle/effect/skill_unique/sing_android_hw20"
FX_FOX = "battle/effect/skill_unique/fox_scientist_hw20"
# 保亮度：橙→万圣橙不动；紫/蓝→深紫；黄绿雷→金黄
FX_RULES = [{"from": [40, 160], "to": 48}, {"from": [180, 260], "to": 275}]
UNIQUE_ICON = "battle/common/unique_condition/unique_halloween_candy"


def skill_tree(lv: str, sing, fox):
    sp = sing["dst_dir"]
    fp = fox["dst_dir"]
    mult = K.S(16, 20) if lv == "2" else K.S(14, 16)
    extra = K.S(6, 8) if lv == "2" else K.S(5, 6)

    def show(name, path, subj, life, pos=("AB",), scale=None, front="ForesideOfCharacter"):
        return K.C("ShowEffect", name, ["SpecifyEffectDirectly", path], subj, [front],
                   ["SpecifyEffectLifetimeDirectly", life], list(pos), 0, 0, 0, True, False,
                   ["Some", K.S(scale)] if scale else ["None"])

    mark = K.cond(2, ["ACUnique", CAND, K.S(1)])
    frozen = K.cond(2, ["ACFrozen", K.S(1200), True])
    normal = K.Blk(
        K.C("CreateHitArea", "*", -1, ["AB"], 0, 0, 0, True, False,
            ["Rectangle", K.S(1500), K.S(2000)], ["Center"], ["Center"], ["Single"],
            ["SpecifyHitAreaLifetimeDirectly", 30], ["CalculatedUsingMaxNumOfHits", 1], ["None"],
            False, True, ["None"], 0, K.Blk(), 1, 2,
            K.Blk(mark, frozen,
                  K.C("DeleteCondition", 2, ["DCAll", 2], 2, 0, "", ["Default"]),
                  show("ヒット演出", f"{fp}/fox_scientist_hw20_hit", 2, 40)),
            0, 0, ["None"]),
        K.C("AddFeverPoint", K.S(200)),
    )
    hit = K.C("CreateHitArea", "*", 10, ["AB"], 0, 0, 0, True, True, ["Circle", K.S(10)], ["Center"], ["Center"],
              ["Single"], ["SpecifyHitAreaLifetimeDirectly", 2], ["CalculatedUsingMaxNumOfHits", 1],
              ["Some", K.S(1)], True, False, ["None"], 11, K.Blk(), 12, 13,
              K.Blk(K.C("CreateNormalAttack", 13, 255, [], [], 80, mult, K.S(0), False, False, False, False, False,
                        K.S(10), K.S(10), ["Coarse"], True),
                    K.C("ConditionalsConditionExist", 13, ["DCFrozen"],
                        K.Blk(K.C("CreateNormalAttack", 13, 255, [], [], 40, extra, K.S(0), False, False, False,
                                  False, False, K.S(5), K.S(5), ["Coarse"], True)),
                        K.Blk()),
                    K.C("ShakeCamera", 2)),
              0, 0, ["None"])
    fever = K.Blk(K.find_all(
        10, 49,
        K.C("ConditionalsConditionExist", 10, ["DCUnique", CAND],
            K.Blk(show("落雷", f"{fp}/fox_scientist_hw20_laser", 10, 50, scale=0.8),
                  show("ヒット演出", f"{fp}/fox_scientist_hw20_hit", 10, 40),
                  K.wait(20, hit),
                  K.wait(24, K.C("ConditionalsChangeSkillFlag", 1,
                                  K.Blk(K.cond(10, ["ACUnique", CAND, K.S(1)])),
                                  K.Blk(K.C("DeleteCondition", 10, ["DCUnique", CAND], 1, 0, "", ["Default"]))))),
            K.Blk())))
    body = [
        K.C("StopBall", -18, 30, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0),
        show("全体演出", f"{sp}/sing_android_hw20", -1, 60, front="SuperForesideOfCharacter"),
        show("自身演出", f"{sp}/sing_android_hw20_player_back", -17, 60, front="BacksideOfCharacter"),
        K.C("ConditionalsFeverMode", fever, normal),
    ]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, K.Blk(*body)]


def build(ctx):
    spec = ctx.spec
    code, cid = spec.code, spec.cid
    CHG = f"change_skill_{code}"
    tf = hw_color.transform(FX_RULES)
    sing = ctx.clone_effect_family(FX_SING, "concert", png_transform=tf)
    fox = ctx.clone_effect_family(FX_FOX, "candy_bolt", png_transform=tf)
    for lv in ("1", "2"):
        K.write_dsl(ctx, f"battle/action/skill/action/rare5/{code}${code}_{lv}", skill_tree(lv, sing, fox), EL)
    inner = ctx.pkg_nested(code)
    out = {}
    for lv, cells in inner.items():
        cells = list(cells)
        cells[0] = NAME_SKILL + ("＋" if lv == "2" else "")
        cells[1] = SKILL_DESC
        cells[2] = "dynamic/skill/atk_all"
        out[lv] = [cells]
    ctx.write_nested(KL.ACTION, code, out, replace_inner=True)
    K.sync_skill_text(ctx)

    # 固有状态「万圣糖果标记」（敌方，20 秒，最多 3 层）+ 图标
    donor = K.KL.donor_row(ctx, KL.UNIQUE, "1699901", source="live")
    urow = list(donor)
    urow[0], urow[1], urow[2], urow[3], urow[4] = "unique_halloween_candy", "万圣糖果标记", UNIQUE_ICON, "1200", "3"
    ctx.write_flat(KL.UNIQUE, {str(CAND): [urow]})
    icon = (K.hw_env.OUT / "art" / "icons" / "unique_halloween_candy.png").read_bytes()
    ctx.write_asset("common", UNIQUE_ICON + ".png", wf_assets.png_encode(icon), owner="kit")

    leader = [
        ("雷共鸣攻击", K.static(32, "party", 100, group=EL, pre=("res", EL))),
        ("雷共鸣技伤", K.static(34, "party", 100, group=EL, pre=("res", EL))),
        ("Fever充能", K.during(4, 3, "party", 30, group=EL, pre=("res", EL))),
    ]
    lrows, lev = K.build_leader(ctx, leader)
    ctx.write_flat(KL.LEADER, {str(cid): lrows})

    plan = {
        1: ("true", [("雷施技技伤", K.trig(23, 34, "party", 50, puller="party_one", puller_group=EL, limit=6,
                                          group=EL, pre=("res", EL)))]),
        2: ("true", [
            ("Fever攻击", K.trig(8, 32, "party", 100, limit=3, group=EL)),
            ("Fever技伤", K.trig(8, 34, "party", 25, limit=4, group=EL)),
        ]),
        3: ("false", [
            ("Fever外回Fever", K.trig(23, 724, "self", 5, pre=("kind", 186)), "1299991#2"),
            ("Fever内充能", K.trig(23, 211, "self", 50, pre=("kind", 12)), "2310021#0"),
            ("糖果独立乘区", K.static(721, "party", 5, group=EL, unique=CAND, pre=("none",)), "1699995#0"),
        ]),
        4: ("false", [("减益特攻", K.static(96, "party", 10, group=EL))]),
        5: ("true", [("雷施技自攻", K.trig(23, 32, "self", 20, puller="party_one", puller_group=EL, limit=5,
                                          pre=("res", EL)))]),
        6: ("false", [
            ("技能强化", ("static", {"instant_content.string_id": CHG, "pre": ("none",)}), "1411113#0"),
            ("糖果层数", K.during(171, 421, "party", 5, threshold=1, limit=3, unique=CAND, group=EL)),
        ]),
    }
    arows, aev = K.build_abilities(ctx, plan)
    ctx.write_flat(KL.ABILITY, arows)

    MAIN = " <icon id='main'>  "
    cas = {
        CHG: "强化『公主大人驾到！』的「万圣糖果标记」效果",
        f"desc_override_{code}": "\n".join([
            "雷属性共鸣时：雷属性角色攻击力＋100%、技能伤害＋100%",
            "雷属性共鸣时：Fever中，雷属性角色技能槽充能速度＋30%",
        ]),
        f"desc_override_{code}_1": "雷属性共鸣时：雷属性角色每次发动技能时，雷属性角色技能伤害＋50%（最多＋300%）",
        f"desc_override_{code}_2": "每次发动Fever时，雷属性角色攻击力＋100%（最多＋300%）、技能伤害＋25%（最多＋100%）",
        f"desc_override_{code}_3": "\n".join(MAIN + x for x in (
            "Fever外自身发动技能时，Fever槽＋5%",
            "Fever中自身发动技能时，自身技能槽＋50%",
            "雷属性角色对带有「万圣糖果标记」的敌人技能伤害额外乘区＋5%")),
        f"desc_override_{code}_4": MAIN + "雷属性角色对处于弱化状态的敌人伤害＋10%",
        f"desc_override_{code}_5": "雷属性共鸣时：雷属性角色每次发动技能时，自身攻击力＋20%（最多＋100%）",
        f"desc_override_{code}_6": "\n".join(MAIN + x for x in (
            "强化『公主大人驾到！』的「万圣糖果标记」效果",
            "敌人身上的「万圣糖果标记」每有1层，雷属性角色伤害额外乘区＋5%（最多＋15%）")),
    }
    for k, v in cas.items():
        for line in v.split("\n"):
            KL.check_panel(line.replace(MAIN, ""), skill_flag=(k == CHG), label=k)
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas.items()})
    ctx.report({"character": KEY, "leader": [e["describe"] for e in lev],
                "abilities": [f"{e['key']}:{e['describe']}" for e in aev], "cas": cas})
    return {"leader": [e["describe"] for e in lev], "abilities": [f"{e['key']} {e['describe']}" for e in aev],
            "fx": [sing["copied_bases"], fox["copied_bases"]]}
