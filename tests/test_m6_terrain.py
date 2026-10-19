"""Terrain edits retain encounter ownership and native point semantics."""
from __future__ import annotations

import copy

import pytest
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.boss.edit_state import BossEditState
from wf.boss.reader import BossReader
from wf.boss.terrain_edit import apply_terrain
from wf.boss.terrain_objects import decode, encode
from wf.rules.boss_terrain import terrain_checks
from test_studio_boss_checks import fixture_editor


@pytest.fixture
def state(tmp_path):
    editor = fixture_editor(tmp_path)
    original = editor.source.view
    tree = decode(original.files["battle/terrain/test.amf3.deflate"])
    for obj in tree["layers"][0]["objects"]:
        obj.update(x=46, y=0, width=16, height=16)
        if obj["type"] == "CUSTOM_POSITION":
            obj.update(x=128, y=100)
    tree["layers"][0]["objects"] += [
        {"type": "GATE", "x": 127, "y": 42, "width": 20, "height": 20},
        {"type": "TRANSIT", "x": 111, "y": 144, "width": 50, "height": 50},
        {"type": "CUSTOM_POSITION", "name": "unused", "x": 10, "y": 10, "width": 16, "height": 16}]
    original.files["battle/terrain/test.amf3.deflate"] = encode(tree)
    other = copy.deepcopy(tree)
    other["layers"][0]["objects"][0]["y"] = 352
    next(o for o in other["layers"][0]["objects"] if o.get("name") == "p0")["x"] = 70
    original.files["battle/terrain/other.amf3.deflate"] = encode(other)
    return BossEditState(editor.source)


def show(state):
    return BossReader(state).show("hard_multi:1006/1")


def test_read_model_reports_rectangles_runtime_centres_and_coffin_seats(state):
    terrain = show(state)["terrain"]
    wave = terrain["waves"][0]
    assert wave["bounds"][0]["x"] == 46
    assert len(wave["coffins"]) == 9
    assert [(p["party"], p["member"]) for p in wave["coffins"]] == [(a, b) for a in range(3) for b in range(3)]
    assert wave["custom_positions"][0]["runtime_point"] == {"x": 816, "y": 648}


def test_replace_keeps_required_point_meaning_and_shared_resources(state):
    before = copy.deepcopy(state.base.files)
    apply_terrain(state, "1006001", {"operation": "terrain_replace", "terrain": "battle/terrain/other"})
    doc = show(state)
    point = next(p for p in doc["terrain"]["waves"][0]["custom_positions"] if p["name"] == "p0")
    assert point["rect"] == {"x": 128, "y": 452, "width": 16, "height": 16}
    assert doc["field_data"]["id"].startswith("studio_terrain_")
    assert state.base.files == before
    assert "battle/terrain/test.amf3.deflate" not in state.client
    assert "battle/terrain/other.amf3.deflate" not in state.client
    assert len(state.client) == 3


def test_position_add_update_delete_replay_retains_other_objects(state):
    before = show(state)["terrain"]["waves"][0]["objects"]
    request = {"operation": "terrain_position", "layer": "0", "name": "new_point"}
    apply_terrain(state, "1006001", request | {"action": "add", "x": 90, "y": 80})
    apply_terrain(state, "1006001", request | {"action": "update", "x": 91, "y": 81, "width": 20})
    point = show(state)["terrain"]["waves"][0]["objects"][-1]
    assert point["x"] == 91 and point["width"] == 20
    apply_terrain(state, "1006001", request | {"action": "delete"})
    assert show(state)["terrain"]["waves"][0]["objects"] == before


def test_append_clones_zone_and_fills_field_without_shared_mutations(state):
    before = show(state)
    apply_terrain(state, "1006001", {"operation": "terrain_add_layer", "sourceQuest": "1006001", "sourceLayer": "0"})
    doc = show(state)
    assert doc["terrain"]["wave_count"] == 2
    assert doc["zone"]["id"] != before["zone"]["id"]
    assert doc["field"]["id"] != before["field"]["id"]
    assert doc["zone"]["rows"][1]["row"] == before["zone"]["rows"][0]["row"]
    assert {o["type"] for o in doc["terrain"]["waves"][1]["objects"]}.isdisjoint({"GATE", "TRANSIT"})
    assert not any(c["blocking"] for c in terrain_checks(doc, view=state))
    doc["field"]["row"][7] = "(None)"
    assert terrain_checks(doc, view=state)[0]["blocking"]
    assert "C8251" in terrain_checks(doc, view=state)[0]["message"]


def test_remove_used_position_and_duplicate_names_are_blocking(state):
    apply_terrain(state, "1006001", {"operation": "terrain_position", "layer": "0", "action": "delete", "name": "p0"})
    doc = show(state)
    assert terrain_checks(doc, view=state)[1]["blocking"]
    doc["terrain"]["waves"][0]["objects"] += [{"type": "CUSTOM_POSITION", "name": "dup"}] * 2
    assert any("重名" in issue for issue in terrain_checks(doc, view=state)[1]["issues"])


@pytest.mark.parametrize("payload", [
    {"operation": "terrain_replace", "terrain": "battle/terrain/../escape"},
    {"operation": "terrain_replace", "terrain": "battle/terrain/missing"},
    {"operation": "terrain_position", "layer": "0", "action": "add", "name": "p0", "x": 1, "y": 1},
    {"operation": "terrain_position", "layer": "9", "action": "delete", "name": "p0"},
    {"operation": "terrain_position", "layer": "0", "action": "update", "name": "p0", "x": float("nan"), "y": 1},
])
def test_invalid_targets_and_coordinates_are_rejected(state, payload):
    with pytest.raises(ValueError):
        apply_terrain(state, "1006001", payload)
    assert not state.client


def test_preexisting_derived_resource_is_not_overwritten(state):
    target = "battle/terrain/studio/hard_multi_1006_1.amf3.deflate"
    state.base.files[target] = encode({"layers": []})
    with pytest.raises(ValueError, match="collision"):
        apply_terrain(state, "1006001", {"operation": "terrain_position", "layer": "0", "action": "update", "name": "p0", "x": 1, "y": 1})
    assert not state.client


def test_append_with_different_recommended_element_cannot_reuse_source_preload(state):
    from wf.view.base149 import join
    logical = s.QUEST_TABLES["hard_multi"]
    table = codec.parse_node(state.base.files[logical])
    values = s.parse_rows(table["1006"]["1"])[0]
    values[0], values[73] = "1007001", str((int(values[73]) + 1) % 6)
    table["1007"] = {"1": join(values)}
    state.base.files[logical] = codec.build_node(table)
    with pytest.raises(ValueError, match="C8016"):
        apply_terrain(state, "1006001", {"operation": "terrain_add_layer", "sourceQuest": "1007001", "sourceLayer": "0"})
    assert not state.client


def test_untouched_existing_table_leaves_remain_byte_identical(state):
    def leaves(raw, path=()):
        parsed = codec._try_parse_map(raw)
        if parsed is None:
            return {path: raw}
        return {key: value for name, child in zip(*parsed) for key, value in leaves(child, path + (name,)).items()}
    apply_terrain(state, "1006001", {"operation": "terrain_position", "layer": "0", "action": "update", "name": "p0", "x": 120, "y": 100})
    for logical in (s.FIELD_DATA, s.QUEST_TABLES["hard_multi"]):
        before, after = leaves(state.original[logical]), leaves(state.client[logical])
        for path, raw in before.items():
            if logical != s.QUEST_TABLES["hard_multi"] or path != ("1006", "1"):
                assert after[path] == raw


def test_saved_terrain_sequence_compiles_and_rejects_deleted_routine_position(state, tmp_path):
    from wf.studio.boss import BossDraftStore, BossEditor, compile_boss
    editor = BossEditor(state.source, store=BossDraftStore(tmp_path / "terrain-drafts"), server_dir=tmp_path / "server")
    added = {"operation": "terrain_position", "layer": "0", "action": "add", "name": "extra", "x": 120, "y": 100}
    applied = editor.apply("1006001", added)
    saved = editor.store.save(applied["questId"])
    compiled = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
    assert any(name.endswith(".amf3.deflate") for name in compiled["client"])
    assert not any(check["blocking"] for check in compiled["checks"])
    preview = editor.preview("1006001", {"operation": "terrain_position", "layer": "0", "action": "delete", "name": "p0"})
    assert not preview["ok"]


@pytest.mark.parametrize("column", [7, 8])
def test_append_missing_transition_is_rejected_by_preview_and_compile(state, tmp_path, monkeypatch, column):
    import wf.studio.boss as bridge
    import wf.boss.terrain_edit as terrain_module
    from wf.view.base149 import join
    editor = bridge.BossEditor(state.source, store=bridge.BossDraftStore(tmp_path / "terrain-drafts"), server_dir=tmp_path / "server")
    payload = {"operation": "terrain_add_layer", "sourceQuest": "1006001", "sourceLayer": "0"}
    applied = editor.apply("1006001", payload)
    saved = editor.store.save(applied["questId"])
    normal = terrain_module.apply_terrain

    def corrupt(candidate, quest, request):
        touched = normal(candidate, quest, request)
        doc = BossReader(candidate).show(touched[0])
        values = list(doc["field"]["row"])
        values[column] = "(None)"
        candidate.set_leaf(s.FIELD, (doc["field"]["id"],), join(values))
        return touched

    monkeypatch.setattr(terrain_module, "apply_terrain", corrupt)
    other = bridge.BossEditor(state.source, store=bridge.BossDraftStore(tmp_path / "negative-drafts"), server_dir=tmp_path / "server")
    preview = other.preview("1006001", payload)
    assert not preview["ok"] and any("C8251" in check["message"] for check in preview["checks"])
    with pytest.raises(ValueError, match="C8251"):
        bridge.compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
