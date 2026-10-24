# -*- coding: utf-8 -*-
"""GBF 双人 2026-09-27 平衡调整第二批：索利兹 129986 ``soriz`` / 冈达葛萨 129987 ``ghandagoza``。

口径：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md``（作者已拍板），设计稿
``growth/growth_design.json``（129986 / 129987）、``growth/down_design.json``；live 按 1.4.1049 重读重推。

**索利兹 129986**（候选 ``gbf-soriz-20260919``）

1. 无上限成长（口径 A）：能力3 ``1299863`` #1-#3「三羽乌（固有 12998601，上限 99，永久）每层 → 自身
   攻击力 +100% / 强化弹射伤害 +100% / 独立乘区强化弹射伤害 +3%」，c102 = ``(None)`` 不设上限。
   - 三行按口径 A3 原样搬进队长 ``leader_ability:129986``（行 = ``[队长 c0, '0', ''] + 能力行[5:]``），
     只把每层强度放缓 1/5：20% / 20% / 0.5%（0.6% 按复核 C09 取 0.5%）。队长原 9 行里没有同触发
     （during 134 / 三羽乌）的行 ⇒ 不合并，新起 #9-#11，共 12 行。
   - 能力3 原位换封顶版：c102 → 10（最多计 10 层），每层 15% / 10% / 1%（= 150% / 100% / 10%）。
   - 放缓档：3 分钟触发约 23–27 次（技能 7–9 发、进 Fever 5–6 次、欧根/仁援护 11–12 次），落 15–30 档 ⇒ 1/5。
2. Down（口径 B3）：三棵援护 629（欧根 CT15 秒 / 仁 CT15 秒 / 双人合击每次 Fever 至多 1 次，消耗合击预备）
   ``CreateNormalAttack`` p13 30 → 3。
3. Down（口径 B2）：Fever 特殊 PF（722 覆盖 ``override_soriz_fever_special_lv1-3``）的 Fever 分支
   11 段 + 终结段 p13 5/5/6.25（合计 60/60/75）→ 每级正好顶到 15/20/25：
   lv1 1.25×11 + 1.25、lv2 1.5×11 + 3.5、lv3 2×11 + 3。非 Fever 分支（官方 special 原树副本，15/20/25）不动。
4. 面板：队长第 2 行插入队长侧三羽乌成长；能力3 首行拆为「获得」与「每层」两行并写封顶，且按
   主位限制槽规则每行加 `` <icon id='main'>  ``（整键 c1=false，覆盖串接管后客户端不再自画 Ⓜ）。

**冈达葛萨 129987**（候选 ``gbf-ghandagoza-20260919``）

5. Down（口径 B4 全队 ≤50%）：能力4 ``1299874`` #0 全队(水) 眩晕蓄积（瞬发 51）c51/c52 300000 → 50000；
   面板 ``desc_override_ghandagoza_4`` 第 1 行「＋300%」→「＋50%」。成长（瓦解上限 5 / 背水按当前 HP）不动。

生成器：``wf_gbf_kit_soriz``（CROWS_GROWTH / ASSIST_TOUGHNESS / PF_FEVER_TOUGHNESS、``derive`` 搬行）与
``wf_gbf_kit_ghandagoza``（行与面板读设计稿）；设计镜像 ``design/soriz.json`` / ``design/ghandagoza.json``
由 :func:`sync_mirrors` 幂等同步。测试断言生成器输出 == :func:`revise` 输出。

接口见 ``${WF_ROOT}/out/平衡调整批次-20260927/module_contract.md``（多角色 ``UNITS``）。本模块只读 ``read()``
给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import wf_client_legality as L
import wf_describe
import wf_dsl
import wf_midautumn_kitlib as KL

SOURCE = "wf_balance_20260927b_gbf.py"
MAIN_ICON = " <icon id='main'>  "
ABILITY_NCOLS, LEADER_NCOLS = 126, 124


class GbfBalanceError(ValueError):
    """输入漂移或结构不符：拒绝修订（fail closed）。"""


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _baseline(before: dict, read: Callable[[str, Any], Any]) -> dict:
    """读取并锁定全部输入；任何一项漂移都拒绝。返回深拷贝（不改 ``read`` 的对象）。"""
    inputs = {}
    for (kind, key), want in before.items():
        value = read(kind, key)
        if value is None:
            raise GbfBalanceError(f"unreviewed live baseline for {kind}:{key} (missing)")
        got = digest(value)
        if got != want:
            raise GbfBalanceError(f"unreviewed live baseline for {kind}:{key} ({got} != {want})")
        inputs[kind, key] = deepcopy(value)
    return inputs


def _cells(row: list[str]) -> dict[int, str]:
    return {i: c for i, c in enumerate(row) if c != ""}


def _expect_exact(row: list[str], width: int, cells: dict[int, str], what: str) -> None:
    """逐格指纹：``cells`` 之外的列必须全空。"""
    if len(row) != width or _cells(row) != cells:
        got = _cells(row) if len(row) == width else f"{len(row)} columns"
        raise GbfBalanceError(f"unexpected preimage for {what}: {got}")


def _single_text(rows: list[list[str]], key: str) -> str:
    if len(rows) != 1 or len(rows[0]) != 1:
        raise GbfBalanceError(f"{key}: expected one single-column row")
    return rows[0][0]


def row_problems(table: str, row: list[str], cas_keys, element: int) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems(table, row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems(table, row)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, set(cas_keys), table)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems(table, row, element)]
    return problems


def dsl_problems(tree, element: int) -> list[str]:
    """contract 要求的四道 DSL 门 + AMF3 往返。"""
    problems = [f"element: {p}" for p in L.action_dsl_element_problems(tree, element)]
    problems += [f"subject: {p}" for p in L.action_dsl_subject_binding_problems(tree)]
    problems += [f"lookup: {p}" for p in L.action_dsl_lookup_scope_problems(tree)]
    problems += [f"hit_target: {p}" for p in L.action_dsl_hit_area_target_problems(tree)]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"] != tree:
        problems.append("amf3 roundtrip mismatch")
    return problems


def _commands(node, name: str, out: list | None = None) -> list[list]:
    """深度优先收集 ``["Command", [name, …]]`` 的参数数组（可原地改）。"""
    out = [] if out is None else out
    if isinstance(node, list):
        if (len(node) == 2 and node[0] == "Command" and isinstance(node[1], list)
                and node[1] and node[1][0] == name):
            out.append(node[1])
        for child in node:
            _commands(child, name, out)
    return out


def V(x) -> list[dict]:
    return [{"min": x, "max": x}]


def toughness(cna: list) -> float:
    """CreateNormalAttack 的 p13（削韧）；只认单格 SLv 且 min == max。"""
    cell = cna[13]
    if not (isinstance(cell, list) and len(cell) == 1 and set(cell[0]) == {"min", "max"}
            and cell[0]["min"] == cell[0]["max"]):
        raise GbfBalanceError(f"CreateNormalAttack p13 shape drift: {cell!r}")
    return cell[0]["max"]


# ====================================================================== 索利兹 129986

SORIZ_CID, SORIZ_CODE = "129986", "soriz"
SORIZ_PACKAGE = "gbf-soriz-20260919"
SORIZ_ELEMENT = 1                                 # 水（character c3）
SORIZ_ABILITY3 = SORIZ_CID + "3"
SORIZ_LEADER_C0 = "soriz_leader"
CAS_SORIZ_LEADER = "desc_override_soriz_leader"
CAS_SORIZ_3 = "desc_override_soriz_3"
CROWS = "12998601"                                # 固有「三羽乌」，上限 99
DUO = "12998606"                                  # 固有「合击预备」（双人合击消耗）
AP = "battle/action/skill/action/ability_skill/{0}${0}"
ASSISTS = {name: AP.format(name) for name in ("soriz_assist_eugen", "soriz_assist_jin", "soriz_assist_duo")}
PF_PATH = ("battle/action/power_flip/action/override/"
           "override_soriz_fever_special$override_soriz_fever_special_lv{n}")
PF_PROGRAMS = {n: PF_PATH.format(n=n) for n in (1, 2, 3)}

#: 能力3 #1-#3：(行号, c109 内容 kind, c110 目标, 改前每层, 能力封顶版每层, 队长每层)。1000 = 1%。
CROWS_ROWS = (
    (1, "0", "0", "100000", "15000", "20000"),     # 攻击力 100% → 能力 15%×10 / 队长 20%
    (2, "23", "", "100000", "10000", "20000"),     # 强化弹射伤害 100% → 10%×10 / 20%
    (3, "413", "", "3000", "1000", "500"),         # 独立乘区强化弹射 3% → 1%×10 / 0.5%（C09）
)
CROWS_CAP = "10"
A_LIMIT, A_STRENGTH = 102, (113, 114)             # ability during_trigger.max_count / during_content 强度
L_LIMIT, L_STRENGTH = 100, (111, 112)             # leader 同列 −2
CROWS_COMMON = {0: "soriz_3", 1: "false", 2: "special", 3: "0", 5: "1", 6: "0", 13: "0", 20: "0",
                85: "(None)", 97: "134", 98: "0", 100: "100000", 101: "100000", 104: CROWS, 108: "false"}


def crows_cells(index: int, *, capped: bool) -> dict[int, str]:
    """能力3 #index 的全部非空格（改前 / 改后）。"""
    _i, kind, target, old, new, _leader = CROWS_ROWS[index - 1]
    cells = {**CROWS_COMMON, 109: kind, A_LIMIT: CROWS_CAP if capped else "(None)"}
    if target:
        cells[110] = target
    value = new if capped else old
    cells[A_STRENGTH[0]] = cells[A_STRENGTH[1]] = value
    return cells


def leader_from_ability(row: list[str], leader_c0: str) -> list[str]:
    """口径 A3：``[队长 c0, '0', ''] + 能力行[5:]``（能力 c≥5 → 队长 c−2）。"""
    if len(row) != ABILITY_NCOLS:
        raise GbfBalanceError(f"ability row has {len(row)} columns")
    return [leader_c0, "0", ""] + list(row[5:])


def soriz_ability3(rows: list[list[str]]) -> list[list[str]]:
    """#1-#3 c102 (None)→10、每层强度换封顶版；其余 8 行与本行其余列逐字保留。"""
    if len(rows) != 11 or any(len(r) != ABILITY_NCOLS for r in rows):
        raise GbfBalanceError(f"ability {SORIZ_ABILITY3}: expected 11×126 rows")
    if {r[1] for r in rows} != {"false"}:
        raise GbfBalanceError(f"ability {SORIZ_ABILITY3}: whole key must stay main-only (c1=false)")
    out = deepcopy(rows)
    for index, *_rest in CROWS_ROWS:
        _expect_exact(rows[index], ABILITY_NCOLS, crows_cells(index, capped=False),
                      f"ability {SORIZ_ABILITY3}#{index}")
        new = CROWS_ROWS[index - 1][4]
        out[index][A_LIMIT] = CROWS_CAP
        out[index][A_STRENGTH[0]] = out[index][A_STRENGTH[1]] = new
        _expect_exact(out[index], ABILITY_NCOLS, crows_cells(index, capped=True),
                      f"revised ability {SORIZ_ABILITY3}#{index}")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [1, 2, 3]:
        raise AssertionError("soriz_ability3 touched another record")
    return out


def soriz_leader(rows: list[list[str]], ability3: list[list[str]]) -> list[list[str]]:
    """队长 9 行原样保留，末尾追加三行搬入的三羽乌逐层成长（每层 1/5）。"""
    if len(rows) != 9 or any(len(r) != LEADER_NCOLS for r in rows):
        raise GbfBalanceError(f"leader {SORIZ_CID}: expected 9×124 rows")
    if {r[0] for r in rows} != {SORIZ_LEADER_C0}:
        raise GbfBalanceError(f"leader {SORIZ_CID}: c0 drift {sorted({r[0] for r in rows})}")
    out = deepcopy(rows)
    for index, kind, target, old, _new, per_layer in CROWS_ROWS:
        source = ability3[index]
        _expect_exact(source, ABILITY_NCOLS, crows_cells(index, capped=False),
                      f"ability {SORIZ_ABILITY3}#{index} (move source)")
        moved = leader_from_ability(source, SORIZ_LEADER_C0)
        # 合并规则：同触发（during 134 / 同固有）、同 kind、同目标、同前置、无 CT 的队长行 ⇒ 强度相加。
        same = [i for i, row in enumerate(out)
                if row[3] == "1" and row[4:25] == moved[4:25] and row[95:107] == moved[95:107]
                and row[107:111] == moved[107:111]]
        if same:
            raise GbfBalanceError(f"leader {SORIZ_CID} already has a same-trigger crows row {same}; "
                                  "reviewed baseline expected none (merge would need a new review)")
        if (moved[L_LIMIT], moved[95], moved[102], moved[107], moved[108]) != ("(None)", "134", CROWS, kind, target):
            raise GbfBalanceError(f"moved row #{index} layout drift")
        moved[L_STRENGTH[0]] = moved[L_STRENGTH[1]] = per_layer
        out.append(moved)
    return out


OLD_SORIZ_A3_FIRST = ("进入FEVER时获得1层「三羽乌」，最多99层。每层「三羽乌」使自身攻击力+100%、强化弹射伤害+100%、"
                      "强化弹射伤害额外+3%（独立乘区）。")
NEW_SORIZ_A3_FIRST = ("进入FEVER时获得1层「三羽乌」，最多99层。",
                      "每层「三羽乌」使自身攻击力+15%、强化弹射伤害+10%、强化弹射伤害额外+1%（独立乘区），最多计10层。")
SORIZ_A3_LINES = 4
SORIZ_LEADER_LINES = 7
SORIZ_LEADER_ANCHOR = "水属性角色攻击力+100%，自身强化弹射伤害+100%。"
SORIZ_LEADER_NEW_LINE = "每层「三羽乌」使自身攻击力+20%、强化弹射伤害+20%、强化弹射伤害额外+0.5%（独立乘区）。"


def soriz_a3_text(rows: list[list[str]]) -> list[list[str]]:
    """首行拆成「获得」「每层（封顶）」两行；整键主位 ⇒ 每行加主位图标，其余文字逐字保留。"""
    lines = _single_text(rows, CAS_SORIZ_3).split("\n")
    if len(lines) != SORIZ_A3_LINES or lines[0] != OLD_SORIZ_A3_FIRST:
        raise GbfBalanceError(f"{CAS_SORIZ_3}: unexpected panel text layout")
    if any("<icon id='main'>" in line for line in lines):
        raise GbfBalanceError(f"{CAS_SORIZ_3}: main icon already present (re-run?)")
    new = [*NEW_SORIZ_A3_FIRST, *lines[1:]]
    return [["\n".join(MAIN_ICON + line for line in new)]]


def soriz_leader_text(rows: list[list[str]]) -> list[list[str]]:
    """第 2 行插入队长侧三羽乌逐层成长；「无上限就写到效果为止」，不写上限/可无限。"""
    lines = _single_text(rows, CAS_SORIZ_LEADER).split("\n")
    if len(lines) != SORIZ_LEADER_LINES or lines[0] != SORIZ_LEADER_ANCHOR or "三羽乌" in "".join(lines):
        raise GbfBalanceError(f"{CAS_SORIZ_LEADER}: unexpected panel text layout")
    return [["\n".join([lines[0], SORIZ_LEADER_NEW_LINE, *lines[1:]])]]


#: 援护 629 的 p13：改前 → 改后；CT 核对见 notes（欧根/仁 c35=900 帧=15 秒；合击消耗合击预备，每次 Fever ≤1 次）。
ASSIST_TOUGHNESS = (30, 3)
#: Fever 特殊 PF 分支 p13：lv → ((改前 每段, 终结), (改后 每段, 终结))；段数 11 + 1。
PF_TOUGHNESS = {1: ((5, 5), (1.25, 1.25)), 2: ((5, 5), (1.5, 3.5)), 3: ((6.25, 6.25), (2, 3))}
PF_CAP = {1: 15, 2: 20, 3: 25}
PF_HITS = (11, 1)
#: 非 Fever 分支（官方 special_lvN 原树副本）的段数与 p13，只核对不改。
PF_NORMAL = {1: ((2, 1), (5, 5)), 2: ((3, 1), (5, 5)), 3: ((3, 1), (6.25, 6.25))}


def _hits(area: list) -> int:
    kind, count = area[14]
    if kind != "CalculatedUsingMaxNumOfHits":
        raise GbfBalanceError(f"hit count kind drift: {area[14]!r}")
    return count


def pf_toughness_total(branch) -> float:
    """分支内每个判定区 段数 × p13 之和（单目标每次 PF 的削韧上界）。"""
    total = 0
    for area in _commands(branch, "CreateHitArea"):
        attacks = _commands(area, "CreateNormalAttack")
        total += _hits(area) * sum(toughness(a) for a in attacks)
    return total


def revise_assist(tree, name: str) -> list:
    """援护树唯一一个 CreateNormalAttack 的 p13 30→3；其余节点逐字保留。"""
    out = deepcopy(tree)
    if out[:10] != ["ActionDsl", 1, ["None"], *[False] * 7] or out[10] != 3:
        raise GbfBalanceError(f"{name}: root header drift (expected PF-attributed 629 tree)")
    areas = _commands(out, "CreateHitArea")
    attacks = _commands(out, "CreateNormalAttack")
    if len(areas) != 1 or _hits(areas[0]) != 1 or len(attacks) != 1:
        raise GbfBalanceError(f"{name}: expected one single-hit area with one CreateNormalAttack")
    old, new = ASSIST_TOUGHNESS
    if toughness(attacks[0]) != old:
        raise GbfBalanceError(f"{name}: p13 preimage {toughness(attacks[0])} != {old}")
    attacks[0][13] = V(new)
    return out


def _fever_node(tree, level: int) -> list:
    top = tree[11]
    if not (isinstance(top, list) and top[0] == "Block" and len(top[1]) == 1
            and top[1][0][0] == "Command" and top[1][0][1][0] == "ConditionalsFeverMode"):
        raise GbfBalanceError(f"PF lv{level}: top block is not a single ConditionalsFeverMode")
    return top[1][0][1]


def revise_pf(tree, level: int) -> list:
    """Fever 分支 11 段 + 终结段的 p13 → PF_TOUGHNESS；非 Fever 分支与其余节点逐字保留。"""
    out = deepcopy(tree)
    node = _fever_node(out, level)
    fever, normal = node[1], node[2]
    areas = _commands(fever, "CreateHitArea")
    if tuple(_hits(a) for a in areas) != PF_HITS:
        raise GbfBalanceError(f"PF lv{level}: fever hit counts {[_hits(a) for a in areas]} != {PF_HITS}")
    attacks = [_commands(a, "CreateNormalAttack") for a in areas]
    if [len(a) for a in attacks] != [1, 1]:
        raise GbfBalanceError(f"PF lv{level}: expected one CreateNormalAttack per fever hit area")
    (old_seg, old_fin), (new_seg, new_fin) = PF_TOUGHNESS[level]
    if (toughness(attacks[0][0]), toughness(attacks[1][0])) != (old_seg, old_fin):
        raise GbfBalanceError(f"PF lv{level}: p13 preimage drift")
    hits, values = PF_NORMAL[level]
    normal_areas = _commands(normal, "CreateHitArea")
    if (tuple(_hits(a) for a in normal_areas) != hits
            or tuple(toughness(c) for a in normal_areas for c in _commands(a, "CreateNormalAttack")) != values):
        raise GbfBalanceError(f"PF lv{level}: non-fever (official special) branch drift")
    if len(_commands(out, "CreateNormalAttack")) != 4:
        raise GbfBalanceError(f"PF lv{level}: unexpected extra CreateNormalAttack")
    attacks[0][0][13] = V(new_seg)
    attacks[1][0][13] = V(new_fin)
    if pf_toughness_total(fever) != PF_CAP[level]:
        raise AssertionError(f"PF lv{level}: fever toughness {pf_toughness_total(fever)} != {PF_CAP[level]}")
    return out


SORIZ_BEFORE: dict[tuple[str, str], str] = {
    ("ability", SORIZ_ABILITY3): "58dd9f7da9dcb326e7c2fc88cb39d446a1faa7874e1196ccbc2e0a7a64c6d20b",
    ("leader", SORIZ_CID): "bf4b1a76532217c8765e70e10060ba3f9489bc612e9b626a74c2fdc2aaece1b0",
    ("cas", CAS_SORIZ_LEADER): "fa893ffac7e97321e10b20117f1f5f4310f29d0209ce2ea17f9fd98c18a2a21f",
    ("cas", CAS_SORIZ_3): "aabc3efeba873838c239362eb067b6157b7eeca258ec8aa7721c7bfcbe4423b8",
    ("dsl", ASSISTS["soriz_assist_eugen"]): "7445caadbfb51cbd89eb5877db18d105a98bc888c3736023aeeb60b4bc8542e8",
    ("dsl", ASSISTS["soriz_assist_jin"]): "e486f6b6289bd5bfb349e9cfb8a0e8e8374664412d16a72cf39553684251872b",
    ("dsl", ASSISTS["soriz_assist_duo"]): "25aa84fbc8010344e2003ee2329629fa9c0c5e4cfa23fbde3423a5c0c44c7409",
    ("dsl", PF_PROGRAMS[1]): "ec6435b408c207a06e0b3e554393fcf37b92f32e60030b183a82fc73b6cee472",
    ("dsl", PF_PROGRAMS[2]): "5acc18f43a5b0e09477801e967a324b70ee404d8d1815d057eacce0551051019",
    ("dsl", PF_PROGRAMS[3]): "91f4f13b5d5adcf063a4ba60e88317c7985c7a12da59fd07d7220e0885815911",
    # 只读：输出里 629 行引用的 string_id（invoke_skill_string 门禁要求 live 有同键行），不改。
    ("cas", "soriz_fever_begin"): "1694a757ffb53648199fde97b84aa5edaf623457483cc6316f8452381528ceb3",
    ("cas", "soriz_fever_end"): "9c9dc284f7dd3fa28e514bfd8ae306fbc5af775610822b4516c7a9ebec2f3944",
    ("cas", "soriz_assist_eugen"): "e3b92cb8262cbcdaae75dc7db7ca992c4d5e955a7d16346df9f52aa1297f0ca3",
    ("cas", "soriz_assist_jin"): "0a56893853c77a3c383cc69f34ce3cb6a40bdee7c8244b67020d62a9c7bbfe37",
    ("cas", "soriz_assist_duo"): "8a2e94bc1a4e2af7e970e7ce5f6d83a8093e44f99e463df760528570c30ebaf5",
}
#: 629 行 string_id 的只读输入（存在性由 BEFORE 锁定）。
SORIZ_INVOKE_STRINGS = ("soriz_fever_begin", "soriz_fever_end", "soriz_assist_eugen", "soriz_assist_jin",
                        "soriz_assist_duo")

#: 能力3 里调用援护的 629 行（只核对 CT 与门，不改）：行号 → (c27 触发, c35 CT 帧, 程序名)。
SORIZ_ASSIST_ROWS = {4: ("2", "900", "soriz_assist_eugen"), 5: ("2", "900", "soriz_assist_jin"),
                     6: ("65", "0", "soriz_assist_duo")}


def _check_assist_rows(ability3: list[list[str]]) -> dict:
    """口径 B3「按当前 live 的实际触发 CT 核对」：欧根/仁 CT 900 帧 = 15 秒；合击 CT 0 但前置 187
    持有「合击预备」且 precontent 消耗 1 层（该层只在进 Fever 时由余热≥5 给 1 层，Fever 结束删除）。"""
    for index, (trigger, ct, name) in SORIZ_ASSIST_ROWS.items():
        row = ability3[index]
        if (row[27], row[35], row[47], row[70]) != (trigger, ct, "629", name):
            raise GbfBalanceError(f"ability {SORIZ_ABILITY3}#{index}: assist gate drift")
    duo = ability3[6]
    # 前置2 = 187 持有合击预备（c13/c19）；instant_precontent = 2 消耗 1 层合击预备（c39/c42/c45）。
    if (duo[13], duo[19], duo[39], duo[42], duo[45]) != ("187", DUO, "2", "100000", DUO):
        raise GbfBalanceError("duo assist is no longer gated by consuming 合击预备")
    return {name: {"trigger": trigger, "cooltime_frames": int(ct), "cooltime_seconds": int(ct) / 60}
            for trigger, ct, name in SORIZ_ASSIST_ROWS.values()}


def revise_soriz(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(SORIZ_BEFORE, read)
    ability_in = inputs["ability", SORIZ_ABILITY3]
    assist_ct = _check_assist_rows(ability_in)
    ability3 = soriz_ability3(ability_in)
    leader = soriz_leader(inputs["leader", SORIZ_CID], ability_in)
    cas = {CAS_SORIZ_LEADER: soriz_leader_text(inputs["cas", CAS_SORIZ_LEADER]),
           CAS_SORIZ_3: soriz_a3_text(inputs["cas", CAS_SORIZ_3])}
    dsl = {path: revise_assist(inputs["dsl", path], name) for name, path in ASSISTS.items()}
    dsl.update({path: revise_pf(inputs["dsl", path], level) for level, path in PF_PROGRAMS.items()})

    strings = {key for key in SORIZ_INVOKE_STRINGS if _single_text(inputs["cas", key], key)} | set(cas)
    problems = [f"ability {SORIZ_ABILITY3}#{i}: {p}" for i, row in enumerate(ability3)
                for p in row_problems("ability", row, strings, SORIZ_ELEMENT)]
    problems += [f"leader {SORIZ_CID}#{i}: {p}" for i, row in enumerate(leader)
                 for p in row_problems("leader_ability", row, strings, SORIZ_ELEMENT)]
    problems += [f"dsl {path}: {p}" for path, tree in dsl.items() for p in dsl_problems(tree, SORIZ_ELEMENT)]
    problems += [f"cas {key}: {p}" for key, rows in cas.items() for p in KL.panel_problems(rows[0][0])]
    if any(not line.startswith(MAIN_ICON) for line in cas[CAS_SORIZ_3][0][0].split("\n")):
        problems.append(f"cas {CAS_SORIZ_3}: main-only slot line without main icon")
    if problems:
        raise GbfBalanceError("; ".join(problems))

    before_pf = {level: float(pf_toughness_total(_fever_node(inputs["dsl", path], level)[1]))
                 for level, path in PF_PROGRAMS.items()}
    after_pf = {level: float(pf_toughness_total(_fever_node(dsl[path], level)[1]))
                for level, path in PF_PROGRAMS.items()}
    return {
        "ability": {SORIZ_ABILITY3: ability3},
        "leader": {SORIZ_CID: leader},
        "cas": cas,
        "text": {}, "table": {}, "action": {}, "server_text": {},
        "dsl": dsl,
        "new_programs": [],
        "notes": {
            "source": SOURCE, "character": f"{SORIZ_CID} {SORIZ_CODE} 索利兹「汉气Ultimatum」（水）",
            "spec": "第二批施工口径 A（无上限成长搬队长 + 能力封顶版）、B2（PF 每级 ≤15/20/25 顶格）、B3（629 每次 ≤3）",
            "growth": {
                "moved_to_leader": {f"leader_ability:{SORIZ_CID}#{8 + i}": f"during134 三羽乌每层 kind {k} "
                                    f"{int(o) / 1000:g}% → {int(p) / 1000:g}%（1/5）"
                                    for i, k, _t, o, _n, p in CROWS_ROWS},
                "capped_in_ability": {f"ability:{SORIZ_ABILITY3}#{i}": f"kind {k} 每层 {int(o) / 1000:g}% → "
                                      f"{int(n) / 1000:g}%，c102 (None)→{CROWS_CAP}"
                                      for i, k, _t, o, n, _p in CROWS_ROWS},
                "merge": "队长原 9 行无 during 134 / 三羽乌 行 ⇒ 新起 #9-#11（共 12 行，复核 C14 不必压行）",
                "rate": "1/5：3 分钟约 23–27 次触发（技能 550 能量约 20–25 秒一发 7–9 次、进 Fever 5–6 次、"
                        "欧根/仁援护 CT15 秒约 11–12 次），落 15–30 档 ⇒ 1/5。按层数计约 35–45 层（技能一次 +3 层）"
                        "会落 ≥30 档，但口径按触发次数计，且口径 A7 / 复核 C09 已钉 413 取 0.5%（= 3% 的 1/5 取整）",
                "leader_precedent": "队长 during 134：官方 161063/141081/161123/141021（kind 0/2/3）；kind 23 与 413 配 "
                                    "during 134 为 live 自制先例 稻穗 139995 队长 #4 / #9（1.4.804 起在线）",
                "3min_estimate": "约 40 层：攻/PF伤 +4000% → 队长 +800% + 能力 +150%/+100%；PF 独立 +120% → +20% + 10%",
            },
            "down": {
                "assist_629_p13": {name: f"{ASSIST_TOUGHNESS[0]} → {ASSIST_TOUGHNESS[1]}" for name in ASSISTS},
                "assist_cooltime": assist_ct,
                "assist_cooltime_rule": "欧根/仁 CT 15 秒、合击每次 Fever ≤1 次（消耗合击预备），均 >3 秒 ⇒ 每次上限 3",
                "fever_special_pf_total": {f"lv{lv}": [before_pf[lv], after_pf[lv]] for lv in PF_PROGRAMS},
                "fever_special_pf_p13": {f"lv{lv}": f"11×{PF_TOUGHNESS[lv][1][0]:g} + {PF_TOUGHNESS[lv][1][1]:g}"
                                         for lv in PF_PROGRAMS},
                "non_fever_branch": "官方 special_lv1-3 原树副本 15/20/25，不动",
                "skill": "技能 soriz_1/_2 单段 30 保留（≤30）",
                "dsl_gates": "只改 CreateNormalAttack p13（SLv 单格 {min,max} 同改），四道门禁 + AMF3 往返为空；"
                             "hibiki kit 严格门的 duplicate bound subject ids（欧根树 / 722 覆盖树 Fever 与非 Fever "
                             "互斥分支各带一份官方原树）改前即有、改后逐字相同，非本批引入",
            },
            "panel": {
                CAS_SORIZ_LEADER: f"第2行插入「{SORIZ_LEADER_NEW_LINE}」",
                CAS_SORIZ_3: "首行拆为两行并写「最多计10层」；整键 c1=false ⇒ 每行加主位图标（原串缺图标）",
            },
            "generator": "wf_gbf_kit_soriz.py（CROWS_GROWTH / ASSIST_TOUGHNESS / PF_FEVER_TOUGHNESS / "
                         "Composer.derive）+ design/soriz.json（sync_mirrors）",
            "capabilities": [],
            "open_points": [
                "队长 12 行超过官方 ≤11 惯例（非技术上限）；413 进队长仅 live 自制先例（稻穗），需真机打开角色页/队长页",
                "Fever 特殊 PF 与援护削韧改动需在 Fever 中打 PF 真机验收",
            ],
            "runtime_verified": False,
        },
    }


# ====================================================================== 冈达葛萨 129987

GHAND_CID, GHAND_CODE = "129987", "ghandagoza"
GHAND_PACKAGE = "gbf-ghandagoza-20260919"
GHAND_ELEMENT = 1
GHAND_ABILITY4 = GHAND_CID + "4"
CAS_GHAND_4 = "desc_override_ghandagoza_4"
GHAND_STUN_ROW = 0
GHAND_STUN_BEFORE = {0: "ghandagoza_4", 1: "true", 2: "attack_common", 3: "0", 5: "0", 6: "0", 13: "0",
                     20: "0", 27: "0", 39: "(None)", 46: "0", 47: "51", 48: "5", 49: "Blue",
                     51: "300000", 52: "300000"}
GHAND_STUN_AFTER = {**GHAND_STUN_BEFORE, 51: "50000", 52: "50000"}
OLD_GHAND_4_LINE = "水属性角色的气绝蓄积＋300%"
NEW_GHAND_4_LINE = "水属性角色的气绝蓄积＋50%"
GHAND_4_LINES = 2

GHAND_BEFORE: dict[tuple[str, str], str] = {
    ("ability", GHAND_ABILITY4): "d5b9825420e1c459e93ff772f875ad07542f646d083fe7ba4afd6700c21072ac",
    ("cas", CAS_GHAND_4): "815bd41c8216ef31232bc2e164d681a49e80cc483511ffbe8c89352a2708ac68",
}


def ghand_ability4(rows: list[list[str]]) -> list[list[str]]:
    if len(rows) != 3 or any(len(r) != ABILITY_NCOLS for r in rows):
        raise GbfBalanceError(f"ability {GHAND_ABILITY4}: expected 3×126 rows")
    _expect_exact(rows[GHAND_STUN_ROW], ABILITY_NCOLS, GHAND_STUN_BEFORE, f"ability {GHAND_ABILITY4}#0")
    out = deepcopy(rows)
    out[GHAND_STUN_ROW][51] = out[GHAND_STUN_ROW][52] = GHAND_STUN_AFTER[51]
    _expect_exact(out[GHAND_STUN_ROW], ABILITY_NCOLS, GHAND_STUN_AFTER, f"revised ability {GHAND_ABILITY4}#0")
    if [i for i, (a, b) in enumerate(zip(rows, out)) if a != b] != [GHAND_STUN_ROW]:
        raise AssertionError("ghand_ability4 touched another record")
    return out


def ghand_text(rows: list[list[str]]) -> list[list[str]]:
    lines = _single_text(rows, CAS_GHAND_4).split("\n")
    if len(lines) != GHAND_4_LINES or lines[0] != OLD_GHAND_4_LINE:
        raise GbfBalanceError(f"{CAS_GHAND_4}: unexpected panel text layout")
    return [["\n".join([NEW_GHAND_4_LINE, *lines[1:]])]]


def revise_ghandagoza(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    inputs = _baseline(GHAND_BEFORE, read)
    ability4 = ghand_ability4(inputs["ability", GHAND_ABILITY4])
    cas = {CAS_GHAND_4: ghand_text(inputs["cas", CAS_GHAND_4])}
    problems = [f"ability {GHAND_ABILITY4}#{i}: {p}" for i, row in enumerate(ability4)
                for p in row_problems("ability", row, set(), GHAND_ELEMENT)]
    problems += [f"cas {key}: {p}" for key, rows in cas.items() for p in KL.panel_problems(rows[0][0])]
    if problems:
        raise GbfBalanceError("; ".join(problems))
    return {
        "ability": {GHAND_ABILITY4: ability4},
        "cas": cas,
        "leader": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "source": SOURCE, "character": f"{GHAND_CID} {GHAND_CODE} 冈达葛萨「破海道」（水）",
            "spec": "第二批施工口径 B4：眩晕蓄积全队 ≤50%",
            "change": {f"ability:{GHAND_ABILITY4}#0 c51/c52": "300000 → 50000（全队(水) 眩晕蓄积 kind 51 300% → 50%）"},
            "kept": {f"ability:{GHAND_ABILITY4}#1-#2": "眩晕畏缩特攻 10% / 麻痹特攻 10% 不动",
                     "growth": "瓦解上限 5 层、背水按当前 HP（可逆）⇒ 不属无上限成长，不动",
                     "charge": "能力1 行3 自身施技队长 +30% 属表二充能规范，本批暂缓不动"},
            "panel": {CAS_GHAND_4: f"第1行 → {NEW_GHAND_4_LINE}（沿用「气绝」用词，与第2行一致）"},
            "generator": "wf_gbf_kit_ghandagoza.py 读 design/ghandagoza.json（sync_mirrors 同步 cells/desc/面板）",
            "capabilities": [],
            "runtime_verified": False,
        },
    }


# ====================================================================== 单元导出

UNITS = [
    dict(CID=SORIZ_CID, CODE=SORIZ_CODE, NAME="索利兹",
         PACKAGES=[SORIZ_PACKAGE], PACKAGE_VERSION={SORIZ_PACKAGE: "1.0.1"},   # 候选现值 1.0.0
         CAPABILITIES=[], REVIEWED_DRIFT={}, BEFORE=SORIZ_BEFORE, revise=revise_soriz),
    dict(CID=GHAND_CID, CODE=GHAND_CODE, NAME="冈达葛萨",
         PACKAGES=[GHAND_PACKAGE], PACKAGE_VERSION={GHAND_PACKAGE: "1.0.1"},   # 候选现值 1.0.0
         CAPABILITIES=[], REVIEWED_DRIFT={}, BEFORE=GHAND_BEFORE, revise=revise_ghandagoza),
]


# ====================================================================== 设计镜像同步

DESIGN_DIR = Path("work/character_packs/midautumn-20260920/design")
SORIZ_DESIGN_REL = DESIGN_DIR / "soriz.json"
GHAND_DESIGN_REL = DESIGN_DIR / "ghandagoza.json"
MIRROR_TAG = "balance_20260927b"


def _row_from_cells(cells: dict, width: int) -> list[str]:
    row = [""] * width
    for col, value in cells.items():
        row[int(col)] = str(value)
    return row


def _describe(cells: dict, table: str) -> str:
    return wf_describe.describe_line(_row_from_cells(cells, ABILITY_NCOLS if table == "ability" else LEADER_NCOLS),
                                     table)


def _leader_record(ability_record: dict, index: int) -> dict:
    """由能力记录（任一状态）推导搬入队长的记录：c≥5 → c−2，c100 (None)，强度 = 队长每层。"""
    _i, kind, _t, _o, _n, per_layer = CROWS_ROWS[index - 1]
    cells = {"0": SORIZ_LEADER_C0, "1": "0"}
    for col, value in ability_record["cells"].items():
        if int(col) >= 5:
            cells[str(int(col) - 2)] = value
    cells[str(L_LIMIT)] = "(None)"
    cells[str(L_STRENGTH[0])] = cells[str(L_STRENGTH[1])] = per_layer
    cells = {str(c): cells[str(c)] for c in sorted(map(int, cells))}
    name = {"0": "攻击力", "23": "PF伤害", "413": "独立乘区PF伤害"}[kind]
    return {"donor": f"move:ability[{SORIZ_ABILITY3}]#{index}", "trigger_donor": "",
            "req": f"L#{8 + index} 每层三羽乌 {name}+{int(per_layer) / 1000:g}%"
                   f"（2026-09-27b 由能力3#{index} 搬入，每层 1/5）",
            "cells": cells, "desc_expected": _describe(cells, "leader_ability"), "index": 8 + index}


def soriz_mirror(design: dict) -> dict:
    design = deepcopy(design)
    plan = design["plan"]
    records = plan["ability"]["keys"][SORIZ_ABILITY3]["records"]
    for index, kind, _t, _o, new, _p in CROWS_ROWS:
        record = records[index]
        cells = {str(c): v for c, v in crows_cells(index, capped=True).items()}
        record["cells"] = {c: cells[c] for c in sorted(cells, key=int)}
        record["desc_expected"] = _describe(record["cells"], "ability")
        name = {"0": "攻击力", "23": "PF伤害", "413": "独立乘区PF伤害"}[kind]
        record["req"] = (f"A3#{index} 每层三羽乌 {name}+{int(new) / 1000:g}%(最多{CROWS_CAP}层)"
                         f"（2026-09-27b 封顶版；无上限部分已搬队长）")
    leader_rows = plan["leader_ability"]["rows"]
    del leader_rows[9:]
    leader_rows.extend(_leader_record(records[index], index) for index, *_rest in CROWS_ROWS)
    texts = plan["texts"]["custom_ability_string"]
    for key, new in ((CAS_SORIZ_LEADER, soriz_leader_text), (CAS_SORIZ_3, soriz_a3_text)):
        current = texts[key]
        if key == CAS_SORIZ_LEADER and "三羽乌" not in current:
            texts[key] = new([[current]])[0][0]
        elif key == CAS_SORIZ_3 and "<icon id='main'>" not in current:
            texts[key] = new([[current]])[0][0]
    pf = plan["power_flip_override"]["fever_branch"]
    pf["削韧"] = ("2026-09-27b：Fever 分支 p13 由官方每段 5/5/6.25（合计 60/60/75）改为 "
                + "、".join(f"lv{lv} 11×{PF_TOUGHNESS[lv][1][0]:g}+{PF_TOUGHNESS[lv][1][1]:g}={PF_CAP[lv]}"
                           for lv in PF_PROGRAMS) + "；非 Fever 分支（官方原树）不动")
    for program in plan["skills"]["programs"]:
        if program.get("name") in ASSISTS:
            program["toughness"] = (f"CreateNormalAttack p13 {ASSIST_TOUGHNESS[0]}→{ASSIST_TOUGHNESS[1]}"
                                    "（2026-09-27b 口径 B3：629 每次 ≤3）")
    design[MIRROR_TAG] = dict(
        spec="第二批施工口径 A/B2/B3（作者 2026-09-27 拍板）",
        growth=[f"能力3#{i} 三羽乌每层 kind {k}：{int(o) / 1000:g}% 不设上限 → 能力 {int(n) / 1000:g}%×最多{CROWS_CAP}层"
                f" + 队长#{8 + i} {int(p) / 1000:g}%/层" for i, k, _t, o, n, p in CROWS_ROWS],
        down=[f"援护 629 ×3 p13 {ASSIST_TOUGHNESS[0]}→{ASSIST_TOUGHNESS[1]}",
              "Fever 特殊 PF 分支 60/60/75 → 15/20/25"],
        panel=[CAS_SORIZ_LEADER, CAS_SORIZ_3],
        module="mod-tools/wf_balance_20260927b_gbf.py",
    )
    return design


def ghand_mirror(design: dict) -> dict:
    design = deepcopy(design)
    plan = design["plan"]
    record = plan["ability"]["keys"][GHAND_ABILITY4]["records"][GHAND_STUN_ROW]
    cells = {str(c): v for c, v in GHAND_STUN_AFTER.items()}
    record["cells"] = {c: cells[c] for c in sorted(cells, key=int)}
    record["desc_expected"] = _describe(record["cells"], "ability")
    record["req"] = "A4-1 水属性角色更容易造成down +50%（2026-09-27b 由 +300% 下调，口径 B4 全队 ≤50%）"
    for row in plan["texts"]["custom_ability_string"]["rows"]:
        if row["key"] == CAS_GHAND_4 and row["text"].split("\n")[0] == OLD_GHAND_4_LINE:
            row["text"] = ghand_text([[row["text"]]])[0][0]
    design[MIRROR_TAG] = dict(
        spec="第二批施工口径 B4（作者 2026-09-27 拍板）：眩晕蓄积全队 ≤50%",
        changed=[f"能力4#0 全队(水) 眩晕蓄积 300% → 50%（c51/c52）", f"{CAS_GHAND_4} 第1行同步"],
        module="mod-tools/wf_balance_20260927b_gbf.py",
    )
    return design


def mirror_updates(soriz: dict, ghand: dict) -> tuple[dict, dict]:
    """两份设计镜像按本批规格重算（纯函数、幂等）。"""
    return soriz_mirror(soriz), ghand_mirror(ghand)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, value: dict) -> None:
    """保持原文件格式：indent=1、CRLF/LF 与末尾换行按原文件。"""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = json.dumps(value, ensure_ascii=False, indent=1)
    if raw.endswith(b"\n"):
        text += "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def sync_mirrors(root: Path, *, write: bool = False) -> list[str]:
    """重算并（``write=True`` 时）写回两份设计镜像；返回有变化的相对路径。"""
    root = Path(root)
    rels = (SORIZ_DESIGN_REL, GHAND_DESIGN_REL)
    before = [_load(root / rel) for rel in rels]
    after = mirror_updates(*before)
    changed = [rel.as_posix() for rel, old, new in zip(rels, before, after) if old != new]
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
