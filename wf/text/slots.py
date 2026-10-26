"""Resolve override ownership from actual slot c0 values, never key suffixes."""
from __future__ import annotations

import csv
import io

from .model import ABILITY, CHARACTER, LEADER, cells


def override_slots(workspace, character_id=None):
    """Map exact desc_override_<c0> keys to their table rows and owners.

    All table slots are retained in a whole-table audit, including slots with
    no character owner. A character projection only includes referenced slots.
    """
    owners = {}
    for cid, leaf in workspace.table(CHARACTER).items():
        row = cells(leaf)
        for table, keys in ((LEADER, row[17:18]), (ABILITY, row[19:25])):
            for key in keys:
                owners.setdefault((table, key), []).append(str(cid))
    result = {}
    for table, kind in ((LEADER, "leader"), (ABILITY, "ability")):
        for key, leaf in workspace.table(table).items():
            character_ids = sorted(set(owners.get((table, key), [])))
            if character_id is not None and str(character_id) not in character_ids:
                continue
            if not isinstance(leaf, str) or not leaf:
                continue
            rows = list(csv.reader(io.StringIO(leaf, newline="")))
            for index, row in enumerate(rows):
                if not row or not row[0]:
                    continue
                result.setdefault("desc_override_" + row[0], []).append({
                    "kind": kind, "table": table, "key": key, "row": index,
                    "c0": row[0], "character_ids": character_ids,
                    "main_only": kind == "ability" and len(row) > 1 and row[1] == "false"})
    return result
