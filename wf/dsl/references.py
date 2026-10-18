"""Derive kind-629 action roots from actual table layouts and skill rows."""
from __future__ import annotations

import csv
import io
import re

from wf.view.layout import col

ACTION_SKILL = "master/skill/action_skill.orderedmap"
ABILITY_TABLES = {
    "master/ability/ability.orderedmap": "ability",
    "master/ability/leader_ability.orderedmap": "leader_ability",
    "master/ability/ability_soul.orderedmap": "ability_soul",
    "master/equipment_enhancement/equipment_enhancement_ability.orderedmap": "equipment_enhancement_ability",
}
DSL_SUFFIX = ".action.dsl.amf3.deflate"
PROGRAM = re.compile(r"^battle/[A-Za-z0-9_./-]+\$[A-Za-z0-9_.-]+$")


def program_logical(value):
    if not isinstance(value, str):
        return None
    program = value.removesuffix(DSL_SUFFIX)
    return program + DSL_SUFFIX if PROGRAM.fullmatch(program) else None


def linked_programs(tree):
    """Return exact path$program references, without treating prose as paths."""
    found = set()

    def walk(value):
        logical = program_logical(value)
        if logical:
            found.add(logical)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(tree)
    return found


def ability_references(logical, data):
    table = ABILITY_TABLES[logical]
    kind_col, skill_col, path_col = (col(table, "instant_content", name)
                                   for name in ("kind", "string_id", "action_path"))
    for key, leaf in data.items():
        if not isinstance(leaf, str):
            raise ValueError(f"{logical}/{key}: ability leaf is not CSV text")
        for index, row in enumerate(csv.reader(io.StringIO(leaf, newline=""))):
            if len(row) > kind_col and row[kind_col] == "629":
                if len(row) <= path_col:
                    raise ValueError(f"{logical}/{key}/{index}: truncated kind 629 row")
                yield {"table": logical, "key": key, "row": index,
                       "skill": row[skill_col], "action": row[path_col]}


def resolve_programs(reference, skills):
    """Explicit action_path wins; absent paths resolve the referenced skill."""
    action = reference["action"]
    if action not in {"", "(None)"}:
        logical = program_logical(action)
        if logical is None:
            raise ValueError(f"invalid kind 629 action_path: {action!r}")
        return {logical}
    skill = reference["skill"]
    direct = program_logical(skill)
    if direct:
        return {direct}
    tiers = skills.get(skill)
    if not isinstance(tiers, dict):
        raise ValueError(f"kind 629 references missing action_skill: {skill}")
    found = set()
    for level, leaf in tiers.items():
        for row in csv.reader(io.StringIO(leaf, newline="")):
            logical = program_logical(row[7]) if len(row) > 7 else None
            if logical:
                found.add(logical)
            else:
                raise ValueError(f"action_skill/{skill}/{level}: missing path$program at c7")
    if not found:
        raise ValueError(f"kind 629 references empty action_skill: {skill}")
    return found
