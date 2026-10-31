"""Regression gates for the usable-editor review; synthetic tests need no APK."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from wf.studio import doctor
from wf.studio.frontend_build import build_state


@pytest.mark.parametrize("bad", ["{", None, {"paths": {"server": "relative"}}])
def test_startup_config_error_prints_doctor_summary(tmp_path, bad):
    config = tmp_path / "profile.json"
    if bad is not None:
        config.write_text(bad if isinstance(bad, str) else json.dumps(bad), "utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("WF_")}
    env.update(WF_PATHS_PROFILE=str(config), PYTHONIOENCODING="utf-8")
    if isinstance(bad, dict):
        env["WF_SERVER"] = "relative"
    result = subprocess.run([sys.executable, "-m", "wf.studio", "--no-prewarm"],
                            env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 1
    assert "编辑台体检" in result.stdout and "启动配置错误" in result.stderr
    assert "Traceback" not in result.stderr


def test_delivery_import_needs_no_publish_cdn(tmp_path):
    server = tmp_path / "server"
    (server / "assets/cdndata").mkdir(parents=True)
    config = tmp_path / "profile.json"
    config.write_text(json.dumps({"paths": {"server": str(server)}}), "utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("WF_")}
    env["WF_PATHS_PROFILE"] = str(config)
    result = subprocess.run([sys.executable, "-c",
        "import wf.studio.deliver_bridge; from wf.tools.release import publish_guard; "
        "publish_guard.chain_latest_index()"], env=env, capture_output=True)
    # Import succeeds, but an actual legacy publish lookup still validates CDN.
    assert result.returncode != 0
    assert b"chain_latest_index" in result.stderr
    assert b"deliver_bridge.py" not in result.stderr


@pytest.mark.parametrize("chain,status", [(None, "warn"), (SimpleNamespace(), "fail"),
                                         (SimpleNamespace(missing=[]), "ok")])
def test_fast_doctor_chain_errors_are_http_results(chain, status, tmp_path, monkeypatch):
    config = tmp_path / "profile.json"
    config.write_text("{}")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    from wf.studio.server import StudioApp
    response = StudioApp(SimpleNamespace(chain=chain)).dispatch("GET", "/api/studio/doctor", {})
    assert response.status == 200
    items = {x["id"]: x for x in json.loads(response.body)["items"]}
    assert items["patch_chain"]["status"] == status


@pytest.mark.parametrize("named", [False, True])
def test_doctor_uses_effective_view_store_and_zip_dirs(tmp_path, monkeypatch, named):
    store, zips = tmp_path / "store", tmp_path / "zips"
    store.mkdir(); zips.mkdir()
    name = "pinball-1.4.131-1.4.132-1-fixture.zip"
    (zips / name).write_bytes(b"existence only")
    (tmp_path / "manifest.json").write_text(json.dumps({"patches": [
        {"version": "1.4.132", "depends_on": "1.4.131", "archive": name}]}))
    view = {"store": "store", "manifest": "manifest.json", "zip_dirs": ["zips"]}
    data = {"wf_root": str(tmp_path)}
    data.update({"default_view": "test", "views": {"test": view}} if named else {"view": view})
    config = tmp_path / "profile.json"; config.write_text(json.dumps(data))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    monkeypatch.delenv("WF_STUDIO_VIEW", raising=False)
    items = {x["id"]: x for x in doctor.run_doctor()["items"]}
    assert items["store131"]["status"] == items["patch_chain"]["status"] == "ok"
    loaded = tmp_path / "loaded"; loaded.mkdir()
    store.rmdir()
    source = SimpleNamespace(view=SimpleNamespace(store=loaded))
    items = {x["id"]: x for x in doctor.run_doctor(fast=True, source=source)["items"]}
    assert items["store131"]["status"] == "ok"


def test_doctor_rejects_empty_server_and_accepts_checkout(tmp_path, monkeypatch):
    config = tmp_path / "profile.json"; config.write_text("{}")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    def status():
        return next(x["status"] for x in doctor.run_doctor(fast=True, server_dir=tmp_path)["items"]
                    if x["id"] == "server")
    assert status() == "fail"
    (tmp_path / "assets/cdndata").mkdir(parents=True)
    assert status() == "ok"


def test_external_static_artifact_does_not_need_sources(tmp_path):
    static = tmp_path / "external"; static.mkdir()
    (static / "index.html").write_text("built")
    assert build_state(tmp_path, static)["built"]
    assert not build_state(tmp_path, static)["stale"]
    (tmp_path / "studio/src").mkdir(parents=True)
    (tmp_path / "studio/src/new.ts").write_text("newer unrelated source")
    assert not build_state(tmp_path, static)["stale"]


def test_doctor_legacy_chain_uses_same_zip_priority_as_startup(tmp_path, monkeypatch):
    from wf.studio.doctor_data import chain_check
    store, old, current = [tmp_path / name for name in ("store", "old", "current")]
    for p in (store, old, current):
        p.mkdir()
    archive = "pinball-1.4.131-1.4.132-1-test.zip"
    (current / archive).write_bytes(b"existence only")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"patches": [{"version": "1.4.132", "depends_on": "1.4.131",
                                                "archive": archive}]}))
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"wf_root": str(tmp_path), "view": {"store": "store", "zip_dirs": ["old"]}}))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.delenv("WF_STUDIO_VIEW", raising=False)
    monkeypatch.setattr("wf.studio.source.default_chain_settings", lambda: (manifest, [current]))
    assert chain_check()[0] == "ok"
