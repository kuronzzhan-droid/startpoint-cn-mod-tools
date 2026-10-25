"""Weapon code ownership and explicitly non-enforcing character metadata."""
import re

from wf.rules.catalog import result
from . import schema as s
from .shop_model import ITEM


def clone_codes(state, spec, identity, reserved):
    code = spec.get("code", "boss_workshop_" + identity)
    if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code):
        raise ValueError("weapon code must match [a-z][a-z0-9_]{0,79}")
    soul_code = code + "_soul" if "code" in spec else "boss_workshop_soul_" + identity
    occupied = set(reserved.get("codes", [])) if isinstance(reserved, dict) else set()
    for logical in (s.EQUIPMENT, ITEM):
        for value in state.table(logical).values():
            occupied.update(s.cell(row, 0) for row in s.parse_rows(value))
    for name in (code, soul_code):
        if name in occupied:
            raise ValueError(f"weapon code collision: {name}")
    return code, soul_code


def exclusive_metadata(spec):
    if "exclusive_character" not in spec:
        return []
    cid = spec["exclusive_character"]
    if not isinstance(cid, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", cid):
        raise ValueError("exclusive_character must be a positive character ID string")
    return [result("weapon.exclusive-character-metadata", "待验证",
        "exclusive_character 仅记录设计归属，不限制装备或魂珠装配；已查客户端装备表无角色 ID 列，"
        "item c12 是属性列表，未找到专属角色限制补丁证据。",
        characterId=cid, enforcement="metadata_only",
        evidence=["EquipmentValues constructor: c0..c15", "ItemValues AbilitySoul: parseAt12(element)"])]
