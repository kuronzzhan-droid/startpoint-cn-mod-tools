#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""wf_rogue_rewards.py — 深渊连战奖励体系:深渊代币 + 15 把专属武装。

代币:克隆官方「激战代币」(item 2370007,23列)→ **2370099「深渊代币」**
  (图标暂复用激战代币;通关每轮由 rogue_event.json 掉落,后续接兑换商店)。
专属武装:每属性 2 把 + 通用 3 把 = 15 键(8000101-8000115),装备元数据
  从既有供体行构建,词条只取经过验证的官方模板首行。
同步:assets/equipment_max_level.json / equipment_element.json / equipment_lookup.json /
  equipment_ids.json / item_ids.json(后两个=邮件校验,静态 import 须重启服务端)。

用法(项目根,默认 dry-run):
  python mod-tools/wf_rogue_rewards.py --write --publish
"""
import argparse
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

from PIL import Image, UnidentifiedImageError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mod-tools"))
import wf_quest_lib as q          # noqa: E402
import wf_mod_tool as core        # noqa: E402
import wf_describe                # noqa: E402
import wf_assets                  # noqa: E402
import wf_rogue_build as rogue_build  # noqa: E402

ITEM_T = "master/item/item.orderedmap"
EQUIP_T = "master/item/equipment.orderedmap"
EQUIP_STATUS_T = "master/item/equipment_status.orderedmap"
SOUL_T = "master/ability/ability_soul.orderedmap"
RUSH_EVENT_T = "master/quest/event/rush_event.orderedmap"

TOKEN_ID = "2370099"
TOKEN_TEMPLATE = "2370007"     # 激战代币
EVENT_ID = "700099"
TOKEN_DESCRIPTION = "在「深渊连战」中获得的深渊结晶。凝聚着历战boss的力量,可用于锻造深渊武装。"

MODE_DESCRIPTION = "【深渊连战专属】仅在深渊连战、宝物域连战 2001 与练习关生效,其余关卡与官方一致。"
IMAGE_PREFIX = "item/equipment/mod/abyss"
ABILITY_SOUL_ALL_ELEMENTS = "0,3,2,1,4,5"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SOURCE_ASSET_SIZE = (20, 20)
SOURCE_ASSET_DIR = Path(ROOT) / "mod-tools" / "assets" / "abyss-equipment"
DEFAULT_UPLIFT_MULTIPLIER = (3, 2)


# ability_soul 行宽与关键列(基址 = ability 基址 −3)
SOUL_ROW_WIDTH = 123
SOUL_PRE1_KIND_COL = 3
SOUL_TRIGGER_KIND_COL = 24
# 规则 A/B(官方实测):kind 清成 0 时这些伴随列必须一并清空,否则会静默继承捐赠行的
# 元素锁/阈值/限次 —— 2026-07-30 设计初稿 45 条里 6 条"永久不生效"的死词条就是这么来的。
# 依据:官方 Initial(c24=0)行 338/338 的 c25/c26/c27/c28/c31/c32/c33 全为空。
SOUL_TRIGGER_COMPANION_COLS = (25, 26, 27, 28, 31, 32, 33)
SOUL_PRE1_COMPANION_COLS = (6, 7, 8, 9)
SOUL_PULLER_COL = 25

# c25 trigger_puller 按触发 kind 分两族(官方 ability_soul 全表实证,2026-07-30)。
# 「谁触发的」类触发**必须**带 puller —— 写空串 = 客户端 AbilitySoulValues.parseAt25
# 抛 C7050「不存在的构造函数」(真机实锤:编成页 PartyLogic.getBattlePower 一进就崩)。
# 「事件计数」类触发的 c25 官方恒空,写值反而不合官方形态。
TRIGGER_NEEDS_PULLER = frozenset({
    "18", "19", "20", "21", "23", "25", "107", "137", "141", "144", "197", "261",
})
TRIGGER_NO_PULLER = frozenset({
    "2", "4", "6", "8", "9", "10", "12", "53", "57", "58", "60", "61", "65", "66",
    "70", "77", "257", "260",
})
PULLER_DEFAULT = "0"          # Myself,needs-puller 族里官方最常用的值
SOUL_PULLER_GROUP_COL = 26
# puller ∈ {5,6,7}(OneOfParty / TotalOfExceptMyself / TotalOfParty)时 c26 必须带组 token:
# 官方 puller=7 的 60 行 c26 无一为空(元素 token 或 `(None)`)。写空串 → 游戏内渲染成
# 「null角色发动技能时」(2026-07-30 真机实锤)。puller=0(Myself)的 c26 官方恒空(97/97)。
PULLER_NEEDS_GROUP = frozenset({"5", "6", "7"})
PULLER_GROUP_DEFAULT = "(None)"   # 不限元素;官方 puller=7 有 1 例、puller=5 有 4 例

# target_groups 哨兵:写武器自身的元素组(旧行为)。写 "(None)" 则不限元素,写 None 则沿用捐赠行。
WEAPON_GROUP = "\x00use-weapon-group"


@dataclass(frozen=True)
class EffectSpec:
    """一条魂珠词条。

    前三项保留原始三位置构造语法；但任何模板行/输出 kind 组合在构建前都必须登记到
    ``EFFECT_STRENGTH_RULES``，未审计的旧声明会失败关闭，不会自动猜测强度位。

    donor_line     捐赠键内的行序(旧行为恒取第 0 行)。越界即抛异常,不静默回退。
    strength=None  不写强度列,**沿用捐赠行原值** —— 注意捐赠行可能自带无关数值
                   (如 4020007#1 的 c48=-10000),对"官方恒空"的 kind 要用 strength=""
                   显式写空,别指望 None 能清掉它。
    strength=""    把 c48/c49 写成空串 —— kind 26/59/68/69/70/220 等客户端解析器压根不读
                   该列,官方也恒空,应显式留空以贴合官方形态。
    target=None    c45 沿用捐赠行 —— kind 55/226/213/190/56 等是惰性列,官方恒空。
    target_groups  WEAPON_GROUP=写武器元素组;None=沿用捐赠行;其余字面写入(常用 "(None)")。
    overrides      (列号, 字面值) 对,最后覆盖、优先级最高;"" 表示写空串。
                   有条件/有触发的词条靠它落地(c3/c6-c9 前置、c24-c33 触发、c54/c55 帧对…)。
    """

    template_id: str
    effect_kind: str
    strength: int | str | None
    donor_line: int = 0
    target: str | None = "5"
    target_groups: str | None = WEAPON_GROUP
    overrides: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class WeaponSpec:
    id: str
    name: str
    donor: str
    element: int
    group: str
    image_slug: str
    effects: tuple[EffectSpec, ...]
    status_multiplier: tuple[int, int] = DEFAULT_UPLIFT_MULTIPLIER


@dataclass(frozen=True)
class MasterTables:
    items: dict[str, object]
    equipment: dict[str, object]
    equipment_status: dict[str, object]
    ability_soul: dict[str, object]
    rush_event: dict[str, object]


@dataclass(frozen=True)
class MasterChanges:
    items: dict[str, object]
    equipment: dict[str, object]
    equipment_status: dict[str, object]
    ability_soul: dict[str, object]
    rush_event: dict[str, object]


@dataclass(frozen=True)
class ServerMirrors:
    equipment_max_level: dict[str, object]
    equipment_element: dict[str, object]
    equipment_lookup: dict[str, object]
    equipment_ids: list[int]
    item_ids: list[int]


# 词条覆写小工具(v3.3,2026-07-30):把捐赠行的门控列显式钉死。
# 构建器的规则 A/B 会在 kind 被设为 0 时自动清伴随列,所以这里只写"要什么"。
_INIT = ((3, "0"), (24, "0"))          # 无条件开幕


def _trig(kind, *, puller=None, groups=None, th="100000", limit="(None)", cool="0"):
    """指定 instant_trigger,并清掉捐赠行自带的元素锁(puller 组 / it 组)。

    puller 不给时按触发 kind 自动取值:needs-puller 族填 `0`(Myself),其余留空。
    别手动写空串给 needs-puller 族 —— 那是 C7050 的直接成因。
    """
    k = str(kind)
    if puller is None:
        puller_v = PULLER_DEFAULT if k in TRIGGER_NEEDS_PULLER else ""
    else:
        puller_v = str(puller)
    if groups is not None:
        grp = groups
    else:
        grp = PULLER_GROUP_DEFAULT if puller_v in PULLER_NEEDS_GROUP else ""
    return ((3, "0"), (24, k), (25, puller_v),
            (26, grp), (27, th), (28, th), (31, limit), (32, cool), (33, ""))


# 深渊武器词条 v3.3(2026-07-30 用户逐把拍板)。设计与校验产物见
# mod-tools/work/abyss-v3/{v33_spec.py,v33_check_result.txt}、
# docs/回调与深渊武器重设计-方案-20260730.md §6.7。
#
# 硬约束(改这张表前必读):
#   · 叠装上限 3 把(每角色一把,最多 3 把武器),所有数值按 ×3 折算;
#   · 数值普遍取官方 ability_soul 同 kind 上限的 ×1~×3;
#   · 35 充能速度游戏内上限 50%;211 技能槽满槽即截顶(开幕式多源会互相浪费);
#     245 = 「自身的技能槽最大值」(不是"2号位技能槽",wf_describe 误报);
#   · 55/28 强化弹射伤害架构上**只作用于自身**,文案不能写"全队";
#   · 70 = 「免疫疲惫效果」(不是"冻结无效",wf_describe 误报);
#   · 禁用:723(进 soul 必崩)、43(定值 20 等于 0)、212/701-711(零先例)。
WEAPONS: tuple[WeaponSpec, ...] = (
    # ---- 火 --------------------------------------------------------------
    # 用户未给 101 的修订,数值按同档推定(+200%)
    WeaponSpec("8000101", "深渊·灰烬巨剑", "5010060", 0, "Red", "fire_01", (
        EffectSpec("3020011", "51", 150000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "202", 50000, donor_line=4, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5020041", "33", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # 用户:技能槽+100%、火队要风抗性、贯通时间延长这种词条
    WeaponSpec("8000102", "深渊·熔核法杖", "5020042", 0, "Red", "fire_02", (
        EffectSpec("3050010", "211", 100000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5050037", "40", 15000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("4030004", "190", 20000, donor_line=0, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5100004", "157", 30000, donor_line=1, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # ---- 水 --------------------------------------------------------------
    # 用户:FEVER获得量+150%;直击/攻击力/强弹 各 +200%
    WeaponSpec("8000103", "深渊·深潮长枪", "5010075", 1, "Blue", "water_01", (
        # 50 官方 target 只用过 0/2,写 5 是零先例格子 → 用 0(6 把各自生效等价全队)
        EffectSpec("5090059", "50", 150000, donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("5040033", "56", 20000, donor_line=4, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5020041", "33", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5050009", "55", 200000, donor_line=0, target=None,
                   target_groups=None, overrides=_INIT),
    )),
    # 用户:+弹射时连击+6;技能伤害+400%;全属性抗性+20%
    WeaponSpec("8000104", "深渊·冻海战锚", "5020031", 1, "Blue", "water_02", (
        EffectSpec("5050020", "227", 20000, donor_line=1, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("4030019", "70", "", donor_line=2, target="0",
                   target_groups=None, overrides=_INIT),
        # ⚠ (226, it=6 BallFlip) 官方零组合先例(226 用 it=4/23/20/260/2)
        EffectSpec("300001", "226", 600000, donor_line=8, target=None,
                   target_groups=None, overrides=_trig(6)),
        EffectSpec("5080029", "205", 25000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5020024", "34", 400000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("3080008", "36", 20000, donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
    )),
    # ---- 雷 --------------------------------------------------------------
    # 用户:FEVER点 +120;直击/攻击力 各 +300%
    WeaponSpec("8000105", "深渊·雷鸣双刃", "5010077", 2, "Yellow", "thunder_01", (
        EffectSpec("5090054", "213", 12000000, donor_line=0, target=None,
                   target_groups=None,
                   overrides=_trig(23, puller=7, groups="Yellow") + ((10, "0"),)),
        EffectSpec("5030021", "26", "", donor_line=1, target=None,
                   target_groups=None,
                   overrides=_INIT + ((54, "120000000"), (55, "120000000"))),
        EffectSpec("5090027", "33", 300000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 300000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # 用户:贯通时长+25%、水抗+15%、充能速度+15%、攻击力+250%
    WeaponSpec("8000106", "深渊·轰电战锤", "5020038", 2, "Yellow", "thunder_02", (
        EffectSpec("4030004", "190", 25000, donor_line=0, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5070040", "38", 15000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("3010035", "35", 15000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 250000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # ---- 风 --------------------------------------------------------------
    # 用户:每25连击、无上限;强弹/攻击力 各 +200%
    WeaponSpec("8000107", "深渊·裂空战镰", "5010068", 3, "Green", "wind_01", (
        EffectSpec("300001", "226", 600000, donor_line=8, target=None,
                   target_groups=None, overrides=_trig(4)),
        EffectSpec("5040009", "211", 5000, donor_line=1, target="0",
                   target_groups=None,
                   overrides=_trig(12, th="2500000", limit="(None)")),
        EffectSpec("5070017", "200", 200000, donor_line=1, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5050009", "55", 200000, donor_line=0, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # 用户:追加10连击;直击/攻击力 各 +200%
    WeaponSpec("8000108", "深渊·苍岚长弓", "5020026", 3, "Green", "wind_02", (
        EffectSpec("4040021", "226", 1000000, donor_line=1, target=None,
                   target_groups=None,
                   overrides=_trig(23, puller=7, groups="Green")),
        EffectSpec("4040007", "191", 20000, donor_line=0, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5090027", "33", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # ---- 光 --------------------------------------------------------------
    # 用户 2026-07-30 重做:原词条「太垃圾且不符合设计意图」。
    # 改为 能力伤害 + 攻击力 + fever 类,≥4 条;自伤那条「有点意思」保留并抬到 45%。
    # ⚠ 209 在 target=0 时是**对自身造成最大生命值 X% 的伤害**(真机文案「受到最大生命值 5% 的伤害」),
    #   是代价型机制,不是对敌造伤 —— 之前判断错过一次。
    WeaponSpec("8000109", "深渊·晨星圣剑", "5017716", 4, "White", "light_01", (
        EffectSpec("3010027", "209", 45000, donor_line=1, target="0",
                   target_groups=None, overrides=_INIT + ((46, ""),)),
        EffectSpec("5090029", "388", 250000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 250000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        # 自身发动技能时 Fever+40(puller=0 → 文案「自身发动技能时」,不会出 null)
        EffectSpec("5090054", "213", 4000000, donor_line=0, target=None,
                   target_groups=None, overrides=_trig(23, puller=0) + ((10, "0"),)),
        EffectSpec("4060023", "220", "", donor_line=2, target="0",
                   target_groups=None, overrides=_INIT),
    )),
    # 用户:复活所需击破 −15;技能槽+50%;攻击力+200%
    WeaponSpec("8000110", "深渊·辉环法器", "5020039", 4, "White", "light_02", (
        # 203 是绝对次数:1500000 = −15 次(官方 soul 上限 500000 = −5)
        EffectSpec("5050017", "203", 1500000, donor_line=2, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("4080015", "206", 25000, donor_line=1, target="0",
                   target_groups=None, overrides=_trig(25, th="80000", limit="2")),
        # v3.3:211 开幕式与 102@100% 撞截顶(合计 150%,溢出 50%)→ 换 245。
        # ★ 245 的游戏内文案是「自身的技能槽最大值」(用户截图印证;wf_describe 渲染成
        #   「2号位技能槽」是误报,见 memory wf-ability-damage-families #15)。官方 target 恒 0。
        EffectSpec("5040019", "245", 50000, donor_line=2, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # ---- 暗 --------------------------------------------------------------
    # 用户:光抗;技能后强弹+300%/12秒;直击+300%
    WeaponSpec("8000111", "深渊·蚀月大剑", "5010078", 5, "Black", "dark_01", (
        EffectSpec("4080016", "67", "", donor_line=2, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("5080038", "41", 15000, donor_line=1, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5090024", "28", 300000, donor_line=2, target=None,
                   target_groups=None,
                   overrides=_trig(23) + ((54, "72000000"), (55, "72000000"))),
        EffectSpec("5090027", "33", 300000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # 用户:技能后「技能伤害」+200%/10秒(原为直击);攻击力+200%
    WeaponSpec("8000112", "深渊·冥灯魔杖", "5020040", 5, "Black", "dark_02", (
        EffectSpec("3020003", "59", "", donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("3020003", "60", "", donor_line=1, target="0",
                   target_groups=None, overrides=_INIT),
        # 捐赠行 5010047#0 自带 frames 60000000/60000000(=10秒)两端同值,无需改
        EffectSpec("5010047", "1", 200000, donor_line=0, target="0",
                   target_groups=None,
                   overrides=_trig(23) + ((54, "60000000"), (55, "60000000"))),
        # 用户 2026-07-30 新增:发动技能时,自身生命值>20% 则对自身造成最大生命值 10% 伤害。
        # ⚠ 新组合:官方 209 的 it.kind 恒为 0(7/7 开幕)、pre1 从未用过 8 HpHigh → 黄灯,需真机。
        # 捐赠行 5050022#1 本身就是「pre1=HpHigh(自身) HP≥50% + 技能发动」的完整形状,
        # 只改阈值/内容/限次 —— **前置块绝不能手搓**:pre1.kind 非零会让解析器去读
        # c4(前置自己的 puller),官方 pre1=8 的 c4 是 '0'/'5' 从不为空,写空即 C7050
        # (2026-07-30 真机实锤 parseAt4)。
        EffectSpec("5050022", "209", 10000, donor_line=1, target="0",
                   target_groups=None,
                   overrides=((6, "20000"), (7, "20000"), (31, "(None)"), (46, ""))),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # ---- 通用 ------------------------------------------------------------
    WeaponSpec("8000113", "深渊·征服者", "5010057", -1, "(None)", "universal_01", (
        EffectSpec("300001", "468", 100000, donor_line=5, target="5",
                   target_groups="(None)",
                   overrides=_INIT + (
                       (56, "300000"), (57, "300000"), (64, "1"),
                   )),
        EffectSpec("300002", "16", "", donor_line=6, target="7",
                   target_groups=None,
                   overrides=_trig(
                       25, puller=5, groups="(None)", th="1000", limit="3",
                   ) + ((64, "1"),)),
        EffectSpec("5045000", "61", "", donor_line=1, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("5020024", "34", 350000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
    # 用户:技能槽+50%;最大HP+50%;充能速度+30%;全属性抗性+30%
    # v3.2 两处调整:①211 改成「发动技能后」触发(开幕式与 102/110 撞截顶,触发式会随消耗回填)
    #               ②35 充能速度 30%→16%(游戏内上限实测 50%,3 把叠满 48% 刚好不溢)
    # 用户 2026-07-30:改成「自身发动技能时」(puller=0,不再出 null)、技能槽 15%、充能 15%
    WeaponSpec("8000114", "深渊·轮转核", "5020010", -1, "(None)", "universal_02", (
        EffectSpec("3050010", "211", 15000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_trig(23, puller=0)),
        EffectSpec("3060003", "156", 30000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5040033", "56", 20000, donor_line=4, target=None,
                   target_groups=None, overrides=_INIT),
        EffectSpec("5080029", "205", 50000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("3010035", "35", 15000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("3080008", "36", 30000, donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
    )),
    # 用户:删全抗;加 攻击力+200%、fever获取率+200%、能力伤害+200%
    WeaponSpec("8000115", "深渊·万象铳", "5090045", -1, "(None)", "universal_03", (
        EffectSpec("3080002", "68", "", donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("3080002", "69", "", donor_line=1, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("5080029", "205", 30000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("300001", "32", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
        EffectSpec("5090059", "50", 200000, donor_line=0, target="0",
                   target_groups=None, overrides=_INIT),
        EffectSpec("5090029", "388", 200000, donor_line=0, target="5",
                   target_groups="(None)", overrides=_INIT),
    )),
)


@dataclass(frozen=True)
class EffectStrengthRule:
    """Audited treatment for one official template line's c48/c49 strength pair."""

    mode: str
    cap: int | None = None
    note: str = ""


@dataclass(frozen=True)
class EffectStrengthResolution:
    value: int | str | None
    raw_scaled: int | None
    capped: bool
    rule: EffectStrengthRule


_SCALE = EffectStrengthRule("scale")
_KEEP_EMPTY = EffectStrengthRule("keep-empty", note="official flag row has blank strength")
_KEEP_PROBABILITY = EffectStrengthRule(
    "keep-probability", note="ConditionGuts probability is not an effect amplitude"
)
_CAP_SKILL_GAUGE = EffectStrengthRule(
    "scale", 100_000, "skill gauge is clamped at 100%"
)
_CAP_CHARGING = EffectStrengthRule(
    "scale", 16_000, "three copies must remain below the measured 50% charging cap"
)
_CAP_RESISTANCE = EffectStrengthRule(
    "scale", 33_000, "single-copy resistance redline is 33% (three copies = 99%)"
)
_CAP_MAX_SKILL_GAUGE = EffectStrengthRule(
    "scale", 100_000, "SecondSkillGauge total is clamped to +100% by the client"
)

# Every canonical (template_id, donor_line, emitted kind) is classified explicitly.
# All numeric amplitudes live in the paired c48/c49 strength columns. Blank flag rows and
# the ConditionGuts probability are the only non-amplitudes; c54/c55 frame values are never
# touched. 5050022#1 intentionally records the pre-existing v3.3 kind override 32 -> 209.
EFFECT_STRENGTH_RULES = MappingProxyType({
    ("3020011", 0, "51"): _SCALE,
    ("300001", 4, "202"): _SCALE,
    ("300001", 0, "32"): _SCALE,
    ("5020041", 0, "33"): _SCALE,
    ("3050010", 0, "211"): _CAP_SKILL_GAUGE,
    ("5050037", 0, "40"): _SCALE,
    ("4030004", 0, "190"): _SCALE,
    ("5100004", 1, "157"): _SCALE,
    ("5090059", 0, "50"): _SCALE,
    ("5040033", 4, "56"): _SCALE,
    ("5050009", 0, "55"): _SCALE,
    ("5050020", 1, "227"): _SCALE,
    ("4030019", 2, "70"): _KEEP_EMPTY,
    ("300001", 8, "226"): _SCALE,
    ("5080029", 0, "205"): _SCALE,
    ("5020024", 0, "34"): _SCALE,
    ("3080008", 0, "36"): _CAP_RESISTANCE,
    ("5090054", 0, "213"): _SCALE,
    ("5030021", 1, "26"): _KEEP_EMPTY,
    ("5090027", 0, "33"): _SCALE,
    ("5070040", 0, "38"): _SCALE,
    ("3010035", 0, "35"): _CAP_CHARGING,
    ("5040009", 1, "211"): _CAP_SKILL_GAUGE,
    ("5070017", 1, "200"): _SCALE,
    ("4040021", 1, "226"): _SCALE,
    ("4040007", 0, "191"): _SCALE,
    ("3010027", 1, "209"): _SCALE,
    ("5090029", 0, "388"): _SCALE,
    ("4060023", 2, "220"): _KEEP_EMPTY,
    ("5050017", 2, "203"): _SCALE,
    ("4080015", 1, "206"): _SCALE,
    ("5040019", 2, "245"): _CAP_MAX_SKILL_GAUGE,
    ("4080016", 2, "67"): _KEEP_EMPTY,
    ("5080038", 1, "41"): _SCALE,
    ("5090024", 2, "28"): _SCALE,
    ("3020003", 0, "59"): _KEEP_EMPTY,
    ("3020003", 1, "60"): _KEEP_EMPTY,
    ("5010047", 0, "1"): _SCALE,
    ("5050022", 1, "209"): _SCALE,
    ("300001", 5, "468"): _KEEP_PROBABILITY,
    ("300002", 6, "16"): _KEEP_EMPTY,
    ("5045000", 1, "61"): _KEEP_EMPTY,
    ("3060003", 0, "156"): _SCALE,
    ("3080002", 0, "68"): _KEEP_EMPTY,
    ("3080002", 1, "69"): _KEEP_EMPTY,
})


def validate_source_assets(
    asset_dir: Path, specs: tuple[WeaponSpec, ...],
) -> dict[str, Path]:
    """严格校验 15 张源 PNG，并按固定 image_slug 返回路径。"""
    if len(specs) != 15:
        raise ValueError(f"深渊武装源图必须正好 15 张,实际规格数 {len(specs)}")
    slugs = [spec.image_slug for spec in specs]
    if len(set(slugs)) != len(slugs):
        raise ValueError("深渊武装 image_slug 必须全部唯一")

    asset_dir = Path(asset_dir)
    expected_names = {f"{slug}.png" for slug in slugs}
    try:
        actual_names = {path.name for path in asset_dir.iterdir()}
    except OSError as exc:
        raise ValueError(f"无法读取源 PNG 目录 {asset_dir}: {exc}") from exc
    missing_names = sorted(expected_names.difference(actual_names))
    unexpected_names = sorted(actual_names.difference(expected_names))
    if missing_names or unexpected_names:
        raise ValueError(
            f"源 PNG 清单必须精确匹配 15 个固定文件: "
            f"missing={missing_names}, unexpected={unexpected_names}"
        )

    sources: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    for spec in specs:
        source = asset_dir / f"{spec.image_slug}.png"
        if not source.is_file():
            raise ValueError(f"缺少源 PNG: {source.name}")

        try:
            source_bytes = source.read_bytes()
        except OSError as exc:
            raise ValueError(f"无法读取源 PNG {source.name}: {exc}") from exc
        if source_bytes[:8] != PNG_SIGNATURE:
            raise ValueError(f"{source.name} 不是标准 PNG(魔数不对)")

        try:
            image = Image.open(io.BytesIO(source_bytes))
            with image:
                image.load()
                if image.format != "PNG":
                    raise ValueError(
                        f"{source.name} Pillow 格式必须是 PNG,实际 {image.format}"
                    )
                if image.size != SOURCE_ASSET_SIZE:
                    raise ValueError(
                        f"{source.name} 尺寸必须是 "
                        f"{SOURCE_ASSET_SIZE[0]}x{SOURCE_ASSET_SIZE[1]},实际 "
                        f"{image.size[0]}x{image.size[1]}"
                    )
                if image.mode != "RGBA":
                    raise ValueError(
                        f"{source.name} 模式必须是 RGBA,实际 {image.mode}"
                    )

                alpha = image.getchannel("A")
                alpha_min, alpha_max = alpha.getextrema()
                if alpha_min != 0:
                    raise ValueError(f"{source.name} 必须包含全透明像素")
                if alpha_max <= 0:
                    raise ValueError(f"{source.name} 不能是全透明图")

                bounds = alpha.getbbox()
                if bounds is None:
                    raise ValueError(f"{source.name} 没有可见像素")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"{source.name} 不是可解码 PNG: {exc}") from exc

        digest = hashlib.sha256(source_bytes).hexdigest()
        duplicate = hashes.get(digest)
        if duplicate is not None:
            raise ValueError(
                f"源 PNG 内容重复: {duplicate}.png 与 {spec.image_slug}.png"
            )
        hashes[digest] = spec.image_slug
        sources[spec.image_slug] = source

    if len(hashes) != 15:
        raise ValueError(f"源 PNG 必须有 15 个不同 SHA-256,实际 {len(hashes)}")
    return sources


def install_source_assets(
    store: Path, sources: dict[str, Path], specs: tuple[WeaponSpec, ...],
) -> list[str]:
    """仅转换 PNG 魔数并写入固定逻辑路径的 upload 哈希位置。"""
    expected_slugs = [spec.image_slug for spec in specs]
    missing = [slug for slug in expected_slugs if slug not in sources]
    unexpected = sorted(set(sources).difference(expected_slugs))
    if missing or unexpected:
        raise ValueError(
            f"源 PNG 映射不完整: missing={missing}, unexpected={unexpected}"
        )

    store = Path(store)
    installed: list[str] = []
    for spec in specs:
        source = Path(sources[spec.image_slug])
        try:
            source_bytes = source.read_bytes()
        except OSError as exc:
            raise ValueError(f"无法读取源 PNG {source.name}: {exc}") from exc
        stored_bytes = wf_assets.png_encode(source_bytes)
        logical = f"{IMAGE_PREFIX}/{spec.image_slug}.png"
        relative = q.hashed_rel(logical)
        destination = store / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(stored_bytes)

        readback = destination.read_bytes()
        if wf_assets.png_decode(readback) != source_bytes:
            raise RuntimeError(f"PNG 写后复读不一致: {logical}")
        installed.append(relative)

    if len(installed) != 15 or len(set(installed)) != 15:
        raise RuntimeError(
            f"PNG 安装路径必须是 15 个不同哈希路径,实际 {len(set(installed))}"
        )
    return installed


def _leaf_text(leaf: bytes | str) -> str:
    return leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf


def _join_like(rows: list[list[str]], like: bytes | str) -> bytes | str:
    text = core.write_csv_lines(rows)
    return text.encode("utf-8") if isinstance(like, bytes) else text


def cells(leaf) -> list[str]:
    return core.read_csv_lines(_leaf_text(leaf))[0]


def join_like(row: list[str], like) -> bytes | str:
    return _join_like([row], like)


def build_equipment_leaf(template_leaf: bytes | str, spec: WeaponSpec) -> bytes | str:
    """从供体装备首行构建一条固定的深渊武装行。"""
    row = list(core.read_csv_lines(_leaf_text(template_leaf))[0])
    row = core.normalize_row_length(row, 16)
    row[0] = f"mod_abyss_{spec.id}"
    row[1] = spec.name
    row[6] = f"{IMAGE_PREFIX}/{spec.image_slug}"
    row[7] = MODE_DESCRIPTION
    row[8] = "5"
    row[9] = "true"
    row[10] = spec.id
    row[11] = "5"
    return _join_like([row], template_leaf)


def build_ability_soul_item_leaf(
    template_leaf: bytes | str, spec: WeaponSpec,
) -> bytes | str:
    """Register the same-ID ability soul item required by detail/upgrade views."""
    row = list(core.read_csv_lines(_leaf_text(template_leaf))[0])
    row = core.normalize_row_length(row, 23)
    row[0] = f"mod_abyss_{spec.id}"
    row[1] = spec.id
    row[2] = f"{spec.name}魂珠"
    row[3] = f"{IMAGE_PREFIX}/{spec.image_slug}"
    row[12] = (
        str(spec.element) if spec.element >= 0 else ABILITY_SOUL_ALL_ELEMENTS
    )
    return _join_like([row], template_leaf)


def _clear_kind_companions(
    row: list[str], explicit: dict[int, str], kind_col: int, companions: tuple[int, ...],
) -> None:
    """kind 被设成 0(无条件/开幕)时清空伴随列;调用方显式给过值的列不动。"""
    if row[kind_col].strip() != "0":
        return
    for col in companions:
        if col not in explicit:
            row[col] = ""


def _assert_soul_row_legal(spec: WeaponSpec, slot: int, row: list[str]) -> None:
    """写盘前的客户端合法性门禁:枚举列空串 = 打开角色页即 C7050/C7101。"""
    if len(row) != SOUL_ROW_WIDTH:
        raise ValueError(f"{spec.id} 槽{slot}: 列数 {len(row)} != {SOUL_ROW_WIDTH}")
    # 只导入纯校验模块:wf_gui 在模块级解析 TARGET_STORE,导入即要求本机装好数据包,
    # 会让 CI/干净克隆里的纯 fixture 单元测试直接 SystemExit。
    import wf_client_legality
    problems = list(wf_client_legality.client_legality_problems("ability_soul", row))
    # wf_gui 的检查器不看 c25 —— 补上这条,2026-07-30 真机实锤过一次 C7050
    trig = row[SOUL_TRIGGER_KIND_COL].strip()
    puller = row[SOUL_PULLER_COL].strip()
    if trig in TRIGGER_NEEDS_PULLER and puller == "":
        problems.append(
            f"c{SOUL_PULLER_COL} trigger_puller 为空,但触发 kind={trig} 属"
            f"「必须带 puller」族(官方该 kind 无一行为空)→ parseAt25 抛 C7050")
    if trig in TRIGGER_NO_PULLER and puller != "":
        problems.append(
            f"c{SOUL_PULLER_COL} trigger_puller={puller!r},但触发 kind={trig} 属"
            f"「不带 puller」族(官方该 kind 恒空)")
    pgrp = row[SOUL_PULLER_GROUP_COL].strip()
    if puller in PULLER_NEEDS_GROUP and pgrp == "":
        problems.append(
            f"c{SOUL_PULLER_GROUP_COL} puller.groups 为空,但 puller={puller} 属队伍族"
            f"(官方无一行为空)→ 游戏内会渲染成「null角色发动技能时」")
    if puller == "0" and pgrp != "":
        problems.append(
            f"c{SOUL_PULLER_GROUP_COL} puller.groups={pgrp!r},但 puller=0(Myself) "
            f"官方恒空(97/97)")
    if problems:
        detail = "\n  ".join(problems)
        raise ValueError(f"{spec.id} 槽{slot} 客户端合法性未通过(会 C7050/C7101):\n  {detail}")


def resolve_effect_strength(
    spec: WeaponSpec, effect: EffectSpec,
) -> EffectStrengthResolution:
    """Resolve one audited c48/c49 value without touching duration or trigger fields."""
    key = (effect.template_id, effect.donor_line, effect.effect_kind)
    try:
        rule = EFFECT_STRENGTH_RULES[key]
    except KeyError as exc:
        raise ValueError(
            f"{spec.id} has no audited strength rule for template {key!r}"
        ) from exc

    # Preserve the pre-existing EffectSpec contract: None means inherit both donor
    # endpoints verbatim. Flag/probability rules must stay explicit so that None can
    # never accidentally carry an unrelated donor number into those semantic types.
    if effect.strength is None:
        if rule.mode != "scale":
            raise ValueError(f"{spec.id} template {key!r} cannot inherit strength")
        return EffectStrengthResolution(None, None, False, rule)
    if rule.mode == "keep-empty":
        if effect.strength != "":
            raise ValueError(f"{spec.id} template {key!r} must have blank strength")
        return EffectStrengthResolution("", None, False, rule)
    if rule.mode == "keep-probability":
        if isinstance(effect.strength, bool) or not isinstance(effect.strength, int):
            raise ValueError(f"{spec.id} template {key!r} probability must be an integer")
        return EffectStrengthResolution(effect.strength, None, False, rule)
    if rule.mode != "scale":
        raise ValueError(f"{spec.id} template {key!r} has unknown rule mode {rule.mode!r}")
    if isinstance(effect.strength, bool) or not isinstance(effect.strength, int):
        raise ValueError(f"{spec.id} template {key!r} strength must be an integer")

    raw_scaled = _ceil_scaled(effect.strength, DEFAULT_UPLIFT_MULTIPLIER)
    value = min(raw_scaled, rule.cap) if rule.cap is not None else raw_scaled
    return EffectStrengthResolution(value, raw_scaled, value != raw_scaled, rule)


def build_soul_leaf(
    template_table: dict[str, bytes | str], spec: WeaponSpec, *, validate: bool = True,
) -> bytes | str:
    """按声明顺序逐条取捐赠行、逐列覆写，构建同键 ability_soul。

    覆写顺序:头部(槽/段/触发模式) → kind → target/组 → 强度 → overrides → 规则 A/B 清伴随列。
    overrides 最后生效,所以任何列都能被调用方钉死。
    """
    rows: list[list[str]] = []
    output_like: bytes | str = ""
    for slot, effect in enumerate(spec.effects, start=1):
        template_leaf = template_table[effect.template_id]
        if slot == 1:
            output_like = template_leaf
        lines = core.read_csv_lines(_leaf_text(template_leaf))
        if not 0 <= effect.donor_line < len(lines):
            raise ValueError(
                f"{spec.id} 槽{slot}: 捐赠键 {effect.template_id} 只有 {len(lines)} 行,"
                f"donor_line={effect.donor_line} 越界")
        row = core.normalize_row_length(list(lines[effect.donor_line]), SOUL_ROW_WIDTH)
        row[0], row[1], row[2] = str(slot), "1", "0"
        row[44] = effect.effect_kind
        if effect.target is not None:
            row[45] = effect.target
        if effect.target_groups is WEAPON_GROUP:
            row[46] = spec.group
        elif effect.target_groups is not None:
            row[46] = effect.target_groups
        strength = resolve_effect_strength(spec, effect).value
        if strength is not None:
            row[48] = row[49] = str(strength)
        explicit = {int(col): value for col, value in effect.overrides}
        for col, value in explicit.items():
            if not 0 <= col < SOUL_ROW_WIDTH:
                raise ValueError(f"{spec.id} 槽{slot}: overrides 列号 {col} 越界")
            row[col] = value
        _clear_kind_companions(
            row, explicit, SOUL_TRIGGER_KIND_COL, SOUL_TRIGGER_COMPANION_COLS)
        _clear_kind_companions(
            row, explicit, SOUL_PRE1_KIND_COL, SOUL_PRE1_COMPANION_COLS)
        if validate:
            _assert_soul_row_legal(spec, slot, row)
        rows.append(row)
    return _join_like(rows, output_like)


def _ceil_scaled(value: int, multiplier: tuple[int, int]) -> int:
    """Apply an exact rational multiplier, rounding toward positive infinity."""
    if (
        not isinstance(multiplier, tuple)
        or len(multiplier) != 2
        or any(isinstance(part, bool) or not isinstance(part, int) for part in multiplier)
    ):
        raise ValueError(f"multiplier must be a pair of integers, got {multiplier!r}")
    numerator, denominator = multiplier
    if numerator <= 0 or denominator <= 0:
        raise ValueError(f"multiplier must be positive, got {multiplier!r}")
    scaled_numerator = value * numerator
    return -((-scaled_numerator) // denominator)


def _parse_status_anchors(
    donor_status: object, *, donor: str,
) -> list[tuple[int, tuple[int, int]]]:
    if not isinstance(donor_status, dict) or not donor_status:
        raise ValueError(f"equipment_status donor {donor} must be a non-empty level map")

    anchors: list[tuple[int, tuple[int, int]]] = []
    for raw_level, raw_pair in donor_status.items():
        try:
            level = int(raw_level)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"equipment_status donor {donor} has invalid level {raw_level!r}"
            ) from exc
        if level < 1 or str(level) != str(raw_level):
            raise ValueError(
                f"equipment_status donor {donor} has non-canonical level {raw_level!r}"
            )
        if not isinstance(raw_pair, str):
            raise ValueError(
                f"equipment_status donor {donor} level {level} must be 'HP,ATK'"
            )
        parts = raw_pair.split(",")
        if len(parts) != 2:
            raise ValueError(
                f"equipment_status donor {donor} level {level} must contain two values"
            )
        try:
            hp, attack = (int(part) for part in parts)
        except ValueError as exc:
            raise ValueError(
                f"equipment_status donor {donor} level {level} has non-integer HP/ATK"
            ) from exc
        if hp < 0 or attack < 0:
            raise ValueError(
                f"equipment_status donor {donor} level {level} has negative HP/ATK"
            )
        anchors.append((level, (hp, attack)))

    anchors.sort()
    if anchors[0][0] != 1:
        raise ValueError(f"equipment_status donor {donor} must start at level 1")
    for (left_level, left), (right_level, right) in zip(anchors, anchors[1:]):
        if right_level == left_level:
            raise ValueError(f"equipment_status donor {donor} repeats level {left_level}")
        if any(after < before for before, after in zip(left, right)):
            raise ValueError(
                f"equipment_status donor {donor} must be monotonic between "
                f"levels {left_level} and {right_level}"
            )
    return anchors


def build_equipment_status(status_table: dict[str, object], spec: WeaponSpec):
    """Materialize the donor curve at every level, then scale HP/ATK exactly."""
    anchors = _parse_status_anchors(status_table[spec.donor], donor=spec.donor)
    result: dict[str, str] = {}
    segment = 0
    for level in range(1, anchors[-1][0] + 1):
        while segment + 1 < len(anchors) and level > anchors[segment + 1][0]:
            segment += 1
        left_level, left_values = anchors[segment]
        if level == left_level or segment + 1 == len(anchors):
            source_values = left_values
        else:
            right_level, right_values = anchors[segment + 1]
            span = right_level - left_level
            offset = level - left_level
            source_values = tuple(
                _ceil_scaled(
                    left * span + (right - left) * offset,
                    (1, span),
                )
                for left, right in zip(left_values, right_values)
            )
        scaled = tuple(
            _ceil_scaled(value, spec.status_multiplier) for value in source_values
        )
        result[str(level)] = f"{scaled[0]},{scaled[1]}"
    return result


def _require_leaf(value: object, label: str) -> bytes | str:
    if not isinstance(value, (bytes, str)):
        raise ValueError(f"{label} 必须是 CSV 叶子,得到 {type(value).__name__}")
    return value


def assert_reserved_ownership(equipment: dict[str, object]) -> None:
    """拒绝覆盖未带精确深渊所有权标记的保留装备 ID。"""
    for spec in WEAPONS:
        if spec.id not in equipment:
            continue
        leaf = _require_leaf(equipment[spec.id], f"equipment[{spec.id}]")
        try:
            rows = core.read_csv_lines(_leaf_text(leaf))
        except Exception as exc:
            raise ValueError(f"保留装备 ID {spec.id} 的行无法解析") from exc
        marker = f"mod_abyss_{spec.id}"
        if len(rows) != 1 or not rows[0] or rows[0][0] != marker:
            actual = rows[0][0] if rows and rows[0] else "<missing>"
            raise ValueError(
                f"保留装备 ID {spec.id} 已被未知数据占用: c0={actual!r}, "
                f"期望 {marker!r}"
            )


def assert_reserved_item_ownership(items: dict[str, object]) -> None:
    """Reject foreign occupants before writing same-ID ability soul items."""
    for spec in WEAPONS:
        if spec.id not in items:
            continue
        leaf = _require_leaf(items[spec.id], f"item[{spec.id}]")
        try:
            rows = core.read_csv_lines(_leaf_text(leaf))
        except Exception as exc:
            raise ValueError(f"reserved item ID {spec.id} cannot be parsed") from exc
        marker = f"mod_abyss_{spec.id}"
        if len(rows) != 1 or not rows[0] or rows[0][0] != marker:
            actual = rows[0][0] if rows and rows[0] else "<missing>"
            raise ValueError(
                f"reserved item ID {spec.id} is occupied by foreign data: "
                f"c0={actual!r}, expected {marker!r}"
            )


def patch_rush_token(leaf: bytes | str) -> bytes | str:
    """只把 Rush Event 行的 c10 改为深渊代币,并保留叶子类型。"""
    rows = core.read_csv_lines(_leaf_text(leaf))
    if len(rows) != 1 or len(rows[0]) <= 10:
        raise ValueError(f"rush_event[{EVENT_ID}] 必须是至少 11 列的单行 CSV")
    rows[0][10] = TOKEN_ID
    return _join_like(rows, leaf)


def build_token_leaf(template_leaf: bytes | str) -> bytes | str:
    """Clone the complete canonical token template and patch owned columns."""
    rows = core.read_csv_lines(_leaf_text(template_leaf))
    if len(rows) != 1 or len(rows[0]) <= 5:
        raise ValueError(f"item[{TOKEN_TEMPLATE}] must be a single row with 6+ columns")
    row = list(rows[0])
    row[0] = "rogue_event_item_99"
    row[1] = TOKEN_ID
    row[2] = "深渊代币"
    row[5] = TOKEN_DESCRIPTION
    return _join_like([row], template_leaf)


def build_master_changes(tables: MasterTables) -> MasterChanges:
    """纯内存构建五张客户端表;所有占用与依赖在修改副本前完成校验。"""
    assert_reserved_ownership(tables.equipment)
    assert_reserved_item_ownership(tables.items)

    for spec in WEAPONS:
        has_owner = spec.id in tables.equipment
        if not has_owner and (
            spec.id in tables.equipment_status or spec.id in tables.ability_soul
        ):
            raise ValueError(f"保留 ID {spec.id} 存在孤立 soul/status,但没有所有权装备行")
        if spec.donor not in tables.equipment:
            raise ValueError(f"缺少装备供体 {spec.donor}")
        if spec.donor not in tables.items:
            raise ValueError(f"ability soul item donor missing: {spec.donor}")
        if spec.donor not in tables.equipment_status:
            raise ValueError(f"缺少装备状态供体 {spec.donor}")
        missing_templates = [
            effect.template_id for effect in spec.effects
            if effect.template_id not in tables.ability_soul
        ]
        if missing_templates:
            raise ValueError(f"武装 {spec.id} 缺少词条模板: {','.join(missing_templates)}")

    if TOKEN_TEMPLATE not in tables.items:
        raise ValueError(f"缺少代币模板 {TOKEN_TEMPLATE}")
    if EVENT_ID not in tables.rush_event:
        raise ValueError(f"缺少 Rush Event {EVENT_ID}")

    token_template = _require_leaf(
        tables.items[TOKEN_TEMPLATE], f"item[{TOKEN_TEMPLATE}]"
    )
    items = copy.deepcopy(tables.items)
    equipment = copy.deepcopy(tables.equipment)
    equipment_status = copy.deepcopy(tables.equipment_status)
    ability_soul = copy.deepcopy(tables.ability_soul)
    rush_event = copy.deepcopy(tables.rush_event)

    items[TOKEN_ID] = build_token_leaf(token_template)
    for spec in WEAPONS:
        donor_item_leaf = _require_leaf(
            tables.items[spec.donor], f"item[{spec.donor}]"
        )
        items[spec.id] = build_ability_soul_item_leaf(donor_item_leaf, spec)
        donor_leaf = _require_leaf(
            tables.equipment[spec.donor], f"equipment[{spec.donor}]"
        )
        equipment[spec.id] = build_equipment_leaf(donor_leaf, spec)
        equipment_status[spec.id] = build_equipment_status(tables.equipment_status, spec)
        ability_soul[spec.id] = build_soul_leaf(tables.ability_soul, spec)
    if rogue_build.TEMPLATE_EVENT not in tables.rush_event:
        raise ValueError(f"缺少 Rush Event 模板 {rogue_build.TEMPLATE_EVENT}")
    rush_leaf = _require_leaf(tables.rush_event[EVENT_ID], f"rush_event[{EVENT_ID}]")
    rush_template = _require_leaf(
        tables.rush_event[rogue_build.TEMPLATE_EVENT],
        f"rush_event[{rogue_build.TEMPLATE_EVENT}]",
    )
    rush_event[EVENT_ID] = rogue_build.build_event_metadata_leaf(
        rush_template,
        rush_leaf,
    )

    assert_reserved_ownership(equipment)
    generated = {spec.id for spec in WEAPONS}
    for label, table in (
        ("item", items),
        ("equipment", equipment),
        ("equipment_status", equipment_status),
        ("ability_soul", ability_soul),
    ):
        missing = generated.difference(table)
        if missing:
            raise RuntimeError(f"{label} 构建后缺少保留 ID: {sorted(missing)}")
    if cells(_require_leaf(items[TOKEN_ID], f"item[{TOKEN_ID}]"))[2] != "深渊代币":
        raise RuntimeError("深渊代币构建后名称校验失败")
    if cells(_require_leaf(rush_event[EVENT_ID], f"rush_event[{EVENT_ID}]"))[10] != TOKEN_ID:
        raise RuntimeError("Rush Event 构建后代币校验失败")

    return MasterChanges(
        items=items,
        equipment=equipment,
        equipment_status=equipment_status,
        ability_soul=ability_soul,
        rush_event=rush_event,
    )


def apply_server_mirrors(mirrors: ServerMirrors) -> ServerMirrors:
    """纯内存应用五个服务端镜像,并规范化 ID 数组。"""
    for spec in WEAPONS:
        if spec.donor not in mirrors.equipment_max_level:
            raise ValueError(f"equipment_max_level 缺少供体 {spec.donor}")
        donor_lookup = mirrors.equipment_lookup.get(spec.donor)
        if not isinstance(donor_lookup, dict) or "category" not in donor_lookup:
            raise ValueError(f"equipment_lookup 缺少供体类别 {spec.donor}")

    max_level = copy.deepcopy(mirrors.equipment_max_level)
    element = copy.deepcopy(mirrors.equipment_element)
    lookup = copy.deepcopy(mirrors.equipment_lookup)
    for spec in WEAPONS:
        donor_lookup = mirrors.equipment_lookup[spec.donor]
        max_level[spec.id] = copy.deepcopy(mirrors.equipment_max_level[spec.donor])
        element[spec.id] = spec.element
        lookup[spec.id] = {
            "name": spec.name,
            "rarity": "5",
            "category": copy.deepcopy(donor_lookup["category"]),
        }

    try:
        equipment_ids = sorted({
            *(int(value) for value in mirrors.equipment_ids),
            *(int(spec.id) for spec in WEAPONS),
        })
        item_ids = sorted({
            *(int(value) for value in mirrors.item_ids),
            int(TOKEN_ID),
        })
    except (TypeError, ValueError) as exc:
        raise ValueError("equipment_ids/item_ids 必须是整数数组") from exc

    return ServerMirrors(
        equipment_max_level=max_level,
        equipment_element=element,
        equipment_lookup=lookup,
        equipment_ids=equipment_ids,
        item_ids=item_ids,
    )


def load_json(name: str):
    with open(os.path.join(ROOT, "assets", name), encoding="utf-8") as fh:
        return json.load(fh)


def save_json(name: str, data) -> None:
    with open(os.path.join(ROOT, "assets", name), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=0 if isinstance(data, list) else 1)


def require_cn_profile() -> core.VersionProfile:
    """锁定生成、写入与发布到同一个无 fallback 的 CN store。"""
    active = core.resolve_profile()
    cn_profile = core.resolve_profile("cn")
    if active is None or cn_profile is None:
        raise ValueError("必须同时配置 active profile 与 cn profile")
    if active.id != "cn" or cn_profile.id != "cn":
        raise ValueError(
            f"仅允许 active=cn,当前 active={active.id!r}, cn={cn_profile.id!r}"
        )
    if active.fallback is not None or cn_profile.fallback is not None:
        raise ValueError("CN profile 必须设置 fallback=null")

    active_store = core.require_active_store(profile=active).resolve()
    cn_store = core.require_active_store(profile=cn_profile).resolve()
    if not active_store.exists() or not cn_store.exists():
        raise ValueError(
            f"CN store 不存在: active={active_store}, explicit={cn_store}"
        )
    if active_store != cn_store:
        raise ValueError(
            f"active/cn store 不一致: active={active_store}, explicit={cn_store}"
        )

    quest_store = q.store_path(ITEM_T).parents[1].resolve()
    if quest_store != active_store:
        raise ValueError(
            f"wf_quest_lib store 与 CN profile 不一致: quest={quest_store}, "
            f"profile={active_store}"
        )
    print(f"[PROFILE] active=cn store={active_store}")
    return replace(active, store=active_store)


def _assert_readback_rows(
    actual: dict[str, object], expected: dict[str, object], keys: list[str], label: str,
) -> None:
    for key in keys:
        if key not in actual:
            raise RuntimeError(f"{label} 写后复读缺少键 {key}")
        if actual[key] != expected[key]:
            raise RuntimeError(f"{label} 写后复读不一致: {key}")


def _print_plan(changes: MasterChanges) -> None:
    print(f"代币: {TOKEN_ID} 深渊代币 <- {TOKEN_TEMPLATE}")
    for spec in WEAPONS:
        effects = ", ".join(
            f"kind {effect.effect_kind}={resolve_effect_strength(spec, effect).value}"
            for effect in spec.effects
        )
        image = f"{IMAGE_PREFIX}/{spec.image_slug}"
        print(
            f"武装: {spec.id} {spec.name} | donor={spec.donor} | "
            f"element={spec.element} | image={image} | effects=[{effects}]"
        )
        leaf = _require_leaf(changes.ability_soul[spec.id], f"ability_soul[{spec.id}]")
        descriptions = wf_describe.describe_rows(
            core.read_csv_lines(_leaf_text(leaf)), "ability_soul"
        )
        for slot, description in enumerate(descriptions, start=1):
            print(f"  词条 {slot}: {description}")
    print(
        f"[PLAN] {len(WEAPONS)} weapons; token {TOKEN_ID}; "
        "5 client tables; 5 server mirrors"
    )
    print(
        "[PLAN] client: item, equipment, equipment_status, ability_soul, rush_event"
    )
    print(
        "[PLAN] mirrors: equipment_max_level, equipment_element, equipment_lookup, "
        "equipment_ids, item_ids"
    )


def _print_asset_validation(sources: dict[str, Path]) -> None:
    digests: list[str] = []
    for spec in WEAPONS:
        source = sources[spec.image_slug]
        source_bytes = source.read_bytes()
        digest = hashlib.sha256(source_bytes).hexdigest()
        with Image.open(io.BytesIO(source_bytes)) as image:
            size = image.size
            mode = image.mode
        logical = f"{IMAGE_PREFIX}/{spec.image_slug}.png"
        relative = q.hashed_rel(logical)
        print(
            f"[ASSET] {source.name}: {size[0]}x{size[1]} {mode} "
            f"sha256={digest} logical={logical} hashed={relative}"
        )
        digests.append(digest)
    print(
        f"[OK] {len(sources)}/15 valid; "
        f"{len(set(digests))} distinct SHA-256"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="深渊代币 + 连战专属武装")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--client-verification")
    ap.add_argument("--ffdec", type=Path)
    ap.add_argument("--java", type=Path)
    ap.add_argument("--validate-assets", action="store_true")
    args = ap.parse_args()

    if args.publish and not args.write:
        print("[ERR] --publish 必须与 --write 同时使用", file=sys.stderr)
        return 1
    if args.publish and not args.client_verification:
        print("[ERR] --publish 必须提供 --client-verification", file=sys.stderr)
        return 1
    if args.publish and (args.ffdec is None or args.java is None):
        print("[ERR] --publish 必须同时提供 --ffdec 与 --java", file=sys.stderr)
        return 1

    sources: dict[str, Path] | None = None
    if args.validate_assets or args.write:
        try:
            sources = validate_source_assets(SOURCE_ASSET_DIR, WEAPONS)
            _print_asset_validation(sources)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            print(f"[ERR] 图片校验失败: {exc}", file=sys.stderr)
            return 1
        if args.validate_assets and not args.write:
            return 0

    try:
        profile = require_cn_profile()
        tables = MasterTables(
            items=q.load_table(ITEM_T),
            equipment=q.load_table(EQUIP_T),
            equipment_status=q.load_table(EQUIP_STATUS_T),
            ability_soul=q.load_table(SOUL_T),
            rush_event=q.load_table(RUSH_EVENT_T),
        )
        mirrors = ServerMirrors(
            equipment_max_level=load_json("equipment_max_level.json"),
            equipment_element=load_json("equipment_element.json"),
            equipment_lookup=load_json("equipment_lookup.json"),
            equipment_ids=load_json("equipment_ids.json"),
            item_ids=load_json("item_ids.json"),
        )
        changes = build_master_changes(tables)
        mirror_changes = apply_server_mirrors(mirrors)
        _print_plan(changes)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"[ERR] 生成计划失败: {exc}", file=sys.stderr)
        return 1

    if not args.write:
        print("[DRY-RUN] 未写入任何文件。加 --write 生效。")
        return 0

    weapon_ids = [spec.id for spec in WEAPONS]
    try:
        q.save_table(ITEM_T, changes.items)
        item_readback = q.load_table(ITEM_T)
        _assert_readback_rows(
            item_readback, changes.items, [TOKEN_ID, *weapon_ids], "item"
        )

        q.save_table(EQUIP_T, changes.equipment)
        equipment_readback = q.load_table(EQUIP_T)
        _assert_readback_rows(
            equipment_readback, changes.equipment, weapon_ids, "equipment"
        )
        assert_reserved_ownership(equipment_readback)

        q.save_table(EQUIP_STATUS_T, changes.equipment_status)
        status_readback = q.load_table(EQUIP_STATUS_T)
        _assert_readback_rows(
            status_readback, changes.equipment_status, weapon_ids, "equipment_status"
        )

        q.save_table(SOUL_T, changes.ability_soul)
        soul_readback = q.load_table(SOUL_T)
        _assert_readback_rows(
            soul_readback, changes.ability_soul, weapon_ids, "ability_soul"
        )

        q.save_table(RUSH_EVENT_T, changes.rush_event)
        rush_readback = q.load_table(RUSH_EVENT_T)
        _assert_readback_rows(
            rush_readback, changes.rush_event, [EVENT_ID], "rush_event"
        )
        rush_leaf = _require_leaf(rush_readback[EVENT_ID], f"rush_event[{EVENT_ID}]")
        if cells(rush_leaf)[10] != TOKEN_ID:
            raise RuntimeError(f"rush_event[{EVENT_ID}] 写后复读 c10 不是 {TOKEN_ID}")

        mirror_writes = (
            ("equipment_max_level.json", mirror_changes.equipment_max_level),
            ("equipment_element.json", mirror_changes.equipment_element),
            ("equipment_lookup.json", mirror_changes.equipment_lookup),
            ("equipment_ids.json", mirror_changes.equipment_ids),
            ("item_ids.json", mirror_changes.item_ids),
        )
        for name, data in mirror_writes:
            save_json(name, data)
            if load_json(name) != data:
                raise RuntimeError(f"{name} 写后复读不一致")

        if sources is None:
            raise RuntimeError("写入前未校验源 PNG")
        installed = install_source_assets(profile.store, sources, WEAPONS)
        if len(installed) != len(WEAPONS):
            raise RuntimeError(
                f"PNG 安装数量不一致: expected={len(WEAPONS)}, actual={len(installed)}"
            )
    except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
        print(f"[ERR] 写入或复读失败,禁止发布: {exc}", file=sys.stderr)
        return 1

    print(
        "[OK] 5 client tables, 5 server mirrors, and 15 PNGs passed "
        "write/readback validation"
    )
    from wf_rogue_validate import require_release_ready, release_logicals

    publish_tables = ",".join(release_logicals())
    if not args.publish:
        print(f"发布命令: python mod-tools/wf_publish.py --tables {publish_tables}")
        return 0

    try:
        publish_profile = require_cn_profile()
    except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
        print(f"[ERR] 发布前 CN profile 复检失败: {exc}", file=sys.stderr)
        return 1

    try:
        release_snapshot = require_release_ready(
            publish_profile.store,
            Path(ROOT) / "assets",
            Path(args.client_verification),
            ffdec=args.ffdec,
            java=args.java,
        )
    except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
        print(f"[ERR] 发布门禁失败,禁止调用发布器: {exc}", file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="wf-abyss-release-snapshot-") as temp:
            snapshot_path = Path(temp) / "release-snapshot.json"
            release_snapshot.write(snapshot_path)
            command = [
                sys.executable,
                str(Path(ROOT) / "mod-tools" / "wf_publish.py"),
                "--tables",
                publish_tables,
                "--snapshot",
                str(snapshot_path),
            ]
            subprocess.run(command, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        code = exc.returncode if exc.returncode else 1
        print(f"[ERR] wf_publish 退出码 {code}", file=sys.stderr)
        return code
    except OSError as exc:
        print(f"[ERR] 无法调用 wf_publish: {exc}", file=sys.stderr)
        return 1
    print("[PUBLISH] wf_publish 退出码 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
