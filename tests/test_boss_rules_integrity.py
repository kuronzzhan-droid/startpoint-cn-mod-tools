"""Entry, shop and reward gates share delivery semantics and explicit states."""
import json
import struct

from wf.deliver.prepush_rewards import SERVER_REWARD_PATHS
from wf.rules.boss_atlas import atlas_check
from wf.rules.boss_integrity import (both_route_check, choice_check, collision_check, prerequisite_check,
                                    reward_check, shop_check, time_check)


class View:
    def __init__(self, tables=None, files=None):
        self.tables, self.files = tables or {}, files or {}

    def table(self, logical):
        return self.tables.get(logical)

    def raw(self, logical):
        return self.files.get(logical)


def quest(kind="hard_multi"):
    row = [""] * 125
    row[0], row[5], row[6] = "2000001", "2000-01-01 00:00:00", "(None)"
    return {"quest": {"id": "2000001", "kind": kind, "row": row}}


def test_custom_time_checks_quest_and_event_rows():
    doc = quest()
    assert time_check(doc, {})["status"] == "未执行"
    assert time_check(doc, {"custom_content": True})["status"] == "满足"
    doc["entrance"] = {"event": {"row": [""] * 23 + ["2026-10-18 00:00:00", "(None)"]}}
    assert time_check(doc, {"custom_content": True})["blocking"]


def test_common_battle_prerequisite_is_blocking():
    doc = quest()
    assert prerequisite_check(doc, {"custom_content": True})["status"] == "满足"
    doc["quest"]["row"][16] = "1066004"
    assert prerequisite_check(doc, {"custom_content": True})["blocking"]
    assert prerequisite_check(doc)["status"] == "未执行"
    doc["quest"]["kind"] = "boss_battle"
    assert prerequisite_check(doc)["status"] == "不适用"


def test_choice_uses_explicit_intent_and_folder_boundary():
    assert choice_check({})["status"] == "未执行"
    assert choice_check({"choice_count": 3, "choice_level": "quest"})["blocking"]
    assert choice_check({"choice_count": 3, "choice_level": "folder"})["status"] == "满足"


def test_bothboss_checks_actual_two_round_routes():
    doc = quest("boss_battle")
    doc["quest"]["row"][122] = "true"
    hidden = [""] * 125
    hidden[0], hidden[123] = "2000002", "true"
    view = View({"master/quest/both_boss/both_boss_group.orderedmap": {"2000001": "route,10"},
                 "master/quest/both_boss/both_boss_map.orderedmap": {"10": ["map"] + [""] * 10 + ["2000002"] * 4},
                 "master/quest/boss_battle_quest.orderedmap": {"1": {"1": {"2": hidden}}}})
    assert both_route_check(doc, view, {})["status"] == "满足"
    hidden[123] = "false"
    assert both_route_check(doc, view, {})["blocking"]
    assert both_route_check(quest(), view, {"both_boss": True})["blocking"]
    assert both_route_check(doc, view, {"both_boss_purpose": "simultaneous"})["blocking"]


def test_collision_checks_all_identity_domains():
    context = {"new_ids": {"quest": ["1"], "zone": ["z"], "node": ["7"]},
               "existing_ids": {"quest": ["2"], "zone": ["other"], "node": ["7"]}}
    assert collision_check(context)["collisions"] == ["node/7"]
    context["existing_ids"]["node"] = []
    assert collision_check(context)["status"] == "满足"


def test_reward_check_reuses_m21_new_vs_existing_rows_and_baseline_evidence():
    target = "assets/score_reward_cnmod.json"
    changes = {target: json.dumps({"r": [{"position": 1, "type": 0, "id": 1}]})}
    before = dict.fromkeys(SERVER_REWARD_PATHS)
    view = View({"master/reward/score_reward.orderedmap": {}})
    assert reward_check(view, changes, before)["blocking"]
    before[target] = changes[target]
    check = reward_check(view, changes, before)
    assert check["status"] == "待验证" and not check["blocking"]
    view.tables["master/reward/score_reward.orderedmap"] = {"r": {"1": "row"}}
    assert reward_check(view, changes, before)["status"] == "满足"
    assert reward_check(view, changes, {})["status"] == "待验证"
    assert reward_check(None, changes, before)["status"] == "未执行"


def test_shop_checks_missing_client_and_category_map_from_actual_server_ids():
    row = ["99"] + [""] * 49
    view = View({"master/shop/boss_coin_shop.orderedmap": {"99001": row}})
    doc = {"shops": [{"id": "99", "products": [{"path": ["99001"], "row": row}]}]}
    server = {"assets/boss_coin_shop.json": '{"99":{"99001":{}}}',
              "assets/boss_coin_shop_item_category_map.json": '{"99001":99}'}
    assert shop_check(doc, view, {}, server)["status"] == "满足"
    server["assets/boss_coin_shop_item_category_map.json"] = '{}'
    assert shop_check(doc, view, {}, server)["blocking"]
    server["assets/boss_coin_shop_item_category_map.json"] = '{"99001":99}'
    view.tables["master/shop/boss_coin_shop.orderedmap"] = {}
    assert "C8601" in shop_check(doc, view, {}, server)["issues"][0]


def test_atlas_uses_actual_png_dimensions_but_never_promotes_estimate_to_proof():
    png = b'\x89png\r\n\x1a\n' + b'\x00\x00\x00\x0dIHDR' + struct.pack('>II', 4096, 4096)
    view = View(files={"sheet.png": png})
    result = atlas_check(view, {"atlas_budget": {"parties": [["sheet.png"]] * 3}})
    assert result["padded_pixels"] == 4098 ** 2
    assert result["near_historical_failure"] is True
    assert result["status"] == "待验证" and not result["blocking"]
    assert result["runtime_executed"] is False
