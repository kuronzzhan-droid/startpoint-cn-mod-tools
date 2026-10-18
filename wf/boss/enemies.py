"""Resolve explicit zone enemy slots and the level band selected at runtime."""
from __future__ import annotations

from . import schema as s
from .links import record

# ZoneValues' BossKind discriminants; dedicated native bosses have their own
# master layouts. ConcertedBoss delegates to GeneralBoss in ZoneSourceValues.
BOSS_TABLES = {"0": "standard_boss", "1": "general_boss", "2": "kraken", "3": "orochi",
               "4": "orochi_ex", "5": "orochi_ex_head", "6": "conductor", "7": "touyakiren_ceo",
               "8": "general_boss", "9": "water_sphere", "10": "holy_sphere",
               "11": "wind_sphere", "12": "thunder_sphere", "13": "fire_sphere"}
POSITION_COLUMNS = {"1": 41, "4": 26, "8": 41, "9": 37, "10": 37, "11": 38, "12": 39, "13": 38}


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
    if kind != "zako" and kind not in BOSS_TABLES:
        return {"kind": "boss", "native_kind": kind, "code": code, "level": level,
                "mode": mode, "wave": wave, "slot": slot, "missing": None,
                "position_name": None, "row": [], "source": zone["source"],
                "limitation": "此原生 boss 类型没有已核对的主表映射"}
    logical = s.GENERAL_ZAKO if kind == "zako" else f"master/battle/boss/{BOSS_TABLES[kind]}.orderedmap"
    path = _level_path(tables.table(logical), code, level)
    data = record(tables, logical, path) if path else None
    row = data["row"] if data else []
    result = {"kind": "zako" if kind == "zako" else "boss", "native_kind": kind,
              "code": code, "level": level, "mode": mode, "wave": wave, "slot": slot,
              "table": logical, "path": path, "row": row,
              "source": data["source"] if data else tables.citation(logical),
              "zone_source": zone["source"], "zone_column": column,
              "missing": data is None, "element": s.cell(row, 0) if kind != "0" else None,
              "name": s.cell(row, 0 if kind == "0" else 1),
              "position_name": s.cell(row, POSITION_COLUMNS[kind]) if kind in POSITION_COLUMNS else None}
    if logical == s.GENERAL_BOSS:
        result["boss_level"] = record(tables, s.BOSS_LEVEL, [code])
    return result
