"""v35 parameter rows must not inherit the old, planned pin-bit semantics."""
import json

import pytest

import wf_wfx as codec
import wfx_gate
import wfx_registry
from wf.wfx_semantics import hidden_icon_capability


@pytest.mark.parametrize("code,arg,value,flags", [
    (24, 3, 2500, 5), (25, 0, 0, 1), (26, 19, -100000, 3),
    (27, 1, 3000, 0), (28, 123, 3000, -2147483648),
    (29, 123, -500, -1), (60, 123, 10000, 250),
    (61, 0, 5000, 999), (62, 0, -500, 0), (71, 9, 10000, 1),
])
def test_v35_parameters_roundtrip_without_pin(code, arg, value, flags):
    sid = codec.encode_sid(code, arg, value, flags, "sample")
    spec = codec.decode_sid(sid)
    assert spec.sid == sid
    assert (spec.code, spec.arg, spec.value, spec.flags) == (code, arg, value, flags)
    assert not spec.pin
    assert "wfx-core-v1" not in codec.required_capabilities(spec)
    row = codec.unique_row(sid, "参数", "unique_zeta", "900", "99",
                           bad=False, cancelable=True)
    assert codec.unique_row_problems(row) == []


@pytest.mark.parametrize("sid", [
    "wfx:24:4:1:0:a", "wfx:27:2:1:0:a", "wfx:61:1:1:0:a",
    "wfx:62:1:1:0:a", "wfx:27:0:1:1:a", "wfx:60:123:1:0:a",
    "wfx:28:123:1:-2147483649:a", "wfx:29:123:1:2147483648:a",
    "wfx:28:123:1:-0:a", "wfx:28:123:1:-01:a",
    "wfx:26:0:1:-1:a", "wfx:24:0:1.5:0:a", "wfx:27:0:-1:0:a",
])
def test_v35_parameters_reject_invalid_encoding_and_ranges(sid):
    with pytest.raises(codec.WfxError):
        codec.decode_sid(sid)


@pytest.mark.parametrize("sid,hidden", [
    ("wfx:24:0:2500:0:hidden_name", True),
    ("wfx:24:0:2500:0:hidden_", True),
    ("wfx:24:0:2500:0:hidden_name:extra", True),
    ("wfx:bad:bad:bad:bad:hidden_name", True),
    ("wfx:24:0:2500:0:Hidden_name", False),
    ("wfx:24:0:2500:0:xhidden_name", False),
    ("wfx:24:0:2500:0", False),
    ("wfx:24:0:2500:0:", False),
    ("wfx:24:0:2500:0:ordinary:hidden_name", False),
    ("hidden_old_marker", False),
    ("WFX:24:0:2500:0:hidden_name", False),
])
def test_hidden_filter_matches_run5_display_scope(sid, hidden):
    expected = "wfx-hidden-unique-icons-v1" if hidden else None
    assert hidden_icon_capability(wfx_registry.load(), sid) == expected


def test_hidden_label_requires_both_effect_and_visibility_capabilities():
    spec = codec.decode_sid("wfx:29:123:2500:-1:hidden_claus")
    assert set(codec.required_capabilities(spec)) == {
        "direct-base-v1", "wfx-effect-query-v1", "wfx-hidden-unique-icons-v1"}


def test_real_v35_profile_rejects_unsupported_v34_and_passes_v35e():
    sid = "wfx:29:123:2500:-1:hidden_claus"
    row = codec.unique_row(sid, "参数", "unique_zeta", "900", "99", bad=False)
    rows = {"unique_condition": {"99000101": ",".join(row)}}
    older = wfx_gate.check(rows, profile="test-v34")
    newer = wfx_gate.check(rows, profile="test-v35e")
    assert not older.ok
    assert "direct-base-v1" in older.missing_capabilities()
    assert newer.ok, newer.problems
    assert not newer.missing_capabilities()


@pytest.mark.parametrize("field", ["swf_sha256", "apk_sha256"])
def test_local_candidate_profile_cannot_claim_unknown_binary(tmp_path, field):
    document = json.loads(wfx_gate.PROFILES_PATH.read_text("utf-8"))
    document["profiles"]["test-v35e"]["evidence"][field] = "0" * 64
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(document), "utf-8")
    with pytest.raises(wfx_gate.GateError, match="SWF/APK"):
        wfx_gate.load_profiles(path)


def test_old_planned_effects_stay_blocked_with_v35e():
    sid = "wfx:21:0:1:1:a"
    row = codec.unique_row(sid, "旧规划效果", "unique_zeta", "900", "99", bad=False)
    report = wfx_gate.check({"unique_condition": {"99000101": ",".join(row)}}, profile="test-v35e")
    assert not report.ok
    assert "wfx-damage-v1" in report.missing_capabilities()


@pytest.mark.parametrize("sid", [
    "wfx:34:5050:100000:150000:gerald",
    "wfx:35:50:500:1000:gerald",
])
def test_shipped_holder_heal_examples_preserve_parameters_and_require_new_client(sid):
    spec = codec.decode_sid(sid)
    assert spec.sid == sid
    assert not spec.pin
    assert spec.effect["patch_version"] == "v35k"
    row = codec.unique_row(sid, "治疗", "unique_zeta", "900", "1", bad=False)
    rows = {"unique_condition": {"12998901": ",".join(row)}}
    older = wfx_gate.check(rows, profile="test-v35e")
    assert not older.ok
    assert spec.effect["capability"] in older.missing_capabilities()
    declared = wfx_gate.ClientProfile("synthetic-v35k", frozenset(codec.required_capabilities(spec)))
    report = wfx_gate.check(rows, profile=declared)
    assert report.ok, report.problems
    assert any("TODO" in warning for warning in report.warnings)


def test_reassigned_codes_never_resolve_to_withdrawn_gauge_capability():
    catalog = wfx_registry.capabilities()
    assert catalog["wfx-gauge-v1"]["status"] == "withdrawn"
    for code, version in [(30, "v35f"), (31, "v35f"), (32, "v35j"),
                          (33, "v35k"), (34, "v35k"), (35, "v35k"), (36, "v35l")]:
        effect = wfx_registry.effect_codes()[code]
        assert effect["patch_version"] == version
        assert catalog[effect["capability"]]["status"] == "shipped"
        assert effect["arg"] != "gauge_mask"
        # Synthetic integer-carrier coverage, not a claim about TODO parameters.
        spec = codec.decode_sid(f"wfx:{code}:0:1:1:carrier")
        assert not spec.pin
        assert "wfx-gauge-v1" not in codec.required_capabilities(spec)
    with pytest.raises(codec.WfxError):
        codec.decode_sid("wfx:31:127:-0.01:0:old_gauge")


@pytest.mark.parametrize("mask,needs_v2", [(1, False), (2, False), (4, False),
                                         (7, False), (8, True), (16, True), (27, True)])
def test_unlock_revision_is_gated_by_actual_bits(mask, needs_v2):
    rows = {"custom_ability_string": {"wfx_unlock_129989": str(mask)}}
    report = wfx_gate.check(rows, profile="test-v35e")
    assert report.ok is not needs_v2
    assert ("leader-unlock-v2" in report.required_capabilities()) is needs_v2
    newer = wfx_gate.ClientProfile("synthetic-v35f", frozenset({"leader-unlock-v1", "leader-unlock-v2"}))
    assert wfx_gate.check(rows, profile=newer).ok


@pytest.mark.parametrize("key,value", [("wfx_unlock_129989", "32"),
                                      ("wfx_unlock_129989", "1.5"),
                                      ("wfx_pf4_129989", "100:FF40"),
                                      ("wfx_pf4_", "100:FF4040")])
def test_shipped_configuration_rejects_bad_formats(key, value):
    assert not wfx_gate.check({"custom_ability_string": {key: value}}, profile="test-v35e").ok


def test_pf4_key_and_character_identity_tag_use_distinct_tables():
    assert wfx_gate.check({"custom_ability_string": {"wfx_pf4_129989": "100:FF4040"}},
                          profile="test-v35e").ok
    older = wfx_gate.check({"character_tag": {"wfx_cid_129989": "identity"}}, profile="test-v35e")
    assert not older.ok
    assert "character-identity-tag-v1" in older.missing_capabilities()
    newer = wfx_gate.ClientProfile("synthetic-v35j", frozenset({"character-identity-tag-v1"}))
    assert wfx_gate.check({"character_tag": {"wfx_cid_129989": "identity"}}, profile=newer).ok


def test_unlock_payload_keeps_value_when_decoded_by_gate():
    import wf_quest_lib as nodes
    payload = nodes.build_node({"wfx_unlock_129989": "27"})
    entry = wfx_gate.PayloadEntry("unlock", lambda: payload, logical=wfx_gate.CUSTOM_STRING_LOGICAL)
    report = wfx_gate.check_entries([entry], profile="test-v35e")
    assert "leader-unlock-v2" in report.missing_capabilities()
    key_only = wfx_gate.check(strings=iter(["wfx_unlock_129989"]), profile="test-v35e")
    assert not key_only.ok
    assert any("未提供位掩码值" in warning for warning in key_only.warnings)


def test_modern_capability_reader_does_not_grant_unregistered_method_evidence():
    from wf.caps.facts import table_signals
    from wf.caps.signals_v35 import unique_signals
    assert any(kind == "unsupported" and "方法证据" in value
               for kind, value in unique_signals("wfx:34:5050:100000:150000:gerald"))
    values = list(table_signals("master/string/custom_ability_string.orderedmap",
                               ("wfx_unlock_129989",), "27"))
    assert any(kind == "unsupported" and "leader-unlock-v2" in value for kind, value in values)
    older = list(table_signals("master/string/custom_ability_string.orderedmap",
                              ("wfx_unlock_129989",), "7"))
    assert not any(kind == "unsupported" for kind, _ in older)
