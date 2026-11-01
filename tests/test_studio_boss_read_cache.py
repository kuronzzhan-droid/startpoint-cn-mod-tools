"""Read caching keeps content drift, negative reads and five-state evidence visible."""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from wf.studio import read_cache


class View:
    def __init__(self):
        self.files = {"present": b"first"}
        self.origin = "fixture"

    def read_raw(self, logical):
        if logical not in self.files:
            raise FileNotFoundError(logical)
        return self.files[logical], self.origin


@pytest.fixture
def memo(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    source = SimpleNamespace(view=View(), version="1.4.1")
    store = SimpleNamespace(root=tmp_path / "drafts/boss")
    return read_cache.BossReadMemo(source, store)


def test_studio_boss_memo_content_origin_missing_and_version_are_inputs(memo):
    calls = []

    def compute(source):
        calls.append(1)
        return {"raw": source.raw("present"), "missing": source.raw("missing"),
                "checks": [{"status": value} for value in
                           ("满足", "问题", "待验证", "不适用", "未执行")]}

    first = memo.get("boss", compute)
    assert memo.get("boss", compute) == first
    assert len(calls) == 1
    first["checks"].clear()
    assert len(memo.get("boss", compute)["checks"]) == 5
    memo.source.view.files["present"] = b"other"
    assert memo.get("boss", compute)["raw"] == b"other"
    memo.source.view.files["missing"] = b"added"
    assert memo.get("boss", compute)["missing"] == b"added"
    memo.source.view.origin = "new-layer"
    memo.get("boss", compute)
    memo.source.version = "1.4.2"
    memo.get("boss", compute)
    assert len(calls) == 5


@pytest.mark.parametrize("relative", ["drafts/boss/7/changeset.json",
                                      "drafts/weapons/8/changeset.json", "schemas/rules.json"])
def test_studio_boss_memo_draft_and_spec_content_invalidates(memo, tmp_path, relative):
    calls = []

    def compute(_):
        calls.append(1)
        return {"checks": []}

    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("first", encoding="utf-8")
    memo.get("boss", compute)
    stat = path.stat()
    path.write_text("other", encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    memo.get("boss", compute)
    assert len(calls) == 2


def test_studio_boss_memo_tracks_server_bytes_without_writing(memo, tmp_path):
    server = tmp_path / "read-only-input"
    server.mkdir()
    path = server / "rewards.json"
    path.write_bytes(b"{}")
    calls = []

    def compute(source):
        calls.append(1)
        raw = path.read_bytes()
        source.note_server(SimpleNamespace(server_dir=server,
                                           server_original={"rewards.json": raw}))
        return json.loads(raw)

    assert memo.get("boss", compute) == {}
    assert memo.get("boss", compute) == {}
    path.write_bytes(b'{"new":1}')
    assert memo.get("boss", compute) == {"new": 1}
    assert len(calls) == 2


def test_studio_boss_memo_retries_a_mid_read_change(memo):
    calls = []

    def compute(source):
        calls.append(1)
        raw = source.raw("present")
        if len(calls) == 1:
            memo.source.view.files["present"] = b"other"
        return raw

    assert memo.get("boss", compute) == b"other"
    assert len(calls) == 2


def test_studio_boss_memo_manifest_change_refuses_stale_view(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("first", encoding="utf-8")
    source = SimpleNamespace(view=View(), version="1.4.1")
    source.view.manifest = manifest
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))
    memo.get("boss", lambda _: "old")
    manifest.write_text("other", encoding="utf-8")
    with pytest.raises(ValueError, match="清单已变化"):
        memo.get("boss", lambda _: "old")


def test_studio_boss_memo_detects_new_automatically_discovered_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    source = SimpleNamespace(view=View(), version="1.4.1")
    source.view.search_dirs = [tmp_path]
    source.view.manifests = None
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))
    memo.get("boss", lambda _: "old")
    (tmp_path / "manifest-new.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="清单已变化"):
        memo.get("boss", lambda _: "old")


def test_studio_boss_explicit_empty_manifests_disable_discovery(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    source = SimpleNamespace(view=View(), version="1.4.1")
    source.view.search_dirs = [tmp_path]
    source.view.manifests = []
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))
    assert memo.get("boss", lambda _: "same") == "same"
    (tmp_path / "manifest-unrelated.json").write_text("{}", encoding="utf-8")
    assert memo.get("boss", lambda _: "unexpected recomputation") == "same"


def test_studio_boss_manifest_entry_fragments_are_not_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    source = SimpleNamespace(view=View(), version="1.4.1")
    source.view.search_dirs = [tmp_path]
    source.view.manifests = None
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))
    assert memo.get("boss", lambda _: "same") == "same"
    (tmp_path / "manifest-entry-fragment.json").write_text("{}", encoding="utf-8")
    assert memo.get("boss", lambda _: "unexpected recomputation") == "same"


def test_studio_boss_refused_store_history_is_not_proof_of_absence(tmp_path, monkeypatch):
    import zipfile
    import wf_quest_lib as codec
    from wf.boss.provenance import BossTables
    from wf.view.base149 import member
    monkeypatch.setattr(read_cache, "REPOSITORY", tmp_path)
    logical = "master/history.orderedmap"
    raw = codec.build_node({"entry": "value"})
    archive = tmp_path / "history.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(member(logical), raw)

    class HistoryView(View):
        refused = True

        def read_store_member(self, name):
            if self.refused:
                raise KeyError("baseline not enrolled")
            raise FileNotFoundError(name)

    view = HistoryView()
    view.zips = [archive]
    view.files = {logical: raw}
    plain = BossTables(view).citation(logical, ["entry"])
    source = SimpleNamespace(view=view, version="test")
    memo = read_cache.BossReadMemo(source, SimpleNamespace(root=tmp_path / "drafts"))

    def compute(source):
        return BossTables(source).citation(logical, ["entry"])

    assert memo.get("boss", compute) == plain
    assert memo.get("boss", compute)["scope"] == "table"
    view.refused = False
    changed = memo.get("boss", compute)
    assert changed["scope"] == "leaf" and changed["layer"] == archive.name


def test_studio_boss_memo_historical_zip_changes_with_same_final_raw_invalidate(memo, tmp_path):
    import zipfile
    from wf.view.base149 import member
    archive = tmp_path / "history.zip"
    name = member("present")

    def write(raw):
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(name, raw)

    write(b"first")
    memo.source.view.zips = [archive]
    calls = []

    def compute(source):
        calls.append(1)
        return source.view.history_digest("present"), source.raw("present")

    initial = memo.get("boss", compute)
    assert memo.get("boss", compute) == initial
    stat = archive.stat()
    write(b"other")
    os.utime(archive, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    updated = memo.get("boss", compute)
    assert updated[0] != initial[0] and updated[1] == initial[1]
    assert len(calls) == 2


def test_studio_boss_timeline_filter_preserves_original_move_and_checks():
    from wf.studio.boss_routes import BossRoutes
    moves = [{"name": "wave/A/state/battle/a", "enemyCode": "A", "slot": 2},
             {"name": "wave/B/state/battle/a", "enemyCode": "B", "slot": 2},
             {"name": "wave/A/state/battle/b", "enemyCode": "A", "slot": 3}]
    result = {"questId": "q", "checks": [{"status": "待验证"}],
              "data": {"moves": moves, "runtime": "未执行", "note": "original"}}
    routes = BossRoutes.__new__(BossRoutes)
    routes.editor = SimpleNamespace(inspect=lambda *_: result)
    selected = json.loads(routes.timeline_summary({"path": ["battle/a"], "enemyCode": ["A"]}, "q").body)
    assert selected == {**result["data"], "moves": [moves[0]], "questId": "q", "checks": result["checks"]}
    fallback = json.loads(routes.timeline_summary({"path": ["unmatched"], "enemyCode": ["A"],
                                                  "slot": ["3"]}, "q").body)
    assert fallback["moves"] == [moves[2]]
    assert result["data"]["moves"] == moves
