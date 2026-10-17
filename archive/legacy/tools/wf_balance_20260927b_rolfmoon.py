# -*- coding: utf-8 -*-
'2026-09-27 平衡第二批：罗尔夫「不落幕的安可」149986 ``black_wolf_knight_moon``（风）的键级修订。\n\n口径 = ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（A 无上限成长 / B Down），\n设计参考 = ``growth/growth_design.json`` designs[149986] ＋ critic C08、``growth/down_design.json``。\n设计稿按 live 1.4.1048 写；本模块按 live 1.4.1049 重读（本角色 1.4.1048→1049 无变化，候选与 live 逐字相同）。\n\n改动（其余行、其余列、其余节点逐字保留）：\n\n1. **队长 L#3/L#4**（风共鸣：风队每 100 次直击 → 风队攻击力 / 直击伤害，trigger 20，不限次）：\n   c49/c50 100000 → 20000（+100% → +20%）。3 分钟约 20 次（区间 10–30）⇒ 口径 A.2 的 15–30 档取 1/5。\n   已在队长技 ⇒ 原位放缓（A.3）。\n2. **能力6 A6#3**（前置 42 队长承载：同一触发 → 风队直击独立乘区 693，不限次）：c51/c52 10000 → 2000\n   （+10% → +2%，同频 1/5）。693 队长表零先例（生成器 FORBIDDEN_LEADER_KINDS），本来就是能力行＋前置 42 承载，原位放缓。\n3. **能力3 A3#1/#2**（速度固定每持续 60 帧，trigger 246，不限次，自身攻击力 / 直击伤害 +50%）：\n   无上限成长只给队长——trigger 246 在官方与 live 自制队长表都是 0 行（口径 A.4 / 复核 C08）⇒ **不进队长表**，\n   改为 **能力6 追加 A6#5/#6**：原行整行搬过去，c0/c1/c2 换成能力6 键值、c6 前置 42（持有者为队长），\n   强度 50000 → 5000（+50% → +5%；3 分钟约 70–110 次 ⇒ ≥30 取 1/10）。原行没有共鸣前置，承载行也不加。\n   能力3 原位换成**有上限版本**（设计稿 replacement）：D214「持有最大速度固定时」自身攻击力 / 直击伤害 +100%\n   （行形 = 官方 D214 donor 1411892#0，同本角色 A2#0；持有即生效、不叠层；官方自身持续带 160/150）。\n   队长表仍 7 行。\n4. **面板**：队长 desc_override 第 5 行数值同步、原能力3 读秒那句（数值 5%）移进队长面板第 6 行；\n   能力3 desc_override 第 2 行换成「自身处于最大速度固定状态时：自身攻击力＋100%、直击伤害＋100%」。\n   能力6 desc_override 只写碰撞回槽（承载行一向不进能力6 面板），不动。\n5. **Down**：629 追击树 ``ability_skill_wolf_moon_encore``（A3#4 触发，CT 300 帧 = 5 秒 > 3 秒 ⇒ 每次 ≤3）\n   两条 CreateNormalAttack 的 p13：斩击 10 → 1.5、爆击 1 → 0.1（×10 段）⇒ 每次 20 → 2.5。\n   正常技能两档（每次 20）不动。\n\n生成器 ``wf_midautumn_kit_rolf``：LEADER / PLAN[3] / PLAN[6] / EXPECT / PANEL_* / ``retune_encore_detoughness``\n已同步（``BALANCE_B`` / ``ENCORE_DETOUGHNESS``），测试断言生成器输出 == :func:`revise` 输出。\n设计镜像（design/rolf.json 的 plan_rework1 计数 ＋ rework1.balance_20260927b、rework1/panel/rolf.json）由\n:func:`sync_mirrors` 幂等同步。本模块只读 ``read()``；不写 live store / assets / .cdn / 候选包，不发布，不 git。\n'
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl
import wf_midautumn_kitlib as KL

CID = "149986"
CODE = "black_wolf_knight_moon"
PACKAGES = ["ma-rolf"]
#: 候选 manifest 现值 1.0.0；包档案 ${WF_ROOT}/pkgarchive/ma-rolf-20260920-1.4.{945..1003} 八份全是 1.0.0 ⇒ 下一号。
PACKAGE_VERSION = {"ma-rolf": "1.0.1"}
#: 候选已声明 dash-parameter-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 ma-rolf 与 live 在本模块读取的全部键上逐字相同、manifest 哈希无漂移（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                        # master/character c3：风（0 基内部元素）
ELEMENT_TOKEN = "Green"
MAIN_ICON = " <icon id='main'>  "
ABILITY_NCOLS, LEADER_NCOLS = 126, 124

LEADER_KEY = CID
A3_KEY, A6_KEY = f"{CID}3", f"{CID}6"
CAS_LEADER = f"desc_override_{CODE}"
CAS_A3 = f"desc_override_{CODE}_3"
CAS_KEYS = frozenset({"ability_skill_wolf_moon_encore", f"change_skill_{CODE}", f"change_skill_{CODE}_2",
                      CAS_LEADER, *(f"desc_override_{CODE}_{slot}" for slot in range(1, 7))})
ENCORE_KEY = "ability_skill_wolf_moon_encore"
ENCORE_PROGRAM = f"battle/action/skill/action/ability_skill/{ENCORE_KEY}${ENCORE_KEY}"

# ---------------------------------------------------------------- 数值

DIRECT_GROWTH = ("100000", "20000")        # 队长 L#3/L#4：+100% → +20%（1/5）
DIRECT_GROWTH_IC693 = ("10000", "2000")    # A6#3：+10% → +2%（1/5）
KEEP_FRAME_GROWTH = ("50000", "5000")      # A3#1/#2 → A6#5/#6：+50% → +5%（1/10）
HOLD_FIXED_SPEED = "100000"                # A3#1/#2 新：持有最大速度固定时 +100%
ENCORE_CT_FRAMES = "300"                   # A3#4 629 的 c35（5 秒）
ENCORE_DETOUGHNESS = {"slash": (10, 1.5), "burst": (1, 0.1)}   # (改前, 改后)
ENCORE_HITS = {"slash": 1, "burst": 10}
CNA_P13 = 13

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数；候选 ma-rolf 1.0.0 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "bc03bd6528eb489e98f7a6446423f70c8bcec82032a75eb5b4b1bff3bea6daf3",
    ("ability", A3_KEY): "4bf73cdf1f6a6388ba66e5fb8fd92e2a0017c42914879e2a6d9dd2d491cf1c5c",
    ("ability", A6_KEY): "e4cd89da7f2abcf7af07f45c51d9c1e26f166378bd27f8d9327a998aa842949a",
    ("cas", CAS_LEADER): "3ee2c15c911d5d3245da34b219914229cf70742fcdd317ee713a5dc7f73b01c9",
    ("cas", CAS_A3): "0033c5764c9ea5703ab08f486f6400605aef11c5d81b428cbd20a5d4ba8c211e",
    ("dsl", ENCORE_PROGRAM): "a6714390caf428cb79fc8cf6793e1ad2cd39b41aa340a1cfad4c953b5a22c100",
}

# ---------------------------------------------------------------- 行指纹（BEFORE 之外的第二道锁）

_LEADER_COMMON = {0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                  11: "0", 18: "0", 37: "(None)", 44: "0"}
_DIRECT_TRIGGER_L = {25: "20", 26: "7", 27: ELEMENT_TOKEN, 28: "10000000", 29: "10000000",
                     32: "(None)", 33: "0"}
LEADER_BEFORE = {
    3: {**_LEADER_COMMON, **_DIRECT_TRIGGER_L, 45: "32", 46: "5", 47: ELEMENT_TOKEN,
        49: DIRECT_GROWTH[0], 50: DIRECT_GROWTH[0]},
    4: {**_LEADER_COMMON, **_DIRECT_TRIGGER_L, 45: "33", 46: "5", 47: ELEMENT_TOKEN,
        49: DIRECT_GROWTH[0], 50: DIRECT_GROWTH[0]},
}

_A3_HEAD = {0: f"{CODE}_3", 1: "false", 2: "attack_common", 3: "0"}
_KEEP_FRAME = {5: "0", 6: "0", 13: "0", 20: "0", 27: "246", 30: "100000", 31: "100000",
               32: "6000000", 33: "6000000", 34: "(None)", 35: "0", 39: "(None)", 46: "0", 48: "0"}
A3_BEFORE = {
    1: {**_A3_HEAD, **_KEEP_FRAME, 47: "32", 51: KEEP_FRAME_GROWTH[0], 52: KEEP_FRAME_GROWTH[0]},
    2: {**_A3_HEAD, **_KEEP_FRAME, 47: "33", 51: KEEP_FRAME_GROWTH[0], 52: KEEP_FRAME_GROWTH[0]},
}
#: 能力3 #1/#2 新行：D214（持有最大速度固定）→ 持续 kind 0 攻击力 / 1 直击伤害，自身，+100%。
#: 行形 = 官方 D214 donor 1411892#0（同 A2#0）：during 块 c85 必须 (None)、D214 puller c98/c99 必须留空。
_HOLD = {5: "1", 6: "0", 13: "0", 20: "0", 85: "(None)", 97: "214", 108: "false", 110: "0",
         113: HOLD_FIXED_SPEED, 114: HOLD_FIXED_SPEED}
A3_AFTER = {1: {**_A3_HEAD, **_HOLD, 109: "0"}, 2: {**_A3_HEAD, **_HOLD, 109: "1"}}
#: 同键的 629 追击行（读 CT 用于削韧上限判定）
A3_ENCORE_ROW = 4
A3_ENCORE_CELLS = {**_A3_HEAD, 5: "0", 6: "2", 9: "600000", 10: "600000", 11: ELEMENT_TOKEN, 13: "0",
                   20: "0", 27: "12", 30: "10000000", 31: "10000000", 34: "(None)",
                   35: ENCORE_CT_FRAMES, 39: "(None)", 46: "0", 47: "629", 70: ENCORE_KEY,
                   71: ENCORE_PROGRAM}

_A6_HEAD = {0: f"{CODE}_6", 1: "true", 2: "special", 3: "0"}
A6_IC693_ROW = 3
A6_IC693_BEFORE = {**_A6_HEAD, 5: "0", 6: "42", 13: "2", 16: "600000", 17: "600000", 18: ELEMENT_TOKEN,
                   20: "0", 27: "20", 28: "7", 29: ELEMENT_TOKEN, 30: "10000000", 31: "10000000",
                   34: "(None)", 35: "0", 39: "(None)", 46: "0", 47: "693", 48: "5", 49: ELEMENT_TOKEN,
                   51: DIRECT_GROWTH_IC693[0], 52: DIRECT_GROWTH_IC693[0]}
A6_ROWS_BEFORE = 5
#: 追加的两条队长承载行：原 A3#1/#2 整行，只换能力6 键值 ＋ 前置 42 ＋ 强度。
A6_CARRIER_CHANGES = {**_A6_HEAD, 6: "42", 51: KEEP_FRAME_GROWTH[1], 52: KEEP_FRAME_GROWTH[1]}

# ---------------------------------------------------------------- 面板

OLD_LEADER_LINE = ("风属性共鸣时：风属性角色每造成100次直接攻击，风属性角色攻击力＋100%、直击伤害＋100%，"
                   "直击伤害额外乘区＋10%")
NEW_LEADER_LINE = ("风属性共鸣时：风属性角色每造成100次直接攻击，风属性角色攻击力＋20%、直击伤害＋20%，"
                   "直击伤害额外乘区＋2%")
NEW_LEADER_KEEP_FRAME_LINE = "最大速度固定效果持续期间，每持续1秒，自身攻击力＋5%、直击伤害＋5%"
LEADER_LINE = 4                    # 0 基；新读秒行插在它后面（第 6 行），开局槽那行顺延到第 7 行
LEADER_LINES_BEFORE = 6
OLD_A3_LINE = MAIN_ICON + "最大速度固定效果持续期间，每持续1秒，自身攻击力＋50%、直击伤害＋50%"
NEW_A3_LINE = MAIN_ICON + "自身处于最大速度固定状态时：自身攻击力＋100%、直击伤害＋100%"
A3_LINE = 1
A3_LINES = 4


class RolfMoonBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise RolfMoonBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                   f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _row(cells: dict[int, str], ncols: int) -> list[str]:
    row = [""] * ncols
    for col, value in cells.items():
        row[col] = value
    return row


def _matches(row: list[str], cells: dict[int, str], ncols: int) -> bool:
    return (len(row) == ncols and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _changed_rows(before: list, after: list) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(before, after)) if a != b]


# ---------------------------------------------------------------- 词条

def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长 L#3/L#4：c49/c50 100000 → 20000；其余 5 行与本两行其余列逐字保留。"""
    if len(rows) != 7 or any(len(r) != LEADER_NCOLS for r in rows):
        raise RolfMoonBalanceError(f"leader {LEADER_KEY}: expected 7×{LEADER_NCOLS} rows")
    out = deepcopy(rows)
    for index, cells in LEADER_BEFORE.items():
        if not _matches(rows[index], cells, LEADER_NCOLS):
            raise RolfMoonBalanceError(f"leader {LEADER_KEY}#{index}: direct-growth row drifted")
        out[index][49] = out[index][50] = DIRECT_GROWTH[1]
    if _changed_rows(rows, out) != sorted(LEADER_BEFORE):
        raise AssertionError("leader_rows touched another record")
    return out


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #1/#2：IT 246 无上限成长行 → D214 持有最大速度固定 +100%（整行替换）。"""
    if len(rows) != 6 or any(len(r) != ABILITY_NCOLS for r in rows):
        raise RolfMoonBalanceError(f"ability {A3_KEY}: expected 6×{ABILITY_NCOLS} rows")
    for index, cells in A3_BEFORE.items():
        if not _matches(rows[index], cells, ABILITY_NCOLS):
            raise RolfMoonBalanceError(f"ability {A3_KEY}#{index}: keep-frame growth row drifted")
    if not _matches(rows[A3_ENCORE_ROW], A3_ENCORE_CELLS, ABILITY_NCOLS):
        raise RolfMoonBalanceError(f"ability {A3_KEY}#{A3_ENCORE_ROW}: 629 encore row drifted")
    out = deepcopy(rows)
    for index, cells in A3_AFTER.items():
        out[index] = _row(cells, ABILITY_NCOLS)
    if _changed_rows(rows, out) != sorted(A3_AFTER):
        raise AssertionError("ability3_rows touched another record")
    return out


def carrier_rows(a3_rows: list[list[str]]) -> list[list[str]]:
    """A3#1/#2（改前）→ 能力6 队长承载行：c0/c1/c2 换键值、c6 前置 42、强度 50% → 5%。"""
    out = []
    for index in sorted(A3_BEFORE):
        row = deepcopy(a3_rows[index])
        if not _matches(row, A3_BEFORE[index], ABILITY_NCOLS):
            raise RolfMoonBalanceError(f"ability {A3_KEY}#{index}: keep-frame growth row drifted")
        for col, value in A6_CARRIER_CHANGES.items():
            row[col] = value
        out.append(row)
    return out


def ability6_rows(rows: list[list[str]], carriers: list[list[str]]) -> list[list[str]]:
    """能力6：#3 693 10% → 2%；末尾追加两条 IT 246 承载行（#5/#6，既有 #0..#4 下标不变）。"""
    if len(rows) != A6_ROWS_BEFORE or any(len(r) != ABILITY_NCOLS for r in rows):
        raise RolfMoonBalanceError(f"ability {A6_KEY}: expected {A6_ROWS_BEFORE}×{ABILITY_NCOLS} rows")
    if not _matches(rows[A6_IC693_ROW], A6_IC693_BEFORE, ABILITY_NCOLS):
        raise RolfMoonBalanceError(f"ability {A6_KEY}#{A6_IC693_ROW}: 693 growth row drifted")
    if any(row[27] == "246" for row in rows):
        raise RolfMoonBalanceError(f"ability {A6_KEY} already carries a trigger-246 row")
    if any((r[0], r[1], r[2]) != (f"{CODE}_6", "true", "special") for r in rows):
        raise RolfMoonBalanceError(f"ability {A6_KEY}: key head drifted")
    out = deepcopy(rows)
    out[A6_IC693_ROW][51] = out[A6_IC693_ROW][52] = DIRECT_GROWTH_IC693[1]
    if _changed_rows(rows, out) != [A6_IC693_ROW]:
        raise AssertionError("ability6_rows touched another record")
    return out + deepcopy(carriers)


# ---------------------------------------------------------------- 面板

def leader_text(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise RolfMoonBalanceError(f"{CAS_LEADER}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != LEADER_LINES_BEFORE or lines[LEADER_LINE] != OLD_LEADER_LINE:
        raise RolfMoonBalanceError(f"{CAS_LEADER}: unexpected panel text layout")
    if NEW_LEADER_KEEP_FRAME_LINE in lines:
        raise RolfMoonBalanceError(f"{CAS_LEADER}: keep-frame line already present")
    lines = lines[:LEADER_LINE] + [NEW_LEADER_LINE, NEW_LEADER_KEEP_FRAME_LINE] + lines[LEADER_LINE + 1:]
    return [["\n".join(lines)]]


def ability3_text(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise RolfMoonBalanceError(f"{CAS_A3}: expected one single-column row")
    lines = rows[0][0].split("\n")
    if len(lines) != A3_LINES or lines[A3_LINE] != OLD_A3_LINE:
        raise RolfMoonBalanceError(f"{CAS_A3}: unexpected panel text layout")
    if any(not line.startswith(MAIN_ICON) for line in lines):
        raise RolfMoonBalanceError(f"{CAS_A3}: main-position slot lines must start with the main icon")
    lines[A3_LINE] = NEW_A3_LINE
    return [["\n".join(lines)]]


def panel_problems(cas: dict[str, list[list[str]]]) -> list[str]:
    problems = []
    for key, rows in cas.items():
        text = rows[0][0]
        if "／" in text:
            problems.append(f"{key}: uses 「／」 instead of line breaks")
        for line in text.split("\n"):
            problems += [f"{key}: {p}" for p in KL.panel_problems(line.replace(MAIN_ICON, ""))]
            if key == CAS_A3 and not line.startswith(MAIN_ICON):
                problems.append(f"{key}: main-position line without the icon: {line}")
    return problems


# ---------------------------------------------------------------- DSL

def encore_tree(tree) -> tuple[list, dict[str, Any]]:
    """629 追击树两条 CreateNormalAttack 的 p13：10 → 1.5（斩击 1 段）、1 → 0.1（爆击 10 段）。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl" and out[10] == 0):
        raise RolfMoonBalanceError("encore tree root drifted")
    areas: dict[int, list] = {}
    for area in wf_dsl.iter_dsl_commands(out, "CreateHitArea"):
        hits = area[14]
        if not (isinstance(hits, list) and hits[0] == "CalculatedUsingMaxNumOfHits"):
            raise RolfMoonBalanceError(f"encore hit-area hit count form drifted: {hits!r}")
        areas[int(hits[1])] = area
    if sorted(areas) != sorted(ENCORE_HITS.values()):
        raise RolfMoonBalanceError(f"encore hit counts {sorted(areas)} drifted")
    if len(list(wf_dsl.iter_dsl_commands(out, "CreateNormalAttack"))) != len(ENCORE_HITS):
        raise RolfMoonBalanceError("encore CreateNormalAttack count drifted")
    per_cast = {"before": 0.0, "after": 0.0}
    for tag, hits in ENCORE_HITS.items():
        attacks = list(wf_dsl.iter_dsl_commands(areas[hits][23], "CreateNormalAttack"))
        if len(attacks) != 1:
            raise RolfMoonBalanceError(f"encore {tag}: expected one CreateNormalAttack")
        old, new = ENCORE_DETOUGHNESS[tag]
        if attacks[0][CNA_P13] != [{"min": old, "max": old}]:
            raise RolfMoonBalanceError(f"encore {tag} p13 drifted: {attacks[0][CNA_P13]!r}")
        attacks[0][CNA_P13] = [{"min": new, "max": new}]
        per_cast["before"] += old * hits
        per_cast["after"] += new * hits
    per_cast = {k: round(v, 6) for k, v in per_cast.items()}
    return out, per_cast


def dsl_problems(tree) -> list[str]:
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    problems = (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                + L.invoke_skill_string_problems(row, set(CAS_KEYS), kind))
    if kind == "ability":
        problems += L.ability_element_column_problems(kind, row, ELEMENT)
    if L.required_client_capabilities(kind, row) and row[109] != "422":
        problems.append(f"unexpected capability {L.required_client_capabilities(kind, row)}")
    return problems


# ---------------------------------------------------------------- 入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader = _checked(read, "leader", LEADER_KEY)
    a3 = _checked(read, "ability", A3_KEY)
    a6 = _checked(read, "ability", A6_KEY)
    cas_leader = _checked(read, "cas", CAS_LEADER)
    cas_a3 = _checked(read, "cas", CAS_A3)
    encore = _checked(read, "dsl", ENCORE_PROGRAM)

    new_leader = leader_rows(leader)
    new_a6 = ability6_rows(a6, carrier_rows(a3))
    new_a3 = ability3_rows(a3)
    cas = {CAS_LEADER: leader_text(cas_leader), CAS_A3: ability3_text(cas_a3)}

    ct_frames = int(a3[A3_ENCORE_ROW][35])
    cap = 1 if ct_frames <= 180 else 3                 # 口径 B.3：CT ≤3 秒每次 ≤1，否则 ≤3
    tree, per_cast = encore_tree(encore)
    if per_cast["after"] > cap:
        raise RolfMoonBalanceError(f"encore detoughness {per_cast['after']} > cap {cap} (CT {ct_frames} 帧)")

    problems = [f"leader#{i}: {p}" for i, row in enumerate(new_leader)
                for p in row_problems("leader_ability", row)]
    problems += [f"{key}#{i}: {p}" for key, rows in ((A3_KEY, new_a3), (A6_KEY, new_a6))
                 for i, row in enumerate(rows) for p in row_problems("ability", row)]
    problems += panel_problems(cas)
    problems += [f"dsl: {p}" for p in dsl_problems(tree)]
    if problems:
        raise RolfMoonBalanceError("; ".join(problems))

    return {
        "ability": {A3_KEY: new_a3, A6_KEY: new_a6},
        "leader": {LEADER_KEY: new_leader},
        "cas": cas,
        "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": {ENCORE_PROGRAM: tree},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_rolfmoon.py",
            "character": f"{CID} {CODE} 罗尔夫「不落幕的安可」（风，中秋；不是 wt26 179999）",
            "spec": "第二批施工口径 A（无上限成长）/ B.3（629 每次 ≤3）；growth_design 149986 ＋ critic C08；"
                    "down_design 149986",
            "live_tail": "1.4.1049（设计稿基于 1.4.1048，本角色两版逐字相同）",
            "frequency": {
                "direct_100": "每 100 次风队直击：3 名风主位 × 直击 3 段 × 每秒 1–2 次碰撞 ⇒ 3 分钟约 1000–3000 次直击 "
                              "⇒ 约 10–30 次触发（中值 20）⇒ 口径 A.2 15–30 档取 1/5",
                "keep_frame_246": "速度固定每持续 60 帧：技能约 20 秒一次，每次速度固定约 8–13 秒（队长 690 +100%、"
                                  "A5 690 +25% 延长）⇒ 3 分钟约 70–110 次（中值 90）⇒ ≥30 取 1/10。"
                                  "前提是 246 在状态持续期间每 60 帧重复触发（生成器注释与面板「每持续1秒」同义），无真机计数",
            },
            "growth_3min": {
                "team_atk_direct": "每 100 直击约 20 次（10–30）：风队攻击力/直击伤害各 +2000% → +400%（+200%–+600%）",
                "team_direct_ic693": "+200% → +40%（+20%–+60%）",
                "self_keep_frame_leader": "读秒约 90 次（70–110）：自身攻击力/直击伤害各 +4500% → 仅队长 +450%（+350%–+550%）",
                "self_hold_fixed_speed": "能力3（主位）速度固定期间常驻 自身攻击力/直击伤害各 +100%，不随时间增长",
            },
            "changes": {
                f"leader:{LEADER_KEY}#3 c49/c50": "100000 → 20000（风队每 100 直击 攻击力 +100% → +20%）",
                f"leader:{LEADER_KEY}#4 c49/c50": "100000 → 20000（风队每 100 直击 直击伤害 +100% → +20%）",
                f"ability:{A6_KEY}#3 c51/c52": "10000 → 2000（队长承载 693 直击独立乘区 +10% → +2%）",
                f"ability:{A3_KEY}#1/#2": "IT 246 读秒 自身攻击力/直击伤害 +50%（不限次）→ D214 持有最大速度固定时 "
                                         "自身攻击力/直击伤害 +100%（持有型，不叠层）",
                f"ability:{A6_KEY}#5/#6（新增）": "原 A3#1/#2 整行 ＋ 前置 42（持有者为队长），+50% → +5%；"
                                               "IT 246 队长表零先例（C08）⇒ 能力行承载，队长表保持 7 行",
                f"cas:{CAS_LEADER}": f"第 5 行数值 → {NEW_LEADER_LINE}；新增第 6 行 {NEW_LEADER_KEEP_FRAME_LINE}",
                f"cas:{CAS_A3}": f"第 2 行 → {NEW_A3_LINE.strip()}",
                f"dsl:{ENCORE_PROGRAM}": "CreateNormalAttack p13 斩击 10 → 1.5、爆击 1 → 0.1（×10）；"
                                          f"每次 {per_cast['before']} → {per_cast['after']}",
            },
            "encore_ct": {"frames": ct_frames, "cap_per_call": cap, "per_call": per_cast},
            "kept": ["队长 L#0-2、L#5-6；能力3 #0、#3-5（含 629 行与其 CT 300）；能力6 #0-2、#4",
                     "能力2 #1（D204 限 100 次）/ 能力1 #0（限 4 次）有上限不动；能力3 #5 追加连击不算成长",
                     "正常技能两档（每次削韧 20）不动；能力6 面板只写碰撞回槽，承载行不进面板"],
            "generator": "wf_midautumn_kit_rolf.py（BALANCE_B / ENCORE_DETOUGHNESS / LEADER / PLAN[3] / PLAN[6] / "
                         "EXPECT / PANEL_LEADER / PANEL_ABILITY[3] / retune_encore_detoughness 已同步；"
                         "ABILITY_RECORDS 19 → 21）",
            "risks": ["IT 246 的触发语义（每 60 帧重复）无真机计数；若只在每个状态实例触发一次，成长会远低于估计",
                      "A6#5/#6 不带风共鸣前置（与原 A3 行一致）；队长面板该行因此不写「风属性共鸣时」",
                      "c2 雕像组 special × 瞬发 33 官方 0 行（记录项，纯面板外观，零功能风险）"],
            "capabilities": list(CAPABILITIES),
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/rolf.json"
PANEL_REL = BATCH / "rework1/panel/rolf.json"
MIRROR_TAG = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27 平衡第二批：队长「每100次直接攻击」三项成长 100%/100%/10% → 20%/20%/2%；"
               "能力3「速度固定每持续1秒」无上限成长搬到能力6 的前置42 队长承载行（IT 246 队长表零先例），"
               "每步 50% → 5%，文案移进队长面板；能力3 原位换成「持有最大速度固定时 自身攻击力＋100%、直击伤害＋100%」；"
               "629 追击树削韧每次 20 → 2.5。")


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等）。"""
    import wf_midautumn_kit_rolf as K
    design, panel = deepcopy(design), deepcopy(panel)

    plan = design["plan_rework1"]
    plan["ability_records"] = K.ABILITY_RECORDS
    plan["ability_rows_by_slot"] = {str(slot): len(K.PLAN[slot]) for slot in range(1, 7)}
    design["rework1"][MIRROR_TAG] = dict(
        spec="第二批施工口径 A/B（作者 2026-09-27 拍板）＋ growth_design 149986 / critic C08 ＋ down_design 149986",
        changed=[
            f"队长 L#3/L#4 c49/c50 100000 → {K.BALANCE_B['direct_growth']}（每 100 直击，约 20 次/3 分钟 ⇒ 1/5）",
            f"A6#3 693 c51/c52 10000 → {K.BALANCE_B['direct_growth_ic693']}（同触发 1/5）",
            "A3#1/#2 IT 246 读秒行 → D214 持有最大速度固定 自身攻击力/直击伤害 "
            f"+{int(K.BALANCE_B['hold_fixed_speed']) // 1000}%（有上限版本）",
            f"A6#5/#6 新增：原 A3#1/#2 ＋ 前置 42，50000 → {K.BALANCE_B['keep_frame_growth']}"
            "（约 90 次/3 分钟 ⇒ 1/10；IT 246 队长表零先例 ⇒ 能力行承载，C08）",
            f"629 追击树 p13 {K.ENCORE_DETOUGHNESS_DONOR} → {K.ENCORE_DETOUGHNESS}（每次 20 → 2.5，CT 5 秒 ⇒ ≤3）",
        ],
        kept=["队长表保持 7 行", "正常技能两档削韧 20 不动", "能力6 面板只写碰撞回槽"],
        panel={"desc_override_" + K.CODE: K.PANEL_LEADER, "desc_override_" + K.CODE + "_3": K.PANEL_ABILITY[3]},
        encore_detoughness={"donor": dict(K.ENCORE_DETOUGHNESS_DONOR), "new": dict(K.ENCORE_DETOUGHNESS)},
        module="mod-tools/wf_balance_20260927b_rolfmoon.py",
    )

    leader_texts = K.PANEL_LEADER.split("\n")
    lines = panel["leader"]["lines"]
    by_text = {line["text"]: line for line in lines}
    new_lines = []
    for text in leader_texts:
        if text in by_text:
            new_lines.append(by_text[text])
        elif text == NEW_LEADER_LINE:
            old = next(line for line in lines if line["text"] == OLD_LEADER_LINE)
            new_lines.append(dict(old, text=text, status="changed",
                                  note="2026-09-27 平衡第二批：每步 100%/100%/10% → 20%/20%/2%（无上限成长放缓）"))
        elif text == NEW_LEADER_KEEP_FRAME_LINE:
            new_lines.append({"text": text, "status": "new", "dev": True,
                              "note": "2026-09-27 平衡第二批：由能力3 第2条移入，每步 50% → 5%；数据落在能力6 的"
                                      "前置42（持有者为队长）承载行——IT 246 在官方与 live 自制队长表都是 0 行，"
                                      "进队长表会让角色页崩溃（C08）"})
        else:
            raise ValueError(f"leader panel mirror cannot place line {text!r}")
    panel["leader"]["lines"] = new_lines
    if [line["text"] for line in panel["leader"]["lines"]] != leader_texts:
        raise ValueError("leader panel mirror still differs from the generator")

    three = [entry for entry in panel["abilities"] if int(entry["index"]) == 3]
    want = [line.replace(K.MAIN_ICON, "") for line in K.PANEL_ABILITY[3].split("\n")]
    if len(three) != 1 or len(three[0]["lines"]) != len(want):
        raise ValueError("panel mirror ability 3 layout drifted")
    line = three[0]["lines"][A3_LINE]
    if line["text"] != want[A3_LINE]:
        three[0]["lines"][A3_LINE] = {
            "text": want[A3_LINE], "status": "changed", "dev": True,
            "note": "2026-09-27 平衡第二批：原「每持续1秒 自身攻击力/直击伤害＋50%」无上限成长移到队长技"
                    "（能力6 前置42 承载），这里换成持有型有上限版本（D214 持有最大速度固定）"}
    if [entry["text"] for entry in three[0]["lines"]] != want:
        raise ValueError("panel mirror ability 3 still differs from the generator")
    notes = [note for note in panel.get("notes", []) if not note.startswith("2026-09-27 平衡第二批")]
    panel["notes"] = notes + [MIRROR_NOTE]
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保留原文件的缩进、换行风格与末尾有无换行。"""
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
