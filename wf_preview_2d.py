"""Compatibility alias for the original A ``wf_preview_2d`` API."""
import sys as _sys
from wf.compat import preview_2d as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

_sys.modules[__name__] = _implementation
