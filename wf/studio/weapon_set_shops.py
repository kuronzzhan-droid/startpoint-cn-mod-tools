"""Shared enhancement categories and mirrored, single-weapon exchange products."""
from wf.boss import schema as s
from wf.boss.shop_edit import one, image_reference, validate_text, server_product, nested_product
from wf.boss.shop_model import ENH_CATEGORY, SERVER_SHOP, SERVER_MAP, SERVER_ENH

from .ids import allocate_available
from .weapon_set import material, write_row

START, END = "2000-01-01 00:00:00", "2099-12-31 23:59:59"


def category(state, spec, kind, reserved):
    enhancement = kind == "enhancement"
    logical = ENH_CATEGORY if enhancement else s.SHOP_CATEGORY
    table = state.table(logical)
    matches = [key for key, text in table.items()
               if ("code" in spec and s.cell(s.parse_rows(text)[0], 0) == spec["code"])
               or (enhancement and "name" in spec and s.cell(s.parse_rows(text)[0], 3) == spec["name"])]
    if "id" in spec and spec["id"] in table:
        matches.append(spec["id"])
    matches = sorted(set(matches))
    if matches:
        if len(matches) != 1 or "id" in spec and spec["id"] != matches[0]:
            raise ValueError("category identity/code/name conflict")
        row = one(state, logical, matches[0])
        if "code" in spec and row[0] != spec["code"]:
            raise ValueError("category code conflicts with existing ID")
        if enhancement and "name" in spec and row[3] != spec["name"]:
            raise ValueError("category name conflicts with existing ID")
        spec["id"] = matches[0]
        return matches[0]
    if not all(name in spec for name in ("sourceCategory", "code", "name")):
        raise ValueError("new category requires sourceCategory, code and name")
    validate_text(spec["name"], "category name")
    row = one(state, logical, spec["sourceCategory"])
    if len(row) < (9 if enhancement else 10):
        raise ValueError("category template layout is incomplete")
    key = kind + "_category"
    for pending in reserved.get(key + "_definitions", []):
        if (spec.get("code") == pending.get("code") and "code" in spec
                or enhancement and spec.get("name") == pending.get("name") and "name" in spec):
            raise ValueError("category is already reserved by another draft; reuse it after loading the merged view")
    occupied = set(table) | set(reserved.get(key, []))
    if enhancement:
        occupied.update(str(value["shopCategoryId"]) for value in state.server(SERVER_ENH).values()
                        if "shopCategoryId" in value)
    else:
        occupied.update(state.server(SERVER_SHOP))
        occupied.update(map(str, state.server(SERVER_MAP).values()))
    identity = allocate_available(key, occupied, requested=spec.get("id"), near=9 if enhancement else 97)
    row[0] = spec["code"]
    # Append the display order; never renumber unrelated categories.
    row[1] = str(max(int(s.cell(s.parse_rows(text)[0], 1)) for text in table.values()) + 1)
    if enhancement:
        row[3], row[8] = spec["name"], START
        images = (4, 5)
    else:
        row[2] = "(None)"  # No donor quest prerequisite for a standalone shop.
        images = (9,)
    for column in images:
        image_reference(state, row[column])
    write_row(state, logical, identity, row)
    spec["id"] = identity
    return identity


def exchange(state, wid, spec, reserved):
    cat = category(state, spec["category"], "exchange", reserved)
    row = one(state, s.SHOP, spec["sourceProduct"], 50)
    equipment = one(state, s.EQUIPMENT, wid, 16)
    server = state.server(SERVER_SHOP)
    occupied = set(state.table(s.SHOP)) | set(state.server(SERVER_MAP))
    occupied.update(key for group in server.values() for key in group)
    occupied.update(reserved.get("exchange_product", []))
    identity = allocate_available("exchange_product", occupied,
        requested=spec.get("productId"), near=991000000)
    material(state, spec["itemId"])
    image_reference(state, equipment[6])
    row[0], row[2], row[6] = cat, "true", equipment[1]
    row[7:10] = ["1", "1", "100"]
    row[10] = spec.get("description", "专属武器兑换")
    validate_text(row[10], "exchange description")
    row[11:17] = ["(None)", equipment[6], equipment[11], "(None)", "", "(None)"]
    row[17:25] = [spec["itemId"], str(spec["amount"])] + ["(None)", ""] * 3
    row[25:32] = [START, END, "1", str(spec["stock"]), "1", "(None)", "(None)"]
    row[32:] = ["4", wid, str(spec.get("count", 1))] + ["(None)", "", ""] * 5
    write_row(state, s.SHOP, identity, row)
    nested_product(state, cat, identity, server_product(row))
    state.set_server_keys(SERVER_MAP, {identity: int(cat)}, new=True)
    spec["productId"] = identity
