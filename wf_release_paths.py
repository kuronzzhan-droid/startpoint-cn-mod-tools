"""Compatibility alias for the original A ``wf_release_paths`` API."""
import sys as _sys
from wf.compat import release_paths as _implementation

_sys.modules[__name__] = _implementation
