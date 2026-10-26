# -*- coding: utf-8 -*-
"""装备强化商店的类目横幅顺序（作者 0928：诅咒武器·觉醒 → 深渊武装·觉醒 → 官方 1–4；0929 起羁绊武器·觉醒插在深渊之后）。

客户端按类目表 ``equipment_enhancement_shop_category`` 的 c1 display_order 升序排横幅
（``ShopProductRepository.as:263-278`` 用 ``Std.parseInt`` 读、``Reflect.compare`` 比，负数合法；
比较没有 id 兜底、AVM2 排序不稳定，所以全表 c1 必须互异）。服务端 ``src/`` 不读这一列。
用负数是为了不碰官方 1–4 行：诅咒 6 → -2、深渊 5 → -1；羁绊 7 → 0（与官方 1–4 互异，排在深渊之后、官方之前）。

每行的 c1 归各自的生成器（诅咒 ``wf_cursed_weapons.ENH_CATEGORY_DISPLAY_ORDER``、深渊
``wf_abyss_weapon_category.DISPLAY_ORDER``、羁绊 ``wf_bond_weapon_enhance.CATEGORY_ORDER``），本模块只把它们对到 live：
``target_rows`` 只改 c1，其余列逐格 = live。羁绊类目 7 由羁绊生成器新增（``OPTIONAL``）：live 里还没有这一行时跳过它，
只校验现有行；发布后它带着 c1 = 0 出现，本模块照常核对。
只读 live，不写 store / .cdn / assets；暂存由调用方按各自的计划合同写（PARADOX 线 ``stage_cat.py``）。

用法::

    python mod-tools/wf_enhancement_category_order.py check     # 只读：live 顺序、目标顺序、将改的键
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_abyss_weapon_category as abyss  # noqa: E402
import wf_bond_weapon_enhance as bond  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402

CATEGORY_LOGICAL = W.ENH_CATEGORY
COLUMNS = 10
ORDER_COL = 1
#: 类目键 → (c0 string_id, 目标 c1)
ORDER = {
    W.ENH_CATEGORY_KEY: ("cursed_weapon", W.ENH_CATEGORY_DISPLAY_ORDER),
    abyss.NEW_KEY: ("abyss_weapon", abyss.DISPLAY_ORDER),
    bond.CATEGORY_KEY: (bond.CATEGORY_C0, bond.CATEGORY_ORDER),
}
#: 由生成器新增、尚未发布时 live 里没有这一行也不算错（缺的键不参与改序，也不进 EXPECTED_SEQUENCE 的比较）
OPTIONAL = frozenset({bond.CATEGORY_KEY})
#: 目标横幅顺序（键）：自制三类在前，官方 1–4 保持原相对顺序
EXPECTED_SEQUENCE = (W.ENH_CATEGORY_KEY, abyss.NEW_KEY, bond.CATEGORY_KEY, "1", "2", "3", "4")
_INT = re.compile(r"-?[0-9]+")


def target_rows(live_rows: dict[str, list[str]]) -> tuple[dict[str, list[str]], list[str]]:
    """live 类目表 {键: 行} -> ({要改的键: 目标行}, problems)。已是目标值的键不出（幂等）。

    本线的两行：c0 须是约定的 string_id，c1 只能是原值（= 键）或目标值——别的值说明有人另改过，拒绝覆盖。
    改后全表 c1 须是整数、互异，且升序恰为 EXPECTED_SEQUENCE。"""
    problems: list[str] = []
    upsert: dict[str, list[str]] = {}
    for key, (string_id, order) in ORDER.items():
        row = live_rows.get(key)
        if row is None and key in OPTIONAL:
            continue
        if not row or len(row) != COLUMNS or row[0] != string_id:
            problems.append(f"类目 {key} 不是 {COLUMNS} 列的 {string_id} 行: {(row or [])[:4]}")
            continue
        if row[ORDER_COL] not in (key, order):
            problems.append(f"类目 {key} c{ORDER_COL}={row[ORDER_COL]!r} 漂移（期望原值 {key} 或目标 {order}）")
            continue
        if row[ORDER_COL] != order:
            upsert[key] = row[:ORDER_COL] + [order] + row[ORDER_COL + 1:]
    staged = {**live_rows, **upsert}
    values = {key: row[ORDER_COL] if len(row) > ORDER_COL else "" for key, row in staged.items()}
    bad = {k: v for k, v in values.items() if not _INT.fullmatch(v)}
    if bad:
        problems.append(f"类目 c{ORDER_COL} 不是整数: {bad}")
        return upsert, problems
    if len(set(map(int, values.values()))) != len(values):
        problems.append(f"类目 c{ORDER_COL} 有重复（客户端排序无兜底，顺序会随机）: {values}")
    sequence = tuple(sorted(values, key=lambda k: int(values[k])))
    expected = tuple(k for k in EXPECTED_SEQUENCE if k in staged)
    if sequence != expected:
        problems.append(f"改后横幅顺序 {sequence} != 目标 {expected}")
    return upsert, problems


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = sys.argv[1:] if argv is None else argv
    if args != ["check"]:
        print(__doc__)
        return 2
    import wf_weapon_gacha as G   # 只在 CLI 里读 live

    live = G.Live().flat(CATEGORY_LOGICAL)
    upsert, problems = target_rows(live)
    staged = {**live, **upsert}
    order = lambda rows: [f"{k}:{rows[k][3]}({rows[k][ORDER_COL]})"  # noqa: E731
                          for k in sorted(rows, key=lambda k: int(rows[k][ORDER_COL]))]
    print(json.dumps({"live": order(live), "target": order(staged), "changed": sorted(upsert), "problems": problems},
                     ensure_ascii=False, indent=1))
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
