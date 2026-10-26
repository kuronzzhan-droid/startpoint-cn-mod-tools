# -*- coding: utf-8 -*-
"""希尔媞「千刃共振」149996 ``wind_spgirl_swim``（风）：灰服版纳入 2026-09-27 平衡第三轮，纯函数。

作者原话（主会话转述）：「对方灰服调整过的角色，把这版替换我本地的，然后一并纳入调整」（替换已在本地 1.4.1054 完成，
commit 183092fa ``wf_balance_20260927b_gray3``）；成长口径「砍到4/5，或者7/10这样吧」「可以砍到2/3」
「数值尽量取5的倍数」。规则建议 = 主会话 ``scratchpad/gray3_results.json`` 最后一版 rules 结果（rows / summary /
vs_batch2）；移入队长照 ``batch2/第二批施工口径.md`` A3（行 = ``[队长行 c0, '0', ''] + 能力行[5:]``，能力 c≥5 →
队长 c−2；前置原样搬、不新增共鸣前置——第三轮口径 D3），先例 ``wf_balance_20260927c_soriz``（队长 c0 = 该键既有
``*_leader`` 名）。BEFORE = live 链尾 1.4.1054（gray3 导入后）。

## 改动（行号 0 起；其余格与未列行逐字保留）

1. ``ability:1499964``（能力4，唯一一行）每 77 连击自身眩晕积蓄：+25%、最多 101 次（理论 +2525%）→
   **+10%、最多 10 次**（合计 100% = 眩晕积蓄自身上限，第二批口径 B4）。只改 c34 101→10、c51/c52 25000→10000；
   kind 51 保留（与能力5「对眩晕/畏缩敌人特攻」联动，灰服版思路）。
2. ``ability:1499962`` #0/#1/#2（能力2，每 77 连击风属性全队攻击 / 直击 / 技能伤害 +12.5%、最多 101 次 = 能力里的
   实质无上限成长）→ 原位有上限版 **各 +10%、最多 10 次**（各合计 +100%）：c34 101→10、c51/c52 12500→10000。
3. ``leader_ability:149996`` 追加 #5/#6/#7 = ``["wind_spgirl_swim_leader", "0", ""] + 能力2改前行[5:]``：
   每 77 连击风属性全队攻击 / 直击 / 技能伤害 **+10%**（12.5×4/5，最多 101 次保留）。队长原 #0/#1 目标是自身
   （c46=0），与这 3 行（目标 5 风队）不同 ⇒ 不合并、新起；原行无前置 ⇒ 新行也无前置。
4. 队长 #0/#1（每 77 连击自身攻击 / 直击 +12.5%、最多 101 次）原位 **+10%**（4/5）：只改 c49/c50 12500→10000。
   4/5 档理由（rules 结果）：她的队长技除充能外没有任何固定攻击/伤害加成，属于「只靠成长」；灰服还删了我方能力6
   「施技后连击 +77」，77 连击类行触发更慢。
5. 能力6#3 629「旋风」（主位、自身施技触发、CT 60 帧 = 1 秒 ≤3 秒 ⇒ 每次削韧 ≤1，第二批口径 B3）：
   ``ability_skill_wind_spgirl_swim_whirlwind`` 树唯一判定区 ``CalculatedUsingMaxNumOfHits 24``（无 Some 硬顶），
   onHit 唯一 CreateNormalAttack 的 p13 13/24 → **1/24**：每次单目标 24×13/24 = 13 → 24×1/24 = **1**（正好顶到上限，
   沿用灰方「总量/24」的写法）。只改 p13（口径 B6），倍率 0.667×24、p14 Fever 点 15/24、耐性 -15%、全队 PF +75% 不动。

## 不改
- 技能连击加成 p8（原生机制，与官方 wind_spgirl_1/2/3 同结构）不封顶；充能/加槽类（能力1#0/#1、能力6#0、队长 #2–#4）
  本轮不动；能力3（有 10 层上限、777 清零）、能力5（限 5 次）、能力6#1（直击判定次数，作者认定特色）不动。
- 面板：本角色没有任何 ``desc_override_wind_spgirl_swim*`` 键，能力/队长面板由客户端按行自动生成（主会话：auto 面板
  一律不新建覆盖文案）；技能描述、character_text、旋风文案「额外发动「旋风」」都不含这些数值 ⇒ 不改文案。
  :func:`revise` 会确认覆盖键仍不存在（出现即拒绝，须同步文案）。

## 禁止重放第二批
导入后 live ``1499964`` 的摘要 == ``wf_balance_20260927b_swimceltie.BEFORE``（灰版就是第二批改前那一行）：第二批
泳装模块会把能力4 改成「自身直击 +20%×5」，与本轮方案冲突——暂存计划里不得再出现它。本模块产物发布后它按摘要
fail closed（测试断言）。

## 生成器
无 flow 包（``PACKAGES = []``，BarePlan）、无生成器：``wf_campus_celtie_data.py`` 只建 149989；
``work/character_packs/xierti_swim/build_workspace.py``、``_patch_kit.py`` 是历史脚本（会写回旧行，不得重跑）；
``wf_balance_20260927b_gray3`` 按导入前摘要 fail closed。本模块是这些键本轮数值的唯一真源。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L
import wf_describe
import wf_dsl

CID = "149996"
CODE = "wind_spgirl_swim"
PACKAGES: list[str] = []
PACKAGE_VERSION: dict[str, str] = {}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                                   # 内部元素：风（0 基）
ABILITY_NCOLS, LEADER_NCOLS = 126, 124
A2, A4, A6 = CID + "2", CID + "4", CID + "6"
LEADER_C0 = CODE + "_leader"                  # 该键既有 5 行的 c0（先例 soriz_leader）
WHIRLWIND_KEY = "ability_skill_wind_spgirl_swim_whirlwind"
WHIRLWIND_PROGRAM = f"battle/action/skill/action/ability_skill/{WHIRLWIND_KEY}${WHIRLWIND_KEY}"
PANEL_OVERRIDE_KEYS = tuple(f"desc_override_{CODE}" + suffix
                            for suffix in ("", "_leader", "_1", "_2", "_3", "_4", "_5", "_6"))

#: live 输入基线（2026-09-27 本地链尾 1.4.1054 = gray3 导入后，extra5 make_read(live_only=True) 只读取数）。
#: ability:1499966（629 行 CT/触发/前置）与旋风文案只读，锁住「CT ≤3 秒 ⇒ 每次 ≤1」的前提。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", A2): "79fb5c985fe230ffb90670b7ebd53802a757d216166d8b01ce544974b02262d4",
    ("ability", A4): "0d0e70e8f7c1f5b6453f536f84ab999f19c73f30d6d589c373d234e767547a8e",
    ("ability", A6): "888efb94ce06f484d0681390f80e3357e279582ca8c539536cadb683feb03622",
    ("leader", CID): "800cd4215705e55e08ab2af335ae814ab742a0df0a710129bc1fa5da49ba5fdb",
    ("cas", WHIRLWIND_KEY): "6f3afa971de5480a4dff002d0a1c76e30b084d5b31ec562ddb9954591f397891",
    ("dsl", WHIRLWIND_PROGRAM): "8d981129d5a4cc5dab87d5b1ac0b43c0a2296c0c07f4aa8c937721fd5953b5e3",
}

# ---------------------------------------------------------------- 逐格指纹（全部非空格；其余列必须为空）

_COMBO77 = {3: "0", 5: "0", 6: "0", 13: "0", 20: "0", 27: "12", 30: "7700000", 31: "7700000", 35: "0",
            39: "(None)", 46: "0"}
#: 能力2 改前三行：每 77 连击 → 全队(风) 攻击 32 / 直击 33 / 技能伤害 34 +12.5%，限 101。
A2_BEFORE = {i: {0: CODE + "_2", 1: "true", 2: icon, **_COMBO77, 34: "101", 47: kind, 48: "5", 49: "Green",
                 51: "12500", 52: "12500"}
             for i, (icon, kind) in enumerate((("attack_green", "32"), ("attack_green", "33"),
                                                ("action_skill", "34")))}
A2_CHANGED = {34: ("101", "10"), 51: ("12500", "10000"), 52: ("12500", "10000")}
A2_AFTER = {i: {**cells, **{c: new for c, (_old, new) in A2_CHANGED.items()}} for i, cells in A2_BEFORE.items()}

#: 能力4 改前唯一一行：每 77 连击 → 自身眩晕积蓄（51）+25%，限 101（= 第二批泳装模块 BEFORE_CELLS）。
A4_BEFORE = {0: CODE + "_4", 1: "true", 2: "attack_common", **_COMBO77, 34: "101", 47: "51", 48: "0",
             51: "25000", 52: "25000"}
A4_CHANGED = {34: ("101", "10"), 51: ("25000", "10000"), 52: ("25000", "10000")}
A4_AFTER = {**A4_BEFORE, **{c: new for c, (_old, new) in A4_CHANGED.items()}}

_L_COMBO77 = {0: LEADER_C0, 1: "0", 3: "0", 4: "0", 11: "0", 18: "0", 25: "12", 28: "7700000", 29: "7700000",
              32: "101", 33: "0", 37: "(None)", 44: "0"}
#: 队长 #0/#1 改前：每 77 连击 → 自身攻击 32 / 直击 33 +12.5%，限 101，无前置。
L_BEFORE = {i: {**_L_COMBO77, 45: kind, 46: "0", 49: "12500", 50: "12500"} for i, kind in ((0, "32"), (1, "33"))}
L_CHANGED = {49: ("12500", "10000"), 50: ("12500", "10000")}
L_AFTER = {i: {**cells, **{c: new for c, (_old, new) in L_CHANGED.items()}} for i, cells in L_BEFORE.items()}
LEADER_ROWS_BEFORE = 5
#: 队长 #2–#4（风编成≥6 的充能/加槽）逐字保留：只核 kind 布局。
LEADER_KINDS_BEFORE = ("32", "33", "211", "245", "211")
#: 新增队长行 #5/#6/#7 ← 能力2 #0/#1/#2；强度 12.5×4/5 = 10%，限 101 保留。
LEADER_ADDED = {5: 0, 6: 1, 7: 2}
LEADER_GROWTH = "10000"
LEADER_ADDED_CELLS = {li: {**_L_COMBO77, 45: A2_BEFORE[ai][47], 46: "5", 47: "Green",
                           49: LEADER_GROWTH, 50: LEADER_GROWTH}
                      for li, ai in LEADER_ADDED.items()}
FACTOR = (4, 5)

#: 能力6#3 = 629 旋风（只读守卫）：主位（202）+ 自身施技（trigger 23，puller 0）+ CT 60 帧。
A6_WHIRLWIND_ROW = 3
A6_WHIRLWIND_CELLS = {0: CODE + "_6", 1: "true", 2: "special", 3: "0", 5: "0", 6: "202", 13: "0", 20: "0",
                      27: "23", 28: "0", 30: "100000", 31: "100000", 34: "(None)", 35: "60", 39: "(None)",
                      46: "0", 47: "629", 70: WHIRLWIND_KEY, 71: WHIRLWIND_PROGRAM}
FAST_CT_FRAMES = 180                          # CT ≤3 秒（60 帧/秒）⇒ 每次 ≤1（第二批口径 B3）
WHIRLWIND_CAP = 1.0
WHIRLWIND_HITS = 24
P13_BEFORE = 13 / 24                          # 0.5416666666666666（灰方写法：总量 13 ÷ 24 段）
P13_AFTER = 1 / 24                            # 0.041666666666666664 ⇒ 24 段合计 1.0
WHIRLWIND_CAS_ROWS = [["额外发动「旋风」"]]

#: wf_describe 回读（改后）；测试与 notes 共用。
DESCRIBE_AFTER = {
    f"ability:{A2}": ["连击≥77(限10次) → 赋予全队(风) 攻击力 10%",
                      "连击≥77(限10次) → 赋予全队(风) Direct伤害 10%",
                      "连击≥77(限10次) → 赋予全队(风) 技能伤害 10%"],
    f"ability:{A4}": ["连击≥77(限10次) → 自身 眩晕蓄积 10%"],
    f"leader_ability:{CID}": ["连击≥77(限101次) → 自身 攻击力 10%",
                              "连击≥77(限101次) → 自身 Direct伤害 10%",
                              "风·编成≥6 时: 连击≥777 → 赋予全队(风) 技能槽 150%",
                              "风·编成≥6 时: 赋予全队(风) 2号位技能槽 50%",
                              "风·编成≥6 时: 强化弹射Lv3≥1 → 赋予全队(风) 技能槽 77%",
                              "连击≥77(限101次) → 赋予全队(风) 攻击力 10%",
                              "连击≥77(限101次) → 赋予全队(风) Direct伤害 10%",
                              "连击≥77(限101次) → 赋予全队(风) 技能伤害 10%"],
}


class SwimCeltieBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _checked(read: Callable[[str, Any], Any], kind: str, key: str) -> Any:
    value = read(kind, key)
    got = digest(value)
    if got != BEFORE[(kind, key)]:
        raise SwimCeltieBalanceError(f"unreviewed live baseline for {kind}:{key} "
                                     f"({got} != {BEFORE[(kind, key)]})")
    return deepcopy(value)


def _matches(row: list[str], ncols: int, cells: dict[int, str]) -> bool:
    return (len(row) == ncols
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def _row(ncols: int, cells: dict[int, str]) -> list[str]:
    row = [""] * ncols
    for col, value in cells.items():
        row[col] = value
    return row


# ---------------------------------------------------------------- 表行


def ability2_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力2 三行：每 77 连击全队(风) 攻击/直击/技能伤害 +12.5%（限 101）→ +10%（限 10）。"""
    if len(rows) != len(A2_BEFORE):
        raise SwimCeltieBalanceError(f"ability {A2}: expected {len(A2_BEFORE)} records, got {len(rows)}")
    out = []
    for i, row in enumerate(rows):
        if not _matches(row, ABILITY_NCOLS, A2_BEFORE[i]):
            raise SwimCeltieBalanceError(f"ability {A2}#{i}: uncapped combo-77 team row not found")
        out.append(_row(ABILITY_NCOLS, A2_AFTER[i]))
    return out


def ability4_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力4 唯一一行：每 77 连击自身眩晕积蓄 +25%（限 101）→ +10%（限 10，合计 100%）。"""
    if len(rows) != 1:
        raise SwimCeltieBalanceError(f"ability {A4}: expected 1 record, got {len(rows)}")
    if not _matches(rows[0], ABILITY_NCOLS, A4_BEFORE):
        raise SwimCeltieBalanceError(f"ability {A4}#0: combo Stunify row (T12 77, limit 101, I51 25%) not found")
    return [_row(ABILITY_NCOLS, A4_AFTER)]


def leader_growth_row(ability_row: list[str], leader_c0: str = LEADER_C0) -> list[str]:
    """口径 A3：``[队长 c0, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2），强度 12.5% → 10%（×4/5）。"""
    index = next((i for i, cells in A2_BEFORE.items() if _matches(ability_row, ABILITY_NCOLS, cells)), None)
    if index is None:
        raise SwimCeltieBalanceError("leader growth must be derived from an uncapped ability-2 row")
    row = [leader_c0, "0", ""] + list(ability_row[5:])
    row[49] = row[50] = LEADER_GROWTH
    added = {ai: li for li, ai in LEADER_ADDED.items()}[index]
    if not _matches(row, LEADER_NCOLS, LEADER_ADDED_CELLS[added]):
        raise AssertionError(f"unexpected leader growth row shape for ability {A2}#{index}")
    return row


def leader_rows(rows: list[list[str]], ability2_before: list[list[str]]) -> list[list[str]]:
    """队长 #0/#1 12.5% → 10%；#2–#4 逐字保留；追加 #5–#7（能力2 三行的无上限部分，10%，限 101）。"""
    if len(rows) != LEADER_ROWS_BEFORE or any(len(r) != LEADER_NCOLS for r in rows):
        raise SwimCeltieBalanceError(f"leader_ability {CID}: expected {LEADER_ROWS_BEFORE}×{LEADER_NCOLS} rows "
                                     "(or growth rows already present)")
    if tuple(r[45] for r in rows) != LEADER_KINDS_BEFORE or {r[0] for r in rows} != {LEADER_C0}:
        raise SwimCeltieBalanceError(f"leader_ability {CID}: layout drifted")
    out = deepcopy(rows)
    for i, cells in L_BEFORE.items():
        if not _matches(out[i], LEADER_NCOLS, cells):
            raise SwimCeltieBalanceError(f"leader_ability {CID}#{i}: combo-77 self growth row not found")
        out[i] = _row(LEADER_NCOLS, L_AFTER[i])
    out += [leader_growth_row(ability2_before[ai]) for _li, ai in sorted(LEADER_ADDED.items())]
    for i, (old, new) in enumerate(zip(rows, out)):
        if i not in L_BEFORE and old != new:
            raise AssertionError(f"leader_ability {CID}#{i}: untouched row changed")
    return out


def whirlwind_row_guard(rows: list[list[str]]) -> int:
    """能力6#3 = 629 旋风：主位 + 自身施技 + CT 60 帧 ⇒ 返回 CT 帧数（≤3 秒档 ⇒ 每次 ≤1）。"""
    if len(rows) != 4 or not _matches(rows[A6_WHIRLWIND_ROW], ABILITY_NCOLS, A6_WHIRLWIND_CELLS):
        raise SwimCeltieBalanceError(f"ability {A6}#{A6_WHIRLWIND_ROW}: whirlwind 629 row drifted")
    if [i for i, r in enumerate(rows) if r[47] == "629"] != [A6_WHIRLWIND_ROW]:
        raise SwimCeltieBalanceError(f"ability {A6}: unexpected extra 629 rows")
    ct = int(rows[A6_WHIRLWIND_ROW][35])
    if ct > FAST_CT_FRAMES:
        raise SwimCeltieBalanceError(f"ability {A6}#{A6_WHIRLWIND_ROW}: CT {ct} frames > 3 s, cap is no longer 1")
    return ct


# ---------------------------------------------------------------- 旋风 629 树


def _slv(value: float) -> list[dict[str, float]]:
    return [{"min": value, "max": value}]


def whirlwind_parts(tree) -> tuple[list, list]:
    """(唯一 CreateHitArea, 其 onHit 里唯一 CreateNormalAttack)；树里任何别处的攻击/判定区一律拒绝。"""
    areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
    attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
    if len(areas) != 1 or len(attacks) != 1:
        raise SwimCeltieBalanceError(f"whirlwind: expected 1 hit area / 1 attack, got {len(areas)}/{len(attacks)}")
    area, attack = areas[0], attacks[0]
    on_hit = list(wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack"))
    if len(on_hit) != 1 or on_hit[0] is not attack or list(wf_dsl.iter_dsl_commands(area[20])):
        raise SwimCeltieBalanceError("whirlwind: attack is not the hit area's only onHit attack")
    return area, attack


def area_hits(area) -> int:
    """判定区对单一目标的最大命中数（本树只接受 CalculatedUsingMaxNumOfHits + 无 Some 硬顶）。"""
    if area[14][0] != "CalculatedUsingMaxNumOfHits" or area[15] != ["None"]:
        raise SwimCeltieBalanceError(f"whirlwind: unreviewed hit-count shape {area[14]} / {area[15]}")
    return area[14][1]


def detoughness(tree) -> float:
    """每次发动对单一目标的总削韧 = 最大命中数 × p13。"""
    area, attack = whirlwind_parts(tree)
    value = attack[13]
    if (not isinstance(value, list) or len(value) != 1 or set(value[0]) != {"min", "max"}
            or value[0]["min"] != value[0]["max"]):
        raise SwimCeltieBalanceError(f"whirlwind: unreviewed p13 shape {value}")
    return round(area_hits(area) * value[0]["max"], 6)


def whirlwind_tree(tree) -> list:
    """旋风：p13 13/24 → 1/24（24 段合计 13 → 1），其余节点逐字保留。"""
    out = deepcopy(tree)
    area, attack = whirlwind_parts(out)
    if (area[2], area[13], area_hits(area), area[22], area[24]) != (
            0, ["SpecifyHitAreaLifetimeDirectly", 150], WHIRLWIND_HITS, 3, 0):
        raise SwimCeltieBalanceError("whirlwind: hit area drifted")
    if attack[1] != area[22] or attack[2] != 255 or attack[8] is not False:
        raise SwimCeltieBalanceError("whirlwind: CreateNormalAttack binding/element/combo-bonus drift")
    if attack[13] != _slv(P13_BEFORE):
        raise SwimCeltieBalanceError(f"whirlwind: p13 preimage drift {attack[13]}")
    attack[13] = _slv(P13_AFTER)
    if detoughness(out) > WHIRLWIND_CAP:
        raise AssertionError(f"whirlwind detoughness {detoughness(out)} > {WHIRLWIND_CAP}")
    return out


# ---------------------------------------------------------------- 门禁


def row_gate_problems(table: str, row: list[str]) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(table, row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, frozenset({WHIRLWIND_KEY}), kind=table)]
    return problems


def dsl_problems(tree) -> list[str]:
    problems = []
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("AMF3 roundtrip mismatch")
    problems += [f"element: {p}" for p in L.action_dsl_element_problems(tree, ELEMENT)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"scope: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    return problems


def capability_set(table: str, rows: list[list[str]]) -> set[str]:
    return {cap for row in rows for cap in L.required_client_capabilities(table, row)}


def _override_present(read: Callable[[str, Any], Any]) -> list[str]:
    present = []
    for key in PANEL_OVERRIDE_KEYS:
        try:
            read("cas", key)
        except KeyError:
            continue
        present.append(key)
    return present


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = {(kind, key): _checked(read, kind, key) for kind, key in BEFORE}
    present = _override_present(read)
    if present:
        raise SwimCeltieBalanceError(f"panel override keys now exist and must be synced: {present}")
    if inputs["cas", WHIRLWIND_KEY] != WHIRLWIND_CAS_ROWS:
        raise SwimCeltieBalanceError("whirlwind panel string drifted")
    ct = whirlwind_row_guard(inputs["ability", A6])
    ability2_before = inputs["ability", A2]
    ability = {A2: ability2_rows(ability2_before), A4: ability4_rows(inputs["ability", A4])}
    leader = leader_rows(inputs["leader", CID], ability2_before)
    tree_before = inputs["dsl", WHIRLWIND_PROGRAM]
    tree = whirlwind_tree(tree_before)

    problems = [f"ability:{key}#{i} {p}" for key, rows in ability.items()
                for i, row in enumerate(rows) for p in row_gate_problems("ability", row)]
    problems += [f"leader_ability:{CID}#{i} {p}" for i, row in enumerate(leader)
                 for p in row_gate_problems("leader_ability", row)]
    problems += [f"dsl:{WHIRLWIND_KEY} {p}" for p in dsl_problems(tree)]
    if problems:
        raise SwimCeltieBalanceError("; ".join(problems))
    new_caps = (capability_set("ability", [r for rows in ability.values() for r in rows])
                | capability_set("leader_ability", leader))
    old_caps = (capability_set("ability", [r for key in (A2, A4) for r in inputs["ability", key]])
                | capability_set("leader_ability", inputs["leader", CID]))
    if (new_caps - old_caps) - set(CAPABILITIES):
        raise SwimCeltieBalanceError(f"revised rows need undeclared client capabilities: {sorted(new_caps - old_caps)}")
    describe = {f"ability:{key}": wf_describe.describe_rows(rows, "ability") for key, rows in ability.items()}
    describe[f"leader_ability:{CID}"] = [wf_describe.describe_line(row, "leader_ability") for row in leader]

    return {
        "ability": ability,
        "leader": {CID: leader},
        "cas": {}, "text": {}, "table": {}, "action": {},
        "dsl": {WHIRLWIND_PROGRAM: tree},
        "server_text": {}, "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 希尔媞「千刃共振」（风，灰服版）",
            "source": "wf_balance_20260927c_swimceltie.py",
            "basis": ["作者：灰服版替换后「一并纳入调整」；成长砍到 4/5 或 7/10、可以 2/3、数值取 5 的倍数",
                      "scratchpad/gray3_results.json 最后一版 rules 结果（149996 行）",
                      "第二批施工口径 A3（移入队长写法）、B3（629 CT≤3 秒每次 ≤1）、B4（眩晕积蓄自身 ≤100%）、B6；"
                      "第三轮口径 D3（不新增共鸣前置）"],
            "changes": {
                f"ability:{A4}#0": "每 77 连击自身眩晕积蓄 +25%（限 101，理论 +2525%）→ +10%（限 10，合计 100%）：c34 101→10、c51/c52 25000→10000",
                f"ability:{A2}#0-#2": "每 77 连击全队(风) 攻击/直击/技能伤害 +12.5%（限 101）→ 各 +10%（限 10，各合计 +100%）：c34 101→10、c51/c52 12500→10000",
                f"leader_ability:{CID}#0/#1": "每 77 连击自身攻击/直击 +12.5% → +10%（×4/5，限 101 保留）：c49/c50 12500→10000",
                f"leader_ability:{CID}#5-#7（新增）": ("= [wind_spgirl_swim_leader, '0', ''] + 能力2改前行[5:]，c49/c50 12500→10000："
                                                      "每 77 连击全队(风) 攻击/直击/技能伤害 +10%（×4/5，限 101）"),
                f"dsl:{WHIRLWIND_KEY}": f"CreateNormalAttack p13 13/24 → 1/24：每次单目标 {WHIRLWIND_HITS}×13/24=13 → {WHIRLWIND_HITS}×1/24=1",
            },
            "tier": ("4/5：队长技除充能外无固定攻击/伤害加成（只靠成长）；灰服删了能力6「施技后连击 +77」，77 连击类触发更慢。"
                     "12.5×4/5=10 恰为 5 的倍数；备选 7/10 档 12.5×0.7=8.75 取 9%（作者要更看重触发频率时）"),
            "not_merged": "队长 #0/#1 目标自身（c46=0），新行目标风队（c46=5 Green）⇒ 目标不同，新起 3 行",
            "precondition": "能力2 原行无前置 ⇒ 新队长行也无前置（口径 A3 前置原样搬；第三轮 D3 不新增共鸣前置）",
            "leader_precedents": {
                "trigger12_kind32_target5_Green": "官方 241004#1 / 341001#2（队长，每 30 连击风队攻击）",
                "kind33_target5_Green": "官方 341005#2（队长，常驻风队直击）；trigger 12 + kind 33 = live 149996#1（本键）",
                "trigger12_kind34_target5": "官方 333001#1（队长，每 30 连击雷队技能伤害）；live 129991#2、159998#1",
                "c0": "新行 c0 = 本键既有 wind_spgirl_swim_leader（先例 wf_balance_20260927c_soriz：soriz_leader）",
            },
            "totals": {
                "as_leader": "前 770 连击：全队(风) 每 77 连击 +20%（能力 10%×10 + 队长 10%），之后每 77 连击 +10%；自身另 +10%/77 连击攻击、直击",
                "not_leader": "能力2 封顶：全队(风) 攻击/直击/技能伤害各 +100%；自身眩晕积蓄 100%",
            },
            "whirlwind": {
                "row": f"ability:{A6}#{A6_WHIRLWIND_ROW}：主位（202）+ 自身施技（trigger 23）+ CT {ct} 帧（1 秒）⇒ 每次削韧 ≤1",
                "detoughness": [detoughness(tree_before), detoughness(tree)],
                "kept": "倍率 0.667×24 段、p14 Fever 点 15/24、敌风耐性 -15%、全队 PF +75%、判定区寿命 150 帧",
            },
            "kept": ("技能连击加成 p8（原生机制，与官方 wind_spgirl 同结构，不封顶）；充能/加槽类（能力1#0/#1、能力6#0、队长 #2–#4）；"
                     "能力3（10 层上限+777 清零）、能力5（限 5 次）、能力6#1 直击判定次数（特色）"),
            "panel": ("无 desc_override_wind_spgirl_swim* 键，能力/队长面板由客户端按行自动生成（auto 面板不新建覆盖文案）；"
                      "技能描述、character_text、旋风文案不含这些数值 ⇒ 不改文案"),
            "describe_after": describe,
            "no_replay_batch2": ("导入后 live 1499964 摘要 == wf_balance_20260927b_swimceltie.BEFORE（0d0e70e8…）：暂存计划不得再出现"
                                 "第二批泳装模块（会把能力4 改成自身直击 +20%×5）；本模块产物发布后它按摘要 fail closed"),
            "generator": ("无 flow 包、无生成器（wf_campus_celtie_data 只建 149989；xierti_swim/build_workspace.py、_patch_kit.py "
                          "为历史脚本，不得重跑；wf_balance_20260927b_gray3 按导入前摘要 fail closed）"),
            "capabilities": [],
            "runtime_verified": False,
        },
    }
