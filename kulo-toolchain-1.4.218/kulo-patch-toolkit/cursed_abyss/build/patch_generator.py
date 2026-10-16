# -*- coding: utf-8 -*-
"""诅咒武器第四轮（2026-10-07 意见征集「时装后的数值建议改动」）：在旧仓生成器的副本上做定点改写。

源：D:/WF/out/kulo-patch-toolkit/oldrepo_modtools/wf_cursed_weapons.py（已验证其输出 == kulo 1.4.149 现状，
见 verify_baseline.py）。产物：同目录 wf_cursed_weapons_r4.py。每处替换都断言恰好命中一次。
"""
import os
from pathlib import Path

SRC = Path(r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools/wf_cursed_weapons.py")
DST = Path(__file__).resolve().parent / "wf_cursed_weapons_r4.py"

R: list[tuple[str, str]] = []


def rep(old: str, new: str) -> None:
    R.append((old, new))


# ---------------------------------------------------------------- 预算门禁：本轮作者待拍板的超额项单列，不阻断构建
rep('''def budget_problems(label: str, author: str, budget: dict[str, Any]) -> list[str]:
    blade_cap, mult_cap = budget_caps(author)''',
    '''#: 第四轮（1007）按提案改动后超出作者 0928 预算的武器：不阻断构建，在报告里列为「待作者拍板」。
ROUND4_OVER_BUDGET: dict[str, str] = {}


def budget_problems(label: str, author: str, budget: dict[str, Any]) -> list[str]:
    blade_cap, mult_cap = budget_caps(author)
    if label[:2] in ROUND4_OVER_BUDGET:
        ROUND4_OVER_BUDGET[label[:2]] = (f"刃 {budget['blades']:g}% / 乘区 {budget['multipliers']:g}%"
                                         f"（上限 {blade_cap}/{mult_cap}）")
        return [f"{label}: 数值预算 {u}" for u in budget["unbounded"]]''')

# ---------------------------------------------------------------- 预算：档位标记（开局按强化等级叠层）互斥的行在 120 级不生效
rep('''    elements = sorted({p["element"] for _w, p in rows if p["element"]}) or [None]''',
    '''    initial_stacks: dict[str, int] = {}
    for _where, p in rows:
        if p["mode"] == "0" and p["kind"] == "461" and p["trig"] == IT_INITIAL:
            initial_stacks[p["uid"]] = initial_stacks.get(p["uid"], 0) + 1

    def tier_excluded(p: dict[str, Any]) -> bool:
        """前置 199「层数 ≤ N」而该固有开局已被叠到 >N 层且从不被消耗 ⇒ 120 级恒不成立（第四轮档位行）。"""
        return any(pre["kind"] == PRE_UNIQUE_LE and pre["uid"] not in consumed
                   and initial_stacks.get(pre["uid"], 0) > int(_number(pre["threshold"]) or 0) // 100000
                   for pre in p["pres"])

    elements = sorted({p["element"] for _w, p in rows if p["element"]}) or [None]''')
rep('''            if any(pre["kind"] == PRE_UNIQUE_LE and pre["threshold"] == "0" and always_held(pre["uid"], element)
                   for pre in p["pres"]):
                continue''',
    '''            if any(pre["kind"] == PRE_UNIQUE_LE and pre["threshold"] == "0" and always_held(pre["uid"], element)
                   for pre in p["pres"]) or tier_excluded(p):
                continue''')

# ---------------------------------------------------------------- 01 饕餮餐刀（面包刀）：强化 1 级即满值 → 按强化阶段 1/70/99/120 分四档
rep('''    program = dsl_program("gluttony_devour")
    # 计数在移除之前取（V = min(存活数, 9)）；带 mul 的 CreateCondition 必须带非空键串（gid 合并不看 mul）
    w.dsl[program] = dsl_root(
        C("ConditionalsMultiballNumber", ids, [], 1, B(
            C("MultiballNumberVariable", 1, False, ids, [], 1, 9),
            C("RemoveMultiball", False, ids),
            give(-17, [["ACAttackPoint", P(1800), [{"min": 1.0, "max": 1.0, "mul": 1}], P(1)]], "cursed_gluttony_atk"),
        ), B()))
    w.cas["cursed_gluttony_devour"] = "吞噬场上所有被召唤的协力球，每吞噬1个，自身攻击力提升100%（30秒，最多9个）"
    w.ea = [
        Eff("0", invoke("cursed_gluttony_devour", program), trig=trig(IT_SKILL, trigger_puller=P_SELF),
            **CURSE, note="【诅咒】发动技能时吞噬己方全部召唤协力球，每个 +100% 攻击力（最多 9 个，30 秒）"),
    ]''',
    '''    # 第四轮（1007）修强化曲线：原单行 629 强化 1 级就是 +100%/个。DSL 数值不随等级插值，改为四档 DSL：
    # 强化 Lv1/70/99/120 每个协力球 +25/50/75/100%。档位由固有「饕餮之胃」层数区分（Lv70/99/120 各在开局 +1 层，
    # 叠层上限 3 >1 才按层读），四行互斥：≤0 层 / =1 / =2 / ≥3，任何时刻只跑一棵（计数→移除→赋予，同键覆盖）。
    u_tier = w.uid(1)
    w.uniques[u_tier] = unique_row(f"cursed_gluttony_{u_tier}", "饕餮之胃", ICON_STACK, "99999999", "3", bad=False)
    cast = trig(IT_SKILL, trigger_puller=P_SELF)
    tiers = ((0, 0.25, "gluttony_devour", dict(learn=1, maxlvl=120)),
             (1, 0.5, "gluttony_devour_70", dict(learn=70, maxlvl=70)),
             (2, 0.75, "gluttony_devour_99", dict(learn=99, maxlvl=99)),
             (3, 1.0, "gluttony_devour_120", dict(learn=120, maxlvl=120)))
    w.ea = []
    for stacks, per_ball, name, lv in tiers:
        program = dsl_program(name)
        # 计数在移除之前取（V = min(存活数, 9)）；带 mul 的 CreateCondition 必须带非空键串（gid 合并不看 mul）
        w.dsl[program] = dsl_root(
            C("ConditionalsMultiballNumber", ids, [], 1, B(
                C("MultiballNumberVariable", 1, False, ids, [], 1, 9),
                C("RemoveMultiball", False, ids),
                give(-17, [["ACAttackPoint", P(1800), [{"min": per_ball, "max": per_ball, "mul": 1}], P(1)]],
                     "cursed_gluttony_atk"),
            ), B()))
        pct_ = int(per_ball * 100)
        w.cas[f"cursed_{name}"] = f"吞噬场上所有被召唤的协力球，每吞噬1个，自身攻击力提升{pct_}%（30秒，最多9个）"
        if stacks == 0:
            pre = ((PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": "0", "unique_condition_id": u_tier}),)
        elif stacks == 3:
            pre = ((PRE_UNIQUE_GE, {"trigger_puller": P_SELF, "threshold": times(3), "unique_condition_id": u_tier}),)
        else:
            pre = ((PRE_UNIQUE_GE, {"trigger_puller": P_SELF, "threshold": times(stacks), "unique_condition_id": u_tier}),
                   (PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": times(stacks), "unique_condition_id": u_tier}))
        w.ea.append(Eff("0", invoke(f"cursed_{name}", program), trig=cast, pre=pre, **lv,
                        note=f"【诅咒】发动技能时吞噬己方全部召唤协力球，每个 +{pct_}% 攻击力（最多 9 个，30 秒；"
                             f"强化 Lv{lv['learn']} 档）"))
        if stacks:
            w.ea.append(Eff("0", unique(u_tier), **lv, note=f"强化 Lv{lv['learn']}：开局「饕餮之胃」+1 层（档位标记）"))''')
rep('''    w.deviations.append("评分审查 0928（作者「按表改」）：吞噬加成持续 15 → 30 秒（盖满一轮约 30 秒的技能回转），"
                        "每球 +100%、上限 9 不动；同一键串后到的整条覆盖，不叠加")
    return w''',
    '''    w.deviations.append("评分审查 0928（作者「按表改」）：吞噬加成持续 15 → 30 秒（盖满一轮约 30 秒的技能回转），"
                        "每球 +100%、上限 9 不动；同一键串后到的整条覆盖，不叠加")
    w.deviations.append("第四轮 1007 修强化曲线（原强化 1 级即满值）：DSL 数值不能随等级插值，按强化突破节点分四档——"
                        "Lv1–69 每球 +25%、Lv70–98 +50%、Lv99–119 +75%、Lv120 +100%；吞噬（诅咒本体）强化 1 级起全额")
    return w''')

# ---------------------------------------------------------------- 03 咸鱼王冠：轻改——诅咒减半、翻身期间技能伤害 800→1000（刃上限）
rep('''        *growth_pair("2", T_SELF, 800, 100, mode="1", trig_=flipped, pre=(wind,)),
        Eff("0", stat("35", T_SELF, -50), pre=(wind,), **CURSE,
            note="【诅咒】风属性共鸣时：自身技能充能速度 -50%"),''',
    '''        *growth_pair("2", T_SELF, 1000, 100, mode="1", trig_=flipped, pre=(wind,)),
        Eff("0", stat("35", T_SELF, -25), pre=(wind,), **CURSE,
            note="【诅咒】风属性共鸣时：自身技能充能速度 -25%"),''')

# ---------------------------------------------------------------- 07 氪金的力量：三项 +200% → +350%
rep('''            *growth_pair("32", T_PARTY, 200, 150, pre=gate),
            *growth_pair("34", T_PARTY, 200, 150, pre=gate),
            *growth_pair("388", T_PARTY, 200, 150, pre=gate),''',
    '''            *growth_pair("32", T_PARTY, 333, 150, pre=gate),
            *growth_pair("34", T_PARTY, 333, 150, pre=gate),
            *growth_pair("388", T_PARTY, 333, 150, pre=gate),''')

# ---------------------------------------------------------------- 10 赌注已下：强化 1 级即满值 → 增益分四档；开局赌注改成长
rep('''    w.dsl[full] = dsl_root(roulette(
        (3, [party(0, give(0, [ac("ACFlying", buff)]), give(0, [ac("ACSwift", buff)]),
                   give(0, [ac("ACDirectDamage", buff, P(5.0), P(1))]))]),
        (3, [party(0, give(0, [ac("ACPiercing", buff)]), give(0, [ac("ACSpeedup", buff, P(0.3), P(1))]),
                   give(0, [ac("ACPowerFlipDamage", buff, P(5.0), P(1))])),
             give(-17, [["ACUnique", int(u_echo), P(1)]], "cursed_dice_echo", cancelable=False)]),
        (3, [party(0, C("AddSkillPoint", 0, P(1.0)), give(0, [ac("ACSkillDamage", buff, P(5.0), P(1))]),
                   give(0, [ac("ACSkillGaugeCharging", buff, P(0.2), P(1))]))]),''',
    '''    def full_roll(scale: float) -> list:
        return dsl_root(roulette(
        (3, [party(0, give(0, [ac("ACFlying", buff)]), give(0, [ac("ACSwift", buff)]),
                   give(0, [ac("ACDirectDamage", buff, P(5.0 * scale), P(1))]))]),
        (3, [party(0, give(0, [ac("ACPiercing", buff)]), give(0, [ac("ACSpeedup", buff, P(0.3), P(1))]),
                   give(0, [ac("ACPowerFlipDamage", buff, P(5.0 * scale), P(1))])),
             give(-17, [["ACUnique", int(u_echo), P(1)]], "cursed_dice_echo", cancelable=False)]),
        (3, [party(0, C("AddSkillPoint", 0, P(1.0 * scale)), give(0, [ac("ACSkillDamage", buff, P(5.0 * scale), P(1))]),
                   give(0, [ac("ACSkillGaugeCharging", buff, P(round(0.2 * scale, 3)), P(1))]))]),''')
rep('''        (1, [party(0, C("SubtractSkillPoint", 0, P(0.8))),
             give(-17, [["ACUnique", int(u_bust), P(1)]], "cursed_dice_bust", cancelable=False)]),
    ))
    w.cas["cursed_fate_roll"] = ("转动老虎机：直击（浮游、迅捷、直接攻击伤害+500%）／强化弹射（贯通、加速、强化弹射伤害+500%、"
                                 "「复读弹射」）／技能（技能槽+100%、技能伤害+500%、充能速度+20%）三种增益（各1/4，20秒），"
                                 "或对应诅咒（各1/12）：随机两名主位麻痹且弹球不受控制5秒、全队减速10秒／连击上限1且增益无效10秒／"
                                 "全队技能槽-80%且「血本无归」10秒")''',
    '''        (1, [party(0, C("SubtractSkillPoint", 0, P(0.8))),
             give(-17, [["ACUnique", int(u_bust), P(1)]], "cursed_dice_bust", cancelable=False)]),
    ))
    # 第四轮（1007）修强化曲线：增益三支按强化突破节点分四档（Lv1/70/99/120 = 25/50/75/100%），诅咒三支各档全额。
    # 档位由固有「赌徒筹码」层数区分（Lv70/99/120 各在开局 +1 层，上限 3），四行互斥，每 25 秒只转一台。
    u_tier = w.uid(5)
    w.uniques[u_tier] = unique_row(f"cursed_dice_{u_tier}", "赌徒筹码", ICON_STACK, "99999999", "3", bad=False)
    roll_tiers = ((0, 0.25, "fate_roll", dict(learn=1, maxlvl=120)), (1, 0.5, "fate_roll_70", dict(learn=70, maxlvl=70)),
                  (2, 0.75, "fate_roll_99", dict(learn=99, maxlvl=99)), (3, 1.0, "fate_roll_120", dict(learn=120, maxlvl=120)))
    for _stacks, scale, name, _lv in roll_tiers:
        w.dsl[dsl_program(name)] = full_roll(scale)
        dmg, gauge, charge = int(500 * scale), int(100 * scale), round(20 * scale, 1)
        w.cas[f"cursed_{name}"] = (f"转动老虎机：直击（浮游、迅捷、直接攻击伤害+{dmg}%）／强化弹射（贯通、加速、强化弹射伤害+{dmg}%、"
                                   f"「复读弹射」）／技能（技能槽+{gauge}%、技能伤害+{dmg}%、充能速度+{charge:g}%）三种增益（各1/4，20秒），"
                                   "或对应诅咒（各1/12）：随机两名主位麻痹且弹球不受控制5秒、全队减速10秒／连击上限1且增益无效10秒／"
                                   "全队技能槽-80%且「血本无归」10秒")''')
rep('''    w.ea = [
        Eff("0", unique(u_mark), **CURSE, note="「赌局」：本体的温和转轮换成完整老虎机"),
        Eff("0", unique(u_open), **CURSE, note="开局获得「开局赌注」15 秒"),
        Eff("1", during("421", T_PARTY, 2), trig=opening, even_if_dead=True, **CURSE,
            note="「开局赌注」期间全队伤害独立乘区 +2%"),
        Eff("1", during("0", T_PARTY, 20), trig=opening, even_if_dead=True, **CURSE,
            note="「开局赌注」期间全队攻击力 +20%"),
        Eff("0", invoke("cursed_fate_roll", full), trig=every25, **CURSE,
            note="【诅咒】每 25 秒转一次：三种增益（各 1/4，20 秒）或三种诅咒（各 1/12，10 秒；"
                 "直击诅咒的麻痹与弹球不受控制 5 秒；诅咒强制付与、不可驱散）"),''',
    '''    def tier_pre(stacks: int) -> tuple:
        if stacks == 0:
            return ((PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": "0", "unique_condition_id": u_tier}),)
        if stacks == 3:
            return ((PRE_UNIQUE_GE, {"trigger_puller": P_SELF, "threshold": times(3), "unique_condition_id": u_tier}),)
        return ((PRE_UNIQUE_GE, {"trigger_puller": P_SELF, "threshold": times(stacks), "unique_condition_id": u_tier}),
                (PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": times(stacks), "unique_condition_id": u_tier}))

    GROW = dict(learn=1, maxlvl=120)
    w.ea = [
        Eff("0", unique(u_mark), **CURSE, note="「赌局」：本体的温和转轮换成完整老虎机"),
        Eff("0", unique(u_open), **CURSE, note="开局获得「开局赌注」15 秒"),
        Eff("1", during("421", T_PARTY, 0.5, 2), trig=opening, even_if_dead=True, **GROW,
            note="「开局赌注」期间全队伤害独立乘区 +0.5%→2%（随强化成长）"),
        Eff("1", during("0", T_PARTY, 5, 20), trig=opening, even_if_dead=True, **GROW,
            note="「开局赌注」期间全队攻击力 +5%→20%（随强化成长）"),
    ]
    for stacks, scale, name, lv in roll_tiers:
        w.ea.append(Eff("0", invoke(f"cursed_{name}", dsl_program(name)), trig=every25, pre=tier_pre(stacks), **lv,
                        note=f"【诅咒】每 25 秒转一次（强化 Lv{lv['learn']} 档，增益 ×{scale:g}）：三种增益（各 1/4，20 秒）"
                             "或三种诅咒（各 1/12，10 秒；诅咒全额、强制付与、不可驱散）"))
        if stacks:
            w.ea.append(Eff("0", unique(u_tier), **lv, note=f"强化 Lv{lv['learn']}：开局「赌徒筹码」+1 层（档位标记）"))
    w.ea += [''')
rep('''    w.deviations.append("评分审查 0928（作者「按表改」）：保留提案这一版的 +500% 刃，只改提案未给的两个量——转盘权重 1:1:1:1:1:1 → "''',
    '''    w.deviations.append("第四轮 1007 修强化曲线（原强化 1 级即满值）：完整老虎机的增益（三项刃、技能槽、充能）按强化突破节点四档 "
                        "25/50/75/100%（Lv1/70/99/120），诅咒三支与复读 7 倍追击各档不变；开局赌注改为强化 1→120 线性成长")
    w.deviations.append("评分审查 0928（作者「按表改」）：保留提案这一版的 +500% 刃，只改提案未给的两个量——转盘权重 1:1:1:1:1:1 → "''')

# ---------------------------------------------------------------- 11 北斗百裂拳：每段 5% → 11%（合计 50% → 110%）
rep('''give(-17, [["ACAdditionalDirectAttack", P(DSL_FOREVER), P(10), P(-0.5), P(1)]],''',
    '''give(-17, [["ACAdditionalDirectAttack", P(DSL_FOREVER), P(10), P(0.1), P(1)]],''')
rep('''    w.cas["cursed_hokuto_hundred"] = "自身的直接攻击变为10段（每段伤害为原本的5%；强制付与，无视免疫与增益无效，不可驱散）"''',
    '''    w.cas["cursed_hokuto_hundred"] = "自身的直接攻击变为10段（每段伤害为原本的11%；强制付与，无视免疫与增益无效，不可驱散）"''')
rep('''            note="【诅咒】直接攻击变为 10 段、每段原伤害 5%（覆盖本体的 3 段；强制付与、无视免疫、不可驱散）"),''',
    '''            note="【诅咒】直接攻击变为 10 段、每段原伤害 11%（合计 110%；覆盖本体的 3 段；强制付与、无视免疫、不可驱散）"),''')

# ---------------------------------------------------------------- 16 孤注一掷（一拳超人）：回到各 500% 刃、乘区 20%
rep('''        Eff("0", stat("32", T_PARTY, 30, 120), pre=same, note="同属性编成时：全队攻击力 +30%→120%"),
        Eff("0", stat("34", T_PARTY, 30, 120), pre=same, note="同属性编成时：全队技能伤害 +30%→120%"),
    ]
    w.ea = [
        *growth_pair("35", T_PARTY, 50, 15, pre=same),
        *growth_pair("32", T_PARTY, 250, 120, pre=same),
        *growth_pair("34", T_PARTY, 250, 120, pre=same),
        Eff("0", stat("694", T_PARTY, 10), pre=same, **FINAL, note="同属性编成时：全队技能伤害独立乘区 +10%"),''',
    '''        Eff("0", stat("32", T_PARTY, 60, 240), pre=same, note="同属性编成时：全队攻击力 +60%→240%"),
        Eff("0", stat("34", T_PARTY, 60, 240), pre=same, note="同属性编成时：全队技能伤害 +60%→240%"),
    ]
    w.ea = [
        *growth_pair("35", T_PARTY, 50, 15, pre=same),
        *growth_pair("32", T_PARTY, 500, 240, pre=same),
        *growth_pair("34", T_PARTY, 500, 240, pre=same),
        Eff("0", stat("694", T_PARTY, 20), pre=same, **FINAL, note="同属性编成时：全队技能伤害独立乘区 +20%"),''')

# ---------------------------------------------------------------- 18 人格召唤枪
rep('''    pulse = lambda: [party(0, C("CreateRatioHeal", 0, 2, P(0.5), [], P(0), ["GenericHealHitEffect"])),''',
    '''    pulse = lambda: [party(0, C("CreateRatioHeal", 0, 2, P(0.15), [], P(0), ["GenericHealHitEffect"])),''')
rep('''    leader20 = trig(IT_HP_LOW, trigger_puller=P_LEADER, threshold=pct(20), cooltime="900")''',
    '''    leader20 = trig(IT_HP_LOW, trigger_puller=P_LEADER, threshold=pct(35), cooltime="900")   # 第四轮 1007：20% → 35%''')
rep('''    w.cas["cursed_persona_heal"] = "每秒回复全队最大HP的50%，队长额外回复20%（5秒）"''',
    '''    w.cas["cursed_persona_heal"] = "每秒回复全队最大HP的15%，队长额外回复20%（5秒）"''')
rep('''        party(0, C("CreateRatioHeal", 0, 2, P(0.2), [], P(0), ["GenericHealHitEffect"])),
        wait(180, party(1, C("CreateRatioHeal", 1, 2, P(0.8), [], P(0), ["GenericHealHitEffect"]))),''',
    '''        party(0, C("CreateRatioHeal", 0, 2, P(0.1), [], P(0), ["GenericHealHitEffect"])),
        wait(180, party(1, C("CreateRatioHeal", 1, 2, P(0.3), [], P(0), ["GenericHealHitEffect"]))),''')
rep('''    w.cas["cursed_persona_echo"] = "回复全队最大HP的20%，3秒后再回复80%；2号位与3号位角色技能槽减少30%"''',
    '''    w.cas["cursed_persona_echo"] = "回复全队最大HP的10%，3秒后再回复30%；2号位与3号位角色技能槽减少30%"''')

# ---------------------------------------------------------------- 21 失声之钟（哑钟）：加连击获取、提数值
rep('''        rows_s.append(Eff("0", stat("34", T_PARTY, 120, 240), pre=gate, note=f"{cn}属性共鸣时：全队技能伤害 +120%→240%"))
        rows_e += [
            *growth_pair("34", T_PARTY, 500, 240, pre=gate),''',
    '''        rows_s.append(Eff("0", stat("34", T_PARTY, 120, 240), pre=gate, note=f"{cn}属性共鸣时：全队技能伤害 +120%→240%"))
        rows_s.append(Eff("0", stat("32", T_PARTY, 75, 150), pre=gate, note=f"{cn}属性共鸣时：全队攻击力 +75%→150%"))
        rows_e += [
            *growth_pair("34", T_PARTY, 700, 240, pre=gate),
            *growth_pair("32", T_PARTY, 300, 150, pre=gate),
            # 第四轮 1007：加连击获取（随诅咒一同强化 1 级起生效；226 + 弹射触发 6 有魂珠/强化表先例）
            Eff("0", ("226", {"strength": (times(3), times(3))}), trig=trig("6", threshold=times(1)), pre=gate, **CURSE,
                note="每次弹射连击 +3"),''')

# ---------------------------------------------------------------- 22 柴油引擎：去掉 2/3 号位技能槽 -50%
rep('''    drain = dsl_program("diesel_drain")
    w.dsl[drain] = dsl_root(slot_member(0, 84, C("SubtractSkillPoint", 0, P(0.5))),
                            slot_member(1, 85, C("SubtractSkillPoint", 1, P(0.5))))
    w.cas["cursed_diesel_drain"] = "2号位与3号位角色技能槽减少50%"
''', '')
rep('''        Eff("0", invoke("cursed_diesel_drain", drain), trig=leader_skill, pre=fire, **CURSE,
            note="【诅咒】队长发动技能时 2、3 号位技能槽 -50%"),
''', '')

# ---------------------------------------------------------------- 25 超频芯片：过载 20 秒 → 10 秒（乘区 50% 不动，待作者拍板）
rep('''    w.uniques[u_over] = unique_row(f"cursed_overclock_{u_over}", "过载", "cursed_chip_overload", "1200", "2", bad=True)''',
    '''    w.uniques[u_over] = unique_row(f"cursed_overclock_{u_over}", "过载", "cursed_chip_overload", "600", "2", bad=True)''')
rep('''            note="【诅咒】自身发动技能后进入「过载」20 秒（强制付与、不可驱散）"),''',
    '''            note="【诅咒】自身发动技能后进入「过载」10 秒（强制付与、不可驱散）"),''')
rep('''    w.deviations.append(timed_curse_unique_note("过载", 20))''', '''    w.deviations.append(timed_curse_unique_note("过载", 10))''')

# ---------------------------------------------------------------- 26 孤狼王冠：单人补偿刃（共鸣无法数据伪造）
rep('''    stats = (("35", T_SELF, 100), ("723", T_SELF, 50))''',
    '''    # 第四轮 1007：单人时角色自身「属性共鸣」类能力天然不成立（前置 2 按真实编成人数计，数据层无法伪造），
    # 改为单人补偿：自身攻击力、技能伤害各 +300%（不要脸常规深渊上限 600% 用满），有队友时同样抵消
    stats = (("35", T_SELF, 100), ("723", T_SELF, 50), ("32", T_SELF, 300), ("34", T_SELF, 300))''')

# ---------------------------------------------------------------- 27 三相之力：全队转移重做
rep('''    TRANSFER = dict(learn=1, maxlvl=120)      # 转入量：强化 1 级 +20% → 120 级 +30%（同一行两端插值，不是诅咒常量）
    # 评分审查 0928 方案 A（作者拍板「按方案做」）：每项补 +140% 底数（含本体满破 14%），转化上限 6 → 2 次；
    # 刃合计 3×140% + 3×30%×2 = 600%（不要脸常规深渊上限），满转后每项净 +160%
    pf_hit = trig(IT_PF_HIT, threshold=times(1), cooltime="60", trigger_limit="2")
    direct = trig(IT_DIRECT, trigger_puller=P_SELF, threshold=times(1), cooltime="60", trigger_limit="2")
    skill_hit = trig(IT_SKILL_HIT, trigger_puller=P_SELF, threshold=times(1), cooltime="60", trigger_limit="2")
    w.ea = [
        *growth_pair("33", T_SELF, 140, 70, pre=gate),
        *growth_pair("34", T_SELF, 140, 70, pre=gate),
        *growth_pair("55", None, 140, 70, pre=gate),
        Eff("0", stat("55", None, -20), trig=pf_hit, pre=gate, **CURSE, note="【诅咒】强化弹射命中时强化弹射伤害 -20%"),
        Eff("0", stat("33", T_SELF, 20, 30), trig=pf_hit, pre=gate, **TRANSFER,
            note="同时自身直接攻击伤害 +20%（随强化成长，120 级 +30%）"),
        Eff("0", stat("33", T_SELF, -20), trig=direct, pre=gate, **CURSE, note="【诅咒】自身直接攻击时直接攻击伤害 -20%"),
        Eff("0", stat("34", T_SELF, 20, 30), trig=direct, pre=gate, **TRANSFER,
            note="同时自身技能伤害 +20%（随强化成长，120 级 +30%）"),
        Eff("0", stat("34", T_SELF, -20), trig=skill_hit, pre=gate, **CURSE, note="【诅咒】自身技能命中时技能伤害 -20%"),
        Eff("0", stat("55", None, 20, 30), trig=skill_hit, pre=gate, **TRANSFER,
            note="同时强化弹射伤害 +20%（随强化成长，120 级 +30%）"),
    ]''',
    '''    TRANSFER = dict(learn=1, maxlvl=120)      # 转入量：强化 1 级 = 终值一半 → 120 级终值（同一行两端插值）
    # 第四轮 1007 提案大改「全队转移」：强化弹射命中 → 全队直击 +40%（上限 +2000%）；全队直击 → 全队技能伤害 +20%；
    # 全队技能命中 → 强化弹射伤害 +100%；每路转出的减项上限 -1000%。触发改为全队（来源=队伍之一），各路 CT1 秒；
    # 上限用 trigger_limit 表达（永久数值每次触发叠加）：转入 2000/每次量、转出 1000/每次量。去掉 0928 方案 A 的 +140% 底数。
    def route(kind_out, out_target, out_step, kind_in, in_target, in_step, trigger_kind, puller, IN_CAP, OUT_CAP):
        def t(limit):
            given = dict(threshold=times(1), cooltime="60", trigger_limit=str(limit))
            if puller is not None:
                given["trigger_puller"] = puller
            return trig(trigger_kind, **given)
        return [
            Eff("0", stat(kind_out, out_target, -out_step), trig=t(int(OUT_CAP // out_step)), pre=gate, **CURSE,
                note=f"【诅咒】转出 -{out_step:g}%（上限 -{OUT_CAP}%）"),
            Eff("0", stat(kind_in, in_target, in_step / 2, in_step), trig=t(int(IN_CAP // in_step)), pre=gate, **TRANSFER,
                note=f"转入 +{in_step / 2:g}%→{in_step:g}%（随强化成长；上限 {int(IN_CAP // in_step)} 次）"),
        ]
    w.ea = [
        *route("55", None, 40, "33", T_PARTY, 40, IT_PF_HIT, None, IN_CAPS[0], OUT_CAPS[0]),
        *route("33", T_PARTY, 20, "34", T_PARTY, 20, IT_DIRECT, P_ONE_OF_PARTY, IN_CAPS[1], OUT_CAPS[1]),
        *route("34", T_PARTY, 100, "55", None, 100, IT_SKILL_HIT, P_ONE_OF_PARTY, IN_CAPS[2], OUT_CAPS[2]),
    ]''')
rep('''    w.deviations.append("「若该伤害加成 >100%」：技能/强化弹射伤害提升量前置官方零用例、直击没有此类前置；改为每种转移 CT1 秒、"
                        "限次数")''',
    '''    w.deviations.append("第四轮 1007 提案大改「全队转移」：PF 命中→全队直击 +40%（上限 2000%）、全队直击→全队技能伤害 +20%、"
                        "全队技能命中→强化弹射伤害 +100%；转出减项各自上限 -1000%（PF -40%×25、直击 -20%×50、技能 -100%×10）；"
                        "作者 1007 拍板收进 600% 预算：转入上限 直击 +160%（4 次）/技能 +180%（9 次）/强化弹射 +200%（2 次），转出上限 -80%/-80%/-100%；各路 CT1 秒；去掉 0928 的 +140% 底数。"
                        "转入量强化 1 级为终值一半，120 级满值；减项强化 1 级起全额")
    w.deviations.append("「若该伤害加成 >100%」：技能/强化弹射伤害提升量前置官方零用例、直击没有此类前置；改为每种转移 CT1 秒、"
                        "限次数")''')

# ---------------------------------------------------------------- 28 肉斩骨断：删掉全队直击 +400% 刃
rep('''        Eff("0", stat("33", T_PARTY, 100, 200), pre=wind, note="风属性共鸣时：全队直接攻击伤害 +100%→200%"),
''', '')
rep('''        *growth_pair("33", T_PARTY, 400, 200, pre=wind),
''', '')

# ---------------------------------------------------------------- 29 被诅咒的面具（鬼面）：永久封印+速度 → 发动技能后 20 秒封印+加速
rep('''    w.dsl[seal] = dsl_root(give(-17, [ac("ACSilence", DSL_FOREVER)], "cursed_mask_silence", cancelable=False, force=True))
    w.dsl[speed] = dsl_root(give(-17, [ac("ACFixedSpeed", DSL_FOREVER, P(2.0), P(0), P(1))], "cursed_mask_speed",
                                 cancelable=False, force=True))
    w.cas["cursed_mask_silence"] = "自身永久封印（强制付与，无视免疫与弱体无效，不可驱散）"
    w.cas["cursed_mask_speed"] = "弹球速度固定为200%（永续，强制付与，无视免疫与增益无效，不可驱散）"''',
    '''    # 第四轮 1007：永久封印/速度固定在复活后丢失（BUG 反馈）→ 改为「自身发动技能后 20 秒封印 + 弹球速度固定 200%」，
    # 一棵 DSL 一次付两个强制、不可驱散的计时状态（与复活无关，不再需要复活重挂行）
    del speed
    w.dsl[seal] = dsl_root(
        give(-17, [ac("ACSilence", 1200)], "cursed_mask_silence", cancelable=False, force=True),
        give(-17, [ac("ACFixedSpeed", 1200, P(2.0), P(0), P(1))], "cursed_mask_speed", cancelable=False, force=True))
    w.cas["cursed_mask_silence"] = "自身封印20秒，弹球速度固定为200%（20秒；强制付与，无视免疫与弱体无效，不可驱散）"''')
rep('''        Eff("0", invoke("cursed_mask_silence", seal), pre=dark, **CURSE,
            note="【诅咒】自身永久封印（不能施放技能；强制付与、无视免疫、不可驱散）"),
        Eff("0", invoke("cursed_mask_silence", seal), trig=revive, pre=dark, **CURSE,
            note="【诅咒】复活后重新附加封印（同键幂等）"),
        Eff("0", invoke("cursed_mask_speed", speed), pre=dark, **CURSE,
            note="【诅咒】弹球速度固定为 200%（永续；强制付与、无视增益无效、不可驱散）"),
        Eff("0", invoke("cursed_mask_speed", speed), trig=revive, pre=dark, **CURSE,
            note="【诅咒】复活后重新固定弹球速度（同键幂等）"),''',
    '''        Eff("0", invoke("cursed_mask_silence", seal), trig=trig(IT_SKILL, trigger_puller=P_SELF), pre=dark, **CURSE,
            note="【诅咒】自身发动技能后封印 20 秒、弹球速度固定 200%（20 秒；强制付与、无视免疫、不可驱散）"),''')


def main() -> None:
    text = SRC.read_text("utf-8")
    for i, (old, new) in enumerate(R):
        n = text.count(old)
        assert n == 1, f"替换 #{i} 命中 {n} 次：{old[:80]!r}"
        text = text.replace(old, new)
    # 第四轮按提案改后超预算、待作者拍板的武器（标签前两位 = 行号）
    # 三相之力各路转入/转出上限（PF→直击, 直击→技能, 技能→PF）。作者 1007 拍板：收进 600% 预算
    # （转入 160+180+200 + 本体满破 3×14 = 582%）；转出约为转入一半。提案原值 = 2000,2000,2000 / 1000,1000,1000。
    in_cap = os.environ.get("R4_TRIPHASE_IN_CAPS", "160,180,200")
    out_cap = os.environ.get("R4_TRIPHASE_OUT_CAPS", "80,80,100")
    assert text.count("    def route(kind_out,") == 1
    text = text.replace("    def route(kind_out,", f"    IN_CAPS, OUT_CAPS = ({in_cap}), ({out_cap})\n    def route(kind_out,")
    text = text.replace("ROUND4_OVER_BUDGET: dict[str, str] = {}",
                        'ROUND4_OVER_BUDGET: dict[str, str] = {}')
    DST.write_text(text, "utf-8")
    print(f"wrote {DST} ({len(R)} replacements)")


if __name__ == "__main__":
    main()
