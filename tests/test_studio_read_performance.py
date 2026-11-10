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


def test_scene_routes_cache_revalidates_inputs_draft_and_server_mirror(tmp_path, monkeypatch):
    from wf.boss import scene as boss_scene, scene_import, scene_spec
    from wf.studio import deliver_bridge, delivery_safety, scene_routes
    from wf.studio.drafts import DraftStore
    from wf.studio.scene_routes import SceneRoutes

    data = {
        member_name("common", "master/event.orderedmap"): b"event-v1",
        member_name("common", "battle/boss.amf3.deflate"): b"boss-v1",
    }
    verify_reads, full_verifies = [], []

    def read_member(name):
        if name not in data:
            raise FileNotFoundError(name)
        return data[name], "fixture"

    source = SimpleNamespace(
        version="1.4.351",
        view=SimpleNamespace(
            read_member=read_member,
            verify_read=lambda: verify_reads.append("read"),
            verify=lambda: full_verifies.append("full"),
        ),
    )
    server_dir = tmp_path / "server"
    (server_dir / "assets").mkdir(parents=True)
    event_file = server_dir / "assets" / "advent_event_quest.json"
    event_file.write_text('{"300097": 1}', encoding="utf8")

    fresh_state = {"latest": "1.4.351", "error": None}
    monkeypatch.setattr(scene_routes, "freshness", lambda _src: dict(fresh_state))

    import_calls, compile_calls = [], []

    def fake_import(read, version):
        import_calls.append(version)
        raw = read("master/event.orderedmap").decode()
        return {
            "id": "hell-pumpkin",
            "sourceVersion": version,
            "event": {"id": "300097"},
            "marker": raw,
        }

    def fake_compile(read, payload, server_dir=None):
        compile_calls.append(copy.deepcopy(payload))
        boss_raw = read("battle/boss.amf3.deflate")
        return {
            "ok": True,
            "canGenerate": True,
            "blockers": [],
            "checks": [],
            "files": {"battle/boss.amf3.deflate": boss_raw},
            "servers": {"advent_event_quest.json": event_file.read_bytes()},
            "serverBefore": {"advent_event_quest.json": "before"},
            "changes": [],
            "marker": payload.get("marker"),
        }

    monkeypatch.setattr(scene_import, "import_hell_pumpkin", fake_import)
    monkeypatch.setattr(boss_scene, "compile_scene", fake_compile)

    app = SimpleNamespace(source=source, ops=SimpleNamespace(store=DraftStore(tmp_path / "drafts")))
    routes = SceneRoutes(app, server_dir=server_dir)

    first = json.loads(routes.read({}, "hell-pumpkin").body)
    second = json.loads(routes.read({}, "hell-pumpkin").body)
    assert first == second
    assert len(import_calls) == 1 and len(compile_calls) == 1
    assert len(verify_reads) == 4  # 2 caches * 2 reads
    assert len(full_verifies) == 0

    # Client byte mutation invalidates import_cache and read_cache
    data[member_name("common", "master/event.orderedmap")] = b"event-v2"
    third = json.loads(routes.read({}, "hell-pumpkin").body)
    assert third["spec"]["marker"] == "event-v2"
    assert third["preview"]["marker"] == "event-v2"
    assert len(import_calls) == 2 and len(compile_calls) == 2

    # Server mirror mutation invalidates read_cache without re-running mother import
    event_file.write_text('{"300097": 2}', encoding="utf8")
    _ = json.loads(routes.read({}, "hell-pumpkin").body)
    assert len(import_calls) == 2 and len(compile_calls) == 3

    # Schema / catalog digest change invalidates caches (Item 7)
    fake_schema = tmp_path / "fake-schema.json"
    fake_schema.write_text('{"v": 1}', encoding="utf8")
    monkeypatch.setattr(scene_spec, "SCHEMA", fake_schema)
    _ = json.loads(routes.read({}, "hell-pumpkin").body)
    assert len(import_calls) == 3 and len(compile_calls) == 4

    # Preview uses read_cache; save and compile_delivery bypass cache and run full verify (Item 3)
    edited = copy.deepcopy(third["payload"])
    edited["marker"] = "draft-edited"
    routes.edit({}, {"payload": edited}, "hell-pumpkin", "preview")
    assert len(compile_calls) == 5 and len(full_verifies) == 0
    routes.edit({}, {"payload": edited}, "hell-pumpkin", "preview")
    assert len(compile_calls) == 5 and len(full_verifies) == 0  # preview hits cache

    routes.edit({}, {"payload": edited, "revision": 0}, "hell-pumpkin", "save")
    assert len(compile_calls) == 6  # save bypassed read_cache and recompiled
    assert len(full_verifies) == 1  # save ran full inputs.verify()

    fourth = json.loads(routes.read({}, "hell-pumpkin").body)
    assert fourth["payload"]["marker"] == "draft-edited"
    assert fourth["preview"]["marker"] == "draft-edited"
    assert len(compile_calls) == 6  # read hit read_cache populated by earlier preview

    # compile_delivery must also bypass read_cache and run full inputs.verify()
    monkeypatch.setattr(routes.deliveries, "baseline_options", lambda: {"baseline_view": object()})
    monkeypatch.setattr(deliver_bridge, "open_baseline", lambda *a, **kw: object())
    monkeypatch.setattr(deliver_bridge, "deliver_compiled", lambda draft, compiled, **kw: {"ok": True})
    monkeypatch.setattr(delivery_safety, "resolve_apks", lambda *a, **kw: [])
    monkeypatch.setattr("wf.caps.profiles.resolve_client", lambda *a, **kw: (None, None))
    delivery_res = routes.deliveries.compile_delivery(
        "hell-pumpkin", from_version="1.4.351", to_version="1.4.352", out=tmp_path / "out_delivery"
    )
    assert delivery_res == {"ok": True}
    assert len(compile_calls) == 7  # compile_delivery bypassed read_cache!
    assert len(full_verifies) >= 2


def test_scene_server_duplicate_top_level_key_blocks_unmodified_mother_and_disables_generate(tmp_path):
    from test_studio_scene_e_fixes import pumpkin_env as make_pumpkin_env
    from wf.boss.scene import compile_scene
    from wf.boss.scene_import import import_hell_pumpkin

    env = make_pumpkin_env.__wrapped__(tmp_path)
    spec = import_hell_pumpkin(env.loader, env.version)
    # Inject duplicate top-level key into event_item_shop_id_map.json while mother spec is unmodified
    dup_json = '{"9730001": {"eventType": 0, "eventId": 300097}, "9730001": {"eventType": 0, "eventId": 300097}}\n'
    (env.server_dir / "assets" / "event_item_shop_id_map.json").write_text(dup_json, encoding="utf-8")

    compiled = compile_scene(env.loader, spec, server_dir=env.server_dir)
    assert compiled["ok"] is False
    assert compiled["canGenerate"] is False
    server_check = next(c for c in compiled["checks"] if c["rule"] == "scene.server")
    assert server_check["blocking"] is True
    assert server_check["status"] == "问题"
    assert "duplicate JSON key" in server_check["message"]


def test_compile_scene_asserts_encoded_table_readback(tmp_path, monkeypatch):
    import wf.text.edit as text_edit
    from test_studio_scene_e_fixes import pumpkin_env as make_pumpkin_env
    from wf.boss.scene import compile_scene
    from wf.boss.scene_import import import_hell_pumpkin

    env = make_pumpkin_env.__wrapped__(tmp_path)
    spec = import_hell_pumpkin(env.loader, env.version)
    spec["trials"][0]["value"] = "18"

    monkeypatch.setattr(text_edit, "_encode", lambda raw, before, current: raw)
    with pytest.raises(ValueError, match="boss table roundtrip mismatch"):
        compile_scene(env.loader, spec, server_dir=env.server_dir)


def test_scene_module_caches_are_frozen_and_hashes_unchanged_after_read_preview_clone(tmp_path, monkeypatch):
    import hashlib
    from test_studio_scene_e_fixes import _routes_for_env, pumpkin_env as make_pumpkin_env
    from wf.boss.behavior_model import _TREE_INFO_CACHE, tree_info
    from wf.boss.behavior_wire import (
        _WIRE_TREE_CACHE,
        _WIRE_TREE_KEYS_BY_ID,
        compress,
        decode_wire_tree,
        write_tree,
    )
    from wf.boss.edit_state import _NODE_CACHE, BossEditState, ReadonlyDict, ReadonlyList
    from wf.boss.scene import _AMF_CACHE
    from wf.boss.scene_server import _JSON_CACHE
    from wf.boss.scene_spec import _SCHEMA_CACHE
    from wf.boss.terrain import _TERRAIN_CACHE
    from wf.rules.boss_common import CandidateView
    from wf.rules.boss_preload import _DSL_TREE_CACHE, DslEvidence
    from wf.rules.multiplayer_inputs import collect_inputs

    env_dir = tmp_path / "env"
    routes_dir = tmp_path / "routes"
    env_dir.mkdir(parents=True, exist_ok=True)
    routes_dir.mkdir(parents=True, exist_ok=True)
    env = make_pumpkin_env.__wrapped__(env_dir)
    routes = _routes_for_env(routes_dir, monkeypatch, env)

    for cache_dict in (
        _NODE_CACHE,
        _WIRE_TREE_CACHE,
        _WIRE_TREE_KEYS_BY_ID,
        _TREE_INFO_CACHE,
        _AMF_CACHE,
        _JSON_CACHE,
        _DSL_TREE_CACHE,
        _TERRAIN_CACHE,
    ):
        cache_dict.clear()

    # Also exercise decode_wire_tree and DslEvidence so all caches have entries
    sample_wire = compress(write_tree(["Command", ["SpawnFunnel", ["Funnel", "f1"]]]))
    wire_tree = decode_wire_tree(sample_wire)
    assert tree_info(wire_tree)[1] == ("f1",)
    action_logical = "battle/action/enemy/action/mod/hell_pumpkin/hp_bgm_p1.action.dsl.amf3.deflate"
    DslEvidence(SimpleNamespace(raw=env.loader)).tree(action_logical)

    # Warm caches with initial read
    first_read = json.loads(routes.read({}, "hell-pumpkin").body)
    assert first_read["preview"]["ok"] is True

    def digest_obj(obj) -> str:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=repr).encode(
            "utf-8", errors="surrogateescape"
        )
        return hashlib.sha256(raw).hexdigest()

    def snapshot_caches():
        snap = {
            "node": {k: digest_obj(v) for k, v in _NODE_CACHE.items()},
            "wire": {k: digest_obj(v) for k, v in _WIRE_TREE_CACHE.items()},
            "amf": {k: digest_obj(v) for k, v in _AMF_CACHE.items()},
            "json": {k: digest_obj(v) for k, v in _JSON_CACHE.items()},
            "dsl": {k: digest_obj(v) for k, v in _DSL_TREE_CACHE.items()},
            "terrain": {k: digest_obj(v) for k, v in _TERRAIN_CACHE.items()},
        }
        if _SCHEMA_CACHE is not None:
            snap["schema"] = {_SCHEMA_CACHE[0]: digest_obj(_SCHEMA_CACHE[1])}
        return snap

    before = snapshot_caches()
    assert all(before[name] for name in ("node", "wire", "amf", "json", "dsl", "terrain"))

    # Verify cached objects and CandidateView.table are frozen (ReadonlyDict / ReadonlyList)
    for cache_dict in (_NODE_CACHE, _WIRE_TREE_CACHE, _AMF_CACHE, _JSON_CACHE, _DSL_TREE_CACHE, _TERRAIN_CACHE):
        for val in cache_dict.values():
            assert isinstance(val, (ReadonlyDict, ReadonlyList))
            with pytest.raises(TypeError, match="read-only"):
                if isinstance(val, dict):
                    val["__mutate__"] = 1
                else:
                    val.append(1)

    state = BossEditState(routes.app.source)
    cv_table = CandidateView(state).table("master/quest/event/advent_event.orderedmap")
    assert isinstance(cv_table, ReadonlyDict)
    with pytest.raises(TypeError, match="read-only"):
        cv_table["__mutate__"] = "x"

    # Run read, preview (unmodified & edited), and clone
    _ = json.loads(routes.read({}, "hell-pumpkin").body)
    payload = copy.deepcopy(first_read["payload"])
    _ = json.loads(routes.edit({}, {"payload": payload}, "hell-pumpkin", "preview").body)
    edited = copy.deepcopy(payload)
    edited["trials"][0]["value"] = "18"
    _ = json.loads(routes.edit({}, {"payload": edited}, "hell-pumpkin", "preview").body)
    cloned = json.loads(routes.clone({}, {"payload": payload, "name": "缓存哈希测试"}, "hell-pumpkin").body)
    assert cloned["preview"]["ok"] is True

    after = snapshot_caches()
    for cache_name, before_entries in before.items():
        after_entries = after[cache_name]
        for k, before_hash in before_entries.items():
            assert k in after_entries, f"{cache_name} lost key"
            assert after_entries[k] == before_hash, f"{cache_name} entry mutated!"

    # Item 6: Candidate table bytes in BossEditState.client must not enter _NODE_CACHE
    node_keys_before = set(_NODE_CACHE.keys())
    state.set_leaf("master/battle/boss/general_boss_state.orderedmap", ["mod_hp_routine", "1", "idle"], "0\n")
    collect_inputs({"enemies": [{"kind": "boss", "table": "master/battle/boss/general_boss.orderedmap",
                                 "code": "mod_hp_boss", "level": 200, "row": ["(None)"] * 43}]}, state)
    assert set(_NODE_CACHE.keys()) == node_keys_before

    # Item 6: _TREE_INFO_CACHE holds no strong reference to tree and evicts with _WIRE_TREE_CACHE
    for val in _TREE_INFO_CACHE.values():
        assert len(val) == 3 and all(isinstance(part, (tuple, frozenset)) for part in val)
    victim_id = id(wire_tree)
    assert victim_id in _TREE_INFO_CACHE
    for i in range(520):
        decode_wire_tree(compress(write_tree(["Command", [f"Evict_{i}"]])))
    assert victim_id not in _TREE_INFO_CACHE
    assert victim_id not in _WIRE_TREE_KEYS_BY_ID

