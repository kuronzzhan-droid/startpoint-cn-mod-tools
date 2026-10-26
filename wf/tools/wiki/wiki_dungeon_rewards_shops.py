"""Event and boss exchanges with gray-runtime shared-stock rules."""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime

from wf_wiki_dungeon_rewards_schema import require

EVENT_KINDS = {"0": "advent", "2": "story", "4": "challenge-dungeon", "6": "world-story",
               "9": "collect-item", "10": "carnival", "11": "rush", "12": "score-attack"}


def iso_date(value):
    if not value:
        return None
    value = value.replace(" ", "T")
    if not value.endswith("Z") and "+" not in value[10:]:
        value += "Z"
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def public_shop_id(kind, key):
    return "shop-" + kind + "-" + hashlib.sha256((kind + ":" + key).encode()).hexdigest()[:12]


def project_product(row, names, *, rerun=False):
    notes = []
    for key, label in (("dailyStock", "每日限购"), ("monthlyStock", "每月限购"), ("maxFrequency", "兑换次数上限")):
        if key in row:
            notes.append(f"{label}：{row[key]}")
    costs = [names.reward("item", cost["id"], cost["amount"]) for cost in row.get("costs", [])]
    user = row.get("userCost")
    if user:
        kind = {0: "beads", 1: "mana", 2: "item"}.get(user["type"], "unknown")
        cost = names.reward(kind, amount=user["amount"])
        if user["type"] == 2:
            cost["name"] = "羁绊凭证"
        costs.append(cost)
    for period in row.get("compatibilityPeriods", []):
        notes.append(f"额外开放时段：{iso_date(period['availableFrom'])} 至 {iso_date(period.get('availableUntil')) or '未设结束时间'}")
    if rerun:
        notes.append("复刻兼容开放时段：2025-06-26 12:00:00 至 2025-08-14 23:59:59（UTC）；仍共用原商品库存。")
    # Missing stock is explicitly unlimited in the actual runtime, not unknown.
    stock = row.get("stock", -1)
    require(type(stock) is int and stock >= -1, "Invalid gray shop stock")
    return {"rewards": [names.raw_reward(reward, shop=True) for reward in row.get("rewards", [])],
            "costs": costs, "stock": stock, "availableFrom": iso_date(row.get("availableFrom")),
            "availableUntil": iso_date(row.get("availableUntil")), "notes": notes}


def build_shops(assets, names, catalog, dungeons, boss_links=None, collect_titles=None):
    leaves = {row["id"]: row for row in catalog["items"]}
    events = copy.deepcopy(assets.get("event_item_shop.json"))
    extra = assets.get("event_item_shop_rank_p5b.json")
    events.setdefault("11", {}).setdefault("700099", {}).update(extra.get("11", {}).get("700099", {}))
    id_map = assets.merged("event_item_shop_id_map.json", "event_item_shop_id_map_rank_p5b.json")
    boss = assets.get("boss_coin_shop.json")
    boss_map = assets.get("boss_coin_shop_item_category_map.json")
    output = []

    def add(kind, key, products, linked, extra_notes=(), rerun=False, reference_title=None):
        products = {pid: row for pid, row in products.items() if pid != "59001010"}
        if not products:
            return
        linked = list(dict.fromkeys(linked))
        identifier = public_shop_id(kind, key)
        title = leaves[linked[0]]["title"] + " · 兑换商店" if linked else "活动兑换商店"
        if not linked:
            currencies = list(dict.fromkeys(names.reward("item", cost["id"])["name"]
                for row in products.values() for cost in row.get("costs", [])))
            if currencies:
                title = "／".join(currencies[:2]) + " · 兑换商店"
        if reference_title:
            title = reference_title + " · 兑换商店"
        shop = {"id": identifier, "title": title, "dungeonIds": linked,
                "notes": ["限购为配置总量，剩余库存因玩家已购数量而异；开放时间以游戏为准。", *extra_notes],
                "items": [project_product(row, names, rerun=rerun) for row in products.values()]}
        if not linked:
            shop["notes"].append("此兑换活动没有独立副本入口；不与同编号的其他玩法合并。")
            shop["notes"].append("活动名称来自客户端元表参考；兑换内容已按灰服快照核对。" if reference_title
                                 else "活动名称尚未对应，暂按兑换货币命名。")
        if kind == "boss" and key == "99":
            shop["title"] = "五重决战 · 兑换商店"
        output.append(shop)
        for leaf in linked:
            dungeons[leaf]["shopIds"].append(identifier)

    for category, products in boss.items():
        verified = {pid: row for pid, row in products.items() if str(boss_map.get(pid)) == category}
        require(len(verified) == len(products), "Boss shop product mapping mismatch")
        linked = (boss_links or {}).get(category, [])
        add("boss", category, verified, linked)
    for event_type, groups in events.items():
        for event_id, products in groups.items():
            verified = {}
            for pid, row in products.items():
                if pid == "59001010":
                    continue
                mapping = id_map.get(pid)
                require(mapping is not None, "Event shop product has no purchase mapping")
                require(str(mapping["eventType"]) == event_type and str(mapping["eventId"]) == event_id,
                        "Event shop product mapping mismatch")
                verified[pid] = row
            leaf = f"event-{EVENT_KINDS.get(event_type, 'unmatched')}-{event_id}"
            linked = [leaf] if leaf in leaves else []
            notes = []
            rerun = False
            if event_type == "11" and event_id == "700099":
                linked += [key for key in leaves if key == "event-rush-700100"]
                notes.append("普通深渊与深渊 EX 使用同一商店和同一份限购库存。")
            if event_type == "11" and event_id.isdigit() and 700001 <= int(event_id) <= 700007:
                rerun_id = str(int(event_id) + 10)
                if rerun_id not in groups:
                    linked += [key for key in leaves if key == "event-rush-" + rerun_id]
                rerun = True
            if any(9700201 <= int(pid) <= 9700214 or 9700301 <= int(pid) <= 9700314 for pid in verified):
                notes.append("幻想连战的两个兑换入口共用对应商品的限购库存。")
            reference_title = (collect_titles or {}).get(event_id) if event_type == "9" else None
            add("event", event_type + ":" + event_id, verified, linked, notes, rerun, reference_title)
    return output
