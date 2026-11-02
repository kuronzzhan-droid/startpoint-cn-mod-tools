"""Opening desk stays offline and reports missing evidence without synthetic optimism."""
import hashlib
import json
from types import SimpleNamespace
import zipfile

import pytest

from wf.studio.drafts import DraftError
from wf.studio.opening_routes import OpeningRoutes, opening_plan


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def files(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def case(tmp_path, monkeypatch):
    from wf.caps import profiles
    from wf.apk import local_registry

    monkeypatch.delenv("WF_ROOT", raising=False)
    monkeypatch.setattr(local_registry, "registrations", lambda *_: [])
    monkeypatch.setattr(local_registry, "find", lambda *_: None)
    profiles_file = tmp_path / "client-profiles.json"
    provides = {"schema": "wf-apk-provides/1", "source": {"kind": "swf", "basis": "synthetic",
                "swf_sha256": "a" * 64}, "patches": [], "provides": [], "unresolved": [], "limitations": []}
    provides_file = tmp_path / "provides.json"
    write(provides_file, provides)
    write(profiles_file, {"default_client_profile": "synthetic", "profiles": {"synthetic": {
        "provides": str(provides_file), "provides_sha256": hashlib.sha256(provides_file.read_bytes()).hexdigest(),
        "evidence": {"swf_sha256": "a" * 64}}}})
    original_load = profiles.load_profiles
    monkeypatch.setattr(profiles, "load_profiles", lambda *_: original_load(profiles_file))
    edges, paths, records, entries = [], [], [], []
    for number in (9, 10, 11):
        previous, target = f"1.4.{number - 1}", f"1.4.{number}"
        name = f"pinball-{previous}-{target}-1-fixture.zip"
        path = tmp_path / "chain" / str(number) / name
        path.parent.mkdir(parents=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("production/upload/aa/" + "b" * 38, b"synthetic")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        edges.append({"depends_on": previous, "version": target, "names": [name], "integrity": {}})
        entries.append({"type": "patch", "enabled": True, "id": f"edge-{number}", "version": target,
                        "depends_on": previous, "chain": [name],
                        "archive_integrity": [{"name": name, "sha256": sha, "size": path.stat().st_size}]})
        paths.append(path)
        records.append({"name": name, "sha256": sha})
    view = SimpleNamespace(edges=edges, zips=paths, zip_records=records, extra_zips=[],
                           base_version="1.4.8", view_name="fixture")
    source = SimpleNamespace(view=view, version="1.4.11")
    manifest_path = tmp_path / "server/assets/asset-patch/manifest.json"
    write(manifest_path, {"cdn_version": "1.4.9", "patches": entries[:1]})
    profile = tmp_path / "profile.json"
    write(profile, {"wf_root": str(tmp_path), "servers": {"local": {"root": "server"},
          "test175": {"root": "server"}, "production": {"root": "https://private:credential@invalid.example"}}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    return SimpleNamespace(root=tmp_path, source=source, paths=paths, entries=entries,
                           manifest=manifest_path, profile=profile, provides=provides_file)


def requirements(case, *, capabilities=()):
    from wf.deliver.changeset import member_name
    logical = "opening-fixture"
    # Make scannedMembers correspond to the real packed logical member name.
    for path, edge, entry, record in zip(case.paths, case.source.view.edges, case.entries,
                                         case.source.view.zip_records):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(member_name("common", logical), b"synthetic")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        record["sha256"] = sha
        entry["archive_integrity"][0].update(sha256=sha, size=path.stat().st_size)
        write(path.parent / "requires.json", {"schemaVersion": 2,
            "pack": {"since": edge["depends_on"], "tail": edge["version"],
                     "anchor": {"from": edge["depends_on"], "to": edge["version"]}, "archives": [path.name]},
            "requires": {"clientCapabilities": list(capabilities), "clientPatches": [], "serverFeatures": [],
                         "serverRestart": False, "restartReasons": [], "minServerVersion": None,
                         "capabilityResolution": "resolved", "scannedMembers": [{"logical_path": logical,
                         "root": "common", "sha256": hashlib.sha256(b"synthetic").hexdigest()}]}})
    write(case.manifest, {"cdn_version": "1.4.9", "patches": case.entries[:1]})


def test_opening_missing_requires_is_pending_and_never_writes(case):
    before = files(case.root)
    result = opening_plan(case.source)
    assert files(case.root) == before
    assert result["status"] == "pending" and not result["ok"]
    assert result["readOnly"] and result["runtime"] == "未执行"
    assert result["source"]["version"] == "1.4.11"
    assert result["target"]["version"] == "1.4.9"
    assert [(edge["from"], edge["to"]) for edge in result["missingEdges"]] == [
        ("1.4.9", "1.4.10"), ("1.4.10", "1.4.11")]
    assert len(result["clientCapabilities"]["unknownEdges"]) == 3
    text = json.dumps(result)
    assert str(case.root) not in text and "credential" not in text
    assert {target["id"] for target in result["targets"]} == {"local", "test175"}
    assert "修正边" in result["rollback"] and "只往前" in result["rollback"]


def test_opening_complete_member_bound_capability_evidence(case):
    requirements(case)
    result = opening_plan(case.source)
    assert result["status"] == "ready" and result["ok"]
    assert result["clientCapabilities"]["status"] == "matched"


def test_opening_client_missing_real_registered_capability(case):
    requirements(case, capabilities=["client.pf.level4@1"])
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert result["clientCapabilities"]["status"] == "mismatch"
    assert "client.pf.level4@1" in result["clientCapabilities"]["missing"]


def test_opening_requires_scan_cannot_be_trusted_by_name_alone(case):
    requirements(case)
    file = case.paths[-1].parent / "requires.json"
    document = json.loads(file.read_text())
    document["requires"]["scannedMembers"][0]["sha256"] = "0" * 64
    write(file, document)
    result = opening_plan(case.source)
    assert result["clientCapabilities"]["status"] == "unknown"
    assert result["status"] == "pending"


@pytest.mark.parametrize("mutation,rule", [
    ("wrong-parent", "target-inputs"), ("wrong-hash", "archive-conflict"),
    ("wrong-names", "edge-conflict"), ("ahead", "target-anchor"),
    ("disabled", "disabled-collision"), ("header", "target-inputs")])
def test_opening_manifest_conflicts_block(case, mutation, rule):
    document = json.loads(case.manifest.read_text())
    if mutation == "wrong-parent":
        document["patches"][0]["depends_on"] = "1.4.9"
    elif mutation == "wrong-hash":
        document["patches"][0]["archive_integrity"][0]["sha256"] = "0" * 64
    elif mutation == "wrong-names":
        document["patches"][0]["chain"][0] = "pinball-1.4.8-1.4.9-1-other.zip"
    elif mutation == "ahead":
        document["cdn_version"] = "1.4.20"
        document["patches"].append({"type": "patch", "enabled": True, "version": "1.4.20", "depends_on": "1.4.9"})
    elif mutation == "disabled":
        document["patches"].append({**case.entries[1], "enabled": False})
    else:
        document["cdn_version"] = "1.4.10"
    write(case.manifest, document)
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert any(item["rule"] == "opening." + rule and item["blocking"] for item in result["checks"])


def test_opening_missing_target_configuration_still_lists_source(case):
    write(case.profile, {})
    result = opening_plan(case.source, server="test175")
    assert result["status"] == "blocked"
    assert result["source"]["edgeCount"] == 3
    assert result["target"] == {"configured": False, "version": None, "manifestSha256": None}


@pytest.mark.parametrize("root", ["https://private:secret@invalid.example", "//private/secret", "\\\\private\\secret"])
def test_opening_rejects_remote_roots_without_reading_or_echoing(case, monkeypatch, root):
    import wf.studio.opening_routes as opening
    config = json.loads(case.profile.read_text())
    config["servers"]["test175"]["root"] = root
    write(case.profile, config)
    monkeypatch.setattr(opening, "server_root", lambda *_: pytest.fail("remote root resolution must not run"))
    result = opening_plan(case.source, server="test175")
    assert result["status"] == "blocked"
    assert "private" not in json.dumps(result) and "secret" not in json.dumps(result)


def test_opening_local_test_only_true_blocks_175(case):
    case.source.view.edges[-1]["local_test_only"] = True
    result = opening_plan(case.source, server="test175")
    assert result["missingEdges"][-1]["localTestOnly"] is True
    assert any(item["rule"] == "opening.local-test-only" and item["blocking"] for item in result["checks"])


def test_opening_local_test_only_false_does_not_block_175(case):
    source_manifest = case.root / "source-manifest.json"
    entries = [{**entry, "local_test_only": False} for entry in case.entries]
    write(source_manifest, {"cdn_version": "1.4.11", "patches": entries})
    for edge in case.source.view.edges:
        edge["local_test_only"] = False
    case.source.view.manifest = source_manifest
    case.source.view.search_dirs = [path.parent for path in case.paths]
    case.source.view.manifests = []
    result = opening_plan(case.source, server="test175")
    assert all(edge["localTestOnly"] is False for edge in result["missingEdges"])
    assert not any(item["rule"] == "opening.local-test-only" and item["blocking"] for item in result["checks"])
    assert not any(item["blocking"] for item in result["checks"])
    assert result["status"] == "pending"


@pytest.mark.parametrize("bad_flag", ["false", "true", 1, 0])
def test_opening_local_test_only_non_bool_fails_closed(case, bad_flag):
    case.source.view.edges[-1]["local_test_only"] = bad_flag
    result = opening_plan(case.source, server="test175")
    assert result["status"] == "blocked"
    assert any(item["rule"] == "opening.source-chain" and item["blocking"] for item in result["checks"])


def test_opening_source_bytes_changed_blocks(case):
    case.paths[-1].write_bytes(b"changed")
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert any(item["rule"] == "opening.target-inputs" and item["blocking"] for item in result["checks"])


def test_opening_bad_provides_digest_blocks_without_path_leak(case):
    case.provides.write_text("{}", encoding="utf-8")
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert not result["clientCapabilities"]["available"]
    assert str(case.root) not in json.dumps(result)


def test_opening_stale_loaded_view_blocks(case):
    source_manifest = case.root / "source-manifest.json"
    entries = [*case.entries, {"type": "patch", "enabled": True, "version": "1.4.12",
        "depends_on": "1.4.11", "chain": ["pinball-1.4.11-1.4.12-1-new.zip"]}]
    write(source_manifest, {"cdn_version": "1.4.12", "patches": entries})
    case.source.view.manifest = source_manifest
    case.source.view.search_dirs = []
    case.source.view.manifests = []
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert any(item["rule"] == "opening.source-chain" and "已更新" in item["message"]
               for item in result["checks"])


def test_opening_remote_wf_root_expansion_never_resolves(case, monkeypatch):
    import wf.studio.opening_routes as opening
    monkeypatch.setenv("WF_ROOT", "//private/secret")
    monkeypatch.setattr(opening, "server_root", lambda *_: pytest.fail("remote root must not resolve"))
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert "private" not in json.dumps(result)


def test_opening_broken_path_profile_does_not_leak_filename(case, monkeypatch):
    monkeypatch.setenv("WF_PATHS_PROFILE", str(case.root / "secret-missing.json"))
    result = opening_plan(case.source)
    assert result["status"] == "blocked"
    assert "secret-missing" not in json.dumps(result)


@pytest.mark.parametrize("server", ["production", "175", "https://private.invalid"])
def test_opening_explicit_target_allowlist(case, server):
    with pytest.raises(DraftError, match="local 或 test175"):
        opening_plan(case.source, server=server)


def test_opening_routes_only_get_and_safe_existing_documents(case):
    routes = OpeningRoutes(SimpleNamespace(source=case.source))
    assert all(verb == "GET" for verb, _, _ in routes.routes())
    for document in ("rehearsal", "apply-local"):
        response = routes.document({}, document)
        assert response.status == 200 and response.content_type.startswith("text/plain")
        assert len(response.body) > 100
    for query in ({"root": ["server"]}, {"server": ["local", "test175"]}):
        with pytest.raises(DraftError):
            routes.preview(query)
    with pytest.raises(DraftError):
        routes.document({}, "../../profiles/local")
