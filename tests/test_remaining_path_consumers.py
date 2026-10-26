"""Actual consumers keep tool outputs separate from configured server data."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import wf.paths as paths
import wf_mod_tool as core
import wf_character_flow as flow
import wf_chain_squash as squash
import wf_pack_consolidate as consolidate
import wf_enhancement_policy as policy
import wf_enhancement_switch as switch
import wf_share_variant as variant
import wf_offline_store as offline_store
import wf_offline_toolchain as toolchain
import wf_rogue_reroll as reroll
import wf_story_export as story


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    checkout = tmp_path / "tool"
    (checkout / "profiles").mkdir(parents=True)
    monkeypatch.setattr(paths, "REPOSITORY", checkout)
    monkeypatch.setattr(core, "profiles_file", lambda: checkout / "profiles.json")
    for key in tuple(os.environ):
        if key.startswith("WF_"):
            monkeypatch.delenv(key)
    return checkout


@pytest.fixture
def configured(isolated, monkeypatch):
    server = isolated.parent / "configured-server"
    cdndata = server / "assets" / "cdndata"
    cdndata.mkdir(parents=True)
    cdn = server / ".cdn" / "cn"
    (cdn / "archive-common-diff").mkdir(parents=True)
    monkeypatch.setenv("WF_SERVER", str(server))
    return server, cdn, cdndata


def test_cdndata_uses_explicit_source_then_configured_server(configured, monkeypatch, tmp_path):
    _, _, mirror = configured
    assert core.resolve_cdndata_dir() == mirror
    explicit = tmp_path / "separate-cdndata"
    explicit.mkdir()
    monkeypatch.setenv("WF_CDNDATA", str(explicit))
    assert core.resolve_cdndata_dir() == explicit
    monkeypatch.setenv("WF_CDNDATA", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="cdndata"):
        core.resolve_cdndata_dir()


def test_cdndata_does_not_assume_checkout_or_sibling_assets(isolated):
    (isolated / "assets" / "cdndata").mkdir(parents=True)
    (isolated.parent / "assets" / "cdndata").mkdir(parents=True)
    with pytest.raises(core.ServerDirNotConfiguredError):
        core.resolve_cdndata_dir()


@pytest.mark.parametrize("resolve", [
    lambda: squash._resolve_dirs(SimpleNamespace(cdn=None, repo_root=None)),
    consolidate._resolve_dirs,
    lambda: policy._resolve_cdn(None),
    variant._default_cdn,
    flow._live_cdn_root,
])
def test_live_operations_reject_missing_config(isolated, resolve):
    with pytest.raises((ValueError, FileNotFoundError)):
        resolve()


def test_chain_and_pack_roots_are_configured_server(configured):
    server, cdn, _ = configured
    assert consolidate._resolve_dirs() == (cdn, server)
    assert squash._resolve_dirs(SimpleNamespace(cdn=None, repo_root=None)) == (cdn, server)
    assert policy._resolve_cdn(None) == variant._default_cdn() == flow._live_cdn_root() == cdn


def test_explicit_chain_roots_preserve_offline_api(isolated, tmp_path):
    server = tmp_path / "explicit"
    cdn = server / ".cdn" / "cn"
    (cdn / "archive-common-diff").mkdir(parents=True)
    assert consolidate._resolve_dirs(repo_root=str(server)) == (cdn, server)
    assert squash._resolve_dirs(SimpleNamespace(cdn=None, repo_root=str(server))) == (cdn, server)
    assert consolidate._resolve_dirs(cdn=str(cdn), repo_root=str(server)) == (cdn, server)


def test_switch_uses_environment_store_without_legacy_profiles(isolated, monkeypatch):
    store, cdn = isolated / "upload", isolated / "cdn"
    store.mkdir(); cdn.mkdir()
    monkeypatch.setenv("WF_STORE", str(store))
    context = switch.resolve_context(cdn=cdn)
    assert context.store == store
    assert context.repo == Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module_name", [
    "wf_all_analysis", "wf_fire_analysis", "wf_unique_mech",
    "wf_balance_patch", "wf_balance_patch_v2",
])
def test_analysis_reports_and_markers_stay_in_tool_checkout(module_name):
    module = importlib.import_module(module_name)
    checkout = Path(__file__).resolve().parents[1]
    assert module.ROOT == checkout
    for name in ("MARKER", "REPORT", "OUT_JSON", "OUT_MD"):
        if hasattr(module, name):
            assert getattr(module, name).is_relative_to(checkout)


def test_readonly_input_and_tool_defaults_stay_in_checkout():
    checkout = Path(__file__).resolve().parents[1]
    assert offline_store._repo_path("work/input.zip") == checkout / "work/input.zip"
    assert toolchain._repository_root() == checkout
    assert Path(reroll.BUILD) == checkout / "wf_rogue_build.py"
    assert Path(reroll.ROOT) == checkout
    assert story.DEFAULT_STORE is None
    assert story.DEFAULT_OUT.is_relative_to(checkout)


def test_backfill_writes_configured_server_only(configured):
    server, cdn, _ = configured
    result = SimpleNamespace(committed=True, archive_paths=[cdn / "archive-common-diff" / "new.zip"])
    with mock.patch.object(flow, "sync_server_mana_board", return_value={"written": True}) as sync:
        assert flow.backfill_server_mana_board_after_publish(result, Path("package")) == {"written": True}
    sync.assert_called_once_with(Path("package"), server / "assets", apply=True)


def test_reroll_uses_configured_assets_and_fails_before_side_effects(isolated, configured, monkeypatch):
    server, _, _ = configured
    data = {"quest": {"rushEventId": 700099, "rushEventFolderId": 1, "rushEventRound": 7}}
    (server / "assets" / "rush_event_quest.json").write_text(json.dumps(data), encoding="utf-8")
    assert reroll.deployed_rounds("700099") == 1
    assert reroll.season_fingerprint("700099") == "1:7"
    monkeypatch.delenv("WF_SERVER")
    with mock.patch.object(sys, "argv", ["wf_rogue_reroll.py", "--apply"]), \
            mock.patch.object(reroll.sqlite3, "connect") as database, \
            mock.patch.object(reroll.subprocess, "run") as run:
        with pytest.raises(core.ServerDirNotConfiguredError):
            reroll.main()
    database.assert_not_called()
    run.assert_not_called()


def test_story_missing_store_fails_before_output(isolated, tmp_path):
    out = tmp_path / "export"
    assert story.main(["--all", "--out", str(out)]) == 2
    assert not out.exists()


def test_offline_store_default_uses_local_profile_then_environment(isolated, monkeypatch):
    local, environment = isolated / "local-upload", isolated / "env-upload"
    local.mkdir(); environment.mkdir()
    (isolated / "profiles" / "local.json").write_text(
        json.dumps({"paths": {"store": str(local)}}), encoding="utf-8"
    )
    assert offline_store.resolve_store_roots("cn").common == local
    monkeypatch.setenv("WF_STORE", str(environment))
    assert offline_store.resolve_store_roots("cn").common == environment
    monkeypatch.setenv("WF_STORE", str(isolated / "missing"))
    with pytest.raises(offline_store.StoreError, match="WF_STORE"):
        offline_store.resolve_store_roots("cn")


def test_offline_store_default_rejects_missing_configuration(isolated):
    with pytest.raises(offline_store.StoreError, match="WF_STORE"):
        offline_store.resolve_store_roots("cn")


def test_offline_modules_import_without_server_or_store(isolated):
    config = isolated / "profiles" / "local.json"
    config.write_text("{}", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if not key.startswith("WF_")}
    env["WF_PATHS_PROFILE"] = str(config)
    names = ["wf_character_flow", "wf_all_analysis", "wf_fire_analysis", "wf_unique_mech",
             "wf_balance_patch", "wf_balance_patch_v2", "wf_rogue_reroll", "wf_offline_store",
             "wf_offline_toolchain", "wf_story_export", "wf_enhancement_switch",
             "wf_enhancement_policy", "wf_share_variant", "wf_chain_squash", "wf_pack_consolidate"]
    code = "import importlib; " + "; ".join(f"importlib.import_module({name!r})" for name in names)
    result = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_gui_store_only_import_then_server_actions_fail_closed(isolated, monkeypatch):
    store = isolated / "upload"
    store.mkdir()
    monkeypatch.setenv("WF_STORE", str(store))
    from test_gui_database_path import _load_gui
    gui = _load_gui()
    assert gui.SAVE_DB is None
    with mock.patch.object(gui.urllib.request, "urlopen") as request:
        for action in (lambda: gui._rogue_asset_path("x.json"), gui._server_assets,
                       gui._resolve_server_url, gui._rogue_reload_server,
                       lambda: gui._clamp_save_for_rarity("1", 5, True)):
            with pytest.raises(core.ServerDirNotConfiguredError):
                action()
        request.assert_not_called()
    # Even if a separate cdndata mirror exists, a mixed server write must fail first.
    monkeypatch.setattr(gui, "CDNDATA", store)
    with mock.patch.object(gui, "save_skill_energy") as save_skill:
        with pytest.raises(core.ServerDirNotConfiguredError):
            gui.save_char_fields("1", {"skill_name": "test"}, False)
        save_skill.assert_not_called()
