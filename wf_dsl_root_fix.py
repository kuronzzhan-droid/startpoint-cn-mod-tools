"""Compatibility entry point: this tool now lives in ``wf/tools/core/dsl_root_fix.py``.

``python wf_dsl_root_fix.py ...`` and ``import wf_dsl_root_fix`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.dsl_root_fix")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.dsl_root_fix")
