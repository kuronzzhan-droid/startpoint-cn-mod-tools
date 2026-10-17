"""Negative controls for chain order, manifest drift and store/ZIP locks."""
import hashlib
import json
import zipfile

import pytest

from wf.view import ManifestView
from wf.view.base149 import member


def setup_view(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir(); store.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"patches": []}', encoding="utf-8")
    return active, store, manifest


def patch(active, before, after, contents, seq=1):
    name = f"pinball-{before}-{after}-{seq}-test.zip"
    with zipfile.ZipFile(active / name, "w") as archive:
        for key, value in contents.items():
            archive.writestr(member(key), value)
    return {"version": after, "depends_on": before, "archive": name, "enabled": True}


def write_manifest(path, entries):
    path.write_text(json.dumps({"patches": entries}), encoding="utf-8")


def view(store, manifest, tip="1.4.132", **kwargs):
    return ManifestView(tip, store=store, manifest=manifest, search_dirs=[], **kwargs)


def test_dependency_and_numeric_seq_order(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    entries = [patch(active, "1.4.131", "1.4.132", {"a": str(i).encode()}, i)
               for i in range(1, 12)]
    edge = entries[0]
    edge["chain"] = sorted(item["archive"] for item in entries)
    later = patch(active, "1.4.132", "1.4.133", {"b": b"later"})
    write_manifest(manifest, [later, edge])
    result = view(store, manifest, "1.4.133")
    assert result.read_raw("a")[0] == b"11"
    assert result.read_raw("b")[0] == b"later"
    assert result.zips[-1].name == later["archive"]


@pytest.mark.parametrize("fault", ["gap", "ambiguous", "seq", "digest", "duplicate-name"])
def test_chain_refuses_invalid_inputs(tmp_path, monkeypatch, fault):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"one"})
    entries, dirs = [edge], []
    if fault == "gap":
        edge["enabled"] = False
    elif fault == "ambiguous":
        other = dict(edge, archive=edge["archive"].replace("test", "different"))
        entries.append(other)
    elif fault == "seq":
        edge["chain"] = [edge["archive"], edge["archive"]]
    elif fault == "digest":
        edge["archive_integrity"] = [{"name": edge["archive"], "sha256": "0" * 64}]
    else:
        extra = tmp_path / "extra"
        extra.mkdir()
        (extra / edge["archive"]).write_bytes(b"different")
        dirs.append(extra)
    write_manifest(manifest, entries)
    with pytest.raises(ValueError):
        ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=dirs)


def test_lock_rejects_changed_zip_and_list(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"old"})
    write_manifest(manifest, [edge])
    first = view(store, manifest)
    lock = first.lock_data()
    assert view(store, manifest, lock=lock).read_raw("a")[0] == b"old"
    patch(active, "1.4.131", "1.4.132", {"a": b"new"})
    with pytest.raises(ValueError, match="changed while reading"):
        first.read_raw("a")
    with pytest.raises(ValueError, match="ZIP list or SHA-256"):
        view(store, manifest, lock=lock)


def test_lock_tracks_used_store_only_and_rejects_new_fallback(tmp_path, monkeypatch):
    _, store, manifest = setup_view(tmp_path, monkeypatch)
    name = member("base")
    target = store / name.removeprefix("production/upload/")
    target.parent.mkdir(); target.write_bytes(b"original")
    first = view(store, manifest, "1.4.131")
    first.read_raw("base")
    lock = first.lock_data()
    assert lock["store_members"] == {name: hashlib.sha256(b"original").hexdigest()}
    locked = view(store, manifest, "1.4.131", lock=lock)
    with pytest.raises(ValueError, match="unlocked"):
        locked.read_raw("unrecorded")
    empty = dict(lock, store_members={})
    with pytest.raises(ValueError, match="unlocked"):
        view(store, manifest, "1.4.131", lock=empty).read_raw("base")
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest drift"):
        view(store, manifest, "1.4.131", lock=lock)
    with pytest.raises(ValueError, match="changed during use"):
        first.verify()


def test_locked_view_still_checks_manifest(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    write_manifest(manifest, [patch(active, "1.4.131", "1.4.132", {"a": b"old"})])
    first = view(store, manifest)
    write_manifest(manifest, [])
    with pytest.raises(ValueError, match="chain gap"):
        first.verify()


def test_explicit_supplemental_manifest_avoids_unselected_historical_drafts(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"value"})
    write_manifest(manifest, [edge])
    write_manifest(active / "manifest-draft.json", [dict(edge, archive=edge["archive"].replace("test", "draft"))])
    from wf.view.chain import resolve_chain
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_chain(manifest, [active], "1.4.131", "1.4.132")
    assert view(store, manifest, manifests=[]).read_raw("a")[0] == b"value"


def test_store_first_read_digest_cannot_be_replaced(tmp_path, monkeypatch):
    _, store, manifest = setup_view(tmp_path, monkeypatch)
    target = store / member("base").removeprefix("production/upload/")
    target.parent.mkdir(); target.write_bytes(b"original")
    first = view(store, manifest, "1.4.131")
    first.read_raw("base")
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed during use"):
        first.read_raw("base")
    with pytest.raises(ValueError, match="changed during use"):
        first.verify()


def test_lock_snapshots_have_no_mutable_aliases(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    write_manifest(manifest, [patch(active, "1.4.131", "1.4.132", {"a": b"value"})])
    unlocked = view(store, manifest)
    lock = unlocked.lock_data()
    locked = view(store, manifest, lock=lock)
    target = store / member("base").removeprefix("production/upload/")
    target.parent.mkdir(); target.write_bytes(b"original")
    lock["store_members"][member("base")] = hashlib.sha256(b"original").hexdigest()
    lock["zips"].clear()
    with pytest.raises(ValueError, match="unlocked"):
        locked.read_raw("base")
    locked.lock_data()["zips"].clear()
    assert len(locked.verify()["zips"]) == len(unlocked.lock_data()["zips"]) == 1


def test_explicit_manifest_does_not_inherit_unrelated_profile_manifests(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"view": {"manifests": [str(tmp_path / "missing.json")]}}), encoding="utf-8")
    write_manifest(manifest, [patch(active, "1.4.131", "1.4.132", {"a": b"value"})])
    assert view(store, manifest).read_raw("a")[0] == b"value"


def test_disabled_supplement_cannot_resurrect_old_enabled_edge(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"value"})
    write_manifest(manifest, [edge])
    supplemental = tmp_path / "later.json"
    write_manifest(supplemental, [dict(edge, enabled=False)])
    with pytest.raises(ValueError, match="enabled state"):
        view(store, manifest, manifests=[supplemental])


def test_malformed_lock_is_rejected_cleanly(tmp_path, monkeypatch):
    _, store, manifest = setup_view(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="lock must be an object"):
        view(store, manifest, "1.4.131", lock=[])


def test_disabled_authoring_placeholder_is_not_a_chain_edge(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"value"})
    write_manifest(manifest, [edge, {"enabled": False, "version": "<由所有者分配>"}])
    assert view(store, manifest).read_raw("a")[0] == b"value"


def test_auto_discovery_excludes_delivery_drafts(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"a": b"official"})
    write_manifest(manifest, [edge])
    draft = dict(edge, archive=edge["archive"].replace("test", "draft"), local_test_only=True)
    write_manifest(active / "manifest-entry-1.4.132.json", [draft])
    from wf.view.chain import resolve_chain
    assert resolve_chain(manifest, [active], "1.4.131", "1.4.132")[0]["names"] == [edge["archive"]]
    # Explicit input remains an explicit choice and must still detect conflicts.
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_chain(manifest, [active], "1.4.131", "1.4.132",
                      [active / "manifest-entry-1.4.132.json"])
