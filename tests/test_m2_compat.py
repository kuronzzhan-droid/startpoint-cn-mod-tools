"""Missing PF4, stale hashes and unresolved inputs must not pass compatibility."""
from copy import deepcopy
import json

import pytest

from wf.apk.provides import derive_provides
from wf.caps.compat import check_compat
from wf.caps.registry import load_registry
from wf.check import main


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def required(ids, **extra):
    return {"schemaVersion": 2, "pack": {"since": "1.4.208", "tail": "1.4.209",
        "anchor": {"from": "1.4.208", "to": "1.4.209"}, "archives": ["seris.zip"]},
        "requires": {"clientCapabilities": ids, "clientPatches": ["#87", "#88", "#89"],
        "serverFeatures": [], "serverRestart": False, "restartReasons": [],
        "minServerVersion": None, "capabilityResolution": "resolved", **extra}}


def provided(registry, numbers=(87, 88, 89)):
    return derive_provides({"patches": [{"number": n, "status": "recorded", "methods":
        registry[f"client.apk.patch{n:03d}@1"]["provided_by"]["methods"]} for n in numbers]}, registry=registry)


def test_pf4_passes_only_with_all_three_patches(registry):
    requirement = required(["client.pf.level4@1"])
    report = check_compat(requirement, provided(registry), registry=registry)
    assert report[0]["status"] == "满足"
    for missing in (87, 88, 89):
        report = check_compat(requirement, provided(registry, [n for n in (87, 88, 89) if n != missing]), registry=registry)
        assert report[0]["status"] == "问题" and report[0]["blocking"]
        assert "缺 PF Lv4" in report[0]["message"]
        assert f"#{missing}" in report[0]["message"]


def test_deleting_patch_records_cannot_leave_stale_capability_success(registry):
    value = provided(registry)
    value["patches"] = []
    report = check_compat(required(["client.pf.level4@1"]), value, registry=registry)
    assert report[0]["status"] == "问题"


def test_method_hash_tampering_fails_and_missing_hash_is_pending(registry):
    value = provided(registry)
    pf4 = next(cap for cap in value["provides"] if cap["id"] == "client.pf.level4@1")
    pf4["methods"] = deepcopy(pf4["methods"])
    pf4["methods"][0]["sha256"] = "0" * 64
    report = check_compat(required([pf4["id"]]), value, registry=registry)
    assert report[0]["rule"] == "capability.method-hash" and report[0]["blocking"]
    pf4["methods"][0]["sha256"] = None
    pf4["methods"][0]["status"] = "待补"
    value["patches"][0]["methods"][0]["sha256"] = None
    value["patches"][0]["methods"][0]["status"] = "待补"
    assert check_compat(required([pf4["id"]]), value, registry=registry)[0]["status"] == "待验证"


def test_partial_and_legacy_empty_requires_are_never_compatible(registry):
    for state in ("partial", "pending-m2"):
        results = check_compat(required([], capabilityResolution=state), provided(registry), registry=registry)
        assert any(r["blocking"] for r in results)
        assert results[0]["status"] == "待验证"


def test_patch_hash_cannot_disagree_with_capability_hash(registry):
    value = deepcopy(provided(registry))
    value["patches"][0]["methods"][0]["sha256"] = "0" * 64
    assert any(r["blocking"] for r in check_compat(required(["client.pf.level4@1"]), value, registry=registry))


def test_explicit_patch_only_requirement_cannot_pass_an_empty_client(registry):
    requirement = required([], capabilityResolution="declared", clientPatches=["#87"])
    results = check_compat(requirement, provided(registry, ()), registry=registry)
    assert any(r["blocking"] and "#87" in r["message"] for r in results)
    assert not any(r["blocking"] for r in check_compat(requirement, provided(registry, (87,)), registry=registry))
    with pytest.raises(ValueError, match="patch notation"):
        check_compat(required([], clientPatches=["made-up"]), provided(registry), registry=registry)


def test_cli_reports_missing_pf4_and_returns_failure(tmp_path, capsys, registry):
    req, prov = tmp_path / "requires.json", tmp_path / "provides.json"
    req.write_text(json.dumps(required(["client.pf.level4@1"])), "utf-8")
    prov.write_text(json.dumps(provided(registry, ())), "utf-8")
    assert main(["compat", "--requires", str(req), "--provides", str(prov)]) == 1
    assert "缺 PF Lv4" in capsys.readouterr().out


def test_unknown_and_duplicate_capability_records_are_rejected(registry):
    value = provided(registry)
    assert check_compat(required(["missing@1"]), value, registry=registry)[0]["blocking"]
    value["provides"].append(value["provides"][0])
    with pytest.raises(ValueError, match="duplicate"):
        check_compat(required([]), value, registry=registry)
