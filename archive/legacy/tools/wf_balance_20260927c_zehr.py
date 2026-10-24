# -*- coding: utf-8 -*-
"""泽赫尔「今晚由团长买单」159997 ``guildknight_leader_tavern``（光）：2026-09-27 平衡第三轮（成长复核），纯函数。

口径：主会话 ``growth_c_spec.md``（作者原话：成长砍到 1/10 不合理 →「砍到 4/5，或者 7/10」→「可以砍到 2/3」、
「数值尽量取 5 的倍数」）+ ``reeval_full.json`` table.rows 泽赫尔四组 + 默认选择 D1–D4。
第二批（``wf_balance_20260927b_zehr``，已发布）把队长成长砍到原值 1/10–1/5；本轮按触发难度回调。

落点（队长 ``leader_ability:159997``，行号 0 起；其余格、其余 4 行逐字保留）：

- L#3 每达成 35 连击 → 自身 PF 伤害：c49/c50 5000 → **35000**（原 50%；3 分钟约 40 次、易、基础足 ⇒ 2/3 = 33.3，
  向上取 35）；
- L#4 每次 PF → 光队攻击力：c49/c50 3500 → **25000**（原 35%；约 50 次、易 ⇒ 2/3 = 23.3，向上取 25）；
- L#6 每层「灯芯」→ 自身 PF 独立乘区：c111/c112 500 → **2000**（原 3%；约 25 层、中 ⇒ 7/10 = 2.1，
  <10% 按 0.5 取整 = 2，实际 2/3）；
- L#7 / L#8 每获得 1 次「灯火正旺」→ 光队攻击力 / 自身 PF 伤害：c49/c50 6000 → **20000**（原 30%；约 25 次、中 ⇒
  7/10 = 21，就近取 20，实际 2/3）。

面板：队长覆盖文案 ``desc_override_guildknight_leader_tavern`` 四处数字随行改写（行数 8 不变，数字由行值推出），
另按主会话口径 1（扩到同形写法）把 L1 / L7 的「、强化弹射伤害」改「，强化弹射伤害」（见下）。
能力 1 / 3 覆盖文案只写能力栏封顶版，D4 不动 ⇒ 不改。技能描述不含这些数值 ⇒ 不改。

面板同条件合并 + 共鸣省略（作者原话「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,
引擎点火提供的效果就不用写火属性共鸣,其他角色类似」；主会话合并规则与扫描 ``panel_merge/scan.json``，按本轮数据重核）：

- 能力6 ``desc_override_guildknight_leader_tavern_6`` 两行（数据 ``1599976`` #0/#1：光共鸣前置、无触发、c1=true、
  无 CT/次数上限/后缀，除效果列外逐格相同）合并为一行「光属性共鸣时，光属性角色技能充能速度＋15%，强化弹射伤害＋50%」。
  第二效果保持原措辞、不补「自身」：#1 是 kind 55（强化弹射伤害），引擎按战斗（小队）级结算、不读 target 列
  （kit 审查锁 R6 ``wf_seasonal7_kit_zehr.PANEL_FORBIDDEN_PHRASES``：不许写「自身强化弹射伤害」）；两个效果用「，」分开，
  不与「光属性角色」连成同一对象（= 主会话口径 1，与冈达葛萨「水属性角色攻击力＋300%，强化弹射伤害＋300%」同式）。
  能力6 词条行只读（核对合并组）。
- 口径 1 扩到同形写法（主会话追加 A：凡「…、强化弹射伤害…」接在带对象的效果后面的，一律改「，强化弹射伤害…」）：
  队长 L1「光属性角色攻击力＋400%、强化弹射伤害＋200%」与 L7「…光属性角色攻击力＋20%、强化弹射伤害＋20%（CT 5s）」
  的强化弹射伤害是 kind 55（#1 / #8：c45=55、c46 对象空，战斗级），前一个效果是带对象的光队攻击（#0 / #7：kind 32 →
  5/White）；「、」会读成「光属性角色的强化弹射伤害」⇒ 两处改「，强化弹射伤害」，仍不补「自身」（R6）。这两行不是合并行
  （kit 设计稿原有的单行），只改分隔符；数据侧只读核对（:func:`pf_damage_problems`，不符 ⇒ 拒绝），
  :func:`problems` 锁住队长面板不许再出现「、强化弹射伤害」（kit 第三轮收口经它送检）。
- 其余覆盖面板无新合并：队长 #0/#1（L1）、#7/#8（L7）、能力1 #2/#3（L3）、能力2 #0/#1（L1）数据同条件组已是一行；
  能力3 #0（限 8 次）与 #3（限 10 次）次数上限不同 ⇒ 不并；能力3 #1/#2（队长冲刺参数）不在面板上。
- 共鸣省略：「灯火正旺」159997 与「灯芯」1599971 的唯一来源是能力1 #2/#3（光共鸣前置 + 461），全部来源带光共鸣；
  但依赖它们的面板行（队长 L6、能力1 L4「每1层「灯芯」」，能力3 L3–L5「持有「灯火正旺」期间」）本来就没写
  「光属性共鸣时，」⇒ 无可删前缀。队长 L7、能力3 L1/L2「光属性共鸣时，每获得1次「灯火正旺」」的数据是
  「连击≥55 + 光共鸣前置」、不依赖该状态 ⇒ 不做共鸣省略（主会话口径）。:data:`PREFIX_DROPS` 为空。
不动：能力 1 #4 / 能力 3 #0 #3 的封顶版（D4）；L#3 / L#4 / L#6 没有共鸣前置，按 D3 不新增。

生成器：``wf_seasonal7_kit_zehr.build`` 在 ``wf_balance_20260927b_zehr.balance_rows`` / ``panel_texts`` 之后调
:func:`leader_rows` / :func:`leader_text` ⇒ kit 重跑产物 == :func:`revise`（测试断言）。kit 里冻结的稻穗 donor
（``FROZEN_DONORS``）不涉及。澄波响 kit 借的能力 1 #4 本轮不改。
本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Callable

import wf_balance_20260927b_zehr as B

CID = B.CID
CODE = B.CODE
PACKAGES = ["s7-zehr"]
#: 候选 manifest 现值 1.0.8（第二批写入）⇒ 1.0.9。
PACKAGE_VERSION = {"s7-zehr": "1.0.9"}
CAPABILITIES: list[str] = []
#: 候选 s7-zehr 的队长行与队长覆盖文案与 live 逐字相同（2026-09-27 只读核对，链尾 1.4.1053）。
REVIEWED_DRIFT: dict = {}

ELEMENT = B.ELEMENT
LEADER_NCOLS = B.LEADER_NCOLS
LEADER_ROWS = B.LEADER_ROWS_AFTER               # 第二批之后 9 行
CAS_LEADER = B.CAS_LEADER
A6 = f"{CID}6"                                  # 1599976（面板合并组的数据行，只读）
CAS_A6 = f"desc_override_{CODE}_6"              # desc_override_guildknight_leader_tavern_6
ABILITY_NCOLS = 126

#: 第二批落值（= 本轮输入）的逐格指纹：行号 → 全部非空格。
B_AFTER = {3: B.LEADER_SLOWED[3][1], 4: B.LEADER_SLOWED[4][1], 6: B.LEADER_NEW[6],
           7: B.LEADER_NEW[7], 8: B.LEADER_NEW[8]}
#: 本轮新值：行号 → (强度列, 新值)。
C_VALUES = {3: ((49, 50), "35000"), 4: ((49, 50), "25000"), 6: ((111, 112), "2000"),
            7: ((49, 50), "20000"), 8: ((49, 50), "20000")}
C_AFTER = {i: {**cells, **{col: C_VALUES[i][1] for col in C_VALUES[i][0]}} for i, cells in B_AFTER.items()}

#: 行 → (成长, 原值 %, 第二批 %, 档位, 本轮 %)，供测试与 notes 复核。
GROWTH = {
    3: ("每达成35连击 → 自身PF伤害", 50, 5, "2/3（33.3 向上取 35）", 35),
    4: ("每次PF → 光队攻击力", 35, 3.5, "2/3（23.3 向上取 25）", 25),
    6: ("每层「灯芯」→ 自身PF独立乘区", 3, 0.5, "7/10（2.1 取 2，实际 2/3）", 2),
    7: ("每获得「灯火正旺」→ 光队攻击力", 30, 6, "7/10（21 取 20，实际 2/3）", 20),
    8: ("每获得「灯火正旺」→ 自身PF伤害", 30, 6, "7/10（21 取 20，实际 2/3）", 20),
}

#: 口径 1：强化弹射伤害（kind 55，战斗级）原文不带对象，不再用「、」接在带对象的效果后面（读作同一对象），改用「，」隔开。
PF_DAMAGE_JOIN_OLD, PF_DAMAGE_JOIN_NEW = "、强化弹射伤害", "，强化弹射伤害"
#: 口径 1 的数据依据（队长行号 0 基）：面板行 → (前一个带对象的效果行, 强化弹射伤害行)。
#: 前者 = kind 32 攻击力、对象 5/White（光属性角色）；后者 = kind 55、对象列空（战斗级，不读 target，R6）。
PF_DAMAGE_JOIN_ROWS = {0: (0, 1), 6: (7, 8)}
PF_DAMAGE_KIND_LEADER = ("55", "", "")           # c45–c47：kind / 对象种类 / 对象元素
TEAM_ATTACK_LEADER = ("32", "5", "White")         # c45–c47

#: 队长覆盖文案逐行改写（第二批行 → 本轮行，按行序）：L3 / L4 / L6 / L7 数字与行值同源（测试断言）；
#: L1 / L7 另按口径 1 把「、强化弹射伤害」改「，强化弹射伤害」。
LEADER_TEXT_REWRITES = (
    ("光属性共鸣时，光属性角色攻击力＋400%、强化弹射伤害＋200%",
     "光属性共鸣时，光属性角色攻击力＋400%，强化弹射伤害＋200%"),
    ("每达成35连击，强化弹射伤害＋5%", "每达成35连击，强化弹射伤害＋35%"),
    ("每发动强化弹射，光属性角色攻击力＋3.5%", "每发动强化弹射，光属性角色攻击力＋25%"),
    ("每1层「灯芯」，强化弹射伤害额外乘区＋0.5%", "每1层「灯芯」，强化弹射伤害额外乘区＋2%"),
    ("光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋6%、强化弹射伤害＋6%（CT 5s）",
     "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋20%，强化弹射伤害＋20%（CT 5s）"),
)
LEADER_TEXT_LINES = B.PANEL_LINES[CAS_LEADER][1]  # 8 行

#: live 输入基线（2026-09-27 本地链尾 1.4.1053 只读取数 = 第二批产物）。任一不符 ⇒ 拒绝（fail closed）。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", CID): "ceb94c9a51534b2fafe995b6754ca0e1fd2cd7812195667f7458ed5b1b74e3ea",
    ("cas", CAS_LEADER): "62a6e354b90335e57d2323f115222d7063ee959b3cc4c0ab339340ece3776777",
    # 面板同条件合并（链尾 1.4.1054 只读取数，与 1.4.1053 及候选 s7-zehr 1.0.8 逐字相同）：
    # 能力6 词条行只读（核对合并组数据条件），能力6 覆盖串改写。
    ("ability", A6): "7e93cff5b0f17de735b9eec0457f4b9b9620ca6e4083f23e90f63ca8b234a34d",
    ("cas", CAS_A6): "5f4f3de1f88d4d9dea8d76d6ace7bbd700bf7e750cbaae6a6d868097046ba77e",
}

# ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

A6_ROWS = 2
#: 同条件的判据：组内各行除「效果列」外逐格相同（前置三块、触发与参数、CT、次数上限、c1 主位、觉醒列、效果后缀列）。
#: 效果列 = c2 分类 + instant 内容块 kind/对象/对象元素/强度（c47–c52）+ during 内容块同位（c109–c114）。
ABILITY_EFFECT_COLUMNS = frozenset({2}) | frozenset(range(47, 53)) | frozenset(range(109, 115))
OLD_A6_LINES = (
    "光属性共鸣时，光属性角色技能充能速度＋15%",
    "光属性共鸣时，强化弹射伤害＋50%",
)
NEW_A6_LINES = (
    "光属性共鸣时，光属性角色技能充能速度＋15%，强化弹射伤害＋50%",
)
#: 合并组：面板键 → (词条键, 同条件数据行（0 基）, 被合并的面板行（0 基）, 改前整段行, 改后整段行)。
PANEL_MERGES: dict[str, tuple[str, tuple[int, ...], tuple[int, ...], tuple[str, ...], tuple[str, ...]]] = {
    CAS_A6: (A6, (0, 1), (0, 1), OLD_A6_LINES, NEW_A6_LINES),
}
#: kind 55 强化弹射伤害是战斗（小队）级、不读 target 列（kit 审查锁 R6）⇒ 合并行不补「自身」。
PF_DAMAGE_KIND = "55"
FORBIDDEN_SELF_PF = "自身强化弹射伤害"
#: 共鸣省略：无（见模块说明）。键 = 面板键，值 = 可删「X属性共鸣时，」的面板行号（1 起）。
PREFIX_DROPS: dict[str, tuple[int, ...]] = {}
UID_LAMP, UID_WICK = "159997", "1599971"         # 「灯火正旺」「灯芯」
RESONANCE_BASIS = ("灯火正旺 159997 / 灯芯 1599971 唯一来源 = 能力1 #2/#3（光共鸣前置 + 461）⇒ 全部来源带光共鸣；"
                   "依赖它们的面板行（队长 L6、能力1 L4、能力3 L3–L5）本无「光属性共鸣时，」⇒ 无可删前缀；"
                   "队长 L7、能力3 L1/L2 的数据是「连击≥55 + 光共鸣前置」、不依赖该状态 ⇒ 保留「光属性共鸣时，」")


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


def ability6_rows_problems(rows: list[list[str]]) -> list[str]:
    """能力6 两行：键头 + 合并组数据条件逐格相同 + #1 仍是 kind 55（合并行不补「自身」的依据）。"""
    if len(rows) != A6_ROWS or any(len(r) != ABILITY_NCOLS for r in rows):
        return [f"ability {A6}: expected {A6_ROWS}×{ABILITY_NCOLS} rows"]
    if any((r[0], r[1]) != (f"{CODE}_6", "true") for r in rows):
        return [f"ability {A6}: key head drifted"]
    if rows[1][47] != PF_DAMAGE_KIND:
        return [f"ability {A6}#1: kind {rows[1][47]} is not the battle-level PF damage {PF_DAMAGE_KIND}"]
    return merge_condition_problems(rows, PANEL_MERGES[CAS_A6][1])


def ability6_text(text: str) -> str:
    """能力6 同条件合并：改前整段逐字核对 → 合并行；已合并则原样（幂等，供 kit 链式回放）。"""
    _ability, _rows, _lines, old, new = PANEL_MERGES[CAS_A6]
    if text == "\n".join(new):
        return text
    if text != "\n".join(old):
        raise ValueError(f"{CAS_A6}: unexpected panel text (expected the live pre-merge text)")
    return "\n".join(new)


def ability6_problems(rows: list[list[str]], text: str) -> list[str]:
    """能力6：数据条件 + 面板规则（kitlib 禁词、无「／」、非主位无图标、共鸣「，」、R6 不写「自身强化弹射伤害」）。"""
    import wf_midautumn_kitlib as KL
    probs = [f"{CAS_A6}: {p}" for p in ability6_rows_problems(rows)]
    probs += [f"{CAS_A6}: {p}" for p in KL.panel_problems(text)]
    if text != "\n".join(NEW_A6_LINES):
        probs.append(f"{CAS_A6}: merged panel differs from the reviewed text")
    if "／" in text or "icon" in text or re.search(r"属性共鸣时[：:,]", text):
        probs.append(f"{CAS_A6}: line-break / icon / resonance punctuation rule broken")
    if FORBIDDEN_SELF_PF in text:
        probs.append(f"{CAS_A6}: kind 55 is battle-level; must not say {FORBIDDEN_SELF_PF!r}")
    if PF_DAMAGE_JOIN_OLD in text:
        probs.append(f"{CAS_A6}: 口径 1: battle-level PF damage must follow with 「，」, not {PF_DAMAGE_JOIN_OLD!r}")
    return probs


def pf_damage_problems(leader: list[list[str]]) -> list[str]:
    """口径 1 的数据依据：队长 L1 / L7 改成「，强化弹射伤害」的两处，前一效果确是带对象的光队攻击（kind 32 → 5/White），
    强化弹射伤害确是战斗级 kind 55（对象列空）。不符 ⇒ 面板要重审。"""
    probs = []
    for line, (team_row, pf_row) in PF_DAMAGE_JOIN_ROWS.items():
        for index, want in ((team_row, TEAM_ATTACK_LEADER), (pf_row, PF_DAMAGE_KIND_LEADER)):
            got = tuple(leader[index][45:48]) if index < len(leader) and len(leader[index]) > 47 else None
            if got != want:
                probs.append(f"leader_ability {CID}#{index} (panel L{line + 1}) c45–c47 = {got!r}, want {want!r}")
    return probs


#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    3: "连击≥35 → 自身 强化弹射伤害 35%",
    4: "强化弹射≥1 → 赋予全队(光) 攻击力 25%",
    6: "持续·状态累积计数固有≥1[固有1599971] → 自身 独立乘区强化弹射伤害 2%",
    7: "光·编成≥6 时: 连击≥55(CT5秒) → 赋予全队(光) 攻击力 20%",
    8: "光·编成≥6 时: 连击≥55(CT5秒) → 自身 强化弹射伤害 20%",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} ({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长五行强度回调；只接受第二批产物（或本轮产物，幂等），其余 4 行逐字保留。"""
    if len(rows) != LEADER_ROWS or any(len(r) != LEADER_NCOLS for r in rows):
        raise ValueError(f"leader_ability {CID}: expected the {LEADER_ROWS}-row batch-2 shape")
    out = deepcopy(rows)
    for index, cells in B_AFTER.items():
        if not (B._matches(out[index], LEADER_NCOLS, cells)
                or B._matches(out[index], LEADER_NCOLS, C_AFTER[index])):
            raise ValueError(f"leader_ability {CID}#{index}: row is not the reviewed batch-2 shape")
        out[index] = B._row(LEADER_NCOLS, C_AFTER[index])
    for index, (old, new) in enumerate(zip(rows, out)):
        if index not in B_AFTER and old != new:
            raise AssertionError(f"leader_ability {CID}#{index}: untouched row changed")
    return out


def leader_text(text: str) -> str:
    """队长覆盖文案四处数字改写；已改则原样（幂等）；其余 4 行逐字保留。"""
    lines = text.split("\n")
    if len(lines) != LEADER_TEXT_LINES:
        raise ValueError(f"{CAS_LEADER}: expected {LEADER_TEXT_LINES} panel lines, got {len(lines)}")
    if all(lines.count(new) == 1 for _old, new in LEADER_TEXT_REWRITES):
        return text
    for old, new in LEADER_TEXT_REWRITES:
        if lines.count(old) != 1:
            raise ValueError(f"{CAS_LEADER}: line {old!r} not found exactly once")
        lines[lines.index(old)] = new
    return "\n".join(lines)


def problems(leader: list[list[str]], text: str) -> list[str]:
    """行合法性（第二批同一套门禁）+ 队长面板规则 + 口径 1（数据依据 + 面板不许再出现「、强化弹射伤害」）。"""
    probs = B.row_problems("leader_ability", leader) + B.panel_problems({CAS_LEADER: text})
    probs += pf_damage_problems(leader)
    if PF_DAMAGE_JOIN_OLD in text:
        probs.append(f"{CAS_LEADER}: 口径 1: battle-level PF damage must follow with 「，」, not {PF_DAMAGE_JOIN_OLD!r}")
    if FORBIDDEN_SELF_PF in text:
        probs.append(f"{CAS_LEADER}: kind 55 is battle-level; must not say {FORBIDDEN_SELF_PF!r}")
    return probs


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader_in = _checked(read, "leader", CID)
    text_rows = _checked(read, "cas", CAS_LEADER)
    a6_rows = _checked(read, "ability", A6)
    a6_text_rows = _checked(read, "cas", CAS_A6)
    for key, rows in ((CAS_LEADER, text_rows), (CAS_A6, a6_text_rows)):
        if len(rows) != 1 or len(rows[0]) != 1:
            raise ValueError(f"{key}: expected one single-column row")
    leader = leader_rows(leader_in)
    text = leader_text(text_rows[0][0])
    # 面板同条件合并：只接受改前整段（对自身输出重跑由 BEFORE 拒绝）；先核对数据条件再改写。
    if a6_text_rows[0][0] != "\n".join(OLD_A6_LINES):
        raise ValueError(f"{CAS_A6}: unexpected panel text (expected the live pre-merge text)")
    a6_text = ability6_text(a6_text_rows[0][0])
    probs = problems(leader, text) + ability6_problems(a6_rows, a6_text)
    if probs:
        raise ValueError(probs)
    new_caps = B.capability_set("leader_ability", leader) - B.capability_set("leader_ability", leader_in)
    if new_caps - set(CAPABILITIES):
        raise ValueError(f"revised rows need undeclared client capabilities: {sorted(new_caps)}")
    return {
        "ability": {},
        "leader": {CID: leader},
        "cas": {CAS_LEADER: [[text]], CAS_A6: [[a6_text]]},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927c_zehr.py",
            "request": "第三轮成长复核：1/10–1/5 → 2/3 / 7/10，数值尽量取 5 的倍数，<10% 按 0.5 取整",
            "changes": {
                **{f"leader_ability:{CID}#{i} c{C_VALUES[i][0][0]}/c{C_VALUES[i][0][1]}":
                   f"{B_AFTER[i][C_VALUES[i][0][0]]} → {C_VALUES[i][1]}（{GROWTH[i][0]}：原 {GROWTH[i][1]}% / "
                   f"第二批 {GROWTH[i][2]}% / 本轮 {GROWTH[i][4]}%，{GROWTH[i][3]}）" for i in sorted(C_VALUES)},
                CAS_LEADER: "四处数字：＋5%→＋35%、＋3.5%→＋25%、＋0.5%→＋2%、＋6%/＋6%→＋20%/＋20%；"
                            "L1 / L7「、强化弹射伤害」→「，强化弹射伤害」（口径 1）",
                CAS_A6: ["\n".join(OLD_A6_LINES), "\n".join(NEW_A6_LINES)],
            },
            "panel_merge": {
                "request": "作者「同一个条件的提升能不能写到一起来简化描述」「引擎点火的获取带火属性共鸣,引擎点火提供的效果"
                           "就不用写火属性共鸣,其他角色类似」",
                "rule": "同一面板里数据条件完全相同的行合并（前置/触发/CT/c1/次数上限/后缀列逐格相同）；效果原措辞与数值保留、"
                        "只省略重复对象名；合并行放在组首行位置；共鸣写「X属性共鸣时，」",
                "merged": {CAS_A6: f"能力6 两行 → 一行（{A6} #0/#1 除效果列外逐格相同：光共鸣前置、无触发、c1=true）；"
                                   "#1 kind 55 战斗级 ⇒ 第二效果不补「自身」（R6），用「，」与光属性角色分开"},
                "not_merged": {
                    f"{CAS_LEADER}": "#0/#1（L1）、#7/#8（L7）已是一行；其余行条件各不相同",
                    f"desc_override_{CODE}_1": "#2/#3（L3）已是一行",
                    f"desc_override_{CODE}_2": "#0/#1（L1）已是一行",
                    f"desc_override_{CODE}_3": "#0（限8次）与 #3（限10次）次数上限不同 ⇒ 不并；#1/#2 队长冲刺参数不在面板上",
                },
                "prefix_drops": {},
                "resonance_basis": RESONANCE_BASIS,
                "pf_damage_wording": "主会话口径 1（kind 55 强化弹射伤害是战场级，不补对象；原文没写对象的不加「自身」，与前一个"
                                     "带对象的效果用「，」隔开）+ 追加 A（同形写法一律改）：能力6 合并行「…光属性角色技能充能速度"
                                     "＋15%，强化弹射伤害＋50%」已是此写法；队长 L1 / L7（kit 设计稿原有的单行，非合并行）"
                                     "「光属性角色攻击力＋N%、强化弹射伤害＋M%」改为「…＋N%，强化弹射伤害＋M%」，只改分隔符；"
                                     "本轮返回的两块面板都不含「自身强化弹射伤害」（R6）与「、强化弹射伤害」",
                "pf_damage_basis": {f"L{line + 1}": f"leader_ability:{CID}#{team}（kind 32 → 5/White 光队攻击）"
                                                    f" + #{pf}（kind 55、对象列空，战斗级）"
                                    for line, (team, pf) in PF_DAMAGE_JOIN_ROWS.items()},
                "resonance_punctuation": "主会话口径 3：本轮返回的两块面板没有「X属性共鸣时：」，无需规范化",
                "auto_panels": "能力4/5 无覆盖文案（自动生成），不新建",
            },
            "growth_3min": "L#3 40 次 2000%→1400%（第二批 200%）；L#4 50 次 1750%→1250%（第二批 175%）；"
                           "L#6 25 层 75%→50%（另加能力封顶 10%）；L#7/L#8 25 次 750%→500%（另加能力封顶 80% / 100%）",
            "first_layers": "前 10 层灯芯 2%+1% = 原 3%；前 8–10 次灯火正旺 20%+10% = 原 30%（能力封顶版 D4 不动）",
            "kept": "能力 1 / 3 封顶版与其覆盖文案（D4）；L#3/L#4/L#6 无共鸣前置（D3 不新增）",
            "describe_after": {f"leader_ability:{CID}#{i}": d for i, d in DESCRIBE_AFTER.items()},
            "generator": "wf_seasonal7_kit_zehr.build：balance_b.balance_rows / panel_texts → 本模块 "
                         "leader_rows / leader_text / ability6_text（能力6 合并行随队长一并回写）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }
