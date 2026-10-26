"""Native enhancement limits and per-level material ranges, without implicit fees."""
import copy

from wf.boss import schema as s
from wf.boss.shop_edit import one
from wf.boss.shop_model import ENH, ENH_ABILITY, ENH_STATUS, ENH_SHOP, ENH_CATEGORY, SERVER_ENH
from wf.boss.weapon_rules import check_ability_rows
from wf.rules.catalog import result
from wf.view.base149 import join

from .ids import allocate_available
from .weapon_set import material, write_row
from .weapon_set_shops import START


def stages_for(state, wid):
    return [(key, s.parse_rows(text)[0]) for key, text in state.table(ENH_SHOP).items()
            if s.cell(s.parse_rows(text)[0], 29) == wid]


def move_category(state, wid, category):
    stages = stages_for(state, wid)
    if not stages:
        raise ValueError("weapon has no enhancement stages; supply enhancement options")
    server = state.server(SERVER_ENH)
    for key, row in stages:
        if key not in server or str(server[key].get("equipmentId")) != wid:
            raise ValueError("enhancement stage client/server ownership mismatch")
        row[0] = category
        write_row(state, ENH_SHOP, key, row)
        state.set_server_keys(SERVER_ENH, {key: {**server[key], "shopCategoryId": int(category)}})


def enhance(state, wid, spec, category, reserved):
    donor = spec.get("sourceWeapon", wid)
    row = one(state, ENH, donor, 9)
    old_cap, cap = int(row[0]), spec["maxLevel"]
    if wid in state.table(ENH) and cap < int(one(state, ENH, wid, 9)[0]):
        raise ValueError("lowering an existing enhancement cap would retire old rows")
    row[0] = str(cap)
    # Display thresholds must remain reachable after selecting a shorter donor curve.
    for column in (1, 3, 7):
        if row[column].isdigit():
            row[column] = str(min(int(row[column]), cap))
    write_row(state, ENH, wid, row)
    curve = state.table(ENH_STATUS).get(donor)
    if not isinstance(curve, dict) or not curve:
        raise ValueError("missing enhancement status curve template")
    if any(not key.isdigit() or int(key) > cap for key in curve):
        raise ValueError("enhancement status curve exceeds requested cap")
    curve = copy.deepcopy(curve)
    curve[str(cap)] = curve[max(curve, key=int)]
    existing = state.table(ENH_STATUS).get(wid, {})
    if set(existing) - set(curve):
        raise ValueError("enhancement curve cannot remove existing level keys")
    state.set_leaf(ENH_STATUS, [wid], curve, new=wid not in state.table(ENH_STATUS))
    abilities = state.table(ENH_ABILITY).get(donor)
    if abilities is not None:
        rows = s.parse_rows(abilities)
        for ability in rows:
            if len(ability) != 126 or not ability[1].isdigit() or not ability[2].isdigit():
                raise ValueError("invalid enhancement ability level layout")
            if int(ability[1]) > cap:
                raise ValueError("enhancement ability learn level exceeds cap")
            if int(ability[2]) == old_cap:
                ability[2] = str(cap)
            elif int(ability[2]) > cap:
                raise ValueError("enhancement ability max level exceeds cap")
        text = "\n".join(join(ability) for ability in rows)
        check_ability_rows("equipment_enhancement_ability", text,
            client_profile=getattr(state, "client_profile", None), provides=getattr(state, "client_provides", None))
        state.set_leaf(ENH_ABILITY, [wid], text, new=wid not in state.table(ENH_ABILITY))
    templates = sorted(stages_for(state, donor), key=lambda pair: int(pair[1][3]))
    if not templates:
        raise ValueError("missing enhancement shop template")
    template = templates[0][1]
    if len(template) != 50:
        raise ValueError("enhancement shop template must have 50 columns")
    category = category or template[0]
    one(state, ENH_CATEGORY, category)
    if int(category) in (1, 2, 3, 4):
        raise ValueError("per_level enhancement requires a custom category outside official 1..4")
    previous, totals, products = 0, {}, []
    current = dict(stages_for(state, wid))
    expected = {str(int(wid) * 100 + i) for i in range(1, len(spec["stages"]) + 1)}
    if "products" in spec and spec["products"] != sorted(expected, key=int):
        raise ValueError("enhancement products do not match weapon ID * 100 + stage")
    if set(current) - expected:
        raise ValueError("new enhancement ladder would remove existing product keys")
    server = state.server(SERVER_ENH)
    if {key for key, value in server.items() if str(value.get("equipmentId")) == wid} != set(current):
        raise ValueError("enhancement stage set differs between client and server")
    occupied = set(state.table(ENH_SHOP)) | set(server) | set(reserved.get("enhancementProducts", []))
    for index, stage in enumerate(spec["stages"], 1):
        limit = stage["maxLevel"]
        if not previous < limit <= cap:
            raise ValueError("enhancement stages must increase strictly and end at maxLevel")
        product = str(int(wid) * 100 + index)
        if product in current:
            if product not in server or str(server[product].get("equipmentId")) != wid:
                raise ValueError("enhancement stage client/server ownership mismatch")
        else:
            allocate_available("enhancement_shop", occupied, requested=product)
        row = list(template)
        row[0], row[2], row[3], row[4], row[5] = category, wid, str(index), "1", "100"
        row[11:22] = ["(None)", "", "(None)"] + ["(None)", ""] * 4
        costs = stage["costs"]
        if len({cost["itemId"] for cost in costs}) != len(costs):
            raise ValueError("duplicate enhancement material")
        for slot, cost in enumerate(costs):
            material(state, cost["itemId"])
            row[14 + slot * 2:16 + slot * 2] = [cost["itemId"], str(cost["amount"])]
            totals[cost["itemId"]] = totals.get(cost["itemId"], 0) + cost["amount"] * (limit - previous)
        awakening = stage.get("requireAwakeningLevel", int(one(state, s.EQUIPMENT, wid, 16)[8]))
        if awakening > int(one(state, s.EQUIPMENT, wid, 16)[8]):
            raise ValueError("stage awakening requirement exceeds weapon max awakening")
        row[22:24] = [START, "(None)"]
        row[29:32] = [wid, str(limit), str(awakening)]
        write_row(state, ENH_SHOP, product, row)
        state.set_server_keys(SERVER_ENH, {product: {
            "availableFrom": START, "availableUntil": None,
            "costs": [{"id": int(cost["itemId"]), "amount": cost["amount"]} for cost in costs],
            "enhancementMaxLevel": limit, "equipmentId": int(wid), "groupId": int(wid),
            "requireAwakeningLevel": awakening, "rewards": [], "shopCategoryId": int(category),
            "stage": index, "stock": -1, "enhancementPurchaseMode": "per_level"}})
        previous = limit
        products.append(product)
    if previous != cap:
        raise ValueError("last enhancement stage must equal maxLevel")
    spec["products"] = products
    state.weapon_checks = [*getattr(state, "weapon_checks", []), result("weapon.enhancement-cost", "满足",
        "强化按每级收费，免费区间无成本，已清除母本额外货币价格。", maxLevel=cap,
        purchaseMode="per_level", materialTotals=totals)]
