"""R3 requires its two recorded parser methods and an explicitly pinned SWF."""
from copy import deepcopy
import hashlib
import json

import pytest

from wf.apk.evidence import v34_evidence, v35e_evidence
from wf.apk.provides import derive_provides
from wf.caps.profiles import load_profiles, read_client, resolve_client
from wf.caps.registry import load_registry, validate_capability
from wf.deliver.changeset import validate_document
from wf.paths import REPOSITORY

R3 = "client.equipment.gauge_gain_rules@1"


def ids(record):
    return {entry["id"] for entry in derive_provides(record)["provides"]}


@pytest.mark.parametrize("evidence", [v34_evidence, v35e_evidence])
def test_r3_has_exact_parser_method_evidence_without_invented_archive(evidence):
    cap = load_registry()[R3]
    assert cap["provided_by"]["patches"] == []
    assert cap["data_surface"]["allowed_tables"] == ["ability_soul", "equipment_enhancement_ability"]
    assert cap["data_surface"]["allowed_blocks"] == ["during_content"]
    assert all(method["patch"] is None for method in cap["provided_by"]["methods"])
    document = derive_provides(evidence())
    validate_document(document, "provides.schema.json")
    r3 = next(entry for entry in document["provides"] if entry["id"] == R3)
    assert r3["patches"] == []
    assert len(r3["methods"]) == 2
    assert {m["label"] for m in r3["methods"]} == {
        "AbilitySoulValues$/parseAt106", "EquipmentEnhancementAbilityValues$/parseAt109"}
    assert document["unresolved"] == []


@pytest.mark.parametrize("fault", ["no_record", "missing_method", "fake_hash", "unknown_swf", "wrong_patch"])
def test_r3_does_not_follow_patch31_or_incomplete_unbound_method_records(fault):
    record = v34_evidence()
    methods = record["method_capabilities"][0]["methods"]
    if fault == "no_record":
        del record["method_capabilities"]
    elif fault == "missing_method":
        methods.pop()
    elif fault == "fake_hash":
        methods[0]["sha256"] = "0" * 64
    elif fault == "unknown_swf":
        record["swf_sha256"] = "0" * 64
    elif fault == "wrong_patch":
        methods[0]["patch"] = 31
    result = ids(record)
    assert "client.kind423.gauge_source_limit@1" in result
    assert R3 not in result


def test_standalone_registration_needs_swf_and_cannot_borrow_patch_number():
    cap = deepcopy(load_registry()[R3])
    del cap["provided_by"]["swf_sha256"]
    with pytest.raises(ValueError, match="pinned SWF"):
        validate_capability(cap)
    cap = deepcopy(load_registry()[R3])
    cap["provided_by"]["patches"] = [31]
    with pytest.raises(ValueError, match="undeclared patch"):
        validate_capability(cap)


def test_r3_duplicate_method_records_are_rejected():
    record = v34_evidence()
    record["method_capabilities"][0]["methods"].append(
        deepcopy(record["method_capabilities"][0]["methods"][0]))
    with pytest.raises(ValueError, match="duplicate method evidence"):
        derive_provides(record)


def test_evidence_backed_profiles_gain_r3_and_bind_their_provides():
    _, profiles = load_profiles()
    for name, profile in profiles.items():
        if name not in {"test-v34", "test-v35e", "local-v35k3"}:
            assert R3 not in profile.get("m2_capabilities", [])
            continue
        assert R3 in profile["m2_capabilities"]
        assert "equipment-gauge-gain-rules-v1" in profile["capabilities"]
        assert profile["evidence"]["swf_path"].startswith("${WF_ROOT}/")
        selected, selected_name = resolve_client(client_profile=name)
        assert selected_name == name
        assert R3 in {entry["id"] for entry in read_client(selected)["provides"]}
        if profile.get("provides_fallback"):
            fallback = REPOSITORY / profile["provides_fallback"]
            assert hashlib.sha256(fallback.read_bytes()).hexdigest() == profile["provides_fallback_sha256"]
            read_client(fallback, profile=profile, expected_digest=profile["provides_fallback_sha256"])


def test_committed_observations_bind_registered_method_hashes_and_actual_branch():
    cap = load_registry()[R3]
    proof = json.loads((REPOSITORY / "wf/apk/data/equipment-rules-r3-methods.json").read_text("utf-8"))
    assert {row["swf_sha256"] for row in proof["artifacts"]} == set(cap["provided_by"]["swf_sha256"])
    for artifact in proof["artifacts"]:
        for actual, expected in zip(artifact["methods"], cap["provided_by"]["methods"]):
            assert actual["label"] == expected["label"] and actual["sha256"] == expected["sha256"]
            assert actual["head"][7]["op"] == "pushstring"
            assert actual["head"][7]["string"] == "423"
            assert actual["head"][8]["op"] == "ifne"
            assert actual["head"][24]["op"] == "returnvalue"
