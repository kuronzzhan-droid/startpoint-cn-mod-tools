"""Synthetic CDN/APK fixtures for collision and input-integrity boundaries."""
import hashlib
import io
import json
from pathlib import Path
import warnings
import zipfile

import pytest
import wf_mod_tool as core
from wf.deliver.changeset import member_name
from wf.studio import bundle_keys as gate
from wf.studio import delivery_inputs as inputs

ACTION = "master/skill/power_flip_action.orderedmap"
OTHER = "master/example/extra.orderedmap"


def ordered(keys):
    return core.build_orderedmap(core.OrderedMap(ACTION, list(keys), [b"value"] * len(keys), Path("fixture")))


def zip_bytes(entries):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
            for name, data in entries:
                archive.writestr(name, data)
    return output.getvalue()


def bundled_member(logical):
    digest = core.sha1_path(gate.bundled_logical(logical))
    return "production/android_bundle/" + digest[:2] + "/" + digest[2:]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "REPOSITORY", tmp_path / "repository")
    monkeypatch.setattr(inputs, "configured_path", lambda _: tmp_path / "pathlist.txt")
    monkeypatch.setenv("WF_STUDIO_BUNDLE_CACHE", str(tmp_path / "cache"))
    return tmp_path


def apk_file(directory, entries=None, *, name="client.apk", outer=None):
    if entries is None:
        entries = [(bundled_member(ACTION), ordered(["ranged", "melee"]))]
    bundle = zip_bytes(entries)
    target = directory / name
    target.write_bytes(zip_bytes(outer if outer is not None else [("assets/bundle.zip", bundle)]))
    return target


def delivery(directory, *, logical=ACTION, data=None, sidecar=True, name="patch.zip"):
    target = directory / name
    member = member_name("common", logical)
    data = ordered(["ranged", "custom"]) if data is None else data
    raw = zip_bytes([(member, data)])
    target.write_bytes(raw)
    if sidecar:
        target.with_suffix(".integrity.json").write_text(json.dumps({
            "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "members": 1,
            "files": [member], "logical": {member: logical},
            "member_sha256": {member: hashlib.sha256(data).hexdigest()},
            "applies_on": "1.4.1", "version": "1.4.2"}), "utf-8")
    return target


def test_bundle_collision_and_staged_bytes(setup):
    apk = apk_file(setup)
    result = gate.check_bundle_keys([apk], tables={ACTION: ordered(["ranged", "custom"])})
    assert result["status"] == "collision"
    assert result["tables"] == [{"logical": ACTION, "bundledLogical": gate.bundled_logical(ACTION),
                                 "collisions": ["ranged"]}]
    assert result["apks"] == [{"label": apk.name, "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
                               "bundledTables": 1}]
    assert gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})["status"] == "ok"


def test_bundle_union_selected_apks_and_index_reuse(setup, monkeypatch):
    first = apk_file(setup)
    second = apk_file(setup, [(bundled_member(ACTION), ordered(["custom"]))], name="second.apk")
    indexes = [gate.load_bundle_index(a, logical_paths=[ACTION]) for a in (first, second)]
    assert gate.bundled_keys(indexes, ACTION) == {"ranged", "melee", "custom"}
    monkeypatch.setattr(gate, "_extract", lambda *_: pytest.fail("valid cache must be reused"))
    assert gate.load_bundle_index(first, logical_paths=[ACTION]) == indexes[0]


def test_bundle_cache_invalidates_for_new_logical_candidates_and_apk_bytes(setup):
    apk = apk_file(setup, [(bundled_member(ACTION), ordered(["ranged"])),
                           (bundled_member(OTHER), ordered(["extra"]))])
    one = gate.load_bundle_index(apk, logical_paths=[ACTION])
    two = gate.load_bundle_index(apk, logical_paths=[ACTION, OTHER])
    assert set(one["tables"]) == {ACTION}
    assert set(two["tables"]) == {ACTION, OTHER}
    apk_file(setup, [(bundled_member(ACTION), ordered(["new"]))])
    three = gate.load_bundle_index(apk, logical_paths=[ACTION])
    assert three["sha256"] != one["sha256"]
    assert three["tables"][ACTION] == ["new"]
    assert len(list((setup / "cache").glob("*.json"))) == 2


def test_unmapped_apk_orderedmaps_are_indexed_by_hash(setup):
    apk = apk_file(setup, [(bundled_member(ACTION), ordered(["ranged"])),
                           (bundled_member(OTHER), ordered(["anonymous"]))])
    index = gate.load_bundle_index(apk, logical_paths=[ACTION])
    assert set(index["tables"]) == {ACTION}
    assert len(index["hashedTables"]) == 2
    assert gate.bundled_keys([index], OTHER) == {"anonymous"}
    report = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})
    assert report["apks"][0]["bundledTables"] == 2


@pytest.mark.parametrize("damage", ["truncated_rows", "bad_index_size", "duplicate_keys"])
def test_unmapped_damaged_orderedmap_is_not_silently_ignored(setup, damage):
    raw = ordered(["anonymous"])
    if damage == "truncated_rows":
        raw = raw[:-1]
    elif damage == "bad_index_size":
        raw = b"\xff\xff\xff\xff" + raw[4:]
    else:
        raw = ordered(["anonymous", "anonymous"])
    apk = apk_file(setup, [(bundled_member(ACTION), ordered(["ranged"])),
                           (bundled_member(OTHER), raw)])
    report = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})
    assert report["status"] == "error"


def test_bundle_cache_logical_hash_consistency_checked(setup):
    apk = apk_file(setup)
    gate.load_bundle_index(apk, logical_paths=[ACTION])
    filename = next((setup / "cache").glob("*.json"))
    document = json.loads(filename.read_text("utf-8"))
    document["index"]["hashedTables"].clear()
    document["indexSha256"] = hashlib.sha256(gate._encoded(document["index"])).hexdigest()
    filename.write_text(json.dumps(document), "utf-8")
    report = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})
    assert report["status"] == "error" and "logical/hash table mismatch" in report["reason"]


def test_previous_index_cache_schema_is_rebuilt(setup, monkeypatch):
    apk = apk_file(setup)
    gate.load_bundle_index(apk, logical_paths=[ACTION])
    filename = next((setup / "cache").glob("*.json"))
    document = json.loads(filename.read_text("utf-8"))
    document["index"]["schema"] = "wf-studio-bundle-keys/1"
    document["indexSha256"] = hashlib.sha256(gate._encoded(document["index"])).hexdigest()
    filename.write_text(json.dumps(document), "utf-8")
    original = gate._extract
    calls = []
    monkeypatch.setattr(gate, "_extract", lambda *args: (calls.append(True), original(*args))[1])
    assert gate.load_bundle_index(apk, logical_paths=[ACTION])["schema"] == gate.SCHEMA
    assert calls == [True]


def test_bundle_cache_corruption_is_error_and_repo_cache_rejected(setup, monkeypatch):
    apk = apk_file(setup)
    gate.load_bundle_index(apk, logical_paths=[ACTION])
    cache = next((setup / "cache").glob("*.json"))
    cache.write_text("{}", "utf-8")
    assert gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})["status"] == "error"
    monkeypatch.setattr(gate, "REPOSITORY", setup)
    with pytest.raises(ValueError, match="outside the repository"):
        gate.load_bundle_index(apk, logical_paths=[ACTION])


@pytest.mark.parametrize("kind", ["duplicate_bundle", "extra_bundle", "no_bundle", "bad_bundle",
                                 "empty_bundle", "duplicate_member", "bad_orderedmap", "duplicate_key",
                                 "bad_apk", "unsafe_bundle_path"])
def test_bundle_invalid_inputs_fail_closed(setup, kind):
    entry = (bundled_member(ACTION), ordered(["ranged"]))
    bundle = zip_bytes([entry])
    outer = [("assets/bundle.zip", bundle)]
    if kind == "duplicate_bundle":
        outer *= 2
    elif kind == "extra_bundle":
        outer.append(("other/bundle.zip", bundle))
    elif kind == "no_bundle":
        outer = [("unrelated.bin", b"x")]
    elif kind == "bad_bundle":
        outer = [("assets/bundle.zip", b"not a zip")]
    elif kind == "empty_bundle":
        outer = [("assets/bundle.zip", zip_bytes([]))]
    elif kind == "duplicate_member":
        outer = [("assets/bundle.zip", zip_bytes([entry, entry]))]
    elif kind == "bad_orderedmap":
        outer = [("assets/bundle.zip", zip_bytes([(entry[0], b"broken")]))]
    elif kind == "duplicate_key":
        outer = [("assets/bundle.zip", zip_bytes([(entry[0], ordered(["same", "same"]))]))]
    elif kind == "unsafe_bundle_path":
        outer = [("assets/bundle.zip", zip_bytes([entry, ("../bad", b"x")]))]
    apk = apk_file(setup, outer=outer)
    if kind == "bad_apk":
        apk.write_bytes(b"not a zip")
    result = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})
    assert result["status"] == "error"
    assert result["reason"]
    assert not list((setup / "cache").glob("*.json"))


def test_bundle_broken_staged_orderedmap_and_missing_apk(setup):
    apk = apk_file(setup)
    assert gate.check_bundle_keys([apk], tables={ACTION: b"broken"})["status"] == "error"
    assert gate.check_bundle_keys([setup / "missing.apk"], tables={})["status"] == "error"
    result = gate.check_bundle_keys([], tables={ACTION: ordered(["ranged"])})
    assert result["status"] == "skipped" and "未核对" in result["reason"]


def test_staged_root_identity_is_preserved_and_validated(setup):
    apk = apk_file(setup)
    assert gate.check_bundle_keys([apk], tables={
        ("common", ACTION): ordered(["custom"]), ("android", "ui/icon.png"): b"image",
    })["status"] == "ok"
    for root in ("android", "medium", "small", "ios"):
        report = gate.check_bundle_keys([apk], tables={(root, ACTION): ordered(["custom"])})
        assert report["status"] == "error" and "common root" in report["reason"]
    report = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"]),
        ("common", ACTION): ordered(["ranged"])})
    assert report["status"] == "error" and "duplicate output orderedmap" in report["reason"]


@pytest.mark.parametrize("staged", [[(ACTION, b"bad")], {123: b"bad"}, {ACTION: "not bytes"}])
def test_malformed_staged_inputs_report_error(setup, staged):
    assert gate.check_bundle_keys([apk_file(setup)], tables=staged)["status"] == "error"


def test_zip_orderedmap_in_wrong_root_is_rejected(setup):
    archive = setup / "wrong-root.zip"
    archive.write_bytes(zip_bytes([(member_name("android", ACTION), ordered(["custom"]))]))
    (setup / "pathlist.txt").write_text(ACTION + "\n", "utf-8")
    result = gate.check_bundle_keys([apk_file(setup)], zips=[archive])
    assert result["status"] == "error" and "common root" in result["reason"]


def test_delivery_zip_and_directory_check(setup):
    apk = apk_file(setup)
    archive = delivery(setup)
    assert gate.check_bundle_keys([apk], zips=[archive])["status"] == "collision"
    assert gate.check_bundle_keys([apk], delivery_dir=setup)["status"] == "collision"
    member = inputs.read_delivery_members([archive])[0]
    assert (member.logical, member.root, member.archive, member.from_version, member.to_version) == (
        ACTION, "common", archive.name, "1.4.1", "1.4.2")


def test_delivery_mapping_fallback_unknown_and_stale_sidecar(setup):
    archive = delivery(setup, sidecar=False)
    assert inputs.read_delivery_members([archive])[0].logical is None
    assert inputs.read_delivery_members([archive], logical_paths=[ACTION])[0].logical == ACTION
    (setup / "pathlist.txt").write_text(ACTION + "\n", "utf-8")
    assert inputs.read_delivery_members([archive])[0].logical == ACTION
    (setup / "pathlist.txt").unlink()
    assert gate.check_bundle_keys([apk_file(setup)], zips=[archive])["status"] == "error"
    delivery(setup)
    archive.write_bytes(zip_bytes([(member_name("common", ACTION), ordered(["changed"]))]))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        inputs.read_delivery_members([archive])


def test_recovered_invalid_guesses_are_ignored_but_explicit_paths_are_strict(setup):
    (setup / "pathlist.txt").write_text(ACTION + "\ncharacter/example//bad.png\n", "utf-8")
    assert inputs.logical_candidates() == [ACTION]
    with pytest.raises(ValueError, match="invalid explicit logical path"):
        inputs.logical_candidates(["character/example//bad.png"])


def test_bundle_crc_corruption_is_error(setup):
    # Corrupt an unrelated APK entry while preserving its central-directory CRC.
    apk = apk_file(setup, outer=[("assets/bundle.zip", zip_bytes([
        (bundled_member(ACTION), ordered(["ranged"]))])), ("other.bin", b"unique payload")])
    apk.write_bytes(apk.read_bytes().replace(b"unique payload", b"damagedpayload"))
    result = gate.check_bundle_keys([apk], tables={ACTION: ordered(["custom"])})
    assert result["status"] == "error"
    assert "corrupt APK" in result["reason"]


@pytest.mark.parametrize("mutation", ["logical", "member_sha256", "files", "members", "size"])
def test_delivery_integrity_metadata_verified(setup, mutation):
    archive = delivery(setup)
    sidecar = archive.with_suffix(".integrity.json")
    doc = json.loads(sidecar.read_text("utf-8"))
    if mutation == "logical":
        doc[mutation][member_name("common", ACTION)] = OTHER
    elif mutation == "member_sha256":
        doc[mutation][member_name("common", ACTION)] = "0" * 64
    elif mutation == "files":
        doc[mutation] = []
    else:
        doc[mutation] += 1
    sidecar.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError):
        inputs.read_delivery_members([archive])


def test_delivery_cross_archive_overlay_is_explicit(setup):
    first = delivery(setup, name="first.zip")
    second = delivery(setup, name="second.zip", data=ordered(["later"]))
    with pytest.raises(ValueError, match="repeats members"):
        inputs.read_delivery_members([first, second])
    members = inputs.read_delivery_members([first, second], allow_overlays=True)
    assert [item.archive for item in members] == ["first.zip", "second.zip"]
    assert members[0].data != members[1].data


def test_delivery_duplicate_and_normalized_alias_members_rejected(setup):
    archive = setup / "duplicate.zip"
    member = member_name("common", ACTION)
    for other in (member, "/".join(member.split("/")[-2:])):
        archive.write_bytes(zip_bytes([(member, ordered(["x"])), (other, ordered(["y"]))]))
        with pytest.raises(ValueError, match="duplicate ZIP member"):
            inputs.read_delivery_members([archive])


def test_delivery_manifest_avoids_layered_archive_duplicates(setup):
    archive = delivery(setup)
    extra = setup / "layered.zip"
    extra.write_bytes(archive.read_bytes())
    (setup / "delivery-manifest.json").write_text(json.dumps({"archives": [{"name": archive.name}]}), "utf-8")
    assert inputs.delivery_zip_paths(delivery_dir=setup) == [archive.resolve()]
    (setup / "delivery-manifest.json").write_text(json.dumps({"archives": [{"name": "../outside.zip"}]}), "utf-8")
    with pytest.raises(ValueError):
        inputs.delivery_zip_paths(delivery_dir=setup)
