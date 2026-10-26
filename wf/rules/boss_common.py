"""Small read-only adapters for boss rule inputs and candidate views."""
from __future__ import annotations

import csv


EMPTY = (None, "", "(None)")


def cells(value):
    if isinstance(value, dict):
        value = value.get("row", [])
    if isinstance(value, str):
        return next(csv.reader([value]), [])
    return list(value) if isinstance(value, (list, tuple)) else []


def cell(value, index, default=None):
    row = cells(value)
    return row[index] if index < len(row) else default


def leaves(node, path=()):
    if isinstance(node, dict):
        for key, child in node.items():
            yield from leaves(child, (*path, str(key)))
    elif isinstance(node, (str, list, tuple)):
        yield path, cells(node)


class CandidateView:
    """Accept both prepush View and ManifestView without changing either."""

    def __init__(self, view):
        self.view = getattr(view, "view", view)

    def raw(self, logical):
        try:
            if hasattr(self.view, "raw"):
                return self.view.raw(logical)
            value = self.view.read_raw(logical)
            return value[0] if isinstance(value, tuple) else value
        except FileNotFoundError:
            return None

    def table(self, logical):
        if hasattr(self.view, "table"):
            return self.view.table(logical)
        raw = self.raw(logical)
        if raw is None:
            return None
        import wf_quest_lib
        return wf_quest_lib.parse_node(raw)


def fields(document):
    return document.get("quest", {}).get("fields", {})


def wave_name(entry):
    path = entry.get("path", [])
    return str(entry.get("wave", entry.get("name", path[-1] if path else "0")))
