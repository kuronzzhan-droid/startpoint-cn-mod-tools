"""Bounded BOSS read memo with live, content-checked dependencies.

Every cache hit rereads consumed resources (including missing resources) and
compares their SHA-256 and origin. Candidate checks are cached as a whole;
neither gates nor advisory scans are replaced with a fabricated success.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

from wf.paths import REPOSITORY


def _digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _file(path):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def _files(paths):
    return tuple((str(path), _digest(_file(path))) for path in sorted(set(paths), key=str))


def _specifications(weapon_evidence=False):
    from .capability_cache import capability_input_digest, input_digest
    digest = capability_input_digest if weapon_evidence else input_digest
    return digest(REPOSITORY), _files((REPOSITORY / "wf/rules").glob("*.json"))


def _draft_inputs(paths):
    def uses_weapon(value):
        if isinstance(value, dict):
            return value.get("operation") == "weapon_clone" or any(uses_weapon(v) for v in value.values())
        return isinstance(value, list) and any(uses_weapon(v) for v in value)

    records, weapon_evidence = [], False
    for path in sorted(set(paths), key=str):
        raw = _file(path)
        records.append((str(path), _digest(raw)))
        if raw is not None:
            try:
                weapon_evidence |= uses_weapon(json.loads(raw))
            except (ValueError, UnicodeError):
                weapon_evidence = True  # Malformed drafts must never reuse weaker evidence.
    return tuple(records), weapon_evidence


class _Trace:
    def __init__(self, source):
        self.original = source
        self.base = getattr(source, "view", source)
        self.values, self.dependencies, self.files = {}, {}, {}
        self.unavailable = {}
        self.history_keys = {}
        from .history_cache import HistoryInputs
        self.history = HistoryInputs(self.base)

    def read(self, kind, name):
        key = kind, name
        if key in self.unavailable:
            raise KeyError(*self.unavailable[key])
        if key in self.values:
            return self.values[key]
        try:
            if kind == "read_raw" and not hasattr(self.base, kind):
                if hasattr(self.original, "raw_with_origin"):
                    value = self.original.raw_with_origin(name)
                else:
                    value = self.original.raw(name), None
            else:
                value = getattr(self.base, kind)(name)
        except (FileNotFoundError, KeyError) as exc:
            if kind == "read_store_member" and isinstance(exc, KeyError):
                self.dependencies[key] = None, "unavailable"
                self.unavailable[key] = exc.args
                raise
            value = None if kind == "read_store_member" else (None, None)
        raw, origin = (value, None) if kind == "read_store_member" else value
        self.dependencies[key] = _digest(raw), origin
        self.values[key] = value
        return value

    def current(self):
        self.history.close()
        fresh = _Trace(self.original)
        for key, expected in self.dependencies.items():
            try:
                fresh.read(*key)
            except KeyError:
                pass  # A refused baseline is distinct from a missing baseline.
            if fresh.dependencies[key] != expected:
                return False
        return (all(_digest(_file(path)) == digest for path, digest in self.files.items())
                and self.history.current())


class _View:
    def __init__(self, trace):
        self.trace = trace
        self._read_cache_original = trace.base

    def __getattr__(self, name):
        return getattr(self.trace.base, name)

    def read_raw(self, logical):
        raw, origin = self.trace.read("read_raw", logical)
        if raw is None:
            raise FileNotFoundError(logical)
        return raw, origin

    def read_member(self, name):
        raw, origin = self.trace.read("read_member", name)
        if raw is None:
            raise FileNotFoundError(name)
        return raw, origin

    def read_store_member(self, name):
        if not hasattr(self.trace.base, "read_store_member"):
            raise KeyError(name)  # Baseline history unavailable, not proven absent.
        raw = self.trace.read("read_store_member", name)
        if raw is None:
            raise FileNotFoundError(name)
        return raw

    def history_digest(self, logical):
        from wf.view.base149 import member
        if logical in self.trace.history_keys:
            return self.trace.history_keys[logical]
        baseline = None
        if hasattr(self.trace.base, "read_store_member"):
            try:
                name = member(logical)
                self.trace.read("read_store_member", name)
                baseline = self.trace.dependencies[("read_store_member", name)][0]
            except KeyError as exc:
                baseline = "unavailable", str(exc)
            except ValueError as exc:
                # Locked views can intentionally withhold baseline history.
                if "unlocked" not in str(exc):
                    raise
                baseline = str(exc)
        result = baseline, self.trace.history.digest(logical)
        self.trace.history_keys[logical] = result
        return result

    def history_members(self, logical):
        return self.trace.history.members(logical)

    def raw(self, logical):
        return self.trace.read("read_raw", logical)[0]

    def load(self, logical):
        import wf_quest_lib
        raw = self.raw(logical)
        return wf_quest_lib.parse_node(raw) if raw is not None else {}

    table = load


class _Source:
    def __init__(self, trace):
        self.trace, self.view = trace, _View(trace)

    def __getattr__(self, name):
        return getattr(self.trace.original, name)

    def raw_with_origin(self, logical):
        return self.trace.read("read_raw", logical)

    def raw(self, logical):
        return self.raw_with_origin(logical)[0]

    def note_server(self, state):
        for target, raw in state.server_original.items():
            self.trace.files[Path(state.server_dir) / target] = _digest(raw)


class BossReadMemo:
    def __init__(self, source, store, *, limit=32):
        self.source, self.store, self.limit = source, store, limit
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        from .cache_locks import KeyedLocks
        from .read_manifest import ReadManifestInputs
        self.flights = KeyedLocks()
        view = getattr(source, "view", source)
        self.manifest = ReadManifestInputs(view)

    def get(self, key, compute):
        with self.flights.hold(key):
            for _ in range(3):
                signature = self._signature()
                with self.lock:
                    cached = self.cache.get(key)
                if cached is not None and cached[0] == signature and cached[1].current():
                    if signature != self._signature():
                        continue
                    with self.lock:
                        if key in self.cache:
                            self.cache.move_to_end(key)
                    return deepcopy(cached[2])
                trace = _Trace(self.source)
                try:
                    value = compute(_Source(trace))
                    if signature != self._signature() or not trace.current():
                        continue
                finally:
                    trace.history.close()
                saved = deepcopy(value)
                with self.lock:
                    self.cache[key] = signature, trace, saved
                    while len(self.cache) > self.limit:
                        self.cache.popitem(last=False)
                return value
            raise ValueError("副本输入在读取期间持续变化，请稍后重试")

    def _signature(self):
        # Other drafts reserve IDs and therefore are also dependencies.
        roots = (self.store.root, self.store.root.parent / "weapons")
        drafts = [path for root in roots for path in root.glob("*/changeset.json")]
        # Inspect parsed operations, including JSON escapes, from the same bytes
        # hashed for draft invalidation. Weapon clones inspect actual SWF kinds.
        draft_inputs, weapon_evidence = _draft_inputs(drafts)
        view = getattr(self.source, "view", self.source)
        return (self.source.version, self.manifest.current(), draft_inputs, _specifications(weapon_evidence),
                json.dumps(getattr(view, "zip_records", []), sort_keys=True))
