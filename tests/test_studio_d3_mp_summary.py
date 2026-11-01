"""Aggregation and candidate deltas use synthetic, source-shaped constructs."""
import copy

from wf.rules.multiplayer_summary import summarize


def hit(path, fingerprint="same", *, logical="battle/action/test", rule="multiplayer.random"):
    return {"rule": rule, "location": logical + "#" + path, "fingerprint": fingerprint,
            "status": "待验证", "blocking": False, "category": "联机风险",
            "message": "可能有本机随机分支", "source": "ActionEvaluator.as:4940-5016"}


def test_same_file_rule_aggregates_all_hits_with_bounded_examples():
    hits = [hit(f"/{n}") for n in range(1200)]
    before = copy.deepcopy(hits)
    summary = summarize(hits, hits, comparison="baseline")
    assert len(summary) == 1
    assert summary[0]["hit_count"] == 1200
    assert summary[0]["locations"] == [f"battle/action/test#/{n}" for n in range(5)]
    assert summary[0]["new_hit_count"] == 0
    assert "fingerprint" not in summary[0]
    assert not summary[0]["blocking"]
    assert hits == before


def test_delta_counts_added_duplicate_and_changed_argument_but_not_moved_node():
    before = [hit("/0", "A"), hit("/1", "B")]
    candidate = [hit("/7", "A"), hit("/8", "A"), hit("/9", "C")]
    summary = summarize(candidate, before, comparison="candidate")[0]
    assert summary["hit_count"] == 3 and summary["new_hit_count"] == 2
    assert summary["new_locations"] == ["battle/action/test#/8", "battle/action/test#/9"]


def test_group_identity_preserves_different_rules_and_files():
    hits = [hit("/0"), hit("/1", logical="battle/action/other"),
            hit("/2", rule="multiplayer.death_event")]
    summary = summarize(hits, [], comparison="candidate")
    assert len(summary) == 3
    assert sum(c["hit_count"] for c in summary) == sum(c["new_hit_count"] for c in summary) == 3


def test_incomplete_baseline_never_claims_new_hits_known():
    incomplete = {"rule": "multiplayer.incomplete", "message": "bad source", "issues": ["missing DSL"]}
    summary = summarize([hit("/0")], [incomplete], comparison="candidate")
    assert summary[0]["new_hit_count"] is None
    assert summary[0]["baseline_comparison"] == "unavailable"
    assert summary[1]["issues"] == ["草稿基线：missing DSL"]


def test_incomplete_reasons_are_deduplicated_without_losing_successful_hits():
    incomplete = {"rule": "multiplayer.incomplete", "message": "bad source", "blocking": False,
                  "category": "联机风险", "issues": ["missing A", "invalid B"]}
    summary = summarize([hit("/0"), incomplete, incomplete], None, comparison="unavailable")
    assert len(summary) == 2
    assert summary[0]["hit_count"] == 1 and summary[0]["new_hit_count"] is None
    assert summary[1]["issues"] == ["invalid B", "missing A"]
    assert summary[1]["issue_count"] == 2 and not summary[1]["blocking"]


def test_candidate_delta_uses_real_overlay_bytes_without_polluting_original(tmp_path):
    import wf_quest_lib as codec
    from test_boss_behavior import behavior_editor
    from test_boss_model import row
    from test_studio_d3_multiplayer_regressions import RANDOM, ACTION, QUEST
    from wf.boss import schema
    from wf.boss.behavior_wire import compress, write_tree
    from wf.boss.edit_state import BossEditState
    from wf.boss.reader import BossReader
    from wf.rules.multiplayer import check_multiplayer

    editor = behavior_editor(tmp_path)
    # The shared editor fixture predates Zako closure scanning. Supply its
    # declared slime's real state-table shape, so the baseline is complete.
    editor.source.view.files[schema.GENERAL_ZAKO] = codec.build_node({
        "slime": {"100": row(40, {17: "slime_routine"})}})
    editor.source.view.files["master/battle/zako/general_zako_state.orderedmap"] = codec.build_node({
        "slime_routine": {"1": {"idle": row(53, {29: 0, 31: "idle"})}}})
    editor.source.view.files[ACTION] = compress(write_tree(RANDOM))
    state = BossEditState(editor.source)
    document = BossReader(editor.source).show(QUEST)
    source_before = copy.deepcopy(editor.source.view.files)
    state.client[ACTION] = compress(write_tree(["Block", [RANDOM, RANDOM]]))
    original = copy.deepcopy(state.original)
    checks = check_multiplayer(document, state, document)
    actual = next(c for c in checks if c["rule"] == "multiplayer.random")
    assert actual["hit_count"] == 2 and actual["new_hit_count"] == 1
    assert actual["baseline_comparison"] == "candidate"
    assert len(actual["new_locations"]) == 1
    assert state.original == original
    assert editor.source.view.files == source_before
    assert all(not c["blocking"] for c in checks)


def test_baseline_comparison_failure_keeps_candidate_findings(tmp_path, monkeypatch):
    from test_boss_behavior import behavior_editor
    from test_studio_d3_multiplayer_regressions import RANDOM, ACTION, QUEST
    from wf.boss.behavior_wire import compress, write_tree
    from wf.boss.edit_state import BossEditState
    from wf.boss.reader import BossReader
    from wf.rules.multiplayer import check_multiplayer

    editor = behavior_editor(tmp_path)
    document = BossReader(editor.source).show(QUEST)
    state = BossEditState(editor.source)
    state.client[ACTION] = compress(write_tree(RANDOM))
    monkeypatch.setattr(BossReader, "show", lambda *args: (_ for _ in ()).throw(ValueError("missing base")))
    checks = check_multiplayer(document, state)
    actual = next(c for c in checks if c["rule"] == "multiplayer.random")
    assert actual["hit_count"] == 1 and actual["new_hit_count"] is None
    assert any(c["rule"] == "multiplayer.incomplete" and "missing base" in c["message"] for c in checks)
    assert state.original == {} and all(not c["blocking"] for c in checks)
