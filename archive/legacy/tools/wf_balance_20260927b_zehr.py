# -*- coding: utf-8 -*-
'泽赫尔「今晚由团长买单」159997 ``guildknight_leader_tavern``（光）：2026-09-27 平衡调整第二批（无上限成长），纯函数。\n\n口径：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）A 节；设计稿\n``growth/growth_design.json`` 159997（按 live 1.4.1049 重新取数，行号与设计稿一致）。\n放缓倍率按 3 分钟**实际**触发次数分档（口径 A2：≤15 → 1/5；≥30 → 1/10；15–30 → 1/5）：\n\n- 每达成 35 连击（队长 #3）：灯火正旺期间每 35 连击再 +15 连击、队长 #5 每 3 次 PF 后 6 次弹射各 +9，\n  连击在单次飞行内自增 ⇒ 3 分钟 30–50 次、典型 40（≥30）⇒ ×1/10。\n- 每次强化弹射（队长 #4）：队长 #5 的 ComboBoost 让拍板后连击从 9 起，几乎每次拍板都 PF ⇒ 40–60 次、\n  典型 50（≥30）⇒ ×1/10（设计稿按标签给 1/5，口径与复核 C07 改为按实际次数）。\n- 灯芯每层 / 每获得 1 次灯火正旺（能力1 #2 #3、能力3 #0 #3 同一触发：光共鸣 + 单次飞行连击 ≥55，CT 5 秒）：\n  CT 封顶 36 次、典型 25（15–30）⇒ ×1/5；灯芯 3% ÷5 = 0.6% 按口径 A7 / 复核 C09 与索利兹同精度取 0.5%。\n\n落点（行号 = 0 起；除下列格与新增行外逐字保留）：\n\n1. ``leader_ability:159997``：#3（连击≥35 → PF 伤害）c49/c50 50000 → 5000；#4（PF≥1 → 光队攻击力）\n   35000 → 3500。队尾新增（口径 A3：行 = ``[CODE, "0", ""] + 能力行[5:]``，能力 c≥5 → 队长 c−2）：\n   - #6 ← 能力1 #4（持续 134 灯芯层数 → 413 PF 独立乘区，c100 限次 ``(None)``，固有 1599971 上限 99）：\n     c111/c112 3000 → 500。队长先例 = live 稻穗 139995#9（134→413，口径 A4 白名单）。\n   - #7 ← 能力3 #0（光共鸣 + 连击≥55 CT 300 帧 → 光队攻击力）：c49/c50 30000 → 6000。\n   - #8 ← 能力3 #3（同触发 → PF 伤害）：c49/c50 30000 → 6000。\n   队长原有行里没有「同触发、同 kind、同目标、同前置、无 CT」的行（#3 阈值 35、#4 触发 PF）⇒ 全部新起。\n   先例：trig12→32 全队 官方 121001#2 等；trig12→55 官方 341005#1；队长 CT 列官方 111099#2（CT 900）。\n2. 能力侧换成有上限的弱化版（设计稿给值）：能力1 #4 c102 ``(None)`` → ``10``、c113/c114 3000 → 1000\n   （每层 +1%，最多计 10 层 = 10%；官方 134 限 10 先例 1611231#1，0 基）；能力3 #0 c34 ``(None)`` → ``8``、\n   c51/c52 30000 → 10000（满 80%）；能力3 #3 c34 ``(None)`` → ``10``、c51/c52 30000 → 10000（满 100%）。\n   触发、CT、共鸣前置、整键主位（c1=false）不变。能力3 #6（持有灯火正旺时每 1 连击 PF +5%）按设计稿 keep：\n   连击每次拍板清零，属单次飞行内状态值，不随战斗时间累积。\n3. 面板（desc_override，裁决 §3 / 复核 C04·C05 选 B：无上限就写到效果为止，不写「可无限累积」）：\n   队长覆盖串改两数并插两行；能力1 末行改成「＋1%（最多10层）」；能力3 首行拆成两行（各带限次与 CT）。\n   主位槽每行保留 `` <icon id=\'main\'>  ``。技能描述不含这些数值 ⇒ 不改。\n\n生成器：``wf_seasonal7_kit_zehr.build`` 按改版计划重放行 → 套 09-17 灯火修订纯函数\n（``wf_zehr_lamp_revision.revise_rows`` / ``revise_text``）→ 再套本模块 :func:`balance_rows` / :func:`panel_texts`\n（队长覆盖文案底稿 = 09-17 ``wf_seasonal_pf_revision.ZEHR_LEADER_TEXT``，该脚本改完 kit 产物后被能力3 sha 锁住）。\n测试断言「kit 重放 → 灯火修订 → 本批」== :func:`revise`（需要 live/.cdn 的部分 skipUnless）。\n跨角色 donor：``wf_midautumn_kit_hibiki`` PLAN[3] 借 live ``1599971#4``，本批改的 c102/c113/c114 该条都显式钉住\n⇒ 澄波响产物不变（测试断言）。\n\n本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "159997"
CODE = "guildknight_leader_tavern"
PACKAGES = ["s7-zehr"]
#: 候选 manifest 现值 1.0.7（09-17 pf_hit 修订写入）⇒ 1.0.8。
PACKAGE_VERSION = {"s7-zehr": "1.0.8"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2；改后行不需要新能力（revise 内核对）。
CAPABILITIES: list[str] = []
#: 候选 145 个 manifest 条目与文件逐一一致，本模块读的键与 live 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 4                        # master/character c3：光（0 基内部元素）
LIGHT = "White"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
A1, A3 = f"{CID}1", f"{CID}3"
CAS_LEADER = f"desc_override_{CODE}"
CAS_A1 = f"desc_override_{CODE}_1"
CAS_A3 = f"desc_override_{CODE}_3"
UNIQUE = "master/character/unique_condition.orderedmap"
UID_LAMP, UID_WICK = "159997", "1599971"         # 「灯火正旺」/「灯芯」
MAIN_ICON = " <icon id='main'>  "
STRINGS = frozenset({f"change_skill_{CODE}", f"override_string_{CODE}_dual_pf"})

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 s7-zehr 1.0.7 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
#: 两个固有状态只作守卫（灯芯 99 层永续、灯火正旺 15 秒），不返回。
BEFORE: dict[tuple[str, Any], str] = {
    ("leader", CID): "b5328e3c944c5deeb9ed7766bb94b00a3b8466dca447ffdddc8da1aa5ce07bbd",
    ("ability", A1): "44eb9ba8c112881bf65dc9eada8c4d723186e979547ed2da9c160a4b64246720",
    ("ability", A3): "2d877fb8255d4e3c40c51ac56b3739da605f1191661413f38f85dc9a707bbb6e",
    ("cas", CAS_LEADER): "21049b1bccb3bd3440ca7e723e3a0089307c125efc878c8212f04fde8fab3e62",
    ("cas", CAS_A1): "ade39dc911079e501071c15a1019d7fbb45036bc71f62707a5239813067bcf32",
    ("cas", CAS_A3): "120460af56c2b1c0bd7c0f88214e3b33069eaaefdd46253300594d0a353fb89b",
    ("table", (UNIQUE, UID_WICK)): "f1546b68170999b292cbaaf1c6063821e9794946af2cb60a11c3d22cdad34f55",
    ("table", (UNIQUE, UID_LAMP)): "519e4ea24ae352d3e79260dcc09d0bc9a58ec860664660b01beff51212f0002d",
}
WICK_CAP, WICK_FRAMES = "99", "99999999"          # unique_condition c4 层数上限 / c3 帧（永续）
LAMP_FRAMES = "900"                               # 15 秒

# ---------------------------------------------------------------- 队长

LEADER_ROWS_BEFORE, LEADER_ROWS_AFTER = 6, 9
_LEADER_COMBO35 = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "12", 28: "3500000", 29: "3500000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "55",
}
_LEADER_PER_PF = {
    0: CODE, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "2", 28: "100000", 29: "100000",
    32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "32", 46: "5", 47: LIGHT,
}
#: 原位放缓：(改前指纹, 改后指纹)。
LEADER_SLOWED = {
    3: ({**_LEADER_COMBO35, 49: "50000", 50: "50000"}, {**_LEADER_COMBO35, 49: "5000", 50: "5000"}),
    4: ({**_LEADER_PER_PF, 49: "35000", 50: "35000"}, {**_LEADER_PER_PF, 49: "3500", 50: "3500"}),
}

# ---------------------------------------------------------------- 能力1 #4 / 能力3 #0 #3

_A1_WICK = {
    0: f"{CODE}_1", 1: "false", 2: "power_flip", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
    85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 104: UID_WICK, 108: "false",
    109: "413",
}
A1_WICK_INDEX = 4
A1_BEFORE = {**_A1_WICK, 102: "(None)", 113: "3000", 114: "3000"}
A1_AFTER = {**_A1_WICK, 102: "10", 113: "1000", 114: "1000"}

_A3_LAMP = {
    1: "false", 3: "0", 5: "0", 6: "2", 9: "600000", 10: "600000", 11: LIGHT, 13: "0", 20: "0",
    27: "12", 30: "5500000", 31: "5500000", 35: "300", 39: "(None)", 46: "0",
}
A3_LAMP_ATK, A3_LAMP_PF = 0, 3
A3_BEFORE = {
    A3_LAMP_ATK: {**_A3_LAMP, 0: f"{CODE}_3", 2: "attack_common", 34: "(None)", 47: "32", 48: "5",
                  49: LIGHT, 51: "30000", 52: "30000"},
    A3_LAMP_PF: {**_A3_LAMP, 0: f"{CODE}_3", 2: "power_flip", 34: "(None)", 47: "55",
                 51: "30000", 52: "30000"},
}
#: 能力侧有上限的弱化版（设计稿 growth_design 159997 replace_in_ability）：(限次 c34, 强度)。
A3_CAPPED = {A3_LAMP_ATK: ("8", "10000"), A3_LAMP_PF: ("10", "10000")}
A3_AFTER = {i: {**cells, 34: A3_CAPPED[i][0], 51: A3_CAPPED[i][1], 52: A3_CAPPED[i][1]}
            for i, cells in A3_BEFORE.items()}
A1_ROWS, A3_ROWS = 5, 7

#: 队长新增行：(源表, 源行号, 源改前指纹, 强度列, 逐步强度)。
LEADER_NEW_SOURCES = {
    6: ("ability", A1, A1_WICK_INDEX, A1_BEFORE, (111, 112), "500"),          # 灯芯每层 PF 独立乘区 0.5%
    7: ("ability", A3, A3_LAMP_ATK, A3_BEFORE[A3_LAMP_ATK], (49, 50), "6000"),  # 灯火正旺 光队攻击力 6%
    8: ("ability", A3, A3_LAMP_PF, A3_BEFORE[A3_LAMP_PF], (49, 50), "6000"),    # 灯火正旺 PF 伤害 6%
}
#: 队长新增行逐格指纹（= 派生结果；测试逐格对 :func:`leader_row_from_ability`）。
LEADER_NEW = {
    6: {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
        98: "100000", 99: "100000", 100: "(None)", 102: UID_WICK, 106: "false", 107: "413",
        111: "500", 112: "500"},
    7: {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: LIGHT, 11: "0", 18: "0",
        25: "12", 28: "5500000", 29: "5500000", 32: "(None)", 33: "300", 37: "(None)", 44: "0",
        45: "32", 46: "5", 47: LIGHT, 49: "6000", 50: "6000"},
    8: {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: LIGHT, 11: "0", 18: "0",
        25: "12", 28: "5500000", 29: "5500000", 32: "(None)", 33: "300", 37: "(None)", 44: "0",
        45: "55", 49: "6000", 50: "6000"},
}

# ---------------------------------------------------------------- 面板

LEADER_TEXT_REWRITES = (
    ("每达成35连击，强化弹射伤害＋50%", "每达成35连击，强化弹射伤害＋5%"),
    ("每发动强化弹射，光属性角色攻击力＋35%", "每发动强化弹射，光属性角色攻击力＋3.5%"),
)
LEADER_TEXT_ANCHOR = "光属性共鸣时，每发动3次强化弹射，接下来6次弹射各追加9连击"   # 新行插在它之后
LEADER_TEXT_INSERTS = (
    "每1层「灯芯」，强化弹射伤害额外乘区＋0.5%",
    "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋6%、强化弹射伤害＋6%（CT 5s）",
)
A1_TEXT_OLD = MAIN_ICON + "每1层「灯芯」，强化弹射伤害额外乘区＋3%（「灯芯」最多99层）"
A1_TEXT_NEW = MAIN_ICON + "每1层「灯芯」，强化弹射伤害额外乘区＋1%（最多10层）"
A3_TEXT_OLD = MAIN_ICON + "每获得1次「灯火正旺」，光属性角色攻击力＋30%、强化弹射伤害＋30%（CT 5s）"
A3_TEXT_NEW = (MAIN_ICON + "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋10%（最多8次，CT 5s）",
               MAIN_ICON + "光属性共鸣时，每获得1次「灯火正旺」，强化弹射伤害＋10%（最多10次，CT 5s）")
PANEL_LINES = {CAS_LEADER: (6, 8), CAS_A1: (4, 4), CAS_A3: (4, 5)}   # (改前行数, 改后行数)
MAIN_SLOT_PANELS = (CAS_A1, CAS_A3)

#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    f"leader_ability:{CID}#3": "连击≥35 → 自身 强化弹射伤害 5%",
    f"leader_ability:{CID}#4": "强化弹射≥1 → 赋予全队(光) 攻击力 3.5%",
    f"leader_ability:{CID}#6": "持续·状态累积计数固有≥1[固有1599971] → 自身 独立乘区强化弹射伤害 0.5%",
    f"leader_ability:{CID}#7": "光·编成≥6 时: 连击≥55(CT5秒) → 赋予全队(光) 攻击力 6%",
    f"leader_ability:{CID}#8": "光·编成≥6 时: 连击≥55(CT5秒) → 自身 强化弹射伤害 6%",
    f"ability:{A1}#4": "持续·状态累积计数固有≥1(限10次)[固有1599971] → 自身 独立乘区强化弹射伤害 1%",
    f"ability:{A3}#0": "光·编成≥6 时: 连击≥55(限8次)(CT5秒) → 赋予全队(光) 攻击力 10%",
    f"ability:{A3}#3": "光·编成≥6 时: 连击≥55(限10次)(CT5秒) → 自身 强化弹射伤害 10%",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: Any) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise ValueError(f"unreviewed live baseline for {kind}:{key} "
                         f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _row(width: int, cells: dict[int, str]) -> list[str]:
    row = [""] * width
    for col, value in cells.items():
        row[col] = value
    return row


def leader_row_from_ability(row: list[str]) -> list[str]:
    """口径 A3：``[能力行 c0, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2），c0 换成队长键的 code。"""
    if len(row) != ABILITY_NCOLS:
        raise ValueError("ability row width")
    out = [CODE, "0", ""] + list(row[5:])
    if len(out) != LEADER_NCOLS:
        raise AssertionError("derived leader row width")
    return out


def _revise_rows(rows: list[list[str]], width: int, label: str,
                 targets: dict[int, tuple[dict[int, str], dict[int, str]]]) -> list[list[str]]:
    """``targets`` 行必须逐格等于改前或改后指纹，改成改后；其余行原样（幂等）。"""
    if any(len(row) != width for row in rows):
        raise ValueError(f"{label}: unexpected row width")
    out = deepcopy(rows)
    for index, (before, after) in targets.items():
        if index >= len(out):
            raise ValueError(f"{label}#{index}: row missing")
        if not (_matches(out[index], width, before) or _matches(out[index], width, after)):
            raise ValueError(f"{label}#{index}: row is not the reviewed shape")
        out[index] = _row(width, after)
    for index, (old, new) in enumerate(zip(rows, out)):
        if index not in targets and old != new:
            raise AssertionError(f"{label}#{index}: untouched row changed")
    return out


def ability1_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力1 #4：灯芯每层 PF 独立乘区 3% 无上限 → 1%、最多计 10 层；其余 4 行逐字保留。"""
    if len(rows) != A1_ROWS:
        raise ValueError(f"ability {A1}: expected {A1_ROWS} records, got {len(rows)}")
    out = _revise_rows(rows, ABILITY_NCOLS, f"ability:{A1}", {A1_WICK_INDEX: (A1_BEFORE, A1_AFTER)})
    if {row[1] for row in out} != {"false"}:
        raise ValueError(f"ability {A1}: whole-key main-slot flag drifted")
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #0 / #3：每获得 1 次灯火正旺 光队攻 / PF 伤 30% 无上限 → 10%、限 8 / 10 次；其余逐字保留。"""
    if len(rows) != A3_ROWS:
        raise ValueError(f"ability {A3}: expected {A3_ROWS} records, got {len(rows)}")
    out = _revise_rows(rows, ABILITY_NCOLS, f"ability:{A3}",
                       {i: (A3_BEFORE[i], A3_AFTER[i]) for i in A3_BEFORE})
    if {row[1] for row in out} != {"false"}:
        raise ValueError(f"ability {A3}: whole-key main-slot flag drifted")
    return out


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 #3 #4 原位放缓；队尾追加 #6（灯芯）#7 #8（灯火正旺）；已追加则只核对。"""
    if any(len(row) != LEADER_NCOLS for row in rows):
        raise ValueError(f"leader_ability {CID}: unexpected row width")
    expected = [_row(LEADER_NCOLS, LEADER_NEW[i]) for i in sorted(LEADER_NEW)]
    if len(rows) == LEADER_ROWS_AFTER:
        if rows[LEADER_ROWS_BEFORE:] != expected:
            raise ValueError(f"leader_ability {CID}: appended rows are not the reviewed shape")
        head = rows[:LEADER_ROWS_BEFORE]
    elif len(rows) == LEADER_ROWS_BEFORE:
        head = rows
    else:
        raise ValueError(f"leader_ability {CID}: expected {LEADER_ROWS_BEFORE} (or revised "
                         f"{LEADER_ROWS_AFTER}) records, got {len(rows)}")
    out = _revise_rows(head, LEADER_NCOLS, f"leader_ability:{CID}", LEADER_SLOWED) + expected
    for index, row in enumerate(out[:LEADER_ROWS_BEFORE]):
        if row[45] == "413" or row[107] == "413" or (row[25] == "12" and row[28] == "5500000"):
            raise ValueError(f"leader_ability {CID}#{index}: pre-existing lamp/wick row would duplicate")
    return out


def balance_rows(leader: list[list[str]], ability1: list[list[str]], ability3: list[list[str]]
                 ) -> tuple[list[list[str]], list[list[str]], list[list[str]]]:
    """生成器链入口（``wf_seasonal7_kit_zehr.build`` 在 09-17 灯火修订之后调用）。"""
    return leader_rows(leader), ability1_rows(ability1), ability3_rows(ability3)


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"{key}: expected one single-column row")
    return rows[0][0]


def _lines(text: str, key: str, count: int) -> list[str]:
    lines = text.split("\n")
    if len(lines) != count:
        raise ValueError(f"{key}: expected {count} panel lines, got {len(lines)}")
    return lines


def leader_text(text: str) -> str:
    before, after = PANEL_LINES[CAS_LEADER]
    lines = text.split("\n")
    if len(lines) == after and all(new in lines for _old, new in LEADER_TEXT_REWRITES) \
            and all(line in lines for line in LEADER_TEXT_INSERTS):
        return text
    lines = _lines(text, CAS_LEADER, before)
    for old, new in LEADER_TEXT_REWRITES:
        if lines.count(old) != 1:
            raise ValueError(f"{CAS_LEADER}: line {old!r} not found exactly once")
        lines[lines.index(old)] = new
    if lines.count(LEADER_TEXT_ANCHOR) != 1:
        raise ValueError(f"{CAS_LEADER}: anchor line missing")
    at = lines.index(LEADER_TEXT_ANCHOR) + 1
    lines[at:at] = list(LEADER_TEXT_INSERTS)
    return "\n".join(lines)


def ability1_text(text: str) -> str:
    before, after = PANEL_LINES[CAS_A1]
    lines = _lines(text, CAS_A1, before)
    if lines[-1] == A1_TEXT_NEW:
        return text
    if lines[-1] != A1_TEXT_OLD:
        raise ValueError(f"{CAS_A1}: wick line drifted: {lines[-1]!r}")
    lines[-1] = A1_TEXT_NEW
    return "\n".join(lines)


def ability3_text(text: str) -> str:
    before, after = PANEL_LINES[CAS_A3]
    lines = text.split("\n")
    if len(lines) == after and tuple(lines[:2]) == A3_TEXT_NEW:
        return text
    lines = _lines(text, CAS_A3, before)
    if lines[0] != A3_TEXT_OLD:
        raise ValueError(f"{CAS_A3}: lamp line drifted: {lines[0]!r}")
    return "\n".join(list(A3_TEXT_NEW) + lines[1:])


def panel_texts(texts: dict[str, str]) -> dict[str, str]:
    """三条覆盖串（队长 / 能力1 / 能力3）→ 改后文本；已改则原样（幂等）。"""
    return {CAS_LEADER: leader_text(texts[CAS_LEADER]), CAS_A1: ability1_text(texts[CAS_A1]),
            CAS_A3: ability3_text(texts[CAS_A3])}


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows: list[list[str]]) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, STRINGS, kind)
                  + L.ability_element_column_problems(kind, row, ELEMENT)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def panel_problems(texts: dict[str, str]) -> list[str]:
    import wf_midautumn_kitlib as KL
    probs = [f"{key}: {p}" for key, text in texts.items() for p in KL.panel_problems(text)]
    for key, text in texts.items():
        lines = text.split("\n")
        if "／" in text:
            probs.append(f"{key}: uses 「／」 instead of line breaks")
        if len(lines) != PANEL_LINES[key][1]:
            probs.append(f"{key}: {len(lines)} lines != {PANEL_LINES[key][1]}")
        if key in MAIN_SLOT_PANELS:
            probs += [f"{key}#{i}: main-slot line lacks icon prefix"
                      for i, line in enumerate(lines) if not line.startswith(MAIN_ICON)]
        elif MAIN_ICON.strip() in text:
            probs.append(f"{key}: leader panel carries a main-slot icon")
    return probs


def capability_set(kind: str, rows: list[list[str]]) -> set[str]:
    import wf_client_legality as L
    return {cap for row in rows for cap in L.required_client_capabilities(kind, row)}


def _unique_guard(wick: list[list[str]], lamp: list[list[str]]) -> None:
    if len(wick) != 1 or (wick[0][3], wick[0][4]) != (WICK_FRAMES, WICK_CAP):
        raise ValueError("「灯芯」 is no longer permanent with a 99-layer cap")
    if len(lamp) != 1 or lamp[0][3] != LAMP_FRAMES:
        raise ValueError("「灯火正旺」 duration drifted from 15 s")


# ---------------------------------------------------------------- 批次入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader_in = _checked(read, "leader", CID)
    a1_in = _checked(read, "ability", A1)
    a3_in = _checked(read, "ability", A3)
    texts_in = {key: _single_text(_checked(read, "cas", key), key) for key in (CAS_LEADER, CAS_A1, CAS_A3)}
    _unique_guard(_checked(read, "table", (UNIQUE, UID_WICK)), _checked(read, "table", (UNIQUE, UID_LAMP)))
    leader, a1, a3 = balance_rows(leader_in, a1_in, a3_in)
    texts = panel_texts(texts_in)
    probs = (row_problems("leader_ability", leader) + row_problems("ability", a1)
             + row_problems("ability", a3) + panel_problems(texts))
    if probs:
        raise ValueError(probs)
    new_caps = ((capability_set("leader_ability", leader) - capability_set("leader_ability", leader_in))
                | (capability_set("ability", a1 + a3) - capability_set("ability", a1_in + a3_in)))
    if new_caps - set(CAPABILITIES):
        raise ValueError(f"revised rows need undeclared client capabilities: {sorted(new_caps)}")
    return {
        "ability": {A1: a1, A3: a3},
        "leader": {CID: leader},
        "cas": {key: [[text]] for key, text in texts.items()},
        "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_zehr.py",
            "rules": "第二批施工口径 A2/A3/A7（复核 C09 灯芯 0.5%）；设计稿 growth_design 159997；"
                     "面板按裁决 §3 / C04·C05 选 B（不写可无限累积）",
            "changes": {
                f"leader_ability:{CID}#3 c49/c50": "50000 → 5000（每 35 连击 PF 伤 50% → 5%，×1/10）",
                f"leader_ability:{CID}#4 c49/c50": "35000 → 3500（每次 PF 光队攻 35% → 3.5%，×1/10）",
                f"leader_ability:{CID}#6": "新增 ← 能力1 #4：灯芯每层 PF 独立乘区 0.5%（3% ×1/5 取 0.5）",
                f"leader_ability:{CID}#7": "新增 ← 能力3 #0：每获得灯火正旺 光队攻 6%（30% ×1/5，CT 5s）",
                f"leader_ability:{CID}#8": "新增 ← 能力3 #3：每获得灯火正旺 PF 伤 6%（30% ×1/5，CT 5s）",
                f"ability:{A1}#4 c102/c113/c114": "(None)/3000/3000 → 10/1000/1000（每层 1%，最多 10 层）",
                f"ability:{A3}#0 c34/c51/c52": "(None)/30000/30000 → 8/10000/10000",
                f"ability:{A3}#3 c34/c51/c52": "(None)/30000/30000 → 10/10000/10000",
                f"{CAS_LEADER}": "两数改写 + 插入灯芯 / 灯火正旺两行",
                f"{CAS_A1}": "末行 ＋3%（「灯芯」最多99层） → ＋1%（最多10层）",
                f"{CAS_A3}": "首行拆成光队攻 ＋10%（最多8次）与 PF 伤 ＋10%（最多10次）两行",
            },
            "frequency": {
                "every_35_combo": "30–50 次，典型 40（灯火正旺 +15/35 连击、ComboBoost +9/弹射自增）⇒ ×1/10",
                "every_pf": "40–60 次，典型 50（队长 #5 ComboBoost 让几乎每次拍板都 PF）⇒ ×1/10",
                "lamp_or_wick": "光共鸣 + 单次飞行连击 ≥55、CT 5 秒：上限 36、典型 25（15–30）⇒ ×1/5",
            },
            "growth_3min_typical": "队长：PF 伤 +2000% → +200%（#3）＋灯火正旺 +150%（#8）；光队攻 +1750% → +175%（#4）"
                                   "＋灯火正旺 +150%（#7）；灯芯 25 层独立乘区 +12.5%（99 层满 49.5%）。"
                                   "能力侧封顶：灯芯 10%、光队攻 80%、PF 伤 100%（原 +75% / +750% / +750%）",
            "kept": "能力3 #6 持有灯火正旺时每 1 连击 PF +5%（单次飞行状态值）；能力5 / 6 充能（口径 A6）",
            "describe_after": DESCRIBE_AFTER,
            "generator": "wf_seasonal7_kit_zehr.build 在 09-17 灯火修订纯函数之后调用 balance_rows / panel_texts"
                         "（队长文案底稿 wf_seasonal_pf_revision.ZEHR_LEADER_TEXT）",
            "donor_pins": "wf_midautumn_kit_hibiki PLAN[3] 借 1599971#4，c102/c113/c114 已显式钉住",
            "leader_precedents": "134→413 live 139995#9；trig12→32 全队 官方 121001#2；trig12→55 官方 341005#1；"
                                 "队长 CT 官方 111099#2",
            "capabilities": [],
            "runtime_verified": False,
        },
    }
