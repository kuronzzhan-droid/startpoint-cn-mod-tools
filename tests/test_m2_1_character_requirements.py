"""Character-specific dependencies follow exact references, never numeric substrings."""
import pytest
import wf_quest_lib as nodes

from wf.caps.facts import CHARACTER, STRINGS
from wf.caps.registry import load_registry
from wf.caps.requirements import infer_requirements
from wf.caps.scan_capabilities import LABEL_IDS
from wf.caps.scan_facts import PER_CHAR_APK
from test_m2_requirements import ABILITY, ability, leaf, payload


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def character(code="test", ability_id=""):
    row = [""] * 25
    row[0], row[19] = code, ability_id
    return leaf(row)


@pytest.mark.parametrize("cid", PER_CHAR_APK)
def test_changed_character_requires_documented_patches(cid, registry):
    result = infer_requirements({"c": payload(CHARACTER, {cid: character()})}, registry=registry)
    expected = {number for cap in registry.values() if cid in cap["data_surface"].get("character_ids", [])
                for number in cap["provided_by"]["patches"]}
    assert expected and {f"#{n}" for n in expected} <= set(result["clientPatches"])
    assert result["capabilityResolution"] == "resolved"
    for label in PER_CHAR_APK[cid]:
        ids = LABEL_IDS[label]
        ids = ids if isinstance(ids, tuple) else (ids,)
        # #54/#56 also have direct unique-ID signals; the character-specific eight are C.
        for cap_id in ids:
            if registry[cap_id]["provided_by"]["patches"] in ([54, 56],):
                continue
            assert registry[cap_id]["layer"] == "C"
            assert cap_id in result["clientCapabilities"]


def test_referenced_ability_only_change_adds_kyle_patch55(registry):
    baseline = {CHARACTER: nodes.build_node({"139990": character(ability_id="shared")}),
                ABILITY: nodes.build_node({"shared": ability(0), "unrelated": ability(0)})}
    members = {"a": payload(ABILITY, {"shared": ability(424), "unrelated": ability(0)})}
    result = infer_requirements(members, read_raw=baseline.__getitem__, registry=registry)
    assert "#55" in result["clientPatches"]
    assert result["capabilityResolution"] == "resolved"
    members["a"] = payload(ABILITY, {"shared": ability(0), "unrelated": ability(424)})
    assert "#55" not in infer_requirements(members, read_raw=baseline.__getitem__, registry=registry)["clientPatches"]
    del baseline[CHARACTER]
    assert infer_requirements(members, read_raw=baseline.__getitem__, registry=registry)["capabilityResolution"] == "partial"


def test_text_only_override_uses_owner_reference(registry):
    baseline = {CHARACTER: nodes.build_node({"139995": character(ability_id="nine")}),
                ABILITY: nodes.build_node({"nine": ability(0)})}
    result = infer_requirements({"t": payload(STRINGS, {"desc_override_test": "updated"})},
                                read_raw=baseline.__getitem__, registry=registry)
    assert "#1" in result["clientPatches"]


def test_no_false_character_match_from_prose_or_unchanged_rows(registry):
    data = {"139995": character(), "other": character()}
    baseline = {CHARACTER: nodes.build_node(data)}
    updated = {**data, "other": character("139995")}
    result = infer_requirements({"c": payload(CHARACTER, updated)}, read_raw=baseline.__getitem__, registry=registry)
    assert "#1" not in result["clientPatches"]
