"""Entrance, reward and shop relations for a resolved boss quest."""
from __future__ import annotations

from . import schema as s


def record(tables, logical, path, row=None):
    text = s.get_leaf(tables.table(logical), path)
    if not isinstance(text, str):
        return None
    rows = s.parse_rows(text)
    return {"table": logical, "path": list(path), "row": row if row is not None else (rows[0] if rows else []),
            "rows": rows, "source": tables.citation(logical, path)}


def entrances(tables, quest):
    kind, path, row = quest["kind"], quest["path"], quest["row"]
    result = {"stage_node": None, "folder": None, "event": None, "event_folder": [],
              "event_folder_events": [], "stage_node_group": None}
    if kind == "boss_battle":
        node = record(tables, s.NODE, path[:2])
        result["stage_node"] = node
        if node:
            result["stage_node_group"] = record(tables, s.NODE_GROUP, [s.cell(node["row"], 2)])
    elif kind == "practice":
        result["folder"] = record(tables, s.PRACTICE_FOLDER, [s.cell(row, 0)])
    elif kind == "hard_multi":
        event_id = path[0]
        result["event"] = record(tables, s.EVENT, [event_id])
        for folder_path, text in s.iter_leaves(tables.table(s.EVENT_FOLDER_EVENTS)):
            if any(s.cell(r, 0) == "13" and s.cell(r, 1) == event_id for r in s.parse_rows(text)):
                result["event_folder_events"].append(record(tables, s.EVENT_FOLDER_EVENTS, folder_path))
                folder = record(tables, s.EVENT_FOLDER, folder_path[:1])
                if folder and folder not in result["event_folder"]:
                    result["event_folder"].append(folder)
    return result


def rewards(tables, quest):
    key = quest["fields"]["score_reward"]
    score, rare, items = [], [], set()
    for path, row in s.rows_at(tables.table(s.SCORE_REWARD), [key]):
        score.append(record(tables, s.SCORE_REWARD, path, row))
        if s.cell(row, 1) == "0" and s.cell(row, 2) == "0":
            items.add(s.cell(row, 3))
        elif s.cell(row, 1) == "1":
            rare_key = s.cell(row, 6)
            for rpath, rrow in s.rows_at(tables.table(s.RARE_SCORE_REWARD), [rare_key]):
                entry = record(tables, s.RARE_SCORE_REWARD, rpath, rrow)
                if entry not in rare:
                    rare.append(entry)
                if s.cell(rrow, 1) == "0":
                    items.add(s.cell(rrow, 2))
    return {"key": key, "missing": s.present(key) and not score,
            "score_reward": score, "rare_score_reward": rare, "item_ids": sorted(items)}


def shops(tables, entrance, reward, quest=None):
    categories, currencies = set(), set(reward["item_ids"])
    inferred = {}
    node, event = entrance["stage_node"], entrance["event"]
    if node:
        categories.add(s.cell(node["row"], 6))
        currencies.update(v for v in node["row"][7:11] if s.present(v))
    if event:
        currencies.update(v for v in event["row"][16:20] if s.present(v))
    if quest and quest["kind"] == "hard_multi":
        # Custom hard encounters copy a field-data family with a _hard suffix.
        # This is a named-family inference, not a native foreign-key relation.
        field_id = quest["fields"]["field_data"]
        if field_id.endswith("_hard"):
            original = field_id.removesuffix("_hard")
            for qpath, text in s.iter_leaves(tables.table(s.QUEST_TABLES["boss_battle"])):
                rows = s.parse_rows(text)
                if rows and s.cell(rows[0], 109) == original:
                    related = record(tables, s.NODE, qpath[:2])
                    if related:
                        category = s.cell(related["row"], 6)
                        categories.add(category)
                        inferred[category] = {"kind": "field_family_inference", "field_data": original,
                                              "note": "按 _hard 母本场景命名关联；不是客户端外键",
                                              "stage_node_source": related["source"]}
    products = []
    for path, text in s.iter_leaves(tables.table(s.SHOP)):
        rows = s.parse_rows(text)
        if not rows:
            continue
        row = rows[0]
        costs = {s.cell(row, c) for c in (17, 19, 21, 23)}
        products.append((path, row))
        if costs & currencies:
            categories.add(s.cell(row, 0))
    result = []
    for category in sorted(categories):
        if not s.present(category):
            continue
        group = record(tables, s.SHOP_CATEGORY, [category])
        weapons, group_products = [], []
        for path, row in products:
            if s.cell(row, 0) != category:
                continue
            group_products.append(record(tables, s.SHOP, path, row))
            for column in range(32, 50, 3):
                if s.cell(row, column) == "4":
                    key = s.cell(row, column + 1)
                    weapon = record(tables, s.EQUIPMENT, [key])
                    value = {"id": key, "product": path[0], "equipment": weapon,
                             "source": tables.citation(s.SHOP, path)}
                    if value not in weapons:
                        weapons.append(value)
        result.append({"id": category, "category": group, "products": group_products,
                       "weapons": weapons, "association": inferred.get(category, {"kind": "native_node_or_currency"}),
                       "server_sync": "未执行；此读模型仅解析客户端视图"})
    return result


def routing(tables, quest):
    if quest["kind"] != "boss_battle" or quest["fields"].get("both_boss") != "true":
        return {"kind": "none", "group": None, "maps": []}
    group = record(tables, s.BOTH_GROUP, [quest["id"]])
    maps = []
    if group:
        for key in s.cell(group["row"], 1).split(","):
            item = record(tables, s.BOTH_MAP, [key])
            if item:
                maps.append(item)
    return {"kind": "BothBoss", "meaning": "选择隐藏关的两轮路由；不表示同屏多 boss",
            "group": group, "maps": maps}
