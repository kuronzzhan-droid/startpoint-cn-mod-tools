"""Soul item text and equip-element restrictions shared by weapon editors."""
from wf.rules.catalog import result

from .shop_edit import validate_text

ALL_ELEMENTS = "0,3,2,1,4,5"
INHERITED_RULE = "weapon.soul-elements-inherited"


def edit_soul_item(item, spec, source):
    """item c5 is description; c12 is the equip-element list (30 = infer)."""
    if "soulDescription" in spec:
        description = spec["soulDescription"]
        if not isinstance(description, str) or not 1 <= len(description) <= 1000:
            raise ValueError("soulDescription must contain 1 to 1000 characters")
        validate_text(description, "soulDescription")
        item[5] = description
    if "soul_elements" not in spec:
        return [result(INHERITED_RULE, "待验证",
            f"未设置 soul_elements，魂珠沿用母本武器 {source} 的可装备属性限制 "
            f"item[12]={item[12]!r}；请确认是否符合新武器设计。",
            sourceWeapon=source, soulElements=item[12])]
    elements = spec["soul_elements"]
    if elements == "all":
        item[12] = ALL_ELEMENTS
    elif elements == "auto":
        item[12] = "30"
    elif (isinstance(elements, list) and 1 <= len(elements) <= 6
          and all(type(value) is int and 0 <= value <= 5 for value in elements)
          and len(set(elements)) == len(elements)):
        item[12] = ",".join(map(str, elements))
    else:
        raise ValueError("soul_elements must be all, auto, or a nonempty unique list of integers 0 to 5")
    return []
