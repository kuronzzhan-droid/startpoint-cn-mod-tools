"""Delivered terrain resources are immutable inputs to later edit generations."""
import copy

import pytest
import wf_quest_lib as codec

from test_m6_terrain import show, state
from wf.boss import schema as s
from wf.boss.edit_state import BossEditState
from wf.boss.terrain_edit import apply_terrain
from wf.studio.boss import BossDraftStore, BossEditor, compile_boss
from wf.studio.source import StudioSource


QUEST = "hard_multi:1006/1"
IDENTITY = "studio_terrain_hard_multi_1006_1"


def update(x):
    return {"operation": "terrain_position", "layer": "0", "action": "update",
            "name": "p0", "x": x, "y": 100}


def baseline_after(state):
    """Simulate a read-only next view without an actual delivery or file writes."""
    base = copy.deepcopy(state.base)
    base.files.update(state.client)
    return StudioSource(base)


def test_each_delivered_generation_can_be_edited_again_and_preserves_predecessors(state):
    for generation in range(1, 4):
        baseline = copy.deepcopy(state.base.files)
        apply_terrain(state, QUEST, update(120 + generation))
        identity = IDENTITY + (f"_v{generation}" if generation > 1 else "")
        assert show(state)["field_data"]["id"] == identity
        path = show(state)["terrain"]["logical"]
        assert path not in baseline
        assert state.base.files == baseline
        apply_terrain(state, QUEST, update(130 + generation))
        assert show(state)["field_data"]["id"] == identity
        assert show(state)["terrain"]["logical"] == path
        assert len([key for key in state.client if key.startswith("battle/terrain/")]) == 1
        state = BossEditState(baseline_after(state))


@pytest.mark.parametrize("logical", [s.FIELD_DATA, s.FIELD, s.ZONE])
def test_any_baseline_dependency_collision_skips_generation_without_overwriting(state, logical):
    tree = codec.parse_node(state.base.files[logical])
    existing = {"0": "foreign-zone"} if logical == s.ZONE else "foreign-row"
    tree[IDENTITY], tree[IDENTITY + "_v2"] = existing, existing
    state.base.files[logical] = codec.build_node(tree)
    apply_terrain(state, QUEST, update(121))
    assert show(state)["field_data"]["id"] == IDENTITY + "_v3"
    assert state.table(logical)[IDENTITY] == existing
    assert state.table(logical)[IDENTITY + "_v2"] == existing


def test_append_after_delivery_uses_new_generation_for_field_zone_and_terrain(state):
    payload = {"operation": "terrain_add_layer", "sourceQuest": QUEST, "sourceLayer": "0"}
    apply_terrain(state, QUEST, payload)
    state = BossEditState(baseline_after(state))
    before = show(state)
    apply_terrain(state, QUEST, payload)
    after = show(state)
    assert after["terrain"]["wave_count"] == 3
    assert all(after[key]["id"] == IDENTITY + "_v2" for key in ("field_data", "field", "zone"))
    for key in ("field_data", "field", "zone"):
        logical = getattr(s, key.upper())
        assert state.table(logical)[before[key]["id"]] == codec.parse_node(state.base.files[logical])[before[key]["id"]]


def test_second_generation_draft_preview_and_compile_replay_identically(state, tmp_path):
    apply_terrain(state, QUEST, update(120))
    source = baseline_after(state)
    editor = BossEditor(source, store=BossDraftStore(tmp_path / "generation-drafts"),
                        server_dir=tmp_path / "server")
    assert editor.preview(QUEST, update(121))["ok"]
    editor.apply(QUEST, update(121))
    editor.apply(QUEST, update(122))
    saved = editor.store.save(QUEST)
    compiled = compile_boss(source, editor.store, saved, server_dir=editor.server_dir)
    terrain_paths = [key for key in compiled["client"] if key.startswith("battle/terrain/")]
    assert terrain_paths == ["battle/terrain/studio/hard_multi_1006_1_v2.amf3.deflate"]
    assert not any(check["blocking"] for check in compiled["checks"])
