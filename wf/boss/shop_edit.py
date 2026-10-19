"""Scoped boss shop edits; preserve every unrelated server product value byte."""
from __future__ import annotations

import copy

from wf.deliver.json_merge import _json_spans
from wf.view.base149 import join
from . import schema as s
from .edit_bytes import delete_keys
from .edit_state import merge_keys
from .shop_model import ITEM, SERVER_SHOP, SERVER_MAP, product_fields


def one(state, logical, identity, width=None):
    value = state.table(logical).get(str(identity))
    rows = s.parse_rows(value) if isinstance(value, str) else []
    if len(rows) != 1 or width is not None and len(rows[0]) != width:
        raise ValueError(f"missing or malformed row: {logical}/{identity}")
    return rows[0]


def reserve(occupied, start, requested=None, *, limit=2147483647):
    occupied = set(map(str, occupied))
    if requested is not None:
        if not str(requested).isdigit() or not 0 < int(requested) <= limit:
            raise ValueError("ID must be a positive bounded decimal string")
        if str(requested) in occupied:
            raise ValueError(f"ID collision: {requested}")
        return str(requested)
    while str(start) in occupied:
        start += 1
    if start > limit:
        raise ValueError("no free ID in allocation range")
    return str(start)


def image_reference(state, reference):
    if not isinstance(reference, str) or not reference or any(t in reference for t in ("..", "\\", ":")):
        raise ValueError("icon must be an existing relative logical image reference")
    logical = reference if reference.endswith(".png") else reference + ".png"
    if state.raw(logical) is None:
        raise ValueError(f"missing icon resource: {logical}")


def item_reference(state, identity):
    row = one(state, ITEM, str(identity))
    if s.present(s.cell(row, 4)):
        from wf_weapon_awaken import decode_atlas
        logical = "item_icon/sprite_sheet.atlas.amf3.deflate"
        raw = state.raw(logical)
        names = {str(e["n"]) for e in decode_atlas(raw)} if raw is not None else set()
        if row[4] not in names or state.raw("item_icon/sprite_sheet.png") is None:
            raise ValueError(f"C8004: item {identity} c4 {row[4]} missing from loaded item_icon atlas")


def set_costs(state, row, costs, start):
    if not 1 <= len(costs) <= 4:
        raise ValueError("price requires one to four currencies")
    if len({str(cost["itemId"]) for cost in costs}) != len(costs):
        raise ValueError("duplicate price currency")
    row[start:start + 8] = ["(None)", ""] * 4
    for index, cost in enumerate(costs):
        item_reference(state, cost["itemId"])
        if not isinstance(cost["amount"], int) or isinstance(cost["amount"], bool) or cost["amount"] <= 0:
            raise ValueError("price amount must be a positive integer")
        row[start + 2 * index:start + 2 * index + 2] = [str(cost["itemId"]), str(cost["amount"])]


def server_product(row):
    value = product_fields(row)
    return {"costs": [{"id": int(c["itemId"]), "amount": int(c["amount"])} for c in value["price"]],
            "rewards": [{"type": int(r["kind"]), "count": int(r["amount"]),
                         **({"id": int(r["id"] or 0)} if r["kind"] not in {"1", "2"} else {})}
                        for r in value["rewards"]],
            "availableFrom": value["availableFrom"] if s.present(value["availableFrom"]) else None,
            "availableUntil": value["availableUntil"] if s.present(value["availableUntil"]) else None,
            "stock": int(value["stock"]) if s.present(value["stock"]) else -1}


def nested_product(state, category, identity, value=None):
    state.server(SERVER_SHOP)
    raw = state.servers.get(SERVER_SHOP, state.server_original[SERVER_SHOP])
    text, document, spans = _json_spans(raw)
    if category not in document:
        if value is None:
            raise ValueError("missing server shop category")
        state.servers[SERVER_SHOP] = merge_keys(raw, {category: {identity: value}})
        return
    begin, end = spans[category]
    inner = text[begin:end].encode("utf-8")
    if value is None:
        changed = delete_keys(inner, [identity])
    elif identity in document[category]:
        product_text, _, product_spans = _json_spans(inner)
        start, stop = product_spans[identity]
        product = merge_keys(product_text[start:stop].encode("utf-8"), value)
        changed = (product_text[:start] + product.decode("utf-8") + product_text[stop:]).encode("utf-8")
    else:
        changed = merge_keys(inner, {identity: value})
    after = (text[:begin] + changed.decode("utf-8") + text[end:]).encode("utf-8")
    if after != raw:
        state.servers[SERVER_SHOP] = after


def edit_shop(state, request, categories, reserved=()):
    operation, spec = request["operation"], request["shop"]
    category = str(spec["category"])
    if category not in categories:
        raise ValueError(f"shop category {category} is not associated with this boss")
    one(state, s.SHOP_CATEGORY, category)
    server, category_map = state.server(SERVER_SHOP), state.server(SERVER_MAP)
    table = state.table(s.SHOP)
    if operation == "shop_add":
        source = str(spec["sourceProduct"])
        row = one(state, s.SHOP, source, 50)
        occupied = set(table) | set(category_map) | {key for group in server.values() for key in group}
        occupied.update((reserved or {}).get("products", []) if isinstance(reserved, dict) else reserved)
        identity = reserve(occupied, 991000000, spec.get("productId"))
        spec["productId"] = identity
        row[0], row[7], row[8] = category, "1", "1"
    else:
        identity = str(spec["productId"])
        row = one(state, s.SHOP, identity, 50)
        if row[0] != category or identity not in server.get(category, {}) or str(category_map.get(identity)) != category:
            raise ValueError("C8601: shop edit requires matching client, server and category_map product")
    if operation == "shop_delete":
        state.delete_leaf(s.SHOP, [identity])
        nested_product(state, category, identity)
        state.delete_server_keys(SERVER_MAP, [identity])
        return
    for name, column in (("name", 6), ("description", 10), ("icon", 12), ("stock", 28)):
        if name in spec:
            if name in ("name", "description") and any(c in str(spec[name]) for c in ("\n", "\r", '"', "::")):
                raise ValueError(f"shop {name} contains unsupported text delimiters")
            row[column] = str(spec[name])
    if "icon" in spec:
        image_reference(state, spec["icon"])
    if "price" in spec:
        set_costs(state, row, spec["price"], 17)
    if "rewards" in spec:
        row[32:50] = ["(None)", "", ""] * 6
        for index, reward in enumerate(spec["rewards"]):
            if int(reward["kind"]) == 0:
                item_reference(state, reward["id"])
            elif int(reward["kind"]) == 4:
                one(state, s.EQUIPMENT, reward["id"])
            row[32 + 3 * index:35 + 3 * index] = [str(reward[k]) for k in ("kind", "id", "amount")]
    new_server = copy.deepcopy(server.get(category, {}).get(identity, {}))
    generated = server_product(row)
    if operation == "shop_add":
        new_server.update(generated)
    else:
        for requested, target in (("price", "costs"), ("stock", "stock"), ("rewards", "rewards")):
            if requested in spec:
                new_server[target] = generated[target]
    state.set_leaf(s.SHOP, [identity], join(row), new=operation == "shop_add")
    nested_product(state, category, identity, new_server)
    if operation == "shop_add":
        state.set_server_keys(SERVER_MAP, {identity: int(category)}, new=True)
