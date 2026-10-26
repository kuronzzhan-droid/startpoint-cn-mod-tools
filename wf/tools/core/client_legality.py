#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户端 AbilityValues.parseAt* 硬规则校验(与数据包无关)。

从 wf_gui 摘出来:写盘前的合法性门禁(wf_rogue_rewards._assert_soul_row_legal)
只需要这一个纯函数,但 wf_gui 在模块级解析 TARGET_STORE,导入即要求本机装好
数据包 —— 于是 CI/干净克隆里跑纯 fixture 的单元测试会直接 SystemExit。
本模块只依赖 wf_describe 的布局表,不碰任何 store。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_describe  # noqa: E402  行级中文描述器(逆向布局+枚举直译)
from wf_client_description_legality import description_compatibility_problems  # noqa: E402
from wf_client_patch_scope import (  # noqa: E402
    patch_parser_capabilities, patch_parser_scope_problems, patch_parser_supported,
)
from wf_battle_rules import row_problems as battle_rule_problems  # noqa: E402
import wfx_registry  # noqa: E402  扩展词条框架注册表(补丁构造的唯一真源)


# master/ability/ability_statue_group.orderedmap 的全部键(25 个,实测取自 store)。
# c2 是玛纳板雕像组键:OwnedManaNodeLogic.resolveStatueImageId 对它做
# MasterStringMap.get 后立刻读 .color,键不存在就是 C8601「指定的Key不存在」,
# 表现为该角色玛纳板整块打不开。自造词(如 guts / resist)是最常见的写法错误。
ABILITY_STATUE_GROUPS = frozenset({
    "action_skill", "attack", "attack_black", "attack_blue", "attack_common",
    "attack_green", "attack_red", "attack_white", "attack_yellow", "condition",
    "defense_black", "defense_blue", "defense_common", "defense_green",
    "defense_red", "defense_white", "defense_yellow", "episode", "fever",
    "hp", "hp_skill", "power_flip", "skill_evolution", "skill_level", "special",
})

# character.orderedmap 第26列(0-based)stance 的运行时合法全集(2026-08-26 实锤,
# 魔王 169995 写 'Special' 详情页即崩 C8601)。StanceLogic 拿该字符串原样查
# StanceTable = CDN 下载表 {Attacker,Tank,Healer,Supporter,Jammer} ∪ APK 内置
# stance_iosbundled {Balance},共 6 键;表外值在 StatusWindow.getFormattedStance
# 抛「指定的Key不存在」。证据:StanceLogic.as:22-23 / CharacterValues.as:237-238 /
# CommonLogicAssetContainer.as:203-226(多文件并集)。
CHARACTER_STANCES = frozenset({
    "Attacker", "Tank", "Healer", "Supporter", "Jammer", "Balance",
})
CHARACTER_STANCE_COL = 26

# 前置 kind 后一列(puller/参数)必须非空的集合(空串=parseAt7/14/21 C7050,
# 2026-07-13 实锤 8/9/87/187/188/200/205,2026-08-26 实锤 144)。
# 202/203(主/副位门)留空反而正确,勿加入。
PRECONDITION_KINDS_NEED_NEXT_COL = frozenset({
    "8", "9", "87", "144", "187", "188", "200", "205",
})

# ─────────────────── 客户端补丁才存在的枚举值(2026-09-07) ───────────────────
#
# ability_enum_map.json 的枚举域 = **打了补丁的**客户端能构造的全集。官方 APK 的
# InstantAbilityContentMasterValue 只到 723;补丁新增的值落到官方 AbilityValues 的
# else 分支就是 `throw new ClientError(7050,"不存在的构造函数。")` —— 打开角色详情
# 页即崩。所以枚举域校验通过 ≠ 任意客户端可用:凡是这里登记的 kind,发布前必须先
# 确认对应 capability 已经装进真机。
#
#   724 AddFeverPointRatio —— 稻穗 139995 V12:按 Fever 槽上限的比例增减当前 Fever
#     槽。强度沿用 Decimal(×100000)且允许负号,-10000 = 上限的 -10%。
#   422 DashParameter —— V12 的可调冲刺参数族。during_content 的 unique_condition_id
#     列(ability c118,parseAt118 -> int)在这条 kind 上装的是 **param_id**
#     (0 冷却 / 1 弹射速度 / 2 锁定距离上限 / 3 蓄力帧 / 4 回拉距离 / 5 惯性 /
#     6 可冲刺高度),strength(c113/c114,Decimal ×100000,允许负号)是调整量;
#     除 param_id 2 是绝对像素上限外,其余六个都是官方常量的倍率
#     (生效值 = 官方常量 × (1 + strength/100000))。官方 CommonAbilityContentMasterValue
#     只到 421,没打补丁读到 422 同样是 C7050。
#
# 表由 wfx_registry.json 的 patch_content_kinds 派生（唯一真源），与此前的手写表逐项相同：
#   {"instant_content": {"724": "kyubi-fever-ratio-v1"},
#    "during_content": {"422": "dash-parameter-v1", "423": "gauge-gain-rules-v1",
#                       "424": "damage-type-rules-v1"}}
# tests/test_wfx_registry.py 钉住这份快照；新增补丁构造只改注册表 + ability_enum_map.json。
CLIENT_PATCH_CONTENT_KINDS = wfx_registry.client_patch_content_kinds()

# ────────── 面板文案覆盖行(master/string/custom_ability_string)的补丁门禁 ──────────
#
# `client-patch/kyubi-panel-override` 在 AbilityLogic / LeaderAbilityLogic 的四个
# 描述方法前置一次查表:键 = "desc_override_" + 该词条/队长技第 0 行的 string_id。
# 没打补丁的客户端读不到这些行 —— 它们是**惰性**的,不崩,只是面板仍走官方生成器。
# 所以这里报出的 capability 是「这行要生效需要哪个 APK」,不是「不装就崩」。
#
#   V11(kyubi-panel-description-override-v1)守卫写死 STRING_ID_PREFIX =
#     "fox_oracle_autumn",只有九尾狐的行会被探测。
#   V14(panel-description-override-v2)把守卫改成空前缀 —— 任何 string_id 都探测,
#     并改走 ILogicAssetContainer.getMasterTableMaybe(表没加载返回 null,而不是
#     getMasterTable 的 ClientError 8013)。V14 APK 同时提供两个 capability。
#
# 判据只看键:string_id 落在 V11 守卫内的行报 v1(V11 与 V14 都能显示),
# 其余 desc_override_* 行报 v2(只有 V14 起作用)。
#
# 例外:`desc_override_equipment_*` 是装备详情覆盖的命名空间,不归 V11/V14。
# `client-patch/equipment-description-override` 在 AbilitySoulAbilityLogic 的
# getDescriptionsWithoutAdditional / getDescriptionWithoutAdditional 与
# EquipmentEnhancementAbilityLogic.getAllDescriptionsToMapForDialog 前置查表,键由装备 ID 派生:
#   desc_override_equipment_<id>                        本体(魂)说明,"\n" 分行
#   desc_override_equipment_enhancement_<id>            强化成长块(开关键)
#   desc_override_equipment_enhancement_<id>_final      强化满级块(可缺)
# 同样是惰性的:没打补丁的客户端不读这些键,照旧显示生成文案、不崩(行为型 capability,
# 只报在 capabilities,不进 problems)。V14 的 AbilityLogic 探针是 "desc_override_" +
# 词条 string_id,只要词条/队长技 string_id 不以 "equipment_" 开头(client_legality_problems
# 拦),两个命名空间就不相撞,所以装备前缀必须先于 V1/V2 判定。
CUSTOM_ABILITY_STRING_KIND = "custom_ability_string"
PANEL_OVERRIDE_KEY_PREFIX = "desc_override_"
PANEL_OVERRIDE_V1_STRING_ID_PREFIX = "fox_oracle_autumn"
PANEL_OVERRIDE_V1 = "kyubi-panel-description-override-v1"
PANEL_OVERRIDE_V2 = "panel-description-override-v2"
EQUIPMENT_DESC_OVERRIDE_STRING_ID_PREFIX = "equipment_"
EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX = PANEL_OVERRIDE_KEY_PREFIX + EQUIPMENT_DESC_OVERRIDE_STRING_ID_PREFIX
EQUIPMENT_DESC_OVERRIDE = "equipment-description-override-v1"
#: 补丁只会拼出这三种键(ID 是 int 的十进制串,无前导 0);ASCII 数字,fullmatch 不放过尾部换行。
EQUIPMENT_DESC_OVERRIDE_KEY_RE = re.compile(
    r"desc_override_equipment_(?:[1-9][0-9]*|enhancement_[1-9][0-9]*(?:_final)?)")


def panel_override_capability(key: str) -> str | None:
    """custom_ability_string 的这个键需要哪个面板覆盖 capability(不是覆盖行则 None)。"""
    key = (key or "").strip()
    if not key.startswith(PANEL_OVERRIDE_KEY_PREFIX):
        return None
    if key.startswith(EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX):
        return EQUIPMENT_DESC_OVERRIDE
    string_id = key[len(PANEL_OVERRIDE_KEY_PREFIX):]
    if string_id.startswith(PANEL_OVERRIDE_V1_STRING_ID_PREFIX):
        return PANEL_OVERRIDE_V1
    return PANEL_OVERRIDE_V2


def equipment_desc_override_key_problems(key: str) -> list[str]:
    """带装备覆盖前缀、却不是补丁会拼出的键形 → 永远读不到(惰性死行)。其他键不归这里管。"""
    if not (key or "").strip().startswith(EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX):
        return []
    if EQUIPMENT_DESC_OVERRIDE_KEY_RE.fullmatch(key):
        return []
    return [f"custom_ability_string 键 {key!r} 带装备覆盖前缀但不合键形 "
            "desc_override_equipment_<id> / _enhancement_<id> / _enhancement_<id>_final(客户端永远读不到)"]


# ────────── 装备强化外观(client-patch/equipment-enhanced-look)的键与值门禁 ──────────
#
# 补丁在两个单方法里查 custom_ability_string,键尾都是**图标路径**(客户端逐字拼接):
#   enhanced_pixelart_tier2_<pixelart0 图标路径>   值 "<等级>,<路径>"
#     EquipmentEnhancementLogic.getPixelart 在原方法已给出 Some(pixelart0) 时,强化等级 >= <等级>
#     改给 Some(<路径>)(第二图标档;唯一消费方 getPixelArtPathWithEnhancement,约 30 处视图跟随)。
#     客户端判据:恰好一个逗号;等级满足 String(int(s)) === s;路径非空;否则静默落回 pixelart0。
#     值含逗号:写表时这一格必须带引号(csv.writer 的 QUOTE_MINIMAL 自动加,客户端 format.csv.Reader
#     按引号读、逗号保留)。没加引号 = 客户端只读到 "<等级>" 一格 → 静默不生效,所以门禁按「一行一格」判。
#   enhanced_frame_override_<缩略图图标路径>        值 "<背景图路径>"
#     ItemThumbnailView.setRarity 在强化态(enhanced=true)hideRarity + replaceBackgroundImage(值)
#     (与称号缩略图同一通路,144×144 不透明 PNG 原尺寸显示)。编成装备槽不走这里,见下一个键。
#   enhanced_party_frame_override_<编成槽图标路径>  值 "<框图路径>"
#     (client-patch/equipment-enhanced-party-frame,**独立** capability equipment-enhanced-party-frame-v1)
#     PartyItemThumbnailView.updateEnhancedEffectAnimation 在强化态把该图(72×72 RGBA,套 rarity 容器的矩阵)
#     放到 image 容器第 0 位并隐藏 rarity 容器(粉框);未命中 / 格子复用时恢复。只装 v1 的客户端不读这个键,
#     所以它不能归到 equipment-enhanced-look-v1,否则只装 v1 的接收端会被误判为支持。
#   rarity_frame_override_<缩略图图标路径>          值 "<底色图路径>"
#     (client-patch/item-rarity-frame-override,**独立** capability item-rarity-frame-override-v1,叠在 v1 之上)
#     ItemThumbnailView.setRarity 在**非**强化态(enhanced=false)hideRarity + replaceBackgroundImage(值),
#     任何物品(不限装备)的品质底色换成该图;强化态仍归 v1 的 enhanced_frame_override_,两键互不回退。
#     只装 v1 / 编成槽框的客户端不读这个键,所以它不能归到那两个 capability。
# 行为型(cosmetic):没打补丁的客户端根本不读这些键,显示原图标与粉框、不崩,数据可以先于 APK 发布。
# 所以 required_client_capabilities 只报 capability;键/值形状错误由 enhanced_look_problems 报。
# 值指向的 PNG 必须随同一条发布边下发(缺图 = 客户端取图失败)—— 本模块不碰 store,由发布方核对。
EQUIPMENT_ENHANCED_LOOK = "equipment-enhanced-look-v1"
EQUIPMENT_ENHANCED_PARTY_FRAME = "equipment-enhanced-party-frame-v1"
ENHANCED_PIXELART_TIER2_KEY_PREFIX = "enhanced_pixelart_tier2_"
ENHANCED_FRAME_OVERRIDE_KEY_PREFIX = "enhanced_frame_override_"
ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX = "enhanced_party_frame_override_"
ITEM_RARITY_FRAME_OVERRIDE = "item-rarity-frame-override-v1"
ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX = "rarity_frame_override_"
#: equipment-enhanced-look-v1 的两个前缀(v1 补丁读的键)。
ENHANCED_LOOK_KEY_PREFIXES = (ENHANCED_PIXELART_TIER2_KEY_PREFIX, ENHANCED_FRAME_OVERRIDE_KEY_PREFIX)
#: 外观族全部前缀 → capability(四个前缀互不为前缀,一个键至多归一个补丁)。
ENHANCED_LOOK_PREFIX_CAPABILITIES = {
    ENHANCED_PIXELART_TIER2_KEY_PREFIX: EQUIPMENT_ENHANCED_LOOK,
    ENHANCED_FRAME_OVERRIDE_KEY_PREFIX: EQUIPMENT_ENHANCED_LOOK,
    ENHANCED_PARTY_FRAME_OVERRIDE_KEY_PREFIX: EQUIPMENT_ENHANCED_PARTY_FRAME,
    ITEM_RARITY_FRAME_OVERRIDE_KEY_PREFIX: ITEM_RARITY_FRAME_OVERRIDE,
}
#: 客户端资源路径:ASCII 段以 "/" 相连;无空白、逗号、引号、换行、扩展名,无首尾 "/"。
ENHANCED_LOOK_PATH_RE = re.compile(r"[A-Za-z0-9_\-]+(?:/[A-Za-z0-9_\-]+)*")
#: 第二图标档的值:规范十进制正整数(1–999999999,远小于 int32 上限,客户端 int() 不回绕)+ 逗号 + 路径。
ENHANCED_TIER2_VALUE_RE = re.compile(r"([1-9][0-9]{0,8}),(" + ENHANCED_LOOK_PATH_RE.pattern + r")")


def _enhanced_look_prefix(key: str) -> str | None:
    raw = (key or "").strip()
    return next((p for p in ENHANCED_LOOK_PREFIX_CAPABILITIES if raw.startswith(p)), None)


def enhanced_look_capability(key: str) -> str | None:
    """custom_ability_string 的这个键是否是外观族的键:是则返回它需要的 capability
    (enhanced_pixelart_tier2_* / enhanced_frame_override_* → equipment-enhanced-look-v1,
    enhanced_party_frame_override_* → equipment-enhanced-party-frame-v1,
    rarity_frame_override_* → item-rarity-frame-override-v1)。"""
    prefix = _enhanced_look_prefix(key)
    return ENHANCED_LOOK_PREFIX_CAPABILITIES[prefix] if prefix else None


def enhanced_look_problems(key: str, value: str | None = None) -> list[str]:
    """外观族键的键形与值形(value=None 只查键)。其他键不归这里管,返回空。

    键尾必须是合法图标路径(客户端按 itemImagePath / pixelart0.value / 编成槽 imagePath 逐字拼接,
    带空白的键永远查不到);值必须非空、无换行;第二图标档的值必须是 "<正整数>,<路径>",
    强化框、编成槽框与品质底色的值必须是一个路径。
    """
    raw = key or ""
    prefix = _enhanced_look_prefix(raw)
    if prefix is None:
        return []
    problems = []
    tail = raw[len(prefix):] if raw.startswith(prefix) else None
    if tail is None or not ENHANCED_LOOK_PATH_RE.fullmatch(tail):
        problems.append(f"custom_ability_string 键 {key!r} 的键尾不是图标路径 {ENHANCED_LOOK_PATH_RE.pattern}"
                        "(客户端按图标路径逐字拼键,永远读不到)")
    if value is None:
        return problems
    if not isinstance(value, str) or value == "":
        problems.append(f"custom_ability_string[{key!r}] 的值为空(客户端当作未设置)")
    elif "\n" in value or "\r" in value:
        problems.append(f"custom_ability_string[{key!r}] 的值含换行: {value!r}")
    elif prefix == ENHANCED_PIXELART_TIER2_KEY_PREFIX:
        if not ENHANCED_TIER2_VALUE_RE.fullmatch(value):
            problems.append(f"custom_ability_string[{key!r}] 的值 {value!r} 不是 \"<正整数等级>,<图标路径>\""
                            "(客户端要求恰好一个逗号、等级是规范十进制整数、路径非空,否则静默不生效)")
    elif not ENHANCED_LOOK_PATH_RE.fullmatch(value):
        problems.append(f"custom_ability_string[{key!r}] 的值 {value!r} 不是一个图标路径 {ENHANCED_LOOK_PATH_RE.pattern}")
    return problems


# ────────── 装备行为键(觉醒专属素材 / 装备列表置顶)的键与值门禁 ──────────
#
# 两个补丁都按装备 ID 查 custom_ability_string,键尾是 int 的十进制串(客户端 "前缀" + id 逐字拼接,
# 无前导 0、无符号、无空白):
#   awakening_material_<装备ID>   值 "<道具ID>"
#     (client-patch/equipment-awakening-material,capability equipment-awakening-material-v1)
#     OwnedEquipmentLogic.getUseableAwakingCrystal 在没有重复本体时:行存在 = 这件装备受限,只提供值所指的道具
#     (规范十进制正整数、道具表有行、持有 > 0、在有效期内),否则 None,**绝不回落星铁钢**;表没加载 / 没有这一行
#     = 原生(按稀有度提供星铁钢)。没打补丁的客户端不读这些行,受限装备重复数为 0 时仍提供星铁钢,
#     服务端白名单(assets/equipment_awakening_material.json)返回 400 —— 静默失效(semantic),发布门禁拒绝。
#   equipment_sort_pin_<装备ID>   值 "<置顶序号>"
#     (client-patch/equipment-sort-pin,capability equipment-sort-pin-v1)
#     EquipmentListScene.compareByEquipmentStatus / EquipmentSelectThumbnailListRepository.sortByRarity 入口:
#     两件都有合法序号且不等 → 序号升序;只有一件有 → 它在前;其余(含序号相等、值不合法)原生顺序。
#     没打补丁的客户端不读,显示原生顺序、不崩 —— 行为型(cosmetic),数据可以先于 APK 发布。
# 值都必须是规范十进制正整数(客户端判据 String(int(s)) === s 且 int(s) > 0;门禁收紧到 1–999999999,
# 9 位以内不触 int32 回绕)。键尾装备 ID 是否存在、道具 ID 是否存在由数据构建器对照 live 表判定(本模块不碰 store)。
EQUIPMENT_AWAKENING_MATERIAL = "equipment-awakening-material-v1"
EQUIPMENT_SORT_PIN = "equipment-sort-pin-v1"
AWAKENING_MATERIAL_KEY_PREFIX = "awakening_material_"
EQUIPMENT_SORT_PIN_KEY_PREFIX = "equipment_sort_pin_"
#: 装备行为键前缀 → capability(两个前缀互不为前缀,也不与面板覆盖 / 外观族前缀相互包含)。
EQUIPMENT_KEY_PREFIX_CAPABILITIES = {
    AWAKENING_MATERIAL_KEY_PREFIX: EQUIPMENT_AWAKENING_MATERIAL,
    EQUIPMENT_SORT_PIN_KEY_PREFIX: EQUIPMENT_SORT_PIN,
}
#: 规范十进制正整数 1–999999999(ASCII 数字;fullmatch 不放过尾部换行)。
CANONICAL_POSITIVE_INT_RE = re.compile(r"[1-9][0-9]{0,8}")


def _equipment_key_prefix(key: str) -> str | None:
    raw = (key or "").strip()
    return next((p for p in EQUIPMENT_KEY_PREFIX_CAPABILITIES if raw.startswith(p)), None)


def equipment_key_capability(key: str) -> str | None:
    """custom_ability_string 的这个键是否是装备行为键:是则返回它需要的 capability
    (awakening_material_* → equipment-awakening-material-v1,equipment_sort_pin_* → equipment-sort-pin-v1)。"""
    prefix = _equipment_key_prefix(key)
    return EQUIPMENT_KEY_PREFIX_CAPABILITIES[prefix] if prefix else None


def equipment_key_problems(key: str, value: str | None = None) -> list[str]:
    """装备行为键的键形与值形(value=None 只查键)。其他键不归这里管,返回空。

    键尾必须是装备 ID 的规范十进制串(客户端按 int 拼键,带前导 0 / 空白 / 符号的键永远查不到);
    值必须是规范十进制正整数 1–999999999(觉醒素材:客户端判「受限但值坏」→ 不提供任何道具;
    置顶:值坏 → 这件不置顶,都不崩,但都不是作者要的效果)。
    """
    raw = key or ""
    prefix = _equipment_key_prefix(raw)
    if prefix is None:
        return []
    problems = []
    tail = raw[len(prefix):] if raw.startswith(prefix) else None
    if tail is None or not CANONICAL_POSITIVE_INT_RE.fullmatch(tail):
        problems.append(f"custom_ability_string 键 {key!r} 的键尾不是装备 ID 的规范十进制串 "
                        f"{CANONICAL_POSITIVE_INT_RE.pattern}(客户端按 int 逐字拼键,永远读不到)")
    if value is None:
        return problems
    if not isinstance(value, str) or not CANONICAL_POSITIVE_INT_RE.fullmatch(value):
        what = "道具 ID" if prefix == AWAKENING_MATERIAL_KEY_PREFIX else "置顶序号"
        problems.append(f"custom_ability_string[{key!r}] 的值 {value!r} 不是规范十进制正整数{what} "
                        f"{CANONICAL_POSITIVE_INT_RE.pattern}(客户端 String(int(s)) === s 且 > 0 才认)")
    return problems


def required_client_capabilities(kind: str, row: list[str]) -> list[str]:
    """这一行需要哪些客户端补丁 capability 才不会 C7050(官方 APK 上为空)。

    只看**该触发模式下客户端真的会解析**的那个内容块 —— 瞬发行不读 during_content、
    持续行不读 instant_content,否则从别的模式克隆行时留下的残值会被判成需要补丁。
    补丁没有扩展该表解析器的构造由 client_legality_problems 报硬错，不将已有
    capability 误报成可修复它的依赖；本函数返回空不代表这一行合法。

    `kind == "custom_ability_string"` 走另一条判据:row[0] 是外层键,报出让
    `desc_override_*` 行真正生效所需的面板覆盖 capability(缺补丁不崩,只是不生效):
    `desc_override_equipment_*` → equipment-description-override-v1(装备详情覆盖),
    `desc_override_fox_oracle_autumn*` → v1,其余 `desc_override_*` → v2;
    `enhanced_pixelart_tier2_*` / `enhanced_frame_override_*` → equipment-enhanced-look-v1(装备强化外观),
    `enhanced_party_frame_override_*` → equipment-enhanced-party-frame-v1(编成装备槽强化框);
    `rarity_frame_override_*` → item-rarity-frame-override-v1(物品品质底色覆盖,非强化态);
    `awakening_material_*` → equipment-awakening-material-v1(觉醒专属素材,缺补丁 = 静默失效),
    `equipment_sort_pin_*` → equipment-sort-pin-v1(装备列表置顶)。
    键形是否合法另由 equipment_desc_override_key_problems / enhanced_look_problems / equipment_key_problems 判。
    """
    if kind == CUSTOM_ABILITY_STRING_KIND:
        key = row[0] if row else ""
        capability = (panel_override_capability(key) or enhanced_look_capability(key)
                      or equipment_key_capability(key))
        return [capability] if capability else []
    blocks = wf_describe.layout(kind)["blocks"]
    mode_col = int(blocks["precondition1"]) - 1
    mode = (row[mode_col] if mode_col < len(row) else "").strip()
    parsed = set(TRIGGER_MODE_BLOCKS.get(mode, ()))
    needed: list[str] = []
    for block, gated in CLIENT_PATCH_CONTENT_KINDS.items():
        if block not in parsed:
            continue
        base = int(blocks[block])
        value = (row[base] if base < len(row) else "").strip()
        if not patch_parser_supported(kind, block, value):
            continue
        capability = gated.get(value)
        if capability is not None and capability not in needed:
            needed.append(capability)
    # 解析器扩展本身也是依赖：装备两表的 423 只有 equipment-rules 补丁认，1047 读到仍 C7050
    for capability in patch_parser_capabilities(kind, row, blocks, parsed):
        if capability not in needed:
            needed.append(capability)
    return needed

# ─────────────────── 「声明即必填」通用律(2026-08-28 第二轮收口) ───────────────────
#
# 上面那条 PRECONDITION_KINDS_NEED_NEXT_COL 白名单、以及 instant_content 的
# multiply_trigger 专项规则,都是同一条定律的特例:
#
#     kind 在 wf_describe.enum_map()['cases'][block] 里声明了某个字段
#     ⇒ 客户端在这一行的分支上一定会调该字段的 parseAt
#     ⇒ 若该 parseAt 没有 `if(v == "")` 分支,则该列留空就是缺陷。
#
# `cases` 本身是分支感知的(precondition kind 202/203 的 fields 是空的,所以主/副位
# 门留空反而正确 —— 通用律不会误伤它们),因此不需要再维护 kind 白名单。
#
# 逐个 parseAt 体的字面量集合取自反编译产物
# 弹国服/scripts/pinball/master/generated/{AbilityValues,LeaderAbilityValues}.as,
# 两张表 55 个 (块, 字段) 判定**逐条一致**;结论只有三类:
#   throw      —— 无 '(None)' 分支且落 else 就 `throw new ClientError(7050)`:
#                 空串 = 打开「查看角色」即崩。
#                 命中 precondition.trigger_puller / instant_trigger.trigger_puller /
#                 during_*.trigger_puller / instant_content.target /
#                 during_content.target / instant_content.multiply_trigger。
#   parseInt   —— `Option.Some(Std.parseInt(v))`:空串给出 Some(null),面板渲染出
#                 破碎文案,战斗里与 NaN 比大小恒假(词条要么不触发要么不耗尽)。
#   safe-empty —— parseAt 体里有显式 `if(v == "")` 分支,空串合法。
#
# 正向对照(2026-08-28,CN store 1.4.559 全表 4488 ability 行 + 1296 leader 行):
# 本规则在**官方行上 0 误报**;命中的只有自制角色的行。
BLOCK_FIELD_EMPTY_OK = frozenset({
    # parseAt 体里有 `if(v == "")` 分支
    "character_groups", "powerflip_override",
    # 不解析成数值也不 throw(string_id 另有 629 专项规则;
    # by_each_trigger_puller 另有 true/false 专项规则)
    "string_id", "action_path", "by_each_trigger_puller",
})

# 块名 → enum_map()['cases'] 的键。during_accumulation_trigger 用的是
# InstantAbilityTriggerMasterValue,与 instant_trigger 同构。
BLOCK_CASE_KEY = {
    "precondition1": "precondition",
    "precondition2": "precondition",
    "precondition3": "precondition",
    "instant_trigger": "instant_trigger",
    "during_accumulation_trigger": "instant_trigger",
    "during_trigger": "during_trigger",
    "instant_content": "instant_content",
    "during_content": "during_content",
}
# 块名 → enum_map()['block_fields'] 的键(三个前置槽共用一张字段表)。
BLOCK_FIELDS_KEY = {
    "precondition1": "precondition",
    "precondition2": "precondition",
    "precondition3": "precondition",
}
# 触发模式 → 客户端构造函数实际解析的块
# (模式 2/开幕只解析 opening 块,precondition 都不读)。
TRIGGER_MODE_BLOCKS = {
    "0": ("precondition1", "precondition2", "precondition3",
          "instant_trigger", "instant_content"),
    "1": ("precondition1", "precondition2", "precondition3",
          "during_accumulation_trigger", "during_trigger", "during_content"),
    "2": (),
}


def _block_field_entry_offsets(block_fields_key: str) -> dict[str, int]:
    """case 字段名 → 该字段在块内的**入口列偏移**。

    复合字段(threshold / strength / frame / number / target …)在 block_fields 里
    摊成多列(threshold.power1 / threshold.first_max …),但客户端只从最小偏移那一列
    进入解析函数,子列由该函数按分支自行决定读不读 —— 所以只校验入口列。
    (反例:target.multiball_group_id 官方 2868 行留空,按子列校验会全表误报。)
    """
    entries: dict[str, int] = {}
    for offset, field, _label in wf_describe.enum_map()["block_fields"][block_fields_key]:
        offset = int(offset)
        name = field.split(".", 1)[0]
        if name == "kind":
            continue
        if name not in entries or offset < entries[name]:
            entries[name] = offset
    return entries


def declared_block_field_problems(kind: str, row: list[str]) -> list[str]:
    """「声明即必填」:kind 声明了的块字段,入口列不许留空。

    覆盖 precondition1-3 / instant_trigger / during_accumulation_trigger /
    during_trigger / instant_content / during_content 七个块;列号全部走
    wf_describe.layout(kind)['blocks'] + block_fields 偏移,不写死。
    """
    layout = wf_describe.layout(kind)
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    cases = wf_describe.enum_map()["cases"]
    mode_col = blocks["precondition1"] - 1
    mode = (row[mode_col] if mode_col < len(row) else "").strip()

    probs: list[str] = []
    for block in TRIGGER_MODE_BLOCKS.get(mode, ()):
        base = blocks[block]
        block_kind = (row[base] if base < len(row) else "").strip()
        case = cases[BLOCK_CASE_KEY[block]].get(block_kind)
        if case is None:          # '(None)' 哨兵或非法 kind,另有规则管
            continue
        offsets = _block_field_entry_offsets(BLOCK_FIELDS_KEY.get(block, block))
        for field in sorted(case["fields"]):
            if field in BLOCK_FIELD_EMPTY_OK or field not in offsets:
                continue
            col = base + offsets[field]
            if (row[col] if col < len(row) else "").strip():
                continue
            probs.append(
                f"c{col} {block}.{field} 留空,但 kind={block_kind} "
                f"({case['ctor']})声明了该字段 —— 客户端 parseAt{col} 必然读到它"
                "(无空串分支;trigger_puller/target/multiply_trigger 类直接 C7050,"
                "其余落 Std.parseInt('')=NaN)"
            )
    return probs


def character_stance_problems(row: list[str]) -> list[str]:
    """character.orderedmap 单行的 stance 合法性(角色详情页 C8601 门禁)。"""
    v = (row[CHARACTER_STANCE_COL] if CHARACTER_STANCE_COL < len(row) else "").strip()
    if v not in CHARACTER_STANCES:
        return [
            f"c{CHARACTER_STANCE_COL} stance={v!r} 不属于运行时 6 键"
            f"({'/'.join(sorted(CHARACTER_STANCES))}),角色详情页 C8601"
        ]
    return []

def client_legality_problems(kind: str, row: list[str]) -> list[str]:
    """客户端字段与说明组合硬规则(C7050/7101/C10010 打开角色页即崩):
    枚举列无空串分支,前置1-3/触发/内容 kind 必须数字;instant_precontent 哨兵 '(None)';
    during_accumulation_trigger 哨兵 '(None)';even_if_owner_dead 必须 true/false;
    瞬发内容 kind 声明 multiply_trigger 时该列必须是 '(None)' 或 0/1/2/3(2026-08-28 实锤)。"""
    if kind == "action_skill":
        from wf_client_skill_legality import action_skill_problems
        return action_skill_problems(row)
    lay = wf_describe.layout(kind)
    B = {k: int(v) for k, v in lay["blocks"].items()}
    enum_map = wf_describe.enum_map()
    cases = enum_map["cases"]
    enums = enum_map["enums"]
    block_offsets = {
        block: {field: int(offset) for offset, field, _label in fields}
        for block, fields in enum_map["block_fields"].items()
    }
    tcol = B["precondition1"] - 1


    def cell(i):
        return (row[i] if i < len(row) else "").strip()

    def is_num(v):
        return bool(v) and v.lstrip("-").isdigit()

    probs = []
    if kind == "ability":
        statue = (row[2] if 2 < len(row) else "").strip()
        if statue and statue not in ABILITY_STATUE_GROUPS:
            probs.append(
                f"c2 雕像组={statue!r} 不属于 ability_statue_group 的 25 个键"
                "(玛纳板 C8601)"
            )
    if kind in ("ability", "leader_ability"):
        # V14 面板覆盖探测 "desc_override_" + c0;以 equipment_ 开头会落进装备详情覆盖的命名空间
        string_id = cell(0)
        if string_id.startswith(EQUIPMENT_DESC_OVERRIDE_STRING_ID_PREFIX):
            probs.append(
                f"c0 string_id={string_id!r} 以 {EQUIPMENT_DESC_OVERRIDE_STRING_ID_PREFIX!r} 开头:"
                f"面板覆盖键会与装备详情覆盖 {EQUIPMENT_DESC_OVERRIDE_KEY_PREFIX}* 相撞"
            )
    tmode = cell(tcol)
    if tmode not in ("0", "1", "2"):
        return [f"c{tcol} 触发模式={tmode!r},须为 0(瞬发)/1(持续)/2(开幕)"]
    # 开幕行(2)客户端只 parseAt123/121,precondition 列不解析——不校验(2026-08-26 审查)
    for p in (() if tmode == "2" else ("precondition1", "precondition2", "precondition3")):
        v = cell(B[p])
        if not is_num(v):
            probs.append(f"c{B[p]} {p}.kind={v!r} 须为数字(无条件填 0;空串=客户端C7050)")
        elif v not in enums["AbilityPreconditionMasterValue"]:
            probs.append(
                f"c{B[p]} {p}.kind={v!r} "
                "不属于 AbilityPreconditionMasterValue 枚举域"
            )
        elif v in PRECONDITION_KINDS_NEED_NEXT_COL and cell(B[p] + 1) == "":
            # 2026-08-26 实锤:kind 144 的 c7(kind 后一列)留空 = parseAt7 C7050;
            # 已知同病 kind 见集合;202/203 留空反而正确,不能一刀切。
            probs.append(
                f"c{B[p] + 1} {p}.kind={v} 的后续列留空(parseAt{B[p] + 1} C7050,填 0)"
            )
    if tmode == "0":
        for name, label in (("instant_trigger", "瞬发触发kind"),
                            ("instant_delay", "延迟"), ("instant_content", "瞬发效果kind")):
            v = cell(B[name])
            if not is_num(v):
                probs.append(f"c{B[name]} {label}={v!r} 须为数字(空串=客户端C7050)")
        v = cell(B["instant_precontent"])
        if v != "(None)" and not is_num(v):
            probs.append(f"c{B['instant_precontent']} instant_precontent={v!r} 须为 '(None)' 或数字")
        elif v != "(None)" \
                and v not in enums["InstantAbilityPrecontentMasterValue"]:
            probs.append(
                f"c{B['instant_precontent']} instant_precontent={v!r} "
                "不属于 InstantAbilityPrecontentMasterValue 枚举域"
            )
        trigger_kind = cell(B["instant_trigger"])
        if is_num(trigger_kind) \
                and trigger_kind not in enums["InstantAbilityTriggerMasterValue"]:
            probs.append(
                f"c{B['instant_trigger']} 瞬发触发kind={trigger_kind!r} "
                "不属于 InstantAbilityTriggerMasterValue 枚举域"
            )
        content_kind = cell(B["instant_content"])
        if is_num(content_kind) and content_kind not in cases["instant_content"]:
            probs.append(
                f"c{B['instant_content']} 瞬发效果kind={content_kind!r} "
                "不属于 InstantAbilityContentMasterValue 枚举域"
            )
        content_case = cases["instant_content"].get(content_kind)
        if content_case is not None \
                and "by_each_trigger_puller" in content_case["fields"]:
            bool_col = (
                B["instant_content"]
                + block_offsets["instant_content"]["by_each_trigger_puller"]
            )
            bool_value = cell(bool_col)
            if bool_value.lower() not in ("true", "false"):
                probs.append(
                    f"c{bool_col} by_each_trigger_puller={bool_value!r} "
                    "须为 true/false(否则C7101)"
                )
        if (content_case is not None
                and "multiply_trigger" in content_case["fields"]):
            # 2026-08-28 实锤(白虎 169994 ability 1699941 三条记录,kind 461):
            # AbilityValues.parseAt75 只认 "(None)" 与 "0"/"1"/"2"/"3",落到 else 分支
            # 就是 `throw new ClientError(7050,"不存在的构造函数。")`(AbilityValues.as:6822-6866,
            # LeaderAbilityValues.parseAt73 / AbilitySoulValues.parseAt72 同构),
            # 空串 = 打开角色详情页即崩。41 个 instant_content kind 声明该字段;
            # 官方 CN store 里这些 kind 的瞬发行 302/302 全部填了值(294 个 "0")。
            mt_col = (
                B["instant_content"]
                + block_offsets["instant_content"]["multiply_trigger"]
            )
            mt_value = cell(mt_col)
            if (mt_value != "(None)"
                    and mt_value
                    not in enums["InstantAbilityMultiplyTriggerMasterValue"]):
                probs.append(
                    f"c{mt_col} multiply_trigger={mt_value!r} 须为 '(None)' 或 "
                    "InstantAbilityMultiplyTriggerMasterValue 枚举域"
                    f"({'/'.join(sorted(enums['InstantAbilityMultiplyTriggerMasterValue']))})"
                    f";空串=parseAt{mt_col} C7050"
                )
    elif tmode == "1":
        v = cell(B["during_accumulation_trigger"])
        if v != "(None)" and not is_num(v):
            probs.append(f"c{B['during_accumulation_trigger']} 累积触发={v!r} 须为 '(None)' 或数字")
        elif v != "(None)" \
                and v not in enums["InstantAbilityTriggerMasterValue"]:
            probs.append(
                f"c{B['during_accumulation_trigger']} 累积触发={v!r} "
                "不属于 InstantAbilityTriggerMasterValue 枚举域"
            )
        v = cell(B["during_trigger"])
        if not is_num(v):
            probs.append(f"c{B['during_trigger']} 持续触发kind={v!r} 须为数字")
        elif v not in enums["DuringAbilityTriggerMasterValue"]:
            probs.append(
                f"c{B['during_trigger']} 持续触发kind={v!r} "
                "不属于 DuringAbilityTriggerMasterValue 枚举域"
            )
        else:
            trigger_case = cases["during_trigger"].get(v)
            if trigger_case is not None \
                    and "trigger_puller" in trigger_case["fields"]:
                puller_col = (
                    B["during_trigger"]
                    + block_offsets["during_trigger"]["trigger_puller"]
                )
                puller = cell(puller_col)
                if puller not in enums["DuringAbilityTriggerPullerMasterValue"]:
                    probs.append(
                        f"c{puller_col} during_trigger.trigger_puller={puller!r} "
                        "不属于 DuringAbilityTriggerPullerMasterValue 枚举域"
                    )
        v = cell(B["even_if_owner_dead"])
        if v.lower() not in ("true", "false"):
            probs.append(f"c{B['even_if_owner_dead']} even_if_owner_dead={v!r} 须为 true/false(否则C7101)")
        v = cell(B["during_content"])
        if not is_num(v):
            probs.append(f"c{B['during_content']} 持续效果kind={v!r} 须为数字")
        elif v not in cases["during_content"]:
            probs.append(
                f"c{B['during_content']} 持续效果kind={v!r} "
                "不属于 CommonAbilityContentMasterValue 枚举域"
            )
    else:
        v = cell(B["opening"])
        if not is_num(v):
            probs.append(f"c{B['opening']} 开幕kind={v!r} 须为数字")
        elif v not in enums["OpeningAbilityMasterValue"]:
            probs.append(
                f"c{B['opening']} 开幕kind={v!r} "
                "不属于 OpeningAbilityMasterValue 枚举域"
            )
    # 「声明即必填」通用律。上面的 PRECONDITION_KINDS_NEED_NEXT_COL 与
    # multiply_trigger 两条专项规则是它的特例,保留是因为它们的报错文案更具体。
    probs.extend(patch_parser_scope_problems(kind, row, B, TRIGGER_MODE_BLOCKS[tmode]))
    probs.extend(declared_block_field_problems(kind, row))
    from wf.rules.instant_content import instant_option_value_problems
    probs.extend(instant_option_value_problems(kind, row))
    probs.extend(description_compatibility_problems(kind, row))
    probs.extend(ability_element_column_problems(kind, row))
    probs.extend(battle_rule_problems(kind, row, B))
    return probs


# ---------------------------------------------------------------------------
# 词条表 element 列(ElementTargetKind,**1-based**)
#
# 逆向依据(2026-08-29,反编译客户端):
#   * 取值域 = `ElementTargetKind`,不是 `ElementKind`:
#     pinball/common/data/character/condition/_ElementTargetKind/
#     ElementTargetKind_Impl_.as:49-71 `toElementKind`
#         0 -> throw "INTERNAL ERROR @ 0c352cfe-0aba-4d3f-b002-3cd590cbfee2"
#         1->0(火) 2->1(水) 3->2(雷) 4->3(风) 5->4(光) 6->5(暗)
#         其余 -> `default: return;`(AS3 int 函数 = 悄悄返回 0 = 火)
#     同文件 :27-47 `fromElementKind` 是它的逆;ElementTargetKindTools.as
#     `colorlessableIncludes` 里 0 = 「全属性,恒真」。
#   * 反向佐证(同一列被两族 kind 共用):
#     MemberAbilityTotalizerImpl.as:1000-1008 `getElementResistanceToConditionEnemies`
#     先查 key 0(全属性),再 `fromElementKind(受击属性)` 查 1..6 —— 也就是说
#     ElementResistanceTo*Enemy 族(instant 630-658 / during 351-379)的 element
#     列同样是 1-based,且 0 在这族里是合法的「全属性」。
#   * 列号(四张表逐一对过生成解析器,全中):
#     ability c73=parseAt73 / leader_ability c71=parseAt71 /
#     ability_soul c70=parseAt70 / ex_ability c72=parseAt72 /
#     equipment_enhancement_ability c73=parseAt73。
#
# 官方正向对照(2026-08-29,`.cdn/cn/archive-common-full` 的 1.4.0 全量,
# ability 2968 键 + leader_ability 496 键 = 5012 行):声明 element 的行**只有 1 条**,
# `ability:1612011` 记录[1](蕾薇 stella_copy_4anv):c27=198 UnisonWithMain、
# c36=White、c47=720、**c73=5**。持有者 161201 自身 c3=5(内部 ElementKind 5=暗)。
# 按 0-based 读 5=暗=自己 ⇒ 这条词条是空转;按 1-based 读 5=光 ⇒ 与「主位须为光」
# 严丝合缝。**1-based 定案**。(链上另外几条 720 都是我们自己发的:
# 3610031#2 / 1610041#3 首见于 1.4.60 的 mod 包,1299991#0 是赛瑞斯。)
#
# 720 OverrideCharacterElement 的两条硬规则:
#   1. 空串 / 0 = `Std.parseInt("")` -> NaN -> int -> 0 -> `toElementKind(0)` **抛异常**;
#   2. 只能挂在瞬发块:MemberAbilityTotalizerImpl.as:2459-2461
#      `throw new ClientError(10109,"DuringのOverrideCharacterElementは禁止")`。
#      (during 侧枚举 CommonAbilityContentMasterValue 里根本没有这个构造,
#       所以数据层写不出来,这里不再重复判。)
# 「改成自己原本的属性」= `BattleCharacterLogic.getElement()` 返回值不变 = 纯空转,
# 也是把 0-based 值直接填进来时最典型的症状,故在给出持有者属性时一并抓。
# ---------------------------------------------------------------------------

ELEMENT_TARGET_KIND_ALL = 0        # 0 = 全属性(仅抗性族合法)
ELEMENT_TARGET_KIND_MIN = 0
ELEMENT_TARGET_KIND_MAX = 6
# 该 kind 的 element 不接受「全属性」哨兵(0 会在 toElementKind 里抛异常)
ELEMENT_TARGET_KIND_NO_ALL = frozenset({"720"})
ELEMENT_CONTENT_BLOCKS = ("instant_content", "during_content")


def _element_entry(block: str) -> int | None:
    for offset, field, _label in wf_describe.enum_map()["block_fields"][block]:
        if field == "element":
            return int(offset)
    return None


def ability_element_column_problems(
    kind: str, row: list[str], character_element: int | None = None,
) -> list[str]:
    """词条表 element 列的取值域 + 720 专项规则。

    `character_element` 传 master/character c3(0-based 内部 ElementKind)时,
    额外抓 720「覆盖成自己原本的属性」这个空转签名。
    """
    layout = wf_describe.layout(kind)
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    cases = wf_describe.enum_map()["cases"]
    # 只判**该触发模式下客户端真的会解析**的那个内容块:瞬发行不读 during_content、
    # 持续行不读 instant_content、开幕行两个都不读。否则从别的模式克隆行时留下的
    # 残值会被判成缺陷(客户端根本不看它)。
    mode_col = blocks["precondition1"] - 1
    mode = (row[mode_col] if mode_col < len(row) else "").strip()
    parsed = set(TRIGGER_MODE_BLOCKS.get(mode, ()))
    probs: list[str] = []
    for block in ELEMENT_CONTENT_BLOCKS:
        if block not in parsed:
            continue
        base = blocks.get(block)
        offset = _element_entry(block)
        if base is None or offset is None:
            continue
        block_kind = (row[base] if base < len(row) else "").strip()
        case = cases[block].get(block_kind)
        if case is None or "element" not in case["fields"]:
            continue
        col = base + offset
        raw = (row[col] if col < len(row) else "").strip()
        if not raw.isdigit():
            # 空串由「声明即必填」通用律报;这里只补一句 720 的后果
            if not raw and block_kind in ELEMENT_TARGET_KIND_NO_ALL:
                probs.append(
                    f"c{col} {block}.element 留空,kind={block_kind}"
                    f"({case['ctor']}):parseAt{col} 得 0,"
                    "ElementTargetKind.toElementKind(0) 直接抛 INTERNAL ERROR"
                )
            continue
        value = int(raw)
        if not (ELEMENT_TARGET_KIND_MIN <= value <= ELEMENT_TARGET_KIND_MAX):
            probs.append(
                f"c{col} {block}.element={value} 越界;ElementTargetKind 只有 "
                f"0(全)/1火/2水/3雷/4风/5光/6暗,越界落 toElementKind 的 "
                "default 分支(悄悄变成火)"
            )
            continue
        if value == ELEMENT_TARGET_KIND_ALL \
                and block_kind in ELEMENT_TARGET_KIND_NO_ALL:
            probs.append(
                f"c{col} {block}.element=0(全属性)不能用于 kind={block_kind}"
                f"({case['ctor']}):toElementKind(0) 抛 "
                "INTERNAL ERROR @ 0c352cfe-0aba-4d3f-b002-3cd590cbfee2"
            )
            continue
        if (character_element is not None
                and block_kind in ELEMENT_TARGET_KIND_NO_ALL
                and value - 1 == character_element):
            probs.append(
                f"c{col} {block}.element={value} 覆盖后仍是角色自身属性 "
                f"{character_element};element 列是 1-based(ElementTargetKind),"
                f"想换成内部元素 N 要写 N+1 —— 现在这条词条是空转"
            )
    return probs

# --- master/degree/degree.orderedmap(称号/铭牌)----------------------------
#
# 列布局取自 DegreeValues 构造器(scripts/pinball/master/generated/DegreeValues.as:36-48),
# 它按下标直读 param1[0..8],**九列一个不能少**:少列 → degree_image 读到 null →
# ViewAssetCache.readTexture 抛 C8601「指定的Key不存在。key=null」(同文件 :839)。
DEGREE_COLUMNS = {
    "string_id": 0,
    "display_order": 1,
    "name": 2,
    "kana": 3,
    "condition": 4,
    "category_id": 5,
    "icon_base_image": 6,
    "icon_dot_image": 7,
    "degree_image": 8,
}
DEGREE_NCOLS = 9

# 官方 1485/1485 行的取值(2026-08-27 全表统计,CN store 1.4.4xx):
# c6 恒 dynamic/degree/background、c7 恒 item/etc/degree、c8 恒 dynamic/degree/ 前缀。
# 这三条不是风格约定而是资源寻址:c8 会被 DegreeView 直接丢给 setTexture
# (DegreeView.as:172),加 ".png" 落到 store 的 sha1(逻辑路径+SALT) 位置;
# 前缀写错 = 该路径在 store 里根本不存在 = 铭牌加载不出来。
DEGREE_ICON_BASE_IMAGE = "dynamic/degree/background"
DEGREE_ICON_DOT_IMAGE = "item/etc/degree"
DEGREE_IMAGE_PREFIX = "dynamic/degree/"


def degree_row_problems(
    row: list[str],
    *,
    category_ids: frozenset[str] | set[str],
) -> list[str]:
    """master/degree/degree.orderedmap 单行的客户端硬规则。

    `category_ids` 传 degree_category 表的键集合:c5 指向不存在的分类时
    DegreeCategoryLogic 的 `values` 是 null(MasterMapBase.getByIndex 索引 <0 返回
    null,见 MasterMapBase.as:94-106),随后 get_name() 就是 AS3 空引用 F1009。
    """
    probs: list[str] = []
    if len(row) != DEGREE_NCOLS:
        probs.append(
            f"列数={len(row)},须为 {DEGREE_NCOLS}"
            "(DegreeValues 直读 param1[0..8];缺列 → degree_image=null → C8601)"
        )
        return probs

    def cell(name: str) -> str:
        return (row[DEGREE_COLUMNS[name]] or "").strip()

    for name, index in DEGREE_COLUMNS.items():
        if any(ch in (row[index] or "") for ch in ("\r", "\n")):
            probs.append(f"c{index} {name} 含换行,会撕碎 orderedmap 的 CSV 行")

    if not cell("string_id"):
        probs.append("c0 string_id 为空")
    order = cell("display_order")
    if not order.isdigit():
        probs.append(f"c1 display_order={order!r} 须为非负整数(列表排序键)")
    if not cell("name"):
        probs.append("c2 name 为空(称号列表/资料页显示空白)")

    category = cell("category_id")
    if not category.isdigit():
        probs.append(f"c5 category_id={category!r} 须为整数")
    elif category not in category_ids:
        probs.append(
            f"c5 category_id={category!r} 不在 degree_category 键集合"
            f"({'/'.join(sorted(category_ids, key=lambda k: int(k) if k.isdigit() else 0))})"
            ",DegreeCategoryLogic.values=null → get_name() 空引用 F1009"
        )

    base = cell("icon_base_image")
    if base != DEGREE_ICON_BASE_IMAGE:
        probs.append(
            f"c6 icon_base_image={base!r} 须为 {DEGREE_ICON_BASE_IMAGE!r}"
            "(官方 1485/1485 恒此值)"
        )
    dot = cell("icon_dot_image")
    if dot != DEGREE_ICON_DOT_IMAGE:
        probs.append(
            f"c7 icon_dot_image={dot!r} 须为 {DEGREE_ICON_DOT_IMAGE!r}"
            "(官方 1485/1485 恒此值)"
        )
    image = cell("degree_image")
    if not image.startswith(DEGREE_IMAGE_PREFIX):
        probs.append(
            f"c8 degree_image={image!r} 须以 {DEGREE_IMAGE_PREFIX!r} 开头"
            "(官方 1485/1485;别处 = store 里没有该 sha1 路径,铭牌加载不出)"
        )
    elif image == DEGREE_IMAGE_PREFIX:
        probs.append("c8 degree_image 只有前缀、没有文件名")
    elif "/" in image[len(DEGREE_IMAGE_PREFIX):]:
        probs.append(
            f"c8 degree_image={image!r} 多了一层子目录;官方全表都是 "
            f"{DEGREE_IMAGE_PREFIX}<name> 单层"
        )
    elif image.endswith(".png"):
        probs.append(
            f"c8 degree_image={image!r} 不能带扩展名"
            "(客户端 readTextureFile 自己补 .png,写死会变成 …png.png)"
        )
    return probs


INVOKE_SKILL_STRING_OFFSET = 23   # 文案键列 = instant_content 基址 + 23(ability 47→70,leader_ability 45→68)


def invoke_skill_string_problems(row: list[str],
                                 custom_string_keys: frozenset[str] | set[str],
                                 kind: str = "ability") -> list[str]:
    """kind 629(InvokeSkill)行的文案键(ability c70 / leader_ability c68)必须存在于
    custom_ability_string,否则角色详情页渲染描述时 MasterStringMap.get 抛 C8601
    (2026-08-26 魔王冲刺行实锤:发布 rebase 按 manifest tables[] outer_keys 合并,
    漏认领的键会被静默回滚)。列号按 `kind` 的布局表取:两表列位差 2,写死 47/70 会让
    队长表里的 629 行(基诺维冲刺、深渊之兽觉醒)整条漏检(2026-09-08 复核工作流抓出)。"""
    blocks = wf_describe.layout(kind)["blocks"]
    kind_col = int(blocks["instant_content"])
    sid_col = kind_col + INVOKE_SKILL_STRING_OFFSET

    def cell(i):
        return (row[i] if i < len(row) else "").strip()
    if cell(kind_col) != "629":
        return []
    sid = cell(sid_col)
    if not sid:
        return [f"c{sid_col} InvokeSkill string_id 为空(渲染描述 C8601)"]
    if sid not in custom_string_keys:
        return [f"c{sid_col} string_id={sid!r} 不在 custom_ability_string 中(C8601,"
                "并检查 manifest tables[] outer_keys 是否认领)"]
    return []


# ---------------------------------------------------------------------------
# 像素小人时间轴(character/<code>/pixelart/pixelart.timeline.amf3.deflate)
#
# 逆向依据(反编译客户端,2026-08-28):
#   * 序列名白名单:pinball/common/data/MasterConstants.as:76
#       SQUAD_MEMBER_REQUIRED_SEQUENCE_NAMES = [neutral, walk_back, walk_front,
#         skill_ready, kachidoki, into_coffin, ghost_raise, ghost_neutral, revive]
#     缺名字不会优雅降级 —— PlayheadTimeline.getSequenceByName 直接抛
#     "<name>は存在しないシーケンス名です"。
#   * kind → 控制码:flatomo/timeline/PlayheadTimeline.as:117-144
#       loop → end 帧 Goto(begin) / once → end 帧 Stop / pass → 无码,继续 +1 /
#       stop → begin..end 每帧 Stop
#     Playhead.advanceFrame(:565-597)没有控制码就 currentFrame += 1,
#     所以**最后一个序列**必须带终止码;否则播放头越过 totalFrames,
#     下一次 get_currentSequence()(:334-351,被 gotoAndPlayComplex 每帧调用)
#     扫不到任何序列 → 抛 "INTERNAL ERROR"。
#   * kachidoki:MemberImpl.as:2143-2150 置 kachidoking=true 后**永不复位**,
#     写成 once 会让胜利姿势停在最后一帧;官方 548/548 是 loop。
#   * hp_gauge / unit_body 两个 marker 对**队友**是死数据
#     (队友碰撞半径硬编码 30,MemberImpl.as:1606;血条锚点是常量,
#      MemberView.as:93-98;circles 的消费者只有敌人与关卡机关),
#     但官方 1151/1151 个 pixelart 时间轴都带,形状高度一致:
#       points  = [hp_gauge @1 -> (0,-10)]
#       circles = [unit_body,每序列一条,begin = 序列 begin + 1,
#                  neutral/walk_back/walk_front 为 (0,0,r=8.3),其余为空]
#     偏离官方形状不致命,但会让"跟官方比对"变成噪声,故一并检查。
# ---------------------------------------------------------------------------

PIXELART_REQUIRED_SEQUENCES = (
    "neutral", "walk_back", "walk_front", "skill_ready", "kachidoki",
    "into_coffin", "ghost_raise", "ghost_neutral", "revive",
)
# 控制码里能让播放头停下或回跳的 kind(pass 不算)
PIXELART_TERMINATING_KINDS = frozenset({"loop", "once", "goto", "stop"})
# 官方 unit_body 圆在**队友序列集**里只有这三段有实体。
# 2026-08-28 全量正向对照(官方 1109 份 character/*/pixelart/pixelart.timeline):
#   有实体圆:neutral / walk_back / walk_front 各 1109/1109;
#   空圆    :skill_ready 510/510、kachidoki 510/510、into_coffin/ghost_raise/
#             ghost_neutral/revive 各 500/500、dead 566/566。
# **但**有 15 个「敌我两用」角色(white_tiger、fox、slango_* 等)的时间轴同时带了
# 敌方那 7 个序列(wince_ready / stun_ready / attack_initial / attack_charge /
# attack_action / attack_fire / dead),其中前 6 段官方**就是**实体圆
# (EnemyImpl.as:2296 getCircleByPath 真的读它们)。所以本判据只能作用在
# PIXELART_REQUIRED_SEQUENCES(队友序列集)上,集合之外的序列不判 —— 否则
# 这 15 个官方角色会被判成 90 条缺陷。
PIXELART_BODY_SEQUENCES = ("neutral", "walk_back", "walk_front")
PIXELART_BODY_RADIUS = 8.3
PIXELART_HP_GAUGE_POINT = {"x": 0, "y": -10}
# 战斗中队员一移动就每帧被切到 walk_back/walk_front(MemberImpl.as:1953-1962),
# 所以这几段是常驻播放的,必须帧帧可见。
PIXELART_ALWAYS_VISIBLE_SEQUENCES = ("neutral", "walk_back", "walk_front",
                                     "ghost_neutral")


def _pixelart_sequences(timeline: dict) -> list[dict]:
    seqs = timeline.get("sequences")
    return seqs if isinstance(seqs, list) else []


def pixelart_timeline_problems(timeline: dict) -> list[str]:
    """pixelart.timeline 的结构 + 官方形状门禁(逐条对应上方逆向实证)。"""
    probs: list[str] = []
    seqs = _pixelart_sequences(timeline)
    if not seqs:
        return ["sequences 为空(客户端 gotoAndPlay('neutral') 立即抛"
                "「neutralは存在しないシーケンス名です」)"]

    names = [s.get("name") for s in seqs]
    for required in PIXELART_REQUIRED_SEQUENCES:
        if required not in names:
            probs.append(
                f"缺序列 {required!r}(MasterConstants."
                f"SQUAD_MEMBER_REQUIRED_SEQUENCE_NAMES;getSequenceByName 会抛"
                f"「{required}は存在しないシーケンス名です」)"
            )
    seen: set = set()
    for name in names:
        if name in seen:
            probs.append(f"序列名重复:{name!r}(getSequenceByName 只返回第一条)")
        seen.add(name)

    prev_end = 0
    for s in seqs:
        begin, end = s.get("begin"), s.get("end")
        name = s.get("name")
        if not isinstance(begin, int) or not isinstance(end, int):
            probs.append(f"序列 {name!r} 的 begin/end 不是整数")
            continue
        if begin > end:
            probs.append(f"序列 {name!r} begin({begin}) > end({end})")
        elif begin != prev_end + 1:
            probs.append(
                f"序列 {name!r} 的 begin={begin} 与上一段 end={prev_end} 不连续"
                "(get_currentSequence 按 end 升序线性扫,空档会被下一段吞掉)"
            )
        prev_end = max(prev_end, end)

    last = seqs[-1]
    if last.get("kind") not in PIXELART_TERMINATING_KINDS:
        probs.append(
            f"最后一个序列 {last.get('name')!r} 的 kind={last.get('kind')!r} "
            "没有终止码(只有 loop/once/goto/stop 会在 end 帧写控制码);"
            "播放头会越过 totalFrames,下一次 get_currentSequence() 抛 INTERNAL ERROR"
        )
    for s in seqs:
        if s.get("name") == "kachidoki" and s.get("kind") != "loop":
            probs.append(
                f"kachidoki 的 kind={s.get('kind')!r};官方 548/548 是 loop,"
                "写成 once 会让胜利姿势停在最后一帧不动"
                "(kachidoking 置位后永不复位,MemberImpl.as:2143-2150)"
            )

    probs += _pixelart_marker_problems(timeline, seqs)
    return probs


def _pixelart_marker_problems(timeline: dict, seqs: list) -> list[str]:
    probs: list[str] = []
    points = timeline.get("points")
    circles = timeline.get("circles")

    hp = None
    if isinstance(points, list):
        hp = next((p for p in points
                   if isinstance(p, dict) and p.get("path") == "hp_gauge"), None)
    if hp is None:
        probs.append("points 里缺 hp_gauge(官方 1151/1151 都有)")
    else:
        frames = hp.get("frames")
        ok = (isinstance(frames, list) and len(frames) == 1
              and isinstance(frames[0], dict) and frames[0].get("begin") == 1
              and frames[0].get("data") == [PIXELART_HP_GAUGE_POINT])
        if not ok:
            probs.append(
                "hp_gauge 形状与官方不一致;官方是 "
                "[{'begin': 1, 'data': [{'x': 0, 'y': -10}]}]"
            )

    body = None
    if isinstance(circles, list):
        body = next((c for c in circles
                     if isinstance(c, dict) and c.get("path") == "unit_body"), None)
    if body is None:
        probs.append("circles 里缺 unit_body(官方 1151/1151 都有)")
        return probs

    frames = body.get("frames")
    if not isinstance(frames, list) or len(frames) != len(seqs):
        got = len(frames) if isinstance(frames, list) else 0
        probs.append(
            f"unit_body 有 {got} 条 frame,官方是每个序列一条(应为 {len(seqs)} 条)"
        )
        return probs
    for seq, frame in zip(seqs, frames):
        name = seq.get("name")
        want_begin = seq.get("begin", 0) + 1
        if not isinstance(frame, dict):
            probs.append(f"unit_body 对应序列 {name!r} 的 frame 不是对象")
            continue
        if frame.get("begin") != want_begin:
            probs.append(
                f"unit_body 对应序列 {name!r} 的 begin={frame.get('begin')},"
                f"官方是 序列begin+1 = {want_begin}"
            )
        data = frame.get("data")
        if name in PIXELART_BODY_SEQUENCES:
            ok = (isinstance(data, list) and len(data) == 1
                  and isinstance(data[0], dict)
                  and data[0].get("x") == 0 and data[0].get("y") == 0
                  and abs(float(data[0].get("r", 0)) - PIXELART_BODY_RADIUS) < 1e-6)
            if not ok:
                probs.append(
                    f"unit_body 在 {name!r} 段应为 [{{'x':0,'y':0,'r':8.3}}]"
                    "(官方 6873 个实例全是这个值)"
                )
        elif name not in PIXELART_REQUIRED_SEQUENCES:
            # 敌方序列(wince_ready / stun_ready / attack_* / dead):官方前 6 段
            # 就是实体圆,且 EnemyImpl 真的会读,不判。
            continue
        elif data != []:
            probs.append(
                f"unit_body 在 {name!r} 段应为空数组"
                "(队友序列集里官方只有 neutral/walk_back/walk_front 有实体圆)"
            )
    return probs


def pixelart_visibility_problems(
    timeline: dict,
    alpha_pixels: dict,
    *,
    min_alpha_pixels: int = 40,
    sequences: tuple = PIXELART_ALWAYS_VISIBLE_SEQUENCES,
) -> list[str]:
    """常驻可见序列里不允许出现近乎全透明的帧。

    `alpha_pixels` = {帧号: 该帧图集矩形里 alpha 超阈值的像素数},由调用方按
    sprite_sheet.png + .atlas 算好传进来 —— 本模块不引入 PIL 依赖。

    为什么这是门禁而不是洁癖:战斗中队员一移动,客户端就每帧调
    gotoAndPlayComplex("walk_front"/"walk_back")(MemberImpl.as:1953-1962),
    这两段基本常驻播放。白虎 1.4.560 把 boss 的「瞬移消散→重组」当成了走路帧,
    61 帧里有 12 帧 alpha 只剩 4~11 px,真机表现就是像素小人不停出现/消失。
    """
    probs: list[str] = []
    for seq in _pixelart_sequences(timeline):
        name = seq.get("name")
        if name not in sequences:
            continue
        begin, end = seq.get("begin"), seq.get("end")
        if not isinstance(begin, int) or not isinstance(end, int) or begin > end:
            continue
        blank = [f for f in range(begin, end + 1)
                 if alpha_pixels.get(f, 0) < min_alpha_pixels]
        if blank:
            probs.append(
                f"序列 {name!r} 有 {len(blank)}/{end - begin + 1} 帧几乎全透明"
                f"(alpha<{min_alpha_pixels}px):{blank[:12]}"
                "(常驻播放段,真机表现为像素小人反复出现/消失)"
            )
    return probs


# ---------------------------------------------------------------------------
# ActionDsl 元素码
#
# 逆向依据:pinball/scene/battle/battle/action/ActionEvaluationResolver.as:228-250
#   resolveElement: 1->0(红) 2->1(蓝) 3->2(黄) 4->3(绿) 5->4(白) 6->5(黑)
#                   7->6(无) 255->上下文元素
# 内部 ElementKind 见 pinball/common/data/general/ElementKindTools.as:13-31。
# 也就是说 DSL 里的元素码是 **1-based**,比 master/character c3 大 1。
#
# 官方正向对照(CN store 1084 个 rare5 技能 DSL):
#   CreateNormalAttack p2:255 共 1555 次;显式值只见 3(雷角色 24 行)/
#   4(风 4 行)/6(暗 4 行)/2(3 行)—— 一律等于「角色内部元素 + 1」,
#   **零行**写成角色自己的内部元素值。FindAllSubjects(种类 33)的元素筛选
#   列表与 ACToleranceOfElement 的元素位是同一套 1-based 约定(零例外)。
#
# 白虎 1.4.560 就栽在这里:雷段写 2(->蓝/水)、风段写 3(->黄/雷),
# 面板写着雷/风,实际打出来是水/雷,整套没有一段是风。
# ---------------------------------------------------------------------------

DSL_ELEMENT_CONTEXT = 255          # 继承 action context 的元素
DSL_ELEMENT_ALL = 254              # ACToleranceOfElement 的「全属性」哨兵
DSL_ELEMENT_MIN = 1
DSL_ELEMENT_MAX = 7                # 7 = colorless

# 差一签名(值 == 角色自己的 0-based 内部元素)只能用在「这一击自己的伤害属性」
# 这类槽位上,不能用在**选择器**槽位上。2026-08-28 全量正向对照
# (官方 951 个玩家侧程序,battle/action/skill/** + battle/action/power_flip/**):
#
#   槽位                          显式值分布                    == 角色内部元素
#   CreateNormalAttack params[1]  3×24 / 4×4 / 6×4 / 255×1422   **0 次**
#   ACToleranceOfElement params[1] 1..6 共 153 + 254×19 + 255×52  38 次
#   FindAllSubjects(33) 元素筛选表 1..6                            2 次
#   ACDamageOfElement params[1]   1×4 / 6×2                       4 次
#
# ACToleranceOfElement 是 AdditionalConditionKind(给目标挂「某属性抗性」增减),
# FindAllSubjects 的表是「筛哪几个属性的同伴」—— 两者的元素都是**被指向的对象**,
# 与施法者自己的属性无关,官方确实有大量「暗角色降光抗」「暗角色筛光同伴」的写法
# (walking_armor 161148、touyakiren_ceo 等)。对它们只做范围校验。
#
# 反过来,CreateNormalAttack 的元素是这一击的伤害属性:官方 1454 个节点里
# 1422 个写 255(继承角色元素),剩下 32 个显式值**全部等于角色自己的元素 + 1**,
# 没有任何一个角色的技能打出与自身不同的属性。所以在这个槽位上
# 「值 == 角色内部元素」= 忘了 +1,零官方反例。
DSL_ELEMENT_STRICT_CONSTRUCTS = frozenset({"CreateNormalAttack"})


def _dsl_element_nodes(node, out: list) -> None:
    if isinstance(node, list):
        if node and isinstance(node[0], str):
            name = node[0]
            if name in ("CreateNormalAttack", "ACToleranceOfElement"):
                if len(node) > 2 and isinstance(node[2], int):
                    out.append((name, node[2]))
            elif (name == "FindAllSubjects" and len(node) > 3
                  and node[2] == 33 and isinstance(node[3], list)):
                for v in node[3]:
                    if isinstance(v, int):
                        out.append(("FindAllSubjects(33)", v))
        for child in node:
            _dsl_element_nodes(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _dsl_element_nodes(child, out)


def action_dsl_element_problems(tree, character_element=None) -> list[str]:
    """ActionDsl 里的元素码必须是 1-based(或 255/254 哨兵)。

    `character_element` 传 master/character c3(0-based 内部 ElementKind)时,
    额外抓「写成了角色自己的内部元素值」这个差一签名 —— 只在
    `DSL_ELEMENT_STRICT_CONSTRUCTS`(伤害属性槽)上生效,选择器槽位官方有反例。
    """
    probs: list[str] = []
    nodes: list = []
    _dsl_element_nodes(tree, nodes)
    for name, value in nodes:
        if value in (DSL_ELEMENT_CONTEXT, DSL_ELEMENT_ALL):
            continue
        if not (DSL_ELEMENT_MIN <= value <= DSL_ELEMENT_MAX):
            probs.append(
                f"{name} 元素码 {value} 越界;合法值 1..7 或 255(继承)"
                "(resolveElement 落 default 返回 undefined)"
            )
            continue
        if (character_element is not None
                and name in DSL_ELEMENT_STRICT_CONSTRUCTS
                and value == character_element):
            probs.append(
                f"{name} 元素码 {value} 等于角色内部元素 {character_element};"
                f"DSL 是 1-based,应写 {character_element + 1}"
                f"(现在实际打出的是内部元素 {value - 1})"
            )
    return probs


# ---------------------------------------------------------------- ActionDsl 主体绑定(C16103)
#
# 2026-08-31 新增。既有的 `action_dsl_element_problems` 只看元素码列(node[2]),
# 对「把元素码写进主体列 node[1]」这一类事故完全无感 —— 三个精灵兽包正是这样:
# CreateNormalAttack 的 params[0] 写了元素码,元素列留 255(合法),门禁全绿,
# 真机第一次判定命中就 ClientError 16103。
#
# 机制(反编译 pinball/scene/battle/battle/action/):
#   ActionEvaluator.as:2703  `_loc18_ = int(params[0])`
#                    :2704  `param2.lookup(_loc18_, Other)`   <- 立刻查表
#   Environment.as:238-267   currentEnvironment -> outerEnvironment 逐层上溯,
#                            到根仍未命中即 `throw new ActionSubjectLookUpFailedError()`
#   ActionSubjectLookUpFailedError.as:15  `super(16103, ...)`
#   ActionEvaluator.as 全文 catch ActionSubjectLookUpFailedError 命中数 = 0
#   (唯一的 catch 在 ActionEvaluationResolver._preresolveCommand,那是预解析缓存,
#    不覆盖执行路径)=> 未绑定主体 = 必崩,没有兜底。
#
# 绑定点(逐个从 ActionEvaluator 反查,括号里是 node 下标 = params 下标 + 1):
#   CreateHitArea  :3473-3475  node[19]->node[20] 块; node[21]/node[22]->node[23](onHit)
#                   ActionHitAreaGroup.as:774 resolveCollisionOfHitArea 只把
#                   这两个 id 塞进 createLocalEnvironment => node[19] 在 onHit 里**不可见**
#   FindAllSubjects            node[1] -> node[9]
#   FindNearSubjects           node[5] -> node[6]     (node[1] 是搜索源,不是绑定)
#   CreateReferencePoint       node[10] -> node[11]
#   CreateSummonsMultiball     node[10]/node[11] -> node[12](Activated callback)
#                   ActionEvaluator.as:3720-3723/3778 forwards params[9]/[10]/[11]
#                   to ActivatedMultiballOfExecutorSelf; ListeningEvent.as:207-212
#                   binds ball/member only inside a child Environment for that callback.
#   TargetMate                 node[1] -> **所在 Block 的后续兄弟语句**(不是子块)
#   CollisionOfBallAndEnemy    node[4] -> node[5]
#
# 正向对照(官方 1.4.0 基线 `.cdn/cn/archive-*-full` 全量 6485 个 .action.dsl):
#   本函数报错文件 2 个(gold_ship_1/_2 的 MoveBall)= 0.03% 误报率;
#   同一语料里 CreateHitArea.onHit 内的 CreateNormalAttack 共 8220 处使用 node[22],
#   使用 node[21] 的 **0 处** —— node[22] 绑的是「被打中的敌人」,node[21] 绑的是判定区本身。
# 变异检验:把已合规包的 CNA 主体改成未绑定值 -> 本函数由 0 变 2(变红);
#           把违规包的主体改回 node[22] -> 由 2 变 0(变绿)。
DSL_BUILTIN_SUBJECTS = frozenset(range(-64, 0)) | {255}

# 构造名 -> [(绑定 id 的 node 下标元组, 作用域块的 node 下标), ...]
DSL_SUBJECT_BINDERS: dict[str, tuple[tuple[tuple[int, ...], int], ...]] = {
    "CreateHitArea": (((19,), 20), ((21, 22), 23)),
    "FindAllSubjects": (((1,), 9),),
    "FindNearSubjects": (((5,), 6),),
    # ActionEvaluator case100: absent branch has no bindings; present binds ball/member.
    "FindMultiballSubjects": (((), 5), ((1, 2), 6)),
    "CreateReferencePoint": (((10,), 11),),
    "CreateReferencePointAtSpecifiedPosition": (((3, 4), 5),),
    "CreatePointsDistanceDetector": (((5,), 6),),
    "CreateWallDistanceDetector": (((3,), 4),),
    "SetHitAreaSomeHitsWithAnyTargetHandler": (((2,), 3),),
    "SetHitAreaSomeHitsWithSpecificTargetHandler": (((2, 3), 4),),
    "CreateShockWaveAttack": (((10, 11, 12), 13),),
    "CollisionOfBallAndEnemy": (((4,), 5),),
    "CollisionOfBallAndSpecificEnemy": (((5,), 6), ((5,), 7)),
    "CollisionOfSpecificBallAndSpecificEnemy": (((6,), 7), ((6,), 8)),
    # ListeningEvent case5 binds the activated squad's ball and member separately.
    "ActivatedMultiballOfExecutorSelf": (((2, 3), 4),),
    "CreateSummonsMultiball": (((10, 11), 12),),
}

# 语句级绑定:对所在 Block 的**后续兄弟**生效(官方 flame_blessgirl 的写法)
DSL_STATEMENT_BINDERS: dict[str, int] = {"TargetMate": 1}

# 构造名 -> 必须能 lookup 到的主体列下标
DSL_SUBJECT_CONSUMERS: dict[str, tuple[int, ...]] = {
    "CreateNormalAttack": (1,), "CreateRatioAttack": (1,), "CreateFixedAttack": (1,),
    "CreateOnlyHitAttack": (1,), "CreateNormalHeal": (1,), "CreateRatioHeal": (1,),
    "CreateCondition": (1,), "DeleteCondition": (1,), "ExtendCondition": (1,),
    "AddSkillPoint": (1,), "SubtractSkillPoint": (1,),
    "MoveHitArea": (1,), "RotateHitArea": (1,), "EraseHitArea": (1,),
    "HideCharacter": (1,), "Revive": (1,), "DecreaseCoffinCount": (1,),
    "StartPiercing": (1,), "StopPiercing": (1,),
    "MoveBall": (1,), "StopBall": (1,),
    "CreateTargetAttack": (1,),
    "SuppressSkill": (1,), "ConsumeUniqueCondition": (1,),
}


def _dsl_is_node(value) -> bool:
    return isinstance(value, list) and bool(value) and isinstance(value[0], str)


def action_dsl_subject_binding_problems(tree) -> list[str]:
    """ActionDsl 里每个主体列都必须能在当前作用域链上 lookup 到,否则 C16103。

    只报**正数未绑定 id**;负数(-1 场地 / -17 自身 / -18 球 ...)与 255 是引擎内建主体。
    返回可读问题串列表,空列表 = 通过。
    """
    probs: list[str] = []

    def walk(node, bound: frozenset) -> None:
        if _dsl_is_node(node):
            name = node[0]
            for index in DSL_SUBJECT_CONSUMERS.get(name, ()):
                if index >= len(node):
                    continue
                subject = node[index]
                if not isinstance(subject, int) or isinstance(subject, bool):
                    continue
                if subject in bound or subject in DSL_BUILTIN_SUBJECTS:
                    continue
                seen = sorted(bound)
                probs.append(
                    f"{name} 主体 node[{index}]={subject} 在当前作用域未绑定"
                    f"(当前可用 {seen});"
                    "Environment.lookup 未命中会 throw ClientError 16103"
                )
            binders = DSL_SUBJECT_BINDERS.get(name)
            if binders:
                handled = {block for _, block in binders}
                for ids, block in binders:
                    if block >= len(node):
                        continue
                    inner = set(bound)
                    for slot in ids:
                        if slot < len(node) and isinstance(node[slot], int):
                            inner.add(node[slot])
                    walk(node[block], frozenset(inner))
                for index, child in enumerate(node[1:], 1):
                    if index not in handled:
                        walk(child, bound)
                return
            for child in node[1:]:
                walk(child, bound)
            return
        if isinstance(node, list):
            scope = set(bound)
            for child in node:
                walk(child, frozenset(scope))
                if (isinstance(child, list) and len(child) == 2 and child[0] == "Command"
                        and _dsl_is_node(child[1]) and child[1][0] in DSL_STATEMENT_BINDERS):
                    slot = DSL_STATEMENT_BINDERS[child[1][0]]
                    if slot < len(child[1]) and isinstance(child[1][slot], int):
                        scope.add(child[1][slot])
            return
        if isinstance(node, dict):
            for child in node.values():
                walk(child, bound)

    walk(tree, frozenset())
    return probs


# ------------------------------------------------- ActionDsl lookup 作用域(C16103 全量)
#
# 2026-09-21 新增(凯尔队伍战斗中 C16103 事故)。上面的 `DSL_SUBJECT_CONSUMERS` 是
# **手抄的子集** —— 它漏了 `CreateReferencePoint` node[1](原点)、`ShowEffect` node[3]、
# `CreateHitArea` node[2] 等一大批同样会走 `Environment.lookup` 的列。
# 事故本体:`ability_skill_kyle_moon_thunder` 的强化分支从常态分支整块克隆后
# 把**绑定位**平移了 +30(30/31/32/33/34),但上面这三个**引用位**留在母本的 0/1,
# 于是 `CreateReferencePoint(0,…)` 在只绑了 30 的环境里 lookup 失败 —— 崩溃栈里
# `Environment/lookup` ×3(当前环境 → ConditionalsChangeSkillFlag 环境 → 全局环境)
# 与 `evalCommand←eval←evalBlock←eval←evalCommand←eval←evalBlock←eval←evalCommand`
# 逐帧对得上。**同一张漏表既造出了缺陷,又让门禁看不见它**(`_remap_binds` 也读它)。
#
# 下表改为**从客户端源码机械提取**,不再手抄(复现脚本
# `mod-tools/work/dsl_scope_check/build_table.py`):切出 `ActionEvaluator.evalCommand`
# 的 `switch(param1.index)`,在每个 case 块里把 `_locN_ = param1.params[i]` 建成变量→列号
# 映射,再收集 `.lookup(_locN_,` 以及三个内部 lookup 的助手
# (`isSelfSubjectId` / `calculateImpactId` / `addImpactToSubject`)的实参;
# 构造名取 `ActionDslCommand.__constructs__` 按 index 对号。得到 49 个构造。
#
# 正向对照(2026-09-21,官方 1.4.0 全量归档 `.cdn/cn/archive-common-full`
# ∩ `弹国服/restored/_pathlist_restored.txt`,**7051 棵 .action.dsl**
# = 玩家侧 1119 + 敌侧 5932):本函数报错 **0 棵**。
# 反向对照:凯尔强化天雷树 4 处命中;把它修好后归零(见 tests/test_client_legality_lookup_scope.py)。
DSL_SUBJECT_LOOKUPS: dict[str, tuple[int, ...]] = {
    "FindNearSubjects": (1,),                 # 搜索原点
    "AddSkillPoint": (1,), "SubtractSkillPoint": (1,),
    "ShowEffect": (3,),                       # 特效锚点
    "MoveBall": (1,), "StopBall": (1,),
    "CreateNormalAttack": (1,), "CreateRatioAttack": (1,),
    "CreateFixedAttack": (1,), "CreateOnlyHitAttack": (1,),
    "CreateNormalHeal": (1,), "CreateRatioHeal": (1,),
    "CreateCondition": (1,), "DeleteCondition": (1,), "ExtendCondition": (1,),
    "CreateHitArea": (2,),                    # 判定区挂载主体
    "MoveHitArea": (1,), "RotateHitArea": (1,), "EraseHitArea": (1,),
    "SetHitAreaSomeHitsWithAnyTargetHandler": (1,),
    "SetHitAreaSomeHitsWithSpecificTargetHandler": (1,),
    "SetHitAreaTerminateHandler": (1,),
    "CreateReferencePoint": (1,),             # 参考点原点
    "CreateReferencePointAtSpecifiedPosition": (1, 2),   # X 取自 / Y 取自
    "CreateShockWaveAttack": (2,),
    "HideCharacter": (1,),
    "CreateGravitationalField": (1,), "CreateTornado": (1,),
    "CreateTargetAttack": (1,), "CreateOneWayWallGimmick": (1,),
    "ConditionalsHealthPointRatioOf": (1,), "CreateBarrier": (1,),
    "ConditionalsConditionExist": (1,),
    "StartPiercing": (1,), "StopPiercing": (1,),
    "CreateWallDistanceDetector": (1,), "CreatePointsDistanceDetector": (1, 2),
    "RecoveryHitCountCheck": (1,), "ConditionalsCoffinCountSubject": (1,),
    "ConsumeUniqueCondition": (1,), "SuppressBallActivity": (1,),
    "CreateCollider": (1,), "SuppressSkill": (1,),
    "BindConditionAccumulationVariable": (1,), "BindCoffinRevivalCountVariableOf": (1,),
    "NotifyPowerflipEnd": (1,),
    # 机械提取覆盖不到的两条(走 `decreaseCoffinCount` 助手,助手内部再 lookup);
    # 与既有 DSL_SUBJECT_CONSUMERS 保持一致,不做收窄。
    "Revive": (1,), "DecreaseCoffinCount": (1,),
}


def _dsl_lookup_slots(name: str) -> tuple[int, ...]:
    """该构造所有会走 `Environment.lookup` 的 node 下标(机械表 ∪ 既有手抄表)。"""
    return tuple(sorted(set(DSL_SUBJECT_LOOKUPS.get(name, ()))
                        | set(DSL_SUBJECT_CONSUMERS.get(name, ()))))


def action_dsl_lookup_scope_problems(tree) -> list[str]:
    """ActionDsl 里**每一个** lookup 位都必须在当前作用域链上可见,否则 C16103。

    与 `action_dsl_subject_binding_problems` 同一套作用域模型,区别只在引用位取
    `DSL_SUBJECT_LOOKUPS`(客户端机械提取的全量表)而不是手抄子集;另外额外判
    坐标系 ``["GH", n]``(`ActionEvaluator.as:1037` 同样 lookup 它)。

    负数(-1 场地 / -17 自身 / -18 球 …)与 255 是引擎内建主体,不判。
    返回可读问题串列表,空列表 = 通过。
    """
    probs: list[str] = []

    def report(what: str, subject: int, bound: frozenset) -> None:
        probs.append(
            f"{what}={subject} 在当前作用域链上找不到"
            f"(此处可见绑定 {sorted(bound) or '无'});"
            "Environment.lookup 上溯到根仍未命中 = ClientError 16103"
        )

    def coordsys(node, bound: frozenset, owner: str) -> None:
        if (isinstance(node, list) and len(node) == 2 and node[0] == "GH"
                and isinstance(node[1], int) and not isinstance(node[1], bool)
                and node[1] not in bound and node[1] not in DSL_BUILTIN_SUBJECTS):
            report(f"{owner} 坐标系 GH 主体", node[1], bound)

    def walk(node, bound: frozenset) -> None:
        if _dsl_is_node(node):
            name = node[0]
            for index in _dsl_lookup_slots(name):
                if index >= len(node):
                    continue
                subject = node[index]
                if not isinstance(subject, int) or isinstance(subject, bool):
                    continue
                if subject in bound or subject in DSL_BUILTIN_SUBJECTS:
                    continue
                report(f"{name} 主体 node[{index}]", subject, bound)
            for child in node[1:]:
                coordsys(child, bound, name)
            binders = DSL_SUBJECT_BINDERS.get(name)
            if binders:
                handled = {block for _, block in binders}
                for ids, block in binders:
                    if block >= len(node):
                        continue
                    inner = set(bound)
                    for slot in ids:
                        if slot < len(node) and isinstance(node[slot], int):
                            inner.add(node[slot])
                    walk(node[block], frozenset(inner))
                for index, child in enumerate(node[1:], 1):
                    if index not in handled:
                        walk(child, bound)
                return
            for child in node[1:]:
                walk(child, bound)
            return
        if isinstance(node, list):
            scope = set(bound)
            for child in node:
                walk(child, frozenset(scope))
                if (isinstance(child, list) and len(child) == 2 and child[0] == "Command"
                        and _dsl_is_node(child[1]) and child[1][0] in DSL_STATEMENT_BINDERS):
                    slot = DSL_STATEMENT_BINDERS[child[1][0]]
                    if slot < len(child[1]) and isinstance(child[1][slot], int):
                        scope.add(child[1][slot])
            return
        if isinstance(node, dict):
            for child in node.values():
                walk(child, bound)

    walk(tree, frozenset())
    return probs


def action_dsl_hit_area_target_problems(tree) -> list[str]:
    """CreateHitArea 的 onHit 块里,伤害/状态应挂在 node[22](被击中的敌人)。

    node[21] 绑的是判定区自身。官方 8220/8220 个 onHit 内 CreateNormalAttack
    一律用 node[22],用 node[21] 的 0 例 —— 挂错不抛异常,但伤害落不到敌人身上。
    """
    probs: list[str] = []

    def scan(node) -> None:
        if isinstance(node, list):
            if _dsl_is_node(node) and node[0] == "CreateHitArea" and len(node) > 23:
                area_id, target_id = node[21], node[22]

                def inner(child) -> None:
                    if _dsl_is_node(child) and child[0] == "CreateHitArea":
                        scan(child)
                        return
                    if (_dsl_is_node(child)
                            and child[0] in ("CreateNormalAttack", "CreateCondition")
                            and len(child) > 1
                            and child[1] == area_id and area_id != target_id):
                        probs.append(
                            f"{child[0]} 挂在 CreateHitArea 的 node[21]={area_id}"
                            f"(判定区自身),应为 node[22]={target_id}(命中目标)"
                        )
                    if isinstance(child, list):
                        for value in child:
                            inner(value)

                inner(node[23])
            for value in node:
                scan(value)
        elif isinstance(node, dict):
            for value in node.values():
                scan(value)

    scan(tree)
    return probs
