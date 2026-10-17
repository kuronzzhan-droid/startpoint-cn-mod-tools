"""Baseline drift must fail before a frozen recipe can package data."""
import hashlib
import zipfile

import pytest

from wf.view.base149 import HistoricalView
from wf.view.balance_inputs import verify_balance_view


def _zip(path, value=b"overlay"):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("production/upload/aa/overlay", value)


def _locked_view(tmp_path):
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir(); store.mkdir()
    archive = active / "pinball-1.4.131-1.4.132-1-data-local.zip"
    _zip(archive)
    member = "production/upload/bb/base"
    source = store / "bb/base"
    source.parent.mkdir(); source.write_bytes(b"base")
    lock = {"format": 1, "tip": 132,
            "active_zips": [{"name": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}],
            "store_members": {member: hashlib.sha256(b"base").hexdigest()}}
    view = HistoricalView(active=active, store=store, tip=132, store_member_sha256=lock["store_members"])
    return view, lock, archive, source


def test_locked_view_accepts_exact_active_and_store(tmp_path):
    view, lock, _, _ = _locked_view(tmp_path)
    assert view.read_member("production/upload/bb/base") == (b"base", "store131")
    result = verify_balance_view(view, lock)
    assert result["active_zip_count"] == result["store_member_count"] == 1


@pytest.mark.parametrize("change", ["add", "remove", "content"])
def test_active_drift_is_rejected(tmp_path, change):
    view, lock, archive, _ = _locked_view(tmp_path)
    if change == "add":
        _zip(view.active / "pinball-1.4.131-1.4.132-2-extra-local.zip")
    elif change == "remove":
        archive.unlink()
    else:
        _zip(archive, b"changed")
    with pytest.raises(ValueError, match="active ZIP .*drift"):
        verify_balance_view(view, lock)


def test_store_drift_and_unrecorded_fallback_are_rejected(tmp_path):
    view, lock, _, source = _locked_view(tmp_path)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="store131 member digest drift"):
        verify_balance_view(view, lock)
    with pytest.raises(ValueError, match="store131 member digest drift"):
        view.read_member("production/upload/bb/base")
    with pytest.raises(ValueError, match="unlocked store131 member"):
        view.read_member("production/upload/cc/unrecorded")


def test_empty_store_lock_denies_every_fallback(tmp_path):
    view, lock, _, _ = _locked_view(tmp_path)
    lock["store_members"] = view.store_member_sha256 = {}
    assert verify_balance_view(view, lock)["store_member_count"] == 0
    with pytest.raises(ValueError, match="unlocked store131 member"):
        view.read_member("production/upload/bb/base")
