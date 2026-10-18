"""Ability drafts execute assertions in memory and preserve untouched bytes."""
from copy import deepcopy

import pytest

import wf_mod_tool as binary
import wf_quest_lib as codec
from wf.balance.ownership import CHARACTER
from wf.balance.rows import TABLES, join_leaf, split_leaf
from wf.studio.ability import AbilityEditor, compile_ability_operations
from wf.studio.drafts import DraftError, DraftStore, schema_errors
from test_m1_balance import valid_row


class Source:
    version = "1.4.233"

    def __init__(self, *, shared=False):
        char = [""] * 37
        char[0], char[8], char[17], char[19] = "hero", "hero", "100", "1001"
        self.rows = [valid_row("first", "true"), valid_row("second")]
        other = list(char)
        other[0] = "other"
        self.tables = {
            CHARACTER: {"139985": join_leaf("\r\n", [char]), **({"100": join_leaf("", [other])} if shared else {})},
            TABLES["ability"]: {"1001": join_leaf("\r\n", self.rows),
                                "untouched": join_leaf("", [valid_row("untouched")])},
            TABLES["leader_ability"]: {"100": join_leaf("\r\n", [valid_row()[:1] + valid_row()[3:]])},
            TABLES["action_skill"]: {"hero": {str(i): join_leaf("\r\n", [["斩击" + "+"*(i-1), "攻击敌人", "100"]])
                                                for i in (1, 2, 3)}},
        }
        self.raw = {logical: codec.build_node(value) for logical, value in self.tables.items()}

    def read_raw(self, logical):
        return self.raw[logical], "fixture"


def op(kind="set_cells", *, row=0, count=2, cells=None, **extra):
    return {"op": kind, "table": "ability", "key": "1001", "row": row, "row_count": count,
            "column_space": "native", "cells": cells if cells is not None else [
                {"column": 51, "old": "10000", "new": "20000"}], **extra}


def full(row, kind):
    return [{"column": i, "old": None if kind == "insert_row" else value,
             "new": None if kind == "delete_row" else value} for i, value in enumerate(row)]


def editor(tmp_path, source=None):
    source = source or Source()
    return AbilityEditor(source, store=DraftStore(tmp_path / "drafts"))


def compiled(ed):
    return compile_ability_operations(ed.source, ed.store, ed.store.load("139985"))


def test_four_operations_roundtrip_and_untouched_compressed_chunk(tmp_path):
    ed = editor(tmp_path)
    original = dict(ed.source.raw)
    ed.apply("139985", {"operations": [op()]})
    inserted = valid_row("inserted")
    ed.apply("139985", {"operations": [op("insert_row", row=1, cells=full(inserted, "insert_row"))]})
    ed.apply("139985", {"operations": [op("move_row", row=1, count=3, to_row=2, cells=full(inserted, "move_row"))]})
    ed.apply("139985", {"operations": [op("delete_row", row=1, count=3,
                                          cells=full(ed.source.rows[1], "delete_row"))]})
    payload = compiled(ed)
    raw = payload["client"][TABLES["ability"]]
    leaf = codec.parse_node(raw)["1001"]
    expected = deepcopy(ed.source.rows[:1]) + [inserted]
    expected[0][51] = "20000"
    assert split_leaf(leaf, "ability") == expected
    assert "\r\n" in leaf and leaf.endswith("\r\n") and "\n" not in leaf.replace("\r\n", "")
    before = binary.read_orderedmap_raw_rows_from_bytes(original[TABLES["ability"]], "ability")
    after = binary.read_orderedmap_raw_rows_from_bytes(raw, "ability")
    assert dict(zip(before.keys, before.rows))["untouched"] == dict(zip(after.keys, after.rows))["untouched"]
    assert ed.source.raw == original
    assert len(ed.store.load("139985")["changes"]) == 1
    preview = ed.row_preview("139985", "ability", "1001", 0)
    assert preview["before"]["cells"][51] == "10000"
    assert preview["after"]["cells"][51] == "20000"
    assert preview["before"]["description"] != preview["after"]["description"]
    assert preview["runtime"] == "未执行"


def test_rejected_requests_do_not_create_or_replace_draft(tmp_path):
    ed = editor(tmp_path)
    wrong = op(cells=[{"column": 51, "old": "wrong", "new": "20000"}])
    assert any(c["blocking"] for c in ed.preview("139985", {"operations": [wrong]})["checks"])
    with pytest.raises(DraftError, match="old-value"):
        ed.apply("139985", {"operations": [wrong]})
    assert ed.store.load("139985") is None
    ed.apply("139985", {"operations": [op()]})
    saved = deepcopy(ed.store.load("139985"))
    with pytest.raises(DraftError, match="assert all"):
        ed.apply("139985", {"operations": [op("delete_row", cells=full(ed.source.rows[1], "delete_row")[:-1])]})
    assert ed.store.load("139985") == saved
    ed.source.raw[TABLES["ability"]] = codec.build_node({**ed.source.tables[TABLES["ability"]], "extra": "x"})
    with pytest.raises(ValueError, match="输入已变化"):
        compiled(ed)


def test_shared_owner_listing_explicit_opt_in_and_unison_warning(tmp_path):
    ed = editor(tmp_path, Source(shared=True))
    request = op(cells=[{"column": 1, "old": "true", "new": "false"}])
    with pytest.raises(DraftError, match=r"owners=\['100', '139985'\].*shared_ok"):
        ed.apply("139985", {"operations": [request]})
    response = ed.apply("139985", {"operations": [{**request, "shared_ok": True}]})
    assert any("合击资格" in c["message"] for c in response["checks"])
    assert compiled(ed)["changes"][0]["owners"] == ["100", "139985"]


def test_leader_126_to_124_mapping_and_absent_columns(tmp_path):
    ed = editor(tmp_path)
    operation = op(table="leader_ability", key="100", count=1)
    operation["column_space"] = "ability"
    operation["cells"] = [{"column": "c51", "old": "10000", "new": "20000"}]
    ed.apply("139985", {"operations": [operation]})
    row = split_leaf(codec.parse_node(compiled(ed)["client"][TABLES["leader_ability"]])["100"], "leader_ability")[0]
    assert len(row) == 124 and row[49] == "20000"
    operation["cells"] = [{"column": "c1", "old": "true", "new": "false"}]
    with pytest.raises(DraftError, match="no ability c1"):
        ed.apply("139985", {"operations": [operation]})


def test_attach_new_key_then_edit_keeps_original_shared_leaf(tmp_path):
    ed = editor(tmp_path, Source(shared=True))
    new = valid_row("new")
    attach = {"op": "attach_key", "table": "ability", "key": "new_key", "slot": 1,
              "old_key": "1001", "column_space": "native", "rows": [full(new, "insert_row")]}
    ed.apply("139985", {"operations": [attach, op(key="new_key", count=1)]})
    result = compiled(ed)
    ability = codec.parse_node(result["client"][TABLES["ability"]])
    assert ability["1001"] == ed.source.tables[TABLES["ability"]]["1001"]
    assert split_leaf(ability["new_key"], "ability")[0][51] == "20000"
    character = split_leaf(codec.parse_node(result["client"][CHARACTER])["139985"], "character")[0]
    assert character[19] == "new_key"
    attach["old_key"] = "new_key"
    attach["key"] = "1001"
    attach.pop("rows")
    with pytest.raises(DraftError, match="shared_ok"):
        ed.apply("139985", {"operations": [attach]})


def test_templates_allow_zero_precedent_and_schema_demands_assertions(tmp_path):
    ed = editor(tmp_path)
    catalog = ed.templates()
    empty = next(item for item in catalog["options"] if item["precedentCount"] == 0)
    assert empty["status"] == "待验证" and empty["selectable"] is True
    assert len(empty["defaults"]) == 126
    request = {"operations": [op()]}
    assert not schema_errors(request, "abilityRequest")
    del request["operations"][0]["cells"][0]["old"]
    assert schema_errors(request, "abilityRequest")


def test_registered_kind_wrong_table_or_block_is_problem(tmp_path):
    ed = editor(tmp_path)
    for table, key, count, column, kind in [("leader_ability", "100", 1, 45, "724"),
                                           ("ability", "1001", 2, 47, "422")]:
        request = op(table=table, key=key, count=count, cells=[{"column": column, "old": "0", "new": kind}])
        with pytest.raises(DraftError, match="问题:.*(allowed_tables|allowed_blocks)"):
            ed.apply("139985", {"operations": [request]})
    assert ed.store.load("139985") is None
