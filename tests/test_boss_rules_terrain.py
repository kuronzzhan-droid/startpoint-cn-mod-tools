"""Boss terrain checks execute on decoded objects and native CSV columns."""
from copy import deepcopy

from wf.rules.boss_terrain import concurrent_positions, terrain_checks
from wf.rules.boss_references import GENERAL, STATES


def snapshot(waves=1):
    groups, rows = [], []
    for index in range(waves):
        objects = [{"type": token} for token in ("BOUNDS", "WALL", "RETURN_LANE_GUIDE")]
        objects += [{"type": "CUSTOM_POSITION", "name": "p0"}, {"type": "CUSTOM_POSITION", "name": "p1"}]
        objects += [{"type": "COFFIN"} for _ in range(9)]
        if index < waves - 1:
            objects += [{"type": "GATE"}, {"type": "TRANSIT"}]
        groups.append({"type": "objectgroup", "name": str(index), "objects": objects})
        row = [""] * 42
        row[22], row[23], row[24], row[25], row[26] = "0", "1", "a", "1", "a"
        rows.append({"path": ["zone", str(index)], "row": row})
    return {"quest": {"kind": "hard_multi_event", "fields": {}},
            "field": {"row": [""] * 7 + ["gate", "transit"]},
            "zone": {"rows": rows}, "terrain": {"waves": groups},
            "enemies": [{"code": "a", "wave": str(index), "position_name": "p0"}
                        for index in range(waves)]}


def test_multilayer_missing_c7_is_blocking():
    doc = snapshot(2)
    assert all(r["status"] == "满足" for r in terrain_checks(doc))
    doc["field"]["row"][7] = "(None)"
    checks = terrain_checks(doc)
    assert checks[0]["blocking"] is True
    assert "C8251" in checks[0]["message"]


def test_zone_extra_rows_do_not_invent_a_wave():
    doc = snapshot()
    extra = deepcopy(doc["zone"]["rows"][0])
    extra["path"][-1] = "1"
    doc["zone"]["rows"].append(extra)
    assert terrain_checks(doc)[0]["status"] == "不适用"


def test_each_layer_needs_own_positions_coffins_and_zone():
    doc = snapshot(2)
    doc["terrain"]["waves"][1]["objects"] = [{"type": "COFFIN"}] * 3
    doc["zone"]["rows"].pop()
    result = terrain_checks(doc)[1]
    assert result["blocking"]
    assert any("9 个" in issue for issue in result["issues"])
    assert any("BOUNDS" in issue for issue in result["issues"])
    assert any("同名 zone" in issue for issue in result["issues"])


def test_terrain_unavailable_is_not_passed():
    assert {r["status"] for r in terrain_checks({})} == {"未执行"}


def test_concurrent_positions_checks_modes_separately():
    doc = snapshot()
    row = doc["zone"]["rows"][0]["row"]
    row[29:31] = ["1", "b"]
    doc["enemies"].append({"code": "b", "wave": "0", "mode": "multi", "position_name": "p0"})
    assert concurrent_positions(doc)["blocking"]
    doc["enemies"][-1]["position_name"] = "p1"
    assert concurrent_positions(doc)["status"] == "满足"
    row[22] = "1"
    assert concurrent_positions(doc)["status"] == "不适用"


def test_missing_enemy_position_does_not_pass():
    doc = snapshot()
    doc["zone"]["rows"][0]["row"][29:31] = ["1", "b"]
    assert concurrent_positions(doc)["status"] == "待验证"


def test_single_player_practice_does_not_require_nine_coffins():
    doc = snapshot()
    doc["quest"]["kind"] = "practice"
    doc["terrain"]["waves"][0]["objects"] = [o for o in doc["terrain"]["waves"][0]["objects"]
                                                if o["type"] != "COFFIN"]
    assert terrain_checks(doc)[1]["status"] == "满足"


def test_official_single_wave_transit_is_unused_and_not_rejected():
    doc = snapshot()
    doc["terrain"]["waves"][0]["objects"].append({"type": "TRANSIT"})
    assert terrain_checks(doc)[1]["status"] == "满足"


def test_native_numbered_wall_tokens_satisfy_boundary_geometry():
    doc = snapshot()
    for obj in doc["terrain"]["waves"][0]["objects"]:
        if obj["type"] == "WALL":
            obj["type"] = "WALL1"
    assert terrain_checks(doc)[1]["status"] == "满足"


class RoutineView:
    def __init__(self, positions):
        self.states = {"crab_100": {"1": {str(index): [""] * 50 + [name]
                                       for index, name in enumerate(positions)}}}

    def table(self, logical):
        return self.states if logical == STATES else None


def routine_snapshot(waves=1):
    doc = snapshot(waves)
    doc["enemies"][0].update(table=GENERAL, path=["a", "100"], row=[""] * 42 + ["crab_100"])
    return doc


def test_selected_native_band_routine_positions_are_required_in_same_layer():
    doc = routine_snapshot(2)
    doc["terrain"]["waves"][1]["objects"].append({"type": "CUSTOM_POSITION", "name": "p4"})
    check = terrain_checks(doc, view=RoutineView(["p0", "p4"]))[1]
    assert check["blocking"]
    assert any("层 0" in issue and "crab_100" in issue and "p4" in issue for issue in check["issues"])
    doc["terrain"]["waves"][0]["objects"].append({"type": "CUSTOM_POSITION", "name": "p4"})
    assert terrain_checks(doc, view=RoutineView(["p0", "p4"]))[1]["status"] == "满足"


def test_missing_referenced_routine_is_a_problem_but_missing_view_is_pending():
    doc = routine_snapshot()
    assert terrain_checks(doc)[1]["status"] == "待验证"
    view = RoutineView(["p0"])
    view.states.clear()
    check = terrain_checks(doc, view=view)[1]
    assert check["status"] == "问题" and check["blocking"]
    assert "缺失 routine" in check["issues"][0]


def test_explicit_dangling_combat_references_are_blocking_not_unexecuted():
    from wf.rules.boss_levels import enemy_level_check
    for key in ("field_data", "field", "zone", "terrain"):
        doc = snapshot()
        doc[key] = {"id": "absent", "missing": True}
        checks = [*terrain_checks(doc), enemy_level_check(doc)]
        assert all(check["status"] == "问题" and check["blocking"] for check in checks), key
        assert all(key in check["issues"][0] for check in checks)
