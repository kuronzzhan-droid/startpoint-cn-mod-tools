"""Whole-table policy scans retain orphan overrides and both mirror inputs."""
import json

import pytest

import wf_quest_lib as codec
from test_m1_text import workspace  # noqa: F401
from wf.text.model import ACTION_SKILL, CUSTOM, TextWorkspace
from wf.text.release import audit_workspace, write_report


def test_audit_includes_unowned_overrides_and_all_tiers(workspace, tmp_path):
    custom = codec.parse_node(workspace.view.raw[CUSTOM])
    custom["desc_override_orphan_1"] = "PF伤害+10%。"
    workspace.view.raw[CUSTOM] = codec.build_node(custom)
    current = TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path)
    result = audit_workspace(current)
    assert result["state"] == "问题"
    orphan = [f for f in result["findings"] if "orphan" in f["location"]]
    assert {f["rule"] for f in orphan} >= {"text.standard.term-pf", "text.standard.no-final-stop"}
    assert result["checked_entries"] == 20  # 2 override + 6 client + 6 base + 6 rank.
    assert len([r for r in result["server_mirrors"] if r["state"] == "满足"]) == 2
    assert all(len(value) == 64 for value in result["sources"].values())
    path = write_report(result, tmp_path / "audit.json")
    assert json.loads(path.read_text("utf-8")) == result
    assert "desc_override_orphan_1" in path.with_suffix(".md").read_text("utf-8")


def test_absent_historical_mirrors_and_semantics_are_not_reported_pass(workspace):
    result = audit_workspace(TextWorkspace(workspace.view))
    assert result["state"] == "待验证"
    assert all(r["state"] == "未执行" for r in result["server_mirrors"])
    assert any(r["state"] == "待验证" for r in result["coverage"])


def test_audit_reads_both_mirrors_and_catches_rank_only_defect(workspace):
    data = json.loads(workspace.rank_path.read_bytes())
    data["1"][0][5] = "对敌人造成43倍火属性伤害"
    workspace.rank_path.write_text(json.dumps(data), "utf-8")
    result = audit_workspace(TextWorkspace(workspace.view, workspace.server_path, workspace.rank_path))
    assert any(f["location"].startswith("character_text_rank_p5b.json.1.c5") and
               f["rule"] == "text.standard.skill-damage-numbers" for f in result["findings"])
    assert not any(f["location"].startswith("character_text.json.") for f in result["findings"])


def test_malformed_skill_fails_audit_instead_of_disappearing(workspace):
    workspace.view.raw[ACTION_SKILL] = codec.build_node({"wolf": {"1": "single-column"}})
    with pytest.raises(ValueError, match="lacks c0/c1"):
        audit_workspace(TextWorkspace(workspace.view))


def test_report_rejects_external_or_colliding_output_before_writing(workspace, tmp_path):
    result = audit_workspace(workspace)
    with pytest.raises(PermissionError):
        write_report(result, tmp_path.anchor + "outside-text-audit.json")
    target = tmp_path / "audit.md"
    with pytest.raises(ValueError, match="must use .json"):
        write_report(result, target)
    assert not target.exists()


def test_cli_audit_and_rules_expose_data_and_nonzero_violation(workspace, tmp_path, monkeypatch):
    import wf.text.cli
    import wf.view
    monkeypatch.setattr(wf.text.cli, "restrict_writes", lambda: None)
    workspace.view.verify = lambda: None
    workspace.view.tip = "1.4.227"
    monkeypatch.setattr(wf.view, "ManifestView", lambda **kw: workspace.view)
    custom = codec.parse_node(workspace.view.raw[CUSTOM])
    custom["desc_override_orphan_1"] = "自身PF伤害+10%"
    workspace.view.raw[CUSTOM] = codec.build_node(custom)
    target = tmp_path / "audit.json"
    assert wf.text.cli.main(["audit-standard", "--tip", "1.4.227", "--output", str(target)]) == 1
    assert json.loads(target.read_bytes())["problem_count"] > 0
    rules = tmp_path / "rules.json"
    assert wf.text.cli.main(["rules", "--output", str(rules)]) == 0
    assert len(json.loads(rules.read_bytes())["rules"]) >= 50
