"""Negative controls for unchanged delivery members and unknown clients."""
import json
import zipfile

import pytest

from test_studio_deliver_bridge import case, build
from wf.deliver.changeset import member_name, sha256
from wf.studio import deliver_bridge as bridge
from wf.studio.draft import main
from wf.studio.drafts import DraftError


def test_unchanged_shared_members_cannot_roll_back_an_intervening_package(case, monkeypatch):
    # Another package changes a different character in a shared positioning table.
    # A draft with only a changed asset must not re-ship the baseline shared table.
    monkeypatch.setattr(bridge, "compile_draft", lambda *a, **kw: (
        {("common", "test.bin"): b"new", ("medium", "test.bin"): b"untouched other layer"},
        {"assets/cdndata/character_text.json": b"baseline mirror"},
        {"assets/cdndata/character_text.json": sha256(b"baseline mirror")}, [], []))
    result = build(case, allow_unknown_client=True)
    assert result["ok"]
    doc = json.loads((case[-1] / "inputs/changeset.json").read_text("utf-8"))
    assert [(m["root"], m["logical_path"]) for m in doc["members"]] == [("common", "test.bin")]
    assert doc["server_changes"] == []
    installed = {member_name("medium", "test.bin"): b"new positioning for another character"}
    for archive in (case[-1] / "delivery").glob("*.zip"):
        with zipfile.ZipFile(archive) as handle:
            installed.update({name: handle.read(name) for name in handle.namelist()})
    assert installed[member_name("medium", "test.bin")] == b"new positioning for another character"
    assert not (case[-1] / "delivery/server/assets/cdndata/character_text.json").exists()


def test_changed_server_mirror_is_retained(case, monkeypatch):
    monkeypatch.setattr(bridge, "compile_draft", lambda *a, **kw: (
        {("common", "test.bin"): b"new"}, {"assets/cdndata/character_text.json": b"new mirror"},
        {"assets/cdndata/character_text.json": sha256(b"old mirror")}, [], []))
    # Stage directly: this test concerns byte filtering, not mirror JSON semantics.
    source = bridge.StudioSource(case[2])
    compiled = bridge.compile_draft(None, None, None)
    filename = bridge._stage(case[-1], case[1], source, compiled, "1.4.133")
    doc = json.loads(filename.read_text("utf-8"))
    assert len(doc["server_changes"]) == 1
    assert (filename.parent / doc["server_changes"][0]["source"]).read_bytes() == b"new mirror"


def test_noop_draft_does_not_emit_delivery(case, monkeypatch):
    monkeypatch.setattr(bridge, "compile_draft", lambda *a, **kw: (
        {("common", "test.bin"): b"old"}, {}, {}, [], []))
    with pytest.raises(DraftError, match="没有与基线不同"):
        build(case)
    assert not case[-1].exists()


@pytest.mark.parametrize("allow", [False, True])
def test_default_profile_and_explicit_unknown_client_override(case, capsys, allow):
    view = case[2]
    args = ["--drafts", str(case[0].root), "build", "139985", "--from", "1.4.132",
            "--to", "1.4.133", "--out", str(case[-1]),
            "--baseline-manifest", str(view.manifest), "--base-store", str(view.store),
            "--base-version", view.base_version]
    for directory in view.search_dirs:
        args.extend(["--baseline-zip-dir", str(directory)])
    for manifest in view.manifests or []:
        args.extend(["--baseline-manifest-extra", str(manifest)])
    if allow:
        args.append("--allow-unknown-client")
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["ok"] and result["compat"] == ("未确认" if allow else "满足")
    assert result["clientProfile"] == (None if allow else "test-v34")
    report = json.loads((case[-1] / "build-report.json").read_text("utf-8"))
    assert report["ok"] and report["allowUnknownClient"] is allow
    manifest = json.loads((case[-1] / "delivery/delivery-manifest.json").read_text("utf-8"))
    expected = {"status": "未确认" if allow else "满足", "allow_unknown_client": allow, "report": "compat.json"}
    if not allow:
        expected["client_profile"] = "test-v34"
    assert manifest["client_compatibility"] == expected
    from wf.check import main as check_main
    assert check_main([str(case[-1] / "delivery/delivery-manifest.json")]) == 0
    checks = json.loads((case[-1] / "delivery/check.json").read_text("utf-8"))["results"]
    assert not any(r["blocking"] for r in checks)
    if allow:
        assert next(r for r in checks if r["rule"] == "capability.unknown")["status"] == "待验证"


def test_explicit_override_cannot_bypass_missing_capability(case, monkeypatch):
    from wf.rules.catalog import result
    from wf.caps.profiles import resolve_client
    monkeypatch.setattr(bridge, "_checks", lambda *a: ([], [
        result("capability.missing", "问题", "缺少 desc_override", blocking=True)]))
    provides, _ = resolve_client()
    assert not build(case, provides=provides, allow_unknown_client=True)["ok"]


def test_provided_client_runs_real_compat(case):
    provides = case[-1].parent / "provides.json"
    provides.write_text(json.dumps({"schema": "wf-apk-provides/1",
        "source": {"kind": "patch-record", "basis": "unit fixture"},
        "patches": [], "provides": [], "unresolved": [], "limitations": []}), "utf-8")
    result = build(case, provides=provides)
    assert result["ok"] and result["compat"] == "满足"
    assert result["compatChecks"]


@pytest.mark.parametrize("identifier", ["code", "rule"])
def test_budget_warning_survives_delivery_readback(case, monkeypatch, identifier):
    warning = {identifier: "studio.pixel.budget", "state": "待验证", "blocking": False,
               "message": "三人房 layer0 需要验证", "layer0Pixels": 500000}
    monkeypatch.setattr(bridge, "compile_draft", lambda *a, **kw: (
        {("common", "test.bin"): b"new"}, {}, {}, [], [warning]))
    result = build(case, allow_unknown_client=True)
    assert result["ok"] and result["draftChecks"] == [warning]
    assert next(r for r in result["checks"] if r["rule"] == "studio.pixel.budget")["status"] == "待验证"
    assert json.loads((case[-1] / "delivery/draft-checks.json").read_text("utf-8")) == [warning]
