import json
import os
from types import SimpleNamespace

import pytest

from wf.studio import doctor
from wf.studio.frontend_build import build_state


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith("WF_"):
            monkeypatch.delenv(key)
    config = tmp_path / "local.json"
    config.write_text("{}")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    monkeypatch.setattr(doctor, "REPOSITORY", tmp_path)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    monkeypatch.setattr("wf.caps.profiles.resolve_client", lambda: (tmp_path / "provides.json", "fixture"))
    return tmp_path, config


def test_missing_inputs_and_optional_scipy(isolated):
    report = doctor.run_doctor()
    items = {row["id"]: row for row in report["items"]}
    assert not report["ok"] and report["counts"]["fail"] > 0
    assert items["dependency.scipy"]["status"] == "warn"
    assert items["dependency.numpy"]["status"] == "fail"
    assert items["client_apks"]["status"] == "fail"
    assert items["server"]["status"] == "fail"
    assert all(row["current"] and row["fix"] for row in items.values())


def test_malformed_config_keeps_all_checks(isolated):
    _, config = isolated
    config.write_text("{")
    report = doctor.run_doctor(fast=True)
    assert report["counts"]["fail"] > 1
    assert report["items"][-1]["id"] == "frontend"


def test_fast_http_never_spawns_or_scans(isolated, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("fast doctor must not execute processes or scan ZIP trees")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: name)
    monkeypatch.setattr(doctor.subprocess, "run", forbidden)
    monkeypatch.setattr("wf.studio.doctor_data.chain_check", forbidden)
    from wf.studio.server import StudioApp
    app = StudioApp(SimpleNamespace())
    response = app.dispatch("GET", "/api/studio/doctor", {})
    assert response.status == 200 and json.loads(response.body)["mode"] == "fast"


def test_cli_exit_code_and_json(isolated, capsys, monkeypatch):
    from wf.studio.__main__ import main
    assert main(["doctor", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["counts"]["fail"]
    monkeypatch.setattr(doctor, "run_doctor", lambda: {"ok": True})
    assert main(["doctor", "--json"]) == 0


def test_frontend_age_includes_source_and_lockfile(tmp_path):
    frontend = tmp_path / "studio"
    (frontend / "src").mkdir(parents=True)
    assert build_state(tmp_path)["stale"]
    (frontend / "dist").mkdir()
    index = frontend / "dist/index.html"
    index.write_text("built")
    os.utime(index, (100, 100))
    src = frontend / "src/a.ts"
    src.write_text("source")
    os.utime(src, (90, 90))
    assert not build_state(tmp_path)["stale"]
    lock = frontend / "package-lock.json"
    lock.write_text("{}")
    os.utime(lock, (110, 110))
    assert build_state(tmp_path)["stale"]


def test_chain_counts_missing_parts(isolated):
    root, config = isolated
    (root / "store").mkdir()
    manifest = root / "manifest.json"
    archive = "pinball-1.4.131-1.4.132-1-fixture.zip"
    manifest.write_text(json.dumps({"patches": [{"version": "1.4.132", "depends_on": "1.4.131",
        "archive": archive, "enabled": True}]}))
    config.write_text(json.dumps({"wf_root": str(root), "default_view": "fixture", "views": {
        "fixture": {"store": "store", "manifest": "manifest.json", "zip_dirs": ["."]}}}))
    from wf.studio.doctor_data import chain_check
    assert chain_check()[0] == "fail" and "缺 1 个" in chain_check()[1]
    (root / archive).write_bytes(b"existence check only")
    assert chain_check()[0] == "ok" and "缺 0 个" in chain_check()[1]
