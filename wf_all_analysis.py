"""Compatibility entry point: this tool now lives in ``wf/tools/core/all_analysis.py``.

``python wf_all_analysis.py ...`` and ``import wf_all_analysis`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.core.all_analysis")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.core.all_analysis")
