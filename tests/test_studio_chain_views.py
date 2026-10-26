"""Small, offline chains exercise portable studio views and builder exports."""
import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest

from wf.studio.source import build_source
from wf.view.base149 import member
from wf.view.export import export_store
from wf.view.manifest import ManifestView


@pytest.fixture
def chain(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    monkeypatch.delenv("WF_STUDIO_VIEW", raising=False)
    store = tmp_path / "production/upload"
    store.mkdir(parents=True)
    manifest = tmp_path / "standalone/manifest.json"
    manifest.parent.mkdir()
    zips = tmp_path / "deliveries/release/data"
    zips.mkdir(parents=True)
    return store, manifest, zips, profile


def archive(directory, before, after, data, *, label="fixture"):
    path = directory / f"pinball-{before}-{after}-1-{label}.zip"
    with zipfile.ZipFile(path, "w") as stream:
        for name, value in data.items():
            stream.writestr(name, value)
    return path, {"depends_on": before, "version": after, "enabled": True, "archive": path.name,
                  "archive_integrity": [{"name": path.name, "size": path.stat().st_size,
                                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}


def write_manifest(manifest, entries):
    manifest.write_text(json.dumps({"patches": entries}), encoding="utf-8")


def put(store, name, value):
    root, relative = name.removeprefix("production/").split("/", 1)
    path = (store if root == "upload" else store.parent / root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return path


def test_manifest_search_integrity_without_active_and_small_upload(chain):
    store, manifest, zips, _ = chain
    small = member("small").replace("/upload/", "/small_upload/")
    good, edge = archive(zips, "1.4.131", "1.4.132", {member("a"): b"one", small: b"small"})
    bad = zips.parent / good.name
    bad.write_bytes(b"x" * good.stat().st_size)  # size alone cannot identify a build
    write_manifest(manifest, [edge])
    view = ManifestView(None, store=store, manifest=manifest, search_dirs=[zips.parent])
    assert not (manifest.parent / "active").exists()
    assert view.zips == [good]
    assert view.read_member(small)[0] == b"small"
    assert view.read_raw("a")[0] == b"one"
    assert view.verify()["tip"] == "1.4.132"


def test_manifest_extra_zips_are_ordered_locked_and_advance_source_version(chain):
    store, manifest, zips, _ = chain
    _, edge = archive(zips, "1.4.131", "1.4.132", {member("a"): b"one"})
    extra, _ = archive(zips, "1.4.132", "1.4.135", {member("a"): b"extra"})
    listing = zips / "extras.txt"
    listing.write_text(f"# relative to this list\n{extra.name}\n", encoding="utf-8")
    write_manifest(manifest, [edge])
    source = build_source(tip=132, store=store, manifest=manifest, search_dirs=[zips], extra_lists=[listing])
    assert source.version == "1.4.135"
    assert source.view.tip == "1.4.132"
    assert source.view.read_raw("a")[0] == b"extra"
    assert source.describe()["extraZips"] == [extra.name]
    lock = source.view.lock_data()
    locked = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[zips],
                          extra_zips=[extra], lock=lock)
    assert locked.verify() == lock
    archive(zips, "1.4.132", "1.4.135", {member("a"): b"drift"})
    with pytest.raises(ValueError, match="changed while reading"):
        locked.read_raw("a")
    with pytest.raises(ValueError, match="changed during use"):
        source.view.verify()


def test_named_views_select_base_and_cutoff_with_explicit_overrides(chain, monkeypatch):
    store, manifest, zips, profile = chain
    _, first = archive(zips, "1.4.150", "1.4.151", {member("a"): b"first"})
    _, second = archive(zips, "1.4.151", "1.4.153", {member("a"): b"second"})
    write_manifest(manifest, [first, second])
    profile.write_text(json.dumps({"views": {
        "test175": {"manifest": str(manifest), "store": str(store), "zip_dirs": [str(zips)],
                    "base_version": "1.4.150", "tip": "1.4.151"},
        "prod": {"manifest": str(manifest), "store": str(store), "zip_dirs": [str(zips)],
                 "base_version": "1.4.150"}}}), encoding="utf-8")
    source = build_source(view_name="test175")
    assert source.version == "1.4.151"
    assert len(source.view.zips) == 1
    assert source.view.base_version == "1.4.150"
    assert build_source(view_name="test175", tip=153).version == "1.4.153"
    assert build_source(view_name="prod").version == "1.4.153"
    monkeypatch.setenv("WF_STUDIO_VIEW", "prod")
    assert build_source().view.view_name == "prod"
    with pytest.raises(ValueError, match="unknown named view"):
        build_source(view_name="missing")


@pytest.mark.parametrize("copy", [False, True])
def test_export_store_preserves_baseline_and_cdn_roots(chain, tmp_path, copy):
    store, manifest, zips, _ = chain
    baseline = put(store, member("base"), b"baseline")
    overlaid = put(store, member("overlaid"), b"old")
    small = member("thumb").replace("/upload/", "/small_upload/")
    put(store, small, b"small baseline")
    _, edge = archive(zips, "1.4.131", "1.4.132", {member("overlaid"): b"new", small: b"thumb"})
    write_manifest(manifest, [edge])
    view = ManifestView(None, store=store, manifest=manifest, search_dirs=[zips])
    destination = tmp_path / "exports/view"
    result = export_store(view, destination, copy=copy)
    assert result["copied" if copy else "linked"] == 1
    assert result["overlaid"] == 2
    assert (destination / member("base")).read_bytes() == b"baseline"
    assert os.path.samefile(baseline, destination / member("base")) is (not copy)
    assert (destination / member("overlaid")).read_bytes() == b"new"
    assert not os.path.samefile(overlaid, destination / member("overlaid"))
    assert (destination / small).read_bytes() == b"thumb"
    assert overlaid.read_bytes() == b"old"
    assert json.loads((destination / "viewstore.json").read_text("utf-8"))["tip"] == "1.4.132"
    with pytest.raises(FileExistsError):
        export_store(view, destination, copy=copy)


def test_bad_overlay_members_rejected_before_export(chain):
    store, manifest, zips, _ = chain
    _, edge = archive(zips, "1.4.131", "1.4.132", {"production/small_upload/../../escape": b"bad"})
    write_manifest(manifest, [edge])
    with pytest.raises(ValueError, match="invalid CDN member"):
        ManifestView(None, store=store, manifest=manifest, search_dirs=[zips])


def test_named_view_keeps_supplemental_manifests(chain):
    store, manifest, zips, profile = chain
    _, first = archive(zips, "1.4.131", "1.4.132", {member("a"): b"one"})
    _, second = archive(zips, "1.4.132", "1.4.133", {member("a"): b"two"})
    write_manifest(manifest, [first])
    supplemental = manifest.parent / "extra.json"
    write_manifest(supplemental, [second])
    profile.write_text(json.dumps({"views": {"test": {
        "store": str(store), "manifest": str(manifest), "zip_dirs": [str(zips)],
        "manifests": [str(supplemental)]}}}), encoding="utf-8")
    assert build_source(view_name="test").version == "1.4.133"
    assert build_source(view_name="test", manifest=manifest).version == "1.4.132"


def test_chain_may_stop_at_baseline_without_active_or_any_archive(chain):
    store, manifest, zips, _ = chain
    small = member("base-small").replace("/upload/", "/small_upload/")
    put(store, small, b"baseline thumb")
    write_manifest(manifest, [{"enabled": False, "version": "1.4.132", "depends_on": "1.4.131",
                               "archive": "pinball-1.4.131-1.4.132-1-absent.zip"}])
    view = ManifestView("1.4.131", store=store, manifest=manifest, search_dirs=[])
    assert view.zips == [] and view.read_member(small)[0] == b"baseline thumb"
    assert view.verify()["tip"] == "1.4.131"
