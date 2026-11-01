"""Refresh capability UI memo inputs once per operation, including prewarm."""
from functools import wraps
from copy import copy
import hashlib
import threading

from .capability_cache import input_digest
from .perf import copy_tree


def _inputs(view):
    from .client_profile_view import COMPAT_REPORT
    raw = COMPAT_REPORT.read_bytes() if COMPAT_REPORT.is_file() else b""
    return input_digest(), hashlib.sha256(raw).digest()


def _artifacts():
    from .capability_cache import REPOSITORY
    from .capability_artifacts import artifact_digest
    return artifact_digest(REPOSITORY)


def kind_inputs(view):
    """Only concrete kind checks depend on real SWFs, once per operation."""
    if not getattr(view, "_artifacts_checked", False):
        view._artifact_digest = _artifacts()
        view._artifacts_checked = True
    return view._artifact_digest


def fresh_inputs(method):
    """Compute on a private snapshot, then publish only a verified generation.

    Nested calls share that snapshot's read-only trees. Only the outer caller
    receives a structural copy, avoiding copies for every row in a kind catalog.
    """
    @wraps(method)
    def call(self, *args, **kwargs):
        if getattr(self, "_input_snapshot", False):
            return method(self, *args, **kwargs)
        for _ in range(3):
            before = _inputs(self)
            with self._lock:
                if getattr(self, "_input_digest", None) != before:
                    self._registry = self._clients = self._default = self._report = None
                    self._compat.clear()
                    self._input_digest = before
                snapshot = copy(self)
                snapshot._lock = threading.RLock()
                snapshot._compat = dict(self._compat)
                snapshot._input_snapshot = True
                snapshot._artifacts_checked = False
            # Methods only replace their private cached values; their returned
            # containers are copied. No expensive parse/check holds the UI lock.
            value = method(snapshot, *args, **kwargs)
            if _inputs(self) != before:
                continue
            if snapshot._artifacts_checked and _artifacts() != snapshot._artifact_digest:
                continue
            with self._lock:
                if self._input_digest == before:
                    for field in ("_registry", "_clients", "_default", "_report"):
                        if getattr(snapshot, field) is not None:
                            setattr(self, field, getattr(snapshot, field))
                    self._compat.update(snapshot._compat)
                    if snapshot._artifacts_checked:
                        # Keep one artifact generation; catalog-only keys are
                        # independent of actual binaries and remain reusable.
                        self._compat = {key: value for key, value in self._compat.items()
                                        if not isinstance(key, tuple) or len(key) != 4
                                        or key[3] in (None, snapshot._artifact_digest)}
                else:
                    continue
            return copy_tree(value)
        raise ValueError("客户端能力输入在读取期间持续变化，请稍后重试")
    return call
