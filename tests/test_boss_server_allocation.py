"""Server-only identities must prevent allocation and reward shadowing."""
import json

import pytest

from wf.boss.template import REWARD_FILES, allocate, clone_rewards
from test_boss_edit_review import edit_state


@pytest.mark.parametrize("target", [*REWARD_FILES, "assets/hard_multi_event_quest.json"])
def test_server_only_key_advances_automatic_allocation_and_rejects_requested_block(tmp_path, target):
    state = edit_state(tmp_path)
    path = tmp_path / target
    values = json.loads(path.read_text("utf-8")) if path.exists() else {}
    key = "2100001" if "hard_multi" in target else "12202100"
    values[key] = {"retained": True}
    path.write_text(json.dumps(values), encoding="utf-8")
    original = path.read_bytes()
    assert allocate(state)["event"] == "2101"
    with pytest.raises(ValueError, match="collision"):
        allocate(state, {"event": "2100"})
    assert path.read_bytes() == original and state.client == {} and state.servers == {}


@pytest.mark.parametrize("target", REWARD_FILES)
def test_reward_clone_rejects_base_or_cnmod_collision_before_mutation(tmp_path, target):
    state = edit_state(tmp_path)
    path = tmp_path / target
    values = json.loads(path.read_text("utf-8"))
    values["12202100"] = [{"existing": True}]
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError, match="server reward ID collision"):
        clone_rewards(state, {"reward": "12202100"})
    assert state.client == {} and state.servers == {}


def test_allocation_reads_candidate_server_keys_as_well_as_baseline(tmp_path):
    state = edit_state(tmp_path)
    state.set_server_keys("assets/score_reward_cnmod.json", {"12202100": []}, new=True)
    state.set_server_keys("assets/hard_multi_event_quest.json", {"2101001": {}}, new=True, required=False)
    assert allocate(state)["event"] == "2102"
