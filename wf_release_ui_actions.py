"""Compatibility alias for the original A ``wf_release_ui_actions`` API."""
import sys as _sys
from wf.compat import release_ui_actions as _implementation

_sys.modules[__name__] = _implementation
