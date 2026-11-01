"""Export a tower candidate without deleting or repurposing old clone keys.

The legacy CLI may purge old clones in its mutable store. Studio deliveries must
retain shared keys. Rename the new clone graph, then merge it into the exact tip.
Selection, stats and DSL construction remain entirely in rogue_build.
"""
import copy
import hashlib
import json

import wf_quest_lib as q
import wf_share_update_codec as codec
from wf.tools.rogue import rogue_build as b
from wf.tools.rogue.rogue_candidate import isolated_builder
from wf.tools.rogue.rogue_validate import validate_candidate_references

CLONE_TABLES = {b.GENERAL_ZAKO, b.ZAKO_LEVEL, b.GENERAL_BOSS, b.BOSS_LEVEL,
                b.GENERAL_BOSS_VARIABLE, b.OROCHI, b.FIELD_DATA_T, b.ZONE_T}
REBUILT_PREFIXES = ("mod_rogue_f", "mod_rogue_z", "mod_rogue_caster",
                    "mod_rogue_boss", "mod_rogue_orochi")


def rename_graph(value, names):
    if isinstance(value, dict):
        return {names.get(key, key): rename_graph(node, names) for key, node in value.items()}
    if isinstance(value, str):
        # Clone identifiers occur in CSV cells, including lists of named enemies.
        # Use the existing CSV codec; do not substring-replace unrelated names.
        import csv
        import io
        rows = list(csv.reader(io.StringIO(value)))
        changed = [[",".join(names.get(token, token) for token in cell.split(","))
                    for cell in row] for row in rows]
        if rows == changed:
            return value
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="\n").writerows(changed)
        return buffer.getvalue() if value.endswith("\n") else buffer.getvalue().rstrip("\n")
    return value


def merge_retained(before, after, reserved=()):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return copy.deepcopy(after)
    merged = copy.deepcopy(before)
    for key, value in after.items():
        if key in before and key in reserved and before[key] != value:
            raise ValueError("模式克隆键已占用且内容不同：" + key)
        merged[key] = merge_retained(before[key], value, reserved) if key in before else copy.deepcopy(value)
    return merged


def retain_and_namespace(loader, candidate):
    files = candidate["files"]
    tables = {logical: q.parse_node(raw) for logical, raw in files.items() if logical.endswith(".orderedmap")}
    stamp = hashlib.sha256(json.dumps({logical: hashlib.sha256(raw).hexdigest()
        for logical, raw in sorted(files.items())}, sort_keys=True).encode()).hexdigest()[:12]
    names = {key: f"{key}_studio_{stamp}" for logical, tree in tables.items() if logical in CLONE_TABLES
             for key in tree if key.startswith(REBUILT_PREFIXES) and "_studio_" not in key}
    # A seed/content-addressed name may already exist after replay. It must have
    # identical semantics, never silently repurpose an existing generation.
    output = dict(files)
    final_tables = {}
    for logical, tree in tables.items():
        raw = loader(logical)
        before = q.parse_node(raw)
        if logical == b.ENEMY_WATCH:
            # Old hosts retain their own graph, even if they refer to a rebuilt code.
            after = {bucket: {names.get(key, key): rename_graph(node, names) if key in names
                              else before.get(bucket, {}).get(key, node)
                              for key, node in hosts.items()} for bucket, hosts in tree.items()}
        elif logical in CLONE_TABLES:
            after = {names.get(key, key): rename_graph(node, names) if key in names
                     else before.get(key, node) for key, node in tree.items()}
        elif logical == b.Q_QUEST:
            after = {key: rename_graph(node, names) if key == b.EVENT_ID else before.get(key, node)
                     for key, node in tree.items()}
        else:
            after = rename_graph(tree, names)
        merged = merge_retained(before, after, set(names.values()))
        final_tables[logical] = merged
        if merged == before:
            output.pop(logical, None)
            continue
        # Preserve every unchanged top-level chunk byte-for-byte.
        chunks = codec.unpack(raw)
        for key, node in merged.items():
            if key not in before or node != before[key]:
                chunks[key] = q.build_node(node)
        output[logical] = codec.pack(chunks)
    rows = {key: b.cells(value) for key, value in final_tables[b.Q_QUEST][b.EVENT_ID].items()}
    with isolated_builder(loader) as builder:
        checks = validate_candidate_references(rows, final_tables, builder)
    return {**candidate, "files": output, "rows": rows, "checks": checks,
            "cloneNamespace": stamp, "retainedPreviousKeys": True}
