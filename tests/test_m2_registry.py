"""Registry completeness and counterexamples for explicit method provenance."""
import copy
import json

import pytest
import yaml

from wf.apk.evidence import v34_evidence
from wf.apk.provides import derive_provides
from wf.caps.registry import load_registry, validate_capability
from wf.deliver.changeset import validate_document


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def test_registry_covers_every_archive_patch_and_official_layers(registry):
    for n in range(1, 112):
        cap = registry[f"client.apk.patch{n:03d}@1"]
        assert cap["provided_by"]["patches"] == [n]
        assert cap["provided_by"]["methods"]
    assert registry["client.apk.patch097@1"]["layer"] == "platform"
    assert registry["client.apk.patch104@1"]["layer"] == "platform"
    assert registry["client.kind424.damage_convert@1"]["layer"] == "A"
    assert registry["official.kind629.invoke_skill@1"]["layer"] == "B"
    assert registry["client.pf.level4@1"]["provided_by"]["patches"] == [87, 88, 89]
    assert registry["client.overlimit.lv120@1"]["server"]["required"]
    assert all(f"client.overlimit.o{n}@1" in registry for n in range(1, 13))


def test_v34_all_recorded_methods_match_and_output_passes_schema(registry):
    document = derive_provides(v34_evidence(), registry=registry)
    validate_document(document, "provides.schema.json")
    assert len(document["patches"]) == 111
    assert len(document["provides"]) == len(registry)
    assert document["unresolved"] == []
    p = next(p for p in document["patches"] if p["number"] == 109)
    assert p["methods"][0]["sha256"] == "ae683cc1f5574ac7b415c43cf779ea642535cd6a66531aa1ee51a150d1492068"


def test_deleting_pf_patches_removes_combined_capability(registry):
    record = v34_evidence()
    record["patches"] = [p for p in record["patches"] if p["number"] not in {87, 88, 89}]
    output = derive_provides(record, registry=registry)
    assert "client.pf.level4@1" not in {p["id"] for p in output["provides"]}
    assert "client.fever.items@1" in {p["id"] for p in output["provides"]}


@pytest.mark.parametrize("number", [87, 88, 89])
def test_pf_requires_every_component(number, registry):
    record = v34_evidence()
    record["patches"] = [p for p in record["patches"] if p["number"] != number]
    assert "client.pf.level4@1" not in {c["id"] for c in derive_provides(record, registry=registry)["provides"]}


def test_tampered_method_never_provides_matching_capability(registry):
    record = v34_evidence()
    next(p for p in record["patches"] if p["number"] == 88)["methods"][0]["sha256"] = "0" * 64
    output = derive_provides(record, registry=registry)
    assert "client.pf.level4@1" not in {p["id"] for p in output["provides"]}
    assert output["unresolved"][0]["patch"] == 88


def test_missing_hashes_stay_null_not_filled_from_registry(registry):
    output = derive_provides({"patches": [{"number": 87, "status": "declared"}]}, registry=registry)
    assert all(m["sha256"] is None and m["status"] == "待补" for m in output["patches"][0]["methods"])
    assert not any(c["layer"] == "B" for c in output["provides"])


def test_null_hash_cannot_be_marked_verified(registry):
    cap = copy.deepcopy(registry["client.apk.patch079@1"])
    assert cap["provided_by"]["methods"][0]["sha256"] is None
    cap["provided_by"]["methods"][0]["status"] = "已记录"
    with pytest.raises(ValueError, match="待补"):
        validate_capability(cap)


def test_duplicate_patch_and_wrong_patch_method_fail(registry):
    row = v34_evidence()["patches"][0]
    with pytest.raises(ValueError, match="duplicate patch"):
        derive_provides({"patches": [row, row]}, registry=registry)
    row["methods"][0]["patch"] = 2
    with pytest.raises(ValueError, match="another patch"):
        derive_provides({"patches": [row]}, registry=registry)


def test_schema_and_filename_reject_bad_declarations(tmp_path, registry):
    cap = copy.deepcopy(registry["client.pf.level4@1"])
    (tmp_path / "wrong.yml").write_text(yaml.safe_dump(cap), encoding="utf-8")
    with pytest.raises(ValueError, match="filename"):
        load_registry(tmp_path)
    del cap["data_surface"]
    with pytest.raises(ValueError, match="data_surface"):
        validate_capability(cap)


def test_duplicate_yaml_keys_rejected(tmp_path):
    (tmp_path / "bad.yml").write_text("id: a\nid: b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate YAML"):
        load_registry(tmp_path)
