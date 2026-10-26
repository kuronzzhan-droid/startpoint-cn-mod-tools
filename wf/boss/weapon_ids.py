"""Canonical weapon IDs and the reserved 99-slot enhancement product namespace."""
import re

INT32_MAX = 2147483647
MAX_WEAPON_ID = (INT32_MAX - 99) // 100
AUTO_WEAPON_START, AUTO_WEAPON_END = 5950001, 5999999
WEAPON_ID_PATTERN = (
    r"^(?:[1-9][0-9]{0,6}|1[0-9]{7}|20[0-9]{6}|21[0-3][0-9]{5}|"
    r"214[0-6][0-9]{4}|2147[0-3][0-9]{3}|21474[0-7][0-9]{2}|"
    r"214748[0-2][0-9]|2147483[0-5])$"
)


def validate_weapon_id(value):
    if not isinstance(value, str) or not re.fullmatch(WEAPON_ID_PATTERN, value):
        raise ValueError(f"weapon ID must be a canonical decimal string from 1 to {MAX_WEAPON_ID}")
    return value


def reserved_ids(reserved):
    """The legacy collection argument reserves weapons; a mapping also reserves products."""
    if isinstance(reserved, dict):
        weapons, products = reserved.get("weapons", ()), reserved.get("enhancementProducts", ())
    else:
        weapons, products = reserved, ()
    for values in (weapons, products):
        if not isinstance(values, (list, set, tuple, frozenset)):
            raise ValueError("reserved IDs must be a collection or a weapons/enhancementProducts mapping")
    return set(map(str, weapons)), set(map(str, products))


def product_owners(products):
    owners = set()
    for product in products:
        value = str(product)
        if not re.fullmatch(r"[1-9][0-9]*", value) or not 0 < int(value) <= INT32_MAX:
            raise ValueError(f"enhancement product ID is not a bounded decimal string: {value}")
        owners.add(str(int(value) // 100))
    return owners
