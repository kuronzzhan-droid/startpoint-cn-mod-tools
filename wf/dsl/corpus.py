"""Reproducible positive-control census of official kind-629 action trees."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zlib

import wf_quest_lib as nodes
from wf_dsl import parse_dsl
from wf_enhancement_policy import OfficialBaseline
from wf.view.safety import local_output

from .references import (ABILITY_TABLES, ACTION_SKILL, ability_references,
                         linked_programs, resolve_programs)
from .sanitize import forbidden_629


def census_official_629(cdn_root):
    """Read official archives only, using pinned table SHA checks; no cache writes."""
    baseline = OfficialBaseline(Path(cdn_root), write_cache=False)
    sources = {}

    def read(logical):
        raw = baseline.get("common", nodes.hashed_rel(logical))
        if raw is None:
            raise FileNotFoundError(f"official corpus member missing: {logical}")
        entry = baseline._index["common"][nodes.hashed_rel(logical)]
        sources[logical] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                            "archive": entry.archive.name, "member": entry.member}
        return raw

    refs = []
    for logical in ABILITY_TABLES:
        refs.extend(ability_references(logical, nodes.parse_node(read(logical))))
    skills = nodes.parse_node(read(ACTION_SKILL)) if any(r["action"] in {"", "(None)"} for r in refs) else {}
    pending = set().union(*(resolve_programs(ref, skills) for ref in refs)) if refs else set()
    trees, counts, findings = {}, Counter(), []

    def count(node):
        if isinstance(node, list):
            if node and isinstance(node[0], str):
                counts[node[0]] += 1
            for child in node:
                count(child)
        elif isinstance(node, dict):
            for child in node.values():
                count(child)

    while pending:
        logical = min(pending)
        pending.remove(logical)
        if logical in trees:
            continue
        tree = parse_dsl(zlib.decompress(read(logical), -15))["tree"]
        children = linked_programs(tree)
        trees[logical] = {"called_programs": sorted(children)}
        pending.update(children - trees.keys())
        count(tree)
        findings.extend({"logical_path": logical, **f} for f in forbidden_629(tree))
    watched = ("RemoveEvent", "SetPowerFilpSuppress", "NotifyPowerflipEnd", "Wait")
    return {"schema": "wf-official-629-corpus/1", "official_tail": baseline.official_tail,
            "pinned_baselines_verified": baseline._verified,
            "ability_table_count": len(ABILITY_TABLES), "reference_count": len(refs),
            "tree_count": len(trees), "references": refs, "trees": trees,
            "lifecycle_counts": {name: counts[name] for name in watched},
            "notify_only_wait_count": sum(f["command"].startswith("Wait(") for f in findings),
            "findings": findings, "sources": dict(sorted(sources.items())),
            "scope": "CN official archives through 1.4.54; excludes mod tags and later increments"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="只读官方 629 正向对照统计")
    parser.add_argument("--cdn", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = local_output(args.output)
    report = census_official_629(args.cdn)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: report[k] for k in ("reference_count", "tree_count", "lifecycle_counts")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
