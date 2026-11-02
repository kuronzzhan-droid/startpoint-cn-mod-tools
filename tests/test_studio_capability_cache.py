"""Capability memo validity uses input contents, including missing evidence."""
import json
import os

import pytest

from wf.studio import capability_cache as cache


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    write(tmp_path / "client_profiles.json", {"profiles": {"test": {
        "provides": "primary.json", "provides_fallback": "fallback.json"}}})
    write(tmp_path / "fallback.json", {"evidence": "old"})
    write(tmp_path / "schemas/capability.schema.json", {"type": "object"})
    spec = tmp_path / "wf/caps/example.yml"
    spec.parent.mkdir(parents=True)
    spec.write_text("id: first", encoding="utf-8")
    monkeypatch.setattr(cache, "REPOSITORY", tmp_path)
    cache._CACHE.clear()
    calls = []

    def query(**args):
        calls.append(args)
        return {"capabilities": ["example"], "checks": [
            {"status": state, "blocking": state == "问题"}
            for state in ("满足", "问题", "待验证", "不适用", "未执行")]}

    monkeypatch.setattr(cache, "query_requirements", query)
    return tmp_path, calls


def test_studio_requirements_reuses_exact_answer_without_mutable_aliases(inputs):
    _, calls = inputs
    before = cache.cached_requirements(kinds=["1"])
    assert cache.cached_requirements(kinds=["1"]) == before
    assert len(calls) == 1
    before["checks"].clear()
    assert len(cache.cached_requirements(kinds=["1"])["checks"]) == 5
    cache.cached_requirements(kinds=["2"])
    assert len(calls) == 2


@pytest.mark.parametrize("relative", ["wf/caps/example.yml", "fallback.json",
                                      "schemas/capability.schema.json"])
def test_studio_requirements_content_change_invalidates_with_same_mtime(inputs, relative):
    root, calls = inputs
    path = root / relative
    before = cache.cached_requirements()
    stat = path.stat()
    raw = path.read_bytes()
    # Whitespace changes are enough to prove the key includes real bytes;
    # validity must not depend on whether a parse would produce the same tree.
    path.write_bytes(raw + b" ")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert cache.cached_requirements() == before
    assert len(calls) == 2


def test_studio_requirements_absent_primary_appearance_invalidates(inputs):
    root, calls = inputs
    cache.cached_requirements()
    write(root / "primary.json", {"evidence": "new"})
    cache.cached_requirements()
    assert len(calls) == 2


def test_studio_requirements_profile_and_registration_changes_invalidate(inputs):
    root, calls = inputs
    cache.cached_requirements()
    write(root / "work/local-clients/new/registration.json", {
        "profile": {"provides": "local.json"}})
    write(root / "local.json", {"evidence": "new"})
    cache.cached_requirements()
    write(root / "local.json", {"evidence": "changed"})
    cache.cached_requirements()
    write(root / "client_profiles.json", {"profiles": {}})
    cache.cached_requirements()
    assert len(calls) == 4


def test_studio_requirements_does_not_reuse_success_after_invalid_input(inputs, monkeypatch):
    root, _ = inputs
    cache.cached_requirements()
    write(root / "fallback.json", {"evidence": "changed"})

    def invalid(**_):
        raise ValueError("invalid evidence")

    monkeypatch.setattr(cache, "query_requirements", invalid)
    with pytest.raises(ValueError, match="invalid evidence"):
        cache.cached_requirements()


def test_studio_capability_validator_reloads_schema_bytes(tmp_path, monkeypatch):
    from wf.caps import registry
    monkeypatch.setattr(registry, "REPOSITORY", tmp_path)
    schema = write(tmp_path / "schemas/capability.schema.json", {"type": "object"})
    assert not list(registry._validator().iter_errors({}))
    write(schema, {"type": "array"})
    assert list(registry._validator().iter_errors({}))


def test_studio_draft_schema_reloads_content(tmp_path, monkeypatch):
    from wf.studio import drafts
    schema = write(tmp_path / "draft.json", {"type": "object"})
    monkeypatch.setattr(drafts, "SCHEMA_PATH", schema)
    assert not drafts.schema_errors({})
    write(schema, {"type": "array"})
    assert drafts.schema_errors({})


def test_studio_profile_ui_refreshes_all_cached_input_layers(inputs, monkeypatch):
    from types import SimpleNamespace
    from wf.studio.client_profile_view import ClientProfileView
    from wf.studio.client_profile_cache import fresh_inputs
    from wf.studio import client_profile_cache
    root, _ = inputs
    monkeypatch.setattr(client_profile_cache, "_inputs", lambda _: cache.input_digest())
    view = ClientProfileView(SimpleNamespace())
    calls = []

    @fresh_inputs
    def read(view):
        if view._registry is None:
            calls.append(1)
            view._registry = {"value": len(calls)}
            view._clients = {"value": len(calls)}
            view._compat["value"] = len(calls)
        return view._registry, view._clients, view._compat

    assert read(view) == read(view)
    write(root / "fallback.json", {"evidence": "updated"})
    registry, clients, compat = read(view)
    assert registry["value"] == clients["value"] == compat["value"] == 2


def test_studio_perf_registry_and_mirror_recheck_same_stat_content(tmp_path, monkeypatch):
    from wf.studio import perf
    from wf.caps import registry
    monkeypatch.setattr(registry, "__file__", str(tmp_path / "registry.py"))
    monkeypatch.setattr(registry, "REPOSITORY", tmp_path)
    write(tmp_path / "schemas/capability.schema.json", {})
    spec = tmp_path / "cap.yml"
    spec.write_bytes(b"first")
    monkeypatch.setattr(registry, "load_registry", lambda _: {"content": spec.read_bytes()})
    before = perf.registry()
    stat = spec.stat()
    spec.write_bytes(b"other")
    os.utime(spec, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert perf.registry() != before
    assert perf.file_bytes(spec) == b"other"
    spec.write_bytes(b"third")
    os.utime(spec, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert perf.file_bytes(spec) == b"third"
