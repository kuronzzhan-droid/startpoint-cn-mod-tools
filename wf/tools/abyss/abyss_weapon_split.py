#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深渊武器觉醒拆分：满额魂珠行 → 本体一半 + 装备强化 1→120 级补另一半（支持持续行）。

纯数据转换，不读 store、不写盘。

来历：拆分规则出自 Codex 未合并工作树
``.worktrees/abyss-weapon-awakening/mod-tools/wf_abyss_weapon_awakening.py`` 的
``split_current_soul``（该工作树只读，不在这里改）。那一版只认瞬发行（``int(c48)``），
遇到持续行（c2=1，强度在 c110/c111，c48 为空）直接报错。这里按同一规则重写并补上持续行：

* 只拆强度规则 ``mode == "scale"`` 的行（含 ``uplift=(1,1)`` 的满额规则）；其余（空强度的旗标行、
  629 InvokeSkill、概率行）只留在本体，不产出强化行——避免次数/概率类效果被重复触发。
* 可拆行两端必须相等且为偶数：本体两端写一半；强化行 = 5 列表头
  ``[槽(0 起的效果序号), learn 1, max_power_level 120, battle_power 0, 0]`` + 本体 c2 起全部列
  （强化表列号 = 魂珠列号 + 3，EquipmentEnhancementAbilityValues 构造函数），
  强度 power1 写 0、first_max 写一半 ⇒ 强化 1 级 0 → 120 级补满。
* 瞬发行强度 = 魂珠 c48/c49 → 强化 c51/c52；持续行 = 魂珠 c110/c111 → 强化 c113/c114
  （AbilitySoulValues.parseAt110 / EquipmentEnhancementAbilityValues.parseAt113）。

对只有瞬发行的武器，本模块输出与 Codex 的 ``split_current_soul`` 逐字节相同
（暂存脚本对 15 把逐把双向核对：未改武器 == Codex 拆分 == live）。
"""
from __future__ import annotations

import csv
import io

import wf_mod_tool as core
import wf_rogue_rewards as rewards

WAB_WIDTH = 126
#: 强化表 = 魂珠表 c2 起整体右移 3 列（前面多出 max_power_level 与 battle_power 两列）。
WAB_COLUMN_OFFSET = 3
WAB_HEADER = ("1", "120", "0", "0")      # learn_level, max_power_level, battle_power p1/fm
#: 魂珠 c2 触发模式 → 强度列对（power1, first_max）。
SOUL_STRENGTH_COLUMNS = {
    "0": rewards.SOUL_INSTANT_CONTENT[3],   # (48, 49)
    "1": rewards.SOUL_DURING_CONTENT[3],    # (110, 111)
}


def _leaf_text(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    raise TypeError(f"orderedmap leaf must be bytes/str, got {type(value).__name__}")


def _rows(value: bytes | str) -> list[list[str]]:
    return [list(row) for row in csv.reader(io.StringIO(_leaf_text(value)))]


def _leaf(rows: list[list[str]], like: bytes | str) -> bytes | str:
    text = core.write_csv_lines(rows)
    return text.encode("utf-8") if isinstance(like, bytes) else text


def _strength_rule(spec, effect) -> rewards.EffectStrengthRule:
    key = (effect.template_id, effect.donor_line, effect.effect_kind)
    try:
        return rewards.EFFECT_STRENGTH_RULES[key]
    except KeyError as exc:
        raise ValueError(f"{spec.id} missing audited strength rule {key!r}") from exc


def strength_columns(row: list[str]) -> tuple[int, int]:
    """魂珠行按 c2 触发模式取强度列对；开幕行(2)没有可拆强度。"""
    try:
        return SOUL_STRENGTH_COLUMNS[row[rewards.SOUL_TRIGGER_MODE_COL]]
    except KeyError as exc:
        raise ValueError(f"trigger mode {row[rewards.SOUL_TRIGGER_MODE_COL]!r} has no strength pair") from exc


def wab_column(soul_column: int) -> int:
    """魂珠列号 → 装备强化表同一字段的列号（c2 起适用）。"""
    if soul_column < 2:
        raise ValueError(f"soul column {soul_column} has no enhancement counterpart")
    return soul_column + WAB_COLUMN_OFFSET


def split_soul_leaf(full_leaf: bytes | str, spec) -> tuple[bytes | str, bytes | str]:
    """满额魂珠叶子 → (本体叶子, 强化叶子)。"""
    full_rows = _rows(full_leaf)
    if len(full_rows) != len(spec.effects):
        raise ValueError(
            f"{spec.id} ability_soul rows {len(full_rows)} != effects {len(spec.effects)}"
        )
    base_rows: list[list[str]] = []
    wab_rows: list[list[str]] = []
    for index, (source, effect) in enumerate(zip(full_rows, spec.effects)):
        if len(source) != rewards.SOUL_ROW_WIDTH:
            raise ValueError(
                f"{spec.id} slot {index + 1} soul width {len(source)} != {rewards.SOUL_ROW_WIDTH}"
            )
        base = list(source)
        if _strength_rule(spec, effect).mode == "scale":
            low_col, high_col = strength_columns(source)
            try:
                low, high = int(source[low_col]), int(source[high_col])
            except ValueError as exc:
                raise ValueError(f"{spec.id} slot {index + 1} strength is not numeric") from exc
            if low != high or low % 2 or high % 2:
                raise ValueError(f"{spec.id} slot {index + 1} cannot split exactly: {low}/{high}")
            half = low // 2
            base[low_col] = base[high_col] = str(half)
            wab = [str(index), *WAB_HEADER, *base[2:]]
            wab[wab_column(low_col)], wab[wab_column(high_col)] = "0", str(half)
            if len(wab) != WAB_WIDTH:
                raise RuntimeError(f"{spec.id} slot {index + 1} WAB width drift")
            wab_rows.append(wab)
        base_rows.append(base)
    if not wab_rows:
        raise ValueError(f"{spec.id} has no numeric effect to awaken")
    return _leaf(base_rows, full_leaf), _leaf(wab_rows, full_leaf)


def full_level_totals(base_leaf: bytes | str, wab_leaf: bytes | str, spec) -> list[int | None]:
    """每个效果槽的「本体 + 强化 120 级」合计（不可拆行 = 本体值；空强度 = None）。"""
    base_rows = _rows(base_leaf)
    wab_by_slot = {int(row[0]): row for row in _rows(wab_leaf)}
    totals: list[int | None] = []
    for index, (row, _effect) in enumerate(zip(base_rows, spec.effects)):
        low_col, high_col = strength_columns(row)
        raw = row[high_col].strip()
        base_value = int(raw) if raw else None
        wab = wab_by_slot.get(index)
        if wab is None:
            totals.append(base_value)
            continue
        totals.append((base_value or 0) + int(wab[wab_column(high_col)]))
    return totals
