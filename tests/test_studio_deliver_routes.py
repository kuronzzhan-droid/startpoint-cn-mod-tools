"""编辑台 M4：生成/导出 HTTP 胶水（只调用 deliver_bridge，列出 work/studio-deliveries）。"""
from __future__ import annotations

import json

import pytest

from wf.studio import deliver_bridge
from wf.studio import drafts as D
from wf.studio.deliver_routes import DeliverRoutes, next_version
from wf.studio.operations import ACTIONS
from wf.studio.server import StudioApp


class _FakeView:
    tip = "1.4.236"
    zips = ()
    index = {}
    active = "."
    store = "."


class _FakeSource:
    view = _FakeView()
    version = "1.4.236"
    chain = None

    def describe(self):
        return {"version": self.version, "extraZips": []}

    def table(self, name, official=False):
        return {}


@pytest.fixture()
def routes(tmp_path):
    app = StudioApp(_FakeSource(), drafts=D.DraftStore(tmp_path / "drafts"))
    deliver = DeliverRoutes(app, root=tmp_path / "deliveries")
    return app, deliver


def _json(response):
    return json.loads(response.body.decode("utf-8"))


def test_next_version_and_defaults(routes):
    assert next_version("1.4.236") == "1.4.237"
    assert next_version("1.4.9") == "1.4.10"
    _, deliver = routes
    body = _json(deliver.defaults({}))
    assert (body["from"], body["to"]) == ("1.4.236", "1.4.237")


def test_actions_generate_export_wired_apply_publish_off():
    state = {a["id"]: a["enabled"] for a in ACTIONS}
    assert state == {"save": True, "generate": True, "export": True, "apply": False, "publish": False}


def test_build_success_listing_detail_and_files(routes, monkeypatch):
    app, deliver = routes
    seen = {}

    def fake_build(cid, *, from_version, to_version, out, store, provides, **options):
        seen.update(cid=cid, from_version=from_version, to_version=to_version, store=store, options=options)
        (out / "delivery").mkdir(parents=True)
        (out / "inputs").mkdir()
        (out / "delivery" / "x.zip").write_bytes(b"zip")
        (out / "delivery" / "requires.json").write_text(json.dumps({"requires": {"clientCapabilities": ["a@1"]}}), "utf-8")
        (out / "delivery" / "delivery-manifest.json").write_text(json.dumps(
            {"archives": [{"name": "x.zip", "size": 3, "sha256": "f" * 64, "members": 1, "files": ["m"]}]}), "utf-8")
        (out / "inputs" / "changeset.json").write_text(json.dumps(
            {"members": [{"root": "common", "logical_path": "master/a", "sha256": "e" * 64, "before_sha256": None}]}), "utf-8")
        report = {"ok": True, "characterId": cid, "from": from_version, "to": to_version, "draftRevision": 3,
                  "checks": [{"rule": "schema", "status": "满足", "message": "", "blocking": False}],
                  "compat": [{"rule": "capability.unknown", "status": "未执行", "message": "", "blocking": False}],
                  "prepush": {"status": "待验证", "exit_code": 0}, "deviceValidation": "未执行"}
        (out / "build-report.json").write_text(json.dumps(report, ensure_ascii=False), "utf-8")
        return report

    monkeypatch.setattr(deliver_bridge, "build_draft", fake_build)
    result = _json(deliver.build({}, {}, cid="139985"))
    assert result["ok"] and result["to"] == "1.4.237" and seen["store"] is app.ops.store
    listing = _json(deliver.listing({"cid": ["139985"]}))
    item = listing["deliveries"][0]
    assert item["name"] == result["name"] and item["draftRevision"] == 3
    assert item["counts"] == {"满足": 1, "未执行": 1}
    detail = _json(deliver.detail({}, name=item["name"]))
    assert detail["archives"][0]["members"] == 1
    assert detail["members"][0]["logical"] == "master/a"
    assert detail["requires"]["requires"]["clientCapabilities"] == ["a@1"]
    assert detail["deviceValidation"] == "未执行"
    assert deliver.file({"path": ["delivery/x.zip"]}, name=item["name"]).body == b"zip"
    with pytest.raises(D.DraftError):
        deliver.file({"path": ["../../drafts/x"]}, name=item["name"])
    with pytest.raises(D.DraftError):
        deliver.detail({}, name="..")


def test_build_failure_is_reported_not_hidden(routes, monkeypatch):
    _, deliver = routes

    def failing(cid, *, out, **kwargs):
        out.mkdir(parents=True)
        raise D.DraftError("草稿角色或基线版本与 --from 不一致")

    monkeypatch.setattr(deliver_bridge, "build_draft", failing)
    result = _json(deliver.build({}, {"from": "1.4.236", "to": "1.4.240"}, cid="139985"))
    assert result["ok"] is False and "不一致" in result["error"]
    item = _json(deliver.listing({}))["deliveries"][0]
    assert item["ok"] is False and "不一致" in item["error"]
    assert deliver.running == {}


def test_build_rejects_bad_versions(routes):
    _, deliver = routes
    with pytest.raises(D.DraftError):
        deliver.build({}, {"from": "1.4", "to": "x"}, cid="139985")


def test_routes_registered_and_post_under_drafts(routes):
    app, _ = routes
    paths = {(verb, pattern.pattern) for verb, pattern, _ in app.routes}
    assert ("POST", r"^/api/drafts/(?P<cid>\d+)/build$") in paths
    assert ("POST", r"^/api/drafts/(?P<cid>\d+)/ability/check$") in paths
    assert any(p == r"^/api/deliveries$" for _, p in paths)
