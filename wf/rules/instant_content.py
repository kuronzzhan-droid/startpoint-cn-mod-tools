"""Sentinel values for fields declared by the client's instant-content cases.

The case and column definitions come from this repository's enum map.  This
keeps ability, leader, soul, and equipment layouts on the same rule without
maintaining another list of content kinds.
"""

from __future__ import annotations

import wf_describe


_DEFAULTS = {
    "by_each_trigger_puller": "false",
    "multiply_trigger": "0",
    "max_accumulation": "(None)",
    "flip_limit": "(None)",
    "power_flip_limit": "(None)",
    "end_power_flip_limit": "(None)",
    "end_power_flip_accepted_levels": "(None)",
}
_ACCEPTED_LEVELS = frozenset({"(None)", "1", "2", "3", "11", "12"})


def _declared_columns(kind: str, row: list[str]) -> dict[str, int]:
    blocks = wf_describe.layout(kind)["blocks"]
    mode_column = int(blocks["precondition1"]) - 1
    if mode_column >= len(row) or str(row[mode_column]).strip() != "0":
        return {}
    base = int(blocks["instant_content"])
    if base >= len(row):
        return {}
    enum_map = wf_describe.enum_map()
    case = enum_map["cases"]["instant_content"].get(str(row[base]).strip())
    if case is None:
        return {}
    return {
        field: base + int(offset)
        for offset, field, _label in enum_map["block_fields"]["instant_content"]
        if field in _DEFAULTS and field in case["fields"]
    }


def fill_instant_content_defaults(kind: str, row: list[str]) -> list[str]:
    """Return a copy with empty, declared sentinel fields initialized.

    Explicit values are retained for the caller's normal legality check.
    Undeclared fields and inactive instant-content blocks remain untouched.
    """
    result = list(row)
    for field, column in _declared_columns(kind, row).items():
        if column >= len(result):
            raise ValueError(f"{kind} row is truncated before {field} at c{column}")
        if not str(result[column]).strip():
            result[column] = _DEFAULTS[field]
    return result


def instant_option_value_problems(kind: str, row: list[str]) -> list[str]:
    """Reject populated PF-level values that the client cannot describe.

    The existing declared-field validator already rejects empty Option cells.
    This check closes the remaining nonempty-value gap only.
    """
    field = "end_power_flip_accepted_levels"
    column = _declared_columns(kind, row).get(field)
    if column is None or column >= len(row):
        return []
    value = str(row[column]).strip()
    if not value or value in _ACCEPTED_LEVELS:
        return []
    return [
        f"c{column} {field}={value!r} 须为 '(None)' 或 1/2/3/11/12"
        "(客户端无法解析其余 PF 等级，角色页 F1009)"
    ]
