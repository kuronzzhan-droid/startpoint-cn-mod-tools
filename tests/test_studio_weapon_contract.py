"""Frontend-facing weapon draft metadata and five-state rejection contracts."""
import copy

import pytest

from test_boss_shop_weapon import state  # noqa: F401
from test_studio_weapon_routes import app, call, clone  # noqa: F401
from wf.boss import schema as s
from wf.rules.catalog import STATES, result
from wf.studio import weapon_editor


def test_draft_summaries_name_new_and_existing_weapons_without_replay(app, monkeypatch):
    base_name = call(app, "GET", "/5010005")[1]["name"]
    named = clone(app, name="新武器名称")
    inherited = clone(app)
    code, _ = call(app, "POST", "/5010005/materials", {
        "stages": [{"productId": "501000501", "costs": [{"itemId": "1", "amount": 8}]}]})
    assert code == 200

    def no_replay(*args, **kwargs):
        pytest.fail("draft discovery must not require candidate replay")

    monkeypatch.setattr(app.weapons.editor, "state", no_replay)
    code, document = call(app, "GET", "/drafts")
    assert code == 200 and document["subjectKind"] == "weapon"
    entries = {entry["characterId"]: entry for entry in document["drafts"]}
    for wid, name, is_new in [(named["weaponId"], "新武器名称", True),
                              (inherited["weaponId"], base_name, True),
                              ("5010005", base_name, False)]:
        entry = entries[wid]
        assert entry["weaponId"] == wid
        assert entry["name"] == name and entry["isNew"] is is_new
        assert entry["code"] == f"weapon_{wid}" and entry["changes"] == 1
        assert "updatedAt" in entry and entry["savedAt"] is None


def test_reverted_clone_summary_does_not_invent_a_base_weapon(app):
    created = clone(app, name="已撤销武器")
    wid = created["weaponId"]
    assert call(app, "POST", f"/drafts/{wid}/changes/{created['change']['id']}/revert", {})[0] == 200
    entry = call(app, "GET", "/drafts")[1]["drafts"][0]
    assert entry["isNew"] is False and entry["name"] is None and entry["changes"] == 0


def test_named_clone_summary_survives_unavailable_source_item(app):
    created = clone(app, name="保留草稿名")
    # Listing metadata is not replay/validation; a removed source must not hide it.
    app.source.view.files.pop(s.EQUIPMENT)
    entry = call(app, "GET", "/drafts")[1]["drafts"][0]
    assert entry["weaponId"] == created["weaponId"]
    assert entry["name"] == "保留草稿名" and entry["isNew"] is True


def test_detail_draft_status_alias_preserves_curves_and_saved_states(app):
    original = call(app, "GET", "/5010005")[1]
    assert original["draft_status"] == original["status"]
    assert original["draft_status"]["state"] == "clean"
    assert original["base_status"] and isinstance(original["base_status"], list)
    created = clone(app)
    wid = created["weaponId"]
    dirty = call(app, "GET", "/" + wid)[1]
    assert dirty["draft_status"] == dirty["status"]
    assert dirty["draft_status"]["state"] == "dirty"
    assert [(point["level"], point["row"]) for point in dirty["base_status"]] == [
        (point["level"], point["row"]) for point in original["base_status"]]
    assert call(app, "POST", f"/drafts/{wid}/save", {})[0] == 200
    saved = call(app, "GET", "/" + wid)[1]
    assert saved["draft_status"] == saved["status"]
    assert saved["draft_status"]["state"] == "saved"
    assert saved["base_status"] == dirty["base_status"]


@pytest.mark.parametrize("preview", [True, False])
@pytest.mark.parametrize("path,body", [
    ("/clone", {}),
    ("/clone", {"sourceWeapon": "5010005", "id": "5010005"}),
    ("/5010005/materials", {"id": "5950001", "stages": []}),
    ("/5010005/materials", {"stages": [
        {"productId": "501000501", "costs": [{"itemId": "9999999", "amount": 1}]}]}),
])
def test_input_failures_return_blocking_five_state_checks(app, preview, path, body):
    code, rejected = call(app, "POST", path, body, {"preview": [str(preview).lower()]})
    assert code == 400 and rejected["ok"] is False
    assert rejected["subjectKind"] == "weapon" and rejected["runtime"] == "未执行"
    check = rejected["checks"][0]
    assert check["rule"] == "weapon.inputs" and check["status"] == "问题"
    assert check["blocking"] is True and check["message"] == rejected["error"]
    assert not app.weapons.store.root.exists()


@pytest.mark.parametrize("preview", [True, False])
def test_rule_rejection_preserves_every_five_state_result_and_allocation(app, monkeypatch, preview):
    checks = [result("weapon.test-" + str(index), state, "规则 " + state,
                     blocking=state == "问题", evidence={"source": "fixture"})
              for index, state in enumerate(STATES)]
    original = weapon_editor.clone_weapon

    def checked(state, spec, reserved):
        outcome = original(state, spec, reserved)
        state.weapon_checks.extend(copy.deepcopy(checks))
        return outcome

    monkeypatch.setattr(weapon_editor, "clone_weapon", checked)
    code, rejected = call(app, "POST", "/clone", {"sourceWeapon": "5010005", "soul_elements": "all"},
                          {"preview": [str(preview).lower()]})
    assert code == 400 and rejected["ok"] is False
    assert rejected["checks"][1:] == checks
    assert rejected["allocation"]["id"] == rejected["weaponId"] == "5950001"
    assert not app.weapons.store.root.exists()


def test_failed_material_preview_keeps_existing_draft_unchanged(app):
    created = clone(app)
    wid = created["weaponId"]
    code, rejected = call(app, "POST", f"/{wid}/materials", {"stages": [
        {"productId": "501000501", "costs": [{"itemId": "1", "amount": 7}]}]},
                          {"preview": ["true"]})
    assert code == 400 and rejected["checks"][0]["blocking"] is True
    assert app.weapons.store.load(wid) == created["changeset"]
