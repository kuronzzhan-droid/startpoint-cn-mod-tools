"""Read kind branches from actual ABC code, never decompiled source snapshots.

The packaged readers derive from ${WF_ROOT}/v35-generic-20261018/run1/vendor:
swfabc.py upstream SHA-256 d3a56b7f23d809e14d78b0ac11e55f8bf127fb60f1d9dfd5814502cc691eaad3;
asm.py upstream SHA-256 c033836d0a7aa109b81509c1cb0731be82fc543c76d8d3b43881f9dab7d81e87.
Existing differences are package-local imports; SWF byte loading is added here
to support immutable APK-member snapshots without temporary extraction files.
"""
from __future__ import annotations

import hashlib

import wf_describe
from . import asm, bodies

TABLE_CLASSES = {
    "ability": "AbilityValues",
    "leader_ability": "LeaderAbilityValues",
    "ability_soul": "AbilitySoulValues",
    "equipment_enhancement_ability": "EquipmentEnhancementAbilityValues",
    "ex_ability": "ExAbilityValues",
}
SCALAR_BLOCKS = {"instant_delay", "even_if_owner_dead"}
COMPARISONS = {"ifeq", "ifne", "ifstricteq", "ifstrictne"}


def branch_kinds(code: bytes, strings) -> list[str]:
    """Numeric strings in reachable equality branches of a parseAt method.

    Numeric constants used as constructor arguments are deliberately excluded.
    This proves a parser branch exists; it does not claim runtime acceptance of
    its parameters, its battle implementation, or deployment of the SWF.
    """
    instructions = asm.decode(code)
    reachable, pending = set(), [0]
    while pending:
        index = pending.pop()
        if index in reachable or index >= len(instructions):
            continue
        reachable.add(index)
        instruction = instructions[index]
        if instruction.target is not None:
            pending.append(instruction.target)
        if instruction.cases is not None:
            pending.extend(instruction.cases)
            pending.append(instruction.default)
        if instruction.op not in asm.TERMINALS:
            pending.append(index + 1)
    found = set()
    for index in sorted(reachable):
        instruction = instructions[index]
        if (instruction.name != "pushstring" or index + 1 not in reachable
                or instructions[index + 1].name not in COMPARISONS):
            continue
        value = strings[instruction.args[0]].decode("utf-8")
        if value.isascii() and value.isdecimal():
            found.add(value)
    return sorted(found, key=int)


def inspect_abc(abc) -> dict:
    """Return all five ability tables, their actual parseAt hashes and kinds."""
    labels = bodies.label_map(abc)
    by_name = {}
    for index, label in labels.items():
        by_name.setdefault(label, []).append(index)
    tables = {}
    for table, class_name in TABLE_CLASSES.items():
        blocks = {}
        for block, column in wf_describe.layout(table)["blocks"].items():
            if block in SCALAR_BLOCKS:
                continue
            label = f"{class_name}$/parseAt{column}"
            matches = by_name.get(label, [])
            if len(matches) != 1:
                raise ValueError(f"SWF parser method must be unique: {label} ({len(matches)})")
            index = matches[0]
            code = abc.bodies[index][5]
            blocks[block] = {
                "abc": "boot_ffc6", "label": label, "body_index": index,
                "sha256": hashlib.sha256(code).hexdigest(),
                "kinds": branch_kinds(code, abc.strings),
            }
        tables[table] = blocks
    return tables


def registry_mismatches(tables, registry, available) -> list[dict]:
    """Compare the union of provided capabilities with their actual parsers.

    Two capabilities may supply the same kind in disjoint tables (423/R3).
    Unprovided extensions must not be required of an older client profile.
    """
    from wf.caps.facts import KIND_BLOCKS

    groups = {}
    for cap_id in sorted(available):
        cap = registry.get(cap_id)
        if cap is None:
            continue
        surface = cap["data_surface"]
        for value in surface["kinds"]:
            kind = str(value)
            blocks = surface.get("allowed_blocks", [])
            if kind in KIND_BLOCKS:
                blocks = [block for block in blocks if block == KIND_BLOCKS[kind]]
            for block in blocks:
                group = groups.setdefault((kind, block), {"tables": set(), "capabilities": []})
                group["tables"].update(surface.get("allowed_tables", []))
                group["capabilities"].append(cap_id)
    mismatches = []
    for (kind, block), group in sorted(groups.items()):
        actual = {table for table, blocks in tables.items()
                  if kind in blocks.get(block, {}).get("kinds", [])}
        if group["tables"] != actual:
            mismatches.append({
                "kind": kind, "block": block, "capabilities": group["capabilities"],
                "allowed_tables": sorted(group["tables"]), "actual_tables": sorted(actual),
                "missing_branches": sorted(group["tables"] - actual),
                "unregistered_tables": sorted(actual - group["tables"]),
                "message": f"kind {kind} / {block}: allowed_tables 与真实 SWF 分支不符",
            })
    return mismatches
