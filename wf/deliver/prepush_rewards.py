"""Reward row identities shared by the companion check and delivery gate."""
from __future__ import annotations

import json

REWARD_TABLES = ("score_reward", "rare_score_reward")
SERVER_REWARD_PATHS = tuple(f"assets/{name}{suffix}.json"
                            for name in REWARD_TABLES for suffix in ("", "_cnmod"))


def reward_groups(raw, target):
    if raw is None:
        return {}
    groups = json.loads(raw)
    if not isinstance(groups, dict):
        raise ValueError(f"{target}: reward groups must be an object")
    for group, entries in groups.items():
        if not isinstance(entries, list) or any(not isinstance(r, dict) for r in entries):
            raise ValueError(f"{target}:{group}: rewards must be a list of objects")
    return groups


def merged_rewards(files, name):
    """Server assets.ts replaces whole groups with the _cnmod group."""
    groups, sources = {}, {}
    for suffix in ("", "_cnmod"):
        target = f"assets/{name}{suffix}.json"
        extra = reward_groups(files.get(target), target)
        groups.update(extra)
        sources.update({group: target for group in extra})
    return groups, sources


def reward_rows(entries, name):
    result = {}
    for index, entry in enumerate(entries, 1):
        # quest.ts uses explicit score positions, but rare pools use array index + 1.
        position = entry.get("position", index) if name == "score_reward" else index
        if isinstance(position, bool) or not str(position).isdigit() or int(position) < 1:
            raise ValueError(f"invalid reward position: {position!r}")
        position = str(int(position))
        if position in result:
            raise ValueError(f"duplicate reward position: {position}")
        result[position] = entry
    return result


def client_rewards(view, name):
    tables = [view.table(f"master/reward/{name}{suffix}.orderedmap")
              for suffix in ("", "_cnmod")]
    # _cnmod support also permits composed fixture/authoring views. Production
    # 233 has the merged rows directly in the base client tables.
    merged = {}
    for table in tables:
        if table is not None:
            merged.update(table)
    return merged
