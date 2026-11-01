"""Source, gate, dependency, and output confinement regressions for Overlay."""
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_studio_overlay import delivery
from test_studio_rehearsal import put, snapshot
from wf.studio import overlay_export as overlay
from wf.studio.rehearsal_io import read_json


def test_view_zip_search_and_tip_overrides(delivery):
    folder, profile = delivery
    root = folder.parent
    put(profile, {"wf_root": str(root), "views": {"dev": {"overlay_base": True,
        "manifest": "manifest.json", "store": "store", "zip_dirs": ["public"], "tip": "1.4.54"}}})
    view = SimpleNamespace(view_name="dev", manifest=root / "manifest.json", store=root / "store",
        extra_zips=[], manifests=None, base_version="1.4.131", search_dirs=[root / "public"], tip="1.4.54")
    assert overlay.source_view(view)["overlayBase"]
    view.search_dirs.append(root / "internal")
    assert not overlay.source_view(view)["overlayBase"]
    view.search_dirs.pop()
    view.tip = "1.4.290"
    assert not overlay.source_view(view)["overlayBase"]
    view.tip = 54
    assert overlay.source_view(view)["overlayBase"]


@pytest.mark.parametrize("problem", ["check", "compat", "draft", "safety", "build", "requires", "server", "missing-report", "client-label"])
def test_failed_or_dependent_delivery_cannot_export(delivery, problem):
    folder, _ = delivery
    if problem in {"check", "compat", "draft", "safety"}:
        file = {"check": "check.json", "compat": "compat.json", "draft": "draft-checks.json", "safety": "safety-checks.json"}[problem]
        rows = [{"blocking": True, "status": "问题"}]
        put(folder / file, rows if problem in {"draft", "safety"} else {"results": rows})
    elif problem == "build":
        put(folder.parent / "build-report.json", {"ok": False})
    elif problem == "requires":
        requirements = read_json(folder / "requires.json")
        requirements["requires"]["clientCapabilities"] = ["client.apk.patch013@1"]
        put(folder / "requires.json", requirements)
    elif problem == "server":
        put(folder / "server/assets/table.json", {"row": 1})
    elif problem == "missing-report":
        manifest = read_json(folder / "delivery-manifest.json")
        manifest["safety_checks"] = "missing.json"
        put(folder / "delivery-manifest.json", manifest)
    else:
        manifest = read_json(folder / "patches/1.4.55/patch-manifest.json")
        manifest["compatibleClient"] = "custom"
        put(folder / "patches/1.4.55/patch-manifest.json", manifest)
    original = snapshot(folder)
    with pytest.raises(ValueError):
        overlay.export_overlay(folder, "custom" if problem == "client-label" else "CN 1.8.1")
    assert snapshot(folder) == original
    if problem != "client-label":
        assert not overlay.availability(folder)["overlayAvailable"]


@pytest.mark.parametrize("subdir", ["server/assets/pkg", "server-entries/pkg", "patches/pkg", "rehearsal/pkg"])
def test_overlay_cannot_inject_semantic_delivery_files(delivery, subdir):
    folder, _ = delivery
    original = snapshot(folder)
    with pytest.raises(ValueError, match="overlay 专用"):
        overlay.export_overlay(folder, "CN 1.8.1", out=folder / subdir)
    assert snapshot(folder) == original


@pytest.mark.parametrize("setting", ["WF_SERVER", "WF_CDN_DIR", "named"])
def test_overlay_respects_protected_input_roots(delivery, monkeypatch, setting):
    folder, profile = delivery
    if setting == "named":
        config = read_json(profile)
        config["servers"] = {"other": {"root": str(folder)}}
        put(profile, config)
    else:
        monkeypatch.setenv(setting, str(folder))
    original = snapshot(folder)
    with pytest.raises(ValueError, match="禁止写入"):
        overlay.export_overlay(folder, "CN 1.8.1")
    assert snapshot(folder) == original


def test_null_optional_config_and_dependency_preservation(delivery):
    folder, profile = delivery
    config = read_json(profile)
    config["servers"] = None
    put(profile, config)
    original = snapshot(folder)
    result = overlay.export_overlay(folder, "CN 1.8.1")
    with zipfile.ZipFile(result["zip"]) as archive:
        assert json.loads(archive.read("requires.json")) == read_json(folder / "requires.json")
    assert all(snapshot(folder)[key] == value for key, value in original.items())
    put(profile, {"views": None, "servers": None})
    assert not overlay.availability(folder)["overlayAvailable"]
    assert not overlay.source_view(SimpleNamespace())["overlayBase"]


def test_detail_hides_staging_and_tolerates_disappearing_file(delivery, monkeypatch):
    from wf.studio.deliver_routes import DeliverRoutes
    folder, _ = delivery
    name = "199000-1.4.54-to-1.4.55-20261101-120000"
    build = folder.parent / name
    build.mkdir()
    folder.rename(build / "delivery")
    staging = build / "delivery/.overlay-temporary"
    staging.mkdir()
    (staging / "secret.tmp").write_bytes(b"half written")
    disappearing = build / "gone.tmp"
    disappearing.write_bytes(b"temporary")
    original = Path.stat
    original_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda p: True if p == disappearing else original_is_file(p))
    def stat(path, *args, **kwargs):
        if path == disappearing:
            raise FileNotFoundError("concurrent removal")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", stat)
    result = json.loads(DeliverRoutes(SimpleNamespace(), root=build.parent).detail({}, name).body)
    assert not any(".overlay-" in item["path"] or "gone.tmp" == item["path"] for item in result["files"])
