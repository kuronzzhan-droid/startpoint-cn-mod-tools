"""Compatibility entry point: this tool now lives in ``wf/tools/rogue/rogue_banner.py``.

``python wf_rogue_banner.py ...`` and ``import wf_rogue_banner`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.rogue.rogue_banner")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.rogue.rogue_banner")
