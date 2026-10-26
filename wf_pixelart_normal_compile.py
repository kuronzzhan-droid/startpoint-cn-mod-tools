"""Compatibility alias for the original A ``wf_pixelart_normal_compile`` API."""
import sys as _sys
from wf.compat import pixelart_normal_compile as _implementation

_sys.modules[__name__] = _implementation
