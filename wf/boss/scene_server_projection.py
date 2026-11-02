"""Explicit Advent client/server projections, verified against the original builder."""
from __future__ import annotations

import copy
import math

from .schema import iter_leaves, parse_rows
from .scene_types import parse_jst_datetime

EMPTY = {"", "(None)"}
SHOP = "master/shop/event_item_shop.orderedmap"
ITEM = "master/item/item.orderedmap"
SCORE = "master/reward/score_reward.orderedmap"
RARE = "master/reward/rare_score_reward.orderedmap"
QUEST_COLUMNS = {"name": (2, 1), "clearRewardId": (4, 1), "scoreRewardGroupId": (76, 1),
                 "element": (76, 1), "sPlusRewardId": (77, 1), "bRankTime": (90, 1000),
                 "aRankTime": (91, 1000), "sRankTime": (92, 1000), "sPlusRankTime": (93, 1000),
                 "rankPointReward": (97, 1), "characterExpReward": (98, 1),
                 "manaReward": (99, 1), "poolExpReward": (100, 1)}


def number(value, *, fraction=False):
    result = float(value) if fraction else int(value)
    if not math.isfinite(result) or result < 0 or result > (1 if fraction else 2147483647):
        raise ValueError("场景服务端投影包含越界数值")
    return result


def rows(state, logical, keys):
    selected = [(path, parse_rows(text)) for path, text in iter_leaves(state.table(logical))
                if path[0] in keys]
    if any(len(parsed) != 1 for _, parsed in selected):
        raise ValueError("场景经济表每个叶子必须包含一行 CSV")
    return sorted(((path, parsed[0]) for path, parsed in selected),
                  key=lambda item: tuple((0, int(key)) if key.isdigit() else (1, key) for key in item[0]))


def original_rows(spec, logical, keys):
    class Original:
        def table(self, name):
            from .edit_state import put
            tree = {}
            for table in spec["tables"]:
                if table["logical"] == name:
                    for entry in table["entries"]:
                        put(tree, entry["path"], entry["value"])
            return tree
    return rows(Original(), logical, keys)


def quest(row):
    if len(row) < 132:
        raise ValueError("活动五档任务行必须包含 132 列")
    return {key: row[column] if key == "name" else number(row[column]) * factor
            for key, (column, factor) in QUEST_COLUMNS.items()}


def reward(values, *, rare=False):
    output = []
    for path, row in values:
        if rare:
            item = {"name": "", "type": number(row[1]), "id": number(row[2]),
                    "rarity": number(row[4], fraction=True)}
            if row[3] not in EMPTY:
                item["count"] = number(row[3])
        elif row[1] == "0":
            item = {"position": number(path[-1]), "name": "", "type": 0,
                    "reward_type": number(row[2]), "id": number(row[3]),
                    "count": number(row[4]), "field5": number(row[5])}
        elif row[1] == "1":
            # Existing server uses a 0..100 inclusive integer roll. Keep the
            # historical builder's half-point correction, not the display rate.
            item = {"position": number(path[-1]), "name": "", "type": 1,
                    "id": number(row[6]), "rarity": round(number(row[7], fraction=True) - .005, 4)}
        else:
            raise ValueError("未支持的场景 score_reward 行类型")
        output.append(item)
    if not output:
        raise ValueError("场景掉落组缺少实际客户端行")
    return output


def product(row, event):
    if len(row) < 51 or row[0] != "0" or row[1] != event:
        raise ValueError("商品必须是当前 Advent 活动的完整 51 列行")
    start = parse_jst_datetime(row[26], "event_item_shop c26", allow_none=False)
    end = parse_jst_datetime(row[27], "event_item_shop c27", allow_none=True)
    if start is not None and end is not None and end < start:
        raise ValueError("event_item_shop c26..c27 结束时间早于开始时间")
    costs, rewards = [], []
    for index in (18, 20, 22, 24):
        if row[index] not in EMPTY:
            costs.append({"id": number(row[index]), "amount": number(row[index + 1])})
    for index in range(32, 48, 3):
        if row[index] not in EMPTY:
            item = {"type": number(row[index]), "count": number(row[index + 2])}
            if row[index + 1] not in EMPTY:
                item["id"] = number(row[index + 1])
            rewards.append(item)
    if not costs or not rewards:
        raise ValueError("场景商店商品必须包含消费和奖励")
    return {"costs": costs, "rewards": rewards, "availableFrom": row[26],
            "availableUntil": None if end is None else row[27], "stock": number(row[29])}


def changed_projection(before, original, candidate, *, target, drift, creating=False):
    """Update edited fields; keep and disclose pre-existing client/server drift."""
    if before is None or creating:
        return copy.deepcopy(candidate)
    if (isinstance(candidate, list) and isinstance(original, list) and isinstance(before, list)
            and len(candidate) == len(original) == len(before)):
        return [changed_projection(old, base, new, target=f"{target}/{index}", drift=drift)
                for index, (old, base, new) in enumerate(zip(before, original, candidate))]
    if isinstance(candidate, dict) and isinstance(original, dict) and isinstance(before, dict):
        output = copy.deepcopy(before)
        for key, value in candidate.items():
            if original.get(key) != value or key not in before:
                output[key] = copy.deepcopy(value)
            elif before[key] != value:
                drift.append({"target": target, "field": key, "clientProjection": value,
                              "server": before[key], "action": "保留已有服务端值；非本次编辑"})
        for key in original.keys() - candidate.keys():
            output.pop(key, None)
        return output
    if original != candidate:
        return copy.deepcopy(candidate)
    if before != candidate:
        drift.append({"target": target, "clientProjection": candidate,
                      "server": before, "action": "保留已有服务端值；非本次编辑"})
    return copy.deepcopy(before)
