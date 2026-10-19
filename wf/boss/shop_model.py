"""Native shop and equipment relations, including the complete material ladder."""
from __future__ import annotations

from . import schema as s

ITEM = "master/item/item.orderedmap"
STATUS = "master/item/equipment_status.orderedmap"
SOUL = "master/ability/ability_soul.orderedmap"
ENH = "master/equipment_enhancement/equipment_enhancement.orderedmap"
ENH_ABILITY = "master/equipment_enhancement/equipment_enhancement_ability.orderedmap"
ENH_STATUS = "master/equipment_enhancement/equipment_enhancement_status.orderedmap"
ENH_SHOP = "master/equipment_enhancement/equipment_enhancement_shop.orderedmap"
ENH_CATEGORY = "master/equipment_enhancement/equipment_enhancement_shop_category.orderedmap"
SERVER_SHOP = "assets/boss_coin_shop.json"
SERVER_MAP = "assets/boss_coin_shop_item_category_map.json"
SERVER_ENH = "assets/equipment_enhancement_shop.json"
WEAPON_TABLES = (s.EQUIPMENT, ITEM, STATUS, SOUL, ENH, ENH_ABILITY, ENH_STATUS)


def costs(row, start=17):
    return [{"itemId": s.cell(row, c), "amount": s.cell(row, c + 1)}
            for c in range(start, start + 8, 2) if s.present(s.cell(row, c))]


def product_fields(row):
    return {"name": s.cell(row, 6), "description": s.cell(row, 10),
            "icon": s.cell(row, 12), "rarity": s.cell(row, 13),
            "price": costs(row), "stock": s.cell(row, 28),
            "limit": {"frequency": s.cell(row, 29), "daily": s.cell(row, 30),
                      "monthly": s.cell(row, 31)},
            "availableFrom": s.cell(row, 25), "availableUntil": s.cell(row, 26),
            "rewards": [{"kind": s.cell(row, c), "id": s.cell(row, c + 1),
                         "amount": s.cell(row, c + 2)}
                        for c in range(32, 50, 3) if s.present(s.cell(row, c))]}


def equipment(tables, identity):
    from .links import record
    import wf_describe

    cache = getattr(tables, "_shop_weapon_cache", None)
    if cache is None:
        tables._shop_weapon_cache = cache = {}
    if identity in cache:
        return cache[identity]
    main = record(tables, s.EQUIPMENT, [identity])
    soul = s.cell(main["row"], 10) if main else identity
    soul = soul if s.present(soul) else identity
    records = {name: record(tables, logical, [identity]) for name, logical in (
        ("equipment", s.EQUIPMENT), ("soul_item", ITEM), ("ability_soul", SOUL),
        ("equipment_enhancement", ENH), ("equipment_enhancement_ability", ENH_ABILITY))}
    records["soul_item"], records["ability_soul"] = record(tables, ITEM, [soul]), record(tables, SOUL, [soul])
    status = {name: [{"level": path[-1], "row": row,
                      "source": tables.citation(logical, path)}
                     for path, row in s.rows_at(tables.table(logical), [identity])]
              for name, logical in (("status", STATUS), ("enhancement_status", ENH_STATUS))}
    chain = []
    for path, text in s.iter_leaves(tables.table(ENH_SHOP)):
        rows = s.parse_rows(text)
        if not rows or s.cell(rows[0], 29) != identity:
            continue
        row = rows[0]
        chain.append({**record(tables, ENH_SHOP, path), "id": path[0],
                      "categoryId": s.cell(row, 0), "groupId": s.cell(row, 2),
                      "stage": s.cell(row, 3), "maxLevel": s.cell(row, 30),
                      "requireAwakeningLevel": s.cell(row, 31), "costs": costs(row, 14),
                      "priceKind": s.cell(row, 11),
                      "userCost": ({"type": s.cell(row, 11), "amount": s.cell(row, 12)}
                                   if s.present(s.cell(row, 11)) else None),
                      "category": record(tables, ENH_CATEGORY, [s.cell(row, 0)])})
    chain.sort(key=lambda p: (int(p["maxLevel"] or 0), int(p["stage"] or 0)))
    totals, user_totals = {}, {}
    previous = 0
    for stage in chain:
        cap = int(stage["maxLevel"])
        count = max(0, min(cap, 120) - previous)
        stage.update(startLevel=previous, purchaseCountTo120=count)
        for cost in stage["costs"]:
            totals[cost["itemId"]] = totals.get(cost["itemId"], 0) + int(cost["amount"]) * count
        if stage["userCost"]:
            cost = stage["userCost"]
            user_totals[cost["type"]] = user_totals.get(cost["type"], 0) + int(cost["amount"]) * count
        previous = cap
    result = {"id": identity, **records, **status, "enhancement_chain": chain,
            "materials_to_120": [{"itemId": key, "amount": value} for key, value in sorted(totals.items())],
            "user_costs_to_120": [{"type": key, "amount": value} for key, value in sorted(user_totals.items())],
            "enhancement_start_level": 0,
            "reaches_120": bool(chain and int(chain[-1]["maxLevel"]) >= 120),
            "material_semantics": "客户端分阶标价；不证明服务端单次购买升阶行为或真实扣费",
            "kind_columns": {name: {block: wf_describe.layout(name)["blocks"][block]
                                    for block in ("instant_content", "during_content")}
                             for name in ("ability_soul", "equipment_enhancement_ability")},
            "kind_evidence": "M2.4 profile-bound SWF parseAt; docs/m2/validation-m2.4.json"}
    cache[identity] = result
    return result


def enrich_product(tables, entry):
    row = entry["row"]
    fields = product_fields(row)
    fields["currencies"] = [{**cost, "item": _record(tables, ITEM, cost["itemId"])} for cost in fields["price"]]
    soul_ids = []
    for reward in fields["rewards"]:
        item = _record(tables, ITEM, reward["id"]) if reward["kind"] == "0" else None
        if item and s.cell(item["row"], 6) == "11":
            soul_ids.append(reward["id"])
    return {**entry, "id": entry["path"][0], "fields": fields, "soul_item_ids": soul_ids}


def _record(tables, logical, identity):
    from .links import record
    return record(tables, logical, [identity])
