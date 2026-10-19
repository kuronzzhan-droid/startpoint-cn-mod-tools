"""Boss timeline HTTP contract, state timing and fractional trial regressions."""
import copy
import json

import pytest
import wf_quest_lib as codec

from test_boss_behavior import behavior_editor, request
from test_boss_model import csv_row
from test_studio_drafts import live, _request
from test_studio_timeline import cmd, root, wait, show
from wf.boss import schema as s
from wf.boss.behavior_wire import compress, write_tree
from wf.boss.esdl import decode_esdl, transform
from wf.studio import drafts
from wf.studio.boss import compile_boss
from wf.studio.server import StudioApp

QUEST = "hard_multi:1006/1"
URL = "/api/boss/hard_multi%3A1006%2F1/timeline-summary"


def app_for(editor, tmp_path):
    return StudioApp(editor.source, drafts=drafts.DraftStore(tmp_path / "app"), server_dir=editor.server_dir)


def install_programs(editor):
    tree = root(wait(5, cmd("ShakeCamera", 1)))
    for name in ("one", "two"):
        editor.source.view.files[f"battle/action/{name}.action.dsl.amf3.deflate"] = compress(write_tree(tree))


def install_standard(editor):
    view = editor.source.view
    tree = {"gender": "Unknown", "initialPosition": ["Absolute", "p0"], "marker": "battle/marker/test",
            "action_base_path": "battle/action/", "animations": ["idle"], "forms": [{"states": [
                {"canonicalPath": 0, "animation": 0, "terminationCondition": ["TimeElapsed", ["Frame", 60]],
                 "trial": ["DamageCheck", {"percentage": 5.0}],
                 "actions": [{"filePath": "one", "event": ["OnStateEnter"]},
                             {"filePath": "two", "event": ["OnStateExit"]}]},
                {"canonicalPath": 1, "animation": 0, "terminationCondition": ["MovementCompleted"],
                 "actions": [{"filePath": "one", "event": ["OnStateExit"]}]}]}]}
    logical = "battle/enemy/boss/test.esdl.amf3.deflate"
    view.files[logical] = compress(write_tree(transform(tree, encode=True)))
    view.files[s.STANDARD_BOSS] = codec.build_node({"org": {"100": "Boss,battle/enemy/boss/test"}})
    zones = codec.parse_node(view.files[s.ZONE])
    cells = s.parse_rows(zones["zone"]["0"])[0]
    cells[23] = cells[25] = "0"
    zones["zone"]["0"] = csv_row(cells)
    view.files[s.ZONE] = codec.build_node(zones)
    return logical


def test_general_http_contract_offsets_dsl_events_and_is_readonly(tmp_path):
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    app = app_for(editor, tmp_path)
    before = copy.deepcopy(editor.source.view.files)
    response = app.dispatch("GET", URL, {})
    assert response.status == 200
    payload = json.loads(response.body)
    moves = payload["moves"]
    idle = next(m for m in moves if m["slot"] == 1 and m["timeline"]["stateInterval"]["id"] == "1/idle")
    timeline = idle["timeline"]
    assert all(key in timeline for key in ("events", "lanes", "arms", "unknown", "issues", "subprograms"))
    assert timeline["stateInterval"]["triggerFrame"] == 3
    assert timeline["stateInterval"]["end"] == 60
    assert next(e["t"] for e in timeline["events"] if e["kind"] == "ShakeCamera") == 8
    assert timeline["timeOrigin"] == "state_entry"
    assert timeline["attribution"]["label"] == "敌方攻击"
    assert any(i["level"] == "待验证" and "裸路径" in i["text"] for i in timeline["issues"])
    assert len({m["name"] for m in moves}) == len(moves)
    assert editor.source.view.files == before
    assert not app.boss.store.root.exists()


def test_standard_entry_exit_and_unknown_exit_are_not_confused(tmp_path):
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    install_standard(editor)
    payload = json.loads(app_for(editor, tmp_path).dispatch("GET", URL, {}).body)
    timelines = [m["timeline"] for m in payload["moves"]]
    assert [t["stateInterval"]["triggerFrame"] for t in timelines] == [0, 60, None]
    assert [next(e["t"] for e in t["events"] if e["kind"] == "ShakeCamera") for t in timelines] == [5, 65, 5]
    assert timelines[-1]["timeOrigin"] == "action_entry"
    assert timelines[-1]["stateInterval"]["end"] is None


def test_missing_program_and_unmapped_slot_are_visible(tmp_path):
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    view = editor.source.view
    del view.files["battle/action/one.action.dsl.amf3.deflate"]
    del view.files["battle/marker/test.timeline.amf3.deflate"]
    moves = json.loads(app_for(editor, tmp_path).dispatch("GET", URL, {}).body)["moves"]
    assert len(moves) == 2
    missing = next(m["timeline"] for m in moves if m["slot"] == 1)
    assert missing["stateInterval"]["triggerFrame"] is None
    assert missing["events"] == []
    assert any(i["level"] == "问题" and "缺少动作" in i["text"] for i in missing["issues"])


def test_general_master_element_is_converted_to_internal_effect_element(tmp_path):
    editor = behavior_editor(tmp_path)
    command = show("属性特效", "battle/effect/test", -17, ["PlayOnlyFirstSequence"])
    command[1][2] = ["ResolveByElement", "battle/effect/test", 255]
    editor.source.view.files["battle/action/one.action.dsl.amf3.deflate"] = compress(write_tree(root(command)))
    moves = json.loads(app_for(editor, tmp_path).dispatch("GET", URL, {}).body)["moves"]
    effects = [e for m in moves for e in m["timeline"]["events"] if e["kind"] == "effect"]
    assert effects and all(e["path"] == "battle/effect/test/test_green/test_green" for e in effects)


def test_state_placement_shifts_absolute_times_but_preserves_local_durations():
    from wf.studio.boss_timeline import _place
    original = {"events": [{"t": 5, "dur": 15, "hiddenAt": 20, "erasedAt": 18,
                            "motions": [{"t": 7}], "hits": {"times": [0, 5]}}],
                "subprograms": [{"t": 10, "timeline": {"events": [{"t": 2}]}}],
                "duration": 20, "notes": []}
    actual = _place(original, {"id": "idle", "end": 60}, {"begin": 30})
    event = actual["events"][0]
    assert (event["t"], event["hiddenAt"], event["erasedAt"], event["motions"][0]["t"]) == (35, 50, 48, 37)
    assert event["dur"] == 15 and event["hits"]["times"] == [0, 5]
    assert actual["subprograms"][0] == {"t": 40, "timeline": {"events": [{"t": 2}]}}
    assert original["events"][0]["t"] == 5


def test_same_enemy_in_different_waves_keeps_both_timelines(tmp_path):
    from wf.boss.reader import BossReader
    from wf.studio.boss_timeline import timeline_summary
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    document = BossReader(editor.source).show(QUEST)
    another = copy.deepcopy(document["enemies"][0])
    another["wave"] = "1"
    document["enemies"].append(another)
    assert {m["wave"] for m in timeline_summary(editor.source, document)["moves"]} == {"0", "1"}


def test_initialization_and_watch_roots_are_visible_without_fake_triggers(tmp_path):
    from wf.boss.behavior_identity import WATCH
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    view = editor.source.view
    rows = codec.parse_node(view.files[s.GENERAL_BOSS])
    cells = s.parse_rows(rows["org"]["100"])[0]
    cells[109] = "battle/action/init"
    rows["org"]["100"] = csv_row(cells)
    view.files[s.GENERAL_BOSS] = codec.build_node(rows)
    view.files[WATCH] = codec.build_node({"1": {"org": {"routine": {
        "2": {"funnel": {"0": "0,phase2,battle/action/watched"}}}}}})
    for name in ("init", "watched"):
        view.files[f"battle/action/{name}.action.dsl.amf3.deflate"] = view.files["battle/action/one.action.dsl.amf3.deflate"]
    moves = json.loads(app_for(editor, tmp_path).dispatch("GET", URL, {}).body)["moves"]
    extras = [m["timeline"] for m in moves if m["timeline"]["program"] in {"battle/action/init", "battle/action/watched"}]
    assert len(extras) == 2
    assert all(t["stateInterval"]["triggerFrame"] is None for t in extras)


def test_summary_reads_draft_candidate(tmp_path):
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    app = app_for(editor, tmp_path)
    app.boss.editor.apply(QUEST, request(state="idle", intervalFrames=90))
    payload = json.loads(app.dispatch("GET", URL, {}).body)
    assert any(m["timeline"]["stateInterval"]["end"] == 90 for m in payload["moves"])
    assert not any(m["timeline"]["stateInterval"]["end"] == 60 for m in payload["moves"])


def test_summary_preserves_host_guard(live):
    port, guard, _ = live
    code, body = _request(port, "GET", "/api/boss/7/timeline-summary", headers={"Host": f"outside.invalid:{port}"})
    assert code == 403 and guard.token.encode() not in body


def test_fractional_damage_trial_passes_http_schema_and_compile(tmp_path):
    editor = behavior_editor(tmp_path)
    install_programs(editor)
    install_standard(editor)
    app = app_for(editor, tmp_path)
    body = request(state="0", trialThreshold=6.25)
    assert not drafts.schema_errors(body, "bossRequest")
    response = app.dispatch("POST", "/api/boss/drafts/hard_multi%3A1006%2F1", {}, body)
    assert response.status == 200, response.body
    draft = app.boss.store.save(QUEST)
    compiled = compile_boss(editor.source, app.boss.store, draft, server_dir=editor.server_dir)
    logical = next(path for path in compiled["client"] if path.endswith(".esdl.amf3.deflate"))
    trial = decode_esdl(compiled["client"][logical])["tree"]["forms"][0]["states"][0]["trial"]
    assert trial == ["DamageCheck", {"percentage": 6.25}]


@pytest.mark.parametrize("value", [0, -1, 100.01])
def test_damage_trial_rejects_out_of_range_values(tmp_path, value):
    editor = behavior_editor(tmp_path)
    install_standard(editor)
    assert not editor.preview(QUEST, request(state="0", trialThreshold=value))["ok"]


def test_fractional_general_trial_is_still_rejected_after_schema_change(tmp_path):
    editor = behavior_editor(tmp_path)
    assert not editor.preview(QUEST, request(state="idle", trialThreshold=6.25))["ok"]
