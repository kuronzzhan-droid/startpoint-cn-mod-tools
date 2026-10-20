# -*- coding: utf-8 -*-
"""瑞西塔尔「奇怪的杰克南瓜灯」149985 lich_halloween：风·技伤通用麻痹辅助。

技能「不死的南瓜派对！」：骨架取官方 psychic_tomboygirl（全场逐敌束缚+麻痹+伤害），束缚线特效克隆换色成南瓜藤绿；
去掉火抗降低；麻痹 8 秒；追加全屏判定区破坏所有弱点（官方 keylock_girl 同形）；队伍攻击力+100%（能力6 技能强化=+200%）；
棺柩计数 -8（母本 lich 原样）。
"""
from __future__ import annotations

import copy

import hw_color
import hw_kitlib as K
import wf_midautumn_kitlib as KL
import wf_seasonal7_common as C

KEY = "recital"
EL = 3  # 风
NAME_SKILL = "不死的南瓜派对！"
SKILL_DESC = ("在全场刮起死亡之风，以长着南瓜头的不死藤蔓束缚所有敌人，对其造成风属性伤害并破坏所有弱点＋赋予麻痹效果（持续8秒）／"
              "赋予参战者全员「攻击力上升」效果（攻击力+100%，持续20秒）／减少参战者全员的棺柩计数")
DONOR_PROG = "battle/action/skill/action/rare4/psychic_tomboygirl$psychic_tomboygirl_{lv}"
FX_SRC = "battle/effect/skill_unique/psychic_tomboygirl_hw22"   # 官方万圣版束缚线(南瓜脸)
# 粉红束缚线 → 南瓜藤绿；红芯 → 南瓜橙（明度不动）
FX_RULES = [{"from": [280, 350], "to": 104, "sat": 0.95},
            {"from": [350, 25], "to": 28}]
PARALYSIS = 480
ATK_FRAMES = 1200


def skill_tree(base, family):
    t = K.walk(copy.deepcopy(base), lambda n: None)
    t = C.replace_strings(t, {"skill_unique/psychic_tomboygirl/psychic_tomboygirl_":
                              "skill_unique/psychic_tomboygirl_hw22/psychic_tomboygirl_hw22_"})
    t, _info = C.rewrite_effect_refs(t, family, strict=True)
    def fix(node):
        if node and node[0] == "ACParalysis":
            node[1] = K.S(PARALYSIS)
        return None
    K.walk(t, fix)
    # 删掉火抗降低：只删那一条 CreateCondition，不能按 repr 删整句——
    # 逐敌 FindAllSubjects 里同时装着麻痹/伤害，按 repr 过滤会把整段攻击一起删掉（1.4.221 实发事故）
    def drop_tol(node):
        if node and node[0] == "Block" and isinstance(node[1], list):
            node[1] = [s for s in node[1] if not (isinstance(s, list) and s and s[0] == "Command"
                                                  and s[1][0] == "CreateCondition"
                                                  and "ACToleranceOfElement" in repr(s[1][2]))]
        return None
    K.walk(t, drop_tol)
    assert "ACToleranceOfElement" not in repr(t)
    body = t[11][1]   # drop_tol 会换掉 Block 的列表，必须在它之后取
    # 全屏破坏弱点（不造伤，官方 keylock_girl 同形：p6=true）
    body.append(K.C("CreateHitArea", "*", -1, ["AB"], 0, 0, 0, True, False,
                    ["Rectangle", K.S(1500), K.S(2000)], ["Center"], ["Center"], ["Single"],
                    ["SpecifyHitAreaLifetimeDirectly", 30], ["CalculatedUsingMaxNumOfHits", 1], ["None"],
                    False, True, ["None"], 70, K.Blk(), 71, 72, K.Blk(), 0, 0, ["None"]))

    def atk(v):
        return K.cond(60, ["ACAttackPoint", K.S(ATK_FRAMES), K.S(v), K.S(1)])
    body.append(K.find_all(60, 33, K.C("ConditionalsChangeSkillFlag", 1, K.Blk(atk(2.0)), K.Blk(atk(1.0)))))
    body.append(K.find_all(61, 65, K.C("DecreaseCoffinCount", 61, 8, ["Generic"])))
    assert t[11][1] is body
    rt = repr(t)
    for need in ("CreateNormalAttack", "ACParalysis", "ACAttackPoint", "DecreaseCoffinCount"):
        assert need in rt, f"技能树缺 {need}"
    return t


def build(ctx):
    spec = ctx.spec
    code, cid = spec.code, spec.cid
    CHG = f"change_skill_{code}"
    family = ctx.clone_effect_family(FX_SRC, "vine", png_transform=hw_color.transform(FX_RULES))
    for lv in ("1", "2"):
        prog = f"battle/action/skill/action/rare5/{code}${code}_{lv}"
        K.write_dsl(ctx, prog, skill_tree(K.load_tree(ctx, DONOR_PROG.format(lv=lv)), family), EL)
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

    leader = [
        ("风共鸣攻击", K.static(32, "party", 100, group=EL, pre=("res", EL))),
        ("风共鸣技伤", K.static(34, "party", 80, group=EL, pre=("res", EL))),
        ("棺柩计数", ("static", {}), "341003#1"),
    ]
    lrows, lev = K.build_leader(ctx, leader)
    ctx.write_flat(KL.LEADER, {str(cid): lrows})

    plan = {
        1: ("true", [("风共鸣充能", K.static(35, "party", 10, group=EL, pre=("res", EL)))]),
        2: ("true", [
            ("风施技攻击", K.trig(23, 32, "party", 50, puller="party_one", puller_group=EL, limit=3, ct=600, group=EL)),
            ("风施技连击", K.trig(23, 226, "self", 0, puller="party_one", puller_group=EL, ct=600,
                                 raw="1000000"), "2310044#0"),
        ]),
        3: ("false", [("每个强化效果", K.during(37, 421, "party", 1, threshold=1, limit=10, group=EL))]),
        4: ("true", [
            ("麻痹特攻", K.static(118, "party", 5, group=EL)),
            ("气绝特攻", K.static(53, "party", 5, group=EL)),
        ]),
        5: ("true", [("施技技伤", K.trig(23, 34, "party", 50, limit=3, group=EL))]),
        6: ("true", [("技能强化", ("static", {"instant_content.string_id": CHG, "pre": ("none",)}), "1411113#0")]),
    }
    arows, aev = K.build_abilities(ctx, plan)
    ctx.write_flat(KL.ABILITY, arows)

    MAIN = " <icon id='main'>  "
    cas = {
        CHG: "强化『不死的南瓜派对！』的「攻击力上升」效果",
        f"desc_override_{code}": "\n".join([
            "风属性共鸣时：风属性角色攻击力＋100%、技能伤害＋80%",
            "参战者全员的棺柩计数减少",
        ]),
        f"desc_override_{code}_1": "风属性共鸣时：风属性角色技能槽充能速度＋10%",
        f"desc_override_{code}_2": "风属性角色发动技能时，风属性角色攻击力＋50%（最多＋150%）、连击数＋10（冷却时间10秒）",
        f"desc_override_{code}_3": MAIN + "自身每拥有1个强化效果，风属性角色对敌人的伤害额外乘区＋1%（最多＋10%）",
        f"desc_override_{code}_4": "风属性角色对处于「麻痹」或「气绝」状态的敌人伤害＋5%",
        f"desc_override_{code}_5": "自身发动技能时，风属性角色技能伤害＋50%（最多＋150%）",
        f"desc_override_{code}_6": "强化『不死的南瓜派对！』的「攻击力上升」效果",
    }
    for k, v in cas.items():
        for line in v.split("\n"):
            KL.check_panel(line.replace(MAIN, ""), skill_flag=(k in (CHG, f"desc_override_{code}_6")), label=k)
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas.items()})
    ctx.report({"character": KEY, "leader": [e["describe"] for e in lev],
                "abilities": [f"{e['key']}:{e['describe']}" for e in aev], "cas": cas,
                "fx": family.get("dst_dir")})
    return {"leader": [e["describe"] for e in lev], "abilities": [f"{e['key']} {e['describe']}" for e in aev],
            "fx": family.get("copied_bases")}
