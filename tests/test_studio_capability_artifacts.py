"""Client cache regressions use tiny, isolated inputs, never workstation APKs."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading
from types import SimpleNamespace

import pytest

from wf.studio import capability_cache, client_profile_cache
from wf.studio.client_profile_view import ClientProfileView


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    from wf.apk import kinds, local_registry
    from wf.caps import profiles, registry
    from wf import paths

    document = {"source": {"swf_sha256": hashlib.sha256(b"good").hexdigest()}, "provides": []}
    record = {"provides": "provides.json", "evidence": {"swf_sha256": document["source"]["swf_sha256"]}}
    write(tmp_path / "client_profiles.json", {"default_client_profile": "fixture", "profiles": {"fixture": record}})
    write(tmp_path / "provides.json", document)
    config = write(tmp_path / "paths.json", {"wf_root": str(tmp_path), "client_apks": {"fixture": ["client.swf"]}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(config))
    monkeypatch.delenv("WF_ROOT", raising=False)
    for module in (paths, kinds, profiles, local_registry, capability_cache):
        monkeypatch.setattr(module, "REPOSITORY", tmp_path)
    monkeypatch.setattr(registry, "load_registry", lambda *args: {})
    monkeypatch.setattr(profiles, "read_client", lambda path, **kwargs: json.loads(path.read_text("utf-8")))
    monkeypatch.setattr(kinds, "_compare", lambda report, *args: report)
    checks = []

    def inspect(path, *, expected_sha256):
        raw = path.read_bytes()
        checks.append(raw)
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected_sha256:
            raise kinds.SwfHashMismatch("fixture SWF hash mismatch")
        return {"source": {"swf_sha256": actual}, "tables": {
            "ability": {"instant_content": {"kinds": ["1"]}}}, "mismatches": []}

    monkeypatch.setattr(kinds, "inspect_swf", inspect)
    from wf.caps.kind_compat import check_kind_sites
    monkeypatch.setattr("wf.caps.compat.check_compat", lambda requires, provides, registry:
                        check_kind_sites(requires["requires"], provides, registry))
    view = ClientProfileView(SimpleNamespace())
    site = {"table": "ability", "block": "instant_content", "kind": "1"}
    return SimpleNamespace(root=tmp_path, config=config, view=view, record=record,
                           document=document, checks=checks,
                           read=lambda: view.compat([], sites=[site])["fixture"])


def test_studio_kind_cache_tracks_missing_created_replaced_and_removed_artifact(fixture):
    case = fixture
    assert not case.read()["compatible"]
    artifact = case.root / "client.swf"
    artifact.write_bytes(b"good")
    assert case.read()["compatible"]
    assert case.read()["compatible"] and len(case.checks) == 1
    stamp = artifact.stat()
    artifact.write_bytes(b"evil")
    os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert not case.read()["compatible"] and len(case.checks) == 2
    artifact.write_bytes(b"good")
    assert case.read()["compatible"]
    artifact.unlink()
    assert not case.read()["compatible"]


def test_studio_kind_cache_nonfile_alternative_does_not_hide_valid_candidate(fixture):
    case = fixture
    case.root.joinpath("client.swf").write_bytes(b"good")
    case.root.joinpath("directory.apk").mkdir()
    write(case.config, {"wf_root": str(case.root), "client_apks": {
        "fixture": ["client.swf", "directory.apk"]}})
    assert case.read()["compatible"]


def test_studio_kind_cache_nonfile_becoming_readable_invalidates(fixture):
    case = fixture
    artifact = case.root / "client.swf"
    artifact.mkdir()
    assert not case.read()["compatible"]
    artifact.rmdir()
    artifact.write_bytes(b"good")
    assert case.read()["compatible"]


def test_studio_kind_cache_bad_provides_source_reports_validation_error(fixture, monkeypatch):
    from wf.caps import profiles
    from wf.deliver.changeset import validate_document
    case = fixture
    write(case.root / "provides.json", {"source": ["malformed"], "provides": []})
    def read_client(path, **kwargs):
        document = json.loads(path.read_text("utf-8"))
        validate_document(document, "provides.schema.json")
        return document
    monkeypatch.setattr(profiles, "read_client", read_client)
    result = case.read()
    assert result["compatible"] is False
    assert result["error"] and not case.checks


def test_studio_kind_cache_tracks_path_profile_and_environment_changes(fixture, monkeypatch):
    case = fixture
    (case.root / "client.swf").write_bytes(b"good")
    assert case.read()["compatible"]
    replacement = case.root / "other"
    replacement.mkdir()
    (replacement / "client.swf").write_bytes(b"evil")
    monkeypatch.setenv("WF_ROOT", str(replacement))
    assert not case.read()["compatible"]
    monkeypatch.delenv("WF_ROOT")
    assert case.read()["compatible"]
    write(case.config, {"wf_root": str(replacement), "client_apks": {"fixture": ["client.swf"]}})
    assert not case.read()["compatible"]
    alternate = write(case.root / "alternate.json", {"wf_root": str(case.root), "client_apks": {"fixture": ["client.swf"]}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(alternate))
    assert case.read()["compatible"]


def test_studio_kind_cache_recovers_after_default_path_profile_appears(fixture, monkeypatch):
    case = fixture
    monkeypatch.delenv("WF_PATHS_PROFILE")
    case.root.joinpath("client.swf").write_bytes(b"good")
    assert not case.read()["compatible"]
    write(case.root / "profiles/local.json", {
        "wf_root": str(case.root), "client_apks": {"fixture": ["client.swf"]}})
    assert case.read()["compatible"]


def test_studio_apk_fingerprint_uses_contents_even_with_identical_stat(fixture):
    case = fixture
    write(case.config, {"wf_root": str(case.root), "client_apks": {"fixture": ["client.apk"]}})
    artifact = case.root / "client.apk"
    artifact.write_bytes(b"first APK bytes")
    before = capability_cache.capability_input_digest()
    stamp = artifact.stat()
    artifact.write_bytes(b"other APK bytes")
    os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert capability_cache.capability_input_digest() != before


@pytest.mark.parametrize("source", ["source", "swf", "swf_path", "provides_fallback"])
def test_studio_artifact_digest_covers_every_evidence_path(fixture, source):
    case = fixture
    artifact = case.root / "direct.swf"
    if source == "source":
        case.document["source"]["path"] = "${WF_ROOT}/direct.swf"
        write(case.root / "provides.json", case.document)
    elif source == "provides_fallback":
        case.record["provides_fallback"] = "fallback.json"
        write(case.root / "fallback.json", {"source": {"path": "direct.swf"}})
    else:
        case.record["evidence"][source] = "direct.swf"
    write(case.root / "client_profiles.json", {"profiles": {"fixture": case.record}})
    missing = capability_cache.capability_input_digest()
    artifact.write_bytes(b"good")
    present = capability_cache.capability_input_digest()
    stamp = artifact.stat()
    artifact.write_bytes(b"evil")
    os.utime(artifact, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    changed = capability_cache.capability_input_digest()
    assert missing != present != changed


def test_studio_cached_api_containers_are_independent(fixture, monkeypatch):
    from wf.studio import client_profile_view, drafts
    case = fixture
    case.root.joinpath("client.swf").write_bytes(b"good")
    first = case.read()
    first["pending"].append({"bad": True})
    first["compatible"] = False
    assert case.read()["compatible"] and not case.read()["pending"]
    clients = case.view.clients()
    clients["fixture"]["document"]["source"]["swf_sha256"] = "bad"
    assert case.view.clients()["fixture"]["document"]["source"]["swf_sha256"] != "bad"
    monkeypatch.setattr("wf.caps.registry.load_registry", lambda: {"cap": {"patches": [1]}})
    case.view._registry = None
    case.view.registry()["cap"]["patches"].append(2)
    assert case.view.registry()["cap"]["patches"] == [1]
    report = write(case.root / "report.json", {"profiles": {}, "snapshots": [{"summary": {"a": [1]}}]})
    monkeypatch.setattr(client_profile_view, "COMPAT_REPORT", report)
    monkeypatch.setattr(client_profile_view, "REPOSITORY", case.root)
    case.view._load_report()["summary"]["a"].append(2)
    assert case.view._load_report()["summary"]["a"] == [1]
    schema = write(case.root / "schema.json", {"properties": {"a": {"enum": [1]}}})
    monkeypatch.setattr(drafts, "SCHEMA_PATH", schema)
    drafts.schema()["properties"]["a"]["enum"].append(2)
    assert drafts.schema()["properties"]["a"]["enum"] == [1]


def test_studio_slow_capability_operation_does_not_hold_other_operations(fixture):
    entered, release = threading.Event(), threading.Event()

    @client_profile_cache.fresh_inputs
    def slow(view):
        entered.set()
        assert release.wait(5)
        return "slow"

    @client_profile_cache.fresh_inputs
    def quick(view):
        return "quick"

    with ThreadPoolExecutor(2) as pool:
        pending = pool.submit(slow, fixture.view)
        assert entered.wait(5)
        try:
            assert pool.submit(quick, fixture.view).result(timeout=3) == "quick"
        finally:
            release.set()
        assert pending.result(timeout=3) == "slow"


def test_studio_stale_inflight_capability_result_cannot_poison_new_generation(fixture, monkeypatch):
    generation = ["old"]
    monkeypatch.setattr(client_profile_cache, "_inputs", lambda _: generation[0])
    entered, release = threading.Event(), threading.Event()

    @client_profile_cache.fresh_inputs
    def read(view):
        current = generation[0]
        if current == "old":
            entered.set()
            assert release.wait(5)
        view._compat["answer"] = current
        return current

    with ThreadPoolExecutor(2) as pool:
        pending = pool.submit(read, fixture.view)
        assert entered.wait(5)
        generation[0] = "new"
        try:
            assert pool.submit(read, fixture.view).result(timeout=3) == "new"
        finally:
            release.set()
        assert pending.result(timeout=3) == "new"
    assert fixture.view._compat["answer"] == "new"


def test_studio_artifact_changed_during_check_is_rechecked_before_return(fixture, monkeypatch):
    from wf.apk import kinds
    case = fixture
    artifact = case.root / "client.swf"
    artifact.write_bytes(b"good")
    inspect = kinds.inspect_swf
    entered, release = threading.Event(), threading.Event()

    def slow(path, **kwargs):
        result = inspect(path, **kwargs)
        entered.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(kinds, "inspect_swf", slow)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(case.read)
        assert entered.wait(5)
        artifact.write_bytes(b"evil")
        release.set()
        assert not pending.result(timeout=3)["compatible"]
    assert not case.read()["compatible"]


def test_studio_catalog_only_operations_do_not_read_unrelated_artifacts(fixture, monkeypatch):
    def unexpected():
        raise AssertionError("catalog-only checks must not inspect actual binaries")

    monkeypatch.setattr(client_profile_cache, "_artifacts", unexpected)
    assert fixture.view.clients()
    assert fixture.view.registry() == {}
    assert fixture.view.compat([])["fixture"]["compatible"]
