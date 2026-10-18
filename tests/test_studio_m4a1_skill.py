"""M4 counterexamples: deleted referenced tiers and invalid newly parsed tiers."""
from copy import deepcopy

import pytest

import wf_client_legality
import wf_quest_lib as codec
from wf.balance.rows import TABLES, join_leaf, split_leaf
from wf.studio.ability_references import AWAKE_EVENT, MANA_NODE
from wf.studio.drafts import DraftError
from test_studio_ability import full, skill_row
from test_studio_ability_text import compile_text, setup


def structure(kind, row, *, level="3", count=3, shared=False):
    return {"op": kind, "table": "action_skill", "key": "hero", "level": level,
            "row": 0, "row_count": count, "cells": full(row, kind), "shared_ok": shared}


def references(ed):
    nodes = {"0": {"1": "139985001,0,,,100,1,", "2": "139985002,0,,,100,2,",
                   "3": "139985003,0,,,100,2,", "4": "139985004,0,,,100,0,1"},
             "1": {"5": "139985205,0,,,100,1,"}}
    ed.source.raw[MANA_NODE] = codec.build_node({"139985": nodes, "100": deepcopy(nodes)})
    ed.source.raw[AWAKE_EVENT] = codec.build_node({"139985": "1,2", "100": "3,4"})


def test_delete_lists_all_owners_default_awakening_and_mana_nodes(tmp_path):
    ed, server = setup(tmp_path, shared=True)
    references(ed)
    response = ed.apply("139985", {"operations": [structure("delete_row", skill_row("斩击++"), shared=True)]})
    check = next(c for c in response["checks"] if c["rule"] == "ability.skill-tier-references")
    assert check["status"] == "待验证" and check["beforeCount"] == 3 and check["afterCount"] == 2
    assert not check["unavailableSources"]
    assert check["missingUnawakenedTiers"] == {"139985": [3], "100": [3]}
    for cid in ("139985", "100"):
        refs = [r for r in check["references"] if r["character"] == cid]
        assert len(refs) == 6  # default, awakening, two SLv nodes and two tier nodes
        assert next(r for r in refs if r["kind"] == "default")["level"] == 1
        assert len(next(r for r in refs if r["kind"] == "awakening")["nodes"]) == 2
        assert {tuple(r["path"]) for r in refs if r["kind"].startswith("mana_")} == {
            (cid, "0", "1"), (cid, "0", "2"), (cid, "0", "3"), (cid, "1", "5")}
    result = compile_text(ed, server)
    assert MANA_NODE not in result["client"] and AWAKE_EVENT not in result["client"]
    assert MANA_NODE in response["change"]["params"]["inputSha256"]


def test_insert_warns_even_without_reference_tables_and_validates_new_row(tmp_path):
    ed, _ = setup(tmp_path)
    ed.apply("139985", {"operations": [structure("delete_row", skill_row("斩击++"))]})
    saved = deepcopy(ed.store.load("139985"))
    invalid = skill_row("新档", "150")
    invalid[8] = "999"
    with pytest.raises(DraftError, match="c8.*C7050"):
        ed.apply("139985", {"operations": [structure("insert_row", invalid, count=2)]})
    assert ed.store.load("139985") == saved
    response = ed.apply("139985", {"operations": [structure("insert_row", skill_row("新档", "150"), count=2)]})
    check = next(c for c in response["checks"] if c["rule"] == "ability.skill-tier-references")
    assert check["status"] == "待验证" and check["afterCount"] == 3
    assert set(check["unavailableSources"]) == {MANA_NODE, AWAKE_EVENT}


def test_attach_new_skill_runs_client_legality_for_every_tier(tmp_path):
    ed, _ = setup(tmp_path)
    invalid = skill_row("新档")
    invalid[3] = "not-bool"
    request = {"operations": [{"op": "attach_key", "table": "action_skill", "slot": 0,
                               "key": "new_skill", "old_key": "hero",
                               "levels": {"1": [full(skill_row(), "insert_row")],
                                          "2": [full(invalid, "insert_row")]}}]}
    with pytest.raises(DraftError, match="new_skill/2.*C7101"):
        ed.apply("139985", request)
    assert ed.store.load("139985") is None


@pytest.mark.parametrize("column,value", [(3, "0"), (4, ""), (5, "x"), (6, ""), (8, "2"), (16, "")])
def test_action_skill_required_parser_fields_reject_invalid_values(column, value):
    row = skill_row()
    assert not wf_client_legality.client_legality_problems("action_skill", row)
    row[column] = value
    assert any(f"c{column}" in p for p in wf_client_legality.client_legality_problems("action_skill", row))


def test_action_skill_conditional_fields_and_truncated_rows():
    assert wf_client_legality.client_legality_problems("action_skill", ["name", "desc", "100"])
    row = skill_row()
    row[8:16] = ["1", "1", "30", "40", "0", "0", "0", "45"]
    row[16:24] = ["1", "0", "30", "", "0", "0", "", ""]
    assert not wf_client_legality.client_legality_problems("action_skill", row)
    row[17] = "99"
    assert any("c17" in p for p in wf_client_legality.client_legality_problems("action_skill", row))
