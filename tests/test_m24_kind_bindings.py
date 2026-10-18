"""Kind identities are table/block scoped; only binary evidence rejects sites."""
from copy import deepcopy

import pytest

from wf.caps.facts import table_signals
from wf.caps.query import requirements_for_signals
from wf.caps.registry import load_registry, validate_capability
from wf.caps.requirements import infer_requirements
from wf.view.layout import col
from test_m2_requirements import ABILITY, ability, payload


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.mark.parametrize("kind", [422, 423, 424])
def test_official_instant_kinds_have_no_patch_dependencies(kind, registry):
    inferred = infer_requirements(
        {"a": payload(ABILITY, {"x": ability(kind, block="instant_content")})}, registry=registry)
    assert inferred["clientCapabilities"] == []
    assert inferred["clientPatches"] == []
    assert inferred["kindSites"][0]["block"] == "instant_content"
    assert inferred["kindSites"][0]["kind"] == str(kind)


@pytest.mark.parametrize("kind,block", [(419, "instant_content"), (722, "during_content")])
def test_pf_reference_and_dependency_require_the_matching_block(kind, block, registry):
    text = ability(kind, block=block, levels="4")
    signals = list(table_signals(ABILITY, ("x",), text, registry=registry))
    assert not any(k == "ref" or (k == "selectors" and v == "pf.forLevels=4") for k, v in signals)
    inferred = infer_requirements({"a": payload(ABILITY, {"x": text})}, registry=registry)
    assert inferred["clientCapabilities"] == []


def test_query_matches_the_same_concrete_sites_as_delivery(registry):
    for table, block, kind, expected in [
        ("ability", "instant_content", "422", []),
        ("ability", "during_content", "422", ["client.kind422.dash@1"]),
        ("ability_soul", "during_content", "423", ["client.equipment.gauge_gain_rules@1"]),
        ("leader_ability", "during_content", "423", []),
    ]:
        site = {"table": table, "block": block, "kind": kind, "row": 0}
        assert requirements_for_signals([("kind_site", site)], registry) == expected


def test_registry_requires_explicit_pairs_and_consistent_indexes(registry):
    original = registry["official.pf.special@1"]
    assert original["data_surface"]["kind_bindings"] == [
        {"block": "instant_content", "kind": 722}, {"block": "during_content", "kind": 419}]
    missing = deepcopy(original)
    missing["data_surface"].pop("kind_bindings")
    with pytest.raises(ValueError, match="kind_bindings"):
        validate_capability(missing)
    inconsistent = deepcopy(original)
    inconsistent["data_surface"]["kind_bindings"][0]["kind"] = 999
    with pytest.raises(ValueError, match="kind_bindings"):
        validate_capability(inconsistent)


def test_ex_ability_participates_in_629_reference_discovery(registry):
    import csv
    import io
    from wf.dsl.references import ability_references
    from test_m2_requirements import leaf

    logical = "master/ex_boost/ex_ability.orderedmap"
    cells = next(csv.reader(io.StringIO(ability(629, table="ex_ability", block="instant_content"))))
    cells[col("ex_ability", "instant_content", "action_path")] = "battle/test$main"
    text = leaf(cells)
    signals = list(table_signals(logical, ("x",), text, registry=registry))
    assert ("program", "battle/test$main") in signals
    assert list(ability_references(logical, {"x": text}))[0]["action"] == "battle/test$main"
    assert requirements_for_signals([s for s in signals if s[0] == "kind_site"], registry) == [
        "official.kind629.invoke_skill@1"]


def test_legacy_evidence_checks_its_recorded_block_without_guessing(monkeypatch, registry):
    from wf.caps.kind_compat import check_kind_sites

    report = {"source": {"swf_sha256": "a" * 64}, "mismatches": [], "tables": {
        "leader_ability": {"instant_content": {"kinds": ["423"]},
                           "during_content": {"kinds": []}}}}
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", lambda *a, **kw: report)
    evidence = {"logical_path": "master/ability/leader_ability.orderedmap", "key": "x",
                "signal": "kinds", "value": "423", "row": 0, "block": "instant_content"}
    required = {"capabilityEvidence": [{"id": "old", "evidence": [evidence]}]}
    assert check_kind_sites(required, {}, registry)[0]["status"] == "满足"
    evidence["block"] = "during_content"
    assert check_kind_sites(required, {}, registry)[0]["rule"] == "capability.kind-unsupported"
    del evidence["block"]
    check = check_kind_sites(required, {}, registry)[0]
    assert check["status"] == "待验证" and check["blocking"]
