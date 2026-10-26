"""Negative candidates must be rejected inside the real draft replay bridge."""
from __future__ import annotations

import copy
import json
import zlib

import pytest
import wf_dsl
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.boss.template import server_quest
from wf.rules.boss_preload import FUNNEL
from wf.studio.boss import BossDraftStore, BossEditor, compile_boss
from wf.studio.source import StudioSource
from test_boss_edit_review import edit_state
from test_boss_model import csv_row


def encoded(tree):
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


def fixture_editor(tmp_path):
    server = tmp_path / "server"
    server.mkdir()
    initial = edit_state(server)
    raw = initial.base
    raw.tip, raw.zips = "1.4.236", []
    quests = codec.parse_node(raw.files[s.QUEST_TABLES["hard_multi"]])
    row = s.parse_rows(quests["1006"]["1"])[0]
    for column in (72, 85, 86, 87, 88, 94, 95, 96, 97):
        row[column] = "1"
    row[107] = "100"
    quests["1006"]["1"] = csv_row(row)
    raw.files[s.QUEST_TABLES["hard_multi"]] = codec.build_node(quests)
    zone = codec.parse_node(raw.files[s.ZONE])
    del zone["zone"]["1"]
    raw.files[s.ZONE] = codec.build_node(zone)
    raw.files.pop(s.SHOP)
    events = codec.parse_node(raw.files[s.EVENT])
    events["2081"] = events["1006"]
    raw.files[s.EVENT] = codec.build_node(events)
    objects = [{"type": t} for t in ("BOUNDS", "WALL1", "RETURN_LANE_GUIDE")]
    objects[0].update(x=0, y=0, width=320, height=352)
    objects += [{"type": "CUSTOM_POSITION", "name": "p0"}] + [{"type": "COFFIN"}] * 9
    raw.files["battle/terrain/test.amf3.deflate"] = encoded(
        {"layers": [{"type": "objectgroup", "name": "0", "objects": objects}]})
    (server / "assets/hard_multi_event_quest.json").write_text(
        json.dumps({"1006001": server_quest(row)}), encoding="utf-8")
    return BossEditor(StudioSource(raw), store=BossDraftStore(tmp_path / "drafts"), server_dir=server)


def request(**extra):
    return {"operation": "create_shared", "sourceQuest": "hard_multi:1006/1", **extra}


def test_valid_real_replay_is_compilable_and_reward_gate_executed(tmp_path):
    editor = fixture_editor(tmp_path)
    preview = editor.preview("new", request())
    assert preview["ok"], preview
    reward = next(c for c in preview["checks"] if c["rule"] == "delivery.reward-keys")
    assert reward["status"] == "满足" and reward["evidence"]["checked_rows"] == 2
    draft = editor.apply("new", request())["changeset"]
    compiled = compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert compiled["client"] and compiled["servers"]
    assert not any(c["blocking"] for c in compiled["checks"])


def test_multilayer_c7_is_rejected_inside_preview_and_compile(tmp_path, monkeypatch):
    import wf.studio.boss as bridge
    editor = fixture_editor(tmp_path)
    draft = editor.apply("new", request())["changeset"]
    original = bridge.create_shared

    def corrupt(state, req, **kwargs):
        ids = original(state, req, **kwargs)
        row = s.parse_rows(state.table(s.FIELD)["field"])[0]
        row[7] = "(None)"
        state.set_leaf(s.FIELD, ("field",), csv_row(row))
        logical = "battle/terrain/test.amf3.deflate"
        terrain = wf_dsl.parse_dsl(zlib.decompress(state.raw(logical), -15))["tree"]
        terrain["layers"].append(copy.deepcopy(terrain["layers"][0]))
        terrain["layers"][1]["name"] = "1"
        terrain["layers"][0]["objects"] += [{"type": "GATE"}, {"type": "TRANSIT"}]
        state.client[logical] = encoded(terrain)
        zone = state.table(s.ZONE)[ids["zone"]]
        state.set_leaf(s.ZONE, (ids["zone"], "1"), zone["0"], new=True)
        return ids

    monkeypatch.setattr(bridge, "create_shared", corrupt)
    preview = editor.preview("new", request())
    assert not preview["ok"] and "C8251" in preview["checks"][0]["message"]
    with pytest.raises(ValueError, match="C8251"):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_changed_element_missing_shim_rejected_by_candidate_resources(tmp_path):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    table = codec.parse_node(raw.files[s.GENERAL_BOSS])
    for key in table["org"]:
        row = s.parse_rows(table["org"][key])[0]
        row[25], row[111] = "battle/marker/test", "battle/action/summon"
        table["org"][key] = csv_row(row)
    raw.files[s.GENERAL_BOSS] = codec.build_node(table)
    raw.files[FUNNEL] = codec.build_node({"funnel": {"100": "1,battle/action/funnel"}})
    raw.files["battle/action/summon.action.dsl.amf3.deflate"] = encoded(["SpawnFunnel", ["Funnel", "funnel"]])
    raw.files["battle/action/funnel.action.dsl.amf3.deflate"] = encoded(["ResolveByElement", "battle/effect/shot", 255])
    raw.files["battle/marker/test.timeline.amf3.deflate"] = encoded(
        {"points": [{"path": "enemy_action1", "frames": [{"data": [1]}]}]})
    draft = editor.apply("new", request())["changeset"]
    preview = editor.preview("new", request(parameters={"recommendedElement": 2}))
    assert not preview["ok"], preview
    assert "预载" in preview["checks"][0]["message"]
    draft["changes"][0]["params"]["requests"][0]["parameters"] = {"recommendedElement": 2}
    with pytest.raises(ValueError, match="预载"):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_new_reward_missing_client_key_rejected_inside_preview_and_compile(tmp_path, monkeypatch):
    import wf.studio.boss as bridge
    editor = fixture_editor(tmp_path)
    draft = editor.apply("new", request())["changeset"]
    original = bridge.create_shared

    def corrupt(state, req, **kwargs):
        ids = original(state, req, **kwargs)
        table = state.table(s.SCORE_REWARD)
        del table[ids["reward"]]
        state.trees[s.SCORE_REWARD] = table
        state.client[s.SCORE_REWARD] = codec.build_node(table)
        return ids

    monkeypatch.setattr(bridge, "create_shared", corrupt)
    preview = editor.preview("new", request())
    assert not preview["ok"] and "奖励" in preview["checks"][0]["message"]
    with pytest.raises(ValueError, match="奖励"):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)


def test_existing_event_or_folder_id_rejected_in_editor_preview(tmp_path):
    editor = fixture_editor(tmp_path)
    for ids in ({"event": "2081"}, {"event": "2100", "node": "4"}):
        preview = editor.preview("new", request(ids=ids))
        assert not preview["ok"] and "collision" in preview["checks"][0]["message"]


def test_level_without_native_enemy_band_blocks_preview_and_compile(tmp_path):
    editor = fixture_editor(tmp_path)
    preview = editor.preview("new", request(parameters={"level": 999}))
    assert not preview["ok"] and "U_3be147" in preview["checks"][0]["message"]
    draft = editor.apply("new", request())["changeset"]
    draft["changes"][0]["params"]["requests"][0]["parameters"] = {"level": 999}
    with pytest.raises(ValueError, match="U_3be147"):
        compile_boss(editor.source, editor.store, draft, server_dir=editor.server_dir)
