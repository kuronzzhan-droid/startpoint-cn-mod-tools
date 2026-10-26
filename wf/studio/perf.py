"""Process-wide caches for the studio's read paths (view objects are immutable per process).

Everything here is keyed by content (bytes) or by a file signature (path, mtime, size),
so a cache hit can never serve stale data:

* :func:`registry` — the capability registry (141 YAML files), keyed by their signature;
* :func:`parsed` — ``parse_node`` results keyed by the raw orderedmap bytes; callers get a
  structural copy (dicts/lists copied, strings shared) so they may mutate it freely;
* :func:`file_bytes` / :func:`mirror` — server text mirrors keyed by (path, mtime, size);
* :func:`owners` — the character → key ownership index keyed by the character table bytes;
* :func:`leaf_tokens` — reference tokens / row names of one ability leaf (``custom_owners``).

:class:`CachedView` lets :class:`~wf.studio.ability_engine.EditState` read through
:class:`~wf.studio.source.StudioSource`'s raw cache instead of reopening the patch ZIPs.
"""
from __future__ import annotations

import csv
import io
import re
import threading
from collections import OrderedDict
from pathlib import Path

_LOCK = threading.RLock()


class _LRU:
    def __init__(self, size: int):
        self.size = size
        self.data: OrderedDict = OrderedDict()

    def get(self, key):
        with _LOCK:
            if key in self.data:
                self.data.move_to_end(key)
                return self.data[key]
        return None

    def put(self, key, value):
        with _LOCK:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)
        return value

    def clear(self):
        with _LOCK:
            self.data.clear()


def copy_tree(value):
    """Copy containers, share immutable leaves (orderedmap leaves are str)."""
    if isinstance(value, dict):
        return {k: copy_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [copy_tree(v) for v in value]
    return value


# -- capability registry -------------------------------------------------------
_REGISTRY: dict = {}


def registry():
    from wf.caps import registry as module
    root = Path(module.__file__).parent
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(root.glob("*.yml")))
    with _LOCK:
        if _REGISTRY.get("signature") == signature:
            return _REGISTRY["value"]
    value = module.load_registry(root)
    with _LOCK:
        _REGISTRY.update(signature=signature, value=value)
    return value


# -- orderedmap parsing --------------------------------------------------------
_PARSED = _LRU(48)


def parsed(raw: bytes, *, shared: bool = False):
    """``wf_quest_lib.parse_node(raw)``; a structural copy unless ``shared`` (read-only callers)."""
    import wf_quest_lib as codec
    hit = _PARSED.get(raw)
    if hit is None:
        hit = _PARSED.put(raw, codec.parse_node(raw))
    return hit if shared else copy_tree(hit)


# -- files and server mirrors ---------------------------------------------------
_FILES = _LRU(8)
_MIRRORS = _LRU(8)


def file_bytes(path) -> bytes:
    path = Path(path).resolve()
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    hit = _FILES.get(key)
    return hit if hit is not None else _FILES.put(key, path.read_bytes())


def mirror(raw: bytes, *, shared: bool = False) -> dict:
    """Strict parse of a server mirror (``wf.text.json_patch.parse_mirror``), cached by bytes."""
    from wf.text.json_patch import parse_mirror
    hit = _MIRRORS.get(raw)
    if hit is None:
        hit = _MIRRORS.put(raw, parse_mirror(raw))
    return hit if shared else copy_tree(hit)


# -- ownership and reference tokens --------------------------------------------
_OWNERS = _LRU(8)


def owners(view) -> dict:
    """``wf.balance.ownership.owner_index`` memoized on the character table bytes (frozen sets)."""
    from wf.balance.ownership import CHARACTER, owner_index
    raw = view.read_raw(CHARACTER)[0]
    hit = _OWNERS.get(raw)
    if hit is None:
        index = owner_index(view)
        hit = _OWNERS.put(raw, {table: {key: frozenset(value) for key, value in keys.items()}
                                for table, keys in index.items()})
    return {table: dict(keys) for table, keys in hit.items()}


_TOKENS = _LRU(20000)
_WORD = re.compile(r"[A-Za-z0-9_]+")


def leaf_tokens(leaf: str) -> tuple[frozenset, frozenset]:
    """(reference tokens, row c0 names) of one ability / leader leaf, as ``custom_keys`` reads them.

    Tokens = every CSV cell plus every ``[A-Za-z0-9_]+`` run inside a cell; the run class holds
    no separator or quote, so scanning the whole leaf once yields the same runs.
    """
    hit = _TOKENS.get(leaf)
    if hit is not None:
        return hit
    tokens, names = set(), set()
    if isinstance(leaf, str) and leaf:
        for record in csv.reader(io.StringIO(leaf, newline="")):
            tokens.update(record)
            if record:
                names.add(record[0])
        tokens.update(_WORD.findall(leaf))
    return _TOKENS.put(leaf, (frozenset(tokens), frozenset(names)))


# -- a view that reads through StudioSource's raw cache --------------------------
class CachedView:
    """``read_raw`` via ``StudioSource.raw_with_origin`` (cached), raising like a view when absent."""

    def __init__(self, source):
        self.source = source
        self.view = getattr(source, "view", None)

    def read_raw(self, logical):
        raw, origin = self.source.raw_with_origin(logical)
        if raw is None:
            raise FileNotFoundError(logical)
        return raw, origin

    def __getattr__(self, name):  # read_member, verify, ... of the underlying view
        if self.view is None:
            raise AttributeError(name)
        return getattr(self.view, name)


def view_for(source):
    if hasattr(source, "raw_with_origin"):
        return CachedView(source)
    return getattr(source, "view", source)
