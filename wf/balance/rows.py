"""Lossless CSV leaves and shared ability/leader column addressing."""
from __future__ import annotations

import csv
import io

TABLES = {
    "ability": "master/ability/ability.orderedmap",
    "leader_ability": "master/ability/leader_ability.orderedmap",
    "action_skill": "master/skill/action_skill.orderedmap",
    "custom_ability_string": "master/string/custom_ability_string.orderedmap",
}
WIDTHS = {"ability": 126, "leader_ability": 124}


def split_leaf(text: str, table: str) -> list[list[str]]:
    """Split *before* indexing: n ability rows have 125*n+1 comma fields.

    A comma split glues c125 to the following c0 across the newline. CSV rows
    also handle quoted commas/newlines correctly; no flat-column edits occur.
    """
    if not isinstance(text, str):
        raise ValueError(f"{table}: expected a CSV leaf")
    rows = [row for row in csv.reader(io.StringIO(text, newline="")) if row]
    width = WIDTHS.get(table)
    if width:
        for index, row in enumerate(rows):
            if len(row) != width:
                raise ValueError(f"{table} row {index}: expected {width} columns, got {len(row)}")
    return rows


def join_leaf(original: str, rows: list[list[str]]) -> str:
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    result = output.getvalue()
    return result if original.endswith("\n") else result.rstrip("\n")


def column_index(table: str, column: int | str, space: str = "ability") -> int:
    """Default ability cN numbering maps automatically to leader c(N-2).

    c0 exists on both tables. Ability c1 (unison) and c2 (category) have no
    leader equivalent and fail explicitly. Native numbering is opt-in.
    """
    if isinstance(column, str):
        if not column.startswith("c") or not column[1:].isdigit():
            raise ValueError(f"invalid column: {column!r}")
        column = int(column[1:])
    if isinstance(column, bool) or not isinstance(column, int) or column < 0:
        raise ValueError(f"invalid column: {column!r}")
    if space not in {"ability", "native"}:
        raise ValueError(f"invalid column_space: {space}")
    if table == "leader_ability" and space == "ability" and column:
        if column in (1, 2):
            raise ValueError(f"leader has no ability c{column}")
        column -= 2
    width = WIDTHS.get(table)
    if width and column >= width:
        raise ValueError(f"{table} column outside {width}-column row: {column}")
    return column


def unison_eligible(rows: list[list[str]]) -> bool:
    """Only the FIRST ability row's c1=true admits an ability to unison."""
    return bool(rows and len(rows[0]) > 1 and rows[0][1] == "true")
