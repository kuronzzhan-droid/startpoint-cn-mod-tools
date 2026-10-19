"""One operation registry shared by HTTP, CLI and persisted boss draft replay."""
from __future__ import annotations


def apply_operation(state, quest, request, *, reserved):
    operation = request["operation"]
    if operation.startswith("terrain_"):
        from wf.boss.terrain_edit import apply_terrain
        return apply_terrain(state, quest, request)
    if operation.startswith("shop_") or operation.startswith("weapon_"):
        from wf.boss.shop_weapon import apply_shop_weapon
        return apply_shop_weapon(state, quest, request, reserved=reserved)
    if operation.startswith("behavior_"):
        from wf.boss.behavior import apply_behavior
        return apply_behavior(state, quest, request)
    raise ValueError(f"unsupported boss operation: {operation}")


def draft_weapons(state, requests):
    from wf.boss.reader import BossReader
    from wf.boss.shop_model import equipment
    reader = BossReader(state)
    identities = dict.fromkeys(req["weapon"]["id"] for req in requests
                               if req["operation"] == "weapon_clone")
    return [equipment(reader, identity) for identity in identities]


def inspect_section(state, document, section, requests=()):
    if section == "terrain":
        return document["terrain"]
    if section == "shops":
        return document["shops"]
    if section == "weapons":
        associated = {weapon["id"]: weapon for shop in document["shops"] for weapon in shop["weapons"]}
        associated.update({weapon["id"]: weapon for weapon in draft_weapons(state, requests)})
        return list(associated.values())
    if section in {"behavior", "timeline"}:
        from wf.boss.behavior import read_behavior
        behavior = read_behavior(state, document)
        return behavior if section == "behavior" else behavior["timeline"]
    raise ValueError(f"unknown boss section: {section}")
