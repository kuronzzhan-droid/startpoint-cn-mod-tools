"""Quest stat values/scales remain explicit across preview, persistence and replay."""
import copy
import json
from itertools import combinations
from pathlib import Path

import pytest
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.boss.parameters import apply_values, columns
from wf.studio.boss import BossEditor, compile_boss
from wf.studio.drafts import DraftStore, schema_errors
from wf.studio.server import StudioApp
from test_boss_model import csv_row
from test_studio_boss_checks import fixture_editor, request
from test_studio_boss_drafts import five_tier_editor


def stat_editor(tmp_path):
    editor = fixture_editor(tmp_path)
    logical = s.QUEST_TABLES["hard_multi"]
    table = codec.parse_node(editor.source.view.files[logical])
    values = s.parse_rows(table["1006"]["1"])[0]
    values[98:104] = ["0.1", "0.2", "0.3", "0.2", "0.4", "0.6"]
    table["1006"]["1"] = csv_row(values)
    editor.source.view.files[logical] = codec.build_node(table)
    return editor


def edit(**parameters):
    return {"operation": "edit", "parameters": parameters}


def actual(compiled):
    table = codec.parse_node(compiled["client"][s.QUEST_TABLES["hard_multi"]])
    return s.parse_rows(table["1006"]["1"])[0][98:104]


@pytest.mark.parametrize("kind", ["boss_battle", "hard_multi", "practice"])
def test_scale_multiplies_each_existing_value_without_float_rounding(kind):
    values = [""] * 130
    for field, initial in (("hpValue", ["0.1", "0.2", "0.3"]),
                           ("attackValue", ["0.2", "0.4", "0.6"])):
        for column, value in zip(columns(kind)[field], initial):
            values[column] = value
    before = list(values)
    after = apply_values(values, kind, {"hpScale": 10, "attackScale": 0.1})
    assert [after[c] for c in columns(kind)["hpValue"]] == ["1", "2", "3"]
    assert [after[c] for c in columns(kind)["attackValue"]] == ["0.02", "0.04", "0.06"]
    assert values == before


@pytest.mark.parametrize("field", ["hpValue", "hpMultiplier", "attackValue", "attackMultiplier"])
def test_absolute_and_legacy_fields_overwrite_rather_than_multiply(field):
    values = ["0.1"] * 130
    after = apply_values(values, "hard_multi", {field: 1})
    assert [after[c] for c in columns("hard_multi")[field]] == ["1"] * 3


@pytest.mark.parametrize("stat", ["hp", "attack"])
def test_conflicting_modes_rejected_by_schema_and_direct_editor(stat):
    for left, right in combinations((stat + "Scale", stat + "Value", stat + "Multiplier"), 2):
        parameters = {left: 1, right: 2}
        assert schema_errors(edit(**parameters), "bossRequest")
        with pytest.raises(ValueError, match="一种写入方式"):
            apply_values(["0.1"] * 130, "hard_multi", parameters)


@pytest.mark.parametrize("field", ["hpScale", "hpValue", "attackScale", "attackValue"])
@pytest.mark.parametrize("invalid", [0, -1, True, 2147483648, "10"])
def test_explicit_fields_reject_invalid_inputs(field, invalid):
    assert schema_errors(edit(**{field: invalid}), "bossRequest")


def test_scale_rejects_output_overflow_and_invalid_current_value():
    with pytest.raises(ValueError, match="2147483647"):
        apply_values(["2147483647"] * 130, "hard_multi", {"hpScale": 2})
    with pytest.raises(ValueError, match="invalid"):
        apply_values(["(None)"] * 130, "hard_multi", {"attackScale": 2})


def test_preview_current_values_and_saved_draft_replay_do_not_add_operations(tmp_path):
    editor = stat_editor(tmp_path)
    source = copy.deepcopy(editor.source.view.files)
    payload = edit(hpScale=10, attackScale=0.1)
    first = editor.preview("hard_multi:1006/1", payload)
    second = editor.preview("hard_multi:1006/1", payload)
    assert first["ok"] and first == second
    hp = first["parameterChanges"][0]
    assert hp["mode"] == "scale" and not hp["repeatScale"]
    assert [(v["before"], v["after"]) for v in hp["values"]] == [("0.1", "1"), ("0.2", "2"), ("0.3", "3")]
    assert not editor.store.root.exists()
    result = editor.apply("hard_multi:1006/1", payload)
    quest = result["questId"]
    assert result["parameterChanges"] == first["parameterChanges"]
    saved = editor.store.save(quest)
    compiled = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
    assert actual(compiled) == ["1", "2", "3", "0.02", "0.04", "0.06"]
    reopened = BossEditor(editor.source, store=editor.store, server_dir=editor.server_dir)
    assert reopened.read(quest)["parameterChanges"] == first["parameterChanges"]
    assert compile_boss(reopened.source, reopened.store, reopened.store.load(quest),
                        server_dir=reopened.server_dir) == compiled
    repeated = reopened.preview(quest, payload)
    assert repeated["ok"]
    hp = repeated["parameterChanges"][-2]
    assert hp["repeatScale"] and [v["before"] for v in hp["values"]] == ["1", "2", "3"]
    assert [v["after"] for v in hp["values"]] == ["10", "20", "30"]
    assert any("会再乘一次" in c["message"] and c.get("repeatScale") for c in repeated["checks"])
    assert len(reopened.store.load(quest)["changes"][0]["params"]["requests"]) == 1
    reopened.apply(quest, payload)
    twice = compile_boss(reopened.source, reopened.store, reopened.store.save(quest), server_dir=reopened.server_dir)
    assert actual(twice) == ["10", "20", "30", "0.002", "0.004", "0.006"]
    assert editor.source.view.files == source


def test_absolute_write_after_scale_is_idempotent_and_legacy_is_deprecated(tmp_path):
    editor = stat_editor(tmp_path)
    editor.apply("hard_multi:1006/1", edit(hpScale=10))
    editor.apply("hard_multi:1006/1", edit(hpValue=1, attackValue=1))
    editor.apply("hard_multi:1006/1", edit(hpValue=1, attackValue=1))
    saved = editor.store.save("hard_multi:1006/1")
    compiled = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
    assert actual(compiled) == ["1"] * 6
    result = editor.apply("hard_multi:1006/1", edit(hpMultiplier=2, attackMultiplier=3))
    warnings = [c for c in result["checks"] if c["rule"] == "boss.parameter-deprecated"]
    assert len(warnings) == 2 and all("绝对值、已弃用" in c["message"] and not c["blocking"] for c in warnings)
    saved = editor.store.save("hard_multi:1006/1")
    reopened = BossEditor(editor.source, store=editor.store, server_dir=editor.server_dir)
    compiled = compile_boss(reopened.source, reopened.store, saved, server_dir=reopened.server_dir)
    assert actual(compiled) == ["2"] * 3 + ["3"] * 3
    assert all(c["deprecated"] and c["mode"] == "absolute" for c in compiled["parameterChanges"][-2:])


def test_schema_marks_only_quest_legacy_multipliers_deprecated():
    schema = json.loads((Path(__file__).parents[1] / "schemas/studio-draft.schema.json").read_text(encoding="utf-8"))
    for stat in ("hp", "attack"):
        field = schema["$defs"]["bossParameters"]["properties"][stat + "Multiplier"]
        assert field["deprecated"] and "绝对值、已弃用" in field["description"]
        assert not schema["$defs"]["bossWeapon"]["properties"][stat + "Multiplier"].get("deprecated")


def test_create_shared_scales_its_defaults_and_accepts_legacy_absolute(tmp_path):
    editor = stat_editor(tmp_path)
    result = editor.preview("new", request(parameters={"hpScale": 10, "attackValue": 1}))
    assert result["ok"], result
    hp, attack = result["parameterChanges"]
    assert [(v["before"], v["after"]) for v in hp["values"]] == [("1.5", "15")] * 3
    assert [v["after"] for v in attack["values"]] == ["1"] * 3
    legacy = editor.preview("new", request(parameters={"hpMultiplier": 10}))
    assert legacy["ok"] and all(v["after"] == "10" for v in legacy["parameterChanges"][0]["values"])


def test_five_tiers_can_override_common_scale_with_absolute_value(tmp_path):
    editor = five_tier_editor(tmp_path)
    logical = s.QUEST_TABLES["boss_battle"]
    table = codec.parse_node(editor.source.view.files[logical])
    for tier, text in table["1"]["80"].items():
        values = s.parse_rows(text)[0]
        values[97:103] = ["1.5"] * 6
        table["1"]["80"][tier] = csv_row(values)
    editor.source.view.files[logical] = codec.build_node(table)
    tiers = [{"hpValue": 1}, {}, {"hpScale": 3}, {"hpMultiplier": 4}, {"attackValue": 5}]
    preview = editor.preview("1080001", {"operation": "edit", "parameters": {"hpScale": 10}, "tiers": tiers})
    assert preview["ok"], preview
    hp = [c for c in preview["parameterChanges"] if c["stat"] == "hp"]
    assert [c["parameter"] for c in hp] == ["hpValue", "hpScale", "hpScale", "hpMultiplier", "hpScale"]
    assert [c["values"][0]["after"] for c in hp] == ["1", "15", "4.5", "4", "15"]


def test_http_preview_returns_actual_values_and_legacy_warning(tmp_path):
    editor = stat_editor(tmp_path)
    app = StudioApp(editor.source, drafts=DraftStore(tmp_path / "app"), server_dir=editor.server_dir)
    response = app.dispatch("POST", "/api/boss/drafts/hard_multi%3A1006%2F1", {"preview": ["true"]}, edit(hpMultiplier=10))
    data = json.loads(response.body)
    assert response.status == 200 and data["ok"]
    assert data["parameterChanges"][0]["values"][0] == {"target": "zako", "column": 98, "before": "0.1", "after": "10"}
    assert any("绝对值、已弃用" in c["message"] for c in data["checks"])
