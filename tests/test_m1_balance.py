"""Behavioral regressions: wrong old values, flat-leaf edits and lost chunks fail."""
from __future__ import annotations

import hashlib
import json

import pytest

import wf_mod_tool as codec
import wf_quest_lib as nodes
from wf.balance import apply_recipe, column_index, load_recipe, split_leaf, unison_eligible, validate_recipe
from wf.balance.output import write_result
from wf.balance.rows import TABLES, join_leaf
from wf.balance.ownership import CHARACTER
from wf.rules.instant_content import fill_instant_content_defaults
from wf.view.base149 import member


def valid_row(name="hero", unison="false"):
    row = [""] * 126
    row[0], row[1], row[5] = name, unison, "0"
    for column in (6, 13, 20, 27, 46, 47):
        row[column] = "0"
    row[39] = "(None)"
    for column, value in ((48, "0"), (51, "10000"), (57, "100000"),
                          (59, "100000"), (67, "0"), (74, "1")):
        row[column] = value
    return fill_instant_content_defaults("ability", row)


def recipe(*operations):
    return {"schema": "wf-balance-recipe/1", "id": "fixture", "name": "测试配方", "slug": "fixture",
            "from_version": "1.4.222", "to_version": "1.4.223", "created_at": "2026-10-17",
            "local_test_only": True, "operations": list(operations)}


def operation(table="ability", key="1001", row=0, row_count=1, cells=None, **kwargs):
    return {"op": "set_cells", "character": "100", "table": table, "key": key, "row": row,
            "row_count": row_count, "cells": cells or [{"column": "c51", "old": "10000", "new": "20000"}], **kwargs}


class MemoryView:
    def __init__(self, tables):
        self.tip = "1.4.222"
        self.raw = {TABLES[name]: nodes.build_node(value) for name, value in tables.items()}
        row = valid_row("unused")
        self.raw.setdefault(TABLES["ability"], nodes.build_node({"unused": join_leaf("", [row])}))
        self.raw.setdefault(TABLES["leader_ability"], nodes.build_node({"unused": join_leaf("", [row[:1] + row[3:]])}))
        character = [""] * 25
        character[0], character[8], character[17], character[19] = "hero", "hero", "100", "1001"
        self.raw[CHARACTER] = nodes.build_node({"100": join_leaf("", [character])})

    def read_raw(self, logical):
        return self.raw[logical], "fixture"


def ability_view(rows=None):
    return MemoryView({"ability": {"1001": join_leaf("\n", rows or [valid_row()]),
                                   "untouched": join_leaf("", [valid_row("other")])}})


def changed_leaf(result, table="ability", key="1001"):
    return nodes.parse_node(result.files[member(TABLES[table])])[key]


def test_multiline_125n_plus_1_is_split_before_column_edits():
    rows = [valid_row(), valid_row("second")]
    text = join_leaf("\n", rows)
    assert len(text.split(",")) == 125 * 2 + 1
    assert split_leaf(text, "ability") == rows
    result = apply_recipe(recipe(operation(row=1, row_count=2)), ability_view(rows))
    after = split_leaf(changed_leaf(result), "ability")
    assert after[0] == rows[0]
    assert after[1][51] == "20000"
    assert after[1][:51] == rows[1][:51]
    assert after[1][52:] == rows[1][52:]


@pytest.mark.parametrize("trailing", ["", "\n"])
def test_csv_quoted_commas_and_newlines_and_trailing_style(trailing):
    rows = [["name,with comma", "text\nwith linebreak"]]
    text = join_leaf(trailing, rows)
    assert split_leaf(text, "custom_ability_string") == rows
    assert text.endswith("\n") == bool(trailing)


def test_leader_uses_ability_column_numbering_and_retains_124_columns():
    leader = valid_row()[:1] + valid_row()[3:]
    view = MemoryView({"leader_ability": {"100": join_leaf("\n", [leader])}})
    result = apply_recipe(recipe(operation("leader_ability", "100")), view)
    changed = split_leaf(changed_leaf(result, "leader_ability", "100"), "leader_ability")[0]
    assert len(changed) == 124 and changed[49] == "20000" and changed[51] == leader[51]
    assert column_index("leader_ability", "c0") == 0
    assert column_index("leader_ability", "c125") == 123
    assert column_index("leader_ability", "c49", "native") == 49


@pytest.mark.parametrize("column", ["c1", "c2", "c126", -1, True])
def test_invalid_leader_columns_are_rejected(column):
    with pytest.raises(ValueError):
        column_index("leader_ability", column)


def test_only_first_ability_row_controls_unison_pool():
    assert not unison_eligible([valid_row(unison="false"), valid_row(unison="true")])
    assert unison_eligible([valid_row(unison="true"), valid_row(unison="false")])
    assert not unison_eligible([])
    view = ability_view([valid_row(unison="false"), valid_row(unison="true")])
    edit = operation(row_count=2, cells=[{"column": "c1", "old": "false", "new": "true"}])
    change = apply_recipe(recipe(edit), view).changes[0]
    assert change["unison_before"] is False and change["unison_after"] is True


@pytest.mark.parametrize("level", ["1", "2", "3"])
def test_action_skill_exact_level_is_edited(level):
    levels = {key: f"skill {key},description {key},400\n" for key in ("1", "2", "3")}
    view = MemoryView({"action_skill": {"hero": levels}})
    edit = operation("action_skill", "hero", level=level,
                     cells=[{"column": "c2", "old": "400", "new": "350"}])
    after = changed_leaf(apply_recipe(recipe(edit), view), "action_skill", "hero")
    assert after[level] == f"skill {level},description {level},350\n"
    assert all(after[key] == levels[key] for key in levels if key != level)


def test_action_skill_zero_tier_is_not_a_game_level():
    edit = operation("action_skill", "hero", level="0")
    with pytest.raises(ValueError, match="'0' is not one of"):
        validate_recipe(recipe(edit))


def test_custom_text_requires_synchronized_text_command():
    view = MemoryView({"custom_ability_string": {"desc_override_hero": '"旧文本,50%"\n'}})
    edit = operation("custom_ability_string", "desc_override_hero",
                     cells=[{"column": "c0", "old": "旧文本,50%", "new": "新文本,20%\n第二行"}])
    with pytest.raises(ValueError, match="wf text"):
        apply_recipe(recipe(edit), view)


def test_wrong_old_cell_rejects_entire_batch_without_mutating_view():
    view = ability_view()
    original = dict(view.raw)
    wrong = operation(cells=[{"column": "c52", "old": "wrong", "new": "1"}])
    with pytest.raises(ValueError, match="old-value assertion failed.*c52"):
        apply_recipe(recipe(operation(), wrong), view)
    assert view.raw == original


def test_wrong_row_count_and_missing_key_do_not_fallback():
    with pytest.raises(ValueError, match="row_count"):
        apply_recipe(recipe(operation(row_count=2)), ability_view())
    with pytest.raises(ValueError, match="missing key"):
        apply_recipe(recipe(operation(key="missing")), ability_view())


def structural(kind, rows, row=0):
    return operation(op=kind, row=row, row_count=len(rows), cells=[
        {"column": column, "old": None if kind == "insert_row" else rows[row][column],
         "new": valid_row("inserted")[column] if kind == "insert_row" else None}
        for column in range(126)])


def test_insert_and_delete_rows_require_each_cell_assertion():
    rows = [valid_row(), valid_row("second")]
    result = apply_recipe(recipe(structural("insert_row", rows, 1)), ability_view(rows))
    after = split_leaf(changed_leaf(result), "ability")
    assert after == [rows[0], valid_row("inserted"), rows[1]]
    result = apply_recipe(recipe(structural("delete_row", rows)), ability_view(rows))
    assert split_leaf(changed_leaf(result), "ability") == [rows[1]]
    invalid = structural("delete_row", rows)
    invalid["cells"].pop()
    with pytest.raises(ValueError, match="assert all 126 cells"):
        apply_recipe(recipe(invalid), ability_view(rows))
    invalid = structural("delete_row", rows)
    invalid["cells"][125]["old"] = "wrong"
    with pytest.raises(ValueError, match="c125"):
        apply_recipe(recipe(invalid), ability_view(rows))


def test_untouched_orderedmap_chunk_is_exactly_preserved():
    view = ability_view()
    before = codec.read_orderedmap_raw_rows_from_bytes(view.raw[TABLES["ability"]])
    result = apply_recipe(recipe(operation()), view)
    after = codec.read_orderedmap_raw_rows_from_bytes(result.files[member(TABLES["ability"])])
    assert before.keys == after.keys
    index = before.keys.index("untouched")
    assert before.rows[index] == after.rows[index]
    assert result.before_sha256[member(TABLES["ability"])] == hashlib.sha256(view.raw[TABLES["ability"]]).hexdigest()


def test_noop_and_cancelled_edits_do_not_hide_rollback():
    undo = operation(cells=[{"column": "c51", "old": "20000", "new": "10000"}])
    with pytest.raises(ValueError, match="silent rollback"):
        apply_recipe(recipe(operation(), undo), ability_view())
    noop = operation(cells=[{"column": "c51", "old": "10000", "new": "10000"}])
    with pytest.raises(ValueError, match="no-op"):
        apply_recipe(recipe(noop), ability_view())
    backwards = recipe(operation())
    backwards["to_version"] = "1.4.221"
    with pytest.raises(ValueError, match="version must advance"):
        validate_recipe(backwards)


@pytest.mark.parametrize("broken", ["missing_old", "unknown_property", "duplicate_column", "bad_width", "illegal_kind"])
def test_invalid_recipe_and_row_are_rejected(broken):
    document = recipe(operation())
    view = ability_view()
    if broken == "missing_old":
        del document["operations"][0]["cells"][0]["old"]
    elif broken == "unknown_property":
        document["silent"] = True
    elif broken == "duplicate_column":
        document["operations"][0]["cells"] *= 2
    elif broken == "bad_width":
        view = ability_view([valid_row()[:-1]])
    else:
        document["operations"][0]["cells"] = [{"column": "c6", "old": "0", "new": ""}]
    with pytest.raises(ValueError):
        apply_recipe(document, view)


def test_duplicate_yaml_mapping_keys_are_rejected(tmp_path):
    source = tmp_path / "duplicate.yml"
    source.write_text("schema: wf-balance-recipe/1\nschema: ignored\n", "utf-8")
    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_recipe(source)


def test_output_contract_and_refuse_overwrite(tmp_path):
    document = recipe(operation())
    result = apply_recipe(document, ability_view())
    output = tmp_path / "output"
    report = write_result(document, result, output, {"fixture": True})
    changeset = json.loads((output / "changeset.json").read_text("utf-8"))
    assert changeset["schema"] == "wf-change-set/1"
    assert report["operation_count"] == report["cell_count"] == 1
    assert report["ownership"] == {"ability/1001": ["100"]}
    item = changeset["members"][0]
    assert item["root"] == "common"
    assert hashlib.sha256((output / item["source"]).read_bytes()).hexdigest() == item["sha256"]
    assert item["before_sha256"] == next(iter(result.before_sha256.values()))
    with pytest.raises(FileExistsError):
        write_result(document, result, output, {})


def test_output_outside_checkout_is_rejected_before_writing():
    from wf.paths import REPOSITORY
    with pytest.raises(PermissionError):
        write_result(recipe(operation()), apply_recipe(recipe(operation()), ability_view()),
                     REPOSITORY.parent / "forbidden-balance-output", {})
