"""Match existing public dungeon leaves to verified gray-server quest records."""
from __future__ import annotations

import re

from wf_wiki_dungeons_schema import EVENTS, NODE_TABLE, QUEST_COLUMNS, RANK_TABLE, clean_text, leaf_rows, quest_table


def quest_file(kind):
    return {"boss": "boss_battle_quest.json", "ranking": "ranking_event_single_quest.json",
            "story": "story_event_single_quest.json", "world_story_boss": "world_story_event_boss_battle_quest.json"}.get(
                kind, kind + "_event_quest.json")


def build_mapping(sources, catalog, assets):
    """Master trees only identify ownership; all reward records must exist in gray assets."""
    known = {row["id"] for row in catalog["items"]}
    result = {key: [] for key in known}
    audit = {"matched": 0, "missingGrayQuest": 0, "nameDifferences": 0}
    ranks = sources.table(RANK_TABLE)

    def add(identifier, node, kind):
        if identifier not in result:
            return
        gray = assets.get(quest_file(kind))
        if kind == "boss":
            gray = {**gray, **assets.get("boss_battle_quest_cnmod.json")}
        seen = set()
        for row in leaf_rows(node):
            quest_id = row[0] if row else ""
            if quest_id in seen:
                continue
            seen.add(quest_id)
            record = gray.get(quest_id)
            if not isinstance(record, dict):
                audit["missingGrayQuest"] += 1
                continue
            name_col = QUEST_COLUMNS[kind][0]
            title = clean_text(row[name_col]) if len(row) > name_col else ""
            remote_name = clean_text(record.get("name", ""))
            audit["matched"] += 1
            if title and remote_name and title != remote_name:
                audit["nameDifferences"] += 1
            rank_col = QUEST_COLUMNS[kind][3]
            rank_id = row[rank_col] if rank_col and len(row) > rank_col else ""
            rank = next(leaf_rows(ranks.get(rank_id, "")), [])
            difficulty = clean_text(rank[1]) if len(rank) > 1 else ""
            if identifier in ("event-rush-700098", "event-rush-700099", "event-rush-700100"):
                difficulty = ""
            record = {**record, "_wikiDifficulty": difficulty}
            name = re.sub(r"\s*:?(?:quest_rank)::", "", remote_name or title).strip()
            result[identifier].append((kind, quest_id, record, name or "关卡奖励"))

    for kind in EVENTS:
        tree = sources.table(quest_table(kind))
        for key, node in tree.items():
            identifier = f"event-{kind.replace('_', '-')}-{str(key).lower()}"
            add(identifier, node, kind)
            if kind == "world_story":
                add(identifier, sources.table(quest_table("world_story_boss")).get(key, {}), "world_story_boss")
    for group, nodes in sources.table(quest_table("boss")).items():
        if isinstance(nodes, dict):
            for key, node in nodes.items():
                add(f"boss-{group}-{key}".lower(), node, "boss")
    return result, audit


def boss_shop_links(sources, catalog):
    known = {row["id"] for row in catalog["items"]}
    linked = {}
    for group, nodes in sources.table(NODE_TABLE).items():
        for key, node in nodes.items():
            row = next(leaf_rows(node), [])
            identifier = f"boss-{group}-{key}".lower()
            if identifier in known and len(row) > 6 and row[6].isdigit():
                linked.setdefault(row[6], []).append(identifier)
    return linked
