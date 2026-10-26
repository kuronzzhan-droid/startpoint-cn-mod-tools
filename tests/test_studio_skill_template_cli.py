"""Skill template CLI shares requests and emits one UTF-8 JSON line."""
import json
import sys
from types import SimpleNamespace

import pytest

from test_studio_skill_template_routes import RecordingEditor
from test_studio_skill_template import skill_env, request as skill_request, CID, NEW_KEY  # noqa: F401
from wf.studio import draft


@pytest.fixture
def backend(monkeypatch):
    editor = RecordingEditor()
    monkeypatch.setitem(sys.modules, "wf.studio.skill_template",
                        SimpleNamespace(SkillTemplateEditor=lambda source, store, server_dir: editor))
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=object()))
    return editor


def execute(tmp_path, capsys, *arguments):
    code = draft.main(["--drafts", str(tmp_path / "drafts"), *arguments])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    return code, json.loads(lines[0])


def test_cli_catalog_detail_and_missing(tmp_path, backend, capsys):
    code, result = execute(tmp_path, capsys, "skill-templates", "list", "--q", "合成")
    assert code == 0 and result["result"]["officialOnly"] is True
    assert backend.calls[-1] == ("list", "合成")
    code, result = execute(tmp_path, capsys, "skill-templates", "detail", "synthetic")
    assert code == 0 and result["result"]["key"] == "synthetic"
    code, result = execute(tmp_path, capsys, "skill-templates", "detail", "missing")
    assert code == 1 and result["ok"] is False


def test_cli_preview_flag_and_body_preview_cannot_save(tmp_path, backend, capsys):
    path = tmp_path / "request.json"
    request = {"source": {"key": "synthetic"}, "newKey": "new_skill"}
    path.write_text(json.dumps(request), encoding="utf-8-sig")
    code, result = execute(tmp_path, capsys, "skill-template", "7", "--request", str(path), "--preview")
    assert code == 0 and result["result"]["preview"] is True
    assert backend.calls[-1] == ("preview", "7", request)
    path.write_text(json.dumps({**request, "preview": True}), encoding="utf-8")
    assert execute(tmp_path, capsys, "skill-template", "7", "--request", str(path))[0] == 0
    assert backend.calls[-1] == ("preview", "7", request)
    path.write_text(json.dumps(request), encoding="utf-8")
    assert execute(tmp_path, capsys, "skill-template", "7", "--request", str(path))[0] == 0
    assert backend.calls[-1] == ("apply", "7", request)
    assert not (tmp_path / "drafts").exists()


@pytest.mark.parametrize("specification", [[], {"preview": "false"}, {"preview": 0}])
def test_cli_invalid_request_is_one_line_error_without_editor_call(tmp_path, backend, capsys, specification):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(specification), encoding="utf-8")
    code, result = execute(tmp_path, capsys, "skill-template", "7", "--request", str(path))
    assert code == 1 and result["ok"] is False and backend.calls == []


def test_cli_real_catalog_shares_http_official_metadata(tmp_path, capsys, monkeypatch):
    from test_studio_skill_template_core import Source
    source = Source()
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=source))
    code, result = execute(tmp_path, capsys, "skill-templates", "detail", "donor")
    assert code == 0 and result["result"]["provenance"] == "official-archive"
    assert result["result"]["tiers"][0]["name"] == "技能"
    assert not (tmp_path / "drafts").exists()


def test_cli_real_editor_previews_then_saves_same_request(skill_env, tmp_path, capsys, monkeypatch):
    source, store, _, _ = skill_env
    monkeypatch.setattr(draft, "_ops", lambda args: SimpleNamespace(source=source))
    path = tmp_path / "skill-request.json"
    path.write_text(json.dumps(skill_request()), encoding="utf-8")
    code, preview = execute(tmp_path, capsys, "skill-template", CID, "--request", str(path), "--preview")
    assert code == 0 and preview["result"]["preview"] is True
    assert not store.root.exists()
    code, saved = execute(tmp_path, capsys, "skill-template", CID, "--request", str(path))
    assert code == 0 and saved["result"]["change"]["kind"] == "skill_template"
    assert store.load(CID)["changes"][0]["params"]["reservations"] == {"action_skill": [NEW_KEY]}
    assert saved["result"]["summary"] == preview["result"]["summary"]
