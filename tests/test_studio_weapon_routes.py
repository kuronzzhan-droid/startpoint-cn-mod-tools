"""Weapon HTTP guards, draft isolation, allocation and delivery replay contracts."""
import copy
import json

import pytest
import wf_quest_lib as codec

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_drafts import live, _request  # noqa: F401
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, ENH_SHOP, SERVER_ENH
from wf.studio import deliver_bridge
from wf.studio.drafts import DraftError, DraftStore
from wf.studio.guard import TOKEN_HEADER
from wf.studio.server import StudioApp
from wf.studio.source import StudioSource
from wf.studio.weapon_editor import compile_weapon
from wf.view.base149 import join, member

PREFIX = "/api/studio/weapons"


@pytest.fixture
def app(state, tmp_path):
    state.base.tip, state.base.zips = "1.4.1", []
    source = StudioSource(state.base, official_root=tmp_path / "missing-official")
    return StudioApp(source, drafts=DraftStore(tmp_path / "drafts"), server_dir=state.server_dir,
                     screenshot_dirs=[])


def call(app, method, path, body=None, query=None):
    response = app.dispatch(method, PREFIX + path, query or {}, body)
    assert response is not None
    return response.status, json.loads(response.body)


def clone(app, **extra):
    code, result = call(app, "POST", "/clone", {"sourceWeapon": "5010005", **extra})
    assert code == 200, result
    return result


def headers(guard, **extra):
    return {TOKEN_HEADER: guard.token, "Content-Type": "application/json", **extra}


@pytest.mark.parametrize("path", ["/clone", "/5010005/materials", "/drafts/5950001/save", "/drafts/5950001/build"])
@pytest.mark.parametrize("extra", [{TOKEN_HEADER: "bad"}, {"Origin": "https://evil.invalid"},
                                   {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.invalid"}])
def test_all_weapon_writes_use_existing_http_guard(live, path, extra):
    port, guard, application = live
    code, _ = _request(port, "POST", PREFIX + path, {}, headers(guard, **extra))
    assert code == 403 and not application.weapons.store.root.exists()


@pytest.mark.parametrize("path", ["", "/5010005", "/drafts", "/deliveries"])
def test_weapon_reads_keep_host_guard(live, path):
    port, guard, _ = live
    code, _ = _request(port, "GET", PREFIX + path, headers=headers(guard, Host="evil.invalid"))
    assert code == 403


def test_global_routes_and_clone_soul_details_without_a_quest(app):
    assert call(app, "GET", "", query={"q": ["5010005"], "limit": ["1"]})[1]["count"] == 1
    assert call(app, "GET", "/5010005")[1]["soulId"] == "5010005"
    assert call(app, "GET", "/9999999")[0] == 404
    created = clone(app, name="独立武器", soul_elements=[1], soulDescription="魂珠新说明")
    wid = created["weaponId"]
    code, detail = call(app, "GET", "/" + wid)
    assert code == 200 and detail["soul_item"]["row"][5] == "魂珠新说明"
    assert detail["soul_item"]["row"][12] == "1" and detail["element"] == -1
    assert detail["enhancement_chain"][0]["id"] == created["allocation"]["enhancementProducts"][0]
    assert created["checks"] == [] and detail["status"]["state"] == "dirty"
    assert app.weapons.store.directory(wid) == app.ops.store.root / "weapons" / wid
    assert app.ops.store.load(wid) is None and app.boss.store.load(wid) is None
    assert call(app, "GET", "/drafts")[1]["drafts"][0]["characterId"] == wid


def test_preview_no_write_and_inherited_warning_survives_compile(app):
    rows = codec.parse_node(app.source.view.files[ITEM])
    item = s.parse_rows(rows["5010005"])[0]
    item[12] = "1"
    rows["5010005"] = join(item)
    app.source.view.files[ITEM] = codec.build_node(rows)
    code, result = call(app, "POST", "/clone", {"sourceWeapon": "5010005"}, {"preview": ["true"]})
    assert code == 200 and result["checks"][0]["rule"] == "weapon.soul-elements-inherited"
    assert not app.weapons.store.root.exists()
    created = clone(app)
    compiled = compile_weapon(app.source, app.weapons.store, created["changeset"], server_dir=app.weapons.server_dir)
    assert compiled["checks"] == created["checks"]


def test_clone_then_materials_save_reload_compile_and_stage(app, tmp_path):
    before = dict(app.source.view.files)
    created = clone(app, soul_elements="all")
    wid, product = created["weaponId"], created["allocation"]["enhancementProducts"][0]
    code, edited = call(app, "POST", f"/{wid}/materials", {
        "stages": [{"productId": product, "costs": [{"itemId": "1", "amount": 9}]}]})
    assert code == 200 and edited["changeset"]["revision"] == 2
    assert len(edited["changeset"]["changes"]) == 1
    assert call(app, "POST", f"/drafts/{wid}/save", {})[1]["status"]["state"] == "saved"
    draft = deliver_bridge._draft(app.weapons.store, wid, app.source)
    compiled = deliver_bridge.compile_draft(app.source, app.weapons.store, draft, server_dir=app.weapons.server_dir)
    client, servers = compiled[:2]
    assert s.parse_rows(codec.parse_node(client[("common", ENH_SHOP)])[product])[0][14:16] == ["1", "9"]
    assert json.loads(servers[SERVER_ENH])[product]["costs"] == [{"id": 1, "amount": 9}]
    def read_member(name):
        for logical, data in app.source.view.files.items():
            if member(logical) == name:
                return data, "fixture"
        raise FileNotFoundError(name)
    app.source.view.read_member = read_member
    filename = deliver_bridge._stage(tmp_path / "delivery", draft, app.source, compiled, "1.4.2")
    document = json.loads(filename.read_text("utf-8"))
    assert document["id"].startswith("studio-weapon-")
    assert any(entry["logical_path"] == s.EQUIPMENT for entry in document["members"])
    assert any(entry["target"] == SERVER_ENH for entry in document["server_changes"])
    assert document["local_test_only"] is True and app.source.view.files == before


def test_existing_weapon_materials_do_not_require_clone_or_boss(app):
    code, result = call(app, "POST", "/5010005/materials", {
        "stages": [{"productId": "501000501", "costs": [{"itemId": "1", "amount": 8}]}]})
    assert code == 200 and result["weaponId"] == "5010005"
    compiled = compile_weapon(app.source, app.weapons.store, result["changeset"], server_dir=app.weapons.server_dir)
    assert set(compiled["client"]) == {ENH_SHOP}
    assert set(compiled["servers"]) == {SERVER_ENH}


@pytest.mark.parametrize("spec", [{}, {"sourceWeapon": "5010005", "soul_elements": []},
                                   {"sourceWeapon": "5010005", "id": "5010005"},
                                   {"sourceWeapon": "5010005", "extra": True}])
def test_invalid_clone_does_not_create_draft(app, spec):
    assert call(app, "POST", "/clone", spec)[0] == 400
    assert not app.weapons.store.root.exists()


def test_materials_reject_foreign_stage_and_mismatched_path_without_changing_draft(app):
    created = clone(app)
    wid = created["weaponId"]
    for body in ({"id": "5010005", "stages": []}, {"stages": [
        {"productId": "501000501", "costs": [{"itemId": "1", "amount": 7}]}]}):
        assert call(app, "POST", f"/{wid}/materials", body)[0] == 400
        assert app.weapons.store.load(wid) == created["changeset"]


def test_allocations_reserve_ids_in_both_draft_namespaces(app):
    first = clone(app)
    second = clone(app)
    assert first["weaponId"] != second["weaponId"]
    assert first["weaponId"] in app.boss.editor._reservations("7")["weapons"]
    # Use a valid persisted boss request to model another editor's allocation.
    change = copy.deepcopy(first["change"])
    spec = change["params"]["requests"][0]["weapon"]
    spec["id"], spec["enhancementProducts"] = "5950003", ["595000401"]
    change["kind"], change["target"] = "boss", {"quest": "7"}
    app.boss.store.put_change("7", "boss_7", app.source.version, change)
    third = clone(app)
    assert third["weaponId"] == "5950005"
    assert third["allocation"]["enhancementProducts"] == ["595000501"]
    assert call(app, "POST", "/clone", {"sourceWeapon": "5010005", "id": first["weaponId"]})[0] == 400


@pytest.mark.parametrize("kind", ["client", "server", "version"])
def test_drift_rejected_before_followup_and_delivery(app, kind):
    created = clone(app)
    if kind == "client":
        app.source.view.files[ITEM] = codec.build_node({})
    elif kind == "server":
        (app.weapons.server_dir / SERVER_ENH).write_text("{}", encoding="utf-8")
    else:
        app.source.view.tip = "1.4.2"
    with pytest.raises((ValueError, DraftError)):
        compile_weapon(app.source, app.weapons.store, created["changeset"], server_dir=app.weapons.server_dir)
    code, _ = call(app, "POST", f"/{created['weaponId']}/materials", {"stages": [
        {"productId": created["allocation"]["enhancementProducts"][0], "costs": [{"itemId": "1", "amount": 9}]}]})
    assert code == 400 and app.weapons.store.load(created["weaponId"]) == created["changeset"]


def test_mixed_namespace_draft_cannot_build(app):
    created = clone(app)
    app.ops.store._write(created["weaponId"], created["changeset"])
    with pytest.raises(DraftError, match="WeaponDraftStore"):
        deliver_bridge._draft(app.ops.store, created["weaponId"], app.source)


def test_weapon_build_route_uses_shared_delivery_bridge(app, tmp_path, monkeypatch):
    created = clone(app)
    app.weapons.deliveries.root = tmp_path / "deliveries" / "weapons"
    seen = {}
    def build(wid, **options):
        seen.update(wid=wid, **options)
        return {"ok": True, "characterId": wid, "from": "1.4.1", "to": "1.4.2"}
    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    code, result = call(app, "POST", f"/drafts/{created['weaponId']}/build", {})
    assert code == 200 and result["ok"]
    assert seen["store"] is app.weapons.store
    assert seen["out"].parent == app.weapons.deliveries.root


def test_revert_clears_only_weapon_change(app):
    created = clone(app)
    wid = created["weaponId"]
    code, result = call(app, "POST", f"/drafts/{wid}/changes/{created['change']['id']}/revert", {})
    assert code == 200 and result["status"]["state"] == "clean"
    assert call(app, "GET", f"/drafts/{wid}")[1]["changeset"]["changes"] == []


def test_weapon_device_result_uses_shared_schema_and_binding(app, tmp_path):
    from test_studio_device_result import make_delivery, record
    name = "5950001-1.4.251-to-1.4.252-20261019-182403"
    app.weapons.deliveries.root = tmp_path / "deliveries" / "weapons"
    make_delivery(app.weapons.deliveries.root, name=name)
    code, result = call(app, "POST", f"/drafts/5950001/deliveries/{name}/device-result", record(status="未执行"))
    assert code == 200 and result["deviceResult"]["result"]["delivery"]["kind"] == "weapon"
