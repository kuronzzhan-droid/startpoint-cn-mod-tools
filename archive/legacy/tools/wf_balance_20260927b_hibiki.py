# -*- coding: utf-8 -*-
"""澄波响 169988 ``psychic_teleport_moon``（暗 · 特殊型 PF 主 C）：2026-09-27 第二批平衡（纯函数）。

规则来源（优先级从高到低）：作者原话 → ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``
→ 设计稿 ``growth/growth_design.json``（169988）与 ``growth/down_design.json``（169988）。
设计稿按 live 1.4.1048 写；本模块按 live 1.4.1049 重读（两者对本角色逐字相同，见 :data:`BEFORE`）。

一、无上限成长（口径 A）

「回响」（固有 16998801）上限 99 ＝ 作者「不设置上限」的官方写法，所以两条「限次 99」的每层成长按无上限处理
（口径 A.1；设计稿 critic C15 已核）。3 分钟实际触发次数（口径 A.2，不按事件名称）：

- 回响层数：当队长（必在主位）时 PF 约 60–90 次（冲刺 CT 1.5 秒即 PF、暗属性角色发动技能即 PF、自然 PF），
  能力 3 每次 PF ＋1 层 ＋ 队长每 3 次 PF ＋2 层 ＋ 每次技能 ＋1 层 ⇒ 约 2–2.5 分钟满 99 层；
  按发放事件计（同批 gbf/索利兹口径：一次发放算一次）也 ≥30：暗共鸣下仅「每次 PF ＋1 层」就有 60–90 次；
  不开暗共鸣时按层数算队长每 3 PF ＋2 层有 40–60 层，按事件算（每 3 PF 20–30 次 ＋ 技能 5–9 次）25–39 次
  处在边界，但本角色全部机制都以暗共鸣为前提 ⇒ **≥30 次 ⇒ ×1/10**：每层 25% → 2.5%。
  （设计稿按事件标签「每层固有＝低频」取 1/5＝5%；口径 A.2 改按实际次数，故取 2.5%。）
- 队长 L7「全等级 PF 累计命中每 4 次 → 自身攻击力」：每次 PF 2–4 段，3 分钟 120–300 段 ⇒ 30–75 次
  ⇒ ≥30 ⇒ ×1/10：50% → 5%（与设计稿一致），仍不限次（c32=(None)）。

改动：

1. ``ability:1699883`` #1（槽 3，仅主位）「每层回响 → 自身 PF 伤害 25%，限 99」：
   无上限部分按口径 A.3 搬进队长 ``[CODE,'0',''] + 行[5:]``（能力列 c≥5 → 队长 c−2），强度 25000 → 2500；
   原位换成封顶版：c102 99 → 10、c113/c114 25000 → 10000（每层 10%，最多 10 层 ＝ ＋100%，设计稿给定）。
2. ``ability:1699884`` #2（槽 4）「每层回响 → 自身攻击力 25%，限 99」：同法搬进队长（2500/层）；
   原位 c102 99 → 10、c113/c114 25000 → 5000（每层 5%，最多 10 层 ＝ ＋50%，设计稿给定）。
3. ``leader_ability:169988``：#6 c49/c50 50000 → 5000；末尾追加上面两行（10 → 12 行）。
   队长原本没有 during 134 行 ⇒ 无「同触发/同 kind/同目标/同前置/无 CT」的合并对象，新起两行。
   先例（口径 A.4）：队长 during 134 官方 7 行（161063#2 ＝ 134 → kind 0 自身）；队长 during kind 23
   官方 5 行、live 稻穗 139995#4 / 丝缇涅尔 169995#6 在 134 上已用 ⇒ 不是零先例。
4. 面板：``desc_override_psychic_teleport_moon`` 第 7 行 ＋50% → ＋5%，其后插入
   「每1层“回响”，自身强化弹射伤害＋2.5%、攻击力＋2.5%」（无上限按裁决 §3 写到效果为止）；
   ``_3`` 第 2 行 →「每1层“回响”，自身强化弹射伤害＋10%（最多10层）」；
   ``_4`` 追加「每1层“回响”，自身攻击力＋5%（最多10层）」（行本来就在槽 4；原偏离 D-13 把文案挂在槽 3，
   封顶后两条数值不同，各回各槽）。

不动：能力 3 #0（461 每次 PF ＋1 层）与队长 #4（每 3 PF ＋2 层）只产层数（设计稿 keep）；能力 2（限 25 次）、
能力 3 #2（413 封顶 5 层）、能力 6 #2（封顶 5 层）为有限成长；能力 6 #1 技能充能与所有加槽行（口径 A.6 本批不动）。

二、Down（口径 B.3）

``battle/action/skill/action/ability_skill/ability_skill_psychic_teleport_moon_pf`` 由队长两行 629 共用：
冲刺行 CT 90 帧 ＝ 1.5 秒、暗属性角色发动技能行 CT 0 ⇒ 「触发 CT ≤3 秒的 629 每次 ≤1」。
两段 ``CreateNormalAttack`` 的 p13（SLv {min,max}）6.25 → 0.25：判定区 3 段 + 1 段 ＝ 每次 25 → 1。
其余节点逐字保留（倍率 19.2/43.2、根头 133、判定区 p23=0）。722 本体三档（15/20/25）不动。

生成器 ``wf_midautumn_kit_hibiki`` 已同步（LEADER / PLAN[3] / PLAN[4] / PANEL_* / build_invoke_tree），
测试断言生成器输出 == :func:`revise` 输出；设计镜像（design/hibiki.json、rework1/panel/hibiki.json）
由 :func:`sync_mirrors` 幂等同步。本模块只读 ``read()`` 并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as legality
import wf_dsl

CID = "169988"
CODE = "psychic_teleport_moon"
PACKAGES = ["ma-hibiki"]
#: 候选 ``work/character_packs/ma-hibiki/package/manifest.json`` 现值 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-hibiki": "1.0.1"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2 / damage-type-rules-v1；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 117 个 manifest 条目与文件逐一一致，本模块读取的队长/6 能力键/10 串键/629 树与 live 逐字相同
#: （2026-09-27 只读核对）⇒ 无已审漂移。
REVIEWED_DRIFT: dict = {}

ELEMENT = 5                        # master/character c3：暗（0 基内部元素）
LEADER_KEY = CID
ABILITY3, ABILITY4 = f"{CID}3", f"{CID}4"
CAS_LEADER = f"desc_override_{CODE}"
CAS_SLOT3 = f"desc_override_{CODE}_3"
CAS_SLOT4 = f"desc_override_{CODE}_4"
#: 队长两行 629 的条目串（只读：invoke_skill_string_problems 需要它们在 custom_ability_string 里）。
CAS_INVOKE = (f"ability_skill_{CODE}_pf_skill", f"ability_skill_{CODE}_pf_dash")
MAIN_ICON = " <icon id='main'>  "  # 主位限制槽 desc_override 每行的前缀（槽 3 c1=false）

UID = "16998801"                   # 固有「回响」
UNIQUE_CAP = "99"
UNIQUE = ("master/character/unique_condition.orderedmap", UID)
INVOKE_PROGRAM = (f"battle/action/skill/action/ability_skill/ability_skill_{CODE}_pf"
                  f"$ability_skill_{CODE}_pf")
INVOKE_BTA = 133                   # 根头 buffTargetAs（damage-type-rules-v1 按 PF3 结算），不动

LEADER_NCOLS, ABILITY_NCOLS = 124, 126
LEADER_ROWS_BEFORE, LEADER_ROWS_AFTER = 10, 12

# ---------------------------------------------------------------- 数值
ECHO_OLD = "25000"                 # 每层 25%
ECHO_LEADER = "2500"               # 队长：×1/10 ⇒ 2.5%/层（≥30 次）
ECHO_CAP_OLD, ECHO_CAP_NEW = UNIQUE_CAP, "10"
ECHO_PFDMG_ABILITY = "10000"       # 槽 3 封顶版：10%/层 × 10 ＝ ＋100%
ECHO_ATK_ABILITY = "5000"          # 槽 4 封顶版：5%/层 × 10 ＝ ＋50%
HIT_OLD, HIT_NEW = "50000", "5000"  # 队长 #6：每累计 4 次 PF 命中自身攻击 50% → 5%
HIT_ROW = 6                        # 0 基；面板/设计稿口中的「队长行 7」
PFDMG_ROW, ATK_ROW = 1, 2          # 0 基：槽 3 #1、槽 4 #2

DOWN_OLD, DOWN_NEW = 6.25, 0.25    # 629 追击树每段削韧（CreateNormalAttack p13）
DOWN_SEGMENTS = [3, 1]             # 两个判定区的 CalculatedUsingMaxNumOfHits
DOWN_CAP_PER_CALL = 1.0            # 口径 B.3：触发 CT ≤3 秒的 629 每次 ≤1
INVOKE_CT_FRAMES = {"23": "0", "4": "90"}   # 两行 629 的触发 → CT（帧）；均 ≤ 180（3 秒）

# ---------------------------------------------------------------- 面板
OLD_LEADER_LINES = (
    "赋予自身特殊强化弹射",
    "强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "持有贯穿效果时，暗属性角色攻击力＋300%、强化弹射伤害＋200%",
    "暗属性共鸣时，贯穿效果持续时间＋30%；暗属性角色发动技能时，自身立即获得强化弹射效果",
    "每发动3次强化弹射（含额外触发），自身“回响”＋2层",
    "强化弹射每累计命中4次，自身攻击力＋50%",
    "冲刺时，立即获得强化弹射效果（冷却时间：1.5秒）",
)
LEADER_HIT_LINE = 6                # 0 基
NEW_LEADER_HIT = "强化弹射每累计命中4次，自身攻击力＋5%"
NEW_LEADER_ECHO = "每1层“回响”，自身强化弹射伤害＋2.5%、攻击力＋2.5%"
NEW_LEADER_LINES = (OLD_LEADER_LINES[:LEADER_HIT_LINE] + (NEW_LEADER_HIT, NEW_LEADER_ECHO)
                    + OLD_LEADER_LINES[LEADER_HIT_LINE + 1:])

OLD_SLOT3_LINES = (
    "暗属性共鸣时，每发动1次强化弹射，自身获得1层“回响”",
    "自身对“回响”每提升1层，强化弹射伤害＋25%、攻击力＋25%",
    "每1层“回响”，强化弹射伤害额外乘区＋5%（最多5层）",
)
SLOT3_LINE = 1
NEW_SLOT3_ECHO = "每1层“回响”，自身强化弹射伤害＋10%（最多10层）"
NEW_SLOT3_LINES = OLD_SLOT3_LINES[:SLOT3_LINE] + (NEW_SLOT3_ECHO,) + OLD_SLOT3_LINES[SLOT3_LINE + 1:]

OLD_SLOT4_LINES = (
    "持有贯穿效果期间，自身攻击力＋200%",
    "持有贯穿效果期间，强化弹射伤害＋150%",
)
NEW_SLOT4_ECHO = "每1层“回响”，自身攻击力＋5%（最多10层）"
NEW_SLOT4_LINES = OLD_SLOT4_LINES + (NEW_SLOT4_ECHO,)

#: 口径 D 面板禁语（与 wf_midautumn_kitlib.FORBIDDEN_PANEL_WORDS 同口径，另加分隔符）。
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "无上限", "无限叠加",
                           "不设上限", "可无限", "／", "(None)", "null")

# ---------------------------------------------------------------- 输入基线

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 ma-hibiki 1.0.0 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER_KEY): "fe263858dacf150425d2d9a7a9a621cf1cb3e38c9a546465e5e45eb10ba7c05d",
    ("ability", ABILITY3): "c73c120225c7aeb555e39a61dfd21b56f8878c9c50e2ffac8117e557e2636ff5",
    ("ability", ABILITY4): "e7c7012b0b905baf79f84c441baeda430ad955fed443ec84a368f5e666ab963e",
    ("cas", CAS_LEADER): "702a377aeae1a033fea898c56e560d466e0caa38b69ed5c09d6def2556346d8c",
    ("cas", CAS_SLOT3): "2b986db9677b829da6c61e8b5bae19d4d04760b1ff732b6e69e1e725d5ba6150",
    ("cas", CAS_SLOT4): "6cb5cc0dc0a5a4eb30b273fd3cba11177a1c92951353515b6cce920361e9feda",
    # 只读：629 条目串必须在场（队长 629 行的文案键）；固有「回响」上限 99 是「按无上限处理」的依据。
    ("cas", CAS_INVOKE[0]): "b73d4db3eb38bbb783996a87f5820e9a65f7c889c1d893fed57bfcc7b27c8959",
    ("cas", CAS_INVOKE[1]): "506cd903110e1f69ae4cad7f0858f2a4c9f8815f410bec8748c64a6262c5a20a",
    ("table", UNIQUE): "fed4c990e9cda456390fa64b6b9f3a3a46259b8a2e8b1ed735380c4df0e8b5c0",
    ("dsl", INVOKE_PROGRAM): "d06f3b29ff89dbcf4409c92b596bb78bbc05d57d7a22580d90846d48c6c6a986",
}

#: 改前逐格指纹（全部非空列；其余列必须为空）。BEFORE 之外的第二道锁，也让纯函数可单测，
#: 且对自身输出重跑必然拒绝（数值已不是旧值）。
BEFORE_HIT_CELLS: dict[int, str] = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "15", 28: "400000", 29: "400000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "32", 46: "0", 49: HIT_OLD, 50: HIT_OLD,
}
_ECHO_A = {3: "0", 5: "1", 6: "0", 13: "0", 20: "0", 85: "(None)", 97: "134", 98: "0",
           100: "100000", 101: "100000", 102: ECHO_CAP_OLD, 104: UID, 108: "false", 110: "0",
           113: ECHO_OLD, 114: ECHO_OLD}
BEFORE_PFDMG_CELLS: dict[int, str] = {0: f"{CODE}_3", 1: "false", 2: "power_flip", **_ECHO_A, 109: "23"}
BEFORE_ATK_CELLS: dict[int, str] = {0: f"{CODE}_4", 1: "true", 2: "attack_common", **_ECHO_A, 109: "0"}
#: 队长两行 629 的指纹（只校验触发/CT/动作，其余逐字保留）：c25 触发 → c33 CT。
INVOKE_ROWS = {5: "23", 7: "4"}


class HibikiBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HibikiBalanceError(message)


def _checked(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise HibikiBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                 f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ---------------------------------------------------------------- 行

def to_leader(row: list[str]) -> list[str]:
    """口径 A.3：``[CODE, '0', ''] + 能力行[5:]``（能力列 c≥5 → 队长 c−2），126 列 → 124 列。"""
    _require(len(row) == ABILITY_NCOLS, f"ability row width {len(row)} != {ABILITY_NCOLS}")
    out = [CODE, "0", ""] + list(row[5:])
    _require(len(out) == LEADER_NCOLS, f"leader row width {len(out)} != {LEADER_NCOLS}")
    return out


def moved_leader_row(row: list[str]) -> list[str]:
    """能力里的回响每层成长 → 队长同形行，强度 25% → 2.5%（其余格原样平移）。"""
    out = to_leader(row)
    _require(out[111:113] == [ECHO_OLD, ECHO_OLD], f"moved row strength drift: {out[111:113]}")
    out[111] = out[112] = ECHO_LEADER
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """槽 3 #1：每层回响 PF 伤害 25%/限 99 → 10%/限 10；其余 2 行逐字保留。"""
    _require(len(rows) == 3 and all(len(r) == ABILITY_NCOLS for r in rows), f"{ABILITY3} shape drift")
    hits = [i for i, row in enumerate(rows) if _matches(row, ABILITY_NCOLS, BEFORE_PFDMG_CELLS)]
    _require(hits == [PFDMG_ROW], f"{ABILITY3}: echo PF-damage growth row not found at #{PFDMG_ROW}: {hits}")
    out = deepcopy(rows)
    row = out[PFDMG_ROW]
    row[102] = ECHO_CAP_NEW
    row[113] = row[114] = ECHO_PFDMG_ABILITY
    _require([i for i, (a, b) in enumerate(zip(rows, out)) if a != b] == [PFDMG_ROW],
             f"{ABILITY3}: touched another record")
    return out


def ability4_rows(rows: list[list[str]]) -> list[list[str]]:
    """槽 4 #2：每层回响攻击力 25%/限 99 → 5%/限 10；其余 2 行逐字保留。"""
    _require(len(rows) == 3 and all(len(r) == ABILITY_NCOLS for r in rows), f"{ABILITY4} shape drift")
    hits = [i for i, row in enumerate(rows) if _matches(row, ABILITY_NCOLS, BEFORE_ATK_CELLS)]
    _require(hits == [ATK_ROW], f"{ABILITY4}: echo attack growth row not found at #{ATK_ROW}: {hits}")
    out = deepcopy(rows)
    row = out[ATK_ROW]
    row[102] = ECHO_CAP_NEW
    row[113] = row[114] = ECHO_ATK_ABILITY
    _require([i for i, (a, b) in enumerate(zip(rows, out)) if a != b] == [ATK_ROW],
             f"{ABILITY4}: touched another record")
    return out


def leader_rows(rows: list[list[str]], ability3: list[list[str]],
                ability4: list[list[str]]) -> list[list[str]]:
    """队长：#6 累计命中攻击 50% → 5%；末尾追加两条回响每层成长（2.5%/层）。"""
    _require(len(rows) == LEADER_ROWS_BEFORE and all(len(r) == LEADER_NCOLS for r in rows),
             f"leader {LEADER_KEY} shape drift ({len(rows)} rows)")
    hits = [i for i, row in enumerate(rows) if _matches(row, LEADER_NCOLS, BEFORE_HIT_CELLS)]
    _require(hits == [HIT_ROW], f"leader PF-hit growth row not found at #{HIT_ROW}: {hits}")
    # 合并判定（口径 A.3）：队长里没有任何 during 134 行 ⇒ 没有同触发/同 kind/同目标/同前置的合并对象。
    _require(not [i for i, r in enumerate(rows) if r[3] == "1" and r[95] == "134"],
             "leader already carries a during-134 row: merge instead of appending")
    for index, trigger in INVOKE_ROWS.items():
        row = rows[index]
        _require((row[3], row[25], row[45], row[69]) == ("0", trigger, "629", INVOKE_PROGRAM)
                 and row[33] == INVOKE_CT_FRAMES[trigger] and int(row[33]) <= 180,
                 f"leader #{index}: 629 invoke row drift")
    out = deepcopy(rows)
    out[HIT_ROW][49] = out[HIT_ROW][50] = HIT_NEW
    for source, label in ((ability3[PFDMG_ROW], ABILITY3), (ability4[ATK_ROW], ABILITY4)):
        _require(_matches(source, ABILITY_NCOLS,
                          BEFORE_PFDMG_CELLS if label == ABILITY3 else BEFORE_ATK_CELLS),
                 f"{label}: moved row must be taken from the unrevised live row")
        out.append(moved_leader_row(source))
    _require(len(out) == LEADER_ROWS_AFTER, "revised leader row count")
    return out


# ---------------------------------------------------------------- 面板

def _single_text(rows: list[list[str]], key: str) -> str:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return rows[0][0]


def leader_panel(text: str) -> str:
    _require(tuple(text.split("\n")) == OLD_LEADER_LINES, f"{CAS_LEADER}: unexpected panel text layout")
    return "\n".join(NEW_LEADER_LINES)


def slot3_panel(text: str, icon: str = MAIN_ICON) -> str:
    """槽 3 仅主位 ⇒ desc_override 每行自带 Ⓜ；``icon=""`` 用于作者原文（不带图标的镜像/kit-report）。"""
    _require(tuple(text.split("\n")) == tuple(icon + line for line in OLD_SLOT3_LINES),
             f"{CAS_SLOT3}: unexpected panel text layout")
    return "\n".join(icon + line for line in NEW_SLOT3_LINES)


def slot4_panel(text: str) -> str:
    _require(tuple(text.split("\n")) == OLD_SLOT4_LINES, f"{CAS_SLOT4}: unexpected panel text layout")
    return "\n".join(NEW_SLOT4_LINES)


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    return [[leader_panel(_single_text(rows, CAS_LEADER))]]


def slot3_text(rows: list[list[str]]) -> list[list[str]]:
    return [[slot3_panel(_single_text(rows, CAS_SLOT3))]]


def slot4_text(rows: list[list[str]]) -> list[list[str]]:
    return [[slot4_panel(_single_text(rows, CAS_SLOT4))]]


def panel_problems(key: str, text: str, main_only: bool) -> list[str]:
    problems = [f"{key}: forbidden phrase {word!r}" for word in FORBIDDEN_PANEL_PHRASES if word in text]
    for line in text.split("\n"):
        if line.startswith(MAIN_ICON) != main_only:
            problems.append(f"{key}: main-position icon does not match the slot: {line!r}")
    return problems


# ---------------------------------------------------------------- DSL

def _slv(value: float) -> list[dict]:
    return [{"min": value, "max": value}]


def _mask_down(tree) -> list:
    """把全部 CreateNormalAttack 的 p13 抹掉后的副本（用于「只改了 p13」自检）。"""
    masked = deepcopy(tree)
    for cna in wf_dsl.iter_dsl_commands(masked, "CreateNormalAttack"):
        cna[13] = None
    return masked


def invoke_tree(tree) -> tuple[list, dict[str, Any]]:
    """629 追击树：两段 CNA 的 p13（SLv min/max）6.25 → 0.25；每次 25 → 1，其余节点逐字保留。"""
    out = deepcopy(tree)
    _require(out[:11] == ["ActionDsl", 1, ["None"], *[False] * 7, INVOKE_BTA],
             f"invoke tree root header drift: {out[:11]}")
    areas = list(wf_dsl.iter_dsl_commands(out, "CreateHitArea"))
    attacks_total = list(wf_dsl.iter_dsl_commands(out, "CreateNormalAttack"))
    _require(len(areas) == len(DOWN_SEGMENTS) and len(attacks_total) == len(DOWN_SEGMENTS),
             f"invoke tree shape drift: {len(areas)} hit areas / {len(attacks_total)} attacks")
    segments, multipliers = [], []
    for cha in areas:
        mode = cha[14]
        _require(isinstance(mode, list) and len(mode) == 2 and mode[0] == "CalculatedUsingMaxNumOfHits",
                 f"invoke hit area hit-count drift: {mode}")
        _require(cha[24] == 0, f"invoke hit area p23 drift: {cha[24]}")
        attacks = list(wf_dsl.iter_dsl_commands(cha, "CreateNormalAttack"))
        _require(len(attacks) == 1, f"hit area carries {len(attacks)} CreateNormalAttack")
        cna = attacks[0]
        _require(cna[2] == 255, f"invoke CNA explicit element {cna[2]} (must stay 255)")
        _require(cna[13] == _slv(DOWN_OLD), f"invoke CNA p13 preimage drift: {cna[13]}")
        cna[13] = _slv(DOWN_NEW)
        segments.append(mode[1])
        multipliers.append(cna[6][0]["max"])
    _require(segments == DOWN_SEGMENTS, f"invoke segments drift: {segments}")
    before, after = sum(segments) * DOWN_OLD, sum(segments) * DOWN_NEW
    _require(after <= DOWN_CAP_PER_CALL, f"invoke detoughness per call {after} > {DOWN_CAP_PER_CALL}")
    _require(_mask_down(out) == _mask_down(tree), "invoke_tree touched more than CreateNormalAttack p13")
    return out, {"segments": segments, "per_segment": [DOWN_OLD, DOWN_NEW],
                 "per_call": [before, after], "multipliers": multipliers}


def dsl_problems(tree) -> list[str]:
    """AMF3 往返 + 四道 DSL 门禁（口径 D）。"""
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in legality.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in legality.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in legality.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in legality.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str], cas_keys) -> list[str]:
    return (legality.client_legality_problems(kind, row)
            + legality.declared_block_field_problems(kind, row)
            + legality.invoke_skill_string_problems(row, cas_keys, kind))


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    unique = inputs["table", UNIQUE]
    _require(len(unique) == 1 and unique[0][4] == UNIQUE_CAP,
             f"unique_condition {UID} cap drift: {unique[0][4] if unique else None}")

    live3, live4 = inputs["ability", ABILITY3], inputs["ability", ABILITY4]
    ability = {ABILITY3: ability3_rows(live3), ABILITY4: ability4_rows(live4)}
    leader = {LEADER_KEY: leader_rows(inputs["leader", LEADER_KEY], live3, live4)}
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]),
           CAS_SLOT3: slot3_text(inputs["cas", CAS_SLOT3]),
           CAS_SLOT4: slot4_text(inputs["cas", CAS_SLOT4])}
    tree, down = invoke_tree(inputs["dsl", INVOKE_PROGRAM])

    cas_keys = set(cas) | set(CAS_INVOKE)
    problems = [f"ability {key}#{i}: {p}" for key, rows in ability.items()
                for i, row in enumerate(rows) for p in row_problems("ability", row, cas_keys)]
    problems += [f"leader {LEADER_KEY}#{i}: {p}" for i, row in enumerate(leader[LEADER_KEY])
                 for p in row_problems("leader_ability", row, cas_keys)]
    problems += [f"dsl {INVOKE_PROGRAM}: {p}" for p in dsl_problems(tree)]
    problems += panel_problems(CAS_LEADER, cas[CAS_LEADER][0][0], False)
    problems += panel_problems(CAS_SLOT3, cas[CAS_SLOT3][0][0], True)
    problems += panel_problems(CAS_SLOT4, cas[CAS_SLOT4][0][0], False)
    if problems:
        raise HibikiBalanceError("; ".join(problems))

    return {
        "ability": ability, "leader": leader, "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {INVOKE_PROGRAM: tree}, "server_text": {},
        "new_programs": [],
        "notes": notes(down),
    }


def notes(down: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "wf_balance_20260927b_hibiki.py",
        "spec": "第二批施工口径 A（无上限成长）+ B.3（629 CT≤3 秒每次≤1）；设计稿 growth_design/down_design 169988",
        "growth": {
            f"ability:{ABILITY3}#{PFDMG_ROW}": "每层回响自身PF伤害 25%/限99 → 10%/限10（c102 99→10，c113/c114 25000→10000）",
            f"ability:{ABILITY4}#{ATK_ROW}": "每层回响自身攻击力 25%/限99 → 5%/限10（c102 99→10，c113/c114 25000→5000）",
            f"leader_ability:{LEADER_KEY}#{HIT_ROW}": "全等级PF累计命中每4次自身攻击力 50%→5%（c49/c50），仍不限次",
            f"leader_ability:{LEADER_KEY}#10": f"新增：[CODE,'0','']+{ABILITY3}#{PFDMG_ROW}[5:]，每层回响自身PF伤害 2.5%（c111/c112）",
            f"leader_ability:{LEADER_KEY}#11": f"新增：[CODE,'0','']+{ABILITY4}#{ATK_ROW}[5:]，每层回响自身攻击力 2.5%（c111/c112）",
        },
        "frequency": {
            "echo_layers_3min": "约 99（PF 60–90 次 × ≈1.67 层 + 每次技能 1 层，约 2–2.5 分钟满 99；"
                                "无暗共鸣时队长每 3 PF +2 层也有 40–60 层）⇒ ≥30 ⇒ ×1/10：25%→2.5%",
            "echo_events_3min": "按发放事件计（与同批 gbf/索利兹一致）：暗共鸣下仅能力3「每次 PF +1 层」就有 60–90 次 ≥30；"
                                "无暗共鸣时每 3 PF 事件 20–30 次 + 技能 5–9 次 ＝ 25–39 次（边界），"
                                "但本角色机制全部以暗共鸣为前提 ⇒ 两种计数口径都落 ≥30 档",
            "pf_hit_quads_3min": "PF 每次 2–4 段 ⇒ 120–300 段 ⇒ 每 4 段触发 30–75 次 ⇒ ≥30 ⇒ ×1/10：50%→5%",
            "deviation_from_design": "设计稿回响每层按事件标签取 1/5（5%）；口径 A.2 按实际次数，改取 1/10（2.5%）",
            "precision": "两条回响队长行同精度 2.5%（口径 A.7）",
        },
        "unlimited_basis": f"固有 {UID} 上限 {UNIQUE_CAP}（作者「不设置上限」的官方写法）⇒ 限次 99 按无上限处理",
        "leader_precedent": "队长 during134：官方 7 行（161063#2 = 134→kind0 自身）；kind23：官方 5 行，"
                            "live 139995#4 / 169995#6 在 134 上；trigger15：官方 131182#1/#2",
        "target_column": "新增两行 c108（目标）＝ '0'，照口径 A.3 由能力行 c110 原样平移。先例形状："
                         "#11（kind0）官方队长 during kind0+c108 '0' 有 2 行（如 161063#2）；"
                         "#10（kind23）官方队长 5 行、live 队长 14 行的 c108 都是空串（live 另有 2 行写 5），"
                         "队长表无 '0' 先例——'0' 的依据是 live 能力表 kind23+c110 '0' 共 13 行（含本角色 1699883#1）"
                         "一直在线正常，且三件合法性门禁全空（解析器接受 '0'）",
        "donor_pin": "生成器队长 #0（722）以 live 菲莉亚 159996#3 为 donor，菲莉亚第二批改其 c49/c50 50000→7000；"
                     "已把 donor 全部非空列（含 c7/c8/c9、c28/c29/c32/c33、c49/c50）按 live 值钉死，"
                     "本角色 #0 输出不变，生成器不再随菲莉亚漂移（测试 DonorPinTest）",
        "merge": "队长原无 during134 行 ⇒ 无合并对象，新起两行（队长 10→12 行）",
        "down": {
            INVOKE_PROGRAM: f"CreateNormalAttack p13 {DOWN_OLD}→{DOWN_NEW}（{down['segments']} 段，"
                            f"每次 {down['per_call'][0]}→{down['per_call'][1]}）",
            "trigger_ct": "冲刺行 CT 90 帧（1.5 秒）/ 暗属性角色发动技能行 CT 0 ⇒ 口径 B.3 每次 ≤1",
            "untouched": "722 本体三档 15/20/25、技能两档（18×0.556＝10）",
        },
        "panel": {
            CAS_LEADER: f"第7行 → {NEW_LEADER_HIT}；插入第8行 → {NEW_LEADER_ECHO}",
            CAS_SLOT3: f"第2行 → {NEW_SLOT3_ECHO}（行首 Ⓜ）",
            CAS_SLOT4: f"追加第3行 → {NEW_SLOT4_ECHO}",
            "wording": "无上限按裁决 §3 写到效果为止（不写「最多99层」「可无限累积」，critic C04/C05 方案B）",
        },
        "kept": {
            f"ability:{ABILITY3}#0 / leader_ability:{LEADER_KEY}#4": "只产回响层数（设计稿 keep）",
            f"ability:{CID}2 / {ABILITY3}#2 / {CID}6#2": "有限成长（限 25 次 / 封顶 5 层）",
            f"ability:{CID}6#1 等充能/加槽": "口径 A.6：本批不动",
        },
        "generator": "wf_midautumn_kit_hibiki.py（LEADER/PLAN[3]/PLAN[4]/PANEL_*/build_invoke_tree 已同步）",
        "capabilities": [],
        "runtime_verified": False,
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/hibiki.json"
PANEL_REL = BATCH / "rework1/panel/hibiki.json"

MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27：第二批平衡——回响每层的无上限成长（PF伤害/攻击力各25%/层）搬进队长并放缓到2.5%/层，"
               "能力3/能力4原位换成封顶10层的10%/5%（攻击力那条的文案随行回到能力4）；"
               "队长累计命中每4次自身攻击力＋50%→＋5%；冲刺/施技PF追击每次削韧25→1。")
DEVIATION_NOTES = {
    "D-13": "2026-09-27 第二批平衡：槽4的回响攻击力行换成封顶10层×5%，文案随行移到能力4第3行，"
            "「文案挂能力3」不再适用；无上限部分在队长（每层2.5%）。",
    "D-17": "2026-09-27 第二批平衡：固有上限仍为99；能力侧每层成长封顶10层（c102=10），"
            "无上限部分只在队长两行 during134（c100=99）与队长累计命中行（c32=(None)）。",
}


def _lines(entries: list[dict], texts) -> list[dict]:
    """按文本重排镜像行：原文不变的行保留原记录，新增/改动的行标 ``changed``。"""
    old = {entry["text"]: entry for entry in entries}
    return [old[text] if text in old else {"text": text, "status": "changed"} for text in texts]


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_hibiki as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan_rework1"]
    plan["leader_rows"] = K.LEADER_ROWS
    plan["ability_records"] = K.ABILITY_RECORDS
    plan["ability_rows_by_slot"] = {str(slot): len(K.PLAN[slot]) for slot in range(1, 7)}
    plan["leader_records"] = [
        {"index": index, "donor": addr, "source": source,
         "cells": {str(col): value for col, value in sorted(cells.items())}, "describe": expect}
        for index, (addr, source, cells, expect) in enumerate(K.LEADER)]
    design["rework1"][MIRROR_TAG] = dict(
        spec="第二批施工口径 A（无上限成长搬队长并按3分钟实际次数放缓）+ B.3（CT≤3秒的629每次削韧≤1）",
        changed=[
            f"队长#{HIT_ROW} 累计命中每4次自身攻击力 50%→5%（仍不限次）",
            f"队长新增#10/#11：回响每层自身PF伤害/攻击力 2.5%（原能力3#{PFDMG_ROW}/能力4#{ATK_ROW}的[5:]，25%×1/10）",
            f"槽3#{PFDMG_ROW} 回响每层PF伤害 25%/限99 → 10%/限10",
            f"槽4#{ATK_ROW} 回响每层攻击力 25%/限99 → 5%/限10",
            f"629 追击树 CreateNormalAttack p13 {DOWN_OLD}→{DOWN_NEW}（3+1段，每次25→1）",
        ],
        kept=["能力3#0 / 队长#4 只产回响层数", "能力2（限25次）、能力3#2 与能力6#2（封顶5层）",
              "所有充能/加槽行（口径 A.6）", "722 三档与技能两档 DSL"],
        donor_pin="队长#0（722）的 donor 菲莉亚159996#3 本批改 c49/c50；生成器已按 live 值钉死该 donor 全部非空列，#0 输出不变",
        frequency="回响3分钟约99层、累计命中约30–75次 ⇒ 均 ≥30 ⇒ ×1/10",
        panel={CAS_LEADER: list(NEW_LEADER_LINES), CAS_SLOT3: list(NEW_SLOT3_LINES),
               CAS_SLOT4: list(NEW_SLOT4_LINES)},
        module="mod-tools/wf_balance_20260927b_hibiki.py",
    )
    for entry in design.get("deviations", []):
        if entry.get("id") in DEVIATION_NOTES:
            entry[MIRROR_TAG] = DEVIATION_NOTES[entry["id"]]
    problems = K.design_problems(design)
    if problems:
        raise HibikiBalanceError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = _lines(panel["leader"]["lines"], K.PANEL_LEADER.split("\n"))
    for block in panel["abilities"]:
        slot = int(block["index"])
        block["lines"] = _lines(block["lines"], K.PANEL_ABILITY[slot].split("\n"))
    notes_ = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27：第二批平衡")]
    panel["notes"] = notes_ + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾换行（两份镜像在本机是 indent=2、LF、末尾换行）。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    second = raw.split(b"\n", 2)[1]
    indent = len(second) - len(second.lstrip(b" "))
    text = json.dumps(value, ensure_ascii=False, indent=indent or 2)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    paths = tuple(root / rel for rel in rels)
    before = [_load(path) for path in paths]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for path, old, new in zip(paths, before, after):
            if old != new:
                _save(path, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))
