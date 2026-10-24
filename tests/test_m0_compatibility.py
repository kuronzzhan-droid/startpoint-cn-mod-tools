"""A-source compatibility: shared module state, explicit inputs and archive isolation."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from wf.paths import REPOSITORY


METADATA = json.loads((REPOSITORY / "docs/m0/compatibility.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("record", METADATA["modules"], ids=lambda row: row["module"])
def test_original_module_alias_shares_private_and_public_state(record, monkeypatch):
    alias = importlib.import_module(record["module"])
    implementation = importlib.import_module("wf.compat." + record["module"].removeprefix("wf_"))
    assert alias is implementation
    assert Path(alias.__file__).resolve() == REPOSITORY / record["implementation"]
    for name in record["public_api"]:
        assert callable(getattr(alias, name))
    for name in record["removed_role_symbols"]:
        assert not hasattr(alias, name)
    marker = object()
    monkeypatch.setattr(alias, "_compatibility_probe", marker, raising=False)
    assert implementation._compatibility_probe is marker


def test_explicit_paths_reject_invalid_overrides_and_resolve_local_fixtures(tmp_path):
    from wf_apk_paths import resolve_explicit_apk
    from wf_database_paths import resolve_database_path
    from wf_device_paths import find_adb, find_mumu_manager

    apk = tmp_path / "fixture.apk"
    apk.write_bytes(b"offline fixture")
    assert resolve_explicit_apk({}) is None
    assert resolve_explicit_apk({"WF_APK": str(apk)}) == apk.resolve()
    assert resolve_database_path({}, server_root=tmp_path) == tmp_path / ".database/wdfp_data.db"
    assert resolve_database_path({"WF_DATABASE_DIR": str(tmp_path)}, server_root="unused") == tmp_path / "wdfp_data.db"
    assert find_adb({"WF_ADB": str(apk)}, finder=lambda _: None) == str(apk)
    assert find_mumu_manager({"WF_MUMU_MANAGER": str(apk)}, finder=lambda _: None) == apk
    assert find_adb({}, finder=lambda _: None) is None
    for bad in ("", "relative/file", str(tmp_path / "missing")):
        with pytest.raises(ValueError):
            resolve_explicit_apk({"WF_APK": bad})
        with pytest.raises(ValueError):
            resolve_database_path({"WF_DATABASE_DIR": bad}, server_root=tmp_path)
        with pytest.raises(ValueError):
            find_adb({"WF_ADB": bad}, finder=lambda _: str(apk))


def test_private_function_patch_is_used_by_public_entrypoint(monkeypatch):
    import wf_device_paths as legacy
    from wf.compat import device_paths

    monkeypatch.setattr(legacy, "_explicit_file", lambda env, key: Path(env[key]))
    assert device_paths.find_adb({"WF_ADB": "fixture.exe"}) == "fixture.exe"


def test_ui_resources_resolve_to_checkout_without_starting_services():
    import wf_preview_2d as preview
    import wf_release_ui as release_ui

    assert preview._HTML_PATH == REPOSITORY / "wf_preview_2d.html"
    assert release_ui._UI_PATH == REPOSITORY / "wf_release_ui.html"
    assert release_ui._PREVIEW_PATH == preview._HTML_PATH
    assert preview._HTML_PATH.is_file() and release_ui._UI_PATH.is_file()


def test_release_paths_use_explicit_mocked_roots(tmp_path, monkeypatch):
    import wf_release_paths as paths

    assert paths.tool_checkout_root(Path(paths.__file__)) == REPOSITORY
    server = tmp_path / "server"
    (server / "assets").mkdir(parents=True)
    store, cdn = tmp_path / "store", tmp_path / "cdn"
    store.mkdir()
    cdn.mkdir()
    monkeypatch.setattr(paths.core, "resolve_profile", lambda _: SimpleNamespace(id="cn"))
    monkeypatch.setattr(paths.core, "require_active_store", lambda **_: store)
    monkeypatch.setattr(paths.core, "resolve_server_dir", lambda _: server)
    monkeypatch.setattr(paths.core, "resolve_cdn_root", lambda _: cdn)
    result = paths.resolve_release_paths("cn", module_file=REPOSITORY / "wf_release.py")
    assert result.tool_root == REPOSITORY
    assert result.live_roots.common == store
    assert result.live_roots.protected == (cdn,)
    with pytest.raises(paths.ReleasePathError, match="CN-only"):
        paths.resolve_release_paths("jp", module_file=REPOSITORY / "wf_release.py")


def test_restored_package_and_compatibility_do_not_load_archived_sources():
    import wf_release_v1

    assert Path(wf_release_v1.__file__).resolve().parent == REPOSITORY / "wf_release_v1"
    archive = REPOSITORY / "archive"
    for name, module in tuple(sys.modules.items()):
        if name.startswith(("wf_", "wf.")) and getattr(module, "__file__", None):
            assert not Path(module.__file__).resolve().is_relative_to(archive), name
