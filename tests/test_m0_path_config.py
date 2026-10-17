"""Explicit path provenance, legacy migration, and sibling-store rejection."""
import json
import os
from pathlib import Path

import pytest

import wf.paths as paths
import wf_mod_tool as core


@pytest.fixture
def config_root(monkeypatch, tmp_path):
    checkout = tmp_path / "tool"
    (checkout / "profiles").mkdir(parents=True)
    monkeypatch.setattr(paths, "REPOSITORY", checkout)
    monkeypatch.setattr(core, "profiles_file", lambda: checkout / "profiles.json")
    for key in tuple(os.environ):
        if key.startswith("WF_"):
            monkeypatch.delenv(key)
    return checkout


def modern(checkout, values):
    (checkout / "profiles/local.json").write_text(json.dumps(values), encoding="utf-8")


def legacy(checkout, **entry):
    (checkout / "profiles.json").write_text(
        json.dumps({"active": "cn", "profiles": {"cn": entry}}), encoding="utf-8")


def test_sibling_worldflipper_is_never_discovered(config_root):
    sibling = config_root.parent / "other" / "WorldFlipper/dummy/download/production/upload"
    sibling.mkdir(parents=True)
    assert core.project_root() == config_root
    assert core.find_world_upload(config_root) is None
    with pytest.raises(ValueError, match="outside the tool checkout"):
        core.find_world_upload(config_root.parent)
    with pytest.raises(FileNotFoundError, match="WF_STORE"):
        core.require_active_store(config_root.parent)
    with pytest.raises(ValueError, match="WF_SERVER"):
        core.resolve_server_dir()


def test_local_profile_and_environment_have_one_priority(config_root, monkeypatch):
    local_store, env_store, server = (config_root / key for key in ("local", "env", "server"))
    for directory in (local_store, env_store, server):
        directory.mkdir()
    modern(config_root, {"paths": {"store": str(local_store), "server": str(server)}})
    assert paths.path("store") == core.require_active_store() == local_store
    assert paths.path("server") == core.resolve_server_dir() == server
    monkeypatch.setenv("WF_STORE", str(env_store))
    assert paths.path("store") == core.require_active_store() == env_store
    assert core.resolve_target_store(None) == env_store


@pytest.mark.parametrize("key,alias", [("store", "WF_TARGET_STORE"), ("server", "WF_SERVER_DIR")])
def test_deprecated_alias_warns_and_conflicts_fail(config_root, monkeypatch, key, alias):
    first, other = config_root / "first", config_root / "other"
    first.mkdir(); other.mkdir()
    monkeypatch.setenv(alias, str(first))
    with pytest.warns(UserWarning, match=alias):
        assert paths.path(key) == first
    monkeypatch.setenv("WF_" + key.upper(), str(first))
    with pytest.warns(UserWarning, match=alias):
        assert paths.path(key) == first
    monkeypatch.setenv("WF_" + key.upper(), str(other))
    with pytest.warns(UserWarning, match=alias), pytest.raises(ValueError, match="Conflicting"):
        paths.path(key)


def test_legacy_relative_paths_use_checkout_and_warn(config_root):
    store = config_root / "upload"
    store.mkdir()
    legacy(config_root, store="upload", cdn_dir=None, server_dir=None)
    with pytest.warns(UserWarning, match="profiles.json is deprecated"):
        assert core.require_active_store() == store
    with pytest.warns(UserWarning, match="profiles.json is deprecated"):
        assert paths.path("store") == store


@pytest.mark.parametrize("source", ["profile", "environment"])
@pytest.mark.parametrize("key,field", [("store", "store"), ("server", "server_dir"), ("cdn_dir", "cdn_dir")])
def test_legacy_conflicts_are_rejected(config_root, monkeypatch, source, key, field):
    first, other = config_root / "first", config_root / "other"
    first.mkdir(); other.mkdir()
    legacy(config_root, **{field: str(first)})
    if source == "profile":
        modern(config_root, {"paths": {key: str(other)}})
    else:
        monkeypatch.setenv("WF_" + key.upper(), str(other))
    with pytest.warns(UserWarning), pytest.raises(ValueError, match="Conflicting"):
        paths.path(key)


def test_equal_legacy_and_modern_paths_are_compatible(config_root):
    store = config_root / "upload"
    store.mkdir()
    modern(config_root, {"paths": {"store": str(store)}})
    legacy(config_root, store="upload")
    with pytest.warns(UserWarning):
        assert core.require_active_store() == store


def test_legacy_version_metadata_conflicts_are_rejected(config_root):
    legacy(config_root, res_version="1.4.54")
    modern(config_root, {"active": "cn", "profiles": {"cn": {"res_version": "1.4.55"}}})
    with pytest.warns(UserWarning), pytest.raises(ValueError, match="Conflicting res_version"):
        core.resolve_profile()


def test_version_id_is_separate_from_paths_file(config_root, monkeypatch):
    profile = config_root / "other.json"
    profile.write_text(json.dumps({"wf_root": "input", "paths": {"store": "upload"}}))
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.setenv("WF_PROFILE", "cn")
    assert paths.path("store") == config_root / "input/upload"
    assert core.resolve_profile().id == "cn"
    monkeypatch.setenv("WF_PROFILE", str(profile))
    with pytest.raises(ValueError, match="WF_PATHS_PROFILE"):
        paths.path("store")


def test_modern_version_entry_uses_the_same_paths(config_root, monkeypatch):
    modern(config_root, {"wf_root": str(config_root), "active": "cn", "profiles": {
        "cn": {"store": "cn-upload", "server_dir": None},
        "global": {"store": "global-upload"},
    }})
    assert paths.path("store") == config_root / "cn-upload"
    monkeypatch.setenv("WF_PROFILE", "global")
    assert paths.path("store") == config_root / "global-upload"
    assert core.resolve_profile().store == paths.path("store")


def test_null_is_unconfigured_and_external_paths_have_no_guesses(config_root):
    modern(config_root, {"paths": {"store": None, "server": None, "cdn_dir": None}})
    assert not paths.configured("store")
    assert core.resolve_active_store() is None
    assert core.resolve_cdn_root_lax() == config_root / ".cdn/cn"
    for name in ("store", "server", "kulo", "store131", "runtimes"):
        with pytest.raises(KeyError, match="Configure path"):
            paths.path(name)
    assert paths.path("output") == config_root / "work/m0"
    assert paths.path("pathlist") == config_root / "WF_PATHLIST_recovered.txt"
    assert not (config_root / "work").exists()


@pytest.mark.parametrize("value", ["", "   ", 4, [], {}])
def test_invalid_configured_paths_are_not_treated_as_unconfigured(config_root, value):
    modern(config_root, {"paths": {"cdn_dir": value}})
    with pytest.raises(ValueError, match="non-empty path"):
        core.resolve_cdn_root_lax()


def test_missing_configured_store_fails_closed(config_root):
    modern(config_root, {"paths": {"store": str(config_root / "missing")}})
    with pytest.raises(ValueError, match="existing directory"):
        core.require_active_store()


def test_legacy_example_optional_nulls_are_valid(config_root):
    source = Path(__file__).resolve().parents[1] / "profiles.example.json"
    example = json.loads(source.read_text(encoding="utf-8"))
    (config_root / "profiles.json").write_text(json.dumps(example))
    with pytest.warns(UserWarning):
        profile = core.resolve_profile()
    assert profile.cdn_dir is None and profile.server_dir is None
    with pytest.warns(UserWarning):
        assert core.resolve_cdn_root_lax() == config_root / ".cdn/cn"
