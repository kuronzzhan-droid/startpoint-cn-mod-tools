# -*- coding: utf-8 -*-
"""水杰拉德 129989 white_wolf_gerald_aqua：水·★5·辅助（母本拉绮夏 121007）。

技能「潮汐守誓」：操纵水流治愈全体参战成员（按各自发动瞬间的当前 HP 分 10 档：HP≥90% 回 5%……HP<10% 回 50% 最大 HP，
硬卡 50% 不吃水属性加成；联机队友只能平值 25%）；HP 全满的成员各获得自身最大 HP 15% 的护盾（作者 10-19 改）；全队两个独立的攻击力 +150%
（15 秒）；消除全体敌人 2 个强化；全队全属性抗性 +15%（15 秒）。
能力 6「Fever 中强化自身技能」：Fever 中发动且学会能力 6 时，护盾 30%、两个攻击力各 +200%、抗性 +25%、消除 3 个强化。
特效：拉绮夏水浪（主体）+ 芙拉克西斯潮水（垫底）+ 妮丝艾丝星光（增益闪光）+ 圣母斜雨换蓝（雨丝）。
调研依据：kit/research_heal_buff.md、kit/research_resonance_pf.md、fx_survey/全屏特效清单.md。
"""
from __future__ import annotations

import copy
import csv
import io

import wg_color
import wg_kitlib as K
import wf_midautumn_kitlib as KL

KEY = "aqua"
EL = 1  # 水
NAME_SKILL = "潮汐守誓"
SKILL_DESC = ("操纵水流治愈全体参战成员（成员当前生命值越低，回复量越高）＋生命值全满的成员获得护盾（护盾量按自身的最大生命值计算）"
              "＋赋予全队攻击力提升效果（2个）与全属性耐性提升效果＋消除全体敌人的2个强化效果")
FX = {  # 源族 → (新子目录, 只复制这些特效, 换色规则)
    "tide_wave": ("battle/effect/skill_unique/drawing_witch", ["drawing_witch_all", "drawing_witch_main"], None),
    "tide_floor": ("battle/effect/skill_unique/navy_officer", ["navy_officer_wave"], None),
    "star_ripple": ("battle/effect/skill_unique/vesta_caster", ["vesta_caster_all"], None),
    # 圣母青色斜雨（治疗）→ 水蓝：只转色相，明度不动
    "rain": ("battle/effect/skill_unique/holy_mother", ["holy_mother_all"], [{"from": [150, 200], "to": 212}]),
}
HEAL_LADDER = [(90, 0.05), (80, 0.10), (70, 0.15), (60, 0.20), (50, 0.25), (40, 0.30), (30, 0.35), (20, 0.40), (10, 0.45)]
HEAL_FLOOR = 0.50          # HP<10%
HEAL_MATE = 0.25           # 联机队友（-33 做 HP 判定会崩，只能平值）
NORMAL = dict(shield=0.15, atk=1.5, res=0.15, dispel=2)
FEVER_ENH = dict(shield=0.30, atk=2.0, res=0.25, dispel=3)
BUFF_FRAMES = 900          # 15 秒


def S(a, b=None):
    return K.S(a, b)


def show(name, path, subj, front="ForesideOfCharacter", life=("PlayOnlyFirstSequence",)):
    return K.C("ShowEffect", name, ["SpecifyEffectDirectly", path], subj, [front], list(life), ["AB"], 0, 0, 0,
               False, False, ["None"])


def heal(subj, r):
    # 组码 [] / 组加成 0：上限硬卡在基础比率，不被水属性加成放大
    return K.C("CreateRatioHeal", subj, 2, S(r), [], S(0), ["GenericHealHitEffect"])


def ladder(bind):
    node = K.Blk(heal(bind, HEAL_FLOOR))
    for thr_, r in reversed(HEAL_LADDER):
        node = K.Blk(K.C("ConditionalsHealthPointRatioOf", bind, thr_, K.Blk(heal(bind, r)), node))
    return node[1][0]


def effect_block(v):
    """一次技能的玩法本体（v=NORMAL 或 FEVER_ENH）。HP 判定都是发动瞬间快照。"""
    atk = ["ACAttackPoint", S(BUFF_FRAMES), S(v["atk"]), S(1)]
    res = ["ACToleranceOfElement", S(BUFF_FRAMES), 254, S(v["res"]), S(1)]
    def shield(bind):
        # 作者 10-19：生命值全满的队伍成员各自获得护盾（发动瞬间快照，先判再回血）。
        # 原生 CreateBarrier 量 = 目标自身最大生命值×比率；v35j 码32（BARRIER_UID 挂在杰拉德身上）改为执行者＝杰拉德的最大生命值
        return K.C("ConditionalsHealthPointRatioOf", bind, 100,
                   K.Blk(K.C("CreateBarrier", bind, S(v["shield"]), ["GenericBarrierHitEffect"])), K.Blk())
    return K.Blk(
        K.find_all(0, 113, shield(0), ladder(0)),
        K.find_all(1, 145, shield(1), ladder(1)),
        heal(-33, HEAL_MATE),
        K.find_all(2, 33,
                   K.cond(2, atk, key="wg_aqua_atk_1"),
                   K.cond(2, atk, key="wg_aqua_atk_2"),
                   K.cond(2, res, key="wg_aqua_res")),
        K.find_all(3, 49, K.C("DeleteCondition", 3, ["DCAll", v["dispel"]], v["dispel"], 0, "", ["Default"])),
    )


def skill_tree(fam):
    p = {k: f["dst_dir"] for k, f in fam.items()}
    body = [
        K.C("StopBall", -18, 48, ["RestoreToSpeedBeforeActionExecution"], ["AB"], 0),
        show("自身演出", f"{p['tide_wave']}/drawing_witch_main", -17,
             life=("SpecifyEffectLifetimeDirectly", 65)),
        show("潮水垫底", f"{p['tide_floor']}/navy_officer_wave", -1),
        K.wait(18, show("雨丝", f"{p['rain']}/holy_mother_all", -1, front="SuperForesideOfCharacter")),
        K.wait(43, show("水浪", f"{p['tide_wave']}/drawing_witch_all", -1),
               K.C("ConditionalsFeverMode",
                   K.Blk(K.C("ConditionalsChangeSkillFlag", 1, effect_block(FEVER_ENH), effect_block(NORMAL))),
                   effect_block(NORMAL))),
        K.wait(60, show("增益星光", f"{p['star_ripple']}/vesta_caster_all", -1, front="SuperForesideOfCharacter")),
    ]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, K.Blk(*body)]


def build_skill(ctx):
    code = ctx.spec.code
    fam = {}
    for sub, (src, names, rules) in FX.items():
        kw = {"png_transform": wg_color.transform(rules)} if rules else {}
        fam[sub] = ctx.clone_effect_family(src, sub, names, **kw)
    tree = skill_tree(fam)
    for lv in ("1", "2"):
        K.write_dsl(ctx, f"battle/action/skill/action/rare5/{code}${code}_{lv}", tree, EL)
    inner = ctx.pkg_nested(code)
    out = {}
    for lv, cells in inner.items():
        cells = list(cells)
        cells[0] = NAME_SKILL + ("＋" if lv == "2" else "")
        cells[1] = SKILL_DESC
        cells[2] = "dynamic/skill/heal"
        out[lv] = [cells]
    ctx.write_nested(KL.ACTION, code, out, replace_inner=True)
    K.sync_skill_text(ctx)
    return {sub: f["copied_bases"] for sub, f in fam.items()}


HEAL_DMG_UID, HEAL_FEVER_UID = "12998901", "12998902"
BARRIER_UID = "12998903"
# v35k 码34/35：治疗不限来源（持有者口径，只挂自身）；有持有者时 v35k 自动跳过全队的 30/31，旧客户端照旧走 30/31
HEAL_DMG_ANY_UID, HEAL_FEVER_ANY_UID = "12998904", "12998905"   # v35j 码32：自身施放的护盾按自身最大生命值算（作者 10-19）
# v35f 新码（见 TASK6）：码30 治疗转伤害 arg=伤害分类(0=跟随队长定位概念) value=每1%实际治疗的攻击力倍率(万分比) flags=每1%溢出的倍率
#                       码31 治疗加 Fever value=每1%实际治疗加槽(万分比/最大槽) flags=每1%溢出加槽
WFX_HEAL_DMG = "wfx:30:0:10000:50000:hidden_wg_aqua_heal_damage"
WFX_HEAL_FEVER = "wfx:31:0:100:200:hidden_wg_aqua_heal_fever"
WFX_BARRIER = "wfx:32:0:0:0:hidden_wg_aqua_caster_barrier"
WFX_HEAL_DMG_ANY = "wfx:34:5050:100000:150000:hidden_wg_aqua_heal_damage_any"   # arg=分类0+10×档位5%+1000×CT5秒：每5%有效10倍/溢出15倍，零头丢弃，出伤后5秒冷却（作者 10-19）
WFX_HEAL_FEVER_ANY = "wfx:35:50:500:1000:hidden_wg_aqua_heal_fever_any"   # 每5%一档：有效+5%槽/溢出+10%槽（作者 10-19）
ANY = ("kind", 208, 6)      # 任意属性共鸣：同一属性最多的人数 ≥ 6（原生前置 208，官方魂珠 5090051 先例）
RES = ("res", EL)           # 水属性共鸣：前置 2，Blue ≥ 6
# 全队目标的组列必须写 "(None)"（官方写法）；空串会解析成 null 组，面板显示「null角色」且能力永不发动（测试服 10-19）
ALL = "(None)"


def build_abilities(ctx):
    code, cid = ctx.spec.code, ctx.spec.cid
    CHG = f"change_skill_{code}"
    plan = {
        1: ("true", [
            ("开局全队技能槽", K.static(211, "party", 50, group=ALL, pre=ANY)),
            ("开局自身技能槽", K.static(211, "self", 50, pre=ANY)),
            ("全队技能槽上限", K.static(245, "party", 25, group=ALL, pre=ANY)),
            # 无前置：技能护盾本身不看共鸣，码32 状态全程挂着（隐藏）
            ("护盾按自身生命值(码32)", ("static", {"instant_content.unique_condition_id": BARRIER_UID,
                                              "pre": [("none",)]}), "1410216#0"),
        ]),
        2: ("true", [
            ("全队攻击力", K.static(32, "party", 200, group=ALL, pre=ANY)),
            ("全队受疗", K.static(195, "party", 20, group=ALL, pre=ANY)),
        ]),
        # 码30/31 认「治疗者身上的状态」：给全队挂，任何成员的治疗/溢出治疗都转伤害与 Fever（作者 10-19）
        3: ("false", [
            ("治疗转伤害(码30)", ("static", {"instant_content.unique_condition_id": HEAL_DMG_UID, "instant_content.target": 5,
                                       "instant_content.target.character_groups": ALL, "pre": ANY}), "1410216#0"),
            ("治疗加Fever(码31)", ("static", {"instant_content.unique_condition_id": HEAL_FEVER_UID, "instant_content.target": 5,
                                       "instant_content.target.character_groups": ALL, "pre": ANY}), "1410216#0"),
            ("Fever中全队攻击力", K.during(4, 0, "party", 200, group=ALL, pre=ANY)),
            ("Fever中全队强化弹射", K.during(4, 23, "party", 400, group=ALL, pre=ANY)),
            # 每次拍板（拍板先清零连击）后 +30 = 只在 Fever 中生效的连击保底，和赛瑞斯的同写法行相加
            ("Fever中连击+30", K.trig(26, 226, "self", 0, raw="3000000", pre=[ANY, ("kind", 12)]), "2310044#0"),
            # 新行只追加到键尾（rec#0 与已有行序号不动）
            ("治疗不限来源转伤害(码34)", ("static", {"instant_content.unique_condition_id": HEAL_DMG_ANY_UID, "pre": ANY}), "1410216#0"),
            ("治疗不限来源加Fever(码35)", ("static", {"instant_content.unique_condition_id": HEAL_FEVER_ANY_UID, "pre": ANY}), "1410216#0"),
        ]),
        4: ("true", [("全队充能速度", K.static(35, "party", 20, group=ALL, pre=ANY))]),
        5: ("true", [
            ("全队受疗", K.static(195, "party", 10, group=ALL, pre=ANY)),
            ("全队技能槽上限", K.static(245, "party", 10, group=ALL, pre=ANY)),
        ]),
        6: ("false", [
            ("技能强化(Fever中)", ("static", {"instant_content.string_id": CHG, "pre": ANY}), "1411113#0"),
        ]),
    }
    return plan, CHG


UNIQUE_ICON = "battle/common/unique_condition/unique_white_wolf_gerald_aqua"
UNIQUE_ICON_SRC = "battle/common/unique_condition/unique_ice_dragon.png"   # 官方冰系图标原样复制（hidden_ 不显示，只为包内自带）


def new_unique(ctx, uid, sid, name, src_uid="16998502"):
    src = KL.donor_row(ctx, KL.UNIQUE, src_uid, source="live")
    r = list(src)
    r[0], r[1], r[2], r[3], r[4] = sid, name, UNIQUE_ICON, "99999999", "1"
    r[9] = "false"      # 不可驱散
    loc = ctx.pack.live_locate(UNIQUE_ICON_SRC)
    ctx.pack.write_asset("common", UNIQUE_ICON + ".png", loc[1].read_bytes(), owner="kit")
    ctx.write_flat(KL.UNIQUE, {uid: [r]})
    return r


# ---------------------------------------------------------------- 专属强化弹射（光杰拉德 PF 换水 + Fever 翻倍）
PF_KEY = "white_wolf_gerald_aqua_pf"
PF_TXT = "override_string_white_wolf_gerald_aqua"
PF_SRC = "battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv{}"
PF_FX_SRC = "battle/effect/powerflip/white_wolf_gerald_powerflip"
PF_FX_NAMES = [f"white_wolf_gerald_powerflip_lv{n}" for n in (1, 2, 3)]
# 光杰拉德的钟环：紫 → 水蓝、蓝 → 浅水蓝、金色刻度 → 淡青
PF_FX_RULES = [{"from": [240, 300], "to": 212}, {"from": [185, 240], "to": 198},
               {"from": [20, 75], "to": 186, "sat": 0.55}]
LIGHT_MARK = ["DCUnique", 1499989]      # 光杰拉德「时之刻印」（光共鸣标记）
EXPLICIT = EL + 1                       # DSL 显式元素 = 内部 +1（水 = 2）
PFA = "master/skill/power_flip_action.orderedmap"


def _x2_attacks(node) -> int:
    """CreateNormalAttack 第 6 参（每段倍率）min/max 翻倍。"""
    n = 0
    for c in K.find_nodes(node, "CreateNormalAttack"):
        for d in c[6]:
            d["min"], d["max"] = d["min"] * 2, d["max"] * 2
        n += 1
    return n


# 合击赛瑞斯时照他的形态同发多种强化弹射（作者 10-18 13:47）：他的队长技第 1 行开战给自身挂 1299901
# （箭头道具标记，只有赛瑞斯的队长技会挂），据此判「合击是赛瑞斯」；「真龙」形态 = 固有 22。
SERIS_MARK = ["DCUnique", 1299901]
SERIS_DRAGON = ["DCUnique", 22]
SERIS_HUMAN_PF = "battle/action/power_flip/action/override/override_seris_human_powerflip$override_seris_human_powerflip_lv{}"
SERIS_DRAGON_PF = "battle/action/power_flip/action/override/override_seris_dragon_special$override_seris_dragon_special_lv{}"
SERIS_SUPPRESS = 142


def _pf_parts(tree, drop_effect=None):
    """赛瑞斯覆盖树的顶层语句，去掉 SetPowerFilpSuppress、只装 NotifyPowerflipEnd 的 Wait，
    drop_effect：再去掉引用该特效的顶层语句（真龙树里的剑士型旋斩换成杰拉德的剑）。"""
    out = []
    for s in tree[11][1]:
        txt = repr(s)
        if s[0] == "Command" and s[1][0] in PF_ONLY:
            continue
        if s[0] == "Event" and "NotifyPowerflipEnd" in txt:
            assert "CreateNormalAttack" not in txt, txt[:200]
            continue
        if drop_effect and drop_effect in txt:
            continue
        out.append(copy.deepcopy(s))
    assert not any(n in repr(out) for n in PF_ONLY)
    return out


# 合击角色的强化弹射类型（作者 10-19「合击索维时也能发动索维的特殊强化弹射」）：
# 队长行按原生前置 4 UnisonMyself+类型组（Knight/Fighter/Ranged/Supporter/Special，matchCharacterGroup case1=specialityType）
# 开战给自身挂隐藏标记，专属强化弹射树按标记追加该类型的官方同档树（去 Suppress/Notify）。合击是赛瑞斯时走他的形态分支。
UNISON_TYPES = (("knight", "Knight", "剑士型"), ("fighter", "Fighter", "格斗型"), ("ranged", "Ranged", "射击型"),
                ("supporter", "Supporter", "辅助型"), ("special", "Special", "特殊型"))
UNISON_UID = {fam: str(12998911 + i) for i, (fam, _, _) in enumerate(UNISON_TYPES)}
# 合击角色自带专属强化弹射（队长技 419/722 覆盖，作者 10-19「合击角色有特殊强化弹射的特效也要发动」）：
# 全库水属性只有这 3 人（赛瑞斯另走形态分支）。按角色专属 tag 判合击（前置 4 + character_groups=tag），
# 命中时追加她/他的覆盖树并跳过通用类型树（官方里专属覆盖本来就顶替通用类型）。
# 特效族挂在各自 code_name 目录下，合击在队时随角色预载。
UNISON_OWN = (("121177", "索维", "override_psycho_reaper_meteor23"),
              ("129997", "克劳德", "claude_wolf_assassin_ex_pf"),
              ("129992", "蔷薇骑士", "override_unicorn_lancer_rose_dual_pf"))
OWN_UID = {cid: str(12998916 + i) for i, (cid, _, _) in enumerate(UNISON_OWN)}
OWN_TAG = {cid: f"wfx_unison_pf_{cid}" for cid, _, _ in UNISON_OWN}
CHAR_TAG = "master/character/character_tag.orderedmap"
CHAR = "master/character/character.orderedmap"


def own_tags(ctx):
    """character_tag 加 3 个专属 tag，3 人的 character 行 c5（tags，split(",")）追加。"""
    ctx.write_flat(CHAR_TAG, {OWN_TAG[cid]: [[zh]] for cid, zh, _ in UNISON_OWN})
    live = ctx.live_flat(CHAR)
    rows = {}
    for cid, _, _ in UNISON_OWN:
        r = next(csv.reader(io.StringIO(live[cid])))
        tags = [t for t in r[5].split(",") if t]
        assert OWN_TAG[cid] not in tags and r[3] == "1", (cid, r[:8])
        r[5] = ",".join(tags + [OWN_TAG[cid]])
        rows[cid] = [r]
    ctx.write_flat(CHAR, rows)
    return {cid: rows[cid][0][5] for cid in rows}


def _strip_pf_only(tree):
    """递归删 SetPowerFilpSuppress / NotifyPowerflipEnd（官方类型树把它们嵌在碰撞/等待事件里）。"""
    t = copy.deepcopy(tree)

    def strip(node):
        if isinstance(node, list):
            if node and node[0] == "Block" and isinstance(node[1], list):
                node[1] = [x for x in node[1] if not (isinstance(x, list) and x and x[0] == "Command"
                                                      and x[1][0] in PF_ONLY)]
            for x in node:
                strip(x)
    strip(t)
    assert not any(n in repr(t) for n in PF_ONLY)
    return t


def _drop_flying(tree):
    """作者 10-19「杰拉德的辅助PF去掉浮游效果」：删掉只给 ACFlying 的 CreateCondition（含追加的辅助型/专属树）。"""
    t = copy.deepcopy(tree)
    hit = [0]

    def strip(node):
        if isinstance(node, list):
            if node and node[0] == "Block" and isinstance(node[1], list):
                keep = []
                for x in node[1]:
                    if (isinstance(x, list) and x and x[0] == "Command" and x[1][0] == "CreateCondition"
                            and all(e[0] == "ACFlying" for e in x[1][2])):
                        hit[0] += 1
                        continue
                    keep.append(x)
                node[1] = keep
            for x in node:
                strip(x)
    strip(t)
    assert "ACFlying" not in repr(t)
    return t, hit[0]


def has_mark(mark, then, other):
    """自身有该固有状态。不用 ConditionalsConditionAccumulationNumber：它只数可叠加状态（上限>1，
    Condition.get_accumulatable），上限 1 的标记永远算 0 层 → 分支永不走（10-19 本机诊断实锤）。
    ConditionalsConditionExist(-17 自身, 状态) 只看有没有，官方 DSL 有同写法先例。"""
    return K.C("ConditionalsConditionExist", -17, mark, then, other)


def seris_extras(ctx, n):
    human = _pf_parts(K.load_tree(ctx, SERIS_HUMAN_PF.format(n)))
    dragon = _pf_parts(K.load_tree(ctx, SERIS_DRAGON_PF.format(n)), drop_effect="pfq_spin")
    assert human and dragon and "pfq_spin" not in repr(dragon)
    chain = K.Blk()
    for fam, _, _ in reversed(UNISON_TYPES):
        parts = _strip_pf_only(K.load_tree(ctx, f"battle/action/power_flip/action/{fam}${fam}_lv{n}"))[11][1]
        assert parts, fam
        chain = K.Blk(has_mark(["DCUnique", int(UNISON_UID[fam])],
                          K.Blk(*parts), chain))
    for cid, _, base in reversed(UNISON_OWN):
        own = _strip_pf_only(K.load_tree(ctx, f"battle/action/power_flip/action/override/{base}${base}_lv{n}"))[11][1]
        assert own, base
        chain = K.Blk(has_mark(["DCUnique", int(OWN_UID[cid])],
                          K.Blk(*own), chain))
    return has_mark(SERIS_MARK, K.Blk(has_mark(SERIS_DRAGON, K.Blk(*dragon), K.Blk(*human))), chain)


def pf_override_tree(src, fam, extras=None):
    """光杰拉德三档树：刻印分支改判「水属性共鸣」（原生 ConditionalsUnifyElement：主位+合击水 ≥6），
    共鸣分支再按 Fever 分：Fever 中每段倍率 ×2；Lv3 的光属性筛选 [5] → 水 [2]；特效引用改到克隆族。
    extras：共鸣分支末尾追加的合击赛瑞斯多重强化弹射（Fever 分支同样 ×2）。"""
    import wf_seasonal7_common as C7
    t = copy.deepcopy(src)
    blk = t[11]
    assert blk[0] == "Block" and len(blk[1]) == 1, blk[0]
    cmd = blk[1][0][1]
    assert cmd[0] == "ConditionalsConditionAccumulationNumber" and cmd[1] == LIGHT_MARK and cmd[2] == 1, cmd[:3]
    res_branch, plain = cmd[3], cmd[4]
    if extras is not None:
        res_branch[1].append(copy.deepcopy(extras))
        # 赛瑞斯真龙树要 142 帧收尾：杰拉德 Lv1 的 140 拉到 142（Lv2/Lv3 本来就更长）
        for st in res_branch[1]:
            if st[0] == "Command" and st[1][0] == "SetPowerFilpSuppress":
                st[1][1] = max(st[1][1], SERIS_SUPPRESS)
            elif st[0] == "Event" and st[1][0] == "Wait" and "NotifyPowerflipEnd" in repr(st):
                st[1][1] = max(st[1][1], SERIS_SUPPRESS - 1)
    fever = copy.deepcopy(res_branch)
    assert _x2_attacks(fever) >= 1
    blk[1][0] = K.C("ConditionalsUnifyElement", EXPLICIT, 6,
                    K.Blk(K.C("ConditionalsFeverMode", fever, res_branch)), plain)
    for f in K.find_nodes(t, "FindAllSubjects"):
        if f[3] == [5]:
            f[3] = [EXPLICIT]
    t, info = C7.rewrite_effect_refs(t, fam, strict=True)
    assert "1499989" not in repr(t) and info["rewritten"] >= 2, info
    return t


def build_pf_override(ctx):
    import wg_color
    fam = ctx.clone_effect_family(PF_FX_SRC, "pf", PF_FX_NAMES, png_transform=wg_color.transform(PF_FX_RULES))
    paths = []
    for n in (1, 2, 3):
        prog = f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
        tree, nfly = _drop_flying(pf_override_tree(K.load_tree(ctx, PF_SRC.format(n)), fam, seris_extras(ctx, n)))
        assert nfly >= 1, n
        K.write_dsl(ctx, prog, tree, EL)
        paths.append(prog)
    ctx.write_flat(PFA, {PF_KEY: [paths]})
    return {"fx": fam["copied_bases"], "paths": paths}


# ---------------------------------------------------------------- 进入 Fever 立即发动全部强化弹射类型
BURST = (("knight", "剑士型"), ("fighter", "格斗型"), ("ranged", "射击型"), ("supporter", "辅助型"), ("special", "特殊型"))
BURST_WAIT = (0, 24, 48, 72, 96)        # 五族错开 0.4 秒（c44 只收整数秒，用树内 Wait 错开）
PF_ONLY = ("SetPowerFilpSuppress", "NotifyPowerflipEnd")


def burst_tree(ctx, fam, wait):
    """官方 Lv3 整树：根头 133（v28+ 伤害分类补丁：按强化弹射 Lv3 结算）、删两条 PF 专用命令
    （629 里执行会 U_e66385，1.4.221 实证）；进 Fever 时发动，必在 Fever 中，按队长技「Fever 中倍率翻倍」×2。"""
    t = copy.deepcopy(K.load_tree(ctx, f"battle/action/power_flip/action/{fam}${fam}_lv3"))
    t[10] = 133

    def strip(node):
        if isinstance(node, list):
            if node and node[0] == "Block" and isinstance(node[1], list):
                node[1] = [s for s in node[1] if not (isinstance(s, list) and s and s[0] == "Command"
                                                      and s[1][0] in PF_ONLY)]
            for x in node:
                strip(x)
    strip(t)
    assert not any(n in repr(t) for n in PF_ONLY)
    assert _x2_attacks(t) >= 1, fam
    if wait:
        t[11] = K.Blk(K.wait(wait, *t[11][1]))
    return _drop_flying(t)[0]


def build_burst(ctx):
    code = ctx.spec.code
    out = []
    for (fam, zh), wait in zip(BURST, BURST_WAIT):
        key = f"ability_skill_{code}_pf_{fam}"
        prog = f"battle/action/skill/action/ability_skill/{key}${key}"
        K.write_dsl(ctx, prog, burst_tree(ctx, fam, wait), EL)
        out.append((fam, zh, key, prog))
    return out


def build_leader(ctx, burst):
    rows = [
        ("水共鸣攻击力", K.static(32, "party", 300, group=EL, pre=RES)),
        ("水共鸣强化弹射伤害", K.static(55, "party", 400, group=EL, pre=RES)),
        # 光杰拉德 149999 第 2 行同款：开战即覆盖，等级只写 1,2,3（Lv4 让给合击赛瑞斯的「苍海怒涛」）
        ("专属强化弹射", ("static", {"instant_content.powerflip_override.id": PF_KEY,
                                  "instant_content.powerflip_override.levels": "1,2,3",
                                  "instant_content.powerflip_override.description_id": PF_TXT}), "149999#1"),
    ]
    for fam, token, zh in UNISON_TYPES:   # 赛瑞斯 129999 第 1 行（开战 461 挂自身）做 donor
        rows.append((f"合击为{zh}时挂标记", ("static", {
            "instant_content.unique_condition_id": UNISON_UID[fam], "pre": [RES, ("kind", 4)],
            "precondition2.character_groups": token}), "129999#0"))
    for cid, zh, _ in UNISON_OWN:         # 同上 donor：合击为该角色时挂专属标记
        rows.append((f"合击为{zh}时挂标记", ("static", {
            "instant_content.unique_condition_id": OWN_UID[cid], "pre": [RES, ("kind", 4)],
            "precondition2.character_groups": OWN_TAG[cid]}), "129999#0"))
    for fam, zh, key, prog in burst:      # 光杰拉德 149999 第 8 行（队长位 629）做 donor
        rows.append((f"进Fever·{zh}强化弹射Lv3", ("trig", {
            "instant_trigger.kind": 8, "instant_trigger.threshold.power1": "100000",
            "instant_trigger.threshold.first_max": "100000",
            "instant_content.kind": 629, "instant_content.string_id": key, "instant_content.action_path": prog,
            "pre": RES}), "149999#7"))
    return rows


# ---------------------------------------------------------------- 合击赛瑞斯兼容（kit/research_seris_unison.md）
SERIS, SERIS_CODE = "129999", "seris_dragon_king"
STANCE = "master/stance_detail/character_stance_detail.orderedmap"


def seris_fever_combo(ctx):
    """作者 10-18「连击加成是 fever 中生效」：赛瑞斯队长技第 5 行 489（首次进 Fever 后整场保底 40）
    → 照他第 6 行（26 自身拍板 → 226）改成 Fever 中每次拍板 +40，等同只在 Fever 中的保底，和水杰拉德的 +30 相加。"""
    rows = list(csv.reader(io.StringIO(ctx.live_flat(KL.LEADER)[SERIS])))
    r4, r5 = rows[4], rows[5]
    assert r4[45] == "489" and r4[49] == "4000000" and r5[25] == "26" and r5[45] == "226", (r4[45], r5[45])
    new = list(r5)
    new[49] = new[50] = "4000000"
    new[K.col("leader_ability", "precondition2.kind")] = "12"
    rows[4] = new
    ctx.write_flat(KL.LEADER, {SERIS: rows})
    return {"r4": "26→226 +40, pre2 Fever"}


def stance_rows(ctx):
    """队伍特性（原生 character_stance_detail，第 2 列 concepts：1 技能/2 强化弹射/3 直接攻击/4 能力）。
    v35f 码 30 的「伤害类型跟随队长」读队长 main_stance.concepts[0]。"""
    gerald = '"1,2",2,"2,4",3,"1,2",2,"2,4",1'     # 驱散+治疗 / 强化弹射 / 治疗+辅助 / 最适强化弹射伤害
    seris = ",2,1,3,,2,1,3"                        # 赛瑞斯原先没有这一行
    ctx.write_flat(STANCE, {ctx.spec.cid_s: [next(csv.reader([gerald]))], SERIS: [next(csv.reader([seris]))]})
    return {"gerald": gerald, "seris": seris}


# ---------------------------------------------------------------- 面板文案（D:/WF/rel227/面板文案规范.md）
MAIN = " <icon id='wfx_main'>  "     # 同台座图集的主位标副本（与 any_element 同纹理，避免同行混纹理画花）
ANYI = "<icon id='any_element'>  任意属性共鸣时，"


def cas_texts(ctx, burst, CHG):
    code = ctx.spec.code
    t = {
        CHG: "强化『潮汐守誓』：Fever模式中发动时，护盾、攻击力提升与全属性耐性提升效果增强，消除的强化效果增加",
        PF_TXT: "自身的强化弹射变为角色专属形态：强化弹射Lv3使水属性角色直接攻击次数与合计伤害提升（持续60秒）；"
                "水属性共鸣时强化弹射持续时间延长、同时发动合击角色的强化弹射类型，Fever模式中伤害倍率翻倍",
        # v35 补丁读的数据键（老客户端只取低 3 位：3 = 合击主位限定能力 + 合击队长技）
        f"wfx_unlock_{ctx.spec.cid}": "27",            # 3 | 8 只限自己的合击 | 16 要求全队同属性 6 人（v35f）
        f"wfx_pf4_{ctx.spec.cid}": "100:FF4040",       # 合击赛瑞斯 PF4 门槛/颜色，与赛瑞斯当队长时一致
        f"wfx_adaptive_{ctx.spec.cid}3": "1",          # 能力 3：战斗中自身属性视为与队长相同
        f"wfx_overlimit_full_{ctx.spec.cid}": "1",     # v35h：0 突破起全程超限材料/台子，120+玛纳满=最高台（作者 10-19）
        f"desc_override_{code}": "\n".join([
            "水属性共鸣时，自身可以发动合击角色的全部能力、队长技与强化弹射类型（自身的强化弹射同时发动合击角色的类型）",
            "水属性共鸣时，水属性角色攻击力+300%、强化弹射伤害+400%",
            "自身的强化弹射变为角色专属形态：强化弹射Lv3使水属性角色直接攻击次数与合计伤害提升（持续60秒），"
            "水属性共鸣时强化弹射持续时间延长",
            "水属性共鸣时，Fever模式中，自身专属强化弹射（含同时发动的类型）的伤害倍率翻倍",
            "水属性共鸣时，进入Fever模式时，立即发动强化弹射Lv3（同时发动全部类型，伤害倍率翻倍）",
        ]),
        f"desc_override_{code}_1": "\n".join([
            ANYI + "战斗开始时，队伍全体技能槽+50%、自身技能槽再+50%",
            ANYI + "队伍全体技能槽最大值+25%",
        ]),
        f"desc_override_{code}_2": ANYI + "队伍全体攻击力+200%、所受的回复量+20%",
        f"desc_override_{code}_3": "\n".join(MAIN + x for x in (
            "战斗中，自身视为与队长相同属性的角色",
            ANYI + "队伍成员受到治疗时（不论治疗来源），每回复5%生命值，对全体敌人造成自身攻击力10倍的伤害（溢出的回复量每5%为15倍；"
                   "单次不足5%的部分不计；伤害类型与队长的队伍特性一致；造成伤害后5秒内不再触发）",
            ANYI + "队伍成员受到治疗时（不论治疗来源），每回复5%生命值，Fever槽+5%（溢出的回复量每5%为+10%；单次不足5%的部分不计）",
            ANYI + "Fever模式中，队伍全体攻击力+200%、强化弹射伤害+400%",
            ANYI + "Fever模式中，弹射后自身连击数至少保留30（可与其他角色的同类效果叠加）",
        )),
        f"desc_override_{code}_4": ANYI + "队伍全体技能充能速度+20%",
        f"desc_override_{code}_5": "\n".join([
            ANYI + "队伍全体所受的回复量+10%",
            ANYI + "队伍全体技能槽最大值+10%",
        ]),
        f"desc_override_{code}_6": MAIN + ANYI + "强化『潮汐守誓』：Fever模式中发动时，护盾、攻击力提升与全属性耐性提升效果增强，"
                                               "消除的强化效果增加",
    }
    for fam, zh, key, prog in burst:
        t[key] = f"发动{zh}强化弹射Lv3（以强化弹射伤害计算）"
    skill_like = {CHG, f"desc_override_{code}_6"}
    for k, v in t.items():
        if k.startswith("wfx_"):
            continue
        for line in v.split("\n"):
            KL.check_panel(line.replace(MAIN, "").replace(ANYI, ""), skill_flag=(k in skill_like), label=k)
    return t


def seris_text(ctx):
    """赛瑞斯队长技面板第 4 句跟着 489 → Fever 中保底改写。"""
    key = "desc_override_seris_dragon_king_leader"
    raw = ctx.live_flat(KL.CAS)[key]
    cell = next(csv.reader(io.StringIO(raw)))[0]
    old = "水属性共鸣时，进入Fever模式时，自身获得「连击加成」，弹射后连击数至少保留40"
    assert old in cell, cell[:200]
    return {key: cell.replace(old, "水属性共鸣时，Fever模式中，弹射后自身连击数至少保留40")}


def build(ctx):
    cid = ctx.spec.cid_s
    res = {"skill_fx": build_skill(ctx)}
    new_unique(ctx, HEAL_DMG_UID, WFX_HEAL_DMG, "潮汐守誓·治疗转伤害")
    new_unique(ctx, HEAL_FEVER_UID, WFX_HEAL_FEVER, "潮汐守誓·治疗充能Fever")
    new_unique(ctx, BARRIER_UID, WFX_BARRIER, "潮汐守誓·护盾")
    new_unique(ctx, HEAL_DMG_ANY_UID, WFX_HEAL_DMG_ANY, "潮汐守誓·全队治疗转伤害")
    new_unique(ctx, HEAL_FEVER_ANY_UID, WFX_HEAL_FEVER_ANY, "潮汐守誓·全队治疗充能Fever")
    for fam, _, zh in UNISON_TYPES:
        new_unique(ctx, UNISON_UID[fam], f"hidden_wg_aqua_unison_{fam}", f"潮汐守誓·合击{zh}")
    for ocid, zh, _ in UNISON_OWN:      # 别用 cid：下面 write_flat 用的是本角色 cid
        new_unique(ctx, OWN_UID[ocid], f"hidden_wg_aqua_unison_{ocid}", f"潮汐守誓·合击{zh}")
    res["own_tags"] = own_tags(ctx)
    res["pf_override"] = build_pf_override(ctx)
    burst = build_burst(ctx)
    lrows, lev = K.build_leader(ctx, build_leader(ctx, burst))
    ctx.write_flat(KL.LEADER, {cid: lrows})
    res["leader"] = [f"L{i} {e['describe']}" for i, e in enumerate(lev)]
    plan, CHG = build_abilities(ctx)
    arows, aev = K.build_abilities(ctx, plan)
    ctx.write_flat(KL.ABILITY, arows)
    res["abilities"] = [f"{e['key']} {e['describe']}" for e in aev]
    res["seris"] = seris_fever_combo(ctx)
    res["stance"] = stance_rows(ctx)
    cas = cas_texts(ctx, burst, CHG)
    cas.update(seris_text(ctx))
    ctx.write_flat(KL.CAS, {k: [[v]] for k, v in cas.items()})
    res["cas_keys"] = sorted(cas)
    ctx.report({"character": KEY, "skill": NAME_SKILL, "fx": res["skill_fx"], "leader": res["leader"],
                "abilities": res["abilities"], "pf_override": res["pf_override"], "cas": cas,
                "required_capabilities": ["panel-description-override-v2"],
                "notes": ["Seris 129999 leader r4 489→26/226 Fever-only (author 10-18)",
                          "wfx_unlock=27: v35e reads &7=3; v35f adds own-unison-only(8)+resonance(16)"]})
    return res
