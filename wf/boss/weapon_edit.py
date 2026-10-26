"""Clone native weapon graphs and edit their semantic abilities/material stages."""
from __future__ import annotations

import copy

import wf_describe
from wf.view.base149 import join
from . import schema as s
from .shop_model import (ITEM, STATUS, SOUL, ENH, ENH_ABILITY, ENH_STATUS, ENH_SHOP,
                         SERVER_ENH, WEAPON_TABLES)
from .shop_edit import one, reserve, image_reference, item_reference, set_costs, validate_text
from .weapon_rules import (check_ability_rows, awakening_materials, clone_awakening,
                           awakening_updates, check_user_cost, AWAKENING)
from .weapon_soul import edit_soul_item
from .weapon_identity import clone_codes, exclusive_metadata
from .weapon_templates import apply_template
from .weapon_ids import (AUTO_WEAPON_START, AUTO_WEAPON_END, MAX_WEAPON_ID,
                         product_owners, reserved_ids, validate_weapon_id)

SERVER_WEAPON_MAPS = tuple("assets/" + name + ".json" for name in (
    "equipment_lookup", "equipment_max_level", "equipment_element", "item_sale", "item_lookup"))
SERVER_WEAPON_LISTS = ("assets/equipment_ids.json", "assets/item_ids.json")


def edit_abilities(rows, changes, table, *, client_profile=None, provides=None):
    layout = wf_describe.layout(table)
    for change in changes:
        if change["table"] != table:
            continue
        index, block = change["row"], change["block"]
        if not 0 <= index < len(rows):
            raise ValueError("weapon ability row index is absent")
        row = rows[index]
        base = layout["blocks"][block]
        mode = row[layout["blocks"]["precondition1"] - 1]
        if mode != ("0" if block == "instant_content" else "1"):
            raise ValueError("weapon ability block is not active in the selected row")
        if "kind" in change:
            row[base] = str(change["kind"])
        if "strength" in change:
            fields = wf_describe.enum_map()["cases"][block].get(row[base], {}).get("fields", {})
            if "strength" not in fields:
                raise ValueError(f"{block} kind {row[base]} does not consume strength")
            offsets = {name: int(offset) for offset, name, _ in wf_describe.enum_map()["block_fields"][block]}
            for field, value in zip(("strength.power1", "strength.first_max"), change["strength"]):
                row[base + offsets[field]] = str(value)
    text = "\n".join(join(row) for row in rows)
    check_ability_rows(table, text, client_profile=client_profile, provides=provides)
    return text


def _scale_status(node, spec):
    result = copy.deepcopy(node)
    for key, value in node.items():
        if isinstance(value, dict):
            result[key] = _scale_status(value, spec)
            continue
        rows = s.parse_rows(value)
        if len(rows) != 1 or len(rows[0]) != 2:
            raise ValueError("equipment status must have HP/attack pairs")
        row = rows[0]
        for name, column in (("hpMultiplier", 0), ("attackMultiplier", 1)):
            if name in spec:
                row[column] = str(round(int(row[column]) * spec[name]))
        result[key] = join(row)
    return result


def clone_weapon(state, spec, reserved=()):
    source = str(spec["sourceWeapon"])
    reserved_weapons, reserved_products = reserved_ids(reserved)
    materials = awakening_materials(state, source)
    equipment = one(state, s.EQUIPMENT, source, 16)
    soul_key = equipment[10]
    occupied = {key for logical in WEAPON_TABLES for key in state.table(logical)}
    occupied.update(materials)
    occupied.update(state.server(AWAKENING, required=False).get("rarityOverrides", {}))
    for target in SERVER_WEAPON_MAPS:
        occupied.update(state.server(target))
    for target in SERVER_WEAPON_LISTS:
        occupied.update(map(str, state.server(target)))
    occupied.update(str(v.get("equipmentId")) for v in state.server(SERVER_ENH).values())
    occupied.update(reserved_weapons)
    occupied.update(product_owners(set(state.table(ENH_SHOP)) | set(state.server(SERVER_ENH)) | reserved_products))
    requested = validate_weapon_id(spec["id"]) if "id" in spec else None
    identity = reserve(occupied, AUTO_WEAPON_START, requested,
                       limit=MAX_WEAPON_ID if requested is not None else AUTO_WEAPON_END)
    awakening_updates(state, source, identity, materials, equipment[11])
    spec["id"] = identity
    icon_item = None
    if "icon" in spec:
        image_reference(state, spec["icon"])
        matches = [s.parse_rows(value)[0] for value in state.table(s.EQUIPMENT).values()
                   if s.cell(s.parse_rows(value)[0], 6) == spec["icon"]]
        if not matches:
            raise ValueError("weapon icon must reuse a current equipment icon with a known soul icon pair")
        icon_item = one(state, ITEM, matches[0][10])
        item_reference(state, matches[0][10])
        image_reference(state, icon_item[3])
    if "enhancedIcon" in spec:
        image_reference(state, spec["enhancedIcon"])
        if not any(s.cell(s.parse_rows(value)[0], 4) == spec["enhancedIcon"]
                   for value in state.table(ENH).values()):
            raise ValueError("enhancedIcon must reuse a current equipment enhancement icon")
    for name in ("name", "description"):
        if name in spec:
            validate_text(spec[name], f"weapon {name}")
    code, soul_code = clone_codes(state, spec, identity, reserved)
    equipment[0], equipment[10] = code, identity
    for name, column in (("name", 1), ("description", 7), ("icon", 6)):
        if name in spec:
            equipment[column] = spec[name]
    state.set_leaf(s.EQUIPMENT, [identity], join(equipment), new=True)
    item = one(state, ITEM, soul_key, 23)
    item[0], item[1], item[2] = soul_code, identity, equipment[1] + "魂珠"
    checks = [*edit_soul_item(item, spec, source), *exclusive_metadata(spec)]
    if icon_item is not None:
        item[3:5] = icon_item[3:5]
    state.set_leaf(ITEM, [identity], join(item), new=True)
    item_reference(state, identity)
    changes = spec.get("abilities", [])
    for logical, table in ((SOUL, "ability_soul"), (ENH_ABILITY, "equipment_enhancement_ability")):
        value = state.table(logical).get(soul_key if logical == SOUL else source)
        if value is None:
            if logical == SOUL or any(c["table"] == table for c in changes):
                raise ValueError(f"weapon donor lacks {logical}")
            continue
        if logical == SOUL and "soul_template" in spec:
            if any(c["table"] == table for c in changes):
                raise ValueError("soul_template and ability_soul edits cannot be combined")
            value = apply_template(state, spec["soul_template"], code)
        else:
            value = edit_abilities(s.parse_rows(value), changes, table,
                                  client_profile=getattr(state, "client_profile", None),
                                  provides=getattr(state, "client_provides", None))
        state.set_leaf(logical, [identity], value, new=True)
    for logical in (STATUS, ENH_STATUS):
        value = state.table(logical).get(source)
        if logical == STATUS and not isinstance(value, dict):
            raise ValueError("weapon donor lacks equipment_status level curve")
        if value is not None:
            state.set_leaf(logical, [identity], _scale_status(value, spec), new=True)
    enhancement = state.table(ENH).get(source)
    if enhancement is not None:
        row = s.parse_rows(enhancement)[0]
        if "name" in spec:
            row[2] = spec["name"] + "·改"
        if "description" in spec:
            row[6] = spec["description"]
        if "enhancedIcon" in spec:
            row[4] = spec["enhancedIcon"]
        state.set_leaf(ENH, [identity], join(row), new=True)
    _clone_stages(state, source, identity, spec, reserved)
    for target in SERVER_WEAPON_MAPS:
        values = state.server(target)
        donor = soul_key if target.endswith(("item_sale.json", "item_lookup.json")) else source
        if donor not in values and not target.endswith("item_lookup.json"):
            raise ValueError(f"server weapon donor missing: {target}/{donor}")
        value = copy.deepcopy(values.get(donor, item[2]))
        if target.endswith("equipment_lookup.json"):
            value["name"] = equipment[1]
        elif target.endswith("item_lookup.json"):
            value = item[2]
        state.set_server_keys(target, {identity: value}, new=True)
    for target in SERVER_WEAPON_LISTS:
        state.append_server_values(target, [int(identity)])
    clone_awakening(state, source, identity, materials, equipment[11])
    state.weapon_checks = [*getattr(state, "weapon_checks", []), *checks]
    return {"id": identity, "warnings": [entry["message"] for entry in checks], "checks": checks}


def _clone_stages(state, source, identity, spec, reserved):
    server, table = state.server(SERVER_ENH), state.table(ENH_SHOP)
    occupied = set(server) | set(table)
    occupied.update(reserved_ids(reserved)[1])
    stages = [(key, s.parse_rows(value)[0]) for key, value in table.items()
              if s.cell(s.parse_rows(value)[0], 29) == source]
    stages.sort(key=lambda pair: (int(pair[1][30]), int(pair[1][3])))
    if len(stages) > 99:
        raise ValueError("weapon enhancement graph exceeds its 99 product slots")
    requested = spec.get("enhancementProducts")
    if requested is not None and len(requested) != len(stages):
        raise ValueError("allocated enhancement products do not match donor stages")
    allocated = []
    for index, (key, row) in enumerate(stages):
        if key not in server:
            raise ValueError(f"missing server enhancement stage {key}")
        check_user_cost(server[key].get("userCost"))
        if s.present(row[11]):
            check_user_cost({"type": int(row[11]), "amount": int(row[12])})
        expected = str(int(identity) * 100 + index + 1)
        if requested is not None and requested[index] != expected:
            raise ValueError("allocated enhancement product ID must match weapon ID * 100 + stage")
        new_id = reserve(occupied, int(expected), expected)
        occupied.add(new_id)
        allocated.append(new_id)
        row[2], row[29] = identity, identity
        state.set_leaf(ENH_SHOP, [new_id], join(row), new=True)
        value = copy.deepcopy(server[key])
        value.update(groupId=int(identity), equipmentId=int(identity))
        state.set_server_keys(SERVER_ENH, {new_id: value}, new=True)
    spec["enhancementProducts"] = allocated


def edit_materials(state, spec):
    identity = str(spec["id"])
    one(state, s.EQUIPMENT, identity)
    server = state.server(SERVER_ENH)
    seen = set()
    for stage in spec["stages"]:
        product = str(stage["productId"])
        if product in seen:
            raise ValueError("duplicate enhancement material stage")
        seen.add(product)
        row = one(state, ENH_SHOP, product, 50)
        if row[29] != identity or product not in server or str(server[product].get("equipmentId")) != identity:
            raise ValueError("enhancement material stage does not belong to this weapon")
        set_costs(state, row, stage["costs"], 14)
        value = copy.deepcopy(server[product])
        value["costs"] = [{"id": int(cost["itemId"]), "amount": cost["amount"]} for cost in stage["costs"]]
        if "userCost" in stage:
            cost = stage["userCost"]
            check_user_cost(cost)
            row[11:13] = [str(cost["type"]), str(cost["amount"])] if cost is not None else ["(None)", ""]
            if cost is None:
                value.pop("userCost", None)
            else:
                value["userCost"] = copy.deepcopy(cost)
        check_user_cost(value.get("userCost"))
        if s.present(row[11]):
            check_user_cost({"type": int(row[11]), "amount": int(row[12])})
        state.set_leaf(ENH_SHOP, [product], join(row))
        state.set_server_keys(SERVER_ENH, {product: value})
