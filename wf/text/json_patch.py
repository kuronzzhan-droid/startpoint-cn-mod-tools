"""Replace selected mirror cells without reserializing any surrounding JSON."""
from __future__ import annotations

import json

from wf.deliver.json_merge import _json_spans


def parse_mirror(raw: bytes) -> dict:
    """Use the strict shared parser: duplicate keys and non-finite values fail."""
    return _json_spans(raw)[1]


def patch_columns(raw: bytes, character_id: str, columns: dict[int, str]) -> bytes:
    """Patch only string tokens in a character's first row; preserve all else."""
    text, document, members = _json_spans(raw)
    rows = document.get(character_id)
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
        raise ValueError(f"server character_text row is malformed: {character_id}")
    if any(not isinstance(column, int) or column < 0 or column >= len(rows[0])
           or not isinstance(rows[0][column], str) or not isinstance(value, str)
           for column, value in columns.items()):
        raise ValueError("server character_text patch requires existing string cells")
    # Both enclosing arrays have already been validated by the strict parser.
    position = members[character_id][0] + 1
    while text[position].isspace():
        position += 1
    position += 1  # First row's opening '['.
    decoder = json.JSONDecoder()
    replacements = []
    for column in range(len(rows[0])):
        while text[position].isspace():
            position += 1
        start = position
        old, position = decoder.raw_decode(text, position)
        if column in columns and old != columns[column]:
            replacements.append((start, position, json.dumps(columns[column], ensure_ascii=False)))
        while text[position].isspace():
            position += 1
        if text[position] == ',':
            position += 1
    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]
    result = text.encode("utf-8") if replacements else raw
    expected = document
    for column, value in columns.items():
        expected[character_id][0][column] = value
    if parse_mirror(result) != expected:
        raise AssertionError("server character_text minimal patch round-trip failed")
    return result
