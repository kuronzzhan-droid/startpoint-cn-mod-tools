"""M6.1 restricted weapon graph, text and currency counterexamples."""
import copy

import pytest

from test_boss_shop_weapon import state, state as shop_state, value_bytes  # noqa: F401
from test_m6_boss_reservations import editor  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_edit import edit_shop
from wf.boss.shop_model import ENH, ENH_SHOP, SOUL
from wf.boss.weapon_edit import clone_weapon, edit_materials, check_ability_rows
from wf.boss.weapon_rules import AWAKENING
from wf.studio.drafts import schema_errors
from wf.view.base149 import join


@pytest.mark.parametrize("operation", ["shop_add", "shop_edit", "weapon_clone"])
@pytest.mark.parametrize("field", ["name", "description"])
def test_ascii_comma_in_names_or_descriptions_is_rejected(state, operation, field):
    if operation == "weapon_clone":
        action = lambda: clone_weapon(state, {"sourceWeapon": "5010005", field: "bad,text"})
    else:
        action = lambda: edit_shop(state, {"operation": operation, "shop": {"category": "81",
            "sourceProduct": "100", "productId": "100" if operation == "shop_edit" else "991000000",
            field: "bad,text"}}, {"81"})
    with pytest.raises(ValueError, match="delimiters"):
        action()


def test_enhanced_weapon_description_matches_requested_description(state):
    spec = {"sourceWeapon": "5010005", "name": "副本武器", "description": "中文，描述"}
    clone_weapon(state, spec)
    base = s.parse_rows(state.table(s.EQUIPMENT)[spec["id"]])[0]
    enhanced = s.parse_rows(state.table(ENH)[spec["id"]])[0]
    assert base[1] == "副本武器" and enhanced[2] == "副本武器·改"
    assert base[7] == enhanced[6] == "中文，描述"


@pytest.mark.parametrize("source", ["5910101", "5920001"])
def test_clone_preserves_restricted_awakening_mapping_and_unrelated_bytes(state, source):
    from wf.boss.weapon_edit import SERVER_WEAPON_MAPS
    from wf.boss.shop_model import WEAPON_TABLES
    for logical in WEAPON_TABLES:
        table = state.table(logical)
        if "5010005" in table:
            state.set_leaf(logical, [source], copy.deepcopy(table["5010005"]), new=True)
    for target in SERVER_WEAPON_MAPS:
        values = state.server(target)
        if "5010005" in values:
            state.set_server_keys(target, {source: copy.deepcopy(values["5010005"])}, new=True)
    state.set_server_keys(AWAKENING, {"materialByEquipment": {source: 10000311, "5950001": 10000312},
                                    "rarityOverrides": {"5": [4, 3, 2, 1]}}, required=False)
    raw = state.servers[AWAKENING]
    spec = {"sourceWeapon": source}
    clone_weapon(state, spec)
    assert spec["id"] == "5950002"
    assert state.server(AWAKENING)["materialByEquipment"][spec["id"]] == 10000311
    assert value_bytes(state.servers[AWAKENING], "rarityOverrides") == value_bytes(raw, "rarityOverrides")
    assert value_bytes(value_bytes(state.servers[AWAKENING], "materialByEquipment"), source) == b"10000311"


@pytest.mark.parametrize("source", ["5910101", "5920001"])
def test_restricted_weapon_without_awakening_evidence_is_rejected(state, source):
    with pytest.raises(ValueError, match="materialByEquipment"):
        clone_weapon(state, {"sourceWeapon": source})


@pytest.mark.parametrize("cost", [{"type": 0, "amount": 10}, {"type": True, "amount": 10},
                                 {"type": 2, "amount": 0}])
def test_invalid_user_cost_rejected_by_schema_and_direct_editor(state, cost):
    spec = {"id": "5010005", "stages": [{"productId": "501000501",
        "costs": [{"itemId": "1", "amount": 9}], "userCost": cost}]}
    assert schema_errors({"operation": "weapon_materials", "weapon": spec}, "bossRequest")
    with pytest.raises(ValueError, match="userCost"):
        edit_materials(state, spec)


def test_clone_rejects_existing_paid_bead_stage(state):
    row = s.parse_rows(state.table(ENH_SHOP)["501000501"])[0]
    row[11:13] = ["0", "10"]
    state.set_leaf(ENH_SHOP, ["501000501"], join(row))
    with pytest.raises(ValueError, match="paid beads"):
        clone_weapon(state, {"sourceWeapon": "5010005"})


def test_kind_validation_uses_configured_default_and_selected_profile(state, monkeypatch):
    seen = []
    def inspect(profile):
        seen.append(profile)
        return {"mismatches": [], "tables": {"ability_soul": {
            "instant_content": {"kinds": ["32", "34"] if profile == "selected-v35" else []}}}}
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", inspect)
    monkeypatch.setattr("wf.caps.profiles.load_profiles", lambda: ("selected-v35", {}))
    check_ability_rows("ability_soul", state.table(SOUL)["5010005"])
    with pytest.raises(ValueError, match="unsupported"):
        check_ability_rows("ability_soul", state.table(SOUL)["5010005"], client_profile="other-profile")
    assert seen == ["selected-v35", "other-profile"]


def test_compile_uses_delivery_selected_profile_in_both_weapon_tables(editor, monkeypatch):
    from wf.studio.deliver_bridge import compile_draft
    applied = editor.apply("1006001", {"operation": "weapon_clone", "weapon": {"sourceWeapon": "5010005"}})
    draft = editor.store.save(applied["questId"])
    seen = []
    def inspect(profile):
        seen.append(profile)
        return {"mismatches": [], "tables": {table: {"instant_content": {"kinds": ["32", "34"]}}
            for table in ("ability_soul", "equipment_enhancement_ability")}}
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", inspect)
    compile_draft(editor.source, editor.store, draft, server_dir=editor.server_dir, client_profile="selected-v35")
    assert seen == ["selected-v35", "selected-v35"]
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", lambda _: {"mismatches": [], "tables": {}})
    with pytest.raises(ValueError, match="unsupported"):
        compile_draft(editor.source, editor.store, draft, server_dir=editor.server_dir, client_profile="selected-v35")
