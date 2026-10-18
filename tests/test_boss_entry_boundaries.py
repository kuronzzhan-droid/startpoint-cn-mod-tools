"""BothBoss entries expose routing, never author combat settings themselves."""
import pytest

import wf_quest_lib as codec
from wf.boss import BossReader, schema as s
from wf.boss.parameters import edit_parameters
from wf.boss.template import template_rows
from test_boss_edit_review import edit_state
from test_boss_model import csv_row, row


def both_state(tmp_path):
    state = edit_state(tmp_path)
    shared = s.parse_rows(state.table(s.QUEST_TABLES["hard_multi"])["1006"]["1"])[0]
    cells = shared[:50] + shared[51:]
    group = {}
    for identity, entry in (("1099001", True), ("1099031", False)):
        values = list(cells)
        values[0], values[122], values[123] = identity, str(entry).lower(), str(not entry).lower()
        group[str(int(identity) % 1000)] = csv_row(values)
    state.base.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({"1": {"99": group}})
    state.base.files[s.BOTH_GROUP] = codec.build_node({"1099001": "1,route"})
    state.base.files[s.BOTH_MAP] = codec.build_node({"route": row(15, {11: "1099031", 13: "1099031", 14: "1099057"})})
    return state


@pytest.mark.parametrize("selector", ["1099001", "boss_battle:1/99/1"])
def test_both_entry_cannot_be_edited_even_for_an_unchanged_value(tmp_path, selector):
    state = both_state(tmp_path)
    with pytest.raises(ValueError, match="BothBoss.*入口"):
        edit_parameters(state, selector, {"parameters": {"level": 100, "hpMultiplier": 2}})
    assert state.client == {} and state.servers == {}


def test_both_entry_cannot_supply_a_shared_battle_template(tmp_path):
    state = both_state(tmp_path)
    with pytest.raises(ValueError, match="BothBoss.*模板来源"):
        template_rows(state, {"sourceQuest": "1099001"}, {})
    assert state.client == {}


def test_five_tier_batch_rejects_an_entry_before_mutating_other_tiers(tmp_path):
    state = both_state(tmp_path)
    table = codec.parse_node(state.base.files[s.QUEST_TABLES["boss_battle"]])
    encounter, entry = table["1"]["99"]["31"], table["1"]["99"]["1"]
    table["1"]["99"] = {str(i): encounter if i < 5 else entry for i in range(1, 6)}
    state.base.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node(table)
    with pytest.raises(ValueError, match="BothBoss"):
        edit_parameters(state, "boss_battle:1/99/1", {"tiers": [{"level": 100}] * 5})
    assert state.client == {}


def test_show_labels_entry_contents_and_resolves_map_targets(tmp_path):
    document = BossReader(both_state(tmp_path)).show("1099001")
    assert document["content_scope"]["label"] == "入口自身，非战斗内容"
    assert document["terrain"]["content_scope"]["combat_content"] is False
    assert document["enemies"] and all(e["content_scope"]["combat_content"] is False for e in document["enemies"])
    hidden = document["routing"]["hidden_quests"]
    assert [q["id"] for q in hidden] == ["1099031", "1099057"]
    assert hidden[0]["selector"] == "boss_battle:1/99/31" and hidden[0]["hidden"]
    assert hidden[0]["map_refs"] == [{"map": "route", "column": 11}, {"map": "route", "column": 13}]
    assert hidden[1]["missing"] is True


def test_field_sources_explicitly_disclaim_cell_level_origin(tmp_path):
    document = BossReader(both_state(tmp_path)).show("1099031")
    semantics = document["quest"]["field_sources_semantics"]
    assert semantics["granularity"] == "whole_leaf"
    assert semantics["column_origin_verified"] is False
    assert all(entry["source"] == document["quest"]["source"] for entry in document["quest"]["field_sources"].values())
    assert "content_scope" not in document
