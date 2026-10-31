"""Default mirror resolution must not depend on the author's profile."""
import json

import pytest

from wf.studio.config import server_directory


@pytest.fixture
def profile(tmp_path, monkeypatch):
    for name in ("WF_SERVER", "WF_SERVER_DIR", "WF_ROOT", "WF_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    filename = tmp_path / "local.json"
    filename.write_text(json.dumps({"wf_root": str(tmp_path), "paths": {"server": "mirror"}}))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(filename))
    return filename


def test_server_priority(profile, tmp_path, monkeypatch):
    assert server_directory() == tmp_path / "mirror"
    monkeypatch.setenv("WF_SERVER", str(tmp_path / "env"))
    assert server_directory() == tmp_path / "env"
    assert server_directory(tmp_path / "explicit") == tmp_path / "explicit"


def test_unconfigured_server_stays_none(profile):
    profile.write_text("{}")
    assert server_directory() is None


def test_draft_resolves_after_subcommand_override(profile, tmp_path, monkeypatch, capsys):
    from wf.studio import draft
    seen = []
    monkeypatch.setattr(draft, "run", lambda args: seen.append(args.server_dir) or {})
    assert draft.main(["list"]) == 0
    assert seen[-1] == tmp_path / "mirror"
    assert draft.main(["--server-dir", str(tmp_path / "explicit"), "list"]) == 0
    assert seen[-1] == tmp_path / "explicit"


def test_startup_passes_profile_mirror(profile, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wf.studio import __main__ as cli, server, source, doctor
    seen = []
    fake_source = SimpleNamespace(describe=lambda: {"version": "fixture", "zipCount": 0, "extraZips": []})
    monkeypatch.setattr(source, "build_source", lambda **kw: fake_source)
    def app(source, **kwargs):
        seen.append(kwargs["server_dir"])
        return SimpleNamespace(ops=SimpleNamespace(store=SimpleNamespace(root=tmp_path)))
    monkeypatch.setattr(server, "StudioApp", app)
    monkeypatch.setattr(server, "serve", lambda *args, **kw: SimpleNamespace(
        guard=SimpleNamespace(write_session=lambda *args: "fixture"),
        serve_forever=lambda: None, server_close=lambda: None))
    monkeypatch.setattr(doctor, "run_doctor", lambda **kw: {"counts": {"ok": 1, "warn": 0, "fail": 0}})
    monkeypatch.setattr("wf.studio.device_result.configured_screenshot_dirs", lambda *args: [])
    assert cli.main(["--no-prewarm"]) == 0
    assert seen == [tmp_path / "mirror"]
