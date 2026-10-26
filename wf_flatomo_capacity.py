"""Compatibility entry point: this tool now lives in ``wf/tools/art/flatomo_capacity.py``.

``python wf_flatomo_capacity.py ...`` and ``import wf_flatomo_capacity`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.flatomo_capacity")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.flatomo_capacity")
