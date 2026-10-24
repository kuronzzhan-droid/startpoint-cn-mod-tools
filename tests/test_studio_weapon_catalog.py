"""Global weapon reads preserve native relations and explicitly unknown facts."""
import json

import pytest

from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL, ENH_SHOP, STATUS
from wf.boss.weapon_rules import AWAKENING
from wf.studio.source import StudioSource
from wf.studio.weapon_catalog import CUSTOM, detail, listing
from wf.studio.weapon_references import EVENT_SHOP, GACHA
from wf.view.base149 import join
from test_boss_shop_weapon import state  # noqa: F401 - shared binary/client/server fixture


@pytest.mark.parametrize("pool", [[], {"1": ["invalid"]}])
def test_invalid_server_gacha_shape_is_reported_as_input_error(state, pool):
    state.set_server_keys("assets/gacha.json", {"7": {"type": 1, "pool": pool}}, required=False)
    with pytest.raises(ValueError, match="equipment gacha"):
        detail(state, "5010005")


def test_global_list_does_not_require_any_quest_and_filters_before_limit(state):
    row = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    row[0], row[1], row[8] = "water_blade", "水剑", "5"
    state.set_leaf(s.EQUIPMENT, ["5010006"], join(row), new=True)
    state.set_server_keys("assets/equipment_element.json", {"5010006": 1})
    result = listing(state, {"q": ["水剑"], "element": ["1"], "rarity": ["5"], "limit": ["1"]})
    assert result["total"] == result["count"] == 1
    assert result["items"][0] == {
        "id": "5010006", "name": "水剑", "rarity": 5, "element": 1, "icon": "item/weapon",
        "soulId": "5010005", "isMod": None, "hasEnhancement": False, "hasAwakening": True}
    assert listing(state, {"q": ["WATER_BLADE"]})["items"][0]["id"] == "5010006"
    limited = listing(state, {"limit": ["1"]})
    assert limited["count"] == 1 and limited["total"] == 2


@pytest.mark.parametrize("query", [
    {"limit": ["0"]}, {"limit": ["2001"]}, {"limit": ["nan"]}, {"rarity": ["6"]},
    {"element": ["-2"]}, {"element": ["1", "2"]}, {"q": "not-parse-qs"},
])
def test_catalog_rejects_invalid_filters(state, query):
    with pytest.raises(ValueError):
        listing(state, query)


def test_missing_official_baseline_and_server_element_remain_unknown(state):
    result = listing(state.base, {})
    assert result["items"][0]["isMod"] is None
    assert result["items"][0]["element"] is None
    assert len(result["notes"]) == 3


def test_mod_flag_uses_official_id_membership_even_when_official_weapon_changed(state):
    baseline = state.base.files[s.EQUIPMENT]
    original = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    original[1] = "Changed official name"
    state.set_leaf(s.EQUIPMENT, ["5010005"], join(original))
    state.set_leaf(s.EQUIPMENT, ["2"], join(original), new=True)

    class OfficialSource:
        version = "fixture"
        view = state

        def _official(self):
            return baseline

        def raw(self, logical, official=False):
            return baseline if official and logical == s.EQUIPMENT else state.raw(logical)

    result = listing(OfficialSource(), {})
    assert {entry["id"]: entry["isMod"] for entry in result["items"]} == {"2": True, "5010005": False}


def test_details_join_separate_soul_id_curves_all_shop_reward_slots_and_gacha(state):
    row = s.parse_rows(state.table(s.EQUIPMENT)["5010005"])[0]
    row[10], row[8] = "700001", "5"
    state.set_leaf(s.EQUIPMENT, ["5010005"], join(row))
    state.set_leaf(ITEM, ["700001"], state.table(ITEM)["5010005"], new=True)
    state.set_leaf(SOUL, ["700001"], state.table(SOUL)["5010005"], new=True)
    shop = s.parse_rows(state.table(s.SHOP)["100"])[0]
    shop[32:35], shop[47:50] = ["0", "700001", "1"], ["4", "5010005", "2"]
    state.set_leaf(s.SHOP, ["100"], join(shop))
    state.set_leaf(STATUS, ["5010005", "10"], "300,80", new=True)
    gacha = [""] * 47
    gacha[1], gacha[13], gacha[24] = "Weapon pool", "1", "weapon_5"
    state.set_leaf(GACHA, ["990003"], join(gacha), new=True)
    # Same numeric ID in a character pool must not become a weapon relation.
    character = list(gacha)
    character[13] = "0"
    state.set_leaf(GACHA, ["990004"], join(character), new=True)
    odds = "master/gacha_odds/weapon_5.orderedmap"
    state.set_leaf(odds, ["weapon_5", "0"], "5010005,5,0,false,false,true", new=True)
    result = detail(state, "5010005")
    assert result["soul_item"]["path"] == result["ability_soul"]["path"] == ["700001"]
    assert result["curves"]["base"] == {
        "count": 3, "first": {"level": 1, "hp": 100, "attack": 20},
        "last": {"level": 10, "hp": 300, "attack": 80}}
    first = next(ref for ref in result["references"]["shops"] if ref["productId"] == "100")
    assert {entry["kind"] for entry in first["matches"]} == {"0", "4"}
    assert any(ref["table"] == ENH_SHOP for ref in result["references"]["shops"])
    assert [(ref["id"], ref["weight"]) for ref in result["references"]["gacha"]] == [("990003", "0")]
    assert result["referenceCoverage"]["serverGachaAvailable"] is False
    assert result["enhancement_chain"][0]["startLevel"] == 0


def test_studio_overlay_uses_server_draft_awakening_element_and_gacha(state, tmp_path):
    state.set_server_keys("assets/equipment_element.json", {"5010005": 2})
    state.set_server_keys(AWAKENING, {"materialByEquipment": {"5010005": 1},
                                    "rarityOverrides": {"5010005": 4}}, required=False)
    state.set_server_keys("assets/gacha.json", {
        "990003": {"type": 1, "name": "武器池", "pool": {"1": [{"id": 5010005, "odds": 0}]}},
        "990004": {"type": 0, "name": "角色池", "pool": {"1": [{"id": 5010005, "odds": 1}]}},
    }, required=False)
    state.set_leaf(CUSTOM, ["awakening_material_5010005"], "1", new=True)
    source = StudioSource(state, official_root=tmp_path / "absent-official")
    before = dict(state.servers)
    result = detail(source, "5010005", server_dir=state.server_dir)
    assert result["element"] == 2
    assert result["awakening"]["materialId"] == "1"
    assert result["awakening"]["rarityOverride"] == 4
    assert result["awakening"]["clientMaterial"]["row"] == ["1"]
    assert [entry["id"] for entry in result["references"]["gacha"]] == ["990003"]
    assert state.servers == before
    assert json.loads((state.server_dir / "assets/equipment_element.json").read_bytes())["5010005"] == -1


def test_unknown_weapon_returns_none(state):
    assert detail(state, "9999999") is None


def test_event_shop_finds_weapon_and_soul_in_first_and_last_reward_slots(state):
    row = [""] * 51
    row[0:3] = ["6", "700099", "11"]
    row[32:35], row[47:50] = ["4", "5010005", "1"], ["0", "5010005", "2"]
    state.set_leaf(EVENT_SHOP, ["9700101"], join(row), new=True)
    result = detail(state, "5010005")
    event = next(ref for ref in result["references"]["shops"] if ref["kind"] == "event_item")
    assert event["scope"] == "client"
    assert (event["eventId"], event["eventType"], event["productId"]) == ("700099", "11", "9700101")
    assert [entry["kind"] for entry in event["matches"]] == ["4", "0"]
    assert EVENT_SHOP in result["referenceCoverage"]["clientShops"]


@pytest.mark.parametrize("filename,kind", [
    ("general_shop", "general"), ("star_grain_shop", "star_grain"), ("treasure_shop", "treasure"),
])
def test_other_registered_shop_files_find_rewards_without_guessing_client_columns(state, filename, kind):
    reward = {"type": 4, "id": 5010005, "count": 1}
    soul = {"type": 0, "id": 5010005, "count": 1}
    state.set_server_keys(f"assets/{filename}.json", {
        "100001": {"rewards": [reward, soul]},
        "group": {"100002": {"rewards": [reward]}},
        "100003": {"costs": [{"id": 5010005, "amount": 1}], "rewards": [{"type": 5, "id": 5010005}]},
    }, required=False)
    result = detail(state, "5010005")
    found = [ref for ref in result["references"]["shops"] if ref["kind"] == kind]
    assert [ref["productId"] for ref in found] == ["100001", "100002"]
    assert found[0]["matches"] == [reward, soul]
    assert found[1]["path"] == ["group", "100002"]
    assert all(ref["scope"] == "server" for ref in found)
    assert result["referenceCoverage"]["serverShops"][f"assets/{filename}.json"] is True


def test_event_server_overlay_and_boss_mirror_preserve_separate_source_evidence(state):
    product = {"rewards": [{"type": 4, "id": 5010005, "count": 1}]}
    for name in ("event_item_shop", "event_item_shop_rank_p5b"):
        state.set_server_keys(f"assets/{name}.json", {"11": {"700099": {"9700101": product}}}, required=False)
    result = detail(state, "5010005")
    event = [ref for ref in result["references"]["shops"] if ref["kind"] == "event_item"]
    assert len(event) == 2
    assert {ref["source"] for ref in event} == {
        "assets/event_item_shop.json", "assets/event_item_shop_rank_p5b.json"}
    assert all(ref["eventId"] == "700099" and ref["eventType"] == "11" for ref in event)
    boss = [ref for ref in result["references"]["shops"] if ref["kind"] == "boss_coin"]
    assert {ref["scope"] for ref in boss} == {"client", "server"}
    enhancement = [ref for ref in result["references"]["shops"] if ref["kind"] == "enhancement"]
    assert {ref["scope"] for ref in enhancement} == {"client", "server"}
    assert result["referenceCoverage"]["serverShops"]["assets/general_shop.json"] is False
