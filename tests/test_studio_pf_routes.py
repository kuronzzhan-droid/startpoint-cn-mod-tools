"""PF HTTP/CLI adapters, request validation and frontend-facing errors."""
import json

import pytest

from test_studio import _FakeSource
from wf.studio import draft
from wf.studio.drafts import DraftError, DraftStore, schema_errors
from wf.studio.server import StudioApp


@pytest.fixture()
def app(tmp_path):
    return StudioApp(_FakeSource(), drafts=DraftStore(tmp_path / "drafts"), screenshot_dirs=[])


def request():
    return {"key": "new_pf", "source": "special", "element": "暗", "scale": [1.0, 1.5, 2.0]}


def test_pf_http_catalog_detail_and_keys_share_backend(app, monkeypatch):
    from wf.studio import pf_actions
    seen = []

    def listing(source, query, **options):
        seen.append(("list", source, query, options))
        return {"items": [{"key": "special", "source": "bundled"}]}

    def detail(source, key, **options):
        seen.append(("detail", source, key, options))
        return {"key": key} if key == "special" else None

    monkeypatch.setattr(pf_actions, "listing", listing)
    monkeypatch.setattr(pf_actions, "detail", detail)
    monkeypatch.setattr(pf_actions, "draft_keys", lambda store, cid: {"characterId": cid, "items": []})
    response = app.dispatch("GET", "/api/studio/pf-actions", {"q": ["spec"], "clientProfile": ["demo"]})
    assert response.status == 200
    assert json.loads(response.body)["items"][0]["source"] == "bundled"
    assert seen[-1] == ("list", app.source, "spec", {"client_profile": "demo"})
    response = app.dispatch("GET", "/api/studio/pf-actions/special", {"clientProfile": ["demo"]})
    assert response.status == 200 and json.loads(response.body)["key"] == "special"
    assert seen[-1] == ("detail", app.source, "special", {"client_profile": "demo"})
    assert app.dispatch("GET", "/api/studio/pf-actions/missing", {}).status == 404
    response = app.dispatch("GET", "/api/drafts/123/pf-actions", {})
    assert json.loads(response.body) == {"characterId": "123", "items": []}


def test_pf_http_preview_and_failure_contract(app, monkeypatch):
    from wf.studio import pf_actions
    seen = []

    def clone(ops, cid, body, **options):
        seen.append((ops, cid, body, options))
        if body.get("key") == "occupied":
            raise DraftError("PF 键已占用")
        return {"ok": True, "preview": options["preview"], "key": body["key"],
                "checks": [{"level": "warn", "code": "pf.bundle", "message": "缺 APK"}]}

    monkeypatch.setattr(pf_actions, "clone", clone)
    response = app.dispatch("POST", "/api/drafts/123/pf-action",
                            {"preview": ["true"], "clientProfile": ["demo"]}, request())
    assert response.status == 200 and json.loads(response.body)["preview"] is True
    checks = json.loads(response.body)["checks"]
    assert checks[0]["status"] == "待验证" and checks[0]["blocking"] is False
    assert checks[-1]["rule"] == "pf.runtime" and checks[-1]["status"] == "未执行"
    assert seen[-1] == (app.ops, "123", request(), {"preview": True, "client_profile": "demo"})
    response = app.dispatch("POST", "/api/drafts/123/pf-action", {}, {**request(), "key": "occupied"})
    payload = json.loads(response.body)
    assert response.status == 400 and payload["ok"] is False
    assert payload["runtime"] == "未执行" and payload["characterId"] == "123"
    assert payload["checks"][0]["status"] == "问题" and payload["checks"][0]["blocking"] is True
    assert not app.ops.store.root.exists()


def test_pf_http_draft_keys_reports_corrupt_json_without_modifying_it(app):
    directory = app.ops.store.directory("123")
    directory.mkdir(parents=True)
    filename = directory / "changeset.json"
    filename.write_text("{", "utf-8")
    response = app.dispatch("GET", "/api/drafts/123/pf-actions", {})
    assert response.status == 400
    assert "PF 草稿读取失败" in json.loads(response.body)["error"]
    assert filename.read_text("utf-8") == "{"


@pytest.mark.parametrize("path,query,method", [
    ("/api/studio/pf-actions", {"q": ["a", "b"]}, "GET"),
    ("/api/studio/pf-actions/special", {"apk": ["unsafe.apk"]}, "GET"),
    ("/api/drafts/123/pf-actions", {"q": ["a"]}, "GET"),
    ("/api/drafts/123/pf-action", {"preview": ["yes"]}, "POST"),
    ("/api/drafts/123/pf-action", {"clientProfile": ["a", "b"]}, "POST"),
])
def test_pf_http_rejects_ambiguous_or_unsupported_query(app, path, query, method):
    response = app.dispatch(method, path, query, request())
    assert response.status == 400


@pytest.mark.parametrize("override", [
    {"key": "../other"}, {"key": "UPPER"}, {"element": 6}, {"element": "无"},
    {"scale": [1, 2]}, {"scale": 0}, {"scale": True}, {"scale": [1, -1, 2]},
    {"effects": {"battle/effect/demo/": "battle/effect/skill_unique/../other/"}},
    {"effects": {"battle/effect/demo/": "battle/effect/shared/"}}, {"apk": "local.apk"},
])
def test_pf_request_schema_rejects_invalid_or_unscoped_values(override):
    assert schema_errors({**request(), **override}, "pfActionCloneRequest")


def test_pf_request_schema_accepts_private_family_and_single_scale():
    spec = {**request(), "scale": 1.25, "dryRun": True,
            "effects": {"battle/effect/power_flip/sample/": "battle/effect/skill_unique/new_pf/"}}
    assert schema_errors(spec, "pfActionCloneRequest") == []


def execute(app, capsys, *arguments):
    code = draft.main(["--drafts", str(app.ops.store.root), "pf-action", *arguments])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    return code, json.loads(lines[0])


def test_pf_cli_utf8_request_overrides_and_preview(app, tmp_path, monkeypatch, capsys):
    from wf.studio import pf_actions
    monkeypatch.setattr(draft, "_ops", lambda args: app.ops)
    seen = []

    def clone(ops, cid, body, **options):
        seen.append((ops, cid, body, options))
        return {"ok": True, "preview": options["preview"], "key": body["key"]}

    monkeypatch.setattr(pf_actions, "clone", clone)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request(), ensure_ascii=False), "utf-8")
    code, payload = execute(app, capsys, "clone", "123", "--request", str(path),
                            "--scale", "2", "--element", "火", "--preview", "--client-profile", "demo")
    assert code == 0 and payload["result"]["preview"] is True
    assert seen[-1] == (app.ops, "123", {**request(), "scale": 2.0, "element": "火"},
                        {"preview": True, "client_profile": "demo", "apks": None})
    code, payload = execute(app, capsys, "clone", "123", "--request", str(path), "--scale", "1", "2")
    assert code == 1 and payload["ok"] is False and len(seen) == 1
    assert not app.ops.store.root.exists()


def test_pf_cli_catalog_detail_and_keys(app, monkeypatch, capsys):
    from wf.studio import pf_actions
    monkeypatch.setattr(draft, "_ops", lambda args: app.ops)
    monkeypatch.setattr(pf_actions, "listing", lambda source, query, **kw: {"q": query, "items": []})
    monkeypatch.setattr(pf_actions, "detail", lambda source, key, **kw: {"key": key} if key == "special" else None)
    monkeypatch.setattr(pf_actions, "draft_keys", lambda store, cid: {"characterId": cid, "items": []})
    code, payload = execute(app, capsys, "list", "--q", "spec")
    assert code == 0 and payload["result"]["q"] == "spec"
    code, payload = execute(app, capsys, "show", "special")
    assert code == 0 and payload["result"]["key"] == "special"
    code, payload = execute(app, capsys, "show", "missing")
    assert code == 1 and payload["ok"] is False
    monkeypatch.setattr(draft, "_ops", lambda args: pytest.fail("draft keys must not load a view"))
    code, payload = execute(app, capsys, "keys", "123")
    assert code == 0 and payload["result"]["characterId"] == "123"


def test_pf_http_real_synthetic_clone_preview_save_and_discovery(app, monkeypatch):
    from test_studio_pf_catalog import DSL_SUFFIX, action, paths, source
    from wf.studio.deliver_media import encode_tree
    import wf.paths
    fixture = source()
    for number, path in enumerate(paths(), 1):
        program = action(number)
        program[11][1][-1][1] = ["NotifyPowerflipEnd", 1]
        fixture.files["common", path + DSL_SUFFIX] = encode_tree(program)
    before = dict(fixture.files)
    monkeypatch.setattr(wf.paths, "profile_data", lambda: ({}, None))
    monkeypatch.setattr(app.source, "raw", fixture.raw, raising=False)
    monkeypatch.setattr(app.source, "read_root", fixture.read_root, raising=False)
    monkeypatch.setattr(app.source, "table", lambda name, **kw: {"123": [["fixture_character"]]}
                        if name == "character" else {})
    app._characters = [{"id": "123", "code": "fixture_character"}]
    listed = json.loads(app.dispatch("GET", "/api/studio/pf-actions", {}).body)
    assert listed["items"][0]["key"] == "special" and listed["bundledAvailable"] is False
    detail = app.dispatch("GET", "/api/studio/pf-actions/special", {})
    assert detail.status == 200 and len(json.loads(detail.body)["levels"]) == 3
    assert app.dispatch("GET", "/api/studio/pf-actions/missing", {}).status == 404
    preview = app.dispatch("POST", "/api/drafts/123/pf-action", {}, {**request(), "dryRun": True})
    assert preview.status == 200 and json.loads(preview.body)["preview"] is True
    assert not app.ops.store.root.exists()
    response = app.dispatch("POST", "/api/drafts/123/pf-action", {}, request())
    payload = json.loads(response.body)
    assert response.status == 200, payload
    assert payload["change"]["kind"] == "pf_action_clone"
    assert payload["change"]["params"]["reservations"] == {"power_flip_action": ["new_pf"]}
    assert payload["elementCode"] == 6 and payload["scale"] == [1.0, 1.5, 2.0]
    assert payload["levels"][2]["coefficients"][0]["terms"][0]["max"] == 6
    assert all("status" in check for check in payload["checks"])
    assert next(check for check in payload["checks"] if check["rule"] == "pf.bundle-unchecked")["status"] == "未执行"
    keys = json.loads(app.dispatch("GET", "/api/drafts/123/pf-actions", {}).body)
    assert keys["items"] == [{"key": "new_pf", "source": "special", "element": "暗",
                              "changeId": payload["change"]["id"], "reference": "new_pf", "state": "draft"}]
    duplicate = app.dispatch("POST", "/api/drafts/123/pf-action", {}, request())
    assert duplicate.status == 400
    assert app.dispatch("POST", "/api/drafts/123/save", {}, {}).status == 200
    assert app.ops.store.load("123")["savedRevision"] == 1
    assert fixture.files == before
