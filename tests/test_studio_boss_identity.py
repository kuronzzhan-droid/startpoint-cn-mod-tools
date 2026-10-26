"""Conflicting native quest IDs stay distinct through HTTP, drafts and delivery."""
import copy
import json
from types import SimpleNamespace
from urllib.parse import quote

import pytest
import wf_quest_lib as codec

from test_boss_model import csv_row, row
from test_studio_boss_checks import fixture_editor
from test_studio_boss_routes import change, headers
from test_studio_drafts import live, _request
from wf.boss import schema as s
from wf.boss.identity import safe_id
from wf.studio import draft, drafts as D, deliver_bridge
from wf.studio.boss import BossDraftStore, compile_boss
from wf.view.base149 import member

LORD, SHARED = "boss_battle:1/6/1", "hard_multi:1006/1"


def conflicting_editor(tmp_path):
    editor = fixture_editor(tmp_path)
    raw = editor.source.view
    cells = s.parse_rows(codec.parse_node(raw.files[s.QUEST_TABLES["hard_multi"]])["1006"]["1"])[0]
    cells = cells[:50] + cells[51:]
    cells[122], cells[123] = "false", "false"
    raw.files[s.QUEST_TABLES["boss_battle"]] = codec.build_node({"1": {"6": {"1": csv_row(cells)}}})
    raw.files[s.NODE] = codec.build_node({"1": {"6": row(14, {1: "Lord", 6: "81"})}})
    return editor


def seed(store, identity):
    return store.put_change(identity, f"boss_{safe_id(identity)}", "1.4.236", change(identity))


def test_conflicting_native_ids_edit_reload_compile_and_stage_independently(tmp_path):
    editor = conflicting_editor(tmp_path)
    for identity, multiplier in ((LORD, 2), (SHARED, 3)):
        applied = editor.apply(identity, {"operation": "edit", "parameters": {"hpMultiplier": multiplier}})
        assert applied["questId"] == identity
        assert applied["change"]["target"]["quest"] == identity
        saved = editor.store.save(identity)
        compiled = compile_boss(editor.source, editor.store, saved, server_dir=editor.server_dir)
        kind = identity.split(":", 1)[0]
        assert list(compiled["client"]) == [s.QUEST_TABLES[kind]]
        actual = editor.read(identity)["boss"]["quest"]
        assert actual["row"][97 if kind == "boss_battle" else 98] == str(multiplier)
        raw = editor.source.view
        raw.read_member = lambda name: next((data, "fixture") for logical, data in raw.files.items() if member(logical) == name)
        staged = ({("common", key): value for key, value in compiled["client"].items()},
                  compiled["servers"], compiled["server_before"], compiled["changes"], compiled["checks"])
        output = deliver_bridge._stage(tmp_path / safe_id(identity), saved, editor.source, staged, "1.4.237")
        document = json.loads(output.read_text("utf-8"))
        assert document["slug"] == "studio-boss-" + safe_id(identity).replace("_", "-")
        assert ":" not in document["slug"] and "/" not in document["slug"]
    assert {entry["characterId"] for entry in editor.store.characters()} == {LORD, SHARED}
    assert editor.store.directory(LORD).name == "boss_battle_1_6_1"
    assert editor.store.directory(SHARED).name == "hard_multi_1006_1"
    assert editor.read("hard_multi:1006001")["questId"] == SHARED
    with pytest.raises(D.DraftError, match="不唯一|one match"):
        editor.apply("1006001", {"operation": "edit", "parameters": {"level": 90}})
    assert not editor.store.directory("1006001").exists()


@pytest.mark.parametrize("corruption", ["identity", "code", "target"])
def test_namespaced_store_rejects_foreign_state_in_same_directory(tmp_path, corruption):
    store = BossDraftStore(tmp_path)
    saved = seed(store, LORD)
    if corruption == "identity":
        saved["characterId"] = SHARED
    elif corruption == "code":
        saved["code"] = "boss_1006001"
    else:
        saved["changes"][0]["target"]["quest"] = "1006001"
    (store.directory(LORD) / "changeset.json").write_text(json.dumps(saved), "utf-8")
    for action, args in ((store.load, (LORD,)), (store.save, (LORD,)), (store.characters, ())):
        with pytest.raises(D.DraftError, match="identity|foreign"):
            action(*args)


@pytest.mark.parametrize("identity", ["../7", "hard_multi:../../7", "hard_multi:1/2/3", "practice:1/2",
                                     "boss_battle:1/6", "hard_multi:1%2F2", "hard_multi:1\\2", "7\n"])
def test_invalid_selector_cannot_form_draft_path(tmp_path, identity):
    with pytest.raises(D.DraftError):
        BossDraftStore(tmp_path).directory(identity)


def test_schema_namespaced_id_is_only_permitted_for_boss(tmp_path):
    saved = seed(BossDraftStore(tmp_path), LORD)
    assert not D.schema_errors(saved)
    for subject in (None, "character"):
        wrong = copy.deepcopy(saved)
        wrong.pop("subjectKind") if subject is None else wrong.update(subjectKind=subject)
        assert D.schema_errors(wrong)


def test_cli_namespaced_list_show_save_revert_and_build(tmp_path, monkeypatch):
    root = tmp_path / "drafts"
    store = BossDraftStore(root / "boss")
    saved = seed(store, SHARED)
    def run(*args):
        return draft.run(draft.build_parser().parse_args(["--drafts", str(root), *args]))
    assert run("list", "--boss")["drafts"][0]["characterId"] == SHARED
    assert run("show", SHARED, "--boss")["changeset"] == saved
    assert run("save", SHARED, "--boss")["status"]["state"] == "saved"
    seen = {}
    baseline = SimpleNamespace(store=tmp_path / "baseline", base_version="1.4.131")
    def baseline_factory(args):
        seen["baseline_args"] = args
        return baseline
    monkeypatch.setattr("wf.studio.build_view.baseline_from_args", baseline_factory)
    monkeypatch.setattr(deliver_bridge, "build_draft", lambda cid, **kw: seen.update(cid=cid, **kw) or {"ok": True})
    assert run("build", SHARED, "--boss", "--from", "1.4.236", "--to", "1.4.237",
               "--out", str(tmp_path / "output"))["ok"]
    assert seen["cid"] == SHARED and seen["store"].directory(SHARED) == store.directory(SHARED)
    assert seen["baseline_view"] is baseline and seen["base_store"] == baseline.store
    assert seen["base_version"] == baseline.base_version
    assert seen["baseline_args"].cid == SHARED and seen["baseline_args"].boss
    assert run("revert", SHARED, saved["changes"][0]["id"], "--boss")["status"]["state"] == "clean"
    assert run("list")["drafts"] == []


def test_http_encoded_selectors_reach_editor_once_and_save_revert(live, monkeypatch):
    port, guard, app = live
    saved = seed(app.boss.store, SHARED)
    encoded = quote(SHARED, safe="")
    seen = []
    monkeypatch.setattr(app.boss.editor, "read", lambda quest: seen.append(quest) or {"questId": quest})
    monkeypatch.setattr(app.boss.editor, "apply", lambda quest, body: seen.append(quest) or {"ok": True})
    assert _request(port, "GET", f"/api/boss/{encoded}")[0] == 200
    assert _request(port, "POST", f"/api/boss/drafts/{encoded}", {}, headers(guard))[0] == 200
    assert seen == [SHARED, SHARED]
    assert _request(port, "POST", f"/api/boss/drafts/{encoded}/save", {}, headers(guard))[0] == 200
    assert _request(port, "POST", f"/api/boss/drafts/{encoded}/changes/{saved['changes'][0]['id']}/revert", {}, headers(guard))[0] == 200


def test_http_namespaced_build_list_detail_and_actual_root(live, tmp_path, monkeypatch):
    port, guard, app = live
    app.boss.deliveries.root = tmp_path / "deliveries" / "boss"
    seen = {}
    def build(cid, **options):
        seen.update(cid=cid, **options)
        out = options["out"]
        out.mkdir(parents=True)
        report = {"ok": True, "compat": "未确认", "compatChecks": [{"status": "待验证"}], "checks": [{"status": "满足"}]}
        (out / "build-report.json").write_text(json.dumps(report), "utf-8")
        return report
    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    encoded = quote(SHARED, safe="")
    code, payload = _request(port, "POST", f"/api/boss/drafts/{encoded}/build", {}, headers(guard))
    result = json.loads(payload)
    assert code == 200 and result["ok"] and seen["cid"] == SHARED
    assert result["name"].startswith("hard_multi_1006_1-")
    code, payload = _request(port, "GET", f"/api/boss/deliveries?cid={encoded}")
    listing = json.loads(payload)
    assert code == 200 and listing["deliveries"][0]["counts"] == {"满足": 1, "待验证": 1}
    assert listing["root"] == app.boss.deliveries.display_root()
    assert _request(port, "GET", f"/api/boss/deliveries/{result['name']}")[0] == 200
    code, payload = _request(port, "GET", "/api/boss/deliveries/defaults")
    assert code == 200 and json.loads(payload)["outRoot"] == listing["root"]
