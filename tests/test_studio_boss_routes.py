"""Boss HTTP/CLI contracts, request errors and independent draft namespaces."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from test_studio_drafts import live, _request
from wf.studio import boss, deliver_bridge, draft, drafts as D
from wf.studio.guard import TOKEN_HEADER


def body(response):
    return json.loads(response.body)


def change(quest="7"):
    return {"id": D.new_change_id(), "kind": "boss", "title": "副本草稿", "createdAt": D.now(),
            "target": {"quest": quest}, "params": {
                "requests": [{"operation": "edit", "parameters": {"level": 100}}],
                "inputs": {"client": {}, "server": {}}},
            "files": [], "pending": [], "checks": []}


def seed(store, quest="7"):
    return store.put_change(quest, f"boss_{quest}", "1.4.1", change(quest))


def headers(guard, **extra):
    return {TOKEN_HEADER: guard.token, "Content-Type": "application/json", **extra}


@pytest.mark.parametrize("payload", [
    {"operation": "edit", "parameters": {"level": 100, "restrictedElement": 4}},
    {"operation": "edit", "tiers": [{"level": 20 + n * 20} for n in range(5)]},
    {"operation": "create_shared", "sourceQuest": "hard_multi:1006/1", "name": "共同决战",
     "ids": {"event": "2100", "node": "31"}},
])
def test_boss_request_schema_accepts_supported_operations(payload):
    assert D.schema_errors(payload, "bossRequest") == []


@pytest.mark.parametrize("payload", [
    {}, {"operation": "erase"}, {"operation": "edit", "ids": {"event": "2100"}},
    {"operation": "edit", "parameters": {"level": True}},
    {"operation": "edit", "parameters": {"restrictedElement": 6}},
    {"operation": "edit", "parameters": {"hpMultiplier": 0}},
    {"operation": "edit", "tiers": [{"level": 20}] * 4},
    {"operation": "create_shared", "sourceQuest": "../../character/7"},
    {"operation": "create_shared", "tiers": [{}] * 5},
])
def test_boss_request_schema_rejects_wrong_shapes(payload):
    assert D.schema_errors(payload, "bossRequest")


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/boss"), ("HEAD", "/api/boss/7"), ("GET", "/api/boss/drafts"),
    ("GET", "/api/boss/deliveries"), ("POST", "/api/boss/drafts/7/save"),
])
def test_boss_endpoints_keep_host_guard(live, method, path):
    port, guard, _ = live
    code, data = _request(port, method, path, {} if method == "POST" else None,
                          headers(guard, Host=f"attacker.invalid:{port}"))
    assert code == 403 and guard.token.encode() not in data


@pytest.mark.parametrize("extra,token", [
    ({"Origin": "https://attacker.invalid"}, True),
    ({"Sec-Fetch-Site": "cross-site"}, True), ({}, False),
])
def test_boss_mutations_keep_origin_and_token_guards(live, extra, token):
    port, guard, app = live
    request_headers = headers(guard, **extra)
    if not token:
        request_headers.pop(TOKEN_HEADER)
    code, _ = _request(port, "POST", "/api/boss/drafts/7", {"operation": "edit"}, request_headers)
    assert code == 403 and not app.boss.store.root.exists()


@pytest.mark.parametrize("path", ["/api/boss/drafts", "/api/boss/drafts/7", "/api/boss/drafts/7?preview=true"])
def test_invalid_request_is_http_400_without_writing(live, path):
    port, guard, app = live
    code, data = _request(port, "POST", path, {"operation": "bad"}, headers(guard))
    assert code == 400 and (json.loads(data).get("error") or json.loads(data).get("checks"))
    assert not app.boss.store.root.exists()


def test_listing_source_error_is_http_400(live, monkeypatch):
    from wf.boss.reader import BossReader
    def failing(_self):
        raise ValueError("corrupt boss table")
    monkeypatch.setattr(BossReader, "list", failing)
    port, _, _ = live
    code, data = _request(port, "GET", "/api/boss")
    assert code == 400 and "corrupt boss table" in json.loads(data)["error"]


@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/api/boss/7", None), ("GET", "/api/boss/drafts", None),
    ("POST", "/api/boss/drafts/7/save", {}),
    ("POST", "/api/boss/drafts/7", {"operation": "edit", "parameters": {"level": 100}}),
])
@pytest.mark.parametrize("stored", ['["invalid"]', '{"truncated":'])
def test_corrupt_draft_shape_is_http_400(live, method, path, payload, stored):
    port, guard, app = live
    target = app.boss.store.directory("7")
    target.mkdir(parents=True)
    (target / "changeset.json").write_text(stored, encoding="utf-8")
    code, data = _request(port, method, path, payload, headers(guard))
    assert code == 400 and json.loads(data)["error"]


def test_boss_namespace_does_not_alias_character_id(live):
    port, guard, app = live
    character = app.ops.store.load_or_new("7", "character_code", "1.4.1")
    app.ops.store._write("7", character)
    boss_draft = seed(app.boss.store)
    assert app.boss.store.directory("7") == app.ops.store.root / "boss" / "7"
    code, result = _request(port, "GET", "/api/boss/drafts")
    assert code == 200 and json.loads(result)["drafts"][0]["code"] == "boss_7"
    code, _ = _request(port, "POST", "/api/boss/drafts/7/save", {}, headers(guard))
    assert code == 200 and app.ops.store.load("7") == character
    code, _ = _request(port, "POST", f"/api/boss/drafts/7/changes/{boss_draft['changes'][0]['id']}/revert",
                       {}, headers(guard))
    assert code == 200 and app.boss.store.load("7")["changes"] == []
    assert app.ops.store.load("7") == character


@pytest.mark.parametrize("action", ["load", "save", "characters"])
def test_character_document_inside_boss_directory_is_rejected(tmp_path, action):
    store = boss.BossDraftStore(tmp_path / "boss")
    document = D.DraftStore(tmp_path).load_or_new("7", "character_code", "1.4.1")
    directory = store.directory("7")
    directory.mkdir(parents=True)
    (directory / "changeset.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(D.DraftError):
        getattr(store, action)(*(() if action == "characters" else ("7",)))


def test_delivery_bridge_rejects_boss_document_in_character_store(tmp_path):
    store = D.DraftStore(tmp_path / "character")
    document = seed(boss.BossDraftStore(tmp_path / "boss"))
    store._write("7", document)
    with pytest.raises(D.DraftError, match="boss|副本|命名"):
        deliver_bridge._draft(store, "7", SimpleNamespace(version="1.4.1"))


def test_boss_store_rejects_code_name_of_a_character(tmp_path):
    store = boss.BossDraftStore(tmp_path / "boss")
    document = seed(store)
    document["code"] = "character_code"
    (store.directory("7") / "changeset.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(D.DraftError):
        store.save("7")


def test_boss_build_http_uses_existing_bridge_and_boss_store(live, tmp_path, monkeypatch):
    port, guard, app = live
    app.boss.deliveries.root = tmp_path / "deliveries" / "boss"
    view = app.source.view
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"patches": [{"version": "1.4.2", "enabled": False}]}), "utf-8")
    monkeypatch.setattr(view, "manifest", manifest, raising=False)
    monkeypatch.setattr(view, "search_dirs", [], raising=False)
    monkeypatch.setattr(view, "manifests", [], raising=False)
    monkeypatch.setattr(view, "verify", lambda: {}, raising=False)
    seen = {}
    def build(cid, **options):
        seen.update(cid=cid, **options)
        return {"ok": True, "characterId": cid,
                "from": options["from_version"], "to": options["to_version"]}
    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    code, result = _request(port, "POST", "/api/boss/drafts/7/build", {}, headers(guard))
    assert code == 200 and json.loads(result)["ok"]
    assert seen["cid"] == "7" and seen["store"] is app.boss.store
    assert isinstance(seen["store"], boss.BossDraftStore)
    assert seen["baseline_view"] is view
    assert (seen["from_version"], seen["to_version"]) == ("1.4.1", "1.4.3")
    assert seen["out"].parent == app.boss.deliveries.root
    assert app.boss.deliveries.running == {}


@pytest.mark.parametrize("boss_flag", [True, False])
def test_build_cli_boss_flag_selects_only_boss_namespace(tmp_path, monkeypatch, boss_flag):
    seen = {}
    baseline = SimpleNamespace(store=tmp_path / "baseline", base_version="1.4.0")
    def baseline_factory(args):
        seen["baseline_args"] = args
        return baseline
    monkeypatch.setattr("wf.studio.build_view.baseline_from_args", baseline_factory)
    def build(cid, **kwargs):
        seen.update(cid=cid, **kwargs)
        return {"ok": True}
    monkeypatch.setattr(deliver_bridge, "build_draft", build)
    args = draft.build_parser().parse_args([
        "--drafts", str(tmp_path / "drafts"), "build", "7", *( ["--boss"] if boss_flag else []),
        "--from", "1.4.1", "--to", "1.4.2", "--out", str(tmp_path / "delivery"),
        "--allow-unknown-client"])
    assert draft.run(args)["ok"]
    assert isinstance(seen["store"], boss.BossDraftStore) == boss_flag
    expected = tmp_path / "drafts" / "boss" if boss_flag else tmp_path / "drafts"
    assert seen["store"].root == expected
    assert seen["allow_unknown_client"] is True
    assert seen["baseline_args"] is args and seen["baseline_view"] is baseline
    assert (seen["base_store"], seen["base_version"]) == (baseline.store, baseline.base_version)


@pytest.mark.parametrize("preview", [True, False])
def test_boss_cli_edit_shares_editor_and_independent_store(tmp_path, monkeypatch, preview):
    request = {"operation": "edit", "parameters": {"level": 99}}
    filename = tmp_path / "request.json"
    filename.write_text(json.dumps(request), encoding="utf-8")
    source, seen = SimpleNamespace(version="1.4.1"), {}
    monkeypatch.setattr(draft, "_ops", lambda _args: SimpleNamespace(source=source))
    def edit(self, quest, value):
        seen.update(source=self.source, store=self.store, quest=quest, request=value)
        return {"ok": True}
    monkeypatch.setattr(boss.BossEditor, "preview" if preview else "apply", edit)
    args = draft.build_parser().parse_args(["--drafts", str(tmp_path / "drafts"), "boss", "7",
                                           "--request", str(filename), *( ["--preview"] if preview else [])])
    assert draft.run(args)["ok"] and seen["source"] is source and seen["request"] == request
    assert isinstance(seen["store"], boss.BossDraftStore)
    assert seen["store"].root == tmp_path / "drafts" / "boss"


def test_compile_dispatches_boss_payload_to_shared_bridge(monkeypatch):
    seen = {}
    def compile_boss(source, store, document, **options):
        seen.update(source=source, store=store, document=document, **options)
        return {"client": {"master/test.orderedmap": b"candidate"}, "servers": {},
                "server_before": {}, "changes": ["assertion"], "checks": []}
    monkeypatch.setattr(boss, "compile_boss", compile_boss)
    source, store, document = object(), object(), {"subjectKind": "boss"}
    result = deliver_bridge.compile_draft(source, store, document, server_dir="read-only")
    assert result == ({("common", "master/test.orderedmap"): b"candidate"}, {}, {}, ["assertion"], [])
    assert seen == {"source": source, "store": store, "document": document, "server_dir": "read-only"}
