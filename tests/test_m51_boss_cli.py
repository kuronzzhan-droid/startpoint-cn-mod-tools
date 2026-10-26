"""M5.1: an omitted tip follows manifests, and locks stay inside the checkout."""
import json

import pytest

from test_m1_view import patch, setup_view, write_manifest
from wf.boss import cli
from wf.check import main as check_main
from wf.view.manifest import ManifestView


def test_default_tip_follows_enabled_manifest_tail_and_refuses_missing_tail(tmp_path, monkeypatch):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    first = patch(active, "1.4.131", "1.4.237", {"a": b"old"})
    second = patch(active, "1.4.237", "1.4.238", {"a": b"new"})
    disabled = {"version": "1.4.999", "enabled": False}
    write_manifest(manifest, [disabled, second, first])
    view = ManifestView(None, store=store, manifest=manifest, search_dirs=[], manifests=[])
    assert view.tip == "1.4.238" and view.read_raw("a")[0] == b"new"
    write_manifest(manifest, [second])
    with pytest.raises(ValueError, match="chain gap"):
        ManifestView(None, store=store, manifest=manifest, search_dirs=[], manifests=[])


def test_both_boss_clis_forward_unset_tip_and_lock_is_fenced(tmp_path, monkeypatch, capsys):
    from wf.boss.reader import BossReader
    seen = []

    class View:
        def __init__(self, tip, **kwargs):
            seen.append(tip)
        def verify(self):
            pass
        def save_lock(self, target):
            target.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cli, "ManifestView", View)
    monkeypatch.setattr("wf.view.manifest.ManifestView", View)
    monkeypatch.setattr(BossReader, "__init__", lambda self, view: None)
    monkeypatch.setattr(BossReader, "list", lambda self: {})
    monkeypatch.setattr(BossReader, "show", lambda self, quest: {})
    monkeypatch.setattr("wf.rules.boss_cli.check_boss", lambda *a, **kw: [{"status": "满足", "blocking": False}])
    assert cli.main(["list"]) == 0
    assert check_main(["boss", "123"]) == 0
    assert seen == [None, None]
    local = tmp_path / "lock.json"
    assert cli.main(["list", "--write-lock", str(local)]) == 0
    assert json.loads(local.read_text("utf-8")) == {}
    from wf.paths import REPOSITORY
    outside = REPOSITORY.parent / "m51-forbidden-lock.json"
    with pytest.raises(PermissionError, match="outside checkout"):
        cli.main(["list", "--write-lock", str(outside)])
    assert not outside.exists()
