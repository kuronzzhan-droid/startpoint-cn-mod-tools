"""Synthetic offline rehearsal: checks, portable entries and strict write boundaries."""
import hashlib
import json
import os
import zipfile

import pytest

from wf.studio.rehearsal import rehearse
from wf.studio.rehearsal_io import json_bytes, latest


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "server"
    delivery = tmp_path / "build/delivery"
    delivery.mkdir(parents=True)
    (root / "assets/asset-patch/active").mkdir(parents=True)
    put(root / "assets/asset-patch/manifest.json", {"cdn_version": "1.4.9", "patches": [
        {"id": "previous", "version": "1.4.9", "depends_on": "1.4.8", "enabled": True, "type": "patch"},
        {"id": "disabled", "version": "1.4.99", "depends_on": "1.4.9", "enabled": False}]})
    profile = tmp_path / "profile.json"
    put(profile, {"wf_root": str(tmp_path), "servers": {"local": {"root": "server"}}})
    monkeypatch.setenv("WF_PATHS_PROFILE", str(profile))
    for i in (1, 2):
        with zipfile.ZipFile(delivery / f"pinball-1.4.9-1.4.10-{i}-test.zip", "w") as archive:
            archive.writestr(f"production/upload/aa/{str(i) * 38}", f"payload {i}")
    return root, delivery, profile


def test_rehearsal_success_portable_entry_and_readonly(case):
    from pathlib import Path
    import jsonschema
    root, delivery, _ = case
    before = snapshot(root)
    result = rehearse(delivery.parent)
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/studio-rehearsal.schema.json").read_text("utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(result)
    assert result["ok"] and result["status"] == "ready"
    assert result["restartRequired"] is False
    assert snapshot(root) == before
    entry = result["manifestEntry"]
    assert set(entry) == {"id", "type", "name", "version", "depends_on", "enabled", "archive",
                          "archive_size", "chain", "files", "archive_integrity", "created_at"}
    assert "local_test_only" not in entry
    assert entry["depends_on"] == "1.4.9" and len(entry["chain"]) == 2
    assert str(root) not in result["manifestEntryJson"]
    raw = result["manifestEntryJson"].encode("utf-8")
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n  " in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert latest(delivery) == result
    assert (delivery / "rehearsal-local.md").is_file()
    assert str(root) in (delivery / "rehearsal-local.md").read_text("utf-8")
    assert result["runtime"] == "未执行"


@pytest.mark.parametrize("change,rule", [("old", "from"), ("collision", "active-collision"),
                                        ("gap", "inputs"), ("badname", "inputs"),
                                        ("flag", "local-test-only"), ("falseflag", "local-test-only")])
def test_rehearsal_blocks_unsafe_edges(case, change, rule):
    root, folder, _ = case
    archive = next(folder.glob("*.zip"))
    if change == "old":
        put(root / "assets/asset-patch/manifest.json", {"cdn_version": "1.4.11", "patches": [
            {"version": "1.4.11", "depends_on": "1.4.9", "type": "patch", "enabled": True}]})
    elif change == "collision":
        (root / "assets/asset-patch/active" / archive.name).write_bytes(b"different")
    elif change == "gap":
        archive.rename(folder / archive.name.replace("-1-test", "-3-test"))
    elif change == "badname":
        archive.rename(folder / "bad.zip")
    else:
        put(folder / "manifest-entry-1.4.10.json", {
            "version": "1.4.10", "depends_on": "1.4.9",
            "chain": [p.name for p in sorted(folder.glob("*.zip"))], "local_test_only": change == "flag"})
    before = snapshot(root)
    result = rehearse(folder)
    assert not result["ok"]
    assert any(c["rule"] == "rehearsal." + rule and c["blocking"] for c in result["checks"])
    assert snapshot(root) == before


def test_same_name_same_bytes_and_zip_list(case):
    root, folder, _ = case
    paths = sorted(folder.glob("*.zip"), reverse=True)
    for p in paths:
        (root / "assets/asset-patch/active" / p.name).write_bytes(p.read_bytes())
    result = rehearse(folder, zips=paths)
    assert result["ok"]
    assert "-1-" in result["manifestEntry"]["archive"]


def test_json_keys_code_restart_and_whole_file_risk(case):
    root, folder, _ = case
    put(root / "assets/cdndata/example.json", {"keep": 7, "edit": {"value": 1, "retain": 5}})
    put(folder / "server/assets/cdndata/example.json", {"add": 2, "edit": {"value": 3}})
    (folder / "server/out").mkdir(parents=True)
    (folder / "server/out/example.js").write_text("// candidate", "utf-8")
    before = snapshot(root)
    result = rehearse(folder)
    assert result["ok"] and result["restartRequired"]
    table = result["serverChanges"][0]
    assert table["addedKeys"] == ["/add"]
    assert table["replacedKeys"] == ["/edit/value"]
    assert set(table["omittedKeys"]) == {"/edit/retain", "/keep"}
    assert table["wholeFileOverwriteRisk"]
    assert snapshot(root) == before


def test_baseline_drift_and_missing_server_candidate(case):
    root, folder, _ = case
    raw = json_bytes({"x": 2})
    put(root / "assets/table.json", {"x": 1})
    put(folder / "server/assets/table.json", {"x": 2})
    put(folder / "assert-box.json", {"files": [{"kind": "server", "target": "assets/table.json",
         "sha256": hashlib.sha256(raw).hexdigest(), "before_sha256": "0" * 64}]})
    result = rehearse(folder)
    assert not result["ok"] and result["serverChanges"][0]["baselineMatches"] is False
    (folder / "server/assets/table.json").unlink()
    assert not rehearse(folder)["ok"]


def test_metadata_hash_and_duplicate_members(case):
    _, folder, _ = case
    paths = sorted(folder.glob("*.zip"))
    put(folder / paths[0].with_suffix(".integrity.json").name, {"sha256": "0" * 64})
    assert not rehearse(folder)["ok"]
    paths[0].with_suffix(".integrity.json").unlink()
    with zipfile.ZipFile(paths[1], "w") as archive:
        archive.writestr("production/upload/aa/" + "1" * 38, b"duplicate")
    assert not rehearse(folder)["ok"]


@pytest.mark.parametrize("patches,cdn", [
    ([{"version": "1.4.9", "depends_on": "1.4.8"}, {"version": "1.4.10", "depends_on": "1.4.7"}], "1.4.10"),
    ([{"version": "1.4.9", "depends_on": "1.4.8"}], "1.4.10"),
    ([{"version": "1.4.9", "depends_on": "1.4.8"}] * 2, "1.4.9"),
])
def test_invalid_enabled_chain_blocks(case, patches, cdn):
    root, folder, _ = case
    put(root / "assets/asset-patch/manifest.json", {"cdn_version": cdn, "patches": patches})
    assert not rehearse(folder)["ok"]


def test_unknown_server_and_bad_server_name(case):
    _, folder, _ = case
    assert not rehearse(folder, "unknown")["ok"]
    for name in ("../local", "a/b", "", None):
        with pytest.raises(ValueError):
            rehearse(folder, name)


def test_never_write_reports_into_server_or_hardlinks(case):
    root, folder, _ = case
    before = snapshot(root)
    with pytest.raises(ValueError, match="禁止写入"):
        rehearse(root / "assets/asset-patch/active", zips=sorted(folder.glob("*.zip")))
    sentinel = root / "untouched.txt"
    sentinel.write_bytes(b"sentinel")
    os.link(sentinel, folder / "rehearsal-local.json")
    with pytest.raises(ValueError, match="硬链接"):
        rehearse(folder)
    assert sentinel.read_bytes() == b"sentinel"
    sentinel.unlink()
    assert snapshot(root) == before


def test_readonly_mode_leaves_delivery_untouched(case):
    root, folder, _ = case
    before = snapshot(folder)
    assert rehearse(folder, write=False)["ok"]
    assert snapshot(folder) == before


def test_historical_key_fragments_and_arrays(case):
    root, folder, _ = case
    put(root / "assets/table.json", {"keep": 1, "nested": {"old": 2}})
    put(root / "assets/ids.json", [1, 2])
    put(folder / "server-entries/table.json", {"nested": {"new": 3}})
    put(folder / "server-entries/ids.json", [3])
    put(folder / "server-entries/merge-manifest.json", {"operations": []})
    result = rehearse(folder)
    assert result["ok"] and result["restartRequired"]
    assert len(result["serverChanges"]) == 2
    ids, table = result["serverChanges"]
    assert ids["appendValues"] == [3] and ids["omittedValues"] == [1, 2]
    assert table["addedKeys"] == ["/nested/new"]
    assert set(table["omittedKeys"]) == {"/keep", "/nested/old"}


@pytest.mark.parametrize("mode", ["traversal", "corrupt", "mixed", "duplicate-seq", "duplicate-json"])
def test_bad_inputs_still_write_blocked_report(case, mode):
    _, folder, _ = case
    paths = sorted(folder.glob("*.zip"))
    if mode == "traversal":
        put(folder / "delivery-manifest.json", {"legacy_manifest": "../outside.json"})
    elif mode == "corrupt":
        paths[0].write_bytes(b"not a zip")
    elif mode == "mixed":
        paths[0].rename(folder / paths[0].name.replace("1.4.10", "1.4.11"))
    elif mode == "duplicate-seq":
        paths[1].rename(folder / paths[1].name.replace("-2-test", "-1-other"))
    else:
        (folder / "manifest-entry-bad.json").write_text('{"version":1,"version":2}', "utf-8")
    result = rehearse(folder)
    assert result["status"] == "blocked"
    assert latest(folder) == result
