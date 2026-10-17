# -*- coding: utf-8 -*-
"""2026-09-27 第三轮（成长复核）：罗尔夫「不落幕的安可」149986 ``black_wolf_knight_moon``（风，中秋）的键级修订。

注意：不是 wt26 罗尔夫 179999，也不是官方 141159。

作者原话（主会话 2026-09-27 逐字转述，按时间顺序）：
「部分角色技能都倍率成长也要无限成长,成长条件放到队长技里面带上对应共鸣条件,凯尔的成长降太低了,本身数值就不高,
很多角色成长过于缓慢,也要基于角色本身的其他词条判断,比如部分角色没有基础刃值只能靠成长」／「成长速度砍到1/10不合理,
现在本来就算是正常偏快而已,砍太多了」／「砍到4/5,或者7/10这样吧,很多角色没有成长完全没用了」／「可以砍到2/3」／
「数值尽量取5的倍数比如36就变成35,39就变成40」。

按 live 链尾 1.4.1053 推导：第二批 ``wf_balance_20260927b_rolfmoon``（1.4.1051）放缓了三项「每 100 直击」成长（×1/5），
并把能力3 两条 IT 246 读秒行搬到能力6 #5/#6 的前置 42 队长承载行（×1/10）。行号 0 基（``#n``）。

改动（数值表 reeval_full.json 罗尔夫·中秋四行；只改强度，其余行、其余列逐字保留）：
    队长 #3 风队攻击力（每 100 次风队直击）      c49/c50 20000 → 80000（+20% → +80%；原 100% × 4/5，风队攻击力只能靠这条）
    队长 #4 风队直击伤害（同触发）               c49/c50 20000 → 70000（+20% → +70%；原 100% × 7/10，有条件型基础）
    能力6 #3 风队独立乘区直击（693，前置 42）     c51/c52  2000 →  7000（+2% → +7%；原 10% × 7/10，<10% 不取 5 的倍数）
    能力6 #5/#6 读秒自身攻击力/直击（IT 246，前置 42）c51/c52 5000 → 35000（+5% → +35%；原 50% × 7/10）
    246 按与 235 同一实现反复触发计（复核：InstantAbilityTriggerMasterValueTools 两者都映射 ConditionKeepFrame），
    取 7/10 不变，不走「只触发一次改 4/5」的分支。
    不新增前置（口径 D3）；能力3 #1/#2 的持有型 +100%（第二批封顶版）不动（口径 D4）。

面板：队长 ``desc_override_black_wolf_knight_moon`` 第 5 行「攻击力＋80%、直击伤害＋70%，直击伤害额外乘区＋7%」、
第 6 行「每持续1秒，自身攻击力＋35%、直击伤害＋35%」（数字按行值渲染），其余 5 行只把「风属性共鸣时：」改成
「风属性共鸣时，」（口径 3，见下）；能力3/能力6 面板不动。

面板同条件合并 + 共鸣省略（作者原话「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,
引擎点火提供的效果就不用写火属性共鸣,其他角色类似」；主会话合并规则与扫描 ``panel_merge/scan.json``，按本轮数值重核）：

- 能力4 ``desc_override_black_wolf_knight_moon_4`` 两行（数据 ``1499864`` #0/#1：风共鸣前置、无触发、c1=true、
  无 CT/次数上限/后缀，除效果列外逐格相同）合并为一行
  「风属性共鸣时，自身技能槽＋50%，赋予风属性角色技能充能速度＋10%」（两个对象用「，」分开，原措辞与数值不变；
  原文共鸣写「：」，合并行按规则写「，」）。能力4 词条行只读（核对合并组）。
- 其余覆盖面板不并（见 :data:`NOT_MERGED`）：队长 #0–#2/#5/#6 同条件，但 L7 写「战斗开始时」（一次性充能）、
  L1 是常驻延长，文案条件不同；能力3 #0/#3 同条件但 #3 是技能形态切换（机制行）；其余同条件组已是一行。
- 共鸣省略：149986 没有任何固有状态（队长与能力 1–6 无 461/413/436/459 授予行，技能/629/PF DSL 亦无授予），
  无可省的「X属性共鸣时，」（:data:`PREFIX_DROPS` 为空）。
- 共鸣写法（主会话口径 3「本轮返回的覆盖面板里，所有「X属性共鸣时：」统一成「X属性共鸣时，」；「：」后换行接效果的并成一行」）：
  本模块返回的两块面板（队长、能力4）里的「风属性共鸣时：」一律改「风属性共鸣时，」（:func:`normalize_resonance`），
  其余字面不变；本角色没有「：」后换行的写法。队长 L2/L3 冲刺两行的数据（能力6 #1/#2）带「队长 + 风编成≥6」，
  L4 是 704 开关行（前置 42 + 风编成≥6，口径 2 真实条件）⇒ 共鸣都保留。未返回的能力1/3 覆盖面板不在本轮范围（仍是「：」）。

技能强化只写在队长技 / 能力的强化条目（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,
技能里面不要重复描述强化后的效果,规范并简化描述做了吗」；主会话口径 R1–R4）：

- 技能说明（action_skill 两档 c1、character_text c5/c7、服务端镜像）本来就只写技能本体（「两段均以直接攻击伤害判定」
  是两支共有的本体效果），不改。
- R2 强化条目：``change_skill_black_wolf_knight_moon``（能力3 #3 kind 536，旗号 1，前置 风≥6 共鸣）
  「风属性共鸣时强化技能：威力随连击数提升（按直接攻击伤害判定）」→「强化『月下独奏』：威力随连击数提升」；
  ``change_skill_black_wolf_knight_moon_2``（能力6 #4 kind 704，旗号 2，前置 42 仅队长 + 风≥6 共鸣）
  「担任队长并达成风属性共鸣时强化技能：把赋予的最大速度固定强化到最高档、不衰减技能槽能量获取」→
  「强化『月下独奏』：赋予的最大速度固定效果强化至最高档，且不衰减技能槽能量获取」。条件不写进条目（客户端按前置拼），
  「按直接攻击伤害判定」两支相同（旗号 1 开支只把两段 CreateNormalAttack 的连击加成开关 False→True）⇒ 删去。
- R2 面板：队长第 4 行（描述 704 开关行，数据带风共鸣 ⇒ 保留「风属性共鸣时，」）改成「风属性共鸣时，」+ 同一条目；
  能力3 ``desc_override_black_wolf_knight_moon_3`` 第 3 行把 536（#3）与 629 追击（#4，每 100 连击、CT 5 秒）两条
  不同触发的数据行挤在一句 ⇒ 拆成强化条目行（「风属性共鸣时，」+ 条目）与追击行，两行都带风共鸣前置（数据如此）；
  本块面板本轮起由本模块返回 ⇒ 按口径 3 其余「风属性共鸣时：」一并改「，」（第 1、4 行，只改标点）。

生成器 ``wf_midautumn_kit_rolf``：``BALANCE_C`` / LEADER / PLAN[6] / EXPECT / PANEL_LEADER / PANEL_ABILITY[3] / PANEL_ABILITY[4]
/ CAS_TEXTS（两条强化条目）已同步
（``BALANCE_B`` 保留作第二批历史记录，其中 ``hold_fixed_speed`` 仍在用），测试断言生成器输出 == :func:`revise` 输出。
设计镜像（design/rolf.json 的 rework1.balance_20260927c、rework1/panel/rolf.json 队长两行与能力4）由 :func:`sync_mirrors`
幂等同步（``python mod-tools/wf_balance_20260927c_rolfmoon.py --write`` 落盘）；测试另接受「镜像停在第二批、
按本模块补齐后 == 生成器」这一种过渡态。
本模块只读 ``read()``；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any, Callable

import wf_balance_20260927b_rolfmoon as B2
import wf_midautumn_kitlib as KL

CID = B2.CID                        # "149986"
CODE = B2.CODE                      # "black_wolf_knight_moon"
PACKAGES = ["ma-rolf"]
#: 候选 manifest 现值 1.0.1（第二批回写）→ 递增。
PACKAGE_VERSION = {"ma-rolf": "1.0.2"}
#: 只改强度与面板数字，不需要新能力（候选已声明 dash-parameter-v1 / panel-description-override-v2）。
CAPABILITIES: list[str] = []
#: 候选 ma-rolf 与 live 在本模块读取的键上逐字相同、manifest 零哈希漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}
ELEMENT, ELEMENT_TOKEN, MAIN_ICON = B2.ELEMENT, B2.ELEMENT_TOKEN, B2.MAIN_ICON
ABILITY_NCOLS, LEADER_NCOLS = B2.ABILITY_NCOLS, B2.LEADER_NCOLS

LEADER_KEY = CID
A6_KEY = B2.A6_KEY                  # 1499866
A4_KEY = f"{CID}4"                  # 1499864（面板合并组的数据行，只读）
CAS_LEADER = B2.CAS_LEADER          # desc_override_black_wolf_knight_moon
CAS_A4 = f"{CAS_LEADER}_4"          # desc_override_black_wolf_knight_moon_4

#: live 1.4.1053 只读取数（stage_batch.make_read(live_only=True) 同法）；值 = digest(read(kind, key))。
#: 前三项都 == 第二批 ``wf_balance_20260927b_rolfmoon`` 输出。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "574e11faa10d9bef0661c1fb538a1e7c5bd07bb874b8f4b047856dffd280e5f1",
    ("ability", A6_KEY): "d8de4111aad4168d38bd46434f3e27418798d9e7a068f1462ce41621d2206b14",
    ("cas", CAS_LEADER): "f94cedfde7d9dad8a5eaf433e5564ec5192dc3445cde1d76bd2f16d84b04c0e3",
    # 面板同条件合并（链尾 1.4.1054 只读取数，与 1.4.1053 及候选 ma-rolf 1.0.1 逐字相同）：
    # 能力4 词条行只读（核对合并组数据条件），能力4 覆盖串改写。
    ("ability", A4_KEY): "79bc1047c8c935c522b49a90ec3628f299ef1774cf98c446c17d0b302530f66d",
    ("cas", CAS_A4): "a20c5f4552dafa1d9efc602ebc40f51704a54310bffaf54dcfd3b08b84169f1c",
    # 技能强化文案（链尾 1.4.1054 只读取数，与候选 ma-rolf 1.0.1 逐字相同）：两条强化条目与能力3 面板改写；
    # 能力3 行只读（536 开关行 #3 与 629 追击行 #4 的数据依据）。
    ("cas", f"change_skill_{CODE}"): "94e61ded8c4f68e1f5c3068f6d5f7016a6022ed1b4ca6573de4f24229a7e52e7",
    ("cas", f"change_skill_{CODE}_2"): "3b6f238f409309f17ccec41b198024e09545a38fa501defb514c7e1e6267e8d7",
    ("cas", B2.CAS_A3): "c1120e3cb3dfdfa07193d3b58a1dac260e18d85a9a6f94b4245d837c6a9a6a8e",
    ("ability", B2.A3_KEY): "119d56ffd242ae05d75b040c0f1fc49785972cd6cdd21514bcb813832775667e",
}

# ---------------------------------------------------------------- 数值：(原值, 第二批 live, 本轮, 档位)

LEADER_GROWTH = {
    3: ("100000", B2.DIRECT_GROWTH[1], "80000", (4, 5)),     # 32 风队攻击力
    4: ("100000", B2.DIRECT_GROWTH[1], "70000", (7, 10)),    # 33 风队直击伤害
}
A6_GROWTH = {
    3: ("10000", B2.DIRECT_GROWTH_IC693[1], "7000", (7, 10)),   # 693 风队独立乘区直击（前置 42）
    5: ("50000", B2.KEEP_FRAME_GROWTH[1], "35000", (7, 10)),    # IT 246 自身攻击力（前置 42）
    6: ("50000", B2.KEEP_FRAME_GROWTH[1], "35000", (7, 10)),    # IT 246 自身直击伤害（前置 42）
}
GROWTH_NAMES = {("leader", 3): "每 100 次风队直击 → 风队攻击力", ("leader", 4): "同触发 → 风队直击伤害",
                ("ability", 3): "同触发 → 风队独立乘区直击伤害（693）",
                ("ability", 5): "最大速度固定每持续 1 秒 → 自身攻击力", ("ability", 6): "同触发 → 自身直击伤害"}
#: 能力6 #5/#6 承载行（第二批由原能力3 #1/#2 搬入）对应的原行号。
A6_CARRIER_SOURCE = {5: 1, 6: 2}
A6_ROWS = 7
ROUNDING_STEP_LARGE, ROUNDING_STEP_SMALL = 5000, 500   # 原值 ≥20% 取 5 的倍数；更小取 0.5 的倍数（口径 D2）

# ---------------------------------------------------------------- 面板

#: 第二批写入、live 现有的两行（B2 常量）。
OLD_LEADER_LINE = B2.NEW_LEADER_LINE
OLD_KEEP_FRAME_LINE = B2.NEW_LEADER_KEEP_FRAME_LINE
LEADER_LINE, KEEP_FRAME_LINE_INDEX, LEADER_LINES = 4, 5, 7


def pct(value: str) -> str:
    return f"{int(value) / 1000:g}"


def leader_line(atk: str, direct: str, ic693: str) -> str:
    return (f"风属性共鸣时：风属性角色每造成100次直接攻击，风属性角色攻击力＋{pct(atk)}%、直击伤害＋{pct(direct)}%，"
            f"直击伤害额外乘区＋{pct(ic693)}%")


def keep_frame_line(atk: str, direct: str) -> str:
    return f"最大速度固定效果持续期间，每持续1秒，自身攻击力＋{pct(atk)}%、直击伤害＋{pct(direct)}%"


#: 口径 3（主会话 2026-09-27）：本轮返回的覆盖面板里「X属性共鸣时：」一律写「X属性共鸣时，」；
#: 「X属性共鸣时：」后直接换行接效果的并成一行。只动这一处标点（与换行），其余字面逐字。
RESONANCE_COLON = re.compile(r"([火水雷风光暗](?:或[火水雷风光暗])*属性共鸣时)[：:]\n?")


def normalize_resonance(text: str) -> str:
    return RESONANCE_COLON.sub(r"\1，", text)


if (leader_line(LEADER_GROWTH[3][1], LEADER_GROWTH[4][1], A6_GROWTH[3][1]), keep_frame_line(
        A6_GROWTH[5][1], A6_GROWTH[6][1])) != (OLD_LEADER_LINE, OLD_KEEP_FRAME_LINE):
    raise AssertionError("batch-2 panel lines are not rendered from the batch-2 values")
#: 第三轮数值、未规范化（第二批写法「风属性共鸣时：」）：镜像过渡态与测试里 check 的 orig 用。
NEW_LEADER_LINE_COLON = leader_line(LEADER_GROWTH[3][2], LEADER_GROWTH[4][2], A6_GROWTH[3][2])
NEW_LEADER_LINE = normalize_resonance(NEW_LEADER_LINE_COLON)
NEW_KEEP_FRAME_LINE = keep_frame_line(A6_GROWTH[5][2], A6_GROWTH[6][2])

#: 第二批写入 live 的整段队长面板（7 行；测试核对 == live fixture）。生成器与镜像的过渡态比对用。
B_PANEL_LEADER = "\n".join((
    "风属性共鸣时：全体增益效果的持续时间＋100%（包括贯穿、最大速度固定）",
    "风属性共鸣时：强化自身冲刺，冲刺冷却时间－33%",
    "风属性共鸣时：冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短",
    "风属性共鸣时：自身发动技能时，技能所赋予的最大速度固定效果强化至4档，且不衰减技能槽能量获取",
    OLD_LEADER_LINE,
    OLD_KEEP_FRAME_LINE,
    "风属性共鸣时：战斗开始时，风属性角色技能槽＋50%、技能槽最大值＋10%",
))

# ---------------------------------------------------------------- 技能强化文案（R1–R4）

SKILL_NAME = "月下独奏"                                   # action_skill c0 / character_text c4
A3_KEY, CAS_A3 = B2.A3_KEY, B2.CAS_A3                    # 1499863 / desc_override_black_wolf_knight_moon_3
CAS_FLAG = f"change_skill_{CODE}"                        # 能力3 #3 kind 536（旗号 1）c70
CAS_FLAG2 = f"change_skill_{CODE}_2"                     # 能力6 #4 kind 704（旗号 2）c70
RESONANCE = "风属性共鸣时，"
#: 强化条目 → (词条键, 行号, kind, c1 主位列, 需要的前置 kind)：前置 2 = 风编成≥6（共鸣），42 = 仅队长。
FLAG_ROWS = {CAS_FLAG: (A3_KEY, 3, "536", "false", ("2",)), CAS_FLAG2: (A6_KEY, 4, "704", "true", ("42", "2"))}
FLAG_TEXTS = {
    CAS_FLAG: ("风属性共鸣时强化技能：威力随连击数提升（按直接攻击伤害判定）",
               "强化『月下独奏』：威力随连击数提升"),
    CAS_FLAG2: ("担任队长并达成风属性共鸣时强化技能：把赋予的最大速度固定强化到最高档、不衰减技能槽能量获取",
                "强化『月下独奏』：赋予的最大速度固定效果强化至最高档，且不衰减技能槽能量获取"),
}
FLAG_ENTRY_HEADS = (f"强化『{SKILL_NAME}』", f"为『{SKILL_NAME}』追加")
FLAG_ENTRY_BANNED = ("强化自身技能", "强化技能", "属性共鸣时", "担任队长", "强化后", "自身为队长时")
#: 队长第 4 行（0 基 #3）= 704 开关行（能力6 #4，前置 42 + 风≥6）：口径 3 规范化后的现行文字 → 强化条目写法。
FLAG2_LINE_INDEX = 3
OLD_FLAG2_LINE = "风属性共鸣时，自身发动技能时，技能所赋予的最大速度固定效果强化至4档，且不衰减技能槽能量获取"
NEW_FLAG2_LINE = RESONANCE + FLAG_TEXTS[CAS_FLAG2][1]
#: 能力3 面板（live 4 行，主位槽逐行带图标）。第 3 行 = 536 开关行（#3）+ 629 追击行（#4）挤在一句 ⇒ 拆两行。
OLD_A3_LINES = (
    MAIN_ICON + "风属性共鸣时：风属性角色的直接攻击强化为3次（同类效果不叠加，取最大值），合计伤害额外乘区＋200%",
    B2.NEW_A3_LINE,
    MAIN_ICON + "风属性共鸣时：强化技能，威力随连击数提升（按直接攻击伤害判定），每达成100连击 → "
                "立即对最近的敌人发动自身技能的攻击效果（不消耗技能槽，冷却时间：5秒）",
    MAIN_ICON + "风属性共鸣时：每达成100连击，连击数＋50",
)
A3_SPLIT_LINE = 2
ENCORE_COMBO, ENCORE_CT_SECONDS = 100, 5                 # 629 追击行 #4：trigger 12 × 100000 / CT 300 帧
A3_SPLIT_LINES = (
    MAIN_ICON + RESONANCE + FLAG_TEXTS[CAS_FLAG][1],
    MAIN_ICON + RESONANCE + f"每达成{ENCORE_COMBO}连击，立即对最近的敌人发动自身技能的攻击效果"
                            f"（不消耗技能槽，冷却时间：{ENCORE_CT_SECONDS}秒）",
)
#: 改后 5 行：第 3 行拆两行；本块本轮起由本模块返回 ⇒ 其余行按口径 3 只改共鸣标点。
NEW_A3_LINES = tuple(normalize_resonance(line) for line in OLD_A3_LINES[:A3_SPLIT_LINE]) + A3_SPLIT_LINES \
    + tuple(normalize_resonance(line) for line in OLD_A3_LINES[A3_SPLIT_LINE + 1:])


class RolfMoonGrowthError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


digest = B2.digest


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RolfMoonGrowthError(f"{CID} balance 20260927c: {message}")


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value) if value is not None else None
    if got != BEFORE[(kind, key)]:
        raise RolfMoonGrowthError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def rounded_growth(original: str, factor: tuple[int, int]) -> str:
    """口径取整：原值 × 档位，原值 ≥20% 就近取 5% 的倍数，其余就近取 0.5%；不得低于原值的 2/3。"""
    exact = int(original) * factor[0] / factor[1]
    step = ROUNDING_STEP_LARGE if int(original) >= 20000 else ROUNDING_STEP_SMALL
    value = int(exact / step + 0.5) * step
    if value * 3 < int(original) * 2:
        raise ValueError(f"{original} × {factor} rounds to {value}, below 2/3")
    return str(value)


def _check_table() -> None:
    for table, growth in (("leader", LEADER_GROWTH), ("ability", A6_GROWTH)):
        for index, (original, _live, new, factor) in growth.items():
            if rounded_growth(original, factor) != new:
                raise AssertionError(f"{table}#{index}: {new} is not {original} × {factor} rounded")


# ---------------------------------------------------------------- 行指纹

def leader_cells(index: int, strength: str) -> dict[int, str]:
    return {**B2.LEADER_BEFORE[index], 49: strength, 50: strength}


def a6_cells(index: int, strength: str) -> dict[int, str]:
    if index == B2.A6_IC693_ROW:
        return {**B2.A6_IC693_BEFORE, 51: strength, 52: strength}
    return {**B2.A3_BEFORE[A6_CARRIER_SOURCE[index]], **B2.A6_CARRIER_CHANGES, 51: strength, 52: strength}


def _matches(row: list[str], cells: dict[int, str], ncols: int) -> bool:
    return B2._matches(row, cells, ncols)


# ---------------------------------------------------------------- 词条

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #3/#4 c49/c50 20000 → 80000 / 70000；其余 5 行与两行其余列逐字保留。"""
    _check_table()
    _require(len(rows) == 7 and all(len(r) == LEADER_NCOLS for r in rows),
             f"leader {LEADER_KEY}: expected 7×{LEADER_NCOLS} rows")
    for index, (_original, live, _new, _factor) in LEADER_GROWTH.items():
        _require(_matches(rows[index], leader_cells(index, live), LEADER_NCOLS),
                 f"leader {LEADER_KEY}#{index}: batch-2 direct-growth row drifted")
    out = deepcopy(rows)
    for index, (_original, _live, new, _factor) in LEADER_GROWTH.items():
        out[index][49] = out[index][50] = new
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(LEADER_GROWTH):
        raise AssertionError(f"leader rows touched: {changed}")
    for index, (_original, _live, new, _factor) in LEADER_GROWTH.items():
        if not _matches(out[index], leader_cells(index, new), LEADER_NCOLS):
            raise AssertionError(f"leader #{index} touched more than c49/c50")
    return out


def ability6_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力6 #3（693）2000 → 7000、#5/#6（IT 246 承载）5000 → 35000；#0–#2、#4 逐字保留。"""
    _check_table()
    _require(len(rows) == A6_ROWS and all(len(r) == ABILITY_NCOLS for r in rows),
             f"ability {A6_KEY}: expected {A6_ROWS}×{ABILITY_NCOLS} rows")
    _require(all((r[0], r[1], r[2]) == (f"{CODE}_6", "true", "special") for r in rows),
             f"ability {A6_KEY}: key head drifted")
    for index, (_original, live, _new, _factor) in A6_GROWTH.items():
        _require(_matches(rows[index], a6_cells(index, live), ABILITY_NCOLS),
                 f"ability {A6_KEY}#{index}: batch-2 growth row drifted")
    _require([i for i, r in enumerate(rows) if r[27] == "246"] == [5, 6],
             f"ability {A6_KEY}: trigger-246 carriers moved")
    out = deepcopy(rows)
    for index, (_original, _live, new, _factor) in A6_GROWTH.items():
        out[index][51] = out[index][52] = new
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(A6_GROWTH):
        raise AssertionError(f"ability6 rows touched: {changed}")
    for index, (_original, _live, new, _factor) in A6_GROWTH.items():
        if not _matches(out[index], a6_cells(index, new), ABILITY_NCOLS):
            raise AssertionError(f"ability6 #{index} touched more than c51/c52")
    return out


# ---------------------------------------------------------------- 面板

def leader_text(rows: list[list[str]]) -> list[list[str]]:
    """第 5/6 行换本轮数字，再按口径 3 把整段的「风属性共鸣时：」统一成「，」（行数不变）；
    最后第 4 行（704 开关行）换成「风属性共鸣时，」+ 强化条目（R2）。"""
    _require(rows == [[B_PANEL_LEADER]], f"{CAS_LEADER}: unexpected panel text (expected the batch-2 output)")
    lines = B_PANEL_LEADER.split("\n")
    _require(len(lines) == LEADER_LINES and lines[LEADER_LINE] == OLD_LEADER_LINE
             and lines[KEEP_FRAME_LINE_INDEX] == OLD_KEEP_FRAME_LINE, f"{CAS_LEADER}: layout drifted")
    lines[LEADER_LINE], lines[KEEP_FRAME_LINE_INDEX] = NEW_LEADER_LINE_COLON, NEW_KEEP_FRAME_LINE
    lines = normalize_resonance("\n".join(lines)).split("\n")
    _require(len(lines) == LEADER_LINES, f"{CAS_LEADER}: resonance normalisation changed the line count")
    _require(lines[FLAG2_LINE_INDEX] == OLD_FLAG2_LINE, f"{CAS_LEADER}: line {FLAG2_LINE_INDEX + 1} drifted")
    lines[FLAG2_LINE_INDEX] = NEW_FLAG2_LINE
    return [["\n".join(lines)]]


#: 第三轮数值、第二批写法（「：」）：口径 3 规范化前的整段（测试里 check 的 orig = 它显式规范化后）。
UNNORMALIZED_PANEL_LEADER = "\n".join(NEW_LEADER_LINE_COLON if i == LEADER_LINE
                                      else NEW_KEEP_FRAME_LINE if i == KEEP_FRAME_LINE_INDEX else line
                                      for i, line in enumerate(B_PANEL_LEADER.split("\n")))
#: 第三轮数值、口径 3 规范化后、强化条目改写前（第 4 行仍是旧写法）：镜像过渡态与测试的 check orig 用。
PRE_FLAG_PANEL_LEADER = normalize_resonance(UNNORMALIZED_PANEL_LEADER)
NEW_PANEL_LEADER = leader_text([[B_PANEL_LEADER]])[0][0]


def ability3_text(rows: list[list[str]]) -> list[list[str]]:
    """能力3 面板：第 3 行拆成强化条目行 + 629 追击行，其余行只改共鸣标点（口径 3）；不接受自身输出（fail closed）。"""
    _require(rows == [["\n".join(OLD_A3_LINES)]], f"{CAS_A3}: unexpected panel text (expected the live text)")
    return [["\n".join(NEW_A3_LINES)]]


def flag_text(key: str, rows: list[list[str]]) -> list[list[str]]:
    old, new = FLAG_TEXTS[key]
    _require(rows == [[old]], f"{key}: live text differs from the reviewed text")
    return [[new]]


def _has_precondition(row: list[str], kind: str) -> bool:
    for base in (6, 13, 20):
        if row[base] == kind and (kind != "2" or (row[base + 3], row[base + 5]) == ("600000", ELEMENT_TOKEN)):
            return True
    return False


def flag_basis_problems(a3: list[list[str]], a6: list[list[str]]) -> list[str]:
    """R1/R2 的数据依据：两条强化条目各挂在自己的开关行（536 / 704，c70 = 串）且前置带风≥6 共鸣（704 另有 42 仅队长），
    面板保留的「风属性共鸣时，」与数据相符；能力3 第 3 行拆出的追击行 = #4 的 629（每 100 连击、CT 5 秒、风共鸣）。"""
    problems = []
    rows = {A3_KEY: a3, A6_KEY: a6}
    for key, (ability, index, kind, main, pres) in FLAG_ROWS.items():
        table = rows[ability]
        row = table[index] if index < len(table) else None
        if row is None or len(row) != ABILITY_NCOLS:
            problems.append(f"{ability}#{index}: missing")
            continue
        if (row[47], row[70], row[1]) != (kind, key, main):
            problems.append(f"{ability}#{index}: (c47,c70,c1) {(row[47], row[70], row[1])} != {(kind, key, main)}")
        for pre in pres:
            if not _has_precondition(row, pre):
                problems.append(f"{ability}#{index}: precondition {pre} missing")
        others = [(ability, i) for ability, table in rows.items() for i, r in enumerate(table)
                  if r[70] == key and (ability, i) != (FLAG_ROWS[key][0], index)]
        if others:
            problems.append(f"{key}: also referenced by {others}")
    encore = a3[B2.A3_ENCORE_ROW] if len(a3) > B2.A3_ENCORE_ROW else []
    if not (len(encore) == ABILITY_NCOLS and all(encore[c] == v for c, v in B2.A3_ENCORE_CELLS.items())):
        problems.append(f"{A3_KEY}#{B2.A3_ENCORE_ROW}: the 629 follow-up row drifted")
    elif (int(encore[30]) // 100000, int(encore[35]) // 60) != (ENCORE_COMBO, ENCORE_CT_SECONDS):
        problems.append(f"{A3_KEY}#{B2.A3_ENCORE_ROW}: combo/CT differ from the panel line")
    return problems


def flag_entry_problems(key: str, text: str) -> list[str]:
    """R2：官方格式、点明技能名、定性无数字、不写条件（客户端 / 面板行按前置写）。"""
    problems = [f"{key}: {p}" for p in KL.panel_problems(text, skill_flag=True)]
    if not text.startswith(FLAG_ENTRY_HEADS):
        problems.append(f"{key}: must start with one of {FLAG_ENTRY_HEADS}")
    problems += [f"{key}: banned wording {w!r}" for w in FLAG_ENTRY_BANNED if w in text]
    return problems

# ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

A4_ROWS = 2
#: 同条件的判据：组内各行除「效果列」外逐格相同（前置三块、触发与参数、CT、次数上限、c1 主位、觉醒列、效果后缀列）。
#: 效果列 = c2 分类 + instant 内容块 kind/对象/对象元素/强度（c47–c52）+ during 内容块同位（c109–c114）。
ABILITY_EFFECT_COLUMNS = frozenset({2}) | frozenset(range(47, 53)) | frozenset(range(109, 115))
OLD_A4_LINES = (
    "风属性共鸣时：自身技能槽＋50%",
    "风属性共鸣时：赋予风属性角色技能充能速度＋10%",
)
NEW_A4_LINES = (
    "风属性共鸣时，自身技能槽＋50%，赋予风属性角色技能充能速度＋10%",
)
#: 合并组：面板键 → (词条键, 同条件数据行（0 基）, 被合并的面板行（0 基）, 改前整段行, 改后整段行)。
PANEL_MERGES: dict[str, tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...], tuple[str, ...]]] = {
    CAS_A4: (A4_KEY, (0, 1), (0, 1), OLD_A4_LINES, NEW_A4_LINES),
}
#: 共鸣省略：无（149986 没有固有状态）。键 = 面板键，值 = 可删「X属性共鸣时，」的面板行号（1 起）。
PREFIX_DROPS: dict[str, tuple[int, ...]] = {}
#: 数据同条件但不并的组（扫描 skipped_groups 按本轮数值重核，理由不变）；其余同条件组已是一行。
NOT_MERGED = {
    f"{CAS_LEADER} L1+L7": "队长 #0–#2（L1 常驻延长）与 #5/#6（L7「战斗开始时」一次性充能 + 技能槽最大值）数据同条件，"
                           "文案条件不同 ⇒ 不并",
    f"{CAS_LEADER}_3 L1+L3": "能力3 #0（直击 3 段）与 #3（技能形态切换，机制行 → L3）⇒ 不并",
    "already_one_line": "队长 #3/#4（+能力6 #3）= L5、能力6 #5/#6 = 队长 L6、能力3 #1/#2 = L2、能力1/2/5 无同条件组",
}
RESONANCE_BASIS = ("149986 无固有状态：队长与能力 1–6 没有 461/413/436/459 授予行，技能 / 629 / PF DSL 亦无授予"
                   "（panel_merge/scan.json states=[]）⇒ 无可省的「X属性共鸣时，」")


def merge_condition_problems(rows: list[list[str]], indexes: tuple[int, ...]) -> list[str]:
    """合并组内各行除效果列外必须逐格相同；返回差异（空 = 数据条件完全相同）。"""
    if any(i >= len(rows) for i in indexes):
        return [f"merge group {indexes} out of range ({len(rows)} rows)"]
    first = rows[indexes[0]]
    problems = []
    for index in indexes[1:]:
        row = rows[index]
        diff = [col for col in range(max(len(first), len(row))) if col not in ABILITY_EFFECT_COLUMNS
                and (first[col] if col < len(first) else None) != (row[col] if col < len(row) else None)]
        if diff:
            problems.append(f"rows #{indexes[0]}/#{index} differ outside the effect columns: {diff}")
    return problems


def ability4_rows_problems(rows: list[list[str]]) -> list[str]:
    """能力4 两行：键头 + 合并组数据条件逐格相同。"""
    if len(rows) != A4_ROWS or any(len(r) != ABILITY_NCOLS for r in rows):
        return [f"ability {A4_KEY}: expected {A4_ROWS}×{ABILITY_NCOLS} rows"]
    if any((r[0], r[1]) != (f"{CODE}_4", "true") for r in rows):
        return [f"ability {A4_KEY}: key head drifted"]
    return merge_condition_problems(rows, PANEL_MERGES[CAS_A4][1])


def merged_panel(key: str, rows: list[list[str]]) -> list[list[str]]:
    """同条件合并：改前整段逐字核对，合并行放在组首行位置，其余行逐字保留；不接受自身输出（fail closed）。"""
    _ability, _rows, _lines, old, new = PANEL_MERGES[key]
    _require(rows == [["\n".join(old)]], f"{key}: unexpected panel text (expected the live pre-merge text)")
    return [["\n".join(new)]]


def ability4_text(rows: list[list[str]]) -> list[list[str]]:
    return merged_panel(CAS_A4, rows)


def merge_text_problems(cas: dict[str, list[list[str]]]) -> list[str]:
    """合并行与复核稿逐字相同；本轮返回的每块面板（口径 3）共鸣只写「X属性共鸣时，」、不许「／」。"""
    problems = []
    for key, (_ability, _rows, _lines, _old, new) in PANEL_MERGES.items():
        if cas[key][0][0] != "\n".join(new):
            problems.append(f"{key}: merged panel differs from the reviewed text")
    for key, rows in cas.items():
        text = rows[0][0]
        if "／" in text or re.search(r"属性共鸣时[：:,]", text):
            problems.append(f"{key}: must use 「X属性共鸣时，」 and line breaks")
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    return B2.row_problems(kind, row)


# ---------------------------------------------------------------- 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", LEADER_KEY)
    a6 = _checked(read, "ability", A6_KEY)
    cas_leader = _checked(read, "cas", CAS_LEADER)
    a4 = _checked(read, "ability", A4_KEY)
    cas_a4 = _checked(read, "cas", CAS_A4)
    flag_rows = {key: _checked(read, "cas", key) for key in FLAG_TEXTS}
    cas_a3 = _checked(read, "cas", CAS_A3)
    a3 = _checked(read, "ability", A3_KEY)

    new_leader = leader_rows(leader)
    new_a6 = ability6_rows(a6)
    # 面板同条件合并：先按数据核对组内条件逐格相同，再改写面板（能力4 行只读）。
    found = ability4_rows_problems(a4)
    _require(not found, f"{CAS_A4}: merge group is not one data condition: {found}")
    # 技能强化文案（R1–R4）：先按数据核对两条条目的开关行与追击行，再改条目、队长第 4 行、能力3 面板（能力3 行只读）。
    found = flag_basis_problems(a3, new_a6)
    _require(not found, f"skill-flag basis drifted: {found}")
    cas = {CAS_LEADER: leader_text(cas_leader), CAS_A4: ability4_text(cas_a4), CAS_A3: ability3_text(cas_a3)}
    cas.update({key: flag_text(key, rows) for key, rows in flag_rows.items()})

    problems = [f"leader#{i}: {p}" for i, row in enumerate(new_leader) for p in row_problems("leader_ability", row)]
    problems += [f"{A6_KEY}#{i}: {p}" for i, row in enumerate(new_a6) for p in row_problems("ability", row)]
    problems += B2.panel_problems(cas) + merge_text_problems(cas)
    for key in FLAG_TEXTS:
        problems += flag_entry_problems(key, cas[key][0][0])
    # 面板里的强化条目行 == 「风属性共鸣时，」+ 同一条目（R2：CAS 与面板对应行写法一致）。
    if cas[CAS_LEADER][0][0].split("\n")[FLAG2_LINE_INDEX] != RESONANCE + cas[CAS_FLAG2][0][0]:
        problems.append(f"{CAS_LEADER}: line {FLAG2_LINE_INDEX + 1} is not the {CAS_FLAG2} entry")
    if cas[CAS_A3][0][0].split("\n")[A3_SPLIT_LINE] != MAIN_ICON + RESONANCE + cas[CAS_FLAG][0][0]:
        problems.append(f"{CAS_A3}: line {A3_SPLIT_LINE + 1} is not the {CAS_FLAG} entry")
    if problems:
        raise RolfMoonGrowthError("; ".join(problems))

    total = lambda value, times: f"{int(value) * times / 1000:g}%"   # noqa: E731
    return {
        "ability": {A6_KEY: new_a6}, "leader": {LEADER_KEY: new_leader}, "cas": cas,
        "text": {}, "table": {}, "action": {}, "server_text": {}, "dsl": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_rolfmoon.py",
            "character": f"{CID} {CODE} 罗尔夫「不落幕的安可」（风，中秋；不是 wt26 179999）",
            "spec": "第三轮（成长复核）施工口径 growth_c_spec.md：作者「砍到4/5,或者7/10」「可以砍到2/3」「数值尽量取5的倍数」；"
                    "reeval_full.json table 罗尔夫·中秋 L#3（4/5）、L#4（7/10）、能力6#3（7/10）、能力6#5/#6（7/10）",
            "live_tail": "1.4.1053（第二批 1.4.1051 已放缓/搬行，本角色此后未变）",
            "changes": {
                **{f"leader:{LEADER_KEY}#{i} c49/c50": f"{live}→{new}：{GROWTH_NAMES['leader', i]} +{pct(live)}%→+{pct(new)}%"
                                                      f"（原 {pct(original)}% × {f[0]}/{f[1]}）"
                   for i, (original, live, new, f) in LEADER_GROWTH.items()},
                **{f"ability:{A6_KEY}#{i} c51/c52": f"{live}→{new}：{GROWTH_NAMES['ability', i]} +{pct(live)}%→+{pct(new)}%"
                                                    f"（原 {pct(original)}% × {f[0]}/{f[1]}）"
                   for i, (original, live, new, f) in A6_GROWTH.items()},
                f"cas:{CAS_LEADER} 第5/6行": [[OLD_LEADER_LINE, NEW_LEADER_LINE], [OLD_KEEP_FRAME_LINE, NEW_KEEP_FRAME_LINE]],
                f"cas:{CAS_LEADER} 共鸣写法": "L1–L5、L7「风属性共鸣时：」→「风属性共鸣时，」（口径 3，其余字面不变）",
                f"cas:{CAS_A4} 第1+2行合并": ["\n".join(OLD_A4_LINES), "\n".join(NEW_A4_LINES)],
                **{f"cas:{key}（R2 强化条目）": list(texts) for key, texts in FLAG_TEXTS.items()},
                f"cas:{CAS_LEADER} 第4行（R2，704 开关行）": [OLD_FLAG2_LINE, NEW_FLAG2_LINE],
                f"cas:{CAS_A3}（R2 拆行 + 口径 3）": ["\n".join(OLD_A3_LINES), "\n".join(NEW_A3_LINES)],
            },
            "skill_enhancement_text": {
                "request": "作者「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                           "规范并简化描述做了吗」；主会话口径 R1–R4",
                "flag_rows": {key: f"ability:{ability}#{index} kind {kind}（前置 {'+'.join(pres)}）c70 = {key}"
                              for key, (ability, index, kind, _main, pres) in FLAG_ROWS.items()},
                "entries": "条目不写条件（客户端 / 面板行按前置写「风属性共鸣时，」），点明『月下独奏』，定性无数字；"
                           "「按直接攻击伤害判定」两支相同（旗号 1 开支只把两段 CreateNormalAttack 的连击加成开关 False→True），"
                           "是技能本体（技能说明已写「两段均以直接攻击伤害判定」）⇒ 删去；「4档」改「最高档」",
                "panels": f"{CAS_LEADER} 第4行 = 「风属性共鸣时，」+ {CAS_FLAG2}；{CAS_A3} 第3行拆成「风属性共鸣时，」+ {CAS_FLAG} "
                          f"与 629 追击行（{A3_KEY}#{B2.A3_ENCORE_ROW}：每 {ENCORE_COMBO} 连击、CT {ENCORE_CT_SECONDS} 秒、风共鸣）；"
                          f"{CAS_A3} 本轮起返回 ⇒ 第1、4行「风属性共鸣时：」→「，」（口径 3，只改标点）",
                "skill_description": "action_skill 两档 c1 / character_text c5/c7 / 服务端镜像本来就只写技能本体，不改",
                "kept": "数据行与 DSL 一格不动（R4）",
            },
            "panel_merge": {
                "request": "作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果"
                           "就不用写火属性共鸣,其他角色类似」",
                "rule": "同一面板里数据条件完全相同的行合并（前置/触发/CT/c1/次数上限/后缀列逐格相同）；效果原措辞与数值保留、"
                        "只省略重复对象名；合并行放在组首行位置；共鸣写「X属性共鸣时，」",
                "merged": {CAS_A4: f"能力4 两行 → 一行（{A4_KEY} #0/#1 除效果列外逐格相同：风共鸣前置、无触发、c1=true）"},
                "not_merged": dict(NOT_MERGED),
                "prefix_drops": {},
                "resonance_basis": RESONANCE_BASIS,
                "style": "主会话口径 3：本轮返回的两块面板（队长、能力4）里「风属性共鸣时：」全部改「风属性共鸣时，」"
                         "（normalize_resonance，只动标点）；没有「：」后换行的写法。未返回的能力1/3 覆盖面板不在本轮范围，"
                         "仍写「风属性共鸣时：」",
                "resonance_kept": "队长 L2/L3 冲刺数据（能力6 #1/#2）= 前置 42 队长 + 风编成≥6；L4 = 能力6 #4 的 704 开关行"
                                  "（前置 42 + 风编成≥6，口径 2 真实条件）⇒ 共鸣与数据相符、保留",
                "auto_panels": "无（队长与能力 1–6 均有覆盖文案）",
            },
            "rounding": "原值 ≥20%：100×4/5=80、100×7/10=70、50×7/10=35 本就是 5 的倍数；693 原值 10%：×7/10=7%，"
                        "5 的倍数只剩 5%（0.5，低于 2/3）或 10%（不放缓）⇒ 保留 7%（口径 D2）",
            "live_verified": "live 现值（20/20/2/5/5%）与数值表批二值一致，无需重算",
            "three_minutes": {
                "direct_100_at_20": {"atk": [total("100000", 20), total(LEADER_GROWTH[3][1], 20), total("80000", 20)],
                                     "direct": [total("100000", 20), total(LEADER_GROWTH[4][1], 20), total("70000", 20)],
                                     "ic693": [total("10000", 20), total(A6_GROWTH[3][1], 20), total("7000", 20)]},
                "keep_frame_246_at_90": [total("50000", 90), total(A6_GROWTH[5][1], 90), total("35000", 90)],
                "order": "[原值, 第二批, 本轮]",
                "it246": "246 与 235 同映射 ConditionKeepFrame（InstantAbilityTriggerMasterValueTools.as:718–720/751–753，"
                         "同一 ThresholdConditionKeepFrameCountHandler）⇒ 按反复触发计 3 分钟 70–110 次（静态证据，仍需真机计数）",
            },
            "kept": ["队长 #0–#2、#5–#6；能力6 #0–#2、#4（422×2 / 704）逐字不动",
                     "能力3 #1/#2 持有型 +100%（第二批封顶版，口径 D4）不读不写；629 追击树削韧不动",
                     "不新增前置（口径 D3）：队长两行已带风共鸣；能力6 #3 已有前置 42 + 风共鸣；#5/#6 维持前置 42、无共鸣（与原行一致）"],
            "generator": "wf_midautumn_kit_rolf.py：BALANCE_C（direct_growth_atk / direct_growth_direct / direct_growth_ic693 / "
                         "keep_frame_growth）→ LEADER / PLAN[6]；EXPECT、PANEL_LEADER 与 PANEL_ABILITY[4]（合并行）同步；"
                         "BALANCE_B 留作第二批记录",
            "mirrors": "design/rolf.json rework1.balance_20260927c 与 rework1/panel/rolf.json 队长两行、能力4 合并行由 "
                       "sync_mirrors 同步（`python mod-tools/wf_balance_20260927c_rolfmoon.py --write`）",
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = B2.BATCH
DESIGN_REL, PANEL_REL = B2.DESIGN_REL, B2.PANEL_REL
MIRROR_TAG = "balance_20260927c"
MIRROR_NOTE = ("2026-09-27 平衡第三轮（成长复核，作者「砍到4/5,或者7/10」）：队长「每100次直接攻击」攻击力/直击伤害/额外乘区 "
               "20%/20%/2% → 80%/70%/7%（原 100%/100%/10% 的 4/5、7/10、7/10）；「速度固定每持续1秒」（能力6 前置42 承载）"
               "5% → 35%（原 50% 的 7/10）。面板同条件合并：能力4 两行（风共鸣、无触发，数据条件逐格相同）并为一行。"
               "共鸣写法：队长与能力4 的「风属性共鸣时：」统一为「风属性共鸣时，」（只改标点）。"
               "技能强化文案（作者「技能都强化效果只在队长技或者能力里面按照格式写」）：两条强化条目改官方格式"
               "「强化『月下独奏』：…」（条件不写进条目）；队长第4行（704 开关行）= 「风属性共鸣时，」+ 条目；能力3 第3行"
               "拆成强化条目行与每100连击追击行，能力3 其余共鸣写法统一为「，」。")
FLAG_LINE_NOTE = ("2026-09-27 平衡第三轮技能强化文案（作者「技能都强化效果只在队长技或者能力里面按照格式写」）："
                  "写成「风属性共鸣时，」+ 强化条目（与 change_skill 串同文，官方格式、点明技能名、不写数字）")
SPLIT_LINE_NOTE = ("2026-09-27 平衡第三轮：原第3行把 536 强化开关（能力3 #3）与 629 追击（#4）两条数据行挤在一句，"
                   "拆成两行，两行都带风共鸣前置（数据如此）")
A4_LINE_NOTE = ("2026-09-27 平衡第三轮面板合并（作者「同一个条件的提升能不能写到一起来简化描述」）：原两行"
                "「风属性共鸣时：自身技能槽＋50%」「风属性共鸣时：赋予风属性角色技能充能速度＋10%」数据条件逐格相同"
                "（1499864 #0/#1），合并为一行，原措辞与数值不变")
LINE_NOTES = {
    NEW_LEADER_LINE_COLON: "2026-09-27 平衡第三轮：每步 20%/20%/2% → 80%/70%/7%（原值的 4/5、7/10、7/10）",
    NEW_KEEP_FRAME_LINE: "2026-09-27 平衡第三轮：每步 5% → 35%（原 50% 的 7/10）；数据仍在能力6 前置42 承载行",
}
RESONANCE_NOTE = "2026-09-27 平衡第三轮：共鸣写法统一为「风属性共鸣时，」（只改标点）"


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量把两份设计镜像推进到第三轮（纯函数、幂等；第二批状态或已同步状态都接受）。"""
    import wf_midautumn_kit_rolf as K
    design, panel = deepcopy(design), deepcopy(panel)
    if K.PANEL_LEADER != NEW_PANEL_LEADER:
        raise ValueError("generator PANEL_LEADER is not the batch-3 panel")
    if K.PANEL_ABILITY[4] != "\n".join(NEW_A4_LINES):
        raise ValueError("generator PANEL_ABILITY[4] is not the merged panel")
    if K.PANEL_ABILITY[3] != "\n".join(NEW_A3_LINES):
        raise ValueError("generator PANEL_ABILITY[3] is not the split panel")
    if {key: K.CAS_TEXTS[key] for key in FLAG_TEXTS} != {key: new for key, (_old, new) in FLAG_TEXTS.items()}:
        raise ValueError("generator skill-flag entries differ from the batch-3 texts")
    plan = design["plan_rework1"]
    if (plan["ability_records"], plan["ability_rows_by_slot"]) != (
            K.ABILITY_RECORDS, {str(slot): len(K.PLAN[slot]) for slot in range(1, 7)}):
        raise ValueError("design plan_rework1 row counts differ from the generator")
    design["rework1"][MIRROR_TAG] = dict(
        spec="第三轮（成长复核）：作者「砍到4/5,或者7/10」「可以砍到2/3」「数值尽量取5的倍数」＋ reeval_full.json 罗尔夫·中秋",
        changed=[
            f"队长 L#3 c49/c50 {B2.DIRECT_GROWTH[1]} → {K.BALANCE_C['direct_growth_atk']}（原 100% × 4/5）",
            f"队长 L#4 c49/c50 {B2.DIRECT_GROWTH[1]} → {K.BALANCE_C['direct_growth_direct']}（原 100% × 7/10）",
            f"A6#3 693 c51/c52 {B2.DIRECT_GROWTH_IC693[1]} → {K.BALANCE_C['direct_growth_ic693']}（原 10% × 7/10）",
            f"A6#5/#6 IT 246 c51/c52 {B2.KEEP_FRAME_GROWTH[1]} → {K.BALANCE_C['keep_frame_growth']}（原 50% × 7/10）",
            f"面板同条件合并：{CAS_A4} 两行 → 一行（{A4_KEY} #0/#1 数据条件逐格相同；无固有状态 ⇒ 无共鸣省略）",
            f"共鸣写法：{CAS_LEADER} 与 {CAS_A4} 的「风属性共鸣时：」→「风属性共鸣时，」（主会话口径 3）",
            f"技能强化文案：{CAS_FLAG} / {CAS_FLAG2} 改官方格式「强化『{SKILL_NAME}』：…」（条件不写进条目）；"
            f"{CAS_LEADER} 第4行 = 「风属性共鸣时，」+ {CAS_FLAG2}；{CAS_A3} 第3行拆成强化条目行与追击行、共鸣写「，」",
        ],
        kept=["队长表保持 7 行", "能力3 持有型 +100% 不动（口径 D4）", "629 追击树削韧不动",
              "技能说明（action_skill / character_text）本来就只写技能本体，不改"],
        panel={CAS_LEADER: K.PANEL_LEADER, CAS_A4: K.PANEL_ABILITY[4], CAS_A3: K.PANEL_ABILITY[3],
               **{key: K.CAS_TEXTS[key] for key in FLAG_TEXTS}},
        module="mod-tools/wf_balance_20260927c_rolfmoon.py",
    )

    # 第二批两行 → 第三轮数字（第二批写法），再按口径 3 统一共鸣标点；已同步的行两步都不动（幂等）。
    replacements = {OLD_LEADER_LINE: NEW_LEADER_LINE_COLON, OLD_KEEP_FRAME_LINE: NEW_KEEP_FRAME_LINE}
    lines = []
    for line in panel["leader"]["lines"]:
        if line["text"] in replacements:
            new_text = replacements[line["text"]]
            note = line.get("note", "")
            line = dict(line, text=new_text, status="changed",
                        note=(note + "；" if note else "") + LINE_NOTES[new_text])
        normalized = normalize_resonance(line["text"])
        if normalized != line["text"]:
            note = line.get("note", "")
            status = line.get("status", "changed")
            joiner = "" if not note or note.endswith(("。", "；")) else "；"
            line = dict(line, text=normalized, status="changed" if status == "same" else status,
                        note=note + joiner + RESONANCE_NOTE)
        if line["text"] == OLD_FLAG2_LINE:                     # 704 开关行 → 「风属性共鸣时，」+ 强化条目
            note = line.get("note", "")
            joiner = "" if not note or note.endswith(("。", "；")) else "；"
            line = dict(line, text=NEW_FLAG2_LINE, status="changed", note=note + joiner + FLAG_LINE_NOTE)
        lines.append(line)
    panel["leader"]["lines"] = lines
    if "\n".join(line["text"] for line in panel["leader"]["lines"]) != K.PANEL_LEADER:
        raise ValueError("leader panel mirror still differs from the generator")

    three = [entry for entry in panel["abilities"] if int(entry["index"]) == 3]
    if len(three) != 1:
        raise ValueError("panel mirror ability 3 layout drifted")
    strip = lambda line: line[len(MAIN_ICON):]                   # noqa: E731   镜像行不带主位图标
    texts = tuple(line["text"] for line in three[0]["lines"])
    if texts == tuple(strip(line) for line in OLD_A3_LINES):
        old = three[0]["lines"]
        new_texts = [strip(line) for line in NEW_A3_LINES]

        def noted(entry, text, extra):
            note = entry.get("note", "")
            joiner = "" if not note or note.endswith(("。", "；")) else "；"
            return dict(entry, text=text, status="changed", note=note + joiner + extra)

        split = old[A3_SPLIT_LINE]
        three[0]["lines"] = (
            [noted(entry, text, RESONANCE_NOTE) if entry["text"] != text else entry
             for entry, text in zip(old[:A3_SPLIT_LINE], new_texts[:A3_SPLIT_LINE])]
            + [{"text": new_texts[A3_SPLIT_LINE], "status": "changed", "note": FLAG_LINE_NOTE + "；" + SPLIT_LINE_NOTE},
               noted(split, new_texts[A3_SPLIT_LINE + 1], SPLIT_LINE_NOTE)]
            + [noted(entry, text, RESONANCE_NOTE) if entry["text"] != text else entry
               for entry, text in zip(old[A3_SPLIT_LINE + 1:], new_texts[A3_SPLIT_LINE + 2:])])
    elif texts != tuple(strip(line) for line in NEW_A3_LINES):
        raise ValueError(f"panel mirror ability 3 is neither the live nor the split text: {texts}")
    if "\n".join(MAIN_ICON + line["text"] for line in three[0]["lines"]) != K.PANEL_ABILITY[3]:
        raise ValueError("ability 3 panel mirror still differs from the generator")

    four = [entry for entry in panel["abilities"] if int(entry["index"]) == 4]
    if len(four) != 1:
        raise ValueError("panel mirror ability 4 layout drifted")
    texts = tuple(line["text"] for line in four[0]["lines"])
    if texts == OLD_A4_LINES:
        four[0]["lines"] = [{"text": NEW_A4_LINES[0], "status": "changed", "note": A4_LINE_NOTE}]
    elif texts != NEW_A4_LINES:
        raise ValueError(f"panel mirror ability 4 is neither the pre-merge nor the merged text: {texts}")
    if "\n".join(line["text"] for line in four[0]["lines"]) != K.PANEL_ABILITY[4]:
        raise ValueError("ability 4 panel mirror still differs from the generator")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27 平衡第三轮")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    paths = tuple(root / rel for rel in rels)
    before = [B2._load(path) for path in paths]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for path, old, new in zip(paths, before, after):
            if old != new:
                B2._save(path, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))
