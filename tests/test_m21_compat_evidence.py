"""Counterexamples for hand-written declarations and incomplete method evidence."""
from copy import deepcopy
import json
import zipfile

import pytest

from wf.apk.cli import main as apk_main
from wf.apk.provides import derive_provides
from wf.caps.compat import check_compat
from wf.check import main
from wf.deliver.changeset import member_name, sha256, validate_document
from test_m2_compat import provided, registry, required


def declared_archive(tmp_path):
    document = required([], capabilityResolution="declared", clientPatches=[])
    name = member_name("common", "test.bin")
    with zipfile.ZipFile(tmp_path / "seris.zip", "w") as archive:
        archive.writestr(name, b"data")
    document["requires"]["scannedMembers"] = [
        {"root": "common", "logical_path": "test.bin", "sha256": sha256(b"data")}]
    return document


@pytest.mark.parametrize("fault", ["absent", "empty", "hash", "duplicate", "layer", "path"])
def test_declared_requires_must_match_archive_bytes(tmp_path, registry, fault):
    document = declared_archive(tmp_path)
    rows = document["requires"]["scannedMembers"]
    if fault == "absent":
        del document["requires"]["scannedMembers"]
    elif fault == "empty":
        rows.clear()
    elif fault == "duplicate":
        rows.append(deepcopy(rows[0]))
    else:
        key, value = {"hash": ("sha256", "0" * 64), "layer": ("root", "medium"),
                      "path": ("logical_path", "../test.bin")}[fault]
        rows[0][key] = value
    results = check_compat(document, provided(registry, ()), registry=registry, delivery_dir=tmp_path)
    assert results[0]["status"] == "问题" and results[0]["blocking"]


def test_declared_success_requires_readable_archive_and_cli_binds_it(tmp_path, registry, capsys):
    document = declared_archive(tmp_path)
    client = provided(registry, ())
    assert any(r["blocking"] for r in check_compat(document, client, registry=registry))
    assert not any(r["blocking"] for r in check_compat(document, client, registry=registry, delivery_dir=tmp_path))
    req, prov = tmp_path / "requires.json", tmp_path / "provides.json"
    req.write_text(json.dumps(document), "utf-8")
    prov.write_text(json.dumps(client), "utf-8")
    assert main(["compat", "--requires", str(req), "--provides", str(prov)]) == 0
    (tmp_path / "seris.zip").unlink()
    assert main(["compat", "--requires", str(req), "--provides", str(prov)]) == 1
    capsys.readouterr()


@pytest.mark.parametrize("mode", ["empty", "null"])
def test_direct_provides_cannot_hide_all_required_method_hashes(registry, mode):
    document = deepcopy(provided(registry))
    for entry in document["patches"] + document["provides"]:
        if mode == "empty":
            entry["methods"] = []
        else:
            for method in entry["methods"]:
                method.update(sha256=None, status="待补")
    results = check_compat(required(["client.pf.level4@1"]), document, registry=registry)
    assert results[0]["status"] == "问题" and results[0]["blocking"]


def test_only_registry_pending_methods_can_remain_pending(registry):
    document = derive_provides({"patches": [{"number": 79, "status": "declared"}]}, registry=registry)
    result = check_compat(required(["client.apk.patch079@1"], clientPatches=["#79"]), document, registry=registry)
    assert result[0]["status"] == "待验证" and not result[0]["blocking"]


def test_summary_missing_hashes_exits_nonzero(tmp_path, registry, capsys):
    source = tmp_path / "summary.json"
    source.write_text(json.dumps({"schema": "wf-apk-summary/1", "patches": [
        {"number": 87, "status": "declared"}]}), "utf-8")
    assert apk_main(["provides", str(source), "--out", str(tmp_path / "result.json")]) == 1
    assert "问题" in capsys.readouterr().out


def test_unknown_methods_warn_without_proving_anything(registry):
    methods = deepcopy(registry["client.apk.patch087@1"]["provided_by"]["methods"])
    methods.append(dict(methods[0], label="unregistered-method", sha256="1" * 64))
    result = derive_provides({"patches": [{"number": 87, "status": "recorded", "methods": methods}]}, registry=registry)
    validate_document(result, "provides.schema.json")
    assert result["unresolved"] == []
    assert result["warnings"][0]["label"] == "unregistered-method"
    assert all(m["label"] != "unregistered-method" for m in result["patches"][0]["methods"])


def test_duplicate_invalid_patch_cannot_escape_duplicate_detection(registry):
    with pytest.raises(ValueError, match="duplicate patch"):
        derive_provides({"patches": [{"number": 87, "status": "declared"}] * 2}, registry=registry)
