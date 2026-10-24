# -*- coding: utf-8 -*-
"""特克托 139993 ``super_robot_tailcoat``：2026-09-27 作者平衡**第三批**（成长复核 + 技能倍率撤封顶 U4）。

口径 = 主会话 ``growth_c_spec.md``（作者原话 1–6 逐字转述；默认选择 D1–D4 / U1–U9），
数值表与撤封顶设计 = ``reeval_full.json`` 的 ``table.rows``（特克托 6 行）与 ``design.characters``（特克托）。
输入 = **当前 live**（本地链尾 1.4.1053；特克托这 12 项与第二批 ``wf_balance_20260927b_tekuto`` 的输出逐字相同，
与候选 s7-tekuto 1.0.9 也逐字相同）。

一、成长复核（作者：「砍到4/5，或者7/10这样吧」「可以砍到2/3」「数值尽量取5的倍数」；第二批的 1/10 作废）：
  档位按「靠成长的程度 × 触发难度」定（表 ``suggested_factor``），取整按表 summary：
  原值 ≥20% 就近取 5 的倍数；原值 ≤10% 按 0.5 取；2/3 档一律向上取、不得跌出下限（D2）。
  队长 #0 引擎每层 雷队攻击力        原 100% / 批二 10%  → 80%（4/5；全队伤害只能靠这条）
  队长 #1 引擎每层 雷队技能伤害      原 200% / 批二 20%  → 160%（4/5）
  队长 #2 引擎每层 自身独立乘区技伤  原 5%   / 批二 0.5% → 3.5%（2/3：3.33 向上取 0.5 档）
  队长 #8 半血持重炮 每 120 帧 技伤  原 100% / 批二 10%  → 70%（7/10：依赖低血，次数中等）
  队长 #10/#11 引擎每层 自身攻/技伤  原 50%  / 批二 5%   → 35%（2/3：33.3 向上取 5 档）
  其余队长行（#3–#7、#9：充能/技能槽上限/层数来源）逐字不动（D3：只改表里列出的行的数值，不新增共鸣前置）；
  能力2 的封顶版（16%/15%×10）保持第二批（D4）。

二、技能倍率撤封顶（U4 / U6 / U7 / U8，「当队长且共鸣时不封顶，其他情况保留第二批封顶」）：
  旗号 1（能力1#1 kind 536，主位＋雷共鸣）、旗号 2（能力3#1 kind 704，雷共鸣）都不是队长门控且已占用 ⇒ 用旗号 3。
  1. 开关行（U6）：能力 ``1399931`` 末尾追加一行 kind **705**（InstantAbilitySource 704–708 → 旗号 2–6），
     瞬发无触发，前置 42（仅队长）＋ 2 元素编成（雷≥6），c70 = 新 CAS ``change_skill_super_robot_tailcoat_leader``。
     与该键第 1 行（536 开关）逐格同形，只换 c6 202→42、c47 536→705、c70；与 live 罗尔夫中秋 1499866#4
     （704＋前置 42＋共鸣）同形。零先例的「队长表 705 行」不做。
  2. 技能 DSL（两档各 11 处）：每个 ``BindConditionAccumulationVariable(-17, 1, [DCUnique 13999301], 1, 10)``
     都在所在 Block 的第 0 句，整段（Bind 起到块尾：2–4 句）换成
     ``ConditionalsChangeSkillFlag(3, Block[同段，Bind 上限 99(int)], Block[live 原段])``：
     开支只有 Bind[5] 一处不同（第二批前原值 int 99，= 固有「引擎启动」c4 叠层上限 99），第二批的激光削韧 0.3
     随整段保留；关支与 live 逐字相同（U7：非队长/不共鸣仍封顶 10 层）。分支在局部环境执行
     （ActionEvaluator case 86），Bind 与读它的判定区在同一分支内 ⇒ :func:`vid_scope_problems` 机械检查。
     根部旗号 2 护盾分支、alv/alv2 数值项、事件名一概不动。
  3. 文案（U8）：新 CAS「强化『多重爆破·礼装重炮』：威力随「引擎启动」层数持续提升」（技能强化条目按官方格式点名技能，
     不写数字/共鸣前缀）。特克托没有 desc_override，这条由客户端自动显示在能力 1 面板并拼上开关行前置（仅队长＋雷共鸣，
     作者已接受），不新写覆盖文案。
     技能说明 5 处（action_skill 两档 c1、character_text c5/c7、服务端 cdndata/character_text.json [5]/[7]）**不改**，
     保持第二批「（最多10层）」：主会话 2026-09-27 技能强化文案口径（作者「技能都强化效果只在队长技或者能力里面按照格式
     写就行,技能里面不要重复描述强化后的效果」）——技能说明只写技能本体（关支上限 10 层照写），强化后的不封顶只由上面的
     CAS 强化条目描述。:func:`revise_texts` 仍逐处核对第二批原文，但结果与 live 相同 ⇒ revise() 不返回这三类键。

生成器 ``wf_seasonal7_kit_tekuto``：``_DESC_BALANCE_C``（= 第二批 ``_DESC_BALANCE_B``）、``CHANGE_SKILL_LEADER_KEY``、第七轮 ``apply_balance_c``
（叠在 apply_balance_b 之后）与 ``balance_c_skill_tree``（叠在 final_tree 之后）已同步；
测试断言生成器输出 == :func:`revise` 输出。本模块只读 ``read()`` 给的 live 值并返回新值；
不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl

CID = "139993"
CODE = "super_robot_tailcoat"
PACKAGES = ["s7-tekuto"]
#: 候选 manifest 现值 1.0.9（第二批回写）⇒ 下一号。
PACKAGE_VERSION = {"s7-tekuto": "1.0.10"}
CAPABILITIES: list[str] = []
#: 候选 s7-tekuto 与 live 在本模块读取的各项逐字相同（2026-09-27 只读核对），无已审漂移。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                          # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
LEADER_KEY = CID
ABILITY_KEYS = tuple(f"{CID}{slot}" for slot in range(1, 7))
ABILITY1_KEY = ABILITY_KEYS[0]
UID_ENGINE = "13999301"
UID_CANNON = "13999302"
UNIQUE = "master/character/unique_condition.orderedmap"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
LEADER_CAS_KEY = f"change_skill_{CODE}_leader"

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数，与候选 s7-tekuto 1.0.9 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER_KEY): "18ac77db984db0849698a94112312044342369214e735d5ed9da0de6a21ef904",
    ("ability", f"{CID}1"): "dd4aaa0386ed4a0ac53814dd65c0b258024e4728f7b00f1a20e897968ab72368",
    ("ability", f"{CID}2"): "1fe563a3aa4837fd365db57c320faa4e0776cc33595967721dd55c264f55fe24",
    ("ability", f"{CID}3"): "5fcfef68d329afe5271bf32256db0a2fe3ee68b5c26f4541c8e8eea5a0bc832e",
    ("ability", f"{CID}4"): "57840b67ff46f4ecfe486a9834fc747b6adc68bfecd24525d87f3d519ae2ba0b",
    ("ability", f"{CID}5"): "95273771ed9aba6173fa77351789e5aafb3953f4a0c401a5785d1b800aba76fd",
    ("ability", f"{CID}6"): "25011fe4134159935005c198238d9360cb8a2b56fd3eb7973a9eb3a3b06b25f7",
    ("table", (UNIQUE, UID_ENGINE)): "73de72d8aaf98458c82450119dcbf5dace3a79a5e105d7275e48f09cc61766f8",
    ("dsl", PROGRAMS["1"]): "32227f801644158db857adca14409000a570955fa0d33a1abe5f6fe4ff6145d8",
    ("dsl", PROGRAMS["2"]): "8fb60919202854cdaa51fa4f55a9f8afaa2c032ab0182ab1f64bfe2a49f5346a",
    ("action", CODE): "997888dbc55b9c27c48ae9afff44644eb4ea79cf18f27a9e47c31a99ed9cdb05",
    ("text", CID): "7708ac8522fc85148e5dec76ddac9daafe11a1764fbe658881b4c913a4f3d974",
    ("server_text", CID): "7708ac8522fc85148e5dec76ddac9daafe11a1764fbe658881b4c913a4f3d974",
}
#: 本批新增、live 里必须还不存在的键（存在 ⇒ 已写过或有人占用 ⇒ 拒绝）。
NEW_KEYS = (("cas", LEADER_CAS_KEY),)

# ------------------------------------------------------------------ 队长（成长复核）

#: 队长 #0–#4 共用的 during-134 块（雷共鸣前置 + 「引擎启动」层数门，无上限）。
_ENGINE_DURING = {
    0: CODE, 1: "0", 3: "1", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN, 11: "0", 18: "0",
    83: "(None)", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)", 102: UID_ENGINE,
    106: "false",
}
#: 第二批从能力2 搬进队长的两行（自身、无前置，during 134 按「引擎启动」层数）。
_SELF_DURING = {
    0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
    98: "100000", 99: "100000", 100: "(None)", 102: UID_ENGINE, 106: "false", 108: "0",
}
#: 半血持重炮的时间跳：雷共鸣 + 188 持重炮 + 9 HP≤50% + trigger 77 每 12000000/100000=120 帧。
_TIMER = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
    11: "188", 12: "0", 14: "100000", 15: "100000", 17: UID_CANNON, 18: "9", 19: "0",
    21: "50000", 22: "50000", 25: "77", 28: "12000000", 29: "12000000", 32: "(None)", 33: "0",
    37: "(None)", 44: "0", 45: "34", 46: "0",
}
#: 改动的队长行：行号 → (live 逐格指纹（全部非空列）, 强度列, 原值（第二批前）, 批二值（live）, 档位, 新值, 说明)。
LEADER_EDITS: dict[int, tuple[dict[int, str], tuple[int, int], str, str, tuple[int, int], str, str]] = {
    0: ({**_ENGINE_DURING, 107: "0", 108: "5", 109: ELEMENT_TOKEN, 111: "10000", 112: "10000"},
        (111, 112), "100000", "10000", (4, 5), "80000", "引擎每层 雷队攻击力"),
    1: ({**_ENGINE_DURING, 107: "2", 108: "5", 109: ELEMENT_TOKEN, 111: "20000", 112: "20000"},
        (111, 112), "200000", "20000", (4, 5), "160000", "引擎每层 雷队技能伤害"),
    2: ({**_ENGINE_DURING, 107: "411", 108: "0", 111: "500", 112: "500"},
        (111, 112), "5000", "500", (2, 3), "3500", "引擎每层 自身独立乘区技能伤害"),
    8: ({**_TIMER, 49: "10000", 50: "10000"},
        (49, 50), "100000", "10000", (7, 10), "70000", "雷共鸣＋持重炮＋HP≤50%：每 120 帧 自身技能伤害"),
    10: ({**_SELF_DURING, 107: "0", 111: "5000", 112: "5000"},
         (111, 112), "50000", "5000", (2, 3), "35000", "引擎每层 自身攻击力（第二批自能力2 搬入）"),
    11: ({**_SELF_DURING, 107: "2", 111: "5000", 112: "5000"},
         (111, 112), "50000", "5000", (2, 3), "35000", "引擎每层 自身技能伤害（第二批自能力2 搬入）"),
}
_CANNON_DURING = {**_ENGINE_DURING, 95: "194", 100: "1", 102: UID_CANNON, 108: "1", 109: ELEMENT_TOKEN,
                  111: "50000", 112: "50000"}
_INSTANT = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN, 18: "0",
            37: "(None)", 44: "0"}
#: 原样保留的队长行：行号 → (live 逐格指纹, 说明)（D3：表里没列的行一格不动）。
LEADER_KEPT: dict[int, tuple[dict[int, str], str]] = {
    3: ({**_ENGINE_DURING, 107: "3", 108: "0", 111: "5000", 112: "5000"},
        "引擎每层 自身技能槽充能 5%（during 3）"),
    4: ({**_ENGINE_DURING, 107: "124", 108: "0", 111: "5000", 112: "5000"},
        "引擎每层 自身技能槽上限 5%（during 124）"),
    5: ({**_CANNON_DURING, 107: "3"}, "持重炮 → 除自身雷队 充能 50%（194 限 1）"),
    6: ({**_CANNON_DURING, 107: "124"}, "持重炮 → 除自身雷队 技能槽上限 50%（194 限 1）"),
    7: ({**_INSTANT, 11: "0", 25: "0", 45: "35", 46: "5", 47: ELEMENT_TOKEN, 49: "25000", 50: "25000"},
        "雷队 技能槽充能 25%"),
    9: ({**_INSTANT, 11: "9", 12: "0", 14: "50000", 15: "50000", 25: "23", 26: "0", 28: "100000",
         29: "100000", 32: "(None)", 33: "0", 45: "461", 46: "0", 49: "100000", 50: "100000",
         57: "100000", 58: "100000", 66: UID_ENGINE, 72: "2", 73: "0"},
        "HP≤50% 自身技能 → 引擎 +2（只提供层数）"),
}
LEADER_ROWS = 12
TIER_NAMES = {(4, 5): "4/5", (7, 10): "7/10", (2, 3): "2/3"}


def tier_value(original: int, tier: tuple[int, int]) -> int:
    """表 summary 的取整规则：原值 ≥20% 取 5% 的倍数，原值 ≤10% 取 0.5% 的倍数；2/3 档一律向上取，其余就近。"""
    num, den = tier
    if original >= 20000:
        step = 5000
    elif original <= 10000:
        step = 500
    else:
        raise ValueError(f"no rounding step for original {original}")
    units = original * num / den / step
    return step * (math.ceil(units) if tier == (2, 3) else math.floor(units + 0.5))


# ------------------------------------------------------------------ 能力1（旗号 3 开关行）

_AB1_HEAD = {0: f"{CODE}_1", 1: "true", 2: "action_skill", 3: "0", 5: "0", 13: "0", 20: "0"}
#: 能力1 live 两行：#0 技能槽 50%（211）、#1 旗号 1 开关（536，前置 202 主位 + 雷≥6）。
ABILITY1_BEFORE = (
    {**_AB1_HEAD, 6: "0", 27: "0", 39: "(None)", 46: "0", 47: "211", 48: "0", 51: "50000", 52: "50000"},
    {**_AB1_HEAD, 6: "202", 13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN, 27: "0",
     39: "(None)", 46: "0", 47: "536", 70: f"change_skill_{CODE}"},
)
SWITCH_KIND = "705"                  # ability c47：切换技能旗号 3
LEADER_ONLY_PRECONDITION = "42"      # c6 前置 1 kind 42 = 仅队长
#: 追加的旗号 3 开关行（126 列，其余格留空）：瞬发无触发，前置 42 仅队长 + 2 元素编成 雷≥6。
SWITCH_ROW_CELLS = {**_AB1_HEAD, 6: LEADER_ONLY_PRECONDITION, 13: "2", 16: "600000", 17: "600000",
                    18: ELEMENT_TOKEN, 27: "0", 39: "(None)", 46: "0", 47: SWITCH_KIND, 70: LEADER_CAS_KEY}
#: 能力行里「切换技能旗号」的 kind → 旗号号（InstantAbilitySource.as:5015-5018、5880-5903）。
FLAG_KINDS = {"536": 1, "704": 2, "705": 3, "706": 4, "707": 5, "708": 6}

# ------------------------------------------------------------------ 技能 DSL（旗号 3 分支）

LEADER_FLAG = 3
FLAG_COMMAND = "ConditionalsChangeSkillFlag"
VID_ENGINE = 1
BIND_CAPPED = ["BindConditionAccumulationVariable", -17, VID_ENGINE, ["DCUnique", int(UID_ENGINE)], 1, 10]
BIND_UNCAPPED_CAP = 99               # 第二批前原值（int，逐字含类型）= 固有「引擎启动」c4 叠层上限
BIND_UNCAPPED = BIND_CAPPED[:5] + [BIND_UNCAPPED_CAP]
UNIQUE_ENGINE_MAX_COL = 4
#: 11 处 Bind 所在 Block 的路径（Block 节点本身；两档相同）与该段的语句形状。
SEGMENTS: tuple[tuple[tuple[int, ...], tuple[str, ...]], ...] = (
    ((11, 1, 6, 1, 6, 1, 2, 1, 3, 1, 0, 1, 23, 1, 4, 1, 3, 1, 0, 1, 11, 1, 1, 1, 3),
     ("Bind", "CreateHitArea")),                                                        # 导弹落点
    ((11, 1, 6, 1, 6, 1, 6, 1, 3), ("Bind", "CreateHitArea")),                          # 第 1 段 S
    ((11, 1, 6, 1, 6, 1, 7, 1, 3), ("Bind", "ShowEffect:charge_core", "CreateHitArea")),  # 第 2 段 L
    ((11, 1, 6, 1, 6, 1, 8, 1, 3), ("Bind", "ShowEffect:charge_core", "CreateHitArea")),  # 第 3 段 LL
    ((11, 1, 6, 1, 6, 1, 9, 1, 3),
     ("Bind", "ShowEffect:charge_core", "ShowEffect:tekuto_beam_lll", "CreateHitArea")),  # 第 4 段 LLL
    ((11, 1, 6, 1, 6, 1, 10, 1, 3), ("Bind", "CreateHitArea")),                         # 终幕
    *(((11, 1, 6, 1, 6, 1, slot, 1, 3, 1, 0, 1, 3), ("Bind", "CreateHitArea"))           # 延长槽 ×5（重炮门 then 支）
      for slot in (13, 14, 15, 16, 17)),
)
#: 根语句（第二批/low_hp 之后）：最后一句是旗号 2 护盾分支，本批不动。
ROOT_STATEMENTS = ("RemoveEventFromOwner", "HideEffectFromOwner", "HideEffectFromOwner", "CreateCondition",
                   "CreateCondition", "CreateCondition", "FindNearSubjects", FLAG_COMMAND)
SHIELD_BRANCH = ["Command", [FLAG_COMMAND, 2,
                             ["Command", ["CreateBarrier", -17, [{"min": 0.15, "max": 0.15}],
                                          ["GenericBarrierHitEffect"]]],
                             ["Block", []]]]

# ------------------------------------------------------------------ 文案

OLD_DESC = ("锁定周围的敌人，架起跟随自身移动的重炮，朝锁定方向发射逐段变粗的充能激光；"
            "发动时「引擎启动」+1，威力随其层数提升（最多10层）；再次发动会以新的一发替换当前激光；"
            "释放技能后不再进入硬直，可立即行动")
#: 技能本体（关支 Bind 10）上限照写；强化后的不封顶不进技能说明（主会话 2026-09-27 口径 R3）⇒ 本轮说明 == 第二批原文。
DESC_CAP = "（最多10层）"
if OLD_DESC.count(DESC_CAP) != 1:
    raise RuntimeError("batch-2 tekuto description no longer carries exactly one layer-cap clause")
NEW_DESC = OLD_DESC
#: 技能说明里不得出现的强化后描述（口径 R3）。
ENHANCED_DESC_MARKS = ("不受此限", "担任队长", "强化后")
TEXT_DESC_COLUMNS = (5, 7)           # character_text 觉醒前 / 觉醒后技能说明
#: 技能强化条目（口径 R2）：官方格式「强化『<技能名>』：<定性说明>」，技能名 = action_skill 第 1 档 c0（revise() 核对）。
SKILL_NAME = "多重爆破·礼装重炮"
CAS_TEXT = f"强化『{SKILL_NAME}』：威力随「引擎启动」层数持续提升"


class TekutoBalanceCError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _row(cells: dict[int, str], width: int) -> list[str]:
    row = [""] * width
    for col, value in cells.items():
        row[col] = value
    return row


# ------------------------------------------------------------------ 词条

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #0/#1/#2/#8/#10/#11 换成第三批档位值；其余 6 行逐字保留。"""
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise TekutoBalanceCError(f"leader {LEADER_KEY}: expected {LEADER_ROWS}×{LEADER_NCOLS}")
    if set(LEADER_EDITS) | set(LEADER_KEPT) != set(range(LEADER_ROWS)):
        raise AssertionError("LEADER_EDITS/LEADER_KEPT must cover every leader row")
    for index, (cells, _what) in LEADER_KEPT.items():
        if not _matches(rows[index], LEADER_NCOLS, cells):
            raise TekutoBalanceCError(f"leader {LEADER_KEY}#{index}: kept row drifted ({_what})")
    out = deepcopy(rows)
    for index, (cells, cols, original, _batch2, tier, new, _what) in LEADER_EDITS.items():
        if not _matches(out[index], LEADER_NCOLS, cells):
            raise TekutoBalanceCError(f"leader {LEADER_KEY}#{index}: not the reviewed batch-2 growth row")
        if int(new) != tier_value(int(original), tier):
            raise AssertionError(f"leader#{index}: {new} is not {TIER_NAMES[tier]} of {original}")
        for col in cols:
            out[index][col] = new
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(LEADER_EDITS):
        raise AssertionError(f"leader_rows touched {changed}")
    return out


def switch_row() -> list[str]:
    return _row(SWITCH_ROW_CELLS, ABILITY_NCOLS)


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力1：两行逐字保留，末尾追加旗号 3 开关行（705，前置 42 仅队长 + 雷≥6）。"""
    if len(rows) != len(ABILITY1_BEFORE) or not all(
            _matches(r, ABILITY_NCOLS, c) for r, c in zip(rows, ABILITY1_BEFORE)):
        raise TekutoBalanceCError(f"ability {ABILITY1_KEY}: rows are not the reviewed 211/536 rows")
    out = deepcopy(rows) + [switch_row()]
    twin = list(rows[1])
    twin[6], twin[47], twin[70] = LEADER_ONLY_PRECONDITION, SWITCH_KIND, LEADER_CAS_KEY
    if out[-1] != twin:
        raise AssertionError("switch row must be the 536 row with only c6/c47/c70 replaced")
    return out


def flag_occupancy(abilities: dict[str, list[list[str]]], leader: list[list[str]]) -> dict[int, list[str]]:
    """{旗号号: [占用它的行]}：能力表 c47、队长表 c45 的切换技能旗号 kind。"""
    found: dict[int, list[str]] = {}
    for key, rows in abilities.items():
        for i, row in enumerate(rows):
            if row[47] in FLAG_KINDS:
                found.setdefault(FLAG_KINDS[row[47]], []).append(f"ability:{key}#{i}")
    for i, row in enumerate(leader):
        if row[45] in FLAG_KINDS:
            found.setdefault(FLAG_KINDS[row[45]], []).append(f"leader:{LEADER_KEY}#{i}")
    return found


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, {LEADER_CAS_KEY}, kind=kind)
            + L.ability_element_column_problems(kind, row, ELEMENT))


# ------------------------------------------------------------------ 技能 DSL

def _tag(node) -> Any:
    return node[0] if isinstance(node, list) and node else None


def _is_command(node, name: str | None = None) -> bool:
    return (isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list)
            and bool(node[1]) and (name is None or node[1][0] == name))


def _at(tree, path: tuple[int, ...]):
    node = tree
    for index in path:
        node = node[index]
    return node


def _shape(statement) -> str:
    if not _is_command(statement):
        return repr(_tag(statement))
    command = statement[1]
    if command[0] == "BindConditionAccumulationVariable":
        return "Bind"
    if command[0] == "ShowEffect":
        return f"ShowEffect:{command[1]}"
    return command[0]


def bind_blocks(tree) -> list[tuple[tuple[int, ...], int]]:
    """所有含 Bind 的 Block：[(Block 节点路径, Bind 在语句表里的下标)]。"""
    out: list[tuple[tuple[int, ...], int]] = []

    def walk(node, path):
        if not isinstance(node, list):
            return
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            for i, statement in enumerate(node[1]):
                if _is_command(statement, "BindConditionAccumulationVariable"):
                    out.append((path, i))
        for i, child in enumerate(node):
            walk(child, path + (i,))

    walk(tree, ())
    return out


def flag_branches(tree, flag: int | None = None) -> list[list]:
    """树里所有 ConditionalsChangeSkillFlag 命令（可按旗号号过滤）。"""
    out = []

    def walk(node):
        if isinstance(node, list):
            if _is_command(node, FLAG_COMMAND) and (flag is None or node[1][1] == flag):
                out.append(node[1])
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(tree)
    return out


def vid_scope_problems(tree) -> list[str]:
    """数值项 vlv 读的变量号必须在词法上已被 Bind（同一 Block 里排在前面，或在外层 Block 里）。

    客户端：Bind 写当前环境（ActionEvaluator.as:4877-4887），ConditionalsChangeSkillFlag 的分支在新的局部环境执行
    （ActionEvaluator.as:4509-4526），局部环境只向外层查找 ⇒ 分支里的 Bind 分支外看不到。
    四道 wf_client_legality 门禁只查主体 lookup，不查 vlv 变量号（复核 minor），这里补上。
    """
    problems: list[str] = []

    def walk(node, visible: frozenset, path: str):
        if isinstance(node, dict):
            for term in node.get("vlv", []) if isinstance(node.get("vlv"), list) else []:
                if term.get("vid") not in visible:
                    problems.append(f"{path}: vlv vid {term.get('vid')} is not bound in scope")
            for key, child in node.items():
                walk(child, visible, f"{path}.{key}")
            return
        if not isinstance(node, list):
            return
        if len(node) == 2 and node[0] == "Block" and isinstance(node[1], list):
            bound = set(visible)
            for i, statement in enumerate(node[1]):
                walk(statement, frozenset(bound), f"{path}[1][{i}]")
                if _is_command(statement, "BindConditionAccumulationVariable"):
                    bound.add(statement[1][2])
            return
        for i, child in enumerate(node):
            walk(child, visible, f"{path}[{i}]")

    walk(tree, frozenset(), "$")
    return problems


_BINDING_SLOTS = {"FindAllSubjects": (1,), "FindNearSubjects": (5,), "CreateReferencePoint": (10,),
                  "CreateHitArea": (19, 21, 22)}


def path_bound_ids(node) -> Counter:
    """一条执行路径上最多会出现的主体绑定号计数：旗号分支两侧互斥 ⇒ 取两侧计数的并（|）而不是和。"""
    found: Counter = Counter()
    if isinstance(node, dict):
        for child in node.values():
            found += path_bound_ids(child)
        return found
    if not isinstance(node, list):
        return found
    if _is_command(node, FLAG_COMMAND):
        return path_bound_ids(node[1][2]) | path_bound_ids(node[1][3])
    if _is_command(node):
        command = node[1]
        for slot in _BINDING_SLOTS.get(command[0], ()):
            found[command[slot]] += 1
        for child in command[1:]:
            found += path_bound_ids(child)
        return found
    for child in node:
        found += path_bound_ids(child)
    return found


def dup_bound_ids(tree) -> list[int]:
    """按分支判断的「绑定号唯一」：同一执行路径上重复的绑定号（两侧各一份不算重复）。"""
    return sorted(i for i, n in path_bound_ids(tree).items() if n > 1)


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """11 处「Bind 起到块尾」整段 → ConditionalsChangeSkillFlag(3, 开支 Bind 上限 99, 关支 live 原段)。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise TekutoBalanceCError(f"skill {level}: unexpected root")
    root = out[11][1]
    if tuple(_shape(s) for s in root) != ROOT_STATEMENTS or root[-1] != SHIELD_BRANCH:
        raise TekutoBalanceCError(f"skill {level}: root statements drifted {[ _shape(s) for s in root]}")
    if [c[1] for c in flag_branches(out)] != [2]:
        raise TekutoBalanceCError(f"skill {level}: flag branches {[c[1] for c in flag_branches(out)]} != [2]")
    found = bind_blocks(out)
    if [(path, i) for path, i in found] != [(path, 0) for path, _shape_ in SEGMENTS]:
        raise TekutoBalanceCError(f"skill {level}: bind blocks {found} are not the reviewed 11 segments")
    facts = []
    for path, shape in SEGMENTS:
        block = _at(out, path)
        items = block[1]
        if tuple(_shape(s) for s in items) != shape or items[0] != ["Command", BIND_CAPPED]:
            raise TekutoBalanceCError(f"skill {level}: segment {path} is {[_shape(s) for s in items]}")
        closed = deepcopy(items)
        opened = deepcopy(items)
        opened[0][1][5] = BIND_UNCAPPED_CAP
        block[1] = [["Command", [FLAG_COMMAND, LEADER_FLAG, ["Block", opened], ["Block", closed]]]]
        facts.append({"block": ".".join(map(str, path)), "statements": list(shape)})
    # 自检：每个旗号 3 分支的关支 == live 原段；开支只在 Bind[5] 与关支不同（int 99）
    for (path, _shape_), branch in zip(SEGMENTS, flag_branches(out, LEADER_FLAG)):
        opened, closed = branch[2][1], branch[3][1]
        if closed != _at(tree, path)[1]:
            raise AssertionError(f"skill {level}: closed branch {path} is not the live segment")
        if opened[1:] != closed[1:] or opened[0][1][:5] != closed[0][1][:5] \
                or type(opened[0][1][5]) is not int or opened[0][1][5] != BIND_UNCAPPED_CAP:
            raise AssertionError(f"skill {level}: open branch {path} differs beyond the bind cap")
    if len(flag_branches(out, LEADER_FLAG)) != len(SEGMENTS):
        raise AssertionError("flag-3 branch count")
    return out, {"level": level, "flag": LEADER_FLAG, "segments": facts,
                 "bind_cap": {"closed": BIND_CAPPED[5], "open": BIND_UNCAPPED_CAP},
                 "amf3_bytes": [len(wf_dsl.encode_amf3(tree)), len(wf_dsl.encode_amf3(out))]}


def dsl_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返 + vlv 作用域 + 按分支的绑定号唯一。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    problems += [f"player_side: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    problems += [f"vid_scope: {p}" for p in vid_scope_problems(tree)]
    problems += [f"dup_bind_id: {i}" for i in dup_bound_ids(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


# ------------------------------------------------------------------ 文案

def _replace_desc(text: str, label: str) -> str:
    """口径 R3：技能说明只写本体——核对是第二批原文并原样返回（本轮不改）。"""
    if text != OLD_DESC:
        raise TekutoBalanceCError(f"{label}: skill description is not the reviewed batch-2 text")
    if any(mark in NEW_DESC for mark in ENHANCED_DESC_MARKS):
        raise TekutoBalanceCError(f"{label}: skill description must not describe the leader-flag enhancement")
    return NEW_DESC


def revise_texts(action, text, server) -> tuple[list, list, list]:
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise TekutoBalanceCError(f"action_skill {CODE}: inner keys changed")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        if fields[7] != PROGRAMS[inner]:
            raise TekutoBalanceCError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
        if inner == "1" and fields[0] != SKILL_NAME:
            raise TekutoBalanceCError(f"action_skill {CODE}/1: skill name {fields[0]!r} != {SKILL_NAME!r} "
                                      "(the flag text names the skill)")
        fields[1] = _replace_desc(fields[1], f"action_skill {inner} c1")
        new_action.append((inner, fields))
    for label, rows in (("character_text", text), ("server character_text", server)):
        if len(rows) != 1 or len(rows[0]) != 12:
            raise TekutoBalanceCError(f"{label} {CID}: expected one 12-column row")
        for col in TEXT_DESC_COLUMNS:
            rows[0][col] = _replace_desc(rows[0][col], f"{label} c{col}")
    return new_action, text, server


# ------------------------------------------------------------------ revise

def _read_inputs(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise TekutoBalanceCError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)
    for kind, key in NEW_KEYS:
        try:
            value = read(kind, key)
        except (KeyError, FileNotFoundError):
            continue
        if value is not None:
            raise TekutoBalanceCError(f"new key already exists in live: {kind}:{key}")
    return inputs


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _read_inputs(read)

    unique = inputs["table", (UNIQUE, UID_ENGINE)]
    if len(unique) != 1 or unique[0][UNIQUE_ENGINE_MAX_COL] != str(BIND_UNCAPPED_CAP):
        raise TekutoBalanceCError(f"unique {UID_ENGINE} max stacks is not {BIND_UNCAPPED_CAP}")
    abilities = {key: inputs["ability", key] for key in ABILITY_KEYS}
    old_leader = inputs["leader", LEADER_KEY]
    occupancy = flag_occupancy(abilities, old_leader)
    if set(occupancy) != {1, 2} or occupancy[1] != [f"ability:{ABILITY1_KEY}#1"] \
            or occupancy[2] != [f"ability:{CID}3#1"]:
        raise TekutoBalanceCError(f"skill flags occupancy drifted: {occupancy}")

    leader = leader_rows(old_leader)
    ability1 = ability1_rows(abilities[ABILITY1_KEY])
    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"{ABILITY1_KEY}#{i}: {p}" for i, row in enumerate(ability1) for p in row_problems("ability", row)]
    for kind, rows in (("leader_ability", leader), ("ability", ability1)):
        for i, row in enumerate(rows):
            if L.required_client_capabilities(kind, row):
                problems.append(f"{kind}#{i}: unexpected capability")
    after = flag_occupancy({**abilities, ABILITY1_KEY: ability1}, leader)
    if after.get(LEADER_FLAG) != [f"ability:{ABILITY1_KEY}#2"]:
        problems.append(f"flag {LEADER_FLAG} occupancy after revise: {after.get(LEADER_FLAG)}")
    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, ev = revise_tree(inputs["dsl", program], level)
        problems += [f"skill {level}: {p}" for p in dsl_problems(tree)]
        trees[program] = tree
        tree_notes.append(ev)
    if problems:
        raise TekutoBalanceCError("; ".join(problems))
    # 技能说明 5 处：核对第二批原文 / 程序路径 / 技能名；口径 R3 下结果 == live ⇒ 不返回
    before = (deepcopy(inputs["action", CODE]), deepcopy(inputs["text", CID]), deepcopy(inputs["server_text", CID]))
    action, text, server = revise_texts(inputs["action", CODE], inputs["text", CID], inputs["server_text", CID])
    if ([[i, list(f)] for i, f in action], text, server) != ([[i, list(f)] for i, f in before[0]], *before[1:]):
        raise TekutoBalanceCError("skill descriptions would change (口径 R3: only the enhancement entry describes it)")

    return {
        "ability": {ABILITY1_KEY: ability1},
        "leader": {LEADER_KEY: leader},
        "cas": {LEADER_CAS_KEY: [[CAS_TEXT]]},
        "table": {},
        "text": {},
        "action": {},
        "dsl": trees,
        "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_tekuto.py",
            "spec": "growth_c_spec.md（作者原话 1–6；D1–D4 / U4 / U6–U8）；reeval_full.json table.rows 特克托 6 行、"
                    "design.characters 特克托",
            "growth": {f"leader_ability:{LEADER_KEY}#{i}": (
                f"c{cols[0]}/c{cols[1]} {batch2}→{new}：{what}（原 {int(original) / 1000:g}% / 批二 "
                f"{int(batch2) / 1000:g}% / 第三批 {int(new) / 1000:g}%，{TIER_NAMES[tier]}）")
                for i, (_c, cols, original, batch2, tier, new, what) in LEADER_EDITS.items()},
            "rounding": "原值 ≥20% 取 5 的倍数、≤10% 取 0.5 的倍数；2/3 档一律向上取（#2 3.33→3.5、#10/#11 33.3→35）",
            "leader_kept": {f"leader_ability:{LEADER_KEY}#{i}": what for i, (_c, what) in LEADER_KEPT.items()},
            "ability2_kept": "能力2 封顶版 16%/15%×10 保持第二批（D4）",
            "early_stack_overlap": "前 10 层自身攻击 35%+16%=51%（原 50%）、自身技伤 35%+15%=50%（=原值），作者知情项",
            "skill_flag": {
                "flag": LEADER_FLAG, "kind": SWITCH_KIND,
                "row": f"ability:{ABILITY1_KEY}#2（= #1 的 536 行只换 c6 202→42、c47 536→705、c70 → {LEADER_CAS_KEY}）",
                "occupied_before": {str(k): v for k, v in occupancy.items()},
                "precedent": "live 罗尔夫中秋 1499866#4（704 + 前置 42 + 共鸣）；官方 705 只在能力表"
                             "（psychic_nao_3halfanv_6、holysword_girl_5）",
                "leader_table_not_used": "零先例 kind 进队长表会崩 ⇒ 不写队长表 705 行（U6）",
            },
            "skill_dsl": {
                "wrap": "每处 Bind 起到块尾 → ConditionalsChangeSkillFlag(3, 开支 Bind 上限 99(int), 关支 live 原段)",
                "closed_branch": "与 live 逐字相同（非队长或不共鸣：封顶 10 层，U7）",
                "open_branch": "只 Bind[5] 10→99（第二批前原值，= 固有「引擎启动」c4）；第二批激光削韧 0.3 随整段保留",
                "untouched": "根部旗号 2 护盾分支、alv/alv2 数值项、事件名、RemoveEventFromOwner/HideEffectFromOwner",
                "trees": tree_notes,
            },
            "skill_description": {"unchanged": OLD_DESC,
                                  "why": "主会话 2026-09-27 口径 R3：技能说明只写技能本体（关支上限「（最多10层）」照写），"
                                         "强化后的不封顶只由 CAS 强化条目描述，不在技能说明里重复",
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"]},
            "cas": {LEADER_CAS_KEY: CAS_TEXT,
                    "panel": "特克托无 desc_override；这条由客户端自动显示在能力 1 面板（U8，作者已接受）"},
            "generator": ("wf_seasonal7_kit_tekuto.py：_DESC_BALANCE_C、CHANGE_SKILL_LEADER_KEY、第七轮 apply_balance_c"
                          "（build() 中叠在 apply_balance_b 之后）与 balance_c_skill_tree（叠在 final_tree 之后）"),
            "capabilities": [],
            "runtime_verified": False,
        },
    }
