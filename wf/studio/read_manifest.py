"""Bind read caches to the loaded chain while allowing later chain tips."""
from pathlib import Path
import hashlib
import threading


def _files(paths):
    result = []
    for path in sorted(set(paths), key=str):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except FileNotFoundError:
            digest = None
        result.append((str(path), digest))
    return tuple(result)


class ReadManifestInputs:
    def __init__(self, view):
        self.view = view
        self.paths = [Path(p) for p in [getattr(view, "manifest", None),
                      *(getattr(view, "manifests", ()) or ())] if p is not None]
        self.search = (getattr(view, "search_dirs", ())
                       if getattr(view, "manifests", None) is None else ())
        self.initial = self._snapshot()
        self.validated = None
        self.lock = threading.RLock()

    def _snapshot(self):
        discovered = (p for directory in self.search for p in Path(directory).glob("manifest*.json")
                      if not p.name.startswith("manifest-entry-"))
        return _files(self.paths), _files(discovered)

    def current(self):
        with self.lock:
            for _ in range(3):
                snapshot = self._snapshot()
                verify = getattr(self.view, "verify_chain", None)
                if verify is not None and snapshot != self.validated:
                    # Compare against edges bound at view construction, including
                    # on the first request; a later tip is outside that chain.
                    verify()
                    if self._snapshot() != snapshot:
                        continue
                    self.validated = snapshot
                elif verify is None and snapshot != self.initial:
                    raise ValueError("视图清单已变化，请重新加载编辑台视图后读取")
                return snapshot
            raise ValueError("视图清单在核验期间持续变化，请稍后重试")
