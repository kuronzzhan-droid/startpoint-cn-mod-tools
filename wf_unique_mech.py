"""Compatibility entry point: this tool now lives in ``wf/tools/content/unique_mech.py``.

``python wf_unique_mech.py ...`` and ``import wf_unique_mech`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.unique_mech")
else:
    from wf.tools.content import unique_mech as _implementation

    _sys.modules[__name__] = _implementation
