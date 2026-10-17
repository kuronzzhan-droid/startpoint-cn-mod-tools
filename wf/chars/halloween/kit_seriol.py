# -*- coding: utf-8 -*-
"""塞里奥尔「别扭的吸血鬼伯爵」159985 crystal_swordman_halloween：光·PF 满速辅助。

技能「伯爵之礼」= 母本 crystal_swordman 演出与前方光属性伤害保留，去掉母本自身攻击/能力伤害增益，
追加官方 silence_suzuka 同形的队伍「固定最大速度/贯通/浮游」（不可消除）+ 强化弹射伤害 + 连击 + 冲刺不受控制。
"""
from __future__ import annotations

import copy

from wf.chars.halloween import color as hw_color
from wf.chars.halloween import kitlib as K
from wf.chars.support import common as C7
from wf.chars.support import kitlib as KL

KEY = "seriol"
EL = 4  # 光
NAME_SKILL = "伯爵之礼"
SKILL_DESC = ("将红酒杯泼洒，释放结晶化手臂中封存的能量，对自身前方的敌人造成光属性伤害／"
              "赋予队伍全体「固定最大速度」「贯通」「浮游」效果（均持续15秒，不可消除），一段时间内冲刺不受控制／"
              "赋予队伍全体「强化弹射伤害上升」效果（强化弹射伤害+100%，持续15秒）／连击数+20")
FRAMES = 900          # 15 秒
FRAMES_ENH = 1500     # 能力3 技能强化：固定最大速度 25 秒
BIND = 50


def skill_tree(base):
    t = copy.deepcopy(base)
    body = t[11][1]
    # 去掉母本两条自身增益（ACAttackPoint / ACAbilityDamage）
    keep = []
    for st in body:
        s = repr(st)
        if st[0] == "Command" and st[1][0] == "CreateCondition" and ("ACAttackPoint" in s or "ACAbilityDamage" in s):
            continue
        keep.append(st)
    removed = len(body) - len(keep)
    assert removed == 2, removed

    def fixed(frames):
        return K.cond(BIND, ["ACFixedSpeed", K.S(frames), K.S(1), K.S(0), K.S(1)], cancel=False)

    keep.append(K.find_all(
        BIND, 82,
        K.cond(BIND, ["ACPiercing", K.S(FRAMES)], cancel=False),
        K.cond(BIND, ["ACFlying", K.S(FRAMES)], cancel=False),
        K.C("ConditionalsChangeSkillFlag", 1, K.Blk(fixed(FRAMES_ENH)), K.Blk(fixed(FRAMES))),
        K.cond(BIND, ["ACPowerFlipDamage", K.S(FRAMES), K.S(1.0), K.S(1)]),
    ))
    keep.append(K.C("SuppressBallActivity", -18, K.S(240)))
    keep.append(K.C("AddCombo", K.S(20)))
    t[11][1] = keep
    return t


def pf3_tree(ctx, *, preserve_221=False):
    """能力5「释放一次 pf3」：官方 knight 弹射 Lv3 整树，根头 buffTargetAs=133（伤害按强化弹射 Lv3 结算，v28+ 客户端补丁）。"""
    t = K.load_tree(ctx, "battle/action/power_flip/action/knight$knight_lv3")
    t = copy.deepcopy(t)
    t[10] = 133
    if preserve_221:
        # 1.4.221 shipped the unsanitized native PF tree. Historical replay
        # must preserve those bytes; ordinary builds retain the 222 fix below.
        return t
    # SetPowerFilpSuppress / NotifyPowerflipEnd 只能在真弹射动作里执行；629 能力动作里会 INTERNAL ERROR
    # （测试服 1.4.221 真机 U_e66385，10-17）。去掉这两条，其余（判定区/特效/伤害/震屏）保留。
    PF_ONLY = ("SetPowerFilpSuppress", "NotifyPowerflipEnd")

    def strip(node):
        if isinstance(node, list):
            if node and node[0] == "Block" and isinstance(node[1], list):
                node[1] = [s for s in node[1] if not (isinstance(s, list) and s and s[0] == "Command"
                                                      and s[1][0] in PF_ONLY)]
            for x in node:
                strip(x)
    strip(t)
    assert not any(n in repr(t) for n in PF_ONLY)
    return t


FX_TPL_RULES = [{"from": [170, 260], "to": 350}]


STACK = 15998501
STACK_ICON = "battle/common/unique_condition/unique_halloween_wine"


def build(ctx):
    spec = ctx.spec
    code, cid = spec.code, spec.cid
    P3 = f"ability_skill_{code}_pf3"
    P3_PATH = f"battle/action/skill/action/ability_skill/{P3}${P3}"
    CHG = f"change_skill_{code}"

    # ---- 技能 DSL + 文案
    fam = ctx.clone_effect_family("battle/effect/skill_unique/crystal_swordman", "fx", png_transform=hw_color.transform(FX_TPL_RULES))
    for lv in ("1", "2"):
        prog = f"battle/action/skill/action/rare5/{code}${code}_{lv}"
        base = K.load_tree(ctx, f"battle/action/skill/action/rare5/{spec.template_code}${spec.template_code}_{lv}")
        K.write_dsl(ctx, prog, C7.rewrite_effect_refs(skill_tree(base), fam, strict=True)[0], EL)
    K.write_dsl(ctx, P3_PATH, pf3_tree(ctx, preserve_221=getattr(ctx, "historical_version", None) == "1.4.221"), EL)
    inner = ctx.pkg_nested(code)
    out = {}
    for lv, cells in inner.items():
        cells = list(cells)
        cells[0] = NAME_SKILL + ("＋" if lv == "2" else "")
        cells[1] = SKILL_DESC
        out[lv] = [cells]
    ctx.write_nested(KL.ACTION, code, out, replace_inner=True)
    K.sync_skill_text(ctx)

    # ---- 固有状态「伯爵的晚宴」：PF3 层数（上限 10，永续）
    import wf_assets
    urow = list(KL.donor_row(ctx, KL.UNIQUE, "1599971", source="live"))
    urow[0], urow[1], urow[2], urow[3], urow[4] = "unique_halloween_wine", "伯爵的晚宴", STACK_ICON, "99999999", "10"
    ctx.write_flat(KL.UNIQUE, {str(STACK): [urow]})
    ctx.write_asset("common", STACK_ICON + ".png",
                    wf_assets.png_encode((K.hw_env.OUT / "art" / "icons" / "unique_halloween_wine.png").read_bytes()), owner="kit")

    # ---- 队长技（自拟）
    leader = [
        ("光共鸣攻击", K.static(32, "party", 100, group=EL, pre=("res", EL))),
        ("光共鸣PF伤", K.static(55, "party", 150, group=EL, pre=("res", EL))),
        ("固定速度PF伤", K.during(214, 23, "party", 50, group=EL, pre=("res", EL))),
    ]
    lrows, lev = K.build_leader(ctx, leader)
    ctx.write_flat(KL.LEADER, {str(cid): lrows})

    # ---- 能力
    plan = {
        1: ("true", [("光共鸣PF伤", K.static(55, "party", 150, group=EL, pre=("res", EL)))]),
        2: ("true", [("每3次PF", K.trig(2, 55, "party", 10, threshold=3, limit=10, group=EL,
                                         pre=("leaderchar", EL)))]),
        3: ("false", [
            ("施技回槽", K.trig(23, 211, "except", 30, limit=2, pre=("leaderchar", EL)), "2310021#0"),
            ("技能强化", ("static", {"instant_content.string_id": CHG, "pre": ("leaderchar", EL)}), "1411113#0"),
        ]),
        4: ("true", [("开局技能槽", K.static(211, "self", 50), "1510334#0")]),
        5: ("true", [("施技释放PF3", ("trig", {
            "instant_trigger.kind": 23, "instant_trigger.trigger_puller": 0,
            "instant_trigger.threshold.power1": "100000", "instant_trigger.threshold.first_max": "100000",
            "instant_trigger.trigger_limit": "(None)", "instant_trigger.cooltime": 600,
            "instant_content.string_id": P3, "instant_content.action_path": P3_PATH,
            "pre": ("res", EL)}), "1611053#0")]),
        # 「每次 PF3 +0.5% 独立乘区」：独立乘区是取最大值类，不能挂累积瞬发触发（C2308 真机实证）
        # → 官方 guildknight_leader_tavern 同法：PF3 刻固有层（上限 10），持续 134 按层数给 413。
        6: ("false", [
            ("PF3刻层", ("trig", {"instant_trigger.kind": 65, "instant_content.unique_condition_id": STACK,
                                  "pre": ("res", EL)}), "1410813#0"),
            ("层数独立乘区", K.during(134, 413, "party", 0.5, threshold=1, limit=10, unique=STACK, group=EL,
                                     pre=("res", EL)), "1599971#4"),
        ]),
    }
    arows, aev = K.build_abilities(ctx, plan)
    ctx.write_flat(KL.ABILITY, arows)

    # ---- 文案
    MAIN = " <icon id='main'>  "
    cas = {
        CHG: "强化『伯爵之礼』的「固定最大速度」效果",
        P3: "释放一次强化弹射Lv3",
        f"desc_override_{code}": "\n".join([
            "光属性共鸣时：光属性角色攻击力＋100%、强化弹射伤害＋150%",
            "光属性共鸣时：处于「固定最大速度」状态时，光属性角色强化弹射伤害＋50%",
        ]),
        f"desc_override_{code}_1": "光属性共鸣时：光属性角色强化弹射伤害＋150%",
        f"desc_override_{code}_2": "队长为光属性时：每发动3次强化弹射，光属性角色强化弹射伤害＋10%（最多＋100%）",
        f"desc_override_{code}_3": "\n".join(MAIN + x for x in (
            "队长为光属性时：自身发动技能时，除自身外的队伍成员技能槽＋30%（最多2次）",
            "队长为光属性时：强化『伯爵之礼』的「固定最大速度」效果")),
        f"desc_override_{code}_4": "战斗开始时，自身技能槽＋50%",
        f"desc_override_{code}_5": "光属性共鸣时：自身发动技能时，释放一次强化弹射Lv3（冷却时间10秒）",
        f"desc_override_{code}_6": MAIN + "光属性共鸣时：队伍每发动一次强化弹射Lv3，光属性角色强化弹射伤害额外乘区＋0.5%（最多＋5%）",
    }
    for k, v in cas.items():
        for line in v.split("\n"):
            KL.check_panel(line.replace(MAIN, ""), skill_flag=(k == CHG), label=k)
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas.items()})
    ctx.report({"character": KEY, "leader": [e["describe"] for e in lev],
                "abilities": [f"{e['key']}:{e['describe']}" for e in aev], "cas": cas})
    return {"leader": [e["describe"] for e in lev], "abilities": [f"{e['key']} {e['describe']}" for e in aev]}
