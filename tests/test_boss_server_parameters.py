"""Recommended element edits preserve the active server row and other keys."""
import json

import pytest

import wf_quest_lib as codec
from wf.boss import schema as s
from wf.boss.parameters import edit_parameters
from wf.boss.template import create_shared
from test_boss_edit_review import edit_state
from test_boss_model import csv_row
from test_studio_boss_checks import fixture_editor, request


def boss_state(tmp_path):
    state = edit_state(tmp_path)
    shared = s.parse_rows(state.table(s.QUEST_TABLES["hard_multi"])["1006"]["1"])[0]
    values = shared[:50] + shared[51:]
    values[0], values[122] = "1012001", "false"
    state.base.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({"1": {"12": {"1": csv_row(values)}}})
    return state


@pytest.mark.parametrize("owner", ["boss_battle_quest.json", "boss_battle_quest_cnmod.json"])
def test_boss_element_edit_updates_active_owner_only_and_preserves_other_bytes(tmp_path, owner):
    state = boss_state(tmp_path)
    base = tmp_path / "assets/boss_battle_quest.json"
    base.write_text('{"1012001": {"element": 5, "reward": 12}, "keep": { "x" : [ 1, 2 ] }}', encoding="utf-8")
    if owner.endswith("_cnmod.json"):
        (tmp_path / "assets" / owner).write_text(
            '{"1012001": {"element": 5, "reward": 99}, "keep": { "x" : [ 1, 2 ] }}', encoding="utf-8")
    original = base.read_bytes()
    edit_parameters(state, "1012001", {"parameters": {"recommendedElement": 4}})
    target = f"assets/{owner}"
    assert set(state.servers) == {target}
    assert b'{ "x" : [ 1, 2 ] }' in state.servers[target]
    assert json.loads(state.servers[target])["1012001"] == {
        "element": 4, "reward": 99 if owner.endswith("_cnmod.json") else 12}
    assert base.read_bytes() == original
    row = s.parse_rows(state.table(s.QUEST_TABLES["boss_battle"])["1"]["12"]["1"])[0]
    assert row[72] == "4"


@pytest.mark.parametrize("kind", ["boss_battle", "hard_multi"])
def test_element_edit_cannot_silently_skip_missing_server_quest(tmp_path, kind):
    state = boss_state(tmp_path)
    quest = "1012001" if kind == "boss_battle" else "hard_multi:1006/1"
    with pytest.raises(ValueError, match="server quest is absent"):
        edit_parameters(state, quest, {"parameters": {"recommendedElement": 4}})
    assert not state.client and not state.servers


def test_unchanged_element_does_not_require_new_server_inputs(tmp_path):
    state = boss_state(tmp_path)
    edit_parameters(state, "1012001", {"parameters": {"recommendedElement": 5}})
    assert not state.servers and not state.server_original


def test_new_shared_quest_and_followup_use_client_recommended_element(tmp_path):
    editor = fixture_editor(tmp_path)
    state = editor.source.view
    from wf.boss.edit_state import BossEditState
    candidate = BossEditState(state, server_dir=editor.server_dir)
    ids = create_shared(candidate, request(parameters={"recommendedElement": 4}))
    target = "assets/hard_multi_event_quest.json"
    assert json.loads(candidate.servers[target])[ids["quest"]]["element"] == 4
    edit_parameters(candidate, ids["quest"], {"parameters": {"recommendedElement": 3}})
    assert json.loads(candidate.servers[target])[ids["quest"]]["element"] == 3
    assert json.loads(candidate.servers[target])["1006001"]["element"] == 5
