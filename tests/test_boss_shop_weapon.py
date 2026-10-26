"""Shop/weapon authoring invariants and M2.4 weapon-column counterexamples."""
import copy
import json
from pathlib import Path

import pytest
import wf_quest_lib as codec

from wf.boss import schema as s
from wf.boss.edit_state import BossEditState
from wf.boss.shop_edit import edit_shop, server_product, item_reference
from wf.boss.shop_model import (ITEM, STATUS, SOUL, ENH, ENH_ABILITY, ENH_STATUS,
                                ENH_SHOP, ENH_CATEGORY, SERVER_SHOP, SERVER_MAP, SERVER_ENH)
from wf.boss.weapon_edit import clone_weapon, edit_materials, check_ability_rows
from wf.boss.weapon_rules import AWAKENING, CUSTOM
from wf.deliver.json_merge import _json_spans
from wf.view.base149 import join
from test_boss_edit_review import RawSource


@pytest.fixture
def state(tmp_path, monkeypatch):
    donor = json.loads(Path("assets/bond-weapons/official_baseline.json").read_bytes())["weapons"]["5010005"]
    soul = donor["soul"][0]
    ea = [soul[0], "1", "120", "0", "0", *soul[2:]]
    shop = [""] * 50
    shop[0], shop[6], shop[12], shop[13] = "81", "item", "item/weapon", "5"
    shop[17:25], shop[25:29] = ["1", "2", "(None)", "", "(None)", "", "(None)", ""], ["2000-01-01", "(None)", "1", "5"]
    shop[32:50] = ["4", "5010005", "1"] + ["(None)", "", ""] * 5
    enhancement = [""] * 50
    enhancement[0], enhancement[2], enhancement[3] = "7", "5010005", "1"
    enhancement[14:22], enhancement[29:32] = shop[17:25], ["5010005", "120", "5"]
    item = [""] * 23
    item[0:7], item[12] = ["soul", "5010005", "soul", "item/soul", "(None)", "", "11"], "0,3,2,1,4,5"
    equipment = list(donor["equipment"])
    equipment[6] = "item/weapon"
    tables = {s.SHOP: {"100": join(shop), "101": join(shop)}, s.SHOP_CATEGORY: {"81": "category"},
              ITEM: {"5010005": join(item), "1": join(item)}, s.EQUIPMENT: {"5010005": join(equipment)},
              SOUL: {"5010005": join(soul)}, ENH_ABILITY: {"5010005": join(ea)},
              STATUS: {"5010005": {"1": "100,20", "5": "200,40"}},
              ENH_STATUS: {"5010005": {"1": "1,1", "120": "120,120"}},
              ENH: {"5010005": "120,70,Weapon,70,item/enhanced,70,Description,120,2000-01-01"},
              ENH_SHOP: {"501000501": join(enhancement)}, ENH_CATEGORY: {"7": "category"},
              CUSTOM: {"unrelated_string": "preserved"}}
    raw = RawSource(tables, {"item/weapon.png": b"png", "item/soul.png": b"png", "item/enhanced.png": b"png"})
    server = {SERVER_SHOP: {"81": {"100": server_product(shop), "101": server_product(shop)}},
              SERVER_MAP: {"100": 81, "101": 81}, SERVER_ENH: {"501000501": {
                  "equipmentId": 5010005, "groupId": 5010005, "costs": [{"id": 1, "amount": 2}],
                  "enhancementMaxLevel": 120, "enhancementPurchaseMode": "per_level"}},
              "assets/equipment_lookup.json": {"5010005": {"name": "Weapon", "rarity": "5"}},
              "assets/equipment_max_level.json": {"5010005": 5},
              "assets/equipment_element.json": {"5010005": -1},
              "assets/item_sale.json": {"5010005": {"sale_price": 5}},
              "assets/item_lookup.json": {}, "assets/equipment_ids.json": [5010005], "assets/item_ids.json": [1, 5010005],
              AWAKENING: {"officialCrystals": {"12001": {"maxRarity": 4}, "12002": {"maxRarity": 5}},
                          "materialByEquipment": {}, "rarityOverrides": {}}}
    for target, document in server.items():
        filename = tmp_path / target
        filename.parent.mkdir(exist_ok=True)
        filename.write_text(json.dumps(document, indent=2), encoding="utf-8")
    # Unit fixtures model the known native branch. Real SWF integration is run
    # independently against both repository profiles by M2.4 and M6 acceptance.
    monkeypatch.setattr("wf.apk.kinds.inspect_profile", lambda _: {"mismatches": [], "tables": {
        t: {"instant_content": {"kinds": ["32", "34"]}} for t in ("ability_soul", "equipment_enhancement_ability")}})
    return BossEditState(raw, server_dir=tmp_path)


def value_bytes(raw, key):
    text, _, spans = _json_spans(raw)
    return text[slice(*spans[key])].encode("utf-8")


def test_shop_add_edit_delete_sync_and_preserve_other_product_bytes(state):
    before = state.base.files[s.SHOP]
    request = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100",
                "price": [{"itemId": "1", "amount": 7}], "stock": 9}}
    edit_shop(state, request, {"81"}, {"products": ["991000000"]})
    identity = request["shop"]["productId"]
    assert identity == "991000001"
    assert state.table(s.SHOP)["100"] == codec.parse_node(before)["100"]
    assert state.server(SERVER_MAP)[identity] == 81
    assert state.server(SERVER_SHOP)["81"][identity]["costs"] == [{"id": 1, "amount": 7}]
    original = value_bytes(value_bytes(state.server_original[SERVER_SHOP], "81"), "101")
    assert value_bytes(value_bytes(state.servers[SERVER_SHOP], "81"), "101") == original
    edit_shop(state, {"operation": "shop_edit", "shop": {"category": "81", "productId": identity, "stock": 3}}, {"81"})
    assert state.server(SERVER_SHOP)["81"][identity]["stock"] == 3
    edit_shop(state, {"operation": "shop_delete", "shop": {"category": "81", "productId": identity}}, {"81"})
    assert identity not in state.table(s.SHOP) and identity not in state.server(SERVER_MAP)
    assert identity not in state.server(SERVER_SHOP)["81"]
    assert value_bytes(value_bytes(state.servers[SERVER_SHOP], "81"), "101") == original


def test_shop_requires_category_same_number_and_all_three_existing_rows(state):
    state.base.files[s.SHOP_CATEGORY] = codec.build_node({"82": "other category"})
    with pytest.raises(ValueError, match="category"):
        edit_shop(state, {"operation": "shop_edit", "shop": {"category": "81", "productId": "100", "stock": 2}}, {"81"})


def test_shop_allocation_checks_server_only_occupation(state):
    state.set_server_keys(SERVER_MAP, {"991000000": 99})
    request = {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "100"}}
    edit_shop(state, request, {"81"})
    assert request["shop"]["productId"] == "991000001"


def test_shop_edit_preserves_unmodified_fields_inside_changed_product(state):
    original = state.server(SERVER_SHOP)
    raw = state.server_original[SERVER_SHOP]
    old_reward = value_bytes(value_bytes(value_bytes(raw, "81"), "100"), "rewards")
    edit_shop(state, {"operation": "shop_edit", "shop": {"category": "81", "productId": "100", "stock": 3}}, {"81"})
    assert state.server(SERVER_SHOP)["81"]["100"]["rewards"] == original["81"]["100"]["rewards"]
    assert value_bytes(value_bytes(value_bytes(state.servers[SERVER_SHOP], "81"), "100"), "rewards") == old_reward


def test_shop_name_edit_does_not_rewrite_server_dates_or_emit_identical_mirrors(state):
    original = state.server(SERVER_SHOP)
    original["81"]["100"]["availableFrom"] = "server-original-time"
    filename = state.server_dir / SERVER_SHOP
    filename.write_text(json.dumps(original, indent=2), encoding="utf-8")
    state.server_original.clear()
    edit_shop(state, {"operation": "shop_edit", "shop": {"category": "81", "productId": "100", "name": "Changed name"}}, {"81"})
    assert state.server(SERVER_SHOP)["81"]["100"]["availableFrom"] == "server-original-time"
    assert not state.servers


def test_clone_uses_weapon_kind_columns_and_copies_entire_material_graph(state):
    spec = {"sourceWeapon": "5010005", "name": "New weapon", "hpMultiplier": 2,
            "abilities": [{"table": "ability_soul", "row": 0, "block": "instant_content",
                           "kind": 34, "strength": [7000, 8000]}]}
    state.set_server_keys("assets/equipment_element.json", {"5950001": -1})
    clone_weapon(state, spec, {"weapons": ["5950002"], "enhancementProducts": ["595000301"]})
    assert spec["id"] == "5950004" and spec["enhancementProducts"] == ["595000401"]
    row = s.parse_rows(state.table(SOUL)[spec["id"]])[0]
    assert row[44] == "34" and row[48:50] == ["7000", "8000"]
    assert row[47] == s.parse_rows(state.table(SOUL)["5010005"])[0][47]
    assert state.table(STATUS)[spec["id"]]["5"] == "400,40"
    assert state.table(ENH_STATUS)[spec["id"]]["120"] == "240,120"
    assert state.server(SERVER_ENH)["595000401"]["equipmentId"] == 5950004
    assert 5950004 in state.server("assets/equipment_ids.json")
    assert state.table(ITEM)["5010005"] != state.table(ITEM)[spec["id"]]


def test_clone_icon_reuses_paired_soul_reference_not_old_atlas_name(state):
    source = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    other = copy.deepcopy(source)
    other[6], other[10] = "item/other", "5010006"
    state.set_leaf(s.EQUIPMENT, ["5010006"], join(other), new=True)
    soul = s.parse_rows(state.table(ITEM)["5010005"])[0]
    soul[3] = "item/other_soul"
    state.set_leaf(ITEM, ["5010006"], join(soul), new=True)
    state.base.files.update({"item/other.png": b"png", "item/other_soul.png": b"png"})
    spec = {"sourceWeapon": "5010005", "icon": "item/other"}
    clone_weapon(state, spec)
    result = s.parse_rows(state.table(ITEM)[spec["id"]])[0]
    assert result[3:5] == ["item/other_soul", "(None)"]


def test_material_edit_updates_client_and_server_only_selected_stage(state):
    before = state.base.files[ENH_SHOP]
    edit_materials(state, {"id": "5010005", "stages": [{"productId": "501000501", "costs": [{"itemId": "1", "amount": 9}]}]})
    assert s.parse_rows(state.table(ENH_SHOP)["501000501"])[0][14:16] == ["1", "9"]
    assert state.server(SERVER_ENH)["501000501"]["costs"] == [{"id": 1, "amount": 9}]
    assert state.base.files[ENH_SHOP] == before


def test_material_chain_starts_at_enhancement_zero_and_counts_user_currency(state):
    from wf.boss.provenance import BossTables
    from wf.boss.shop_model import equipment
    # Native equipment level and enhancement level are independent counters.
    state.set_leaf(STATUS, ["5010005", "100"], "1000,400", new=True)
    first = s.parse_rows(state.table(ENH_SHOP)["501000501"])[0]
    first[30] = "110"
    state.set_leaf(ENH_SHOP, ["501000501"], join(first))
    second = list(first)
    second[3], second[30], second[15], second[11], second[12] = "2", "120", "3", "2", "7"
    state.set_leaf(ENH_SHOP, ["501000502"], join(second), new=True)
    model = equipment(BossTables(state), "5010005")
    assert model["enhancement_start_level"] == 0
    assert [(r["startLevel"], r["purchaseCountTo120"]) for r in model["enhancement_chain"]] == [(0, 110), (110, 10)]
    assert model["materials_to_120"] == [{"itemId": "1", "amount": 250}]
    assert model["user_costs_to_120"] == [{"type": "2", "amount": 70}]


def test_material_user_currency_update_and_removal_sync(state):
    spec = {"id": "5010005", "stages": [{"productId": "501000501", "costs": [{"itemId": "1", "amount": 3}],
                                           "userCost": {"type": 2, "amount": 8}}]}
    edit_materials(state, spec)
    assert s.parse_rows(state.table(ENH_SHOP)["501000501"])[0][11:13] == ["2", "8"]
    assert state.server(SERVER_ENH)["501000501"]["userCost"] == {"type": 2, "amount": 8}
    spec["stages"][0]["userCost"] = None
    edit_materials(state, spec)
    assert "userCost" not in state.server(SERVER_ENH)["501000501"]


def test_kind_written_at_character_column_is_rejected(state):
    row = s.parse_rows(state.table(SOUL)["5010005"])[0]
    row[44], row[47] = "", row[44]
    with pytest.raises(ValueError, match="kind/fields"):
        check_ability_rows("ability_soul", join(row))


def test_wrong_instant_block_kind_is_rejected_by_real_branch_contract(state):
    row = s.parse_rows(state.table(SOUL)["5010005"])[0]
    row[44] = "423"
    with pytest.raises(ValueError, match="kind|SWF"):
        check_ability_rows("ability_soul", join(row))


def test_c8004_requires_loaded_atlas_member_not_standalone_png(state):
    row = s.parse_rows(state.table(ITEM)["1"])[0]
    row[4] = "item_icon/missing"
    state.set_leaf(ITEM, ["1"], join(row))
    state.base.files["item_icon/missing.png"] = b"present but irrelevant"
    with pytest.raises(ValueError, match="C8004"):
        item_reference(state, "1")
