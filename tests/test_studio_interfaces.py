"""Public route/CLI plumbing and error propagation, independent of live views."""
import json
from types import SimpleNamespace

from wf.studio.draft import build_parser, main
from wf.studio.drafts import DraftStore
from wf.studio.server import StudioApp


class Backend:
    def read(self, cid):
        return {"characterId": cid, "entries": []}

    def apply(self, cid, request):
        return {"characterId": cid, "request": request}

    def preview(self, cid, request):
        return {"checks": [{"status": "问题", "blocking": True}]}

    def row_preview(self, cid, table, key, **kwargs):
        return {"cid": cid, "table": table, "key": key, **kwargs}

    def templates(self, **kwargs):
        return kwargs


def test_ability_http_routes_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr("wf.studio.draft_commands.editor", lambda *a: Backend())
    app = StudioApp(SimpleNamespace(), drafts=DraftStore(tmp_path / "drafts"))
    prefix = "/api/drafts/139985/ability"
    assert json.loads(app.dispatch("GET", "/api/characters/139985/ability", {}).body)["characterId"] == "139985"
    request = {"operations": [{"op": "test"}]}
    assert json.loads(app.dispatch("POST", prefix, {}, request).body)["request"] == request
    assert app.dispatch("GET", prefix, {}).status == 405
    query = {"table": ["action_skill"], "key": ["7"], "row": ["0"], "level": ["2"]}
    assert json.loads(app.dispatch("GET", prefix + "/preview", query).body)["level"] == "2"
    assert app.dispatch("GET", prefix + "/preview", {"key": ["7"], "row": ["bad"]}).status == 400
    assert app.dispatch("GET", prefix + "/preview", {}).status == 400
    templates = "/api/studio/ability/templates"
    assert json.loads(app.dispatch("GET", templates, {"kind": ["424"]}).body)["kind"] == 424
    assert app.dispatch("GET", templates, {"kind": ["bad"]}).status == 400
    assert not (tmp_path / "drafts").exists()


def test_cli_preview_problem_returns_nonzero_without_writing(tmp_path, monkeypatch, capsys):
    request = tmp_path / "request.json"
    request.write_text('{"operations": []}', "utf-8")
    monkeypatch.setattr("wf.studio.draft._ops", lambda args: SimpleNamespace(source=object()))
    monkeypatch.setattr("wf.studio.draft_commands.editor", lambda *a: Backend())
    drafts = tmp_path / "drafts"
    assert main(["--drafts", str(drafts), "ability", "139985", "--request", str(request), "--preview"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert not drafts.exists()


def test_cli_server_dir_global_and_build_override(tmp_path):
    prefix = ["--server-dir", str(tmp_path / "global"), "build", "139985", "--from", "1.4.233",
              "--to", "1.4.234", "--out", str(tmp_path / "out")]
    assert build_parser().parse_args(prefix).server_dir == tmp_path / "global"
    assert build_parser().parse_args(prefix + ["--server-dir", str(tmp_path / "override")]).server_dir == tmp_path / "override"
