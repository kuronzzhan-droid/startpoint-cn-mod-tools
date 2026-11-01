"""Fault injection for receipt publication, rollback locks, and repeat application."""
import shutil

import pytest

from test_studio_apply import enabled, case
from test_studio_rehearsal import put, snapshot
from wf.studio import apply_io as io, apply_local as local
from wf.studio.rehearsal_io import read_json


def test_reapply_archives_receipt_and_separates_namespaces(enabled):
    root, folder, profile = enabled
    assert local.apply(folder)["ok"]
    assert local.unapply(folder)["ok"]
    receipt_dir = io.receipt_folder(folder, root)
    original = snapshot(receipt_dir)
    assert local.apply(folder)["ok"]
    history = next((receipt_dir.parent / ".history").iterdir())
    assert snapshot(history) == original
    other = folder.parent.parent / "boss/build/delivery"
    other.mkdir(parents=True)
    assert io.receipt_folder(other, root) != receipt_dir
    second = root.with_name("server-two")
    shutil.copytree(root, second)
    config = read_json(profile)
    config["servers"]["second"] = {"root": str(second), "apply_enabled": True}
    put(profile, config)
    assert local.unapply(folder)["ok"]
    shutil.copyfile(root / io.MANIFEST, second / io.MANIFEST)
    assert local.apply(folder, "second")["ok"]
    assert io.receipt_folder(folder, second, "second") != receipt_dir


def test_prepare_failure_cleans_partial_backup_and_allows_retry(enabled, monkeypatch):
    root, folder, _ = enabled
    original = io.atomic_write
    before = snapshot(root)
    def fail(path, raw, **kwargs):
        if path.suffix == ".bin":
            raise OSError("backup storage full")
        original(path, raw, **kwargs)
    monkeypatch.setattr(io, "atomic_write", fail)
    result = local.apply(folder)
    assert not result["ok"] and snapshot(root) == before
    assert not io.receipt_folder(folder, root).exists()
    assert not list(io.APPLIED.rglob(".studio-*"))
    monkeypatch.setattr(io, "atomic_write", original)
    assert local.apply(folder)["ok"]


def test_clean_rollback_can_retry(enabled, monkeypatch):
    root, folder, _ = enabled
    original = io.atomic_write
    def fail(path, raw, **kwargs):
        if path == root / io.MANIFEST:
            raise OSError("manifest busy")
        original(path, raw, **kwargs)
    monkeypatch.setattr(io, "atomic_write", fail)
    before = snapshot(root)
    assert not local.apply(folder)["ok"]
    assert snapshot(root) == before
    assert read_json(io.receipt_folder(folder, root) / "receipt.json")["status"] == "rolled-back"
    monkeypatch.setattr(io, "atomic_write", original)
    assert local.apply(folder)["ok"]


@pytest.mark.parametrize("undo,receipt_failure", [(False, False), (False, True), (True, False), (True, True)])
def test_incomplete_rollback_keeps_lock_and_failure_receipt(enabled, monkeypatch, undo, receipt_failure):
    root, folder, _ = enabled
    put(root / "assets/rows.json", {"old": 1})
    put(folder / "server/assets/rows.json", {"new": 2})
    if undo:
        assert local.apply(folder)["ok"]
    original = io.atomic_write
    broken = False
    def fail(path, raw, **kwargs):
        nonlocal broken
        final_status = b'"status": "unapplied"' if undo else b'"status": "applied"'
        if receipt_failure and path.name == "receipt.json" and final_status in raw and not broken:
            broken = True
            raise OSError("receipt publication failure")
        if not receipt_failure and path == root / "assets/rows.json" and not broken:
            original(path, raw, **kwargs)
            broken = True
            raise OSError("failure after data write")
        if broken and path.is_relative_to(root):
            raise OSError("rollback file locked")
        original(path, raw, **kwargs)
    monkeypatch.setattr(io, "atomic_write", fail)
    result = (local.unapply if undo else local.apply)(folder)
    assert not result["ok"] and broken
    assert list((io.APPLIED / ".locks").glob("*.lock"))
    receipt = read_json(io.receipt_folder(folder, root) / "receipt.json")
    assert receipt["status"] == "rollback-failed"
    assert receipt["error"]
    assert any(s["status"] == "failed" for s in receipt["unapplySteps" if undo else "steps"])
    monkeypatch.setattr(io, "atomic_write", original)
    assert "已有应用事务" in local.apply(folder)["error"]


def test_unapply_receipt_reverse_checks_skipped_zip(enabled, monkeypatch):
    root, folder, _ = enabled
    source = next(folder.glob("*.zip"))
    existing = root / "assets/asset-patch/active" / source.name
    existing.write_bytes(source.read_bytes())
    assert local.apply(folder)["ok"]
    original = io.atomic_write
    def fail(path, raw, **kwargs):
        if path.name == "receipt.json" and b'"status": "unapplied"' in raw:
            existing.write_bytes(b"external concurrent bytes")
            raise OSError("receipt failed with concurrent zip drift")
        original(path, raw, **kwargs)
    monkeypatch.setattr(io, "atomic_write", fail)
    result = local.unapply(folder)
    assert not result["ok"]
    assert existing.read_bytes() == b"external concurrent bytes"
    assert list((io.APPLIED / ".locks").glob("*.lock"))
    receipt = read_json(io.receipt_folder(folder, root) / "receipt.json")
    assert receipt["status"] == "rollback-failed"
    assert "摘要变化" in str(receipt["unapplySteps"])
