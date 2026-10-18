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
