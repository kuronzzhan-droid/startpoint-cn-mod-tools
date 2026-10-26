"""A standalone weapon draft produces a real local delivery from a locked view."""
import json
import zipfile

import wf_quest_lib as codec

from test_boss_shop_weapon import state  # noqa: F401 - binary native graph fixture
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL, ENH_SHOP, SERVER_ENH
from wf.deliver.changeset import member_name, sha256
from wf.studio.deliver_bridge import build_draft
from wf.studio.source import StudioSource
from wf.studio.weapon_editor import WeaponEditor
from wf.studio.weapon_store import WeaponDraftStore
from wf.view import ManifestView


def test_standalone_weapon_builds_real_archives_server_mirrors_and_assertions(state, tmp_path, monkeypatch):
    active, store = tmp_path / "active", tmp_path / "store"
    active.mkdir()
    store.mkdir()
    # The delivery DSL gate reads all native ability tables, even for a weapon-only edge.
    for logical in ("master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"):
        state.base.files[logical] = codec.build_node({})
    archive_name = "pinball-1.4.131-1.4.132-1-weapon-fixture.zip"
    with zipfile.ZipFile(active / archive_name, "w") as archive:
        for logical, raw in state.base.files.items():
            archive.writestr(member_name("common", logical), raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [
        {"version": "1.4.132", "depends_on": "1.4.131", "chain": [archive_name], "type": "patch"}]}),
        encoding="utf-8")
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[active])
    source = StudioSource(view, official_root=tmp_path / "absent-official")
    drafts = WeaponDraftStore(tmp_path / "drafts" / "weapons")
    editor = WeaponEditor(source, store=drafts, server_dir=state.server_dir)
    server_before = {path: path.read_bytes() for path in (state.server_dir / "assets").glob("*.json")}
    client_before = (active / archive_name).read_bytes()

    created = editor.apply("weapon_clone", {"sourceWeapon": "5010005", "name": "Delivery weapon",
                                           "soul_elements": [1], "soulDescription": "Delivery soul"})
    wid = created["weaponId"]
    product = created["allocation"]["enhancementProducts"][0]
    editor.apply("weapon_materials", {"id": wid, "stages": [
        {"productId": product, "costs": [{"itemId": "1", "amount": 9}]}]}, wid=wid)
    drafts.save(wid)

    # Native kind branches are a synthetic unit fixture, just as in ``state``.
    # The real compile, requirement scan, archives, prepush and read-back run below.
    evidence = {"schema": "wf-apk-provides/1", "source": {
        "kind": "swf", "basis": "synthetic native branch fixture", "swf_sha256": "a" * 64},
        "patches": [], "provides": [], "unresolved": [], "limitations": []}
    provides = tmp_path / "provides.json"
    provides.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr("wf.apk.kinds.inspect_provides", lambda *args, **kwargs: {
        "source": evidence["source"], "mismatches": [], "tables": {table: {
            "instant_content": {"kinds": ["32", "34"]}}
            for table in ("ability_soul", "equipment_enhancement_ability")}})
    pathlist = tmp_path / "pathlist.txt"
    pathlist.write_text("\n".join(state.base.files), encoding="utf-8")
    out = tmp_path / "out"
    result = build_draft(wid, from_version="1.4.132", to_version="1.4.133", store=drafts,
                         baseline_view=view, server_dir=state.server_dir, pathlist=pathlist,
                         provides=provides, out=out)
    assert result["ok"], result
    assert result["prepush"]["exit_code"] == 0

    delivery = out / "delivery"
    document = json.loads((out / "inputs/changeset.json").read_text("utf-8"))
    assert document["id"].startswith("studio-weapon-") and document["local_test_only"] is True
    packed = {}
    for filename in delivery.glob("pinball-*.zip"):
        with zipfile.ZipFile(filename) as archive:
            packed.update({name: archive.read(name) for name in archive.namelist()})
    equipment = codec.parse_node(packed[member_name("common", s.EQUIPMENT)])
    item = codec.parse_node(packed[member_name("common", ITEM)])
    soul = codec.parse_node(packed[member_name("common", SOUL)])
    stages = codec.parse_node(packed[member_name("common", ENH_SHOP)])
    assert s.parse_rows(equipment[wid])[0][1] == "Delivery weapon"
    assert s.parse_rows(item[wid])[0][5] == "Delivery soul"
    assert s.parse_rows(item[wid])[0][12] == "1" and wid in soul
    assert s.parse_rows(stages[product])[0][14:16] == ["1", "9"]
    mirrored = json.loads((delivery / "server" / SERVER_ENH).read_text("utf-8"))
    assert mirrored[product]["equipmentId"] == int(wid)
    assert mirrored[product]["costs"] == [{"id": 1, "amount": 9}]
    assert int(wid) in json.loads((delivery / "server/assets/item_ids.json").read_text("utf-8"))

    assertions = json.loads((delivery / "assert-box.json").read_text("utf-8"))["files"]
    for entry in assertions:
        raw = (packed[entry["member"]] if entry["kind"] == "client"
               else (delivery / "server" / entry["target"]).read_bytes())
        assert entry["sha256"] == sha256(raw)
    client_assertion = next(entry for entry in assertions if entry.get("member") == member_name("common", ITEM))
    assert client_assertion["before_sha256"] == sha256(state.base.files[ITEM])
    prepush = json.loads((delivery / "prepush.json").read_text("utf-8"))
    assert prepush["local_contract"]["pre_and_post_hashes_checked"]
    assert prepush["local_contract"]["server_pre_hashes_checked"]
    assert prepush["local_contract"]["server_post_hashes_checked"]
    assert not prepush["local_contract"]["errors"]
    assert (active / archive_name).read_bytes() == client_before
    assert all(path.read_bytes() == raw for path, raw in server_before.items())
