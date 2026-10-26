"""Resolve all character owners from the input view before editing shared keys."""
from __future__ import annotations

import csv
import io

import wf_quest_lib as nodes

CHARACTER = "master/character/character.orderedmap"


def owner_index(view):
    result = {name: {} for name in ("ability", "leader_ability", "action_skill")}
    characters = nodes.parse_node(view.read_raw(CHARACTER)[0])
    for cid, leaf in characters.items():
        rows = list(csv.reader(io.StringIO(leaf, newline="")))
        if len(rows) != 1 or len(rows[0]) < 25:
            raise ValueError(f"character/{cid}: cannot determine balance key ownership")
        row = rows[0]
        for table, keys in (("ability", row[19:25]), ("leader_ability", row[17:18]),
                            ("action_skill", row[8:9])):
            for key in set(keys) - {""}:
                result[table].setdefault(key, set()).add(cid)
    return result


def check_owner(operation, index):
    table, key, cid = operation["table"], operation["key"], operation["character"]
    owners = sorted(index[table].get(key, set()))
    location = f"{table}/{key}"
    if cid not in owners:
        raise ValueError(f"{location}: character {cid} is not an owner; owners={owners}")
    if len(owners) > 1 and operation.get("shared_ok") is not True:
        raise ValueError(f"{location}: shared key owners={owners}; declare shared_ok: true explicitly")
    return owners
