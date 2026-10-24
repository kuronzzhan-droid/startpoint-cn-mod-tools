"""Compatibility alias for the original A ``wf_apk_paths`` API."""
import sys as _sys
from wf.compat import apk_paths as _implementation

_sys.modules[__name__] = _implementation
