# -*- coding: utf-8 -*-
"特克托 139993 ``super_robot_tailcoat``：2026-09-27 作者平衡**第二批**（无上限成长 + Down）。\n\n口径 = ``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）；设计稿\n``growth/growth_design.json`` 139993、``growth/down_design.json`` 139993 按 live 1.4.1049 重读重推。\n\n一、无上限成长（口径 A）——频率按 3 分钟实际触发次数（A2，不按事件名称）：\n  队长行只在特克托当队长时生效，此时他在主位，Ⓜ能力3 生效。「引擎启动」13999301 每一层都是这些逐层行的一步：\n  (a) 自身技能约 11–14 发（580/530 能量；雷队充能 +25%〔队长#7〕、能力6 +10%、引擎每层自身充能 +5%〔队长#3，\n      A6 保留〕约 13 层后钳到 +100%），每发 DSL +1；两发间隔 <15 秒（「重炮展开」13999302 live 900 帧）时\n      能力3#2（trigger 23 c28=5，含自身）再 +1 ⇒ 22–28 层；\n  (b) 持重炮期间 2 名雷队友的技能（队长#5 持重炮时队友充能 +50%）约 20–28 次，每次 +1 ⇒ 20–28 层；\n  (c) HP≤50%（这套背水 kit 的设计玩法）时队长#9 每发自身技能再 +2 ⇒ 再 +22–28 层。\n  合计约 40–55 层，半血 60–80 层；即使取设计稿的保守估计（8–10 发、不计自身那次 +1）也有 20–25 层、\n  半血 35–45 层。按触发次数计（自身施技 + 持重炮时队友施技）也有约 30–40 次 ⇒ **≥30 ⇒ 每层 ×1/10**。\n  设计稿按「低频」标签取 1/5，口径 A2 不按事件名称，与同批 kyle / celtie / hibiki / magnus（逐层行按层数 ≥30 取\n  1/10）一致，改取 1/10（复核 major）。半血持重炮的时间跳（队长 #8 trigger 77，每 120 帧）≈ 20–60 跳\n  （按 40）⇒ ≥30 取 1/10。\n\n  1. 队长原位放缓（A3「已在队长技的成长 → 原位放缓」，×1/10）：\n     #0 引擎每层 雷队攻击力 c111/c112 100000 → 10000；#1 雷队技能伤害 200000 → 20000；\n     #2 自身独立乘区技能伤害（411）5000 → 500（0.5%，与 magnus 411 同精度，A7）；\n     #8 半血持重炮每 120 帧 自身技能伤害 c49/c50 100000 → 10000。\n     #3（during 3 充能）/#4（during 124 技能槽上限）/#5–#7（充能、技能槽上限）按 A6 原样保留。\n  2. 能力2（``1399932``，非Ⓜ、无前置）两条引擎每层行原位换成有上限的弱化版：c102 (None) → 10，\n     c113/c114 攻 50000 → 16000、技伤 50000 → 15000（满 10 层 160% / 150%）。\n  3. 能力2 的无上限部分搬进队长（A3 公式：行 = [c0,'0',''] + 能力行[5:]，能力 c≥5 → 队长 c−2），\n     每层 50% → 5%（1/10）；与队长 #0/#1（全队(雷)＋雷共鸣）目标与前置都不同 ⇒ 不合并，追加为 #10/#11。\n     队长 during-134 kind 0/2 target 0 有官方先例（设计稿：官方 2 行 / 1 行），合法性门禁为空。\n  4. 技能 DSL（A5）：两档各 11 条 ``BindConditionAccumulationVariable(-17, 1, DCUnique 13999301, 1, 99)``\n     第 5 参（上限）99 → 10 ⇒ 倍率的层数贡献封顶 10 层。客户端 ``ActionEvaluator`` case 101：\n     ``bindFloatVariable(vid, Math.min(count / divisor, cap))``；官方同构先例 ``blackflower_wiz_smr22``\n     ``Bind(-17, 2, [DCUnique, 11], 1, 10)``。只改已有命令的已有参数，不新增命令。无上限部分由队长\n     #0–#2 的同一层数逐层行承担（A5「队长里已有同一层数的逐层成长行 → 视为已合并」）。\n  5. 技能说明写出上限：「威力随其层数提升」→「威力随其层数提升（最多10层）」（action_skill 两档 c1、\n     character_text c5/c7、服务端 cdndata/character_text.json [5]/[7]）。\n\n二、Down（口径 B1，≤30）：两档各 9 组光束判定区（4 段 寿命 60 + 5 个延长槽 寿命 70，最小命中间隔 10、\n    上限 Some(6)）的 ``CreateNormalAttack`` p13 {1,1} → {0.3,0.3}；导弹 p13=2、终幕 p13=4 不动。\n    单目标满打 基础 36 → 19.2，带「重炮展开」66 → 28.2（按 live 树重算，见 :func:`down_census`）。\n\n生成器 ``wf_seasonal7_kit_tekuto``：ENGINE_CAP 99→10、BEAM_BREAK 0.3、_DESC_BALANCE_B、第六轮\n``apply_balance_b``（叠在 wf_tekuto_low_hp 之后）已同步，测试断言生成器输出 == :func:`revise` 输出。\n\n本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。\n"
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_dsl

CID = "139993"
CODE = "super_robot_tailcoat"
PACKAGES = ["s7-tekuto"]
#: 候选 manifest 现值 1.0.8（第一批写入；${WF_ROOT}/pkgarchive/s7-tekuto-* 六份全是 1.0.0）⇒ 下一号。
PACKAGE_VERSION = {"s7-tekuto": "1.0.9"}
CAPABILITIES: list[str] = []
#: 候选 s7-tekuto 的 manifest 条目与文件逐一一致（2026-09-27 RevisionCandidate 只读打开无漂移），
#: 本模块读取的 7 项与 live 逐项相同。
REVIEWED_DRIFT: dict = {}

ELEMENT = 2                          # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
LEADER_KEY = CID
ABILITY2_KEY = f"{CID}2"
UID_ENGINE = "13999301"
UID_CANNON = "13999302"
PROGRAMS = {level: f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}" for level in ("1", "2")}
LEADER_NCOLS, ABILITY_NCOLS = 124, 126

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 s7-tekuto 1.0.8 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", LEADER_KEY): "ef309bed34497e4b27a2b5623abc03b38cc450f1b16b7884193f06d7f7e84ee2",
    ("ability", ABILITY2_KEY): "a51aa245d6da5ab63b61dbe66ea06dc02319db63d66bccf187924a043307db95",
    ("dsl", PROGRAMS["1"]): "c02d83fcb2e363b3c5441f17055cf94762f082b21c1838489a53226e4872d753",
    ("dsl", PROGRAMS["2"]): "7f2219bd5d2796e41fe420ca9b73935e72f63aff16c9fedd1241de405e33aca1",
    ("action", CODE): "11cd9ee99e0772f1dae8997606bca4dced5edc2db47c4f1863ede46b6b998101",
    ("text", CID): "12f6938dfa4ebfa1ff174fe43a7fd89aea532115d243cb3a29474b46355e3f56",
    ("server_text", CID): "12f6938dfa4ebfa1ff174fe43a7fd89aea532115d243cb3a29474b46355e3f56",
}

# ------------------------------------------------------------------ 队长

#: 队长 #0–#4 共用的 during-134 块（雷共鸣前置 + 「引擎启动」层数门，无上限）。
_ENGINE_DURING = {
    0: CODE, 1: "0", 3: "1", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN, 11: "0", 18: "0",
    83: "(None)", 95: "134", 96: "0", 98: "100000", 99: "100000", 100: "(None)", 102: UID_ENGINE,
    106: "false",
}
#: 半血持重炮的时间跳（low_hp 那条）：雷共鸣 + 188 持重炮 + 9 HP≤50% + trigger 77 每 12000000/100000=120 帧。
_TIMER = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: ELEMENT_TOKEN,
    11: "188", 12: "0", 14: "100000", 15: "100000", 17: UID_CANNON, 18: "9", 19: "0",
    21: "50000", 22: "50000", 25: "77", 28: "12000000", 29: "12000000", 32: "(None)", 33: "0",
    37: "(None)", 44: "0", 45: "34", 46: "0",
}
#: 改动的队长行：行号 → (改前逐格指纹（全部非空列）, 强度列, 旧, 新, 说明)。
LEADER_EDITS: dict[int, tuple[dict[int, str], tuple[int, int], str, str, str]] = {
    0: ({**_ENGINE_DURING, 107: "0", 108: "5", 109: ELEMENT_TOKEN, 111: "100000", 112: "100000"},
        (111, 112), "100000", "10000", "引擎每层 雷队攻击力 100% → 10%（1/10）"),
    1: ({**_ENGINE_DURING, 107: "2", 108: "5", 109: ELEMENT_TOKEN, 111: "200000", 112: "200000"},
        (111, 112), "200000", "20000", "引擎每层 雷队技能伤害 200% → 20%（1/10）"),
    2: ({**_ENGINE_DURING, 107: "411", 108: "0", 111: "5000", 112: "5000"},
        (111, 112), "5000", "500", "引擎每层 自身独立乘区技能伤害 5% → 0.5%（1/10）"),
    8: ({**_TIMER, 49: "100000", 50: "100000"},
        (49, 50), "100000", "10000", "雷共鸣＋持重炮＋HP≤50%：每 120 帧 自身技能伤害 100% → 10%（1/10）"),
}
#: 原样保留的队长行（口径 A6：充能 kind 3 / 技能槽上限 124 的成长行不动）：行号 → 说明。
LEADER_KEPT = {
    3: "引擎每层 自身技能槽充能 5%（during 3，A6 不动）",
    4: "引擎每层 自身技能槽上限 5%（during 124，A6 不动）",
    5: "持重炮 → 除自身雷队 充能 50%（194 限 1，持有型）",
    6: "持重炮 → 除自身雷队 技能槽上限 50%（194 限 1，持有型）",
    7: "雷队 技能槽充能 25%（表二暂缓）",
    9: "HP≤50% 自身技能 → 引擎 +2（只提供层数）",
}
LEADER_ROWS_BEFORE = 10
#: 口径 A2：引擎层数 3 分钟 ≥30（见模块说明）⇒ 逐层行每步 ×1/10。
ENGINE_LAYER_SLOWDOWN = 10
MOVED_LEADER_STRENGTH = "5000"       # 能力2 每层 50% → 队长 5%（1/10）

# ------------------------------------------------------------------ 能力2

#: 能力2 两条 during-134 行（第五轮 T3：自身 攻 / 技伤 每层 +50%，无上限）。
_AB2 = {
    0: f"{CODE}_2", 1: "true", 2: "attack_common", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
    85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 102: "(None)", 104: UID_ENGINE,
    108: "false", 110: "0", 113: "50000", 114: "50000",
}
ABILITY2_BEFORE = ({**_AB2, 109: "0"}, {**_AB2, 109: "2"})
ABILITY2_CAP = ("(None)", "10")                    # c102 上限：无 → 10 层
ABILITY2_STRENGTH = {"0": ("50000", "16000"),      # 攻击力 50% → 16%（满 10 层 160%）
                     "2": ("50000", "15000")}      # 技能伤害 50% → 15%（满 10 层 150%）

# ------------------------------------------------------------------ 技能 DSL

BIND_BEFORE = ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", int(UID_ENGINE)], 1, 99]
BIND_AFTER = ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", int(UID_ENGINE)], 1, 10]
BINDS_PER_TREE = 11
BEAM_BREAK_BEFORE = [{"min": 1, "max": 1}]
BEAM_BREAK_AFTER = [{"min": 0.3, "max": 0.3}]
#: 光束判定区指纹：最小命中间隔 10、上限 Some(6)、矩形；寿命 60（四段，无门）/ 70（延长槽，重炮门内）。
BEAM_INTERVAL = ["SpecifyMinHitIntervalDirectly", 10]
BEAM_CAP = ["Some", [{"min": 6, "max": 6}]]
BEAM_LIFETIMES = {False: 60, True: 70}             # gated → 寿命
BEAMS_PER_TREE = {False: 4, True: 5}
#: 不动的两类攻击：导弹（4 段 × p13=2）、终幕（1 段 × p13=4）。
KEPT_BREAKS = {"missile": [{"min": 2, "max": 2}], "finale": [{"min": 4, "max": 4}]}
DOWN_BEFORE = {"ungated": 36.0, "gated": 30.0}
DOWN_AFTER = {"ungated": 19.2, "gated": 9.0}
DOWN_CAP = 30                                      # 口径 B1：技能每次施放单目标总削韧 ≤30

# ------------------------------------------------------------------ 文案

OLD_DESC = ("锁定周围的敌人，架起跟随自身移动的重炮，朝锁定方向发射逐段变粗的充能激光；"
            "发动时「引擎启动」+1，威力随其层数提升；再次发动会以新的一发替换当前激光；"
            "释放技能后不再进入硬直，可立即行动")
DESC_ANCHOR = "威力随其层数提升"
DESC_CAP = "（最多10层）"
NEW_DESC = OLD_DESC.replace(DESC_ANCHOR, DESC_ANCHOR + DESC_CAP)
TEXT_DESC_COLUMNS = (5, 7)           # character_text 觉醒前 / 觉醒后技能说明


class TekutoBalanceBError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _matches(row: list[str], width: int, cells: dict[int, str]) -> bool:
    return (len(row) == width
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


# ------------------------------------------------------------------ 词条

def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力2 两行：c102 (None)→10；强度 50% → 16% / 15%；其余列逐字保留。"""
    if len(rows) != 2 or not all(_matches(r, ABILITY_NCOLS, c) for r, c in zip(rows, ABILITY2_BEFORE)):
        raise TekutoBalanceBError(f"ability {ABILITY2_KEY}: rows are not the reviewed uncapped engine rows")
    out = deepcopy(rows)
    for row in out:
        _old, new = ABILITY2_STRENGTH[row[109]]
        row[102] = ABILITY2_CAP[1]
        row[113] = row[114] = new
    if [i for i, (a, b) in enumerate(zip(rows, out)) for c in range(ABILITY_NCOLS) if a[c] != b[c]
            and c not in (102, 113, 114)]:
        raise AssertionError("ability2_rows touched more than c102/c113/c114")
    return out


def moved_leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力2 改前两行 → 队长两行（[c0,'0',''] + 能力行[5:]，强度 1/10）。"""
    if len(rows) != 2 or not all(_matches(r, ABILITY_NCOLS, c) for r, c in zip(rows, ABILITY2_BEFORE)):
        raise TekutoBalanceBError(f"ability {ABILITY2_KEY}: moved rows must be the uncapped engine rows")
    out = []
    for row in rows:
        moved = [CODE, "0", ""] + deepcopy(row[5:])
        if len(moved) != LEADER_NCOLS:
            raise AssertionError(f"moved leader row width {len(moved)}")
        moved[111] = moved[112] = MOVED_LEADER_STRENGTH
        out.append(moved)
    return out


def leader_rows(rows: list[list[str]], ability2_before: list[list[str]]) -> list[list[str]]:
    """队长：#0/#1/#2/#8 放缓，其余 6 行逐字保留，末尾追加能力2 搬来的两行（10 → 12 行）。"""
    if len(rows) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in rows):
        raise TekutoBalanceBError(f"leader {LEADER_KEY}: expected {LEADER_ROWS_BEFORE}×{LEADER_NCOLS}")
    if set(LEADER_EDITS) | set(LEADER_KEPT) != set(range(LEADER_ROWS_BEFORE)):
        raise AssertionError("LEADER_EDITS/LEADER_KEPT must cover every leader row")
    out = deepcopy(rows)
    for index, (cells, cols, old, new, _what) in LEADER_EDITS.items():
        if not _matches(out[index], LEADER_NCOLS, cells):
            raise TekutoBalanceBError(f"leader {LEADER_KEY}#{index}: not the reviewed growth row")
        for col in cols:
            out[index][col] = new
    # 口径 A6：引擎每层的充能 / 技能槽上限行必须仍是改前值（本批不动）
    for index, kind in ((3, "3"), (4, "124")):
        row = out[index]
        if (row[95], row[102], row[107], row[111], row[112]) != ("134", UID_ENGINE, kind, "5000", "5000"):
            raise TekutoBalanceBError(f"leader {LEADER_KEY}#{index}: charge/gauge-max growth row drifted")
    out.extend(moved_leader_rows(ability2_before))
    # 口径 A2：引擎逐层行（#0–#2 原位、#10/#11 搬入）同一放缓倍率
    slowed = [(LEADER_EDITS[i][2], LEADER_EDITS[i][3]) for i in (0, 1, 2)]
    slowed += [(row[113], MOVED_LEADER_STRENGTH) for row in ability2_before]
    if any(int(old) != ENGINE_LAYER_SLOWDOWN * int(new) for old, new in slowed):
        raise AssertionError(f"engine per-layer rows must all slow down ×1/{ENGINE_LAYER_SLOWDOWN}: {slowed}")
    changed = [i for i, (a, b) in enumerate(zip(rows, out)) if a != b]
    if changed != sorted(LEADER_EDITS):
        raise AssertionError(f"leader_rows touched {changed}")
    return out


# ------------------------------------------------------------------ 技能 DSL

def _tag(node) -> Any:
    return node[0] if isinstance(node, list) and node else None


def _direct_attacks(node) -> list[list]:
    """``node`` 子树里的 CreateNormalAttack，不下潜进嵌套 CreateHitArea（雷达 → 导弹各算各的）。"""
    out: list[list] = []

    def walk(n):
        if not isinstance(n, list):
            return
        if _tag(n) == "Command" and isinstance(n[1], list) and n[1]:
            if n[1][0] == "CreateHitArea":
                return
            if n[1][0] == "CreateNormalAttack":
                out.append(n[1])
                return
        for child in n:
            walk(child)

    walk(node)
    return out


def hit_areas(tree) -> list[tuple[list, bool]]:
    """全部 CreateHitArea 参数数组 + 是否在「重炮展开」门（ConditionalsConditionAccumulationNumber）then 分支内。"""
    out: list[tuple[list, bool]] = []

    def visit(node, gated: bool):
        if not isinstance(node, list):
            return
        if _tag(node) == "Command" and isinstance(node[1], list) and node[1]:
            c = node[1]
            if c[0] == "ConditionalsConditionAccumulationNumber":
                visit(c[3], True)
                visit(c[4], gated)
                return
            if c[0] == "CreateHitArea":
                out.append((c, gated))
                visit(c[20], gated)
                visit(c[23], gated)
                return
        for child in node:
            visit(child, gated)

    visit(tree, False)
    return out


def max_hits(area: list) -> int:
    """单体全程贴脸的最大段数（同 ``wf_seasonal7_kit_tekuto.hitarea_max_hits``）。"""
    lifetime, interval, cap = area[13], area[14], area[15]
    limit = int(cap[1][0]["max"]) if _tag(cap) == "Some" else None
    if _tag(interval) == "CalculatedUsingMaxNumOfHits":
        n = int(interval[1])
    elif _tag(interval) == "SpecifyMinHitIntervalDirectly":
        n = (int(lifetime[1]) - 1) // int(interval[1]) + 1
    else:
        raise TekutoBalanceBError(f"unknown hit interval {interval!r}")
    return min(n, limit) if limit else n


def down_census(tree) -> dict[str, float]:
    """单目标满打削韧（Σ 段数 × p13.max）：ungated = 必定打出，gated = 「重炮展开」门内的延长槽。"""
    total = {"ungated": 0.0, "gated": 0.0}
    for area, gated in hit_areas(tree):
        brk = sum(float(cna[13][0]["max"]) for cna in _direct_attacks(area[23]))
        total["gated" if gated else "ungated"] += brk * max_hits(area)
    return {key: round(value, 4) for key, value in total.items()}


def _is_beam(area: list, gated: bool) -> bool:
    return (_tag(area[9]) == "Rectangle" and area[13] == ["SpecifyHitAreaLifetimeDirectly", BEAM_LIFETIMES[gated]]
            and area[14] == BEAM_INTERVAL and area[15] == BEAM_CAP)


def revise_tree(tree, level: str) -> tuple[list, dict[str, Any]]:
    """Bind 上限 99→10（11 处）＋ 9 组光束 CNA p13 1→0.3；其余节点逐一保持。"""
    out = deepcopy(tree)
    if not (isinstance(out, list) and len(out) == 12 and out[0] == "ActionDsl"):
        raise TekutoBalanceBError(f"skill {level}: unexpected root")
    binds = list(wf_dsl.iter_dsl_commands(out, "BindConditionAccumulationVariable"))
    if len(binds) != BINDS_PER_TREE or any(b != BIND_BEFORE for b in binds):
        raise TekutoBalanceBError(f"skill {level}: engine binds are not {BINDS_PER_TREE}× {BIND_BEFORE}")
    for bind in binds:
        bind[5] = BIND_AFTER[5]
    beams = {False: 0, True: 0}
    kept = []
    for area, gated in hit_areas(out):
        attacks = _direct_attacks(area[23])
        if _is_beam(area, gated):
            if len(attacks) != 1 or attacks[0][13] != BEAM_BREAK_BEFORE:
                raise TekutoBalanceBError(f"skill {level}: beam attack p13 drift {[a[13] for a in attacks]}")
            attacks[0][13] = deepcopy(BEAM_BREAK_AFTER)
            beams[gated] += 1
        else:
            kept += [a[13] for a in attacks]
    if beams != BEAMS_PER_TREE:
        raise TekutoBalanceBError(f"skill {level}: beam hit areas {beams} != {BEAMS_PER_TREE}")
    if sorted(json.dumps(k) for k in kept) != sorted(json.dumps(k) for k in KEPT_BREAKS.values()):
        raise TekutoBalanceBError(f"skill {level}: non-beam attack p13 drift {kept}")
    before, after = down_census(tree), down_census(out)
    if before != DOWN_BEFORE or after != DOWN_AFTER:
        raise TekutoBalanceBError(f"skill {level}: down census {before} → {after}")
    if after["ungated"] + after["gated"] > DOWN_CAP:
        raise AssertionError("skill down total still above the cap")
    return out, {"level": level, "bind_cap": [BIND_BEFORE[5], BIND_AFTER[5]], "binds": len(binds),
                 "beam_p13": [1, 0.3], "beams": {"ungated": beams[False], "gated": beams[True]},
                 "down_before": {**before, "total": round(before["ungated"] + before["gated"], 4)},
                 "down_after": {**after, "total": round(after["ungated"] + after["gated"], 4)}}


def dsl_problems(tree) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


def row_problems(kind: str, row: list[str]) -> list[str]:
    return (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
            + L.invoke_skill_string_problems(row, set(), kind=kind)
            + L.ability_element_column_problems(kind, row, ELEMENT))


# ------------------------------------------------------------------ 文案

def _replace_desc(text: str, label: str) -> str:
    if text != OLD_DESC:
        raise TekutoBalanceBError(f"{label}: skill description is not the reviewed text")
    return NEW_DESC


def revise_texts(action, text, server) -> tuple[list, list, list]:
    if [inner for inner, _fields in action] != ["1", "2"]:
        raise TekutoBalanceBError(f"action_skill {CODE}: inner keys changed")
    new_action = []
    for inner, fields in action:
        fields = list(fields)
        if fields[7] != PROGRAMS[inner]:
            raise TekutoBalanceBError(f"action_skill {CODE}/{inner}: program {fields[7]!r}")
        fields[1] = _replace_desc(fields[1], f"action_skill {inner} c1")
        new_action.append((inner, fields))
    for label, rows in (("character_text", text), ("server character_text", server)):
        if len(rows) != 1 or len(rows[0]) != 12:
            raise TekutoBalanceBError(f"{label} {CID}: expected one 12-column row")
        for col in TEXT_DESC_COLUMNS:
            rows[0][col] = _replace_desc(rows[0][col], f"{label} c{col}")
    return new_action, text, server


# ------------------------------------------------------------------ revise

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {}
    for (kind, key), want in BEFORE.items():
        value = read(kind, key)
        got = digest(value)
        if got != want:
            raise TekutoBalanceBError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)

    ability2_before = inputs["ability", ABILITY2_KEY]
    leader = leader_rows(inputs["leader", LEADER_KEY], ability2_before)
    ability2 = ability2_rows(ability2_before)
    problems = [f"leader#{i}: {p}" for i, row in enumerate(leader) for p in row_problems("leader_ability", row)]
    problems += [f"{ABILITY2_KEY}#{i}: {p}" for i, row in enumerate(ability2) for p in row_problems("ability", row)]
    for i, row in enumerate(leader):
        if L.required_client_capabilities("leader_ability", row):
            problems.append(f"leader#{i}: unexpected capability")
    trees, tree_notes = {}, []
    for level, program in PROGRAMS.items():
        tree, ev = revise_tree(inputs["dsl", program], level)
        problems += [f"skill {level}: {p}" for p in dsl_problems(tree)]
        trees[program] = tree
        tree_notes.append(ev)
    if problems:
        raise TekutoBalanceBError("; ".join(problems))
    action, text, server = revise_texts(inputs["action", CODE], inputs["text", CID], inputs["server_text", CID])

    return {
        "ability": {ABILITY2_KEY: ability2},
        "leader": {LEADER_KEY: leader},
        "cas": {}, "table": {},
        "text": {CID: text},
        "action": {CODE: action},
        "dsl": trees,
        "server_text": {CID: server},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_tekuto.py",
            "spec": "第二批施工口径 A1–A6（无上限成长）、B1/B6（Down ≤30，只改 p13）；设计稿 growth/down_design 139993",
            "frequency": {
                "engine_layers_3min": (
                    "特克托当队长（主位，Ⓜ能力3 生效）：自身技能 11–14 发（雷队充能+25%、能力6+10%、每层自身充能+5% "
                    "约13层钳到+100%），每发 DSL +1，间隔<15秒（重炮 900 帧）时能力3#2 再+1 ⇒ 22–28 层；持重炮时 2 名"
                    "雷队友技能（队长#5 充能+50%）20–28 次 ⇒ +20–28 层；合计 40–55 层，HP≤50%（背水玩法）队长#9 每发再+2 "
                    "⇒ 60–80 层。设计稿保守估计也有 20–25 层、半血 35–45 层；按触发次数计约 30–40 次 ⇒ ≥30 ⇒ ×1/10"),
                "deviation_from_design": ("设计稿按「低频」标签取 1/5（20%/40%/1%、搬入 10%）；口径 A2 按实际次数、不按事件名称，"
                                          "与同批 kyle/celtie/hibiki/magnus 逐层行按层数取 1/10 一致，改取 1/10（复核 major）。"
                                          "若作者改判 1/5：#0 20000、#1 40000、#2 1000、#10/#11 10000，生成器常量同步"),
                "timer_77_3min": "持重炮且 HP≤50% 每 120 帧一跳 ≈ 20–60 跳（按 40）⇒ ≥30 取 1/10",
                "rounding": "#2 独立乘区 5%→0.5%，与 magnus 411 每层 0.5% 同精度（口径 A7）",
            },
            "leader": {f"leader_ability:{LEADER_KEY}#{i}": f"c{cols[0]}/c{cols[1]} {old}→{new}：{what}"
                       for i, (_c, cols, old, new, what) in LEADER_EDITS.items()},
            "leader_appended": {
                f"leader_ability:{LEADER_KEY}#10": "能力2#0 搬入：引擎每层 自身攻击力 50%→5%（1/10；during 134 kind 0 target 0）",
                f"leader_ability:{LEADER_KEY}#11": "能力2#1 搬入：引擎每层 自身技能伤害 50%→5%（1/10；during 134 kind 2 target 0）",
                "not_merged": "队长 #0/#1 是全队(雷)+雷共鸣，目标与前置都不同",
                "rows": [LEADER_ROWS_BEFORE, len(leader)],
            },
            "leader_kept": {f"leader_ability:{LEADER_KEY}#{i}": what for i, what in LEADER_KEPT.items()},
            "ability": {f"ability:{ABILITY2_KEY}#{i}": f"c102 (None)→10；c113/c114 50000→{row[113]}"
                        for i, row in enumerate(ability2)},
            "skill_dsl": {
                "engine_cap": "BindConditionAccumulationVariable 第5参 99→10（每档 11 处），官方先例 "
                              "blackflower_wiz_smr22 Bind(-17,2,[DCUnique,11],1,10)；客户端 case 101 min(count/div, cap)",
                "uncapped_part": "由队长 #0–#2 同一层数逐层行承担（口径 A5：视为已合并）",
                "down": "9 组光束（4 段寿命60 + 5 延长槽寿命70，间隔10，上限6）CNA p13 1→0.3；导弹 2、终幕 4 不动",
                "trees": tree_notes,
            },
            "skill_description": {"replaced": DESC_ANCHOR, "with": DESC_ANCHOR + DESC_CAP,
                                  "places": ["action_skill 1/2 c1", "character_text c5/c7",
                                             "server cdndata/character_text.json [5]/[7]"],
                                  "why": "技能倍率的层数贡献封顶 10 层（有上限的才写上限）"},
            "panel": "特克托无 desc_override；词条/队长面板由客户端自动生成（能力2 显示「(限10次)」）",
            "generator": ("wf_seasonal7_kit_tekuto.py：ENGINE_CAP 99→10、BEAM_BREAK=0.3、_DESC_BALANCE_B、"
                          "第六轮 apply_balance_b（build() 中叠在 wf_tekuto_low_hp 之后）；"
                          "apply_rev5_ability2 认得第二批回写后的包内行"),
            "capabilities": [],
            "runtime_verified": False,
        },
    }
