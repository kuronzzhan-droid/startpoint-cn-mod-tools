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
from wf.tools.rogue.rogue_candidate import configure_builder_event, isolated_builder
from wf.tools.rogue.rogue_validate import validate_candidate_references

CLONE_TABLES = {b.GENERAL_ZAKO, b.ZAKO_LEVEL, b.GENERAL_BOSS, b.BOSS_LEVEL,
                b.GENERAL_BOSS_VARIABLE, b.OROCHI, b.FIELD_DATA_T, b.ZONE_T}
REBUILT_PREFIXES = ("mod_rogue_f", "mod_rogue_z", "mod_rogue_caster",
                    "mod_rogue_boss", "mod_rogue_orochi")


def rename_graph(value, names):
    if isinstance(value, dict):
        return {names.get(key, key): rename_graph(node, names) for key, node in value.items()}
    if isinstance(value, bytes):
        return rename_graph(value.decode("utf-8"), names).encode("utf-8")
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


def rename_candidate(logical, node, names):
    """Rewrite numeric phase IDs only in their declared reference columns."""
    text_names = {key: value for key, value in names.items() if not str(key).isdigit()}
    rewritten = rename_graph(node, text_names)
    columns = {int(column) for spec in getattr(b, "SPHERE_SPECS", {}).values()
               if logical == spec["logical"] for group in spec.get("aux_groups", ())
               for column in group.get("id_columns", ())}
    if not columns:
        return rewritten
    def phase_refs(value):
        if isinstance(value, dict):
            return {key: phase_refs(child) for key, child in value.items()}
        row = b.cells(value)
        changed = False
        for column in columns:
            if column < len(row) and row[column] in names and row[column].isdigit():
                row[column], changed = names[row[column]], True
        return b.join(row, isinstance(value, bytes)) if changed else value
    return phase_refs(rewritten)


def retain_and_namespace(loader, candidate):
    from .mode_rogue import event_identity
    event_id = event_identity(candidate.get("eventId", "700099"))
    files = candidate["files"]
    tables = {logical: q.parse_node(raw) for logical, raw in files.items() if logical.endswith(".orderedmap")}
    stamp = hashlib.sha256(json.dumps({logical: hashlib.sha256(raw).hexdigest()
        for logical, raw in sorted(files.items())}, sort_keys=True).encode()).hexdigest()[:12]
    rebuilt = candidate.get("rebuiltKeys")
    if rebuilt is None:
        # Compatibility for pre-port candidates and the historical adapter API.
        rebuilt = {logical: [key for key in tree if key.startswith(REBUILT_PREFIXES)
                              and "_studio_" not in key]
                   for logical, tree in tables.items() if logical in CLONE_TABLES}
    names = {}
    for logical, keys in rebuilt.items():
        if logical == b.ENEMY_WATCH:
            continue  # The outer keys are watch buckets, not enemy identifiers.
        for key in keys:
            if key not in tables.get(logical, {}):
                raise ValueError("本轮克隆键未出现在候选表：" + str(key))
            # Dedicated phase tables use AS3-int IDs. Keep their references numeric.
            renamed = (str(1_000_000_000 + int(hashlib.sha256(
                f"{stamp}:{key}".encode()).hexdigest()[:12], 16) % 1_100_000_000)
                if str(key).isdigit() else f"{key}_studio_{stamp}")
            names[key] = renamed
    if len(set(names.values())) != len(names):
        raise ValueError("本轮克隆命名空间发生碰撞")
    # Standard ESDL is round-addressed in the CLI. Keep earlier generations alive
    # by giving each new resource a content-bound address and rewriting its row pointer.
    resources = {logical: logical.removesuffix(".esdl.amf3.deflate") + f"_studio_{stamp}.esdl.amf3.deflate"
                 for logical in files if logical.endswith(".esdl.amf3.deflate")
                 and logical.startswith(("battle/enemy/boss/mod_rogue/", "battle/enemy/boss/mod_abyss_ex/"))}
    names.update({logical.removesuffix(".esdl.amf3.deflate"):
                  renamed.removesuffix(".esdl.amf3.deflate") for logical, renamed in resources.items()})
    # A seed/content-addressed name may already exist after replay. It must have
    # identical semantics, never silently repurpose an existing generation.
    output = dict(files)
    for logical, renamed in resources.items():
        try:
            existing = loader(renamed)
        except FileNotFoundError:
            existing = None
        if existing is not None and existing != files[logical]:
            raise ValueError("模式克隆资源已占用且内容不同：" + renamed)
        output.pop(logical)
        output[renamed] = files[logical]
    final_tables = {}
    for logical, tree in tables.items():
        raw = loader(logical)
        before = q.parse_node(raw)
        if logical == b.ENEMY_WATCH:
            # Old hosts retain their own graph, even if they refer to a rebuilt code.
            after = {bucket: {names.get(key, key): rename_candidate(logical, node, names) if key in names
                              else before.get(bucket, {}).get(key, node)
                              for key, node in hosts.items()} for bucket, hosts in tree.items()}
        elif logical in CLONE_TABLES or logical in rebuilt:
            after = {names.get(key, key): rename_candidate(logical, node, names) if key in names
                     else before.get(key, node) for key, node in tree.items()}
        elif logical == b.Q_QUEST:
            after = {**before, event_id: rename_candidate(logical, tree[event_id], names)}
        else:
            after = rename_candidate(logical, tree, names)
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
    rows = {key: b.cells(value) for key, value in final_tables[b.Q_QUEST][event_id].items()}
    with isolated_builder(lambda logical: output[logical] if logical in output else loader(logical)) as builder:
        configure_builder_event(builder, event_id)
        checks = validate_candidate_references(rows, final_tables, builder)
    return {**candidate, "eventId": event_id, "files": output, "rows": rows, "checks": checks,
            "cloneNamespace": stamp, "retainedPreviousKeys": True}
