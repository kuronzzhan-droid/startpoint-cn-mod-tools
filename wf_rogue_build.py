"""Compatibility entry point: this tool now lives in ``wf/tools/rogue/rogue_build.py``.

``python wf_rogue_build.py ...`` and ``import wf_rogue_build`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.rogue.rogue_build")
else:
    from wf.tools.rogue import rogue_build as _implementation

    _sys.modules[__name__] = _implementation
