"""Real build chain and rejection of incomplete/stale shared-table candidates."""
import json
import shutil
import zipfile

import pytest
import wf_publish_guard as publish_guard
import wf_quest_lib as codec

from wf.boss.shop_model import ITEM, SOUL, STATUS, ENH_SHOP, SERVER_ENH
from wf.deliver.assert_box import verify
from wf.deliver.build import build_delivery
from wf.deliver.changeset import member_name, sha256
from wf.deliver.key_guard import AWAKENING, CUSTOM, check_shared_keys
from wf.studio.deliver_bridge import build_draft
from wf.studio.weapon_editor import compile_weapon
from wf.view import ManifestView
from weapon_delivery_fixture import case, create_draft


def build(fixture, wid, out):
    return build_draft(wid, from_version="1.4.132", to_version="1.4.133", out=out,
        store=fixture["store"], baseline_view=fixture["view"], server_dir=fixture["server_dir"],
        pathlist=fixture["pathlist"], provides=fixture["provides"])


def packed(delivery):
    result = {}
    for path in delivery.glob("pinball-*.zip"):
        with zipfile.ZipFile(path) as archive:
            result.update({name: archive.read(name) for name in archive.namelist()})
    return result


@pytest.mark.parametrize("restricted", [False, True])
def test_unmocked_build_preserves_shared_keys_records_and_server_inventory(tmp_path, restricted):
    fixture = case(tmp_path, restricted=restricted)
    baseline_files = {path: path.read_bytes() for path in fixture["server_dir"].rglob("*.json")}
    archive = next(fixture["active"].glob("*.zip"))
    original_archive = archive.read_bytes()
    wid, product = create_draft(fixture)
    out = tmp_path / "out"
    report = build(fixture, wid, out)
    assert report["prepush"]["exit_code"] == 0, report
    assert report["deviceValidation"] == "未执行"
    if restricted:
        # The registry has no M2 method-evidence entry for this capability.
        # A synthetic native parser cannot manufacture awakening support.
        assert report["ok"] is False
        assert any(check["blocking"] for check in report["compatChecks"])
        requires = json.loads((out / "delivery/requires.json").read_text("utf-8"))
        assert "equipment-awakening-material-v1" in json.dumps(requires["requires"]["unresolved"])
    else:
        assert report["ok"], report
    delivery = out / "delivery"
    members = packed(delivery)
    for logical, old in fixture["client"].items():
        name = member_name("common", logical)
        if name not in members or not logical.endswith(".orderedmap"):
            continue
        old_rows, new_rows = publish_guard._rows_of(old), publish_guard._rows_of(members[name])
        assert set(old_rows) <= set(new_rows), logical
        assert all(new_rows[key] == value for key, value in old_rows.items()), logical
    soul = codec.parse_node(members[member_name("common", SOUL)])
    assert soul[wid].count("\n") == 2  # all three source records survive the clone
    material = codec.parse_node(members[member_name("common", ENH_SHOP)])[product]
    assert ",1,9," in material
    for target, before in fixture["server"].items():
        filename = delivery / "server" / target
        if not filename.is_file():
            continue
        after = json.loads(filename.read_text("utf-8"))
        if isinstance(before, dict):
            if target == AWAKENING:
                for section, entries in before.items():
                    assert all(after[section][key] == value for key, value in entries.items())
            else:
                assert all(after[key] == value for key, value in before.items())
        else:
            assert all(value in after for value in before)
    assert json.loads((delivery / "server" / SERVER_ENH).read_text("utf-8"))[product]["costs"] == [
        {"id": 1, "amount": 9}]
    if restricted:
        strings = codec.parse_node(members[member_name("common", CUSTOM)])
        assert strings["awakening_material_" + wid] == "1"
        assert json.loads((delivery / "server" / AWAKENING).read_text("utf-8"))["materialByEquipment"][wid] == 1
    manifest = json.loads((delivery / "delivery-manifest.json").read_text("utf-8"))
    assert manifest["local_test_only"] and manifest["prepush"]["exit_code"] == 0
    assertions = json.loads((delivery / "assert-box.json").read_text("utf-8"))
    for entry in assertions["files"]:
        raw = members[entry["member"]] if entry["kind"] == "client" else (delivery / "server" / entry["target"]).read_bytes()
        assert entry["sha256"] == sha256(raw)
    gate = json.loads((delivery / "prepush.json").read_text("utf-8"))
    assert gate["shared_table_preservation"]["errors"] == []
    assert SOUL in gate["shared_table_preservation"]["client_tables"]
    assert gate["local_contract"]["server_pre_hashes_checked"]
    assert archive.read_bytes() == original_archive
    assert all(path.read_bytes() == data for path, data in baseline_files.items())


@pytest.mark.parametrize("fault", ["outer-key", "record", "malformed", "binary-row", "server-key", "server-missing"])
def test_incomplete_shared_files_are_rejected_before_archives(tmp_path, fault):
    fixture = case(tmp_path)
    source_id = fixture["source_id"]
    old = fixture["client"][SOUL]
    table = codec.parse_node(old)
    raw = codec.build_node({}) if fault == "outer-key" else (
        codec.build_node({source_id: table[source_id].splitlines()[0]}) if fault == "record" else
        codec.build_node({source_id: "\x00"}) if fault == "binary-row" else
        b"broken orderedmap" if fault == "malformed" else old)
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "client").write_bytes(raw)
    doc = {"schema": "wf-change-set/1", "id": "unsafe", "name": "unsafe", "slug": "unsafe",
        "created_at": "2026-10-25", "from_version": "1.4.132", "to_version": "1.4.133",
        "local_test_only": True, "members": [{"root": "common", "logical_path": SOUL,
        "source": "client", "sha256": sha256(raw), "before_sha256": sha256(old)}]}
    if fault.startswith("server"):
        target = "assets/equipment_lookup.json"
        (staged / "server").write_bytes(b"{}")
        original = (fixture["server_dir"] / target).read_bytes()
        doc["server_changes"] = [{"target": target, "source": "server", "sha256": sha256(b"{}"),
            "before_sha256": sha256(original)}]
        if fault == "server-missing":
            (fixture["server_dir"] / target).unlink()
    filename = staged / "changeset.json"
    filename.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(ValueError, match="shared-table preservation failed"):
        build_delivery(filename, tmp_path / "out", baseline_view=fixture["view"],
                       server_dir=fixture["server_dir"], provides=fixture["provides"])
    assert not (tmp_path / "out").exists()


def test_claims_are_checked_only_against_matching_baseline_table(tmp_path):
    fixture = case(tmp_path)
    members = {member_name("common", SOUL): (codec.build_node({}), {"logical_path": SOUL})}
    report = check_shared_keys(members, {}, baseline=fixture["view"], protected={
        SOUL: {fixture["source_id"], "future-not-in-this-baseline"}, ITEM: {"unrelated-table"}})
    assert any("protected character-pack claims" in error for error in report["errors"])
    assert "future-not-in-this-baseline" not in str(report)
    assert "unrelated-table" not in str(report)


def test_nested_weapon_curves_cannot_lose_existing_level_keys(tmp_path):
    fixture = case(tmp_path)
    rows = codec.parse_node(fixture["client"][STATUS])
    del rows[fixture["source_id"]]["1"]
    members = {member_name("common", STATUS): (codec.build_node(rows), {"logical_path": STATUS})}
    report = check_shared_keys(members, {}, baseline=fixture["view"], protected={})
    assert any("lost nested baseline key" in error for error in report["errors"])


def test_two_same_edge_drafts_are_alternatives_and_stale_second_is_rejected(tmp_path):
    fixture = case(tmp_path)
    first, _ = create_draft(fixture, "5950001")
    second, _ = create_draft(fixture, "5950002")
    for wid in (first, second):
        result = build(fixture, wid, tmp_path / wid)
        assert result["ok"], result
        candidate = codec.parse_node(packed(tmp_path / wid / "delivery")[member_name("common", SOUL)])
        assert fixture["source_id"] in candidate and wid in candidate
        assert len(candidate) == 2  # These are two alternatives for one version edge.
    first_delivery = tmp_path / first / "delivery"
    for filename in (first_delivery / "server").rglob("*.json"):
        shutil.copyfile(filename, fixture["server_dir"] / filename.relative_to(first_delivery / "server"))
    with pytest.raises(ValueError, match="SHA-256 drift"):
        compile_weapon(fixture["source"], fixture["store"], fixture["store"].load(second),
                       server_dir=fixture["server_dir"], provides=fixture["provides"])
    assertions = json.loads((tmp_path / second / "delivery/assert-box.json").read_text("utf-8"))
    assertions["files"] = [entry for entry in assertions["files"] if entry["kind"] == "server"]
    assert verify(assertions, phase="pre", server_dir=fixture["server_dir"], manifest={"cdn_version": "1.4.132"})
    manifest = json.loads(fixture["manifest"].read_text("utf-8"))
    manifest["cdn_version"] = "1.4.133"
    edge = json.loads((first_delivery / "manifest-entry-1.4.133.json").read_text("utf-8"))
    manifest["patches"].append(edge)
    fixture["manifest"].write_text(json.dumps(manifest), "utf-8")
    with pytest.raises(ValueError, match="occupied|stale"):
        build(fixture, second, tmp_path / "stale")
    latest = ManifestView("1.4.133", store=fixture["view"].store, manifest=fixture["manifest"],
                          search_dirs=[fixture["active"], first_delivery])
    with pytest.raises(ValueError, match="基线版本.*不一致"):
        build_draft(second, from_version="1.4.133", to_version="1.4.134", out=tmp_path / "new-view",
            store=fixture["store"], baseline_view=latest, provides=fixture["provides"],
            server_dir=fixture["server_dir"])
