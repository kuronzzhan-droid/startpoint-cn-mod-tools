"""The six legacy consumers must not infer a server from their parent directory."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import pytest

import wf_mod_tool as core
import wf_rogue_banner as banner
import wf_rogue_rewards as rewards
import wf_rogue_save as save
import wf_rogue_shop as shop
import wf_rogue_validate as validate
from tool_source import tool_source


ROOT = Path(__file__).resolve().parents[1]
MODULES = ("wf_rogue_rewards", "wf_rogue_shop", "wf_rogue_save",
           "wf_rogue_banner", "wf_rogue_validate", "wf_balance_suite")


def copied_module(name, tool_dir, monkeypatch):
    # 复制工具本体（搬进 wf/tools 的按原相对位置放），根目录兼容入口只是转发。
    source = tool_source(ROOT, f"{name}.py")
    target = tool_dir / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    module_name = f"isolated_{name}"
    spec = importlib.util.spec_from_file_location(module_name, target)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def missing_server():
    raise ValueError("explicit server required")


def missing_cdn():
    raise ValueError("explicit CDN required")


def test_plain_imports_do_not_resolve_server_or_database(tmp_path):
    environment = os.environ.copy()
    environment.update({"WF_SERVER": str(tmp_path / "missing-server"),
                        "WF_SERVER_DIR": str(tmp_path / "missing-server"),
                        "WF_DATABASE_DIR": str(tmp_path / "missing-database"),
                        "PYTHONDONTWRITEBYTECODE": "1"})
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", "; ".join(f"import {m}" for m in MODULES)],
        cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["wf_rogue_rewards", "wf_rogue_shop"])
def test_mirrors_require_explicit_server_and_never_write_sibling(name, tmp_path, monkeypatch):
    tool_dir = tmp_path / "tools"
    sibling_assets = tmp_path / "assets"
    sibling_assets.mkdir()
    decoy = sibling_assets / "mirror.json"
    decoy.write_bytes(b'{"original":true}')
    module = copied_module(name, tool_dir, monkeypatch)
    monkeypatch.setattr(core, "resolve_server_dir", missing_server)
    with pytest.raises(ValueError, match="explicit server"):
        module.save_json("mirror.json", {"wrong": True})
    assert decoy.read_bytes() == b'{"original":true}'

    server = tmp_path / "configured-server"
    (server / "assets").mkdir(parents=True)
    monkeypatch.setattr(core, "resolve_server_dir", lambda: server)
    module.save_json("mirror.json", {"correct": True})
    assert module.load_json("mirror.json") == {"correct": True}
    assert json.loads((server / "assets/mirror.json").read_text()) == {"correct": True}
    assert decoy.read_bytes() == b'{"original":true}'


def test_tool_resources_and_balance_artifacts_stay_under_tool_dir(tmp_path, monkeypatch):
    tool_dir = tmp_path / "tools"
    module = copied_module("wf_rogue_rewards", tool_dir, monkeypatch)
    assert module.SOURCE_ASSET_DIR == tool_dir / "assets/abyss-equipment"
    suite = copied_module("wf_balance_suite", tool_dir, monkeypatch)
    assert suite.MARKER == tool_dir / "logs/balance_suite_applied.json"
    assert suite.REPORT == tool_dir / "logs/balance_suite_report.json"
    configured_cdn = tmp_path / "configured-cdn"
    diff = configured_cdn / "archive-common-diff"
    diff.mkdir(parents=True)
    archive = diff / "pinball-1-mod-fixture.zip"
    archive.write_bytes(b"selected CDN bytes")
    decoy = tmp_path / ".cdn/cn/archive-common-diff"
    decoy.mkdir(parents=True)
    (decoy / archive.name).write_bytes(b"wrong sibling CDN")
    result = suite.export_pack(configured_cdn, "fixture")
    assert result.parent == tool_dir
    with zipfile.ZipFile(result) as package:
        assert package.read(f"archive-common-diff/{archive.name}") == b"selected CDN bytes"
    assert not list(tmp_path.glob("*.zip"))
    assert not (tmp_path / "logs").exists()


@pytest.mark.parametrize("flag", ["--apply", "--export-pack"])
@pytest.mark.parametrize("missing", ["server", "cdn"])
def test_suite_missing_configuration_stops_before_restore(flag, missing, tmp_path, monkeypatch):
    suite = copied_module("wf_balance_suite", tmp_path / "tools", monkeypatch)
    monkeypatch.setattr(core, "resolve_server_dir", missing_server if missing == "server"
                        else lambda: tmp_path / "configured-server")
    monkeypatch.setattr(core, "resolve_cdn_root", missing_cdn if missing == "cdn"
                        else lambda: tmp_path / "configured-cdn")
    monkeypatch.setattr(core, "resolve_cdndata_dir", missing_server if missing == "server"
                        else lambda: tmp_path / "configured-cdndata")
    def forbidden(*args, **kwargs):
        pytest.fail("configuration failure reached store access or baseline restore")
    monkeypatch.setattr(core, "require_active_store", forbidden)
    monkeypatch.setattr(shutil, "copy2", forbidden)
    argv = ["wf_balance_suite.py", flag]
    if flag == "--apply":
        argv.append("--publish")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="explicit"):
        suite.main()
    assert not (tmp_path / "logs").exists()


def test_suite_independent_cdndata_does_not_require_server(tmp_path, monkeypatch):
    suite = copied_module("wf_balance_suite", tmp_path / "tools", monkeypatch)
    monkeypatch.setattr(core, "resolve_server_dir", missing_server)
    selected = []
    monkeypatch.setattr(core, "resolve_cdndata_dir", lambda: (
        selected.append(tmp_path / "cdndata") or selected[-1]))
    def stop_after_preflight():
        raise RuntimeError("reached configured store")
    monkeypatch.setattr(core, "require_active_store", stop_after_preflight)
    monkeypatch.setattr(sys, "argv", ["wf_balance_suite.py"])
    with pytest.raises(RuntimeError, match="reached configured store"):
        suite.main()
    assert selected == [tmp_path / "cdndata"]


def test_save_database_and_auth_reject_missing_server_before_side_effects(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "resolve_server_dir", missing_server)
    with pytest.raises(ValueError, match="explicit server"):
        save.resolve_database_path({})
    with pytest.raises(ValueError, match="explicit server"):
        save.api_post("http://invalid", "/unused")
    database_dir = tmp_path / "explicit-database"
    database_dir.mkdir()
    assert save.resolve_database_path({"WF_DATABASE_DIR": str(database_dir)}) == (
        database_dir / "wdfp_data.db")
    assert not list(database_dir.iterdir())
    assert Path(save._publish_command((save.RUSH_QUEST_LOGICAL,))[1]) == ROOT / "wf_publish.py"


@pytest.mark.parametrize("missing", ["server", "cdn"])
def test_save_missing_config_precedes_database_and_device_changes(missing, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "resolve_server_dir", missing_server if missing == "server"
                        else lambda: tmp_path / "configured-server")
    monkeypatch.setattr(core, "resolve_cdn_root", missing_cdn)
    def forbidden(*args, **kwargs):
        pytest.fail("missing CDN reached a mutation")
    monkeypatch.setattr(save.sqlite3, "connect", forbidden)
    monkeypatch.setattr(save, "mumu_sh", forbidden)
    monkeypatch.setattr(sys, "argv", ["wf_rogue_save.py", "--reset", "1", "--apply",
                                     "--random-boss", "--restart-game"])
    with pytest.raises(ValueError, match="explicit"):
        save.main()


@pytest.mark.parametrize("missing", ["server", "cdn"])
def test_rewards_publish_preflights_before_master_mutations(missing, tmp_path, monkeypatch):
    monkeypatch.setattr(rewards, "validate_source_assets", lambda *args: {})
    monkeypatch.setattr(rewards, "_print_asset_validation", lambda *args: None)
    monkeypatch.setattr(rewards, "require_cn_profile", lambda: SimpleNamespace(store=tmp_path))
    monkeypatch.setattr(core, "resolve_server_dir", missing_server if missing == "server"
                        else lambda: tmp_path / "server")
    monkeypatch.setattr(core, "resolve_cdn_root", missing_cdn)
    def forbidden(*args):
        pytest.fail("configuration failure reached master table access")
    monkeypatch.setattr(rewards.q, "load_table", forbidden)
    monkeypatch.setattr(rewards.q, "save_table", forbidden)
    monkeypatch.setattr(sys, "argv", ["rewards", "--write", "--publish",
                                     "--client-verification", "proof.json",
                                     "--ffdec", "ffdec", "--java", "java"])
    assert rewards.main() == 1


@pytest.mark.parametrize("missing", ["server", "cdn"])
def test_banner_publish_preflights_before_any_store_access(missing, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "resolve_server_dir", missing_server if missing == "server"
                        else lambda: tmp_path / "server")
    monkeypatch.setattr(core, "resolve_cdn_root", missing_cdn)
    def forbidden():
        pytest.fail("configuration failure reached store access")
    monkeypatch.setattr(core, "require_active_store", forbidden)
    monkeypatch.setattr(sys, "argv", ["banner", "--main", "unused.png", "--write", "--publish"])
    with pytest.raises(ValueError, match="explicit"):
        banner.main()


def test_banner_publishes_local_script_from_configured_server(tmp_path, monkeypatch):
    tool_dir = tmp_path / "tools"
    module = copied_module("wf_rogue_banner", tool_dir, monkeypatch)
    server, store = tmp_path / "server", tmp_path / "store"
    image = tmp_path / "source.png"
    image.write_bytes(b"fixture")
    monkeypatch.setattr(core, "resolve_server_dir", lambda: server)
    monkeypatch.setattr(core, "resolve_cdn_root", lambda: tmp_path / "cdn")
    monkeypatch.setattr(core, "require_active_store", lambda: store)
    monkeypatch.setattr(module, "fit_png", lambda *args: b"image")
    monkeypatch.setattr(module, "write_store", lambda *args: "aa/image")
    monkeypatch.setattr(module.q, "load_table", lambda *args: {module.EVENT_ID: ",,,,"})
    monkeypatch.setattr(module.q, "save_table", lambda *args: store / "aa/table")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: (
        calls.append((command, kwargs)) or SimpleNamespace(returncode=0)))
    monkeypatch.setattr(sys, "argv", ["banner", "--main", str(image), "--write", "--publish"])
    assert module.main() == 0
    assert calls == [([sys.executable, str(tool_dir / "wf_publish.py")], {"cwd": server})]
    assert (tool_dir / "work/sync_pending.json").is_file()
    assert not (tmp_path / "work").exists()


def test_validator_resolves_server_assets_but_sources_remain_tool_owned(tmp_path, monkeypatch):
    server = tmp_path / "server"
    sources = tmp_path / "tool-sources"
    monkeypatch.setattr(core, "resolve_server_dir", lambda: server)
    monkeypatch.setattr(rewards, "require_cn_profile", lambda: SimpleNamespace(store=tmp_path / "store"))
    monkeypatch.setattr(validate, "ASSETS_DIR", None)
    monkeypatch.setattr(validate, "_print_result", lambda result: None)
    seen = []
    monkeypatch.setattr(validate, "validate_release", lambda *args, **kwargs: (
        seen.append(args) or SimpleNamespace(errors=[])))
    monkeypatch.setattr(sys, "argv", ["validate", "--client-verification", "proof.json",
                                     "--ffdec", "ffdec", "--java", "java"])
    assert validate.main() == 0
    assert seen[0][1] == server / "assets"
    monkeypatch.setattr(rewards, "SOURCE_ASSET_DIR", sources)
    monkeypatch.setattr(rewards, "WEAPONS", ())
    monkeypatch.setattr(rewards, "validate_source_assets", lambda path, weapons: seen.append(path))
    validate._validate_pngs(tmp_path / "store", server / "assets", [], [])
    assert seen[-1] == sources
