"""Compact advisory results and compare structural hits against the draft base."""
from __future__ import annotations

from collections import Counter


def _file(hit):
    return hit.get("location", "").split("#", 1)[0]


def _identity(hit):
    # A moved node is not new. Repeated identical constructs still count by
    # multiplicity; changed arguments count as a new/changed structural hit.
    return hit["rule"], _file(hit), hit.get("fingerprint", hit.get("location"))


def summarize(hits, baseline, *, comparison):
    before = Counter(_identity(hit) for hit in baseline or [])
    unknown = baseline is None or any(h["rule"] == "multiplayer.incomplete" for h in baseline)
    groups, incomplete = {}, []
    for hit in hits:
        if hit["rule"] == "multiplayer.incomplete":
            incomplete.append(hit)
            continue
        key = hit["rule"], _file(hit)
        if key not in groups:
            groups[key] = {**{k: v for k, v in hit.items() if k != "fingerprint"},
                           "location": key[1], "hit_count": 0, "locations": [],
                           "new_hit_count": None if unknown else 0, "new_locations": [],
                           "baseline_comparison": "unavailable" if unknown else comparison,
                           "_sources": [], "_messages": []}
        entry = groups[key]
        entry["hit_count"] += 1
        location = hit.get("location", "")
        if location not in entry["locations"] and len(entry["locations"]) < 5:
            entry["locations"].append(location)
        for internal, value in (("_sources", hit.get("source")), ("_messages", hit["message"])):
            if value and value not in entry[internal]:
                entry[internal].append(value)
        identity = _identity(hit)
        if not unknown:
            if before[identity]:
                before[identity] -= 1
            else:
                entry["new_hit_count"] += 1
                if len(entry["new_locations"]) < 5:
                    entry["new_locations"].append(location)
    results = []
    for entry in groups.values():
        entry["source"] = "；".join(entry.pop("_sources"))
        entry["message"] = "；".join(entry.pop("_messages")) + f"（本文件共 {entry['hit_count']} 处）"
        results.append(entry)
    if comparison == "candidate":
        for hit in baseline or []:
            if hit["rule"] == "multiplayer.incomplete":
                incomplete.append({**hit, "issues": ["草稿基线：" + reason
                                  for reason in hit.get("issues", [hit["message"]])]})
    if incomplete:
        reasons = sorted({reason for hit in incomplete for reason in hit.get("issues", [hit["message"]])})
        results.append({**incomplete[0], "issues": reasons, "issue_count": len(reasons),
                        "message": "联机风险扫描不完整：" + "；".join(reasons[:3])
                        + (f"；另 {len(reasons) - 3} 项，详见原因。" if len(reasons) > 3 else "")})
    return results
