"""L4: native leader templates must never silently fall back to ability columns."""
import json

import pytest

from wf.balance.rows import TABLES, split_leaf
from wf.studio.ability_engine import EditState, apply_operation
from wf.studio.ability_routes import AbilityRoutes
from test_studio_ability import Source, editor, full, op


def test_template_http_response_recommends_request_column_space(tmp_path):
    ed = editor(tmp_path)
    routes = AbilityRoutes(None)
    routes.editor = lambda: ed
    response = routes.templates({"table": ["leader_ability"]})
    document = json.loads(response.body)
    assert document["column_space"] == "native"
    assert all(entry["column_space"] == entry["columnSpace"] == "native" for entry in document["options"])
    assert all(len(entry["defaults"]) == 124 for entry in document["options"])


def test_leader_native_columns_cannot_use_implicit_ability_space():
    state = EditState(Source())
    row = split_leaf(state.table(TABLES["leader_ability"])["100"], "leader_ability")[0]
    # Both physical cells are empty: old-value assertions alone cannot detect the shift.
    column = next(i for i in range(3, 124) if row[i] == row[i - 2] == "")
    operation = op(table="leader_ability", key="100", count=1,
                   cells=[{"column": column, "old": "", "new": "0"}])
    del operation["column_space"]
    with pytest.raises(ValueError, match="column_space"):
        apply_operation(state, "139985", operation)
    assert not state.client


def test_native_template_row_mislabeled_as_ability_space_is_rejected():
    state = EditState(Source())
    row = split_leaf(state.table(TABLES["leader_ability"])["100"], "leader_ability")[0]
    operation = op("insert_row", table="leader_ability", key="100", count=1,
                   column_space="ability", cells=full(row, "insert_row"))
    with pytest.raises(ValueError, match="no ability c1"):
        apply_operation(state, "139985", operation)
    assert not state.client
