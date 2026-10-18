"""Infer content dependencies from changed leaves and their actual references."""
from __future__ import annotations

import hashlib
import json
import re
import zlib

import wf_mod_tool as codec
import wf_quest_lib as nodes
from wf_dsl import parse_dsl
from wf.dsl.references import DSL_SUFFIX, program_logical

from .facts import dsl_signals, leaves, table_signals


def parse_table(raw, logical):
    indexed = codec.read_orderedmap_raw_rows_from_bytes(raw, logical)
    value = nodes.parse_node(raw) if indexed.keys else {}
    if not isinstance(value, dict):
        raise ValueError(f"{logical}: expected an orderedmap")
    return value


def infer_requirements(members, *, declared=(), read_raw=None, server=None, registry=None):
    """Scan candidate payloads, using baseline only for diffs/referenced leaves.

    Missing referenced inputs remain explicit unresolved evidence. A supplied
    baseline that is corrupt is an error; it must never become an empty table.
    """
    if registry is None:
        from .registry import load_registry
        registry = load_registry()
    unknown = set(declared) - registry.keys()
    if unknown:
        raise ValueError(f"unknown declared capability IDs: {sorted(unknown)}")
    candidate = {}
    scanned = []
    for raw, entry in members.values():
        logical, root = entry["logical_path"], entry.get("root", "common")
        scanned.append({"logical_path": logical, "root": root, "sha256": hashlib.sha256(raw).hexdigest()})
        if root != "common" and (logical.endswith(".orderedmap") or logical.endswith(DSL_SUFFIX)):
            raise ValueError(f"capability table/DSL must use common root: {logical}")
        if root == "common":
            candidate[logical] = raw
    hits, unresolved, notes = {}, [], []
    changed = {}
    visited, tables = set(), {}

    def add(cap_id, context, signal, value):
        evidence = {**context, "signal": signal, "value": value}
        if evidence not in hits.setdefault(cap_id, []):
            hits[cap_id].append(evidence)

    def baseline(logical):
        if read_raw is None:
            raise FileNotFoundError(logical)
        data = read_raw(logical)
        return data[0] if isinstance(data, tuple) else data

    def read(logical):
        return candidate[logical] if logical in candidate else baseline(logical)

    def table(logical):
        if logical not in tables:
            tables[logical] = parse_table(read(logical), logical)
        return tables[logical]

    def missing(logical, key, context):
        entry = {"logical_path": logical, "key": key, "referenced_by": context}
        if entry not in unresolved:
            unresolved.append(entry)

    def signals(values, context):
        for kind, value in values:
            if kind == "unsupported":
                entry = {"logical_path": context["logical_path"], "key": context.get("key"),
                         "referenced_by": {**context, "reason": value}}
                if entry not in unresolved:
                    unresolved.append(entry)
                continue
            if kind in {"ref", "optional_ref"}:
                logical, key = value
                if key in {"", "(None)"}:
                    continue
                identity = (logical, key)
                if identity in visited:
                    continue
                visited.add(identity)
                try:
                    child = table(logical)[key]
                except (KeyError, FileNotFoundError):
                    if kind != "optional_ref":
                        missing(logical, key, context)
                    continue
                for trail, text in leaves(child, (key,)):
                    source = {"logical_path": logical, "key": "/".join(trail), "via": context["logical_path"]}
                    signals(table_signals(logical, trail, text, registry=registry), source)
                continue
            if kind == "program":
                logical = program_logical(value)
                if logical is None and isinstance(value, str) and re.fullmatch(r"battle/[A-Za-z0-9_./-]+", value):
                    logical = value if value.endswith(DSL_SUFFIX) else value + DSL_SUFFIX
                if not logical:
                    missing(str(value), None, context)
                else:
                    scan_dsl(logical, context)
                continue
            for cap_id, cap in registry.items():
                surface = cap["data_surface"]
                match = str(value) in {str(item) for item in surface.get(kind, [])}
                if kind == "unique_string":
                    match = any(str(value).startswith(prefix) for prefix in surface.get("unique_prefixes", []))
                if match:
                    add(cap_id, context, kind, value)

    def scan_dsl(logical, context=None):
        identity = (logical, None)
        if identity in visited:
            return
        visited.add(identity)
        try:
            raw = read(logical)
        except (KeyError, FileNotFoundError):
            missing(logical, None, context or {"logical_path": logical})
            return
        tree = parse_dsl(zlib.decompress(raw, -15))["tree"]
        signals(dsl_signals(tree), {"logical_path": logical, "sha256": hashlib.sha256(raw).hexdigest()})

    for logical, raw in candidate.items():
        changed[logical] = set() if logical.endswith(".orderedmap") else None
        if re.search(r"(?:^|/)(?:matched_)?skill_ready_alt_?[1-5](?:[./]|$)", logical):
            signals([("selectors", "voice.skill_ready_alt")], {"logical_path": logical})
        if logical.endswith(".orderedmap"):
            data = table(logical)
            try:
                old = dict(leaves(parse_table(baseline(logical), logical)))
            except (KeyError, FileNotFoundError):
                old = {}
                notes.append({"logical_path": logical, "reason": "baseline-missing",
                              "detail": "基线缺失；按整张候选表扫描，可能保守地增加能力依赖。"})
            for trail, text in leaves(data):
                if old.get(trail) == text:
                    continue
                changed[logical].add(trail)
                signals(table_signals(logical, trail, text, registry=registry),
                        {"logical_path": logical, "key": "/".join(trail)})
        elif logical.endswith(DSL_SUFFIX):
            scan_dsl(logical)
    from .character_requirements import character_requirements
    affected, incomplete = character_requirements({p: keys for p, keys in changed.items() if keys != set()},
                                                 read=read, table=table, registry=registry)
    unresolved.extend(entry for entry in incomplete if entry not in unresolved)
    for cid, evidence in affected:
        for context in evidence:
            signals([("character_ids", cid)], context)
    for target, raw in (server or {}).items():
        if target.endswith("character_overlimit.json"):
            data = json.loads(raw)
            if data:
                signals([("tables", "character_overlimit")], {"logical_path": target, "side": "server"})
    for cap_id in declared:
        add(cap_id, {"logical_path": "changeset.capabilities"}, "declared", cap_id)
    patches = sorted({number for cap_id in hits for number in registry[cap_id]["provided_by"]["patches"]})
    features = sorted({feature for cap_id in hits for feature in registry[cap_id]["server"].get("features", [])})
    return {"clientCapabilities": sorted(hits), "clientPatches": [f"#{n}" for n in patches],
            "serverFeatures": features, "capabilityResolution": "partial" if unresolved else "resolved",
            "capabilityEvidence": [{"id": cap_id, "evidence": evidence} for cap_id, evidence in sorted(hits.items())],
            "unresolved": unresolved, "scannedMembers": scanned, "inferenceNotes": notes}


def requirements_document(doc, members, archives, *, read_raw=None, server=None, registry=None):
    inferred = infer_requirements(members, declared=doc.get("capabilities", []), read_raw=read_raw,
                                  server=server, registry=registry)
    inferred.update(serverRestart=bool(doc.get("server_changes")),
                    restartReasons=["server data changed"] if doc.get("server_changes") else [],
                    minServerVersion=None)
    return {"schemaVersion": 2, "pack": {"since": doc["from_version"], "tail": doc["to_version"],
            "anchor": {"from": doc["from_version"], "to": doc["to_version"]}, "archives": archives},
            "requires": inferred}
