"""Read-only scene allocation checks the complete derived identity graph."""
from collections import Counter
import copy
import json

import pytest
import wf_quest_lib as codec

from wf.boss.scene_allocate import EVENTS, allocate_scene
from wf.boss.scene_import import AQ
from wf.boss.scene_server import FILES
from wf.boss.scene_server_projection import ITEM, SHOP


@pytest.fixture
def allocation():
    spec = {"schema": "wf-boss-scene/1", "id": "hell-pumpkin", "name": "来源场景", "sourceVersion": "1.4.351",
        "event": {"id": "300097", "settings": []},
        "tiers": [{"id": str(i), "quest": f"30009700{i}", "settings": []} for i in range(1, 6)],
        "phases": [{"id": "p1", "settings": []}], "shops": [{"id": "9730001", "settings": []}],
        "drops": [{"id": "drop", "settings": []}], "summons": [], "mechanisms": [], "trials": [],
        "tables": [{"logical": EVENTS, "entries": [{"path": ["300097"], "value": "mod_hell_pumpkin,,来源场景"}]},
                   {"logical": AQ, "entries": [{"path": ["300097", str(i)], "value": f"30009700{i},row"} for i in range(1, 6)]},
                   {"logical": SHOP, "entries": [{"path": ["9730001"], "value": "0,300097,shop"}]},
                   {"logical": ITEM, "entries": [{"path": ["10009701"], "value": "mod_hp_candy,10009701,糖果"}]}],
        "resources": [{"logical": "battle/action/enemy/action/mod/hell_pumpkin/hp_main.action.dsl.amf3.deflate",
                       "encoding": "amf3", "value": ["Nothing"]}], "requirements": []}
    data = {EVENTS: codec.build_node({"300097": "source"}), AQ: codec.build_node({"unrelated": "keep"}),
            SHOP: codec.build_node({"unrelated": "keep"}), ITEM: codec.build_node({"unrelated": "keep"})}
    reads = Counter()
    def load(logical):
        reads[logical] += 1
        if logical not in data:
            raise FileNotFoundError(logical)
        return data[logical]
    return spec, data, reads, load


def server(root, *, quest=None, currency=None):
    for name in FILES:
        path = root / "assets" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        value = [] if name == "item_ids.json" else {}
        if name == "advent_event_quest.json" and quest:
            value = {quest: {"name": "occupied"}}
        if name == "item_ids.json" and currency:
            value = [currency]
        path.write_text(json.dumps(value), encoding="utf8")


def test_scene_allocate_skips_derived_shop_even_when_event_itself_is_free(allocation):
    spec, data, reads, load = allocation
    data[SHOP] = codec.build_node({"30000101": "occupied derived product"})
    original_spec, original_data = copy.deepcopy(spec), copy.deepcopy(data)
    cloned = allocate_scene(spec, load)
    assert cloned["event"]["id"] == "300002"
    assert [tier["quest"] for tier in cloned["tiers"]] == [f"30000200{i}" for i in range(1, 6)]
    assert all(reads[table["logical"]] == 1 for table in spec["tables"])
    assert spec == original_spec and data == original_data
    assert not cloned["provenance"]["allocation"]["reserved"]


def test_scene_allocate_skips_server_quest_and_reserved_then_existing_resource(allocation, tmp_path):
    spec, data, _, load = allocation
    server(tmp_path, quest="300001001")
    data["battle/action/enemy/action/mod/studio_scene_300003/hp_main.action.dsl.amf3.deflate"] = b"occupied"
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")}
    cloned = allocate_scene(spec, load, server_dir=tmp_path, reserved=["300002"])
    assert cloned["event"]["id"] == "300004"
    assert cloned["provenance"]["allocation"]["serverSnapshotChecked"]
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*.json")} == before


def test_scene_allocate_checks_server_item_id_list(allocation, tmp_path):
    spec, _, _, load = allocation
    server(tmp_path, currency=30000151)
    assert allocate_scene(spec, load, server_dir=tmp_path)["event"]["id"] == "300002"


@pytest.mark.parametrize("currency,expected", [(None, "300001"), (30000151, "300002")])
def test_scene_allocate_watch_group_is_not_server_identity(allocation, tmp_path, monkeypatch, currency, expected):
    spec, data, _, load = allocation
    watch = "master/battle/boss/general_enemy_watch.orderedmap"
    path = ["1", "mod_hp_rage_ego", "mod_hp_rage_ego", "1", "mod_hp_rage", "mod_hp_rage"]
    spec["tables"].append({"logical": watch, "entries": [{"path": path, "value": "0,1"}]})
    tree = "0,1"
    for key in reversed(path):
        tree = {key: tree}
    data[watch] = codec.build_node(tree)
    server(tmp_path, quest="1", currency=currency)
    # Keep a future false collision from scanning hundreds of thousands of IDs.
    monkeypatch.setattr("wf.boss.scene_allocate.range", lambda *_: range(300001, 300004), raising=False)
    cloned = allocate_scene(spec, load, server_dir=tmp_path)
    assert cloned["event"]["id"] == expected
    targets = [target for target in cloned["creation"]["tableTargets"] if target["logical"] == watch]
    assert targets and targets[0]["path"][0] == "1"
    assert not cloned["provenance"]["allocation"]["reserved"]


def test_scene_allocate_checks_current_event_and_currency_table(allocation):
    spec, data, _, load = allocation
    data[EVENTS] = codec.build_node({"300001": "occupied", "300097": "source"})
    data[ITEM] = codec.build_node({"30000251": "occupied"})
    assert allocate_scene(spec, load)["event"]["id"] == "300003"


def test_scene_allocate_missing_server_evidence_fails_closed(allocation, tmp_path):
    spec, _, _, load = allocation
    with pytest.raises(ValueError, match="镜像不完整"):
        allocate_scene(spec, load, server_dir=tmp_path)


def test_scene_allocate_missing_client_table_is_unknown_not_free(allocation):
    spec, data, _, load = allocation
    del data[ITEM]
    with pytest.raises(ValueError, match="无法证明新 ID 未占用"):
        allocate_scene(spec, load)


@pytest.mark.parametrize("reserved", ["300001", ["bad"], ["1"]])
def test_scene_allocate_rejects_invalid_reserved_ids(allocation, reserved):
    spec, _, _, load = allocation
    with pytest.raises(ValueError):
        allocate_scene(spec, load, reserved=reserved)
