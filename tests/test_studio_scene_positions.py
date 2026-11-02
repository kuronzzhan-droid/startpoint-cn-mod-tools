"""Real GeneralBoss movement discriminators protect scene terrain validation."""
import pytest

from test_boss_rules_terrain import RoutineView, routine_snapshot
from wf.rules.boss_terrain import terrain_checks


def movement_view(kind, x, y=""):
    view = RoutineView([])
    view.states["crab_100"]["1"]["move"] = [""] * 49 + [kind, x, y, "0"]
    return view


@pytest.mark.parametrize("x,y", [("0", "0"), ("-20", "1.5"), ("2e1", "-120")])
def test_studio_scene_relative_offsets_are_not_named_positions(x, y):
    check = terrain_checks(routine_snapshot(), view=movement_view("1", x, y))[1]
    assert check["status"] == "满足" and not check["blocking"]


def test_studio_scene_absolute_numeric_name_remains_a_real_reference():
    doc = routine_snapshot()
    check = terrain_checks(doc, view=movement_view("0", "0"))[1]
    assert check["blocking"] and any("0" in issue for issue in check["issues"])
    doc["terrain"]["waves"][0]["objects"].append({"type": "CUSTOM_POSITION", "name": "0"})
    assert terrain_checks(doc, view=movement_view("0", "0"))[1]["status"] == "满足"


@pytest.mark.parametrize("kind,x,y", [("2", "p0", ""), ("1", "NaN", "0"),
    ("1", "0", "Infinity"), ("1", "missing", "0"), ("0", "", "")])
def test_studio_scene_invalid_movement_is_still_blocked(kind, x, y):
    check = terrain_checks(routine_snapshot(), view=movement_view(kind, x, y))[1]
    assert check["status"] == "问题" and check["blocking"]


def test_studio_scene_none_movement_does_not_consume_leftover_coordinates():
    check = terrain_checks(routine_snapshot(), view=movement_view("(None)", "unused", ""))[1]
    assert check["status"] == "满足"
