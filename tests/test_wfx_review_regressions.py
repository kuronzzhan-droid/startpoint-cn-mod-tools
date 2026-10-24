"""Real table surfaces and conservative v35 parameter regressions."""
import csv
import io

import pytest

import wf_describe
import wf_quest_lib as nodes
import wf_wfx
import wfx_gate
import wfx_registry
from wf.caps.facts import table_signals
from wf.caps.requirements import infer_requirements
from wf.view.layout import col, mode_col


def csv_row(row):
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="").writerow(row)
    return stream.getvalue()


def ability_row(table="ability", *, mode="0", block="precondition1",
                field="character_groups", kind="3", tag="wfx_cid_129989"):
    row = [""] * wf_describe.layout(table)["ncols"]
    row[0], row[mode_col(table)] = "1299893", mode
    row[col(table, block, "kind")] = kind
    row[col(table, block, field)] = f"Human/{tag},Water"
    return row


@pytest.mark.parametrize("table", wfx_gate.ABILITY_TABLE_LOGICALS)
def test_identity_tag_in_real_ability_precondition_gates_every_table(table):
    row = ability_row(table)
    raw = nodes.build_node({"1299893": csv_row(row)})
    entry = wfx_gate.PayloadEntry(table, lambda: raw, logical=wfx_gate.ABILITY_TABLE_LOGICALS[table])
    older = wfx_gate.check_entries([entry], profile="test-v35e")
    assert not older.ok
    assert "character-identity-tag-v1" in older.missing_capabilities()
    newer = wfx_gate.ClientProfile("identity-supported", frozenset({"character-identity-tag-v1"}))
    assert wfx_gate.check_entries([entry], profile=newer).ok
    signals = list(table_signals(entry.logical, ("1299893",), csv_row(row)))
    assert any(kind == "unsupported" and "character-identity-tag-v1" in text for kind, text in signals)


@pytest.mark.parametrize("mode,block,field,kind", [
    ("0", "precondition1", "trigger_puller.character_groups", "100"),
    ("0", "instant_trigger", "character_groups", "58"),
    ("0", "instant_trigger", "trigger_puller.character_groups", "107"),
    ("0", "instant_content", "character_groups", "52"),
    ("0", "instant_content", "target.character_groups", "52"),
    ("0", "instant_content", "mt.tp.character_groups", "0"),
    ("0", "instant_precontent", "target.character_groups", "1"),
    ("1", "during_trigger", "character_groups", "184"),
    ("1", "during_trigger", "trigger_puller.character_groups", "0"),
    ("1", "during_accumulation_trigger", "character_groups", "58"),
    ("1", "during_accumulation_trigger", "trigger_puller.character_groups", "107"),
    ("1", "during_content", "character_groups", "20"),
    ("1", "during_content", "target.character_groups", "20"),
])
def test_identity_tag_in_other_parsed_group_fields(mode, block, field, kind):
    row = ability_row(mode=mode, block=block, field=field, kind=kind)
    report = wfx_gate.check({"ability": {"1299893": csv_row(row)}}, profile="official")
    assert "character-identity-tag-v1" in report.missing_capabilities()


def test_unused_mode_and_non_group_prose_do_not_claim_identity_tag():
    row = ability_row(mode="2")
    row[0] = "wfx_cid_129989"
    report = wfx_gate.check({"ability": {"1299893": csv_row(row)}}, profile="official")
    assert report.ok
    assert not report.required_capabilities()


@pytest.mark.parametrize("tag", ["wfx_cid_abc", "wfx_cid_", "wfx_cid_0", "wfx_cid_0129989"])
def test_identity_tag_rejects_invalid_suffix_in_real_group_cells(tag):
    row = ability_row(tag=tag)
    profile = wfx_gate.ClientProfile("identity-supported", frozenset({"character-identity-tag-v1"}))
    report = wfx_gate.check({"ability": {"1299893": csv_row(row)}}, profile=profile)
    assert not report.ok
    assert any("十进制正整数" in problem for problem in report.problems)


def test_character_payload_and_modern_inference_detect_identity_without_fake_table():
    raw = nodes.build_node({"129989": csv_row(["gerald", "", "", "", "", "Human,wfx_cid_129989"])})
    entry = wfx_gate.PayloadEntry("character", lambda: raw, logical=wfx_gate.CHARACTER_LOGICAL)
    assert "character-identity-tag-v1" in wfx_gate.check_entries([entry], profile="official").missing_capabilities()
    ability = nodes.build_node({"1299893": csv_row(ability_row())})
    requirements = infer_requirements({"ability": (ability, {
        "logical_path": wfx_gate.ABILITY_TABLE_LOGICALS["ability"], "root": "common"})})
    assert requirements["capabilityResolution"] == "partial"
    assert any("character-identity-tag-v1" in entry["referenced_by"].get("reason", "")
               for entry in requirements["unresolved"])
    assert "master/character/character_tag.orderedmap" not in wfx_gate.GATE_TABLE_LOGICALS.values()


def test_mod_dual_form_registration_and_bare_tag_compatibility_are_preserved():
    rules = {rule["prefix"]: rule for rule in wfx_registry.load()["character_tag_patterns"]}
    assert rules["ModDualForm"]["capability"] == "dual-form-uid-v1"
    assert rules["ModDualForm"]["default_uid"] == 22
    assert "wfx_cid_" in rules
    rows = {"character": {"129999": "seris,,,,,ModDualForm"}}
    assert "dual-form-uid-v1" not in wfx_gate.check(rows, profile="test-v34").required_capabilities()
    rows["character"]["129999"] += ":22"
    assert "dual-form-uid-v1" in wfx_gate.check(rows, profile="test-v34").missing_capabilities()
    assert wfx_gate.check(rows, profile="test-v35e").ok


@pytest.mark.parametrize("code,arg", [(30, 0), (31, 0), (32, 0), (33, 0),
                                     (34, 5050), (35, 50), (36, 1)])
def test_every_shipped_effect_requires_query_runtime_and_warns_unknown_stacking(code, arg):
    effect = wfx_registry.effect_codes()[code]
    sid = f"wfx:{code}:{arg}:1:1:sample"
    row = wf_wfx.unique_row(sid, "测试", "unique_zeta", "900", "1", bad=False)
    rows = {"unique_condition": {"12998901": csv_row(row)}}
    profile = wfx_gate.ClientProfile("missing-query", frozenset({effect["capability"]}))
    report = wfx_gate.check(rows, profile=profile)
    assert not report.ok
    assert "wfx-effect-query-v1" in report.missing_capabilities()
    assert effect["stack_scaled"] is None
    assert any("叠层" in warning and "未知" in warning for warning in report.warnings)


@pytest.mark.parametrize("code,arg", [(30, 5), (30, 99), (34, 0), (34, 5059),
                                     (34, 5000), (35, 0), (35, 59), (35, 1000),
                                     (36, 2), (36, 3), (36, 2147483647)])
def test_effect_negative_arguments_fail_codec_and_gate(code, arg):
    sid = f"wfx:{code}:{arg}:100000:150000:invalid"
    with pytest.raises(wf_wfx.WfxError):
        wf_wfx.decode_sid(sid)
    row = wf_wfx.unique_row("wfx:34:5050:100000:150000:valid", "测试", "unique_zeta", "900", "1", bad=False)
    row[0] = sid
    profile = wfx_gate.ClientProfile("all-registered", frozenset(wfx_registry.capabilities()))
    assert not wfx_gate.check({"unique_condition": {"12998901": csv_row(row)}}, profile=profile).ok


@pytest.mark.parametrize("sid", ["wfx:30:4:100000:0:damage", "wfx:34:5050:100000:150000:gerald",
                                 "wfx:35:50:500:1000:gerald", "wfx:36:0:10000:1000:unison",
                                 "wfx:36:1:10000:1000:unison"])
def test_documented_or_conservatively_bounded_arguments_roundtrip(sid):
    assert wf_wfx.decode_sid(sid).sid == sid


@pytest.mark.parametrize("key,value", [("wfx_unlock_", "27"), ("wfx_unlock_0129989", "27"),
                                      ("wfx_unlock_0", "27"), ("wfx_unlock_abc", "27"),
                                      ("wfx_pf4_129989", "0"), ("wfx_pf4_129989", "0:ff4040")])
def test_configuration_rejects_noncanonical_ids_and_zero_pf4_threshold(key, value):
    profile = wfx_gate.ClientProfile("all-registered", frozenset(wfx_registry.capabilities()))
    report = wfx_gate.check({"custom_ability_string": {key: value}}, profile=profile)
    assert not report.ok


@pytest.mark.parametrize("value", ["100:FF4040", "100:ff4040", "100:fF4040", "100"])
def test_pf4_accepts_both_hex_cases(value):
    assert wfx_gate.check({"custom_ability_string": {"wfx_pf4_129989": value}}, profile="test-v35e").ok


def test_awakening_material_requires_unregistered_method_evidence():
    logical = wfx_gate.CUSTOM_STRING_LOGICAL
    raw = nodes.build_node({"awakening_material_5950001": "10000311"})
    result = infer_requirements({"custom": (raw, {"logical_path": logical, "root": "common"})})
    assert result["capabilityResolution"] == "partial"
    assert any("equipment-awakening-material-v1" in entry["referenced_by"].get("reason", "")
               for entry in result["unresolved"])
    # Patch 29 is a specific 5900101 restriction, not evidence of this generic key.
    assert "client.apk.patch029@1" not in result["clientCapabilities"]
    ordinary = list(table_signals(logical, ("ordinary_key",), "10000311"))
    assert not any(kind == "unsupported" for kind, _ in ordinary)
