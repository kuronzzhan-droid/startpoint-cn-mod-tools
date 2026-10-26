"""Compatibility alias for the original A ``wf_release_ui`` API."""
import sys as _sys
from wf.compat import release_ui as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

_sys.modules[__name__] = _implementation
