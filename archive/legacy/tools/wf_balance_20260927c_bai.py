# -*- coding: utf-8 -*-
"""白「盛夏的咆哮」149990 ``white_tiger_summer``：2026-09-27 平衡调整第三轮（c）——成长复核（只改数值）+ 面板同条件合并。

依据（主会话施工口径 growth_c_spec.md，作者原话逐字转述）：「成长速度砍到1/10不合理，现在本来就算是正常偏快
而已，砍太多了」「砍到4/5,或者7/10这样吧,很多角色没有成长完全没用了」「可以砍到2/3」「数值尽量取5的倍数比如36就
变成35,39就变成40」；口径 D3（只改表里列出的行的数值，不新增共鸣前置）。数值表 ``reeval_full.json``
table.rows「白·夏日 149990」：队长 L#3/L#4 原 50% / 批二 5% / 建议 35%（2/3 档：50×2/3=33.3，向上取 5 的倍数）。

输入基线 = 当前 live（本地链尾 1.4.1053，= 第二批 ``wf_balance_20260927b_bai`` 输出逐字；1.4.1054 灰服三角色替换
未碰本角色，BEFORE 两项在 1.4.1054 复核逐字相同）。

改动（其余行逐字保留）：

1. ``leader_ability:149990`` #3 / #4（trigger 248 FeverFrame，全场累计 Fever 帧每满 90 帧 = 每 1.5 秒一次，
   c32=(None) 不设限）：c49/c50 5000 → 35000，即风队攻击力（kind 32）/ 能力伤害（kind 388）每跳 +5% → +35%。
   3 分钟约 87 跳（72–102）：原 4350% / 第二批 435% / 本轮 3045%（2520–3570%）。
2. 面板 ``desc_override_white_tiger_summer`` 第 5 行同步「＋5%」→「＋35%」（两处）。
3. 面板同条件合并（作者「同一个条件的提升能不能写到一起来简化描述」；主会话合并规则）：原第 3/4 行
   ← 队长 #1（风队技能槽最大值 kind 245）/#2（Fever 时间 kind 56），两行除效果列（c45 kind / c46 对象 / c47 属性组 /
   c49–c50 数值）外逐列相同（风属性 6 人共鸣、瞬发、无触发、无次数上限）⇒ 合并为一行放在第 3 行位置：
   「风属性共鸣时，风属性角色技能槽最大值＋50%，FEVER时间＋50%」（各效果原措辞与数值保留，只省略重复条件）。
   面板由 6 行变 5 行。共鸣省略：本角色两个固有状态「假日」1499900（技能 DSL 授予，无共鸣）、「晒伤」1499901
   （能力3#3 授予，无共鸣）都有不带共鸣的来源，不省略任何「风属性共鸣时，」。其余能力 1–6 覆盖面板没有要合并的组
   （能力3 #0/#1 已在同一行；能力4「战斗开始时」一次性充能与常驻攻击力文案条件不同，按规则不并），不返回。

4. 技能强化文案规范（作者原话「角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述
   强化后的效果,规范并简化描述」；主会话口径 R1–R4）：能力1 #1（I536 旗号 1，前置 风 6 人共鸣）的条目
   ``change_skill_white_tiger_summer`` 与能力1 面板第 2 行统一为官方格式
   「强化『盛夏咆哮』：追加全队贯穿与最大速度固定效果，对最近的敌人追加能力伤害，并强制赋予自身无法消除的「假日」」
   （CAS 不带共鸣前缀；面板行保留开关行真实前置「风属性共鸣时，」，其余两行逐字）。依据：两档技能树唯一的
   ConditionalsChangeSkillFlag(1) 关支为空，开支 = FindAllSubjects(33) 贯穿 + FindAllSubjects(82) 最大速度固定 +
   自身「假日」1499900（强制）+ 最近敌人追加一击（:func:`enhancement_basis_problems`，fail closed）。
   技能描述（action_skill / character_text / 服务端）不含强化后的效果，不读不改。

不改：队长 #0（进 Fever 风队技能槽充能，口径 A.6）、#1/#2/#5；两档技能树与三档 PF 树（第二批 Down 修订保持，
本模块只读核对旗号 1 分支）；技能描述 / character_text（不含该成长数值，也不含强化后的效果）；能力1 数据行。
本角色没有队长行生成器（历史构建脚本是快照，禁止重跑；``wf_summer_bai_ability`` / ``wf_summer_bai_fever_damage``
只改技能树，不碰队长行与面板文字），无需同步生成器；队长面板、能力1 面板与旗号 1 条目文字在 mod-tools 下只有
第二批 / 本模块两个写入源（本模块是现行写入源）。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as legality
import wf_midautumn_kitlib as kitlib   # 面板规则（禁语、恒真条件文本等）

CID = "149990"
CODE = "white_tiger_summer"
PACKAGES = ["white_tiger_summer"]
PACKAGE_VERSION = {"white_tiger_summer": "1.0.4"}     # 候选 manifest 现值 1.0.3（第二批回写）→ 1.0.4
CAPABILITIES: list[str] = ["panel-description-override-v2"]   # desc_override 队长面板生效所需（核对 minor：第二批漏声明）
REVIEWED_DRIFT: dict = {}     # 候选只读打开无漂移；队长 / 面板候选与 live 逐字一致
ELEMENT = 3                   # master/character c3：风（0 基内部元素）

LEADER = CID
CAS_LEADER = "desc_override_" + CODE
LEADER_NCOLS = 124

#: 0 基行号 → 内容 kind（c45）。两行同触发、不同 kind，不合并。
FEVER_TICK_ROWS = {3: "32", 4: "388"}
FEVER_TICK_OLD, FEVER_TICK_NEW = "5000", "35000"
#: 表 reeval_full.json 149990 L#3/L#4：原 50% / 批二 5% / 建议 35%。
FEVER_TICK_TABLE = {"original": "50000", "batch2": FEVER_TICK_OLD, "suggested": FEVER_TICK_NEW}
#: 两行的逐格指纹（全部非空列；其余列必须为空串），强度列另给。
_FEVER_TICK_CELLS = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: "Green", 11: "0", 18: "0",
    25: "248", 28: "9000000", 29: "9000000", 32: "(None)", 33: "0", 37: "(None)", 44: "0",
    46: "5", 47: "Green",
}


def fever_tick_cells(kind: str, strength: str) -> dict[int, str]:
    return {**_FEVER_TICK_CELLS, 45: kind, 49: strength, 50: strength}


FEVER_TICK_ESTIMATE = {
    "trigger": "leader c25=248 FeverFrame，c28/c29=9000000 ⇒ 全场累计 Fever 帧每满 90 帧（1.5 秒）一次，不归零",
    "three_minutes": "Fever 15 秒 ×1.5（队长 #2），724 续时（队长每 35 连击 +35%、假日中技能 +35%）；"
                     "覆盖 60–85% ⇒ 72–102 跳，按 87 跳算（表中推断）",
    "tier": "易触发且有 500% 级基础（能力3 假日每 2 秒 +50%×10、能力4 +100%、能力1#2 独立能伤 +20%）"
            "⇒ 取作者给的下限档 2/3：50×2/3=33.3 → 向上取 5 的倍数 35%（实际 0.7）",
}

PANEL_LINE_INDEX = 4
PANEL_OLD_LINE = "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋5%、能力伤害＋5%"
PANEL_NEW_LINE = "风属性共鸣时，FEVER模式中每持续1.5秒，风属性角色攻击力＋35%、能力伤害＋35%"
PANEL_LINES = 6

#: live 面板（第二批输出，6 行）。
PANEL_LINES_BEFORE = (
    "赋予专属强化弹射：格斗型＋特殊型强化弹射同时生效",
    "风属性共鸣时，风属性角色进入FEVER模式时技能槽充能速度＋100%",
    "风属性共鸣时，风属性角色技能槽最大值＋50%",
    "风属性共鸣时，FEVER时间＋50%",
    PANEL_OLD_LINE,
    "每达成35连击，自身FEVER槽＋35%",
)
#: 数值稿（本轮成长数值，未合并）：只换第 5 行；是面板合并校验（wf_panel_merge_check）的原文。
PANEL_LINES_NUMERIC = (PANEL_LINES_BEFORE[:PANEL_LINE_INDEX] + (PANEL_NEW_LINE,)
                       + PANEL_LINES_BEFORE[PANEL_LINE_INDEX + 1:])
#: 同条件合并：数值稿 0 基第 2/3 行 ← 队长 #1/#2（数据条件逐列相同，见 MERGE_ROWS）。
MERGE_LINES = (2, 3)
MERGE_ROWS = (1, 2)
MERGED_LINE = "风属性共鸣时，风属性角色技能槽最大值＋50%，FEVER时间＋50%"
PANEL_LINES_AFTER = PANEL_LINES_NUMERIC[:MERGE_LINES[0]] + (MERGED_LINE,) + PANEL_LINES_NUMERIC[MERGE_LINES[-1] + 1:]
#: 共鸣省略：本角色固有状态及其获取来源（live 1.4.1054 全部队长/能力表 + 1476 个可枚举 DSL 只读扫描，
#: 与主会话 scan.json all_states 一致）；两者都有不带共鸣的来源 ⇒ 不省略。
RESONANCE_OMISSION: dict[str, dict] = {}
STATES_NOT_OMITTED = {
    "1499900": {"name": "假日", "sources": ["skill DSL white_tiger_summer_1/_2（无共鸣）"]},
    "1499901": {"name": "晒伤", "sources": ["ability:1499903#3 kind413（前置：主位 + 假日，无共鸣）"]},
}
#: 队长行效果列 = 瞬发内容块 c45–c82，扣除仍属「条件」的后缀限定列
#: （持续帧、次数、累积上限、弹射/强化弹射次数上限、结束条件、按触发者计数）。
_LEADER_EFFECT_COLS = frozenset(range(45, 83)) - {55, 56, 59, 60, 61, 62, 63, 70}


def same_condition(a: list[str], b: list[str]) -> bool:
    """两条队长行除效果列外逐列相同（前置 / 触发 / CT / 次数上限 / 觉醒列 / 后缀限定）。"""
    return len(a) == len(b) == LEADER_NCOLS and all(
        x == y for c, (x, y) in enumerate(zip(a, b)) if c not in _LEADER_EFFECT_COLS)

# ------------------------------------------------------------------ 技能强化条目（能力1 I536 旗号 1）

SKILL_NAME = "盛夏咆哮"
ABILITY1_KEY = CID + "1"
ABILITY_NCOLS = 126
CAS_SWITCH = "change_skill_" + CODE
CAS_A1 = CAS_LEADER + "_1"
MAIN_ICON = " <icon id='main'>  "
RESONANCE_PREFIX = "风属性共鸣时，"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
SWITCH_TEXT_BEFORE = "风属性共鸣时，强化技能『盛夏咆哮』：追加效果与能力伤害，并强制赋予自身无法消除的「假日」"
#: 官方格式「强化『<技能名>』：<定性说明>」：点名技能、不写数字；共鸣是开关行前置，只写在面板行。
SWITCH_TEXT = "强化『盛夏咆哮』：追加全队贯穿与最大速度固定效果，对最近的敌人追加能力伤害，并强制赋予自身无法消除的「假日」"
A1_LINES_BEFORE = (
    MAIN_ICON + "战斗开始时，自身技能槽＋50%",
    MAIN_ICON + SWITCH_TEXT_BEFORE,
    MAIN_ICON + "「假日」期间，风属性角色对敌人造成的能力伤害额外乘区＋20%（技能斩击本体除外）",
)
A1_SWITCH_LINE = 1
A1_LINES_AFTER = (A1_LINES_BEFORE[0], MAIN_ICON + RESONANCE_PREFIX + SWITCH_TEXT, A1_LINES_BEFORE[2])
#: 旗号 1 开支（两档技能树）的状态 / 攻击签名：全队（33）贯穿、主小队（82）最大速度固定、自身「假日」（强制付与）、
#: 最近敌人追加一击；关支为空。
HOLIDAY_UID = 1499900
FLAG1_SIGNATURE = (
    ("FindAllSubjects", 33), ("CreateCondition", "ACPiercing"),
    ("FindAllSubjects", 82), ("CreateCondition", "ACFixedSpeed"),
    ("CreateCondition", "ACUnique", HOLIDAY_UID, "force"),
    ("FindNearSubjects",), ("CreateNormalAttack",),
)
#: R3：强化后的效果只写在强化条目里；强化条目不用「强化技能」泛称。
ENHANCED_PHRASES = ("不受此限", "强化后", "强化自身技能", "强化技能")

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数，stage_batch.make_read(live_only=True)）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", LEADER): "28b2e71be185e7e7fe7a0def2b940f252d7f065106d91d46843bad3775aa9f12",
    ("cas", CAS_LEADER): "f9c03a681a914daa29f97ed8283abcda62ad83c0cf6a25185f95c1482991270f",
    # 技能强化文案规范新增（live 1.4.1054 只读取数；第二批未触碰）：旗号 1 条目、能力1 面板与其数据依据。
    ("cas", CAS_SWITCH): "d9f1927643d7df25c2a820c638255c28ee2f3923266916dc5db19e59c6cb914f",
    ("cas", CAS_A1): "a9242ac6f3d22c25fa30205b5dc3ae56531894f6d6513f3cd47a97dad25756f8",
    ("ability", ABILITY1_KEY): "e35cc54c3362a31e38ddbd32ed3e54267f6b27437ac721a28f3542a343c111c9",
    ("dsl", PROGRAMS["1"]): "d5ae598a80368415b0c367cab29a2c9cd860fca2f53d0211d2feb03fb7764d5a",
    ("dsl", PROGRAMS["2"]): "f8405d8ee643adb8f9c9b0293117a1a2b2e54401f92b2a1f450256c0d5e4aa7a",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    """读取并锁定全部输入；任何一项漂移或缺失都拒绝（fail closed）。"""
    inputs = {}
    for kind, key in BEFORE:
        value = read(kind, key)
        if value is None or digest(value) != BEFORE[kind, key]:
            raise ValueError(f"unreviewed live baseline: {kind}:{key}")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == LEADER_NCOLS
            and all(row[c] == v for c, v in cells.items())
            and all(v == "" for c, v in enumerate(row) if c not in cells))


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """只改 #3/#4 的 c49/c50（5000 → 35000）；其余 4 行与两行其余列逐字保留。"""
    if len(rows) != 6 or any(len(row) != LEADER_NCOLS for row in rows):
        raise ValueError("unexpected leader_ability shape")
    out = deepcopy(rows)
    for index, kind in FEVER_TICK_ROWS.items():
        if not _matches(rows[index], fever_tick_cells(kind, FEVER_TICK_OLD)):
            raise ValueError(f"unexpected preimage for leader #{index} (Fever tick {kind})")
        out[index][49] = out[index][50] = FEVER_TICK_NEW
        if not _matches(out[index], fever_tick_cells(kind, FEVER_TICK_NEW)):
            raise AssertionError("leader_rows touched more than c49/c50")
    gauge = out[0]
    if (gauge[25], gauge[45], gauge[46], gauge[49], gauge[50]) != ("8", "35", "5", "100000", "100000"):
        raise ValueError("leader #0 (enter Fever → wind gauge charge 100%) drifted; charge rows stay untouched")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != sorted(FEVER_TICK_ROWS):
        raise AssertionError("leader_rows touched another record")
    return out


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    """live 6 行 → 数值稿（第 5 行 ＋35%）→ 同条件合并（第 3/4 行并为一行），共 5 行。"""
    lines = _single_text(rows, CAS_LEADER).split("\n")
    if len(lines) != PANEL_LINES or lines[PANEL_LINE_INDEX] != PANEL_OLD_LINE \
            or tuple(lines) != PANEL_LINES_BEFORE:
        raise ValueError(f"{CAS_LEADER}: unexpected panel text layout")
    return [["\n".join(PANEL_LINES_AFTER)]]


def merge_problems(rows: list[list[str]]) -> list[str]:
    """合并依据（按数据）：被并的两行条件逐列相同；数值稿其余相邻行不与它们同条件（不漏并）。"""
    first, second = (rows[i] for i in MERGE_ROWS)
    problems = []
    if not same_condition(first, second):
        problems.append(f"leader #{MERGE_ROWS[0]}/#{MERGE_ROWS[1]}: conditions differ, lines must not merge")
    if (first[45], first[49], second[45], second[49]) != ("245", "50000", "56", "50000"):
        problems.append("merged rows are not (skill gauge max 50%, Fever time 50%)")
    others = [i for i in range(len(rows)) if i not in MERGE_ROWS and same_condition(rows[i], first)]
    if others:
        problems.append(f"leader rows {others} share the merged condition but are not merged")
    return problems


def switch_text(rows: list[list[str]]) -> list[list[str]]:
    """旗号 1 条目：live「风属性共鸣时，强化技能『盛夏咆哮』：…」→ 官方格式（去共鸣前缀、点名技能、写明追加效果）。"""
    if _single_text(rows, CAS_SWITCH) != SWITCH_TEXT_BEFORE:
        raise ValueError(f"{CAS_SWITCH}: unexpected text")
    return [[SWITCH_TEXT]]


def a1_text(rows: list[list[str]]) -> list[list[str]]:
    """能力1 面板（主位槽）：第 2 行 = 图标 +「风属性共鸣时，」+ 条目；第 1 / 3 行逐字。"""
    if tuple(_single_text(rows, CAS_A1).split("\n")) != A1_LINES_BEFORE:
        raise ValueError(f"{CAS_A1}: unexpected panel text layout")
    return [["\n".join(A1_LINES_AFTER)]]


def _commands(node, out: list | None = None) -> list[list]:
    out = [] if out is None else out
    if isinstance(node, list):
        if len(node) == 2 and node[0] == "Command" and isinstance(node[1], list) and node[1] \
                and isinstance(node[1][0], str):
            out.append(node[1])
        for child in node:
            _commands(child, out)
    elif isinstance(node, dict):
        for child in node.values():
            _commands(child, out)
    return out


def _flag_signature(args) -> tuple:
    if args[0] == "FindAllSubjects":
        return ("FindAllSubjects", args[2])
    if args[0] == "CreateCondition":
        kinds = [c[0] for c in args[2]]
        if kinds == ["ACUnique"]:
            return ("CreateCondition", "ACUnique", args[2][0][1], "force" if args[12] is True else "normal")
        return ("CreateCondition", *kinds)
    return (args[0],)


def enhancement_basis_problems(ability1: list[list[str]], trees: dict[str, Any]) -> list[str]:
    """旗号 1 条目的数据依据（fail closed）：能力1 唯一的技能开关行是 #1 I536（前置 风 6 人共鸣，c70 = 条目键）；
    两档技能树各只有一个 ConditionalsChangeSkillFlag(1)，关支为空，开支签名 == :data:`FLAG1_SIGNATURE`。"""
    problems: list[str] = []
    switches = [i for i, row in enumerate(ability1)
                if row[5] == "0" and row[47] in ("536", "704", "705", "706", "707", "708")]
    if switches != [A1_SWITCH_LINE]:
        problems.append(f"ability {ABILITY1_KEY}: skill-flag rows {switches} != reviewed [#{A1_SWITCH_LINE}]")
    else:
        row = ability1[A1_SWITCH_LINE]
        if len(row) != ABILITY_NCOLS or row[47] != "536" or row[70] != CAS_SWITCH:
            problems.append(f"ability {ABILITY1_KEY}#{A1_SWITCH_LINE} is not the I536 switch of {CAS_SWITCH}")
        if (row[6], row[9], row[10], row[11], row[13], row[20]) != ("2", "600000", "600000", "Green", "0", "0"):
            problems.append(f"ability {ABILITY1_KEY}#{A1_SWITCH_LINE}: precondition is not exactly wind resonance "
                            f"(panel line keeps 「{RESONANCE_PREFIX}」 only on that basis)")
    for program, tree in trees.items():
        flags = [a for a in _commands(tree) if a[0].startswith("ConditionalsChangeSkill")]
        if [(a[0], a[1]) for a in flags] != [("ConditionalsChangeSkillFlag", 1)]:
            problems.append(f"{program}: expected exactly one ConditionalsChangeSkillFlag(1), got "
                            f"{[(a[0], a[1]) for a in flags]}")
            continue
        on, off = flags[0][2], flags[0][3]
        if _commands(off):
            problems.append(f"{program}: flag-1 off-branch is not empty (the entry only describes additions)")
        signature = tuple(_flag_signature(a) for a in _commands(on) if a[0] in (
            "FindAllSubjects", "CreateCondition", "FindNearSubjects", "CreateNormalAttack"))
        if signature != FLAG1_SIGNATURE:
            problems.append(f"{program}: flag-1 branch {signature} is not what {CAS_SWITCH} describes")
    return problems


def text_problems(texts: dict[str, str]) -> list[str]:
    """R2 / R3：条目官方格式、点名技能、不写数字；面板第 2 行 = 图标 +「风属性共鸣时，」+ 条目；其余行不写强化后的效果。"""
    problems: list[str] = []
    switch, panel = texts[CAS_SWITCH], texts[CAS_A1].split("\n")
    problems += [f"{CAS_SWITCH}: {p}" for p in kitlib.panel_problems(switch, skill_flag=True)]
    problems += [f"{CAS_A1}#{A1_SWITCH_LINE}: {p}"
                 for p in kitlib.panel_problems(panel[A1_SWITCH_LINE].replace(MAIN_ICON, ""), skill_flag=True)]
    if not switch.startswith(f"强化『{SKILL_NAME}』："):
        problems.append(f"{CAS_SWITCH}: skill-flag entry must read 「强化『{SKILL_NAME}』：…」")
    if panel[A1_SWITCH_LINE] != MAIN_ICON + RESONANCE_PREFIX + switch:
        problems.append(f"{CAS_A1}: panel entry of {CAS_SWITCH} must read 「{RESONANCE_PREFIX}{switch}」")
    for key, text in texts.items():
        problems += [f"{key}: {p}" for p in kitlib.panel_problems(text)]
        for phrase in ENHANCED_PHRASES:
            if phrase in text:
                problems.append(f"{key}: {phrase!r}（强化条目点名『{SKILL_NAME}』，强化后的效果只写在强化条目里）")
        if "／" in text or "共鸣时：" in text or "自身为队长时" in text:
            problems.append(f"{key}: 多条不用「／」、共鸣写「X属性共鸣时，」、不写「自身为队长时」")
    if any(not line.startswith(MAIN_ICON) for line in panel):
        problems.append(f"{CAS_A1}: main-position slot lines keep the main icon")
    return problems


def row_problems(row: list[str]) -> list[str]:
    return (legality.client_legality_problems("leader_ability", row)
            + legality.declared_block_field_problems("leader_ability", row)
            + legality.invoke_skill_string_problems(row, set(), "leader_ability")
            + legality.ability_element_column_problems("leader_ability", row, ELEMENT))


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    leader = {LEADER: leader_rows(inputs["leader", LEADER])}
    cas = {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]),
           CAS_SWITCH: switch_text(inputs["cas", CAS_SWITCH]), CAS_A1: a1_text(inputs["cas", CAS_A1])}

    problems = [f"leader {LEADER}#{i}: {p}" for i, row in enumerate(leader[LEADER])
                for p in row_problems(row)]
    problems += [f"merge {CAS_LEADER}: {p}" for p in merge_problems(leader[LEADER])]
    problems += [f"panel {CAS_LEADER}: {p}" for p in kitlib.panel_problems(cas[CAS_LEADER][0][0])]
    if "／" in cas[CAS_LEADER][0][0]:
        problems.append(f"panel {CAS_LEADER}: 多条不用「／」")
    if "共鸣时：" in cas[CAS_LEADER][0][0] or "自身为队长时" in cas[CAS_LEADER][0][0]:
        problems.append(f"panel {CAS_LEADER}: 共鸣写「X属性共鸣时，」且不写「自身为队长时」")
    problems += [f"enhancement basis: {p}" for p in enhancement_basis_problems(
        inputs["ability", ABILITY1_KEY], {program: inputs["dsl", program] for program in PROGRAMS.values()})]
    problems += [f"skill-flag text: {p}" for p in text_problems({key: rows[0][0] for key, rows in cas.items()})]
    caps = sorted({c for row in leader[LEADER] for c in legality.required_client_capabilities("leader_ability", row)}
                  | {c for key in cas
                     for c in legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key])})
    if caps != sorted(CAPABILITIES):
        problems.append(f"capabilities {caps} != {CAPABILITIES}")
    if problems:
        raise ValueError("; ".join(problems))
    return {
        "ability": {}, "leader": leader, "cas": cas, "text": {}, "table": {},
        "action": {}, "dsl": {}, "server_text": {}, "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 白「盛夏的咆哮」（夏日，风）",
            "source": "mod-tools/wf_balance_20260927c_bai.py",
            "basis": ["growth_c_spec.md（作者原话 3–6；D3）", "reeval_full.json table.rows 149990"],
            "growth": {
                f"leader_ability:{LEADER}#3": "248 FeverFrame 每1.5秒 → 风队攻击力(32) 5000→35000，c32=(None) 保持",
                f"leader_ability:{LEADER}#4": "248 FeverFrame 每1.5秒 → 风队能力伤害(388) 5000→35000，c32=(None) 保持",
                "frequency": FEVER_TICK_ESTIMATE,
                "three_minutes_87_ticks": {"original": "4350%（3600–5100%）", "batch2": "435%",
                                           "batch3": "3045%（2520–3570%）"},
                "panel": {CAS_LEADER: f"第5行：{PANEL_OLD_LINE} → {PANEL_NEW_LINE}"},
            },
            "panel_merge": {
                "rule": "作者「同一个条件的提升能不能写到一起来简化描述」：同一面板数据条件逐列相同的行合并为一行，"
                        "效果原措辞与数值保留，只省略重复条件；合并行放在组首行位置",
                CAS_LEADER: {
                    "merged": {"lines_before": [PANEL_LINES_NUMERIC[i] for i in MERGE_LINES],
                               "line_after": MERGED_LINE,
                               "rows": [f"leader_ability:{LEADER}#{i}" for i in MERGE_ROWS],
                               "same_condition": "风·编成≥6、瞬发无触发、无次数上限；只差效果列 c45/c46/c47/c49/c50"},
                    "lines": f"{len(PANEL_LINES_NUMERIC)} → {len(PANEL_LINES_AFTER)}",
                    "check_merge": "数值稿 → 终稿过 mod-tools/wf_panel_merge_check.check（无 prefix_drops），见测试",
                },
                "resonance_omission": {"omitted": [], "not_omitted": STATES_NOT_OMITTED},
                "other_panels": "能力1–6 覆盖面板没有要合并的组、无可省略共鸣，不返回（能力3 #0/#1 已在同一行；"
                                "能力4「战斗开始时」一次性充能与常驻攻击力文案条件不同，见 scan skipped_groups）",
            },
            "skill_flag_text_rule": {
                "author": "角色调整时技能都强化效果只在队长技或者能力里面按照格式写就行,技能里面不要重复描述强化后的效果,"
                          "规范并简化描述做了吗",
                CAS_SWITCH: f"{SWITCH_TEXT_BEFORE} → {SWITCH_TEXT}",
                CAS_A1: {"L2": f"{A1_LINES_BEFORE[A1_SWITCH_LINE]} → {A1_LINES_AFTER[A1_SWITCH_LINE]}",
                         "L1/L3": "逐字"},
                "basis": f"ability:{ABILITY1_KEY}#{A1_SWITCH_LINE} I536（前置 风 6 人共鸣，c70={CAS_SWITCH}）；两档技能树唯一的 "
                         "ConditionalsChangeSkillFlag(1)：关支为空，开支 = FindAllSubjects(33) ACPiercing + "
                         "FindAllSubjects(82) ACFixedSpeed + 自身 ACUnique 1499900（强制付与）+ 最近敌人追加一击"
                         "（enhancement_basis_problems，fail closed）",
                "wording": "「最大速度固定」同校园希尔媞能力6 措辞；「能力伤害」「强制赋予自身无法消除的「假日」」沿用 live 原文",
                "skill_description": "action_skill / character_text / 服务端 不含强化后的效果，不读不改",
            },
            "candidate_preexisting_drift": {
                f"custom_ability_string:{CAS_A1}": "候选仍是加主位图标前的文案（live 已有图标）；暂存整键替换 ⇒ 候选收敛为本轮输出",
                f"ability:{ABILITY1_KEY}": "候选三行 c1 仍为 true（live 主位 false）；本模块只读不返回该键，候选保持原样（未修）",
            },
            "kept": {
                f"leader_ability:{LEADER}#0": "进 Fever 风队技能槽充能 +100%（kind35），口径 A.6 不动",
                "skill_pf_down": "两档技能 / 三档 PF 树第二批 Down 修订保持，本轮不读不写",
                "descriptions": "技能描述 / character_text / 服务端 character_text 不含该成长数值与强化后的效果",
                f"ability:{ABILITY1_KEY}": "数据行只读（旗号 1 条目依据），不返回",
            },
            "generators": "无队长行生成器（历史构建脚本为快照，禁止重跑）；wf_summer_bai_* 只改技能树",
            "runtime_verified": False,
        },
    }
