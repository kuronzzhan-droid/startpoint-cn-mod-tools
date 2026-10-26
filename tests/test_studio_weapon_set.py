"""Optional weapon-set contracts: final rows, mirrors, replay and rejected drift."""
import copy
import json
import zlib

import pytest
import wf_quest_lib as codec
import wf_mod_tool as core

from test_studio_weapon_routes import app, call, clone  # noqa: F401
from test_boss_shop_weapon import state  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL, ENH, ENH_SHOP, ENH_CATEGORY, SERVER_ENH, SERVER_SHOP, SERVER_MAP
from wf.boss.weapon_rules import AWAKENING, CUSTOM
from wf.studio.weapon_editor import compile_weapon
from wf.studio.ids import check_id
from wf.view.base149 import join


@pytest.fixture
def workshop(app):
    files = app.source.view.files
    # All new rows/art are synthetic. No private paths/assets are copied.
    files[ENH_CATEGORY] = codec.build_node({"7": join([
        "bond", "0", "", "羁绊", "item/banner", "item/header", "help", "help", "2000-01-01"])})
    files[s.SHOP_CATEGORY] = codec.build_node({"81": join([
        "exchange", "1", "(None)", "", "", "", "", "", "", "item/banner"])})
    files["item/banner.png"] = files["item/header.png"] = b"synthetic image existence fixture"
    item = s.parse_rows(codec.parse_node(files[ITEM])["1"])[0]
    item[2], item[6] = "测试星铁", "0"
    table = codec.parse_node(files[ITEM])
    table["1"] = join(item)
    files[ITEM] = codec.build_node(table)
    filename = app.weapons.server_dir / "assets/equipment_dissolve.json"
    filename.write_text(json.dumps({"5010005": {"ability_soul_id": 5010005,
        "generate_ability_soul": True, "mana": 23}, "42": {"unchanged": True}}), encoding="utf-8")
    return app


def full_set():
    return {"noSoul": True, "awakeningMaterial": "1",
        "enhancementCategory": {"sourceCategory": "7", "code": "exclusive", "name": "专属武器·觉醒"},
        "enhancement": {"maxLevel": 120, "stages": [
            {"maxLevel": cap, "costs": [{"itemId": "1", "amount": cost}] if cost else []}
            for cap, cost in ((68, 0), (69, 1), (70, 1), (97, 0), (98, 2), (99, 2), (118, 0), (119, 3), (120, 3))]},
        "exchange": {"category": {"id": "81"}, "sourceProduct": "100", "itemId": "1", "amount": 3, "stock": 1}}


def test_weapon_set_preview_replay_exact_costs_and_preservation(workshop):
    app = workshop
    created = clone(app)
    wid = created["weaponId"]
    old_draft = app.weapons.store.load(wid)
    baseline = copy.deepcopy(app.source.view.files)
    originals = {path: path.read_bytes() for path in (app.weapons.server_dir / "assets").glob("*.json")}
    code, preview = call(app, "POST", f"/{wid}/set", full_set(), {"preview": ["true"]})
    assert code == 200, preview
    assert app.weapons.store.load(wid) == old_draft
    cost_check = next(c for c in preview["checks"] if c["rule"] == "weapon.enhancement-cost")
    assert cost_check["materialTotals"] == {"1": 12}
    code, saved = call(app, "POST", f"/{wid}/set", full_set())
    assert code == 200, saved
    assert saved["rows"] == preview["rows"]
    compiled = compile_weapon(app.source, app.weapons.store, saved["changeset"], server_dir=app.weapons.server_dir)
    candidate, _ = app.weapons.editor.state(wid)
    equipment = s.parse_rows(candidate.table(s.EQUIPMENT)[wid])[0]
    assert equipment[9:11] == ["false", wid]
    assert wid in candidate.table(ITEM) and wid in candidate.table(SOUL)
    assert candidate.server("assets/equipment_dissolve.json")[wid] == {
        "ability_soul_id": int(wid), "generate_ability_soul": False, "mana": 23}
    assert candidate.server("assets/equipment_dissolve.json")["42"] == {"unchanged": True}
    assert candidate.server(AWAKENING)["materialByEquipment"][wid] == 1
    assert candidate.table(CUSTOM)["awakening_material_" + wid] == "1"
    ladder = [(key, s.parse_rows(text)[0]) for key, text in candidate.table(ENH_SHOP).items()
              if s.parse_rows(text)[0][29] == wid]
    previous, paid = 0, []
    for key, row in ladder:
        cap = int(row[30])
        cost = int(row[15]) if row[14] == "1" else 0
        assert row[11:14] == ["(None)", "", "(None)"]
        assert row[16:22] == ["(None)", ""] * 3
        assert candidate.server(SERVER_ENH)[key]["costs"] == ([{"id": 1, "amount": cost}] if cost else [])
        paid += [[level, cost] for level in range(previous + 1, cap + 1) if cost]
        previous = cap
    assert paid == [[69, 1], [70, 1], [98, 2], [99, 2], [119, 3], [120, 3]]
    product = saved["changeset"]["changes"][0]["params"]["requests"][-1]["weapon"]["exchange"]["productId"]
    assert candidate.server(SERVER_SHOP)["81"][product]["stock"] == 1
    assert candidate.server(SERVER_SHOP)["81"][product]["rewards"] == [{"type": 4, "id": int(wid), "count": 1}]
    assert candidate.server(SERVER_MAP)[product] == 81
    for logical, raw in compiled["client"].items():
        if not logical.endswith(".orderedmap"):
            continue
        before, after = codec.parse_node(baseline[logical]), codec.parse_node(raw)
        assert all(after[k] == value for k, value in before.items())
        indexed = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        for key, value in zip(indexed.keys, indexed.rows):
            if key not in before and isinstance(after[key], str):
                assert zlib.decompress(value).decode("utf-8") == after[key]
    assert app.source.view.files == baseline
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    assert "equipment-awakening-material-v1" in saved["requires"]["clientCapabilities"]


def test_weapon_set_options_and_id_discovery(workshop):
    code, choices = call(workshop, "GET", "/set-options")
    assert code == 200
    assert next(i for i in choices["materials"] if i["id"] == "1")["name"] == "测试星铁"
    assert choices["categories"]["enhancement"][0]["name"] == "羁绊"
    wid = clone(workshop)["weaponId"]
    code, saved = call(workshop, "POST", f"/{wid}/set", full_set())
    assert code == 200, saved
    request = saved["changeset"]["changes"][0]["params"]["requests"][-1]["weapon"]
    for kind, identity in (("enhancement_category", request["enhancementCategory"]["id"]),
                           ("exchange_product", request["exchange"]["productId"])):
        info = check_id(workshop.source, kind, identity, drafts_root=workshop.ops.store.root)
        assert not info["available"] and info["owners"][0]["source"] == "draft"


@pytest.mark.parametrize("edit", [
    {"enhancement": {"maxLevel": 120, "stages": [{"maxLevel": 119, "costs": []}]}},
    {"enhancement": {"maxLevel": 120, "stages": [{"maxLevel": 120, "costs": [{"itemId": "999", "amount": 1}]}]}},
    {"awakeningMaterial": "999"}, {"noSoul": "true"},
    {"exchange": {"category": {"id": "81"}, "sourceProduct": "100", "productId": "100", "itemId": "1", "amount": 1, "stock": 1}},
])
def test_weapon_set_rejection_is_atomic(workshop, edit):
    wid = clone(workshop)["weaponId"]
    before = workshop.weapons.store.load(wid)
    code, result = call(workshop, "POST", f"/{wid}/set", edit)
    assert code == 400, result
    assert workshop.weapons.store.load(wid) == before


def test_weapon_set_category_reused_and_no_options_added_by_default(workshop):
    wid = clone(workshop)["weaponId"]
    state, _ = workshop.weapons.editor.state(wid)
    assert ENH_CATEGORY not in state.client and "assets/equipment_dissolve.json" not in state.servers
    edit = {"enhancementCategory": {"code": "bond", "name": "羁绊"}}
    code, result = call(workshop, "POST", f"/{wid}/set", edit)
    assert code == 200, result
    candidate, _ = workshop.weapons.editor.state(wid)
    assert ENH_CATEGORY not in candidate.client
    assert len(candidate.table(ENH_CATEGORY)) == 1


def test_weapon_set_input_drift_blocks_replay(workshop):
    wid = clone(workshop)["weaponId"]
    code, saved = call(workshop, "POST", f"/{wid}/set", {"awakeningMaterial": "1"})
    assert code == 200, saved
    path = workshop.weapons.server_dir / AWAKENING
    document = json.loads(path.read_bytes())
    document["materialByEquipment"]["42"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="drift"):
        workshop.weapons.editor.state(wid)


def test_weapon_set_extends_curve_and_ability_endpoint_to_200(workshop):
    from wf.boss.shop_model import ENH_STATUS, ENH_ABILITY
    wid = clone(workshop)["weaponId"]
    code, result = call(workshop, "POST", f"/{wid}/set", {
        "enhancement": {"maxLevel": 200, "stages": [{"maxLevel": 200, "costs": []}]}})
    assert code == 200, result
    candidate, _ = workshop.weapons.editor.state(wid)
    assert s.parse_rows(candidate.table(ENH)[wid])[0][0] == "200"
    assert candidate.table(ENH_STATUS)[wid]["200"] == candidate.table(ENH_STATUS)[wid]["120"]
    assert all(row[2] == "200" for row in s.parse_rows(candidate.table(ENH_ABILITY)[wid]))


def test_weapon_set_pending_category_collision_and_new_exchange_category(workshop):
    first = clone(workshop)["weaponId"]
    code, result = call(workshop, "POST", f"/{first}/set", {
        "enhancementCategory": full_set()["enhancementCategory"]})
    assert code == 200, result
    second = clone(workshop)["weaponId"]
    code, result = call(workshop, "POST", f"/{second}/set", {
        "enhancementCategory": full_set()["enhancementCategory"]})
    assert code == 400 and "reserved" in result["error"]
    exchange = full_set()["exchange"]
    exchange["category"] = {"sourceCategory": "81", "code": "exclusive_shop", "name": "兑换"}
    code, result = call(workshop, "POST", f"/{second}/set", {"exchange": exchange})
    assert code == 200, result
    candidate, _ = workshop.weapons.editor.state(second)
    request = result["changeset"]["changes"][0]["params"]["requests"][-1]["weapon"]["exchange"]
    category = request["category"]["id"]
    row = s.parse_rows(candidate.table(s.SHOP_CATEGORY)[category])[0]
    assert row[:3] == ["exclusive_shop", "2", "(None)"]
    assert request["productId"] in candidate.server(SERVER_SHOP)[category]


def test_weapon_set_does_not_infer_old_awakening_keys_as_new_requirements():
    from wf.caps.requirements import infer_requirements
    before = codec.build_node({"awakening_material_42": "1", "unrelated": "old"})
    after = codec.build_node({"awakening_material_42": "1", "unrelated": "new"})
    result = infer_requirements({"member": (after, {"logical_path": CUSTOM, "root": "common"})},
                                read_raw=lambda _: before)
    assert "equipment-awakening-material-v1" not in result["clientCapabilities"]


def test_weapon_set_requirements_accept_empty_native_baseline():
    from wf.caps.weapon_requirements import weapon_requirements
    result = weapon_requirements({CUSTOM: codec.build_node({"unrelated": "text"})}, {},
                                 read_raw=lambda _: codec.build_node({}))
    assert result == {"clientCapabilities": [], "serverFeatures": []}


def test_weapon_set_no_soul_does_not_overwrite_server_only_identity(workshop):
    wid = clone(workshop)["weaponId"]
    path = workshop.weapons.server_dir / "assets/equipment_dissolve.json"
    document = json.loads(path.read_bytes())
    document[wid] = {"ability_soul_id": 77, "generate_ability_soul": True}
    path.write_text(json.dumps(document), encoding="utf-8")
    code, result = call(workshop, "POST", f"/{wid}/set", {"noSoul": True})
    assert code == 400 and "collides" in result["error"]


def test_weapon_set_existing_ladder_rejects_extra_server_only_stage(workshop):
    path = workshop.weapons.server_dir / SERVER_ENH
    document = json.loads(path.read_bytes())
    document["501000599"] = {"equipmentId":5010005, "costs":[{"id":1,"amount":9}]}
    path.write_text(json.dumps(document), encoding="utf-8")
    code, result = call(workshop, "POST", "/5010005/set", {
        "enhancement": {"maxLevel":120, "stages":[{"maxLevel":120,"costs":[]}]}})
    assert code == 400 and "stage set differs" in result["error"]
