"""Real layouts and negative controls for payload-derived capability requirements."""
from __future__ import annotations

import csv
import io
import json
import zlib

import pytest
import wf_quest_lib as nodes
from wf_dsl import encode_amf3
from wf.caps.facts import CHARACTER, UNIQUE, PF, STRINGS
from wf.caps.registry import load_registry
from wf.caps.requirements import infer_requirements, requirements_document
from wf.deliver.changeset import validate_document
from wf.view.layout import EM, col

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def leaf(row):
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerow(row)
    return out.getvalue().rstrip("\n")


def ability(kind, *, table="ability", block="during_content", levels=None, unique=None, unison=False):
    layout = EM["layouts"][table]
    width = max(int(base) + max(int(f[0]) for f in EM["block_fields"][
        "precondition" if block.startswith("precondition") else block])
        for block, base in layout["blocks"].items()) + 1
    row = ["0"] * width
    row[0] = "test"
    trigger = next(int(c[1:]) for c, label in layout["head"] if label.split()[0] == "trigger")
    row[trigger] = "1" if block == "during_content" else "0"
    row[col(table, block, "kind")] = str(kind)
    if levels is not None:
        row[col(table, block, "powerflip_override.id")] = "test_pf"
        row[col(table, block, "powerflip_override.levels")] = levels
    if unique:
        row[col(table, block, "unique_condition_id")] = unique
    if table == "ability":
        row[1] = "true" if unison else "false"
    return leaf(row)


def payload(logical, data):
    return nodes.build_node(data), {"logical_path": logical, "root": "common"}


@pytest.mark.parametrize("kind,block,expected", [
    (422, "during_content", "client.kind422.dash@1"),
    (423, "during_content", "client.kind423.gauge_source_limit@1"),
    (424, "during_content", "client.kind424.damage_convert@1"),
    (724, "instant_content", "client.kind724.fever_ratio@1"),
])
@pytest.mark.parametrize("table,logical", [("ability", ABILITY)])
def test_actual_layouts_and_prose_counterexample(kind, block, expected, table, logical, registry):
    raw, entry = payload(logical, {"1": ability(kind, table=table, block=block)})
    result = infer_requirements({"x": (raw, entry)}, registry=registry)
    assert expected in result["clientCapabilities"]
    raw, entry = payload(logical, {"1": ability(0, table=table, block=block).replace("test", str(kind), 1)})
    assert expected not in infer_requirements({"x": (raw, entry)}, registry=registry)["clientCapabilities"]


def test_pf4_is_from_levels_and_changed_keys_only(registry):
    initial = {"pf": ability(722, block="instant_content", levels="1,2,3,4"), "other": ability(0)}
    modified = {**initial, "other": ability(424)}
    base = nodes.build_node(initial)
    result = infer_requirements({"x": payload(ABILITY, modified)}, read_raw=lambda p: base, registry=registry)
    assert result["clientCapabilities"] == ["client.kind424.damage_convert@1"]
    result = infer_requirements({"x": payload(ABILITY, initial), "pf": payload(PF, {"test_pf": ""})}, registry=registry)
    assert "client.pf.level4@1" in result["clientCapabilities"]
    initial["pf"] = ability(722, block="instant_content", levels="1,2,3")
    assert "client.pf.level4@1" not in infer_requirements({"x": payload(ABILITY, initial)}, registry=registry)["clientCapabilities"]


def test_unique_references_follow_baseline_strings_and_missing_is_partial(registry):
    members = {"a": payload(ABILITY, {"1": ability(0, unique="99881")})}
    base = {UNIQUE: nodes.build_node({"99881": "fever:items:test,0"}), CHARACTER: nodes.build_node({})}
    result = infer_requirements(members, read_raw=base.__getitem__, registry=registry)
    assert "client.fever.items@1" in result["clientCapabilities"]
    assert result["capabilityResolution"] == "resolved"
    result = infer_requirements(members, registry=registry)
    assert result["capabilityResolution"] == "partial" and result["unresolved"]


def test_unique_ids_hidden_and_text_keys_are_typed(registry):
    members = {"u": payload(UNIQUE, {"13999010": "hidden_charger,0", "13999011": "direct,0"}),
               "t": payload(STRINGS, {"desc_override_test": "效果"})}
    caps = infer_requirements(members, registry=registry)["clientCapabilities"]
    assert {"client.charge.cap@1", "client.direct.parameters@1", "client.unique.hidden@1", "client.text.desc_override@1"} <= set(caps)
    result = infer_requirements({"t": payload(STRINGS, {"ordinary": "13999010 hidden_ desc_override_"})}, registry=registry)
    assert not result["clientCapabilities"]


def test_dsl_flags_and_unique_node_requirements(registry):
    tree = ["ActionDsl"] + [None] * 9 + [104, ["Block", [["Command", ["ACUnique", 13999010]]]]]
    encoded = encode_amf3(tree)
    compressor = zlib.compressobj(wbits=-15)
    raw = compressor.compress(encoded) + compressor.flush()
    logical = "battle/test$main.action.dsl.amf3.deflate"
    result = infer_requirements({"d": (raw, {"logical_path": logical})}, registry=registry)
    assert {"client.kind424.damage_convert@1", "client.charge.cap@1"} <= set(result["clientCapabilities"])
    with pytest.raises((ValueError, zlib.error)):
        infer_requirements({"bad": (b"bad", {"logical_path": logical})}, registry=registry)


def test_unison_is_first_row_and_overlimit_uses_real_level_keys(registry):
    combined = ability(0) + "\n" + ability(0, unison=True)
    result = infer_requirements({"a": payload(ABILITY, {"1": combined})}, registry=registry)
    assert "official.unison@1" not in result["clientCapabilities"]
    status = "master/character/character_status.orderedmap"
    assert "client.overlimit.lv120@1" in infer_requirements({"s": payload(status, {"1": {"120": "1,1"}})}, registry=registry)["clientCapabilities"]
    assert "client.overlimit.lv120@1" not in infer_requirements({"s": payload(status, {"1": {"100": "120,120"}})}, registry=registry)["clientCapabilities"]


def test_unknown_declaration_and_corrupt_table_cannot_be_no_dependencies(registry):
    with pytest.raises(ValueError, match="unknown declared"):
        infer_requirements({}, declared=["made.up@1"], registry=registry)
    with pytest.raises(ValueError):
        infer_requirements({"a": (b"bad", {"logical_path": ABILITY})}, registry=registry)
    with pytest.raises(ValueError, match="truncated"):
        infer_requirements({"a": payload(ABILITY, {"1": "1,2"})}, registry=registry)


def test_requires_schema_has_source_evidence_and_server_features(registry):
    doc = {"from_version": "1.4.228", "to_version": "1.4.229", "server_changes": [{}]}
    result = requirements_document(doc, {}, ["test.zip"], registry=registry,
        server={"assets/character_overlimit.json": json.dumps({"characters": [1]}).encode()})
    validate_document(result, "requires.schema.json")
    required = result["requires"]
    assert required["capabilityResolution"] == "resolved"
    assert required["serverFeatures"] == ["character-overlimit"]
    assert required["capabilityEvidence"] and required["serverRestart"]


def test_character_only_change_follows_existing_ability_and_skill(registry):
    from wf.caps.facts import CHARACTER, SKILL
    character = [""] * 25
    character[0], character[8], character[19] = "hero", "hero_skill", "100"
    skill = [""] * 8
    skill[7] = "battle/skill/hero/hero"
    tree = ["ActionDsl"] + [None] * 9 + [104, ["Block", []]]
    compressor = zlib.compressobj(wbits=-15)
    dsl = compressor.compress(encode_amf3(tree)) + compressor.flush()
    baseline = {ABILITY: nodes.build_node({"100": ability(423)}),
        SKILL: nodes.build_node({"hero_skill": {"1": leaf(skill)}}),
        "battle/skill/hero/hero.action.dsl.amf3.deflate": dsl}
    result = infer_requirements({"c": payload(CHARACTER, {"1": leaf(character)})},
                                read_raw=baseline.__getitem__, registry=registry)
    assert {"client.kind423.gauge_source_limit@1", "client.kind424.damage_convert@1"} <= set(result["clientCapabilities"])
    assert result["capabilityResolution"] == "resolved"
    del baseline[ABILITY]
    assert infer_requirements({"c": payload(CHARACTER, {"1": leaf(character)})},
        read_raw=baseline.__getitem__, registry=registry)["capabilityResolution"] == "partial"


def test_wrong_layer_table_is_rejected(registry):
    raw, entry = payload(ABILITY, {"1": ability(424)})
    entry["root"] = "medium"
    with pytest.raises(ValueError, match="common root"):
        infer_requirements({"a": (raw, entry)}, registry=registry)


@pytest.mark.parametrize("name,expected", [("skill_ready_alt_1", True), ("matched_skill_ready_alt_5", True),
    ("skill_ready_alt_6", False), ("battle_alt_1", False), ("skill_ready", False)])
def test_actual_voice_rotation_suffixes(name, expected, registry):
    result = infer_requirements({"v": (b"voice", {"logical_path": f"character/hero/voice/{name}.mp3"})}, registry=registry)
    assert ("client.voice.rotation@1" in result["clientCapabilities"]) is expected


@pytest.mark.parametrize("kind,wrong_block", [(422, "instant_content"), (423, "instant_content"),
    (424, "instant_content"), (419, "instant_content"), (724, "during_content"), (722, "during_content")])
def test_kind_numbers_from_the_wrong_enum_block_do_not_invent_capabilities(kind, wrong_block, registry):
    with pytest.raises(ValueError, match=f"问题: .*kind {kind}.*{wrong_block}"):
        infer_requirements({"a": payload(ABILITY, {"1": ability(kind, block=wrong_block)})}, registry=registry)
