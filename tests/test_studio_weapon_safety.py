"""Draft boundaries reject unsafe weapon rules and share all reserved IDs."""
import copy

import pytest

from test_studio_weapon_routes import app, call, clone  # noqa: F401
from test_boss_shop_weapon import state  # noqa: F401
from wf.studio import weapon_editor
from wf.studio.drafts import DraftError
from wf.studio.weapon_store import identity, reservations


@pytest.mark.parametrize("wid", ["0", "01", "21474836", "9999999999", "1/2", None, 123])
def test_store_rejects_ids_outside_shared_native_range(wid):
    with pytest.raises(DraftError):
        identity(None, wid)


@pytest.mark.parametrize("wid", ["1", "8000201", "21474835"])
def test_store_accepts_explicit_ids_outside_automatic_range(wid):
    identity(None, wid)


def inject_check(monkeypatch, entry):
    original = weapon_editor.clone_weapon

    def checked(state, spec, reserved):
        result = original(state, spec, reserved)
        state.weapon_checks.append(copy.deepcopy(entry))
        return result

    monkeypatch.setattr(weapon_editor, "clone_weapon", checked)


@pytest.mark.parametrize("entry", [
    {"rule": "weapon.test-block", "message": "blocked fixture", "blocking": True},
    {"rule": "weapon.test-error", "message": "error fixture", "level": "error"},
])
@pytest.mark.parametrize("preview", [False, True])
def test_blocking_rules_stop_preview_and_persistence(app, monkeypatch, entry, preview):
    inject_check(monkeypatch, entry)
    code, result = call(app, "POST", "/clone", {"sourceWeapon": "5010005", "soul_elements": "all"},
                        {"preview": [str(preview).lower()]})
    assert code == 400 and entry["message"] in result["error"]
    assert not app.weapons.store.root.exists()


def test_rule_info_level_survives_draft_save_and_reload(app, monkeypatch):
    inject_check(monkeypatch, {"rule": "weapon.test-info", "message": "information", "level": "info"})
    created = clone(app, soul_elements="all")
    draft = app.weapons.store.load(created["weaponId"])
    assert draft["changes"][0]["checks"] == [
        {"level": "info", "code": "weapon.test-info", "message": "information"}]


def test_compile_rechecks_blocking_rules_before_delivery(app, monkeypatch):
    created = clone(app, soul_elements="all")
    inject_check(monkeypatch, {"rule": "weapon.test-block", "message": "new blocker", "blocking": True})
    with pytest.raises(DraftError, match="new blocker"):
        weapon_editor.compile_weapon(app.source, app.weapons.store, created["changeset"],
                                     server_dir=app.weapons.server_dir)
    assert app.weapons.store.load(created["weaponId"]) == created["changeset"]


def test_material_edits_reserve_weapon_and_stage_across_both_namespaces(app):
    code, result = call(app, "POST", "/5010005/materials", {
        "stages": [{"productId": "501000501", "costs": [{"itemId": "1", "amount": 8}]}]})
    assert code == 200
    assert reservations(app.weapons.store) == {"weapons": ["5010005"],
                                              "enhancementProducts": ["501000501"]}
    assert reservations(app.weapons.store, "5010005") == {"weapons": [], "enhancementProducts": []}
    boss_reserved = app.boss.editor._reservations("7")
    assert "5010005" in boss_reserved["weapons"]
    assert "501000501" in boss_reserved["enhancementProducts"]
    change = copy.deepcopy(result["change"])
    change["kind"], change["target"] = "boss", {"quest": "7"}
    app.boss.store.put_change("7", "boss_7", app.source.version, change)
    # Exclude the standalone draft; its boss peer must still reserve the targets.
    assert app.weapons.editor.reserved("5010005") == {
        "weapons": ["5010005"], "enhancementProducts": ["501000501"]}
    assert app.boss.editor._reservations("8")["weapons"].count("5010005") == 2
