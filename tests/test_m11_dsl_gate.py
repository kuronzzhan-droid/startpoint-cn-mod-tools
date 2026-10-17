"""629 context comes from candidate tables and follows transitive programs."""
import copy
import csv
import io
import json
import zlib

import pytest

import wf_quest_lib as nodes
from wf_dsl import encode_amf3
from wf.dsl import forbidden_629, sanitize_for_629
from wf.dsl.gate import check_629_actions
from wf.dsl.references import ABILITY_TABLES, ACTION_SKILL, DSL_SUFFIX
from wf.paths import REPOSITORY

ABILITY, LEADER = list(ABILITY_TABLES)[:2]
ROOT = "battle/action/skill/action/test$root" + DSL_SUFFIX
CHILD = "battle/action/skill/action/test$child" + DSL_SUFFIX


def csv_row(values):
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="").writerow(values)
    return output.getvalue()


def ability(action=ROOT, *, leader=False, skill="test", kind="629"):
    row = [""] * 126
    row[47], row[70], row[71] = kind, skill, action.removesuffix(DSL_SUFFIX)
    return csv_row(row[:1] + row[3:] if leader else row)


def dsl(*commands):
    tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", list(commands)]]
    return zlib.compress(encode_amf3(tree), wbits=-15)


def data():
    return {ABILITY: nodes.build_node({"1001": ability()}), LEADER: nodes.build_node({}),
            ROOT: dsl(["Command", ["Trace", "safe"]])}


def run(raw, overrides, changed=None):
    return check_629_actions(lambda logical: (raw[logical], "fixture"), overrides=overrides,
                             changed_logicals=set(overrides) if changed is None else changed)


def test_ability_context_catches_dsl_only_change_without_explicit_kind():
    raw = data()
    report = run(raw, {ROOT: dsl(["Command", ["NotifyPowerflipEnd", 0]])})
    assert report["status"] == "问题"
    assert report["findings"][0]["command"] == "NotifyPowerflipEnd"
    assert report["references"][0]["key"] == "1001"


def test_transitive_path_program_and_cycle_are_checked():
    raw = data()
    raw[ROOT] = dsl(["Command", ["Run", CHILD.removesuffix(DSL_SUFFIX)]])
    raw[CHILD] = dsl(["Command", ["Run", ROOT.removesuffix(DSL_SUFFIX)]])
    report = run(raw, {CHILD: dsl(["NotifyPowerflipEnd", 0], ["Run", ROOT.removesuffix(DSL_SUFFIX)])})
    assert report["status"] == "问题"
    assert set(report["checked_programs"]) == {ROOT, CHILD}


def test_changed_leader_row_resolves_skill_c7_when_action_is_absent():
    raw = data()
    raw[ROOT] = dsl(["Command", ["SetPowerFilpSuppress", True]])
    raw[ACTION_SKILL] = nodes.build_node({"test": {"1": csv_row([""] * 7 + [ROOT.removesuffix(DSL_SUFFIX)])}})
    report = run(raw, {LEADER: nodes.build_node({"100": ability("", leader=True)})})
    assert report["status"] == "问题"
    assert report["findings"][0]["command"] == "SetPowerFilpSuppress"


def test_skill_key_change_selects_caller_but_unrelated_skill_does_not():
    raw = data()
    raw[ROOT] = dsl(["RemoveEvent", "*"])
    raw[ACTION_SKILL] = nodes.build_node({"test": {"1": "old"}, "unrelated": {"1": "old"}})
    report = run(raw, {ACTION_SKILL: nodes.build_node({"test": {"1": "new"}, "unrelated": {"1": "old"}})})
    assert report["status"] == "问题"
    report = run(raw, {ACTION_SKILL: nodes.build_node({"test": {"1": "old"}, "unrelated": {"1": "new"}})})
    assert report["status"] == "满足"
    assert report["checked_programs"] == []


def test_unchanged_unsafe_table_key_does_not_block_independent_balance_edit():
    raw = data()
    raw[ROOT] = dsl(["NotifyPowerflipEnd", 0])
    report = run(raw, {ABILITY: nodes.build_node({"1001": ability(), "other": ability(kind="0")})})
    assert report["status"] == "满足"
    assert report["checked_programs"] == []


def test_missing_selected_subprogram_and_missing_callers_block():
    raw = data()
    report = run(raw, {ROOT: dsl(["Run", CHILD.removesuffix(DSL_SUFFIX)])})
    assert report["status"] == "问题"
    assert any(f.get("logical_path") == CHILD for f in report["findings"])
    del raw[ABILITY]
    assert run(raw, {ROOT: dsl()})["status"] == "问题"


@pytest.mark.parametrize("params", [[10], [10, "*"], [10, "*", 123]])
def test_wait_argument_count_does_not_hide_notify_callback(params):
    source = ["Event", ["Wait", *params, ["Block", [["NotifyPowerflipEnd", 0]]]]]
    frozen = copy.deepcopy(source)
    assert forbidden_629(source)[0]["command"] == "Wait(NotifyPowerflipEnd only)"
    assert sanitize_for_629(source) == ["Block", []]
    assert source == frozen


@pytest.mark.parametrize("source", [
    ["RemoveEvent", "*"], ["Event", ["NotifyPowerflipEnd", 0]],
    {"Command": ["SetPowerFilpSuppress", True]},
    {"type": "RemoveEvent", "args": ["*"]},
])
def test_non_command_shapes_cannot_bypass_lifecycle_scan(source):
    assert forbidden_629(source)
    assert sanitize_for_629(source) == ["Block", []]
    assert not forbidden_629(["Command", ["Trace", "RemoveEvent"]])


def test_official_corpus_evidence_has_pinned_provenance_and_zero_pf_commands():
    report = json.loads((REPOSITORY / "docs/m1/official-629-corpus.json").read_text("utf-8"))
    assert report["pinned_baselines_verified"] is True
    assert report["reference_count"] == report["tree_count"] == 3
    assert set(report["lifecycle_counts"].values()) == {0}
    assert all(len(source["sha256"]) == 64 for source in report["sources"].values())
