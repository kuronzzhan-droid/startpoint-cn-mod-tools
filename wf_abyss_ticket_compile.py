"""Compatibility alias for the parameterized A ``wf_abyss_ticket_compile`` API."""
import sys as _sys
from wf.compat import abyss_ticket_compile as _implementation

_sys.modules[__name__] = _implementation
