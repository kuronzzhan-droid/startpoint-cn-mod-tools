"""Native boss table paths and zero-based CSV columns.

Columns follow the existing quest exporter and five-boss builder. Practice
quest IDs are ordered-map keys: its c0 is a folder, not a unique quest ID.
"""
from __future__ import annotations

import csv
import io

QUEST_TABLES = {
    "boss_battle": "master/quest/boss_battle_quest.orderedmap",
    "hard_multi": "master/quest/event/hard_multi_event_quest.orderedmap",
    "practice": "master/quest/practice/practice_quest.orderedmap",
}
NODE = "master/quest/boss_battle_stage_node.orderedmap"
NODE_GROUP = "master/quest/boss_battle_stage_node_group.orderedmap"
PRACTICE_FOLDER = "master/quest/practice/practice_quest_folder.orderedmap"
EVENT = "master/quest/event/hard_multi_event.orderedmap"
EVENT_FOLDER = "master/quest/event/event_folder.orderedmap"
EVENT_FOLDER_EVENTS = "master/quest/event/event_folder_events.orderedmap"
FIELD_DATA = "master/battle/field_data.orderedmap"
FIELD = "master/battle/field.orderedmap"
ZONE = "master/battle/zone.orderedmap"
GENERAL_BOSS = "master/battle/boss/general_boss.orderedmap"
STANDARD_BOSS = "master/battle/boss/standard_boss.orderedmap"
GENERAL_ZAKO = "master/battle/zako/general_zako.orderedmap"
BOSS_LEVEL = "master/battle/boss/boss_level.orderedmap"
SCORE_REWARD = "master/reward/score_reward.orderedmap"
RARE_SCORE_REWARD = "master/reward/rare_score_reward.orderedmap"
SHOP = "master/shop/boss_coin_shop.orderedmap"
SHOP_CATEGORY = "master/shop/boss_coin_shop_category.orderedmap"
EQUIPMENT = "master/item/equipment.orderedmap"
BOTH_GROUP = "master/quest/both_boss/both_boss_group.orderedmap"
BOTH_MAP = "master/quest/both_boss/both_boss_map.orderedmap"

QUEST_COLUMNS = {
    "boss_battle": {"name": 2, "start_time": 5, "end_time": 6,
                    "restriction": 68, "stamina": 69, "score_reward": 70,
                    "recommended_element": 72, "hide_recommended_element": 73,
                    "hp_zako": 97, "hp_funnel": 98, "hp_boss": 99,
                    "attack_zako": 100, "attack_funnel": 101, "attack_boss": 102,
                    "level": 106, "rank": 107, "field_data": 109, "bgm": 110,
                    "time_limit": 111, "both_boss": 122, "hidden": 123},
}
for _kind in ("hard_multi", "practice"):
    QUEST_COLUMNS[_kind] = {
        name: index if index < 68 else index + 1
        for name, index in QUEST_COLUMNS["boss_battle"].items()
        if name not in ("both_boss", "hidden")
    }


def parse_rows(text):
    return list(csv.reader(io.StringIO(text)))


def cell(row, index):
    return row[index] if 0 <= index < len(row) else ""


def present(value):
    return value not in (None, "", "(None)")


def get_leaf(tree, path, default=None):
    node = tree
    for key in path:
        if not isinstance(node, dict) or str(key) not in node:
            return default
        node = node[str(key)]
    return node


def iter_leaves(node, path=()):
    if isinstance(node, str):
        yield tuple(path), node
    elif isinstance(node, dict):
        for key, child in node.items():
            yield from iter_leaves(child, (*path, str(key)))


def rows_at(tree, path):
    return [(leaf_path, row) for leaf_path, text in iter_leaves(get_leaf(tree, path, {}), path)
            for row in parse_rows(text)]
