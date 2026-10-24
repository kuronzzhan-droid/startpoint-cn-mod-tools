"""Add native six-character elemental resonance gates to abyss weapon effects.

Soul rows use condition offsets 3/10/17; enhancement rows use 6/13/20.
These are the official PartyCharacterCountHigh (2) blocks, not target filters.
"""
from __future__ import annotations

import wf_mod_tool as core

ELEMENT_GROUPS = ("Red", "Blue", "Yellow", "Green", "White", "Black")
WEAPON_GROUPS = {
    str(8000101 + index): ELEMENT_GROUPS[index // 2] for index in range(12)
}
UNIVERSAL_IDS = frozenset({"8000113", "8000114", "8000115"})
LAYOUTS = {"ability_soul": (123, 3), "equipment_enhancement_ability": (126, 6)}
EMPTY = ["0", "", "", "", "", "", ""]


def gate_row(row: list[str], key: str, kind: str) -> list[str]:
    """Return a gated copy; preserve existing conditions and every effect field."""
    if key not in WEAPON_GROUPS and key not in UNIVERSAL_IDS:
        raise ValueError(f"not one of the 15 abyss weapons: {key}")
    width, start = LAYOUTS[kind]
    if len(row) != width:
        raise ValueError(f"{key}: expected {width} columns, got {len(row)}")
    result = list(row)
    if key in UNIVERSAL_IDS:
        return result
    gate = ["2", "", "", "600000", "600000", WEAPON_GROUPS[key], ""]
    blocks = [start, start + 7, start + 14]
    if any(result[i:i + 7] == gate for i in blocks):
        return result
    for i in blocks:
        if result[i:i + 7] == EMPTY:
            result[i:i + 7] = gate
            return result
    raise ValueError(f"{key}: no empty condition block; refusing to replace a condition")


def gate_leaf(leaf: bytes | str, key: str, kind: str) -> bytes | str:
    """Idempotent single-key patch with native client legality validation."""
    from wf_client_legality import client_legality_problems

    text = leaf.decode("utf-8") if isinstance(leaf, bytes) else leaf
    rows = core.read_csv_lines(text)
    if not rows:
        raise ValueError(f"{key}: empty effect leaf")
    changed = [gate_row(row, key, kind) for row in rows]
    for row in changed:
        errors = client_legality_problems(kind, row)
        if errors:
            raise ValueError(f"{key}: {'; '.join(errors)}")
    if changed == rows:
        return leaf
    result = core.write_csv_lines(changed)
    return result.encode("utf-8") if isinstance(leaf, bytes) else result
