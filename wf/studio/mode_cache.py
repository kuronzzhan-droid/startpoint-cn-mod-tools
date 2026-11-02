"""Content-bound mode previews; hits revalidate the chain, ZIP stats and hashed inputs."""
from __future__ import annotations

import copy
from collections import OrderedDict
import hashlib
import json
import threading


class ModeReadCache:
    def __init__(self):
        from .cache_locks import KeyedLocks
        self._flights = KeyedLocks()
        self._lock = threading.RLock()
        self._entries = OrderedDict()

    def get(self, mode, source, context, build):
        # Include the entire draft/spec, never only a revision counter or mtime.
        context_hash = hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False,
                                                allow_nan=False).encode()).hexdigest()
        key = (source.version, context_hash)
        cache_key = mode, id(source), key
        with self._flights.hold(cache_key):
            with self._lock:
                entry = self._entries.get(cache_key)
            if entry is not None and entry[0] == key and entry[2].source is source:
                try:
                    getattr(entry[2], "verify_read", entry[2].verify)()
                except (ValueError, OSError, KeyError, TypeError, RuntimeError):
                    with self._lock:
                        if self._entries.get(cache_key) is entry:
                            self._entries.pop(cache_key)
                    # Rebuild through the original error/blocked-response path.
                else:
                    with self._lock:
                        if cache_key in self._entries:
                            self._entries.move_to_end(cache_key)
                    return copy.deepcopy(entry[1])
            value, inputs = build()
            # The dependency hashes and their negative lookups are recorded by
            # ViewInputs; verify_read() compares all of them before every reuse.
            saved = copy.deepcopy(value)
            with self._lock:
                self._entries[cache_key] = (key, saved, inputs)
                self._entries.move_to_end(cache_key)
                while len(self._entries) > 8:
                    self._entries.popitem(last=False)
            return value
