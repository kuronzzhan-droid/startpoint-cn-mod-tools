"""Compatibility entry point: this tool now lives in ``wf/tools/art/atlas_budget_check.py``.

``python wf_atlas_budget_check.py ...`` and ``import wf_atlas_budget_check`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.atlas_budget_check")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.atlas_budget_check")
