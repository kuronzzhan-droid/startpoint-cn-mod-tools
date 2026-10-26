"""Skill template adapters preserve the existing HTTP write boundary."""
import json

import pytest

from test_studio_drafts import live, _request  # noqa: F401
from test_studio_skill_template import skill_env, request as skill_request, CID, NEW_KEY  # noqa: F401
from wf.studio.drafts import DraftError
from wf.studio.guard import TOKEN_HEADER


PREFIX = "/api/studio/skill-templates"
EDIT = "/api/drafts/7/skill-template"


def headers(guard, **extra):
    return {TOKEN_HEADER: guard.token, "Content-Type": "application/json", **extra}


@pytest.mark.parametrize("extra", [
    {TOKEN_HEADER: "bad"}, {"Origin": "https://evil.invalid"},
    {"Sec-Fetch-Site": "cross-site"}, {"Host": "evil.invalid"},
])
@pytest.mark.parametrize("suffix", ["", "?preview=true"])
def test_skill_template_writes_and_previews_use_http_guard(live, extra, suffix):
    port, guard, app = live
    code, _ = _request(port, "POST", EDIT + suffix, {}, headers(guard, **extra))
    assert code == 403 and not app.ops.store.root.exists()


@pytest.mark.parametrize("path", [PREFIX, PREFIX + "/synthetic"])
def test_skill_template_reads_keep_host_guard(live, path):
    port, guard, _ = live
    assert _request(port, "GET", path, headers=headers(guard, Host="evil.invalid"))[0] == 403


class RecordingEditor:
    def __init__(self):
        self.calls = []

    def listing(self, q=""):
        self.calls.append(("list", q))
        return {"templates": [{"key": "synthetic"}], "officialOnly": True}

    def detail(self, key):
        self.calls.append(("detail", key))
        return None if key == "missing" else {"key": key, "damageNodes": []}

    def preview(self, cid, request):
        self.calls.append(("preview", cid, request))
        return {"ok": True, "preview": True, "checks": [], "runtime": "未执行"}

    def apply(self, cid, request):
        self.calls.append(("apply", cid, request))
        if not request:
            error = DraftError("合成输入缺少 source")
            error.checks = [{"rule": "skill-template.synthetic", "status": "问题",
                             "message": "合成规则", "blocking": True}]
            raise error
        return {"ok": True, "preview": False, "checks": [], "runtime": "未执行"}


def test_skill_template_route_contract_and_preview_safety(live, monkeypatch):
    port, guard, app = live
    backend = RecordingEditor()
    monkeypatch.setattr(app.skill_templates, "editor", lambda: backend)
    code, raw = _request(port, "GET", PREFIX + "?q=synthetic")
    assert code == 200 and json.loads(raw)["officialOnly"] is True
    assert backend.calls[-1] == ("list", "synthetic")
    assert _request(port, "GET", PREFIX + "/missing")[0] == 404
    assert _request(port, "GET", PREFIX + "/synthetic")[0] == 200
    request = {"source": {"key": "synthetic"}, "newKey": "new_skill"}
    for suffix, body in (("?preview=true", request), ("", {**request, "preview": True}),
                         ("?preview=false", {**request, "preview": True})):
        code, raw = _request(port, "POST", EDIT + suffix, body, headers(guard))
        assert code == 200 and json.loads(raw)["preview"] is True
        assert backend.calls[-1] == ("preview", "7", request)
    code, raw = _request(port, "POST", EDIT, request, headers(guard))
    assert code == 200 and json.loads(raw)["preview"] is False
    assert backend.calls[-1] == ("apply", "7", request)
    assert _request(port, "GET", EDIT)[0] == 405
    assert not app.ops.store.root.exists()


@pytest.mark.parametrize("suffix,body", [("?preview=1", {}), ("", {"preview": "false"}),
                                        ("", {"preview": 1})])
def test_skill_template_invalid_preview_does_not_call_editor(live, monkeypatch, suffix, body):
    port, guard, app = live
    backend = RecordingEditor()
    monkeypatch.setattr(app.skill_templates, "editor", lambda: backend)
    code, raw = _request(port, "POST", EDIT + suffix, body, headers(guard))
    result = json.loads(raw)
    assert code == 400 and result["ok"] is False and result["checks"][0]["blocking"] is True
    assert backend.calls == []


def test_skill_template_rejections_preserve_five_state_checks(live, monkeypatch):
    port, guard, app = live
    monkeypatch.setattr(app.skill_templates, "editor", RecordingEditor)
    code, raw = _request(port, "POST", EDIT, {}, headers(guard))
    result = json.loads(raw)
    assert code == 400 and result["characterId"] == "7" and result["runtime"] == "未执行"
    assert result["checks"][0]["rule"] == "skill-template.inputs"
    assert result["checks"][1]["rule"] == "skill-template.synthetic"


@pytest.mark.parametrize("path", [PREFIX, PREFIX + "/synthetic"])
def test_skill_template_read_errors_are_bad_requests(live, monkeypatch, path):
    port, _, app = live
    def unavailable():
        raise ValueError("官方基线不可用")
    monkeypatch.setattr(app.skill_templates, "editor", unavailable)
    code, raw = _request(port, "GET", path)
    assert code == 400 and json.loads(raw)["error"] == "官方基线不可用"


def test_skill_template_real_catalog_preserves_official_provenance(live):
    from test_studio_skill_template_core import Source
    port, _, app = live
    app.source = Source()
    code, raw = _request(port, "GET", PREFIX + "?q=donor")
    result = json.loads(raw)
    assert code == 200 and result["provenance"] == "official-archive"
    assert result["templates"][0]["names"] == ["技能"]
    code, raw = _request(port, "GET", PREFIX + "/donor")
    detail = json.loads(raw)
    assert code == 200 and detail["tiers"][0]["name"] == "技能"
    assert detail["tiers"][0]["damageNodes"][0]["coefficient"] == [{"min": 2, "max": 3}]
    assert detail["effects"][0]["previewUrl"] is None
    assert _request(port, "GET", PREFIX + "/mod_only")[0] == 404
    assert not app.ops.store.root.exists()


@pytest.mark.parametrize("path", [PREFIX, PREFIX + "/donor"])
def test_skill_template_missing_official_baseline_is_400(live, path):
    from test_studio_skill_template_core import Source
    port, _, app = live
    app.source = Source()
    app.source.official["skill"] = {}
    code, raw = _request(port, "GET", path)
    assert code == 400 and "官方" in json.loads(raw)["error"]


def test_skill_template_real_editor_previews_then_saves_through_http_routes(skill_env):
    from wf.studio.server import StudioApp
    source, store, _, _ = skill_env
    app = StudioApp(source, drafts=store, screenshot_dirs=[])
    path = f"/api/drafts/{CID}/skill-template"
    response = app.dispatch("POST", path, {"preview": ["true"]}, skill_request())
    preview = json.loads(response.body)
    assert response.status == 200 and preview["preview"] is True and preview["buildable"]
    assert preview["reservations"] == {"action_skill": [NEW_KEY]}
    assert all({"rule", "status", "message", "blocking"} <= check.keys() for check in preview["checks"])
    assert not store.root.exists()
    response = app.dispatch("POST", path, {}, skill_request())
    saved = json.loads(response.body)
    assert response.status == 200 and saved["preview"] is False
    assert saved["change"]["kind"] == "skill_template"
    assert store.load(CID)["changes"][0]["params"]["reservations"] == {"action_skill": [NEW_KEY]}
    assert saved["summary"] == preview["summary"]
