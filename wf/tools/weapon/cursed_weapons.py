# -*- coding: utf-8 -*-
"""诅咒武器 29 把：腾讯文档「诅咒武器专题意见征集」提案 → 武器数据（纯函数生成器）。

作者口径（2026-09-27 首轮，0928 修订）：
- 把表里的武器全部做出来，图标仿官方 20×20 像素风；
- **未强化（本体，含满破）只有正面数值，而且很弱**（满破值 = 设计值 × BASE_SCALE）；
- **觉醒分级（0928「每个等级也要设计区分数值」，满破锚定）**：本体数值行觉醒 0 = 满破值 × AWAKEN_FLOOR（20%），
  每觉醒 1 级 +20% 满破值，觉醒 4（满破）不变 ⇒ 预算、强化行、DSL、120 级终值都不动；
- **强化 1 级起诅咒全额生效**；**强化到 120 级为最终数值**；
- 强化材料来自五重决战（深界结晶 10000145 / 五王心核 10000147 / 终式武装图纸 10000144）；
- **数值预算（0928 追加）**：基线 = 死亡使者合计 500% 刃；有诅咒也不能让刃合计超过 1000%，乘区不超过 50%；
  不要脸的提案压到常规深渊水准（≈500–600% 刃）。:func:`weapon_budget` 按 120 级 + 满破的行/DSL 计算，``build`` 进 problems；
- **评分审查 0928**（作者「按表改吧，拍板项也按方案做」）：按 ${WF_ROOT}/out/诅咒武器评分审查-20260928/诅咒武器调整建议.xlsx 调数值；
- **诅咒负面一律强制赋予**（作者 0928「角色免疫也会生效」）：能力表计时状态没有强制付与列，诅咒状态走 629 DSL
  CreateCondition forceApply（命中率 1）或固有状态 c10=true；能力表诅咒行不再用瞬发 19/219/688 与负值计时状态；
- **「无法获得能量」**（作者 0928）= 计时固有状态 + 持续 423 回槽拦截规则码 :data:`GAUGE_LOCK`（78，只放行开局槽）。

数据面（全部新键，不改任何已有键）：

- 客户端：``item`` / ``equipment`` / ``equipment_status``（嵌套）/ ``ability_soul`` / ``equipment_enhancement`` /
  ``equipment_enhancement_ability`` / ``equipment_enhancement_status``（嵌套）/ ``equipment_enhancement_shop``（每把 6 阶）/
  ``equipment_enhancement_shop_category``（新类目 6「诅咒武器·觉醒」）/
  ``unique_condition``（诅咒与计时用固有状态）/ ``custom_ability_string``（629 行文案）+ 新 ability_skill DSL。
- 服务端：``equipment_ids`` / ``equipment_lookup`` / ``equipment_max_level`` / ``equipment_element`` / ``item_ids`` /
  ``item_sale`` / ``equipment_enhancement_shop``。
- 获取：作者 0928 起诅咒武器不可兑换，本体只从武器扭蛋 990003 抽取（每把 0.3%，250 点可兑换），
  **不再**上架五重商店（原 990099003–031 已撤下，见 wf_weapon_gacha.py）；本生成器不产出任何 boss_coin_shop 行。

机制约束（反编译实证，写在这里防回退）：

1. 攻击力加成总和在 ``NormalAttackCalculator.totalAttackPoint`` 被钳到 ≥ -50%（boot_ffc6 STAT_MODIFIER_ATTACK_POINT_MIN）；
   单次伤害最终 ``max(floor(dmg), 1)``。所以「攻击 -9999% / 伤害归零」用 **独立乘区伤害 -100%**（723/421）表达，
   「输出 -99%」同理用独立乘区 -99%。
2. 装备词条 = 本体 concat 强化；同 slot 取 learn ≤ 当前等级最高一行 ⇒ 每行独占一个 slot；
   「只在 120 级生效」= learn=max=120 的行；「强化 1 级起全额」= learn=1、max=120、两端同值。
   本体行随觉醒等级 1→5 在 power1→first_max 线性插值（``AbilityPowerValue.resolve``：觉醒 N = p1 + (fm − p1) × N/4；
   ElapsedTime 等触发阈值同样插值）。
3. 629 InvokeSkill 在 ability_soul（c67/c68）与强化表（c70/c71）解析器里都有分支；装备词条的 DSL 走
   ``BattleCharacterLogic.resolvePathCollection`` → ``equipment.getCurrentAbility()`` 正式预载。
   string_id 必须写进 custom_ability_string（缺键 C8601）。DSL 不带任何特效路径（杜绝 C8016）。
4. 玩家侧 DSL 的 CreateWindAttack / CreateGravitationalField / CreateFlood 在 MemberImpl 直接 throw ⇒ 风场推人、重力、
   淹水物理做不了（第 12、15 条按偏差记录）。
5. 「能力/被动回槽禁止」= 持续 423 GaugeGainRestriction：装备两表的解析只有客户端补丁 equipment-rules 认（1047 读到 C7050），
   ``build`` 按 ``client_capabilities`` 拦截（默认 1047 基线），本机已装补丁时显式传 ``PATCHED_CLIENT_CAPABILITIES``。
6. 带 mul 的 CreateCondition 必须带非空唯一键串（基诺维吞噬同款坑）。
7. DSL 解自己挂的锁：DeleteCondition 必须带锁的键串，cancelableKind 选得中锁（不可驱散的锁写 1；写 0 删不掉，
   1.4.1057 剑舞圆环连击上限从未解除），``own_lock_delete_problems`` 拦截。
8. 根头或判定区 buffTargetAs ≥100（133 = 按强化弹射 Lv3 结算）需要 damage-type-rules-v1，``dsl_capabilities`` 进 capability 门禁；
   按强化弹射段结算的 629 命中算真实 PF 命中，不能再用「强化弹射命中」类触发（183 与对应等级的 180-182、15-17，
   见 wf_battle_rules.PF_SEGMENT_HIT_TRIGGERS）触发（自我连锁），``pf_echo_trigger_problems`` 拦截。
9. 按层数读/消耗固有状态（持续 134/207、前置 144/199、瞬发 525/526、瞬发前置 1/2/3、DSL ConsumeUniqueCondition）
   要求该固有叠层上限 c4 >1：``Condition.get_accumulatable() = maxAccumulation > 1``，上限 1 时层数恒 0、消耗为空操作
   （第三轮复审：6 把武器的门禁因此静默失效）。``unique_accumulation_problems`` 拦截；已知未修的在 ``ACCUMULATION_CAP_PENDING``。

接口：:func:`build` 只经 ``read`` 读 live（见 :class:`LiveReader`），返回全部新增内容；不写盘、不发布、不 git。
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable

from wf.paths import REPOSITORY
import wf_battle_rules as BR
import wf_client_legality as L
import wf_client_patch_scope as SCOPE
import wf_describe as D
DEVOUR_IDS = (1110021, 1110022, 1110061, 1110062, 1110063, 1110064, 1110391, 1110392, 1110393, 1110394, 1110811, 1110812, 1111351, 1111352, 1111471, 1111472, 1111711, 1111712, 1130011, 1399961, 1610391, 1610392, 1610511, 1610512, 1610871, 1610872, 1611051, 1611291, 1611292, 1611771, 1611772, 1611891, 1611892, 1611951, 1611952, 1699891, 1699892, 2510061, 2510062, 2510063, 2610011, 2610012, 2610651, 2610652, 2630031, 2630032, 3510041, 3510042)

# ---------------------------------------------------------------------------
# 表与常量
# ---------------------------------------------------------------------------

ITEM = "master/item/item.orderedmap"
EQUIPMENT = "master/item/equipment.orderedmap"
EQUIPMENT_STATUS = "master/item/equipment_status.orderedmap"            # 嵌套（wf_quest_lib）
SOUL = "master/ability/ability_soul.orderedmap"
ENH = "master/equipment_enhancement/equipment_enhancement.orderedmap"
EA = "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"
ENH_STATUS = "master/equipment_enhancement/equipment_enhancement_status.orderedmap"   # 嵌套
ENH_SHOP = "master/equipment_enhancement/equipment_enhancement_shop.orderedmap"
ENH_CATEGORY = "master/equipment_enhancement/equipment_enhancement_shop_category.orderedmap"
BOSS_COIN_SHOP = "master/shop/boss_coin_shop.orderedmap"   # 只用于断言「不产出」：本体已撤出五重商店（作者 0928）
UNIQUE = "master/character/unique_condition.orderedmap"
CAS = "master/string/custom_ability_string.orderedmap"

FLAT_TABLES = (ITEM, EQUIPMENT, SOUL, ENH, EA, ENH_SHOP, ENH_CATEGORY, UNIQUE, CAS)
NESTED_TABLES = (EQUIPMENT_STATUS, ENH_STATUS)

ID_BASE = 5910100                      # 武器 / 魂珠 / 强化 / 强化组 ID = 5910100 + 提案表行号
UNIQUE_BASE = 59100000                 # 固有状态 ID = 59100000 + 行号×10 + k
ENH_CATEGORY_KEY = "6"
#: 类目表 c1 display_order（升序，负数合法且须全表互异；作者 0928 横幅顺序 诅咒 → 深渊 → 官方 1–4，见 wf_enhancement_category_order）
ENH_CATEGORY_DISPLAY_ORDER = "-2"
IMAGE_DIR = "item/equipment/mod/cursed"
BANNER = "dynamic/equipment_enhancement/cursed_weapon_banner"
HEADER = "dynamic/equipment_enhancement/cursed_weapon_header"
DSL_DIR = "battle/action/skill/action/ability_skill/cursed_weapon"
START_TIME = "2000-01-01 00:00:00"     # 服务器时钟偏移，自制内容一律写 2000-01-01（见 wf-custom-server-time-trap）

BLUEPRINT = "10000144"                 # 终式武装图纸（五重：每局 50% 掉 1）
CRYSTAL = "10000145"                   # 深界结晶（五重：5×倍率）
CORE = "10000147"                      # 五王心核（五重：25%，数量=倍率）

#: 强化 6 阶（阶段上限, [(材料, 数量), ...]）——全部五重材料；阶段形状照 5900101 / 深渊觉醒。
ENH_STAGES = (
    (69, ((CRYSTAL, 1),)),
    (70, ((CRYSTAL, 10), (CORE, 1))),
    (98, ((CRYSTAL, 2),)),
    (99, ((CRYSTAL, 10), (CORE, 2))),
    (119, ((CRYSTAL, 3), (CORE, 1))),
    (120, ((CORE, 3), (BLUEPRINT, 2))),
)
REQUIRE_AWAKENING = 5

#: 作者 0928 口径：强化前（本体含满破）非常弱且只有正面；强化 1 级诅咒全额生效；强化 120 级为最终数值。
#: 诅咒行与其配套机制行用 CURSE（learn=1、全额常量）；正面终值行用 FINAL（120 级）；成长行 1→119 + 120 补足。
CURSE = dict(learn=1, maxlvl=120)
FINAL = dict(learn=120, maxlvl=120)
#: 作者 0928「要的就是强化前非常弱」：本体（含满破）按设计值的 20% 生效，强化 1→119 成长行补回差额，120 级终值不变。
#: 只缩数值类效果；机制类（技能槽上限 245、连击、贯通、固有状态、629 调用、扣血回血等）保持设计值。
BASE_SCALE = 0.2
#: 作者 0928「每个等级也要设计区分数值」（设计 武器觉醒与新掉落-20260928 §3.3，满破锚定 + 等差）：WEAK_KINDS 本体行
#: power1 = round(first_max × AWAKEN_FLOOR)，first_max（满破）逐字节不变 ⇒ 觉醒 0/1/2/3/4 = 满破的 20/40/60/80/100%。
#: 满破值 fm 都是 500 的倍数（0.5%），所以五级都是整数或一位小数。机制行（245/461/525/26/226/58/629）不动；
#: 206（被诅咒的面具吸血）不缩 BASE_SCALE，但作者 0928 要求同样按觉醒 0 = 满破 20% 分级（在 w29 里直接写 0.2%→1%）。
AWAKEN_FLOOR = 0.2
WEAK_KINDS = frozenset({"0", "1", "2", "28", "32", "33", "34", "35", "55", "156", "202", "205", "211", "227", "388", "470",
                        "486", "693", "694", "701", "717", "723"})
#: 官方 5★ 武器 HP/ATK 成长（照 5020042 哈尔波曼 / 5900101）与强化 status（照官方 120 级武器）。
EQUIPMENT_STATUS_ROWS = {"1": "330,148", "5": "495,221"}
ENH_STATUS_ROWS = {"98": "0,0", "99": "50,10", "120": "50,10"}

INF_FRAMES = "9.999999E11"             # 「永续」帧（×100000），照 cnmod_boss_limit 实机在役写法

#: 回槽限制规则码：只拦「能力」类回槽（角色/队长/武器/魂珠/EX 的能力加槽，含连击与施技触发；来源不限）。
GAUGE_MASK = BR.gauge_mask(["ability"])
#: 「无法获得能量」（作者 0928）：移动跑条 2 + 技能直接回槽 4 + 能力回槽 8（含连击/施技触发子类）+ 其他动作脚本 64
#: （PF、召唤/炸弹协力球、道具）= 78。只放行开局槽（1）：开场不在时间窗内；跑条不接受出处/持有者混合筛选，只按加槽方式组。
GAUGE_LOCK = BR.gauge_mask(["movement", "skill", "ability", "other_action"])
#: 客户端 capability 门禁。基线 = 1047 客户端已有能力（与 client-patch/equipment-rules/rules.py INHERITED_CAPABILITIES
#: 同步，PARADOX 测试互证）；equipment-rules 补丁 APK 再加 R1/R2 的 equipment-rules-v1 与 R3 的 equipment-gauge-gain-rules-v1。
EQUIPMENT_RULES_CAP = "equipment-rules-v1"
BASE_CLIENT_CAPABILITIES = frozenset({
    "damage-type-rules-v1", "dash-parameter-v1", "gauge-gain-rules-v1", "kyubi-fever-ratio-v1",
    "kyubi-panel-description-override-v1", "kyubi-pf-initial-combo-v1", "panel-description-override-v2",
})
PATCHED_CLIENT_CAPABILITIES = BASE_CLIENT_CAPABILITIES | {EQUIPMENT_RULES_CAP, SCOPE.EQUIPMENT_GAUGE_CAP}

# 目标 / 来源 枚举
T_SELF, T_EXCEPT, T_LEADER, T_SECOND, T_THIRD, T_PARTY, T_TRIGGER, T_MULTIBALL = "0", "1", "2", "3", "4", "5", "7", "8"
P_SELF, P_LEADER, P_SECOND, P_THIRD, P_ONE_OF_PARTY, P_ONE_OF_MULTIBALL = "0", "1", "2", "3", "5", "9"
# 触发 kind
IT_INITIAL, IT_PF, IT_FEVER, IT_DIRECT, IT_SKILL, IT_SKILL_MAX, IT_HP_LOW, IT_ELAPSED, IT_REVIVAL, IT_MB_REMOVE = (
    "0", "2", "8", "20", "23", "24", "25", "77", "18", "194")
IT_SKILL_HIT, IT_PF_HIT = "107", "183"   # SkillHit（带来源）/ OneOfEnemyPowerFlipHitLvAny（官方 139998 队长技同款）
# 持续触发 kind（207 = 固有状态层数 ≤ 阈值，官方 1111172「缺固有」同形）
DT_HP_HIGH, DT_FEVER, DT_UNIQUE, DT_UNIQUE_LOW, DT_HP_LOW_EX = "0", "4", "134", "207", "227"
# 前置 kind
PRE_MEMBER, PRE_HP_HIGH, PRE_UNIQUE_GE, PRE_HAS_UNIQUE, PRE_UNIQUE_LE, PRE_SAME_ELEMENT = "2", "8", "144", "187", "199", "208"
PRE_MY_SELF = "3"
#: SkillGaugeHigh / SkillGaugeLow（阈值 Decimal，100000 = 100% 基准槽；官方零先例，运行时对象同 1110153 的 107）
PRE_GAUGE_HIGH, PRE_GAUGE_LOW = "119", "120"
#: DSL 根头 buffTargetAs 覆盖（damage-type-rules-v1）：133 = 按强化弹射 Lv3 完整结算（通用池、分档、413、PF 显示）。
#: 未装补丁的客户端读成 0，按技能伤害结算，不崩。
PF3_BTA = BR.segment_override("pf3")

ELEMENT_GROUP = {"fire": "Red", "water": "Blue", "thunder": "Yellow", "wind": "Green", "light": "White", "dark": "Black"}
ELEMENT_CODE = {"fire": 0, "water": 1, "thunder": 2, "wind": 3, "light": 4, "dark": 5}   # equipment_element.json（0 基）


class CursedWeaponError(RuntimeError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise CursedWeaponError(message)


def pct(x: float) -> str:
    """百分比 → 词条强度（1000 = 1%）。"""
    return str(int(round(x * 1000)))


def times(n: float) -> str:
    """次数 / 层数 → ×100000。"""
    return str(int(round(n * 100000)))


def frames(n: int) -> str:
    """帧 → ×100000（frame 字段与 ElapsedTime 阈值同单位）。"""
    return str(int(n) * 100000)


# ---------------------------------------------------------------------------
# 词条行构建（ability_soul 123 列 / equipment_enhancement_ability 126 列）
# ---------------------------------------------------------------------------

SOUL_T = "ability_soul"
EA_T = "equipment_enhancement_ability"
_LAYOUT = {t: D.layout(t) for t in (SOUL_T, EA_T)}
_OFF = {block: {name: int(off) for off, name, _label in fields}
        for block, fields in D.enum_map()["block_fields"].items()}
_CASES = D.enum_map()["cases"]


def _col(table: str, block: str, name: str) -> int:
    fields = _OFF["precondition" if block.startswith("precondition") else block]
    return int(_LAYOUT[table]["blocks"][block]) + fields[name]


@dataclass(frozen=True)
class Eff:
    """一行装备词条（本体或强化）。数值字段直接给存储值（字符串）。"""
    mode: str                                   # "0" 瞬发 / "1" 持续
    content: tuple                              # (kind, {字段: 值})
    trig: tuple = (IT_INITIAL, {})              # 瞬发触发或持续触发 (kind, {字段: 值})
    pre: tuple = ()                             # ((kind, {字段: 值}), ...) 最多 3 个
    pc: tuple | None = None                     # 瞬发前置 (kind, {字段: 值})
    delay: int = 0                              # instant_delay（秒；客户端 ×60 帧。三重咒钥说明即「1秒后」）
    even_if_dead: bool = False
    learn: int = 1
    maxlvl: int = 1                             # 仅强化表
    note: str = ""                              # 人话说明（写进设计文档，不进数据）


def _fill_block(row: list[str], table: str, block: str, values: dict[str, str]) -> None:
    for name, value in values.items():
        row[_col(table, block, name)] = value


def _content_defaults(kind: str, block: str, given: dict[str, str]) -> dict[str, str]:
    """按 kind 声明的字段补官方哨兵（声明即必填）。"""
    case = _CASES["instant_content" if block == "instant_content" else "during_content"].get(kind)
    _require(case is not None, f"{block} kind {kind} 不在枚举域")
    fields = case["fields"]
    out: dict[str, str] = {"kind": kind}
    if "target" in fields:
        out["target"] = given.pop("target", T_SELF)
        out["target.character_groups"] = given.pop("target.character_groups", "(None)")
    pairs = {"strength": None, "frame": None, "number": times(1)}
    for name, default in pairs.items():
        if name in fields:
            value = given.pop(name, default)
            _require(value is not None, f"{block} kind {kind} 缺 {name}")
            lo, hi = value if isinstance(value, tuple) else (value, value)
            out[f"{name}.power1"], out[f"{name}.first_max"] = lo, hi
    sentinels = {
        "max_accumulation": "(None)", "flip_limit": "(None)", "power_flip_limit": "(None)",
        "end_power_flip_limit": "(None)", "end_power_flip_accepted_levels": "(None)",
        "cancelable": "0", "by_each_trigger_puller": "false", "initial_multiply": "1", "multiply_trigger": "0",
    }
    for name, default in sentinels.items():
        if name in fields:
            out[name] = given.pop(name, default)
    for name in ("unique_condition_id", "string_id", "action_path", "element"):
        if name in fields:
            _require(name in given, f"{block} kind {kind} 缺 {name}")
            out[name] = given.pop(name)
    _require(not given, f"{block} kind {kind} 多余字段 {sorted(given)}")
    return out


def _trigger_values(kind: str, block: str, given: dict[str, str]) -> dict[str, str]:
    case = _CASES["instant_trigger" if block == "instant_trigger" else "during_trigger"].get(kind)
    _require(case is not None, f"{block} kind {kind} 不在枚举域")
    fields = case["fields"]
    out = {"kind": kind}
    if "trigger_puller" in fields:
        puller = given.pop("trigger_puller", P_SELF)
        out["trigger_puller"] = puller
        # 4/5/6/7/9（含 OneOfMultiball）都带角色组参数；空串会被读成空组，说明里显示「null角色」（1.4.1057 叛乱军旗）
        if puller in ("4", "5", "6", "7", "9"):
            out["trigger_puller.character_groups"] = given.pop("trigger_puller.character_groups", "(None)")
    if "threshold" in fields:
        lo = given.pop("threshold", times(1))
        out["threshold.power1"], out["threshold.first_max"] = lo if isinstance(lo, tuple) else (lo, lo)
    if "trigger_limit" in fields:
        out["trigger_limit"] = given.pop("trigger_limit", "(None)")
    if "cooltime" in fields:
        out["cooltime"] = given.pop("cooltime", "0")
    if "unique_condition_id" in fields:
        _require("unique_condition_id" in given, f"{block} kind {kind} 缺 unique_condition_id")
        out["unique_condition_id"] = given.pop("unique_condition_id")
    _require(not given, f"{block} kind {kind} 多余字段 {sorted(given)}")
    return out


def _pre_values(kind: str, given: dict[str, str]) -> dict[str, str]:
    case = _CASES["precondition"].get(kind)
    _require(case is not None, f"precondition kind {kind} 不在枚举域")
    fields = case["fields"]
    out = {"kind": kind}
    if "trigger_puller" in fields:
        out["trigger_puller"] = given.pop("trigger_puller", P_SELF)
    if "threshold" in fields:
        lo = given.pop("threshold")
        out["threshold.power1"], out["threshold.first_max"] = lo if isinstance(lo, tuple) else (lo, lo)
    if "character_groups" in fields:
        out["character_groups"] = given.pop("character_groups")
    if "unique_condition_id" in fields:
        out["unique_condition_id"] = given.pop("unique_condition_id")
    _require(not given, f"precondition kind {kind} 多余字段 {sorted(given)}")
    return out


def build_row(table: str, slot: int, eff: Eff) -> list[str]:
    lay = _LAYOUT[table]
    row = [""] * int(lay["ncols"])
    if table == SOUL_T:
        row[0], row[1], row[2] = str(slot), str(eff.learn), eff.mode
    else:
        grow = eff.learn < eff.maxlvl
        power = ("24", "48") if grow else ("48", "48")
        row[0:6] = [str(slot), str(eff.learn), str(eff.maxlvl), power[0], power[1], eff.mode]
    _require(len(eff.pre) <= 3, "前置最多 3 个")
    for index, name in enumerate(("precondition1", "precondition2", "precondition3")):
        if index < len(eff.pre):
            kind, given = eff.pre[index]
            _fill_block(row, table, name, _pre_values(kind, dict(given)))
        else:
            row[_col(table, name, "kind")] = "0"
    if eff.mode == "0":
        kind, given = eff.trig
        _fill_block(row, table, "instant_trigger", _trigger_values(kind, "instant_trigger", dict(given)))
        if eff.pc is None:
            row[_col(table, "instant_precontent", "kind")] = "(None)"
        else:
            kind, given = eff.pc
            _fill_block(row, table, "instant_precontent", {"kind": kind, **given})
        row[_col(table, "instant_delay", "instant_delay")] = str(eff.delay)
        kind, given = eff.content
        _fill_block(row, table, "instant_content", _content_defaults(kind, "instant_content", dict(given)))
    else:
        row[_col(table, "during_accumulation_trigger", "kind")] = "(None)"
        kind, given = eff.trig
        _fill_block(row, table, "during_trigger", _trigger_values(kind, "during_trigger", dict(given)))
        row[_col(table, "even_if_owner_dead", "even_if_owner_dead")] = "true" if eff.even_if_dead else "false"
        kind, given = eff.content
        _fill_block(row, table, "during_content", _content_defaults(kind, "during_content", dict(given)))
    return row


# ---------------------------------------------------------------------------
# 词条速写（常用 kind）
# ---------------------------------------------------------------------------

def res(element: str) -> tuple:
    """属性共鸣（编成 6 人 = 全队含协力）。"""
    return (PRE_MEMBER, {"threshold": times(6), "character_groups": ELEMENT_GROUP[element]})


SAME_ELEMENT = (PRE_SAME_ELEMENT, {"threshold": times(6)})


def my_element(*elements: str) -> tuple:
    """自身为某属性（官方先例：魂珠 5040010「风·MySelf」）；多属性逗号并列 = 任一。"""
    return (PRE_MY_SELF, {"character_groups": ",".join(ELEMENT_GROUP[e] for e in elements)})


#: 队伍中除自身外还有其他角色（主位或合击位）：编成人数 ≥ 2（六属性并列 = 不限属性）。
HAS_TEAMMATE = (PRE_MEMBER, {"threshold": times(2), "character_groups": ",".join(ELEMENT_GROUP.values())})


def has_unique(uid: str) -> tuple:
    return (PRE_HAS_UNIQUE, {"trigger_puller": P_SELF, "unique_condition_id": uid})


def lacks_unique(uid: str) -> tuple:
    """前置：自身没有固有状态 uid（199「层数 ≤0」）。uid 的叠层上限必须 >1，否则层数恒 0、前置恒真。"""
    return (PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": "0", "unique_condition_id": uid})


def lacks_unique_during(uid: str) -> tuple:
    """持续触发：自身没有固有状态 uid（207「层数 ≤ 阈值」，阈值必须写 "0"；写 times(1) 会把 1 层也算作「没有」）。
    uid 的叠层上限必须 >1，否则层数恒 0、触发恒真。"""
    return (DT_UNIQUE_LOW, {"trigger_puller": P_SELF, "threshold": "0", "unique_condition_id": uid})


def stat(kind: str, target: str, lo: float, hi: float | None = None, **kw) -> tuple:
    """数值直改（瞬发 32/33/34/35/55/…，开幕永久）。"""
    hi = lo if hi is None else hi
    given = {"strength": (pct(lo), pct(hi))}
    if target is not None:
        given["target"] = target
    given.update(kw)
    return (kind, given)


def condition(kind: str, target: str | None, strength: float | tuple[float, float] | None, frame_count: int | str,
              *, cancelable: bool = True, number: float = 1, **kw) -> tuple:
    """计时状态；strength 为单值或 (觉醒 0, 满破) 区间。"""
    given: dict[str, Any] = {}
    if target is not None:
        given["target"] = target
    if isinstance(strength, tuple):
        given["strength"] = (pct(strength[0]), pct(strength[1]))
    elif strength is not None:
        given["strength"] = pct(strength)
    given["frame"] = frame_count if isinstance(frame_count, str) else frames(frame_count)
    if "number" in _CASES["instant_content"][kind]["fields"]:
        given["number"] = times(number)
    given["cancelable"] = "0" if cancelable else "1"
    given.update(kw)
    return (kind, given)


def unique(uid: str, stacks: int = 1, target: str = T_SELF) -> tuple:
    return ("461", {"target": target, "strength": times(stacks), "number": times(1), "unique_condition_id": uid})


def invoke(string_id: str, program: str) -> tuple:
    return ("629", {"string_id": string_id, "action_path": program})


def during(kind: str, target: str | None, lo: float, hi: float | None = None) -> tuple:
    hi = lo if hi is None else hi
    given = {"strength": (pct(lo), pct(hi))}
    if target is not None:
        given["target"] = target
    return (kind, given)


def trig(kind: str, **given) -> tuple:
    return (kind, given)


def elapsed(frame_count: int, limit: str = "(None)") -> tuple:
    return (IT_ELAPSED, {"threshold": frames(frame_count), "trigger_limit": limit})


def gate_unique(uid: str, limit: str = "1", at_least: int = 1) -> tuple:
    """持续触发：自身持有固有状态 uid（≥at_least 层）；limit=倍乘上限（1 = 不随层数倍乘）。
    134 按层数计：uid 的叠层上限必须 >1，否则层数恒 0、永不生效（只看有没有用 has_unique / 前置 187）。"""
    return (DT_UNIQUE, {"trigger_puller": P_SELF, "threshold": times(at_least), "trigger_limit": limit,
                        "unique_condition_id": uid})


# ---------------------------------------------------------------------------
# DSL 速写（ActionDsl 树，wf_dsl.encode_amf3 可直接编码）
# ---------------------------------------------------------------------------

def P(v: float) -> list[dict[str, float]]:
    return [{"min": v, "max": v}]


def C(name: str, *args) -> list:
    return ["Command", [name, *args]]


def B(*cmds) -> list:
    return ["Block", list(cmds)]


def dsl_root(*cmds) -> list:
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, B(*cmds)]


def ac(name: str, frame_count: int, *params) -> list:
    return [name, P(frame_count), *params]


def give(subject: int, acs: list, key: str = "", cancelable: bool = True, force: bool = False) -> list:
    """CreateCondition(对象, AC 列表, 命中率 1, 通用演出, 可驱散, 去重, 键串, None, False, 付与种类 3, 层 1, 强制付与)。

    force = params[11] forceApply：绕过弱体耐性、各类 ConditionPrevent（DebuffPrevent 58 等）与增益无效；
    不跳过持续时间伸缩（「弱体时间缩短」仍会缩短）。键串 params[6] 即 discriminationKey，DeleteCondition 按它定点删除。"""
    return C("CreateCondition", subject, acs, P(1), ["GenericConditionHitEffect"], cancelable, False, key, None,
             False, 3, P(1), force)


def party(bind: int, *body) -> list:
    """FindAllSubjects(bind, 82=主小队三人不含多球, …)。"""
    return C("FindAllSubjects", bind, 82, [], [], [], [], [], ["DoNothing"], B(*body))


def slot_member(bind: int, selector: int, *body) -> list:
    """83/84/85 = 直接点名 1/2/3 号位主位。"""
    return C("FindAllSubjects", bind, selector, [], [], [], [], [], ["DoNothing"], B(*body))


def roulette(*branches: tuple[int, list]) -> list:
    return C("ConditionalsProbability", B(*[B(C("ProbabilityWeight", w), B(*body)) for w, body in branches]))


def wait(frame_count: int, *body) -> list:
    return ["Event", ["Wait", frame_count, "*", B(*body)]]


def dsl_program(name: str) -> str:
    return f"{DSL_DIR}${name}"


#: DSL 状态「永续」帧：≥99999 帧不参与持续时间伸缩（CommonBattleConstants / ConditionChangeCalculator:162）。
DSL_FOREVER = 9999999

#: 作者 0928「要求全部诅咒武器带的负面都是强制赋予，角色免疫也会生效」的统一偏差说明（强制赋予方案 §2.0）。
FORCED_CURSE_NOTE = ("作者 0928「诅咒负面都是强制赋予，角色免疫也会生效」：能力行的计时状态没有强制付与列（只有固有状态 c10 能强制），"
                     "改走 629 DSL CreateCondition forceApply（命中率固定 1）；绕过弱体耐性、各类无效"
                     "（含 PARADOX 魂珠自带的弱体无效）与增益无效，但不跳过持续时间伸缩（「弱体时间缩短」仍会缩短计时诅咒，永续不受影响）")

#: 强制赋予方案 §5.3：瞬发 209 扣血是强制付与管不到的一类（W04/W08/W18/W28/W29）。
FRIENDLY_FIRE_NOTE = ("作者 0928 强制赋予：瞬发 209 扣最大 HP 按友伤结算，友伤免疫（瞬发 467 / 持续 160）会直接清零"
                      "（RatioAttackCalculator）；玩家侧没有不经友伤判定的扣血入口，数据侧强制不了，真要防只能打客户端补丁"
                      "（让装备诅咒来源跳过友伤免疫判定）。live 能力表目前没有 467/160 来源")


def timed_curse_unique_note(name: str, seconds: int) -> str:
    """强制赋予方案 §5.1：坏方向计时固有状态的持续帧同样按方向伸缩（W22「断油」、W25「过载」）。"""
    return (f"作者 0928 强制赋予：「{name}」是坏方向计时固有状态，c10 强制只绕过免疫与弱体无效，持续帧仍按方向伸缩——"
            f"装备者的「弱体时间缩短」会缩短这 {seconds} 秒（减益延长则变长）；live 能力表目前没有缩短来源")


#: 官方 CreateCondition 第 8 参（linkedHitCheckKind）一律写 null（夏琳/基诺维等在役 DSL 同形）。
NULLABLE_DSL_ENUMS = frozenset({"HitCountCheckTargetKind"})


def dsl_signature_problems(tree: list) -> list[str]:
    """按 wf_dsl_sig（反编译生成的白名单）逐参核对：命令/事件名、参数个数、枚举构造名与嵌套参数、
    CreateCondition 的 AC 构造名与参数个数。编码器对拼错的构造名不报错（静默吞节点），必须在这里拦住。"""
    import wf_dsl_sig as SIG
    probs: list[str] = []
    enums = SIG.ENUMS

    def value(typ: str, v: Any, where: str) -> None:
        if v is None and typ in NULLABLE_DSL_ENUMS:
            return
        if typ in enums:
            if not (isinstance(v, list) and v and isinstance(v[0], str)):
                probs.append(f"{where}: {typ} 需要构造 [名, …]，得到 {v!r:.60}")
                return
            ctor = v[0]
            if ctor not in enums[typ]:
                probs.append(f"{where}: {typ}.{ctor} 不在白名单")
                return
            args = enums[typ][ctor]
            if len(v) - 1 != len(args):
                probs.append(f"{where}: {typ}.{ctor} 参数 {len(v) - 1} != {len(args)}")
                return
            for i, (t, x) in enumerate(zip(args, v[1:])):
                value(t, x, f"{where}.{ctor}[{i}]")
        elif typ == "ActionDslExpression" and v is not None:     # 官方 44 处可空表达式（如召唤球回调）
            expr(v, where)

    def expr(node: Any, where: str) -> None:
        if not (isinstance(node, list) and node and node[0] in ("Block", "Command", "Event")):
            probs.append(f"{where}: 不是 Block/Command/Event：{node!r:.60}")
            return
        if node[0] == "Block":
            for i, child in enumerate(node[1]):
                expr(child, f"{where}/{i}")
            return
        table = SIG.COMMANDS if node[0] == "Command" else SIG.EVENTS
        name, params = node[1][0], node[1][1:]
        if name not in table:
            probs.append(f"{where}: 未知 {node[0]} {name}")
            return
        sig = table[name]
        if sig is None:
            sig = {"Wait": ["int", "String", "ActionDslExpression"]}.get(name)
            if sig is None:
                return
        if len(params) != len(sig):
            probs.append(f"{where}: {name} 参数 {len(params)} != {len(sig)}")
            return
        for i, (t, x) in enumerate(zip(sig, params)):
            if name == "CreateCondition" and i == 1:
                for j, acv in enumerate(x):
                    value("AdditionalConditionKind", acv, f"{where}:{name}.ac{j}")
            else:
                value(t, x, f"{where}:{name}[{i}]")

    _require(isinstance(tree, list) and tree[0] == "ActionDsl" and len(tree) == 12, "DSL 根形状不对")
    expr(tree[11], "root")
    return probs


#: 按属性取素材的命中特效；无属性没有这几套素材（ActionDslAssetResolver.resolveNormalAttackHitEffect 抛 10013）。
ELEMENT_COLORED_HIT_EFFECTS = frozenset({"Fine", "Coarse", "Slash", "CriticalSlash"})


def colorless_hit_effect_problems(tree: list) -> list[str]:
    """装备词条的 DSL 以装备为主体，主体属性恒为无属性（AbilitySoulAbilityLogic ownerElement=6）。
    继承属性(255)/无属性(7) 的 CreateNormalAttack 配上按属性取素材的命中特效，进战斗预载即 C10013
    （1.4.1057 终焉拳套实机）。"""
    probs: list[str] = []

    def walk(node: Any) -> None:
        if not isinstance(node, list):
            return
        if node and node[0] == "Command" and isinstance(node[1], list) and node[1][0] == "CreateNormalAttack":
            params = node[1][1:]
            element, effect = params[1], params[14]
            if element in (255, 7) and isinstance(effect, list) and effect and effect[0] in ELEMENT_COLORED_HIT_EFFECTS:
                probs.append(f"CreateNormalAttack 属性 {element} 配命中特效 {effect[0]}：装备主体无属性，预载抛 C10013")
        for child in node:
            walk(child)

    walk(tree)
    return probs


def _commands(node: Any, name: str) -> Iterable[list]:
    """树里所有名为 name 的 Command 的参数列表（不含命令名）。"""
    if not isinstance(node, list):
        return
    if node and node[0] == "Command" and isinstance(node[1], list) and node[1] and node[1][0] == name:
        yield node[1][1:]
    for child in node:
        yield from _commands(child, name)


#: DeleteCondition params[3] cancelableKind（ConditionSlot.as:7246-7255）：0 只删可驱散、1 只删不可驱散、2 全删。
DELETE_CANCELABLE_ONLY, DELETE_NON_CANCELABLE_ONLY, DELETE_ALL = 0, 1, 2


def own_lock_delete_problems(dsl: dict[str, list]) -> list[str]:
    """DeleteCondition 只允许删自己挂的状态：必须带键串（空键连敌方给的同类状态一起删），键串要对得上本批某个
    CreateCondition，cancelableKind 要选得中那个状态——不可驱散（params[4]=False）的锁用 0 永远删不掉
    （1.4.1057 剑舞圆环 dance_release 实证：连击上限 9 从未解除）。"""
    created: dict[str, set[bool]] = {}
    for tree in dsl.values():
        for params in _commands(tree, "CreateCondition"):
            created.setdefault(params[6], set()).add(bool(params[4]))
    probs: list[str] = []
    for program, tree in dsl.items():
        for params in _commands(tree, "DeleteCondition"):
            kind, key = params[3], params[4]
            if not key:
                probs.append(f"{program}: DeleteCondition 空键串会连敌方给的同类状态一起删")
            elif key not in created:
                probs.append(f"{program}: DeleteCondition 键串 {key!r} 找不到本批的 CreateCondition")
            elif False in created[key] and kind == DELETE_CANCELABLE_ONLY:
                probs.append(f"{program}: DeleteCondition 键串 {key!r} 的状态不可驱散，cancelableKind 0 删不掉")
            elif True in created[key] and kind == DELETE_NON_CANCELABLE_ONLY:
                probs.append(f"{program}: DeleteCondition 键串 {key!r} 的状态可驱散，cancelableKind 1 删不掉")
    return probs


#: 按「层数」读固有状态的位置（反编译实证）：持续触发 134（层数 ≥ 阈值）/207（层数 ≤ 阈值）、前置 144/199、
#: 瞬发 525/526（消耗）、瞬发前置 1/2/3（消耗/判层，都走 consumeUniqueCondition）、DSL ConsumeUniqueCondition。
#: 前置 187/188 按状态个数计，不受叠层上限影响。
ACC_DURING_KINDS = frozenset({DT_UNIQUE, DT_UNIQUE_LOW})
ACC_PRE_KINDS = frozenset({PRE_UNIQUE_GE, PRE_UNIQUE_LE})
ACC_CONTENT_KINDS = frozenset({"525", "526"})
ACC_PRECONTENT_KINDS = frozenset({"1", "2", "3"})

#: 已知的层数门禁死行：不在本轮改动范围内（作者 0928「不动」），等作者决定后单独修复、单独重发。
#: 修好后必须从这里删掉（build 会把不再触发门禁的残留条目报出来）。
ACCUMULATION_CAP_PENDING: dict[str, str] = {}    # 09 蛰龙之心 / 13 封能风笛已于第三轮一并修复（上限 2）


def accumulated_unique_reads(table: str, row: list[str]) -> list[tuple[str, str]]:
    """该词条行里按层数读取的固有状态 [(位置, uid), ...]。"""
    reads: list[tuple[str, str]] = []
    for block in ("precondition1", "precondition2", "precondition3"):
        kind = row[_col(table, block, "kind")]
        if kind in ACC_PRE_KINDS:
            reads.append((f"前置 {kind}", row[_col(table, block, "unique_condition_id")]))
    if row[int(_LAYOUT[table]["blocks"]["precondition1"]) - 1] == "0":
        kind = row[_col(table, "instant_content", "kind")]
        if kind in ACC_CONTENT_KINDS:
            reads.append((f"瞬发 {kind}", row[_col(table, "instant_content", "unique_condition_id")]))
        kind = row[_col(table, "instant_precontent", "kind")]
        if kind in ACC_PRECONTENT_KINDS:
            reads.append((f"瞬发前置 {kind}", row[_col(table, "instant_precontent", "unique_condition_id")]))
    else:
        kind = row[_col(table, "during_trigger", "kind")]
        if kind in ACC_DURING_KINDS:
            reads.append((f"持续触发 {kind}", row[_col(table, "during_trigger", "unique_condition_id")]))
    return reads


def unique_accumulation_problems(rows: Iterable[tuple[str, str, list[str]]], dsl: dict[str, list],
                                 uniques: dict[str, list[list[str]]]) -> list[tuple[str, str]]:
    """被按层数读取/消耗的固有状态，叠层上限 c4 必须是 >1 的整数 ⇒ [(uid, 问题), ...]。

    客户端 ``Condition.get_accumulatable() = maxAccumulation > 1``（Condition.as:291-294）；为 false 时
    ``ConditionSlot._getConditionAccumulationCount`` 恒 0（134/144 永不生效、199/207 恒真），
    ``consumeUniqueCondition`` 三种模式都跳过（525/526/瞬发前置/DSL 消耗全是空操作）。
    ACUnique / 461 给 1 层照常，只有「按层数读」这一侧静默失效（第三轮复审：像素城之环刃/咸鱼王冠等 6 把实证）。
    rows = [(位置说明, 表, 行)]；只查本批 uniques 里的固有（官方固有不归这里管）。"""
    reads: list[tuple[str, str]] = []
    for where, table, row in rows:
        reads += [(f"{where} {what}", uid) for what, uid in accumulated_unique_reads(table, row)]
    for program, tree in dsl.items():
        reads += [(f"DSL {program} ConsumeUniqueCondition", str(params[1]))
                  for params in _commands(tree, "ConsumeUniqueCondition")]
    probs: list[tuple[str, str]] = []
    for where, uid in reads:
        if uid not in uniques:
            continue
        cap = uniques[uid][0][4]
        if not (cap.isdigit() and int(cap) > 1):
            probs.append((uid, f"{where} 按层数读固有 {uid}（{uniques[uid][0][1]}），但叠层上限 c4={cap!r} 不是 >1 的整数："
                               "get_accumulatable() 为 false，层数恒 0、消耗为空操作，词条静默失效"))
    return probs


def dsl_capabilities(tree: list) -> list[str]:
    """DSL 需要的客户端 capability：根头 tree[10] 或 CreateHitArea params[23] 的 buffTargetAs ≥100
    是 damage-type-rules 的段覆盖（未装补丁读成 0 按技能伤害结算，不崩，但归属不对）。
    判据与 wfx_gate 的 DSL 扫描共用 wf_battle_rules.dsl_capabilities。"""
    return BR.dsl_capabilities(tree)


def pf_echo_trigger_problems(table: str, row: list[str], dsl: dict[str, list]) -> list[str]:
    """按强化弹射段结算（131-133）的 629 树，其命中会被计为真实的 PF 命中，驱动「强化弹射命中」类触发
    （183 LvAny、对应等级 180-182、PowerFlipHitLvNHigh 15-17，见 wf_battle_rules.PF_SEGMENT_HIT_TRIGGERS）；
    用这些触发去触发它 = 自己的命中再次触发自己（复读弹射期间约每 60 帧连锁一次）。只能用强化弹射发动 (2) 等触发。"""
    if row[int(_LAYOUT[table]["blocks"]["precondition1"]) - 1] != "0" or row[_col(table, "instant_content", "kind")] != "629":
        return []
    tree = dsl.get(row[_col(table, "instant_content", "action_path")])
    if tree is None:
        return []
    trigger = row[_col(table, "instant_trigger", "kind")]
    if trigger in BR.pf_hit_triggers_driven_by(tree):
        segments = sorted(set(BR.dsl_segment_overrides(tree)) & set(BR.PF_SEGMENT_HIT_TRIGGERS))
        return [f"629 按强化弹射段结算（buffTargetAs {segments}）却由强化弹射命中类触发 {trigger} 触发："
                "会被自己的命中连锁触发"]
    return []


# ---------------------------------------------------------------------------
# 武器规格
# ---------------------------------------------------------------------------

@dataclass
class Weapon:
    row: int                   # 提案表行号（1..29）
    slug: str
    name: str
    category: str              # 服务端 equipment_lookup 类别
    elements: tuple[str, ...]  # 属性限制（空 = 通用）
    author: str
    look: str
    flavor: str
    summary_120: str           # 强化 120 解放说明（写进强化描述）
    soul: list[Eff] = field(default_factory=list)
    ea: list[Eff] = field(default_factory=list)
    uniques: dict[str, list[str]] = field(default_factory=dict)
    dsl: dict[str, list] = field(default_factory=dict)
    cas: dict[str, str] = field(default_factory=dict)
    deviations: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(ID_BASE + self.row)

    def uid(self, k: int) -> str:
        return str(UNIQUE_BASE + self.row * 10 + k)

    @property
    def icon(self) -> str:
        return f"{IMAGE_DIR}/{self.slug}_lv0"

    @property
    def icon120(self) -> str:
        return f"{IMAGE_DIR}/{self.slug}_lv120"

    def element_code(self) -> int:
        return ELEMENT_CODE[self.elements[0]] if len(self.elements) == 1 else -1


def unique_row(sid: str, name: str, icon: str, duration: str, max_acc: str, *, bad: bool,
               cancelable: bool = False, force: bool = True, keep_on_death: bool = True) -> list[str]:
    """unique_condition 15 列：sid,名称,图标,持续帧,最大层,弹射上限,PF上限,结束PF,结束PF档,可驱散,强制,方向,覆写,入棺移除,PF语音。"""
    return [sid, name, f"battle/common/unique_condition/{icon}", duration, max_acc, "(None)", "(None)", "(None)",
            "(None)", "true" if cancelable else "false", "true" if force else "false", "1" if bad else "0", "0",
            "false" if keep_on_death else "true", "(None)"]


#: 专属状态图标源目录（48×48；发布到 battle/common/unique_condition/<name>.png）
STATUS_ICON_DIR = REPOSITORY / "assets/cursed-weapons/status"
ICON_CURSE = "unique_devil_leader"          # 官方「诅咒」图标
ICON_TIME = "unique_gerald_time_seal"       # 时之刻印（计时类）
ICON_BUFF = "unique_fire_dragon_zenith"     # 勇敢之焰（增益类）
ICON_STACK = "unique_wind_spgirl_1anv"      # 神速剑技（叠层类）


KIND_LABEL = {"32": "攻击力", "0": "攻击力", "34": "技能伤害", "2": "技能伤害", "33": "直接攻击伤害", "1": "直接攻击伤害",
              "55": "强化弹射伤害", "23": "强化弹射伤害", "28": "强化弹射伤害", "388": "能力伤害", "35": "技能充能速度",
              "156": "增益持续时间", "227": "护盾", "211": "技能槽", "470": "逆境", "701": "技能充能速度",
              "694": "技能伤害独立乘区", "723": "伤害独立乘区", "717": "合击角色攻击力白值", "411": "技能伤害独立乘区",
              "410": "直接攻击伤害独立乘区", "413": "强化弹射伤害独立乘区", "421": "伤害独立乘区",
              "693": "直接攻击伤害独立乘区", "696": "强化弹射伤害独立乘区", "56": "Fever 时间"}
#: 瞬发「状态」类 kind 的名字（与持续类同号不同义：瞬发 1 = ConditionSkillDamage，持续 1 = 直击）。
COND_LABEL = {"0": "攻击力", "1": "技能伤害", "28": "强化弹射伤害", "470": "逆境", "701": "技能充能速度"}
TARGET_LABEL = {T_SELF: "自身", T_PARTY: "全队", T_LEADER: "队长", T_SECOND: "2号位", T_THIRD: "3号位",
                T_MULTIBALL: "协力球", T_TRIGGER: "触发者"}


def weak(x: float) -> float:
    """本体满破实际生效值（设计值 × BASE_SCALE）；觉醒 0 另乘 AWAKEN_FLOOR，见 :func:`_weaken`。"""
    return round(x * BASE_SCALE, 3)


def _grow(total: float, base: float) -> float:
    """强化 1→119 线性成长的满值：最终值 - 本体满破实际值 - 120 级补足（最终值的 2.5%）。base 为本体设计值。"""
    return round(total - weak(base) - total * 0.025, 3)


def _topup(total: float, base: float) -> float:
    return round(total - weak(base) - _grow(total, base), 3)


#: 说明里的强度写法：「+N%」（单值）或「+N%→M%」（区间）；每条本体数值行的说明恰好一处。
_STRENGTH_IN_NOTE = re.compile(r"\+(\d+(?:\.\d+)?)%(?:→(\d+(?:\.\d+)?)%)?")


def awaken_floor(first_max: str) -> str:
    """觉醒 0 的存储值：round(满破 × AWAKEN_FLOOR)（设计 §3.3 的取整口径）。"""
    return str(int(round(int(first_max) * AWAKEN_FLOOR)))


def _pct_text(stored: str) -> str:
    return f"{int(stored) / 1000:g}"


def _weaken(eff: Eff) -> Eff:
    """本体数值行（WEAK_KINDS 且有强度）：满破 = 设计满值 × BASE_SCALE，觉醒 0 = 满破 × AWAKEN_FLOOR（满破锚定）。

    设计里的区间下限（原 power1）不再使用：觉醒 0→4 = 满破的 20/40/60/80/100%，单值的计时状态也一样分级。
    说明里的「+N%」「+N%→M%」改写成「+觉醒0%→满破%」。机制类 kind 原样返回。"""
    kind, given = eff.content
    if kind not in WEAK_KINDS or "strength" not in given:
        return eff
    s_ = given["strength"]
    top = str(int(round(int(s_[1] if isinstance(s_, tuple) else s_) * BASE_SCALE)))
    strength = (awaken_floor(top), top)
    _require(int(strength[0]) < int(top), f"本体数值行满破值过小，觉醒分级后五级不可区分：{eff.note or eff.content}")
    # 觉醒 N = 满破 × (N+1)/5；满破须是 500（0.5%）的倍数，五级才都是整数或一位小数（设计 §1 Q4），且觉醒 0 恰为满破的 20%
    _require(int(top) % 500 == 0 and int(strength[0]) * 5 == int(top),
             f"本体数值行满破值 {_pct_text(top)}% 不是 0.5% 的倍数，觉醒分级会出现两位小数：{eff.note or eff.content}")
    found =_STRENGTH_IN_NOTE.findall(eff.note)
    _require(len(found) <= 1, f"本体说明里有多处强度，无法改写：{eff.note}")
    note = _STRENGTH_IN_NOTE.sub(f"+{_pct_text(strength[0])}%→{_pct_text(top)}%", eff.note)
    return replace(eff, content=(kind, {**given, "strength": strength}), note=note)


def growth_pair(kind: str, target: str | None, total: float, base: float, *, mode: str = "0",
                trig_: tuple = (IT_INITIAL, {}), pre: tuple = (), even_if_dead: bool = False,
                cond_frames: int | None = None, cancelable: bool = True, **extra) -> list[Eff]:
    """同一数值两行：强化 1→119 成长行（1/119 起步→满值）+ 120 级补足行。"""
    grow = _grow(total, base)
    top = _topup(total, base)
    rows = []
    label = (COND_LABEL if cond_frames is not None else KIND_LABEL).get(kind, kind)
    who = TARGET_LABEL.get(target, "") if target is not None else ""
    notes = (f"{who}{label}再 +{grow / 119:.3g}%→{grow:g}%（强化成长；本体实际 +{weak(base):g}%）",
             f"{who}{label}再 +{top:g}%（120 级补足，合计 +{total:g}%）")
    for (lo, hi, learn, maxlvl), note in zip(((grow / 119, grow, 1, 119), (top, top, 120, 120)), notes):
        if mode == "1":
            content = during(kind, target, lo, hi)
        elif cond_frames is not None:
            content = (kind, {**({"target": target} if target is not None else {}),
                              "strength": (pct(lo), pct(hi)), "frame": frames(cond_frames),
                              "number": times(1), "cancelable": "0" if cancelable else "1", **extra})
        else:
            content = stat(kind, target, lo, hi, **extra)
        rows.append(Eff(mode, content, trig=trig_, pre=pre, learn=learn, maxlvl=maxlvl, even_if_dead=even_if_dead,
                        note=note))
    return rows


def w01() -> Weapon:
    w = Weapon(1, "gluttony_knife", "饕餮餐刀", "剑", (), "神秘小罐头",
               "锯齿切肉刀，刃口带咬痕", "据说用它切过的面包，会连同主人的饥饿一起被吞下。",
               "发动技能时吞噬己方全部召唤协力球，每吞 1 个自身攻击力 +100%（30 秒，最多 9 个）")
    ids = list(DEVOUR_IDS)
    w.soul = [
        Eff("0", stat("32", T_SELF, 20, 40), note="自身攻击力 +20%→40%"),
        Eff("0", stat("32", T_SELF, 5, 10), trig=trig(IT_MB_REMOVE, threshold=times(1), trigger_limit="6"),
            note="己方协力球消失时，自身攻击力 +5%→10%（最多 6 次）"),
    ]
    program = dsl_program("gluttony_devour")
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
    ]
    w.deviations.append("第三轮「扣除协力球 100% 生命值」：玩家侧扣血钳到 1HP 消灭不了协力球，按 RemoveMultiball 真移除实现"
                        "（原生消失演出，计入协力球消失）；只覆盖 48 种存活的召唤协力球（不含炸弹球与关卡 NPC 助战），"
                        "正在出场/排队中的球会被静默移除且不计数；技能伤害半边按提案去掉")
    w.deviations.append("施放时场上没有可吞噬的协力球：否则分支为空，上一次的加成照常持续到结束（不刷新也不清除）")
    w.deviations.append("作者 0928「尽量还原原本设计」：去掉实现方加的常驻攻击力强化成长，只留提案的每吞 1 个 +100%"
                        "（强化 1 级起全额）；本体保留弱正面（常驻攻击与协力球消失叠攻），吞满 9 个时刃合计 920%")
    w.deviations.append("评分审查 0928（作者「按表改」）：吞噬加成持续 15 → 30 秒（盖满一轮约 30 秒的技能回转），"
                        "每球 +100%、上限 9 不动；同一键串后到的整条覆盖，不叠加")
    return w


def w02() -> Weapon:
    w = Weapon(2, "feast_drum", "狂宴战鼓", "饰品", (), "神秘小罐头",
               "红边战鼓与交叉鼓槌", "鼓声越狂，技能之力越被献给狂欢。",
               "进入 Fever 时全队技能槽 -100%；Fever 中全队攻击力 +1000%；Fever 时间 +100%")
    program = dsl_program("feast_drain")
    w.dsl[program] = dsl_root(party(0, C("SubtractSkillPoint", 0, P(1.0))))
    w.cas["cursed_feast_drain"] = "全队技能槽减少100%"
    fever = (DT_FEVER, {})
    w.soul = [Eff("1", during("0", T_PARTY, 100, 200), trig=fever, note="Fever 中全队攻击力 +100%→200%")]
    w.ea = [
        *growth_pair("0", T_PARTY, 1000, 200, mode="1", trig_=fever),
        Eff("0", invoke("cursed_feast_drain", program), trig=trig(IT_FEVER, threshold=times(1)),
            **CURSE, note="【诅咒】进入 Fever 时全队技能槽 -100%"),
        # 瞬发 56 FeverTimeExtension 没有目标字段（队伍级；官方魂珠 5040033 +20% 同形），不计刃/乘区
        *growth_pair("56", None, 100, 0),
    ]
    w.deviations.append("第三轮：诅咒 -50% → -100%；正面只留 Fever 中全队攻击力（终值 +1000%），去掉技能伤害与强化弹射伤害两项；"
                        "扣槽按技能槽容量的 100% 计（技能槽上限提高的角色扣得更多）")
    w.deviations.append("评分审查 0928（作者拍板「按方案做」）：新增 Fever 时间 +100%（强化成长，120 级合计；提案里没有这一条），"
                        "Fever 15 → 30 秒，只拉长 +1000% 的窗口；刃已顶格 1000%，+1000% 与进 Fever 扣槽 -100% 不动")
    return w


def w03() -> Weapon:
    w = Weapon(3, "salted_fish_crown", "咸鱼王冠", "饰品", ("wind",), "百合色彩虹桥",
               "戴着小王冠的咸鱼", "躺平的咸鱼也有王冠——只是要攒满两层才肯翻身。",
               "风属性共鸣时：发动技能获得「咸鱼蓄力」（最多 2 层）；满 2 层时发动技能，消耗 2 层并获得「咸鱼翻身」"
               "10 秒：技能伤害 +800%、技能伤害独立乘区 +30%；自身技能充能速度 -50%")
    wind = res("wind")
    u_flip, u_charge = w.uid(1), w.uid(2)
    # 叠层上限必须 >1：134 按层数计（翻身）、144/199/525 按层数读与消耗（蓄力）；上限 1 时全部静默失效。
    # 翻身 10 秒内再次获得只刷新时长（134 倍乘上限 1，加成不翻倍）
    w.uniques[u_flip] = unique_row(f"cursed_saltfish_{u_flip}", "咸鱼翻身", "cursed_saltfish_flip", "600", "2", bad=False)
    w.uniques[u_charge] = unique_row(f"cursed_saltfish_{u_charge}", "咸鱼蓄力", "cursed_saltfish_charge", "99999999", "2",
                                     bad=False)
    cast = trig(IT_SKILL, trigger_puller=P_SELF)
    # 三行同一触发，按施放前的「咸鱼蓄力」层数分流：≤1 层（199）+1 层；≥2 层（144）获得翻身并消耗 2 层。
    # 行序固定为 +1 → 翻身 → 消耗：固有状态的获得排队生效，若消耗当场生效，排在它前面的 +1 行已经按 2 层判定为不满足，
    # 不会在同一次施放里补回 1 层；翻身行也在消耗之前判定（按 2 层满足）。
    below_two = (PRE_UNIQUE_LE, {"trigger_puller": P_SELF, "threshold": times(1), "unique_condition_id": u_charge})
    at_two = (PRE_UNIQUE_GE, {"trigger_puller": P_SELF, "threshold": times(2), "unique_condition_id": u_charge})
    flipped = gate_unique(u_flip)
    w.soul = [
        Eff("0", stat("245", T_SELF, 100, 100), pre=(wind,), note="风属性共鸣时：自身技能槽上限 +100%（可蓄至 200%）"),
        Eff("0", unique(u_charge), trig=cast, pre=(wind, below_two),
            note="风属性共鸣时：「咸鱼蓄力」不满 2 层时发动技能，获得 1 层「咸鱼蓄力」"),
        Eff("0", unique(u_flip), trig=cast, pre=(wind, at_two),
            note="风属性共鸣时：「咸鱼蓄力」满 2 层时发动技能，获得「咸鱼翻身」10 秒"),
        Eff("0", ("525", {"target": T_SELF, "strength": times(2), "unique_condition_id": u_charge}), trig=cast,
            pre=(wind, at_two), note="「咸鱼蓄力」满 2 层时发动技能，消耗 2 层「咸鱼蓄力」"),
        Eff("1", during("2", T_SELF, 50, 100), trig=flipped, pre=(wind,), note="「咸鱼翻身」期间：自身技能伤害 +50%→100%"),
    ]
    w.ea = [
        *growth_pair("2", T_SELF, 800, 100, mode="1", trig_=flipped, pre=(wind,)),
        Eff("0", stat("35", T_SELF, -50), pre=(wind,), **CURSE,
            note="【诅咒】风属性共鸣时：自身技能充能速度 -50%"),
        Eff("1", during("411", T_SELF, 30), trig=flipped, pre=(wind,), **FINAL,
            note="「咸鱼翻身」期间：自身技能伤害独立乘区 +30%"),
    ]
    w.deviations.append("作者 0928「只有 2 层才触发消耗增伤」：不再看技能槽是否 200%，改为每次发动技能叠 1 层「咸鱼蓄力」"
                        "（上限 2、永续、不可驱散），满 2 层的那次施放消耗 2 层并获得 10 秒「咸鱼翻身」（施放前 0/1/2 层 → "
                        "+1/+1/翻身），即每 3 次施放翻身 1 次；翻身期间再发动技能不再清掉翻身。去掉前置 119/120")
    w.deviations.append("技能槽上限 +100% 保留：蓄到 200% 时翻身那次与紧接的下一次都在 10 秒窗口内，最好情况 3 次施放里 2 次吃到"
                        "加成（旧版最好是连放两次里 1 次），平均翻身频率 1/3–1/2 次施放，与旧版 200% 施放相当；数值不变")
    w.deviations.append("「咸鱼翻身」「咸鱼蓄力」叠层上限都写 2：客户端只对上限 >1 的状态计层（Condition.get_accumulatable），"
                        "上限 1 时 134/144 读层恒 0、199 恒真、525 消耗为空操作，整套静默失效")
    w.deviations.append("风险：同一施放三行的执行顺序与消耗是否排队需真机验证（行序已排成最坏情况也不串层）；固有状态排队生效，"
                        "翻身那次施放当帧结算的第一击可能吃不到加成；队友的 CountUp 瞬发内容也会让施放计数；"
                        "411 与其他技能伤害独立乘区相加不相乘")
    w.deviations.append("评分审查 0928（作者「按表改」）：「咸鱼翻身」期间技能伤害终值 +500% → +800%（机制简介「技能伤害变为 2 倍以上」）；"
                        "技能伤害独立乘区 +30%、充能 -50%、槽上限 +100% 不动")
    return w


def w04() -> Weapon:
    w = Weapon(4, "rebel_banner", "叛乱军旗", "枪", (), "百合色彩虹桥",
               "破损的深红战旗", "面包们举起了叛旗——冲锋时不分敌我。",
               "协力球攻击力 +350%、直接攻击伤害 +350%；协力球每次直接攻击时全队受到最大 HP 2% 的伤害（不致死，共用 CT1 秒）")
    u_ct = w.uid(1)
    # 叠层上限必须 >1：前置 199「层数 ≤0」在上限 1 时层数恒 0 ⇒ 恒真，共用 CT 失效。只在 0 层时上锁，实际只有 1 层
    w.uniques[u_ct] = unique_row(f"cursed_rebel_{u_ct}", "叛旗", "cursed_rebel_banner", "60", "2", bad=True)
    w.soul = [
        Eff("0", stat("32", T_MULTIBALL, 30, 60), note="协力球攻击力 +30%→60%"),
        Eff("0", stat("33", T_MULTIBALL, 30, 60), note="协力球直接攻击伤害 +30%→60%"),
        Eff("0", stat("205", T_MULTIBALL, 20, 40), note="协力球最大 HP +20%→40%"),
    ]
    hit = trig(IT_DIRECT, trigger_puller=P_ONE_OF_MULTIBALL, cooltime="60")
    ready = (lacks_unique(u_ct),)
    w.ea = [
        *growth_pair("32", T_MULTIBALL, 350, 60),
        *growth_pair("33", T_MULTIBALL, 350, 60),
        # 固有状态行必须排在扣血行之后：同一次派发内先判前置再上锁
        Eff("0", stat("209", T_PARTY, 2), trig=hit, pre=ready, **CURSE,
            note="【诅咒】协力球直接攻击时，全队受到最大 HP 2% 的伤害（共用 CT1 秒，不致死）"),
        Eff("0", unique(u_ct), trig=hit, pre=ready, **CURSE, note="进入「叛旗」1 秒（共用冷却）"),
    ]
    w.deviations.append("「面包攻击改为可伤害队友」是碰撞层行为；改为协力球每次撞击时对全队造成最大 HP 2% 的友伤（玩家侧伤害钳到 1HP）")
    w.deviations.append("第三轮「CT1s」：触发自带冷却按协力球各算，N 个球 = 每秒 N 次；改用 1 秒固有状态「叛旗」做全队共用冷却"
                        "（肉斩骨断同款）。风险：两个球同帧命中可能都先于上锁通过；持有者阵亡期间诅咒停止；"
                        "来源「协力球之一」官方零先例，需真机确认")
    w.deviations.append("「叛旗」叠层上限写 2：前置 199 按层数判「没有」，上限 1 的状态层数恒读 0，锁永远判为没有、共用 CT 失效"
                        "（N 个球 = 每秒 N 次）；只在 0 层时上锁，实际只挂 1 层")
    w.deviations.append(FRIENDLY_FIRE_NOTE)
    return w


def w05() -> Weapon:
    w = Weapon(5, "stopped_watch", "停摆怀表", "饰品", (), "百合色彩虹桥",
               "指针冻结的裂纹怀表", "时间在表盘里停住了——祝福与诅咒都不会再结束。",
               "全队增益/减益持续时间 +1000%；每 10 秒随机赋予全队 1 种减益（10 秒，不含无法行动类；强制付与，无视免疫）")
    program = dsl_program("watch_curse")
    minus = -0.2
    # 强制付与（作者 0928）；可驱散与否保持原样（驱散不是免疫）；键串留空：同种减益再次抽中时刷新，不叠加
    w.dsl[program] = dsl_root(party(0, roulette(
        (20, [give(0, [ac("ACAttackPoint", 600, P(minus), P(1))], force=True)]),
        (20, [give(0, [ac("ACSkillDamage", 600, P(minus), P(1))], force=True)]),
        (20, [give(0, [ac("ACPowerFlipDamage", 600, P(minus), P(1))], force=True)]),
        (20, [give(0, [ac("ACHealRejection", 600)], force=True)]),
        (20, [give(0, [ac("ACSkillGaugeCharging", 600, P(minus), P(1))], force=True)]),
    )))
    w.cas["cursed_watch_curse"] = ("随机赋予全队1种减益（攻击力/技能伤害/强化弹射伤害/技能充能速度降低20%，或回复无效，10秒；"
                                   "强制付与，无视免疫与弱体无效）")
    w.soul = [Eff("0", stat("156", T_PARTY, 25, 50), note="全队增益效果持续时间 +25%→50%")]
    w.ea = [
        *growth_pair("156", T_PARTY, 1000, 50),
        Eff("0", stat("155", T_PARTY, 1000), **CURSE, note="【诅咒】全队减益效果持续时间 +1000%"),
        Eff("0", invoke("cursed_watch_curse", program), trig=elapsed(600), **CURSE,
            note="【诅咒】每 10 秒随机赋予全队 1 种减益（10 秒；强制付与、无视免疫）"),
    ]
    w.deviations.append("「无视时间无限延长」改为持续时间 +1000%（次数型/消耗型效果照常结束，也不附带防驱散）")
    w.deviations.append(FORCED_CURSE_NOTE + "；随机减益本就是 DSL，只把 5 支都改成强制付与，仍可驱散（驱散不是免疫）")
    w.deviations.append("评分审查 0928：定为整活/机制型武器，数值不改。随机减益自身也吃减益持续 +1000%（10 秒 → 约 110 秒并累积），"
                        "敌方施加的麻痹、冻结同样 ×11；适合技能/强化弹射限时增益多的队伍")
    return w


def w06() -> Weapon:
    w = Weapon(6, "burnout_candle", "燃尽之烛", "杖", (), "水鱼",
               "顶端点着蜡烛的法杖", "最亮的火焰，只照亮最初的几次咏唱。",
               "自身攻击力与技能伤害 +500%，每发动 1 次技能两者各 -100%（最多 5 次）；自身技能槽上限 -15%（200% 槽降到 185%）")
    w.soul = [
        Eff("0", stat("32", T_SELF, 100, 200), note="自身攻击力 +100%→200%"),
        Eff("0", stat("34", T_SELF, 100, 200), note="自身技能伤害 +100%→200%"),
    ]
    skill = trig(IT_SKILL, trigger_puller=P_SELF, trigger_limit="5")
    w.ea = [
        *growth_pair("32", T_SELF, 500, 200),
        *growth_pair("34", T_SELF, 500, 200),
        Eff("0", stat("32", T_SELF, -100), trig=skill, **CURSE,
            note="【诅咒】发动技能时自身攻击力 -100%（最多 5 次）"),
        Eff("0", stat("34", T_SELF, -100), trig=skill, **CURSE,
            note="【诅咒】发动技能时自身技能伤害 -100%（最多 5 次）"),
        Eff("0", stat("245", T_SELF, -15), **CURSE, note="【诅咒】自身技能槽上限 -15%（200% 槽降到 185%）"),
    ]
    # 作者 0928 口径：「技能槽最大值 -15%」= 第二段槽上限 200%→185%。原生 245 各来源先求和再钳到 [0,1]
    # （MemberImpl.as:646-647），负值只抵消其他 +上限来源；没有 200% 槽时不生效，槽不会低于 100%。
    w.deviations.append("「技能槽最大值 -15%」按作者口径做成技能槽上限 -15%（245）：有 200% 槽时降到 185%，"
                        "没有其他槽上限加成时不生效（引擎槽容量不低于 100%）")
    return w


def _full_screen_attack(multiplier: float, *, buff_target_as: int = 0, delay: int = 0) -> list:
    """对全体敌人造成自身攻击力 multiplier 倍的伤害（默认按技能伤害结算）。

    装备 DSL 的主体属性恒为无属性，命中特效只能用不按属性取素材的构造（见 colorless_hit_effect_problems）；
    这里用官方通用的 Explosion。伤害按无属性结算：不吃克制，也不会走到 10014（forceUncolorless 只在炸弹球里）。
    buff_target_as 写进根头 tree[10]（PF3_BTA = 按强化弹射 Lv3 结算，需要 damage-type-rules-v1）；delay>0 时包一层 Wait。
    """
    # 26 参照 work/codex_out/hitarea_params.md：全屏 = 3600×3600 矩形（官方 8 例）；p15 每目标硬帽 1；
    # p16 eliminatedOnHit 必须 False（True 会命中第一个敌人就移除，打不到其余目标）。
    area = C("CreateHitArea", "*", -18, ["AB"], 0, 0, 0, False, False,
             ["Rectangle", P(3600), P(3600)], ["Center"], ["Center"],
             ["Single"], ["SpecifyHitAreaLifetimeDirectly", 2], ["CalculatedUsingMaxNumOfHits", 1],
             ["Some", P(1)], False, True, ["None"], 0, B(), 1, 2,
             B(C("CreateNormalAttack", 2, 255, [], [], 0, P(multiplier), P(0), False, False, False, False,
                 False, P(0.25), P(0.25), ["Explosion"], True)),
             0, 0, ["None"])
    tree = dsl_root(wait(delay, area) if delay > 0 else area)
    tree[10] = buff_target_as
    return tree


def _echo_hit(multiplier: float, *, buff_target_as: int = PF3_BTA) -> list:
    """跟球的小判定区（半径 60、100 帧、命中第一个敌人即移除）：追加 1 次 multiplier 倍伤害。

    外形照官方瓦格纳 629 追击的外层判定区；命中特效同样只能用 Explosion。根头 133 按强化弹射 Lv3 结算——
    这些命中会被计为真实的 PF Lv3 命中，**不能**再用「强化弹射命中」(183) 触发本树，否则会被自己的命中再次触发。"""
    tree = dsl_root(C("CreateHitArea", "*", -18, ["AB"], 0, 0, 0, True, False, ["Circle", P(60)], ["Center"], ["Center"],
                      ["Single"], ["SpecifyHitAreaLifetimeDirectly", 100], ["CalculatedUsingMaxNumOfHits", 1],
                      ["Some", P(1)], True, True, ["None"], 0, B(), 1, 2,
                      B(C("CreateNormalAttack", 2, 255, [], [], 0, P(multiplier), P(0), False, False, False, False,
                          False, P(0.25), P(0.25), ["Explosion"], True)),
                      0, 0, ["None"]))
    tree[10] = buff_target_as
    return tree


def w07() -> Weapon:
    w = Weapon(7, "finality_gauntlet", "氪金的力量", "拳", ("fire", "water"), "P.P.P.P",
               "镶有星导石的拳套", "一拳之后，世界与你一同静止。",
               "火/水属性共鸣时：全队攻击、技能伤害、能力伤害 +200%；发动技能时全场 6 倍 + 10 倍技能伤害（各 CT0.5 秒）；"
               "8 秒后全队永续麻痹、封印，攻击力/技能伤害/能力伤害 -886%（强制付与，无视免疫，不可驱散）")
    uid_end = w.uid(1)
    w.uniques[uid_end] = unique_row(f"cursed_finality_{uid_end}", "终焉", "cursed_finality_end", "99999999", "1", bad=True)
    fist_a, fist_b, fist_c = (dsl_program(f"finality_fist_{k}") for k in "abc")
    w.dsl[fist_a], w.dsl[fist_b], w.dsl[fist_c] = (_full_screen_attack(x) for x in (1.0, 5.0, 10.0))
    w.cas["cursed_finality_fist_a"] = "对全体敌人造成1倍技能伤害"
    w.cas["cursed_finality_fist_b"] = "对全体敌人造成5倍技能伤害"
    w.cas["cursed_finality_fist_c"] = "对全体敌人造成10倍技能伤害"
    skill_ct = trig(IT_SKILL, trigger_puller=P_SELF, cooltime="30")
    eight_s = elapsed(480, "1")
    revive = trig(IT_REVIVAL, trigger_puller=P_ONE_OF_PARTY)
    after = has_unique(uid_end)
    # 作者 0928 强制赋予：能力表 19/219/0/1/486 没有强制付与列，改为一棵 DSL 一次付 5 个强制状态（各自键串，复活重挂幂等）。
    # ACParalysis 第 2 参写 True：引擎取反得 Paralysis(false)，与能力表 19 一致（W10 同形）
    doom = dsl_program("finality_doom")
    w.dsl[doom] = dsl_root(party(
        0,
        give(0, [ac("ACParalysis", DSL_FOREVER, True)], "cursed_finality_para", cancelable=False, force=True),
        give(0, [ac("ACSilence", DSL_FOREVER)], "cursed_finality_seal", cancelable=False, force=True),
        give(0, [ac("ACAttackPoint", DSL_FOREVER, P(-8.86), P(1))], "cursed_finality_atk", cancelable=False, force=True),
        give(0, [ac("ACSkillDamage", DSL_FOREVER, P(-8.86), P(1))], "cursed_finality_skill", cancelable=False, force=True),
        give(0, [ac("ACAbilityDamage", DSL_FOREVER, P(-8.86), P(1))], "cursed_finality_ability", cancelable=False,
             force=True)))
    w.cas["cursed_finality_doom"] = ("全队永续麻痹、封印，攻击力/技能伤害/能力伤害降低886%"
                                     "（强制付与，无视免疫与弱体无效，不可驱散）")
    rows_s, rows_e = [], []
    for element in ("fire", "water"):
        gate = (res(element),)
        cn = "火" if element == "fire" else "水"
        rows_s += [
            Eff("0", stat("32", T_PARTY, 75, 150), pre=gate, note=f"{cn}属性共鸣时：全队攻击力 +75%→150%"),
            Eff("0", stat("34", T_PARTY, 75, 150), pre=gate, note=f"{cn}属性共鸣时：全队技能伤害 +75%→150%"),
            Eff("0", stat("388", T_PARTY, 75, 150), pre=gate, note=f"{cn}属性共鸣时：全队能力伤害 +75%→150%"),
            Eff("0", invoke("cursed_finality_fist_a", fist_a), trig=skill_ct, pre=gate,
                note=f"{cn}属性共鸣时：发动技能时对全体敌人造成 1 倍技能伤害（CT0.5 秒）"),
        ]
        rows_e += [
            *growth_pair("32", T_PARTY, 200, 150, pre=gate),
            *growth_pair("34", T_PARTY, 200, 150, pre=gate),
            *growth_pair("388", T_PARTY, 200, 150, pre=gate),
            Eff("0", invoke("cursed_finality_fist_b", fist_b), trig=skill_ct, pre=gate, **FINAL,
                note="发动技能时再对全体敌人造成 5 倍技能伤害（与本体合计 6 倍，CT0.5 秒）"),
            Eff("0", invoke("cursed_finality_fist_c", fist_c), trig=skill_ct, pre=gate, **FINAL,
                note="发动技能时再对全体敌人造成 10 倍技能伤害（CT0.5 秒）"),
            Eff("0", unique(uid_end), trig=eight_s, pre=gate, **CURSE, note="8 秒后刻下「终焉」"),
            Eff("0", invoke("cursed_finality_doom", doom), trig=eight_s, pre=gate, **CURSE,
                note="【诅咒】8 秒后全队永续麻痹、封印，攻击力/技能伤害/能力伤害 -886%（强制付与、无视免疫、不可驱散）"),
            Eff("0", invoke("cursed_finality_doom", doom), trig=revive, pre=(*gate, after), **CURSE,
                note="「终焉」后复活时重新附加以上诅咒（同键幂等）"),
        ]
    w.soul, w.ea = rows_s, rows_e
    w.deviations.append("「攻刃 -886%」引擎攻击加成总和下限 -50%（STAT_MODIFIER_ATTACK_POINT_MIN），技能/能力伤害 -886% 会压到单次 1 伤害；"
                        "「无法接触的麻痹」按不可驱散的麻痹实现")
    w.deviations.append("第三轮：改名「氪金的力量」、外形「镶有星导石的拳套」（沿用 slug 与图标路径）；数值与第二轮一致")
    w.deviations.append("作者 0928 数值预算（刃合计 ≤1000%）：全队攻击、技能伤害、能力伤害终值各 +600% → +300%；"
                        "评分审查 0928（作者「按表改」）再降到 +200%（合计 600%），清掉「爆发等效 >1000%」的严重超模红线"
                        "（火队开局一轮技能约 1164 → 793）；本体设计值与 8 秒 -886% 诅咒、1/5/10 倍全屏命中（固定倍率，不计刃）不动")
    w.deviations.append(FORCED_CURSE_NOTE + "；每属性原 10 行（8 秒 5 种 + 复活重挂 5 种）合并为 2 行 629，"
                        "一棵 DSL 付 5 个强制、不可驱散的状态")
    return w


def w08() -> Weapon:
    w = Weapon(8, "sisyphus_stone", "西西弗斯的石头", "盾", (), "百合色彩虹桥",
               "被锁链缠住的巨石", "推到山顶的那一刻，石头总会滚落。",
               "HP≥40% 时自身攻击与技能伤害 +500%；自身 HP<40% 时全队攻击与技能伤害 -100%（攻击力受引擎下限 -50%）；"
               "HP 回满时 HP 降至 0.1% 并获得最大 HP 30% 的护盾")
    # 评分审查 0928 方案②（作者拍板）：正面/诅咒的分界 50% → 40%，两条阈值同步，正面区 40%–99.9%
    hp40 = (DT_HP_HIGH, {"trigger_puller": P_SELF, "threshold": pct(40)})
    low40 = (DT_HP_LOW_EX, {"trigger_puller": P_SELF, "threshold": pct(40)})
    w.soul = [
        Eff("1", during("0", T_SELF, 30, 60), trig=hp40, note="HP≥40% 时自身攻击力 +30%→60%"),
        Eff("1", during("2", T_SELF, 30, 60), trig=hp40, note="HP≥40% 时自身技能伤害 +30%→60%"),
    ]
    full = (elapsed(30), ((PRE_HP_HIGH, {"trigger_puller": P_SELF, "threshold": pct(100)}),))
    w.ea = [
        *growth_pair("0", T_SELF, 500, 60, mode="1", trig_=hp40),
        *growth_pair("2", T_SELF, 500, 60, mode="1", trig_=hp40),
        # 判定看持有者 HP、作用全队；持有者阵亡时 HP=0 仍 <40%，even_if_dead 让诅咒不因阵亡解除
        Eff("1", during("0", T_PARTY, -100), trig=low40, even_if_dead=True, **CURSE,
            note="【诅咒】自身 HP<40% 时全队攻击力 -100%（引擎下限 -50%）"),
        Eff("1", during("2", T_PARTY, -100), trig=low40, even_if_dead=True, **CURSE,
            note="【诅咒】自身 HP<40% 时全队技能伤害 -100%"),
        Eff("0", stat("209", T_SELF, 99.9), trig=full[0], pre=full[1], **CURSE,
            note="【诅咒】HP 为 100% 时（每 0.5 秒检查）失去最大 HP 的 99.9%"),
        Eff("0", stat("227", T_SELF, 30), trig=full[0], pre=full[1], delay=1, **CURSE,
            note="随后获得最大 HP 30% 的护盾"),
    ]
    w.deviations.append("第三轮：正面终值 +150% → +350%；诅咒由自身 -50% 改为持有者 HP<50% 时全队 -100%。"
                        "攻击力 -100% 实际是「先抵消最多 +50% 的其他攻击加成，再到引擎下限 -50%」；技能伤害 -100% 真实生效"
                        "（队伍没有其他技能伤害加成时单次伤害为 1）；持有者阵亡后诅咒仍生效")
    w.deviations.append("评分审查 0928（作者「按表改」，含拍板项②）：自身攻击/技能伤害终值 +350% → +500%（刃顶格 1000%）；"
                        "正面与诅咒的 HP 分界 50% → 40%（偏离提案数字，作者拍板）。西西弗斯循环（满血失去 99.9% + 30% 护盾）不动；"
                        "回复队专用：HP 回满即重置到 0.1%，持有者阵亡后诅咒不解除")
    w.deviations.append(FRIENDLY_FIRE_NOTE + "（本把：满血失去 99.9%）")
    return w


def w09() -> Weapon:
    w = Weapon(9, "dormant_dragon_heart", "蛰龙之心", "饰品", ("fire", "thunder"), "脆脆鲨",
               "余烬与电光交织的龙心结晶", "沉睡的龙心只在两个时刻苏醒。",
               "火/雷属性共鸣时：0–49 秒全队伤害 -99%；50–59 秒攻击 +500%、伤害独立 +30%；61–109 秒再度 -99%；"
               "110–129 秒攻击 +1000%、伤害独立 +50%；131 秒起永久伤害 -90%（均不可驱散）")
    u_dorm, u_wake1, u_wake2, u_dry = w.uid(1), w.uid(2), w.uid(3), w.uid(4)
    # 四个阶段都被持续触发 134（按层数）读：叠层上限必须 >1（上限 1 时层数恒 0，1.4.1057–1069 期间阶段效果从未生效）
    w.uniques[u_dorm] = unique_row(f"cursed_dragon_{u_dorm}", "蛰伏", "cursed_dragon_dormant", "2940", "2", bad=True)
    w.uniques[u_wake1] = unique_row(f"cursed_dragon_{u_wake1}", "苏醒", "cursed_dragon_awaken", "600", "2", bad=False)
    # 评分审查 0928：「龙怒」10 → 20 秒（110–129 秒），「枯竭」顺延到第 131 秒，两段不重叠
    w.uniques[u_wake2] = unique_row(f"cursed_dragon_{u_wake2}", "龙怒", "cursed_dragon_wrath", "1200", "2", bad=False)
    w.uniques[u_dry] = unique_row(f"cursed_dragon_{u_dry}", "枯竭", "cursed_dragon_dry", "99999999", "2", bad=True)
    for element in ("fire", "thunder"):
        gate = (res(element),)
        # 本体弱正面：只在「苏醒」同一时刻（第 50 秒，10 秒），与「龙怒」窗口不重叠，刃上限按「龙怒」+1000% 计
        w.soul.append(Eff("0", condition("0", T_PARTY, 100, 600), trig=elapsed(3000, "1"), pre=gate,
                          note=f"{'火' if element == 'fire' else '雷'}属性共鸣时：第 50 秒起全队攻击力 +100%（10 秒）"))
        w.ea += [
            Eff("0", unique(u_dorm), pre=gate, **CURSE, note="开局「蛰伏」49 秒"),
            Eff("0", unique(u_wake1), trig=elapsed(3000, "1"), pre=gate, **CURSE, note="第 50 秒「苏醒」10 秒"),
            Eff("0", unique(u_dorm), trig=elapsed(3660, "1"), pre=gate, **CURSE, note="第 61 秒再度「蛰伏」49 秒"),
            Eff("0", unique(u_wake2), trig=elapsed(6600, "1"), pre=gate, **CURSE, note="第 110 秒「龙怒」20 秒"),
            Eff("0", unique(u_dry), trig=elapsed(7860, "1"), pre=gate, **CURSE, note="第 131 秒「枯竭」（永久）"),
            Eff("1", during("421", T_PARTY, -99), trig=gate_unique(u_dorm), pre=gate, even_if_dead=True,
                **CURSE, note="【诅咒】「蛰伏」期间全队伤害独立乘区 -99%"),
            Eff("1", during("0", T_PARTY, 50, 500), trig=gate_unique(u_wake1), pre=gate, even_if_dead=True,
                **CURSE, note="「苏醒」期间全队攻击力 +500%"),
            Eff("1", during("421", T_PARTY, 3, 30), trig=gate_unique(u_wake1), pre=gate, even_if_dead=True,
                **CURSE, note="「苏醒」期间全队伤害独立乘区 +30%"),
            Eff("1", during("0", T_PARTY, 100, 1000), trig=gate_unique(u_wake2), pre=gate, even_if_dead=True,
                **CURSE, note="「龙怒」期间全队攻击力 +1000%"),
            Eff("1", during("421", T_PARTY, 5, 50), trig=gate_unique(u_wake2), pre=gate, even_if_dead=True,
                **CURSE, note="「龙怒」期间全队伤害独立乘区 +50%"),
            Eff("1", during("421", T_PARTY, -90), trig=gate_unique(u_dry), pre=gate, even_if_dead=True,
                **CURSE, note="【诅咒】「枯竭」后全队伤害独立乘区 -90%"),
        ]
    w.deviations.append("时间点按战斗计时（ElapsedTime）；「输出 -99% / -90%」用伤害独立乘区实现（固定伤害等少数来源不经过该乘区）")
    w.deviations.append("作者 0928 数值预算（刃 ≤1000%、乘区 ≤50%）+「尽量还原原本设计」：攻击恢复提案「苏醒」+500%、「龙怒」+1000%，"
                        "伤害独立乘区「苏醒」+300% → +30%、「龙怒」+500% → +50%（保持 3:5）；去掉实现方加的每 10 秒叠攻；"
                        "两个窗口时间上不重叠，按「龙怒」计刃 1000%")
    w.deviations.append("评分审查 0928（作者「按表改」）：「龙怒」10 → 20 秒（110–129 秒），「枯竭」顺延到第 131 秒（避免与拉长后的"
                        "龙怒重叠）；苏醒 50–59 秒、两段蛰伏、+500%/+30%、+1000%/+50%、-99%/-90% 与本体第 50 秒弱加成都不动；"
                        "战斗短于 110 秒见不到龙怒，只适合长时间 boss 战")
    return w


def w10() -> Weapon:
    w = Weapon(10, "fate_dice", "赌注已下", "饰品", (), "P.P.P.P",
               "黑色的老虎机，屏幕上停着头奖", "拉杆落下的那一刻，赌注就再也收不回来了。",
               "开局 15 秒全队伤害独立乘区 +2%、攻击力 +20%；每 25 秒转一次（直击/强化弹射/技能 × 增益/诅咒 六种结果，"
               "增益与诅咒权重 3:1，每种增益 1/4、每种诅咒 1/12；增益持续 20 秒，诅咒持续 10 秒；"
               "直击诅咒的麻痹与弹球不受控制为 5 秒）：增益——直击=浮游+迅捷+直击伤害 +500%，"
               "强化弹射=贯通+加速+强化弹射伤害 +500%+「复读弹射」，技能=技能槽 +100%+技能伤害 +500%+充能速度 +20%；"
               "诅咒——直击=弹球不受控制 5 秒+随机两名主位麻痹 5 秒+全队减速 10 秒，"
               "强化弹射=连击上限 1+增益无效，技能=技能槽 -80%+技能伤害独立乘区 -100%")
    u_mark, u_open, u_echo, u_bust = w.uid(1), w.uid(2), w.uid(3), w.uid(4)
    # 被 134（层数 ≥）/199（层数 ≤0）读的固有叠层上限必须 >1（上限 1 时层数恒 0）；「复读弹射」只被 187（按个数）读，保持 1
    w.uniques[u_mark] = unique_row(f"cursed_dice_{u_mark}", "赌局", "cursed_wager_table", "99999999", "2", bad=False)
    w.uniques[u_open] = unique_row(f"cursed_dice_{u_open}", "开局赌注", "cursed_wager_opening", "900", "2", bad=False)
    w.uniques[u_echo] = unique_row(f"cursed_dice_{u_echo}", "复读弹射", "cursed_wager_echo", "1200", "1", bad=False)
    w.uniques[u_bust] = unique_row(f"cursed_dice_{u_bust}", "血本无归", "cursed_wager_bust", "600", "2", bad=True)
    lite, full, echo = dsl_program("fate_roll_lite"), dsl_program("fate_roll"), dsl_program("fate_echo")
    w.dsl[lite] = dsl_root(party(0, roulette(
        (1, [give(0, [ac("ACDirectDamage", 600, P(0.12), P(1))])]),
        (1, [give(0, [ac("ACPowerFlipDamage", 600, P(0.16), P(1))])]),
        (1, [give(0, [ac("ACSkillDamage", 600, P(0.12), P(1))])]),
    )))
    w.cas["cursed_fate_roll_lite"] = "随机赋予全队1种增益（直接攻击伤害+12%/强化弹射伤害+16%/技能伤害+12%，10秒）"

    def paralyse(bind: int, selector: int) -> list:
        return slot_member(bind, selector, give(bind, [ac("ACParalysis", 300, True)], cancelable=False, force=True))

    # ACUnique 单独一条 CreateCondition（可驱散/强制由 unique_condition 表决定）。
    # 评分审查 0928：增益三支权重 3、诅咒三支权重 1（每种增益 1/4、每种诅咒 1/12）；增益 20 秒（仍短于 25 秒周期，不重叠），诅咒不动
    buff = 1200
    w.dsl[full] = dsl_root(roulette(
        (3, [party(0, give(0, [ac("ACFlying", buff)]), give(0, [ac("ACSwift", buff)]),
                   give(0, [ac("ACDirectDamage", buff, P(5.0), P(1))]))]),
        (3, [party(0, give(0, [ac("ACPiercing", buff)]), give(0, [ac("ACSpeedup", buff, P(0.3), P(1))]),
                   give(0, [ac("ACPowerFlipDamage", buff, P(5.0), P(1))])),
             give(-17, [["ACUnique", int(u_echo), P(1)]], "cursed_dice_echo", cancelable=False)]),
        (3, [party(0, C("AddSkillPoint", 0, P(1.0)), give(0, [ac("ACSkillDamage", buff, P(5.0), P(1))]),
                   give(0, [ac("ACSkillGaugeCharging", buff, P(0.2), P(1))]))]),
        (1, [party(0, give(0, [ac("ACComboRestriction", 600, P(1))], cancelable=False, force=True),
                   give(0, [ac("ACBuffRejection", 600)], cancelable=False, force=True))]),
        (1, [roulette((1, [paralyse(0, 83), paralyse(1, 84)]),
                      (1, [paralyse(0, 83), paralyse(1, 85)]),
                      (1, [paralyse(0, 84), paralyse(1, 85)])),
             C("SuppressBallActivity", -18, P(300)),
             party(0, give(0, [ac("ACSpeedup", 600, P(-0.35), P(1))], cancelable=False, force=True))]),
        (1, [party(0, C("SubtractSkillPoint", 0, P(0.8))),
             give(-17, [["ACUnique", int(u_bust), P(1)]], "cursed_dice_bust", cancelable=False)]),
    ))
    w.cas["cursed_fate_roll"] = ("转动老虎机：直击（浮游、迅捷、直接攻击伤害+500%）／强化弹射（贯通、加速、强化弹射伤害+500%、"
                                 "「复读弹射」）／技能（技能槽+100%、技能伤害+500%、充能速度+20%）三种增益（各1/4，20秒），"
                                 "或对应诅咒（各1/12）：随机两名主位麻痹且弹球不受控制5秒、全队减速10秒／连击上限1且增益无效10秒／"
                                 "全队技能槽-80%且「血本无归」10秒")
    w.dsl[echo] = _echo_hit(7.0)
    w.cas["cursed_fate_echo"] = "强化弹射命中敌人时追加1次强化弹射伤害（7倍）"
    every25 = elapsed(1500)
    # 本体只有 629 一行、没有强度可分级：用触发周期分级（设计 §3.3），ElapsedTime 阈值随觉醒插值 45/40/35/30/25 秒。
    # 强化表的完整老虎机仍每 25 秒（强化要求满破，且不碰 EA）。
    awaken_period = trig(IT_ELAPSED, threshold=(frames(2700), frames(1500)), trigger_limit="(None)")
    opening = gate_unique(u_open)
    w.soul = [Eff("0", invoke("cursed_fate_roll_lite", lite), trig=awaken_period, pre=(lacks_unique(u_mark),),
                  note="每 45→25 秒（每觉醒 1 级缩短 5 秒）随机赋予全队 1 种增益（10 秒）")]
    w.ea = [
        Eff("0", unique(u_mark), **CURSE, note="「赌局」：本体的温和转轮换成完整老虎机"),
        Eff("0", unique(u_open), **CURSE, note="开局获得「开局赌注」15 秒"),
        Eff("1", during("421", T_PARTY, 2), trig=opening, even_if_dead=True, **CURSE,
            note="「开局赌注」期间全队伤害独立乘区 +2%"),
        Eff("1", during("0", T_PARTY, 20), trig=opening, even_if_dead=True, **CURSE,
            note="「开局赌注」期间全队攻击力 +20%"),
        Eff("0", invoke("cursed_fate_roll", full), trig=every25, **CURSE,
            note="【诅咒】每 25 秒转一次：三种增益（各 1/4，20 秒）或三种诅咒（各 1/12，10 秒；"
                 "直击诅咒的麻痹与弹球不受控制 5 秒；诅咒强制付与、不可驱散）"),
        # 只能用强化弹射发动(2)触发：复读命中按 PF Lv3 计，用强化弹射命中(183)会被自己的命中连锁触发
        Eff("0", invoke("cursed_fate_echo", echo), trig=trig(IT_PF, threshold=times(1)), pre=(has_unique(u_echo),),
            **CURSE, note="「复读弹射」期间打出强化弹射：命中敌人时追加 1 次 7 倍强化弹射伤害"),
        Eff("1", during("411", T_PARTY, -100), trig=gate_unique(u_bust), even_if_dead=True, **CURSE,
            note="【诅咒】「血本无归」期间全队技能伤害独立乘区 -100%"),
    ]
    w.deviations.append("第三轮：改名「赌注已下」、外形黑色老虎机（沿用 slug 与图标路径）；开局「开局赌注」15 秒 = 全队伤害独立乘区 +2% "
                        "与攻击力 +20%（提案未给攻刃数值，暂定 +20%）；三种增益刃值全部 +500%；强化弹射增益去掉连击 +40")
    w.deviations.append("直击「冲刺 CD 缩短为 30%」：原生有冲刺冷却效果——迅捷（ACSwift）把冲刺恢复压到 20 帧（约 22%，比 30% 略强），"
                        "浮游单独只到 60 帧；去掉旧的「球速 +35%」替代。迅捷/浮游是弹球级状态，作用全队")
    w.deviations.append("强化弹射「复读一次 PF 伤害」：DSL 读不到上一次伤害，改为「复读弹射」20 秒内（评分审查 0928 前为 10 秒）每次强化弹射追加 1 次"
                        "持有者攻击力 7 倍的无属性命中（约一段 Lv3 PF）；根头 133 按强化弹射 Lv3 结算，需要 damage-type-rules-v1，"
                        "未装补丁按技能伤害结算（不崩）。复读命中会被计为真实 PF Lv3 命中，喂给全队的强化弹射命中类触发；"
                        "因此只用强化弹射发动(2)触发，不用强化弹射命中(183)（后者会被自己的命中约每 60 帧连锁一次）")
    w.deviations.append("诅咒：直击「不受控制」= 弹球不受控制 5 秒（不能冲刺/施放技能，弹板仍可用）+ 随机两名主位麻痹 5 秒 + "
                        "全队减速 10 秒（引擎减速下限 35%，速度固定类增益无视减速）；强化弹射「无法获取强化 buff」= 增益无效"
                        "（拦截所有新增增益 10 秒，强制付与的来源除外）；技能「技能伤害为 1」= 「血本无归」10 秒内全队技能伤害"
                        "独立乘区 -100%（与队伍其他技能伤害独立乘区相加，有正向加成时不会完全归 1）")
    w.deviations.append("风险：迅捷、增益无效、负值加速、根头 133 的 629 复读在玩家侧官方零先例，六个分支都需真机冒烟；"
                        "同队诅咒互斥只在装了 equipment-rules-v1 补丁的客户端生效，1047 基线客户端上与停摆怀表（减益持续 +1000%）"
                        "同队时 10 秒诅咒会被拉长到超过 25 秒周期")
    w.deviations.append("「赌局」「开局赌注」「血本无归」叠层上限写 2：134/199 按层数读，上限 1 时层数恒 0——开局赌注与血本无归"
                        "的持续行永不生效、本体温和转轮的「没有赌局」恒真（与完整老虎机同时转）；各自只给 1 层，134 倍乘上限 1 不翻倍。"
                        "「复读弹射」只被前置 187（按状态个数）读，保持上限 1")
    w.deviations.append("评分审查 0928（作者「按表改」）：保留提案这一版的 +500% 刃，只改提案未给的两个量——转盘权重 1:1:1:1:1:1 → "
                        "3:3:3:1:1:1（每种增益 1/4、每种诅咒 1/12），三支增益的全部状态与「复读弹射」10 → 20 秒"
                        "（仍短于 25 秒周期，两次转盘不重叠）；三支诅咒、开局赌注与本体温和转轮不动")
    return w


def w11() -> Weapon:
    w = Weapon(11, "hokuto_fist", "北斗百裂拳", "拳", (), "百合色彩虹桥",
               "北斗七星纹的拳套", "你的每一击都被拆成了百裂——可惜每一拳都很轻。",
               "直接攻击改为 10 段、每段 5%（合计 -50%；强制付与，无视免疫与增益无效，复活后重新附加）；"
               "每累计 100 次直接攻击，全队攻击与技能伤害 +150%（20 秒）")
    hundred = dsl_program("hokuto_hundred")
    # 追加直击恒为「好方向」：增益无效/全状态无效挡得住，作者 0928 要求强制付与；阵亡入棺会清掉它，复活时同键重挂
    w.dsl[hundred] = dsl_root(give(-17, [["ACAdditionalDirectAttack", P(DSL_FOREVER), P(10), P(-0.5), P(1)]],
                                   "cursed_hokuto", cancelable=False, force=True))
    w.cas["cursed_hokuto_hundred"] = "自身的直接攻击变为10段（每段伤害为原本的5%；强制付与，无视免疫与增益无效，不可驱散）"
    w.soul = [
        Eff("0", stat("33", T_SELF, 30, 60), note="自身直接攻击伤害 +30%→60%"),
        Eff("0", stat("202", T_SELF, 25, 50), note="自身直接攻击计为 3 次（合计伤害 +25%→50%）"),
    ]
    hit100 = trig(IT_DIRECT, trigger_puller=P_SELF, threshold=times(100))
    w.ea = [
        *growth_pair("33", T_SELF, 150, 60),
        Eff("0", invoke("cursed_hokuto_hundred", hundred), **CURSE,
            note="【诅咒】直接攻击变为 10 段、每段原伤害 5%（覆盖本体的 3 段；强制付与、无视免疫、不可驱散）"),
        Eff("0", condition("0", T_PARTY, 150, 1200), trig=hit100, **FINAL,
            note="每累计 100 次直接攻击，全队攻击力 +150%（20 秒）"),
        Eff("0", condition("1", T_PARTY, 150, 1200), trig=hit100, **FINAL,
            note="每累计 100 次直接攻击，全队技能伤害 +150%（20 秒）"),
        Eff("0", invoke("cursed_hokuto_hundred", hundred), trig=trig(IT_REVIVAL, trigger_puller=P_SELF), **CURSE,
            note="【诅咒】复活后重新附加直击 10 段（同键幂等）"),
    ]
    w.deviations.append("「触发队里一个角色的技能」没有通用原语（每个角色技能 DSL 不同），按提案备选改为全队增伤")
    w.deviations.append("评分审查 0928（作者「按表改」）：每累计 100 次直接攻击的全队攻击/技能伤害 +100% → +150%（提案只写「增伤」、"
                        "数值由实现方定）；10 段 × 5% 诅咒、自身直击 +150% 与 100 次阈值不动。10 段后约 10 次接触就累计满 100 次，"
                        "20 秒增益接近常驻")
    w.deviations.append(FORCED_CURSE_NOTE + "；追加直击是好方向内容，原来挡得住它的是增益无效与全状态无效。"
                        "它是成员级状态，阵亡入棺会被清掉，新增复活重挂一行（否则复活后白拿本体「3 段 +50%」）")
    return w


def w12() -> Weapon:
    w = Weapon(12, "dancer_chakram", "像素城之环刃", "饰品", ("light", "dark"), "P.P.P.P",
               "金色的像素环刃", "舞步未完成之前，观众只看见跌倒。",
               "光/暗属性共鸣时：开局进入「伶俐准备」（连击上限 9、强化弹射伤害独立乘区 -666%）；「伶俐准备」期间打出 10 次"
               "强化弹射后转为永久「剑舞准备」：解除连击上限、连击 +40、强化弹射伤害 +500%、贯通与加速（永续），"
               "并对全体敌人造成 1 次 30 倍强化弹射伤害")
    u_clever, u_dance = w.uid(1), w.uid(2)
    # 叠层上限必须 >1：134 按层数计、ConsumeUniqueCondition 只消耗可叠层状态；上限 1 时 -666%、+500% 与消耗全部静默失效。
    # 两者每场只给 1 层（开局 / 转换各一次），134 倍乘上限 1 不翻倍
    w.uniques[u_clever] = unique_row(f"cursed_dance_{u_clever}", "伶俐准备", "cursed_chakram_clever", "99999999", "2", bad=True)
    w.uniques[u_dance] = unique_row(f"cursed_dance_{u_dance}", "剑舞准备", "cursed_chakram_dance", "99999999", "2", bad=False)
    lock_key = "cursed_dance_lock"
    init, awaken, finale = (dsl_program(f"dance_{k}") for k in ("lock", "awaken", "finale"))
    # 锁：不可驱散 + 强制付与（DebuffPrevent/弱体耐性挡不住）；解锁按同一键串、cancelableKind 1（只删不可驱散）定点删，
    # 敌方给的连击限制不受影响。AddCombo 立即生效、删锁排队处理，必须 Wait 之后再加连击，否则被还在的上限 9 钳住。
    w.dsl[init] = dsl_root(
        give(-17, [["ACComboRestriction", P(9999999), P(9)]], lock_key, cancelable=False, force=True),
        give(-17, [["ACUnique", int(u_clever), P(1)]], "cursed_dance_clever", cancelable=False))
    w.dsl[awaken] = dsl_root(
        C("DeleteCondition", -17, ["DCComboRestriction"], 99, DELETE_NON_CANCELABLE_ONLY, lock_key, ["Default"]),
        C("ConsumeUniqueCondition", -17, int(u_clever), ["Some", 1]),
        give(-17, [["ACUnique", int(u_dance), P(1)]], "cursed_dance_sword", cancelable=False),
        give(-17, [ac("ACPiercing", 9999999)], "cursed_dance_pierce", cancelable=False),
        give(-17, [ac("ACSpeedup", 9999999, P(0.2), P(1))], "cursed_dance_speed", cancelable=False),
        wait(6, C("AddCombo", P(40))))
    w.dsl[finale] = _full_screen_attack(30.0, buff_target_as=PF3_BTA, delay=6)
    w.cas["cursed_dance_lock"] = "连击上限变为9，并处于「伶俐准备」状态"
    w.cas["cursed_dance_awaken"] = "解除连击上限与「伶俐准备」，获得「剑舞准备」、贯通与加速状态（永续），连击+40"
    w.cas["cursed_dance_finale"] = "对全体敌人造成30倍强化弹射伤害"
    every10 = trig(IT_PF, threshold=times(10))
    once10 = trig(IT_PF, threshold=times(10), trigger_limit="1")
    rows_s, rows_e = [], []
    for element in ("light", "dark"):
        gate = (res(element),)
        cn = "光" if element == "light" else "暗"
        clever = (*gate, has_unique(u_clever))
        rows_s += [
            Eff("0", condition("28", None, 50, 900), trig=every10, pre=gate,
                note=f"{cn}属性共鸣时：每 10 次强化弹射，强化弹射伤害 +50%（15 秒）"),
            Eff("0", condition("26", None, None, 900), trig=every10, pre=gate,
                note=f"{cn}属性共鸣时：每 10 次强化弹射，贯通（15 秒）"),
            Eff("0", ("226", {"strength": (times(4), times(4))}), trig=every10, pre=gate,
                note=f"{cn}属性共鸣时：每 10 次强化弹射，连击 +4"),
        ]
        rows_e += [
            Eff("0", invoke("cursed_dance_lock", init), pre=gate, **CURSE,
                note="【诅咒】开局进入「伶俐准备」：连击上限 9（强制付与、不可驱散）"),
            Eff("1", during("413", None, -666), trig=gate_unique(u_clever), pre=gate, even_if_dead=True, **CURSE,
                note="【诅咒】「伶俐准备」期间强化弹射伤害独立乘区 -666%"),
            # 终结技排在转换之前：两行都在「伶俐准备」还在时判前置；命中晚 6 帧落下，那时消耗已处理，-666% 不再生效
            Eff("0", invoke("cursed_dance_finale", finale), trig=once10, pre=clever, **FINAL,
                note="转为「剑舞准备」时对全体敌人造成 1 次 30 倍强化弹射伤害"),
            Eff("0", invoke("cursed_dance_awaken", awaken), trig=once10, pre=clever, **CURSE,
                note="「伶俐准备」期间第 10 次强化弹射：转为永久「剑舞准备」，解除连击上限、连击 +40、贯通与加速 +20%（永续）"),
            *growth_pair("23", None, 500, 0, mode="1", trig_=gate_unique(u_dance), pre=gate, even_if_dead=True),
        ]
    w.soul, w.ea = rows_s, rows_e
    w.deviations.append("第三轮：改名「像素城之环刃」、外形金色像素环刃（沿用 slug 与图标路径）、光/暗属性共鸣；"
                        "单向转换：「剑舞准备」永久（提案未给时长），每场一次；加速取官方常见值 +20%")
    w.deviations.append("-666% 保留原值，不等于 -100%：413 与强化弹射分档/独立乘区类加成在同一个 (1+x) 括号里，"
                        "-666% 要等这些加成超过 +566% 才会漏出伤害；若队伍里还有其他负向因子（强化弹射伤害减益合计低于 -100%、"
                        "敌方强化弹射抗性超过 100%）乘积会变号")
    w.deviations.append("30 倍全屏 = 持有者攻击力 30 倍的无属性命中（Explosion）；根头 133 按强化弹射 Lv3 完整结算"
                        "（通用池 +500%、分档、413），需要 damage-type-rules-v1，未装补丁按技能伤害结算（不崩）")
    w.deviations.append("解锁 DeleteCondition 按锁的键串、cancelableKind 1 定点删（旧版 dance_release 写 0 删不掉不可驱散的锁，"
                        "连击上限 9 从未解除）；持有者阵亡期间的强化弹射不计数，但诅咒照常生效；第 10 次强化弹射本身的命中"
                        "落在转换之后；永续贯通/加速/「剑舞准备」仍会被敌方全删（cancelableKind 2）类效果清掉")
    w.deviations.append("「场地变成有风的 boss 场地、把人往左右推」：玩家侧 DSL 的 CreateWindAttack 在 MemberImpl 直接 throw，不做")
    w.deviations.append("「伶俐准备」「剑舞准备」叠层上限写 2：134 按层数读、ConsumeUniqueCondition 只消耗可叠层状态，上限 1 时"
                        "-666%、+500% 永不生效，「伶俐准备」也消耗不掉；两者每场只给 1 层")
    return w


def w13() -> Weapon:
    w = Weapon(13, "sealed_wind_flute", "封能风笛", "饰品", ("wind",), "脆脆鲨",
               "缠着封符的风笛", "封住了旁门，只剩风能灌满技能。",
               "风属性共鸣时：开局全队技能槽清空；全队技能充能速度 +100%；角色技能槽满时自身攻击与技能伤害 +500%（20 秒）")
    wind = (res("wind"),)
    drain = dsl_program("flute_drain")
    w.dsl[drain] = dsl_root(party(0, C("SubtractSkillPoint", 0, P(2.0))))
    w.cas["cursed_flute_drain"] = "清空全队技能槽"
    full = trig(IT_SKILL_MAX, trigger_puller=P_ONE_OF_PARTY, cooltime="1200")
    u_seal = w.uid(1)
    # 被持续触发 134（按层数）读：叠层上限必须 >1（1.4.1069 首发写 1，封印未生效）
    w.uniques[u_seal] = unique_row(f"cursed_flute_{u_seal}", "封能", "cursed_flute_seal", "99999999", "2", bad=True)
    w.soul = [Eff("0", stat("35", T_PARTY, 15, 30), pre=wind, note="风属性共鸣时：全队技能充能速度 +15%→30%")]
    w.ea = [
        *growth_pair("35", T_PARTY, 100, 30, pre=wind),
        Eff("0", invoke("cursed_flute_drain", drain), trig=elapsed(30, "1"), pre=wind, **CURSE,
            note="【诅咒】开局（0.5 秒后）清空全队技能槽"),
        Eff("0", condition("0", T_TRIGGER, 500, 1200, by_each_trigger_puller="true"), trig=full, pre=wind,
            **FINAL, note="角色技能槽满时，该角色攻击力 +500%（20 秒，每人各自 CT20 秒）"),
        Eff("0", condition("1", T_TRIGGER, 500, 1200, by_each_trigger_puller="true"), trig=full, pre=wind,
            **FINAL, note="角色技能槽满时，该角色技能伤害 +500%（20 秒，每人各自 CT20 秒）"),
        Eff("0", unique(u_seal), pre=wind, **CURSE, note="开局给自身刻上「封能」（永续、不可驱散）"),
        Eff("1", ("423", {"target": T_PARTY, "unique_condition_id": str(GAUGE_MASK)}), trig=gate_unique(u_seal),
            pre=wind, even_if_dead=True, **CURSE,
            note="【诅咒】持有「封能」时全队无法因能力和装备获得技能槽（423，规则码 8；持有者阵亡后仍生效）"),
    ]
    w.deviations.append("「无法因能力和被动得到充能」按回槽来源限制（423，规则码 8）实现：拦下能力/装备带来的加槽，"
                        "技能自身回槽、移动跑条与开局槽不受影响；需要 equipment-rules 客户端补丁（未装读到 C7050）。"
                        "充能速度 +100% 受引擎充能上限约束")
    return w


def w14() -> Weapon:
    w = Weapon(14, "triple_curse_key", "三重咒钥", "饰品", (), "脆脆鲨",
               "三齿咒纹钥匙", "第一次打开很难，之后的门会自己敞开。",
               "全队技能充能速度 -66%（约三倍充能）、开局清空技能槽；自身首次发动技能后，之后两次发动技能各回复 100% 技能槽；"
               "任一角色发动技能时该角色攻击力 +1000%（40 秒，各自获得）")
    u_key = w.uid(1)
    w.uniques[u_key] = unique_row(f"cursed_key_{u_key}", "咒钥", "cursed_key", "99999999", "2", bad=False)
    drain = dsl_program("key_drain")
    w.dsl[drain] = dsl_root(party(0, C("SubtractSkillPoint", 0, P(2.0))))
    w.cas["cursed_key_drain"] = "清空全队技能槽"
    skill = trig(IT_SKILL, trigger_puller=P_SELF)
    # 评分审查 0928（作者拍板）：攻击 buff 按原文主语「队伍」给每名施放者各自获得（触发者 + 各自计算），10 → 40 秒
    any_skill = trig(IT_SKILL, trigger_puller=P_ONE_OF_PARTY)
    w.soul = [
        Eff("0", ("0", {"target": T_TRIGGER, "strength": (pct(100), pct(300)), "frame": frames(2400), "number": times(1),
                        "cancelable": "0", "by_each_trigger_puller": "true"}), trig=any_skill,
            note="任一角色发动技能时该角色攻击力 +100%→300%（40 秒）")]
    consume = ("2", {"target": "0", "threshold.power1": times(1), "threshold.first_max": times(1),
                     "unique_condition_id": u_key})
    w.ea = [
        *growth_pair("0", T_TRIGGER, 1000, 300, trig_=any_skill, cond_frames=2400, by_each_trigger_puller="true"),
        Eff("0", ("211", {"target": T_SELF, "strength": (pct(100), pct(100))}), trig=skill, pc=consume,
            **CURSE, note="发动技能时消耗 1 层「咒钥」回复 100% 技能槽"),
        Eff("0", unique(u_key, 2), trig=trig(IT_SKILL, trigger_puller=P_SELF, trigger_limit="1"), delay=1,
            **CURSE, note="首次发动技能后获得「咒钥」2 层"),
        Eff("0", stat("35", T_PARTY, -66), **CURSE, note="【诅咒】全队技能充能速度 -66%"),
        Eff("0", invoke("cursed_key_drain", drain), trig=elapsed(30, "1"), **CURSE,
            note="【诅咒】开局（0.5 秒后）清空全队技能槽"),
    ]
    w.deviations.append("「需要三倍充能」：槽容量不能调，改为全队充能速度 -66%（约三倍时间）；回充只给装备者")
    w.deviations.append("作者 0928 数值预算（刃合计 ≤1000%）：发动技能时攻击力终值 +1500% → +1000%")
    w.deviations.append("评分审查 0928（作者拍板「按方案做」）：攻击力 +1000% 从「装备者发动技能时自身」改为「任一角色发动技能时该角色"
                        "各自获得」（原文主语是队伍：全队承担三倍充能，收益也给全队），持续 10 → 40 秒（原文没有给时长）；"
                        "数值、咒钥回充（仍只给装备者）、全队充能 -66% 与开局清槽不动")
    return w


def w15() -> Weapon:
    w = Weapon(15, "expired_gasoline", "过期汽油", "饰品", ("fire",), "脆脆鲨",
               "漏油的红色油桶", "油是过期了，火还是会点着。",
               "火属性共鸣时：队长攻击 +100%、强化弹射伤害 +750%、强化弹射独立乘区 +15%；"
               "全队弹球速度 -50%（永续，强制付与，无视免疫，不可驱散；引擎速度合计下限 -35%）")
    fire = (res("fire"),)
    # 作者 0928 强制赋予：能力表 228 没有强制付与列 ⇒ 629 DSL forceApply。减速是弹球级状态，付给成员后转交队伍槽，
    # 持有者阵亡不清；全灭续关会清队伍槽，复活时同键重挂（孤星同形）
    slow = dsl_program("gasoline_slow")
    w.dsl[slow] = dsl_root(give(-17, [ac("ACSpeedup", DSL_FOREVER, P(-0.5), P(1))], "cursed_gasoline_slow",
                                cancelable=False, force=True))
    w.cas["cursed_gasoline_slow"] = "全队弹球速度降低50%（永续，强制付与，无视免疫与弱体无效，不可驱散）"
    w.soul = [
        Eff("0", stat("32", T_LEADER, 50, 120), pre=fire, note="火属性共鸣时：队长攻击力 +50%→120%"),
        Eff("0", stat("55", None, 150, 360), pre=fire, note="火属性共鸣时：强化弹射伤害 +150%→360%"),
    ]
    w.ea = [
        *growth_pair("32", T_LEADER, 100, 120, pre=fire),
        *growth_pair("55", None, 750, 360, pre=fire),
        Eff("0", ("696", {"strength": (pct(15), pct(15))}), pre=fire, **FINAL,
            note="火属性共鸣时：强化弹射伤害独立乘区 +15%"),
        Eff("0", invoke("cursed_gasoline_slow", slow), pre=fire, **CURSE,
            note="【诅咒】火属性共鸣时：全队弹球速度 -50%（永续，强制付与、无视免疫、不可驱散）"),
        Eff("0", invoke("cursed_gasoline_slow", slow), trig=trig(IT_REVIVAL, trigger_puller=P_ONE_OF_PARTY), pre=fire,
            **CURSE, note="【诅咒】复活时重新附加弹球减速（同键幂等）"),
    ]
    w.deviations.append("第二轮反馈「刃值和乘区减半」：队长攻击 500→250%、强化弹射伤害 1500→750%、独立乘区 30→15%")
    w.deviations.append("「冲刺冷却 +50%」没有原生能力（冲刺参数补丁只认角色表，装备表 422 会 C7050）；「重力」「溺水」是 boss 场地物理，"
                        "玩家侧 DSL 会 throw；统一改为弹球减速")
    w.deviations.append("评分审查 0928（作者「按表改」，下调 + 加强自带负面）：减速 -30% → -50%（代理原案的重力/溺水），"
                        "队长攻击终值 +250% → +150%（本体设计值不动）；强化弹射伤害 +750% 与独立乘区 +15% 不动。"
                        "引擎把弹球速度合计钳在 ≥-35%（BallImpl._getSpeedupCorrectionFactor），单独生效时实际 -35%，"
                        "多出的 -15% 用来抵消队伍的加速增益；速度固定类增益会让减速整段失效（强制付与改变不了）")
    w.deviations.append(FORCED_CURSE_NOTE + "；原 228 行原位换成 629，另加复活重挂一行")
    w.deviations.append("评分审查 0928 兜底（表内预设「减速不能足额生效 → 队长攻击再降到 100%」）：引擎速度合计下限 -35% "
                        "已由 BallImpl.as 静态确认，-50% 单独生效只剩 -35%，负面系数退回约 ×0.9、分数约 533 仍超 500；"
                        "队长攻击终值 +150% → +100%（本体设计 120 不动，满破实际 +24%），刃 900% → 850%，预估约 492")
    return w


def w16() -> Weapon:
    w = Weapon(16, "all_in_blade", "孤注一掷", "剑", (), "脆脆鲨",
               "剑柄嵌着独颗宝石的大剑", "只出一拳——之后就是太空垃圾的时间。",
               "同属性编成时：全队充能速度 +50%、攻击与技能伤害 +250%、技能伤害独立乘区 +10%；"
               "任一角色发动技能后自身封印 30 秒（强制付与、无视免疫、不可驱散）")
    same = (SAME_ELEMENT,)
    w.soul = [
        Eff("0", stat("35", T_PARTY, 7.5, 15), pre=same, note="同属性编成时：全队技能充能速度 +7.5%→15%"),
        Eff("0", stat("32", T_PARTY, 30, 120), pre=same, note="同属性编成时：全队攻击力 +30%→120%"),
        Eff("0", stat("34", T_PARTY, 30, 120), pre=same, note="同属性编成时：全队技能伤害 +30%→120%"),
    ]
    w.ea = [
        *growth_pair("35", T_PARTY, 50, 15, pre=same),
        *growth_pair("32", T_PARTY, 250, 120, pre=same),
        *growth_pair("34", T_PARTY, 250, 120, pre=same),
        Eff("0", stat("694", T_PARTY, 10), pre=same, **FINAL, note="同属性编成时：全队技能伤害独立乘区 +10%"),
    ]
    # 能力行没有强制付与列，只能走 629 DSL 的 forceApply；DSL 里没有「触发者」主体 ⇒ 按槽位拆 3 行（触发者 1/2/3 × 点名 83/84/85）
    for puller, selector, tag, cn in ((P_LEADER, 83, "1", "队长"), (P_SECOND, 84, "2", "2号位"), (P_THIRD, 85, "3", "3号位")):
        program = dsl_program(f"allin_silence_{tag}")
        w.dsl[program] = dsl_root(slot_member(0, selector, give(0, [ac("ACSilence", 1800)], "cursed_allin_silence",
                                                               cancelable=False, force=True)))
        w.cas[f"cursed_allin_silence_{tag}"] = f"使{cn}角色封印30秒（强制付与，无视免疫与弱体无效，不可驱散）"
        w.ea.append(Eff("0", invoke(f"cursed_allin_silence_{tag}", program), trig=trig(IT_SKILL, trigger_puller=puller),
                        pre=same, **CURSE, note=f"【诅咒】{cn}发动技能后，该角色封印 30 秒（强制付与、无视免疫、不可驱散）"))
    w.deviations.append("第三轮「数值太高减半」：全队充能 100→50%、攻击/技能伤害 1000→500%、技能伤害独立乘区 20→10%（本体同比减半）")
    w.deviations.append("第三轮「沉默强制赋予无视免疫」：能力行不能强制付与，改为 629 DSL 的 CreateCondition forceApply；"
                        "DSL 没有「触发者」主体，拆成队长/2 号位/3 号位三行（面板显示 3 条），时机不变。forceApply 不跳过持续时间伸缩"
                        "（「弱体时间缩短」仍会缩短 30 秒）；玩家侧对己方强制付与弱体官方零先例，点名 83/84/85 是否只取单人需真机金丝雀确认")
    w.deviations.append("评分审查 0928（作者「按表改」）：全队攻击/技能伤害终值 +500% → +250%（刃合计 500%，等于死亡使者基线），"
                        "本体按第三轮先例同比减半（设计 240 → 120，满破实际 +24%）；全队充能 +50%、技能伤害独立乘区 +10% 与"
                        "30 秒强制封印不动")
    return w


def w17() -> Weapon:
    w = Weapon(17, "overload_capacitor", "过载电容", "饰品", ("thunder",), "苍氿兮曰",
               "迸着电火花的电容", "放电两次之后，线圈会把你也电住。",
               "雷属性共鸣时：全队技能伤害 +600%；每名角色每发动 2 次技能后麻痹 10 秒（强制付与，无视免疫，不可驱散）")
    thunder = (res("thunder"),)
    w.soul = [Eff("0", stat("34", T_PARTY, 125, 250), pre=thunder, note="雷属性共鸣时：全队技能伤害 +125%→250%")]
    w.ea = [*growth_pair("34", T_PARTY, 600, 250, pre=thunder)]
    # 作者 0928 强制赋予：能力表 19 没有强制付与列 ⇒ 629 DSL forceApply；DSL 没有「触发者」主体 ⇒ 照孤注一掷按位拆 3 行，
    # 每行只数自己那个位置的施放次数（门槛 2），与原「按触发者各自计数」等价
    for puller, selector, tag, cn in ((P_LEADER, 83, "1", "队长"), (P_SECOND, 84, "2", "2号位"), (P_THIRD, 85, "3", "3号位")):
        program = dsl_program(f"capacitor_paralysis_{tag}")
        w.dsl[program] = dsl_root(slot_member(0, selector, give(0, [ac("ACParalysis", 600, True)],
                                                               "cursed_capacitor_paralysis", cancelable=False, force=True)))
        w.cas[f"cursed_capacitor_paralysis_{tag}"] = f"使{cn}角色麻痹10秒（强制付与，无视免疫与弱体无效，不可驱散）"
        w.ea.append(Eff("0", invoke(f"cursed_capacitor_paralysis_{tag}", program),
                        trig=trig(IT_SKILL, trigger_puller=puller, threshold=times(2)), pre=thunder, **CURSE,
                        note=f"【诅咒】{cn}每发动 2 次技能，该角色麻痹 10 秒（强制付与、无视免疫、不可驱散；"
                             "麻痹期间不能施放技能与直接攻击）"))
    w.deviations.append(FORCED_CURSE_NOTE + "；DSL 没有「触发者」主体，原一行（触发者、按人计数）拆成队长/2 号位/3 号位三行"
                        "（面板显示 3 条，时机不变）；点名 83/84/85 是否只取单人与孤注一掷同待真机金丝雀确认")
    return w


def _persona_dark_heal() -> list:
    """暗诅咒：每秒回复全队 50%，队长额外 20%（5 秒）。"""
    pulse = lambda: [party(0, C("CreateRatioHeal", 0, 2, P(0.5), [], P(0), ["GenericHealHitEffect"])),
                     slot_member(1, 83, C("CreateRatioHeal", 1, 2, P(0.2), [], P(0), ["GenericHealHitEffect"]))]
    return [*pulse()] + [wait(60 * i, *pulse()) for i in range(1, 5)]


def w18() -> Weapon:
    w = Weapon(18, "persona_pistol", "人格召唤枪", "铳", ("dark", "thunder"), "P.P.P.P",
               "萦绕面具幻影的银色小手枪", "扣下扳机，唤醒的是另一个自己。",
               "暗属性共鸣：开局全队 HP -25%；角色 HP 为 1% 时护盾 100%、攻击 +1000%、逆境 +20%（2 秒）、全队充能 +40%（3 秒）；"
               "诅咒：任一角色施放技能后每秒回复全队 50%、队长再 +20%（5 秒）。雷属性共鸣：开局队长 HP -15%；队长 HP<20% 时"
               "护盾 80%、攻击 +600%、技能伤害 +400%（6 秒）、技能槽 +100%（冷却 15 秒）；诅咒：队长施放技能后全队回复 20%、"
               "3 秒后再回复 80%，2、3 号位技能槽 -30%")
    dark, thunder = (res("dark"),), (res("thunder"),)
    near_death = trig(IT_HP_LOW, trigger_puller=P_ONE_OF_PARTY, threshold=pct(1), cooltime="60")
    # 评分审查 0928（作者「按表改」，表第 18 行）：「限 2 次」改冷却 15 秒（还原提案第二版「都取消了次数上限」）；本体 4 行与强化 8 行共用
    leader20 = trig(IT_HP_LOW, trigger_puller=P_LEADER, threshold=pct(20), cooltime="900")
    heal = dsl_program("persona_heal")
    w.dsl[heal] = dsl_root(*_persona_dark_heal())
    w.cas["cursed_persona_heal"] = "每秒回复全队最大HP的50%，队长额外回复20%（5秒）"
    echo = dsl_program("persona_echo")
    w.dsl[echo] = dsl_root(
        party(0, C("CreateRatioHeal", 0, 2, P(0.2), [], P(0), ["GenericHealHitEffect"])),
        wait(180, party(1, C("CreateRatioHeal", 1, 2, P(0.8), [], P(0), ["GenericHealHitEffect"]))),
        slot_member(2, 84, C("SubtractSkillPoint", 2, P(0.3))),
        slot_member(3, 85, C("SubtractSkillPoint", 3, P(0.3))))
    w.cas["cursed_persona_echo"] = "回复全队最大HP的20%，3秒后再回复80%；2号位与3号位角色技能槽减少30%"
    w.soul = [
        Eff("0", stat("227", T_TRIGGER, 50, 100), trig=near_death, pre=dark,
            note="暗属性共鸣：角色 HP 为 1% 时获得最大 HP +50%→100% 的护盾"),
        Eff("0", condition("0", T_TRIGGER, 500, 120), trig=near_death, pre=dark, note="同上时攻击力 +500%（2 秒）"),
        Eff("0", condition("470", T_TRIGGER, 20, 120), trig=near_death, pre=dark, note="同上时逆境 +20%（2 秒）"),
        Eff("0", condition("701", T_PARTY, 40, 180), trig=near_death, pre=dark, note="同上时全队技能充能速度 +40%（3 秒）"),
        Eff("0", stat("227", T_LEADER, 40, 80), trig=leader20, pre=thunder,
            note="雷属性共鸣：队长 HP<20% 时获得最大 HP +40%→80% 的护盾（冷却 15 秒）"),
        Eff("0", condition("0", T_LEADER, 300, 360), trig=leader20, pre=thunder, note="同上时队长攻击力 +300%（6 秒）"),
        Eff("0", condition("1", T_LEADER, 200, 360), trig=leader20, pre=thunder, note="同上时队长技能伤害 +200%（6 秒）"),
        Eff("0", stat("211", T_LEADER, 50, 100), trig=leader20, pre=thunder, note="同上时队长技能槽 +50%→100%"),
    ]
    w.ea = [
        *growth_pair("227", T_TRIGGER, 100, 100, trig_=near_death, pre=dark),
        *growth_pair("0", T_TRIGGER, 1000, 500, trig_=near_death, pre=dark, cond_frames=120),
        *growth_pair("470", T_TRIGGER, 20, 20, trig_=near_death, pre=dark, cond_frames=120),
        *growth_pair("701", T_PARTY, 40, 40, trig_=near_death, pre=dark, cond_frames=180),
        Eff("0", stat("209", T_PARTY, 25), pre=dark, **CURSE, note="【诅咒】暗：开局全队失去最大 HP 的 25%"),
        Eff("0", invoke("cursed_persona_heal", heal), trig=trig(IT_SKILL, trigger_puller=P_ONE_OF_PARTY), pre=dark,
            **CURSE, note="【诅咒】暗：任一角色施放技能后每秒回复全队 50%、队长再 +20%（5 秒）"),
        *growth_pair("227", T_LEADER, 80, 80, trig_=leader20, pre=thunder),
        *growth_pair("0", T_LEADER, 600, 300, trig_=leader20, pre=thunder, cond_frames=360),
        *growth_pair("1", T_LEADER, 400, 200, trig_=leader20, pre=thunder, cond_frames=360),
        *growth_pair("211", T_LEADER, 100, 100, trig_=leader20, pre=thunder),
        Eff("0", stat("209", T_LEADER, 15), pre=thunder, **CURSE, note="【诅咒】雷：开局队长失去最大 HP 的 15%"),
        Eff("0", invoke("cursed_persona_echo", echo), trig=trig(IT_SKILL, trigger_puller=P_LEADER), pre=thunder,
            **CURSE, note="【诅咒】雷：队长施放技能后全队回复 20%、3 秒后再回复 80%，2、3 号位技能槽 -30%"),
    ]
    w.deviations.append("第二轮 v2：两套都取消次数上限（雷的濒死爆发原保留机制简介里的上限 2 次，评分审查 0928 改为冷却 15 秒）；"
                        "「攻击 +700%&+700%」原按两段合计 +1400% 实现")
    w.deviations.append("「类似响的 buff」：没有可复用的状态外观，按「立刻回复 20%、3 秒后回复 80%」实现（原版暗响特殊 buff 持续 3 秒）")
    w.deviations.append("作者 0928 数值预算（刃合计 ≤1000%）：暗攻击 +1400% → +1000%；雷攻击 +1000%、技能伤害 +600% → "
                        "攻击 +600%、技能伤害 +400%（5:3 取整时向攻击多砍）；逆境 +20% 在乘区上限内保留，护盾/充能/回槽/扣血回血不变")
    w.deviations.append("评分审查 0928：定为高操作背水向整活武器，不参与常规强度梯度（HP 阈值触发的覆盖率低，预算内到不了 250 分）")
    w.deviations.append("评分审查 0928（作者「按表改」，表第 18 行具体改法）：雷模式队长 HP<20% 触发去掉「限 2 次」，改为冷却 15 秒"
                        "（还原提案第二版「都取消了次数上限」；HpLow 是边沿触发，再次触发须先吃掉护盾再掉血）；"
                        "攻击 +600%、技能伤害 +400%（6 秒，短于冷却，不重叠）、护盾 80%、技能槽 +100% 等数值与暗模式都不动")
    w.deviations.append(FRIENDLY_FIRE_NOTE + "（本把：暗开局全队 -25%、雷开局队长 -15%）")
    return w


def w19() -> Weapon:
    w = Weapon(19, "lone_star", "孤星", "剑", (), "苍氿兮曰",
               "剑尖缀着一颗星的细剑", "孤星只照得亮十五步，再远的连击都落在黑暗里。",
               "队长攻击 +350%、强化弹射伤害 +650%、强化弹射伤害独立乘区 +30%；战斗开始起连击上限 15"
               "（强化弹射最高 Lv2，打不出 Lv3）")
    lock = dsl_program("lonestar_lock")
    # 不可驱散 + 强制付与（弱体无效挡不住）；同一键串重挂只刷新、上限取小，幂等
    w.dsl[lock] = dsl_root(give(-17, [["ACComboRestriction", P(9999999), P(15)]], "cursed_lonestar",
                                cancelable=False, force=True))
    w.cas["cursed_lonestar_lock"] = "连击上限变为15"
    w.soul = [
        Eff("0", stat("32", T_LEADER, 87.5, 175), note="队长攻击力 +87.5%→175%"),
        Eff("0", stat("55", None, 162.5, 325), note="强化弹射伤害 +162.5%→325%"),
    ]
    w.ea = [
        *growth_pair("32", T_LEADER, 350, 175),
        *growth_pair("55", None, 650, 325),
        Eff("0", ("696", {"strength": (pct(30), pct(30))}), **FINAL, note="强化弹射伤害独立乘区 +30%"),
        Eff("0", invoke("cursed_lonestar_lock", lock), **CURSE, note="【诅咒】战斗开始起连击上限 15（强化弹射最高 Lv2）"),
        Eff("0", invoke("cursed_lonestar_lock", lock), trig=trig(IT_PF, threshold=times(1)), **CURSE,
            note="每次强化弹射时重挂连击上限 15（幂等）"),
        Eff("0", invoke("cursed_lonestar_lock", lock), trig=trig(IT_REVIVAL, trigger_puller=P_ONE_OF_PARTY), **CURSE,
            note="复活时重挂连击上限 15（幂等）"),
    ]
    w.deviations.append("第三轮「常驻锁 15 连击上限」：开局 DSL 强制付与连击上限 15（永续、不可驱散），每次强化弹射与复活时同键幂等重挂"
                        "（全灭/超时会清掉队伍槽，官方少数 cancelableKind 2 全删效果也会清掉）；上限 15 低于 Lv3 阈值，"
                        "强化弹射最高 Lv2；连击上限作用全队，与谁装备无关；「PF 后 3 秒」的旧写法删除")
    w.deviations.append("第三轮「加强化弹射伤害乘区」：120 级强化弹射伤害独立乘区 +30%（官方最高 5–6%）")
    w.deviations.append("作者 0928 数值预算（刃合计 ≤1000%）：队长攻击 +500% → +350%、强化弹射伤害 +1000% → +650%"
                        "（按原 1:2 比例缩放后取整，强化弹射仍是主项）；强化弹射伤害独立乘区 +30% 在乘区上限内保留")
    return w


def w20() -> Weapon:
    w = Weapon(20, "master_eater_sword", "噬主魔剑", "剑", (), "来点关注谢谢喵",
               "锁链缠绕、剑柄带刺的暗紫魔剑", "剑认可所有人，唯独不认握着它的队长。",
               "2、3 号位攻击力 +550%；装备者额外获得合击角色攻击力 50% 的白值；队长攻击力 -9999%（伤害归零）")
    w.soul = [
        Eff("0", stat("32", T_SECOND, 120, 240), note="2 号位攻击力 +120%→240%"),
        Eff("0", stat("32", T_THIRD, 120, 240), note="3 号位攻击力 +120%→240%"),
    ]
    w.ea = [
        *growth_pair("32", T_SECOND, 550, 240),
        *growth_pair("32", T_THIRD, 550, 240),
        Eff("0", stat("717", T_SELF, 50), **FINAL, note="装备者攻击力再加上 50% 合击角色攻击力"),
        Eff("0", stat("32", T_LEADER, -9999), **CURSE, note="【诅咒】队长攻击力 -9999%（引擎下限 -50%）"),
        Eff("0", stat("723", T_LEADER, -100), **CURSE, note="【诅咒】队长伤害独立乘区 -100%（伤害降为 1）"),
    ]
    w.deviations.append("「除队长外」按 2、3 号位实现；攻击 -9999% 受 -50% 下限，另加伤害独立乘区 -100% 让队长伤害归零")
    w.deviations.append("第三轮「非装备者带不了合击、装备者带 50%」：去掉 2/3 号位的合击白值 +100%，改为装备者合击白值 +50%"
                        "（引擎另有固定 25% 合击份额，不做负值抵消）；队长装备时加成落在伤害归零的队长身上，等于作废")
    return w


def w21() -> Weapon:
    w = Weapon(21, "silent_bell", "失声之钟", "饰品", ("wind", "dark"), "来点关注谢谢喵",
               "裂开、没有钟舌的铜钟", "钟不再响了，可每个人都听见了它。",
               "风/暗属性共鸣时：全队技能伤害 +500%、技能伤害独立乘区 +50%；全队永续封印（强制付与，无视免疫，不可驱散，"
               "复活后重新附加）")
    # 作者 0928 强制赋予：能力表 219 没有强制付与列 ⇒ 629 DSL forceApply（同键幂等，复活重挂）
    seal = dsl_program("silentbell_seal")
    w.dsl[seal] = dsl_root(party(0, give(0, [ac("ACSilence", DSL_FOREVER)], "cursed_silentbell_seal",
                                         cancelable=False, force=True)))
    w.cas["cursed_silentbell_seal"] = "全队永续封印（强制付与，无视免疫与弱体无效，不可驱散）"
    rows_s, rows_e = [], []
    for element in ("wind", "dark"):
        gate = (res(element),)
        cn = "风" if element == "wind" else "暗"
        rows_s.append(Eff("0", stat("34", T_PARTY, 120, 240), pre=gate, note=f"{cn}属性共鸣时：全队技能伤害 +120%→240%"))
        rows_e += [
            *growth_pair("34", T_PARTY, 500, 240, pre=gate),
            Eff("0", stat("694", T_PARTY, 50), pre=gate, **FINAL, note="全队技能伤害独立乘区 +50%"),
            Eff("0", invoke("cursed_silentbell_seal", seal), pre=gate, **CURSE,
                note="【诅咒】全队永续封印（强制付与、无视免疫、不可驱散）"),
            Eff("0", invoke("cursed_silentbell_seal", seal), trig=trig(IT_REVIVAL, trigger_puller=P_ONE_OF_PARTY),
                pre=gate, **CURSE, note="【诅咒】复活后重新附加封印（同键幂等）"),
        ]
    w.soul, w.ea = rows_s, rows_e
    w.deviations.append("作者 0928 数值预算（乘区 ≤50%）：全队技能伤害独立乘区 +100% → +50%；技能伤害 +500% 与永续封印不变")
    w.deviations.append(FORCED_CURSE_NOTE + "；每属性两行 219（开局 + 复活重挂）原位换成 629")
    return w


def w23() -> Weapon:
    w = Weapon(23, "coral_venom_claw", "珊瑚毒爪", "拳", ("water",), "阿关",
               "珊瑚与鱼骨组成的指刃", "毒是它的饵——没有毒的时候，爪子什么也抓不住。",
               "水属性共鸣时：强化弹射时获得「珊瑚毒」10 秒，并叠加攻击 +75%（最多 +375%）、技能伤害 +90%（最多 +360%）；"
               "没有「珊瑚毒」时自身直接攻击与技能伤害 -99%")
    water = (res("water"),)
    u_venom = w.uid(1)
    # 强制、不可驱散、弱体方向、入棺移除；再次强化弹射刷新到 10 秒。只当开关用：不掉血、不吃毒强化。
    # 叠层上限必须 >1：207「层数 ≤0」在上限 1 时层数恒 0 ⇒ 恒真，持有「珊瑚毒」也照样 -99%；上限 2 = 最多显示 2 层
    w.uniques[u_venom] = unique_row(f"cursed_coral_{u_venom}", "珊瑚毒", "cursed_coral_venom", "600", "2", bad=True,
                                    cancelable=False, force=True, keep_on_death=False)
    pf5 = trig(IT_PF, threshold=times(1), trigger_limit="5")
    pf4 = trig(IT_PF, threshold=times(1), trigger_limit="4")
    no_venom = lacks_unique_during(u_venom)
    w.soul = [
        Eff("0", stat("32", T_SELF, 18.75, 37.5), trig=pf5, pre=water,
            note="水属性共鸣时：强化弹射时自身攻击力 +18.75%→37.5%（最多 5 次）"),
        Eff("0", stat("34", T_SELF, 22.5, 45), trig=pf4, pre=water,
            note="水属性共鸣时：强化弹射时自身技能伤害 +22.5%→45%（最多 4 次）"),
    ]
    w.ea = [
        *growth_pair("32", T_SELF, 75, 37.5, trig_=pf5, pre=water),
        *growth_pair("34", T_SELF, 90, 45, trig_=pf4, pre=water),
        Eff("0", unique(u_venom), trig=trig(IT_PF, threshold=times(1)), pre=water, **CURSE,
            note="【诅咒】强化弹射时自身获得「珊瑚毒」10 秒（强制付与、不可驱散）"),
        Eff("1", during("410", T_SELF, -99), trig=no_venom, pre=water, **CURSE,
            note="【诅咒】没有「珊瑚毒」时自身直接攻击伤害独立乘区 -99%"),
        Eff("1", during("411", T_SELF, -99), trig=no_venom, pre=water, **CURSE,
            note="【诅咒】没有「珊瑚毒」时自身技能伤害独立乘区 -99%"),
    ]
    w.deviations.append("第三轮「赋予自身中毒做不了」：中毒改为自制固有状态「珊瑚毒」（10 秒，强制付与、不可驱散、不掉血，入棺移除，"
                        "复活后要再次强化弹射才解除 -99%）；「没有珊瑚毒时 -99%」用持续触发 207（固有层数 ≤0）一行直接生效，"
                        "不再用常驻 -99% + 中毒期间 +99% 抵消")
    w.deviations.append("第三轮「数值太高」：每次强化弹射攻击 +100→50%、技能伤害 +120→60%，本体同比减半；"
                        "评分审查 0928（作者拍板「按方案做」）部分回退到原设计与第三轮减半的中点：每次攻击 +75%（5 次共 +375%）、"
                        "技能伤害 +90%（4 次共 +360%），本体同比（设计 37.5/45）；「珊瑚毒」10 秒、上限 2 层与没有时 -99% 的诅咒不动。"
                        "「珊瑚毒」是弱体方向，会被弱体计数类效果读到，持续时间也会被「弱体时间缩短」缩短")
    w.deviations.append("「珊瑚毒」叠层上限写 2：207 按层数判「没有」，上限 1 的状态层数恒读 0，-99% 永远生效、解除条件失效；"
                        "连续强化弹射叠到 2 层（只当开关用，层数不影响数值）")
    return w


def w24() -> Weapon:
    w = Weapon(24, "reverse_hourglass", "倒流沙漏", "饰品", ("thunder", "wind"), "阿关",
               "沙粒向上流的金框沙漏", "沙子往上流时，你的技能也慢了下来。",
               "雷/风属性共鸣时：发动技能或强化弹射时叠「逆沙」（最多 5 层），每层自身攻击 +100%（最多 +500%）、"
               "技能伤害 +100%（最多 +500%）；自身技能充能速度 -90%、其他角色 -45%")
    u_sand = w.uid(1)
    w.uniques[u_sand] = unique_row(f"cursed_sand_{u_sand}", "逆沙", "cursed_hourglass_sand", "99999999", "5", bad=False)
    rows_s, rows_e = [], []
    for element in ("thunder", "wind"):
        gate = (res(element),)
        cn = "雷" if element == "thunder" else "风"
        stack5, stack4, fifth = gate_unique(u_sand, "5"), gate_unique(u_sand, "4"), gate_unique(u_sand, "1", at_least=5)
        rows_s += [
            Eff("0", unique(u_sand), trig=trig(IT_SKILL, trigger_puller=P_SELF), pre=gate, note=f"{cn}属性共鸣时：发动技能叠 1 层「逆沙」"),
            Eff("0", unique(u_sand), trig=trig(IT_PF, threshold=times(1)), pre=gate, note=f"{cn}属性共鸣时：强化弹射叠 1 层「逆沙」"),
            Eff("1", during("0", T_SELF, 25, 50), trig=stack5, pre=gate, note="每层「逆沙」自身攻击力 +25%→50%（最多 5 层）"),
            Eff("1", during("2", T_SELF, 25, 50), trig=stack4, pre=gate, note="每层「逆沙」自身技能伤害 +25%→50%（按 4 层计）"),
        ]
        rows_e += [
            *growth_pair("0", T_SELF, 100, 50, mode="1", trig_=stack5, pre=gate),
            *growth_pair("2", T_SELF, 100, 50, mode="1", trig_=stack4, pre=gate),
            *growth_pair("2", T_SELF, 100, 0, mode="1", trig_=fifth, pre=gate),
            Eff("0", stat("35", T_SELF, -90), pre=gate, **CURSE, note="【诅咒】自身技能充能速度 -90%"),
            Eff("0", stat("35", T_EXCEPT, -45), pre=gate, **CURSE, note="【诅咒】自身以外的角色技能充能速度 -45%"),
        ]
    w.soul, w.ea = rows_s, rows_e
    w.deviations.append("第二轮：「逆沙」上限 5 层；技能伤害按「前 4 层每层一档、第 5 层单独 +100%」两行实现")
    w.deviations.append("「PF 命中敌人时」按强化弹射发动计；两种触发共用「逆沙」上限")
    w.deviations.append("第三轮「负面太少」：自身充能 -90%、队伍 -45%。队伍一项按「自身以外」实现——照字面全队 -45% 会让持有者合计 -135%，"
                        "充能先求和再钳到 -100%，持有者移动完全不充能、充能增益要先补满 35% 才有用、施放叠「逆沙」半边几乎失效；"
                        "瞬发 35 目标「自身以外」官方零先例（PARADOX 同形）")
    w.deviations.append("作者 0928 数值预算（刃合计 ≤1000%）：每层攻击 +160% → +100%（满层 +800% → +500%），"
                        "技能伤害前 4 层每层 +150% → +100%、第 5 层 +100% 不变（满层 +700% → +500%）；充能诅咒不变")
    return w


def w22() -> Weapon:
    w = Weapon(22, "diesel_engine", "柴油引擎", "饰品", ("fire",), "脆脆鲨",
               "冒着黑烟的铸铁柴油引擎", "引擎一响，后排的油就被抽干了。",
               "火属性共鸣时：队长攻击与技能伤害 +300%，伤害/技能伤害独立乘区各 +10%，获得合击角色攻击力 20% 的白值；"
               "队长每次发动技能，2、3 号位攻击力 -200%、技能槽 -50%，并「断油」10 秒：期间 2、3 号位无法获得能量")
    fire = (res("fire"),)
    drain = dsl_program("diesel_drain")
    w.dsl[drain] = dsl_root(slot_member(0, 84, C("SubtractSkillPoint", 0, P(0.5))),
                            slot_member(1, 85, C("SubtractSkillPoint", 1, P(0.5))))
    w.cas["cursed_diesel_drain"] = "2号位与3号位角色技能槽减少50%"
    leader_skill = trig(IT_SKILL, trigger_puller=P_LEADER)
    # 作者 0928「柴油写个10秒内无法获得能量吧」：计时固有「断油」挂在装备者身上（封能风笛/PARADOX 同形：持有者的 134 门禁），
    # 持有期间 2、3 号位 423 拦截规则码 78。134 按层数读 ⇒ 叠层上限必须 >1；10 秒内队长再次施放叠到 2 层并刷新时长
    u_cut = w.uid(1)
    w.uniques[u_cut] = unique_row(f"cursed_diesel_{u_cut}", "断油", "cursed_diesel_cutoff", "600", "2", bad=True)
    cut = gate_unique(u_cut)
    w.soul = [
        Eff("0", stat("32", T_LEADER, 75, 150), pre=fire, note="火属性共鸣时：队长攻击力 +75%→150%"),
        Eff("0", stat("34", T_LEADER, 75, 150), pre=fire, note="火属性共鸣时：队长技能伤害 +75%→150%"),
    ]
    w.ea = [
        *growth_pair("32", T_LEADER, 300, 150, pre=fire),
        *growth_pair("34", T_LEADER, 300, 150, pre=fire),
        Eff("0", stat("723", T_LEADER, 10), pre=fire, **FINAL, note="火属性共鸣时：队长伤害独立乘区 +10%"),
        Eff("0", stat("694", T_LEADER, 10), pre=fire, **FINAL, note="火属性共鸣时：队长技能伤害独立乘区 +10%"),
        Eff("0", stat("717", T_LEADER, 20), pre=fire, **FINAL, note="火属性共鸣时：队长获得合击角色攻击力 20% 的白值"),
        Eff("0", stat("32", T_SECOND, -200), trig=leader_skill, pre=fire, **CURSE,
            note="【诅咒】队长发动技能时 2 号位攻击力 -200%（每次叠加）"),
        Eff("0", stat("32", T_THIRD, -200), trig=leader_skill, pre=fire, **CURSE,
            note="【诅咒】队长发动技能时 3 号位攻击力 -200%（每次叠加）"),
        Eff("0", invoke("cursed_diesel_drain", drain), trig=leader_skill, pre=fire, **CURSE,
            note="【诅咒】队长发动技能时 2、3 号位技能槽 -50%"),
        Eff("0", unique(u_cut), trig=leader_skill, pre=fire, **CURSE,
            note="【诅咒】队长发动技能后装备者进入「断油」10 秒（强制付与、不可驱散）"),
        Eff("1", ("423", {"target": T_SECOND, "unique_condition_id": str(GAUGE_LOCK)}), trig=cut, pre=fire,
            even_if_dead=True, **CURSE, note="【诅咒】「断油」期间 2 号位无法获得能量（423，规则码 78；装备者阵亡仍生效）"),
        Eff("1", ("423", {"target": T_THIRD, "unique_condition_id": str(GAUGE_LOCK)}), trig=cut, pre=fire,
            even_if_dead=True, **CURSE, note="【诅咒】「断油」期间 3 号位无法获得能量（423，规则码 78；装备者阵亡仍生效）"),
    ]
    w.deviations.append("「10% 火属性伤害乘区」在火属性共鸣下等价于伤害独立乘区 +10%；「50% 的充能」按技能槽 -50% 实现；"
                        "攻击力 -200% 叠加受引擎攻击加成下限 -50% 约束")
    w.deviations.append("评分审查 0928（作者「按表改」）：队长攻击/技能伤害终值 +500% → +300%（刃合计 600%），本体设计 250 → 150"
                        "（满破实际 +30%）；独立乘区 10/10、717 白值 20%、2/3 号位攻击 -200%/次与技能槽 -50%/次不动")
    w.deviations.append("作者 0928「柴油写个10秒内无法获得能量吧」：保留原诅咒，追加队长发动技能后装备者「断油」10 秒（固有状态，"
                        "c10 强制、不可驱散、叠层上限 2），持有期间 2、3 号位 423 回槽拦截规则码 78（移动跑条/技能直接回槽/"
                        "能力回槽/其他动作脚本；只放行开局槽），装备者阵亡仍生效；图标挂在装备者身上。"
                        "需要 equipment-gauge-gain-rules-v1（equipment-rules 补丁 APK），未装补丁的客户端读到 C7050")
    w.deviations.append(timed_curse_unique_note("断油", 10))
    return w


def w25() -> Weapon:
    w = Weapon(25, "overclock_chip", "超频芯片", "饰品", ("thunder",), "不要脸",
               "迸着蓝白电弧的限制解除核心", "解除限制的代价，是核心过热的二十秒。",
               "自身为雷属性时：技能伤害 +600%、技能伤害独立乘区 +50%；自身发动技能后进入「过载」20 秒，"
               "期间无法获得能量（强制付与，不可驱散）")
    thunder = (my_element("thunder"),)
    # 作者 0928「超频芯片就是想做的无法获得能量」：施放后给自身计时固有「过载」（c10 强制、不可驱散、叠层上限 2——134 按层数读），
    # 持有期间自身 423 拦截规则码 78；替换原「充能速度 -100%」（701 与队友充能加成相加后会被抵消，直接回槽也拦不住）
    u_over = w.uid(1)
    w.uniques[u_over] = unique_row(f"cursed_overclock_{u_over}", "过载", "cursed_chip_overload", "1200", "2", bad=True)
    w.soul = [
        Eff("0", stat("694", T_SELF, 12.5, 25), pre=thunder, note="自身为雷属性时：技能伤害独立乘区 +12.5%→25%"),
        Eff("0", stat("34", T_SELF, 150, 300), pre=thunder, note="自身为雷属性时：技能伤害 +150%→300%"),
    ]
    w.ea = [
        *growth_pair("694", T_SELF, 50, 25, pre=thunder),
        *growth_pair("34", T_SELF, 600, 300, pre=thunder),
        Eff("0", unique(u_over), trig=trig(IT_SKILL, trigger_puller=P_SELF), pre=thunder, **CURSE,
            note="【诅咒】自身发动技能后进入「过载」20 秒（强制付与、不可驱散）"),
        Eff("1", ("423", {"target": T_SELF, "unique_condition_id": str(GAUGE_LOCK)}), trig=gate_unique(u_over),
            pre=thunder, **CURSE, note="【诅咒】「过载」期间自身无法获得能量（423，规则码 78）"),
    ]
    w.deviations.append("「乘区 7」按技能伤害独立乘区")
    w.deviations.append("作者 0928「不要脸写的数值都太高了，降低到其他深渊武器的常规水准」：技能伤害独立乘区终值 +400% → +50%"
                        "（乘区上限）")
    w.deviations.append("评分审查 0928（作者拍板「按方案做」）：乘区上限砍掉的部分用同名、同对象、同条件的技能伤害刃补回，"
                        "自身技能伤害 +600%（不要脸常规深渊上限 600/50 用满；本体设计 300，满破实际 +60%）")
    w.deviations.append("作者 0928「超频芯片就是想做的无法获得能量」：「过载」改为施放后 20 秒无法获得能量——计时固有「过载」"
                        "（c10 强制、不可驱散、叠层上限 2）+ 持有期间自身 423 回槽拦截规则码 78（移动跑条/技能直接回槽/能力回槽/"
                        "其他动作脚本；只放行开局槽），删掉原「技能充能速度 -100%」行（它会被队友的充能加成抵消，直接回槽也拦不住）。"
                        "需要 equipment-gauge-gain-rules-v1（equipment-rules 补丁 APK），未装补丁的客户端读到 C7050")
    w.deviations.append(timed_curse_unique_note("过载", 20))
    return w


def w26() -> Weapon:
    w = Weapon(26, "lone_wolf_crown", "孤狼王冠", "饰品", (), "不要脸",
               "狼首造型的银色王冠", "王座只容得下一个人——多一个都不行。",
               "自身技能充能速度 +100%，伤害独立乘区 +50%；队伍中有其他角色时以上全部抵消")
    # 提案表「建议」0928：删去全部刃值，只保留 100% 充能速度与增伤乘区（乘区 9）；增伤乘区按作者上限 50%
    stats = (("35", T_SELF, 100), ("723", T_SELF, 50))
    w.soul = [Eff("0", stat(kind, target, total / 4, total / 2),
                  note=f"自身{KIND_LABEL.get(kind, '伤害独立乘区')} +{total / 4:g}%→{total / 2:g}%")
              for kind, target, total in stats]
    w.ea = [row for kind, target, total in stats for row in growth_pair(kind, target, total, total / 2)]
    w.ea += [Eff("0", stat(kind, target, -total), pre=(HAS_TEAMMATE,), **CURSE,
                 note=f"【诅咒】队伍中有其他角色时：{KIND_LABEL.get(kind, '伤害独立乘区')} -{total:g}%")
             for kind, target, total in stats]
    w.deviations.append("「除自身外没有队友」无直接前置：改为「编成 ≥2 人时」逐项抵消（强化 1 级起按终值扣，120 级正好归零）；"
                        "「乘区 9」按伤害独立乘区")
    w.deviations.append("作者 0928 数值预算 + 提案表「建议」（删去全部刃值，只保留 100% 充能速度与 100% 增伤乘区）："
                        "刃值五项删除；增伤乘区按作者上限 +50%；技能充能速度 +100% 不计入预算，保留；抵消诅咒随之按新终值扣")
    w.deviations.append("评分审查 0928：定为单人挑战向整活武器，不参与常规强度梯度，数值不改（编成人数含合击位，带 1 个合击角色即触发抵消）")
    return w


def w27() -> Weapon:
    w = Weapon(27, "triphase_prism", "三相之力", "饰品", ("wind", "water", "fire"), "不要脸",
               "三色棱面的三角晶体", "三角形最稳定——可力量从不在一个角停留。",
               "自身为风/水/火属性时：直击、技能伤害、强化弹射伤害各 +140%；强化弹射命中时强化弹射伤害 -20%、直击 +20%；"
               "直击时直击 -20%、技能伤害 +20%；技能命中时技能伤害 -20%、强化弹射伤害 +20%"
               "（转入量随强化 +20%→120 级 +30%；各 CT1 秒，最多 2 次）")
    gate = (my_element("wind", "water", "fire"),)
    w.soul = [
        Eff("0", stat("33", T_SELF, 35, 70), pre=gate, note="自身为风/水/火属性时：直接攻击伤害 +35%→70%"),
        Eff("0", stat("34", T_SELF, 35, 70), pre=gate, note="自身为风/水/火属性时：技能伤害 +35%→70%"),
        Eff("0", stat("55", None, 35, 70), pre=gate, note="自身为风/水/火属性时：强化弹射伤害 +35%→70%"),
    ]
    TRANSFER = dict(learn=1, maxlvl=120)      # 转入量：强化 1 级 +20% → 120 级 +30%（同一行两端插值，不是诅咒常量）
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
    ]
    w.deviations.append("「若该伤害加成 >100%」：技能/强化弹射伤害提升量前置官方零用例、直击没有此类前置；改为每种转移 CT1 秒、"
                        "限次数")
    w.deviations.append("第三轮「转移量 +20%（满级 30%）」：三路转入改为强化 1 级 +20% 线性成长到 120 级 +30%；-20% 仍是强化 1 级起全额")
    w.deviations.append("作者 0928「不要脸写的数值都太高了，降低到其他深渊武器的常规水准」：去掉三项基础伤害的强化底数（原 +500%）")
    w.deviations.append("评分审查 0928 方案 A（作者拍板「按方案做」；群第二轮也认为 6 次无底数「削过头」）：每项补 +140% 底数"
                        "（实现方加的，提案本来没有底数），转化上限 6 → 2 次；刃合计 3×140% + 3×30%×2 = 600%，"
                        "满转后每项净 +160%。代价：成长只剩每项净 +20%，基本放弃「高成长」定位")
    return w


def w28() -> Weapon:
    w = Weapon(28, "flesh_for_bone", "肉斩骨断", "剑", ("wind",), "脆脆鲨",
               "刃口带血槽的厚背斩骨刀", "先斩自己的肉，才能断敌人的骨。",
               "风属性共鸣时：全队直接攻击伤害 +400%，获得合击角色攻击力 100% 的白值，伤害独立乘区 +10%、"
               "直接攻击伤害独立乘区 +10%；"
               "每次对敌人造成伤害时全队受到最大 HP 8% 的伤害、连击 +10（共用 CT2 秒）")
    wind = (res("wind"),)
    u_cd = w.uid(1)
    # 叠层上限必须 >1：前置 199「层数 ≤0」在上限 1 时层数恒 0 ⇒ 恒真，三路触发都没有冷却。只在 0 层时上锁，实际只有 1 层
    w.uniques[u_cd] = unique_row(f"cursed_bone_{u_cd}", "骨断", "cursed_bone_break", "120", "2", bad=True)
    w.soul = [
        Eff("0", stat("717", T_PARTY, 25, 50), pre=wind, note="风属性共鸣时：全队合击角色攻击力白值 +25%→50%"),
        Eff("0", stat("33", T_PARTY, 100, 200), pre=wind, note="风属性共鸣时：全队直接攻击伤害 +100%→200%"),
    ]
    w.ea = [
        *growth_pair("717", T_PARTY, 100, 50, pre=wind),
        *growth_pair("33", T_PARTY, 400, 200, pre=wind),
        Eff("0", stat("723", T_PARTY, 10), pre=wind, **FINAL, note="风属性共鸣时：全队伤害独立乘区 +10%"),
        Eff("0", stat("693", T_PARTY, 10), pre=wind, **FINAL, note="风属性共鸣时：全队直接攻击伤害独立乘区 +10%"),
    ]
    ready = (*wind, lacks_unique(u_cd))
    for source, trigger in (("直接攻击", trig(IT_DIRECT, trigger_puller=P_ONE_OF_PARTY, threshold=times(1))),
                            ("技能命中", trig(IT_SKILL_HIT, trigger_puller=P_ONE_OF_PARTY, threshold=times(1))),
                            ("强化弹射命中", trig(IT_PF_HIT, threshold=times(1)))):
        # 固有状态行排最后：同一次派发内先判前置再上锁
        w.ea += [
            Eff("0", stat("209", T_PARTY, 8), trig=trigger, pre=ready, **CURSE,
                note=f"【诅咒】{source}时全队受到最大 HP 8% 的伤害（共用 CT2 秒）"),
            Eff("0", ("226", {"strength": (times(10), times(10))}), trig=trigger, pre=ready, **CURSE,
                note=f"{source}时连击 +10（共用 CT2 秒）"),
            Eff("0", unique(u_cd), trig=trigger, pre=ready, **CURSE, note="进入「骨断」2 秒（共用冷却）"),
        ]
    w.deviations.append("「每次对敌人造成伤害」：官方「敌人受伤次数」触发只接场地系统、能力表零用例；按直击/技能命中/强化弹射命中三路触发，"
                        "以固有状态「骨断」2 秒做共用冷却（叠层上限写 2：前置 199 按层数判「没有」，上限 1 时层数恒读 0、"
                        "冷却从未生效——已上线版本即如此）；「10% 风属性伤害乘区」在风属性共鸣下等价于伤害独立乘区 +10%")
    w.deviations.append("第三轮按机制简介重做：自伤 5→8%、连击 +5→+10；去掉全队直击伤害 +1000%；正面改为全队合击角色攻击力白值"
                        "（终值 100%，按各自的合击角色计）、伤害独立乘区 +10%、直接攻击伤害独立乘区 +10%。"
                        "风险：瞬发 693 作用全队官方零先例；717 +100% 对三名主位同时生效，攻击力跳幅较大")
    w.deviations.append("评分审查 0928（作者拍板「按方案做」）：补回提案人第一轮写过、第三轮自己删掉的全队直接攻击伤害，取 40%："
                        "终值 +400%（本体设计 200，满破实际 +40%）；717 +100%、723/693 各 +10%、8% 自伤、连击 +10 与 CT2 秒不动")
    w.deviations.append(FRIENDLY_FIRE_NOTE + "（本把：三路命中时全队 8% 自伤）")
    return w


def w29() -> Weapon:
    w = Weapon(29, "cursed_mask", "被诅咒的面具", "饰品", ("dark",), "不要脸",
               "淌着血的鬼形面具", "戴上它就说不出咒语——但你已经不需要了。",
               "自身为暗属性时：攻击力 +500%、伤害独立乘区 +50%，造成伤害时回复最大 HP 1%（CT0.5 秒）；永久封印且弹球速度"
               "固定为最大（强制付与，无视免疫，不可驱散，复活后重新附加）；每 5 秒若 HP≥30%，失去最大 HP 的 10%")
    dark = (my_element("dark"),)
    revive = trig(IT_REVIVAL, trigger_puller=P_SELF)
    # 作者 0928 强制赋予：封印（219）与速度固定（688，作者定为负面）都换成 629 DSL forceApply，同键幂等、复活重挂。
    # ACFixedSpeed 参数 = 帧 / 速度 / 第二值 / 层数，对应能力表 688 的 FixedSpeed(strength, 0)（InstantAbilitySource.as:5753）
    seal, speed = dsl_program("mask_silence"), dsl_program("mask_speed")
    w.dsl[seal] = dsl_root(give(-17, [ac("ACSilence", DSL_FOREVER)], "cursed_mask_silence", cancelable=False, force=True))
    w.dsl[speed] = dsl_root(give(-17, [ac("ACFixedSpeed", DSL_FOREVER, P(2.0), P(0), P(1))], "cursed_mask_speed",
                                 cancelable=False, force=True))
    w.cas["cursed_mask_silence"] = "自身永久封印（强制付与，无视免疫与弱体无效，不可驱散）"
    w.cas["cursed_mask_speed"] = "弹球速度固定为200%（永续，强制付与，无视免疫与增益无效，不可驱散）"
    hit = dict(threshold=times(1), cooltime="30")
    w.soul = [
        Eff("0", stat("723", T_SELF, 12.5, 25), pre=dark, note="自身为暗属性时：伤害独立乘区 +12.5%→25%"),
        # 206 吸血不缩 BASE_SCALE（满破仍 1%），作者 0928 要求按觉醒 0 = 满破 20% 分级：0.2/0.4/0.6/0.8/1%
        Eff("0", stat("206", T_SELF, 0.2, 1), trig=trig(IT_DIRECT, trigger_puller=P_SELF, **hit),
            pre=dark, note="自身为暗属性时：直接攻击时回复最大 HP 的 0.2%→1%（CT0.5 秒）"),
        Eff("0", stat("206", T_SELF, 0.2, 1), trig=trig(IT_PF_HIT, **hit),
            pre=dark, note="自身为暗属性时：强化弹射命中时回复最大 HP 的 0.2%→1%（CT0.5 秒）"),
        Eff("0", stat("32", T_SELF, 50, 100), pre=dark, note="自身为暗属性时：攻击力 +50%→100%"),
    ]
    w.ea = [
        *growth_pair("723", T_SELF, 50, 25, pre=dark),
        *growth_pair("32", T_SELF, 500, 100, pre=dark),
        Eff("0", invoke("cursed_mask_silence", seal), pre=dark, **CURSE,
            note="【诅咒】自身永久封印（不能施放技能；强制付与、无视免疫、不可驱散）"),
        Eff("0", invoke("cursed_mask_silence", seal), trig=revive, pre=dark, **CURSE,
            note="【诅咒】复活后重新附加封印（同键幂等）"),
        Eff("0", invoke("cursed_mask_speed", speed), pre=dark, **CURSE,
            note="【诅咒】弹球速度固定为 200%（永续；强制付与、无视增益无效、不可驱散）"),
        Eff("0", invoke("cursed_mask_speed", speed), trig=revive, pre=dark, **CURSE,
            note="【诅咒】复活后重新固定弹球速度（同键幂等）"),
        Eff("0", stat("209", T_SELF, 10), trig=elapsed(300),
            pre=(*dark, (PRE_HP_HIGH, {"trigger_puller": P_SELF, "threshold": pct(30)})), **CURSE,
            note="【诅咒】每 5 秒若自身 HP ≥30%，失去最大 HP 的 10%"),
    ]
    w.deviations.append("「速度最大化」按官方速度固定 200%（ConditionFixedSpeed，风属性角色 1499896 同值）；「乘区 9」按伤害独立乘区；"
                        "「造成伤害时」按直击与强化弹射命中两路（本身已被封印，不会有技能伤害）")
    w.deviations.append("作者 0928「不要脸写的数值都太高了，降低到其他深渊武器的常规水准」：伤害独立乘区终值 +100% → +50%"
                        "（提案表「建议」列，恰好等于乘区上限）")
    w.deviations.append("评分审查 0928（作者拍板「按方案做」）：为达到评分线另加自身攻击力 +500%（暗属性门槛，与死亡使者基线相同；"
                        "本体设计 100，满破实际 +20%），超出提案原设计强度——面具是唯一整场封印自身技能的武器，代价远大于同作者两把；"
                        "封印、速度固定、吸血与扣血不变")
    w.deviations.append(FORCED_CURSE_NOTE + "；封印两行（开局 + 复活）原位换成 629。弹球速度固定 200% 是好方向内容，"
                        "作者 0928 定为负面一并强制（原来挡得住它的是增益无效与全状态无效），同样两行 629")
    w.deviations.append("作者 0928：本体两条吸血（206）也按觉醒分级，觉醒 0 = 满破 1% 的 20%（0.2%→1%）")
    w.deviations.append(FRIENDLY_FIRE_NOTE + "（本把：每 5 秒 HP≥30% 时失去 10%）")
    return w


WEAPON_BUILDERS: tuple[Callable[[], Weapon], ...] = (
    w01, w02, w03, w04, w05, w06, w07, w08, w09, w10, w11, w12, w13, w14, w15, w16, w17, w18, w19, w20, w21, w22, w23,
    w24, w25, w26, w27, w28, w29)


def weapons() -> list[Weapon]:
    out = [builder() for builder in WEAPON_BUILDERS]
    _require([w.row for w in out] == list(range(1, 30)), "提案行号必须是 1..29")
    _require(len({w.slug for w in out}) == len(out), "slug 重复")
    for w in out:
        w.soul = [_weaken(e) for e in w.soul]
    return out


# ---------------------------------------------------------------------------
# 数值预算门禁（作者 0928）
# ---------------------------------------------------------------------------

#: 作者 0928 原话：「武器数值基线是死亡使者的合计 500% 刃，有诅咒效果也不能让总数值超过 1000%，乘区不超过 50%」；
#: 「不要脸写的数值都太高了，降低到其他深渊武器的常规水准」。死亡使者 5900101 Lv120 = 全队攻击 25% + 全队能力伤害 475%；
#: 常规深渊武器 ≈500–600% 刃（8000101 攻击 300 + 直击 300、8000113 技能 525），官方只有死亡使者带 5% 独立乘区。
BLADE_CAP = 1000
MULTIPLIER_CAP = 50
REGULAR_ABYSS_BLADE_CAP = 600
REGULAR_ABYSS_AUTHORS = frozenset({"不要脸"})

#: 刃 = 攻击力 / 技能伤害 / 直接攻击伤害 / 能力伤害 / 强化弹射伤害 的正值 %（各种来源、各种目标合在一起算）。
BLADE_INSTANT_STATS = frozenset({"32", "34", "33", "388", "55"})         # 永久：开局给或每次触发永久叠加
BLADE_INSTANT_CONDITIONS = frozenset({"0", "1", "214", "486", "28"})     # 计时状态：按面值
BLADE_DURING = frozenset({"0", "2", "1", "154", "23"})
BLADE_ACS = frozenset({"ACAttackPoint", "ACSkillDamage", "ACDirectDamage", "ACAbilityDamage", "ACPowerFlipDamage"})
#: 乘区 = 独立乘区（伤害/直击/技能/能力/强化弹射）+ 逆境 的正值 %。
MULT_INSTANT_STATS = frozenset({"723", "693", "694", "695", "696"})
MULT_INSTANT_CONDITIONS = frozenset({"712", "713", "470"})
MULT_DURING = frozenset({"421", "410", "411", "412", "413"})
#: 不计入（「其他效果可以保留」）：负值诅咒、固定倍率命中、717 合击白值、充能、技能槽/上限、连击、贯通、浮游、速度、
#: 增减益持续时间、护盾、回复、协力球 HP、麻痹/封印、复读追加命中。

_MAIN_SLOTS = ("L", "S2", "S3")
_BUDGET_HORIZON = 18000        # 帧：周期触发的计时窗口展开到 5 分钟（最晚的固定时间点是 7860 帧）
_PERMANENT_FRAMES = 9999999    # 帧数 ≥ 这个值按永续
_GROUP_ELEMENT = {group: element for element, group in ELEMENT_GROUP.items()}
_DSL_SELECTOR = {82: "party", 83: "L", 84: "S2", 85: "S3"}


def _is_mult_ac(name: str) -> bool:
    return name.startswith("ACSeparatedTerm") or name == "ACAdversity"


#: DSL 刃/乘区 AC 的数组形状（wf_dsl_sig AdditionalConditionKind）：(强度下标…, 层数下标)，下标按 AC 列表项计（[0] = 名字）。
#: 三数组 = 帧 / 强度 / 层数；ACAdversity 四数组 = 帧 / 最小值 / 最大值 / 层数（引擎对状态来源的逆境 min/max 各钳 0.5，
#: 门禁按写的较大值保守计）。没登记形状的刃/乘区 AC 一律报 unbounded，不按三数组去猜。
_AC_SHAPES: dict[str, tuple[tuple[int, ...], int]] = {
    **{name: ((2,), 3) for name in (*sorted(BLADE_ACS), "ACSeparatedTermDirectDamage", "ACSeparatedTermPowerFlipDamage")},
    "ACAdversity": ((2, 3), 4),
}


def _refires_while_live(p: dict[str, Any], duration: float) -> bool:
    """同一瞬发行两次触发的效果能否同时存活（前一次还没结束，下一次又触发）。
    时机由战斗决定时：只触发 1 次或 CT 不短于持续时间才不会重叠；固定时间点触发按窗口判。"""
    fired = _fire_windows(p["trig"], p["threshold"], p["limit"], p["delay"], duration)
    if fired is None:
        if p["limit"] == "1":
            return False
        return (_number(p.get("cooltime", "")) or 0) < duration
    return any(later[0] < earlier[1] for earlier, later in zip(fired, fired[1:]))


def _number(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _frames_of(text: str) -> float:
    """frame 字段（×100000）→ 帧；永续写法记 inf。"""
    value = _number(text)
    if value is None:
        return float("inf")
    value /= 100000
    return float("inf") if value >= _PERMANENT_FRAMES else value


def _fire_windows(kind: str, threshold: str, limit: str, delay: float, duration: float) -> tuple | None:
    """瞬发触发 → 效果存续窗口 ((起, 止), …)（帧）；None = 时机由战斗决定（随时可能同时生效）。"""
    if kind == IT_INITIAL:
        return ((delay, delay + duration),)
    if kind == IT_ELAPSED:
        period = int(_number(threshold) or 0) // 100000
        if period <= 0:
            return None
        count = int(limit) if limit.isdigit() else _BUDGET_HORIZON // period
        return tuple((k * period + delay, k * period + delay + duration) for k in range(1, count + 1))
    return None


def _intersect(a: tuple | None, b: tuple | None) -> tuple | None:
    if a is None:
        return b
    if b is None:
        return a
    return tuple((max(s1, s2), min(e1, e2)) for s1, e1 in a for s2, e2 in b if max(s1, s2) < min(e1, e2))


def _gated(fired: tuple | None, gate: tuple | None, duration: float) -> tuple | None:
    """瞬发效果的存续窗口：触发时刻必须落在前置门禁窗口内（如持有某固有），效果从触发起持续 duration，
    不随门禁结束而截断（保守）。fired = 触发本身的窗口（None = 时机不定）。"""
    if gate is None:
        return fired
    if fired is None:
        return tuple((s, e + duration) for s, e in gate)
    return tuple((s, e) for s, e in fired if any(gs <= s < ge for gs, ge in gate))


def _reach(to: str | None, equipper: str) -> set[str]:
    """效果目标（表内目标码或 DSL 主体）→ 受益角色（队长 L / 2 号位 S2 / 3 号位 S3 / 协力球 MB）。"""
    if to in (T_SELF, "self"):
        return {equipper}
    if to == T_EXCEPT:
        return set(_MAIN_SLOTS) - {equipper}
    if to in (T_LEADER, "L"):
        return {"L"}
    if to in (T_SECOND, "S2"):
        return {"S2"}
    if to in (T_THIRD, "S3"):
        return {"S3"}
    if to == T_MULTIBALL:
        return {"MB"}
    return set(_MAIN_SLOTS)            # 全队 / 触发者 / 无目标（强化弹射）/ 未知：保守按任一主位都能拿到


def _budget_row(table: str, row: list[str]) -> dict[str, Any]:
    """一行词条里预算要用的字段（满破 / 120 级 = strength.first_max）。"""
    cell = lambda block, name: row[_col(table, block, name)]
    mode = row[int(_LAYOUT[table]["blocks"]["precondition1"]) - 1]
    pres = []
    for block in ("precondition1", "precondition2", "precondition3"):
        kind = cell(block, "kind")
        if kind not in ("0", "", "(None)"):
            pres.append({"kind": kind, "threshold": cell(block, "threshold.first_max"),
                         "groups": cell(block, "character_groups"), "uid": cell(block, "unique_condition_id")})
    element = None
    for pre in pres:
        if pre["kind"] == PRE_MEMBER and pre["threshold"] == times(6) and pre["groups"] in _GROUP_ELEMENT:
            element = _GROUP_ELEMENT[pre["groups"]]
    content = "instant_content" if mode == "0" else "during_content"
    trigger = "instant_trigger" if mode == "0" else "during_trigger"
    kind = cell(content, "kind")
    fields = _CASES[content].get(kind, {}).get("fields", {})
    out = {"mode": mode, "pres": pres, "element": element, "kind": kind,
           "target": cell(content, "target") if "target" in fields else None,
           "strength": _number(cell(content, "strength.first_max")) if "strength" in fields else None,
           "trig": cell(trigger, "kind"), "threshold": cell(trigger, "threshold.first_max"),
           "limit": cell(trigger, "trigger_limit")}
    if mode == "0":
        out["delay"] = (_number(cell("instant_delay", "instant_delay")) or 0) * 60
        trig_fields = _CASES["instant_trigger"].get(out["trig"], {}).get("fields", {})
        out["cooltime"] = cell("instant_trigger", "cooltime") if "cooltime" in trig_fields else ""
        out["frames"] = _frames_of(cell(content, "frame.first_max")) if "frame" in fields else float("inf")
        # 状态叠层上限：(None) = 不叠（重复触发只刷新）；数值兼容 ×100000 与裸数两种写法，保守取层数
        acc = _number(cell(content, "max_accumulation")) if "max_accumulation" in fields else None
        out["stacks"] = 1 if acc is None or acc < 1 else int(acc // 100000) if acc >= 100000 else int(acc)
        out["uid"] = cell(content, "unique_condition_id") if "unique_condition_id" in fields else ""
        out["program"] = cell(content, "action_path") if kind == "629" else ""
        out["precontent"] = (cell("instant_precontent", "kind"), cell("instant_precontent", "unique_condition_id"))
    else:
        out["uid"] = cell(trigger, "unique_condition_id")
    return out


def _dsl_effects(node: Any, binds: dict[int, str], variables: dict[int, int],
                 out: dict[str, list]) -> list[tuple[list, list]]:
    """DSL 树 → 可能的结果 [(效果, 授予的固有)]：随机/条件分支展开成并列备选，块内顺序拼接。
    效果 = (类别, 存储值, 主体, 持续帧, 说明)；AC 数值 ×1000 与表内同单位（1.0 = 100% = 100000）。
    带 mul 的数值乘以对应变量的上限（吞噬协力球计数等）；找不到变量上限记进 out["unbounded"]。"""
    if not isinstance(node, list) or not node:
        return [([], [])]
    head = node[0]
    if head == "ActionDsl":
        return _dsl_effects(node[11], binds, variables, out)
    if head == "Block":
        alts: list[tuple[list, list]] = [([], [])]
        for child in node[1]:
            sub = _dsl_effects(child, binds, variables, out)
            alts = [(a[0] + s[0], a[1] + s[1]) for a in alts for s in sub]
        return alts
    if head == "Event":
        return _dsl_effects(node[1][-1], binds, variables, out)
    if head != "Command":
        return [([], [])]
    name, params = node[1][0], node[1][1:]
    if name == "ConditionalsProbability":
        return [alt for branch in params[0][1] for alt in _dsl_effects(branch[1][1], binds, variables, out)]
    if name.startswith("Conditionals"):
        alts = [alt for p in params if isinstance(p, list) and p and p[0] in ("Block", "Command", "Event")
                for alt in _dsl_effects(p, binds, variables, out)]
        return alts or [([], [])]
    if name == "MultiballNumberVariable":
        variables[params[0]] = int(params[-1])
        return [([], [])]
    if name == "FindAllSubjects":
        return _dsl_effects(params[-1], {**binds, params[0]: _DSL_SELECTOR.get(params[1], "party")}, variables, out)
    if name == "CreateCondition":
        subject = "self" if params[0] == -17 else binds.get(params[0], "party")
        magnification = params[10][0]["max"] if isinstance(params[10], list) and params[10] else 1
        effects, grants = [], []
        for acv in params[1]:
            if acv[0] == "ACUnique":
                grants.append(str(acv[1]))
                continue
            category = "blade" if acv[0] in BLADE_ACS else "mult" if _is_mult_ac(acv[0]) else None
            if category is None:
                continue
            shape = _AC_SHAPES.get(acv[0])
            if shape is None:
                out["unbounded"].append(f"DSL {acv[0]} 的参数形状未登记，数值无法计入预算")
                continue
            value_at, stacks_at = shape
            values = []
            for index in value_at:
                spec = acv[index][0]
                value = spec["max"] * magnification
                if "mul" in spec:
                    cap = variables.get(spec["mul"])
                    if cap is None:
                        out["unbounded"].append(f"DSL {acv[0]} 的 mul 变量 {spec['mul']} 没有上限")
                        cap = 1
                    value *= cap
                values.append(value)
            has_stacks = len(acv) > stacks_at and isinstance(acv[stacks_at], list) and acv[stacks_at]
            stacks = acv[stacks_at][0]["max"] if has_stacks else 1
            effects.append((category, round(max(values) * max(stacks, 1) * 100000), subject, acv[1][0]["max"], acv[0]))
        return [(effects, grants)]
    alts = [([], [])]
    for p in params:
        if isinstance(p, list) and p and p[0] in ("Block", "Command", "Event"):
            sub = _dsl_effects(p, binds, variables, out)
            alts = [(a[0] + s[0], a[1] + s[1]) for a in alts for s in sub]
    return alts


def weapon_budget(soul_rows: list[list[str]], ea_rows: list[list[str]], uniques: dict[str, list[list[str]]],
                  dsl: dict[str, list]) -> dict[str, Any]:
    """一把武器满破 + 强化 120 级时单个角色能同时拿到的最大刃值 / 乘区（%），纯函数、确定性。

    口径（作者 0928 预算）：
    - 数值取 strength.first_max（本体满破、强化 120 级）；
    - 永久数值（32/34/33/388/55、723/693–696）开局给 ×1，触发给 × 触发次数上限；没有次数上限的触发记进 unbounded；
    - 计时状态按面值（同一行重复触发只刷新）；持续词条按固有层数门禁 134 取 min(叠层上限 ÷ 阈值, 倍乘上限)，
      其他计数型持续触发（带 trigger_limit 字段）× 倍乘上限，没有倍乘上限记进 unbounded；
    - 629 DSL 的 AC 同样计入（mul 乘变量上限、maxAccumulation、倍率；形状按 _AC_SHAPES，未登记的记进 unbounded）；
      随机/条件分支每次只取一支——前提是同一行两次触发不会同时存活，多支且可能重叠时记进 unbounded；
    - 按属性共鸣拆开的行只在对应分支生效，结果取各分支最大；
    - 固有状态由开局 / 固定时间点授予时有存续窗口，时间上不重叠的效果不相加；其余时机不定的效果一律当作可同时生效；
    - 「没有某固有」且该固有开局永续、从不被消耗 ⇒ 该行 120 级恒不生效；
    - 全队与自身同样按单个角色计（全队 +500% 记 500 不记 1500），不同目标（2 号位 / 3 号位）不相加。
    """
    rows = [(f"本体#{i}", _budget_row(SOUL_T, r)) for i, r in enumerate(soul_rows)]
    rows += [(f"强化#{i}", _budget_row(EA_T, r)) for i, r in enumerate(ea_rows)]
    notes: dict[str, list] = {"unbounded": []}
    trees = {p["program"]: dsl.get(p["program"]) for _w, p in rows if p["mode"] == "0" and p["kind"] == "629"}
    for program, tree in trees.items():
        if tree is None:
            notes["unbounded"].append(f"629 引用的 DSL {program} 不存在")

    consumed = {p["uid"] for _w, p in rows if p["mode"] == "0" and p["kind"] in ACC_CONTENT_KINDS}
    consumed |= {p["precontent"][1] for _w, p in rows if p["mode"] == "0" and p["precontent"][0] in ACC_PRECONTENT_KINDS}
    for tree in trees.values():
        consumed |= {str(params[1]) for params in _commands(tree, "ConsumeUniqueCondition")}

    def unique_frames(uid: str) -> float:
        """固有状态 c3 持续帧（不是 ×100000）；缺表或永续写法按 inf。"""
        rec = uniques.get(uid)
        if not (rec and rec[0][3].isdigit()):
            return float("inf")
        return float("inf") if int(rec[0][3]) >= _PERMANENT_FRAMES else float(rec[0][3])

    def unique_cap(uid: str) -> int:
        rec = uniques.get(uid)
        return int(rec[0][4]) if rec and rec[0][4].isdigit() else 1

    # 固有状态的授予：(uid, 属性分支) → [窗口 | None]
    grants: dict[tuple[str, str | None], list] = {}
    for _where, p in rows:
        if p["mode"] != "0":
            continue
        uids = [p["uid"]] if p["kind"] == "461" else []
        if p["kind"] == "629" and trees.get(p["program"]) is not None:
            scratch: dict[str, list] = {"unbounded": []}
            uids += [u for _e, gs in _dsl_effects(trees[p["program"]], {}, {}, scratch) for u in gs]
        for uid in dict.fromkeys(uids):
            windows = _fire_windows(p["trig"], p["threshold"], p["limit"], p["delay"], unique_frames(uid))
            grants.setdefault((uid, p["element"]), []).append(windows)

    def held(uid: str, element: str | None) -> tuple | None:
        """该属性分支里持有 uid 的时间窗口；None = 时机不定（随时可能持有）；() = 从未授予。"""
        found = grants.get((uid, None), []) + (grants.get((uid, element), []) if element else [])
        if any(w is None for w in found):
            return None
        return tuple(sorted(iv for w in found for iv in w))

    def always_held(uid: str, element: str | None) -> bool:
        """开局起永续持有且从不被消耗（「没有 uid」的门禁 120 级恒不成立）。"""
        windows = held(uid, element)
        return (uid not in consumed and windows is not None
                and any(s <= 0 and e == float("inf") for s, e in windows))

    elements = sorted({p["element"] for _w, p in rows if p["element"]}) or [None]
    best: dict[str, tuple[int, list]] = {"blade": (0, []), "mult": (0, [])}
    for element in elements:
        items: list[tuple[str, int, str | None, tuple | None, str]] = []    # (类别, 存储值, 目标, 窗口, 说明)
        groups: list[list[list]] = []
        for where, p in rows:
            if p["element"] not in (None, element):
                continue
            window = None
            if any(pre["kind"] == PRE_UNIQUE_LE and pre["threshold"] == "0" and always_held(pre["uid"], element)
                   for pre in p["pres"]):
                continue
            for pre in p["pres"]:
                if pre["kind"] == PRE_HAS_UNIQUE:
                    window = _intersect(window, held(pre["uid"], element))
            strength = p["strength"] or 0
            if p["mode"] == "1":
                count = 1
                category = "blade" if p["kind"] in BLADE_DURING else "mult" if p["kind"] in MULT_DURING else None
                if p["trig"] == DT_UNIQUE:
                    need = max(1, int(_number(p["threshold"]) or 0) // 100000)
                    count = unique_cap(p["uid"]) // need
                    if p["limit"].isdigit():
                        count = min(count, int(p["limit"]))
                    window = _intersect(window, held(p["uid"], element))
                elif p["trig"] == DT_UNIQUE_LOW and p["threshold"] == "0" and always_held(p["uid"], element):
                    continue
                elif "trigger_limit" in _CASES["during_trigger"].get(p["trig"], {}).get("fields", {}):
                    # 计数型持续触发（ComboHigh / Count* / ConditionCount* / HpDecrease …）：引擎取 floor(计数 ÷ 阈值)
                    # 再截倍乘上限 trigger_limit；(None) = 不封顶
                    if p["limit"].isdigit():
                        count = int(p["limit"])
                    elif category and strength > 0:
                        notes["unbounded"].append(f"{where} 持续触发 {p['trig']} 按计数倍乘，没有倍乘上限")
                if category and strength > 0 and count > 0:
                    items.append((category, int(strength) * count, p["target"], window, where))
                continue
            kind = p["kind"]
            if kind in BLADE_INSTANT_STATS or kind in MULT_INSTANT_STATS:
                category = "blade" if kind in BLADE_INSTANT_STATS else "mult"
                count = 1
                if p["trig"] != IT_INITIAL:
                    if p["limit"].isdigit():
                        count = int(p["limit"])
                    elif strength > 0:
                        notes["unbounded"].append(f"{where} kind {kind} 触发无次数上限，永久叠加没有封顶")
                if strength > 0 and window != ():            # 永久数值：只要触发得了，之后一直在
                    items.append((category, int(strength) * count, p["target"], None, where))
            elif kind in BLADE_INSTANT_CONDITIONS or kind in MULT_INSTANT_CONDITIONS:
                category = "blade" if kind in BLADE_INSTANT_CONDITIONS else "mult"
                timed = _fire_windows(p["trig"], p["threshold"], p["limit"], p["delay"], p["frames"])
                if strength > 0:
                    items.append((category, int(strength) * p["stacks"], p["target"],
                                  _gated(timed, window, p["frames"]), where))
            elif kind == "629" and trees.get(p["program"]) is not None:
                options, longest = [], 0.0
                for effects, _grants in _dsl_effects(trees[p["program"]], {}, {}, notes):
                    option = []
                    for category, value, subject, frame_count, name in effects:
                        if value <= 0:
                            continue
                        duration = float("inf") if frame_count >= _PERMANENT_FRAMES else frame_count
                        longest = max(longest, duration)
                        timed = _fire_windows(p["trig"], p["threshold"], p["limit"], p["delay"], duration)
                        option.append((category, value, subject, _gated(timed, window, duration), f"{where} {name}"))
                    if option:
                        options.append(option)
                # 每行只选一支、所有触发共用：前提是同一行的两次触发不会同时存活，否则不同分支可能叠在一起
                if len(options) > 1 and _refires_while_live(p, longest):
                    notes["unbounded"].append(f"{where} 629 的 {len(options)} 支随机/条件分支可能被多次触发同时存活，"
                                              "按单支计会低估")
                if options:
                    groups.append(options)

        points = {0.0}
        for option in [items] + [o for g in groups for o in g]:
            for _c, _v, _t, window, _w in option:
                points |= {s for s, _e in (window or ()) if s < _BUDGET_HORIZON}
        for choice in itertools.product(*groups):
            pool = items + [it for option in choice for it in option]
            for t in sorted(points):
                live = [it for it in pool if it[3] is None or any(s <= t < e for s, e in it[3])]
                for equipper in _MAIN_SLOTS:
                    for who in (*_MAIN_SLOTS, "MB"):
                        for category in ("blade", "mult"):
                            got = [it for it in live if it[0] == category and who in _reach(it[2], equipper)]
                            total = sum(it[1] for it in got)
                            if total > best[category][0]:
                                best[category] = (total, sorted(it[4] for it in got))
    return {"blades": best["blade"][0] / 1000, "multipliers": best["mult"][0] / 1000,
            "blade_sources": best["blade"][1], "multiplier_sources": best["mult"][1],
            "unbounded": sorted(set(notes["unbounded"]))}


def budget_caps(author: str) -> tuple[float, float]:
    """(刃上限, 乘区上限)：不要脸的提案压到常规深渊水准。"""
    blade = REGULAR_ABYSS_BLADE_CAP if author in REGULAR_ABYSS_AUTHORS else BLADE_CAP
    return blade, MULTIPLIER_CAP


def budget_problems(label: str, author: str, budget: dict[str, Any]) -> list[str]:
    blade_cap, mult_cap = budget_caps(author)
    probs = [f"{label}: 数值预算 {u}" for u in budget["unbounded"]]
    if budget["blades"] > blade_cap:
        probs.append(f"{label}: 刃合计 {budget['blades']:g}% 超过上限 {blade_cap}%（{'、'.join(budget['blade_sources'])}）")
    if budget["multipliers"] > mult_cap:
        probs.append(f"{label}: 乘区合计 {budget['multipliers']:g}% 超过上限 {mult_cap}%"
                     f"（{'、'.join(budget['multiplier_sources'])}）")
    return probs


# ---------------------------------------------------------------------------
# 读 live
# ---------------------------------------------------------------------------

class LiveReader:
    """最小只读接口：flat(logical) -> {key: [[cells]]}；nested(logical) -> {key: {...}}；
    server(name) -> 解析后的 JSON。由暂存脚本注入真实实现，测试注入 fixture。"""

    def __init__(self, flat: Callable[[str], dict], nested: Callable[[str], dict], server: Callable[[str], Any]):
        self.flat, self.nested, self.server = flat, nested, server


def _template(read: LiveReader, logical: str, key: str, width: int) -> list[str]:
    rows = read.flat(logical)[key]
    _require(len(rows) >= 1 and len(rows[0]) == width, f"{logical}[{key}] 模板形状漂移")
    return list(rows[0])


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

#: 官方文案长度上限（live 实测）：equipment c7 ≤ 57、equipment_enhancement c6 ≤ 54。
#: 详细效果由客户端按词条行自动生成，文案只放风味与口径，超长会溢出详情框。
DESC_LIMITS = {"equipment": 57, "enhancement": 54}


#: 客户端补丁 equipment-rules R2：本方（主位武器槽 + 魂珠槽）诅咒段装备 ≥2 件时全部整件失效（本体 + 强化）。
#: 装备详情页仍显示满档，玩家只能从说明里看到这条规则；PARADOX 不计入（作者确认）。
#: 魂珠槽同样计数（一把诅咒武器 + 另一把的魂珠也会两件都失效），所以写「两件（含魂珠）」不写「两把」，与 PARADOX 衰减说明口径一致。
CURSE_RULE = "【诅咒武器·同队两件以上（含魂珠）全部失效】"


def _description(w: Weapon) -> str:
    return f"{w.flavor}{CURSE_RULE}提案：{w.author}"


def _enh_description(w: Weapon) -> str:
    return f"强化1级起诅咒生效，120级为最终数值。提案：{w.author}"


def _cost_cells(costs: Iterable[tuple[str, int]]) -> list[str]:
    cells = []
    for item_id, amount in costs:
        cells += [item_id, str(amount)]
    while len(cells) < 8:
        cells += ["(None)", ""]
    return cells


def row_capabilities(table: str, row: list[str]) -> list[str]:
    """该行在客户端不 C7050 所需的 capability（wf_client_legality 已合并运行时与表解析器扩展两部分）。"""
    return list(L.required_client_capabilities(table, row))


def build(read: LiveReader, *, client_capabilities: Iterable[str] = BASE_CLIENT_CAPABILITIES) -> dict[str, Any]:
    """client_capabilities = 接收这批数据的**全部**客户端共有的 capability；默认 1047 基线，
    装备表 423 行（封能风笛）会作为缺 equipment-gauge-gain-rules-v1 进 problems。"""
    _require(not isinstance(client_capabilities, str), "client_capabilities 须是 capability 名的集合，不是单个字符串")
    have = frozenset(client_capabilities)
    capabilities: list[str] = []
    ws = weapons()
    flat: dict[str, dict[str, list[list[str]]]] = {t: {} for t in FLAT_TABLES}
    nested: dict[str, dict[str, dict]] = {t: {} for t in NESTED_TABLES}
    dsl: dict[str, list] = {}
    problems: list[str] = []

    item_tpl = _template(read, ITEM, "8000101", 23)
    equip_tpl = _template(read, EQUIPMENT, "8000101", 16)
    enh_tpl = _template(read, ENH, "5900101", 9)
    shop_tpls = [_template(read, ENH_SHOP, f"5900110{i}", 50) for i in range(1, 7)]
    cat_tpl = _template(read, ENH_CATEGORY, "5", 10)

    for w in ws:
        wid = w.id
        for kind, text in (("equipment", _description(w)), ("enhancement", _enh_description(w))):
            _require(len(text) <= DESC_LIMITS[kind], f"{w.name} {kind} 文案 {len(text)} 字超出官方上限 {DESC_LIMITS[kind]}")
            _require("," not in text and "\n" not in text, f"{w.name} {kind} 文案含半角逗号/换行")
        # item（同键魂珠物品行，缺了 ItemLogic 取空崩）
        row = list(item_tpl)
        row[0], row[1], row[2], row[3] = f"mod_cursed_{wid}", wid, f"{w.name}魂珠", w.icon
        flat[ITEM][wid] = [row]
        # equipment
        row = list(equip_tpl)
        row[0], row[1], row[6], row[7], row[9], row[10] = f"mod_cursed_{w.slug}", w.name, w.icon, _description(w), "false", wid
        _require(row[2] == "0" and row[8] == "5" and row[11] == "5", "equipment 模板列义漂移")
        flat[EQUIPMENT][wid] = [row]
        nested[EQUIPMENT_STATUS][wid] = dict(EQUIPMENT_STATUS_ROWS)
        # ability_soul / 强化词条
        soul_rows = [build_row(SOUL_T, slot, eff) for slot, eff in enumerate(w.soul)]
        ea_rows = [build_row(EA_T, slot, eff) for slot, eff in enumerate(w.ea)]
        for table, rows in ((SOUL_T, soul_rows), (EA_T, ea_rows)):
            for index, r in enumerate(rows):
                for p in L.client_legality_problems(table, r):
                    problems.append(f"{w.row:02d} {w.name} {table}#{index}: {p}")
                needed = row_capabilities(table, r)
                capabilities += [c for c in needed if c not in capabilities]
                problems += [f"{w.row:02d} {w.name} {table}#{index}: 目标客户端缺 capability {c}（未打补丁读到即 C7050）"
                             for c in needed if c not in have]
        flat[SOUL][wid] = soul_rows
        flat[EA][wid] = ea_rows
        # equipment_enhancement：名/图/描述/发光全部 120 级（最终形态）才切换
        row = list(enh_tpl)
        row[0:9] = ["120", "120", f"{w.name}·解咒", "120", w.icon120, "120", _enh_description(w), "120", START_TIME]
        flat[ENH][wid] = [row]
        nested[ENH_STATUS][wid] = dict(ENH_STATUS_ROWS)
        # 强化商店 6 阶（类目 6，组 = 武器 ID）
        for stage, ((cap, costs), tpl) in enumerate(zip(ENH_STAGES, shop_tpls), start=1):
            row = list(tpl)
            row[0], row[2], row[3] = ENH_CATEGORY_KEY, wid, str(stage)
            row[14:22] = _cost_cells(costs)
            row[22], row[23], row[29], row[30], row[31] = START_TIME, "(None)", wid, str(cap), str(REQUIRE_AWAKENING)
            flat[ENH_SHOP][f"{wid}{stage:02d}"] = [row]
        # 固有状态 / 文案 / DSL
        for uid, urow in w.uniques.items():
            flat[UNIQUE][uid] = [urow]
        for sid, text in w.cas.items():
            _require("," not in text and "\n" not in text, f"{w.name} 文案 {sid} 含半角逗号/换行")
            flat[CAS][sid] = [[text]]
        dsl.update(w.dsl)

    cas_keys = set(read.flat(CAS)) | set(flat[CAS])
    for w in ws:
        for table, logical in ((SOUL_T, SOUL), (EA_T, EA)):
            for index, r in enumerate(flat[logical][w.id]):
                problems += [f"{w.row:02d} {w.name} {table}#{index}: {p}"
                             for p in L.invoke_skill_string_problems(r, cas_keys, table)]
        for table, logical in ((SOUL_T, SOUL), (EA_T, EA)):
            for index, r in enumerate(flat[logical][w.id]):
                problems += [f"{w.row:02d} {w.name} {table}#{index}: {p}" for p in pf_echo_trigger_problems(table, r, dsl)]
        programs = {r[_col(t, "instant_content", "action_path")]
                    for t, logical in ((SOUL_T, SOUL), (EA_T, EA)) for r in flat[logical][w.id]
                    if r[_col(t, "instant_content", "kind")] == "629"}
        _require(programs == set(w.dsl), f"{w.name} 629 行引用的 DSL 与生成的 DSL 不一致：{programs ^ set(w.dsl)}")

    # 数值预算门禁（作者 0928）：刃 ≤1000%、乘区 ≤50%；不要脸的提案压到常规深渊水准（刃 ≤600%）
    budgets: dict[int, dict[str, Any]] = {}
    for w in ws:
        budgets[w.row] = weapon_budget(flat[SOUL][w.id], flat[EA][w.id], flat[UNIQUE], dsl)
        problems += budget_problems(f"{w.row:02d} {w.name}", w.author, budgets[w.row])

    row = list(cat_tpl)
    row[0], row[1], row[3], row[4], row[5], row[8] = ("cursed_weapon", ENH_CATEGORY_DISPLAY_ORDER, "诅咒武器·觉醒", BANNER,
                                                      HEADER, START_TIME)
    flat[ENH_CATEGORY][ENH_CATEGORY_KEY] = [row]

    for program, tree in dsl.items():
        for check in (dsl_signature_problems, colorless_hit_effect_problems, L.action_dsl_element_problems,
                      L.action_dsl_subject_binding_problems, L.action_dsl_lookup_scope_problems,
                      L.action_dsl_hit_area_target_problems):
            problems += [f"DSL {program}: {p}" for p in check(tree)]
        # 根头 buffTargetAs 段覆盖（133 = PF3）：未装 damage-type-rules 读成 0 按技能伤害结算，不崩但归属不对
        needed = dsl_capabilities(tree)
        capabilities += [c for c in needed if c not in capabilities]
        problems += [f"DSL {program}: 目标客户端缺 capability {c}（伤害归属退回技能伤害）" for c in needed if c not in have]
    problems += [f"DSL {p}" for p in own_lock_delete_problems(dsl)]

    # 叠层上限门禁：按层数读/消耗的固有 c4 必须 >1；已知死行（ACCUMULATION_CAP_PENDING）单列，修好后必须删条目
    rows = [(f"{w.row:02d} {w.name} {table}#{index}", table, r)
            for w in ws for table, logical in ((SOUL_T, SOUL), (EA_T, EA))
            for index, r in enumerate(flat[logical][w.id])]
    pending: list[str] = []
    seen_pending: set[str] = set()
    for uid, message in unique_accumulation_problems(rows, dsl, flat[UNIQUE]):
        if uid in ACCUMULATION_CAP_PENDING:
            seen_pending.add(uid)
            pending.append(message)
        else:
            problems.append(message)
    problems += [f"ACCUMULATION_CAP_PENDING 残留：{uid}（{ACCUMULATION_CAP_PENDING[uid]}）已不再触发叠层上限门禁，删掉这一条"
                 for uid in sorted(set(ACCUMULATION_CAP_PENDING) - seen_pending)]

    _check_collisions(read, flat, nested)
    return {
        "flat": flat, "nested": nested, "dsl": dsl, "server": _server_delta(read, ws, flat),
        "problems": problems, "weapons": ws, "capabilities": capabilities, "accumulation_pending": pending,
        "budgets": budgets,
    }


def _check_collisions(read: LiveReader, flat: dict, nested: dict) -> None:
    for logical, rows in flat.items():
        live = read.flat(logical)
        clash = sorted(set(rows) & set(live))
        _require(not clash, f"{logical} 键已存在：{clash[:5]}")
    for logical, rows in nested.items():
        live = read.nested(logical)
        clash = sorted(set(rows) & set(live))
        _require(not clash, f"{logical} 键已存在：{clash[:5]}")


def _server_delta(read: LiveReader, ws: list[Weapon], flat: dict) -> dict[str, Any]:
    ids = [int(w.id) for w in ws]
    shop = {}
    for key, rows in flat[ENH_SHOP].items():
        r = rows[0]
        costs = [{"id": int(r[i]), "amount": int(r[i + 1])} for i in (14, 16, 18, 20) if r[i] not in ("", "(None)")]
        shop[key] = {"availableFrom": START_TIME, "availableUntil": None, "costs": costs,
                     "enhancementMaxLevel": int(r[30]), "equipmentId": int(r[29]), "groupId": int(r[2]),
                     "requireAwakeningLevel": int(r[31]), "rewards": [], "shopCategoryId": int(r[0]),
                     "stage": int(r[3]), "stock": -1}
    return {
        "equipment_ids.json": ids,
        "equipment_lookup.json": {w.id: {"name": w.name, "rarity": "5", "category": w.category} for w in ws},
        "equipment_max_level.json": {w.id: 5 for w in ws},
        "equipment_element.json": {w.id: w.element_code() for w in ws},
        "item_ids.json": ids,
        "item_sale.json": {w.id: {"category": 5, "sale_price": 500, "sellable": True} for w in ws},
        "equipment_enhancement_shop.json": shop,
    }


# ---------------------------------------------------------------------------
# 设计文档（由同一份规格生成，防止文档与数据漂移）
# ---------------------------------------------------------------------------

def _level_label(e: Eff) -> str:
    if e.learn == e.maxlvl:
        return f"Lv{e.learn}"
    return "Lv1 起" if e.maxlvl == 120 else f"Lv{e.learn}→{e.maxlvl}"


def design_markdown(ws: list[Weapon]) -> str:
    lines = [f"# 诅咒武器 {len(ws)} 把 · 设计与实现", "",
             f"口径（作者 0928）：未强化（本体/满破）只有正面效果且很弱（设计值 × {BASE_SCALE:g}）；"
             f"本体数值行觉醒 0 = 满破的 {AWAKEN_FLOOR:.0%}，每觉醒 1 级 +{AWAKEN_FLOOR:.0%}（满破值不变）；强化 1 级起诅咒全额生效；"
             "强化 120 级为最终数值；强化材料全部来自五重决战。",
             "获取：武器扭蛋（只能用五重决战兑换的专用券抽取；每把 0.3%，250 点可兑换任选 1 把；满破需 5 把）。"
             "作者 0928 起不再在五重商店兑换。",
             "强化：装备强化「诅咒武器·觉醒」分类，6 阶（→69 每级 1 结晶 / 70：10 结晶+1 心核 / →98 每级 2 结晶 / 99：10 结晶+2 心核 / "
             "→119 每级 3 结晶+1 心核 / 120：3 心核+2 图纸），需满破。", ""]
    for w in ws:
        el = "/".join({"fire": "火", "water": "水", "thunder": "雷", "wind": "风", "dark": "暗", "light": "光"}[e]
                      for e in w.elements) or "通用"
        lines += [f"## {w.row:02d}. {w.name}（{w.id}，{w.category}，{el}，提案：{w.author}）", "",
                  f"- 外形：{w.look}", f"- 120 级解放：{w.summary_120}", "- 本体（箭头左值 = 觉醒 0，右值 = 满破）："]
        lines += [f"  - {e.note}" for e in w.soul]
        lines.append("- 强化：")
        lines += [f"  - {_level_label(e)}：{e.note or '（成长/补足）'}" for e in w.ea]
        if w.deviations:
            lines.append("- 与提案原文的偏差：")
            lines += [f"  - {d}" for d in w.deviations]
        lines.append("")
    return "\n".join(lines)
