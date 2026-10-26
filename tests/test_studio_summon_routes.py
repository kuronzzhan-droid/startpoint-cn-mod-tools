"""Summon authoring uses the same contracts through HTTP, CLI and schema."""
import json
from types import SimpleNamespace

import pytest

from test_studio_summon import summon_env, CID, MOTHER, NEW_BALL, request  # noqa: F401
from wf.studio import draft as draft_cli
from wf.studio.drafts import DraftError, schema_errors
from wf.studio.server import StudioApp


def application(env):
    source, store, _ = env
    return StudioApp(source, drafts=store, screenshot_dirs=[])


def test_templates_http_search_and_unsupported_method(summon_env):
    app = application(summon_env)
    response = app.dispatch("GET", "/api/studio/summon/templates", {"q": [MOTHER]})
    assert response.status == 200
    result = json.loads(response.body)
    assert result["schema"] == "wf-studio-summon-templates/1"
    assert any(item["id"] == MOTHER and item["kind"] == "character" for item in result["items"])
    assert app.dispatch("POST", "/api/studio/summon/templates", {}, {}).status == 405


@pytest.mark.parametrize("query,body", [({"preview": ["true"]}, request()), ({}, request(preview=True))])
def test_http_preview_does_not_write_or_reserve(summon_env, query, body):
    source, store, _ = summon_env
    app = application(summon_env)
    response = app.dispatch("POST", f"/api/drafts/{CID}/summon", query, body)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    assert result["preview"] is True and result["multiballId"] == NEW_BALL
    assert result["rows"] and "skillTemplate" in result
    assert store.load(CID) is None
    assert not store.directory(CID).exists()
    from wf.studio.ids import check_id
    assert check_id(source, "multiball", NEW_BALL, drafts_root=store.root)["available"]


def test_http_save_read_and_schema(summon_env):
    _, store, _ = summon_env
    app = application(summon_env)
    response = app.dispatch("POST", f"/api/drafts/{CID}/summon", {}, request())
    assert response.status == 200, response.body
    saved = json.loads(response.body)
    assert not schema_errors(saved["changeset"])
    response = app.dispatch("GET", f"/api/drafts/{CID}/summon", {})
    assert response.status == 200, response.body
    result = json.loads(response.body)
    assert result["schema"] == "wf-studio-summons/1"
    assert result["items"][0]["changeId"] == saved["change"]["id"]
    assert result["items"][0]["multiballId"] == NEW_BALL
    assert store.load(CID)["changes"][0]["params"]["reservations"]["multiball"] == [NEW_BALL]


def test_http_invalid_input_is_structured_and_does_not_write(summon_env):
    _, store, _ = summon_env
    app = application(summon_env)
    response = app.dispatch("POST", f"/api/drafts/{CID}/summon", {}, request(element=6))
    assert response.status == 400
    result = json.loads(response.body)
    assert result["ok"] is False and result["characterId"] == CID
    assert result["error"] and result["checks"][0]["blocking"]
    assert result["checks"][0]["rule"] == "summon.inputs"
    assert store.load(CID) is None


@pytest.mark.parametrize("values", [["truee"], ["TRUE"], [""], ["true", "false"]])
def test_invalid_preview_query_cannot_fall_through_to_save(summon_env, values):
    _, store, _ = summon_env
    response = application(summon_env).dispatch("POST", f"/api/drafts/{CID}/summon",
                                               {"preview": values}, request())
    assert response.status == 400 and json.loads(response.body)["checks"][0]["blocking"]
    assert store.load(CID) is None and not store.directory(CID).exists()


def test_template_query_rejects_duplicate_search(summon_env):
    response = application(summon_env).dispatch("GET", "/api/studio/summon/templates", {"q": ["one", "two"]})
    assert response.status == 400


@pytest.mark.parametrize("field", ["hp_scale", "attack_scale"])
def test_http_rejects_huge_integer_multiplier_as_400(summon_env, field):
    _, store, _ = summon_env
    response = application(summon_env).dispatch("POST", f"/api/drafts/{CID}/summon",
        {"preview": ["true"]}, request(panel={"mode": "scaled", field: 10**400}))
    assert response.status == 400
    result = json.loads(response.body)
    assert result["ok"] is False and result["checks"][0]["blocking"]
    assert not store.directory(CID).exists()


def test_cli_templates_preview_and_save_share_editor(summon_env, monkeypatch, tmp_path):
    source, store, _ = summon_env
    monkeypatch.setattr(draft_cli, "_ops", lambda args: SimpleNamespace(source=source))
    parser = draft_cli.build_parser()
    prefix = ["--drafts", str(store.root), "summon"]
    result = draft_cli.run(parser.parse_args([*prefix, "templates", "--q", MOTHER]))
    assert any(item["id"] == MOTHER for item in result["items"])
    filename = tmp_path / "summon-request.json"
    filename.write_text(json.dumps(request(), ensure_ascii=False), encoding="utf-8-sig")
    result = draft_cli.run(parser.parse_args([*prefix, CID, "--request", str(filename), "--preview"]))
    assert result["preview"] is True and store.load(CID) is None
    result = draft_cli.run(parser.parse_args([*prefix, CID, "--request", str(filename)]))
    assert result["change"]["kind"] == "summon_clone"
    read = draft_cli.run(parser.parse_args([*prefix, CID]))
    assert read["items"][0]["multiballId"] == NEW_BALL


@pytest.mark.parametrize("arguments", [[CID, "--preview"], [CID, "--q", "invalid"],
                                       ["templates", "--preview"], ["templates", "--request", "unused.json"]])
def test_cli_rejects_mixed_modes(summon_env, monkeypatch, arguments):
    source, store, _ = summon_env
    monkeypatch.setattr(draft_cli, "_ops", lambda args: SimpleNamespace(source=source))
    args = draft_cli.build_parser().parse_args(["--drafts", str(store.root), "summon", *arguments])
    with pytest.raises(DraftError):
        draft_cli.run(args)
    assert store.load(CID) is None


@pytest.mark.parametrize("override", [
    {"element": True}, {"element": 6}, {"pf_type": 5}, {"assist": "true"},
    {"lifetime": {"frames": 60, "seconds": 1}}, {"lifetime": {"frames": 2147483648}},
    {"panel": {"mode": "source", "hp_scale": 1}},
    {"panel": {"mode": "manual", "levels": [{"level": 1, "hp": 0, "attack": 1}]}},
    {"skill": {"mode": "specified"}}, {"skill": {"mode": "inherit", "key": "unexpected"}},
    {"extensions": {"flip_pf": {"enabled": True, "min_interval_frames": -1}}},
])
def test_summon_request_schema_rejects_invalid_shapes(override):
    assert schema_errors(request(**override), "summonCloneRequest")


def test_summon_request_schema_accepts_zero_interval_and_manual_zero_attack():
    spec = request(panel={"mode": "manual", "levels": [{"level": 1, "hp": 10, "attack": 0}]},
                   skill={"mode": "inherit", "level": "1"},
                   extensions={"flip_pf": {"enabled": True, "min_interval_frames": 0}})
    assert not schema_errors(spec, "summonCloneRequest")


@pytest.mark.parametrize("missing", ["spec.id", "reservations"])
def test_saved_summon_schema_requires_allocated_identity_and_reservations(summon_env, missing):
    _, _, editor = summon_env
    change = editor.apply(CID, request())["change"]
    if missing == "spec.id":
        change["params"]["spec"].pop("id")
    else:
        change["params"].pop("reservations")
    assert schema_errors(change, "change")
    assert not schema_errors({"template": {"kind": "character", "id": MOTHER}}, "summonCloneRequest")
