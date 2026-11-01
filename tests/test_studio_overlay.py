"""Real existing three-layer metadata and packer, using synthetic payloads only."""
import json
import zipfile
from types import SimpleNamespace

import pytest

from test_studio_rehearsal import put, snapshot
from wf.deliver.manifests import write_manifests
from wf.deliver.archives import write_archives
from wf.deliver.changeset import member_name, sha256
from wf.studio import overlay_export as overlay
from wf.studio.drafts import DraftError


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    folder = tmp_path / "delivery"
    folder.mkdir()
    cdn = tmp_path / "cdn"
    cdn.mkdir()
    (cdn / "archive-common-full").mkdir()
    monkeypatch.setenv("WF_CDN_DIR", str(cdn))
    profile = tmp_path / "profile.json"
    put(profile, {"views": {"dev": {"overlay_base": True}}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    members = {member_name("common", "fixture.bin"): (b"fixture", {
        "root": "common", "logical_path": "fixture.bin", "sha256": sha256(b"fixture"), "before_sha256": None})}
    doc = {"id": "fixture", "name": "test", "from_version": "1.4.54", "to_version": "1.4.55",
           "local_test_only": True, "created_at": "2026-11-01"}
    records = write_archives(folder, members, lambda seq: f"pinball-1.4.54-1.4.55-{seq}-test.zip")
    legacy, upstream = write_manifests(folder, doc, members, records)
    put(folder / "delivery-manifest.json", {**doc, "archives": records, "legacy_manifest": legacy,
                                           "upstream_manifest": upstream})
    put(folder / "source-view.json", {"name": "dev", "overlayBase": True})
    put(folder / "check.json", {"results": [{"blocking": False}]})
    return folder, profile


def test_overlay_real_packer_schema_layout_and_unchanged_inputs(delivery):
    folder, _ = delivery
    before = snapshot(folder)
    result = overlay.export_overlay(folder, "CN 1.8.1")
    assert result["ok"] and result["overlayAvailable"]
    overlay.validate_schema(result["manifest"])
    from wf.tools.core import dev_catalog
    dev_catalog._validate_staged_overlay(folder / "overlay/1.4.55", result["manifest"])
    assert {a["layer"] for a in result["manifest"]["archives"]} == {"common", "medium", "android"}
    assert result["manifest"]["baseVersion"] == "1.4.54"
    with zipfile.ZipFile(result["zip"]) as archive:
        assert "patch-manifest.json" in archive.namelist() and "README.md" in archive.namelist()
        text = archive.read("README.md").decode()
        assert "CDN_DIR/patches/1.4.55/" in text and "npm run start:cn" in text
        assert "local_test_only" not in json.loads(archive.read("patch-manifest.json"))
    assert all(snapshot(folder)[key] == value for key, value in before.items())
    with pytest.raises(DraftError, match="已存在"):
        overlay.export_overlay(folder, "CN 1.8.1")


@pytest.mark.parametrize("problem", ["internal", "unknown-view", "base", "order", "layer", "missing-layer", "schema", "hash", "client", "outside"])
def test_overlay_refusal_paths(delivery, problem):
    folder, profile = delivery
    file = folder / "patches/1.4.55/patch-manifest.json"
    manifest = json.loads(file.read_bytes())
    if problem == "internal":
        put(profile, {"views": {"dev": {"overlay_base": False}}})
    elif problem == "unknown-view":
        (folder / "source-view.json").unlink()
    elif problem == "base":
        manifest["baseVersion"] = "1.4.53"
    elif problem == "order":
        manifest["archives"][0]["order"] = 2
    elif problem == "layer":
        manifest["archives"][0]["layer"] = "medium"
    elif problem == "missing-layer":
        manifest["archives"].pop()
    elif problem == "schema":
        manifest["archives"][0]["bytes"] = "string"
    elif problem == "hash":
        manifest["archives"][0]["sha256"] = "0" * 64
    put(file, manifest)
    before = snapshot(folder)
    with pytest.raises(ValueError):
        overlay.export_overlay(folder, "invalid" if problem == "client" else "CN 1.8.1",
                               out=folder.parent / "outside" if problem == "outside" else None)
    assert snapshot(folder) == before
    if problem in {"internal", "unknown-view"}:
        assert overlay.availability(folder)["overlayReason"] == overlay.INTERNAL_REASON


def test_overlay_view_provenance_overrides_rejected(delivery, tmp_path):
    _, profile = delivery
    put(profile, {"wf_root": str(tmp_path), "views": {"dev": {"overlay_base": True,
        "manifest": "dev.json", "store": "store"}}})
    view = SimpleNamespace(view_name="dev", manifest=tmp_path / "dev.json", store=tmp_path / "store",
                           manifests=None, extra_zips=[], base_version="1.4.131", search_dirs=[tmp_path])
    assert overlay.source_view(view)["overlayBase"]
    view.manifest = tmp_path / "internal.json"
    assert not overlay.source_view(view)["overlayBase"]


def test_overlay_cli(delivery, capsys):
    from wf.studio.draft import main
    folder, _ = delivery
    assert main(["export-overlay", "--delivery-dir", str(folder), "--compatible-client", "CN 1.8.1"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["overlayAvailable"]


def test_overlay_source_changes_between_validation_and_snapshot(delivery, monkeypatch):
    from wf.tools.core import dev_catalog as catalog
    folder, _ = delivery
    original = catalog._pin_overlay_source
    def changed(archive, source_root, relative, *args):
        with zipfile.ZipFile(source_root / relative, "a") as container:
            container.comment = b"concurrent change"
        return original(archive, source_root, relative, *args)
    monkeypatch.setattr(catalog, "_pin_overlay_source", changed)
    with pytest.raises(DraftError, match="校验后变化"):
        overlay.export_overlay(folder, "CN 1.8.1")
    assert not (folder / "overlay").exists()


def test_overlay_actual_studio_build_records_selected_view(tmp_path, monkeypatch):
    from test_studio_deliver_bridge import case as build_case, build
    from wf.view import ManifestView
    data = build_case.__wrapped__(tmp_path, monkeypatch)
    drafts, changes, old_view, out = data
    profile = tmp_path / "profile.json"
    put(profile, {"wf_root": str(tmp_path), "views": {"dev": {
        "manifest": "manifest.json", "store": "store", "base_version": "1.4.131", "overlay_base": True}}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    view = ManifestView("1.4.132", view_name="dev", search_dirs=[])
    result = build((drafts, changes, view, out), allow_unknown_client=True)
    assert result["ok"] and result["overlayAvailable"]
    assert json.loads((out / "delivery/source-view.json").read_bytes()) == {"name": "dev", "overlayBase": True}
    exported = overlay.export_overlay(out, "CN 1.8.1")
    assert exported["manifest"]["baseVersion"] == "1.4.132"
    assert exported["manifest"]["targetVersion"] == "1.4.133"
