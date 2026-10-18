"""Resolve explicit zone enemy slots and the level band selected at runtime."""
from __future__ import annotations

from . import schema as s
from .links import record


def _level_path(table, code, level):
    node = table.get(code)
    if isinstance(node, str):
        return [code]
    if not isinstance(node, dict):
        return None
    levels = [int(key) for key in node if key.isdigit()]
    # GeneralEnemySourceHelper.getSurjectivity scans native insertion order.
    target = next((bound for bound in levels if bound >= level), None)
    return [code, str(target)] if target is not None else None


def enemies(tables, zone_rows, quest):
    level_text = quest["fields"]["level"]
    level = int(level_text) if level_text.isdigit() else 0
    found = []
    for zone in zone_rows:
        row, wave = zone["row"], zone["path"][-1]
        for slot in range(3):
            for mode, offset in (("single", 23), ("multi", 25)):
                col = offset + slot * 4
                kind, code = s.cell(row, col), s.cell(row, col + 1)
                if s.present(kind) and s.present(code):
                    found.append(_enemy(tables, kind, code, level, mode, wave, slot + 1, zone, col))
        for slot in range(10):
            col = 2 + slot * 2
            code = s.cell(row, col)
            if s.present(code):
                entry = _enemy(tables, "zako", code, level,
                               "both", wave, slot + 1, zone, col)
                entry["spawn_interval"] = s.cell(row, col + 1)
                entry["level_origin"] = {"source": quest.get("source"),
                                         "column": s.QUEST_COLUMNS[quest["kind"]]["level"]}
                found.append(entry)
    return found


def _enemy(tables, kind, code, level, mode, wave, slot, zone, column):
    # Zone boss kind 0 = standard, 1 = general. Zako has its own table.
    logical = s.GENERAL_ZAKO if kind == "zako" else s.GENERAL_BOSS if kind == "1" else s.STANDARD_BOSS
    path = _level_path(tables.table(logical), code, level)
    data = record(tables, logical, path) if path else None
    row = data["row"] if data else []
    result = {"kind": "zako" if kind == "zako" else "boss", "native_kind": kind,
              "code": code, "level": level, "mode": mode, "wave": wave, "slot": slot,
              "table": logical, "path": path, "row": row,
              "source": data["source"] if data else tables.citation(logical),
              "zone_source": zone["source"], "zone_column": column,
              "missing": data is None, "element": s.cell(row, 0) if kind in ("1", "zako") else None,
              "position_name": s.cell(row, 41) if logical == s.GENERAL_BOSS else None}
    if logical == s.GENERAL_BOSS:
        result["boss_level"] = record(tables, s.BOSS_LEVEL, [code])
    return result
