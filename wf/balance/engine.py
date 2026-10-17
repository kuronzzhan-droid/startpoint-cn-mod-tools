"""Assertion-first balance edits preserving untouched orderedmap chunks."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field

import wf_mod_tool as codec
import wf_quest_lib as nodes
import wf_client_legality as legality

from wf.view.base149 import member
from .recipe import validate_recipe
from .rows import TABLES, WIDTHS, column_index, join_leaf, split_leaf, unison_eligible
from .inputs import require_version
from .ownership import check_owner, owner_index


@dataclass
class BalanceResult:
    files: dict[str, bytes]
    logical_paths: dict[str, str]
    before_sha256: dict[str, str]
    changes: list[dict]
    touched_keys: dict[str, list[str]]
    warnings: list[dict] = field(default_factory=list)
    dsl_gate: dict = field(default_factory=dict)

    @property
    def ownership(self):
        return {f"{change['table']}/{change['key']}": change["owners"]
                for change in self.changes if "owners" in change}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_equal(actual, expected, location):
    if actual != expected:
        raise ValueError(f"old-value assertion failed at {location}: expected {expected!r}, found {actual!r}")


def _edit_rows(operation: dict, rows: list[list[str]], location: str) -> list[list[str]]:
    table, kind, index = operation["table"], operation["op"], operation["row"]
    _assert_equal(len(rows), operation["row_count"], f"{location} row_count")
    inserting = kind == "insert_row"
    last_index = len(rows) if inserting else len(rows) - 1
    if index > last_index:
        raise ValueError(f"{location}: row index out of range")
    cells = operation["cells"]
    mapped = [(column_index(table, cell["column"], operation.get("column_space", "ability")), cell)
              for cell in cells]
    if len({column for column, _ in mapped}) != len(mapped):
        raise ValueError(f"{location}: duplicate cell address")
    width = WIDTHS.get(table)
    if kind in {"insert_row", "delete_row"}:
        if not width:
            raise ValueError("structural row operations require an ability or leader table")
        if {column for column, _ in mapped} != set(range(width)):
            raise ValueError(f"{location}: structural edit must assert all {width} cells")
    target = [None] * width if inserting else list(rows[index])
    for column, cell in mapped:
        if column >= len(target):
            raise ValueError(f"{location}: c{column} outside row")
        _assert_equal(target[column], cell["old"], f"{location} row {index} c{column}")
        if cell["old"] == cell["new"]:
            raise ValueError(f"{location} c{column}: no-op edit is not allowed")
        if kind == "delete_row":
            if cell["new"] is not None:
                raise ValueError(f"{location}: deletion new values must be null")
        elif not isinstance(cell["new"], str):
            raise ValueError(f"{location}: inserted/updated cells must be strings")
        target[column] = cell["new"]
    if inserting:
        rows.insert(index, target)
    elif kind == "delete_row":
        del rows[index]
        if not rows:
            raise ValueError(f"{location}: cannot remove every ability row")
    else:
        rows[index] = target
    return rows


def apply_recipe(recipe: dict, view) -> BalanceResult:
    """Validate all old cells in memory; failure produces no files or mutation."""
    validate_recipe(recipe)
    require_version(getattr(view, "effective_tip", getattr(view, "tip", None)), recipe["from_version"])
    for operation in recipe["operations"]:
        table = operation["table"]
        if table == "custom_ability_string" or (table == "action_skill" and any(
                column_index(table, cell["column"]) in (0, 1) for cell in operation["cells"])):
            raise ValueError(f"{table}/{operation['key']}: visible text edits require wf text for rules and synchronization")
    result = _apply_operations(recipe, view, owner_index(view))
    from wf.dsl.gate import check_629_actions
    overrides = {result.logical_paths[name]: raw for name, raw in result.files.items()}
    result.dsl_gate = check_629_actions(view.read_raw, overrides=overrides, changed_logicals=set(overrides))
    if result.dsl_gate["status"] == "问题":
        raise ValueError(f"balance 629 gate blocked: {result.dsl_gate['findings']}")
    return result


def _apply_operations(recipe: dict, view, owners=None) -> BalanceResult:
    """Encoding core; the only legacy caller is the digest-pinned 223 verifier."""
    raw_tables, originals, tables, touched, changes = {}, {}, {}, {}, []
    warnings = []
    for operation in recipe["operations"]:
        table = operation["table"]
        logical, key = TABLES[table], operation["key"]
        if logical not in tables:
            raw_tables[logical] = view.read_raw(logical)[0]
            originals[logical] = nodes.parse_node(raw_tables[logical])
            tables[logical] = copy.deepcopy(originals[logical])
        location = f"{table}/{key}"
        if key not in tables[logical]:
            raise ValueError(f"{location}: missing key, refusing fallback or replacement")
        key_owners = check_owner(operation, owners) if owners is not None else None
        node = tables[logical][key]
        level = operation.get("level")
        if table == "action_skill":
            if not isinstance(node, dict) or level not in node:
                raise ValueError(f"{location}: missing action_skill level {level}")
            leaf = node[level]
            location += f"/{level}"
        else:
            if level is not None:
                raise ValueError(f"{location}: level only applies to action_skill")
            leaf = node
        rows = split_leaf(leaf, table)
        _assert_equal(join_leaf(leaf, rows), leaf, f"{location} original CSV roundtrip")
        unison_before = unison_eligible(rows) if table == "ability" else None
        updated = _edit_rows(operation, rows, location)
        value = join_leaf(leaf, updated)
        if level is None:
            tables[logical][key] = value
        else:
            node[level] = value
        touched.setdefault(logical, set()).add(key)
        change = copy.deepcopy(operation)
        if key_owners is not None:
            change["owners"] = key_owners
        if table == "ability":
            change["unison_before"] = unison_before
            change["unison_after"] = unison_eligible(updated)
            if change["unison_before"] != change["unison_after"]:
                warning = {"code": "unison-eligibility-changed", "table": table, "key": key,
                           "before": change["unison_before"], "after": change["unison_after"],
                           "message": "首行 c1 变化导致合击资格改变，请审阅。"}
                warnings.append(warning)
        changes.append(change)

    files, paths, before = {}, {}, {}
    for logical, keys in touched.items():
        raw = raw_tables[logical]
        ordered = codec.read_orderedmap_raw_rows_from_bytes(raw, logical)
        old_chunks = list(ordered.rows)
        for key in keys:
            if tables[logical][key] == originals[logical][key]:
                raise ValueError(f"{logical}/{key}: edits cancel out; refusing silent rollback")
            table = next(name for name, path in TABLES.items() if path == logical)
            if table in WIDTHS:
                for row_index, row in enumerate(split_leaf(tables[logical][key], table)):
                    problems = legality.client_legality_problems(table, row)
                    if problems:
                        raise ValueError(f"{table}/{key} row {row_index}: {'; '.join(problems)}")
            index = ordered.keys.index(key)
            _assert_equal(nodes.build_node(originals[logical][key]), old_chunks[index],
                          f"{logical}/{key} original binary roundtrip")
            ordered.rows[index] = nodes.build_node(tables[logical][key])
        encoded = codec.build_orderedmap_raw_rows(ordered)
        decoded = nodes.parse_node(encoded)
        _assert_equal(decoded, tables[logical], f"{logical} encoded roundtrip")
        actual_keys = {key for key in decoded if decoded[key] != originals[logical][key]}
        _assert_equal(actual_keys, keys, f"{logical} changed-key boundary")
        name = member(logical)
        files[name], paths[name], before[name] = encoded, logical, _sha(raw)
    return BalanceResult(files, paths, before, changes,
                         {logical: sorted(keys) for logical, keys in touched.items()}, warnings)
