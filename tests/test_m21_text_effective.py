"""M4: rank rows replace base rows, including their actual skill descriptions."""
import copy
import json

import pytest

from test_m1_text import workspace  # noqa: F401
from wf.text.model import RANK_TARGET, SERVER_TARGET, TextWorkspace
from wf.text.rules import check_character
from wf.text.release import audit_workspace, write_report


def effective_findings(document):
    return [f for f in check_character(document) if f["rule"] == "text.server_effective"]


def test_rank_wins_and_stale_base_does_not_report_effective_mismatch(workspace):
    doc = workspace.read("1")
    doc["server_character_text"][0][5] = "已被覆盖的旧描述"
    checks = effective_findings(doc)
    assert checks and all(f["state"] == "满足" for f in checks)
    assert all(f["evidence"]["effective_source"] == RANK_TARGET for f in checks)


def test_base_is_effective_when_rank_has_no_character(workspace):
    doc = workspace.read("1")
    doc["server_character_text_rank_p5b"] = None
    doc["server_character_text"][0][7] = "旧描述"
    checks = effective_findings(doc)
    assert [f["location"] for f in checks if f["state"] == "问题"] == ["server_effective.1.c7"]
    assert all(f["evidence"]["effective_source"] == SERVER_TARGET for f in checks)


def test_rank_replaces_whole_row_instead_of_filling_from_base(workspace):
    doc = workspace.read("1")
    doc["server_character_text_rank_p5b"] = [["short"]]
    assert sum(f["state"] == "问题" for f in effective_findings(doc)) == 3


@pytest.mark.parametrize("target", [SERVER_TARGET, RANK_TARGET])
@pytest.mark.parametrize("invalid", [None, [], {}, [None], [[None]]])
def test_explicit_malformed_mirror_row_cannot_fall_back_to_base(workspace, target, invalid):
    path = workspace.server_paths[target]
    data = json.loads(path.read_bytes())
    data["1"] = invalid
    path.write_text(json.dumps(data), "utf-8")
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    with pytest.raises(ValueError, match="malformed server mirror"):
        current.read("1")


@pytest.mark.parametrize("missing", [SERVER_TARGET, RANK_TARGET])
def test_incomplete_mirror_inputs_cannot_pass(workspace, missing):
    doc = workspace.read("1")
    del doc["sources"][missing]
    checks = effective_findings(doc)
    assert len(checks) == 1 and checks[0]["state"] == "待验证"
    assert checks[0]["evidence"]["missing_sources"] == [missing]


def test_style_valid_server_drift_reaches_audit_and_cli(workspace, tmp_path, capsys):
    from wf.check import main
    rank = json.loads(workspace.rank_path.read_bytes())
    rank["1"][0][9] = "追加雷属性伤害"
    workspace.rank_path.write_text(json.dumps(rank), "utf-8")
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    report = audit_workspace(current)
    findings = [f for f in report["findings"] if f["rule"] == "text.server_effective"]
    assert len(findings) == 1 and findings[0]["location"] == "server_effective.1.c9"
    assert report["state"] == "问题"
    write_report(report, tmp_path / "audit.json")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(current.read("1")), "utf-8")
    assert main(["text", str(snapshot)]) == 1
    output = json.loads(capsys.readouterr().out)
    wording = next(r for r in output["files"][0]["results"] if r["rule"] == "text.wording")
    assert any(f["rule"] == "text.server_effective" and f["state"] == "问题" for f in wording["findings"])


def test_139985_historical_slow_case_detects_drift_then_passes_when_aligned(workspace):
    # Exact c5/c7 excerpts verified against the 1.4.227 client view and the
    # prepared rank delta (not a claim about deployed full server mirrors).
    client = ("【非Fever模式中】向全场撒下万圣糖果，赋予所有敌人「万圣糖果标记」＋迟缓效果"
              "（迟缓持续20秒）＋消除2个强化效果／Fever槽增加【Fever模式中】对持有「万圣糖果标记」"
              "的敌人造成雷属性伤害，对迟缓效果中的敌人追加雷属性伤害，随后移除「万圣糖果标记」")
    prepared = client.replace("，对迟缓效果中的敌人追加雷属性伤害", "【对迟缓效果中的敌人伤害提升】")
    doc = copy.deepcopy(workspace.read("1"))
    doc["character_id"] = "139985"
    for column in (5, 7):
        doc["character_text"][str(column)] = client
        doc["server_character_text"][0][column] = client
        doc["server_character_text_rank_p5b"][0][column] = prepared
    findings = [f for f in effective_findings(doc) if f["state"] == "问题"]
    assert [f["location"] for f in findings] == ["server_effective.139985.c5", "server_effective.139985.c7"]
    assert all(f["evidence"]["effective_source"] == RANK_TARGET for f in findings)
    for column in (5, 7):
        doc["server_character_text_rank_p5b"][0][column] = client
    assert all(f["state"] == "满足" for f in effective_findings(doc))
