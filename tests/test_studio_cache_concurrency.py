"""Loaded-chain integrity, independent reads and visible warmup diagnostics."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from types import SimpleNamespace

import pytest

from wf.studio.boss import BossEditor
from wf.studio.boss_store import BossDraftStore
from wf.studio import read_cache
from wf.studio.mode_cache import ModeReadCache
from wf.studio.prewarm import warm_read
from wf.studio.server import json_response
from wf.studio.source import StudioSource
from test_m1_view import patch, setup_view, view, write_manifest
from test_studio_boss_read_cache import View


def make_memo(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    return read_cache.BossReadMemo(SimpleNamespace(view=View(), version="fixture"),
                                   SimpleNamespace(root=tmp_path / "drafts"))


@pytest.mark.parametrize("before_editor", [False, True])
def test_studio_boss_first_read_rejects_manifest_changed_after_view_load(tmp_path, monkeypatch, before_editor):
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"present": b"old"})
    write_manifest(manifest, [edge])
    source = StudioSource(view(store, manifest))
    if before_editor:
        write_manifest(manifest, [])
    editor = BossEditor(source, store=BossDraftStore(tmp_path / "drafts"))
    if not before_editor:
        write_manifest(manifest, [])
    with pytest.raises(ValueError, match="chain gap"):
        editor.read("unused")


def test_studio_boss_chain_advance_recomputes_loaded_view_and_keeps_stale_guard(tmp_path, monkeypatch):
    from wf.studio.freshness import freshness
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"present": b"old"})
    write_manifest(manifest, [edge])
    source = StudioSource(view(store, manifest))
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))
    calls = []
    def compute(traced):
        calls.append(True)
        return traced.raw("present")
    assert memo.get("boss", compute) == b"old"
    later = patch(active, "1.4.132", "1.4.133", {"present": b"new"})
    write_manifest(manifest, [edge, later])
    assert memo.get("boss", compute) == b"old"
    assert memo.get("boss", compute) == b"old"
    assert len(calls) == 2
    assert freshness(source)["stale"] is True
    source.view.verify()  # Full verification still accepts the pinned old chain.
    write_manifest(manifest, [dict(edge, enabled=False), later])
    with pytest.raises(ValueError, match="chain gap"):
        memo.get("boss", compute)


def test_studio_manifest_signature_binds_the_bytes_actually_verified(tmp_path, monkeypatch):
    from wf.studio.read_manifest import ReadManifestInputs
    active, store, manifest = setup_view(tmp_path, monkeypatch)
    edge = patch(active, "1.4.131", "1.4.132", {"present": b"old"})
    write_manifest(manifest, [edge])
    loaded = view(store, manifest)
    write_manifest(manifest, [])
    inputs = ReadManifestInputs(loaded)
    original, calls = loaded.verify_chain, []
    def switch_before_validation():
        calls.append(True)
        if len(calls) == 1:
            write_manifest(manifest, [edge])
        return original()
    monkeypatch.setattr(loaded, "verify_chain", switch_before_validation)
    inputs.current()
    assert len(calls) == 2
    write_manifest(manifest, [])
    with pytest.raises(ValueError, match="chain gap"):
        inputs.current()


def test_studio_boss_different_keys_compute_concurrently(tmp_path, monkeypatch):
    memo = make_memo(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()
    def slow(_):
        started.set()
        assert release.wait(5)
        return "slow"
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(memo.get, "detail", slow)
        assert started.wait(5)
        try:
            assert pool.submit(memo.get, "section", lambda _: "fast").result(2) == "fast"
        finally:
            release.set()
        assert first.result(5) == "slow"


def test_studio_boss_same_key_is_single_flight_and_editor_memo_is_eager(tmp_path, monkeypatch):
    source = SimpleNamespace(view=View(), version="fixture")
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    editor = BossEditor(source, store=BossDraftStore(tmp_path / "drafts"))
    assert editor._read_memo is not None
    started, release, calls = threading.Event(), threading.Event(), []
    def compute(self, quest, section):
        calls.append(True)
        started.set()
        assert release.wait(5)
        return {"quest": quest}
    monkeypatch.setattr(BossEditor, "_read_current", compute)
    with ThreadPoolExecutor(4) as pool:
        results = [pool.submit(editor.read, "same") for _ in range(4)]
        assert started.wait(5)
        release.set()
        assert [r.result(5) for r in results] == [{"quest": "same"}] * 4
    assert len(calls) == 1
    assert not editor._read_memo.flights._entries


def test_studio_mode_new_context_does_not_wait_for_old_warmup():
    memo = ModeReadCache()
    source = SimpleNamespace(version="fixture")
    inputs = SimpleNamespace(source=source, verify=lambda: None)
    started, release = threading.Event(), threading.Event()
    def slow():
        started.set()
        assert release.wait(5)
        return {"spec": "old"}, inputs
    with ThreadPoolExecutor(2) as pool:
        old = pool.submit(memo.get, "five", source, {"spec": "old"}, slow)
        assert started.wait(5)
        try:
            new = pool.submit(memo.get, "five", source, {"spec": "new"},
                              lambda: ({"spec": "new"}, inputs))
            assert new.result(2) == {"spec": "new"}
        finally:
            release.set()
        assert old.result(5) == {"spec": "old"}
    def already_cached():
        pytest.fail("old warmup replaced the newer context cache")
    assert memo.get("five", source, {"spec": "new"}, already_cached) == {"spec": "new"}
    assert not memo._flights._entries


@pytest.mark.parametrize("operation", ["weapon_clone", r"weapon\u005fclone"])
def test_studio_boss_weapon_clone_uses_artifact_content_signature(tmp_path, monkeypatch, operation):
    from wf.studio import capability_cache
    memo = make_memo(tmp_path, monkeypatch)
    artifact = tmp_path / "client.swf"
    artifact.write_bytes(b"first")
    monkeypatch.setattr(capability_cache, "input_digest", lambda _: "spec")
    monkeypatch.setattr(capability_cache, "capability_input_digest", lambda _: artifact.read_bytes())
    draft = tmp_path / "drafts/1/changeset.json"
    draft.parent.mkdir(parents=True)
    draft.write_text('{"operation":"' + operation + '"}', encoding="utf8")
    calls = []
    def compute(_):
        calls.append(True)
        return artifact.read_bytes()
    assert memo.get("weapon", compute) == b"first"
    stamp = artifact.stat()
    artifact.write_bytes(b"other")
    os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert memo.get("weapon", compute) == b"other"
    assert len(calls) == 2


@pytest.mark.parametrize("case", ["exception", "http", "preview"])
def test_studio_warmup_failures_are_visible_and_do_not_prevent_next_task(caplog, case):
    def failed():
        if case == "exception":
            raise ValueError("broken evidence")
        if case == "http":
            return json_response({"error": "broken evidence"}, 400)
        return json_response({"preview": {"ok": False, "blockers": ["broken evidence"]}})
    assert warm_read("fixture", failed) is None
    assert "fixture" in caplog.text and "broken evidence" in caplog.text
    assert warm_read("next", lambda: {"ok": True}) == {"ok": True}
