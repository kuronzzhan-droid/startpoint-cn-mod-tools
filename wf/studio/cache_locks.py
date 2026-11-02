"""Single-flight locks scoped to a live cache key, without retaining idle keys."""
from contextlib import contextmanager
import threading


class KeyedLocks:
    def __init__(self):
        self._guard = threading.Lock()
        self._entries = {}

    @contextmanager
    def hold(self, key):
        with self._guard:
            entry = self._entries.setdefault(key, [threading.RLock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._guard:
                entry[1] -= 1
                if not entry[1]:
                    del self._entries[key]
