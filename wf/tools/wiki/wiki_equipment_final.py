"""Conservative final equipment effects, combined from resolved native rows."""
from fractions import Fraction
import math

import wf_describe
from wf_wiki_equipment_helpers import cell, effects, endpoint_row, integer, learned_rows

KIND = "equipment_enhancement_ability"
# CommonAbilityContent additive stats, NOT condition buffs, instant gauge refill,
# InvokeSkill programs or DirectAttack overrides. Unknown effects stay separate.
# 35 is passive SkillGaugeCharging speed (InstantAbilitySource), not SkillGauge.
ADDITIVE = {"32", "33", "34", "35", "55", "205", "388"}
# Deterministic opening / skill events only. Random and reactive condition
# triggers can observe intermediate state and must not be collapsed.
TRIGGERS = {"", "0", "1", "23", "57"}


def row_at_level(row, level):
    """Native MinToMaxLevelScale + Decimal rounding, without modifying input."""
    result = list(row)
    first_level, last_level = integer(row[1], 1), integer(row[2], 1)
    definitions = wf_describe.enum_map()["block_fields"]
    for name, base in wf_describe.layout(KIND)["blocks"].items():
        group = "precondition" if name.startswith("precondition") else name
        for offset, field, _ in definitions.get(group, []):
            if not field.endswith(".power1") or base + offset + 1 >= len(row):
                continue
            first, last = base + offset, base + offset + 1
            if not cell(row, first) and not cell(row, last):
                continue
            a, b = integer(cell(row, first)), integer(cell(row, last))
            if level <= first_level:
                value = a
            elif level >= last_level:
                value = b
            else:
                value = math.floor(Fraction(a) + Fraction((b - a) * (level - first_level),
                                                         last_level - first_level) + Fraction(1, 2))
            result[first] = result[last] = str(value)
    return result


def additive_key(row, kind):
    """Compare EVERY body field except the additive strength endpoint pair.

    Native equipment headers differ by three columns (level scaling and battle
    power); the complete trigger body is identical. No text-derived matching,
    broad blank/zero normalization, target guessing or partial condition keys.
    """
    blocks = wf_describe.layout(kind)["blocks"]
    start, content = blocks["precondition1"] - 1, blocks["instant_content"]
    if (cell(row, start) != "0" or cell(row, content) not in ADDITIVE or
            cell(row, blocks["instant_trigger"]) not in TRIGGERS or
            cell(row, blocks["instant_precontent"]) not in ("", "(None)")):
        return None
    # Dynamic multipliers, overrides, custom actions and timed content are
    # intentionally excluded even when two rows happen to match.
    for offset in (*range(6, 19), *range(21, 38)):
        if cell(row, content + offset) not in ("", "0", "false", "(None)"):
            return None
    try:
        int(cell(row, content + 4))
    except (TypeError, ValueError):
        return None
    body = list(row[start:])
    body[content + 4 - start:content + 6 - start] = ["<strength>"] * 2
    return tuple(body)


def combined_effects(rows, text):
    """Preserve all unsupported rows and their order, including duplicates."""
    result, positions = [], {}
    for kind, original in rows:
        row = list(original)
        key = additive_key(row, kind)
        if key is not None and key in positions:
            old_kind, old = result[positions[key]]
            target = wf_describe.layout(old_kind)["blocks"]["instant_content"] + 4
            source = wf_describe.layout(kind)["blocks"]["instant_content"] + 4
            total = int(old[target]) + int(row[source])
            old[target:target + 2] = [str(total)] * 2
        else:
            if key is not None:
                positions[key] = len(result)
            result.append((kind, row))
    rendered = []
    for kind, row in result:
        # Render one row at a time: base/enhancement slots are separate namespaces.
        lines = effects([row], kind, integer(cell(row, 1), 1), text)
        blocks = wf_describe.layout(kind)["blocks"]
        trigger, content = blocks["instant_trigger"], blocks["instant_content"]
        limit = integer(cell(row, trigger + 7))
        if lines and additive_key(row, kind) is not None and cell(row, trigger) == "23" and limit > 1:
            total = int(cell(row, content + 4)) * limit / 1000
            lines[-1] += f"（该项触发满{limit}次时累计{total:g}%）"
        rendered.extend(lines)
    return rendered


def final_effect_fields(soul_rows, enhancement_rows, awakening_level, enhancement_level, text):
    """Return complete effects for max/initial base plus the selected upgrade."""
    enhanced = [(KIND, row_at_level(row, enhancement_level))
                for row in learned_rows(enhancement_rows, enhancement_level)]
    def at_base(level, maximum):
        base = [("ability_soul", endpoint_row(row, "ability_soul", maximum))
                for row in learned_rows(soul_rows, level)]
        return combined_effects(base + enhanced, text)
    return {"finalEffects": at_base(awakening_level, True),
            "initialFinalEffects": at_base(1, False)}
