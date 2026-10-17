"""Do not infer capability support from a filename, version, or unbound SWF."""
import copy
import json
import zipfile

import pytest

from wf.apk import evidence
from wf.apk.cli import main
from wf.apk.provides import build_provides


def test_unknown_binary_name_does_not_claim_v34(tmp_path):
    path = tmp_path / "v34.swf"
    path.write_bytes(b"not a known SWF")
    with pytest.raises(ValueError, match="unknown APK/SWF"):
        build_provides(path)


def test_malformed_apk_is_a_clear_input_error(tmp_path):
    path = tmp_path / "broken.apk"
    path.write_bytes(b"not a ZIP")
    with pytest.raises(ValueError, match="invalid APK ZIP"):
        build_provides(path)


def test_summary_negative_status_and_unknown_patch(tmp_path):
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"schema": "wf-apk-summary/1", "patches": [
        {"number": 87, "status": "failed"}, {"number": 112, "status": "recorded"}]}), encoding="utf-8")
    result = build_provides(path)
    assert result["provides"] == []
    assert len(result["unresolved"]) == 2


def test_pipeline_records_do_not_inherit_base_and_merge_shared_archive(tmp_path):
    path = tmp_path / "patch-list.json"
    path.write_text(json.dumps({"base": {"version": "v34"}, "patches": [
        {"name": "110 / O10", "status": "enabled"},
        {"name": "110 / O11", "status": "enabled"},
        {"name": "111 / O12", "status": "disabled"}]}), encoding="utf-8")
    result = build_provides(path)
    assert [p["number"] for p in result["patches"]] == [110]
    assert all(m["sha256"] is None for m in result["patches"][0]["methods"])
    assert not any(c["id"] == "client.overlimit.lv120@1" for c in result["provides"])


def test_known_swf_alone_does_not_prove_asset_or_native_entries(tmp_path, monkeypatch):
    path = tmp_path / "fixture.SWF"
    path.write_bytes(b"synthetic test SWF")
    record = evidence.v34_evidence()
    record["swf_sha256"] = evidence.digest(path.read_bytes())
    monkeypatch.setattr(evidence, "v34_evidence", lambda: copy.deepcopy(record))
    output = build_provides(path)
    assert output["source"]["kind"] == "swf"
    numbers = {p["number"] for p in output["patches"]}
    assert {79, 82, 86, 97, 98, 99, 100}.isdisjoint(numbers)
    assert {87, 88, 89}.issubset(numbers)


def test_apk_payload_identity_is_required_for_non_swf_entries(tmp_path, monkeypatch):
    path = tmp_path / "client.apk"
    data = b"synthetic SWF"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("assets/main.swf", data)
        archive.writestr("lib/arm64-v8a/library.so", b"fixture")
    record = evidence.v34_evidence()
    record["swf_sha256"] = evidence.digest(data)
    with zipfile.ZipFile(path) as archive:
        record["artifacts"] = [{"payload_sha256": evidence.payload_digest(archive), "excluded_patches": [97, 98, 99, 100]}]
    monkeypatch.setattr(evidence, "v34_evidence", lambda: copy.deepcopy(record))
    output = build_provides(path)
    numbers = {p["number"] for p in output["patches"]}
    assert {79, 82, 86}.issubset(numbers)
    assert {97, 98, 99, 100}.isdisjoint(numbers)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("lib/extra.so", b"changed")
    changed = build_provides(path)
    assert 79 not in {p["number"] for p in changed["patches"]}


def test_apk_uses_game_swf_when_runtime_contains_other_swf(tmp_path, monkeypatch):
    path = tmp_path / "client.apk"
    data = b"game SWF fixture"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("assets/worldflipper_android_release.swf", data)
        archive.writestr("assets/air-runtime.swf", b"runtime fixture")
    record = evidence.v34_evidence()
    record["swf_sha256"] = evidence.digest(data)
    monkeypatch.setattr(evidence, "v34_evidence", lambda: copy.deepcopy(record))
    assert "client.pf.level4@1" in {c["id"] for c in build_provides(path)["provides"]}


def test_modified_unrecognized_build_report_rejected(tmp_path):
    path = tmp_path / "build-report.json"
    path.write_text(json.dumps({"swf": {"sha256": evidence.v34_evidence()["swf_sha256"]}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported or modified"):
        build_provides(path)


def test_cli_cannot_write_outside_checkout(tmp_path):
    with pytest.raises(PermissionError, match="outside checkout"):
        main(["provides", "missing.json", "--output", str(tmp_path.anchor + "outside-provides.json")])
