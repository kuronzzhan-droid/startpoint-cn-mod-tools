"""从实际126列行计算六能力伤害增益峰值，不以面板文字作验收。"""
from decimal import Decimal

INSTANT_DAMAGE = {0, 1, 32, 33, 34, 53, 55, 96, 117, 119, 145, 199,
                  201, 202, 223, 388, 483, 484, 491, 512, 518, 520, 538, 559,
                  565, 693, 694, 695, 696}
DURING_DAMAGE = {0, 1, 2, 21, 23, 45, 46, 83, 106, 154, 158, 159, 161, 162,
                 258, 288, 410, 411, 412, 413}
INDEPENDENT = {("0", 201), ("0", 202), ("1", 45), ("1", 46),
               ("0", 693), ("0", 694), ("0", 695),
               ("0", 696), ("1", 410), ("1", 411), ("1", 412), ("1", 413)}
# Reduction of an enemy's resistance also improves damage and is counted.
ENEMY_RESISTANCE = set(range(392, 399))
NATIVE_COUNT_DURING = {2, 38, 64, 134, 136, 209}


def _cap(raw):
    if raw in ("", "(None)"):
        raise ValueError("damage growth must have an explicit finite native cap")
    value = Decimal(raw)
    if value <= 0:
        raise ValueError("damage cap must be positive")
    return value


def row_peak(row):
    mode = row[5]
    if mode not in ("0", "1"):
        raise ValueError("unsupported damage budget mode")
    column = 47 if mode == "0" else 109
    kind = int(row[column])
    if mode == "1" and int(row[97]) == 136 and kind not in (158, 159, 258, 288):
        raise ValueError("enemy-scoped trigger requires a target-aware damage content")
    damage = kind in (INSTANT_DAMAGE if mode == "0" else DURING_DAMAGE)
    resist = mode == "0" and kind in ENEMY_RESISTANCE
    if not damage and not resist:
        return Decimal(0), False
    strength = max(Decimal(row[column + offset] or 0) for offset in (4, 5)) / 1000
    if resist:
        strength = max(-Decimal(row[column + offset] or 0) for offset in (4, 5)) / 1000
    if strength <= 0:
        return Decimal(0), False
    count = Decimal(1)
    if mode == "1" and int(row[97]) in NATIVE_COUNT_DURING:
        count *= _cap(row[102])
    if mode == "0":
        timed = row[57] != ""
        if timed:
            count *= _cap(row[61])
        elif row[27] not in ("", "0"):
            count *= _cap(row[34])
        if row[75] not in ("", "0"):
            raise ValueError("unreviewed multiply-trigger damage growth")
    return strength * count, (mode, kind) in INDEPENDENT


def audit(abilities):
    slots, independent = {}, []
    for slot, rows in abilities.items():
        total = Decimal(0)
        for index, row in enumerate(rows):
            peak, separate = row_peak(row)
            total += peak
            if separate:
                independent.append({"slot": slot, "row": index, "peak_percent": float(peak)})
        slots[str(slot)] = float(total)
    total = sum(slots.values())
    if total > 300:
        raise ValueError(f"six-ability damage budget exceeded: {total}%")
    if len(independent) > 1 or any(entry["peak_percent"] > 15 for entry in independent):
        raise ValueError("only one independent term of at most 15% is permitted")
    return {"scope": "six abilities, all simultaneous conditional peaks conservatively summed",
            "slot_peak_percent": slots, "total_peak_percent": total,
            "independent_terms": independent,
            "active_and_leader_excluded_from_300_percent": True,
            "base_hp_and_attack_excluded_from_damage_bonus_budget": True,
            "triggered_attack_coefficients_are_attacks_not_percentage_bonuses": True}
