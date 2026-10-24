# -*- coding: utf-8 -*-
"""索利兹 129986 ``soriz``：2026-09-27 平衡调整第三轮（c，成长复核）。

作者口径（主会话逐字转述，施工口径 ``growth_c_spec.md``）：「成长速度砍到1/10不合理……砍太多了」→「砍到4/5，
或者7/10这样吧」→「可以砍到2/3」→「数值尽量取5的倍数」。第二批（``wf_balance_20260927b_gbf`` 的索利兹单元）
把队长三羽乌逐层成长放缓到 1/5；本轮按成长复核表（``reeval_full.json`` table.rows，行号 0 起）回调，只改数值。

规格（队长行号 0 起，与复核表一致）：
1. 队长 L#9 / L#10（during 134 每层「三羽乌」→ 自身攻击力 kind 0 / 自身强化弹射伤害 kind 23，不设上限）：
   c111/c112 20000 → 70000（每层 +20% → +70%）。原值 100%，2/3 档：100×2/3=66.7，向上取 5 的倍数 70%
   （实际 0.7，不低于 2/3 下限）。
2. 队长 L#11（每层三羽乌 → 自身强化弹射独立乘区 kind 413）：c111/c112 500 → 2000（+0.5% → +2%）。
   原值 3%，2/3 档：3×2/3=2.0，恰为下限；原值 ≤10%，不取 5 的倍数。
3. 面板 ``desc_override_soriz_leader`` 第 2 行同步数字（数值稿 :data:`NUMERIC_LEADER_LINES`）。
4. 面板口径（暂存前最后一轮文字修正；作者「同一个条件的提升能不能写到一起来简化描述」，主会话口径 1/4/5 与追加
   A/B/D）。数值稿 8 行 → 终稿 11 行（:data:`NEW_LEADER_LINES`），每处改写都由数据只读核对（:func:`panel_basis_problems`）。
   下列 L 行号 = live / 数值稿 8 行的行号：
   - L2（A，口径 1 扩到同形写法）：「自身攻击力+70%、强化弹射伤害+70%」→「，强化弹射伤害」，不补对象（#9 kind 0 自身 →
     #10 during 23）；其后「、强化弹射伤害额外+2%（独立乘区）」（#11 413）接在同为强化弹射伤害、不带对象的一项后面，保留「、」。
   - L3（B，口径 5 按数据条件拆行）：原文一行挤了四种数据条件 → 拆 4 行，各带「水属性共鸣时，FEVER模式中，」
     （四组数据都带水编成≥6 前置，共鸣是真实条件）：禁疗 = 队长 #5（进 Fever → 629 soriz_fever_begin 的
     FindAll 水 ACHealRejection，#6 Fever 结束解除）；强化弹射伤害+300% = #2（持续·Fever，during 23）；
     连击数+16 = #3（Fever 前置 + 每次弹射触发 → 226）；护盾与 FEVER 槽减少 = 能力3 #7/#8（水共鸣 + Fever + 队长、
     每次强化弹射触发，两行同条件仍在一行）。数值与措辞不变，只把「：」「；」换成每行的「，」「。」。
     禁疗与 L6 同出 #5，但文案写的是整个 FEVER 期间的状态（#6 结束解除），按原措辞单独成行，未并入 L6。
   - L4（B，半角「/」）：Lv1/Lv2/Lv3 是同一条 722 行（#4，水共鸣）指向的三档覆盖树，条件相同 ⇒ 不拆行，改「、」
     分项、各写各的数值（先例 wf_balance_20260927c_kuro 口径 5 分项）；三档 Fever 分支倍率 10/20/50、11+1 段 = 连击数 12、
     首个判定区时长 = 非 Fever 分支的 2 倍，按 live DSL 核对。
   - L5（D）：「&」改分项；分项后是 A 的形（自身攻击力+5%、强化弹射伤害+10%，#7 kind 0 / #8 during 23 同条件）
     ⇒ 按 A 写「，」。
   - L6（D，按口径 4）：「不死不休」获取行，来源 = 队长 #5（水编成≥6 → 629 soriz_fever_begin；live 1.4.1054 本角色
     队长/能力 1–6 行、9 棵 629、2 棵技能树、3 棵 722 覆盖树只读核对，只有 soriz_fever_begin 授予 ACUnique 12998603），
     数据带水共鸣 ⇒ 补「水属性共鸣时，」。L7/L8（消耗「不死不休」、FEVER 结束清除）是依赖该状态的行，不补。
   其余三行（L1/L7/L8）逐字不动。本模块只返回队长面板；能力2/5 面板里同样的「&」不在本轮范围，未返回。

不改（口径 D3/D4）：能力3 1299863 的封顶版（每层 15% / 10% / 1%，最多计 10 层）保持第二批值；不给这三行加共鸣前置
（live c4=0，本轮只改数值）；援护 629 / Fever 特殊 PF 的削韧、技能、主动说明、character_text 均不动。

生成器 ``wf_gbf_kit_soriz.CROWS_GROWTH`` 的队长每层值已同步；kit 的队长行 cells 与面板串读设计镜像
``work/character_packs/midautumn-20260920/design/soriz.json``，本模块提供纯函数 :func:`soriz_mirror` 与
:func:`sync_mirror`（``--write`` 才落盘）。镜像接受第二批、数值稿（本模块首版 --write）与终稿三种形态，一律重算成终稿。
测试断言生成器（配第三轮镜像）输出 == :func:`revise`。

接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（单角色导出）。本模块只读 ``read()`` 给的 live 值
并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

import wf_client_legality as L
import wf_describe
import wf_midautumn_kitlib as KL

SOURCE = "wf_balance_20260927c_soriz.py"
CID = "129986"
CODE = "soriz"
PACKAGES = ["gbf-soriz-20260919"]
PACKAGE_VERSION = {"gbf-soriz-20260919": "1.0.2"}     # 候选现值 1.0.1（第二批）
# 本轮回写 desc_override_soriz_leader（V14 面板覆盖补丁）；候选 manifest 已声明，追加是幂等并集。
CAPABILITIES = ["panel-description-override-v2"]
REVIEWED_DRIFT: dict = {}

ELEMENT = 1                                        # 水（character c3）
ABILITY3 = CID + "3"
LEADER_C0 = "soriz_leader"
CAS_LEADER = "desc_override_soriz_leader"
CROWS = "12998601"                                 # 固有「三羽乌」，上限 99
INVOKE_STRINGS = ("soriz_fever_begin", "soriz_fever_end")   # 队长 L#5/L#6 的 629 文案键（只读）
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
L_STRENGTH = (111, 112)                            # 队长 during_content 强度两格
MAIN_ICON = " <icon id='main'>  "


class SorizBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


#: 队长 L#9-#11：(行号, 内容 kind, 名称, 原值, 第二批值, 本轮值, 取整说明)。强度单位 1000 = 1%。
GROWTH = (
    (9, "0", "攻击力", 100_000, 20_000, 70_000, "100×2/3=66.7，向上取 5 的倍数 70%（实际 0.7）"),
    (10, "23", "强化弹射伤害", 100_000, 20_000, 70_000, "同 L#9（同一层数来源、同一档位）"),
    (11, "413", "独立乘区强化弹射伤害", 3_000, 500, 2_000,
     "3×2/3=2.0，恰为下限（原值 ≤10%，不取 5 的倍数）"),
)
BAND = "2/3"
#: 能力3 #1-#3 封顶版（第二批值，口径 D4 不动）：行号 → (kind, 每层, 最多计层数)。
A3_CAPPED = {1: ("0", "15000", "10"), 2: ("23", "10000", "10"), 3: ("413", "1000", "10")}


def leader_cells(index: int, strength: str) -> dict[int, str]:
    """队长 L#index 的全部非空格（强度两格取 ``strength``）。"""
    _i, kind, *_rest = next(g for g in GROWTH if g[0] == index)
    cells = {0: LEADER_C0, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
             98: "100000", 99: "100000", 100: "(None)", 102: CROWS, 106: "false", 107: kind,
             111: strength, 112: strength}
    if kind == "0":
        cells[108] = "0"
    return cells


def _cells(row: list[str]) -> dict[int, str]:
    return {i: c for i, c in enumerate(row) if c != ""}


def _expect(row: list[str], width: int, cells: dict[int, str], what: str) -> None:
    if len(row) != width or _cells(row) != cells:
        got = _cells(row) if len(row) == width else f"{len(row)} columns"
        raise SorizBalanceError(f"unexpected preimage for {what}: {got}")


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1 or not isinstance(rows[0][0], str):
        raise SorizBalanceError(f"{key}: expected one single-column row")
    return rows[0][0]


def check_ability3(rows: list[list[str]]) -> None:
    """口径 D4：能力3 封顶版保持第二批值；只读核对（不返回能力3）。"""
    if len(rows) != 11 or any(len(r) != ABILITY_NCOLS for r in rows) or {r[1] for r in rows} != {"false"}:
        raise SorizBalanceError(f"ability {ABILITY3}: expected 11x126 main-only rows")
    for index, (kind, per_layer, cap) in A3_CAPPED.items():
        row = rows[index]
        if (row[97], row[104], row[109], row[102], row[113], row[114]) != ("134", CROWS, kind, cap,
                                                                          per_layer, per_layer):
            raise SorizBalanceError(f"ability {ABILITY3}#{index}: capped batch-2 values drifted")


def soriz_leader(rows: list[list[str]], ability3: list[list[str]]) -> list[list[str]]:
    """队长 12 行：L#9/L#10 每层 20%→70%、L#11 每层 0.5%→2%；其余九行与这三行的其余格逐字不动。"""
    if len(rows) != 12 or any(len(r) != LEADER_NCOLS for r in rows):
        raise SorizBalanceError(f"leader {CID}: expected 12x124 rows (batch-2 layout)")
    if {r[0] for r in rows} != {LEADER_C0}:
        raise SorizBalanceError(f"leader {CID}: c0 drift {sorted({r[0] for r in rows})}")
    out = deepcopy(rows)
    for index, _kind, _name, _original, before, after, _rounding in GROWTH:
        _expect(rows[index], LEADER_NCOLS, leader_cells(index, str(before)), f"leader {CID}#{index}")
        # 搬行一致性：仍是能力3 #n 的队长同形行（[c0,'0',''] + 能力行[5:]），只差最多计层数与每层强度。
        formula = [LEADER_C0, "0", ""] + list(ability3[index - 8][5:])
        if [c for c in range(LEADER_NCOLS) if formula[c] != rows[index][c]] != [100, *L_STRENGTH]:
            raise SorizBalanceError(f"leader {CID}#{index}: no longer the moved copy of ability {ABILITY3}#{index - 8}")
        out[index][L_STRENGTH[0]] = out[index][L_STRENGTH[1]] = str(after)
        _expect(out[index], LEADER_NCOLS, leader_cells(index, str(after)), f"revised leader {CID}#{index}")
    changed = [(i, c) for i in range(12) for c in range(LEADER_NCOLS) if rows[i][c] != out[i][c]]
    if changed != [(g[0], c) for g in GROWTH for c in L_STRENGTH]:
        raise AssertionError(f"soriz_leader touched unexpected cells: {changed}")
    return out


# ====================================================================== 队长面板

RESONANCE_PREFIX = "水属性共鸣时，"
#: live 队长面板（= 第二批输出，8 行；BEFORE 锁定）。
OLD_LEADER_LINES = (
    "水属性角色攻击力+100%，自身强化弹射伤害+100%。",
    "每层「三羽乌」使自身攻击力+20%、强化弹射伤害+20%、强化弹射伤害额外+0.5%（独立乘区）。",
    "水属性共鸣时，FEVER模式中：水属性角色无法获得治疗；自身强化弹射伤害+300%；每次弹射的连击数+16；"
    "每次强化弹射为水属性角色提供15%最大生命值的护盾，并使FEVER槽减少（槽上限的）20%。",
    "水属性共鸣时，FEVER模式中获得特殊的强化弹射：Lv1/Lv2/Lv3倍率提升至10倍/20倍/50倍，判定时间延长，连击数12。",
    "自身生命值每减少1%，自身攻击力+5%&强化弹射伤害+10%。",
    "进入FEVER时，按自身已损失的生命值获得「不死不休」，每损失10%最大生命值1层，最多9层；"
    "已损失30%以上时，水属性角色各获得1次踏止（生命值保留1）。",
    "水属性角色受到致命伤害时，消耗3层「不死不休」并获得4秒无敌。",
    "FEVER结束时，「不死不休」与踏止全部消失。",
)
LEADER_TEXT_LINES = 8
LEADER_LINE_INDEX = 1
OLD_LEADER_LINE = OLD_LEADER_LINES[LEADER_LINE_INDEX]
#: 数值稿（本模块首版输出 = 设计镜像首版 --write 的形态）：只换第 2 行数字。
NUMERIC_LEADER_LINE = "每层「三羽乌」使自身攻击力+70%、强化弹射伤害+70%、强化弹射伤害额外+2%（独立乘区）。"
NUMERIC_LEADER_LINES = (OLD_LEADER_LINES[:LEADER_LINE_INDEX] + (NUMERIC_LEADER_LINE,)
                        + OLD_LEADER_LINES[LEADER_LINE_INDEX + 1:])

# ---- 口径 1 扩到同形写法（A）：「对象效果、强化弹射伤害」→「，强化弹射伤害」，不补对象。
#: 「、」后面的强化弹射伤害项（含「独立乘区的强化弹射伤害」）。
_PF_ITEM_AFTER_ENUM = re.compile(r"、((?:独立乘区的)?强化弹射伤害)")
#: 不带对象的强化弹射伤害项（前一项也是它时，「、」保留）。
_PF_ITEM_BARE = re.compile(r"(?:独立乘区的)?强化弹射伤害")
_ITEM_MARKS = "，；：:。、"


def _pf_joins(line: str) -> list[tuple[int, str]]:
    """每个「、强化弹射伤害…」→（「、」的位置, 前一项文字）。"""
    out = []
    for match in _PF_ITEM_AFTER_ENUM.finditer(line):
        start = max(line.rfind(mark, 0, match.start()) for mark in _ITEM_MARKS) + 1
        out.append((match.start(), line[start:match.start()]))
    return out


def pf_damage_join_problems(text: str) -> list[str]:
    """A：「、强化弹射伤害…」的前一项必须也是不带对象的强化弹射伤害项，否则应写「，」。"""
    return [f"line {number}: 「{previous}、」 joins pf damage to an effect with a target by 「、」 (use 「，」)"
            for number, line in enumerate(text.split("\n"), start=1)
            for _at, previous in _pf_joins(line) if not _PF_ITEM_BARE.match(previous)]


def join_pf_damage(line: str) -> str:
    """A：只把接在带对象效果后面的那个「、」改「，」；接在强化弹射伤害项后面的「、」逐字保留。"""
    out = list(line)
    for at, previous in _pf_joins(line):
        if not _PF_ITEM_BARE.match(previous):
            out[at] = "，"
    joined = "".join(out)
    if joined == line:
        raise SorizBalanceError(f"line is not the rule-A shape: {line}")
    return joined


# ---- 口径 5（B）：一行挤多种数据条件的拆行。
FEVER_HEAD_OLD = RESONANCE_PREFIX + "FEVER模式中："
FEVER_HEAD_NEW = RESONANCE_PREFIX + "FEVER模式中，"


def split_fever_line(line: str) -> tuple[str, ...]:
    """「水属性共鸣时，FEVER模式中：甲；乙；丙；丁。」→ 四行「水属性共鸣时，FEVER模式中，甲。」…（措辞、数值逐字）。"""
    if not (line.startswith(FEVER_HEAD_OLD) and line.endswith("。")):
        raise SorizBalanceError(f"not the Fever multi-condition line: {line}")
    items = line[len(FEVER_HEAD_OLD):-1].split("；")
    if len(items) != len(SPLIT_BASIS):
        raise SorizBalanceError(f"Fever line has {len(items)} items, expected {len(SPLIT_BASIS)}")
    return tuple(f"{FEVER_HEAD_NEW}{item}。" for item in items)


# ---- 口径 5（B）：半角「/」按等级并列、同一条 722 行（同条件）⇒ 「、」分项，各写各的数值。
_LEVEL_SLASH = re.compile(r"Lv1/Lv2/Lv3倍率提升至(\d+)倍/(\d+)倍/(\d+)倍")
PF_LEVEL_MULTIPLIERS = (10, 20, 50)


def itemize_levels(line: str) -> str:
    match = _LEVEL_SLASH.search(line)
    if not match or line.count("/") != 4 or tuple(map(int, match.groups())) != PF_LEVEL_MULTIPLIERS:
        raise SorizBalanceError(f"not the Lv1/Lv2/Lv3 slash line: {line}")
    items = "、".join(f"Lv{level}倍率提升至{value}倍" for level, value in enumerate(match.groups(), start=1))
    return line[:match.start()] + items + line[match.end():]


# ---- D：「&」改分项（分项后是 A 的形 ⇒ 「，」）；「不死不休」获取行补共鸣（口径 4）。
AMPERSAND = "&"


def replace_ampersand(line: str) -> str:
    if line.count(AMPERSAND) != 1:
        raise SorizBalanceError(f"expected exactly one {AMPERSAND!r}: {line}")
    return join_pf_damage(line.replace(AMPERSAND, "、"))


GUTS_GAIN_HEAD = "进入FEVER时，按自身已损失的生命值获得「不死不休」"


def add_resonance(line: str) -> str:
    if not line.startswith(GUTS_GAIN_HEAD):
        raise SorizBalanceError(f"not the 不死不休 gain line: {line}")
    return RESONANCE_PREFIX + line


#: 数值稿 0 基行号 →（口径, 改写）；其余行逐字保留。
LEADER_LINE_RULES: dict[int, tuple[str, Callable[[str], tuple[str, ...]]]] = {
    1: ("A（口径 1 扩到同形写法）：「自身攻击力+70%、强化弹射伤害」→「，强化弹射伤害」，不补对象；"
        "其后「、强化弹射伤害额外+2%（独立乘区）」接在强化弹射伤害项后，保留「、」",
        lambda line: (join_pf_damage(line),)),
    2: ("B（口径 5）：一行四种数据条件 → 按数据条件拆 4 行，各带「水属性共鸣时，FEVER模式中，」",
        split_fever_line),
    3: ("B（口径 5）：半角「/」按等级并列，数据是同一条 722 行（同条件）⇒ 「、」分项、各写各的数值",
        lambda line: (itemize_levels(line),)),
    4: ("D：「&」改分项；分项后是「自身攻击力+5%、强化弹射伤害」= A 的形 ⇒ 写「，」",
        lambda line: (replace_ampersand(line),)),
    5: ("D（口径 4）：「不死不休」获取行，数据 = 队长 #5 水编成≥6 ⇒ 补「水属性共鸣时，」",
        lambda line: (add_resonance(line),)),
}


def _final_lines(numeric: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(new for index, line in enumerate(numeric)
                 for new in (LEADER_LINE_RULES[index][1](line) if index in LEADER_LINE_RULES else (line,)))


#: L3 拆出的四行 → 数据依据（:func:`panel_basis_problems` 核对）。
SPLIT_BASIS = (
    "leader #5（水编成≥6，进 Fever → 629 soriz_fever_begin：FindAll 水 ACHealRejection；#6 Fever 结束解除）",
    "leader #2（水编成≥6，持续·Fever → 自身 during 23 强化弹射伤害 300%）",
    "leader #3（水编成≥6 且 Fever，每次弹射 → 自身 226 追加连击 16）",
    "ability 1299863 #7/#8（水编成≥6 且 Fever 且 队长，每次强化弹射 → 全队水 227 护盾 15% / 自身 724 Fever槽 -20%）",
)
#: 终稿（11 行）。与 :func:`_final_lines` 的推导逐字相同（导入时自检）。
NEW_LEADER_LINES = (
    "水属性角色攻击力+100%，自身强化弹射伤害+100%。",
    "每层「三羽乌」使自身攻击力+70%，强化弹射伤害+70%、强化弹射伤害额外+2%（独立乘区）。",
    "水属性共鸣时，FEVER模式中，水属性角色无法获得治疗。",
    "水属性共鸣时，FEVER模式中，自身强化弹射伤害+300%。",
    "水属性共鸣时，FEVER模式中，每次弹射的连击数+16。",
    "水属性共鸣时，FEVER模式中，每次强化弹射为水属性角色提供15%最大生命值的护盾，并使FEVER槽减少（槽上限的）20%。",
    "水属性共鸣时，FEVER模式中获得特殊的强化弹射：Lv1倍率提升至10倍、Lv2倍率提升至20倍、Lv3倍率提升至50倍，"
    "判定时间延长，连击数12。",
    "自身生命值每减少1%，自身攻击力+5%，强化弹射伤害+10%。",
    "水属性共鸣时，进入FEVER时，按自身已损失的生命值获得「不死不休」，每损失10%最大生命值1层，最多9层；"
    "已损失30%以上时，水属性角色各获得1次踏止（生命值保留1）。",
    "水属性角色受到致命伤害时，消耗3层「不死不休」并获得4秒无敌。",
    "FEVER结束时，「不死不休」与踏止全部消失。",
)
if _final_lines(NUMERIC_LEADER_LINES) != NEW_LEADER_LINES:
    raise AssertionError("final leader panel is not the rule-derived rewrite of the numeric draft")
NEW_LEADER_LINE = NEW_LEADER_LINES[LEADER_LINE_INDEX]
OLD_LEADER_TEXT = "\n".join(OLD_LEADER_LINES)
NUMERIC_LEADER_TEXT = "\n".join(NUMERIC_LEADER_LINES)
NEW_LEADER_TEXT = "\n".join(NEW_LEADER_LINES)


def soriz_leader_text(rows: list[list[str]]) -> list[list[str]]:
    """live（第二批）8 行 → 终稿 11 行：第 2 行换数字再按 A 改标点、L3/L4 按 B、L5/L6 按 D；其余三行逐字。
    无上限成长写到效果为止，不写上限/可无限。"""
    lines = tuple(_single_text(rows, CAS_LEADER).split("\n"))
    if lines != OLD_LEADER_LINES:
        raise SorizBalanceError(f"{CAS_LEADER}: unexpected panel text layout")
    return [[NEW_LEADER_TEXT]]


def row_problems(row: list[str], cas_keys) -> list[str]:
    table = "leader_ability"
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, set(cas_keys), table)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(table, row, ELEMENT)]
    return problems


#: 「/」（半角）与「&」：暂存前最后一轮面板修正（B）规则扫描同时覆盖半角斜杠；「共鸣时：」：口径 3。
FORBIDDEN_PANEL_PHRASES = ("自身为队长时", "觉醒后", "生命值100%以下", "／", "/", AMPERSAND, "共鸣时：",
                           "无上限", "无限叠加", "不设上限", "可无限")


def panel_problems(text: str) -> list[str]:
    problems = [f"forbidden phrase {p!r}" for p in FORBIDDEN_PANEL_PHRASES if p in text]
    problems += list(KL.panel_problems(text))
    problems += pf_damage_join_problems(text)
    if any(line.startswith(MAIN_ICON) for line in text.split("\n")):
        problems.append("leader panel must not carry the main icon")
    return problems


# ---------------------------------------------------------------- 面板改写的数据依据（只读）

#: 前置块起始列（kind, pulled, pulled_group, 下限, 上限, 属性组）：队长 / 能力。
PRECONDITION_BASES = {"leader_ability": (4, 11, 18), "ability": (6, 13, 20)}
#: 触发/前置签名列（前置三块 + 瞬发触发块 + 持续触发类型）：队长 / 能力。同签名 = 同一数据条件。
CONDITION_COLS = {"leader_ability": tuple(range(4, 37)) + (95,), "ability": tuple(range(6, 39)) + (97,)}
FEVER_PRECONDITION = "12"
PF_TREE = "battle/action/power_flip/action/override/{k}${k}_lv{n}"
PF_OVERRIDE_KEY = "override_soriz_fever_special"
PF_TREES = tuple(PF_TREE.format(k=PF_OVERRIDE_KEY, n=n) for n in (1, 2, 3))
FEVER_BEGIN_TREE = "battle/action/skill/action/ability_skill/soriz_fever_begin$soriz_fever_begin"
GUTS = 12998603                                    # 固有「不死不休」
DSL_WATER = 2                                      # DSL 显式元素 = 内部 + 1


def resonance_tokens(row: list[str], table: str) -> list[str]:
    """该行前置里的属性共鸣（kind 2、编成 600000、不按拉取组计数）的属性组。"""
    out = []
    for base in PRECONDITION_BASES[table]:
        kind, _pulled, pulled_group, low, high, group = row[base:base + 6]
        if kind == "2" and low == "600000" and high in ("600000", "") and group \
                and pulled_group in ("", "0", "(None)"):
            out.append(group)
    return out


def _condition(row: list[str], table: str) -> tuple[str, ...]:
    return tuple(row[c] for c in CONDITION_COLS[table])


def _commands(node: Any, name: str) -> list[list]:
    out: list[list] = []

    def walk(item: Any) -> None:
        if isinstance(item, list):
            if len(item) > 1 and item[0] == "Command" and isinstance(item[1], list) and item[1][:1] == [name]:
                out.append(item[1])
            for child in item:
                walk(child)
    walk(node)
    return out


def _slv(value: Any) -> float:
    if not (isinstance(value, list) and len(value) == 1 and value[0]["min"] == value[0]["max"]):
        raise SorizBalanceError(f"unexpected skill-level value {value!r}")
    return float(value[0]["min"])


def pf_level_facts(tree: Any) -> dict[str, Any]:
    """722 覆盖树的 Fever 分支：总倍率、段数、首个判定区时长（与非 Fever 分支之比）。"""
    fever_mode = _commands(tree, "ConditionalsFeverMode")
    if len(fever_mode) != 1:
        raise SorizBalanceError(f"override tree has {len(fever_mode)} ConditionalsFeverMode")
    fever, normal = fever_mode[0][1], fever_mode[0][2]
    areas, normal_areas = _commands(fever, "CreateHitArea"), _commands(normal, "CreateHitArea")
    total, hits = 0.0, 0
    for area in areas:
        count = int(area[14][1])
        attacks = _commands(area, "CreateNormalAttack")
        if len(attacks) != 1:
            raise SorizBalanceError("hit area without exactly one CreateNormalAttack")
        total += count * _slv(attacks[0][6])
        hits += count
    return {"total": round(total, 3), "hits": hits,
            "lifetime_ratio": areas[0][13][1] / normal_areas[0][13][1] if areas and normal_areas else None}


def panel_basis_problems(leader: list[list[str]], ability3: list[list[str]], trees: dict[str, Any]) -> list[str]:
    """终稿每处改写的数据依据（A / B / D）；任何一条不成立即拒绝（fail closed）。"""
    problems = []
    lt, at = "leader_ability", "ability"
    # A：L2 #9 自身攻击力 → #10 during 23 → #11 413；L5 #7 kind 0 / #8 during 23 同条件。
    if [leader[i][107] for i in (9, 10, 11)] != ["0", "23", "413"] or leader[9][108] != "0":
        problems.append("L2: leader #9/#10/#11 are no longer self attack / pf damage / independent pf damage")
    if [leader[i][107] for i in (7, 8)] != ["0", "23"] or leader[7][108] != "0" \
            or leader[7][95:107] != leader[8][95:107]:
        problems.append("L5: leader #7/#8 are no longer same-condition self attack / pf damage")
    # B（L3）：四组数据都带水共鸣、Fever 相关，且四组条件两两不同；#7/#8 同条件。
    sources = {
        "heal_rejection": (leader[5], lt), "pf_damage": (leader[2], lt), "combo": (leader[3], lt),
        "shield": (ability3[7], at),
    }
    for name, (row, table) in sources.items():
        if resonance_tokens(row, table) != ["Blue"]:
            problems.append(f"L3 split {name}: data no longer gated on water resonance")
    if (leader[5][25], leader[5][45], leader[5][68]) != ("8", "629", "soriz_fever_begin"):
        problems.append("L3 split heal_rejection: leader #5 is no longer Fever-entry soriz_fever_begin")
    if (leader[2][95], leader[2][107], leader[2][111]) != ("4", "23", "300000"):
        problems.append("L3 split pf_damage: leader #2 is no longer during-Fever pf damage 300%")
    if (leader[3][11], leader[3][25], leader[3][45], leader[3][49]) != (FEVER_PRECONDITION, "6", "226", "1600000"):
        problems.append("L3 split combo: leader #3 is no longer Fever + every flip → combo +16")
    shield, drain = ability3[7], ability3[8]
    if (shield[27], shield[47], shield[48], shield[49], shield[51]) != ("2", "227", "5", "Blue", "15000") \
            or (drain[47], drain[51]) != ("724", "-20000") or _condition(shield, at) != _condition(drain, at):
        problems.append("L3 split shield: ability3 #7/#8 are no longer the same-condition PF shield / Fever drain")
    signatures = [_condition(row, table) for row, table in sources.values()]
    if len(set(signatures)) != len(signatures):
        problems.append("L3 split: two split lines now share one data condition (merge them instead)")
    begin = trees[FEVER_BEGIN_TREE]
    heal = [c for c in _commands(begin, "FindAllSubjects") if c[2] == 33 and c[3] == [DSL_WATER]
            and any(cond[2][0][0] == "ACHealRejection" for cond in _commands(c, "CreateCondition"))]
    if not heal:
        problems.append("L3 split heal_rejection: soriz_fever_begin no longer bans healing for the water party")
    # B（L4）：同一条 722 行（水共鸣）→ 三档覆盖树；Fever 分支倍率 10/20/50、11+1 段、判定时长 ×2。
    row722 = leader[4]
    if (row722[45], row722[80], row722[81]) != ("722", PF_OVERRIDE_KEY, "1,2,3") \
            or resonance_tokens(row722, lt) != ["Blue"]:
        problems.append("L4: leader #4 is no longer the single water-resonance 722 override row")
    for level, (path, multiplier) in enumerate(zip(PF_TREES, PF_LEVEL_MULTIPLIERS), start=1):
        facts = pf_level_facts(trees[path])
        if facts != {"total": float(multiplier), "hits": 12, "lifetime_ratio": 2.0}:
            problems.append(f"L4: Lv{level} Fever branch drifted from the panel ({facts})")
    # D（L6）：「不死不休」获取 = #5（水共鸣）→ soriz_fever_begin 授予 ACUnique 12998603 与踏止。
    granted = [cond for cond in _commands(begin, "CreateCondition") if cond[2][0][:2] == ["ACUnique", GUTS]]
    guts = [cond for cond in _commands(begin, "CreateCondition") if cond[2][0][0] == "ACGuts"]
    if len(granted) != 9 or len(guts) != 1:
        problems.append(f"L6: soriz_fever_begin grants {len(granted)} 不死不休 layers / {len(guts)} guts (expected 9 / 1)")
    return problems


BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "f5c6ba162d5ec01d6cd2e098050993a3f40e92b9adb88fc445c7e4ebdd1c418f",
    ("cas", CAS_LEADER): "c4177accce160614c5209219131e2ff37ced4a9377e3092d2f6a1570cb01f5b8",
    # 只读：能力3 封顶版（口径 D4 不动）与搬行原像核对。
    ("ability", ABILITY3): "9376175bf91ed2f9f105a9308e58c2ab2234fd898c94ec06026d4bb7e8fa8818",
    # 只读：队长 L#5/L#6 629 行的 string_id（invoke_skill_string 门禁要求 live 有同键行），不改。
    ("cas", "soriz_fever_begin"): "1694a757ffb53648199fde97b84aa5edaf623457483cc6316f8452381528ceb3",
    ("cas", "soriz_fever_end"): "9c9dc284f7dd3fa28e514bfd8ae306fbc5af775610822b4516c7a9ebec2f3944",
    # 只读（面板口径 B/D 的数据依据，live 1.4.1054）：722 三档覆盖树（L4 分项）与进 Fever 629 树（L3 禁疗、L6 获取）。
    ("dsl", PF_TREES[0]): "c2129710d661036db94dd8fdfc1bb03f0949d2999d6d35f815bec2d536dad54b",
    ("dsl", PF_TREES[1]): "c32b98815233a7c2234939508b6b7cd413b658c883c99080fd780fa260be9e81",
    ("dsl", PF_TREES[2]): "3b222e699195f0dbc28479373462edf1b84c0bf95cf4f76f64f938571078520c",
    ("dsl", FEVER_BEGIN_TREE): "795e2dad18d66866c037ead09cdf3f832836229c398b9e1681c93e273ced5fe7",
}


def _baseline(read: Callable[[str, Any], Any]) -> dict:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        if value is None:
            raise SorizBalanceError(f"unreviewed live baseline for {kind}:{key} (missing)")
        got = digest(value)
        if got != want:
            raise SorizBalanceError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _pct(strength: int) -> str:
    return f"{strength / 1000:g}%"


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(read)
    ability3 = inputs["ability", ABILITY3]
    check_ability3(ability3)
    leader = soriz_leader(inputs["leader", CID], ability3)
    cas = {CAS_LEADER: soriz_leader_text(inputs["cas", CAS_LEADER])}

    trees = {key: value for (kind, key), value in inputs.items() if kind == "dsl"}

    strings = {key for key in INVOKE_STRINGS if _single_text(inputs["cas", key], key)} | set(cas)
    problems = [f"leader {CID}#{i}: {p}" for i, row in enumerate(leader) for p in row_problems(row, strings)]
    problems += [f"cas {key}: {p}" for key, rows in cas.items() for p in panel_problems(rows[0][0])]
    problems += [f"panel basis: {p}" for p in panel_basis_problems(leader, ability3, trees)]
    needed = {c for row in leader for c in L.required_client_capabilities("leader_ability", row)}
    needed |= {c for key in cas for c in L.required_client_capabilities(L.CUSTOM_ABILITY_STRING_KIND, [key])}
    if needed != set(CAPABILITIES):
        problems.append(f"capabilities {sorted(needed)} != declared {CAPABILITIES}")
    if problems:
        raise SorizBalanceError("; ".join(problems))

    return {
        "ability": {}, "leader": {CID: leader}, "cas": cas,
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": SOURCE, "character": f"{CID} {CODE} 索利兹「汉气Ultimatum」（水）",
            "scope": "2026-09-27 第三轮（c）成长复核：第二批 1/5 回调到 2/3 档，数值取 5 的倍数（原值 ≤10% 取整数）",
            "changes": [
                {"where": f"leader_ability:{CID} L#{index}（0 起）c111/c112",
                 "what": f"during 134 每层三羽乌 → 自身{name}（kind {kind}）",
                 "before": f"{before}（每层 {_pct(before)}，第二批 1/5；原值 {_pct(original)}）",
                 "after": f"{after}（每层 {_pct(after)}，{BAND} 档：{rounding}）"}
                for index, kind, name, original, before, after, rounding in GROWTH
            ] + [{"where": f"custom_ability_string:{CAS_LEADER} 第2行（数值稿）",
                  "before": OLD_LEADER_LINE, "after": NUMERIC_LEADER_LINE},
                 {"where": f"custom_ability_string:{CAS_LEADER}（面板口径 A/B/D，8 行 → 11 行）",
                  "before": list(NUMERIC_LEADER_LINES), "after": list(NEW_LEADER_LINES)}],
            "panel_rules": {
                "author": "同一个条件的提升能不能写到一起来简化描述",
                "rules": "主会话口径 1（强化弹射伤害不补对象、与前一效果用「，」）扩到同形写法 A；口径 5（一行两种数据条件拆行、"
                         "斜杠分项拆行）扩到 B（含半角「/」，同条件就「、」分项）；口径 4（面板与数据不符按数据改文字）落到 D",
                "lines": {f"数值稿L{index + 1}": rule for index, (rule, _fn) in LEADER_LINE_RULES.items()},
                "split_basis": {f"终稿L{3 + n}": basis for n, basis in enumerate(SPLIT_BASIS)},
                "pf_levels": {f"Lv{level}": f"Fever 分支倍率 {multiplier} 倍（11 段 + 终结段 = 连击数 12，首个判定区时长 ×2）"
                              for level, multiplier in enumerate(PF_LEVEL_MULTIPLIERS, start=1)},
                "guts_gain": "数值稿L6（终稿L9）获取来源 = 队长 #5（水编成≥6，进 Fever → 629 soriz_fever_begin 授予 9 档 ACUnique 12998603 与"
                             "踏止）；本角色队长/能力行、9 棵 629、技能树、722 覆盖树只读核对无其他授予",
                "kept": ["终稿L1/L10/L11（数值稿L1/L7/L8）逐字", "数值稿L7 消耗「不死不休」、L8 FEVER 结束清除是依赖该状态的行，不补共鸣",
                         "终稿L3 禁疗行与终稿L9（数值稿L6）同出 #5（soriz_fever_begin）：文案描述的是整个 FEVER 期间的状态（#6 FEVER 结束解除），"
                         "按原措辞单独成行，未并入终稿L9"],
                "not_returned": "能力2（Lv.1 攻击力&强化弹射伤害）、能力5（与数值稿L5 同句）面板里的「&」不在本轮范围，未返回",
                "check_merge": "拆行按「合并的逆」过 mod-tools/wf_panel_merge_check.check（拆出的 4 行 → 原 L3 一行），"
                               "整块先在测试里显式规范化再比对，见测试",
            },
            "basis": {
                "author": ["成长速度砍到1/10不合理……砍太多了", "砍到4/5，或者7/10这样吧", "可以砍到2/3",
                           "数值尽量取5的倍数"],
                "table": "reeval_full.json table.rows 索利兹两行（已按复核修正：65%→70%，不低于 2/3 下限）",
                "reason": "三羽乌上限 99 无消耗，来源多（技能每发 +3、进 Fever +1、欧根/仁援护各 +1），3 分钟约 35–45 层"
                          "（按 40 层）；基础极厚（队长水队攻击 +100%、PF +100%、Fever 中 PF +300%、背水、老当益壮等）→ 取下限 2/3",
            },
            "totals_3min_40_layers": {
                "self_attack": "原 +4000% / 第二批 +800%+150%（能力3 封顶）/ 本轮 +2800%+150%",
                "self_pf_damage": "原 +4000% / 第二批 +800%+100% / 本轮 +2800%+100%",
                "self_pf_independent": "原 +120% / 第二批 +20%+10% / 本轮 +80%+10%",
            },
            "early_stack_notice": "能力3 封顶版与队长行在前 10 层叠加：L#11 每层 2%+1%=3%，等于原值（复核表已列出，作者知情项）",
            "unchanged": [f"leader {CID} L#0-L#8", f"ability {ABILITY3}（能力3 封顶版 15%/10%/1%×10，口径 D4）",
                          f"{CAS_LEADER} 数值稿第1、3-8行的数值与措辞（面板口径只动标点、分行与共鸣前缀）",
                          "desc_override_soriz_3（能力3 面板，数值未变）",
                          "援护 629 / Fever 特殊 PF 削韧 / 技能 / action_skill / character_text",
                          "共鸣前置：三行 live c4=0，口径 D3 只改数值不新增"],
            "generator": "wf_gbf_kit_soriz.py CROWS_GROWTH 队长每层 20000/20000/500 → 70000/70000/2000；kit 的队长面板串"
                         "读设计镜像 design/soriz.json，由本模块 sync_mirror(write=True) 同步到终稿",
            "capabilities": CAPABILITIES,
            "runtime_verified": False,
        },
    }


# ====================================================================== 设计镜像同步

DESIGN_REL = Path("work/character_packs/midautumn-20260920/design/soriz.json")
MIRROR_TAG = "balance_20260927c"


def _describe(cells: dict) -> str:
    row = [""] * LEADER_NCOLS
    for col, value in cells.items():
        row[int(col)] = str(value)
    return wf_describe.describe_line(row, "leader_ability")


def soriz_mirror(design: dict) -> dict:
    """设计镜像按本轮规格重算（纯函数、幂等）：队长 #9-#11 的 cells/describe/req 与队长面板（终稿 11 行）。

    接受第二批已同步（``balance_20260927b``）或本轮已同步的镜像；队长面板接受 live 原文（第二批）、数值稿
    （本模块首版 --write）与终稿三种形态，一律写成终稿；其余形态拒绝。"""
    design = deepcopy(design)
    plan = design["plan"]
    rows = plan["leader_ability"]["rows"]
    if len(rows) != 12:
        raise SorizBalanceError(f"design leader rows {len(rows)} != 12 (batch-2 mirror expected)")
    for index, kind, name, _original, before, after, _rounding in GROWTH:
        record = rows[index]
        current = {int(c): v for c, v in record["cells"].items()}
        if current not in (leader_cells(index, str(before)), leader_cells(index, str(after))):
            raise SorizBalanceError(f"design leader row {index}: unexpected cells {current}")
        cells = {str(c): v for c, v in sorted(leader_cells(index, str(after)).items())}
        record["cells"] = cells
        record["desc_expected"] = _describe(cells)
        record["req"] = (f"L#{index} 每层三羽乌 {name}+{_pct(after)}（2026-09-27b 由能力3#{index - 8} 搬入；"
                         f"2026-09-27c 成长复核 {BAND} 档，原 {_pct(_original)}）")
    texts = plan["texts"]["custom_ability_string"]
    if texts[CAS_LEADER] not in (OLD_LEADER_TEXT, NUMERIC_LEADER_TEXT, NEW_LEADER_TEXT):
        raise SorizBalanceError(f"design {CAS_LEADER}: unexpected panel text {texts[CAS_LEADER]!r}")
    texts[CAS_LEADER] = NEW_LEADER_TEXT
    design[MIRROR_TAG] = dict(
        spec="第三轮（c）成长复核：作者「1/10 砍太多了」「砍到4/5，或者7/10」「可以砍到2/3」「数值尽量取5的倍数」",
        growth=[f"队长#{index} 每层三羽乌 kind {kind}：{_pct(before)} → {_pct(after)}（原 {_pct(original)}，{BAND} 档）"
                for index, kind, _n, original, before, after, _r in GROWTH],
        panel=[CAS_LEADER],
        panel_rules={f"数值稿L{index + 1}": rule for index, (rule, _fn) in LEADER_LINE_RULES.items()},
        kept="能力3 封顶版 15%/10%/1%×最多10层（第二批值）",
        module="mod-tools/wf_balance_20260927c_soriz.py",
    )
    return design


def _save(path: Path, value: dict) -> None:
    """保持原文件格式：indent=1、CRLF/LF 与末尾换行按原文件。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = json.dumps(value, ensure_ascii=False, indent=1)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirror(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回设计镜像；返回有变化的相对路径。"""
    path = Path(root) / DESIGN_REL
    before = json.loads(path.read_text(encoding="utf-8"))
    after = soriz_mirror(before)
    if before == after:
        return []
    if write:
        _save(path, after)
    return [DESIGN_REL.as_posix()]


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirror(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))
