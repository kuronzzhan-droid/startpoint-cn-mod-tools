"""Boss request dispatcher for shop products and their weapon graphs."""
from . import schema as s
from .shop_edit import edit_shop
from .weapon_edit import clone_weapon, edit_materials

OPERATIONS = {"shop_add", "shop_edit", "shop_delete", "weapon_clone", "weapon_materials"}


def apply_shop_weapon(state, quest, request, *, reserved=()):
    from .reader import BossReader
    document = BossReader(state).show(quest)
    if document.get("routing", {}).get("kind") == "BothBoss":
        raise ValueError("BothBoss route entrance cannot be edited; select a hidden combat quest")
    operation = request["operation"]
    if operation not in OPERATIONS:
        raise ValueError(f"unsupported shop/weapon operation: {operation}")
    shops = document["shops"]
    if operation.startswith("shop_"):
        edit_shop(state, request, {entry["id"] for entry in shops}, reserved)
    elif operation == "weapon_clone":
        clone_weapon(state, request["weapon"], reserved)
    else:
        identity = str(request["weapon"]["id"])
        associated = {weapon["id"] for shop in shops for weapon in shop["weapons"]}
        associated.update(c["path"][0] for c in state.changes
                          if c["table"] == s.EQUIPMENT and c["old"] is None and c["path"])
        if identity not in associated:
            raise ValueError(f"weapon {identity} is not associated with this boss or its cloned draft")
        edit_materials(state, request["weapon"])
    return [document["quest"]["selector"]]
