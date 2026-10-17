import copy
import json

import pytest

from wf.check_delivery import check_delivery
from wf.deliver.build import build_delivery
from wf.deliver.changeset import sha256


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    import wf.deliver.build as build
    monkeypatch.setattr(build, "run_prepush", lambda *_a, **_kw: {
        "status": "待验证", "exit_code": 0, "since": "1.4.131", "report": "prepush.json",
        "log": "prepush.log", "limitations": ["测试夹具未提供完整服务端"]})
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
    return target, build_delivery(changes, target)


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
