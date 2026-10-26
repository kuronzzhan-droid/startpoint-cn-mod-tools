"""P0 code ownership, source-faithful metadata and soul template contracts."""
import zlib

import pytest
import wf_client_legality
import wf_dsl

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app, call, clone  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL
from wf.boss.weapon_edit import clone_weapon
from wf.boss.weapon_templates import (INVOKE_CAPABILITIES, _attack_tree, apply_template, template_row)
from wf.studio.drafts import validate
from wf.view.base149 import join


def test_custom_code_and_exclusive_metadata_have_no_invented_column(state):
    original = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    clone_weapon(state, {"sourceWeapon": "5010005", "id": "5950001", "code": "duet",
                         "exclusive_character": "139988"})
    equipment = s.parse_rows(state.table(s.EQUIPMENT)["5950001"])[0]
    item = s.parse_rows(state.table(ITEM)["5950001"])[0]
    assert equipment[0] == "duet" and item[0] == "duet_soul"
    assert equipment[2:10] == original[2:10] and equipment[11:] == original[11:]
    assert state.weapon_checks[-1]["enforcement"] == "metadata_only"
    assert state.weapon_checks[-1]["characterId"] == "139988"


def test_default_boss_code_remains_compatible(state):
    clone_weapon(state, {"sourceWeapon": "5010005", "id": "5950001"})
    assert s.parse_rows(state.table(s.EQUIPMENT)["5950001"])[0][0] == "boss_workshop_5950001"
    assert s.parse_rows(state.table(ITEM)["5950001"])[0][0] == "boss_workshop_soul_5950001"


@pytest.mark.parametrize("code", ["../weapon", "A", "weapon-name", "a" * 81, "", "龙"])
def test_code_grammar_is_enforced_without_schema(state, code):
    with pytest.raises(ValueError, match="weapon code"):
        clone_weapon(state, {"sourceWeapon": "5010005", "code": code})


def test_equipment_and_derived_soul_code_collisions_are_rejected(state):
    row = s.parse_rows(state.table(ITEM)["1"])[0]
    row[0] = "duet_soul"
    state.set_leaf(ITEM, ["1"], join(row))
    with pytest.raises(ValueError, match="code collision"):
        clone_weapon(state, {"sourceWeapon": "5010005", "code": "duet"})
    with pytest.raises(ValueError, match="code collision"):
        clone_weapon(state, {"sourceWeapon": "5010005", "code": "reserved"}, {"codes": ["reserved"]})


def test_independent_drafts_reserve_custom_codes_and_preview_does_not(app):
    request = {"sourceWeapon": "5010005", "code": "fresh_code"}
    assert call(app, "POST", "/clone", request, {"preview": ["true"]})[0] == 200
    created = clone(app, code="fresh_code")
    code, rejected = call(app, "POST", "/clone", request)
    assert code == 400 and "code collision" in rejected["error"]
    assert len(app.weapons.store.characters()) == 1
    assert app.weapons.editor.state(created["weaponId"])[1] is not None


@pytest.mark.parametrize("name,trigger,base", [("pf_hit_ability_damage", 183, 316),
                                               ("pf_use_ability_damage", 2, 251)])
@pytest.mark.parametrize("element", range(6))
def test_native_templates_are_legal_and_use_element_kind_family(name, trigger, base, element):
    spec = {"template": name, "element": element, "multiplier": 1.25, "max_multiplier": 3,
            "trigger_limit": 5, "cooldown_frames": 120}
    validate(spec, "weaponSoulTemplate")
    row = template_row(spec)
    assert len(row) == 123 and row[24] == str(trigger) and row[44] == str(base + element)
    assert row[31:33] == ["5", "120"] and row[48:50] == ["125000", "300000"]
    assert row[67:69] == ["", ""]
    assert wf_client_legality.client_legality_problems("ability_soul", row) == []


@pytest.mark.parametrize("extra", [{"element": 6}, {"element": True}, {"multiplier": -1},
                                   {"max_multiplier": 0.5}, {"trigger_limit": 0},
                                   {"cooldown_frames": -1}, {"hit_effect": "Explosion"},
                                   {"damage_target": "trigger_enemy"}])
def test_native_template_rejects_unsafe_parameters(extra):
    spec = {"template": "pf_use_ability_damage", "element": 2, "multiplier": 1, **extra}
    with pytest.raises(ValueError):
        template_row(spec)


def test_native_template_replaces_donor_soul_rows_in_http_draft(app, monkeypatch):
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", lambda _: {"mismatches": [], "tables": {
        "ability_soul": {"instant_content": {"kinds": ["318"]}},
        "equipment_enhancement_ability": {"instant_content": {"kinds": ["32", "34"]}}}})
    created = clone(app, code="native_pf", soul_template={"template": "pf_hit_ability_damage",
                    "element": 2, "multiplier": 1, "trigger_limit": 7})
    state, _ = app.weapons.editor.state(created["weaponId"])
    rows = s.parse_rows(state.table(SOUL)[created["weaponId"]])
    assert len(rows) == 1 and rows[0][24] == "183" and rows[0][44] == "318" and rows[0][31] == "7"
    assert not any(path.endswith(".action.dsl.amf3.deflate") for path in state.client)


def invoke_spec(**extra):
    return {"template": "pf_use_invoke_damage", "element": 2, "dsl_element": 3,
            "hit_effect": "Explosion", "multiplier": 2, **extra}


@pytest.mark.parametrize("extra", [{"dsl_element": 255}, {"dsl_element": 2}, {"hit_effect": "Slash"},
                                   {"hit_effect": None}, {"max_multiplier": 3}])
def test_invoke_template_explicit_element_effect_and_fixed_multiplier(extra):
    with pytest.raises(ValueError):
        template_row(invoke_spec(**extra))


def test_invoke_cannot_be_selected_without_explicit_provides(state):
    with pytest.raises(ValueError, match="explicit target"):
        apply_template(state, invoke_spec(), "test")


def test_invoke_provides_and_soul_column_guards(state, tmp_path, monkeypatch):
    from wf.boss import weapon_templates
    document = {"provides": []}
    monkeypatch.setattr("wf.caps.profiles.resolve_client", lambda **kwargs: (tmp_path / "target.json", None))
    monkeypatch.setattr("wf.caps.profiles.read_client", lambda path: document)
    state.client_provides = tmp_path / "target.json"
    with pytest.raises(ValueError, match="target provides lacks"):
        apply_template(state, invoke_spec(), "test")
    document["provides"] = [{"id": value} for value in INVOKE_CAPABILITIES]
    with pytest.raises(ValueError, match="recorded patch 20"):
        apply_template(state, invoke_spec(), "test")
    for entry in document["provides"]:
        if entry["id"] == "client.kind424.damage_convert@1":
            entry["patches"] = [20]
    document["patches"] = [{"number": 20, "status": "recorded"}]
    seen = []
    monkeypatch.setattr(weapon_templates, "check_ability_rows", lambda *a, **kw: seen.append((a, kw)))
    row = s.parse_rows(apply_template(state, invoke_spec(), "test"))[0]
    assert row[44] == "629" and row[67] == "test_pf_damage"
    logical = row[68] + ".action.dsl.amf3.deflate"
    tree = wf_dsl.parse_dsl(zlib.decompress(state.client[logical], -15))["tree"]
    assert tree[10] == 2 and seen[0][1]["provides"] == state.client_provides
    assert row[70:72] == ["", ""]


@pytest.mark.parametrize("effect", ["Explosion", "None"])
def test_invoke_generated_tree_matches_dsl_signature_and_c10013_guards(effect):
    from wf.tools.weapon.cursed_weapons import dsl_signature_problems, colorless_hit_effect_problems
    tree = _attack_tree(1.5, 3, effect)
    assert dsl_signature_problems(tree) == []
    assert colorless_hit_effect_problems(tree) == []
    assert wf_client_legality.action_dsl_element_problems(tree) == []
    assert wf_client_legality.action_dsl_subject_binding_problems(tree) == []
    assert wf_client_legality.action_dsl_hit_area_target_problems(tree) == []
