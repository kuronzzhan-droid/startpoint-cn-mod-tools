"""Review regressions for malformed markers, APK errors and failed builds."""
import json

import pytest
import wf_quest_lib as nodes

from wf.studio.client_extensions import PF, STRINGS, UNIQUE, MULTIBALL, check_client_extensions
from wf.studio.delivery_safety import inspect_output
from wf.studio import bundle_keys, deliver_bridge
from wf.studio.key_diff import compare_delivery, markdown
from test_studio_bundle_keys import apk_file, bundled_member
from test_studio_deliver_bridge import case, build  # noqa: F401
from test_studio_safety_integration import isolated_machine_settings, baseline_tables, compiled  # noqa: F401
from test_studio_key_diff import View, delivered


@pytest.mark.parametrize("sid", ["wfx:41:0:05:0:label", "wfx:42:3:07:0:label",
    "wfx:41:0:+25:0:label", "WFX:41:0:25:0:label", "wFx:42:3:7:0:label", "wfx:41", "wfx:42"])
def test_studio_wfx_invalid_markers_match_release_gate_and_persist(case, monkeypatch, sid):
    from wf.caps.signals_v35 import wfx_problem
    assert wfx_problem(sid)
    raw = nodes.build_node({"7": sid})
    report = check_client_extensions({UNIQUE: raw})
    assert report["status"] == "error"
    assert any(c["rule"] == "CLIENT_EXTENSION_FORMAT" for c in report["checks"])
    fixture = baseline_tables(case, {UNIQUE: nodes.build_node({})})
    compiled(monkeypatch, UNIQUE, raw)
    result = build(fixture, allow_unknown_client=True)
    saved = json.loads((fixture[-1] / "build-report.json").read_text("utf-8"))
    assert saved == result and not result["ok"]
    assert result["clientExtensions"]["status"] == "error"
    assert (fixture[-1] / "delivery/client-extensions.json").is_file()


@pytest.mark.parametrize("damage", ["missing", "broken_zip", "broken_pf", "collision", "clean"])
def test_studio_apk_reference_index_is_loaded_once_and_errors_are_not_skips(tmp_path, monkeypatch, damage):
    raw = nodes.build_node({"wfx_ball_pf_action_7": "native_pf"})
    baseline = View({PF: nodes.build_node({"native_pf": "action"}), MULTIBALL: nodes.build_node({"7": "ball"})})
    apk = tmp_path / "client.apk"
    if damage == "broken_zip":
        apk.write_bytes(b"broken zip")
    elif damage != "missing":
        data = b"broken header" if damage == "broken_pf" else nodes.build_node({
            "native_pf" if damage == "collision" else "other_pf": "action"})
        apk_file(tmp_path, [(bundled_member(PF), data)])
    original = bundle_keys.load_bundle_index
    calls = []
    def load(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(bundle_keys, "load_bundle_index", load)
    reports, _ = inspect_output([delivered(STRINGS, raw)], baseline, {}, apks=[apk])
    assert len(calls) == 1 and PF in calls[0]["logical_paths"]
    extension = reports["clientExtensions"]
    rules = {c["rule"] for c in extension["checks"]}
    assert "CLIENT_EXTENSION_BUNDLE_UNCHECKED" not in rules
    if damage in {"missing", "broken_zip", "broken_pf"}:
        assert reports["bundleCheck"]["status"] == "error"
        assert "CLIENT_EXTENSION_BUNDLE_ERROR" in rules and extension["status"] == "error"
    elif damage == "collision":
        assert "CLIENT_EXTENSION_ACTION_COLLISION" in rules
    else:
        assert extension["status"] == "ok"


@pytest.mark.parametrize("old,new,kind", [
    ({"root": {"1": "one", "2": "two"}}, {"root": {"1": "one"}}, "nested_key_removed"),
    ({"root": {"level": {"1": "one", "2": "two"}}}, {"root": {"level": {"1": "one"}}}, "nested_key_removed"),
    ({"root": "one\ntwo"}, {"root": "two"}, "csv_rows_removed"),
    ({"root": {"1": "one\ntwo"}}, {"root": {"1": "one"}}, "csv_rows_removed"),
    ({"root": {"1": "one"}}, {"root": "text"}, "nested_map_replaced"),
])
def test_studio_inner_deletions_block_key_diff_and_build_with_reports(case, monkeypatch, old, new, kind):
    # A shared table exercises the real existing delivery preservation guard too.
    before, after = nodes.build_node(old), nodes.build_node(new)
    diff = compare_delivery(View({STRINGS: before}), members=[delivered(STRINGS, after)])
    assert not diff["ok"] and diff["tables"][0]["removed"] == ["root"]
    detail = diff["tables"][0]["deletions"][0]
    assert detail["kind"] == kind and detail["path"][0] == "root"
    assert kind in markdown(diff)
    fixture = baseline_tables(case, {STRINGS: before})
    compiled(monkeypatch, STRINGS, after)
    result = build(fixture, allow_unknown_client=True)
    assert not result["ok"] and not result["keyDiff"]["ok"]
    assert json.loads((fixture[-1] / "build-report.json").read_text("utf-8")) == result
    assert (fixture[-1] / "delivery/key-diff.json").is_file()


def test_studio_multiline_csv_is_one_record_and_equal_counts_are_not_deletions():
    before = nodes.build_node({"row": '"one\ntwo",x\nother,y'})
    after = nodes.build_node({"row": 'changed,x\nother,y'})
    diff = compare_delivery(View({STRINGS: before}), members=[delivered(STRINGS, after)])
    assert diff["ok"] and not diff["tables"][0]["deletions"]


@pytest.mark.parametrize("extension_error", [False, True])
def test_studio_unrelated_value_error_is_preserved_with_or_without_other_failures(case, monkeypatch, extension_error):
    if extension_error:
        compiled(monkeypatch, STRINGS, nodes.build_node({"wfx_summon_flip_pf_7": "1:-1"}))
    def fail(*args, **kwargs):
        raise ValueError("synthetic independent server mirror gate failure")
    monkeypatch.setattr(deliver_bridge, "build_delivery", fail)
    result = build(case, allow_unknown_client=True)
    assert not result["ok"]
    assert result["prepush"]["limitations"] == [result["buildError"]["message"]]
    assert result["buildError"]["message"] == "synthetic independent server mirror gate failure"
    assert json.loads((case[-1] / "build-report.json").read_text("utf-8")) == result


def test_studio_failed_secondary_inspection_cannot_erase_original_failure(case, monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("original gate failure")
    def inspect(*args, **kwargs):
        raise ValueError("secondary inspection failure")
    monkeypatch.setattr(deliver_bridge, "build_delivery", fail)
    monkeypatch.setattr("wf.studio.delivery_safety.inspect_output", inspect)
    result = build(case, allow_unknown_client=True)
    assert not result["ok"] and result["buildError"]["message"] == "original gate failure"
    assert result["inspectionError"]["message"] == "secondary inspection failure"
    assert json.loads((case[-1] / "build-report.json").read_text("utf-8")) == result
