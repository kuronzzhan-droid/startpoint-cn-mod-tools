"""Remaining review cases use isolated directories, never the author's server."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("assets", [False, True])
@pytest.mark.parametrize("environment", [False, True])
def test_rehearsal_cannot_write_global_server(tmp_path, monkeypatch, assets, environment):
    from wf.studio.rehearsal_io import save_reports
    from wf.studio.drafts import DraftError
    root = tmp_path / "server"
    (root / "assets").mkdir(parents=True)
    value = root / "assets" if assets else root
    config = tmp_path / "profile.json"
    config.write_text(json.dumps({"paths": {} if environment else {"server": str(value)}}))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    monkeypatch.delenv("WF_SERVER_DIR", raising=False)
    monkeypatch.delenv("WF_SERVER", raising=False)
    if environment:
        monkeypatch.setenv("WF_SERVER", str(value))
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    with pytest.raises(DraftError, match="禁止写入服务端"):
        save_reports(root, {"server": "local"}, "report", tmp_path / "other")
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before


@pytest.mark.parametrize("command", ["list", "schema"])
def test_offline_draft_command_does_not_resolve_bad_server(tmp_path, command):
    env = {k: v for k, v in os.environ.items() if not k.startswith("WF_")}
    config = tmp_path / "bad.json"
    config.write_text("{")
    env.update(WF_PATHS_PROFILE=str(config), WF_SERVER="relative", PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-m", "wf.studio.draft", "--drafts",
                             str(tmp_path / "drafts"), command], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["ok"]


@pytest.mark.parametrize("missing", [False, True])
def test_doctor_checks_nondefault_and_all_configured_apks(tmp_path, monkeypatch, missing):
    from wf.studio.doctor import run_doctor
    good = tmp_path / "good.apk"
    good.write_bytes(b"existence only")
    configured = {"test-merge-1008094": [str(good)]}
    if missing:
        configured["test-v34"] = [str(tmp_path / "missing.apk")]
    config = tmp_path / "profile.json"
    config.write_text(json.dumps({"client_apks": configured}))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    item = next(i for i in run_doctor(fast=True)["items"] if i["id"] == "client_apks")
    assert item["status"] == ("fail" if missing else "ok")
    assert f"缺少 {int(missing)} 个" in item["current"]


@pytest.mark.parametrize("fast", [False, True])
def test_doctor_uses_ffmpeg_override(tmp_path, monkeypatch, fast):
    from wf.studio import doctor
    executable = str(tmp_path / "configured-ffmpeg.exe")
    monkeypatch.setenv("WF_FFMPEG", executable)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: executable if name == executable else None)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="ffmpeg test", stderr="")
    monkeypatch.setattr(doctor.subprocess, "run", run)
    item = next(i for i in doctor.run_doctor(fast=fast)["items"] if i["id"] == "ffmpeg")
    assert item["status"] == "ok"
    assert calls == ([] if fast else [[executable, "-version"]])


def test_freshness_discovers_manifests_when_attribute_absent(tmp_path):
    from wf.studio.freshness import freshness
    main = tmp_path / "manifest.json"
    main.write_text('{"patches":[]}')
    extra = tmp_path / "manifest-extra.json"
    extra.write_text(json.dumps({"version": "1.4.132", "depends_on": "1.4.131",
                                "archive": "pinball-1.4.131-1.4.132-1-test.zip"}))
    view = SimpleNamespace(manifest=main, search_dirs=[tmp_path])
    assert freshness(SimpleNamespace(version="1.4.131", view=view)) == {
        "loaded": "1.4.131", "latest": "1.4.132", "stale": True}


def test_freshness_all_disabled_returns_configured_base(tmp_path):
    from wf.studio.freshness import freshness
    main = tmp_path / "manifest.json"
    main.write_text('{"patches":[{"version":"1.4.132","enabled":false}]}')
    view = SimpleNamespace(manifest=main, base_version="1.4.130")
    assert freshness(SimpleNamespace(version="1.4.130", view=view)) == {
        "loaded": "1.4.130", "latest": "1.4.130", "stale": False}
