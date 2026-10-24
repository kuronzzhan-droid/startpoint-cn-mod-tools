"""M6 requests and read-only sections use the guarded shared editor surface."""
import copy
import json
from types import SimpleNamespace

import pytest

from test_studio_drafts import live, _request
from test_studio_boss_checks import fixture_editor
from wf.studio import boss, draft, drafts
from wf.studio.guard import TOKEN_HEADER
from wf.studio.server import StudioApp


@pytest.mark.parametrize("payload", [
    {"operation": "terrain_replace", "terrain": "battle/terrain/harbor.amf3.deflate"},
    {"operation": "terrain_position", "layer": "0", "action": "add", "name": "new", "x": 1, "y": 2},
    {"operation": "terrain_position", "layer": "0", "action": "delete", "name": "new"},
    {"operation": "terrain_add_layer", "sourceQuest": "hard_multi:1006/1", "sourceLayer": "0"},
    {"operation": "behavior_replace", "enemyCode": "target", "slot": 1, "sourceEnemyCode": "donor", "sourceSlot": 2},
    {"operation": "behavior_parameters", "enemyCode": "target", "state": "idle", "intervalFrames": 60},
    {"operation": "shop_add", "shop": {"category": "81", "sourceProduct": "42"}},
    {"operation": "shop_edit", "shop": {"category": "81", "productId": "42", "stock": 4}},
    {"operation": "shop_delete", "shop": {"category": "81", "productId": "42"}},
    {"operation": "weapon_clone", "weapon": {"sourceWeapon": "43", "hpMultiplier": 1.2}},
    {"operation": "weapon_materials", "weapon": {"id": "43", "stages": [
        {"productId": "44", "costs": [{"itemId": "1", "amount": 10}]}]}},
    {"operation": "weapon_materials", "weapon": {"id": "43", "stages": [
        {"productId": "44", "costs": [{"itemId": "1", "amount": 10}],
         "userCost": {"type": 2, "amount": 3}}]}},
])
def test_m6_operation_schema_accepts_complete_requests(payload):
    assert not drafts.schema_errors(payload, "bossRequest")
    invalid = {**payload, "arbitraryRawColumn": 101}
    assert drafts.schema_errors(invalid, "bossRequest")


@pytest.mark.parametrize("payload", [
    {"operation": "terrain_position", "layer": "0", "action": "add", "name": "new", "x": 1},
    {"operation": "terrain_position", "layer": "0", "action": "delete", "name": "new", "x": 1},
    {"operation": "terrain_add_layer", "sourceQuest": "../../outside", "sourceLayer": "0"},
    {"operation": "behavior_replace", "enemyCode": "target", "slot": 0, "sourceEnemyCode": "donor", "sourceSlot": 2},
    {"operation": "behavior_parameters", "enemyCode": "target", "state": "idle", "intervalFrames": 0},
    {"operation": "behavior_parameters", "enemyCode": "target", "slot": 1,
     "damageMultiplier": 2, "intervalFrames": 60},
    {"operation": "shop_delete", "shop": {"category": "81", "productId": "42", "stock": 4}},
    {"operation": "shop_add", "shop": {"category": "81"}},
    {"operation": "weapon_materials", "weapon": {"id": "43", "stages": []}},
    {"operation": "weapon_clone", "weapon": {"sourceWeapon": "43", "kindColumn": 22}},
])
def test_m6_operation_schema_rejects_incomplete_or_invalid_requests(payload):
    assert drafts.schema_errors(payload, "bossRequest")


def test_terrain_section_is_readonly_and_links_exact_field_zone_layers(tmp_path):
    editor = fixture_editor(tmp_path)
    app = StudioApp(editor.source, drafts=drafts.DraftStore(tmp_path / "app"), server_dir=editor.server_dir)
    before = copy.deepcopy(editor.source.view.files)
    response = app.dispatch("GET", "/api/boss/hard_multi%3A1006%2F1/terrain", {})
    result = json.loads(response.body)
    assert response.status == 200 and result["section"] == "terrain"
    terrain = result["data"]
    assert terrain["bindings"]["zone"] == "zone"
    assert terrain["bindings"]["waves"] == [{"layer": "0", "zone_paths": [["zone", "0"]]}]
    assert len(terrain["waves"][0]["coffins"]) == 9
    assert editor.source.view.files == before
    assert not app.boss.store.root.exists()


@pytest.mark.parametrize("section", ["terrain", "shops", "weapons", "behavior", "timeline"])
def test_new_sections_keep_host_guard(live, section):
    port, guard, _ = live
    code, data = _request(port, "GET", f"/api/boss/7/{section}", headers={"Host": f"outside.invalid:{port}"})
    assert code == 403 and guard.token.encode() not in data


def test_terrain_request_keeps_mutation_guards(live):
    port, guard, app = live
    payload = {"operation": "terrain_position", "layer": "0", "action": "delete", "name": "p0"}
    code, _ = _request(port, "POST", "/api/boss/drafts/7", payload,
                       {TOKEN_HEADER: guard.token, "Content-Type": "application/json", "Origin": "https://outside.invalid"})
    assert code == 403 and not app.boss.store.root.exists()


def test_cli_section_and_http_editor_share_the_same_read_path(tmp_path, monkeypatch):
    seen = {}
    source = object()
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=source))
    def inspect(self, quest, section):
        seen.update(source=self.source, quest=quest, section=section)
        return {"runtime": "未执行"}
    monkeypatch.setattr(boss.BossEditor, "inspect", inspect)
    args = draft.build_parser().parse_args(["--drafts", str(tmp_path), "boss", "hard_multi:1006/1", "--section", "timeline"])
    assert draft.run(args) == {"runtime": "未执行"}
    assert seen == {"source": source, "quest": "hard_multi:1006/1", "section": "timeline"}
    args.preview = True
    with pytest.raises(drafts.DraftError, match="只读取"):
        draft.run(args)
