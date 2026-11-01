"""Assertion-first boss table overlays; inputs are never mutated or written."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import wf_quest_lib as codec
from wf.text.edit import _encode
from wf.deliver.json_merge import _json_spans


def digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def leaf(tree, path, default=None):
    node = tree
    for key in path:
        if not isinstance(node, dict) or str(key) not in node:
            return default
        node = node[str(key)]
    return node


def put(tree, path, value):
    node = tree
    for key in path[:-1]:
        node = node.setdefault(str(key), {})
        if not isinstance(node, dict):
            raise ValueError("table path traverses a leaf")
    node[str(path[-1])] = value


def merge_keys(raw, updates):
    """Replace/add selected top-level server keys, preserving all other bytes."""
    text, before, spans = _json_spans(raw)
    for key in sorted(set(updates) & set(before), key=lambda k: spans[k][0], reverse=True):
        if before[key] != updates[key]:
            start, end = spans[key]
            text = text[:start] + json.dumps(updates[key], ensure_ascii=False, allow_nan=False) + text[end:]
    additions = {k: v for k, v in updates.items() if k not in before}
    if additions:
        end = text.rfind("}")
        entries = json.dumps(additions, ensure_ascii=False, allow_nan=False)[1:-1]
        text = text[:end].rstrip() + ("," if before else "") + "\n" + entries + "\n" + text[end:]
    after = text.encode("utf-8")
    final, document, final_spans = _json_spans(after)
    original = raw.decode("utf-8")
    assert all(original[a:b] == final[slice(*final_spans[k])]
               for k, (a, b) in spans.items() if k not in updates)
    assert all(document[k] == v for k, v in updates.items())
    return after


class BossEditState:
    def __init__(self, source, *, server_dir=None):
        self.source = source
        self.base = getattr(source, "view", source)
        self.version = getattr(source, "version", getattr(self.base, "tip", None))
        self.tip = getattr(self.base, "tip", self.version)
        self.server_dir = Path(server_dir) if server_dir is not None else None
        self.original, self.client, self.trees = {}, {}, {}
        self.servers, self.server_original = {}, {}
        self.changes = []
        self.zips = []  # Overlay provenance is deliberately local, not a historical ZIP.

    def read_raw(self, logical):
        if logical in self.client:
            return self.client[logical], "boss-draft"
        if logical not in self.original:
            self.original[logical] = self.base.read_raw(logical)[0]
        if self.original[logical] is None:
            raise FileNotFoundError(logical)
        return self.original[logical], "boss-draft"

    def raw(self, logical):
        try:
            return self.read_raw(logical)[0]
        except (FileNotFoundError, KeyError):
            return None

    def table(self, logical):
        if logical not in self.trees:
            raw = self.raw(logical)
            self.trees[logical] = codec.parse_node(raw) if raw is not None else {}
        return copy.deepcopy(self.trees[logical])

    load = table

    def set_raw(self, logical, raw, *, new=False):
        """Replace a logical resource in memory, recording absent targets too."""
        from pathlib import PurePosixPath
        path = PurePosixPath(logical)
        if not logical or "\\" in logical or ":" in logical or path.is_absolute() or ".." in path.parts:
            raise ValueError("resource must have a relative logical path")
        if not isinstance(raw, bytes):
            raise ValueError("resource content must be bytes")
        before = self.raw(logical)
        if new and before is not None:
            raise ValueError(f"resource collision: {logical}")
        self.original.setdefault(logical, before)
        if before == raw:
            return
        self.client[logical] = raw
        self.trees.pop(logical, None)
        self.changes.append({"table": logical, "path": [], "resource": True,
                             "old": digest(before), "new": digest(raw)})

    def set_leaf(self, logical, path, value, *, new=False):
        table = self.table(logical)
        before = leaf(table, path)
        if new and before is not None:
            raise ValueError(f"ID collision: {logical}/{'/'.join(path)}")
        if not new and before is None:
            raise ValueError(f"missing edit target: {logical}/{'/'.join(path)}")
        if before == value:
            return
        put(table, path, value)
        raw = self.raw(logical)
        encoded = _encode(raw, codec.parse_node(raw), table) if raw is not None else codec.build_node(table)
        if codec.parse_node(encoded) != table:
            raise ValueError(f"boss table roundtrip mismatch: {logical}")
        self.client[logical], self.trees[logical] = encoded, table
        self.changes.append({"table": logical, "path": list(path), "old": before, "new": value})

    def delete_leaf(self, logical, path):
        table = self.table(logical)
        before = leaf(table, path)
        if not path or before is None:
            raise ValueError(f"missing delete target: {logical}/{'/'.join(path)}")
        parent = leaf(table, path[:-1]) if len(path) > 1 else table
        del parent[str(path[-1])]
        raw = self.raw(logical)
        encoded = _encode(raw, codec.parse_node(raw), table)
        if codec.parse_node(encoded) != table:
            raise ValueError(f"boss table roundtrip mismatch: {logical}")
        self.client[logical], self.trees[logical] = encoded, table
        self.changes.append({"table": logical, "path": list(path), "old": before, "new": None})

    def server(self, target, *, required=True):
        if target not in self.server_original:
            if self.server_dir is None:
                raise ValueError("boss edits require an explicit read-only server_dir")
            root = self.server_dir.resolve()
            filename = (root / target).resolve()
            if not filename.is_relative_to(root):
                raise ValueError("server target escapes input root")
            if not filename.is_file():
                if required:
                    raise ValueError(f"missing server input: {target}")
                raw = None
            else:
                raw = filename.read_bytes()
            self.server_original[target] = raw
        raw = self.servers.get(target, self.server_original[target])
        return json.loads(raw) if raw is not None else {}

    def set_server_keys(self, target, updates, *, new=False, required=True):
        current = self.server(target, required=required)
        if new and set(updates) & set(current):
            raise ValueError(f"server ID collision: {target}: {sorted(set(updates) & set(current))}")
        raw = self.servers.get(target, self.server_original[target])
        self.servers[target] = merge_keys(raw if raw is not None else b"{}\n", updates)

    def delete_server_keys(self, target, keys):
        from .edit_bytes import delete_keys
        self.server(target)
        raw = self.servers.get(target, self.server_original[target])
        self.servers[target] = delete_keys(raw, keys)

    def append_server_values(self, target, values):
        from .edit_bytes import append_values
        self.server(target)
        raw = self.servers.get(target, self.server_original[target])
        self.servers[target] = append_values(raw, values)

    def snapshot(self):
        return {"client": {k: digest(v) for k, v in sorted(self.original.items())},
                "server": {k: digest(v) for k, v in sorted(self.server_original.items())}}

    def verify_snapshot(self, expected):
        actual = self.snapshot()
        # Earlier D3 drafts enrolled advisory-only behavior reads. Keep those
        # saved locks effective when opening them, without polluting new input
        # snapshots or requiring the scanner to repeat the old reads.
        expected_client = expected.get("client", {})
        if (actual["server"] != expected.get("server")
                or any(key not in expected_client or expected_client[key] != value
                       for key, value in actual["client"].items())):
            raise ValueError("boss draft input SHA-256 drift; rebuild the draft against this view")
        for logical in expected_client.keys() - actual["client"].keys():
            try:
                raw = self.base.read_raw(logical)[0]
            except (FileNotFoundError, KeyError):
                raw = None
            if digest(raw) != expected_client[logical]:
                raise ValueError("boss draft input SHA-256 drift; rebuild the draft against this view")
