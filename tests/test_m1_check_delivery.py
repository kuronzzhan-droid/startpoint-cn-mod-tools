import copy
import json
import zipfile

import pytest

from wf.check_delivery import check_delivery
from wf.deliver.build import build_delivery
from wf.deliver.changeset import sha256


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    import wf.deliver.build as build
    def prepush(out, *_a, **_kw):
        (out / "prepush.json").write_text(json.dumps({"since": "1.4.131", "findings": [],
            "local_contract": {"no_baseline_i_know": True}}), encoding="utf-8")
        (out / "prepush.log").write_text("test fixture", encoding="utf-8")
        return {"status": "待验证", "exit_code": 0, "since": "1.4.131", "report": "prepush.json",
                "log": "prepush.log", "limitations": ["测试夹具未提供完整服务端"]}
    monkeypatch.setattr(build, "run_prepush", prepush)
    source = tmp_path / "source"
    source.mkdir()
    (source / "data.bin").write_bytes(b"data")
    doc = {"schema": "wf-change-set/1", "id": "test", "name": "测试", "slug": "test",
           "created_at": "2026-10-17", "from_version": "1.4.131", "to_version": "1.4.132",
           "local_test_only": True, "members": [{"root": "common", "logical_path": "test.bin",
           "source": "data.bin", "sha256": sha256(b"data"), "before_sha256": None}]}
    changes = source / "changeset.json"
    changes.write_text(json.dumps(doc), encoding="utf-8")
    target = tmp_path / "delivery"
    return target, build_delivery(changes, target, no_baseline_i_know=True)


def test_check_preserves_incomplete_or_failed_prepush(delivery):
    directory, doc = delivery
    results = check_delivery(doc, directory)
    assert results[0]["status"] == "满足"
    assert results[1]["status"] == "待验证" and not results[1]["blocking"]
    doc = copy.deepcopy(doc)
    doc["prepush"].update(status="问题", exit_code=1)
    assert check_delivery(doc, directory)[1]["blocking"]


def test_check_rejects_total_size_drift(delivery):
    directory, doc = delivery
    doc["installed_size"] += 1
    with pytest.raises(ValueError, match="total"):
        check_delivery(doc, directory)


def test_check_rejects_upstream_only_corruption(delivery):
    directory, doc = delivery
    manifest = directory / doc["upstream_manifest"]
    entry = json.loads(manifest.read_text(encoding="utf-8"))["archives"][0]
    path = manifest.parent / entry["relativePath"]
    path.write_bytes(b"broken")
    with pytest.raises(ValueError, match="upstream archive integrity"):
        check_delivery(doc, directory)


@pytest.mark.parametrize("fault", ["content", "missing", "extra", "wrong-layer"])
def test_layered_members_must_equal_legacy_even_with_valid_hashes(delivery, fault):
    directory, doc = delivery
    manifest = directory / doc["upstream_manifest"]
    upstream = json.loads(manifest.read_text("utf-8"))
    entry = next(x for x in upstream["archives"] if x["layer"] == "common")
    path = manifest.parent / entry["relativePath"]
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    name = next(iter(contents))
    if fault == "content":
        contents[name] = b"different"
    elif fault == "missing":
        contents = {".empty": b""}
    elif fault == "extra":
        contents[name[:-1] + ("0" if name[-1] != "0" else "1")] = b"extra"
    else:
        contents = {name.replace("/upload/", "/medium_upload/"): contents[name]}
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in contents.items():
            archive.writestr(name, raw)
    entry.update(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()))
    manifest.write_text(json.dumps(upstream), "utf-8")
    with pytest.raises(ValueError, match="upstream member"):
        check_delivery(doc, directory)


@pytest.mark.parametrize("change", ["exit_code", "limitations", "missing-report", "missing-assertions", "error-report"])
def test_claimed_prepush_pass_requires_consistent_evidence(delivery, change):
    directory, doc = delivery
    doc["prepush"].update(status="满足", limitations=[])
    if change == "exit_code":
        doc["prepush"]["exit_code"] = 99
    elif change == "limitations":
        doc["prepush"]["limitations"] = ["检查未执行"]
    elif change == "missing-report":
        doc["prepush"]["report"] = "nonexistent.json"
    elif change == "missing-assertions":
        doc["assertions"] = "nonexistent.json"
    else:
        (directory / "prepush.json").write_text(json.dumps({"since": "1.4.131", "findings": [{"level": "ERROR"}]}), encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        check_delivery(doc, directory)
