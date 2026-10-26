"""Compatibility entry point: this tool now lives in ``wf/tools/core/dsl_sig.py``.

``python wf_dsl_sig.py ...`` and ``import wf_dsl_sig`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.dsl_sig")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.dsl_sig")
