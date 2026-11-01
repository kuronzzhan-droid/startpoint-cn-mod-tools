"""Adapt advent encounters to the existing five-state and D3 gates."""
from __future__ import annotations

from types import SimpleNamespace
from . import schema as s
from .provenance import BossTables
from .links import record
from .enemies import enemies
from .terrain import read_terrain
from .scene_import import AQ
from wf.rules.boss import check_boss
from wf.rules.multiplayer import MultiplayerScanner
from wf.rules.catalog import result

COLS = {"name": 2, "start_time": 5, "end_time": 6, "stamina": 75,
        "score_reward": 76, "recommended_element": 78, "hp_boss": 105,
        "attack_boss": 108, "level": 112, "rank": 113, "field_data": 115,
        "bgm": 116, "time_limit": 117}


def encounter(source, event, tier):
    tables = BossTables(source)
    path = [event, tier]
    text = s.get_leaf(tables.table(AQ), path)
    if text is None:
        raise ValueError("缺少活动五档行：" + "/".join(path))
    row = s.parse_rows(text)[0]
    quest = {"id": row[0], "selector": "advent_event:" + "/".join(path), "kind": "advent_event",
             "table": AQ, "path": path, "row": row, "fields": {k: s.cell(row, i) for k, i in COLS.items()}}
    fd_id = quest["fields"]["field_data"]
    fd = record(tables, s.FIELD_DATA, [fd_id])
    fdrow = (fd or {}).get("row", [])
    field_id, terrain_id, zone_id = (s.cell(fdrow, i) for i in range(3))
    field = record(tables, s.FIELD, [field_id])
    zones = [record(tables, s.ZONE, p, r) for p, r in s.rows_at(tables.table(s.ZONE), [zone_id])]
    # Enemy extraction needs only the level-column provenance for zako. It uses
    # the same resolved level value; fix that provenance to advent's real c112.
    found = enemies(tables, zones, {**quest, "kind": "hard_multi"})
    for enemy in found:
        if "level_origin" in enemy:
            enemy["level_origin"]["column"] = 112
    return {"quest": quest, "field_data": {"id": fd_id, "missing": fd is None, **(fd or {})},
            "field": {"id": field_id, "missing": field is None, **(field or {})},
            "zone": {"id": zone_id, "missing": not zones, "rows": zones},
            "terrain": read_terrain(tables, terrain_id), "enemies": found,
            "entrance": {}, "shops": [], "rewards": {}, "routing": {"kind": "advent_event"}}


def scene_checks(state, spec):
    scanner = MultiplayerScanner(state)
    checks = []
    for tier in spec["tiers"]:
        document = encounter(state, spec["event"]["id"], tier["id"])
        baseline = encounter(state.source, spec.get("creation", {}).get("sourceEvent", spec["event"]["id"]), tier["id"])
        from .atlas import encounter_budget
        budget = encounter_budget(state, document)
        gates = check_boss(document, view=state, baseline=baseline,
                           context={"choice_count": 1, "atlas_budget": budget,
                                    "custom_content": bool(spec.get("creation"))},
                           multiplayer_scanner=scanner)
        for check in gates:
            if check["rule"] == "boss.shop-sync":
                check.update(status="未执行", message="Advent 商店由 scene.server 独立核对三处候选，不能套用共同决战商店表")
        checks.extend({**check, "quest": document["quest"]["selector"]} for check in gates)
    checks.append(result("scene.runtime", "待验证", "场地切换、召唤机关、试炼及三人联机均未执行设备实测"))
    return checks
