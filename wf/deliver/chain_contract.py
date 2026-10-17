"""Offline chain invariants; no dependency on loading a server module."""
from collections import defaultdict

from .prepush_base import archive_key, vkey


def chain_errors(names, target):
    edges = defaultdict(list)
    errors = []
    for name in names:
        key = archive_key(name)
        if key is None:
            errors.append(f"invalid archive name: {name}")
            continue
        frm, to, seq = key
        if frm >= to:
            errors.append(f"non-forward edge: {name}")
        edges[(frm, to)].append(seq)
    successors = defaultdict(set)
    incoming = defaultdict(set)
    for (frm, to), sequences in edges.items():
        if sorted(sequences) != list(range(1, len(sequences) + 1)):
            errors.append(f"duplicate or missing seq: {frm}->{to}: {sorted(sequences)}")
        successors[frm].add(to)
        incoming[to].add(frm)
    if any(len(values) != 1 for values in successors.values()):
        errors.append("chain has divergent edges")
    if any(len(values) != 1 for values in incoming.values()):
        errors.append("chain has convergent edges")
    if edges:
        starts = set(successors) - set(incoming)
        ends = set(incoming) - set(successors)
        if len(starts) != 1 or ends != {vkey(target)}:
            errors.append("chain is disconnected or target version is not the unique tail")
    return errors
