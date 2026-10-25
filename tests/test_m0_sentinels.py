"""Regression coverage for the existing C validator and composer gap."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import wf_client_legality
import wf_describe
from wf.rules.instant_content import (
    fill_instant_content_defaults,
    instant_option_value_problems,
)
from tool_source import tool_source


KINDS = ("ability", "leader_ability", "ability_soul", "equipment_enhancement_ability")


def _row(kind: str, mode: str = "0", content: str = "0") -> list[str]:
    layout = wf_describe.layout(kind)
    blocks = layout["blocks"]
    row = [""] * int(layout["ncols"])
    row[int(blocks["precondition1"]) - 1] = mode
    for name in ("precondition1", "precondition2", "precondition3"):
        row[int(blocks[name])] = "0"
    row[int(blocks["instant_trigger"])] = "0"
    row[int(blocks["instant_delay"])] = "0"
    row[int(blocks["instant_precontent"])] = "(None)"
    base = int(blocks["instant_content"])
    row[base] = content
    for offset, value in ((1, "0"), (4, "10000"), (10, "100000"),
                          (12, "100000"), (20, "0"), (27, "1")):
        row[base + offset] = value
    return row


@pytest.mark.parametrize("kind", KINDS)
def test_declared_defaults_cover_all_three_failure_classes(kind):
    row = _row(kind)
    base = int(wf_describe.layout(kind)["blocks"]["instant_content"])
    fixed = fill_instant_content_defaults(kind, row)
    assert fixed[base + 25] == "false"
    assert fixed[base + 28] == "0"
    assert fixed[base + 14:base + 19] == ["(None)"] * 5
    assert row[base + 25] == ""  # generation must not alter its input template
    original_problems = "\n".join(wf_client_legality.client_legality_problems(kind, row))
    for name in ("by_each_trigger_puller", "multiply_trigger", "max_accumulation",
                 "flip_limit", "power_flip_limit", "end_power_flip_limit",
                 "end_power_flip_accepted_levels"):
        assert name in original_problems
        assert name not in "\n".join(wf_client_legality.client_legality_problems(kind, fixed))


@pytest.mark.parametrize("mode", ("1", "2"))
def test_inactive_instant_block_is_untouched(mode):
    row = _row("ability", mode)
    assert fill_instant_content_defaults("ability", row) == row
    row[65] = "4"
    assert instant_option_value_problems("ability", row) == []


def test_undeclared_fields_and_explicit_values_are_preserved():
    row = _row("ability", content="629")
    assert fill_instant_content_defaults("ability", row) == row
    row = _row("ability")
    row[72], row[75], row[61], row[65] = "true", "3", "2", "12"
    fixed = fill_instant_content_defaults("ability", row)
    assert [fixed[i] for i in (72, 75, 61, 65)] == ["true", "3", "2", "12"]


@pytest.mark.parametrize("value", ("0", "4", "13", "-1", "wrong"))
def test_nonempty_invalid_pf_levels_are_rejected(value):
    row = fill_instant_content_defaults("ability", _row("ability"))
    row[65] = value
    problems = wf_client_legality.client_legality_problems("ability", row)
    assert any("end_power_flip_accepted_levels" in p and "F1009" in p for p in problems)


@pytest.mark.parametrize("value", ("(None)", "1", "2", "3", "11", "12"))
def test_valid_pf_levels_are_accepted(value):
    row = _row("ability")
    row[65] = value
    assert instant_option_value_problems("ability", row) == []


@pytest.mark.parametrize("kind", ("ability", "leader_ability"))
def test_real_gui_composer_initializes_sentinels_without_a_store(kind):
    # Execute the actual composer function while replacing only the GUI's
    # store-backed blank-template lookup. Importing the whole GUI needs a
    # local game installation, unrelated to this pure generation regression.
    source = tool_source(Path(__file__).resolve().parents[1], "wf_gui.py")
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "composer_generate")
    namespace = {
        "wf_describe": wf_describe,
        "_FXGEN_TRIGGERS": [],
        "_FXGEN_EFFECTS": [],
        "composer_meta": lambda: {"enums": {"trigger": {}, "instant_content": {}}},
        "composer_blank": lambda key: {"kind": kind, "row": _row(kind)},
        "_unit_mul": lambda unit: 1000,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    generated = namespace["composer_generate"](
        "test", mode="instant", trigger_kind="0", effect_kind="0", value=10,
    )["row"]
    base = int(wf_describe.layout(kind)["blocks"]["instant_content"])
    assert generated[base + 14:base + 19] == ["(None)"] * 5
    assert generated[base + 25] == "false"
    assert generated[base + 28] == "0"
