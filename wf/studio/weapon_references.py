"""Weapon references in verified native shop layouts and local server inputs."""
from __future__ import annotations

from wf.boss import schema as s
from wf.boss.links import record
from wf.boss.shop_model import ENH_SHOP, product_fields

EVENT_SHOP = "master/shop/event_item_shop.orderedmap"
GACHA = "master/gacha/gacha.orderedmap"
SERVER_GACHA = "assets/gacha.json"
# Explicit runtime files: server-patch/assets.ts.diff; event overlay:
# wf_wiki_dungeon_rewards_shops.build_shops. Depth bounds group traversal.
SERVER_SHOPS = {
    "boss_coin_shop": ("boss_coin", 2),
    "event_item_shop": ("event_item", 3),
    "event_item_shop_rank_p5b": ("event_item", 3),
    "general_shop": ("general", 3),
    "star_grain_shop": ("star_grain", 3),
    "treasure_shop": ("treasure", 3),
    "equipment_enhancement_shop": ("enhancement", 1),
}


def _matches(kind, identifier, weapon, soul):
    return ((str(kind) == "4" and str(identifier) == weapon) or
            (str(kind) == "0" and s.present(soul) and str(identifier) == soul))


def _client_shops(tables, identity, soul):
    result = []
    for logical, kind in ((s.SHOP, "boss_coin"), (EVENT_SHOP, "event_item")):
        for path, text in s.iter_leaves(tables.table(logical)):
            for index, row in enumerate(s.parse_rows(text)):
                # EventItemShop c32..49 matches the six reward triples; other
                # fields differ (event c1/c2 vs boss category c0).
                matched = [entry for entry in product_fields(row)["rewards"]
                           if _matches(entry["kind"], entry["id"], identity, soul)]
                if matched:
                    group = ({"categoryId": s.cell(row, 0)} if kind == "boss_coin" else
                             {"eventId": s.cell(row, 1), "eventType": s.cell(row, 2)})
                    result.append({"scope": "client", "kind": kind, "productId": path[0], **group,
                                   "rowIndex": index, "matches": matched, **record(tables, logical, path, row)})
    for path, text in s.iter_leaves(tables.table(ENH_SHOP)):
        for row in s.parse_rows(text):
            if s.cell(row, 29) == identity:
                result.append({"scope": "client", "kind": "enhancement", "productId": path[0],
                               "categoryId": s.cell(row, 0), **record(tables, ENH_SHOP, path, row)})
    return result


def _products(node, depth, path=()):
    """Visit explicit product records inside a bounded, allowlisted document."""
    if path and ("rewards" in node or "equipmentId" in node):
        yield path, node
    elif len(path) < depth:
        for key, child in node.items():
            if isinstance(child, dict):
                yield from _products(child, depth, (*path, str(key)))


def _server_shops(source, identity, soul, server_dir, read_server):
    result, coverage = [], {}
    for name, (kind, depth) in SERVER_SHOPS.items():
        logical = f"assets/{name}.json"
        document, available = read_server(source, logical, server_dir)
        coverage[logical] = available
        for path, product in _products(document, depth):
            rewards = product.get("rewards", [])
            if not isinstance(rewards, list):
                raise ValueError(f"shop rewards must be an array: {logical}/{'/'.join(path)}")
            matched = [reward for reward in rewards if isinstance(reward, dict)
                       and _matches(reward.get("type"), reward.get("id"), identity, soul)]
            if matched or (kind == "enhancement" and str(product.get("equipmentId")) == identity):
                group = ({"categoryId": path[0]} if kind == "boss_coin" and len(path) == 2 else
                         {"eventType": path[0], "eventId": path[1]} if kind == "event_item" and len(path) == 3 else {})
                result.append({"scope": "server", "kind": kind, "productId": path[-1], **group,
                               "path": list(path), "matches": matched, "product": product, "source": logical})
    return result, coverage


def _gacha(tables, source, identity, server_dir, read_server):
    result = []
    for path, text in s.iter_leaves(tables.table(GACHA)):
        for row in s.parse_rows(text):
            if s.cell(row, 13) != "1":
                continue
            for column in (22, 23, 24):
                odds = s.cell(row, column)
                if not s.present(odds):
                    continue
                logical = f"master/gacha_odds/{odds}.orderedmap"
                for entry_path, entry_text in s.iter_leaves(tables.table(logical)):
                    for entry in s.parse_rows(entry_text):
                        if s.cell(entry, 0) == identity:
                            result.append({"scope": "client", "id": path[0], "name": s.cell(row, 1),
                                           "oddsId": odds, "weight": s.cell(entry, 2),
                                           "gacha": record(tables, GACHA, path, row),
                                           "entry": record(tables, logical, entry_path, entry)})
    document, available = read_server(source, SERVER_GACHA, server_dir)
    for pool_id, pool in document.items():
        if not isinstance(pool, dict) or str(pool.get("type")) != "1":
            continue
        groups = pool.get("pool", {})
        if not isinstance(groups, dict):
            raise ValueError(f"equipment gacha pool must be an object: {pool_id}")
        for group, entries in groups.items():
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                raise ValueError(f"equipment gacha entries must be objects: {pool_id}/{group}")
            for entry in entries:
                if str(entry.get("id")) == identity:
                    result.append({"scope": "server", "id": pool_id, "name": pool.get("name"),
                                   "group": group, "entry": entry, "source": SERVER_GACHA})
    return result, available


def references(tables, source, identity, soul, server_dir, read_server):
    shops = _client_shops(tables, identity, soul)
    server_shops, coverage = _server_shops(source, identity, soul, server_dir, read_server)
    gacha, gacha_known = _gacha(tables, source, identity, server_dir, read_server)
    return ({"shops": shops + server_shops, "gacha": gacha},
            {"clientShops": [s.SHOP, EVENT_SHOP, ENH_SHOP], "serverShops": coverage,
             "clientGacha": GACHA, "serverGachaAvailable": gacha_known})
