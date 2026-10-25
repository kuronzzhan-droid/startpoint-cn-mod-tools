"""Compatibility entry point: this tool now lives in ``wf/tools/core/wfx_registry.py``.

``python wfx_registry.py ...`` and ``import wfx_registry`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.wfx_registry")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.wfx_registry")
