"""Negative controls for server reward/client key reconciliation."""
import json
from types import SimpleNamespace

import pytest

from wf.deliver.prepush_base import Report
from wf.deliver.prepush_companion import check_server_rewards
from wf.deliver.prepush_rewards import SERVER_REWARD_PATHS

SCORE = "assets/score_reward_cnmod.json"
RARE = "assets/rare_score_reward_cnmod.json"


def raw(groups):
    return json.dumps(groups).encode()


def check(changes, tables, before=None):
    baseline = dict.fromkeys(SERVER_REWARD_PATHS)
    baseline.update(before or {})
    view = SimpleNamespace(table=lambda path: tables.get(path.removeprefix("master/reward/").removesuffix(".orderedmap")))
    report = Report(set())
    evidence = check_server_rewards(view, report, changes, baseline)
    return report, evidence


@pytest.mark.parametrize("name,target", [("score_reward", SCORE), ("rare_score_reward", RARE)])
def test_new_missing_group_or_position_is_error(name, target):
    for client in ({}, {"8": {"1": "existing"}}):
        report, evidence = check({target: raw({"8": [{"type": 0}, {"type": 0}]})}, {name: client})
        assert report.count("ERROR") >= 1
        assert any(f"{name}:8/2" in item.fid for item in report.items)
        assert evidence["executed"] and evidence["checked_rows"] == 2


@pytest.mark.parametrize("edited", [False, True])
def test_existing_row_including_modified_row_is_warning(edited):
    old = {"8": [{"type": 0, "count": 1}]}
    new = {"8": [{"type": 0, "count": 2 if edited else 1}]}
    report, _ = check({SCORE: raw(new)}, {}, {SCORE: raw(old)})
    assert report.count("ERROR") == 0 and report.count("WARN") == 1


def test_append_to_existing_group_is_new_and_explicit_positions_are_used():
    before = {SCORE: raw({"8": [{"position": 3, "type": 0}]})}
    changes = {SCORE: raw({"8": [{"position": 3, "type": 0}, {"position": 7, "type": 0}]})}
    report, _ = check(changes, {"score_reward": {"8": {"1": "wrong"}}}, before)
    assert [(f.level, f.fid.rsplit(":", 1)[1]) for f in report.items] == [("WARN", "8/3"), ("ERROR", "8/7")]


def test_rare_reference_needs_group_and_every_emittable_position():
    changes = {SCORE: raw({"8": [{"type": 1, "id": 9}]})}
    before = {RARE: raw({"9": [{"type": 0}, {"type": 0}]})}
    tables = {"score_reward": {"8": {"1": "rare"}}, "rare_score_reward": {"9": {"1": "item"}}}
    report, _ = check(changes, tables, before)
    assert report.count("ERROR") == 1 and "rare_score_reward:9/2" in report.items[0].fid
    tables["rare_score_reward"] = {}
    report, _ = check(changes, tables, before)
    assert any(f.fid.endswith("rare_score_reward:9") for f in report.items)


def test_cnmod_whole_group_override_on_server_and_candidate_client():
    before = {"assets/score_reward.json": raw({"8": [{"type": 0}]})}
    changes = {SCORE: raw({"8": [{"type": 0}, {"type": 0}]})}
    tables = {"score_reward": {"8": {"1": "old"}},
              "score_reward_cnmod": {"8": {"1": "new", "2": "added"}}}
    report, _ = check(changes, tables, before)
    assert not report.items
    # The baseline base row was already live: moving it into _cnmod is not new.
    report, _ = check(changes, {}, before)
    assert [f.level for f in report.items] == ["WARN", "ERROR"]
    # Server _cnmod overrides whole groups, not nested rows.
    masked = {"assets/score_reward.json": raw({"8": [{"type": 0}, {"type": 0}]})}
    report, evidence = check(masked, {}, {SCORE: raw({"8": [{"type": 0}]})})
    assert not report.items and evidence["checked_rows"] == 0


def test_rare_positions_follow_runtime_array_index_not_position_field():
    report, _ = check({RARE: raw({"9": [{"position": 99, "type": 0}]})},
                      {"rare_score_reward": {"9": {"1": "item"}}})
    assert not report.items


def test_removing_cnmod_override_checks_newly_exposed_base_rows():
    before = {SCORE: raw({"8": [{"type": 0}]}),
              "assets/score_reward.json": raw({"8": [{"type": 0}, {"type": 0}]})}
    report, evidence = check({SCORE: raw({})}, {"score_reward": {"8": {"1": "item"}}}, before)
    assert evidence["checked_rows"] == 2
    assert report.count("ERROR") == 1 and report.items[0].fid.endswith("score_reward:8/2")


@pytest.mark.parametrize("groups", [[], {"8": {}}, {"8": ["bad"]},
                                  {"8": [{"position": 0}]},
                                  {"8": [{"position": 1}, {"position": 1}]}])
def test_malformed_reward_inputs_do_not_silently_pass(groups):
    with pytest.raises(ValueError):
        check({SCORE: raw(groups)}, {})


def test_unrelated_server_changes_are_explicitly_not_applicable():
    report, evidence = check({"assets/cdndata/character_text.json": raw({})}, {})
    assert not report.items and evidence == {"executed": True, "server_targets": [],
        "checked_rows": 0, "server_baseline_complete": True}


def test_delivery_gate_records_reward_failure_and_execution(tmp_path):
    import wf_quest_lib as nodes
    from wf.deliver.build import build_delivery
    from wf.deliver.changeset import sha256

    source, server = tmp_path / "source", tmp_path / "server"
    source.mkdir()
    server.mkdir()
    client = nodes.build_node({"8": {"1": "item"}})
    rewards = raw({"8": [{"type": 0}, {"type": 0}]})
    (source / "client").write_bytes(client)
    (source / "rewards").write_bytes(rewards)
    doc = {"schema": "wf-change-set/1", "id": "rewards", "name": "rewards", "slug": "rewards",
           "created_at": "2026-10-18", "from_version": "1.4.232", "to_version": "1.4.233",
           "local_test_only": True, "members": [{"root": "common",
               "logical_path": "master/reward/score_reward.orderedmap", "source": "client",
               "sha256": sha256(client), "before_sha256": None}],
           "server_changes": [{"target": SCORE, "source": "rewards",
               "sha256": sha256(rewards), "before_sha256": None}]}
    changeset = source / "changeset.json"
    changeset.write_text(json.dumps(doc), "utf-8")
    out = tmp_path / "out"
    delivery = build_delivery(changeset, out, server_dir=server, no_baseline_i_know=True)
    report = json.loads((out / "prepush.json").read_text("utf-8"))
    assert delivery["prepush"]["exit_code"] == 1
    assert report["companion_reward_keys"]["executed"] is True
    assert report["companion_reward_keys"]["server_baseline_complete"] is True
    assert any(f["level"] == "ERROR" and f["fid"].endswith("score_reward:8/2") for f in report["findings"])
