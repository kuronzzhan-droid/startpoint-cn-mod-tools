"""Studio sources retain both manifest locks and explicit machine profiles."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

from wf.studio.source import StudioSource, default_chain_settings


def test_chain_settings_use_public_profile_and_environment(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "wf_root": str(tmp_path),
        "paths": {"studio_chain_manifest": "chain.json"},
        "studio_zip_dirs": ["first", "missing"],
    }), encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    for variable in ("WF_ROOT", "WF_PROFILE", "WF_STUDIO_CHAIN_MANIFEST", "WF_STUDIO_ZIP_DIRS"):
        monkeypatch.delenv(variable, raising=False)

    assert default_chain_settings() == (tmp_path / "chain.json", [first])
    monkeypatch.setenv("WF_STUDIO_CHAIN_MANIFEST", str(tmp_path / "override.json"))
    monkeypatch.setenv("WF_STUDIO_ZIP_DIRS", os.pathsep.join(map(str, (second, first))))
    assert default_chain_settings() == (tmp_path / "override.json", [second, first])


def test_default_dirs_include_reorganized_releases(tmp_path, monkeypatch):
    legacy, release = tmp_path / "rel254", tmp_path / "outputs/releases/rel-1.4.265"
    for directory in (legacy, release / "shipped", tmp_path / "out"):
        directory.mkdir(parents=True)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"wf_root": str(tmp_path)}), encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    for variable in ("WF_ROOT", "WF_PROFILE", "WF_STUDIO_CHAIN_MANIFEST", "WF_STUDIO_ZIP_DIRS"):
        monkeypatch.delenv(variable, raising=False)

    assert default_chain_settings()[1] == [legacy, release, release / "shipped", tmp_path / "out"]


def test_manifest_version_stays_locked():
    source = StudioSource(SimpleNamespace(tip="1.4.233", zips=()))
    assert source.version == "1.4.233"


def test_historical_version_includes_extra_archives():
    view = SimpleNamespace(tip=206, zips=("pinball-1.4.232-1.4.233-1-demo.zip",))
    assert StudioSource(view).version == "1.4.233"
