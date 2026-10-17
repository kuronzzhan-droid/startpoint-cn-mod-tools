"""M1.1 counterexamples for stale views, text bypass, sharing and CSV damage."""
from __future__ import annotations

import hashlib
import json

import pytest

import wf_quest_lib as nodes
from wf.balance import apply_recipe, split_leaf
from wf.balance.inputs import historical_tip, open_inputs
from wf.balance.ownership import CHARACTER
from wf.balance.rows import TABLES, join_leaf
from wf.paths import REPOSITORY
from test_m1_balance import MemoryView, ability_view, operation, recipe, structural, valid_row


def test_224_view_cannot_be_declared_as_226():
    view = ability_view()
    view.tip = "1.4.224"
    document = recipe(operation())
    document.update(from_version="1.4.226", to_version="1.4.227")
    with pytest.raises(ValueError, match="input tip.*1.4.224.*from_version.*1.4.226"):
        apply_recipe(document, view)


def test_manifest_recipe_rejects_wrong_tip_before_opening_view(tmp_path):
    document = recipe(operation())
    document.update(from_version="1.4.226", to_version="1.4.227",
                    input={"kind": "manifest", "tip": "1.4.224"})
    with pytest.raises(ValueError, match="from_version"):
        open_inputs(document, tmp_path / "recipe.yml")


def test_historical_lock_tip_is_bound_to_from_version(tmp_path):
    (tmp_path / "base.json").write_text(json.dumps({"tip": 224}), "utf-8")
    (tmp_path / "extra.json").write_text(json.dumps({"tip": 224, "zips": []}), "utf-8")
    document = recipe(operation())
    document.update(from_version="1.4.226", to_version="1.4.227",
                    input={"kind": "historical-lock", "base_lock": "base.json", "extra_lock": "extra.json"})
    with pytest.raises(ValueError, match="input tip.*1.4.224.*from_version.*1.4.226"):
        open_inputs(document, tmp_path / "recipe.yml")


def test_historical_target_label_cannot_hide_a_stale_or_broken_chain():
    base = {"tip": 224}
    extra = {"tip": 224, "target_base": "1.4.226", "zips": [
        {"path": "pinball-1.4.224-1.4.225-1-fixture.zip"}]}
    with pytest.raises(ValueError, match="input tip"):
        historical_tip(base, extra)
    extra["zips"][0]["path"] = "pinball-1.4.225-1.4.226-1-fixture.zip"
    with pytest.raises(ValueError, match="chain gap"):
        historical_tip(base, extra)
    extra["zips"][0]["path"] = "pinball-1.4.224-1.4.226-2-fixture.zip"
    with pytest.raises(ValueError, match="seq"):
        historical_tip(base, extra)


@pytest.mark.parametrize("column", ["c0", "c1", 0, 1])
def test_action_skill_visible_columns_require_wf_text(column):
    view = MemoryView({"action_skill": {"hero": {"1": "name,description,400\n"}}})
    edit = operation("action_skill", "hero", level="1",
                     cells=[{"column": column, "old": "name", "new": "生命值100%以下"}])
    with pytest.raises(ValueError, match="wf text"):
        apply_recipe(recipe(edit), view)


@pytest.mark.parametrize("table,key", [("ability", "1001"), ("leader_ability", "100"),
                                        ("action_skill", "hero")])
def test_shared_keys_require_consent_and_report_all_owners(table, key):
    row = valid_row()
    tables = {"ability": {"1001": join_leaf("", [row])},
              "leader_ability": {"100": join_leaf("", [row[:1] + row[3:]])},
              "action_skill": {"hero": {"1": "skill,description,400\n"}}}
    view = MemoryView(tables)
    characters = nodes.parse_node(view.raw[CHARACTER])
    characters["200"] = characters["100"]
    characters["300"] = characters["100"]
    view.raw[CHARACTER] = nodes.build_node(characters)
    edit = operation(table, key)
    if table == "action_skill":
        edit.update(level="1", cells=[{"column": "c2", "old": "400", "new": "350"}])
    with pytest.raises(ValueError, match=r"owners=\['100', '200', '300'\].*shared_ok"):
        apply_recipe(recipe(edit), view)
    edit["shared_ok"] = True
    result = apply_recipe(recipe(edit), view)
    assert result.changes[0]["owners"] == ["100", "200", "300"]
    assert result.ownership == {f"{table}/{key}": ["100", "200", "300"]}
    edit["character"] = "400"
    with pytest.raises(ValueError, match="is not an owner"):
        apply_recipe(recipe(edit), view)


def test_first_row_deletion_reports_unison_eligibility_warning():
    rows = [valid_row(unison="false"), valid_row(unison="true")]
    result = apply_recipe(recipe(structural("delete_row", rows)), ability_view(rows))
    assert result.warnings == [{"code": "unison-eligibility-changed", "table": "ability", "key": "1001",
                                "before": False, "after": True,
                                "message": "首行 c1 变化导致合击资格改变，请审阅。"}]


CRLF = json.loads((REPOSITORY / "tests/fixtures/balance223_crlf.json").read_text("utf-8"))["leaves"]


@pytest.mark.parametrize("fixture", CRLF, ids=[f"{row['table']}-{row['key']}" for row in CRLF])
def test_all_thirteen_real_crlf_leaves_roundtrip_and_retain_separators(fixture):
    leaf, table = fixture["leaf"], fixture["table"]
    assert hashlib.sha256(leaf.encode()).hexdigest() == fixture["sha256"]
    rows = split_leaf(leaf, table)
    assert join_leaf(leaf, rows) == leaf
    rows[0][0] += "_edited"
    edited = join_leaf(leaf, rows)
    assert edited.count("\r\n") == leaf.count("\r\n")
    assert "\n" not in edited.replace("\r\n", "")
    assert split_leaf(edited, table) == rows
    rows[0][0] = rows[0][0].removesuffix("_edited")
    assert join_leaf(edited, rows) == leaf


def test_crlf_cancelled_edits_cannot_escape_rollback_detection():
    view = MemoryView({"ability": {"1001": join_leaf("\r\n", [valid_row(), valid_row("second")])}})
    undo = operation(row_count=2, cells=[{"column": "c51", "old": "20000", "new": "10000"}])
    with pytest.raises(ValueError, match="silent rollback"):
        apply_recipe(recipe(operation(row_count=2), undo), view)


def test_csv_original_roundtrip_is_asserted_before_editing():
    view = ability_view()
    leaf = join_leaf("\n", [valid_row()]).replace("hero,", '"hero",', 1)
    view.raw[TABLES["ability"]] = nodes.build_node({"1001": leaf})
    with pytest.raises(ValueError, match="original CSV roundtrip"):
        apply_recipe(recipe(operation()), view)


def test_quoted_text_newline_does_not_change_record_separator():
    rows = [["name", "description\nsecond line"], ["other", "description"]]
    original = join_leaf("\r\n", rows)
    assert join_leaf(original, split_leaf(original, "action_skill")) == original


def test_fixed_223_verifier_refuses_recipe_or_lock_drift(tmp_path, monkeypatch):
    import recipes.balance_replay223 as frozen
    monkeypatch.setattr(frozen, "REPOSITORY", tmp_path)
    for name in frozen.PINNED:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY / name).read_bytes())
    (tmp_path / "recipes/balance/balance1017-223.yml").write_text("schema: changed\n", "utf-8")
    with pytest.raises(ValueError, match="fixed 223 replay input changed"):
        frozen.replay()


def test_balance_629_gate_blocks_before_writing_output(tmp_path, monkeypatch):
    import wf.balance.cli as cli
    import wf.dsl.gate as gate
    view = ability_view()
    seen = {}

    def reject(read_raw, **kwargs):
        seen.update(kwargs)
        assert read_raw(TABLES["ability"])[0] == view.raw[TABLES["ability"]]
        return {"status": "问题", "findings": [{"command": "NotifyPowerflipEnd"}]}

    monkeypatch.setattr(gate, "check_629_actions", reject)
    monkeypatch.setattr(cli, "load_recipe", lambda path: recipe(operation()))
    monkeypatch.setattr(cli, "open_inputs", lambda *args: (view, lambda: {}))
    output = tmp_path / "blocked"
    assert cli.main([str(tmp_path / "recipe.yml"), "--write", "--output", str(output)]) == 1
    assert seen["changed_logicals"] == {TABLES["ability"]}
    assert seen["overrides"][TABLES["ability"]] != view.raw[TABLES["ability"]]
    assert not output.exists()
