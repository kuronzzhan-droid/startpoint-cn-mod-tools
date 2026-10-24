"""v35 markers are typed, referenced, and keep legacy meaning separate."""
from copy import deepcopy

import pytest

from wf.caps.compat import check_compat
from wf.caps.facts import CHARACTER, PF, STRINGS, UNIQUE, table_signals
from wf.caps.requirements import infer_requirements
from wf.caps.method_evidence import accepted_hashes
from wf.caps.signals_v35 import unique_signals
from test_m2_compat import provided, registry, required
from test_m2_requirements import leaf, payload


@pytest.mark.parametrize("text,hidden", [
    ("wfx:24:0:100:0:hidden_label", True),
    ("wfx:x:x:x:x:hidden_label", True),
    ("wfx:24:0:100:0:visible:hidden_label", False),
    ("wfx:24:0:100:0", False),
    ("WFX:24:0:100:0:hidden_label", False),
    ("hidden_old", False),
])
def test_hidden_icons_follow_exact_runtime_field(text, hidden):
    assert (("selectors", "wfx.hidden_unique_icons") in list(unique_signals(text))) is hidden


@pytest.mark.parametrize("uid,text,needs_v2", [
    ("1299901", "fever:items:apple:label", False),
    ("1299909", "fever:items:apple:lv_label", False),
    ("1299901", "fever:items:apple:lv100", True),
    ("1299910", "fever:items:apple", True),
])
def test_fever_data_does_not_relabel_legacy_strings(uid, text, needs_v2):
    assert (("selectors", "fever.items.v2") in list(unique_signals(text, uid))) is needs_v2


def test_character_and_pf_follow_optional_custom_configuration():
    row = ["hero"] + ["0"] * 24
    row[5], row[17], row[19] = "ModDualForm:33", "leader_key", "ability_key"
    signals = list(table_signals(CHARACTER, ("123",), leaf(row)))
    keys = {value[1] for kind, value in signals if kind == "optional_ref"}
    assert {"wfx_pf4_123", "ability_visual_hero", "wfx_fever_voice_hero",
            "wfx_unlock_leader_key", "wfx_adaptive_ability_key"} <= keys
    assert ("selectors", "character_tag.ModDualForm") in signals
    pf = list(table_signals(PF, ("pf_override", "1"), "no_dsl"))
    assert ("optional_ref", (STRINGS, "wfx_snapcombo_pf_override")) in pf


def test_switched_action_skill_uses_c0_instead_of_unrelated_c7():
    program = "battle/action/skill/action/rare5/lady_summoner_campus$lady_summoner_campus_1"
    signals = list(table_signals("master/skill/switched_action_skill.orderedmap",
                                ("lady_summoner_campus_voice_ready", "1"),
                                leaf([program, "1", "2", "2400", "3000", "0", "0", "0"])))
    assert ("program", program) in signals
    assert ("program", "0") not in signals


@pytest.mark.parametrize("sid", ["wfx:999:0:100:0:unknown", "wfx:10:0:1:0:planned"])
def test_unknown_or_planned_wfx_never_becomes_resolved_empty_requirements(registry, sid):
    import wf_quest_lib as nodes
    result = infer_requirements({"unique": payload(UNIQUE, {"700": sid})},
                                read_raw={CHARACTER: nodes.build_node({})}.__getitem__, registry=registry)
    assert result["capabilityResolution"] == "partial" and result["unresolved"]


@pytest.mark.parametrize("code,cap", [
    (24, "client.direct.base@1"), (28, "client.direct.base@1"), (29, "client.direct.base@1"),
    (25, "client.direct.merge@1"), (26, "client.ability.resistance@1"),
    (71, "client.charge.cap@2"), (27, "client.heal.overflow_damage@1"),
    (60, "client.super_fever@1"), (61, "client.super_fever@1"), (62, "client.super_fever@1"),
])
def test_registered_effect_codes_produce_real_payload_dependencies(registry, code, cap):
    import wf_quest_lib as nodes
    flags = 1 if code == 60 else 0
    result = infer_requirements({"unique": payload(UNIQUE, {"700": f"wfx:{code}:0:100:{flags}:effect"})},
                                read_raw={CHARACTER: nodes.build_node({})}.__getitem__, registry=registry)
    assert cap in result["clientCapabilities"] and result["capabilityResolution"] == "resolved"


def test_variant_is_exact_swf_bound_and_unknown_hashes_stay_blocked(registry):
    registry = deepcopy(registry)
    cap = registry["client.apk.patch087@1"]
    method = cap["provided_by"]["methods"][0]
    old = method["sha256"]
    method["accepted_variants"] = [{"sha256": "a" * 64, "swf_sha256": "b" * 64,
                                    "source": "offline fixture", "reason": "intentional replacement"}]
    assert accepted_hashes(method, "b" * 64) == {"a" * 64}
    assert accepted_hashes(method, "c" * 64) == {old}
    client = provided(registry, (87,))
    client["source"]["swf_sha256"] = "b" * 64
    req = required([cap["id"]], clientPatches=["#87"])
    # A client claiming the new SWF with its old method bytes is inconsistent.
    assert any(r["blocking"] for r in check_compat(req, client, registry=registry))
    key = method["patch"], method["abc"], method["label"]
    for entry in client["patches"] + client["provides"]:
        for actual in entry["methods"]:
            if (actual["patch"], actual["abc"], actual["label"]) == key:
                actual["sha256"] = "a" * 64
    assert not any(r["blocking"] for r in check_compat(req, client, registry=registry))
    client["source"]["swf_sha256"] = "c" * 64
    assert any(r["blocking"] for r in check_compat(req, client, registry=registry))
