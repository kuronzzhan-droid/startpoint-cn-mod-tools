"""Boss CLI returns the same five-state gates and rejects real negative rows."""
import json

import pytest

from wf.check import check_file, main
from wf.rules.boss import assert_boss, check_boss
from wf.rules.catalog import EVIDENCE, catalog


def snapshot():
    row = [""] * 125
    row[5], row[6] = "2000-01-01 00:00:00", "(None)"
    objects = [{"type": value} for value in ("BOUNDS", "WALL", "RETURN_LANE_GUIDE")]
    objects += [{"type": "CUSTOM_POSITION", "name": "p0"}] + [{"type": "COFFIN"}] * 9
    return {"schema": "wf-boss/1", "quest": {"kind": "hard_multi", "row": row},
            "field": {"row": [""] * 7 + ["gate", "transit"]},
            "zone": {"rows": [{"path": ["z", "0"], "row": [""] * 35}]},
            "terrain": {"waves": [{"name": "0", "objects": objects}]}, "shops": []}


def test_all_requested_rules_have_evidence_and_executable_checker():
    required = {"boss.multiwave-field", "boss.terrain-layers", "boss.concurrent-positions",
                "boss.element-preload", "boss.choice-folder", "boss.both-route", "boss.custom-time",
                "delivery.reward-keys", "boss.shop-sync", "art.atlas-budget", "boss.visible-prerequisites"}
    rules = {r["id"]: r for r in catalog()["rules"]}
    assert required <= rules.keys()
    assert all(rules[key]["checker"] for key in required)
    assert all(rules[key]["evidence_nature"] in EVIDENCE for key in required)
    checks = check_boss(snapshot())
    assert required <= {r["rule"] for r in checks}
    assert all(r.get("source") and r.get("evidence_nature") in EVIDENCE for r in checks)


def test_cli_snapshot_passes_static_checks_and_preserves_unexecuted(tmp_path, capsys):
    path = tmp_path / "boss.json"
    path.write_text(json.dumps(snapshot()), encoding="utf-8")
    assert main(["boss", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    checks = {r["rule"]: r for r in report["files"][0]["results"]}
    assert checks["boss.terrain-layers"]["status"] == "满足"
    assert checks["delivery.reward-keys"]["status"] == "未执行"
    assert check_file(path) == check_boss(snapshot())


def test_cli_and_assert_reject_multilayer_missing_c7(tmp_path, capsys):
    doc = snapshot()
    second = {"name": "1", "objects": list(doc["terrain"]["waves"][0]["objects"])}
    doc["terrain"]["waves"].append(second)
    doc["field"]["row"][7] = ""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["boss", str(path)]) == 1
    assert "boss.multiwave-field" in capsys.readouterr().out
    with pytest.raises(ValueError, match="boss.multiwave-field"):
        assert_boss(doc)


def test_wrong_snapshot_schema_is_input_error(tmp_path, capsys):
    path = tmp_path / "wrong.json"
    path.write_text('{}', encoding='utf-8')
    assert main(["boss", str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["files"][0]["results"][0]["rule"] == "input"


def test_cli_does_not_auto_discover_unrequested_manifests(monkeypatch, capsys):
    from wf.rules import boss_cli
    captured = []

    def check_inputs(args):
        captured.append(args.extra_manifest)
        return [{"file": "1", "results": [{"blocking": False, "status": "满足"}]}]

    monkeypatch.setattr(boss_cli, "check_inputs", check_inputs)
    assert main(["boss", "1"]) == 0
    capsys.readouterr()
    assert captured == [[]]
