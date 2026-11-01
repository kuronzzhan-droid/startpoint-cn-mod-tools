"""Known missing combat references are failures, not absent check input."""
from __future__ import annotations

import math

from .boss_common import CandidateView, EMPTY, cell, leaves

GENERAL = "master/battle/boss/general_boss.orderedmap"
STATES = "master/battle/boss/general_boss_state.orderedmap"


def missing_combat_references(document):
    return [f"{key} 引用 {document[key].get('id')!r} 缺失"
            for key in ("field_data", "field", "zone", "terrain")
            if isinstance(document.get(key), dict) and document[key].get("missing") is True]


def routine_positions(document, view):
    """Use the already selected native general_boss band, never another tier."""
    routines, required, issues, pending = {}, {}, [], []
    active = {str(wave.get("name", "0")) for wave in document.get("terrain", {}).get("waves", [])}
    for enemy in document.get("enemies", []):
        if active and str(enemy.get("wave", "0")) not in active:
            continue
        if enemy.get("table") != GENERAL and str(enemy.get("native_kind")) not in {"1", "8"}:
            continue
        routine = cell(enemy, 42)
        key = (str(enemy.get("wave", "0")), enemy.get("code"), routine,
               tuple(enemy.get('path') or ()), tuple(enemy.get('row') or ()))
        routines[key] = enemy
    if not routines:
        return required, issues, pending
    if view is None:
        return required, issues, ["缺少 general_boss_state 候选视图，未核对 routine c50 站位"]
    states = CandidateView(view).table(STATES) or {}
    from wf.boss.behavior_positions import PositionReferences
    actions = PositionReferences(view)
    for (wave, code, routine, _, _), enemy in routines.items():
        node = states.get(routine)
        rows = list(leaves(node))
        if routine not in EMPTY and not rows:
            issues.append(f"层 {wave} 敌人 {code} 档 {enemy.get('path')} 引用缺失 routine {routine}")
        names = set()
        # GeneralBossStateValues.as:1608-1629 reads c50 as a named position
        # only for c49=0 (Absolute). For c49=1 it is the Relative x offset;
        # a numeric offset such as 0 must never become a terrain reference.
        for path, row in rows:
            movement = cell(row, 49)
            if movement in EMPTY:
                continue
            if movement == "0":
                name = str(cell(row, 50, "")).strip()
                if name in EMPTY:
                    issues.append(f"层 {wave} 敌人 {code} 状态 {path} 绝对移动缺少命名站位")
                else:
                    names.add(name)
            elif movement == "1":
                try:
                    valid = all(math.isfinite(float(cell(row, index))) for index in (50, 51))
                except (ValueError, TypeError):
                    valid = False
                if not valid:
                    issues.append(f"层 {wave} 敌人 {code} 状态 {path} 相对移动坐标不是有限数值")
            else:
                issues.append(f"层 {wave} 敌人 {code} 状态 {path} 移动种类 {movement!r} 未知")
        positions, missing = actions.general(enemy)
        names.update(positions)
        # A missing native input cannot establish a missing named position.
        # Keep that distinction visible; selected/borrowed action edits have
        # their own strict closure gates before reaching this terrain check.
        pending.extend(f"层 {wave} 敌人 {code} 站位动作闭包缺失，待验证 {logical}" for logical in missing)
        required.setdefault((wave, code, routine), set()).update(names)
    return required, issues, pending
