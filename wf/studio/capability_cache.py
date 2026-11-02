"""Content-bound memo for the legacy requirements endpoint.

The query is independent of the game view: its complete inputs are the marker
arguments, capability specifications, schemas, profile records and method
evidence. Re-read their bytes on every lookup, including absent primary files
whose later appearance supersedes a fallback. Never cache failed computation.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import threading

from wf.caps.query import query_requirements
from wf.paths import REPOSITORY

_LOCK = threading.RLock()
_CACHE: OrderedDict = OrderedDict()
_LIMIT = 64


def input_digest(root=None):
    """Hash live contents, not mtime/size; fixtures may supply an isolated root."""
    root = Path(root or REPOSITORY)
    from wf.apk.local_registry import BUILTIN, REVIEWED, LOCAL
    paths = {root / "client_profiles.json", root / BUILTIN, root / REVIEWED}
    paths.update((root / LOCAL).glob("*/registration.json"))
    paths.update((root / "wf/caps").glob("*.yml"))
    paths.update((root / "schemas").glob("*.json"))
    paths.update((root / "wf/apk/data").glob("*.json"))
    blobs = {}

    def read(path):
        if path not in blobs:
            try:
                blobs[path] = path.read_bytes()
            except FileNotFoundError:
                blobs[path] = None
        return blobs[path]

    # Discover evidence paths from the same bytes included in the digest.
    for path in list(paths):
        raw = read(path)
        if raw is None or not (path.name in {"client_profiles.json", "registration.json"}
                               or path in {root / BUILTIN, root / REVIEWED}):
            continue
        document = json.loads(raw.decode("utf-8-sig"))
        profiles = document.get("profiles", {}) if path.name == "client_profiles.json" else {
            "registration": document.get("profile", {})}
        for record in profiles.values():
            for key in ("provides", "provides_fallback"):
                name = record.get(key)
                if name:
                    candidate = Path(name)
                    paths.add(candidate if candidate.is_absolute() else root / candidate)
    digest = hashlib.sha256()
    for path in sorted(paths, key=str):
        raw = read(path)
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0missing\0" if raw is None else b"\0" + hashlib.sha256(raw).digest())
    return digest.hexdigest()


def cached_requirements(**arguments):
    """Preserve the complete query JSON and every compatibility check."""
    arguments_key = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with _LOCK:
        for _ in range(3):
            before = input_digest()
            key = before, arguments_key
            if key in _CACHE:
                _CACHE.move_to_end(key)
                return deepcopy(_CACHE[key])
            result = query_requirements(**arguments)
            if input_digest() != before:
                continue
            _CACHE[key] = deepcopy(result)
            while len(_CACHE) > _LIMIT:
                _CACHE.popitem(last=False)
            return result
    raise ValueError("客户端能力输入在读取期间持续变化，请稍后重试")


def capability_input_digest(root=None):
    """Complete inputs for kind/SWF checks, unlike the catalog-only query."""
    from .capability_artifacts import artifact_digest
    root = Path(root or REPOSITORY)
    return input_digest(root), artifact_digest(root)
