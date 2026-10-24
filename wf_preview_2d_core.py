"""Compatibility alias for the original A ``wf_preview_2d_core`` API."""
import sys as _sys
from wf.compat import preview_2d_core as _implementation

_sys.modules[__name__] = _implementation
