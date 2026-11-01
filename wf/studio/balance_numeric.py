"""Exact numeric candidates, checked again by rendering the entire description."""
import re
from decimal import Decimal
import wf_describe

from .ability_fields import active_fields
from .ability_vocabulary import field_rules, strength_count_kinds

INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)")


def numeric_cells(row, table):
    rules = field_rules()[table]
    result = {}
    for col, (block, field) in active_fields(row, table).items():
        rule = rules.get(str(col), {})
        if field == "time":
            start = wf_describe.layout(table)["blocks"][block]
            name = wf_describe.enum_options()[block].get(row[start], {}).get("en", "")
            rule = {"block": block, "field": field,
                    "format": "count" if "EnemyDamageBy" in name else "raw_integer"}
        if rule.get("format") and INTEGER.fullmatch(row[col]):
            result[col] = rule
    return result


def valid_value(value, rule):
    return bool(INTEGER.fullmatch(value)) and (not value.startswith("-") or
            rule["format"] in {"strength", "percent", "threshold"})


def scale_for(row, rule):
    unit = rule["format"]
    if unit == "strength":
        count = row[rule["kindColumn"]] in strength_count_kinds()[rule["group"]]
        return 100000 if count and all(int(row[c] or 0) % 100000 == 0 for c in rule["endpoints"]) else 1000
    if unit == "threshold":
        return None  # chosen from the current endpoint below, matching describe._threshold
    return {"percent": 1000, "scaled_frames": 6000000, "scaled_count": 100000,
            "frames": 60}.get(unit, 1)


def candidates(row, table, old, new):
    allowed = numeric_cells(row, table)
    for col, rule in allowed.items():
        if rule["format"] == "raw_integer":
            continue  # The constructor has no verified human-readable unit.
        raw = int(row[col])
        scale = scale_for(row, rule)
        if scale is None:
            scale = 100000 if raw >= 100000 and raw % 100000 == 0 else 1000
        if Decimal(raw) != old * scale or new * scale != (new * scale).to_integral_value():
            continue
        value = str(int(new * scale))
        if not valid_value(value, rule):
            continue
        groups = [[col]]
        field = rule["field"]
        if field.endswith(".power1") and col + 1 in allowed and row[col] == row[col + 1]:
            other = allowed[col + 1]
            if other["block"] == rule["block"] and other["field"] == field.replace(".power1", ".first_max"):
                groups.append([col, col + 1])
        for columns in groups:
            yield [{"column": c, "old": row[c], "new": value} for c in columns]
