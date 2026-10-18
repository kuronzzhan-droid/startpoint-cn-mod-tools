"""R3 table-scoped inference and compatibility must survive negative controls."""
from copy import deepcopy

import pytest

from wf.apk.evidence import v34_evidence, v35e_evidence
from wf.apk.provides import derive_provides
from wf.caps.compat import check_compat
from wf.caps.requirements import infer_requirements
from wf.dsl.references import ABILITY_TABLES
from wf_quest_lib import build_node
from test_m2_compat import required
from test_m2_requirements import ability, payload

R3 = "client.equipment.gauge_gain_rules@1"
CHARACTER_423 = "client.kind423.gauge_source_limit@1"
WEAPONS = [(logical, name) for logical, name in ABILITY_TABLES.items()
           if name in {"ability_soul", "equipment_enhancement_ability"}]


def weapon_requirements(logical, table):
    inferred = infer_requirements({"weapon": payload(logical, {"test": ability(423, table=table)})},
                                  read_raw=lambda _: build_node({}))
    document = required([])
    document["requires"].update(inferred)
    return document


@pytest.mark.parametrize("logical,table", WEAPONS)
def test_r3_is_selected_by_table_and_records_actual_kind_site(logical, table):
    doc = weapon_requirements(logical, table)
    assert doc["requires"]["clientCapabilities"] == [R3]
    assert doc["requires"]["clientPatches"] == []
    assert doc["requires"]["capabilityResolution"] == "resolved"
    assert doc["requires"]["kindSites"] == [{"logical_path": logical, "key": "test", "row": 0,
                                          "table": table, "block": "during_content", "kind": "423"}]
    character = infer_requirements({"a": payload("master/ability/ability.orderedmap", {"x": ability(423)})})
    assert character["clientCapabilities"] == [CHARACTER_423]
    assert character["clientPatches"] == ["#31"]


@pytest.mark.parametrize("logical,table", WEAPONS)
def test_r3_rule_mask_is_not_a_unique_condition_reference(logical, table):
    inferred = infer_requirements({"a": payload(logical, {"x": ability(423, table=table, unique="78")})})
    assert inferred["capabilityResolution"] == "resolved"
    assert inferred["unresolved"] == []
    assert inferred["clientCapabilities"] == [R3]


@pytest.mark.parametrize("record", [v34_evidence, v35e_evidence])
@pytest.mark.parametrize("logical,table", WEAPONS)
def test_removing_r3_is_missing_capability_even_when_binary_supports_it(monkeypatch, record, logical, table):
    client = derive_provides(record())
    monkeypatch.setattr("wf.caps.kind_compat.check_kind_sites", lambda *a: [])
    document = weapon_requirements(logical, table)
    assert not any(r["blocking"] for r in check_compat(document, client))
    client["provides"] = [entry for entry in client["provides"] if entry["id"] != R3]
    checks = check_compat(document, client)
    assert any(r["rule"] == "capability.missing" and r["id"] == R3 and r["blocking"] for r in checks)


def test_r3_hash_and_swf_identity_are_both_required(monkeypatch):
    monkeypatch.setattr("wf.caps.kind_compat.check_kind_sites", lambda *a: [])
    document = weapon_requirements(*WEAPONS[0])
    client = derive_provides(v34_evidence())
    modified = deepcopy(client)
    entry = next(c for c in modified["provides"] if c["id"] == R3)
    entry["methods"][0]["sha256"] = "0" * 64
    assert any(r["rule"] == "capability.method-hash" and r["blocking"] for r in check_compat(document, modified))
    client["source"]["swf_sha256"] = "0" * 64
    assert any(r["rule"] == "capability.method-hash" and r["blocking"] for r in check_compat(document, client))


def test_real_kind_check_does_not_accept_registry_or_profile_claim_alone(monkeypatch):
    report = {"source": {"swf_sha256": "a" * 64}, "tables": {}, "mismatches": []}
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", lambda *a, **k: report)
    monkeypatch.setattr("wf.apk.kinds.kind_supported", lambda *a: False)
    checks = check_compat(weapon_requirements(*WEAPONS[0]), derive_provides(v34_evidence()))
    assert any(r["rule"] == "capability.kind-unsupported" and r["blocking"] for r in checks)


def test_unavailable_binary_cannot_be_called_compatible(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("profile SWF unavailable")
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", missing)
    checks = check_compat(weapon_requirements(*WEAPONS[0]), derive_provides(v34_evidence()))
    assert any(r["rule"] == "capability.kind-evidence" and r["status"] == "待验证" and r["blocking"]
               for r in checks)


def test_legacy_kind_evidence_still_requires_real_swf(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("legacy SWF unavailable")
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", missing)
    document = weapon_requirements(*WEAPONS[0])
    del document["requires"]["kindSites"]
    for entry in document["requires"]["capabilityEvidence"]:
        for evidence in entry["evidence"]:
            for field in ("table", "block", "row"):
                evidence.pop(field, None)
    checks = check_compat(document, derive_provides(v34_evidence()))
    assert any(r["rule"] == "capability.kind-evidence" and r["blocking"] for r in checks)
