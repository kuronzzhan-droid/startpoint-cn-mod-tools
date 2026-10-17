"""Safe, per-effect ability badges derived from native table conditions.

AbilityValues: c1 is unisonable; the three precondition blocks start at
c6/c13/c20. AbilityPreconditionMasterValueTools resolves 202/203 to position,
3 to MySelf and 2 to Member. InstantAbilityDescriptionGenerator calls only
a single-element Member(count=6) resonance. Character groups are OR groups:
never split a multi-group expression into independent AND badges.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

ELEMENTS = {
    "Red": ("火", "fire"), "Blue": ("水", "water"),
    "Yellow": ("雷", "thunder"), "Green": ("风", "wind"),
    "White": ("光", "light"), "Black": ("暗", "dark"),
}


def _cell(row, index):
    return str(row[index]).strip() if index < len(row) else ""


def _six(value):
    # AbilityPowerValue uses Decimal fixed-point values (one = 100000).
    try:
        return Decimal(value) == 600000
    except InvalidOperation:
        return False


def ability_restrictions(row: list) -> dict:
    """Return proven badges, supplementary to (never replacing) row text.

    Items all constrain this one effect. Empty or unknown conditions and
    multi-group OR expressions retain their existing description only.
    A changing member-count threshold is not a constant resonance badge.
    """
    items = []

    def position(kind):
        item = {"kind": kind, "label": "仅主位" if kind == "main" else "仅合击位", "icon": kind}
        if item not in items:
            items.append(item)

    if _cell(row, 1).lower() == "false":
        position("main")
    # Opening abilities do not read the three normal precondition blocks.
    if _cell(row, 5) not in ("0", "1"):
        return {"operator": "AND", "items": items}
    for start in (6, 13, 20):
        condition = _cell(row, start)
        if condition in ("202", "203"):
            position("main" if condition == "202" else "unison")
            continue
        element = ELEMENTS.get(_cell(row, start + 5))
        if element is None:
            continue
        label, icon = element
        if condition == "3":
            item = {"kind": "selfElement", "label": f"自身为{label}属性", "icon": icon, "element": label}
        elif condition == "2" and all(_six(_cell(row, start + i)) for i in (3, 4)):
            item = {"kind": "resonance", "label": f"{label}属性共鸣（编成6名{label}属性角色）",
                    "icon": icon, "element": label}
        else:
            continue
        if item not in items:
            items.append(item)
    return {"operator": "AND", "items": items}
