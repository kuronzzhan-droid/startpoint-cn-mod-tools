"""Public discovery routing and CLI parsing, without starting an HTTP listener."""
import json
from types import SimpleNamespace

import pytest
from wf.studio.drafts import DraftStore
from wf.studio.versions import next_version


class Source:
    version = "1.4.282"
    view = SimpleNamespace(tip="1.4.282", zips=[], index={}, store=".", active=".")

    def raw(self, logical):
        return None

    def table(self, name, official=False):
        return {}

    def describe(self):
        return {"version": self.version}


@pytest.fixture
def app(tmp_path, monkeypatch):
    from wf.studio.server import StudioApp
    profile = tmp_path / "paths.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.delenv("WF_STUDIO_VIEW", raising=False)
    return StudioApp(Source(), drafts=DraftStore(tmp_path / "drafts"), screenshot_dirs=[])


def test_all_discovery_routes_dispatch_and_return_validation_errors(app, monkeypatch, tmp_path):
    from wf.studio import versions
    for endpoint, query in (("ids/check", {"kind": ["character"], "id": ["199000"]}),
                            ("ids/next", {"kind": ["weapon"], "near": ["5950001"]}),
                            ("versions/next", {})):
        result = app.dispatch("GET", "/api/studio/" + endpoint, query)
        assert result.status == 200
    for query in ({"view": ["unknown"]}, {"view": [""]}, {"view": ["a", "b"]}):
        assert app.dispatch("GET", "/api/studio/versions/next", query).status == 400
    assert app.dispatch("GET", "/api/studio/ids/check", {"kind": ["invalid"], "id": ["1"]}).status == 400
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(versions, "DEFAULT_RESERVATIONS", invalid)
    assert app.dispatch("GET", "/api/studio/versions/next", {}).status == 400
    monkeypatch.setattr(app.source, "raw", lambda _: b"broken")
    assert app.dispatch("GET", "/api/studio/ids/check", {"kind": ["character"], "id": ["1"]}).status == 400


def test_cli_versions_command_local_view_and_one_json_line(monkeypatch, capsys, tmp_path):
    from wf.studio import draft
    calls = []
    def source(**options):
        calls.append(options)
        return Source()
    monkeypatch.setattr("wf.studio.source.build_source", source)
    code = draft.main(["--drafts", str(tmp_path), "versions", "next", "--view", "test175"])
    output = capsys.readouterr().out.splitlines()
    assert code == 0 and len(output) == 1
    assert calls[0]["view_name"] == "test175"
    assert json.loads(output[0])["result"]["next"] == "1.4.283"


def test_next_version_does_not_reuse_later_manifest_declarations(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"patches": [
        {"version": "1.4.283", "enabled": False},
        {"version": "1.4.284", "enabled": True}]}), encoding="utf-8")
    source = Source()
    source.view = SimpleNamespace(manifest=manifest, search_dirs=[], manifests=[], view_name="historical")
    result = next_version(source)
    assert result["next"] == "1.4.285" and result["view"] == "historical"
    assert all(row["source"] == "manifest" for row in result["skipped"])
