"""Negative controls for required baseline provenance and server assertions."""
import json
import zipfile

import pytest

from wf.deliver.build import build_delivery
from wf.deliver.changeset import member_name, sha256
from wf.deliver.cli import main
from wf.view import ManifestView


@pytest.fixture
def case(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_bytes(b"new")
    doc = {"schema": "wf-change-set/1", "id": "test", "name": "测试", "slug": "test",
           "created_at": "2026-10-17", "from_version": "1.4.132", "to_version": "1.4.133",
           "local_test_only": True, "members": [{"root": "common", "logical_path": "test.bin",
           "source": "data", "sha256": sha256(b"new"), "before_sha256": sha256(b"old")}]}
    changes = source / "changeset.json"
    changes.write_text(json.dumps(doc), "utf-8")
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir()
    store.mkdir()
    name = "pinball-1.4.131-1.4.132-1-test.zip"
    with zipfile.ZipFile(active / name, "w") as archive:
        archive.writestr(member_name("common", "test.bin"), b"old")
    edge = {"version": "1.4.132", "depends_on": "1.4.131", "chain": [name], "enabled": True, "type": "patch"}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [edge]}), "utf-8")
    return changes, doc, manifest, store, active


def test_default_cli_refuses_no_baseline(case, tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main([str(case[0]), "--out", str(tmp_path / "out")])
    assert error.value.code != 0
    assert "问题" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_waiver_is_explicit_and_recorded(case, tmp_path):
    result = build_delivery(case[0], tmp_path / "out", no_baseline_i_know=True)
    assert result["prepush"]["exit_code"] == 0
    assert result["baseline"] == {"no_baseline_i_know": True, "tip": None, "lock": None}
    report = json.loads((tmp_path / "out/prepush.json").read_text("utf-8"))
    assert report["local_contract"]["no_baseline_i_know"] is True
    assert any("--no-baseline-i-know" in text for text in result["prepush"]["limitations"])


@pytest.mark.parametrize("fault", ["occupied", "disabled-occupied", "stale", "recast"])
def test_manifest_newer_or_occupied_edge_cannot_be_waived(case, tmp_path, fault):
    changes, doc, manifest, store, _ = case
    target = "1.4.134" if fault == "stale" else "1.4.133"
    data = json.loads(manifest.read_text("utf-8"))
    data["patches"].append({"version": target, "depends_on": "1.4.132",
                            "archive": f"pinball-1.4.132-{target}-1-original.zip",
                            "enabled": fault != "disabled-occupied", "type": "patch"})
    manifest.write_text(json.dumps(data), "utf-8")
    with pytest.raises(ValueError, match="stale" if fault == "stale" else "occupied.*recast"):
        build_delivery(changes, tmp_path / "out", baseline_manifest=manifest,
                       base_store=store, no_baseline_i_know=True)
    assert not (tmp_path / "out").exists()


def test_manifest_baseline_ignores_unlisted_archives_without_copying(case, tmp_path):
    changes, doc, manifest, store, active = case
    # An invalid abandoned ZIP with a newer edge must never become an input.
    (active / "pinball-1.4.132-1.4.999-1-abandoned.zip").write_bytes(b"not a zip")
    out = tmp_path / "out"
    result = build_delivery(changes, out, baseline_manifest=manifest, base_store=store)
    assert result["prepush"]["exit_code"] == 0
    assert list((out / "validation").rglob("*.zip")) == []
    lock = json.loads((out / "baseline.lock.json").read_text("utf-8"))
    assert len(lock["zips"]) == 1 and lock["tip"] == doc["from_version"]
    report = json.loads((out / "prepush.json").read_text("utf-8"))
    assert report["local_contract"]["pre_and_post_hashes_checked"]


def test_baseline_view_binding_and_lock_are_enforced(case, tmp_path):
    changes, doc, manifest, store, active = case
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[])
    doc["from_version"], doc["to_version"] = "1.4.134", "1.4.135"
    changes.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="tip must equal"):
        build_delivery(changes, tmp_path / "out", baseline_view=view)


def test_baseline_pre_hash_drift_is_blocking(case, tmp_path):
    changes, doc, manifest, store, active = case
    doc["members"][0]["before_sha256"] = sha256(b"wrong")
    changes.write_text(json.dumps(doc), "utf-8")
    result = build_delivery(changes, tmp_path / "out", baseline_manifest=manifest, base_store=store)
    assert result["prepush"]["status"] == "问题" and result["prepush"]["exit_code"] == 1


@pytest.mark.parametrize("target", ["assets/local_fixture.json", "assets/cdndata/character_text.json"])
def test_server_pre_hash_never_waived(case, tmp_path, target):
    changes, doc, _, _, _ = case
    raw = b"{}"
    (changes.parent / "server").write_bytes(raw)
    doc["server_changes"] = [{"target": target, "source": "server",
                              "sha256": sha256(raw), "before_sha256": None}]
    changes.write_text(json.dumps(doc), "utf-8")
    if target == "assets/cdndata/character_text.json":
        # Shared character maps now fail before packaging when the full mirror is missing.
        with pytest.raises(ValueError, match="missing complete server baseline"):
            build_delivery(changes, tmp_path / "out", no_baseline_i_know=True)
        assert not (tmp_path / "out").exists()
        return
    result = build_delivery(changes, tmp_path / "out", no_baseline_i_know=True)
    assert result["prepush"]["status"] == "问题" and result["prepush"]["exit_code"] == 1
    report = json.loads((tmp_path / "out/prepush.json").read_text("utf-8"))
    assert any("server root required" in text for text in report["local_contract"]["errors"])


def test_explicit_zip_requires_manifest(case, tmp_path):
    with pytest.raises(ValueError, match="require --baseline-manifest"):
        build_delivery(case[0], tmp_path / "out", baseline_zips=list(case[4].glob("*.zip")),
                       no_baseline_i_know=True)


@pytest.mark.parametrize("root", ["medium", "android"])
@pytest.mark.parametrize("logical", ["master/ability/ability.orderedmap",
                                    "battle/action/test$test.action.dsl.amf3.deflate"])
def test_alternate_asset_layer_cannot_skip_combat_gate(case, tmp_path, root, logical):
    changes, doc, *_ = case
    doc["members"][0].update(root=root, logical_path=logical)
    changes.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="must use common root"):
        build_delivery(changes, tmp_path / "out", no_baseline_i_know=True)
    assert list((tmp_path / "out").rglob("*.zip")) == []


@pytest.mark.parametrize("flag", ["server_pre_hashes_checked", "server_post_hashes_checked"])
def test_delivery_readback_requires_server_check_evidence(case, tmp_path, flag):
    from wf.check_delivery import check_delivery
    changes, doc, *_ = case
    before = b'{"existing":[["preserved"]]}'
    after = b'{"existing":[["preserved"]],"new":[["added"]]}'
    (changes.parent / "server").write_bytes(after)
    doc["server_changes"] = [{"target": "assets/cdndata/character_text.json", "source": "server",
                              "sha256": sha256(after), "before_sha256": sha256(before)}]
    changes.write_text(json.dumps(doc), "utf-8")
    server = tmp_path / "server"
    mirror = server / "assets/cdndata/character_text.json"
    mirror.parent.mkdir(parents=True)
    mirror.write_bytes(before)
    out = tmp_path / "out"
    result = build_delivery(changes, out, no_baseline_i_know=True, server_dir=server)
    assert result["prepush"]["exit_code"] == 0
    check_delivery(result, out)
    report = json.loads((out / "prepush.json").read_text("utf-8"))
    report["local_contract"][flag] = False
    (out / "prepush.json").write_text(json.dumps(report), "utf-8")
    with pytest.raises(ValueError, match="server pre/post hashes"):
        check_delivery(result, out)
