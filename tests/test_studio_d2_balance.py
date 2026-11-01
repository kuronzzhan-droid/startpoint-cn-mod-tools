"""D2 review regressions: exact active fields and unambiguous table imports."""
from types import SimpleNamespace
import pytest
from test_studio_character_clone import env, OLD
from test_studio_batch import balance_body, service, MAPPING
from test_m1_balance import valid_row
from wf.studio.balance_import import _replacement, convert_row
from wf.studio.ability_engine import describe
from wf.studio.drafts import DraftError


@pytest.mark.parametrize("value", ["60.5", "+60000", "60000.", ".5", "01", "-01", "1e5", "１２"])
def test_raw_numbers_reject_noncanonical_in_preview_and_apply(env, tmp_path, value):
    svc = service(env, tmp_path)
    body = balance_body(value)
    preview = svc.balance_preview(body)
    assert preview["rows"][0]["status"] == "需人工"
    with pytest.raises(DraftError):
        svc.balance_apply({**body, "review": preview["review"], "selected": [1]})
    assert not env[1].directory(OLD).exists()


def test_inactive_and_undeclared_numeric_cells_rejected():
    row = valid_row()
    row[5] = "1"
    with pytest.raises(DraftError):
        _replacement(row, "ability", row[51], "50000", "c51")
    row[5], row[47], row[57] = "0", "34", "60000000"
    with pytest.raises(DraftError):
        _replacement(row, "ability", row[57], "90000000", "c57")
    row[47] = "0"
    with pytest.raises(DraftError):
        _replacement(row, "ability", row[57], "-90000000", "c57")


@pytest.mark.parametrize("who,entry", [("", "能力1"), (OLD, "")])
def test_blank_identity_never_matches_nameless_character(who, entry):
    with pytest.raises(DraftError, match="不能为空"):
        convert_row(None, {"character": who, "entry": entry}, [{"id": OLD, "name": "", "code": ""}])


@pytest.mark.parametrize("table,columns,old,new,kind", [
    ("leader_ability", [49, 50], "100000", "120000", "34"),
    ("ability", [57, 58], "60000000", "90000000", "0"),
    ("ability", [59, 60], "300000", "500000", "0"),
    ("ability", [9, 10], "600000", "500000", "0"),
    ("ability", [51, 52], "300000", "500000", "203"),
    ("ability", [61], "3", "5", "0"),
    ("ability", [69], "1", "2", "251"),
])
def test_description_exact_units_and_folded_endpoints(table, columns, old, new, kind):
    row = valid_row()
    row[47] = kind
    if columns == [9, 10]:
        row[6], row[7], row[8] = "10", "5", "(None)"
    if table == "leader_ability":
        row = row[:1] + row[3:]
    after = list(row)
    for c in columns:
        row[c], after[c] = old, new
    before_text, after_text = describe(row, table), describe(after, table)
    assert before_text != after_text
    assert _replacement(row, table, before_text, after_text, "") == [
        {"column": c, "old": old, "new": new} for c in columns]


def test_balance_preview_uses_one_based_row(env, tmp_path):
    assert service(env, tmp_path).balance_preview(balance_body())["rows"][0]["changes"][0]["row"] == 1


def test_cli_remembered_optional_mapping_is_pruned(env, tmp_path, monkeypatch):
    import wf.studio.batch as module
    svc = service(env, tmp_path)
    svc.mapping(MAPPING)
    monkeypatch.setattr(module, "BatchEditor", lambda *a, **kw: svc)
    row = valid_row()
    after = list(row)
    after[51] = "20000"
    file = tmp_path / "table.tsv"
    file.write_text(f"对象\t项目\t旧\t新\n{OLD}\t能力1\t{describe(row, 'ability')}\t{describe(after, 'ability')}\n", encoding="utf-8")
    result = module.run_command(SimpleNamespace(file=file, mapping=None, remember_mapping=False,
                                select=[], review=None, server_dir=env[3]), env[2])
    assert result["mapping"]["row"] == result["mapping"]["column"] == ""
    assert result["rows"][0]["status"] == "可写草稿"
