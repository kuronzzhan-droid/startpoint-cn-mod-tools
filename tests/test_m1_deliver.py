"""Mutation-sensitive checks for delivery contracts and artifact bytes."""
import json
import random
import zipfile
from pathlib import Path

import pytest

from wf.deliver.archives import MAX_ZIP, split_archives
from wf.deliver.assert_box import verify
from wf.deliver.build import build_delivery
from wf.deliver.changeset import load_changeset, member_name, sha256, validate_document
from wf.paths import REPOSITORY


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "payload.bin").write_bytes(b"new payload")
    doc = {"schema": "wf-change-set/1", "id": "test", "name": "测试交付",
           "from_version": "1.4.220", "to_version": "1.4.221", "slug": "test-local",
           "created_at": "2026-10-17", "local_test_only": True, "members": [
               {"root": "common", "logical_path": "test/payload.bin", "source": "payload.bin",
                "sha256": sha256(b"new payload"), "before_sha256": sha256(b"old payload")} ]}
    path = source / "changeset.json"
    path.write_text(json.dumps(doc), "utf-8")
    return path, doc


@pytest.fixture
def delivery(case, tmp_path):
    # Test runner's basetemp is within this checkout; no external fixture writes.
    path, _ = case
    out = tmp_path / "delivery"
    result = build_delivery(path, out, no_baseline_i_know=True)
    return out, result


def test_source_hash_is_mandatory_and_verified(case):
    path, doc = case
    (path.parent / "payload.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_changeset(path)
    del doc["members"][0]["before_sha256"]
    with pytest.raises(ValueError, match="before_sha256"):
        validate_document(doc, "change-set.schema.json")


@pytest.mark.parametrize("field,value", [("source", "../outside.bin"), ("source", "a\\b"), ("logical_path", "../../outside")])
def test_traversal_is_rejected(case, field, value):
    path, doc = case
    doc["members"][0][field] = value
    path.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError):
        load_changeset(path)


def test_duplicate_member_and_rollback_rejected(case):
    path, doc = case
    doc["members"].append(dict(doc["members"][0]))
    path.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="duplicate member"):
        load_changeset(path)
    doc["to_version"] = doc["from_version"]
    path.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="move forward"):
        load_changeset(path)


def test_experimental_cannot_claim_production(case):
    path, doc = case
    doc.update(experimental=True, local_test_only=False)
    path.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="local_test_only"):
        load_changeset(path)


def test_real_compressed_size_and_single_member_oversize():
    noise = random.Random(13).randbytes(MAX_ZIP)
    with pytest.raises(ValueError, match="single member"):
        split_archives({"production/upload/aa/" + "b" * 38: (noise, {"logical_path": "a"})})
    members = {f"member-{i}": (noise[:1200], {"logical_path": str(i)}) for i in range(3)}
    parts = split_archives(members, cap=2500)
    assert len(parts) == 3  # Raw sum fits two, container overhead does not.
    assert all(len(raw) <= 2500 for _, raw in parts)


def test_integrity_sha_installed_bytes_and_checksums(delivery):
    out, result = delivery
    validate_document(result, "delivery-manifest.schema.json")
    assert result["installed_size"] == len(b"new payload")
    integrity = json.loads((out / "integrity.json").read_text("utf-8"))
    for record in result["archives"]:
        raw = (out / record["name"]).read_bytes()
        assert len(raw) == record["size"] <= MAX_ZIP
        assert sha256(raw) == record["sha256"]
        with zipfile.ZipFile(out / record["name"]) as archive:
            assert archive.testzip() is None
            assert archive.read(record["files"][0]) == b"new payload"
    assert integrity["installed_size"] == result["installed_size"]
    for line in (out / "SHA256SUMS").read_text("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        assert sha256((out / name).read_bytes()) == digest


def test_upstream_three_layers_empty_marker_and_exact_contract(delivery):
    out, result = delivery
    path = out / result["upstream_manifest"]
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == 1 and doc["compatibleClient"] == "CN 1.8.1"
    assert doc["baseVersion"] == "1.4.220" and doc["targetVersion"] == "1.4.221"
    assert {r["layer"] for r in doc["archives"]} == {"common", "medium", "android"}
    for record in doc["archives"]:
        assert set(record) == {"relativePath", "layer", "order", "bytes", "sha256"}
        raw = (path.parent / record["relativePath"]).read_bytes()
        assert len(raw) == record["bytes"] and sha256(raw) == record["sha256"]
        assert record["order"] == 1
        if record["layer"] != "common":
            with zipfile.ZipFile(path.parent / record["relativePath"]) as archive:
                assert archive.namelist() == [".empty"]


def test_requires_scans_ordinary_asset_without_inventing_capabilities(delivery):
    out, _ = delivery
    doc = json.loads((out / "requires.json").read_text("utf-8"))
    validate_document(doc, "requires.schema.json")
    assert doc["requires"]["clientCapabilities"] == []
    assert doc["requires"]["capabilityResolution"] == "resolved"
    assert doc["requires"]["scannedMembers"][0]["logical_path"] == "test/payload.bin"


def test_assert_box_checks_versions_and_before_after_hashes(delivery, tmp_path):
    out, _ = delivery
    assertions = json.loads((out / "assert-box.json").read_text("utf-8"))
    store = tmp_path / "store"
    target = store / assertions["files"][0]["member"].removeprefix("production/")
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old payload")
    assert verify(assertions, phase="pre", manifest={"cdn_version": "1.4.220"}, store=store) == []
    assert verify(assertions, phase="post", manifest={"cdn_version": "1.4.221"}, store=store)
    target.write_bytes(b"new payload")
    assert verify(assertions, phase="post", manifest={"cdn_version": "1.4.221"}, store=store) == []
    assert verify(assertions, phase="post", manifest={"cdn_version": "1.4.222"}, store=store)


def test_prepush_runs_since_and_reports_skips_honestly(delivery):
    out, result = delivery
    report = json.loads((out / "prepush.json").read_text("utf-8"))
    assert report["since"] == "1.4.220"
    assert result["prepush"]["status"] == "待验证"
    assert any("未执行" in msg or "跳过" in msg for msg in result["prepush"]["limitations"])


def test_prepush_failure_is_not_success(case, tmp_path, monkeypatch):
    from wf.deliver import prepush
    def fail(argv, **_kwargs):
        path = Path(argv[argv.index("--json") + 1])
        path.write_text(json.dumps({"findings": [{"fid": "forced", "msg": "bad", "level": "ERROR"}]}), "utf-8")
        return 1
    monkeypatch.setattr(prepush, "main", fail)
    result = build_delivery(case[0], tmp_path / "failed", no_baseline_i_know=True)
    assert result["prepush"]["status"] == "问题"
    assert result["prepush"]["exit_code"] == 1


def test_server_payload_is_staged_and_asserted_only(case, tmp_path):
    path, doc = case
    before = b'{"existing": [["preserved"]]}'
    raw = b'{"existing": [["preserved"]], "new": [["added"]]}'
    (path.parent / "server.json").write_bytes(raw)
    doc["server_changes"] = [{"target": "assets/cdndata/character_text.json", "source": "server.json",
                               "sha256": sha256(raw), "before_sha256": sha256(before)}]
    path.write_text(json.dumps(doc), "utf-8")
    out = tmp_path / "with-server"
    server = tmp_path / "server"
    original = server / "assets/cdndata/character_text.json"
    original.parent.mkdir(parents=True)
    original.write_bytes(before)
    result = build_delivery(path, out, server_dir=server, no_baseline_i_know=True)
    assert (out / "server/assets/cdndata/character_text.json").read_bytes() == raw
    asserts = json.loads((out / "assert-box.json").read_text("utf-8"))
    assert asserts["files"][-1]["kind"] == "server"
    assert asserts["files"][-1]["before_sha256"] == sha256(before)
    assert result["prepush"]["exit_code"] == 0
    assert original.read_bytes() == before


def test_output_is_checkout_local_and_never_overwrites(case, delivery):
    with pytest.raises(PermissionError):
        build_delivery(case[0], REPOSITORY.parent / "outside-delivery")
    with pytest.raises(FileExistsError):
        build_delivery(case[0], delivery[0])


@pytest.mark.parametrize("names", [
    ["pinball-1.4.220-1.4.221-2-test.zip"],
    ["pinball-1.4.220-1.4.221-1-test.zip", "pinball-1.4.220-1.4.221-1-other.zip"],
    ["pinball-1.4.218-1.4.219-1-test.zip", "pinball-1.4.220-1.4.221-1-test.zip"],
    ["pinball-1.4.220-1.4.221-1-test.zip", "pinball-1.4.220-1.4.222-1-test.zip"],
])
def test_chain_rejects_missing_duplicate_disconnected_or_forked_sequences(names):
    from wf.deliver.chain_contract import chain_errors
    assert chain_errors(names, "1.4.221")


def test_before_hash_drift_fails_delivery(case, tmp_path):
    path, doc = case
    store = tmp_path / "store"
    filename = store / member_name("common", doc["members"][0]["logical_path"]).removeprefix("production/")
    filename.parent.mkdir(parents=True)
    filename.write_bytes(b"drift")
    result = build_delivery(path, tmp_path / "drifted", base_store=store, no_baseline_i_know=True)
    assert result["prepush"]["exit_code"] == 1
    assert result["prepush"]["status"] == "问题"


def test_server_before_hash_is_enforced_without_external_mutation(case, tmp_path):
    path, doc = case
    raw = b'{"new": []}'
    (path.parent / "server.json").write_bytes(raw)
    relative = "assets/cdndata/character_text.json"
    doc["server_changes"] = [{"target": relative, "source": "server.json", "sha256": sha256(raw),
                               "before_sha256": sha256(b"wrong old bytes")}]
    path.write_text(json.dumps(doc), "utf-8")
    server = tmp_path / "original-server"
    target = server / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b"{}")
    result = build_delivery(path, tmp_path / "server-drift", server_dir=server, no_baseline_i_know=True)
    assert result["prepush"]["exit_code"] == 1
    assert target.read_bytes() == b"{}"


def test_historical_changeset_keeps_long_dsl_paths(tmp_path, monkeypatch):
    import os
    from recipes.halloween221_changeset import create_changeset
    from wf.view import character_pack
    package = tmp_path / "replay/pkgroot"
    package.mkdir(parents=True)
    metadata = {"historical_version": "1.4.221"}
    for key in character_pack.KEYS:
        metadata[key] = dict.fromkeys(("init", "tables", "kit", "assets", "pixel", "art", "voice"), {})
    (package.parent / "build-report.json").write_text(json.dumps(metadata), "utf-8")
    logical = "battle/action/skill/action/ability_skill/" + "long_action_" * 8 + ".action.dsl.amf3.deflate"
    target = package / "work/character_packs/hw-ludi/package/roots/common" / logical
    if os.name == "nt":
        target = Path("\\\\?\\" + str(target.resolve()))
    target.parent.mkdir(parents=True)
    target.write_bytes(b"long DSL")
    monkeypatch.setattr(character_pack, "base_bytes", lambda root, logical: None)
    original = character_pack.hw_env.ROOT
    source = create_changeset(package, tmp_path / "long-changeset")
    doc = json.loads(source.read_text("utf-8"))
    assert len(doc["members"]) == 1 and doc["members"][0]["logical_path"] == logical
    assert character_pack.hw_env.ROOT == original


def test_assert_box_orders_archives_numerically_and_requires_a_client_source(tmp_path):
    member = member_name("common", "test/value.bin")
    active = tmp_path / "active"
    active.mkdir()
    patches = []
    for seq, raw in [(2, b"new"), (1, b"old")]:
        name = f"pinball-1.4.220-1.4.221-{seq}-test.zip"
        with zipfile.ZipFile(active / name, "w") as archive:
            archive.writestr(member, raw)
        patches.append({"type": "patch", "enabled": True, "archive": name})
    assertions = {"from_version": "1.4.220", "to_version": "1.4.221",
                  "files": [{"kind": "client", "member": member,
                             "before_sha256": None, "sha256": sha256(b"new")}]}
    assert verify(assertions, phase="post", manifest={"cdn_version": "1.4.221", "patches": patches}, active=active) == []
    assert verify(assertions, phase="pre", manifest={"cdn_version": "1.4.220"})
