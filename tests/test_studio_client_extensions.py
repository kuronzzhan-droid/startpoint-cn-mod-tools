"""Synthetic p12/p13 tables, declarations and compatibility regressions."""
import json
import pytest
import wf_quest_lib as nodes
import wf_wfx

from wf.caps.compat import check_compat
from wf.caps.p13 import DEGRADED
from wf.caps.profiles import load_profiles, profile_options, read_client, resolve_client
from wf.caps.query import query_requirements
from wf.caps.registry import load_registry
from wf.caps.requirements import requirements_document
from wf.deliver.client_compatibility import compatibility_status
from wf.studio.client_extensions import MULTIBALL, PF, STRINGS, UNIQUE, check_client_extensions

CHARACTER = "master/character/character.orderedmap"


def tables(value="1:0", *, action="custom_pf", ball="7"):
    return {STRINGS: nodes.build_node({"wfx_summon_flip_pf_" + ball: value,
                                     "wfx_ball_pf_action_" + ball: action})}


def baseline():
    # Pin the real master path independently of the implementation constants.
    return {"master/battle/multiball/multiball.orderedmap": nodes.build_node({"7": "ball"}),
            "master/skill/power_flip_action.orderedmap": nodes.build_node({"custom_pf": "action"}),
            CHARACTER: nodes.build_node({})}


def requires(ids):
    return {"schemaVersion": 2, "pack": {"since": "1.0.0", "tail": "1.0.1",
            "anchor": {"from": "1.0.0", "to": "1.0.1"}, "archives": ["synthetic.zip"]},
            "requires": {"clientCapabilities": ids, "clientPatches": [], "serverFeatures": [],
                         "serverRestart": False, "restartReasons": [], "minServerVersion": None,
                         "capabilityResolution": "resolved"}}


@pytest.mark.parametrize("value", ["1", "1:0", "1:2147483647", '"1:0"'])
def test_valid_keys_use_baseline_and_known_empty_bundle(value):
    report = check_client_extensions(tables(value), baseline(), bundled_keys={PF: set()})
    assert report["status"] == "ok" and not report["checks"]
    assert set(report["requires"]) == {"client.summon.flip_pf@1", "client.ball.pf_action@1"}


def test_quoted_csv_and_reference_validation_have_the_same_contract():
    from wf.caps.signals_v35 import custom_signals
    signals = list(custom_signals("wfx_summon_flip_pf_7", '"1:0"'))
    assert not any(kind == "unsupported" for kind, _ in signals)
    signals = list(custom_signals("wfx_ball_pf_action_7", "custom_pf,extra"))
    assert any(kind == "unsupported" for kind, _ in signals)


@pytest.mark.parametrize("value", ["", "0", "01", "1:-1", "1:01", "1:2147483648", "1:1:2", "1:+1", "1: 2", "1,2", "1\n1"])
def test_bad_flip_values_block(value):
    report = check_client_extensions(tables(value), baseline(), bundled_keys={})
    assert report["status"] == "error"
    assert any(c["rule"] == "CLIENT_EXTENSION_FORMAT" and c["blocking"] for c in report["checks"])


@pytest.mark.parametrize("ball", ["", "07", "-7", "2147483648"])
def test_bad_ball_identifiers_block(ball):
    assert check_client_extensions(tables(ball=ball), baseline(), bundled_keys={})["status"] == "error"


@pytest.mark.parametrize("change,code", [("ball", "CLIENT_EXTENSION_MULTIBALL_MISSING"),
                                         ("action", "CLIENT_EXTENSION_ACTION_MISSING"),
                                         ("collision", "CLIENT_EXTENSION_ACTION_COLLISION")])
def test_bad_references_and_bundled_action_block(change, code):
    source = baseline()
    keys = {PF: {"custom_pf"}} if change == "collision" else {}
    if change in {"ball", "action"}:
        source[MULTIBALL if change == "ball" else PF] = nodes.build_node({})
    report = check_client_extensions(tables(), source, bundled_keys=keys)
    assert any(c["rule"] == code and c["blocking"] for c in report["checks"])


def test_outputs_override_baseline_and_no_apk_is_warning():
    output = {**tables(), MULTIBALL: nodes.build_node({}), PF: nodes.build_node({})}
    report = check_client_extensions(output, baseline())
    assert {c["rule"] for c in report["checks"]} == {"CLIENT_EXTENSION_MULTIBALL_MISSING",
            "CLIENT_EXTENSION_ACTION_MISSING", "CLIENT_EXTENSION_BUNDLE_UNCHECKED"}
    report = check_client_extensions(tables(), baseline())
    assert report["status"] == "warning" and not any(c["blocking"] for c in report["checks"])
    assert "未核对内置键" in report["checks"][0]["message"]


def test_corrupt_referenced_table_cannot_be_treated_as_missing():
    source = {**baseline(), MULTIBALL: b"broken"}
    report = check_client_extensions(tables(), source, bundled_keys={})
    assert report["status"] == "error" and report["checks"][0]["rule"] == "CLIENT_EXTENSION_TABLE_INVALID"


def test_unique_codes_are_registered_once_and_strict():
    import wfx_registry
    for code in (41, 42):
        assert sum(e["code"] == code for e in wfx_registry.load()["effect_codes"]) == 1
    assert wf_wfx.decode_sid("wfx:41:0:25:0:hidden_base").value == 25
    assert wf_wfx.decode_sid("wfx:42:3:7:1:hidden_dual").flags == 1
    for sid in ["wfx:41:1:25:0:x", "wfx:41:0:-1:0:x", "wfx:41:0:25:1:x", "wfx:42:4:7:0:x",
                "wfx:42:3:0:0:x", "wfx:42:3:7:2:x"]:
        with pytest.raises(ValueError):
            wf_wfx.decode_sid(sid)


def test_all_five_capabilities_infer_from_typed_output_tables():
    output = {**tables(), UNIQUE: nodes.build_node({"1": "wfx:41:0:25:0:hidden_base,0",
                                                  "2": "wfx:42:3:7:0:hidden_dual,0"}),
              MULTIBALL: nodes.build_node({"7": "ball,appearance,0,0,0,0,0,0,0,skill"})}
    members = {str(i): (raw, {"logical_path": logical}) for i, (logical, raw) in enumerate(output.items())}
    doc = requirements_document({"from_version": "1.0.0", "to_version": "1.0.1"}, members,
                                ["synthetic.zip"], read_raw=baseline().__getitem__)
    assert set(doc["requires"]["clientCapabilities"]) == set(DEGRADED)
    assert doc["requires"]["capabilityResolution"] == "resolved"
    report = check_client_extensions(output, baseline(), bundled_keys={})
    assert set(report["requires"]) == set(DEGRADED) and report["status"] == "ok"
    # Unchanged extension rows still travel in the full delivered table.
    same = {**baseline(), **output}
    doc = requirements_document({"from_version": "1.0.0", "to_version": "1.0.1"}, members,
                                ["synthetic.zip"], read_raw=same.__getitem__)
    assert set(doc["requires"]["clientCapabilities"]) == set(DEGRADED)


def test_profiles_resolve_without_manufactured_swf_or_method_evidence():
    _, records = load_profiles()
    options = {p["id"] for p in profile_options()["clientProfiles"]}
    assert {"p12b", "p13"} <= options
    for name, version, count in [("p12b", 1008033, 3), ("p13", 1008050, 5)]:
        path, selected = resolve_client(client_profile=name)
        evidence = read_client(path)
        assert selected == name and records[name]["versionCode"] == version
        assert evidence["source"]["verification"] == "report_declared"
        assert len(evidence["provides"]) == count
        assert "swf_sha256" not in evidence["source"]
        assert all(not row["methods"] and not row["patches"] for row in evidence["provides"])


def test_declared_profile_rejects_tampered_evidence(tmp_path):
    _, records = load_profiles()
    path, _ = resolve_client(client_profile="p13")
    document = read_client(path)
    document["provides"].pop()
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(document), "utf-8")
    with pytest.raises(ValueError, match="哈希"):
        read_client(edited, profile=records["p13"])


def test_missing_known_caps_degrade_support_stays_unverified_unknown_blocks():
    path, _ = resolve_client(client_profile="p12b")
    evidence = read_client(path)
    checks = check_compat(requires(list(DEGRADED)), evidence)
    assert not any(c["blocking"] for c in checks)
    assert compatibility_status(path, checks) == "降级"
    assert {c["id"] for c in checks if c.get("compatibility") == "degraded"} == {
        "client.ball.pf_action@1", "client.summon.flip_pf@1"}
    p13, _ = resolve_client(client_profile="p13")
    checks = check_compat(requires(list(DEGRADED)), read_client(p13))
    assert compatibility_status(p13, checks) == "待验证"
    assert all(c["rule"] == "capability.declared" for c in checks)
    assert check_compat(requires(["client.unregistered@1"]), evidence)[0]["blocking"]
    assert check_compat(requires(["client.wfx.effect_query@1"]), evidence)[0]["blocking"]
    assert not query_requirements(custom_keys=["wfx_summon_flip_pf_7"], client_profile="p12b")["selectedCompatible"]


def test_new_capability_definitions_pass_existing_registry_schema():
    registry = load_registry()
    assert set(DEGRADED) <= registry.keys()
    assert all(registry[c]["provided_by"]["status"] == "待补" for c in DEGRADED)


@pytest.mark.parametrize("key", ["wfx_summon_flip_pf_7", "wfx_ball_pf_action_7"])
def test_actual_ui_lookup_distinguishes_degraded_and_declared_without_blocking(key):
    from test_studio_deliver_routes import _FakeSource
    from wf.studio.server import StudioApp
    app = StudioApp(_FakeSource())
    response = app.dispatch("GET", "/api/studio/caps/lookup", {"customKey": [key]}, None)
    assert response.status == 200
    document = json.loads(response.body)
    p12b, p13 = document["profiles"]["p12b"], document["profiles"]["p13"]
    assert not p12b["compatible"] and p12b["degraded"] and not p12b["declared"]
    assert not p13["compatible"] and p13["declared"] and not p13["degraded"]
    assert not p12b["missing"] and not p13["missing"]
    assert p12b["pending"] and p13["pending"]
    assert not {"p12b", "p13"} & set(document["requiredClientProfiles"])
    # Delivery remains allowed for known missing extensions and declarations.
    cid = document["capabilities"][0]["id"]
    for profile in ("p12b", "p13"):
        path, _ = resolve_client(client_profile=profile)
        assert not any(c["blocking"] for c in check_compat(requires([cid]), read_client(path)))


def test_ui_generic_pending_check_keeps_existing_nonblocking_behavior(monkeypatch):
    from test_studio_deliver_routes import _FakeSource
    from wf.studio.server import StudioApp
    from wf.rules.catalog import result
    monkeypatch.setattr("wf.caps.compat.check_compat", lambda *args, **kwargs: [
        result("capability.provided", "待验证", "既有方法证据待补")])
    response = StudioApp(_FakeSource()).dispatch(
        "GET", "/api/studio/caps/lookup", {"customKey": ["wfx_summon_flip_pf_7"]}, None)
    assert response.status == 200
    for profile in json.loads(response.body)["profiles"].values():
        assert profile["compatible"] and not profile["degraded"] and not profile["declared"]
        assert not profile["missing"] and profile["pending"]
