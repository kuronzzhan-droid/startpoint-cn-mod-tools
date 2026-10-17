"""Character-bound dependency references used by roster detection and comparisons."""
from __future__ import annotations

import wf_describe


def at(row: list, column: int) -> str:
    return row[column] if column < len(row) else ""


def logical_program(program: str) -> str:
    return program if program.endswith(".amf3.deflate") else program + ".action.dsl.amf3.deflate"


def character_references(source, row: list[str], official: bool = False) -> tuple[dict, dict]:
    """Collect explicit linked tables and named programs without guessing paths."""
    refs = {name: set() for name in ("switched", "strings", "condition", "power_flip")}
    programs = {}
    for kind, key, column in (("skill", at(row, 8), 7), ("switched", at(row, 14), 0)):
        if not key or key == "(None)":
            continue
        if kind == "switched":
            refs[kind].add(key)
        for level, rows in source.table(kind, official).get(key, {}).items():
            program = at(rows[0], column) if rows else ""
            if program.startswith("battle/"):
                programs[f"{kind}:{level}"] = logical_program(program)
    condition = at(row, 11)
    if condition and condition != "(None)":
        refs["condition"].add(condition)
    strings = set(source.table("strings")) | set(source.table("strings", True))
    groups = [("leader", at(row, 17), "L")]
    groups += [("ability", key, f"A{slot}") for slot, key in enumerate(row[19:25], 1)]
    for kind, key, slot in groups:
        rows = source.table(kind, official).get(key, [])
        layout = wf_describe.layout("leader_ability" if kind == "leader" else "ability")
        blocks, fields = layout["blocks"], wf_describe.enum_map()["block_fields"]
        for index, values in enumerate(rows, 1):
            sid = at(values, 0)
            refs["strings"].update(value for value in values if value in strings)
            if sid:
                refs["strings"].add("desc_override_" + sid)
            for block, start in blocks.items():
                field_kind = "precondition" if block.startswith("precondition") else block
                for offset, field, _label in fields.get(field_kind, []):
                    if field == "unique_condition_id":
                        value = at(values, start + offset)
                        if value and value not in ("0", "(None)"):
                            refs["condition"].add(value)
            instant = blocks["instant_content"]
            program = at(values, instant + 24)
            if at(values, instant) == "629" and program.startswith("battle/"):
                programs[f"{slot}:row{index}:invoke"] = logical_program(program)
            for field in (instant + 35, blocks["during_content"] + 11):
                flip = at(values, field)
                if not flip or flip == "(None)":
                    continue
                refs["power_flip"].add(flip)
                for flip_rows in source.table("power_flip", official).get(flip, []):
                    for level, program in enumerate(flip_rows, 1):
                        if program.startswith("battle/"):
                            programs[f"{slot}:row{index}:PF{level}"] = logical_program(program)
    return refs, programs


def linked_changes(source, before: list[str], after: list[str]) -> list[str]:
    """Find changed bound descriptions, switch routes, statuses and programs."""
    old_refs, old_programs = character_references(source, before, True)
    new_refs, new_programs = character_references(source, after)
    changes = []
    for name in old_refs:
        old, new = source.table(name, True), source.table(name)
        for key in sorted(old_refs[name] | new_refs[name]):
            if old.get(key) != new.get(key):
                changes.append(name + ":" + key)
    for logical in sorted(set(old_programs.values()) | set(new_programs.values())):
        live, base = source.raw(logical), source.raw(logical, True)
        if live != base and source.tree(logical) != source.tree(logical, True):
            changes.append("dsl:" + logical)
    return changes
