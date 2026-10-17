"""Compatibility alias for the original A ``wf_tool_distribution`` API."""
import sys as _sys
from wf.compat import tool_distribution as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

_sys.modules[__name__] = _implementation
