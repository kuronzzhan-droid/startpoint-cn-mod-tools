# -*- coding: utf-8 -*-
"""斩铁·白梅 159998 ``samurai_robot_plum``（光）：2026-09-27 平衡调整第二批（成长 + Down），纯函数。

口径：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板）A 节「无上限成长」、
B3「能力调用技能（kind 629）每次 ≤3」；设计稿 ``growth/growth_design.json`` 159998、
``growth/down_design.json`` 159998。设计稿按 live 1.4.1048 写，本模块按 live 1.4.1049
（1.5 批 b3cc9dca 之后）重新取数；1.5 批改过的格（队长 #3 / 能力3 #4 #5 puller 6、连击 50、
能力1 去 202）一格不碰。

落点（行号 = 0 起；除下列格与新增行外逐字保留）：

1. **无上限成长搬进队长并放缓**（口径 A3）。能力3 ``1599983`` #1/#2/#3 是「光共鸣：单次飞行
   连击 ≥250 → 自身攻击力 / 技能伤害 / 技能伤害独立乘区」，限次 ``(None)`` 的永久叠加。
   3 分钟实际次数：连击每次拍板清零，250 须在同一次飞行内由「技能槽满 +100、施放 +15 +50」叠出，
   约每 1–2 次施放一次；技能能量 580/530 + 队长充能 22.5–30%，约 15–20 秒一放 ⇒ 250 连击
   4–10 次、典型 6 次 ≤15 ⇒ 每步 ×1/5（口径 A2；不是设计稿复核 C07 的 1/10）：
   - 新增 ``leader_ability:159998`` #7/#8/#9 = ``[CODE, "0", ""] + 能力行[5:]``（能力 c≥5 → 队长 c−2），
     强度 c49/c50：攻击力 50000/100000 → 10000/20000、技能伤害 50000/100000 → 10000/20000、
     技能伤害独立乘区（694）5000/10000 → 1000/2000。队长原有 7 行没有同触发同 kind 行 ⇒ 不合并。
     队长表先例：trig12→32 自身 = 官方 341001#4；trig12→34 自身 = live 129992#1 / 149987#9；
     694 = live 芙拉菲 149987#12（口径 A4 白名单）。
   - 能力3 原位换成有上限的弱化版（设计稿给值）：#1/#2 c34 ``(None)`` → ``4``、c51/c52 → 12500/25000
     （满叠 50%→100%）；#3 c34 ``(None)`` → ``5``、c51/c52 → 1000/2000（满叠 5%→10%）。
2. **Down**（口径 B3）：能力1 #2（kind 629，自身发动技能 trig23 / puller 0 / 行 CT 0）调用的
   ``samurai_robot_plum$samurai_robot_plum_pf``：唯一的 ``CreateNormalAttack`` p13
   ``{3,3}`` → ``{0.5,0.5}``，判定区 ``CalculatedUsingMaxNumOfHits 5`` ⇒ 每次 15 → 2.5（≤3）。
   触发 CT 核对：行 CT 为 0，但触发事件是「自身发动技能」，两次之间至少隔一个技能周期
   （技能动作本身约 190 帧 ≈3.2 秒内不充能，能量 580/530 满槽约 15–20 秒）⇒ 实际间隔 >3 秒，
   适用「每次 ≤3」而非「≤1」。其余节点逐字保留。技能两档（削韧 32）按口径 B1 保留不动。
3. 面板：斩铁没有 desc_override，队长 / 能力由客户端按行自动生成（限次 4/5 会画「（上限 N 次）」）；
   技能描述不含这些数值 ⇒ 不改文案。充能 / 回槽（队长 #2 #3 #4、能力3 #4 等）按口径 A6 不动。

生成器链（kit 重建后固定顺序）：``wf_seasonal7_kit_zantetsu`` → ``wf_zantetsu_fever_revision.apply_candidate``
（09-17 修订 → 1.5 批 ``wf_balance_20260927_zantetsu.balance_rows`` → 本模块 :func:`balance_rows` 与
:func:`pf_tree`）。kit 源码不引用本批；kit 已钉冻结 donor 1499963#1（FROZEN_DONORS），源码 sha 已变，
``gates.json`` 的 ``kit_source_sha256`` 登记为已知过期、待按 tables→kit→…→gates 步序重跑；测试断言链尾 == :func:`revise`。

跨角色 donor：mod-tools 与 midautumn 设计稿里借斩铁的只有 1599981#0/#1、1599982#0/#2、1599983#4/#6、
1599985#0、1599986#0/#1、leader 159998#1/#6（1 基 #2/#7），本批改的 1599983#1–#3 与队长新增行都不在其中。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "159998"
CODE = "samurai_robot_plum"
PACKAGES = ["s7-zantetsu"]
#: 候选 manifest 现值 1.0.2（1.5 批写入）⇒ 1.0.3。
PACKAGE_VERSION = {"s7-zantetsu": "1.0.3"}
CAPABILITIES: list[str] = []
#: 候选 134 个 manifest 条目与文件逐一一致，本模块读的四项与 live 逐字相同（2026-09-27 只读核对）。
REVIEWED_DRIFT: dict = {}

ELEMENT = 4                        # master/character c3：光（0 基内部元素）
LIGHT = "White"
LEADER_NCOLS, ABILITY_NCOLS = 124, 126
A1, A3 = f"{CID}1", f"{CID}3"
CAS_CHANGE_SKILL = f"change_skill_{CODE}"
CAS_PF = f"ability_skill_{CODE}_pf"
PF_PROGRAM = f"battle/action/skill/action/rare5/{CODE}${CODE}_pf"

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数，与候选 s7-zantetsu 1.0.2 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；任一不符 ⇒ revise() 拒绝（fail closed）。
#: 能力1 只作守卫（629 触发 / 程序路径），不返回。
BEFORE: dict[tuple[str, str], str] = {
    ("leader", CID): "8ebe85b8b56e13c141786f5f2084f126dc6a37b7939bbc207b5e486ca8927392",
    ("ability", A1): "3a04b12cc8e4c4d0139045a12a91fee1a004648ae10a186b0281671563db92dd",
    ("ability", A3): "26a226d4042460b538c1fead0d0e2423450cca867052a7fc6828817b8822bffc",
    ("dsl", PF_PROGRAM): "2e505a34bc4b0af087a9d6c5761e5eecfe676de46f4ca2fe575c482edb27a6d1",
}

# ---------------------------------------------------------------- 成长（能力3 #1–#3 → 队长 #7–#9）

LEADER_ROWS_BEFORE, LEADER_ROWS_AFTER = 7, 10
A3_ROWS = 7
GROWTH_INDEXES = (1, 2, 3)         # 能力3 #1 攻击力 / #2 技能伤害 / #3 技能伤害独立乘区
COMBO_250 = "25000000"             # 连击阈值 250（100000 = 1 连击）
_A3_GROWTH_COMMON = {
    0: f"{CODE}_3", 1: "false", 2: "action_skill", 3: "0", 5: "0", 6: "2", 9: "600000",
    10: "600000", 11: LIGHT, 13: "0", 20: "0", 27: "12", 30: COMBO_250, 31: COMBO_250,
    34: "(None)", 35: "0", 39: "(None)", 46: "0", 48: "0",
}
#: 能力3 改前逐格指纹（全部非空列；其余列必须为空）。
A3_BEFORE = {
    1: {**_A3_GROWTH_COMMON, 47: "32", 51: "50000", 52: "100000"},
    2: {**_A3_GROWTH_COMMON, 47: "34", 51: "50000", 52: "100000"},
    3: {**_A3_GROWTH_COMMON, 47: "694", 51: "5000", 52: "10000"},
}
#: 能力侧有上限的弱化版（设计稿 growth_design 159998 replace_in_ability）：(限次 c34, c51, c52)。
A3_CAPPED = {1: ("4", "12500", "25000"), 2: ("4", "12500", "25000"), 3: ("5", "1000", "2000")}
A3_AFTER = {i: {**cells, 34: A3_CAPPED[i][0], 51: A3_CAPPED[i][1], 52: A3_CAPPED[i][2]}
            for i, cells in A3_BEFORE.items()}
#: 队长新增行的逐步强度 c49/c50 = 能力行原值 ×1/5（250 连击 3 分钟典型 6 次 ≤15）。
LEADER_GROWTH = {1: ("10000", "20000"), 2: ("10000", "20000"), 3: ("1000", "2000")}
SLOWDOWN = (1, 5)

#: 队长新增行（#7/#8/#9）逐格指纹，= ``[CODE, "0", ""] + 能力行改前[5:]`` 再换强度（测试逐格对派生）。
_LEADER_GROWTH_COMMON = {
    0: CODE, 1: "0", 3: "0", 4: "2", 7: "600000", 8: "600000", 9: LIGHT, 11: "0", 18: "0",
    25: "12", 28: COMBO_250, 29: COMBO_250, 32: "(None)", 33: "0", 37: "(None)", 44: "0", 46: "0",
}
LEADER_NEW = {
    7: {**_LEADER_GROWTH_COMMON, 45: "32", 49: "10000", 50: "20000"},
    8: {**_LEADER_GROWTH_COMMON, 45: "34", 49: "10000", 50: "20000"},
    9: {**_LEADER_GROWTH_COMMON, 45: "694", 49: "1000", 50: "2000"},
}
LEADER_SOURCE = {7: 1, 8: 2, 9: 3}  # 队长新行 → 能力3 源行

# ---------------------------------------------------------------- Down（629 剑 PF 树 p13）

PF_HITS = 5                        # CreateHitArea CalculatedUsingMaxNumOfHits
DOWN_OLD = [{"min": 3, "max": 3}]
DOWN_NEW = [{"min": 0.5, "max": 0.5}]
DOWN_PARAM = 13                    # CreateNormalAttack p13（按 SLv 的 min/max）
DOWN_CAP_PER_INVOKE = 3            # 口径 B3：629 每次 ≤3（触发间隔 >3 秒）
#: 629 行守卫：能力1 #2 = 光共鸣（前置2）+ 自身发动技能（trig 23 / puller 0 / CT 0）→ 629 → PF 程序。
A1_INVOKE_INDEX = 2
A1_INVOKE_GUARD = {27: "23", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "0",
                   47: "629", 70: CAS_PF, 71: PF_PROGRAM}

#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    f"leader_ability:{CID}#7": "光·编成≥6 时: 连击≥250 → 自身 攻击力 10%→20%",
    f"leader_ability:{CID}#8": "光·编成≥6 时: 连击≥250 → 自身 技能伤害 10%→20%",
    f"leader_ability:{CID}#9": "光·编成≥6 时: 连击≥250 → 自身 独立乘区技能伤害 1%→2%",
    f"ability:{A3}#1": "光·编成≥6 时: 连击≥250(限4次) → 自身 攻击力 12.5%→25%",
    f"ability:{A3}#2": "光·编成≥6 时: 连击≥250(限4次) → 自身 技能伤害 12.5%→25%",
    f"ability:{A3}#3": "光·编成≥6 时: 连击≥250(限5次) → 自身 独立乘区技能伤害 1%→2%",
}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
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


def ability3_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力3 #1–#3：限次 (None) → 4/4/5，强度 → 12500/25000、12500/25000、1000/2000；其余 4 行逐字保留。

    改前 / 改后两种指纹都接受（链重跑幂等），其余形态一律拒绝。"""
    if len(rows) != A3_ROWS or any(len(row) != ABILITY_NCOLS for row in rows):
        raise ValueError(f"ability {A3}: expected {A3_ROWS} records of {ABILITY_NCOLS} columns")
    out = deepcopy(rows)
    for index in GROWTH_INDEXES:
        row = out[index]
        if not (_matches(row, ABILITY_NCOLS, A3_BEFORE[index])
                or _matches(row, ABILITY_NCOLS, A3_AFTER[index])):
            raise ValueError(f"ability {A3}#{index}: row is not the reviewed 250-combo growth shape")
        out[index] = _row(ABILITY_NCOLS, A3_AFTER[index])
    for index, (old, new) in enumerate(zip(rows, out)):
        if index not in GROWTH_INDEXES and old != new:
            raise AssertionError(f"ability {A3}#{index}: untouched row changed")
    if {row[1] for row in out} != {"false"}:
        raise ValueError(f"ability {A3}: whole-key main-slot flag drifted")
    return out


def leader_rows(rows: list[list[str]]) -> list[list[str]]:
    """队长：原 7 行逐字保留，队尾追加 #7–#9（250 连击成长，逐步 ×1/5）；已追加则原样返回。"""
    if any(len(row) != LEADER_NCOLS for row in rows):
        raise ValueError(f"leader_ability {CID}: unexpected row width")
    expected = [_row(LEADER_NCOLS, LEADER_NEW[i]) for i in sorted(LEADER_NEW)]
    if len(rows) == LEADER_ROWS_AFTER and rows[LEADER_ROWS_BEFORE:] == expected:
        out = deepcopy(rows)
    elif len(rows) == LEADER_ROWS_BEFORE:
        out = deepcopy(rows) + expected
    else:
        raise ValueError(f"leader_ability {CID}: expected {LEADER_ROWS_BEFORE} (or revised "
                         f"{LEADER_ROWS_AFTER}) records, got {len(rows)}")
    growth = [i for i, row in enumerate(out) if row[3] == "0" and row[25] == "12" and row[28] == COMBO_250]
    if growth != sorted(LEADER_NEW):
        raise ValueError(f"leader_ability {CID}: 250-combo growth rows at {growth}")
    return out


def balance_rows(leader: list[list[str]], ability3: list[list[str]]
                 ) -> tuple[list[list[str]], list[list[str]]]:
    """生成器链入口（``wf_zantetsu_fever_revision.apply_candidate`` 在 1.5 批之后调用）。"""
    return leader_rows(leader), ability3_rows(ability3)


def _cmds(node, name: str) -> list[list]:
    out: list[list] = []
    if isinstance(node, list):
        if node and node[0] == name:
            out.append(node)
        for child in node:
            out.extend(_cmds(child, name))
    elif isinstance(node, dict):
        for child in node.values():
            out.extend(_cmds(child, name))
    return out


def _masked(tree) -> Any:
    masked = deepcopy(tree)
    (attack,) = _cmds(masked, "CreateNormalAttack")
    attack[DOWN_PARAM] = None
    return masked


#: 629 剑 PF 树除 p13 外的形状指纹（live 1.4.1049 = kit ``build_pf_action_tree`` 产物）。
PF_TREE_SHAPE = "b3308674841db4a2e1799b28357d7f5d548c5b5e736b5c69ee0a11cbe1386853"


def pf_tree(tree) -> list:
    """629 剑 PF 树：唯一 ``CreateNormalAttack`` 的 p13 {3,3} → {0.5,0.5}；其余节点逐字保留。

    改前 / 改后都接受（幂等）；除 p13 外任何节点漂移都拒绝。"""
    out = deepcopy(tree)
    attacks = _cmds(out, "CreateNormalAttack")
    areas = _cmds(out, "CreateHitArea")
    if len(attacks) != 1 or len(areas) != 1:
        raise ValueError(f"{PF_PROGRAM}: expected one hit area with one attack, "
                         f"got {len(areas)}/{len(attacks)}")
    if areas[0][14] != ["CalculatedUsingMaxNumOfHits", PF_HITS]:
        raise ValueError(f"{PF_PROGRAM}: hit count drifted: {areas[0][14]}")
    if attacks[0][DOWN_PARAM] not in (DOWN_OLD, DOWN_NEW):
        raise ValueError(f"{PF_PROGRAM}: p13 drifted: {attacks[0][DOWN_PARAM]}")
    if digest(_masked(out)) != PF_TREE_SHAPE:
        raise ValueError(f"{PF_PROGRAM}: nodes other than p13 drifted")
    attacks[0][DOWN_PARAM] = deepcopy(DOWN_NEW)
    return out


def down_per_invoke(tree) -> float:
    (attack,) = _cmds(tree, "CreateNormalAttack")
    (area,) = _cmds(tree, "CreateHitArea")
    return area[14][1] * max(v["max"] for v in attack[DOWN_PARAM])


# ---------------------------------------------------------------- 门禁

def row_problems(kind: str, rows: list[list[str]], strings: set[str]) -> list[str]:
    import wf_client_legality as L
    probs = []
    for i, row in enumerate(rows):
        for p in (L.client_legality_problems(kind, row) + L.declared_block_field_problems(kind, row)
                  + L.invoke_skill_string_problems(row, frozenset(strings), kind)
                  + L.ability_element_column_problems(kind, row, ELEMENT)):
            probs.append(f"{kind}#{i}: {p}")
    return probs


def dsl_problems(tree) -> list[str]:
    import wf_client_legality as L
    import wf_dsl
    probs = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        probs.append("AMF3 roundtrip mismatch")
    probs += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    probs += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    probs += [f"scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    probs += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    probs += [f"player_side: {p}" for p in wf_dsl.player_side_dsl_problems(tree)]
    return probs


def capability_set(kind: str, rows: list[list[str]]) -> set[str]:
    import wf_client_legality as L
    return {cap for row in rows for cap in L.required_client_capabilities(kind, row)}


def _invoke_guard(a1: list[list[str]]) -> None:
    if len(a1) <= A1_INVOKE_INDEX:
        raise ValueError(f"ability {A1}: 629 row missing")
    row = a1[A1_INVOKE_INDEX]
    drift = {col: row[col] for col, value in A1_INVOKE_GUARD.items() if row[col] != value}
    if drift:
        raise ValueError(f"ability {A1}#{A1_INVOKE_INDEX}: 629 trigger/program drifted {drift}")


# ---------------------------------------------------------------- 批次入口

def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    leader_in = _checked(read, "leader", CID)
    a1_in = _checked(read, "ability", A1)
    a3_in = _checked(read, "ability", A3)
    pf_in = _checked(read, "dsl", PF_PROGRAM)
    _invoke_guard(a1_in)
    leader, a3 = balance_rows(leader_in, a3_in)
    pf = pf_tree(pf_in)
    strings = {CAS_CHANGE_SKILL, CAS_PF}
    probs = row_problems("leader_ability", leader, strings) + row_problems("ability", a3, strings)
    probs += [f"dsl {PF_PROGRAM}: {p}" for p in dsl_problems(pf)]
    if down_per_invoke(pf) > DOWN_CAP_PER_INVOKE:
        probs.append(f"629 down per invoke {down_per_invoke(pf)} > {DOWN_CAP_PER_INVOKE}")
    if probs:
        raise ValueError(probs)
    new_caps = ((capability_set("leader_ability", leader) - capability_set("leader_ability", leader_in))
                | (capability_set("ability", a3) - capability_set("ability", a3_in)))
    if new_caps - set(CAPABILITIES):
        raise ValueError(f"revised rows need undeclared client capabilities: {sorted(new_caps)}")
    return {
        "ability": {A3: a3},
        "leader": {CID: leader},
        "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {PF_PROGRAM: pf}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927b_zantetsu.py",
            "rules": "第二批施工口径 A2/A3（成长）、B3（629 Down）；设计稿 growth_design / down_design 159998",
            "changes": {
                f"leader_ability:{CID}#7-#9": "新增：由能力3 #1/#2/#3 派生，250 连击每步 攻/技伤 10→20%、"
                                              "技伤独立乘区 1→2%（原 50→100% / 5→10% 的 1/5）",
                f"ability:{A3}#1/#2 c34/c51/c52": "(None)/50000/100000 → 4/12500/25000",
                f"ability:{A3}#3 c34/c51/c52": "(None)/5000/10000 → 5/1000/2000",
                f"dsl:{PF_PROGRAM} CreateNormalAttack p13": "{3,3} → {0.5,0.5}（5 段 15 → 2.5）",
            },
            "frequency": {
                "every_250_combo": "连击每次拍板清零，250 须单次飞行内叠出（技能槽满 +100、施放 +15/+50）；"
                                   "约 15–20 秒一放 ⇒ 3 分钟 4–10 次、典型 6 次（≤15）⇒ ×1/5",
                "invoke_629": "自身发动技能（trig23 / puller0 / 行 CT 0）；技能周期 >3 秒 ⇒ 每次 ≤3，取 2.5",
            },
            "growth_3min_typical": "6 次 250 连击：队长 攻/技伤 +60→120%、独立乘区 +6→12%（原能力侧 +300→600% / "
                                   "+30→60%）；能力侧封顶 攻/技伤 50→100%、独立乘区 5→10%",
            "describe_after": DESCRIBE_AFTER,
            "kept": "技能两档削韧 32（口径 B1 保留）；充能/回槽行（口径 A6）；1.5 批改动",
            "panel": "无 desc_override，客户端按行自动生成；技能描述无相关数值",
            "generator": "wf_seasonal7_kit_zantetsu（kit 已钉冻结 donor 1499963#1（FROZEN_DONORS））→ wf_zantetsu_fever_revision.apply_candidate"
                         "（09-17 → 1.5 批 balance_rows → 本批 balance_rows + pf_tree）",
            "leader_precedents": "trig12→32 自身 官方 341001#4；trig12→34 自身 live 129992#1/149987#9；"
                                 "694 live 149987#12（口径 A4）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }
