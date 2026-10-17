"""Matrix regressions exercise data interpretation, not only saved output shapes."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wf.caps.scan import scan_characters
from wf.caps.scan_capabilities import compare_records, project_character
from wf.caps.scan_facts import Layout, dsl_facts
from wf.caps.scan_output import write_capability_matrix
from wf.caps.scan_source import ScanSource
from wf.paths import REPOSITORY


def source_for(monkeypatch, tmp_path, *, kind="419", levels="4", trigger="1", unique="fever:items:1|2"):
    """A PF/unique fixture whose ID intentionally does not hit per-character overrides."""
    monkeypatch.setattr("wf.caps.scan.provenance", lambda *args: {"999": ["1.4.209"]})
    enum = json.loads((REPOSITORY / "ability_enum_map.json").read_text("utf-8"))
    layout = Layout(enum, "ability")
    row = [""] * 126
    row[0], row[layout.trigger] = "example", trigger
    block = "instant" if trigger == "0" else "during"
    row[layout.col(f"{block}_content", "kind")] = kind
    row[layout.col(f"{block}_content", "powerflip_override.id")] = "pf"
    row[layout.col(f"{block}_content", "powerflip_override.levels")] = levels
    row[layout.unique_cols()[0]] = "22"
    char = [""] * 27
    char[0], char[8], char[19] = "example", "skill", "ability"
    tables = {"character": {"999": [char]}, "ability": {"ability": [row]},
              "power_flip": {"pf": [["example_pf"]]},
              "condition": {"22": [[unique, "Fever", "", "", "1"]]}}
    source = SimpleNamespace(
        baseline=SimpleNamespace(get=lambda *args: None), missing_dsl=set(),
        table=lambda name, official=False: {} if official else tables.get(name, {}),
        characters=lambda: [{"id": "999", "name": "测试", "title": "测试称号", "origin": "new"}],
        tree=lambda logical: ["ActionDsl", *([0] * 9), 133], locate=lambda logical: None,
        server_table=lambda filename: {})
    return source, tables


def test_pf4_and_fever_are_separate_from_official_pf(monkeypatch, tmp_path):
    from wf.caps.registry import load_registry
    source, _ = source_for(monkeypatch, tmp_path)
    record = scan_characters(source, tmp_path)[0]
    projected = project_character(record, {"999": {"mech": ["独有名字"]}}, load_registry())
    assert "client.pf.level4@1" in projected["capabilities"]
    assert "client.fever.items@1" in projected["capabilities"]
    assert "official.pf.special@1" in projected["capability_layers"]["B"]
    assert projected["layer_c"]["mech"] == ["独有名字"]


@pytest.mark.parametrize("levels", ["1,2,3", "14", "", "40"])
def test_non_lv4_values_do_not_claim_pf4(monkeypatch, tmp_path, levels):
    source, _ = source_for(monkeypatch, tmp_path, levels=levels)
    record = scan_characters(source, tmp_path)[0]
    assert not record["pf_overrides"][0]["lv4"]
    assert "PF Lv4(APK#87-89)" not in record["apk"]


def test_instant_419_is_not_a_pf_override(monkeypatch, tmp_path):
    source, _ = source_for(monkeypatch, tmp_path, trigger="0", unique="normal_fever")
    record = scan_characters(source, tmp_path)[0]
    assert not record["pf_overrides"]
    assert "Fever箭头换道具(APK#90-93)" not in record["apk"]


def test_broken_dsl_is_an_error_not_an_empty_capability_set(monkeypatch, tmp_path):
    source, _ = source_for(monkeypatch, tmp_path)
    def broken(_):
        raise ValueError("corrupt AMF")
    source.tree = broken
    with pytest.raises(ValueError, match="cannot scan DSL"):
        scan_characters(source, tmp_path)


def test_missing_dsl_is_reported(monkeypatch, tmp_path):
    source, _ = source_for(monkeypatch, tmp_path)
    source.tree = lambda _: None
    scan_characters(source, tmp_path)
    assert source.missing_dsl == {"example_pf.action.dsl.amf3.deflate"}


def test_dsl_conversion_requires_exact_slots():
    correct = ["CreateHitArea"] + [0] * 24
    correct[24] = 133
    wrong = ["CreateHitArea"] + [0] * 24
    wrong[23] = 133
    assert dsl_facts([correct])["bta"] == {133}
    assert not dsl_facts([wrong])["bta"]


def test_unknown_registry_id_refuses_projection(monkeypatch, tmp_path):
    source, _ = source_for(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="unregistered scanner capability"):
        project_character(scan_characters(source, tmp_path)[0], {}, {})


def test_comparison_detects_same_count_wrong_ids_and_field_drift():
    result = compare_records([{"id": "1", "apk": ["PF4"]}, {"id": "3"}],
                             [{"id": "1", "apk": []}, {"id": "2"}])
    assert result["current_count"] == result["reference_count"]
    assert not result["same_ids"]
    assert result["difference_count"] == 3
    with pytest.raises(ValueError, match="duplicate character"):
        compare_records([{"id": "1"}], [{"id": "1"}, {"id": "1"}])


def test_csv_uses_capability_ids_and_quotes_names(tmp_path):
    target = tmp_path / "matrix.csv"
    records = [{"id": "1", "name": "带,逗号", "title": "称号", "origin": "new",
                "capabilities": ["a@1"], "layer_c": {"mech": ["机制"]}}]
    write_capability_matrix(records, ["a@1", "b@1"], target)
    with target.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["name"] == "带,逗号"
    assert rows[0]["a@1"] == "1" and rows[0]["b@1"] == "0"


def test_missing_server_whitelist_is_not_empty(tmp_path):
    source = ScanSource.__new__(ScanSource)
    source._server = {}
    with pytest.raises(FileNotFoundError):
        source.server_table(tmp_path / "missing.json")


def test_empty_official_baseline_cannot_classify_everyone_new():
    source = ScanSource.__new__(ScanSource)
    source.table = lambda *args: {}
    with pytest.raises(ValueError, match="official character baseline is empty"):
        source.characters()


def test_changed_server_snapshot_is_rejected(tmp_path):
    filename = tmp_path / "character_overlimit.json"
    filename.write_text('{"characters": ["999"]}', "utf-8")
    source = ScanSource.__new__(ScanSource)
    source._server = {}
    source.server_table(filename)
    filename.write_text('{"characters": []}', "utf-8")
    with pytest.raises(ValueError, match="server mechanism input changed"):
        source.verify()


def test_cli_refuses_output_outside_checkout():
    import subprocess
    import sys
    outside = REPOSITORY.parent / "caps-scan-forbidden-output"
    assert not outside.exists()
    result = subprocess.run([sys.executable, "-B", "-m", "wf.caps.cli", "scan",
                             "--tip", "1.4.224", "--output", str(outside)],
                            cwd=REPOSITORY, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert "outside checkout" in result.stdout
    assert not outside.exists()
