"""Compatibility alias for the original A ``wf_flatomo_compile`` API."""
import sys as _sys
from wf.compat import flatomo_compile as _implementation

_sys.modules[__name__] = _implementation
