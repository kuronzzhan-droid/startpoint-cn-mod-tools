"""Compatibility entry point: this tool now lives in ``wf/tools/content/unique_mech.py``.

``python wf_unique_mech.py ...`` and ``import wf_unique_mech`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.content.unique_mech")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.content.unique_mech")
