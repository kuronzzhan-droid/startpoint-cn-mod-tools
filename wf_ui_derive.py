"""Compatibility entry point: this tool now lives in ``wf/tools/art/ui_derive.py``.

``python wf_ui_derive.py ...`` and ``import wf_ui_derive`` keep working unchanged.
"""
import sys as _sys

if __name__ == "__main__":
    from wf.tools import run_as_main

    run_as_main("wf.tools.art.ui_derive")
else:
    import importlib as _importlib

    _sys.modules[__name__] = _importlib.import_module("wf.tools.art.ui_derive")
