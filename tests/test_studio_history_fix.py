"""Legacy member origins and cross-request history invalidation are content based."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from types import SimpleNamespace
import zipfile

import pytest
import wf_quest_lib as codec

from wf.boss import provenance
from wf.boss.provenance import BossTables
from wf.studio.history_cache import HistoryInputs
from wf.studio import read_cache
from wf.view.base149 import HistoricalView, member


LOGICAL = "master/history-regression.orderedmap"
NAME = member(LOGICAL)
LEGACY = NAME.removeprefix("production/upload/")


def write_archive(path, value, *, legacy=False):
    stat = path.stat() if path.exists() else None
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(LEGACY if legacy else NAME, codec.build_node({"entry": value}))
    if stat is not None:
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def layered_view(tmp_path):
    active, store = tmp_path / "active", tmp_path / "production/upload"
    active.mkdir()
    baseline = store / LEGACY
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(codec.build_node({"entry": "1"}))
    early, final = tmp_path / "legacy.zip", tmp_path / "final.zip"
    write_archive(early, "2", legacy=True)
    write_archive(final, "2")
    return HistoricalView(store=store, active=active, tip=131, extra_zips=[early, final]), baseline


@pytest.mark.parametrize("legacy", [False, True])
def test_studio_history_member_layouts_hash_actual_bytes(tmp_path, legacy):
    archive = tmp_path / "history.zip"
    write_archive(archive, "1", legacy=legacy)
    view = SimpleNamespace(zips=[archive])
    inputs = HistoryInputs(view)
    digest = inputs.digest(LOGICAL)
    assert list(inputs.members(LOGICAL)) == [(archive, codec.build_node({"entry": "1"}))]
    inputs.close()
    assert inputs.current()
    write_archive(archive, "2", legacy=legacy)
    assert not inputs.current()
    fresh = HistoryInputs(view)
    try:
        assert fresh.digest(LOGICAL) != digest
    finally:
        fresh.close()


@pytest.mark.parametrize("duplicate", [False, True])
def test_studio_history_conflicting_archive_rejected_before_and_after_cache(tmp_path, duplicate):
    view, _ = layered_view(tmp_path)
    archive = view.zips[0]
    inputs = HistoryInputs(view)
    inputs.digest(LOGICAL)
    list(inputs.members(LOGICAL))
    inputs.close()
    with zipfile.ZipFile(archive, "a") as package:
        if duplicate:
            with pytest.warns(UserWarning, match="Duplicate name"):
                package.writestr(LEGACY, codec.build_node({"entry": "9"}))
        else:
            package.writestr(NAME, codec.build_node({"entry": "9"}))
    with pytest.raises(ValueError, match="duplicate ZIP member"):
        inputs.current()
    fresh = HistoryInputs(view)
    try:
        with pytest.raises(ValueError, match="duplicate ZIP member"):
            fresh.digest(LOGICAL)
    finally:
        fresh.close()
    with pytest.raises(ValueError, match="duplicate ZIP member"):
        BossTables(view).citation(LOGICAL, ["entry"])


def test_studio_history_legacy_leaf_origin_matches_plain_and_memo_reads(tmp_path, monkeypatch):
    view, _ = layered_view(tmp_path)
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    memo = read_cache.BossReadMemo(SimpleNamespace(view=view, version="1.4.131"),
                                  SimpleNamespace(root=tmp_path / "drafts/boss"))
    calls = []

    def compute(source):
        calls.append(1)
        return BossTables(source).citation(LOGICAL, ["entry"])

    plain = BossTables(view).citation(LOGICAL, ["entry"])
    assert plain["layer"] == "legacy.zip"
    assert memo.get("boss", compute) == plain
    assert memo.get("boss", compute) == plain
    write_archive(view.zips[0], "1", legacy=True)
    changed = memo.get("boss", compute)
    assert changed["layer"] == "final.zip"
    assert changed["table_sha256"] == plain["table_sha256"]
    assert len(calls) == 2


@pytest.mark.parametrize("changed", ["archive", "store"])
def test_studio_plain_histories_never_share_unsigned_input_across_requests(tmp_path, changed):
    view, baseline = layered_view(tmp_path)
    first = BossTables(view)
    assert first.citation(LOGICAL, ["entry"])["layer"] == "legacy.zip"
    if changed == "archive":
        write_archive(view.zips[0], "1", legacy=True)
        expected = "final.zip"
    else:
        stat = baseline.stat()
        baseline.write_bytes(codec.build_node({"entry": "2"}))
        os.utime(baseline, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        expected = "store131"
    second = BossTables(view)
    assert second.histories is not first.histories
    assert second.citation(LOGICAL, ["entry"])["layer"] == expected


def test_studio_signed_histories_build_once_under_concurrent_readers(tmp_path, monkeypatch):
    view, _ = layered_view(tmp_path)
    barrier, started, release = threading.Barrier(8), threading.Event(), threading.Event()
    original, calls, caches = BossTables._build_history, [], []

    def build(self, logical):
        calls.append(logical)
        started.set()
        assert release.wait(5)
        return original(self, logical)

    monkeypatch.setattr(BossTables, "_build_history", build)

    def request(_):
        trace = read_cache._Trace(SimpleNamespace(view=view))
        try:
            tables = BossTables(read_cache._Source(trace))
            caches.append(tables.histories)
            barrier.wait(timeout=5)
            return tables.citation(LOGICAL, ["entry"])
        finally:
            trace.history.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(request, n) for n in range(8)]
        assert started.wait(5)
        release.set()
        results = [future.result(timeout=5) for future in futures]
    assert calls == [LOGICAL]
    assert all(cache is caches[0] for cache in caches)
    assert all(result["layer"] == "legacy.zip" for result in results)


def test_studio_signed_history_locks_do_not_serialize_unrelated_tables():
    cache, barrier = provenance._Histories(), threading.Barrier(2)

    def request(logical):
        def build():
            barrier.wait(timeout=5)
            return {"leaf": logical}
        return cache.get_or_build(logical, (logical, "digest"), build)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request, logical) for logical in ("first", "second")]
        assert [future.result(timeout=5) for future in futures] == [
            {"leaf": "first"}, {"leaf": "second"}]
