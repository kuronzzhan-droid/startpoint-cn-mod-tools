"""Edited position rectangles must remain within their own terrain layer."""
import copy

import pytest

from test_m6_terrain import show, state
from wf.boss.terrain_edit import apply_terrain
from wf.boss.terrain_objects import decode, encode
from wf.rules.boss_terrain import terrain_checks
from wf.studio.boss import BossDraftStore, BossEditor, compile_boss


def position(action="add", **values):
    return {"operation": "terrain_position", "layer": "0", "action": action,
            "name": "extra" if action == "add" else "p0", **values}


@pytest.mark.parametrize("values", [{}, {"x": 90}, {"y": 80}])
def test_add_missing_either_coordinate_is_rejected_before_overlay_changes(state, values):
    with pytest.raises(ValueError, match="requires both x and y"):
        apply_terrain(state, "1006001", position(**values))
    assert not state.client


@pytest.mark.parametrize("action", ["add", "update"])
@pytest.mark.parametrize("values", [
    {"x": 45, "y": 10}, {"x": 50, "y": -1},
    {"x": 331, "y": 10}, {"x": 50, "y": 285},
    {"x": 50, "y": 10, "width": 297}, {"x": 50, "y": 10, "height": 291},
])
def test_out_of_bounds_rectangle_is_rejected_including_size(state, action, values):
    with pytest.raises(ValueError, match="outside BOUNDS"):
        apply_terrain(state, "1006001", position(action, **values))
    assert not state.client


def test_positions_exactly_touching_edges_are_valid(state):
    apply_terrain(state, "1006001", position(x=46, y=0, width=300, height=300))
    apply_terrain(state, "1006001", position("update", x=346, y=300, width=0, height=0))
    assert not any(check["blocking"] for check in terrain_checks(show(state), view=state))


def test_lower_layer_uses_its_own_bounds_origin(state):
    logical = "battle/terrain/test.amf3.deflate"
    tree = decode(state.base.files[logical])
    for obj in tree["layers"][0]["objects"]:
        obj["y"] += 352
    state.base.files[logical] = encode(tree)
    with pytest.raises(ValueError, match="outside BOUNDS"):
        apply_terrain(state, "1006001", position(x=80, y=10))
    assert not state.client
    apply_terrain(state, "1006001", position(x=80, y=352))


def test_replacement_rejects_preserved_positions_outside_narrower_bounds(state):
    logical = "battle/terrain/other.amf3.deflate"
    tree = decode(state.base.files[logical])
    tree["layers"][0]["objects"][0]["width"] = 80
    state.base.files[logical] = encode(tree)
    original = copy.deepcopy(state.base.files)
    with pytest.raises(ValueError, match="p0.*outside BOUNDS"):
        apply_terrain(state, "1006001", {"operation": "terrain_replace", "terrain": logical})
    assert not state.client and state.base.files == original


def test_edit_does_not_reject_untouched_native_offscreen_positions(state):
    logical = "battle/terrain/test.amf3.deflate"
    tree = decode(state.base.files[logical])
    native = next(obj for obj in tree["layers"][0]["objects"] if obj.get("name") == "unused")
    native["x"] = -100
    state.base.files[logical] = encode(tree)
    apply_terrain(state, "1006001", position(x=80, y=100))
    assert not any(check["blocking"] for check in terrain_checks(show(state), view=state))
    assert next(obj for obj in show(state)["terrain"]["waves"][0]["objects"]
                if obj.get("name") == "unused")["x"] == -100


def test_out_of_bounds_is_rejected_by_preview_and_compile(state, tmp_path):
    editor = BossEditor(state.source, store=BossDraftStore(tmp_path / "bounds-drafts"),
                        server_dir=tmp_path / "server")
    good = position(x=120, y=100)
    draft = editor.apply("1006001", good)["changeset"]
    bad = good | {"x": 335}
    preview = editor.preview("1006001", position("update", x=335, y=100))
    assert not preview["ok"] and "outside BOUNDS" in str(preview)
    draft["changes"][0]["params"]["requests"][0] = bad
    with pytest.raises(ValueError, match="outside BOUNDS"):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
