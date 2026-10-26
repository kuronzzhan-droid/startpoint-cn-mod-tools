"""End-to-end delivery gates with tiny archives and offline HTTP/CLI adapters."""
import json
from pathlib import Path
import zipfile

import pytest

from wf.deliver.changeset import member_name
from wf.check import check_file
from wf.studio import bundle_keys, deliver_bridge
from wf.studio.draft import main
from wf.studio.key_diff import KEY_LISTS, compare_delivery, write_reports
from wf.view import ManifestView

from test_studio_bundle_keys import apk_file, delivery as fixture_delivery
from test_studio_deliver_bridge import build, case  # noqa: F401 - shared synthetic fixture
from test_studio_deliver_routes import _json, routes  # noqa: F401 - shared HTTP fixture
from test_studio_key_diff import CHARACTER, CUSTOM, PF, View, character, delivered, leaf, ordered


@pytest.fixture(autouse=True)
def isolated_machine_settings(tmp_path, monkeypatch):
    # The real cache remains forbidden inside the real checkout; this test-only
    # repository marker allows a synthetic cache under pytest's audited temp root.
    monkeypatch.setattr(bundle_keys, "REPOSITORY", tmp_path / "synthetic-repository")
    monkeypatch.setattr("wf.studio.delivery_inputs.configured_path", lambda _: tmp_path / "no-pathlist")
    monkeypatch.setattr("wf.paths.profile_data", lambda: ({}, tmp_path / "local.json"))
    monkeypatch.setattr("wf.view.config.profile_data", lambda: ({}, tmp_path / "local.json"))
    monkeypatch.setenv("WF_STUDIO_BUNDLE_CACHE", str(tmp_path / "bundle-cache"))


def compiled(monkeypatch, logical, data):
    monkeypatch.setattr(deliver_bridge, "compile_draft", lambda *a, **kw: (
        {("common", logical): data}, {}, {}, [{"old": "before", "new": "after"}], []))


def baseline_tables(case, tables):
    """Replace synthetic fixture bytes, then open a fresh locked view."""
    drafts, changeset, view, out = case
    archive_path = view.zips[0]
    with zipfile.ZipFile(archive_path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files.update({member_name("common", logical): raw for logical, raw in tables.items()})
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    refreshed = ManifestView(view.tip, store=view.store, manifest=view.manifest, search_dirs=view.search_dirs)
    return drafts, changeset, refreshed, out


def test_safety_build_skipped_apk_is_explicit_warning_and_writes_artifacts(case):
    result = build(case, allow_unknown_client=True)
    assert result["ok"]
    assert result["bundleCheck"]["status"] == "skipped"
    assert result["bundleCheck"]["reason"]
    assert result["iconAlpha"]["status"] == "skipped"
    assert result["keyDiff"]["status"] == "ok"
    delivery = case[-1] / "delivery"
    for name in ("bundle-check.json", "key-diff.json", "key-diff.md", "icon-alpha.json"):
        assert (delivery / name).is_file()
    assert json.loads((delivery / "bundle-check.json").read_text("utf-8"))["status"] == "skipped"


def test_safety_build_bundle_collision_blocks_and_keeps_result(case, tmp_path, monkeypatch):
    compiled(monkeypatch, PF, ordered({"ranged": leaf("fixture")}))
    apk = apk_file(tmp_path)
    result = build(case, allow_unknown_client=True, apk=[apk], bundle_cache_dir=tmp_path / "cache")
    assert not result["ok"]
    assert result["bundleCheck"]["status"] == "collision"
    assert result["bundleCheck"]["tables"][0]["collisions"] == ["ranged"]
    saved = json.loads((case[-1] / "delivery/bundle-check.json").read_text("utf-8"))
    assert saved == result["bundleCheck"]
    reread = check_file(case[-1] / "delivery/delivery-manifest.json")
    assert any(check["rule"] == "studio.bundle-keys" and check["blocking"] for check in reread)


def test_safety_build_bundle_parse_error_is_blocking_json(case, tmp_path, monkeypatch):
    compiled(monkeypatch, PF, ordered({"fixture_pf": leaf("fixture")}))
    apk = tmp_path / "broken.apk"
    apk.write_bytes(b"invalid archive")
    result = build(case, allow_unknown_client=True, apk=str(apk), bundle_cache_dir=tmp_path / "cache")
    assert not result["ok"] and result["bundleCheck"]["status"] == "error"
    assert result["bundleCheck"]["reason"]
    assert (case[-1] / "delivery/bundle-check.json").is_file()


def test_safety_build_removed_key_blocks_and_retains_handoff(case, monkeypatch):
    fixture = baseline_tables(case, {CUSTOM: ordered({"demo_keep": leaf("x"), "someone_old": leaf("old")})})
    compiled(monkeypatch, CUSTOM, ordered({"demo_keep": leaf("new")}))
    result = build(fixture, allow_unknown_client=True)
    assert not result["ok"] and result["keyDiff"]["blocking"]
    assert result["keyDiff"]["tables"][0]["removed"] == ["someone_old"]
    delivery = fixture[-1] / "delivery"
    assert json.loads((delivery / "key-diff.json").read_text("utf-8"))["counts"]["removed"] == 1
    assert "someone_old" in (delivery / "key-diff.md").read_text("utf-8")


def test_safety_build_foreign_key_warns_without_hard_block(case, monkeypatch):
    fixture = baseline_tables(case, {CHARACTER: ordered({"139985": character("demo"), "22": character("other")}),
                                     CUSTOM: ordered({"other_text": leaf("before")})})
    compiled(monkeypatch, CUSTOM, ordered({"other_text": leaf("after")}))
    result = build(fixture, allow_unknown_client=True)
    assert result["keyDiff"]["status"] == "warning" and not result["keyDiff"]["blocking"]
    assert result["keyDiff"]["tables"][0]["foreign"] == ["other_text"]
    assert result["ok"]


def test_safety_http_detail_missing_reports_are_null_then_summary_is_bounded(routes):
    _, deliver = routes
    name = "139985-1.4.236-to-1.4.237-20261026-010101"
    folder = deliver.root / name
    delivery = folder / "delivery"
    delivery.mkdir(parents=True)
    absent = _json(deliver.detail({}, name))
    for field in ("bundleCheck", "keyDiff", "iconAlpha"):
        assert absent[field] is None
    report = compare_delivery(View(), members=[delivered(CUSTOM, ordered({f"key_{i}": leaf("x") for i in range(250)}))])
    write_reports(report, delivery)
    (folder / "build-report.json").write_text(json.dumps({"ok": True, "keyDiff": report}), "utf-8")
    bundle = {"status": "skipped", "reason": "fixture", "apks": [], "tables": []}
    alpha = {"status": "warning", "slots": [{"slot": "square_0", "ratio": 1.0}]}
    (delivery / "bundle-check.json").write_text(json.dumps(bundle), "utf-8")
    (delivery / "icon-alpha.json").write_text(json.dumps(alpha), "utf-8")
    detail = _json(deliver.detail({}, name))
    assert detail["bundleCheck"] == bundle and detail["iconAlpha"] == alpha
    table = detail["keyDiff"]["tables"][0]
    assert table["counts"]["added"] == 250 and table["counts"]["unknown"] == 250
    assert sum(len(table[key]) for key in KEY_LISTS) <= 200 and table["truncated"]
    nested = detail["report"]["keyDiff"]["tables"][0]
    assert sum(len(nested[key]) for key in KEY_LISTS) <= 200 and nested["truncated"]


def test_safety_cli_build_passes_repeated_apks_to_bridge(case, monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr("wf.studio.build_view.baseline_from_args", lambda args: case[2])
    def fake_build(cid, **kwargs):
        seen.update(kwargs)
        return {"ok": True}
    monkeypatch.setattr(deliver_bridge, "build_draft", fake_build)
    code = main(["build", "139985", "--from", "1.4.132", "--to", "1.4.133",
                 "--out", str(case[-1]), "--apk", "first.apk", "--apk", "second.apk"])
    assert code == 0 and json.loads(capsys.readouterr().out)["ok"]
    assert list(map(str, seen["apk"])) == ["first.apk", "second.apk"]


@pytest.mark.parametrize("apks", ["fixture.apk", ["first.apk", "second.apk"]])
def test_safety_http_build_passes_explicit_apk_selection(routes, monkeypatch, apks):
    _, deliver = routes
    seen = {}
    def fake_build(cid, **kwargs):
        seen.update(kwargs)
        return {"ok": True}
    monkeypatch.setattr(deliver_bridge, "build_draft", fake_build)
    result = _json(deliver.build({}, {"apk": apks}, "139985"))
    expected = [apks] if isinstance(apks, str) else apks
    assert result["ok"] and [Path(value).name for value in seen["apk"]] == expected
    assert all(Path(value).is_absolute() for value in seen["apk"])


def test_safety_bundle_cli_emits_direct_json_and_collision_exit(tmp_path, capsys):
    apk = apk_file(tmp_path)
    archive = fixture_delivery(tmp_path)
    assert main(["bundle-check", "--apk", str(apk), "--zip", str(archive)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "collision" and "result" not in output
    assert output["tables"][0]["collisions"] == ["ranged"]


@pytest.mark.parametrize("removed", [False, True])
def test_safety_key_diff_cli_named_view_tip_full_markdown_and_exit(case, tmp_path, monkeypatch, capsys, removed):
    fixture = baseline_tables(case, {CUSTOM: ordered({"old": leaf("before")}) if removed else ordered({})})
    view = fixture[2]
    config = {"wf_root": str(tmp_path), "views": {"fixture": {
        "store": str(view.store), "manifest": str(view.manifest), "zip_dirs": []}}}
    monkeypatch.setattr("wf.paths.profile_data", lambda: (config, tmp_path / "local.json"))
    monkeypatch.setattr("wf.view.config.profile_data", lambda: (config, tmp_path / "local.json"))
    archive = fixture_delivery(tmp_path, logical=CUSTOM,
                               data=ordered({f"demo_text_{i}": leaf("x") for i in range(250)}))
    md = tmp_path / "key-diff.md"
    code = main(["key-diff", "--view", "fixture", "--tip", "132", "--zip", str(archive),
                 "--subject", "139985", "--md", str(md)])
    output = json.loads(capsys.readouterr().out)
    assert code == (1 if removed else 0) and output["ok"] is not removed, output
    assert output["baseline"]["view"] == "fixture" and output["baseline"]["tip"] == "1.4.132"
    assert output["subject"]["code"] == "demo" and output["counts"]["added"] == 250
    assert md.read_text("utf-8").count("`demo_text_") == 500


@pytest.mark.parametrize("key,value,code", [
    ("wfx_summon_flip_pf_7001", "1:01", "CLIENT_EXTENSION_FORMAT"),
    ("wfx_ball_pf_action_7001", "missing_pf", "CLIENT_EXTENSION_ACTION_MISSING"),
])
def test_safety_client_extension_errors_block_with_persisted_evidence(case, monkeypatch, key, value, code):
    fixture = baseline_tables(case, {"master/battle/multiball/multiball.orderedmap": ordered({"7001": leaf("fixture")})})
    compiled(monkeypatch, CUSTOM, ordered({key: leaf(value)}))
    result = build(fixture, allow_unknown_client=True)
    assert not result["ok"] and result["clientExtensions"]["status"] == "error"
    assert any(check["rule"] == code and check["blocking"] for check in result["clientExtensions"]["checks"])
    saved = json.loads((fixture[-1] / "delivery/client-extensions.json").read_text("utf-8"))
    assert saved == result["clientExtensions"]


def test_safety_valid_extension_uses_actual_multiball_path_and_p12b_degrades(case, monkeypatch):
    fixture = baseline_tables(case, {
        "master/battle/multiball/multiball.orderedmap": ordered({"7001": leaf("fixture")}),
        PF: ordered({"demo_pf": leaf("fixture")}),
        CUSTOM: ordered({}),
    })
    compiled(monkeypatch, CUSTOM, ordered({"wfx_ball_pf_action_7001": leaf("demo_pf")}))
    result = build(fixture, client_profile="p12b")
    assert not any(check["blocking"] for check in result["clientExtensions"]["checks"])
    assert "client.ball.pf_action@1" in result["clientExtensions"]["requires"]
    assert any(check.get("compatibility") == "degraded" for check in result["compatChecks"])
    assert result["ok"]
    reread = check_file(fixture[-1] / "delivery/delivery-manifest.json")
    assert not any(check["blocking"] for check in reread)
    assert any(check.get("compatibility") == "degraded" for check in reread)


@pytest.mark.parametrize("damage", [
    "empty", "non_object", "missing_bundle", "missing_diff", "duplicate_bundle", "duplicate_diff",
    "forged_bundle_status", "forged_diff_blocking", "missing_detail", "broken_detail", "non_object_detail",
    "forged_bundle_detail", "forged_diff_detail", "forged_extension_status", "missing_extension_finding",
    "forged_extension_blocking", "non_object_draft",
])
def test_safety_readback_rejects_missing_corrupt_or_contradictory_evidence(case, damage):
    result = build(case, allow_unknown_client=True)
    assert result["ok"]
    directory = case[-1] / "delivery"
    filename = directory / "safety-checks.json"
    checks = json.loads(filename.read_text("utf-8"))
    if damage == "empty":
        checks = []
    elif damage == "non_object":
        checks = [0]
    elif damage in {"missing_bundle", "missing_diff", "duplicate_bundle", "duplicate_diff"}:
        rule = "studio.bundle-keys" if damage.endswith("bundle") else "studio.key-diff"
        if damage.startswith("missing"):
            checks = [entry for entry in checks if entry["rule"] != rule]
        else:
            checks.append(next(entry.copy() for entry in checks if entry["rule"] == rule))
    elif damage == "forged_bundle_status":
        next(entry for entry in checks if entry["rule"] == "studio.bundle-keys")["status"] = "满足"
    elif damage == "forged_diff_blocking":
        next(entry for entry in checks if entry["rule"] == "studio.key-diff")["blocking"] = True
    elif damage in {"missing_detail", "broken_detail", "non_object_detail"}:
        target = directory / "bundle-check.json"
        if damage == "missing_detail":
            target.unlink()
        else:
            target.write_text("{" if damage == "broken_detail" else "[]", "utf-8")
    elif damage == "forged_bundle_detail":
        target = directory / "bundle-check.json"
        detail = json.loads(target.read_text("utf-8"))
        detail["status"] = "ok"
        target.write_text(json.dumps(detail), "utf-8")
    elif damage == "forged_diff_detail":
        target = directory / "key-diff.json"
        detail = json.loads(target.read_text("utf-8"))
        detail["counts"]["removed"] = 1
        target.write_text(json.dumps(detail), "utf-8")
    elif damage.startswith("forged_extension") or damage == "missing_extension_finding":
        target = directory / "client-extensions.json"
        detail = json.loads(target.read_text("utf-8"))
        detail["status"] = "error"
        if damage != "forged_extension_status":
            detail["checks"] = [{"rule": "CLIENT_EXTENSION_FORMAT", "status": "问题",
                                  "blocking": True, "message": "synthetic invalid extension"}]
        if damage == "forged_extension_blocking":
            checks.insert(0, {**detail["checks"][0], "blocking": False})
        target.write_text(json.dumps(detail), "utf-8")
    else:
        (directory / "draft-checks.json").write_text("[0]", "utf-8")
    filename.write_text(json.dumps(checks), "utf-8")
    reread = check_file(directory / "delivery-manifest.json")
    assert any(check["rule"] == "input" and check["blocking"] for check in reread), reread


def test_safety_readback_rejects_collision_detail_forged_as_ok(case, tmp_path, monkeypatch):
    compiled(monkeypatch, PF, ordered({"ranged": leaf("fixture")}))
    result = build(case, allow_unknown_client=True, apk=[apk_file(tmp_path)])
    assert not result["ok"]
    directory = case[-1] / "delivery"
    detail_path = directory / "bundle-check.json"
    detail = json.loads(detail_path.read_text("utf-8"))
    detail["status"] = "ok"
    detail_path.write_text(json.dumps(detail), "utf-8")
    filename = directory / "safety-checks.json"
    checks = json.loads(filename.read_text("utf-8"))
    next(entry for entry in checks if entry["rule"] == "studio.bundle-keys").update(
        status="满足", blocking=False, level="info")
    filename.write_text(json.dumps(checks), "utf-8")
    reread = check_file(directory / "delivery-manifest.json")
    assert any(check["rule"] == "input" and check["blocking"] for check in reread)


def test_safety_readback_keeps_historical_manifest_and_draft_content_contract(case):
    build(case, allow_unknown_client=True)
    directory = case[-1] / "delivery"
    manifest_path = directory / "delivery-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    del manifest["safety_checks"]
    manifest_path.write_text(json.dumps(manifest), "utf-8")
    for name in ("safety-checks.json", "bundle-check.json", "key-diff.json", "client-extensions.json"):
        (directory / name).unlink()
    (directory / "draft-checks.json").write_text('[{"message": "historical partial draft check"}]', "utf-8")
    reread = check_file(manifest_path)
    assert not any(check["blocking"] for check in reread)
    assert any(check["rule"] == "studio.draft" and check["status"] == "待验证" for check in reread)
