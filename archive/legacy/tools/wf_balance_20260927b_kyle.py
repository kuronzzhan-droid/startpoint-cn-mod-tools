# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon``：2026-09-27 平衡调整第二批（无上限成长 + Down）。

口径 = ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）；设计稿
``growth/growth_design.json`` / ``growth/down_design.json`` 的 139990 条目只作参考，行号与数值按
live 1.4.1049 重新推导（第一批已删队长「月牙 Stunify」与能力5「雷队 Stunify」，本批不重复）。

**A. 无上限成长（口径 A1–A5）**——3 分钟触发次数：月牙约 35–60 层（队长位约 60；雷队技能约 22–26 次
各 +1 层，雷队每 100 直击 +1 层约 15–30 次）、获得贯穿约 30–60 次（队长冲刺 CD−50% 每次给贯穿，强化档
技能给全队贯穿）⇒ 都 ≥30 次 ⇒ 每步 ×1/10（口径 A2 按实际次数，不按事件名；设计稿按旧 R2 标签给的
月牙 ×1/5 不采用，见 notes）。

1. ``leader_ability:139990``（live 9 行，0 基）原位放缓：
   #0 月牙每层 → 雷队攻击力 12.5% → 1.25%；#3 月牙每层 → 自身直击 25% → 2.5%；
   #6 每获得贯穿 → 雷队攻击力 25% → 2.5%；#7 每获得贯穿 → 雷队眩晕畏缩特攻（面板「追击伤害」）5% → 0.5%。
2. ``ability:1399902``（能力2 Ⓜ）两条无上限逐层成长搬进队长（行 = ``[c0,'0',''] + 能力行[5:]``，
   与队长 #2 / #1 同触发 134、同 kind、同目标、同前置、无 CT ⇒ 合并，强度相加）：
   #2 雷队直击 2.5% + 能力2#0 50%/10 = 7.5%；#1 自身攻击 1.25% + 能力2#1 50%/10 = 6.25%。
   能力栏原位换成有上限的弱化版（设计稿给定值）：c102 (None) → 10（官方 134 限次族 1611231–1611236
   同写法），#0 雷队直击每层 50% → 10%（满 +100%），#1 自身攻击每层 50% → 16%（满 +160%）。
3. 技能程序里的无上限：629 追击树 ``ability_skill_kyle_moon_pierce``（能力3#4/#5，前置 42 仅队长）
   ``BindConditionAccumulationVariable(-17, 1, DCUnique 13999001, 1, 99)`` → 第 5 参 99 → 10，
   段数 = 1 + min(月牙层数, 10)（客户端 ActionEvaluator case 101 ``min(层数/第4参, 第5参)``；
   live 先例索利兹 10、普莉姆拉 20）。无上限部分由队长月牙逐层成长行承担（口径 A5：视为已合并）。
   ⚠ 作业单写的是「雷击 629（ability_skill kyle_moon_thunder）段数 = 1+月牙层数」，按 live 核对段数成长
   实际在 ``_pierce`` 树；``_thunder`` 树没有 vlv（只做下面 B 的削韧）。
4. 不动（口径 A6「其他充能的都暂时不动」）：能力5#0「每 50 直击雷队充能 +5%」（kind 35）及设计稿里它的
   队长搬移/能力替换项；队长 #4/#5 技能槽上限 / 充能。

**B. Down（口径 B1、B3、B6）**——只改 ``CreateNormalAttack`` node[13]（参数卡 p13 削韧），其余逐字保留：

5. 技能两档 ``kyle_moon_1/_2``：首斩 10 → 8、终斩 12 → 8，连斩 1×14 不动 ⇒ 单目标 36 → 30。
6. 天雷 629 ``ability_skill_kyle_moon_thunder``（能力3#6 触发 CT c35=180 帧 = 3 秒 ⇒ CT ≤3 秒每次 ≤1）：
   常态分支单段 20 → 1；强化分支（ConditionalsChangeSkillFlag 1）5 段 × 3.6 → 5 × 0.2 = 1。

面板：``desc_override_kyle_moon``（队长，6 → 7 行：段数上限单列一行）、``desc_override_kyle_moon_2``。
技能描述 / character_text / 服务端文本没有受影响的数字，不改。

生成器 ``wf_midautumn_kit_kyle``（LEADER / PIERCING_GROWTH / PLAN[2] / EXPECT / PANEL_* / CNA_SHAPE /
PIERCE_VAR_CEIL / THUNDER_DETOUGHNESS_*）已同步，测试断言生成器输出 == :func:`revise` 输出。
设计镜像（design/kyle.json、rework1/panel/kyle.json）由 :func:`sync_mirrors` 幂等同步。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

CID = "139990"
CODE = "kyle_moon"
PACKAGES = ["ma-kyle"]
#: 候选 manifest 现值 1.0.2（第一批写入）⇒ 下一号。
PACKAGE_VERSION = {"ma-kyle": "1.0.3"}
#: 候选已声明 damage-type-rules-v1 / dash-parameter-v1 / panel-description-override-v2；改后行不需要新能力。
CAPABILITIES: list[str] = []
#: 候选 164 个 manifest 条目与文件逐一一致（2026-09-27 只读核对 RevisionCandidate 构造通过）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                              # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
UID_CRESCENT = "13999001"                # 固有「月牙」（unique_condition 上限 99 不动）
MAIN_ICON = " <icon id='main'>  "
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
SLOW = 10                                # 口径 A2：3 分钟 ≥30 次 ⇒ 每步 ×1/10

LEADER_KEY = CID
ABILITY2 = f"{CID}2"
ABILITY3 = f"{CID}3"                     # 只读：核对两条 629 的触发 / CT / 前置
CAS_LEADER = f"desc_override_{CODE}"
CAS_ABILITY2 = f"desc_override_{CODE}_2"
CAS_PIERCE = f"ability_skill_{CODE}_pierce"
CAS_THUNDER = f"ability_skill_{CODE}_thunder"
PIERCE_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_PIERCE}${CAS_PIERCE}"
THUNDER_PROGRAM = f"battle/action/skill/action/ability_skill/{CAS_THUNDER}${CAS_THUNDER}"
SKILL_PROGRAMS = {lv: f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in ("1", "2")}

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数；leader / cas 与第一批 revise() 输出逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "14d2a0271dad70106338a285aa2efdd8cab3a94694b4c5156e6352e29f41f6fb",
    ("ability", ABILITY2): "f4f5d75922c0ab6559fc264c32d26a63c02d295467336a7f24aec76df5ef7e39",
    ("ability", ABILITY3): "fd274f08504d07afa19e18b9db541f2687659066e04e98fd3c5c22fd38ac85b0",
    ("cas", CAS_LEADER): "73c8a8e271096b9bafa17e5894f185d112c14f7d05077a4e216dd66ddf4a96f1",
    ("cas", CAS_ABILITY2): "8440ca58ff794220fda8e8ae1e5bcb937d6b506086108444d296158aaa7be1ab",
    ("dsl", PIERCE_PROGRAM): "7af287a4bcb597a608053965ac8b66a4c752a40c90fda15f66504da33e892f25",
    ("dsl", THUNDER_PROGRAM): "f7f098c6828b51f307c2a8cb0757e2b1e29e8057c12d39b88a482cdc2c425601",
    ("dsl", SKILL_PROGRAMS["1"]): "fa7be1876ce8c3396835926550d30407a1e0092b4899d9c69e0e01c8686a1703",
    ("dsl", SKILL_PROGRAMS["2"]): "5efa2b1f29843512d11a612b8d16206df9866ae1c14f4472904650dfc74acc83",
}

# ---------------------------------------------------------------- A. 队长与能力2

_CRESCENT = {3: "1", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)",
             102: UID_CRESCENT, 106: "false"}
_PIERCING = {3: "0", 25: "51", 28: "100000", 29: "100000", 32: "(None)", 33: "0", 37: "(None)",
             44: "0", 46: "5", 47: ELEMENT_TOKEN}
_LEADER_RESONANCE = {0: CODE, 1: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
                     11: "0", 18: "0"}

#: 队长放缓：记录号 → (识别格, 数值列, 旧值, 并入的能力2记录号或 None, 新值, 说明)。
#: 新值 = 旧值/10（＋能力2 该记录旧值/10）；revise() 按输入重算并与这里的常量互锁。
LEADER_EDITS: dict[int, tuple[dict[int, str], tuple[int, int], str, int | None, str, str]] = {
    0: ({**_CRESCENT, 107: "0", 108: "5", 109: ELEMENT_TOKEN}, (111, 112), "12500", None, "1250",
        "月牙每层 → 雷队攻击力 12.5% → 1.25%"),
    1: ({**_CRESCENT, 107: "0", 108: "0", 109: ""}, (111, 112), "12500", 1, "6250",
        "月牙每层 → 自身攻击力 1.25% ＋ 能力2#1 搬入 5% = 6.25%"),
    2: ({**_CRESCENT, 107: "1", 108: "5", 109: ELEMENT_TOKEN}, (111, 112), "25000", 0, "7500",
        "月牙每层 → 雷队直击 2.5% ＋ 能力2#0 搬入 5% = 7.5%"),
    3: ({**_CRESCENT, 107: "1", 108: "0", 109: ""}, (111, 112), "25000", None, "2500",
        "月牙每层 → 自身直击 25% → 2.5%"),
    6: ({**_PIERCING, 45: "32"}, (49, 50), "25000", None, "2500",
        "每获得贯穿 → 雷队攻击力 25% → 2.5%"),
    7: ({**_PIERCING, 45: "53"}, (49, 50), "5000", None, "500",
        "每获得贯穿 → 雷队眩晕畏缩特攻（面板「追击伤害」）5% → 0.5%"),
}
#: 不动的队长行：#4 技能槽上限 20%（245）、#5 充能 20%（35）—— 口径 A6；#8 特殊强化弹射 722。
LEADER_KEPT = {4: "245", 5: "35", 8: "722"}
LEADER_ROWS = 9

_ABILITY2_COMMON = {0: f"{CODE}_2", 1: "false", 2: "attack_common", 3: "0", 5: "1", 6: "2",
                    9: "600000", 10: "600000", 11: ELEMENT_TOKEN, 13: "0", 20: "0", 85: "(None)",
                    97: "134", 98: "0", 100: "100000", 101: "100000", 104: UID_CRESCENT,
                    108: "false"}
#: 能力2 原位换成有上限的弱化版：记录号 → (识别格, 旧上限, 新上限, 旧强度, 新强度, 说明)。
ABILITY2_EDITS: dict[int, tuple[dict[int, str], str, str, str, str, str]] = {
    0: ({**_ABILITY2_COMMON, 109: "1", 110: "5", 111: ELEMENT_TOKEN}, "(None)", "10", "50000", "10000",
        "月牙每层 → 雷队直击 50% → 10%（最多 10 层，满 +100%）"),
    1: ({**_ABILITY2_COMMON, 109: "0", 110: "0", 111: ""}, "(None)", "10", "50000", "16000",
        "月牙每层 → 自身攻击力 50% → 16%（最多 10 层，满 +160%）"),
}
LIMIT_COL, STRENGTH_COLS = 102, (113, 114)

# ---------------------------------------------------------------- 面板

OLD_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "雷属性共鸣时：强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋25%、直击伤害＋50%、直击判定次数＋1；"
    "除自身外雷属性角色攻击力＋12.5%、直击伤害＋25%",
    "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋25%、追击伤害＋5%",
    "雷属性共鸣时：雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
#: 自身 = 全队(雷)行 + 自身行：攻击 1.25 + 6.25 = 7.5%、直击 7.5 + 2.5 = 10%；除自身外 = 全队(雷)行。
NEW_LEADER_TEXT = "\n".join((
    "赋予自身特殊强化弹射",
    "雷属性共鸣时：强化自身冲刺",
    "自身冲刺间隔无法进一步缩短",
    "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋7.5%、直击伤害＋10%；"
    "除自身外雷属性角色攻击力＋1.25%、直击伤害＋7.5%",
    "雷属性共鸣时：自身“月牙”每上升1层，自身直击判定次数＋1（最多10层）",
    "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋2.5%、追击伤害＋0.5%",
    "雷属性共鸣时：雷属性角色技能槽最大值＋20%、技能充能速度＋20%",
))
OLD_ABILITY2_TEXT = (MAIN_ICON + "雷属性共鸣时：自身“月牙”每提升1层，自身直击伤害＋50%、攻击力＋50%，"
                     "除自身外雷属性角色直击伤害＋50%")
NEW_ABILITY2_TEXT = (MAIN_ICON + "雷属性共鸣时：自身“月牙”每提升1层，自身攻击力＋16%、雷属性角色直击伤害＋10%"
                     "（最多10层）")

# ---------------------------------------------------------------- DSL

#: 第 5 参 = 变量上限（客户端 ActionEvaluator case 101：``bind(vid, min(层数 / 第4参, 第5参))``）。
PIERCE_CEIL_SLOT, PIERCE_CEIL_BEFORE, PIERCE_CEIL_AFTER = 5, 99, 10
PIERCE_BIND_BEFORE = ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", int(UID_CRESCENT)], 1,
                      PIERCE_CEIL_BEFORE]
PIERCE_TIMES = [{"min": 1, "max": 1, "vlv": [{"vid": 1, "min": 0, "max": 1}]}]

DETOUGHNESS_SLOT = 13                    # CreateNormalAttack node[13] = 参数卡 p13 削韧（node[14] = Fever 点）
#: 天雷：分支 → (旧, 新, 每目标段数)；CT 3 秒 ⇒ 每次 ≤1（口径 B3）。
THUNDER_EDITS = {"boost": (3.6, 0.2, 5), "normal": (20, 1, 1)}
THUNDER_COOLTIME_FRAMES = "180"
#: 技能：三段 CreateNormalAttack（树序）→ (旧, 新, 每目标段数)；36 → 30（口径 B1）。
SKILL_EDITS = ((10, 8, 1), (1, 1, 14), (12, 8, 1))
SKILL_CAP, THUNDER_CAP = 30, 1


class KyleBalanceError(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise KyleBalanceError(f"unreviewed live baseline for {kind}:{key} "
                               f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise KyleBalanceError(message)


def _cells_match(row: list[str], cells: dict[int, str], label: str) -> None:
    got = {col: row[col] for col in cells}
    _require(got == cells, f"{label}: unexpected preimage {got} != {cells}")


def _slow(value: str) -> int:
    number = int(value)
    _require(number % SLOW == 0, f"{value} is not divisible by {SLOW}")
    return number // SLOW


def moved_row(ability_row: list[str]) -> list[str]:
    """口径 A3：能力行搬进队长的形状 = ``[能力行 c0, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2）。"""
    return [CODE, "0", ""] + list(ability_row[5:])


def leader_rows(leader: list[list[str]], ability2: list[list[str]]) -> list[list[str]]:
    """队长 #0/#1/#2/#3/#6/#7 原位放缓（#1/#2 并入能力2 两条）；#4/#5/#8 逐字不动。"""
    out = deepcopy(leader)
    _require(len(out) == LEADER_ROWS and all(len(r) == LEADER_NCOLS for r in out),
             f"leader_ability:{LEADER_KEY} shape drift ({len(out)} rows)")
    _require(len(ability2) == 2 and all(len(r) == ABILITY_NCOLS for r in ability2),
             f"ability:{ABILITY2} shape drift")
    for index, kind in LEADER_KEPT.items():
        _require(out[index][45] == kind or out[index][107] == kind,
                 f"leader#{index}: kept row is not kind {kind}")
    for index, (cells, cols, old, merge, new, _why) in LEADER_EDITS.items():
        row = out[index]
        _cells_match(row, {**_LEADER_RESONANCE, **cells}, f"leader#{index}")
        _require([row[c] for c in cols] == [old, old], f"leader#{index}: strength {row[cols[0]]} != {old}")
        value = _slow(old)
        if merge is not None:
            source = ability2[merge]
            moved = moved_row(source)
            # 合并条件：同触发/同 kind/同目标/同前置（整行除强度两列逐格相同）且无 CT（持续型行没有 CT 列）
            _require(moved[:111] + moved[113:] == row[:111] + row[113:],
                     f"leader#{index} and ability {ABILITY2}#{merge} are not mergeable")
            value += _slow(source[STRENGTH_COLS[0]])
            _require(source[STRENGTH_COLS[0]] == source[STRENGTH_COLS[1]],
                     f"ability {ABILITY2}#{merge}: low/max strengths differ")
        _require(str(value) == new, f"leader#{index}: computed {value} != reviewed {new}")
        for col in cols:
            row[col] = new
    return out


def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力2 两条逐层成长：限 10 层 + 弱化版强度；其余格逐字不动。"""
    out = deepcopy(rows)
    _require(len(out) == len(ABILITY2_EDITS) and all(len(r) == ABILITY_NCOLS for r in out),
             f"ability:{ABILITY2} shape drift")
    for index, (cells, old_limit, new_limit, old, new, _why) in ABILITY2_EDITS.items():
        row = out[index]
        _cells_match(row, cells, f"ability {ABILITY2}#{index}")
        _require(row[LIMIT_COL] == old_limit, f"ability {ABILITY2}#{index}: limit {row[LIMIT_COL]!r}")
        _require([row[c] for c in STRENGTH_COLS] == [old, old],
                 f"ability {ABILITY2}#{index}: strength {row[STRENGTH_COLS[0]]}")
        row[LIMIT_COL] = new_limit
        for col in STRENGTH_COLS:
            row[col] = new
    return out


def ability3_checks(rows: list[list[str]]) -> dict[str, Any]:
    """只读核对：天雷 629 触发 CT 3 秒（⇒ 每次削韧 ≤1），两条段数 629 都挂前置 42（仅队长）。"""
    _require(all(len(r) == ABILITY_NCOLS for r in rows), f"ability:{ABILITY3} shape drift")
    thunder = [r for r in rows if r[47] == "629" and r[70] == CAS_THUNDER]
    pierce = [r for r in rows if r[47] == "629" and r[70] == CAS_PIERCE]
    _require(len(thunder) == 1 and thunder[0][71] == THUNDER_PROGRAM, "thunder 629 row not found")
    _require(thunder[0][35] == THUNDER_COOLTIME_FRAMES,
             f"thunder 629 cooltime {thunder[0][35]!r} != {THUNDER_COOLTIME_FRAMES}")
    _require(len(pierce) == 2 and all(r[71] == PIERCE_PROGRAM and r[6] == "42" for r in pierce),
             "pierce 629 rows must stay leader-only (precondition 42)")
    return {"thunder_cooltime_frames": int(thunder[0][35]),
            "thunder_trigger": {"c27": thunder[0][27], "c30": thunder[0][30]},
            "pierce_rows_leader_only": True}


def _single_text(rows: list[list[str]], key: str) -> str:
    _require(len(rows) == 1 and len(rows[0]) == 1, f"{key}: expected one single-column row")
    return rows[0][0]


def leader_text(rows: list[list[str]]) -> list[list[str]]:
    _require(_single_text(rows, CAS_LEADER) == OLD_LEADER_TEXT, f"{CAS_LEADER}: unexpected panel text")
    return [[NEW_LEADER_TEXT]]


def ability2_text(rows: list[list[str]]) -> list[list[str]]:
    _require(_single_text(rows, CAS_ABILITY2) == OLD_ABILITY2_TEXT, f"{CAS_ABILITY2}: unexpected panel text")
    return [[NEW_ABILITY2_TEXT]]


# ---------------------------------------------------------------- DSL 工具

def _walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, dict):
        for child in node.values():
            yield from _walk(child)


def commands(node, name: str | None = None) -> list[list]:
    """树序列出 ``["Command", body]`` 的 body（可按构造名过滤）。"""
    return [n[1] for n in _walk(node)
            if isinstance(n, list) and len(n) == 2 and n[0] == "Command" and isinstance(n[1], list)
            and n[1] and isinstance(n[1][0], str) and (name is None or n[1][0] == name)]


def _slv(value) -> list[dict]:
    return [{"min": value, "max": value}]


def _hits_per_target(area: list) -> float:
    """单目标命中次数上界：``CalculatedUsingMaxNumOfHits`` N，与 p15 ``Some`` 硬帽取小（参数卡口径）。"""
    count = area[14]
    _require(isinstance(count, list) and count[0] == "CalculatedUsingMaxNumOfHits",
             f"unsupported hit-count constructor {count!r}")
    hits = float(count[1])
    cap = area[15]
    if isinstance(cap, list) and cap and cap[0] == "Some":
        hits = min(hits, max(float(v["max"]) for v in cap[1]))
    return hits


def detoughness_per_cast(node) -> float:
    """单目标每次施放总削韧：判定区命中数 × 区内 CNA p13；技能旗两支互斥取大；其余并列相加。"""
    if isinstance(node, list) and len(node) == 2 and node[0] == "Command" and isinstance(node[1], list):
        body = node[1]
        if body[0] == "CreateNormalAttack":
            return max(float(v["max"]) for v in body[DETOUGHNESS_SLOT])
        if body[0] == "CreateHitArea":
            return _hits_per_target(body) * sum(detoughness_per_cast(c) for c in body[1:])
        if body[0] == "ConditionalsChangeSkillFlag":
            return max(detoughness_per_cast(body[2]), detoughness_per_cast(body[3]))
        return sum(detoughness_per_cast(c) for c in body[1:])
    if isinstance(node, list):
        return sum(detoughness_per_cast(c) for c in node)
    return 0.0


def pierce_tree(tree) -> list:
    """段数成长封顶：``BindConditionAccumulationVariable`` 第 5 参 99 → 10；其余逐字不动。"""
    out = deepcopy(tree)
    _require(isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl", "pierce root drift")
    block = out[11]
    _require(block[0] == "Block" and len(block[1]) == 2, "pierce body must be [Bind, CreateCondition]")
    bind, condition = block[1][0][1], block[1][1][1]
    _require(bind == PIERCE_BIND_BEFORE, f"pierce bind preimage drift: {bind}")
    _require(condition[0] == "CreateCondition" and condition[1] == -17,
             "pierce CreateCondition drift")
    ac = condition[2][0]
    _require(ac[0] == "ACAdditionalDirectAttack" and ac[2] == PIERCE_TIMES,
             f"pierce ACAdditionalDirectAttack times drift: {ac[2]}")
    bind[PIERCE_CEIL_SLOT] = PIERCE_CEIL_AFTER
    return out


def thunder_tree(tree) -> list:
    """天雷两支（技能旗 1 = 强化、否则常态）各自只改 CNA p13；判定区段数锁定。"""
    out = deepcopy(tree)
    flags = commands(out, "ConditionalsChangeSkillFlag")
    _require(len(flags) == 1 and flags[0][1] == 1, "thunder tree must carry one skill-flag branch")
    branches = {"boost": flags[0][2], "normal": flags[0][3]}
    for name, block in branches.items():
        old, new, hits = THUNDER_EDITS[name]
        areas, attacks = commands(block, "CreateHitArea"), commands(block, "CreateNormalAttack")
        _require(len(areas) == 1 and len(attacks) == 1, f"thunder {name}: expected 1 area + 1 attack")
        _require(_hits_per_target(areas[0]) == hits, f"thunder {name}: hits drift")
        _require(attacks[0][DETOUGHNESS_SLOT] == _slv(old),
                 f"thunder {name}: detoughness preimage {attacks[0][DETOUGHNESS_SLOT]}")
        attacks[0][DETOUGHNESS_SLOT] = _slv(new)
    return out


def skill_tree(tree, level: str) -> list:
    """技能三段斩：首斩 / 终斩 p13 → 8，连斩不动；判定区段数锁定。"""
    out = deepcopy(tree)
    areas, attacks = commands(out, "CreateHitArea"), commands(out, "CreateNormalAttack")
    _require(len(areas) == len(attacks) == len(SKILL_EDITS), f"skill {level}: attack layout drift")
    for index, ((old, new, hits), area, attack) in enumerate(zip(SKILL_EDITS, areas, attacks)):
        _require(_hits_per_target(area) == hits, f"skill {level} cna{index}: hits drift")
        _require(attack in commands(area), f"skill {level} cna{index} is not inside its hit area")
        _require(attack[DETOUGHNESS_SLOT] == _slv(old),
                 f"skill {level} cna{index}: detoughness preimage {attack[DETOUGHNESS_SLOT]}")
        attack[DETOUGHNESS_SLOT] = _slv(new)
    return out


def dsl_problems(tree) -> list[str]:
    """AMF3 往返 + 四道 DSL 门禁（元素 / 主体绑定 / lookup 作用域 / 判定区目标）。"""
    import wf_client_legality as L
    import wf_dsl
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    import wf_client_legality as L
    cas_keys = {CAS_LEADER, CAS_ABILITY2, CAS_PIERCE, CAS_THUNDER}
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, cas_keys, kind=kind))


# ---------------------------------------------------------------- revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {key: _checked(read, *key) for key in BEFORE}
    leader_in = inputs["leader", LEADER_KEY]
    ability2_in = inputs["ability", ABILITY2]
    checks = ability3_checks(inputs["ability", ABILITY3])

    leader = leader_rows(leader_in, ability2_in)
    ability2 = ability2_rows(ability2_in)
    trees = {PIERCE_PROGRAM: pierce_tree(inputs["dsl", PIERCE_PROGRAM]),
             THUNDER_PROGRAM: thunder_tree(inputs["dsl", THUNDER_PROGRAM])}
    for level, program in SKILL_PROGRAMS.items():
        trees[program] = skill_tree(inputs["dsl", program], level)

    detoughness = {program: [detoughness_per_cast(inputs["dsl", program]), detoughness_per_cast(tree)]
                   for program, tree in trees.items() if program != PIERCE_PROGRAM}
    for program, (_before, after) in detoughness.items():
        cap = THUNDER_CAP if program == THUNDER_PROGRAM else SKILL_CAP
        _require(after <= cap + 1e-9, f"{program}: detoughness {after} > {cap}")

    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"ability {ABILITY2}#{i}: {p}" for i, row in enumerate(ability2)
                 for p in row_problems("ability", row)]
    problems += [f"dsl {program}: {p}" for program, tree in trees.items() for p in dsl_problems(tree)]
    _require(not problems, "; ".join(problems))

    return {
        "ability": {ABILITY2: ability2},
        "leader": {LEADER_KEY: leader},
        "cas": {CAS_LEADER: leader_text(inputs["cas", CAS_LEADER]),
                CAS_ABILITY2: ability2_text(inputs["cas", CAS_ABILITY2])},
        "text": {}, "table": {}, "action": {}, "dsl": trees, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_kyle.py",
            "batch": "2026-09-27 第二批（口径 A 无上限成长 + B Down）",
            "generator": "wf_midautumn_kit_kyle.py（LEADER/PIERCING_GROWTH/PLAN[2]/EXPECT/PANEL_*/"
                         "CNA_SHAPE/PIERCE_VAR_CEIL/THUNDER_DETOUGHNESS_* 已同步）",
            "frequency": {
                "crescent_layers_per_3min": "35–60（队长位约 60）：雷队技能约 22–26 次各 +1 层；"
                                            "雷队每 100 直击 +1 层约 15–30 次（能力3 直击 3 段化）",
                "piercing_gains_per_3min": "30–60：队长冲刺 CD−50% 每次付与贯穿 5.5 秒，强化档技能付与全队贯穿",
                "factor": "两者都 ≥30 次 ⇒ ×1/10（口径 A2 按实际次数）；设计稿按旧 R2 事件标签给月牙 ×1/5"
                          "（队长 2500/12500/15000/5000），与口径冲突，不采用",
            },
            "growth_3min_leader_60_layers_45_piercing": {
                "self_attack": "25%×60 + 能力2 50%×60 = 4500% → 7.5%×60 + 能力2 16%×10 = 610%",
                "thunder_team_direct": "25%×60 + 能力2 50%×60 = 4500% → 7.5%×60 + 能力2 10%×10 = 550%",
                "thunder_team_attack": "12.5%×60 = 750% → 1.25%×60 = 75%",
                "self_direct_extra": "25%×60 = 1500% → 2.5%×60 = 150%",
                "piercing": "雷队攻 25%×45 = 1125% → 112.5%；追击 5%×45 = 225% → 22.5%",
                "direct_hit_segments": "1 + 60（上限 99）→ 1 + 10",
            },
            "leader": {f"leader_ability:{LEADER_KEY}#{i}": why for i, (*_x, why) in LEADER_EDITS.items()},
            "ability": {f"ability:{ABILITY2}#{i}": why for i, (*_x, why) in ABILITY2_EDITS.items()},
            "merged": {"leader#2": f"ability:{ABILITY2}#0（同触发134/kind1/目标5雷/同前置，无CT）",
                       "leader#1": f"ability:{ABILITY2}#1（同触发134/kind0/目标0/同前置，无CT）"},
            "dsl_growth_cap": {
                PIERCE_PROGRAM: "BindConditionAccumulationVariable 第5参 99→10：段数 = 1 + min(月牙层, 10)",
                "why": "口径 A5；作业单写成 _thunder 树，按 live 核对段数成长只在 _pierce 树",
                "unlimited_part": "队长月牙逐层成长行 #0–#3 已存在 ⇒ 视为已合并，不新增行",
            },
            "detoughness_per_cast": detoughness,
            "ability3_checks": checks,
            "kept": {
                f"ability:{CID}5#0": "每 50 直击雷队充能 +5%（kind 35）——口径 A6 充能暂不动",
                f"leader_ability:{LEADER_KEY}#4/#5": "雷共鸣 技能槽上限/充能 +20%——口径 A6",
                f"ability:{ABILITY3}#3": "DirectAttack3 300%（直击判定 +N 是特色）——口径 B5",
                "power_flip": "PF 4.5/8/15 与官方剑士相同——设计稿 keep",
            },
            "panel": {CAS_LEADER: "月牙/贯穿成长数值更新；段数上限单列一行（最多10层）",
                      CAS_ABILITY2: NEW_ABILITY2_TEXT.replace(MAIN_ICON, "")},
            "runtime_verified": False,
        },
    }


# ---------------------------------------------------------------- 设计镜像同步

BATCH = Path("work/character_packs/midautumn-20260920")
DESIGN_REL = BATCH / "design/kyle.json"
PANEL_REL = BATCH / "rework1/panel/kyle.json"
MIRROR_KEY = "balance_20260927b"
MIRROR_NOTE = ("2026-09-27 第二批平衡（口径 A/B）：月牙逐层与贯穿成长 ×1/10，能力2 两条逐层成长 ×1/10 并入队长、"
               "能力栏换成限 10 层弱化版（自身攻击＋16%、雷队直击＋10%）；629 段数成长 DSL 封顶 10 层"
               "（BindConditionAccumulationVariable 第5参 99→10），面板单列「直击判定次数＋1（最多10层）」；"
               "技能削韧 36→30（首斩/终斩 10/12→8），天雷 629 削韧 20→1、5×3.6→5×0.2。"
               "每50直击雷队充能（kind35）按口径 A6 不动。")


def mirror_updates(design: dict, panel: dict) -> tuple[dict, dict]:
    """按当前生成器常量重算两份设计镜像（纯函数、幂等；与第一批 mirror_updates 互不干扰）。"""
    import wf_midautumn_kit_kyle as K
    design, panel = deepcopy(design), deepcopy(panel)
    mirror = design["plan"]["rework1"]
    mirror[MIRROR_KEY] = dict(
        module="mod-tools/wf_balance_20260927b_kyle.py",
        leader={f"#{i}": why for i, (*_x, why) in LEADER_EDITS.items()},
        ability={f"{ABILITY2}#{i}": why for i, (*_x, why) in ABILITY2_EDITS.items()},
        crescent_ability_limit=int(K.CRESCENT_ABILITY_LIMIT),
        # 记第二批自己的封顶值（第三轮 wf_balance_20260927c_kyle 把生成器恢复到 99，不能回写本块历史）
        direct_hit_count=f"1 + min(月牙层数, {PIERCE_CEIL_AFTER})（DSL 封顶，原 99）",
        skill_detoughness={"before": [10, 1, 12], "after": [K.CNA_SHAPE[i]["p12"] for i in (0, 1, 2)],
                           "hits": [1, 14, 1], "total": [36, 30]},
        thunder_detoughness={"normal": [20, K.THUNDER_DETOUGHNESS_NORMAL],
                             "boost": [3.6, K.THUNDER_DETOUGHNESS_BOOST], "boost_hits": 5},
        kept=["ability:1399905#0 每50直击雷队充能 5%（kind35，口径 A6）",
              "leader_ability:139990 #4/#5 技能槽上限/充能 20%（口径 A6）"],
    )
    problems = K._design_problems(design)
    if problems:
        raise KyleBalanceError(f"design mirror still drifts: {problems}")

    panel["leader"]["lines"] = [dict(text=line, status="changed") for line in K.PANEL_LEADER.split("\n")]
    for entry in panel["abilities"]:
        slot = int(entry["index"])
        entry["lines"] = [dict(text=line.replace(K.MAIN_ICON, ""), status="changed")
                          for line in K.PANEL_ABILITY[slot].split("\n")]
    panel[MIRROR_KEY] = dict(note=MIRROR_NOTE, module="mod-tools/wf_balance_20260927b_kyle.py",
                             supersedes="notes 里「leader第3条…可以超过3次…面板文字（不封顶…）」一条："
                                        "段数成长现封顶 10 层，面板已单列上限")
    return design, panel


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """indent=2、保留原文件换行风格（本机两份镜像是 CRLF）。"""
    newline = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (DESIGN_REL, PANEL_REL)
    before = [_load(root / rel) for rel in rels]
    after = mirror_updates(*before)
    changed = [str(rel) for rel, old, new in zip(rels, before, after) if old != new]
    if write:
        for rel, old, new in zip(rels, before, after):
            if old != new:
                _save(root / rel, new)
    return changed


if __name__ == "__main__":
    import sys
    here = Path(__file__).resolve().parent
    pass  # Imports resolve from this checkout/package, not external source copies.
    changed = sync_mirrors(here.parent, write="--write" in sys.argv[1:])
    print(json.dumps({"changed": changed, "write": "--write" in sys.argv[1:]}, ensure_ascii=False))
