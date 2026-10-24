"""Leader-only Swift compensation, using the same native row as Magnus.

For the existing grounded dash implementation: normal = 90 * (1 + base),
Swift = 20 * (1 + base + compensation). This is not a new client patch.
"""


def swift_guard_plan(code: str, base: int, *, element: str = "",
                     statue: str = "attack_common", metadata: bool = True) -> tuple:
    if not -100000 < base <= 0:
        raise ValueError("unexpected base cooldown modifier")
    strength = (100000 + base) * 7 // 2
    cells = {0: f"{code}_5", 1: "true", 2: statue, 6: "42",
             13: "0", 20: "0", 97: "34", 109: "422", 110: "0",
             113: str(strength), 114: str(strength), 118: "0"}
    if element:
        cells.update({13: "2", 16: "600000", 17: "600000", 18: element})
    if not metadata:
        for col in (0, 1, 2):
            cells.pop(col)
    prefix = "队长 且 风·编成≥6 时" if element == "Green" else "队长 时"
    expected = f"{prefix}: 持续·状态冲刺 → 自身 冲刺参数(可调) {strength / 1000:g}%"
    return "1699991#7", "store", cells, expected


def ability_to_leader(row: list[str], code: str) -> list[str]:
    """Drop ability-only unisonable/statue fields; keep all trigger semantics."""
    if len(row) != 126:
        raise ValueError("ability row must have 126 columns")
    return [code, *row[3:]]
