"""Independent regression cases for shared-battle authoring boundaries."""
import json

import pytest

import wf_quest_lib as codec
from wf.boss import schema as s
from wf.boss.edit_state import BossEditState, merge_keys
from wf.boss.parameters import apply_values, edit_parameters, BGM_GROUP
from wf.boss.template import allocate, clone_rewards, template_rows
from test_boss_model import Source, csv_row, row, source


class RawSource(Source):
    def read_raw(self, logical):
        if logical not in self.files:
            raise FileNotFoundError(logical)
        return self.files[logical], "fixture"


def edit_state(tmp_path):
    initial = source()
    raw = RawSource({})
    raw.files = initial.files
    quest = codec.parse_node(raw.files[s.QUEST_TABLES["hard_multi"]])["2081"]["1"]
    values = s.parse_rows(quest)[0]
    values[0] = "1006001"
    raw.files[s.QUEST_TABLES["hard_multi"]] = codec.build_node({"1006": {"1": csv_row(values)}})
    raw.files[s.EVENT] = codec.build_node({"1006": row(26, {0: "official", 2: "Official", 23: "2025-01-01"})})
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "score_reward.json").write_text(json.dumps({"501": [{"type": 1, "id": 701, "rate": 0.2}]}), encoding="utf-8")
    (assets / "rare_score_reward.json").write_text(json.dumps({"701": [{"id": 55, "count": 1}]}), encoding="utf-8")
    (assets / "score_reward_cnmod.json").write_text("{}", encoding="utf-8")
    (assets / "rare_score_reward_cnmod.json").write_text("{}", encoding="utf-8")
    return BossEditState(raw, server_dir=tmp_path)


def test_rare_reward_clone_uses_group_column_six_and_preserves_probability(tmp_path):
    state = edit_state(tmp_path)
    clone_rewards(state, {"reward": "12202100"})
    values = s.parse_rows(state.table(s.SCORE_REWARD)["12202100"]["1"])[0]
    assert values[6:8] == ["12202100", "0.2"]
    assert state.table(s.RARE_SCORE_REWARD)["12202100"] == state.table(s.RARE_SCORE_REWARD)["701"]
    server = json.loads(state.servers["assets/score_reward_cnmod.json"])
    assert server["12202100"][0]["id"] == 12202100


def test_new_master_overlay_is_readable_without_a_baseline_file(tmp_path):
    state = edit_state(tmp_path)
    logical = "master/battle/new_workshop_table.orderedmap"
    state.set_leaf(logical, ("new",), "a,b", new=True)
    assert codec.parse_node(state.raw(logical)) == {"new": "a,b"}
    assert logical not in state.original


def test_template_rejects_bgm_missing_from_view(tmp_path):
    state = edit_state(tmp_path)
    ids = allocate(state)
    with pytest.raises(ValueError, match="BGM|bgm"):
        template_rows(state, {"parameters": {"bgm": "no_such_bgm"}}, ids)


def test_existing_unused_bgm_group_is_accepted(tmp_path):
    state = edit_state(tmp_path)
    state.base.files[BGM_GROUP] = codec.build_node({"bgm": "2,,bgm/test/current", "unused": "2,,bgm/test/unused"})
    edit_parameters(state, "hard_multi:1006/1", {"parameters": {"bgm": "unused"}})
    values = s.parse_rows(state.table(s.QUEST_TABLES["hard_multi"])["1006"]["1"])[0]
    assert values[111] == "unused"
    assert template_rows(state, {"parameters": {"bgm": "unused"}}, allocate(state))["quest"][111] == "unused"


def test_existing_audio_cannot_substitute_for_missing_bgm_group(tmp_path):
    state = edit_state(tmp_path)
    state.base.files["bgm/audio_only.mp3"] = b"existing audio bytes"
    with pytest.raises(ValueError, match="BGM group"):
        edit_parameters(state, "hard_multi:1006/1", {"parameters": {"bgm": "audio_only"}})
    with pytest.raises(ValueError, match="BGM group"):
        template_rows(state, {"parameters": {"bgm": "audio_only"}}, allocate(state))


def test_scene_edit_accepts_namespaced_selector_and_repeat_edit(tmp_path):
    state = edit_state(tmp_path)
    before = state.table(s.FIELD_DATA)["org_hard"]
    edit_parameters(state, "hard_multi:1006/1", {"parameters": {"scene": "field"}})
    edit_parameters(state, "hard_multi:1006/1", {"parameters": {"scene": "field"}})
    values = s.parse_rows(state.table(s.QUEST_TABLES["hard_multi"])["1006"]["1"])[0]
    assert ":" not in values[110] and "/" not in values[110]
    assert state.table(s.FIELD_DATA)["org_hard"] == before


@pytest.mark.parametrize("value", ["garbage", float("nan"), float("inf"), True, -1, 0])
def test_numeric_parameter_errors_are_user_errors(value):
    with pytest.raises(ValueError):
        apply_values([""] * 130, "hard_multi", {"hpMultiplier": value})


def test_server_key_merge_keeps_unrelated_raw_value_bytes():
    original = b'{\n "keep" : { "formatted" : [ 1, 2, 3 ] },\n "edit": {"x":1}\n}'
    result = merge_keys(original, {"edit": {"x": 2}, "add": {"z": 3}})
    assert b'{ "formatted" : [ 1, 2, 3 ] }' in result
    assert json.loads(result) == {"keep": {"formatted": [1, 2, 3]}, "edit": {"x": 2}, "add": {"z": 3}}


def test_collision_allocation_checks_actual_client_rows(tmp_path):
    state = edit_state(tmp_path)
    with pytest.raises(ValueError, match="collision"):
        allocate(state, {"event": "1006"})
    with pytest.raises(ValueError, match="collision"):
        allocate(state, {"event": "2100", "node": "4"})
