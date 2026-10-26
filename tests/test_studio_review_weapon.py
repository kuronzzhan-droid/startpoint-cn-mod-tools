"""Weapon-set review regressions using the shared synthetic workshop."""
import json
import pytest
import wf_quest_lib as codec

from test_studio_weapon_set import workshop, full_set, clone, call  # noqa: F401
from test_studio_weapon_routes import app  # noqa: F401
from test_boss_shop_weapon import state  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ENH_CATEGORY, SERVER_ENH, SERVER_SHOP, SERVER_MAP
from wf.boss.weapon_rules import AWAKENING
from wf.deliver.key_guard import _server_problems, check_shared_keys
from wf.studio.ids import check_id
from wf.view.base149 import join


def test_category_and_product_gates_are_cleared_with_exact_widths(workshop):
    files = workshop.source.view.files
    categories = codec.parse_node(files[s.SHOP_CATEGORY])
    row = s.parse_rows(categories["81"])[0]
    row[2], row[3:9], row[11:13] = "2", ["locked"] * 6, ["event", "true"]
    categories["81"] = join(row)
    files[s.SHOP_CATEGORY] = codec.build_node(categories)
    products = codec.parse_node(files[s.SHOP])
    row = s.parse_rows(products["100"])[0]
    row[1], row[3:6] = "event", ["campaign", "lineup", "prefix"]
    products["100"] = join(row)
    files[s.SHOP] = codec.build_node(products)
    wid = clone(workshop)["weaponId"]
    spec = full_set()
    spec["exchange"]["category"] = {"sourceCategory": "81", "code": "my_store", "name": "Store"}
    status, result = call(workshop, "POST", f"/{wid}/set", spec)
    assert status == 200, result
    current, _ = workshop.weapons.editor.state(wid)
    allocation = result["allocation"]
    category = s.parse_rows(current.table(s.SHOP_CATEGORY)[allocation["exchange"]["category"]["id"]])[0]
    assert len(category) == 13 and category[2] == "2"
    assert category[3:9] == ["(None)"] * 6 and category[11:13] == ["", "false"]
    enhancement = s.parse_rows(current.table(ENH_CATEGORY)[allocation["enhancementCategory"]["id"]])[0]
    assert len(enhancement) == 10 and enhancement[2] == enhancement[9] == "(None)"
    assert enhancement[4:6] == ["item/banner", "item/header"]
    product = s.parse_rows(current.table(s.SHOP)[allocation["exchange"]["productId"]])[0]
    assert product[1] == "(None)" and product[3:6] == ["(None)", "", "(None)"]


def test_shop_guard_protects_nested_products_but_allows_asserted_delete():
    old = b'{"81":{"100":{},"101":{}}}'
    assert _server_problems(SERVER_SHOP, old, b'{"81":{"100":{}}}')
    assert not _server_problems(SERVER_SHOP, old, b'{"81":{"100":{}}}', {"101"})
    assert not _server_problems(SERVER_SHOP, old, b'{}', {"100", "101"})
    assert _server_problems(SERVER_MAP, b'{"100":81}', b'{}')
    raw = codec.build_node({"100": "x"})
    result = check_shared_keys({"fixture": (raw, {"logical_path": s.SHOP})}, {}, protected={})
    assert any("missing complete client baseline" in e for e in result["errors"])


def test_preview_allocation_options_and_category_only_rules(workshop):
    wid = clone(workshop)["weaponId"]
    status, preview = call(workshop, "POST", f"/{wid}/set", full_set(), {"preview": ["true"]})
    assert status == 200 and preview["allocation"]["exchange"]["productId"]
    _, choices = call(workshop, "GET", "/set-options")
    assert any(p["id"] == "100" and p["categoryId"] == "81" for p in choices["products"])
    assert call(workshop, "POST", f"/{wid}/set", full_set())[0] == 200
    from wf.studio.weapon_set_enhancement import move_category
    current, _ = workshop.weapons.editor.state(wid)
    with pytest.raises(ValueError, match="official 1..4"):
        move_category(current, wid, "1")
    old = workshop.weapons.store.load(wid)
    assert call(workshop, "POST", f"/{wid}/set", {"noSoul": False})[0] == 400
    assert workshop.weapons.store.load(wid) == old


def test_server_only_occupancy_and_nested_preview_delta(workshop):
    directory = workshop.weapons.server_dir
    for relative, value in ((SERVER_ENH, {"500": {"shopCategoryId": 89}}),
                            (SERVER_SHOP, {"88": {"999": {}}}), (SERVER_MAP, {"998": 87})):
        (directory / relative).write_text(json.dumps(value), encoding="utf-8")
    for kind, value in (("enhancement_category", "89"), ("exchange_category", "87"),
                        ("exchange_category", "88"), ("exchange_product", "999")):
        assert not check_id(workshop.source, kind, value, server_dir=directory)["available"]
    from wf.studio.weapon_set import changed_keys
    assert changed_keys({"81": {"100": {"stock": 1}, "101": 2}},
                        {"81": {"100": {"stock": 3}, "101": 2}}) == {"81": {"100": {"stock": 3}}}


def test_awakening_merge_preserves_other_child_bytes_and_server_only_fix(workshop):
    directory = workshop.weapons.server_dir
    target = directory / AWAKENING
    target.write_bytes(b'{ "materialByEquipment": {"keep" : 5}, "rarityOverrides": {"keep" : 4} }')
    status, result = call(workshop, "POST", "/5010005/set", {"awakeningMaterial": "1"})
    assert status == 200, result
    current, _ = workshop.weapons.editor.state("5010005")
    assert b'"keep" : 5' in current.servers[AWAKENING]
    assert b'"keep" : 4' in current.servers[AWAKENING]
    # The source client already disables soul output; only its server mirror needs repair.
    equipment = codec.parse_node(workshop.source.view.files[s.EQUIPMENT])
    row = s.parse_rows(equipment["5010005"])[0]
    row[9] = "false"
    equipment["5010005"] = join(row)
    workshop.source.view.files[s.EQUIPMENT] = codec.build_node(equipment)
    from wf.studio.weapon_editor import WeaponEditor
    from wf.studio.weapon_store import WeaponDraftStore
    editor = WeaponEditor(workshop.source, store=WeaponDraftStore(directory.parent / "isolated"), server_dir=directory)
    result = editor.apply("weapon_set", {"id": "5010005", "noSoul": True}, wid="5010005")
    assert result["ok"] and result["serverTargets"] == ["assets/equipment_dissolve.json"]


def test_borrowed_high_cap_curve_retains_target_display_and_ability(state, monkeypatch):
    from wf.boss.shop_model import ENH, ENH_STATUS, ENH_ABILITY
    from wf.studio.weapon_set_enhancement import enhance
    from wf.boss.weapon_edit import clone_weapon
    spec = {"sourceWeapon": "5010005", "id": "5950001", "name": "Private weapon"}
    clone_weapon(state, spec, {})
    wid = spec["id"]
    own_display = state.table(ENH)[wid]
    own_ability = state.table(ENH_ABILITY)[wid]
    state.set_leaf(ENH, ["5010005"], "200,150,Wrong,150,item/wrong,150,Wrong,200,2000-01-01")
    state.set_leaf(ENH_STATUS, ["5010005"], {"1": "1,1", "120": "120,120", "200": "200,200"})
    monkeypatch.setattr("wf.boss.weapon_edit.check_ability_rows", lambda *a, **kw: pytest.fail("unchanged ability must not load SWF"))
    enhance(state, wid, {"sourceWeapon": "5010005", "maxLevel": 120,
                        "stages": [{"maxLevel": 120, "costs": []}]}, "7", {})
    assert state.table(ENH)[wid] == own_display
    assert state.table(ENH_ABILITY)[wid] == own_ability
    assert set(state.table(ENH_STATUS)[wid]) == {"1", "120"}


def test_new_category_rename_is_owned_but_reuse_is_not_definition(workshop):
    from wf.studio.weapon_store import reservations
    wid = clone(workshop)["weaponId"]
    status, saved = call(workshop, "POST", f"/{wid}/set", full_set())
    assert status == 200
    cid = saved["allocation"]["enhancementCategory"]["id"]
    status, result = call(workshop, "POST", f"/{wid}/set", {
        "enhancementCategory": {"id": cid, "code": "renamed", "name": "Renamed"}})
    assert status == 200, result
    current, _ = workshop.weapons.editor.state(wid)
    row = s.parse_rows(current.table(ENH_CATEGORY)[cid])[0]
    assert row[0] == "renamed" and row[3] == "Renamed"
    registered = reservations(workshop.weapons.store)
    assert not registered.get("exchange_category_definitions")  # existing category 81 was reused.
