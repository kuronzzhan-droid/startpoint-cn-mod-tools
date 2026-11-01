"""Read nested masters and trace each leaf's last semantic change layer."""
from __future__ import annotations

import hashlib
from pathlib import Path
import threading
import weakref
import zipfile

import wf_quest_lib as codec
from wf.view.base149 import member
from wf.view.members import archive_members
from .schema import get_leaf, iter_leaves, parse_rows


def _semantics(text):
    return parse_rows(text)


# Only content-signed histories may outlive a request. A ZIP/store path does not
# establish immutable bytes, even when it belongs to the same view object.
_SHARED_HISTORIES = weakref.WeakKeyDictionary()
_SHARED_LOCK = threading.RLock()


class _Histories(dict):
    def __init__(self):
        super().__init__()
        self.lock = threading.RLock()
        self.build_locks = {}

    def get_or_build(self, logical, key, build):
        with self.lock:
            if key in self:
                return self[key]
            lock = self.build_locks.setdefault(logical, threading.RLock())
        # Serialize the same table; unrelated tables can decode concurrently.
        with lock:
            with self.lock:
                if key in self:
                    return self[key]
            value = build()
            with self.lock:
                self[key] = value
            return value


def _histories_for(view):
    signed = callable(getattr(view, "history_digest", None))
    view = getattr(view, "_read_cache_original", view)
    if not signed or hasattr(view, "changes") or not hasattr(view, "zips"):
        return _Histories()
    key = (tuple(str(path) for path in view.zips), str(getattr(view, "store", "")))
    try:
        with _SHARED_LOCK:
            caches = _SHARED_HISTORIES.setdefault(view, {})
            if key not in caches:
                caches[key] = _Histories()
            return caches[key]
    except TypeError:  # not weak-referenceable: keep a private cache
        return _Histories()


class BossTables:
    def __init__(self, source):
        self.source = source
        self.view = getattr(source, "view", source)
        self.tables, self.raw_cache = {}, {}
        self.histories = _histories_for(self.view)
        self._archive_members = None
        self._parent_tables = None

    def raw_with_origin(self, logical):
        if logical not in self.raw_cache:
            try:
                if hasattr(self.source, "raw_with_origin"):
                    value = self.source.raw_with_origin(logical)
                elif hasattr(self.view, "read_raw"):
                    value = self.view.read_raw(logical)
                else:
                    value = self.source.raw(logical), None
            except (FileNotFoundError, KeyError):
                value = None, None
            self.raw_cache[logical] = value
        return self.raw_cache[logical]

    def raw(self, logical):
        return self.raw_with_origin(logical)[0]

    def table(self, logical):
        if logical not in self.tables:
            raw = self.raw(logical)
            node = {} if raw is None else codec.parse_node(raw)
            if not isinstance(node, dict):
                raise ValueError(f"boss master is not an ordered map: {logical}")
            self.tables[logical] = node
        return self.tables[logical]

    load = table

    def _archives(self):
        if self._archive_members is None:
            self._archive_members = []
            for archive in getattr(self.view, "zips", ()):
                with zipfile.ZipFile(archive) as package:
                    self._archive_members.append((Path(archive), archive_members(package)))
        return self._archive_members

    def _history(self, logical):
        key = (logical, self.view.history_digest(logical)) if hasattr(self.view, "history_digest") else logical
        return self.histories.get_or_build(logical, key, lambda: self._build_history(logical))

    def _build_history(self, logical):
        name = member(logical)
        previous, origins = {}, {}
        baseline_known = False
        if hasattr(self.view, "read_store_member"):
            try:
                raw = self.view.read_store_member(name)
            except FileNotFoundError:
                # A genuinely absent baseline is evidence that later rows are new.
                baseline_known = True
            except (KeyError, ValueError):
                # Locked views may intentionally disallow baseline history reads.
                pass
            else:
                baseline_known = True
                previous = dict(iter_leaves(codec.parse_node(raw)))
                origins = {p: "store131" for p in previous}
        known = baseline_known
        for archive, raw in self._historical_members(logical):
            current = dict(iter_leaves(codec.parse_node(raw)))
            for path, text in current.items():
                if path not in previous or _semantics(previous[path]) != _semantics(text):
                    origins[path] = archive.name if known else None
            origins = {path: origins.get(path) for path in current}
            previous, known = current, True
        return origins

    def _historical_members(self, logical):
        if hasattr(self.view, "history_members"):
            yield from self.view.history_members(logical)
            return
        name = member(logical)
        for archive, names in self._archives():
            if name in names:
                with zipfile.ZipFile(archive) as package:
                    yield archive, package.read(names[name])

    def citation(self, logical, path=None):
        raw, table_layer = self.raw_with_origin(logical)
        result = {"logical": logical, "table_layer": table_layer,
                  "table_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None}
        if hasattr(self.view, "changes") and hasattr(self.view, "source"):
            # A studio overlay is not a new origin for every inherited row.
            if self._parent_tables is None:
                self._parent_tables = BossTables(self.view.source)
            inherited = self._parent_tables.citation(logical, path)
            if logical not in getattr(self.view, "client", {}):
                return inherited
            if path is None:
                return result | {"layer": "boss-draft", "scope": "asset", "local": True}
            before = get_leaf(self._parent_tables.table(logical), path)
            after = get_leaf(self.table(logical), path)
            if before is not None and _semantics(before) == _semantics(after):
                return inherited | {"table_layer": "boss-draft", "table_sha256": result["table_sha256"]}
            return result | {"layer": "boss-draft", "scope": "leaf", "leaf_path": list(path),
                             "local": True, "note": "本地未发布草稿的叶子变更"}
        if path is None:
            return result | {"layer": table_layer, "scope": "asset"}
        leaf_path = tuple(str(p) for p in path)
        layer = self._history(logical).get(leaf_path)
        return result | {"leaf_path": list(leaf_path), "layer": layer,
                         "scope": "leaf" if layer is not None else "table",
                         "note": None if layer is not None else "叶子变更层未核验；table_layer 仅表示整表载入层"}
