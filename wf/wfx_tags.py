"""Read character tags from their actual typed cells, not a synthetic master table."""
from __future__ import annotations

import re


def tag_tokens(value):
    return (token.strip() for token in re.split(r"[,/]", value) if token.strip())


def ability_tags(table, row):
    """Yield (column, token) from group fields in the active parsed blocks."""
    import wf_describe
    from wf_client_legality import BLOCK_CASE_KEY, BLOCK_FIELDS_KEY, TRIGGER_MODE_BLOCKS

    enum = wf_describe.enum_map()
    blocks = wf_describe.layout(table)["blocks"]
    mode_column = int(blocks["precondition1"]) - 1
    mode = row[mode_column].strip() if len(row) > mode_column else ""
    parsed = list(TRIGGER_MODE_BLOCKS.get(mode, ()))
    if mode == "0":
        parsed.append("instant_precontent")
    for block in parsed:
        base = int(blocks[block])
        kind = row[base].strip() if len(row) > base else ""
        if kind in {"", "(None)"}:
            continue
        case_key = BLOCK_CASE_KEY.get(block)
        case = enum["cases"].get(case_key, {}).get(kind)
        if case_key and case is None:
            continue
        for offset, field, _ in enum["block_fields"][BLOCK_FIELDS_KEY.get(block, block)]:
            if field != "character_groups" and not field.endswith(".character_groups"):
                continue
            root = field.split(".", 1)[0]
            root = "multiply_trigger" if root == "mt" else root
            if case is not None and root not in case["fields"]:
                continue
            column = base + int(offset)
            if len(row) > column:
                for token in tag_tokens(row[column]):
                    yield column, token
