"""Reject unsupported table/block surfaces and exercise both weapon layouts."""
from copy import deepcopy

import pytest

from wf.caps.facts import UNIQUE
from wf.caps.registry import load_registry, validate_capability
from wf.caps.requirements import infer_requirements
from wf.dsl.references import ABILITY_TABLES
from test_m2_requirements import ABILITY, ability, payload


@pytest.mark.parametrize("logical,table", list(ABILITY_TABLES.items())[1:])
@pytest.mark.parametrize("kind,block", [(422, "during_content"), (423, "during_content"),
    (424, "during_content"), (724, "instant_content")])
def test_patch_kinds_reject_unpatched_table_parsers(logical, table, kind, block):
    with pytest.raises(ValueError, match=f"问题: .*kind {kind}.*allowed_tables.*{table}"):
        infer_requirements({"a": payload(logical, {"x": ability(kind, table=table, block=block)})})


@pytest.mark.parametrize("logical,table", list(ABILITY_TABLES.items())[2:])
def test_weapon_layout_without_awake_kind_follows_unique(logical, table):
    members = {"a": payload(logical, {"x": ability(0, table=table, unique="99881")}),
               "u": payload(UNIQUE, {"99881": "hidden_weapon,0"})}
    result = infer_requirements(members)
    assert "client.unique.hidden@1" in result["clientCapabilities"]
    assert "official.awakening@1" not in result["clientCapabilities"]
    del members["u"]
    assert infer_requirements(members)["capabilityResolution"] == "partial"


def test_missing_baseline_note_and_423_excludes_performance_patch():
    members = {"a": payload(ABILITY, {"x": ability(423)})}
    result = infer_requirements(members)
    assert result["clientPatches"] == ["#31"]
    assert result["inferenceNotes"][0]["reason"] == "baseline-missing"
    unchanged = infer_requirements(members, read_raw=lambda _: members["a"][0])
    assert not unchanged["inferenceNotes"] and not unchanged["clientCapabilities"]


def test_selector_is_data_driven():
    registry = deepcopy(load_registry())
    cap = registry["client.kind424.damage_convert@1"]
    assert "dsl.buffTargetAs.convert" in cap["data_surface"]["selectors"]
    cap["data_surface"]["allowed_tables"] = ["ability_soul"]
    with pytest.raises(ValueError, match="allowed_tables"):
        infer_requirements({"a": payload(ABILITY, {"x": ability(424)})}, registry=registry)


def test_schema_rejects_untyped_surface_constraints():
    cap = deepcopy(load_registry()["client.kind424.damage_convert@1"])
    cap["data_surface"]["allowed_blocks"] = "during_content"
    with pytest.raises(ValueError, match="invalid capability"):
        validate_capability(cap)
