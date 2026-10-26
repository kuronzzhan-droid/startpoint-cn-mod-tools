"""Weapon data dependencies, including legacy capabilities without hash evidence."""
import json

CUSTOM = "master/string/custom_ability_string.orderedmap"
AWAKENING = "equipment-awakening-material-v1"


def weapon_requirements(client, server, *, read_raw=None):
    from .requirements import parse_table
    capabilities, features = set(), set()
    before = None
    if CUSTOM in client and read_raw is not None:
        try:
            before = read_raw(CUSTOM)
            before = before[0] if isinstance(before, tuple) else before
        except (KeyError, FileNotFoundError):
            pass
    original = parse_table(before, CUSTOM) if before is not None else {}
    if CUSTOM in client and any(key.startswith("awakening_material_") and original.get(key) != value
                                for key, value in parse_table(client[CUSTOM], CUSTOM).items()):
        capabilities.add(AWAKENING)
        features.add("equipment_awakening_material.materialByEquipment")
    for target, raw in server.items():
        document = json.loads(raw)
        if target.endswith("equipment_awakening_material.json") and document.get("materialByEquipment"):
            features.add("equipment_awakening_material.materialByEquipment")
        if target.endswith("equipment_enhancement_shop.json") and any(
                value.get("enhancementPurchaseMode") == "per_level" for value in document.values()):
            features.add("equipment_enhancement_shop.per_level")
        if target.endswith("equipment_dissolve.json") and any(
                value.get("generate_ability_soul") is False for value in document.values()):
            features.add("equipment_dissolve.generate_ability_soul")
    return {"clientCapabilities": sorted(capabilities), "serverFeatures": sorted(features)}
