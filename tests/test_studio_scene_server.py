"""Scene economic projections use synthetic mirrors and never touch real server files."""
import copy
import json
from types import SimpleNamespace

import pytest

from wf.boss.scene_import import AQ
from wf.boss.scene_server import FILES, server_candidate
from wf.boss.scene_server_projection import ITEM, RARE, SCORE, SHOP
from wf.boss.schema import iter_leaves


def csv(row):
    return ",".join(map(str, row))


def put(root, name, value):
    path = root / "assets" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def change(case, logical, path, column, value):
    node = case.tables[logical]
    for key in path[:-1]:
        node = node[key]
    row = node[path[-1]].split(",")
    row[column] = str(value)
    node[path[-1]] = csv(row)


@pytest.fixture
def case(tmp_path):
    quest_rows, server_quests, tiers = {}, {}, []
    for index in range(1, 6):
        qid = "100" + str(index)
        row = [""] * 132
        for column, value in {0: qid, 2: "client name", 4: 31, 76: 9001, 77: 32,
                              90: 816, 91: 621, 92: 426, 93: 270,
                              97: 3, 98: 4, 99: 47, 100: 117}.items():
            row[column] = str(value)
        quest_rows[str(index)] = csv(row)
        tiers.append({"id": str(index), "quest": qid})
        server_quests[qid] = {"name": "old server name", "clearRewardId": 31,
            "scoreRewardGroupId": 9001, "element": 9001, "sPlusRewardId": 32,
            "bRankTime": 816000, "aRankTime": 621000, "sRankTime": 426000, "sPlusRankTime": 270000,
            "rankPointReward": 3, "characterExpReward": 4, "manaReward": 47, "poolExpReward": 117,
            "unknownNativeField": "retain"}
    product = [""] * 51
    for column, value in {0: 0, 1: 1, 18: 8001, 19: 500, 26: "2000-01-01 00:00:00",
                          27: "(None)", 29: 5, 32: 0, 33: 8001, 34: 2}.items():
        product[column] = str(value)
    tables = {AQ: {"1": quest_rows}, SHOP: {"7001": csv(product)}, ITEM: {"8001": "candy_code,8001,糖果名称"},
        SCORE: {"9001": {"1": "pool,0,0,8001,18,1000,,", "2": "pool,1,,,,,9101,0.1"}},
        RARE: {"9101": {"1": "rare,0,8001,50,1,true"}}}
    docs = {"advent_event_quest.json": server_quests,
        "score_reward_cnmod.json": {"9001": [
            {"position": 1, "name": "", "type": 0, "reward_type": 0, "id": 8001, "count": 18, "field5": 1000},
            {"position": 2, "name": "", "type": 1, "id": 9101, "rarity": 0.095}]},
        "rare_score_reward_cnmod.json": {"9101": [{"name": "", "type": 0, "id": 8001, "count": 50, "rarity": 1.0}]},
        "event_item_shop.json": {"0": {"1": {"7001": {"costs": [{"id": 8001, "amount": 500}],
            "rewards": [{"type": 0, "id": 8001, "count": 2}], "availableFrom": "2000-01-01 00:00:00",
            "availableUntil": None, "stock": 5}}}, "unrelated": {"kept": True}},
        "event_item_shop_id_map.json": {"7001": {"eventType": 0, "eventId": 1}},
        "item_ids.json": [1, 8001], "item_lookup_cnmod.json": {"8001": "糖果名称", "1": "untouched"}}
    for name, value in docs.items():
        put(tmp_path, name, value)
    spec = {"event": {"id": "1"}, "tiers": tiers, "shops": [{"id": "7001"}],
            "tables": [{"logical": logical, "entries": [{"path": list(path), "value": value}
                for path, value in iter_leaves(tree)]} for logical, tree in tables.items()]}
    state = SimpleNamespace(table=lambda name: copy.deepcopy(tables.get(name, {})))
    return SimpleNamespace(root=tmp_path, state=state, tables=tables, spec=spec, docs=docs)


def test_scene_server_no_edit_preserves_actual_bytes_and_discloses_baseline_drift(case):
    before = snapshot(case.root)
    files, hashes, checks = server_candidate(case.state, case.spec, case.root)
    assert files == {} and len(hashes) == 7
    assert snapshot(case.root) == before
    assert not any(check["blocking"] for check in checks)
    drift = next(check for check in checks if check["rule"] == "scene.server-baseline")
    assert len(drift["differences"]) == 5
    assert {entry["field"] for entry in drift["differences"]} == {"name"}


def test_scene_server_quest_changes_sync_real_columns_without_resetting_unedited_fields(case):
    for column, value in {4: 34, 77: 33, 90: 700, 97: 9, 98: 10, 99: 60, 100: 80}.items():
        change(case, AQ, ["1", "1"], column, value)
    files, _, checks = server_candidate(case.state, case.spec, case.root)
    assert not any(check["blocking"] for check in checks)
    output = json.loads(files["assets/advent_event_quest.json"])
    row = output["1001"]
    assert row["clearRewardId"] == 34 and row["sPlusRewardId"] == 33 and row["bRankTime"] == 700000
    assert [row[key] for key in ("rankPointReward", "characterExpReward", "manaReward", "poolExpReward")] == [9, 10, 60, 80]
    assert row["name"] == "old server name" and row["unknownNativeField"] == "retain"
    assert output["1002"] == case.docs["advent_event_quest.json"]["1002"]


def test_scene_server_shop_and_currency_use_real_name_column(case):
    change(case, SHOP, ["7001"], 19, 125)
    change(case, SHOP, ["7001"], 29, 3)
    change(case, ITEM, ["8001"], 2, "新的糖果名")
    files, _, checks = server_candidate(case.state, case.spec, case.root)
    assert not any(check["blocking"] for check in checks)
    product = json.loads(files["assets/event_item_shop.json"])
    assert product["0"]["1"]["7001"]["costs"] == [{"id": 8001, "amount": 125}]
    assert product["0"]["1"]["7001"]["stock"] == 3
    assert product["unrelated"] == {"kept": True}
    assert json.loads(files["assets/item_lookup_cnmod.json"])["8001"] == "新的糖果名"


def test_scene_server_drop_edit_preserves_labels_and_probability_correction(case):
    case.docs["score_reward_cnmod.json"]["9001"][0]["name"] = "historical server label"
    put(case.root, "score_reward_cnmod.json", case.docs["score_reward_cnmod.json"])
    change(case, SCORE, ["9001", "1"], 4, 25)
    change(case, SCORE, ["9001", "2"], 7, .2)
    change(case, RARE, ["9101", "1"], 3, 70)
    files, _, checks = server_candidate(case.state, case.spec, case.root)
    assert not any(check["blocking"] for check in checks)
    score = json.loads(files["assets/score_reward_cnmod.json"])["9001"]
    assert score[0]["count"] == 25 and score[0]["name"] == "historical server label"
    assert score[1]["rarity"] == .195
    assert json.loads(files["assets/rare_score_reward_cnmod.json"])["9101"][0]["count"] == 70


def new_scene(case):
    mapping = {"1": "2", "7001": "7002", "8001": "8002", "9001": "9002", "9101": "9102",
               **{f"100{i}": f"200{i}" for i in range(1, 6)}}
    spec = copy.deepcopy(case.spec)
    spec["event"]["id"] = "2"
    spec["creation"] = {"sourceEvent": "1"}
    for tier in spec["tiers"]:
        tier["sourceQuest"] = tier["quest"]
        tier["quest"] = mapping[tier["quest"]]
    spec["shops"][0]["id"] = "7002"
    for table in spec["tables"]:
        for entry in table["entries"]:
            entry["path"][0] = mapping.get(entry["path"][0], entry["path"][0])
            row = entry["value"].split(",")
            # Only identifiers are remapped; numeric counts/rates remain values.
            indices = {AQ: [0, 76], SHOP: [1, 18, 33], ITEM: [1], SCORE: [3, 6], RARE: [2]}[table["logical"]]
            for index in indices:
                row[index] = mapping.get(row[index], row[index])
            entry["value"] = csv(row)
            node = case.tables[table["logical"]]
            for key in entry["path"][:-1]:
                node = node.setdefault(key, {})
            node[entry["path"][-1]] = entry["value"]
    return spec


def test_scene_server_creation_clones_explicit_readonly_mothers_and_adds_economic_graph(case):
    spec = new_scene(case)
    before = snapshot(case.root)
    files, _, checks = server_candidate(case.state, spec, case.root)
    assert not any(check["blocking"] for check in checks)
    assert len(files) == len(FILES) and snapshot(case.root) == before
    quests = json.loads(files["assets/advent_event_quest.json"])
    assert quests["1001"] == case.docs["advent_event_quest.json"]["1001"]
    assert quests["2001"]["name"] == "client name" and quests["2001"]["scoreRewardGroupId"] == 9002
    assert quests["2001"]["unknownNativeField"] == "retain"
    assert json.loads(files["assets/event_item_shop_id_map.json"])["7002"] == {"eventType": 0, "eventId": 2}
    assert json.loads(files["assets/item_ids.json"]) == [1, 8001, 8002]
    assert json.loads(files["assets/item_lookup_cnmod.json"])["8002"] == "糖果名称"


@pytest.mark.parametrize("failure", ["mother", "qid", "shop-map", "score-link", "rare-link", "currency", "type"])
def test_scene_server_invalid_inputs_block_without_writes(case, failure):
    if failure == "mother":
        del case.docs["advent_event_quest.json"]["1001"]
        put(case.root, "advent_event_quest.json", case.docs["advent_event_quest.json"])
    elif failure == "qid":
        case.spec["tiers"][0]["quest"] = "99999"
    elif failure == "shop-map":
        put(case.root, "event_item_shop_id_map.json", {"7001": {"eventType": 0, "eventId": 20}})
    elif failure == "score-link":
        change(case, AQ, ["1", "1"], 76, 9999)
    elif failure == "rare-link":
        change(case, SCORE, ["9001", "2"], 6, 9999)
    elif failure == "currency":
        change(case, SHOP, ["7001"], 18, 9999)
    else:
        put(case.root, "item_lookup_cnmod.json", [])
    before = snapshot(case.root)
    files, _, checks = server_candidate(case.state, case.spec, case.root)
    assert files == {} and any(check["blocking"] for check in checks)
    assert snapshot(case.root) == before


def test_scene_server_missing_creation_mother_and_collision_block(case):
    spec = new_scene(case)
    spec["tiers"][0]["sourceQuest"] = "missing"
    assert any(check["blocking"] for check in server_candidate(case.state, spec, case.root)[2])
    spec["tiers"][0]["sourceQuest"] = "1001"
    case.docs["advent_event_quest.json"]["2001"] = {}
    put(case.root, "advent_event_quest.json", case.docs["advent_event_quest.json"])
    assert any(check["blocking"] for check in server_candidate(case.state, spec, case.root)[2])
