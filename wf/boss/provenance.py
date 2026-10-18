"""Read nested masters and trace each leaf's last semantic change layer."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import wf_quest_lib as codec
from wf.view.base149 import member
from .schema import iter_leaves, parse_rows


def _semantics(text):
    return parse_rows(text)


class BossTables:
    def __init__(self, source):
        self.source = source
        self.view = getattr(source, "view", source)
        self.tables, self.raw_cache, self.histories = {}, {}, {}
        self._archive_members = None

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
                    self._archive_members.append((Path(archive), set(package.namelist())))
        return self._archive_members

    def _history(self, logical):
        if logical in self.histories:
            return self.histories[logical]
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
        for archive, names in self._archives():
            if name not in names:
                continue
            with zipfile.ZipFile(archive) as package:
                current = dict(iter_leaves(codec.parse_node(package.read(name))))
            for path, text in current.items():
                if path not in previous or _semantics(previous[path]) != _semantics(text):
                    origins[path] = archive.name if known else None
            origins = {path: origins.get(path) for path in current}
            previous, known = current, True
        self.histories[logical] = origins
        return origins

    def citation(self, logical, path=None):
        raw, table_layer = self.raw_with_origin(logical)
        result = {"logical": logical, "table_layer": table_layer,
                  "table_sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None}
        if path is None:
            return result | {"layer": table_layer, "scope": "asset"}
        leaf_path = tuple(str(p) for p in path)
        layer = self._history(logical).get(leaf_path)
        return result | {"leaf_path": list(leaf_path), "layer": layer,
                         "scope": "leaf" if layer is not None else "table",
                         "note": None if layer is not None else "叶子变更层未核验；table_layer 仅表示整表载入层"}
