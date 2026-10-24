"""Compatibility alias for the original A ``wf_character_ui_compile`` API."""
import sys as _sys
from wf.compat import character_ui_compile as _implementation

_sys.modules[__name__] = _implementation
