"""Performance optimizations must preserve content and every integrity check."""
import copy
import gzip
import json
import os
from types import SimpleNamespace

import pytest

from wf.deliver.changeset import member_name
from wf.studio.mode_cache import ModeReadCache
from wf.studio.mode_store import ViewInputs


def test_mode_memo_rechecks_bytes_missing_inputs_and_full_verification():
    data = {member_name("common", "one"): b"first"}
    verified, builds = [], []

    def read(name):
        if name not in data:
            raise FileNotFoundError(name)
        return data[name], "fixture"

    source = SimpleNamespace(version="1.4.999", view=SimpleNamespace(
        read_member=read, verify=lambda: verified.append(True)))
    memo = ModeReadCache()

    def build():
        builds.append(True)
        inputs = ViewInputs(source)
        value = inputs.read("one").decode()
        try:
            optional = inputs.read("optional").decode()
        except FileNotFoundError:
            optional = None
        inputs.verify()
        return {"value": value, "optional": optional, "checks": [
            {"status": s, "blocking": s == "问题"} for s in
            ("满足", "问题", "待验证", "不适用", "未执行")]}, inputs

    def get(context=None):
        return memo.get("five", source, context or {"spec": 1}, build)

    expected = get()
    altered = get()
    altered["checks"].clear()
    assert get() == expected and len(builds) == 1 and len(verified) == 3
    data[member_name("common", "one")] = b"other"  # Same length; no metadata shortcut.
    assert get()["value"] == "other" and len(builds) == 2
    data[member_name("medium", "optional")] = b"new"
    assert get()["optional"] == "new" and len(builds) == 3
    data[member_name("common", "optional")] = b"priority"
    assert get()["optional"] == "priority" and len(builds) == 4
    get({"spec": 2})
    assert len(builds) == 5
    source.version = "1.4.1000"
    get({"spec": 2})
    assert len(builds) == 6


def test_mode_memo_draft_content_and_manifest_context_invalidate(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text('{"hp":1}', encoding="utf8")
    stamp = spec.stat()
    builds = []
    source = SimpleNamespace(version="fixture")
    inputs = SimpleNamespace(source=source, verify=lambda: None)
    memo = ModeReadCache()

    def get(draft, latest):
        context = {"spec": json.loads(spec.read_text()), "draft": draft, "latest": latest}
        def build():
            builds.append(copy.deepcopy(context))
            return context, inputs
        return memo.get("five", source, context, build)

    get({"revision": 1, "payload": 1}, 1)
    get({"revision": 1, "payload": 1}, 1)
    assert len(builds) == 1
    spec.write_text('{"hp":2}', encoding="utf8")
    os.utime(spec, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert get({"revision": 1, "payload": 1}, 1)["spec"] == {"hp": 2}
    get({"revision": 1, "payload": 2}, 1)
    get({"revision": 1, "payload": 2}, 2)
    assert len(builds) == 4


def test_mode_input_reuses_reads_but_never_reuses_verification_bytes():
    reads = []
    data = [b"before"]
    def read(name):
        reads.append(name)
        return data[0], "fixture"
    inputs = ViewInputs(SimpleNamespace(view=SimpleNamespace(read_member=read)))
    assert inputs.read("one") == inputs.read("one") == b"before"
    assert len(reads) == 1
    data[0] = b"after!"
    with pytest.raises(ValueError, match="输入发生变化"):
        inputs.verify()


def test_same_version_different_source_does_not_validate_the_old_view():
    memo = ModeReadCache()
    sources = [SimpleNamespace(version="1.4.999") for _ in range(2)]
    for index, source in enumerate(sources):
        inputs = SimpleNamespace(source=source, verify=lambda: None)
        assert memo.get("five", source, {}, lambda: ({"view": index}, inputs)) == {"view": index}


def test_five_dsl_decode_cache_follows_staged_bytes():
    from wf.tools.boss import five_boss_v2 as f
    logical = f.wf_dsl.dsl_logical("battle/action/test")
    old, new = f.encode_dsl(["ActionDsl", "old"]), f.encode_dsl(["ActionDsl", "new"])
    live = f.Live(lambda _: old)
    assert f.dsl_tree(live, "battle/action/test", {}) == ["ActionDsl", "old"]
    assert f.dsl_tree(live, "battle/action/test", {logical: new}) == ["ActionDsl", "new"]
    assert f.dsl_tree(live, "battle/action/test", {}) == ["ActionDsl", "old"]


def test_archive_discovery_preserves_order_duplicates_and_directory_exclusions(tmp_path):
    from wf.view.archive_index import index_zip_names
    for name in ("a/one.zip", "a/sub/one.zip", "b/one.zip", ".git/one.zip", "node_modules/one.zip"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"zip")
    found = index_zip_names([tmp_path, tmp_path / "a"], {"one.zip"})
    assert found == {"one.zip": [(tmp_path / name).resolve()
                                for name in ("a/one.zip", "a/sub/one.zip", "b/one.zip")]}


def test_archive_hardlink_hash_is_shared_only_within_one_verification(tmp_path, monkeypatch):
    from wf.view import chain
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    name = "pinball-1.4.1-1.4.2-1-test.zip"
    archive = first / name
    archive.write_bytes(b"first bytes")
    os.link(archive, second / name)
    calls, original = [], chain.digest
    def counted(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(chain, "digest", counted)
    edges = [{"names": [name], "integrity": {name: {"sha256": original(archive)}}}]
    chain.resolve_archives(edges, [first, second])
    assert len(calls) == 1
    stamp = archive.stat()
    archive.write_bytes(b"other bytes")
    os.utime(archive, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with pytest.raises(ValueError, match="integrity mismatch"):
        chain.resolve_archives(edges, [first, second])
    assert len(calls) == 2


@pytest.mark.parametrize("header,compressed", [("gzip", True), ("br, gzip;q=0.5", True),
    ("gzip;q=0, *;q=1", False), ("identity", False), ("*", True), ("gzip;q=no", False)])
def test_gzip_negotiation_preserves_json(header, compressed):
    from wf.studio.http_encoding import representation
    raw = json.dumps({"checks": ["满足", "问题", "待验证", "不适用", "未执行"] * 300}).encode()
    body, encoding, varies = representation(raw, "application/json; charset=utf-8", header)
    assert varies and (encoding == "gzip") is compressed
    assert (gzip.decompress(body) if encoding else body) == raw


def test_wiki_compact_preserves_all_visible_data_without_mutating_full():
    from wf.studio.response_projection import wiki_card
    full = {"card": {"name": "fixture", "raw": {"large": "raw evidence"},
        "leader": {"name": "leader", "description": "description", "raw": "large"},
        "stats": {"levels": [{"level": 1, "hp": 2, "atk": 3}], "note": "note"},
        "abilities": [], "skills": [], "portraits": [], "warnings": []}, "readOnly": True}
    saved = copy.deepcopy(full)
    compact = wiki_card(full)
    assert full == saved and "raw" not in compact["card"]
    assert compact["card"]["stats"] == full["card"]["stats"]
    assert compact["card"]["leader"] == {"name": "leader", "description": "description"}
    assert compact["readOnly"] is True


def test_manifest_verify_read_only_escalates_when_zip_stat_changes():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from wf.view.manifest import ManifestView

    with TemporaryDirectory() as root:
        archive = Path(root) / "edge.zip"
        archive.write_bytes(b"x")
        view = ManifestView.__new__(ManifestView)
        view.zips = [archive]
        view._stats = {archive: ManifestView._stat(archive)}
        calls = []
        view.verify_chain = lambda: calls.append("chain")
        view.verify = lambda: calls.append("full")
        view.verify_read()
        assert calls == ["chain"]
        archive.write_bytes(b"xy")
        view.verify_read()
        assert calls == ["chain", "chain", "full"]
