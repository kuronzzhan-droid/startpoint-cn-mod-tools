"""Real orderedmap/SWF bytes for offline delivery tests; no patched functions."""
import copy
import json
from pathlib import Path
import zipfile

import wf_describe
import wf_quest_lib as codec
from wf.apk.bodies import label_map
from wf.apk.swfabc import PoolEditor, SwfAbc
from wf.boss import schema as s
from wf.boss.shop_model import ITEM, SOUL, STATUS, ENH, ENH_ABILITY, ENH_STATUS, ENH_SHOP, SERVER_ENH
from wf.deliver.changeset import member_name, sha256
from wf.deliver.key_guard import AWAKENING, CUSTOM
from wf.studio.drafts import new_change_id, now
from wf.studio.source import StudioSource
from wf.studio.weapon_editor import _replay
from wf.studio.weapon_store import WeaponDraftStore
from wf.view import ManifestView
from wf.view.base149 import join
from test_m23_apk_kinds import _code, _fixture_swf


def case(root, *, restricted=False):
    """Synthetic native branches prove inspection plumbing, never game runtime."""
    source_id = "5910101" if restricted else "5010005"
    donor = json.loads(Path("assets/bond-weapons/official_baseline.json").read_bytes())["weapons"]["5010005"]
    equipment = list(donor["equipment"])
    equipment[6], equipment[10] = "item/weapon", source_id
    item = [""] * 23
    item[0:7], item[12] = ["soul", source_id, "soul", "item/soul", "(None)", "", "11"], "0,3,2,1,4,5"
    soul = donor["soul"][0]
    ability = [soul[0], "1", "120", "0", "0", *soul[2:]]
    stage = [""] * 50
    stage[0], stage[2], stage[3] = "7", source_id, "1"
    stage[14:22] = ["1", "2", "(None)", "", "(None)", "", "(None)", ""]
    stage[29:32] = [source_id, "120", "5"]
    product = str(int(source_id) * 100 + 1)
    tables = {s.EQUIPMENT: {source_id: join(equipment)}, ITEM: {source_id: join(item), "1": join(item)},
        SOUL: {source_id: "\n".join([join(soul)] * 3)},
        ENH_ABILITY: {source_id: "\n".join([join(ability)] * 2)},
        STATUS: {source_id: {"1": "100,20", "5": "200,40"}},
        ENH_STATUS: {source_id: {"1": "1,1", "120": "120,120"}},
        ENH: {source_id: "120,70,Weapon,70,item/enhanced,70,Description,120,2000-01-01"},
        ENH_SHOP: {product: join(stage)}, CUSTOM: {"legacy_keep": "untouched"},
        "master/ability/ability.orderedmap": {}, "master/ability/leader_ability.orderedmap": {}}
    tables["master/character/character.orderedmap"] = {}
    if restricted:
        tables[CUSTOM]["awakening_material_" + source_id] = "1"
    client = {logical: codec.build_node(table) for logical, table in tables.items()}
    client.update({logical: b"png" for logical in ("item/weapon.png", "item/soul.png", "item/enhanced.png")})
    server = {SERVER_ENH: {product: {"equipmentId": int(source_id), "groupId": int(source_id),
        "costs": [{"id": 1, "amount": 2}], "enhancementMaxLevel": 120, "enhancementPurchaseMode": "per_level"}},
        "assets/equipment_lookup.json": {source_id: {"name": "Weapon", "rarity": "5"}},
        "assets/equipment_max_level.json": {source_id: 5}, "assets/equipment_element.json": {source_id: -1},
        "assets/item_sale.json": {source_id: {"sale_price": 5}}, "assets/item_lookup.json": {},
        "assets/equipment_ids.json": [int(source_id)], "assets/item_ids.json": [1, int(source_id)],
        AWAKENING: {"materialByEquipment": {source_id: 1} if restricted else {},
                    "rarityOverrides": {"8000101": 5}, "officialCrystals": {"12001": {"maxRarity": 4}}}}
    server_dir = root / "server"
    (server_dir / "assets").mkdir(parents=True)
    for target, document in server.items():
        (server_dir / target).write_text(json.dumps(document, indent=2), "utf-8")
    active, store = root / "active", root / "store"
    active.mkdir()
    store.mkdir()
    archive_name = "pinball-1.4.131-1.4.132-1-fixture.zip"
    with zipfile.ZipFile(active / archive_name, "w") as archive:
        for logical, raw in client.items():
            archive.writestr(member_name("common", logical), raw)
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"cdn_version": "1.4.132", "patches": [{"version": "1.4.132",
        "depends_on": "1.4.131", "chain": [archive_name], "type": "patch"}]}), "utf-8")
    view = ManifestView("1.4.132", store=store, manifest=manifest, search_dirs=[active])
    source = StudioSource(view, official_root=root / "absent-official")
    drafts = WeaponDraftStore(root / "drafts/weapons")
    swf = SwfAbc.from_bytes(_fixture_swf(equipment_r3=False), source=root / "synthetic.swf")
    pool = PoolEditor(swf.abc)
    kinds = [pool.string("32"), pool.string("34")]
    for index, label in label_map(swf.abc).items():
        for table, name in (("ability_soul", "AbilitySoulValues"),
                            ("equipment_enhancement_ability", "EquipmentEnhancementAbilityValues")):
            if label == f"{name}$/parseAt{wf_describe.layout(table)['blocks']['instant_content']}":
                swf.abc.bodies[index][5] = _code(kinds)
    swf_path = root / "fixture.swf"
    swf_path.write_bytes(swf.serialize())
    provides = root / "provides.json"
    provides.write_text(json.dumps({"schema": "wf-apk-provides/1", "source": {
        "kind": "swf", "basis": "Synthetic parser-only fixture; no device or awakening-method evidence",
        "path": str(swf_path), "swf_sha256": sha256(swf_path.read_bytes())}, "patches": [],
        "provides": [], "unresolved": [], "limitations": ["Not a playable or shipped client"]}), "utf-8")
    pathlist = root / "pathlist.txt"
    pathlist.write_text("\n".join(client), "utf-8")
    return {"root": root, "source_id": source_id, "source": source, "view": view, "store": drafts,
            "server_dir": server_dir, "client": client, "server": server, "provides": provides,
            "pathlist": pathlist, "manifest": manifest, "active": active}


def create_draft(fixture, wid="5950001"):
    requests = [{"operation": "weapon_clone", "weapon": {"sourceWeapon": fixture["source_id"],
        "id": wid, "name": "Delivery weapon", "soul_elements": [1], "soulDescription": "Delivery soul"}}]
    options = {"server_dir": fixture["server_dir"], "reserved": {}, "provides": fixture["provides"]}
    state, _ = _replay(fixture["source"], wid, requests, **options)
    product = requests[0]["weapon"]["enhancementProducts"][0]
    requests.append({"operation": "weapon_materials", "weapon": {"id": wid,
        "stages": [{"productId": product, "costs": [{"itemId": "1", "amount": 9}]}]}})
    state, _ = _replay(fixture["source"], wid, requests, **options)
    change = {"id": new_change_id(), "kind": "weapon", "title": "真实交付测试", "createdAt": now(),
        "target": {"weapon": wid}, "params": {"requests": copy.deepcopy(requests), "inputs": state.snapshot()},
        "files": [], "pending": [], "checks": []}
    fixture["store"].put_change(wid, "weapon_" + wid, "1.4.132", change)
    fixture["store"].save(wid)
    return wid, product
