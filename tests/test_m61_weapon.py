"""M6.1 restricted weapon graph, text and currency counterexamples."""
import copy

import pytest

from test_boss_shop_weapon import state, state as shop_state, value_bytes  # noqa: F401
from test_m6_boss_reservations import editor  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_edit import edit_shop
from wf.boss.shop_model import ENH, ENH_SHOP, SOUL, ITEM
from wf.boss.weapon_edit import clone_weapon, edit_materials, check_ability_rows
from wf.boss.weapon_rules import AWAKENING, CUSTOM
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
    assert state.table(CUSTOM)["awakening_material_" + spec["id"]] == "10000311"
    assert state.table(CUSTOM)["unrelated_string"] == "preserved"
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


@pytest.mark.parametrize(("elements", "expected"), [
    ("all", "0,3,2,1,4,5"), ("auto", "30"), ([0], "0"), ([3, 1, 5], "3,1,5")])
def test_clone_explicit_soul_elements_and_description(state, elements, expected):
    donor = state.table(ITEM)["5010005"]
    spec = {"sourceWeapon": "5010005", "soul_elements": elements, "soulDescription": "专属魂珠说明"}
    assert not schema_errors({"operation": "weapon_clone", "weapon": spec}, "bossRequest")
    result = clone_weapon(state, spec)
    item = s.parse_rows(state.table(ITEM)[spec["id"]])[0]
    assert item[12] == expected and item[5] == "专属魂珠说明"
    assert state.table(ITEM)["5010005"] == donor
    assert result == {"id": spec["id"], "warnings": [], "checks": []}


@pytest.mark.parametrize("elements", [[], [0, 0], [6], [-1], [True], [1.5], ["0"], "0", None])
def test_clone_invalid_soul_elements_rejected_by_schema_and_editor(state, elements):
    spec = {"sourceWeapon": "5010005", "soul_elements": elements}
    assert schema_errors({"operation": "weapon_clone", "weapon": spec}, "bossRequest")
    with pytest.raises(ValueError, match="soul_elements"):
        clone_weapon(state, spec)


def test_clone_soul_description_rejects_delimiters(state):
    with pytest.raises(ValueError, match="soulDescription.*delimiters"):
        clone_weapon(state, {"sourceWeapon": "5010005", "soulDescription": "bad,text"})


def test_clone_inherits_soul_restriction_with_nonblocking_warning(state):
    row = s.parse_rows(state.table(ITEM)["5010005"])[0]
    row[5], row[12] = "母本说明", "0"
    state.set_leaf(ITEM, ["5010005"], join(row))
    spec = {"sourceWeapon": "5010005"}
    result = clone_weapon(state, spec)
    item = s.parse_rows(state.table(ITEM)[spec["id"]])[0]
    assert item[5] == "母本说明" and item[12] == "0"
    assert "母本武器 5010005" in result["warnings"][0]
    assert "item[12]='0'" in result["warnings"][0]
    assert result["checks"] == state.weapon_checks
    assert result["checks"][0]["status"] == "待验证" and not result["checks"][0]["blocking"]


def test_inherited_soul_warning_survives_preview_save_and_delivery_compile(editor):
    import wf_quest_lib as codec
    from wf.boss.weapon_soul import INHERITED_RULE
    from wf.studio.deliver_bridge import compile_draft
    items = codec.parse_node(editor.source.view.files[ITEM])
    donor = s.parse_rows(items["5010005"])[0]
    donor[12] = "0"
    items["5010005"] = join(donor)
    editor.source.view.files[ITEM] = codec.build_node(items)
    request = {"operation": "weapon_clone", "weapon": {"sourceWeapon": "5010005"}}
    preview = editor.preview("1006001", request)
    assert preview["ok"]
    assert any(c["rule"] == INHERITED_RULE for c in preview["checks"])
    applied = editor.apply("1006001", request)
    assert any(c["code"] == INHERITED_RULE and c["level"] == "warn" for c in applied["change"]["checks"])
    draft = editor.store.save(applied["questId"])
    compiled = compile_draft(editor.source, editor.store, draft, server_dir=editor.server_dir)
    assert any(c["rule"] == INHERITED_RULE and not c["blocking"] for c in compiled[4])


@pytest.mark.parametrize("field,value", [("soulDescription", "说明"), ("soul_elements", "all")])
def test_soul_clone_fields_cannot_be_silently_ignored_by_material_edits(field, value):
    spec = {"id": "5010005", field: value, "stages": [{"productId": "501000501",
        "costs": [{"itemId": "1", "amount": 2}]}]}
    assert schema_errors({"operation": "weapon_materials", "weapon": spec}, "bossRequest")


@pytest.mark.parametrize("has_materials", [False, True])
def test_clone_adds_actual_rarity_override_independently_of_material_restrictions(state, has_materials):
    row = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    row[11] = "4"
    state.set_leaf(s.EQUIPMENT, ["5010005"], join(row))
    document = {"rarityOverrides": {"8000101": 5}, "untouched": {"keep": [1, 2, 3]}}
    if has_materials:
        document["materialByEquipment"] = {"5010005": 10000311}
    state.set_server_keys(AWAKENING, document, required=False)
    before = state.servers[AWAKENING]
    spec = {"sourceWeapon": "5010005"}
    clone_weapon(state, spec)
    after = state.server(AWAKENING)
    assert after["rarityOverrides"] == {"8000101": 5, spec["id"]: 4}
    assert value_bytes(state.servers[AWAKENING], "untouched") == value_bytes(before, "untouched")
    assert value_bytes(value_bytes(state.servers[AWAKENING], "rarityOverrides"), "8000101") == b"5"
    if has_materials:
        assert after["materialByEquipment"] == {"5010005": 10000311, spec["id"]: 10000311}
    else:
        assert after["materialByEquipment"] == {}


def test_clone_rejects_missing_awakening_document_for_nonstandard_id_rarity(state):
    (state.server_dir / AWAKENING).unlink()
    spec = {"sourceWeapon": "5010005", "id": "4950001"}
    with pytest.raises(ValueError, match="complete baseline"):
        clone_weapon(state, spec)
    assert not state.servers and not state.client


def test_clone_reserves_ids_present_only_in_rarity_overrides(state):
    state.set_server_keys(AWAKENING, {"rarityOverrides": {"5950001": 4}}, required=False)
    spec = {"sourceWeapon": "5010005"}
    clone_weapon(state, spec)
    assert spec["id"] == "5950002"
    with pytest.raises(ValueError, match="ID collision"):
        clone_weapon(state, {"sourceWeapon": "5010005", "id": "5950001"})
