"""In-memory, assertion-first ability edits with lossless orderedmap leaves."""
from __future__ import annotations

import copy

import wf_client_legality
import wf_describe
import wf_quest_lib as codec
from wf.balance.engine import _assert_equal, _edit_rows
from wf.balance.ownership import CHARACTER, check_owner, owner_index
from wf.balance.rows import TABLES, WIDTHS, column_index, join_leaf, split_leaf, unison_eligible
from wf.caps.facts import table_signals
from wf.caps.registry import load_registry
from wf.rules.catalog import result
from wf.text.edit import _encode


class EditState:
    """A disposable overlay; no method writes the input view or a table file."""

    def __init__(self, source):
        self.view = getattr(source, "view", source)
        self.original = {}
        self.client = {}
        self.changes = []
        self.checks = []
        self.servers = {}
        self.server_original = {}
        self.registry = load_registry()

    def read_raw(self, logical):
        if logical not in self.original:
            self.original[logical] = self.view.read_raw(logical)[0]
        return self.client.get(logical, self.original[logical]), "draft-memory"

    def table(self, logical):
        return codec.parse_node(self.read_raw(logical)[0])

    def write_table(self, logical, table):
        raw = self.read_raw(logical)[0]
        self.client[logical] = _encode(raw, codec.parse_node(raw), table)
        _assert_equal(codec.parse_node(self.client[logical]), table, logical + " encoded roundtrip")

    def character(self, cid):
        table = self.table(CHARACTER)
        if cid not in table:
            raise ValueError(f"角色 {cid} 不在当前视图")
        rows = split_leaf(table[cid], "character")
        if len(rows) != 1 or len(rows[0]) < 25:
            raise ValueError(f"character/{cid}: 不能确定能力槽归属")
        return rows[0]

    def validate_rows(self, table, key, leaf):
        if table not in WIDTHS:
            return
        list(table_signals(TABLES[table], (key,), leaf, registry=self.registry))
        for index, row in enumerate(split_leaf(leaf, table)):
            problems = wf_client_legality.client_legality_problems(table, row)
            if problems:
                raise ValueError(f"问题: {table}/{key}/{index}: {'; '.join(problems)}")


def _skill_structure(state, cid, operation, document, owners):
    """A skill row is one tier leaf; structural edits shift the numbered tiers."""
    key, kind, level = operation["key"], operation["op"], operation["level"]
    node = document[key]
    levels = sorted(node, key=int)
    if levels != [str(i + 1) for i in range(len(levels))]:
        raise ValueError("action_skill structural editing requires contiguous tiers starting at 1")
    _assert_equal(operation["row_count"], len(levels), "action_skill tier count")
    _assert_equal(operation["row"], 0, "action_skill tier row")
    rows = [split_leaf(node[tier], "action_skill") for tier in levels]
    if any(len(items) != 1 for items in rows):
        raise ValueError("action_skill 每档必须是单行叶")
    records = [items[0] for items in rows]
    index = int(level) - 1
    if kind == "insert_row":
        if len(records) >= 3 or index > len(records):
            raise ValueError("action_skill 插入位置越界或已达三档上限")
        incoming = _new_rows(operation, [operation["cells"]])[0]
        if len(incoming) != len(records[0]):
            raise ValueError("action_skill 插入档位列数必须与现有档位相同")
        records.insert(index, incoming)
    else:
        if index >= len(records):
            raise ValueError("action_skill source tier does not exist")
        for column, cell in _whole_row(operation, records[index]):
            _assert_equal(cell["new"], None if kind == "delete_row" else records[index][column],
                          f"action_skill structural new c{column}")
        if kind == "delete_row":
            if len(records) == 1:
                raise ValueError("cannot remove every action_skill tier")
            records.pop(index)
        else:
            target = operation["to_row"]
            if target >= len(records) or target == index:
                raise ValueError("action_skill move target is out of range or unchanged")
            records.insert(target, records.pop(index))
            state.checks.append(result("ability.row-order", "待验证", "技能档位顺序已改变；请核对技能等级与能量"))
    document[key] = {str(i + 1): join_leaf(node.get(str(i + 1), node[levels[-1]]), [record])
                     for i, record in enumerate(records)}
    state.write_table(TABLES["action_skill"], document)
    state.changes.append({**operation, "owners": owners, "character": cid,
                          "structure": "action_skill_tiers"})


def _whole_row(operation, row, *, insert=False):
    cells = operation["cells"]
    mapped = [(column_index(operation["table"], cell["column"],
                            operation.get("column_space", "ability")), cell) for cell in cells]
    if len(mapped) != len(row) or {col for col, _ in mapped} != set(range(len(row))):
        raise ValueError(f"structural edit must assert all {len(row)} cells")
    for column, cell in mapped:
        _assert_equal(cell["old"], None if insert else row[column], f"whole-row c{column}")
    return mapped


def _new_rows(operation, assertions):
    width = WIDTHS.get(operation["table"])
    rows = []
    for cells in assertions:
        size = width or len(cells)
        row = [""] * size
        op = {**operation, "cells": cells}
        for column, cell in _whole_row(op, row, insert=True):
            if not isinstance(cell["new"], str):
                raise ValueError("new row cells must have string new values")
            row[column] = cell["new"]
        rows.append(row)
    if not rows:
        raise ValueError("a new key requires at least one row")
    return rows


def _skill_key_shape(node, expected_width=None):
    if not isinstance(node, dict) or not node:
        raise ValueError("action_skill key must contain tier leaves")
    levels = sorted(node, key=int)
    if len(levels) > 3 or levels != [str(i + 1) for i in range(len(levels))]:
        raise ValueError("action_skill tiers must be contiguous 1..3")
    widths = set()
    for leaf in node.values():
        rows = split_leaf(leaf, "action_skill")
        if len(rows) != 1 or len(rows[0]) < 2:
            raise ValueError("action_skill 每档必须为包含名称和文案的单行")
        widths.add(len(rows[0]))
    if len(widths) != 1 or expected_width is not None and widths != {expected_width}:
        raise ValueError("action_skill 档位列数不一致或与原技能不同")
    return next(iter(widths))


def _attach(state, cid, operation):
    table, key = operation["table"], operation["key"]
    slot = operation["slot"]
    if table == "ability":
        if not 1 <= slot <= 6:
            raise ValueError("ability slot must be 1..6")
        column = 18 + slot
    else:
        if slot != 0:
            raise ValueError("leader/action_skill slot must be 0")
        column = 17 if table == "leader_ability" else 8
    character = state.character(cid)
    _assert_equal(character[column], operation["old_key"], f"character/{cid} c{column}")
    if character[column] == key:
        raise ValueError("attach_key cannot be a no-op")
    logical = TABLES[table]
    target = state.table(logical)
    owners = sorted(owner_index(state)[table].get(key, set()))
    if set(owners) - {cid} and operation.get("shared_ok") is not True:
        raise ValueError(f"{table}/{key}: shared key owners={owners}; declare shared_ok: true explicitly")
    creating = "rows" in operation or "levels" in operation
    if creating:
        _assert_equal(target.get(key), None, f"{table}/{key} new-key assertion")
        if table == "action_skill":
            if "rows" in operation or not operation.get("levels"):
                raise ValueError("new action_skill keys require levels")
            value = {level: join_leaf("", _new_rows(operation, rows))
                     for level, rows in operation["levels"].items()}
        else:
            if "levels" in operation or "rows" not in operation:
                raise ValueError("new ability/leader keys require rows")
            value = join_leaf("", _new_rows(operation, operation["rows"]))
            state.validate_rows(table, key, value)
        target[key] = value
        state.write_table(logical, target)
    elif key not in target:
        raise ValueError(f"{table}/{key}: key does not exist; provide asserted rows")
    elif table in WIDTHS:
        state.validate_rows(table, key, target[key])
    if table == "action_skill":
        previous_width = _skill_key_shape(state.table(logical)[operation["old_key"]])
        _skill_key_shape(target[key], previous_width)
    old_leaf = state.table(CHARACTER)[cid]
    character[column] = key
    characters = state.table(CHARACTER)
    characters[cid] = join_leaf(old_leaf, [character])
    state.write_table(CHARACTER, characters)
    state.changes.append({**operation, "character": cid, "owners": owners})


def apply_operation(state, cid, requested):
    operation = copy.deepcopy(requested)
    if operation.get("character", cid) != cid:
        raise ValueError("operation character must match the draft character")
    operation["character"] = cid
    if operation["op"] == "attach_key":
        _attach(state, cid, operation)
        return
    table, key = operation["table"], operation["key"]
    owners = check_owner(operation, owner_index(state))
    logical = TABLES[table]
    document = state.table(logical)
    if key not in document:
        raise ValueError(f"{table}/{key}: missing key")
    if table == "action_skill" and operation["op"] in {"insert_row", "delete_row", "move_row"}:
        _skill_structure(state, cid, operation, document, owners)
        return
    node, level = document[key], operation.get("level")
    if table == "action_skill":
        if not isinstance(node, dict) or level not in node:
            raise ValueError(f"action_skill/{key}: missing level {level}")
        leaf = node[level]
    else:
        if level is not None:
            raise ValueError("level only applies to action_skill")
        leaf = node
    rows = split_leaf(leaf, table)
    _assert_equal(join_leaf(leaf, rows), leaf, f"{table}/{key} original CSV roundtrip")
    before = copy.deepcopy(rows)
    index, kind = operation["row"], operation["op"]
    if table == "action_skill" and kind == "set_cells" and any(
            column_index(table, c["column"]) < 2 for c in operation["cells"]):
        raise ValueError("visible action_skill text must use wf text")
    if kind == "move_row":
        _assert_equal(len(rows), operation["row_count"], "move row_count")
        if index >= len(rows) or operation["to_row"] >= len(rows):
            raise ValueError("move row index out of range")
        if index == operation["to_row"]:
            raise ValueError("move_row cannot be a no-op")
        for column, cell in _whole_row(operation, rows[index]):
            _assert_equal(cell["new"], rows[index][column], f"move c{column} unchanged")
        rows.insert(operation["to_row"], rows.pop(index))
        state.checks.append(result("ability.row-order", "待验证", "同一键的行顺序有语义；请核对移动后的效果与合击资格"))
    else:
        rows = _edit_rows(operation, rows, f"{table}/{key}")
    value = join_leaf(leaf, rows)
    state.validate_rows(table, key, value)
    if level is None:
        document[key] = value
    else:
        document[key][level] = value
    state.write_table(logical, document)
    if table == "ability" and unison_eligible(before) != unison_eligible(rows):
        state.checks.append(result("ability.unison-first-row", "待验证",
            "首行 c1 变化导致合击资格改变，请审阅。", before=unison_eligible(before), after=unison_eligible(rows)))
    state.changes.append({**operation, "owners": owners,
                          "beforeDescription": describe(before[index], table) if index < len(before) else None,
                          "afterDescription": describe(rows[index], table) if index < len(rows) else None})


def describe(row, table):
    if row is None:
        return None
    if table in WIDTHS:
        return wf_describe.describe_line(row, table)
    return " · ".join(row[:2])
