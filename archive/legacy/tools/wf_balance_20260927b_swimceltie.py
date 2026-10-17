# -*- coding: utf-8 -*-
"""希尔媞「千刃共振」149996 ``wind_spgirl_swim``：2026-09-27 平衡调整第二批——删眩晕蓄积成长。

依据：``${WF_ROOT}/out/平衡调整批次-20260927/batch2/第二批施工口径.md`` B4（作者已拍板）：
「希尔媞「千刃共振」149996 A4 行1（每 77 连击眩晕蓄积 +25%，最多 101 次）→ 删除，换成
「每 77 连击自身直击 +20%，最多 5 次」（官方先例 brown_fighter 1210011 **行2**）」；
设计稿 ``growth/down_design.json`` id=149996 与复核 R1（先例行号更正为行2）。按当前 live 1.4.1049 重读。

只改 ``ability:1499964``（能力4，唯一一行）四格，其余列逐字保留：

- c47 51（Stunify 眩晕蓄积）→ 33（Direct 直击伤害）；c48 仍为 0（自身），c49 仍为空（自身不填元素组）；
- c51/c52 25000 → 20000（+20%）；
- c34 限次 101 → 5（合计 +100%）；
- 触发 c27=12 连击、c30/c31=7700000（每 77 连击）、c35=0、c1=true（不限主位）、c2=attack_common 不动。

官方先例 brown_fighter_1 ``1210011#1``（0 基；「行2」，觉醒1 追加）：c27=12 连击、c30/c31=3000000、c34=6、
c47=33、c48=0、c2=attack_common、c51/c52 10000/20000（满级 +20%×6 = +120%）；本行 +20%×5 = +100% 在其内。

面板：本角色没有任何 ``desc_override_wind_spgirl_swim*`` 键，能力4 面板由客户端按行自动生成
（「连击≥77(限5次) → 自身 Direct伤害 20%」），无需写覆盖文案；:func:`revise` 会确认覆盖键仍不存在。

无 flow 包（locator owner=null，口径 D）：``PACKAGES = []``、``PACKAGE_VERSION = {}``，暂存走 BarePlan。
无生成器：locator 登记的 ``wf_campus_celtie_data.py`` 只构建 149989（CID 常量），149996 仅出现在
``source_notes()['excluded_local_variant']``，不会重写本键。locator 列出的历史副本
``work/character_packs/xierti_swim/build_workspace.py:437`` 与 ``_patch_kit.py:155`` 仍把能力4 建成
``ab_instant(4, 'attack_common', TRIG_COMBO, c_self(51, 50000))``（自身眩晕蓄积 50%）——它们不归 flow 管、
早已与 live 不一致（live 改前是 25%、限 101），不是同步对象；**不得重跑**，否则会把本批删掉的眩晕蓄积带回来。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn，不发布，不 git。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

import wf_client_legality as L

CID = "149996"
CODE = "wind_spgirl_swim"
PACKAGES: list[str] = []
PACKAGE_VERSION: dict[str, str] = {}
CAPABILITIES: list[str] = []
REVIEWED_DRIFT: dict = {}

ELEMENT = 3                          # 内部元素：风
ABILITY_KEY = CID + "4"
ABILITY_NCOLS = 126
PANEL_OVERRIDE_KEYS = tuple(f"desc_override_{CODE}" + suffix
                            for suffix in ("", "_1", "_2", "_3", "_4", "_5", "_6"))

#: 改前唯一一行的逐格指纹（全部非空列；其余列必须为空）。
BEFORE_CELLS: dict[int, str] = {
    0: CODE + "_4", 1: "true", 2: "attack_common", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    27: "12", 30: "7700000", 31: "7700000", 34: "101", 35: "0", 39: "(None)", 46: "0",
    47: "51", 48: "0", 51: "25000", 52: "25000",
}
CHANGED: dict[int, tuple[str, str]] = {
    34: ("101", "5"),                # 限次
    47: ("51", "33"),                # Stunify → Direct 伤害
    51: ("25000", "20000"),          # 低级
    52: ("25000", "20000"),          # 满级
}
AFTER_CELLS: dict[int, str] = {**BEFORE_CELLS, **{col: new for col, (_old, new) in CHANGED.items()}}
#: 官方先例 brown_fighter 1210011#1（0 基）的关键格，测试里与 .cdn 官方基线逐字核对。
PRECEDENT = {"key": "1210011", "row": 1,
             "cells": {0: "brown_fighter_1", 2: "attack_common", 27: "12", 30: "3000000",
                       31: "3000000", 34: "6", 47: "33", 48: "0", 51: "10000", 52: "20000"}}
#: 同角色能力2 #1：每 77 连击全队直击 +12.5%（限 101 次）——与本行一起看直击总量（复核 R1），本批不动。
PEER_DIRECT = {"key": CID + "2", "row": 1, "cells": {27: "12", 30: "7700000", 34: "101", 47: "33",
                                                      48: "5", 51: "12500", 52: "12500"}}

#: live 输入基线（2026-09-27 本地链尾 1.4.1049 只读取数）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "0d0e70e8f7c1f5b6453f536f84ab999f19c73f30d6d589c373d234e767547a8e",
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


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == ABILITY_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def ability4_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力4 唯一一行：每 77 连击自身眩晕蓄积 +25%（限 101）→ 自身直击 +20%（限 5）。"""
    if len(rows) != 1:
        raise SwimCeltieBalanceError(f"ability {ABILITY_KEY}: expected 1 record, got {len(rows)}")
    if not _matches(rows[0], BEFORE_CELLS):
        raise SwimCeltieBalanceError(f"ability {ABILITY_KEY}#0: combo Stunify row "
                                     "(T12 77, limit 101, I51 25%) not found")
    out = deepcopy(rows)
    for col, (_old, new) in CHANGED.items():
        out[0][col] = new
    if not _matches(out[0], AFTER_CELLS):
        raise AssertionError("ability4_rows touched more than c34/c47/c51/c52")
    return out


def row_gate_problems(row: list[str]) -> list[str]:
    problems = [f"legality: {p}" for p in L.client_legality_problems("ability", row)]
    problems += [f"declared: {p}" for p in L.declared_block_field_problems("ability", row)]
    problems += [f"element: {p}" for p in L.ability_element_column_problems("ability", row, ELEMENT)]
    problems += [f"invoke: {p}" for p in L.invoke_skill_string_problems(row, frozenset(), kind="ability")]
    caps = L.required_client_capabilities("ability", row)
    if sorted(caps) != sorted(CAPABILITIES):
        problems.append(f"capabilities {caps} != {CAPABILITIES}")
    return problems


def _override_absent(read: Callable[[str, Any], Any]) -> list[str]:
    present = []
    for key in PANEL_OVERRIDE_KEYS:
        try:
            read("cas", key)
        except KeyError:
            continue
        present.append(key)
    return present


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    ability = _checked(read, "ability", ABILITY_KEY)
    present = _override_absent(read)
    if present:
        raise SwimCeltieBalanceError(f"panel override keys now exist and must be synced: {present}")
    rows = ability4_rows(ability)
    problems = row_gate_problems(rows[0])
    if problems:
        raise SwimCeltieBalanceError(f"ability {ABILITY_KEY}#0 rejected: {problems}")
    return {
        "ability": {ABILITY_KEY: rows},
        "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {}, "server_text": {},
        "new_programs": [],
        "notes": {
            "character": f"{CID} {CODE} 希尔媞「千刃共振」（风）",
            "source": "wf_balance_20260927b_swimceltie.py",
            "basis": ["第二批施工口径 B4（作者 2026-09-27 拍板）", "down_design.json id=149996 + 复核 R1"],
            "change": {f"ability:{ABILITY_KEY}#0 c{col}": f"{old} → {new}" for col, (old, new) in CHANGED.items()},
            "meaning": "每 77 连击：自身眩晕蓄积 +25%（最多 101 次，理论 +2525%）→ 自身直击伤害 +20%（最多 5 次，合计 +100%）",
            "kept": {f"ability:{ABILITY_KEY}#0": "c27=12、c30/c31=7700000、c35=0、c1=true、c2=attack_common、c48=0"},
            "precedent": "官方 brown_fighter 1210011#1（行2，觉醒1追加）：每 30 连击自身 Direct 10%→20%，限 6 次（+120%）",
            "panel": "无 desc_override_wind_spgirl_swim* 键，能力4 面板由客户端按行自动生成，无需同步",
            "generator": ("无（wf_campus_celtie_data.py 只构建 149989，不会重写本键）。历史副本 "
                          "work/character_packs/xierti_swim/build_workspace.py:437、_patch_kit.py:155 仍写 "
                          "ab_instant(4,'attack_common',TRIG_COMBO,c_self(51,50000))（自身眩晕蓄积）：非 flow 包、"
                          "与 live 早已不一致，不是同步对象，不得重跑，否则会带回已删的眩晕蓄积"),
            "direct_total": {
                "this_row": "自身直击 +20%×5 = +100%（385 连击封顶）",
                "ability2_row1": "全队直击 +12.5%/77 连击，限 101 次（本批不动）",
                "leader_rows": "队长 #1 自身直击、#3 全队直击各 +12.5%/77 连击，限 101 次（本批不动）",
                "note": "新增量有上限、低于官方 ★5 先例 +120%；与既有 101 次行合看，前 385 连击自身直击多 +100%",
            },
            "flag_for_author": ("能力2 三行与队长 4 行都是「每 77 连击 +12.5%，限 101 次」的永久成长（理论各 +1262.5%）。"
                                "第二批方案表一把本角色列为「只有追加连击…」未改；口径 A1 以「限次为空或层上限 ≥99」"
                                "判定无上限、以「限次 ≤20」判定有上限，限 101 落在两者之间。本单元按作用域不动，"
                                "是否纳入成长批请作者裁决。"),
            "runtime_verified": False,
        },
    }
