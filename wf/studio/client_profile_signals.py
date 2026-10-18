"""Canonical signal/site values for the editor's shared capability checks."""
from __future__ import annotations

import json

from wf.dsl.references import ABILITY_TABLES

ABILITY_PATHS = {table: logical for logical, table in ABILITY_TABLES.items()}
CONTENT_BLOCKS = {"instant_content", "during_content"}


def signature(value) -> str:
    """Stable cache/dedup key, including structured kind-site context."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def distinct_signals(signals) -> list:
    found, seen = [], set()
    for signal in signals:
        key = signature(signal)
        if key not in seen:
            found.append(signal)
            seen.add(key)
    return found


def kind_site(table, block, kind, *, key="query", row=0) -> dict:
    """A schema-valid use site, distinct from context-free kind directory lookup."""
    if table not in ABILITY_PATHS:
        raise ValueError(f"不支持的能力表：{table}")
    if block not in CONTENT_BLOCKS:
        raise ValueError(f"不支持的效果块：{block}")
    return {"logical_path": ABILITY_PATHS[table], "key": str(key), "row": row,
            "table": table, "block": block, "kind": str(kind)}


def kind_sites(signals) -> list:
    sites = []
    for signal, value in signals:
        if signal == "kind_site":
            site = kind_site(value["table"], value["block"], value["kind"],
                             key=value.get("key", "query"), row=value.get("row", 0))
            site.update(value)
            site["kind"] = str(site["kind"])
            sites.append(site)
    return [value for _, value in distinct_signals(("kind_site", site) for site in sites)]


def candidate_kinds(registry) -> list[str]:
    """Check registered numbers in every block, including official same-number enums.

    The picker already renders the complete official enum. This overlay covers all
    registered extensions and their number collisions without evaluating unrelated
    official options on every request. Candidates carry no capability claims.
    """
    return sorted({str(kind) for cap in registry.values() for kind in cap["data_surface"]["kinds"]},
                  key=int)
