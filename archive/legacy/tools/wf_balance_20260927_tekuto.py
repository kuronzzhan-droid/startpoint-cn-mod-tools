# -*- coding: utf-8 -*-
"""特克托 139993 ``super_robot_tailcoat``：2026-09-27 作者平衡批次——能力6 技能槽充能减半。

唯一改动：``ability:1399936``（能力6，唯一一行，瞬发开场常驻）
全队雷属性技能槽充能速度（kind 35 SkillGaugeCharging，target 5 全队，c49 Yellow）
c51/c52 = 10000/20000 → 5000/10000，即 Lv1 10%→5%、满级 20%→10%，保留 1:2 成长比例。
其余 124 列逐字不动（c1=true 不限主位、c2=special、c27=0 无触发、c49=Yellow）。

取值口径：作者定的是「满级 10%」；低级按原设计 1:2 同比减半。官方瞬发 kind35/target5 共 32 行
全部是 1:2，满级 10% 的 4 行都是 5000/10000；低满相等的官方先例 0 行。

面板：能力6 没有 ``desc_override_super_robot_tailcoat_6``，客户端按当前等级自动生成单值
（wf_describe：「赋予全队(雷) 技能槽充能 5%→10%」），不新增覆盖文案。

生成器 ``wf_seasonal7_kit_tekuto``：plan.json 对 1399936 是 ``no_change``，
``revision_ability_rows`` 原样照抄包内现行行，kit 里没有任何符号编码这两格数值 ⇒ 候选回写后重跑
kit 输出 == :func:`revise` 输出，不需要改生成器代码（测试断言）。

本模块只读 ``read()`` 给的 live 值并返回新值；不写 live store / assets / .cdn / 候选包。
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

CID = "139993"
CODE = "super_robot_tailcoat"
PACKAGES = ["s7-tekuto"]
#: 候选 manifest 现值 1.0.0（发布后修订曾写过 1.0.5/1.0.6/1.0.7，后续工具写回 1.0.0）；
#: 取历史最高 1.0.7 的下一号，对现值与历史都只升不降。
PACKAGE_VERSION = {"s7-tekuto": "1.0.8"}
CAPABILITIES: list[str] = []
#: 候选 144 个 manifest 条目与文件逐一一致（2026-09-27 只读核对），无需声明既有漂移。
REVIEWED_DRIFT: dict = {}

ABILITY_KEY = f"{CID}6"
ABILITY_NCOLS = 126
ELEMENT = 2                        # master/character c3：雷（0 基内部元素）
ELEMENT_TOKEN = "Yellow"
LOW_COL, MAX_COL = 51, 52          # 瞬发内容块数值：c51 = 低级（Lv1），c52 = 满级（Lv6）
OLD_VALUES = ("10000", "20000")    # 10% / 20%（100000 = 100%）
NEW_VALUES = ("5000", "10000")     # 5% / 10%

#: live 输入基线（2026-09-27 本地链尾 1.4.1047 只读取数，与候选 s7-tekuto 逐字相同）。
#: 值 = :func:`digest` (read(kind, key))；不符 ⇒ revise() 拒绝（fail closed）。
#: 该行 CSV 文本 sha256 = d67886a8d17823aaa032876b14a3634c9ca70ae93aad384a82bbb4c3150a2014（调研记录）。
BEFORE: dict[tuple[str, str], str] = {
    ("ability", ABILITY_KEY): "e0cd3d3062d0a443d494e0f56a5a11294f8b1c31a09450b451eed0b2b34f2c61",
}

#: 改前行的逐格指纹（全部非空列；其余列必须为空）。BEFORE 之外的第二道锁，也让纯函数可单测、
#: 且对自身输出重跑必然拒绝（c51/c52 已不是旧值）。
BEFORE_CELLS: dict[int, str] = {
    0: f"{CODE}_6", 1: "true", 2: "special", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0",
    27: "0", 39: "(None)", 46: "0", 47: "35", 48: "5", 49: ELEMENT_TOKEN,
    LOW_COL: OLD_VALUES[0], MAX_COL: OLD_VALUES[1],
}
AFTER_CELLS: dict[int, str] = {**BEFORE_CELLS, LOW_COL: NEW_VALUES[0], MAX_COL: NEW_VALUES[1]}


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


def _matches(row: list[str], cells: dict[int, str]) -> bool:
    return (len(row) == ABILITY_NCOLS
            and all(row[col] == value for col, value in cells.items())
            and all(value == "" for col, value in enumerate(row) if col not in cells))


def ability6_rows(rows: list[list[str]]) -> list[list[str]]:
    """能力6 唯一一行：c51/c52 10000/20000 → 5000/10000；其余列逐字保留。"""
    if len(rows) != 1:
        raise ValueError(f"ability {ABILITY_KEY}: expected exactly one record, got {len(rows)}")
    if not _matches(rows[0], BEFORE_CELLS):
        raise ValueError(f"ability {ABILITY_KEY}: row is not the reviewed kind35 10000/20000 shape")
    out = deepcopy(rows)
    out[0][LOW_COL], out[0][MAX_COL] = NEW_VALUES
    if not _matches(out[0], AFTER_CELLS):            # 自检：只动了这两格
        raise AssertionError("ability6_rows touched more than c51/c52")
    return out


def revise(read: Callable[[str, Any], Any]) -> dict[str, Any]:
    ability = _checked(read, "ability", ABILITY_KEY)
    return {
        "ability": {ABILITY_KEY: ability6_rows(ability)},
        "leader": {}, "cas": {}, "text": {}, "table": {}, "action": {}, "dsl": {},
        "server_text": {}, "new_programs": [],
        "notes": {
            "source": "wf_balance_20260927_tekuto.py",
            "change": {
                f"ability:{ABILITY_KEY}#0 c{LOW_COL}/c{MAX_COL}":
                    f"{'/'.join(OLD_VALUES)} → {'/'.join(NEW_VALUES)}",
                "meaning": "全队雷属性技能槽充能速度（kind35，target5，瞬发常驻）Lv1 10%→5%，满级 20%→10%",
            },
            "growth": "保留 1:2 成长（官方瞬发 kind35/target5 共 32 行全部 1:2；满级 10% 的 4 行均为 5000/10000）",
            "panel": "无 desc_override；客户端按等级自动生成单值（wf_describe：赋予全队(雷) 技能槽充能 5%→10%）",
            "untouched": "其余 124 列、leader_ability、其余能力键、技能/DSL、文案均不变",
            "generator": ("wf_seasonal7_kit_tekuto：plan.json 对 1399936 为 no_change，照抄包内行；"
                          "候选回写后重跑 kit 保留新值，无需改代码"),
            "capabilities": [],
            "runtime_verified": False,
        },
    }
