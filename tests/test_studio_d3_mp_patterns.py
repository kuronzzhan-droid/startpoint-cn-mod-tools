"""Multiplayer patterns follow client constructor/column shapes, without local assets."""
import copy
import json

import pytest

from wf.boss.esdl import transform
from wf.rules.multiplayer_patterns import BASIS, scan_tree

ESDL = "battle/enemy/boss/example.esdl.amf3.deflate"
ACTION = "battle/action/enemy/action/example/example$attack"
STATES = "master/battle/boss/general_boss_state.orderedmap"
WATCH = "master/battle/boss/general_enemy_watch.orderedmap"


def probability(weight=1):
    return ["Command", ["ConditionalsProbability", ["Block", [
        ["Block", [["Command", ["ProbabilityWeight", weight]], ["Block", []]]],
        ["Block", [["Command", ["ProbabilityWeight", 2]], ["Block", []]]],
    ]]]]


def standard(state=None, **form):
    return {"forms": [{"states": [state or {}], **form}]}


def row(**columns):
    result = [""] * 54
    for key, value in columns.items():
        result[int(key.removeprefix("c"))] = value
    return result


def test_action_local_probability_has_runtime_evidence_and_no_mutation():
    tree = ["Block", [probability(), probability(5)]]
    before = copy.deepcopy(tree)
    hits = scan_tree(tree, ACTION)
    assert len(hits) == 2 and tree == before
    assert all(h["rule"] == "multiplayer.random" and h["blocking"] is False for h in hits)
    assert "ActionManagerImpl.as:154-159" in hits[0]["source"]
    assert hits[0]["fingerprint"] != hits[1]["fingerprint"]
    assert hits[0]["location"] == ACTION + "#/1/0/1"


@pytest.mark.parametrize("name", ["Random", "RandomInt", "RandomFloat", "RandomRange", "RandomSelect", "LocalRandom", "Math.random", "SetLocalState", "SetLocalVariable"])
def test_unsupported_constructor_guesses_do_not_generate_hints(name):
    assert scan_tree([name, 1, 3], ACTION) == []


def test_words_sync_flags_and_coordinate_enums_are_not_evidence():
    tree = {"sync": False, "synced": False, "synchronized": False,
            "events": "SomebodyDead", "formEvents": ["untyped"],
            "text": "Math.random() Std.random(5)", "coords": [["EF"], ["GH", -18], ["CD"]]}
    assert scan_tree(tree, ACTION) == []
    assert scan_tree(["ConditionalsProbability", ["Block", []]], ACTION) == []


def test_synced_script_variables_and_transition_send_flag_are_not_unsynced_state():
    tree = standard({"synchronization": False,
                     "battleScript1": ["SetVariableValue", "counter", ["Number", 1]],
                     "battleScript2": ["SetGlobalValue", "counter", ["Number", 1]]})
    assert scan_tree(tree, ESDL) == []
    assert "6647-6648" in BASIS and "synchronization=false" in BASIS


@pytest.mark.parametrize("transition", [
    ["A", [1, 2]], ["B", [1, 2]], ["C", [1, 2]],
    ["D", [{"state": 1, "weight": ["Value", 1]}, {"state": 2, "weight": ["Value", 3]}]],
])
def test_typed_transition_candidates_use_shared_seed_wording(transition):
    hits = scan_tree(standard({"next": ["QS", ["Pure", transition]]}), ESDL)
    assert len(hits) == 1 and hits[0]["rule"] == "multiplayer.state_random"
    assert "共享基种" in hits[0]["message"] and "GeneralEnemyStateChooser.as:30,54-62" in hits[0]["source"]
    assert scan_tree({"next": ["D", [{"state": 1}, {"state": 2}]]}, ACTION) == []


def test_single_target_and_repeated_identical_targets_are_not_random_branches():
    assert scan_tree(standard({"next": ["QS", ["Pure", ["A", [1, 1]]]]}), ESDL) == []
    assert scan_tree(standard({"next": ["QS", ["Pure", ["D", [{"state": 1, "weight": ["Value", 1]}]]]]}), ESDL) == []


def test_legacy_next_and_standard_watch_choices_are_scanned():
    tree = standard({"next": ["LS", ["Always", [1, 2]]]},
                    watches=[{"content": ["ChangeState", [2, 3], True]}])
    hits = scan_tree(tree, ESDL)
    assert len(hits) == 2
    assert all(h["rule"] == "multiplayer.state_random" for h in hits)


def test_form_death_is_typed_and_records_synchronized_event_deduplication():
    hits = scan_tree(standard(events=[{"kind": ["SomebodyDead"], "processes": ["Pure", {"contents": []}]}]), ESDL)
    assert len(hits) == 1 and hits[0]["rule"] == "multiplayer.death_event"
    assert "executedDeadEvents" in hits[0]["message"] and "6647" in hits[0]["source"]
    assert scan_tree(standard(events=[{"kind": ["unsupported"], "processes": None}]), ESDL) == []


def test_funnel_death_condition_and_count_are_scanned():
    tree = standard({"next": ["LS", ["GeneralFunnelDead", [1], [2], ["None"], ["funnel"]]],
                     "battleScript1": ["FunctionCall", ["GetFunnelDeadCount"], [["GetVariableValue", "__fid0"]]]})
    hits = scan_tree(tree, ESDL)
    assert len(hits) == 2 and all(h["rule"] == "multiplayer.death_event" for h in hits)
    assert "3109-3125" in hits[0]["source"]


def test_general_rows_scan_all_evidenced_transition_columns():
    data = row(c16="0", c21="a,b", c22="0", c26="a,b", c29="1", c31="a,b", c32="a,b",
               c40="a,b", c41="a,b", c42="a,b", c43="a,b")
    hits = scan_tree({"routine": {"state": [data]}}, STATES)
    assert len(hits) == 8
    assert {h["location"].rsplit("/", 1)[1] for h in hits} == {"21", "26", "31", "32", "40", "41", "42", "43"}
    ignored = row(c16="(None)", c21="a,b", c22="(None)", c26="a,b", c29="0", c31="one", c32="unused,other")
    assert scan_tree({"routine": {"state": [ignored]}}, STATES) == []


def test_general_death_and_watch_transition_require_correct_discriminants():
    assert scan_tree({"r": [row(c29="17", c30="funnel", c31="a", c32="b")]}, STATES)[0]["rule"] == "multiplayer.death_event"
    selected = {"1": {"boss": {"r": [row(c14="0", c15="a,b")]}}}
    assert scan_tree(selected, WATCH)[0]["location"].endswith("/1/boss/r/0/15")
    assert scan_tree({"r": [row(c14="5", c15="a,b")]}, WATCH) == []


@pytest.mark.parametrize("kind", ["11", "18"])
def test_general_backtrack_reads_only_fallback_column(kind):
    assert scan_tree({"r": [row(c29=kind, c31="unused,other", c32="one")]}, STATES) == []
    hits = scan_tree({"r": [row(c29=kind, c31="unused,other", c32="one,two")]}, STATES)
    assert len(hits) == 1 and hits[0]["location"].endswith("/32")


@pytest.mark.parametrize("logical,column,gate", [(STATES, 27, {}), (STATES, 30, {"c29": "10"}), (WATCH, 8, {"c7": "7"}), (WATCH, 22, {"c14": "3"})])
def test_table_script_cells_decode_real_typed_json(logical, column, gate):
    expression = ["FunctionCall", ["GetFunnelDeadCount"], [["GetVariableValue", "__fid0"]]]
    serialized = json.dumps(transform(expression, "pinball.common.data.battle.script.BattleScriptExpression", encode=True))
    hits = scan_tree({"r": [row(**gate, **{f"c{column}": serialized})]}, logical)
    assert len(hits) == 1 and hits[0]["rule"] == "multiplayer.death_event"
    assert hits[0]["location"].endswith(f"/r/0/{column}")


def test_fingerprint_ignores_path_but_retains_changed_construct():
    left = scan_tree(["Block", [probability()]], ACTION)[0]
    moved = scan_tree(["Block", [["Block", []], probability()]], ACTION)[0]
    changed = scan_tree(["Block", [probability(9)]], ACTION)[0]
    assert left["fingerprint"] == moved["fingerprint"] != changed["fingerprint"]


def test_table_scripts_use_client_numeric_enum_indexes_recursively():
    # Expressions -> SetVariableValue -> FunctionCall(GetFunnelDeadCount, GetVariableValue).
    serialized = json.dumps([6, [[2, "count", [3, [20], [[1, "__fid0"]]]], [2, "flag", [0, 1]]]])
    hits = scan_tree({"r": [row(c27=serialized)]}, STATES)
    assert len(hits) == 1 and hits[0]["rule"] == "multiplayer.death_event"
    assert hits[0]["location"].endswith("/27/1/0/2")


@pytest.mark.parametrize("serialized", ["{bad json", "[999]", '[2,"missing argument"]'])
def test_bad_script_cell_preserves_prior_and_later_hits_with_exact_incomplete_location(serialized):
    tree = {"r": [row(c29="0", c31="a,b", c27=serialized), row(c29="0", c31="b,c")]}
    hits = scan_tree(tree, STATES)
    assert sum(h["rule"] == "multiplayer.state_random" for h in hits) == 2
    incomplete = [h for h in hits if h["rule"] == "multiplayer.incomplete"]
    assert len(incomplete) == 1 and incomplete[0]["blocking"] is False
    assert incomplete[0]["location"] == STATES + "#/r/0/27"
    assert incomplete[0]["location"] in incomplete[0]["issues"][0]


@pytest.mark.parametrize("family", ["funnel/general_funnel_state", "zako/general_zako_state"])
def test_spawned_enemy_state_tables_use_their_own_client_parser_evidence(family):
    logical = "master/battle/" + family + ".orderedmap"
    hits = scan_tree({"r": [row(c29="0", c31="a,b")]}, logical)
    assert len(hits) == 1 and hits[0]["rule"] == "multiplayer.state_random"
    assert ("GeneralFunnelStateValues" if "funnel" in family else "GeneralZakoStateValues") in hits[0]["source"]
