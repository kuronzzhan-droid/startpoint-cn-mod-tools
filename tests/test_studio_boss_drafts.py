"""Stateful boss editing: real replay, reservations, input locks and cancellation."""
from __future__ import annotations

import copy
import json

import pytest
import wf_quest_lib as codec

from test_boss_model import csv_row, row
from test_studio_boss_checks import encoded, fixture_editor, request
from wf.boss import schema as s
from wf.rules.boss_preload import FUNNEL
from wf.studio.boss import BossEditor, compile_boss
from wf.studio.deliver_bridge import _stage
from wf.studio.drafts import DraftError
from wf.studio.source import StudioSource
from wf.view.base149 import member


def compile_saved(editor, quest):
    saved = editor.store.save(quest)
    return compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)


def test_new_draft_survives_save_reload_and_compiles_identically(tmp_path):
    editor = fixture_editor(tmp_path)
    applied = editor.apply("new", request(name="独立重放"))
    quest = applied["questId"]
    first = compile_saved(editor, quest)
    reopened = BossEditor(StudioSource(editor.source.view), store=editor.store, server_dir=editor.server_dir)
    second = compile_saved(reopened, quest)
    assert first == second
    values = codec.parse_node(first["client"][s.QUEST_TABLES["hard_multi"]])
    actual = s.parse_rows(values[applied["allocation"]["event"]]["1"])[0]
    assert actual[0] == quest and actual[2] == "独立重放 ::quest_rank::"
    assert json.loads(first["servers"]["assets/hard_multi_event_quest.json"])[quest]["name"] == actual[2]
    assert editor.store.load(quest)["savedRevision"] == 1


def test_create_then_second_edit_preserves_one_replay_sequence(tmp_path):
    editor = fixture_editor(tmp_path)
    created = editor.apply("new", request())
    quest = created["questId"]
    editor.apply(quest, {"operation": "edit", "parameters": {"hpMultiplier": 2, "level": 90}})
    editor.apply(quest, {"operation": "edit", "parameters": {"attackMultiplier": 1.7}})
    saved = editor.store.save(quest)
    assert len(saved["changes"]) == 1 and len(saved["changes"][0]["params"]["requests"]) == 3
    result = compile_saved(editor, quest)
    values = codec.parse_node(result["client"][s.QUEST_TABLES["hard_multi"]])
    actual = s.parse_rows(values[created["allocation"]["event"]]["1"])[0]
    assert actual[98:104] == ["2", "2", "2", "1.7", "1.7", "1.7"]
    assert actual[107] == "90"
    assert codec.parse_node(editor.source.view.files[s.QUEST_TABLES["hard_multi"]]).keys() == {"1006"}


def five_tier_editor(tmp_path):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    original = codec.parse_node(raw.files[s.QUEST_TABLES["hard_multi"]])["1006"]["1"]
    cells = s.parse_rows(original)[0]
    cells = cells[:50] + cells[51:]
    group = {}
    for tier in range(1, 6):
        values = list(cells)
        values[0], values[122], values[123] = str(1080000 + tier), "false", "false"
        group[str(tier)] = csv_row(values)
    raw.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({"1": {"80": group}})
    raw.files[s.NODE] = codec.build_node({"1": {"80": row(14, {1: "五档领主", 6: "81"})}})
    return editor


def test_five_tiers_apply_base_parameters_and_per_tier_overrides(tmp_path):
    editor = five_tier_editor(tmp_path)
    tiers = [{"level": 20 * index, "hpMultiplier": index} for index in range(1, 6)]
    editor.apply("1080001", {"operation": "edit", "parameters": {"attackMultiplier": 1.2}, "tiers": tiers})
    result = compile_saved(editor, "1080001")
    group = codec.parse_node(result["client"][s.QUEST_TABLES["boss_battle"]])["1"]["80"]
    for index in range(1, 6):
        cells = s.parse_rows(group[str(index)])[0]
        assert cells[97:100] == [str(index)] * 3
        assert cells[100:103] == ["1.2"] * 3 and cells[106] == str(index * 20)


def test_saved_new_drafts_reserve_distinct_event_quest_and_folder_node(tmp_path):
    editor = fixture_editor(tmp_path)
    first = editor.apply("new", request())
    editor.store.save(first["questId"])
    second = editor.apply("new", request())
    for key in ("event", "quest", "node", "zone", "fieldData", "reward"):
        assert first["allocation"][key] != second["allocation"][key]
    assert len(editor.store.characters()) == 2
    assert compile_saved(editor, first["questId"])["client"]
    assert compile_saved(editor, second["questId"])["client"]


@pytest.mark.parametrize("collision", ["event", "node"])
def test_forced_id_collision_against_other_draft_is_rejected(tmp_path, collision):
    editor = fixture_editor(tmp_path)
    first = editor.apply("new", request())
    ids = {"event": first["allocation"]["event"] if collision == "event" else "2200"}
    if collision == "node":
        ids["node"] = first["allocation"]["node"]
    before = editor.store.load(first["questId"])
    with pytest.raises(DraftError, match="collision"):
        editor.apply("new", request(ids=ids))
    assert editor.store.load(first["questId"]) == before and len(editor.store.characters()) == 1


@pytest.mark.parametrize("drift", ["version", "client", "server", "lock"])
def test_input_drift_is_rejected_before_compile_or_next_edit(tmp_path, drift):
    editor = fixture_editor(tmp_path)
    applied = editor.apply("new", request())
    quest, document = applied["questId"], applied["changeset"]
    if drift == "version":
        editor.source.view.tip = "1.4.237"
    elif drift == "client":
        table = codec.parse_node(editor.source.view.files[s.EVENT])
        cells = s.parse_rows(table["1006"])[0]
        cells[2] = "changed outside draft"
        table["1006"] = csv_row(cells)
        editor.source.view.files[s.EVENT] = codec.build_node(table)
    elif drift == "server":
        (editor.server_dir / "assets/hard_multi_event_quest.json").write_text('{"unrelated":{}}', encoding="utf-8")
    else:
        document = copy.deepcopy(document)
        logical = next(iter(document["changes"][0]["params"]["inputs"]["client"]))
        document["changes"][0]["params"]["inputs"]["client"][logical] = "0" * 64
    with pytest.raises(ValueError, match="mismatch|drift"):
        compile_boss(editor.source, editor.store, document, server_dir=editor.server_dir)
    if drift != "lock":
        with pytest.raises(DraftError, match="mismatch|drift"):
            editor.apply(quest, {"operation": "edit", "parameters": {"level": 90}})


def test_no_change_request_never_creates_a_draft(tmp_path):
    editor = fixture_editor(tmp_path)
    with pytest.raises(DraftError, match="no changes"):
        editor.apply("1006001", {"operation": "edit", "parameters": {"level": 100}})
    assert editor.store.characters() == [] and not editor.store.root.exists()


def test_reversed_edits_cannot_stage_an_empty_delivery(tmp_path):
    editor = fixture_editor(tmp_path)
    for level in (90, 100):
        editor.apply("1006001", {"operation": "edit", "parameters": {"level": level}})
    saved = editor.store.save("1006001")
    result = compile_saved(editor, "1006001")
    raw = editor.source.view
    def read_member(name):
        return next((data, "fixture") for logical, data in raw.files.items() if member(logical) == name)
    raw.read_member = read_member
    compiled = ({("common", key): value for key, value in result["client"].items()},
                result["servers"], result["server_before"], result["changes"], result["checks"])
    out = tmp_path / "empty-delivery"
    with pytest.raises(DraftError, match="没有与基线不同"):
        _stage(out, saved, editor.source, compiled, "1.4.237")
    assert not out.exists()


@pytest.mark.parametrize("bad", [
    {"operation": "unknown"}, {"operation": "edit", "parameters": {"reward": 1}},
    {"operation": "edit", "tiers": [{}] * 5},
    {"operation": "create_shared", "sourceQuest": "hard_multi:1006/1"},
])
def test_unsupported_or_mixed_followup_preserves_saved_draft(tmp_path, bad):
    editor = fixture_editor(tmp_path)
    created = editor.apply("new", request())
    quest = created["questId"]
    before = editor.store.save(quest)
    with pytest.raises(DraftError):
        editor.apply(quest, bad)
    assert editor.store.load(quest) == before


def test_create_then_element_edit_checks_original_template_preload(tmp_path):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    table = codec.parse_node(raw.files[s.GENERAL_BOSS])
    for level, text in table["org"].items():
        cells = s.parse_rows(text)[0]
        cells[25], cells[111] = "battle/marker/summon", "battle/action/summon"
        table["org"][level] = csv_row(cells)
    raw.files[s.GENERAL_BOSS] = codec.build_node(table)
    raw.files[FUNNEL] = codec.build_node({"funnel": {"100": "1,battle/action/funnel"}})
    raw.files["battle/action/summon.action.dsl.amf3.deflate"] = encoded(["SpawnFunnel", ["Funnel", "funnel"]])
    raw.files["battle/action/funnel.action.dsl.amf3.deflate"] = encoded(["ResolveByElement", "battle/effect/shot", 255])
    raw.files["battle/marker/summon.timeline.amf3.deflate"] = encoded(
        {"points": [{"path": "enemy_action1", "frames": [{"data": [1]}]}]})
    created = editor.apply("new", request())
    quest = created["questId"]
    followup = {"operation": "edit", "parameters": {"recommendedElement": 2}}
    preview = editor.preview(quest, followup)
    assert not preview["ok"] and "预载" in preview["checks"][0]["message"]
    with pytest.raises(DraftError, match="预载"):
        editor.apply(quest, followup)
    tampered = copy.deepcopy(created["changeset"])
    tampered["changes"][0]["params"]["requests"].append(followup)
    with pytest.raises(ValueError, match="预载"):
        compile_boss(editor.source, editor.store, tampered, server_dir=editor.server_dir)
