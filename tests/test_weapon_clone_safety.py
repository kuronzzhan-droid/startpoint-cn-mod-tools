"""Weapon clone review regressions against actual table and server representations."""
import copy
import json

import pytest

from test_boss_shop_weapon import state, value_bytes  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL, SERVER_ENH
from wf.boss.weapon_edit import clone_weapon
from wf.boss.weapon_ids import INT32_MAX, MAX_WEAPON_ID, validate_weapon_id
from wf.boss.weapon_rules import AWAKENING, CUSTOM
from wf.boss.weapon_soul import INHERITED_RULE
from wf.studio.drafts import schema_errors
from wf.view.base149 import join


@pytest.mark.parametrize("reserved", [["5950001"], {"5950001"}, ("5950001",),
                                     {"weapons": [5950001]}])
def test_collection_reservations_are_never_ignored(state, reserved):
    spec = {"sourceWeapon": "5010005"}
    clone_weapon(state, spec, reserved)
    assert spec["id"] == "5950002"
    assert spec["enhancementProducts"] == ["595000201"]


@pytest.mark.parametrize("reserved", ["5950001", None, {"weapons": "5950001"},
                                     {"enhancementProducts": "595000101"}])
def test_malformed_reservations_fail_before_writing(state, reserved):
    with pytest.raises(ValueError, match="reserved IDs"):
        clone_weapon(state, {"sourceWeapon": "5010005"}, reserved)
    assert not state.client and not state.servers


def test_product_only_reservation_excludes_entire_weapon_namespace(state):
    reserved = {"enhancementProducts": ["595000101"]}
    spec = {"sourceWeapon": "5010005"}
    clone_weapon(state, spec, reserved)
    assert spec["id"] == "5950002"
    assert spec["enhancementProducts"] == ["595000201"]
    with pytest.raises(ValueError, match="ID collision"):
        clone_weapon(state, {"sourceWeapon": "5010005", "id": "5950001"}, reserved)


@pytest.mark.parametrize("identity", ["1", "8000201", "21474835"])
def test_explicit_weapon_ids_use_bound_for_all_99_stage_slots(state, identity):
    # The item fixture already occupies 1, so direct cloning must report collision.
    spec = {"sourceWeapon": "5010005", "id": identity}
    assert validate_weapon_id(identity) == identity
    assert not schema_errors({"operation": "weapon_clone", "weapon": spec}, "bossRequest")
    if identity == "1":
        with pytest.raises(ValueError, match="ID collision"):
            clone_weapon(state, spec)
        return
    clone_weapon(state, spec)
    assert spec["enhancementProducts"] == [str(int(identity) * 100 + 1)]
    assert int(identity) * 100 + 99 <= INT32_MAX
    assert state.server(AWAKENING)["rarityOverrides"][identity] == 5


@pytest.mark.parametrize("identity", ["0", "01", "21474836", "21474899", "99999999", "100000000", "１", 5950001, True])
def test_schema_and_clone_reject_noncanonical_or_out_of_range_weapon_ids(state, identity):
    spec = {"sourceWeapon": "5010005", "id": identity}
    assert schema_errors({"operation": "weapon_clone", "weapon": spec}, "bossRequest")
    with pytest.raises(ValueError, match="weapon ID"):
        clone_weapon(state, spec)
    assert not state.client and not state.servers


def test_weapon_limit_really_fits_and_review_suggested_limit_does_not():
    assert MAX_WEAPON_ID == 21474835
    assert MAX_WEAPON_ID * 100 + 99 <= INT32_MAX
    assert (MAX_WEAPON_ID + 1) * 100 + 99 > INT32_MAX


def test_nonmatching_saved_enhancement_product_is_rejected(state):
    with pytest.raises(ValueError, match="weapon ID \\* 100 \\+ stage"):
        clone_weapon(state, {"sourceWeapon": "5010005", "id": "5950001",
                             "enhancementProducts": ["595000102"]})


def test_multiple_awakening_clones_preserve_staged_maps_and_original_bytes(state):
    row = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    row[11] = "4"
    state.set_leaf(s.EQUIPMENT, ["5010005"], join(row))
    state.set_server_keys(AWAKENING, {"materialByEquipment": {"5010005": 10000311},
                                    "rarityOverrides": {"8000101": 5}})
    original = state.servers[AWAKENING]
    first, second = {"sourceWeapon": "5010005"}, {"sourceWeapon": "5010005"}
    clone_weapon(state, first)
    clone_weapon(state, second)
    final = state.server(AWAKENING)
    assert final["materialByEquipment"] == {"5010005": 10000311, "5950001": 10000311, "5950002": 10000311}
    assert final["rarityOverrides"] == {"8000101": 5, "5950001": 4, "5950002": 4}
    for identity in (first["id"], second["id"]):
        assert state.table(CUSTOM)["awakening_material_" + identity] == "10000311"
    assert value_bytes(state.servers[AWAKENING], "officialCrystals") == value_bytes(original, "officialCrystals")
    assert value_bytes(value_bytes(state.servers[AWAKENING], "rarityOverrides"), "8000101") == b"5"


def test_server_reads_latest_staged_bytes_without_a_stale_json_cache(state):
    assert state.server(AWAKENING)["rarityOverrides"] == {}
    updated = state.server(AWAKENING)
    updated["rarityOverrides"] = {"5950001": 4}
    state.servers[AWAKENING] = json.dumps(updated).encode()
    assert state.server(AWAKENING)["rarityOverrides"] == {"5950001": 4}


def test_staged_document_cannot_replace_missing_awakening_baseline(state):
    (state.server_dir / AWAKENING).unlink()
    state.set_server_keys(AWAKENING, {"rarityOverrides": {}}, required=False)
    staged = copy.deepcopy(state.servers)
    with pytest.raises(ValueError, match="complete baseline"):
        clone_weapon(state, {"sourceWeapon": "5010005", "id": "8000201"})
    assert state.servers == staged and not state.client


def test_restricted_clone_requires_client_string_baseline(state):
    del state.base.files[CUSTOM]
    state.set_server_keys(AWAKENING, {"materialByEquipment": {"5010005": 10000311}})
    staged = copy.deepcopy(state.servers)
    with pytest.raises(ValueError, match="client custom_ability_string baseline"):
        clone_weapon(state, {"sourceWeapon": "5010005"})
    assert not state.client and state.servers == staged


def test_different_soul_id_gets_independent_item_and_ability_copies(state):
    equipment = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    equipment[10] = "5010007"
    state.set_leaf(s.EQUIPMENT, ["5010005"], join(equipment))
    for logical in (ITEM, SOUL):
        state.set_leaf(logical, ["5010007"], state.table(logical)["5010005"], new=True)
    state.set_server_keys("assets/item_sale.json", {"5010007": {"sale_price": 9}}, new=True)
    donor_item, donor_soul = state.table(ITEM)["5010007"], state.table(SOUL)["5010007"]
    spec = {"sourceWeapon": "5010005", "soul_elements": [2], "soulDescription": "独立说明",
            "abilities": [{"table": "ability_soul", "row": 0, "block": "instant_content",
                           "kind": 34, "strength": [7000, 8000]}]}
    clone_weapon(state, spec)
    identity = spec["id"]
    assert s.parse_rows(state.table(s.EQUIPMENT)[identity])[0][10] == identity
    assert s.parse_rows(state.table(ITEM)[identity])[0][5] == "独立说明"
    assert s.parse_rows(state.table(ITEM)[identity])[0][12] == "2"
    assert state.table(SOUL)[identity] != donor_soul
    assert state.table(ITEM)["5010007"] == donor_item
    assert state.table(SOUL)["5010007"] == donor_soul
    assert state.server("assets/item_sale.json")[identity] == {"sale_price": 9}


@pytest.mark.parametrize("elements", ["0,3,2,1,4,5", "5,4,3,2,1,0"])
def test_all_element_donor_does_not_emit_a_restriction_warning(state, elements):
    row = s.parse_rows(state.table(ITEM)["5010005"])[0]
    row[12] = elements
    state.set_leaf(ITEM, ["5010005"], join(row))
    result = clone_weapon(state, {"sourceWeapon": "5010005"})
    assert not any(check["rule"] == INHERITED_RULE for check in result["checks"])


def test_source_description_override_is_not_inherited_over_new_soul_description(state):
    state.set_leaf(CUSTOM, ["desc_override_equipment_5010005"], "母本旧属性说明", new=True)
    spec = {"sourceWeapon": "5010005", "soul_elements": "all", "soulDescription": "全属性通用魂珠"}
    clone_weapon(state, spec)
    assert s.parse_rows(state.table(ITEM)[spec["id"]])[0][5] == "全属性通用魂珠"
    assert "desc_override_equipment_" + spec["id"] not in state.table(CUSTOM)
    assert state.table(CUSTOM)["desc_override_equipment_5010005"] == "母本旧属性说明"
