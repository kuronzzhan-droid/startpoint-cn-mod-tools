# -*- coding: utf-8 -*-
"""深渊武器二期 9 把（意见征集「深渊武器专题」采用项 #2 #3 #4 #6 #7 #8 #9 #10 #12）。

照现有 15 把（8000101–8000115，kulo 1.4.149）的形态：
- equipment / item（魂珠行）/ equipment_status（同属性模板）/ ability_soul（本体 = 满值一半）/
  equipment_enhancement（120 级上限，70 级换图换名「·觉醒」）/ equipment_enhancement_status /
  equipment_enhancement_ability（强化 1→120 线性补另一半，表头 [槽,1,120,0,0]）/ equipment_enhancement_shop（类目 5，
  每把 6 阶 69/70/98/99/119/120，材料照同属性第一把）/ event_item_shop（深渊连战兑换 700099，深渊结晶 ×15，限 1）。
- 属性武器的每条词条都挂原生「同属性 6 人共鸣」前置（wf_abyss_weapon_resonance 同形：pre kind 2，阈值 6）。
- 非数值行（连击、Fever 点、技能槽、免疫、加速、629 全屏）只放本体，按满值写（wf_abyss_weapon_split 规则）。

词条行全部经 wf_cursed_weapons.build_row（按枚举表补全伴随列与哨兵）+ wf_client_legality 校验。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

import wf_cursed_weapons as W
from base149 import join

ID0 = 8000116
SHOP_PRODUCT0 = 9700121          # 9700116-9700118、9700199 已被扭蛋券/称号/觉醒核占用
ENH_SHOP_KEY0 = 8100091          # 现有 8100001-8100090（15 把 × 6 阶）
ENH_GROUP0 = 81016               # 现有 81001-81015
SHOP_ORDER0 = 19                 # 现有商品列表序 1-18
DSL_DIR = "battle/action/skill/action/ability_skill/abyss_weapon"
DESC = "【深渊武装·觉醒】深渊连战、五重决战与练习关发挥完整效果；其他官方模式仅在满120级后发挥当前数值的50%。"
#: 每属性的模板武器（equipment_status / 强化 6 阶材料 / 魂珠道具行）
ELEMENT_DONOR = {"fire": "8000101", "water": "8000103", "thunder": "8000105", "wind": "8000107",
                 "light": "8000110", "dark": "8000111"}
SHOP_TEMPLATE = "9700110"
EQUIP_TEMPLATE = "8000110"
ITEM_TEMPLATE = "8000110"
ENH_TEMPLATE = "8000110"
IMG = "item/equipment/mod/abyss"

T_SELF, T_LEADER, T_PARTY, T_MB = W.T_SELF, W.T_LEADER, W.T_PARTY, W.T_MULTIBALL


@dataclass
class Row:
    """content(lo, hi) → 内容元组。split=True：本体 hi/2 常量 + 强化 0→hi/2；False：只进本体（满值）。"""
    content: Callable[[float, float], tuple]
    total: float
    trig: tuple = (W.IT_INITIAL, {})
    pre: tuple = ()
    mode: str = "0"
    split: bool = True
    note: str = ""


@dataclass
class Spec:
    n: int                       # 提案表序号
    slug: str
    name: str
    element: str
    category: str
    author: str
    rows: list[Row]
    dsl: dict = field(default_factory=dict)
    cas: dict = field(default_factory=dict)
    deviations: list[str] = field(default_factory=list)


def stat(kind, target):
    return lambda lo, hi: W.stat(kind, target, lo, hi)


def cond(kind, target, seconds):
    return lambda lo, hi: W.condition(kind, target, (lo, hi), int(seconds * 60))


def during(kind, target):
    return lambda lo, hi: W.during(kind, target, lo, hi)


def const(content):
    return lambda lo, hi: content


def stacks(step: float, cap: float) -> str:
    return str(int(round(cap / step)))


def specs() -> list[Spec]:
    out: list[Spec] = []
    PF = lambda limit="(None)", cool="0": W.trig(W.IT_PF, threshold=W.times(1), trigger_limit=limit, cooltime=cool)

    # #2 白信鸽羽毛（光 PF，来点关注谢谢喵）——审查「采用」，数值照提案
    light = (W.res("light"),)
    out.append(Spec(2, "light_03", "深渊·白鸽羽毛", "light", "饰品", "来点关注谢谢喵", [
        Row(stat("32", T_LEADER), 200, pre=light, note="光共鸣：队长攻击力 +200%"),
        Row(stat("32", T_LEADER), 4, trig=PF(stacks(4, 120)), pre=light, note="光共鸣：强化弹射时队长攻击力 +4%（最多 +120%）"),
        Row(cond("28", None, 12), 200, trig=W.trig(W.IT_SKILL, trigger_puller=W.P_SELF), pre=light,
            note="光共鸣：自身发动技能时强化弹射伤害 +200%（12 秒）"),
        Row(cond("28", None, 15), 120, trig=W.trig("12", threshold=W.times(40), cooltime="900"), pre=light,
            note="光共鸣：连击达到 40 时强化弹射伤害 +120%（15 秒，CT15 秒）"),
    ]))

    # #3 珍珠奶茶（暗 协力球直击，脆脆鲨）——审查「加上 fever 限制采用」：攻击/直击 +300% 改为 Fever 期间
    dark = (W.res("dark"),)
    fever_d = (W.DT_FEVER, {})
    s = Spec(3, "dark_03", "深渊·珍珠奶茶", "dark", "饰品", "脆脆鲨", [
        Row(during("0", T_PARTY), 300, trig=fever_d, pre=dark, mode="1", note="暗共鸣：Fever 中全队攻击力 +300%"),
        Row(during("1", T_PARTY), 300, trig=fever_d, pre=dark, mode="1", note="暗共鸣：Fever 中全队直接攻击伤害 +300%"),
        Row(cond("0", T_MB, 15), 300, trig=W.trig(W.IT_FEVER, threshold=W.times(1)), pre=dark,
            note="暗共鸣：进入 Fever 时协力球攻击力 +300%（15 秒）"),
        Row(cond("214", T_MB, 15), 300, trig=W.trig(W.IT_FEVER, threshold=W.times(1)), pre=dark,
            note="暗共鸣：进入 Fever 时协力球直接攻击伤害 +300%（15 秒）"),
        Row(const(("226", {"strength": (W.times(10), W.times(10))})), 10, trig=W.trig("6", threshold=W.times(1)),
            pre=dark, split=False, note="暗共鸣：每次弹射连击 +10"),
        Row(during("3", T_PARTY), 2, trig=("208", {"threshold": W.times(1), "trigger_limit": "7"}), pre=dark, mode="1",
            note="暗共鸣：场上每有 1 个协力球，全队技能充能速度 +2%（最多 7 个 = +14%）"),
    ])
    s.deviations += ["「加上 fever 限制」：开局全队与协力球攻击/直击 +300% 改为 Fever 期间生效（全队走持续 Fever 触发；"
                     "协力球没有持续目标先例，改为进入 Fever 时 15 秒状态）",
                     "「每有一个协力球充能 +2%（最大 15%）」：持续触发 208 按个数倍乘，上限 7 个 = +14%（2% 的整数倍）"]
    out.append(s)

    # #4 血月（暗 能力，来点关注谢谢喵）——审查「采用」
    burst = f"{DSL_DIR}$bloodmoon_burst"
    hp1 = (W.res("dark"), ("9", {"trigger_puller": W.P_SELF, "threshold": W.pct(1)}))
    every2 = W.trig(W.IT_ELAPSED, threshold=W.frames(120), trigger_limit="20")
    s = Spec(4, "dark_04", "深渊·血月", "dark", "饰品", "来点关注谢谢喵", [
        Row(stat("32", T_SELF), 150, pre=dark, note="暗共鸣：自身攻击力 +150%"),
        Row(stat("388", T_PARTY), 150, pre=dark, note="暗共鸣：全队能力伤害 +150%"),
        Row(stat("32", T_SELF), 5, trig=every2, pre=hp1, note="暗共鸣：自身 HP 低于 1% 时每 2 秒自身攻击力 +5%（最多 +100%）"),
        Row(stat("388", T_PARTY), 15, trig=every2, pre=hp1, note="同上，全队能力伤害 +15%（最多 +300%）"),
        Row(const(W.invoke("abyss_bloodmoon_burst", burst)), 0,
            trig=W.trig("144", trigger_puller=W.P_SELF, threshold=W.times(10)), pre=dark, split=False,
            note="暗共鸣：自身每造成 10 次能力伤害，对全体敌人造成攻击力 5 倍的伤害（按能力伤害结算）"),
    ])
    s.dsl[burst] = W._full_screen_attack(5.0, buff_target_as=2)
    s.cas["abyss_bloodmoon_burst"] = "对全体敌人造成自身攻击力5倍的伤害（按能力伤害结算）"
    s.deviations += ["「5 倍暗属性伤害」：装备 DSL 主体恒为无属性，命中只能无属性（不吃克制）；归属写能力伤害（buffTargetAs 2）",
                     "「HP 低于 1% 时每 2 秒」：经过时间 2 秒触发 + 前置自身 HP≤1%，两项各最多叠 20 次（永久，不随回血清除）"]
    out.append(s)

    # #6 大葱话筒（雷 能力，脆脆鲨）——审查「数值降低到 4/5 后去掉免疫沉默采用」
    th = (W.res("thunder"),)
    s = Spec(6, "thunder_03", "深渊·大葱话筒", "thunder", "杖", "脆脆鲨", [
        Row(stat("388", T_PARTY), 160, pre=th, note="雷共鸣：全队能力伤害 +160%（提案 200% ×0.8）"),
        Row(stat("32", T_PARTY), 16, trig=PF(stacks(16, 240)), pre=th, note="雷共鸣：强化弹射时全队攻击力 +16%（最多 +240%）"),
        Row(stat("388", T_PARTY), 16, trig=PF(stacks(16, 240)), pre=th, note="雷共鸣：强化弹射时全队能力伤害 +16%（最多 +240%）"),
    ])
    s.deviations.append("按审查：数值 ×0.8（200→160、20→16/次、上限 300→240），去掉「自身免疫沉默」")
    out.append(s)

    # #7 胡萝卜剑（风 兔子技伤，来点关注谢谢喵）——审查「数值降低到 4/5 采用」
    wind = (W.res("wind"),)
    out.append(Spec(7, "wind_03", "深渊·胡萝卜剑", "wind", "剑", "来点关注谢谢喵", [
        Row(const(("226", {"strength": (W.times(8), W.times(8))})), 8, trig=PF(), pre=wind, split=False,
            note="风共鸣：强化弹射时连击 +8（提案 10 ×0.8）"),
        Row(stat("32", T_PARTY), 120, pre=wind, note="风共鸣：全队攻击力 +120%"),
        Row(stat("34", T_PARTY), 120, pre=wind, note="风共鸣：全队技能伤害 +120%"),
        Row(stat("32", T_PARTY), 8, trig=PF(stacks(8, 160)), pre=wind, note="风共鸣：强化弹射时全队攻击力 +8%（最多 +160%）"),
        Row(stat("34", T_PARTY), 8, trig=PF(stacks(8, 160)), pre=wind, note="风共鸣：强化弹射时全队技能伤害 +8%（最多 +160%）"),
    ]))

    # #8 冲浪板（风 能力，lpg认证xpg）——提案已按审查削弱
    combo35 = W.trig("12", threshold=W.times(35))
    green_ability = W.trig("144", trigger_puller=W.P_ONE_OF_PARTY, threshold=W.times(1), trigger_limit="10",
                           **{"trigger_puller.character_groups": "Green"})
    s = Spec(8, "wind_04", "深渊·冲浪板", "wind", "盾", "lpg认证xpg", [
        Row(stat("32", T_PARTY), 200, pre=wind, note="风共鸣：全队攻击力 +200%"),
        Row(const(("213", {"strength": ("8000000", "8000000")})), 80, trig=combo35, pre=(*wind, ("186", {})), split=False,
            note="风共鸣：不处于 Fever 时每达成 35 连击，Fever 槽 +80 点（槽上限 400 的 20%）"),
        Row(const(("211", {"target": T_SELF, "target.character_groups": "(None)", "strength": (W.pct(5), W.pct(5))})), 5,
            trig=combo35, pre=(*wind, ("12", {})), split=False, note="风共鸣：Fever 中每达成 35 连击，自身技能槽 +5%"),
        Row(stat("388", T_PARTY), 40, trig=green_ability, pre=wind,
            note="风共鸣：风属性角色每次造成能力伤害时全队能力伤害 +40%（最多 +400%）"),
    ])
    s.deviations.append("「Fever 槽 +20%」：按比例加槽的 724 只认角色能力表（装备表写 = C7050），改为加 80 点（基础槽 400 的 20%）")
    out.append(s)

    # #9 沙滩排球（火 fever，pppp）——审查「降低后采用：降低 fever 获取，去掉免疫」
    fire = (W.res("fire"),)
    s = Spec(9, "fire_03", "深渊·沙滩排球", "fire", "饰品", "pppp", [
        Row(stat("32", T_SELF), 230, pre=fire, note="火共鸣：自身攻击力 +230%"),
        Row(stat("388", T_SELF), 27, trig=W.trig("144", trigger_puller=W.P_SELF, threshold=W.times(1), trigger_limit="10"),
            pre=(*fire, ("12", {})), note="火共鸣：Fever 中自身造成能力伤害时自身能力伤害 +27%（最多 +270%）"),
        Row(const(("213", {"strength": ("12000000", "12000000")})), 120,
            trig=W.trig(W.IT_SKILL, trigger_puller=W.P_ONE_OF_PARTY), pre=fire, split=False,
            note="火共鸣：队伍中角色发动技能时 Fever 槽 +120 点"),
    ])
    s.deviations += ["按审查去掉开局全队水/火属性抗性（免疫）",
                     "「其他角色发动技能时 fever+290」：审查要求降低 Fever 获取，取 +120 点（与深渊·雷鸣双刃同档；290 点 ≈ 槽上限 73%）；"
                     "来源只能写「队伍之一」（含自身，引擎没有「除自身外」的施技来源）",
                     "「每次 +25%（最多 270%）」改为每次 +27%、最多 10 次 = 270%"]
    out.append(s)

    # #10 机车头盔（火 PF，pppp）——审查「采用」：强化弹射伤害只有队长能获得
    pf3 = W.trig(W.IT_PF, threshold=W.times(3), cooltime="300")
    s = Spec(10, "fire_04", "深渊·机车头盔", "fire", "盾", "pppp", [
        Row(const(("59", {"target": T_SELF, "target.character_groups": "(None)"})), 0, split=False,
            note="自身攻击力降低无效"),
        Row(stat("55", None), 290, pre=fire, note="火共鸣：强化弹射伤害 +290%（只作用于队长的强化弹射）"),
        Row(stat("55", None), 8.25, trig=PF(stacks(8.25, 330)), pre=fire,
            note="火共鸣：每次强化弹射，强化弹射伤害 +8.25%（最多 +330%）"),
        Row(const(W.condition("228", None, 10, 60)), 0, trig=pf3, pre=fire, split=False,
            note="火共鸣：每打出 3 次强化弹射，全队加速 1 秒（CT5 秒）"),
    ])
    s.deviations += ["「开局时全队获得抗性降低」语义不明（像是自带减益），未实现",
                     "强化弹射伤害 55 在引擎里只作用于持有者自身的强化弹射 ⇒ 只有队长装备时有效（=「仅队长」）",
                     "「每次 +8%（最多 330%）」改为 +8.25% × 40 次 = 330%；加速强度取官方魂珠 5090005 档 10%"]
    out.append(s)

    # #12 船夹板（水 PF，脆脆鲨）——未审，按同期 PF 武器削：600→300、500→120、+10→+5
    water = (W.res("water"),)
    s = Spec(12, "water_03", "深渊·船夹板", "water", "盾", "脆脆鲨", [
        Row(cond("28", None, 20), 300, trig=W.trig(W.IT_FEVER, threshold=W.times(1)), pre=water,
            note="水共鸣：进入 Fever 时强化弹射伤害 +300%（20 秒）"),
        Row(const(("213", {"strength": ("12000000", "12000000")})), 120, trig=W.trig("184", threshold=W.times(1)),
            pre=water, split=False, note="水共鸣：Fever 结束时 Fever 槽 +120 点"),
        Row(const(("226", {"strength": (W.times(5), W.times(5))})), 5, trig=W.trig("6", threshold=W.times(1)), pre=water,
            split=False, note="水共鸣：每次弹射连击 +5"),
    ])
    s.deviations.append("未经审查，按同期 PF 武器削弱：Fever 强化弹射伤害 600%→300%（与机车头盔 290% 同档），"
                        "退出 Fever 加槽 500→120 点（500 点超过槽上限 400，会无限 Fever），弹射连击 +10→+5（冻海战锚 +6 档）")
    out.append(s)
    for i, s in enumerate(out):
        s.id = str(ID0 + i)
    return out


def _abyss_ea_header(row: list[str]) -> list[str]:
    row[3], row[4] = "0", "0"
    return row


def rows_for(s: Spec) -> tuple[list[list[str]], list[list[str]]]:
    soul, ea = [], []
    for r in s.rows:
        if r.split:
            half = r.total / 2
            soul_eff = W.Eff(r.mode, r.content(half, half), trig=r.trig, pre=r.pre, note=r.note)
            ea_eff = W.Eff(r.mode, r.content(0, half), trig=r.trig, pre=r.pre, learn=1, maxlvl=120, note=r.note)
            soul.append(W.build_row(W.SOUL_T, len(soul), soul_eff))
            ea.append(_abyss_ea_header(W.build_row(W.EA_T, len(ea), ea_eff)))
        else:
            soul.append(W.build_row(W.SOUL_T, len(soul), W.Eff(r.mode, r.content(r.total, r.total), trig=r.trig,
                                                                pre=r.pre, note=r.note)))
    return soul, ea


def build(flat, nested, server) -> dict:
    """flat(lp)->{key:[[cells]]}；nested(lp)->dict；server(name)->JSON。返回新增内容（全部新键）。"""
    out = {"flat": {}, "nested": {}, "dsl": {}, "server": {}, "specs": specs(), "problems": []}
    F = out["flat"]
    for lp in (W.EQUIPMENT, W.ITEM, W.SOUL, W.ENH, W.EA, W.ENH_SHOP, W.CAS, "master/shop/event_item_shop.orderedmap"):
        F[lp] = {}
    for lp in (W.EQUIPMENT_STATUS, W.ENH_STATUS):
        out["nested"][lp] = {}
    eq_t = flat(W.EQUIPMENT)[EQUIP_TEMPLATE][0]
    item_t = flat(W.ITEM)[ITEM_TEMPLATE][0]
    enh_t = flat(W.ENH)[ENH_TEMPLATE][0]
    shop_t = flat("master/shop/event_item_shop.orderedmap")[SHOP_TEMPLATE][0]
    enh_shop = flat(W.ENH_SHOP)
    srv_enh = server("equipment_enhancement_shop.json")
    srv_event = server("event_item_shop.json")["11"]["700099"]
    elem_code = W.ELEMENT_CODE
    lookup = {}
    for i, s in enumerate(out["specs"]):
        wid = s.id
        # equipment
        r = list(eq_t)
        assert r[2] == "0" and r[8] == "5" and r[10] == EQUIP_TEMPLATE and r[11] == "5", r
        r[0], r[1], r[6], r[7], r[10] = f"mod_abyss_{wid}", s.name, f"{IMG}/{s.slug}", DESC, wid
        F[W.EQUIPMENT][wid] = [r]
        # item（魂珠道具行）
        r = list(item_t)
        assert r[1] == ITEM_TEMPLATE and r[12] == "4", r
        r[0], r[1], r[2], r[3], r[12] = f"mod_abyss_{wid}", wid, f"{s.name}魂珠", f"{IMG}/soul/{s.slug}", str(elem_code[s.element])
        F[W.ITEM][wid] = [r]
        out["nested"][W.EQUIPMENT_STATUS][wid] = copy.deepcopy(nested(W.EQUIPMENT_STATUS)[ELEMENT_DONOR[s.element]])
        soul, ea = rows_for(s)
        F[W.SOUL][wid], F[W.EA][wid] = soul, ea
        r = list(enh_t)
        r[2], r[4] = f"{s.name}·觉醒", f"{IMG}/{s.slug}_lv120"
        assert r[0] == "120" and r[6] == DESC, r
        F[W.ENH][wid] = [r]
        out["nested"][W.ENH_STATUS][wid] = copy.deepcopy(nested(W.ENH_STATUS)[ENH_TEMPLATE])
        # 强化商店：同属性模板武器的 6 阶
        donor = ELEMENT_DONOR[s.element]
        tpl = sorted(((k, v[0]) for k, v in enh_shop.items() if v and v[0][29] == donor), key=lambda kv: int(kv[1][3]))
        assert [int(v[30]) for _k, v in tpl] == [69, 70, 98, 99, 119, 120], (donor, tpl)
        group = str(ENH_GROUP0 + i)
        for stage, (tk, tv) in enumerate(tpl):
            key = str(ENH_SHOP_KEY0 + i * 6 + stage)
            r = list(tv)
            r[2], r[29] = group, wid
            F[W.ENH_SHOP][key] = [r]
            e = copy.deepcopy(srv_enh[tk])
            assert e["equipmentId"] == int(donor)
            e["equipmentId"], e["groupId"] = int(wid), int(group)
            out["server"].setdefault("equipment_enhancement_shop.json", {})[key] = e
        # 深渊连战兑换
        pid = str(SHOP_PRODUCT0 + i)
        r = list(shop_t)
        assert r[8] == SHOP_TEMPLATE and r[33] == "8000110", r
        r[7], r[8], r[10], r[13], r[33] = s.name, pid, str(SHOP_ORDER0 + i), f"{IMG}/{s.slug}", wid
        F["master/shop/event_item_shop.orderedmap"][pid] = [r]
        e = copy.deepcopy(srv_event[SHOP_TEMPLATE])
        e["rewards"] = [{"type": 4, "id": int(wid), "count": 1}]
        out["server"].setdefault("event_item_shop.json", {})[pid] = e
        out["server"].setdefault("event_item_shop_id_map.json", {})[pid] = {"eventType": 11, "eventId": 700099}
        out["dsl"].update(s.dsl)
        for sid, text in s.cas.items():
            assert "," not in text and "\n" not in text
            F[W.CAS][sid] = [[text]]
        lookup[wid] = {"name": s.name, "rarity": "5", "category": s.category}
    ids = [int(s.id) for s in out["specs"]]
    sv = out["server"]
    sv["equipment_ids.json"] = ids
    sv["item_ids.json"] = ids
    sv["equipment_lookup.json"] = lookup
    sv["equipment_max_level.json"] = {s.id: 5 for s in out["specs"]}
    sv["equipment_element.json"] = {s.id: elem_code[s.element] for s in out["specs"]}
    sv["item_sale.json"] = {s.id: {"category": 5, "sale_price": 500, "sellable": True} for s in out["specs"]}
    sv["equipment_awakening_material.json"] = {"rarityOverrides": {s.id: 5 for s in out["specs"]}}
    # 合法性
    for s in out["specs"]:
        for table, logical in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA)):
            for idx, r in enumerate(F[logical][s.id]):
                out["problems"] += [f"{s.id} {table}#{idx}: {p}" for p in W.L.client_legality_problems(table, r)]
    for prog, tree in out["dsl"].items():
        for check in (W.dsl_signature_problems, W.colorless_hit_effect_problems):
            out["problems"] += [f"DSL {prog}: {p}" for p in check(tree)]
    return out
